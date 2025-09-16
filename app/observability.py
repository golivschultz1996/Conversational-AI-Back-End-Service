"""
Observability module for the LumaHealth Conversational AI Service.

This module provides structured logging, metrics collection, and request tracing
for monitoring and debugging the conversational AI system.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional
from contextlib import contextmanager

import structlog
from structlog.processors import JSONRenderer


# Configure structured logging
def setup_logging(log_level: str = "INFO") -> structlog.BoundLogger:
    """
    Setup structured logging with JSON output.
    
    Returns configured logger instance for the application.
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=None,
        level=getattr(logging, log_level.upper())
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    return structlog.get_logger("lumahealth.api")


# Global logger instance
logger = setup_logging()


class RequestMetrics:
    """
    Simple in-memory metrics collector for request statistics.
    
    In production, this would integrate with Prometheus, DataDog, etc.
    """
    
    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.total_latency_ms = 0
        self.intent_counts = {}
        self.tool_usage = {}
        self.session_stats = {}
    
    def record_request(self, intent: str, latency_ms: int, success: bool, tools_used: list = None):
        """Record request metrics."""
        self.request_count += 1
        self.total_latency_ms += latency_ms
        
        if not success:
            self.error_count += 1
        
        # Track intent frequency
        self.intent_counts[intent] = self.intent_counts.get(intent, 0) + 1
        
        # Track tool usage
        if tools_used:
            for tool in tools_used:
                self.tool_usage[tool] = self.tool_usage.get(tool, 0) + 1
    
    def get_metrics(self) -> dict:
        """Get current metrics summary."""
        avg_latency = (
            self.total_latency_ms / self.request_count 
            if self.request_count > 0 else 0
        )
        
        success_rate = (
            (self.request_count - self.error_count) / self.request_count * 100
            if self.request_count > 0 else 0
        )
        
        return {
            "request_count": self.request_count,
            "error_count": self.error_count,
            "success_rate_percent": round(success_rate, 2),
            "average_latency_ms": round(avg_latency, 2),
            "intent_counts": self.intent_counts,
            "tool_usage": self.tool_usage,
            "timestamp": datetime.utcnow().isoformat()
        }


# Global metrics instance
metrics = RequestMetrics()


def log_request(
    session_id: str,
    intent: str,
    message: str,
    response: str,
    latency_ms: int,
    success: bool,
    tools_used: Optional[list] = None,
    patient_id: Optional[int] = None,
    additional_context: Optional[dict] = None
) -> None:
    """
    Log a conversational AI request with full context.
    
    This function masks PII and provides structured logging for observability.
    """
    # Mask PII in message and response
    masked_message = mask_pii(message)
    masked_response = mask_pii(response)
    
    # Build log context
    log_context = {
        "session_id": session_id,
        "intent": intent,
        "message_length": len(message),
        "response_length": len(response),
        "latency_ms": latency_ms,
        "success": success,
        "tools_used": tools_used or [],
        "patient_id": patient_id,  # Already anonymized ID
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Add additional context if provided
    if additional_context:
        log_context.update(additional_context)
    
    # Log the interaction
    if success:
        logger.info(
            "Conversational AI request processed",
            **log_context,
            masked_message=masked_message[:100],  # Truncate for logs
            masked_response=masked_response[:200]
        )
    else:
        logger.error(
            "Conversational AI request failed",
            **log_context,
            masked_message=masked_message[:100],
            error_response=masked_response[:200]
        )
    
    # Record metrics
    metrics.record_request(intent, latency_ms, success, tools_used)


def mask_pii(text: str) -> str:
    """
    Mask personally identifiable information in text.
    
    This is a simple implementation - in production, use more sophisticated
    PII detection and masking techniques.
    """
    if not text:
        return text
    
    import re
    
    # Mask common PII patterns
    # Phone numbers
    text = re.sub(r'\b\d{10,11}\b', '[PHONE]', text)
    text = re.sub(r'\(\d{3}\)\s*\d{3}-\d{4}', '[PHONE]', text)
    
    # Email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
    
    # Dates (conservative masking)
    text = re.sub(r'\b\d{1,2}/\d{1,2}/\d{4}\b', '[DATE]', text)
    text = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', '[DATE]', text)
    
    # Names (very conservative - only mask common patterns)
    # In production, use NER models for better name detection
    
    return text


@contextmanager
def trace_operation(operation_name: str, **context):
    """
    Context manager for tracing operations with timing and logging.
    
    Usage:
        with trace_operation("verify_user", session_id="123"):
            # Your operation here
            pass
    """
    start_time = time.time()
    operation_id = f"{operation_name}_{int(start_time * 1000)}"
    
    logger.info(
        f"Starting operation: {operation_name}",
        operation_id=operation_id,
        **context
    )
    
    try:
        yield operation_id
        
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"Completed operation: {operation_name}",
            operation_id=operation_id,
            duration_ms=duration_ms,
            success=True,
            **context
        )
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            f"Failed operation: {operation_name}",
            operation_id=operation_id,
            duration_ms=duration_ms,
            success=False,
            error=str(e),
            **context
        )
        raise


def log_conversation_flow(session_id: str, flow_steps: list) -> None:
    """
    Log the complete conversation flow for a session.
    
    Useful for understanding user journeys and debugging conversation paths.
    """
    logger.info(
        "Conversation flow completed",
        session_id=session_id,
        flow_steps=flow_steps,
        step_count=len(flow_steps),
        timestamp=datetime.utcnow().isoformat()
    )


def get_observability_summary() -> dict:
    """
    Get comprehensive observability summary for monitoring dashboards.
    """
    return {
        "metrics": metrics.get_metrics(),
        "system_info": {
            "timestamp": datetime.utcnow().isoformat(),
            "version": "0.1.0"
        }
    }
