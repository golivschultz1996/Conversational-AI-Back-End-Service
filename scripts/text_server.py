"""
Text Processing MCP Server for LumaHealth Demo.

This auxiliary MCP server provides text processing utilities like
date normalization and text cleaning. It demonstrates how multiple
MCP servers can be composed together in a single agent.
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List
import locale

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types


# Initialize MCP server
server = Server("lumahealth-text-processor")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available text processing tools.
    """
    return [
        types.Tool(
            name="normalize_date_pt_br",
            description="Normalize Portuguese date expressions to ISO format (YYYY-MM-DD)",
            inputSchema={
                "type": "object",
                "properties": {
                    "date_text": {"type": "string", "description": "Date text in Portuguese (e.g., '15/03/1985', 'amanhã', 'próxima semana')"}
                },
                "required": ["date_text"]
            }
        ),
        types.Tool(
            name="normalize_time_pt_br",
            description="Normalize Portuguese time expressions to HH:MM format",
            inputSchema={
                "type": "object",
                "properties": {
                    "time_text": {"type": "string", "description": "Time text in Portuguese (e.g., '14h30', '2:30 PM', 'meio-dia')"}
                },
                "required": ["time_text"]
            }
        ),
        types.Tool(
            name="extract_patient_info",
            description="Extract patient information from natural language text",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Natural language text containing patient info"}
                },
                "required": ["text"]
            }
        ),
        types.Tool(
            name="clean_and_validate_text",
            description="Clean and validate text input, removing harmful content",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to clean and validate"},
                    "max_length": {"type": "integer", "description": "Maximum allowed length", "default": 1000}
                },
                "required": ["text"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """
    Handle tool calls from MCP clients.
    """
    try:
        if name == "normalize_date_pt_br":
            result = normalize_date_pt_br(arguments)
        elif name == "normalize_time_pt_br":
            result = normalize_time_pt_br(arguments)
        elif name == "extract_patient_info":
            result = extract_patient_info(arguments)
        elif name == "clean_and_validate_text":
            result = clean_and_validate_text(arguments)
        else:
            result = {"error": f"Unknown tool: {name}"}
        
        return [types.TextContent(type="text", text=str(result))]
    
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


def normalize_date_pt_br(args: dict) -> Dict[str, Any]:
    """
    Normalize Portuguese date expressions to ISO format.
    """
    date_text = args.get("date_text", "").lower().strip()
    
    if not date_text:
        return {"error": "Empty date text"}
    
    today = datetime.now().date()
    
    try:
        # Handle relative dates
        if "hoje" in date_text:
            return {
                "original": args.get("date_text"),
                "normalized": today.isoformat(),
                "confidence": 1.0,
                "type": "relative"
            }
        
        elif "amanhã" in date_text or "amanha" in date_text:
            tomorrow = today + timedelta(days=1)
            return {
                "original": args.get("date_text"),
                "normalized": tomorrow.isoformat(),
                "confidence": 1.0,
                "type": "relative"
            }
        
        elif "ontem" in date_text:
            yesterday = today - timedelta(days=1)
            return {
                "original": args.get("date_text"),
                "normalized": yesterday.isoformat(),
                "confidence": 1.0,
                "type": "relative"
            }
        
        elif "próxima semana" in date_text or "proxima semana" in date_text:
            next_week = today + timedelta(days=7)
            return {
                "original": args.get("date_text"),
                "normalized": next_week.isoformat(),
                "confidence": 0.8,
                "type": "relative"
            }
        
        # Handle absolute dates
        # Format: DD/MM/YYYY
        match = re.search(r'(\\d{1,2})/(\\d{1,2})/(\\d{4})', date_text)
        if match:
            day, month, year = match.groups()
            try:
                parsed_date = datetime(int(year), int(month), int(day)).date()
                return {
                    "original": args.get("date_text"),
                    "normalized": parsed_date.isoformat(),
                    "confidence": 1.0,
                    "type": "absolute"
                }
            except ValueError:
                pass
        
        # Format: DD-MM-YYYY
        match = re.search(r'(\\d{1,2})-(\\d{1,2})-(\\d{4})', date_text)
        if match:
            day, month, year = match.groups()
            try:
                parsed_date = datetime(int(year), int(month), int(day)).date()
                return {
                    "original": args.get("date_text"),
                    "normalized": parsed_date.isoformat(),
                    "confidence": 1.0,
                    "type": "absolute"
                }
            except ValueError:
                pass
        
        # If no pattern matches, return low confidence
        return {
            "original": args.get("date_text"),
            "normalized": None,
            "confidence": 0.0,
            "type": "unknown",
            "error": "Unable to parse date"
        }
        
    except Exception as e:
        return {
            "original": args.get("date_text"),
            "normalized": None,
            "confidence": 0.0,
            "error": str(e)
        }


def normalize_time_pt_br(args: dict) -> Dict[str, Any]:
    """
    Normalize Portuguese time expressions to HH:MM format.
    """
    time_text = args.get("time_text", "").lower().strip()
    
    if not time_text:
        return {"error": "Empty time text"}
    
    try:
        # Handle common time expressions
        if "meio-dia" in time_text or "meio dia" in time_text:
            return {
                "original": args.get("time_text"),
                "normalized": "12:00",
                "confidence": 1.0,
                "type": "named"
            }
        
        elif "meia-noite" in time_text or "meia noite" in time_text:
            return {
                "original": args.get("time_text"),
                "normalized": "00:00",
                "confidence": 1.0,
                "type": "named"
            }
        
        # Handle HH:MM format
        match = re.search(r'(\\d{1,2}):(\\d{2})', time_text)
        if match:
            hour, minute = match.groups()
            if 0 <= int(hour) <= 23 and 0 <= int(minute) <= 59:
                return {
                    "original": args.get("time_text"),
                    "normalized": f"{int(hour):02d}:{minute}",
                    "confidence": 1.0,
                    "type": "standard"
                }
        
        # Handle HHhMM format
        match = re.search(r'(\\d{1,2})h(\\d{2})', time_text)
        if match:
            hour, minute = match.groups()
            if 0 <= int(hour) <= 23 and 0 <= int(minute) <= 59:
                return {
                    "original": args.get("time_text"),
                    "normalized": f"{int(hour):02d}:{minute}",
                    "confidence": 1.0,
                    "type": "brazilian"
                }
        
        # Handle HHh format (no minutes)
        match = re.search(r'(\\d{1,2})h(?!\\d)', time_text)
        if match:
            hour = match.group(1)
            if 0 <= int(hour) <= 23:
                return {
                    "original": args.get("time_text"),
                    "normalized": f"{int(hour):02d}:00",
                    "confidence": 0.9,
                    "type": "brazilian"
                }
        
        return {
            "original": args.get("time_text"),
            "normalized": None,
            "confidence": 0.0,
            "type": "unknown",
            "error": "Unable to parse time"
        }
        
    except Exception as e:
        return {
            "original": args.get("time_text"),
            "normalized": None,
            "confidence": 0.0,
            "error": str(e)
        }


def extract_patient_info(args: dict) -> Dict[str, Any]:
    """
    Extract patient information from natural language text.
    """
    text = args.get("text", "").strip()
    
    if not text:
        return {"error": "Empty text"}
    
    extracted = {
        "original_text": text,
        "extracted_info": {},
        "confidence": 0.0
    }
    
    try:
        # Extract name patterns
        name_patterns = [
            r"(?:eu sou|me chamo|meu nome é|sou)\\s+([A-ZÁÉÍÓÚÀÂÊÔÃÇ][a-záéíóúàâêôãç]+(?:\\s+[A-ZÁÉÍÓÚÀÂÊÔÃÇ][a-záéíóúàâêôãç]+)*)",
            r"([A-ZÁÉÍÓÚÀÂÊÔÃÇ][a-záéíóúàâêôãç]+\\s+[A-ZÁÉÍÓÚÀÂÊÔÃÇ][a-záéíóúàâêôãç]+)(?:\\s+(?:nascido|nascida|born))"
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted["extracted_info"]["name"] = match.group(1).strip()
                extracted["confidence"] += 0.4
                break
        
        # Extract date of birth patterns
        dob_patterns = [
            r"(?:nascido|nascida|born).*?(\\d{1,2}/\\d{1,2}/\\d{4})",
            r"(?:nascimento|birth).*?(\\d{1,2}/\\d{1,2}/\\d{4})",
            r"(\\d{1,2}/\\d{1,2}/\\d{4})"
        ]
        
        for pattern in dob_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted["extracted_info"]["date_of_birth"] = match.group(1)
                extracted["confidence"] += 0.4
                break
        
        # Extract phone patterns
        phone_patterns = [
            r"(?:telefone|phone|cel|celular).*?(\\+?\\d{2}\\s?\\d{2}\\s?\\d{4,5}-?\\d{4})",
            r"(\\+?\\d{2}\\s?\\d{2}\\s?\\d{4,5}-?\\d{4})"
        ]
        
        for pattern in phone_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted["extracted_info"]["phone"] = match.group(1)
                extracted["confidence"] += 0.2
                break
        
        return extracted
        
    except Exception as e:
        return {
            "original_text": text,
            "extracted_info": {},
            "confidence": 0.0,
            "error": str(e)
        }


def clean_and_validate_text(args: dict) -> Dict[str, Any]:
    """
    Clean and validate text input, removing harmful content.
    """
    text = args.get("text", "")
    max_length = args.get("max_length", 1000)
    
    if not text:
        return {"error": "Empty text"}
    
    try:
        # Remove potentially harmful patterns
        cleaned = text
        
        # Remove excessive whitespace
        cleaned = re.sub(r'\\s+', ' ', cleaned).strip()
        
        # Remove potential script injections (basic)
        cleaned = re.sub(r'<script.*?</script>', '', cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r'javascript:', '', cleaned, flags=re.IGNORECASE)
        
        # Truncate if too long
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length] + "..."
            truncated = True
        else:
            truncated = False
        
        # Basic profanity filter (very simple)
        profanity_indicators = ['***', '###', 'censored']
        has_profanity = any(indicator in cleaned.lower() for indicator in profanity_indicators)
        
        return {
            "original": text,
            "cleaned": cleaned,
            "truncated": truncated,
            "original_length": len(text),
            "cleaned_length": len(cleaned),
            "has_potential_issues": has_profanity,
            "confidence": 0.9 if not has_profanity else 0.5
        }
        
    except Exception as e:
        return {
            "original": text,
            "cleaned": text,
            "error": str(e),
            "confidence": 0.0
        }


async def run_text_server():
    """Run the text processing MCP server."""
    try:
        print("🔤 Starting LumaHealth Text Processing MCP Server...")
        
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, 
                write_stream, 
                server.create_initialization_options()
            )
        
    except Exception as e:
        print(f"❌ Error running text server: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_text_server())
