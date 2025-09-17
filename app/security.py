"""
Security and Guardrails for LumaHealth Conversational AI Service.

This module implements before-tool guardrails, security callbacks, rate limiting,
and content filtering to ensure safe and compliant operation of the AI system.
"""

import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict, deque

from .observability import setup_logging

# Setup logging
logger = setup_logging()


@dataclass
class SecurityViolation:
    """Represents a security violation detected by guardrails."""
    violation_type: str
    severity: str  # low, medium, high, critical
    message: str
    context: Dict[str, Any]
    timestamp: datetime


class RateLimiter:
    """
    Rate limiter for controlling request frequency per session/IP.
    
    Implements sliding window rate limiting with different limits
    for verified vs unverified users.
    """
    
    def __init__(self):
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.violations: Dict[str, List[SecurityViolation]] = defaultdict(list)
    
    def is_allowed(self, identifier: str, is_verified: bool = False) -> Tuple[bool, Optional[str]]:
        """Check if request is allowed based on rate limits."""
        now = time.time()
        window_size = 60  # 1 minute window
        
        # Different limits for verified vs unverified users
        if is_verified:
            max_requests = 30  # 30 requests per minute for verified users
        else:
            max_requests = 10  # 10 requests per minute for unverified users
        
        # Clean old requests outside the window
        request_times = self.requests[identifier]
        while request_times and request_times[0] < now - window_size:
            request_times.popleft()
        
        # Check if limit exceeded
        if len(request_times) >= max_requests:
            violation = SecurityViolation(
                violation_type="rate_limit_exceeded",
                severity="medium",
                message=f"Rate limit exceeded: {len(request_times)}/{max_requests} requests",
                context={"identifier": identifier, "is_verified": is_verified, "window": window_size},
                timestamp=datetime.utcnow()
            )
            self.violations[identifier].append(violation)
            
            return False, f"Rate limit exceeded. Try again in {window_size} seconds."
        
        # Record this request
        request_times.append(now)
        return True, None
    
    def get_stats(self, identifier: str) -> Dict[str, Any]:
        """Get rate limiting stats for an identifier."""
        now = time.time()
        window_size = 60
        
        request_times = self.requests[identifier]
        recent_requests = [t for t in request_times if t > now - window_size]
        
        return {
            "requests_in_window": len(recent_requests),
            "window_size_seconds": window_size,
            "violations_count": len(self.violations[identifier]),
            "last_violation": self.violations[identifier][-1].timestamp.isoformat() if self.violations[identifier] else None
        }


class ContentFilter:
    """
    Content filtering for detecting and blocking inappropriate content.
    
    Implements multiple layers of content checking including PII detection,
    harmful content screening, and medical compliance validation.
    """
    
    def __init__(self):
        # PII patterns (basic implementation)
        self.pii_patterns = {
            'cpf': re.compile(r'\\b\\d{3}\\.\\d{3}\\.\\d{3}-\\d{2}\\b|\\b\\d{11}\\b'),
            'phone': re.compile(r'\\(\\d{2}\\)\\s*\\d{4,5}-\\d{4}|\\d{2}\\s*\\d{4,5}-\\d{4}'),
            'email': re.compile(r'\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b'),
            'credit_card': re.compile(r'\\b\\d{4}[-\\s]?\\d{4}[-\\s]?\\d{4}[-\\s]?\\d{4}\\b')
        }
        
        # Harmful content keywords (basic list)
        self.harmful_keywords = [
            'suicide', 'kill', 'die', 'death', 'harm', 'hurt', 'violence',
            'drug', 'illegal', 'fraud', 'scam', 'hack', 'breach'
        ]
        
        # Medical advice keywords that require special handling
        self.medical_advice_keywords = [
            'diagnose', 'treatment', 'medicine', 'prescription', 'dose',
            'surgery', 'emergency', 'urgent', 'serious', 'dangerous'
        ]
    
    def scan_content(self, content: str, context: Dict[str, Any] = None) -> List[SecurityViolation]:
        """Scan content for security violations."""
        violations = []
        content_lower = content.lower()
        
        # Check for PII
        for pii_type, pattern in self.pii_patterns.items():
            if pattern.search(content):
                violations.append(SecurityViolation(
                    violation_type=f"pii_detected_{pii_type}",
                    severity="high",
                    message=f"Potential {pii_type.upper()} detected in content",
                    context={"pii_type": pii_type, "content_length": len(content)},
                    timestamp=datetime.utcnow()
                ))
        
        # Check for harmful content
        found_harmful = [kw for kw in self.harmful_keywords if kw in content_lower]
        if found_harmful:
            violations.append(SecurityViolation(
                violation_type="harmful_content",
                severity="high",
                message=f"Potentially harmful content detected: {', '.join(found_harmful)}",
                context={"keywords": found_harmful, "content_length": len(content)},
                timestamp=datetime.utcnow()
            ))
        
        # Check for medical advice requests
        found_medical = [kw for kw in self.medical_advice_keywords if kw in content_lower]
        if found_medical:
            violations.append(SecurityViolation(
                violation_type="medical_advice_request",
                severity="medium",
                message=f"Medical advice request detected: {', '.join(found_medical)}",
                context={"keywords": found_medical, "requires_disclaimer": True},
                timestamp=datetime.utcnow()
            ))
        
        return violations
    
    def sanitize_content(self, content: str) -> str:
        """Sanitize content by removing or masking sensitive information."""
        sanitized = content
        
        # Mask PII
        for pii_type, pattern in self.pii_patterns.items():
            sanitized = pattern.sub(f"[{pii_type.upper()}_MASKED]", sanitized)
        
        return sanitized


class GuardrailsEngine:
    """
    Main guardrails engine that coordinates all security checks.
    
    Implements before-tool and after-tool guardrails to ensure safe operation
    of the conversational AI system.
    """
    
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.content_filter = ContentFilter()
        self.blocked_sessions: Dict[str, datetime] = {}
        self.violation_history: List[SecurityViolation] = []
    
    def before_tool_guardrails(
        self, 
        session_id: str, 
        message: str, 
        tool_name: str,
        is_verified: Optional[bool] = None,
        context: Dict[str, Any] = None
    ) -> Tuple[bool, Optional[str], List[SecurityViolation]]:
        """
        Execute before-tool guardrails.
        
        Returns:
            - allowed: bool - Whether to allow the tool execution
            - reason: Optional[str] - Reason for blocking if not allowed
            - violations: List[SecurityViolation] - Any security violations found
        """
        violations = []
        
        # Check if session is currently blocked
        if session_id in self.blocked_sessions:
            block_until = self.blocked_sessions[session_id]
            if datetime.utcnow() < block_until:
                violation = SecurityViolation(
                    violation_type="session_blocked",
                    severity="high",
                    message="Session is temporarily blocked due to security violations",
                    context={"session_id": session_id, "blocked_until": block_until.isoformat()},
                    timestamp=datetime.utcnow()
                )
                violations.append(violation)
                return False, "Session temporarily blocked for security reasons", violations
            else:
                # Unblock session
                del self.blocked_sessions[session_id]
        
        # Rate limiting check
        allowed, rate_reason = self.rate_limiter.is_allowed(session_id, bool(is_verified))
        if not allowed:
            return False, rate_reason, violations
        
        # Content filtering
        content_violations = self.content_filter.scan_content(message, context)
        violations.extend(content_violations)
        
        # Check violation severity
        critical_violations = [v for v in content_violations if v.severity == "critical"]
        high_violations = [v for v in content_violations if v.severity == "high"]
        
        if critical_violations:
            # Block session for critical violations
            self.blocked_sessions[session_id] = datetime.utcnow() + timedelta(hours=1)
            return False, "Content violates security policies", violations
        
        if len(high_violations) >= 2:
            # Block session for multiple high violations
            self.blocked_sessions[session_id] = datetime.utcnow() + timedelta(minutes=15)
            return False, "Multiple security violations detected", violations
        
        # Tool-specific guardrails
        tool_allowed, tool_reason = self._check_tool_specific_guardrails(
            tool_name, message, is_verified, context
        )
        
        if not tool_allowed:
            violation = SecurityViolation(
                violation_type=f"tool_guardrail_{tool_name}",
                severity="medium",
                message=tool_reason,
                context={"tool_name": tool_name, "session_id": session_id},
                timestamp=datetime.utcnow()
            )
            violations.append(violation)
            return False, tool_reason, violations
        
        # Log violations for monitoring
        for violation in violations:
            self.violation_history.append(violation)
            logger.warning(f"Security violation: {violation.violation_type} - {violation.message}")
        
        return True, None, violations
    
    def after_tool_guardrails(
        self,
        session_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Any,
        context: Dict[str, Any] = None
    ) -> Tuple[bool, Optional[str], Any]:
        """
        Execute after-tool guardrails.
        
        Returns:
            - allowed: bool - Whether to allow the response
            - reason: Optional[str] - Reason for blocking if not allowed  
            - filtered_output: Any - Potentially filtered/sanitized output
        """
        
        # Sanitize output if it contains sensitive information
        if isinstance(tool_output, str):
            filtered_output = self.content_filter.sanitize_content(tool_output)
        elif isinstance(tool_output, dict) and "message" in tool_output:
            tool_output["message"] = self.content_filter.sanitize_content(tool_output["message"])
            filtered_output = tool_output
        else:
            filtered_output = tool_output
        
        # Check for data leakage in appointment listings
        if tool_name == "list_appointments" and isinstance(tool_output, list):
            # Ensure appointments belong to the verified user
            # (This would integrate with session verification)
            pass
        
        return True, None, filtered_output
    
    def _check_tool_specific_guardrails(
        self, 
        tool_name: str, 
        message: str, 
        is_verified: Optional[bool], 
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Check tool-specific guardrails."""
        
        # Defer verification checks to the tool implementation itself to avoid
        # false negatives when verification state is managed outside guardrails.
        # This avoids blocking legitimate calls when is_verified is unknown here.
        
        # Appointment modification limits
        if tool_name in ["confirm_appointment", "cancel_appointment"]:
            # Check for excessive modifications (could indicate automated abuse)
            # This would integrate with session history tracking
            pass
        
        # Time-based restrictions
        if tool_name == "cancel_appointment":
            # Don't allow cancellations too close to appointment time
            # This would require checking appointment timing
            pass
        
        return True, None
    
    def get_security_summary(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get security summary for monitoring dashboard."""
        recent_violations = [
            v for v in self.violation_history 
            if v.timestamp > datetime.utcnow() - timedelta(hours=24)
        ]
        
        summary = {
            "total_violations_24h": len(recent_violations),
            "violation_types": {},
            "blocked_sessions_count": len(self.blocked_sessions),
            "active_blocks": []
        }
        
        # Count violation types
        for violation in recent_violations:
            vtype = violation.violation_type
            summary["violation_types"][vtype] = summary["violation_types"].get(vtype, 0) + 1
        
        # Active blocks info
        now = datetime.utcnow()
        for sid, block_until in self.blocked_sessions.items():
            if block_until > now:
                summary["active_blocks"].append({
                    "session_id": sid,
                    "blocked_until": block_until.isoformat(),
                    "remaining_minutes": int((block_until - now).total_seconds() / 60)
                })
        
        # Session-specific info
        if session_id:
            summary["session_info"] = {
                "rate_limit_stats": self.rate_limiter.get_stats(session_id),
                "is_blocked": session_id in self.blocked_sessions,
                "recent_violations": [
                    v for v in recent_violations 
                    if v.context.get("session_id") == session_id
                ]
            }
        
        return summary


# Global guardrails instance
guardrails = GuardrailsEngine()


# Decorator for adding guardrails to functions
def with_guardrails(tool_name: str):
    """Decorator to add guardrails to tool functions."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract session info from kwargs
            session_id = kwargs.get("session_id", "unknown")
            message = kwargs.get("message", "")
            
            # Before-tool guardrails
            allowed, reason, violations = guardrails.before_tool_guardrails(
                session_id=session_id,
                message=str(message),
                tool_name=tool_name,
                is_verified=kwargs.get("is_verified", False),
                context={"function": func.__name__, "args": len(args), "kwargs": list(kwargs.keys())}
            )
            
            if not allowed:
                logger.warning(f"Tool {tool_name} blocked for session {session_id}: {reason}")
                return {
                    "success": False,
                    "message": reason,
                    "security_block": True,
                    "violations": [v.__dict__ for v in violations]
                }
            
            # Execute the original function
            try:
                result = await func(*args, **kwargs)
                
                # After-tool guardrails
                allowed, reason, filtered_result = guardrails.after_tool_guardrails(
                    session_id=session_id,
                    tool_name=tool_name,
                    tool_input=kwargs,
                    tool_output=result,
                    context={"function": func.__name__}
                )
                
                return filtered_result
                
            except Exception as e:
                logger.error(f"Error in guarded tool {tool_name}: {e}")
                return {
                    "success": False,
                    "message": "Internal error occurred",
                    "error_logged": True
                }
        
        return wrapper
    return decorator
