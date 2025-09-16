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

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlmodel import Session

from .db import create_db_and_tables, get_session, seed_database, PatientCRUD, AppointmentCRUD
from .models import (
    ChatRequest, ChatResponse, VerifyUserRequest, VerifyUserResponse,
    AppointmentResponse, ConfirmAppointmentRequest, CancelAppointmentRequest,
    ActionResponse, AppointmentStatus, Patient
)
from .session_manager import SessionManager
from .observability import setup_logging, log_request

# Setup structured logging
logger = setup_logging()

# Global session manager (in-memory for MVP)
session_manager = SessionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting LumaHealth Conversational AI Service")
    create_db_and_tables()
    seed_database()
    logger.info("Database initialized and seeded")
    
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
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
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


# REST API Endpoints
@app.get("/")
async def root():
    """Root endpoint providing API information."""
    return {
        "message": "LumaHealth Conversational AI Service",
        "version": "0.1.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    db: Session = Depends(get_session)
):
    """
    Main chat endpoint for conversational interactions.
    
    This endpoint processes natural language requests and routes them
    to appropriate actions (verify, list, confirm, cancel).
    """
    start_time = datetime.utcnow()
    
    # Generate or use existing session ID
    session_id = request.session_id or str(uuid.uuid4())
    
    # Get or create session state
    session_state = session_manager.get_or_create_session(session_id)
    
    try:
        # Simple intent detection (will be replaced with LangGraph)
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
            reply = "Para verificar sua identidade, preciso do seu nome completo e data de nascimento. Por favor, forneça essas informações."
            
        elif intent == "list_appointments":
            if not session_state.is_verified:
                reply = "Primeiro preciso verificar sua identidade. Por favor, forneça seu nome completo e data de nascimento."
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
                    
                    reply = f"Você tem {len(appointments)} consulta(s):\\n"
                    for i, apt in enumerate(apt_list, 1):
                        reply += f"{i}. {apt['date']} às {apt['time']} - {apt['doctor']} ({apt['status']})\\n"
                else:
                    reply = "Você não tem consultas agendadas."
                    
        elif intent == "confirm_appointment":
            if not session_state.is_verified:
                reply = "Primeiro preciso verificar sua identidade."
            else:
                reply = "Para confirmar uma consulta, por favor especifique qual consulta deseja confirmar (número ou data)."
                
        elif intent == "cancel_appointment":
            if not session_state.is_verified:
                reply = "Primeiro preciso verificar sua identidade."
            else:
                reply = "Para cancelar uma consulta, por favor especifique qual consulta deseja cancelar (número ou data)."
                
        else:
            reply = "Desculpe, não entendi. Posso ajudar você a verificar sua identidade, listar suas consultas, confirmar ou cancelar consultas. Como posso ajudar?"
        
        # Calculate response time
        latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        # Log the interaction
        log_request(
            session_id=session_id,
            intent=intent,
            message=request.message,
            response=reply,
            latency_ms=latency_ms,
            success=True
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
                "latency_ms": latency_ms
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
                message="Verificação realizada com sucesso!",
                patient_id=patient.id
            )
        else:
            logger.warning(f"Verification failed for session: {request.session_id}")
            
            return VerifyUserResponse(
                success=False,
                message="Não foi possível verificar sua identidade. Verifique os dados informados."
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
