"""
MCP Server for LumaHealth Conversational AI Service.

This module exposes the same functionality as the REST API through the 
Model Context Protocol (MCP), enabling integration with LangChain and 
other MCP-compatible clients.
"""

import asyncio
import os
from datetime import datetime
from typing import List, Optional, Dict, Any

# Using standard MCP server instead of FastMCP for now
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, TextContent
import mcp.types as types

from sqlmodel import Session

from .db import create_db_and_tables, PatientCRUD, AppointmentCRUD, engine
from .session_manager import SessionManager
from .observability import setup_logging
from .security import with_guardrails, guardrails

# Setup logging
logger = setup_logging()

# Initialize MCP server
server = Server("lumahealth-clinic-assistant")

# Session manager (shared with REST API in production)
session_manager = SessionManager()


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available tools for the MCP client.
    """
    return [
        types.Tool(
            name="verify_user",
            description="Verify user identity using full name and date of birth",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "Unique session identifier"},
                    "full_name": {"type": "string", "description": "Patient's full name"},
                    "dob": {"type": "string", "description": "Date of birth in YYYY-MM-DD format"}
                },
                "required": ["session_id", "full_name", "dob"]
            }
        ),
        types.Tool(
            name="list_appointments",
            description="List all appointments for a verified session",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "Unique session identifier"}
                },
                "required": ["session_id"]
            }
        ),
        types.Tool(
            name="confirm_appointment",
            description="Confirm an appointment by ID or by date/time reference",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "Unique session identifier"},
                    "appointment_id": {"type": "integer", "description": "Specific appointment ID to confirm"},
                    "date": {"type": "string", "description": "Date reference (YYYY-MM-DD format)"},
                    "time": {"type": "string", "description": "Time reference (HH:MM format)"}
                },
                "required": ["session_id"]
            }
        ),
        types.Tool(
            name="cancel_appointment",
            description="Cancel an appointment by ID or by date/time reference",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "Unique session identifier"},
                    "appointment_id": {"type": "integer", "description": "Specific appointment ID to cancel"},
                    "date": {"type": "string", "description": "Date reference (YYYY-MM-DD format)"},
                    "time": {"type": "string", "description": "Time reference (HH:MM format)"}
                },
                "required": ["session_id"]
            }
        ),
        types.Tool(
            name="get_session_info",
            description="Get current session information and status",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "Unique session identifier"}
                },
                "required": ["session_id"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """
    Handle tool calls from MCP clients.
    """
    try:
        if name == "verify_user":
            result = await verify_user_tool(arguments)
        elif name == "list_appointments":
            result = await list_appointments_tool(arguments)
        elif name == "confirm_appointment":
            result = await confirm_appointment_tool(arguments)
        elif name == "cancel_appointment":
            result = await cancel_appointment_tool(arguments)
        elif name == "get_session_info":
            result = await get_session_info_tool(arguments)
        else:
            result = {"error": f"Unknown tool: {name}"}
        
        return [types.TextContent(type="text", text=str(result))]
    
    except Exception as e:
        logger.error(f"Error handling tool call {name}: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


@with_guardrails("verify_user")
async def verify_user_tool(args: dict) -> Dict[str, Any]:
    """
    Verify user identity using full name and date of birth.
    """
    session_id = args.get("session_id")
    full_name = args.get("full_name")
    dob = args.get("dob")
    
    if not all([session_id, full_name, dob]):
        return {
            "success": False,
            "message": "Missing required parameters: session_id, full_name, dob"
        }
    
    try:
        with Session(engine) as db:
            # Look up patient by name and DOB
            patient = PatientCRUD.get_by_name_and_dob(db, full_name, dob)
            
            if patient:
                # Update session state
                session_state = session_manager.get_or_create_session(session_id)
                session_state.is_verified = True
                session_state.patient_id = patient.id
                session_manager.update_session(session_id, session_state)
                
                logger.info(f"User verified via MCP: {session_id}")
                
                return {
                    "success": True,
                    "message": "Verificação realizada com sucesso!",
                    "patient_id": patient.id,
                    "session_verified": True
                }
            else:
                logger.warning(f"MCP verification failed for session: {session_id}")
                
                return {
                    "success": False,
                    "message": "Não foi possível verificar sua identidade. Verifique os dados informados.",
                    "session_verified": False
                }
                
    except Exception as e:
        logger.error(f"Error during MCP verification: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Erro interno: {str(e)}",
            "session_verified": False
        }


@with_guardrails("list_appointments")
async def list_appointments_tool(args: dict) -> List[Dict[str, Any]]:
    """
    List all appointments for a verified session.
    """
    session_id = args.get("session_id")
    
    if not session_id:
        return [{"error": "Missing session_id parameter"}]
    
    try:
        # Check session verification
        session_state = session_manager.get_session(session_id)
        
        if not session_state or not session_state.is_verified:
            return [{
                "error": "Session not verified",
                "message": "Por favor, verifique sua identidade primeiro."
            }]
        
        with Session(engine) as db:
            appointments = AppointmentCRUD.get_by_patient_id(db, session_state.patient_id)
            
            appointment_list = []
            for apt in appointments:
                appointment_list.append({
                    "id": apt.id,
                    "date": apt.when_utc.strftime("%Y-%m-%d"),
                    "time": apt.when_utc.strftime("%H:%M"),
                    "datetime_utc": apt.when_utc.isoformat(),
                    "doctor": apt.doctor_name,
                    "location": apt.location,
                    "status": apt.status.value,
                    "notes": apt.notes
                })
            
            # Update session state with last list
            session_state.last_list = appointment_list
            session_manager.update_session(session_id, session_state)
            
            logger.info(f"Listed {len(appointment_list)} appointments for session: {session_id}")
            
            return appointment_list
            
    except Exception as e:
        logger.error(f"Error listing appointments via MCP: {e}", exc_info=True)
        return [{
            "error": "Internal error",
            "message": f"Erro ao listar consultas: {str(e)}"
        }]


@with_guardrails("confirm_appointment")
async def confirm_appointment_tool(args: dict) -> Dict[str, Any]:
    """
    Confirm an appointment by ID or by date/time reference.
    """
    session_id = args.get("session_id")
    appointment_id = args.get("appointment_id")
    date = args.get("date")
    time = args.get("time")
    
    if not session_id:
        return {"success": False, "message": "Missing session_id parameter"}
    
    try:
        # Check session verification
        session_state = session_manager.get_session(session_id)
        
        if not session_state or not session_state.is_verified:
            return {
                "success": False,
                "message": "Session não verificada. Por favor, verifique sua identidade primeiro.",
                "appointment": None
            }
        
        with Session(engine) as db:
            appointment = None
            
            if appointment_id:
                # Direct ID confirmation
                appointment = AppointmentCRUD.confirm_appointment(
                    db, appointment_id, session_state.patient_id
                )
            elif date and session_state.last_list:
                # Try to match by date from last list
                for apt_data in session_state.last_list:
                    if apt_data.get("date") == date:
                        if time and apt_data.get("time") != time:
                            continue
                        appointment = AppointmentCRUD.confirm_appointment(
                            db, apt_data["id"], session_state.patient_id
                        )
                        break
            
            if appointment:
                logger.info(f"Appointment {appointment.id} confirmed via MCP for session: {session_id}")
                
                return {
                    "success": True,
                    "message": "Consulta confirmada com sucesso!",
                    "appointment": {
                        "id": appointment.id,
                        "date": appointment.when_utc.strftime("%Y-%m-%d"),
                        "time": appointment.when_utc.strftime("%H:%M"),
                        "doctor": appointment.doctor_name,
                        "location": appointment.location,
                        "status": appointment.status.value
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "Não foi possível confirmar a consulta. Verifique o ID ou data/hora.",
                    "appointment": None
                }
                
    except Exception as e:
        logger.error(f"Error confirming appointment via MCP: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Erro ao confirmar consulta: {str(e)}",
            "appointment": None
        }


@with_guardrails("cancel_appointment")
async def cancel_appointment_tool(args: dict) -> Dict[str, Any]:
    """
    Cancel an appointment by ID or by date/time reference.
    """
    session_id = args.get("session_id")
    appointment_id = args.get("appointment_id")
    date = args.get("date")
    time = args.get("time")
    
    if not session_id:
        return {"success": False, "message": "Missing session_id parameter"}
    
    try:
        # Check session verification
        session_state = session_manager.get_session(session_id)
        
        if not session_state or not session_state.is_verified:
            return {
                "success": False,
                "message": "Session não verificada. Por favor, verifique sua identidade primeiro.",
                "appointment": None
            }
        
        with Session(engine) as db:
            appointment = None
            
            if appointment_id:
                # Direct ID cancellation
                appointment = AppointmentCRUD.cancel_appointment(
                    db, appointment_id, session_state.patient_id
                )
            elif date and session_state.last_list:
                # Try to match by date from last list
                for apt_data in session_state.last_list:
                    if apt_data.get("date") == date:
                        if time and apt_data.get("time") != time:
                            continue
                        appointment = AppointmentCRUD.cancel_appointment(
                            db, apt_data["id"], session_state.patient_id
                        )
                        break
            
            if appointment:
                logger.info(f"Appointment {appointment.id} cancelled via MCP for session: {session_id}")
                
                return {
                    "success": True,
                    "message": "Consulta cancelada com sucesso!",
                    "appointment": {
                        "id": appointment.id,
                        "date": appointment.when_utc.strftime("%Y-%m-%d"),
                        "time": appointment.when_utc.strftime("%H:%M"),
                        "doctor": appointment.doctor_name,
                        "location": appointment.location,
                        "status": appointment.status.value
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "Não foi possível cancelar a consulta. Verifique o ID ou data/hora.",
                    "appointment": None
                }
                
    except Exception as e:
        logger.error(f"Error cancelling appointment via MCP: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Erro ao cancelar consulta: {str(e)}",
            "appointment": None
        }


async def get_session_info_tool(args: dict) -> Dict[str, Any]:
    """
    Get current session information and status.
    """
    session_id = args.get("session_id")
    
    if not session_id:
        return {"error": "Missing session_id parameter"}
    
    try:
        session_state = session_manager.get_session(session_id)
        
        if not session_state:
            return {
                "session_exists": False,
                "is_verified": False,
                "message": "Session não encontrada"
            }
        
        return {
            "session_exists": True,
            "is_verified": session_state.is_verified,
            "patient_id": session_state.patient_id,
            "last_intent": session_state.last_intent,
            "last_activity": session_state.last_activity.isoformat(),
            "appointments_count": len(session_state.last_list) if session_state.last_list else 0,
            "created_at": session_state.created_at.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting session info via MCP: {e}", exc_info=True)
        return {
            "session_exists": False,
            "is_verified": False,
            "error": str(e)
        }


async def run_mcp_server():
    """Run the MCP server with stdio transport."""
    try:
        # Initialize database
        create_db_and_tables()
        logger.info("MCP Server: Database initialized")
        
        # Run the server with stdio transport
        logger.info("Starting LumaHealth MCP Server with stdio transport...")
        
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, 
                write_stream, 
                server.create_initialization_options()
            )
        
    except Exception as e:
        logger.error(f"Error running MCP server: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(run_mcp_server())