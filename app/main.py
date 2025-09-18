"""
FastAPI main application for LumaHealth Conversational AI Service.

This module provides the REST API endpoints for the conversational AI service,
supporting patient verification, appointment management, and session handling.
"""

import os
import uuid
from datetime import datetime
from typing import Dict, Optional
from contextlib import asynccontextmanager

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from .db import create_db_and_tables, get_session, seed_database, PatientCRUD, AppointmentCRUD
from .models import (
    ChatRequest, ChatResponse, VerifyUserRequest, VerifyUserResponse,
    AppointmentResponse, ConfirmAppointmentRequest, CancelAppointmentRequest,
    ActionResponse, AppointmentStatus, Patient
)
from .session_manager import SessionManager
from .observability import setup_logging, log_request
from .graph import LumaHealthAgent
from .settings import settings
from .security import guardrails

# Setup structured logging
logger = setup_logging()

# Global session manager (in-memory for MVP)
session_manager = SessionManager()

# Global LangGraph agent (will be initialized in lifespan)
langgraph_agent: Optional[LumaHealthAgent] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    global langgraph_agent
    
    # Startup
    logger.info("Starting LumaHealth Conversational AI Service")
    create_db_and_tables()
    seed_database()
    logger.info("Database initialized and seeded")
    
    # Initialize LangGraph Agent with Claude
    anthropic_api_key = settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY")
    if anthropic_api_key:
        try:
            langgraph_agent = LumaHealthAgent(anthropic_api_key, session_manager)
            logger.info("LangGraph Agent with Claude initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LangGraph Agent: {e}")
            logger.warning("Falling back to simple NLU mode")
    else:
        logger.warning("ANTHROPIC_API_KEY not found - using simple NLU mode")
    
    yield
    
    # Shutdown
    logger.info("Shutting down LumaHealth Conversational AI Service")


# FastAPI application
app = FastAPI(
    title="LumaHealth Conversational AI Service",
    description="A conversational AI back-end service for healthcare appointment management",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# Utility functions
def format_appointment_response(appointment) -> AppointmentResponse:
    """Format appointment data for API response."""
    return AppointmentResponse(
        id=appointment.id,
        when_utc=appointment.when_utc,
        location=appointment.location,
        status=appointment.status,
        doctor_name=appointment.doctor_name,
        formatted_datetime=appointment.when_utc.strftime("%Y-%m-%d %H:%M")
    )


# Web UI HTML Template
WEB_UI_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LumaHealth - Assistente de Consultas</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #333;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            width: 90%;
            max-width: 600px;
            min-height: 600px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .header {
            background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 20px;
            text-align: center;
        }
        .header h1 { font-size: 1.8rem; margin-bottom: 5px; }
        .header p { opacity: 0.9; font-size: 0.9rem; }
        .chat-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            padding: 20px;
        }
        .messages {
            flex: 1;
            overflow-y: auto;
            margin-bottom: 20px;
            min-height: 300px;
            max-height: 400px;
            padding-right: 10px;
        }
        .message {
            margin-bottom: 15px;
            padding: 12px 16px;
            border-radius: 18px;
            max-width: 80%;
            word-wrap: break-word;
            animation: fadeIn 0.3s ease-in;
        }
        .user-message {
            background: #007bff;
            color: white;
            margin-left: auto;
            border-bottom-right-radius: 5px;
        }
        .bot-message {
            background: #f1f3f4;
            color: #333;
            border-bottom-left-radius: 5px;
        }
        .input-area {
            display: flex;
            gap: 10px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 15px;
        }
        .input-area input {
            flex: 1;
            padding: 12px 16px;
            border: 2px solid #e9ecef;
            border-radius: 25px;
            font-size: 16px;
            outline: none;
            transition: border-color 0.3s;
        }
        .input-area input:focus { border-color: #007bff; }
        .input-area button {
            padding: 12px 24px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-weight: 600;
            transition: background 0.3s;
        }
        .input-area button:hover { background: #0056b3; }
        .input-area button:disabled {
            background: #6c757d;
            cursor: not-allowed;
        }
        .typing-indicator {
            display: none;
            padding: 10px 16px;
            background: #f1f3f4;
            border-radius: 18px;
            margin-bottom: 15px;
            max-width: 80px;
        }
        .typing-dots { display: flex; gap: 4px; }
        .typing-dots span {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #999;
            animation: typing 1.4s infinite;
        }
        .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
        .typing-dots span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes typing { 0%, 60%, 100% { transform: translateY(0); } 30% { transform: translateY(-10px); } }
        .status { 
            text-align: center; 
            color: #666; 
            font-size: 0.9rem; 
            margin-bottom: 10px;
            padding: 8px;
            background: #f8f9fa;
            border-radius: 10px;
        }
        .welcome {
            text-align: center;
            color: #666;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 15px;
            margin-bottom: 20px;
        }
        .welcome h3 { color: #007bff; margin-bottom: 10px; }
        .examples {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: center;
            margin-top: 15px;
        }
        .example-btn {
            background: #e3f2fd;
            color: #1976d2;
            border: none;
            padding: 8px 12px;
            border-radius: 15px;
            cursor: pointer;
            font-size: 0.8rem;
            transition: all 0.3s;
        }
        .example-btn:hover {
            background: #bbdefb;
            transform: translateY(-1px);
        }
        .session-info {
            font-size: 0.8rem;
            color: #666;
            text-align: center;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏥 LumaHealth</h1>
            <p>Intelligent Appointment Assistant</p>
        </div>
        
        <div class="chat-container">
            <div class="session-info" id="sessionInfo">Session: Starting...</div>
            
            <div class="welcome" id="welcome">
                <h3>👋 Welcome!</h3>
                <p>I'm your assistant for medical appointment management.</p>
                <p><strong>Examples of what I can do:</strong></p>
                <div class="examples">
                    <button class="example-btn" onclick="sendExample('I am John Silva, born on 03/15/1985')">✅ Verify identity</button>
                    <button class="example-btn" onclick="sendExample('List my appointments')">📋 View appointments</button>
                    <button class="example-btn" onclick="sendExample('Confirm appointment')">✅ Confirm</button>
                    <button class="example-btn" onclick="sendExample('Cancel appointment')">❌ Cancel</button>
                </div>
            </div>
            
            <div class="messages" id="messages"></div>
            
            <div class="typing-indicator" id="typingIndicator">
                <div class="typing-dots">
                    <span></span><span></span><span></span>
                </div>
            </div>
            
            <div class="input-area">
                <input type="text" id="messageInput" placeholder="Type your message..." onkeypress="handleKeyPress(event)">
                <button onclick="sendMessage()" id="sendBtn">Send</button>
            </div>
        </div>
    </div>

    <script>
        let sessionId = null;
        let messageCount = 0;
        
        // Initialize session
        function initSession() {
            sessionId = 'web-' + Math.random().toString(36).substr(2, 9);
            document.getElementById('sessionInfo').textContent = `Session: ${sessionId.substr(-6)}`;
        }
        
        // Send example message
        function sendExample(message) {
            document.getElementById('messageInput').value = message;
            sendMessage();
        }
        
        // Handle enter key
        function handleKeyPress(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
            }
        }
        
        // Add message to chat
        function addMessage(content, isUser = false) {
            const messagesDiv = document.getElementById('messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
            messageDiv.textContent = content;
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            
            // Hide welcome after first message
            if (messageCount === 0) {
                document.getElementById('welcome').style.display = 'none';
            }
            messageCount++;
        }
        
        // Show/hide typing indicator
        function showTyping(show) {
            document.getElementById('typingIndicator').style.display = show ? 'block' : 'none';
            if (show) {
                document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
            }
        }
        
        // Send message to API
        async function sendMessage() {
            const input = document.getElementById('messageInput');
            const sendBtn = document.getElementById('sendBtn');
            const message = input.value.trim();
            
            if (!message) return;
            
            // Disable input
            input.disabled = true;
            sendBtn.disabled = true;
            
            // Add user message
            addMessage(message, true);
            input.value = '';
            
            // Show typing indicator
            showTyping(true);
            
            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        session_id: sessionId,
                        message: message
                    })
                });
                
                if (!response.ok) {
                    throw new Error('Server response error');
                }
                
                const data = await response.json();
                
                // Hide typing indicator
                showTyping(false);
                
                // Add bot response
                addMessage(data.reply);
                
                // Update session info if verification successful
                if (data.state && data.state.is_verified) {
                    document.getElementById('sessionInfo').innerHTML = 
                        `Session: ${sessionId.substr(-6)} <span style="color: green;">✅ Verified</span>`;
                }
                
            } catch (error) {
                console.error('Error:', error);
                showTyping(false);
                addMessage('Sorry, an error occurred. Please try again.');
            } finally {
                // Re-enable input
                input.disabled = false;
                sendBtn.disabled = false;
                input.focus();
            }
        }
        
        // Initialize on page load
        window.onload = function() {
            initSession();
            document.getElementById('messageInput').focus();
        };
    </script>
</body>
</html>
"""

# REST API Endpoints
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web UI for chat interface."""
    return WEB_UI_HTML

@app.get("/api/status")
async def api_status():
    """API status endpoint for health checks."""
    return {
        "message": "LumaHealth Conversational AI Service",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "langgraph_enabled": langgraph_agent is not None
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/security/summary")
async def security_summary(session_id: Optional[str] = None):
    """Get security and guardrails summary for monitoring."""
    summary = guardrails.get_security_summary(session_id)
    summary["service_info"] = {
        "langgraph_enabled": langgraph_agent is not None,
        "total_sessions": session_manager.get_session_count(),
        "verified_sessions": session_manager.get_verified_session_count()
    }
    return summary


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    db: Session = Depends(get_session)
):
    """
    Main chat endpoint for conversational interactions.
    
    This endpoint processes natural language requests using LangGraph + Claude
    or falls back to simple NLU if LangGraph is not available.
    """
    start_time = datetime.utcnow()
    
    # Generate or use existing session ID
    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        # Use LangGraph agent if available
        if langgraph_agent:
            logger.info(f"Processing with LangGraph Agent: {session_id}")
            
            result = await langgraph_agent.process_conversation(
                session_id=session_id,
                message=request.message
            )
            
            # Calculate response time
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Add latency to observability
            result["observability"]["latency_ms"] = latency_ms
            
            # Log the interaction
            log_request(
                session_id=session_id,
                intent=result["observability"].get("intent", "unknown"),
                message=request.message,
                response=result["reply"],
                latency_ms=latency_ms,
                success=True,
                tools_used=result["observability"].get("tools_used", [])
            )
            
            return ChatResponse(
                session_id=session_id,
                reply=result["reply"],
                state=result["state"],
                observability=result["observability"]
            )
        
        else:
            # Fallback to simple NLU (original implementation)
            logger.info(f"Processing with Simple NLU (fallback): {session_id}")
            
            # Get or create session state
            session_state = session_manager.get_or_create_session(session_id)
            
            # Simple intent detection
            message = request.message.lower().strip()
            
            if any(word in message for word in ["verificar", "verify", "sou", "nome"]):
                intent = "verify_user"
            elif any(word in message for word in ["listar", "list", "consultas", "appointments"]):
                intent = "list_appointments"
            elif any(word in message for word in ["confirmar", "confirm"]):
                intent = "confirm_appointment"
            elif any(word in message for word in ["cancelar", "cancel"]):
                intent = "cancel_appointment"
            else:
                intent = "unknown"
            
            # Update session state
            session_state.last_intent = intent
            session_state.last_activity = datetime.utcnow()
            session_manager.update_session(session_id, session_state)
            
            # Process based on intent
            if intent == "verify_user":
                reply = "To verify your identity, I need your full name and date of birth. Please provide this information."
                
            elif intent == "list_appointments":
                if not session_state.is_verified:
                    reply = "I need to verify your identity first. Please provide your full name and date of birth."
                else:
                    appointments = AppointmentCRUD.get_by_patient_id(db, session_state.patient_id)
                    if appointments:
                        apt_list = []
                        for apt in appointments:
                            apt_list.append({
                                "id": apt.id,
                                "date": apt.when_utc.strftime("%Y-%m-%d"),
                                "time": apt.when_utc.strftime("%H:%M"),
                                "doctor": apt.doctor_name,
                                "location": apt.location,
                                "status": apt.status
                            })
                        session_state.last_list = apt_list
                        session_manager.update_session(session_id, session_state)
                        
                        reply = f"You have {len(appointments)} appointment(s):\\n"
                        for i, apt in enumerate(apt_list, 1):
                            reply += f"{i}. {apt['date']} at {apt['time']} - {apt['doctor']} ({apt['status']})\\n"
                    else:
                        reply = "You have no scheduled appointments."
                        
            elif intent == "confirm_appointment":
                if not session_state.is_verified:
                    reply = "I need to verify your identity first."
                else:
                    reply = "To confirm an appointment, please specify which appointment you want to confirm (number or date)."
                    
            elif intent == "cancel_appointment":
                if not session_state.is_verified:
                    reply = "I need to verify your identity first."
                else:
                    reply = "To cancel an appointment, please specify which appointment you want to cancel (number or date)."
                    
            else:
                reply = "Sorry, I didn't understand. I can help you verify your identity, list your appointments, confirm or cancel appointments. How can I help you?"
            
            # Calculate response time
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Log the interaction
            log_request(
                session_id=session_id,
                intent=intent,
                message=request.message,
                response=reply,
                latency_ms=latency_ms,
                success=True,
                tools_used=["simple_nlu"]
            )
            
            return ChatResponse(
                session_id=session_id,
                reply=reply,
                state={
                    "is_verified": session_state.is_verified,
                    "last_intent": intent,
                    "patient_id": session_state.patient_id
                },
                observability={
                    "intent": intent,
                    "tools_used": ["simple_nlu"],
                    "latency_ms": latency_ms,
                    "mode": "fallback"
                }
            )
        
    except Exception as e:
        logger.error(f"Error processing chat request: {e}", exc_info=True)
        
        # Log the error
        log_request(
            session_id=session_id,
            intent="error",
            message=request.message,
            response=str(e),
            latency_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
            success=False
        )
        
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/verify", response_model=VerifyUserResponse)
async def verify_user(
    request: VerifyUserRequest,
    db: Session = Depends(get_session)
):
    """
    Verify user identity with full name and date of birth.
    
    This endpoint authenticates patients and establishes verified sessions.
    """
    try:
        # Look up patient by name and DOB
        patient = PatientCRUD.get_by_name_and_dob(
            db, request.full_name, request.dob
        )
        
        if patient:
            # Update session state
            session_state = session_manager.get_or_create_session(request.session_id)
            session_state.is_verified = True
            session_state.patient_id = patient.id
            session_manager.update_session(request.session_id, session_state)
            
            logger.info(f"User verified successfully: {request.session_id}")
            
            return VerifyUserResponse(
                success=True,
                message="Identity verification successful!",
                patient_id=patient.id
            )
        else:
            logger.warning(f"Verification failed for session: {request.session_id}")
            
            return VerifyUserResponse(
                success=False,
                message="Unable to verify your identity. Please check the information provided."
            )
            
    except Exception as e:
        logger.error(f"Error during verification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/appointments/{session_id}")
async def list_appointments(
    session_id: str,
    db: Session = Depends(get_session)
):
    """List appointments for a verified session."""
    session_state = session_manager.get_session(session_id)
    
    if not session_state or not session_state.is_verified:
        raise HTTPException(status_code=401, detail="Session not verified")
    
    try:
        appointments = AppointmentCRUD.get_by_patient_id(db, session_state.patient_id)
        return [format_appointment_response(apt) for apt in appointments]
        
    except Exception as e:
        logger.error(f"Error listing appointments: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/confirm", response_model=ActionResponse)
async def confirm_appointment(
    request: ConfirmAppointmentRequest,
    db: Session = Depends(get_session)
):
    """Confirm an appointment."""
    session_state = session_manager.get_session(request.session_id)
    
    if not session_state or not session_state.is_verified:
        raise HTTPException(status_code=401, detail="Session not verified")
    
    try:
        if request.appointment_id:
            appointment = AppointmentCRUD.confirm_appointment(
                db, request.appointment_id, session_state.patient_id
            )
            
            if appointment:
                return ActionResponse(
                    success=True,
                    message="Consulta confirmada com sucesso!",
                    appointment=format_appointment_response(appointment)
                )
            else:
                return ActionResponse(
                    success=False,
                    message="Não foi possível confirmar a consulta."
                )
        else:
            return ActionResponse(
                success=False,
                message="ID da consulta é obrigatório."
            )
            
    except Exception as e:
        logger.error(f"Error confirming appointment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/cancel", response_model=ActionResponse)
async def cancel_appointment(
    request: CancelAppointmentRequest,
    db: Session = Depends(get_session)
):
    """Cancel an appointment."""
    session_state = session_manager.get_session(request.session_id)
    
    if not session_state or not session_state.is_verified:
        raise HTTPException(status_code=401, detail="Session not verified")
    
    try:
        if request.appointment_id:
            appointment = AppointmentCRUD.cancel_appointment(
                db, request.appointment_id, session_state.patient_id
            )
            
            if appointment:
                return ActionResponse(
                    success=True,
                    message="Consulta cancelada com sucesso!",
                    appointment=format_appointment_response(appointment)
                )
            else:
                return ActionResponse(
                    success=False,
                    message="Não foi possível cancelar a consulta."
                )
        else:
            return ActionResponse(
                success=False,
                message="ID da consulta é obrigatório."
            )
            
    except Exception as e:
        logger.error(f"Error cancelling appointment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )
