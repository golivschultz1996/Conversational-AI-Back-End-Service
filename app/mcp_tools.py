"""
MCP Tools Integration for LangGraph Agent.

This module provides proper MCP tool integration for the LangGraph agent,
allowing Claude to use MCP tools through the standard protocol.
"""

import asyncio
import os
from typing import List, Dict, Any

from langchain_core.tools import BaseTool, StructuredTool
from langchain_core.pydantic_v1 import BaseModel, Field
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .observability import setup_logging

logger = setup_logging()


class VerifyUserInput(BaseModel):
    """Input schema for user verification."""
    session_id: str = Field(description="Unique session identifier")
    full_name: str = Field(description="Patient's full name")
    dob: str = Field(description="Date of birth in YYYY-MM-DD format")


class ListAppointmentsInput(BaseModel):
    """Input schema for listing appointments."""
    session_id: str = Field(description="Unique session identifier")


class ConfirmAppointmentInput(BaseModel):
    """Input schema for confirming appointments."""
    session_id: str = Field(description="Unique session identifier")
    appointment_id: int = Field(description="Specific appointment ID to confirm", default=None)
    date: str = Field(description="Date reference (YYYY-MM-DD format)", default=None)
    time: str = Field(description="Time reference (HH:MM format)", default=None)


class CancelAppointmentInput(BaseModel):
    """Input schema for cancelling appointments."""
    session_id: str = Field(description="Unique session identifier")
    appointment_id: int = Field(description="Specific appointment ID to cancel", default=None)
    date: str = Field(description="Date reference (YYYY-MM-DD format)", default=None)
    time: str = Field(description="Time reference (HH:MM format)", default=None)


class GetSessionInfoInput(BaseModel):
    """Input schema for getting session info."""
    session_id: str = Field(description="Unique session identifier")


class MCPToolsManager:
    """
    Manager for MCP tools that provides LangChain-compatible tools
    backed by true MCP protocol communication.
    """
    
    def __init__(self):
        self.mcp_session = None
        self.tools = []
        self.is_connected = False
    
    async def initialize_mcp_connection(self) -> bool:
        """Initialize connection to MCP server."""
        try:
            # Configure MCP server parameters
            server_params = StdioServerParameters(
                command="python",
                args=["-m", "app.mcp_server"],
                env=os.environ.copy()
            )
            
            # Connect to MCP server
            self.stdio_client = stdio_client(server_params)
            read_stream, write_stream = await self.stdio_client.__aenter__()
            
            self.mcp_session = ClientSession(read_stream, write_stream)
            await self.mcp_session.initialize()
            
            logger.info("MCP connection established successfully")
            self.is_connected = True
            
            # Create LangChain tools
            await self._create_langchain_tools()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP connection: {e}")
            self.is_connected = False
            return False
    
    async def _create_langchain_tools(self):
        """Create LangChain-compatible tools from MCP tools."""
        
        # Verify User Tool
        async def verify_user_mcp(session_id: str, full_name: str, dob: str) -> Dict[str, Any]:
            """Verify user identity using MCP protocol."""
            try:
                result = await self.mcp_session.call_tool(
                    "verify_user",
                    {"session_id": session_id, "full_name": full_name, "dob": dob}
                )
                return eval(result.content[0].text) if result.content else {"error": "No response"}
            except Exception as e:
                logger.error(f"MCP verify_user error: {e}")
                return {"success": False, "message": str(e)}
        
        # List Appointments Tool
        async def list_appointments_mcp(session_id: str) -> List[Dict[str, Any]]:
            """List appointments using MCP protocol."""
            try:
                result = await self.mcp_session.call_tool(
                    "list_appointments",
                    {"session_id": session_id}
                )
                return eval(result.content[0].text) if result.content else []
            except Exception as e:
                logger.error(f"MCP list_appointments error: {e}")
                return [{"error": str(e)}]
        
        # Confirm Appointment Tool
        async def confirm_appointment_mcp(
            session_id: str, 
            appointment_id: int = None, 
            date: str = None, 
            time: str = None
        ) -> Dict[str, Any]:
            """Confirm appointment using MCP protocol."""
            try:
                args = {"session_id": session_id}
                if appointment_id:
                    args["appointment_id"] = appointment_id
                if date:
                    args["date"] = date
                if time:
                    args["time"] = time
                    
                result = await self.mcp_session.call_tool("confirm_appointment", args)
                return eval(result.content[0].text) if result.content else {"error": "No response"}
            except Exception as e:
                logger.error(f"MCP confirm_appointment error: {e}")
                return {"success": False, "message": str(e)}
        
        # Cancel Appointment Tool
        async def cancel_appointment_mcp(
            session_id: str, 
            appointment_id: int = None, 
            date: str = None, 
            time: str = None
        ) -> Dict[str, Any]:
            """Cancel appointment using MCP protocol."""
            try:
                args = {"session_id": session_id}
                if appointment_id:
                    args["appointment_id"] = appointment_id
                if date:
                    args["date"] = date
                if time:
                    args["time"] = time
                    
                result = await self.mcp_session.call_tool("cancel_appointment", args)
                return eval(result.content[0].text) if result.content else {"error": "No response"}
            except Exception as e:
                logger.error(f"MCP cancel_appointment error: {e}")
                return {"success": False, "message": str(e)}
        
        # Get Session Info Tool
        async def get_session_info_mcp(session_id: str) -> Dict[str, Any]:
            """Get session info using MCP protocol."""
            try:
                result = await self.mcp_session.call_tool(
                    "get_session_info",
                    {"session_id": session_id}
                )
                return eval(result.content[0].text) if result.content else {"error": "No response"}
            except Exception as e:
                logger.error(f"MCP get_session_info error: {e}")
                return {"error": str(e)}
        
        # Create LangChain StructuredTools
        self.tools = [
            StructuredTool.from_function(
                func=verify_user_mcp,
                name="verify_user",
                description="Verify user identity using full name and date of birth",
                args_schema=VerifyUserInput,
                return_direct=False
            ),
            StructuredTool.from_function(
                func=list_appointments_mcp,
                name="list_appointments", 
                description="List all appointments for a verified session",
                args_schema=ListAppointmentsInput,
                return_direct=False
            ),
            StructuredTool.from_function(
                func=confirm_appointment_mcp,
                name="confirm_appointment",
                description="Confirm an appointment by ID or by date/time reference",
                args_schema=ConfirmAppointmentInput,
                return_direct=False
            ),
            StructuredTool.from_function(
                func=cancel_appointment_mcp,
                name="cancel_appointment",
                description="Cancel an appointment by ID or by date/time reference", 
                args_schema=CancelAppointmentInput,
                return_direct=False
            ),
            StructuredTool.from_function(
                func=get_session_info_mcp,
                name="get_session_info",
                description="Get current session information and status",
                args_schema=GetSessionInfoInput,
                return_direct=False
            )
        ]
        
        logger.info(f"Created {len(self.tools)} MCP-backed LangChain tools")
    
    def get_tools(self) -> List[BaseTool]:
        """Get the list of LangChain tools."""
        return self.tools if self.is_connected else []
    
    async def close(self):
        """Close MCP connection."""
        try:
            if self.mcp_session:
                await self.mcp_session.close()
            if hasattr(self, 'stdio_client'):
                await self.stdio_client.__aexit__(None, None, None)
            self.is_connected = False
            logger.info("MCP connection closed")
        except Exception as e:
            logger.error(f"Error closing MCP connection: {e}")


# Fallback functions for when MCP is not available
async def verify_user_fallback(session_id: str, full_name: str, dob: str) -> Dict[str, Any]:
    """Fallback verify user function when MCP is not available."""
    from .mcp_server import verify_user_tool
    return await verify_user_tool({
        "session_id": session_id,
        "full_name": full_name, 
        "dob": dob
    })


async def list_appointments_fallback(session_id: str) -> List[Dict[str, Any]]:
    """Fallback list appointments function when MCP is not available."""
    from .mcp_server import list_appointments_tool
    return await list_appointments_tool({"session_id": session_id})


async def confirm_appointment_fallback(
    session_id: str, 
    appointment_id: int = None, 
    date: str = None, 
    time: str = None
) -> Dict[str, Any]:
    """Fallback confirm appointment function when MCP is not available."""
    from .mcp_server import confirm_appointment_tool
    args = {"session_id": session_id}
    if appointment_id:
        args["appointment_id"] = appointment_id
    if date:
        args["date"] = date
    if time:
        args["time"] = time
    return await confirm_appointment_tool(args)


async def cancel_appointment_fallback(
    session_id: str, 
    appointment_id: int = None, 
    date: str = None, 
    time: str = None
) -> Dict[str, Any]:
    """Fallback cancel appointment function when MCP is not available."""
    from .mcp_server import cancel_appointment_tool
    args = {"session_id": session_id}
    if appointment_id:
        args["appointment_id"] = appointment_id
    if date:
        args["date"] = date
    if time:
        args["time"] = time
    return await cancel_appointment_tool(args)


def create_fallback_tools() -> List[BaseTool]:
    """Create fallback tools when MCP is not available."""
    return [
        StructuredTool.from_function(
            func=verify_user_fallback,
            name="verify_user",
            description="Verify user identity using full name and date of birth",
            args_schema=VerifyUserInput,
            return_direct=False
        ),
        StructuredTool.from_function(
            func=list_appointments_fallback,
            name="list_appointments",
            description="List all appointments for a verified session",
            args_schema=ListAppointmentsInput,
            return_direct=False
        ),
        StructuredTool.from_function(
            func=confirm_appointment_fallback,
            name="confirm_appointment",
            description="Confirm an appointment by ID or by date/time reference",
            args_schema=ConfirmAppointmentInput,
            return_direct=False
        ),
        StructuredTool.from_function(
            func=cancel_appointment_fallback,
            name="cancel_appointment",
            description="Cancel an appointment by ID or by date/time reference",
            args_schema=CancelAppointmentInput,
            return_direct=False
        )
    ]


# Global MCP tools manager instance
mcp_tools_manager = MCPToolsManager()
