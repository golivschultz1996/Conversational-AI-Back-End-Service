"""
Data models for the LumaHealth Conversational AI Service.

This module defines the database models and Pydantic schemas used throughout
the application for patient data, appointments, and session management.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from pydantic import BaseModel
import hashlib


# Enums
class AppointmentStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


# Database Models
class Patient(SQLModel, table=True):
    """Patient database model with PII protection."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str = Field(index=True, max_length=255)
    dob: str = Field(description="Date of birth in YYYY-MM-DD format")
    phone_hash: str = Field(index=True, unique=True, description="Hashed phone number for privacy")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    appointments: List["Appointment"] = Relationship(back_populates="patient")
    
    @staticmethod
    def hash_phone(phone: str) -> str:
        """Hash phone number for privacy protection."""
        return hashlib.sha256(phone.encode()).hexdigest()


class Appointment(SQLModel, table=True):
    """Appointment database model."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id")
    when_utc: datetime = Field(description="Appointment datetime in UTC")
    location: str = Field(max_length=255)
    status: AppointmentStatus = Field(default=AppointmentStatus.PENDING)
    doctor_name: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    patient: Patient = Relationship(back_populates="appointments")


# Session State Models (in-memory)
class SessionState(BaseModel):
    """Session state management for conversational flow."""
    
    session_id: str
    patient_id: Optional[int] = None
    is_verified: bool = False
    last_intent: Optional[str] = None
    last_list: List[dict] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)


# API Request/Response Models
class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    
    session_id: Optional[str] = None
    message: str
    metadata: Optional[dict] = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    
    session_id: str
    reply: str
    state: dict
    observability: dict


class VerifyUserRequest(BaseModel):
    """Request model for user verification."""
    
    session_id: str
    full_name: str
    dob: str  # YYYY-MM-DD format


class VerifyUserResponse(BaseModel):
    """Response model for user verification."""
    
    success: bool
    message: str
    patient_id: Optional[int] = None


class AppointmentResponse(BaseModel):
    """Response model for appointment data."""
    
    id: int
    when_utc: datetime
    location: str
    status: AppointmentStatus
    doctor_name: Optional[str] = None
    formatted_datetime: str


class ConfirmAppointmentRequest(BaseModel):
    """Request model for appointment confirmation."""
    
    session_id: str
    appointment_id: Optional[int] = None
    date: Optional[str] = None  # For natural language date reference
    time: Optional[str] = None  # For natural language time reference


class CancelAppointmentRequest(BaseModel):
    """Request model for appointment cancellation."""
    
    session_id: str
    appointment_id: Optional[int] = None
    date: Optional[str] = None  # For natural language date reference
    time: Optional[str] = None  # For natural language time reference


class ActionResponse(BaseModel):
    """Generic response model for confirm/cancel actions."""
    
    success: bool
    message: str
    appointment: Optional[AppointmentResponse] = None
