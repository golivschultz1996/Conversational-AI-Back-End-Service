"""
Database seeding script for LumaHealth Conversational AI Service.

This script populates the database with sample patients and appointments
for testing and demonstration purposes.
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import create_db_and_tables, PatientCRUD, AppointmentCRUD, engine
from sqlmodel import Session


def seed_extended_data():
    """Seed the database with extended sample data for comprehensive testing."""
    
    print("🌱 Seeding database with extended sample data...")
    
    with Session(engine) as session:
        # Clear existing data (optional)
        print("📝 Creating additional test patients...")
        
        # Create more diverse patient data
        patients_data = [
            ("Maria Santos", "1990-07-22", "+5511876543210"),
            ("Pedro Oliveira", "1988-12-10", "+5511765432109"),
            ("Ana Rodrigues", "1992-05-18", "+5511654321098"),
            ("Carlos Mendes", "1975-09-03", "+5511543210987"),
            ("Lucia Fernandes", "1983-11-30", "+5511432109876"),
            ("Roberto Silva", "1995-02-14", "+5511321098765"),
            ("Julia Costa", "1987-08-07", "+5511210987654"),
            ("Fernando Lima", "1991-04-25", "+5511109876543")
        ]
        
        created_patients = []
        for full_name, dob, phone in patients_data:
            try:
                # Check if patient already exists
                existing = PatientCRUD.get_by_name_and_dob(session, full_name, dob)
                if existing:
                    print(f"   ↳ Patient {full_name} already exists")
                    created_patients.append(existing)
                else:
                    patient = PatientCRUD.create(session, full_name, dob, phone)
                    created_patients.append(patient)
                    print(f"   ✅ Created patient: {full_name}")
            except Exception as e:
                print(f"   ❌ Error creating patient {full_name}: {e}")
        
        print(f"📅 Creating diverse appointments...")
        
        # Create appointments across different time periods
        base_date = datetime.now()
        
        appointments_data = [
            # Past appointments (for history)
            (0, base_date - timedelta(days=30), "Clínica Central - Sala 101", "Dr. João Carvalho", "CONFIRMED"),
            (1, base_date - timedelta(days=15), "Hospital São Paulo - Consultório 25", "Dra. Maria Silva", "CONFIRMED"),
            
            # Recent appointments
            (0, base_date - timedelta(days=2), "Clínica Norte - Sala 203", "Dr. Pedro Lima", "CANCELLED"),
            (2, base_date - timedelta(days=1), "Clínica Central - Sala 105", "Dra. Ana Costa", "CONFIRMED"),
            
            # Today and near future
            (1, base_date + timedelta(hours=2), "Hospital Santa Maria - Consultório 12", "Dr. Carlos Santos", "PENDING"),
            (3, base_date + timedelta(hours=4), "Clínica Sul - Sala 302", "Dra. Lucia Mendes", "PENDING"),
            
            # Tomorrow
            (0, base_date + timedelta(days=1, hours=10), "Clínica Central - Sala 201", "Dr. Carlos Mendes", "PENDING"),
            (4, base_date + timedelta(days=1, hours=14), "Hospital São Paulo - Consultório 18", "Dra. Julia Rodrigues", "PENDING"),
            (5, base_date + timedelta(days=1, hours=16), "Clínica Norte - Sala 105", "Dr. Roberto Lima", "PENDING"),
            
            # This week
            (2, base_date + timedelta(days=3, hours=9), "Clínica Central - Sala 104", "Dr. Fernando Costa", "PENDING"),
            (6, base_date + timedelta(days=4, hours=11), "Hospital Santa Maria - Consultório 08", "Dra. Ana Rodrigues", "PENDING"),
            (7, base_date + timedelta(days=5, hours=15), "Clínica Sul - Sala 201", "Dr. Pedro Silva", "PENDING"),
            
            # Next week
            (1, base_date + timedelta(days=7, hours=10), "Hospital São Paulo - Consultório 15", "Dra. Ana Rodrigues", "PENDING"),
            (3, base_date + timedelta(days=8, hours=13), "Clínica Norte - Sala 203", "Dr. Carlos Lima", "PENDING"),
            (4, base_date + timedelta(days=9, hours=16), "Clínica Central - Sala 301", "Dra. Maria Santos", "PENDING"),
            
            # Future appointments
            (0, base_date + timedelta(days=14, hours=14), "Hospital Santa Maria - Consultório 22", "Dr. João Silva", "PENDING"),
            (5, base_date + timedelta(days=21, hours=10), "Clínica Sul - Sala 102", "Dra. Lucia Costa", "PENDING"),
            (6, base_date + timedelta(days=28, hours=15), "Clínica Central - Sala 205", "Dr. Roberto Mendes", "PENDING")
        ]
        
        for patient_idx, when_utc, location, doctor_name, status in appointments_data:
            try:
                if patient_idx < len(created_patients):
                    patient = created_patients[patient_idx]
                    
                    # Import status enum
                    from app.models import AppointmentStatus
                    appointment_status = AppointmentStatus(status)
                    
                    appointment = AppointmentCRUD.create(
                        session=session,
                        patient_id=patient.id,
                        when_utc=when_utc,
                        location=location,
                        doctor_name=doctor_name
                    )
                    
                    # Update status if not PENDING
                    if status != "PENDING":
                        appointment.status = appointment_status
                        session.commit()
                    
                    print(f"   ✅ Created appointment: {doctor_name} for {patient.full_name} on {when_utc.strftime('%Y-%m-%d %H:%M')}")
                    
            except Exception as e:
                print(f"   ❌ Error creating appointment: {e}")
        
        print("\\n✅ Extended database seeding completed!")
        print(f"📊 Summary:")
        print(f"   - Patients: {len(created_patients)}")
        print(f"   - Appointments: {len(appointments_data)}")


def print_database_summary():
    """Print a summary of current database contents."""
    print("\\n📋 Database Summary:")
    print("=" * 50)
    
    with Session(engine) as session:
        from sqlmodel import select
        from app.models import Patient, Appointment
        
        # Count patients
        patients = session.exec(select(Patient)).all()
        print(f"👥 Total Patients: {len(patients)}")
        
        # Count appointments by status
        appointments = session.exec(select(Appointment)).all()
        status_counts = {}
        for apt in appointments:
            status_counts[apt.status.value] = status_counts.get(apt.status.value, 0) + 1
        
        print(f"📅 Total Appointments: {len(appointments)}")
        for status, count in status_counts.items():
            print(f"   - {status}: {count}")
        
        # Show upcoming appointments
        from datetime import datetime
        now = datetime.utcnow()
        upcoming = [apt for apt in appointments if apt.when_utc > now and apt.status.value == "PENDING"]
        upcoming.sort(key=lambda x: x.when_utc)
        
        print(f"\\n🔮 Next 5 Upcoming Appointments:")
        for apt in upcoming[:5]:
            patient = next(p for p in patients if p.id == apt.patient_id)
            print(f"   - {apt.when_utc.strftime('%Y-%m-%d %H:%M')} | {patient.full_name} | {apt.doctor_name}")


def main():
    """Main function to run database seeding."""
    print("🗄️  LumaHealth Database Seeding Tool")
    print("=" * 50)
    
    try:
        # Ensure database exists
        create_db_and_tables()
        print("✅ Database tables ensured")
        
        # Seed basic data first (from db.py)
        from app.db import seed_database
        seed_database()
        
        # Add extended data
        seed_extended_data()
        
        # Print summary
        print_database_summary()
        
        print("\\n🎉 Database seeding completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during database seeding: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
