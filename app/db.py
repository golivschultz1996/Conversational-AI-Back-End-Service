"""
Database configuration and setup for the LumaHealth Conversational AI Service.

This module handles SQLite database initialization, session management,
and provides CRUD operations for patients and appointments.
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional
from sqlmodel import SQLModel, create_engine, Session, select
from .models import Patient, Appointment, AppointmentStatus
from .settings import settings


# Database configuration
DATABASE_URL = settings.DATABASE_URL
engine = create_engine(DATABASE_URL, echo=settings.DB_ECHO)


def create_db_and_tables():
    """Create database tables if they don't exist."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Get database session."""
    with Session(engine) as session:
        yield session


# CRUD Operations
class PatientCRUD:
    """CRUD operations for Patient model."""
    
    @staticmethod
    def get_by_phone_hash(session: Session, phone_hash: str) -> Optional[Patient]:
        """Get patient by phone hash."""
        statement = select(Patient).where(Patient.phone_hash == phone_hash)
        return session.exec(statement).first()
    
    @staticmethod
    def get_by_name_and_dob(session: Session, full_name: str, dob: str) -> Optional[Patient]:
        """Get patient by full name and date of birth."""
        statement = select(Patient).where(
            Patient.full_name == full_name,
            Patient.dob == dob
        )
        return session.exec(statement).first()
    
    @staticmethod
    def get_by_name_dob_and_phone(session: Session, full_name: str, dob: str, phone: str) -> Optional[Patient]:
        """Get patient by full name, date of birth, and phone number."""
        statement = select(Patient).where(
            Patient.full_name == full_name,
            Patient.dob == dob,
            Patient.phone == phone
        )
        return session.exec(statement).first()
    
    @staticmethod
    def create(session: Session, full_name: str, dob: str, phone: str) -> Patient:
        """Create a new patient."""
        phone_hash = Patient.hash_phone(phone)
        patient = Patient(
            full_name=full_name,
            dob=dob,
            phone_hash=phone_hash
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)
        return patient


class AppointmentCRUD:
    """CRUD operations for Appointment model."""
    
    @staticmethod
    def get_by_patient_id(session: Session, patient_id: int) -> List[Appointment]:
        """Get all appointments for a patient."""
        statement = select(Appointment).where(
            Appointment.patient_id == patient_id
        ).order_by(Appointment.when_utc)
        return list(session.exec(statement).all())
    
    @staticmethod
    def get_pending_by_patient_id(session: Session, patient_id: int) -> List[Appointment]:
        """Get pending appointments for a patient."""
        statement = select(Appointment).where(
            Appointment.patient_id == patient_id,
            Appointment.status == AppointmentStatus.PENDING
        ).order_by(Appointment.when_utc)
        return list(session.exec(statement).all())
    
    @staticmethod
    def get_by_id(session: Session, appointment_id: int) -> Optional[Appointment]:
        """Get appointment by ID."""
        return session.get(Appointment, appointment_id)
    
    @staticmethod
    def confirm_appointment(session: Session, appointment_id: int, patient_id: int) -> Optional[Appointment]:
        """Confirm an appointment."""
        appointment = session.get(Appointment, appointment_id)
        if appointment and appointment.patient_id == patient_id:
            appointment.status = AppointmentStatus.CONFIRMED
            appointment.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(appointment)
            return appointment
        return None
    
    @staticmethod
    def cancel_appointment(session: Session, appointment_id: int, patient_id: int) -> Optional[Appointment]:
        """Cancel an appointment."""
        appointment = session.get(Appointment, appointment_id)
        if appointment and appointment.patient_id == patient_id:
            appointment.status = AppointmentStatus.CANCELLED
            appointment.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(appointment)
            return appointment
        return None
    
    @staticmethod
    def create(session: Session, patient_id: int, when_utc: datetime, 
               location: str, doctor_name: Optional[str] = None) -> Appointment:
        """Create a new appointment."""
        appointment = Appointment(
            patient_id=patient_id,
            when_utc=when_utc,
            location=location,
            doctor_name=doctor_name
        )
        session.add(appointment)
        session.commit()
        session.refresh(appointment)
        return appointment


def seed_database():
    """Seed the database with sample data for testing."""
    with Session(engine) as session:
        # Check if data already exists
        existing_patient = session.exec(select(Patient)).first()
        if existing_patient:
            print("Database already seeded.")
            return
        
        # Create sample patients
        patient1 = PatientCRUD.create(
            session=session,
            full_name="João Silva",
            dob="1985-03-15",
            phone="+5511987654321"
        )
        
        patient2 = PatientCRUD.create(
            session=session,
            full_name="Maria Santos",
            dob="1990-07-22",
            phone="+5511876543210"
        )
        
        # Create sample appointments
        tomorrow = datetime.utcnow() + timedelta(days=1)
        next_week = datetime.utcnow() + timedelta(days=7)
        
        AppointmentCRUD.create(
            session=session,
            patient_id=patient1.id,
            when_utc=tomorrow.replace(hour=14, minute=0, second=0, microsecond=0),
            location="Clínica Central - Sala 201",
            doctor_name="Dr. Carlos Mendes"
        )
        
        AppointmentCRUD.create(
            session=session,
            patient_id=patient1.id,
            when_utc=next_week.replace(hour=10, minute=30, second=0, microsecond=0),
            location="Hospital São Paulo - Consultório 15",
            doctor_name="Dra. Ana Rodrigues"
        )
        
        AppointmentCRUD.create(
            session=session,
            patient_id=patient2.id,
            when_utc=tomorrow.replace(hour=16, minute=0, second=0, microsecond=0),
            location="Clínica Central - Sala 105",
            doctor_name="Dr. Pedro Lima"
        )
        
        print("Database seeded successfully!")


if __name__ == "__main__":
    create_db_and_tables()
    seed_database()
