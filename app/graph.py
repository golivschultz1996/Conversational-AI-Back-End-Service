"""
LangGraph StateGraph for LumaHealth Conversational AI Service.

This module implements advanced conversation management using LangGraph StateGraph
with Claude LLM, state persistence, and MCP tool integration.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Annotated, Dict, List, Optional, TypedDict, Any

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

from .session_manager import SessionManager
from .observability import setup_logging, trace_operation
from .models import SessionState


# Setup logging
logger = setup_logging()


class ConversationState(TypedDict):
    """
    Enhanced state for LangGraph conversation management.
    
    Includes message history, session info, and conversation context.
    """
    messages: Annotated[List[BaseMessage], add_messages]
    session_id: str
    patient_id: Optional[int]
    is_verified: bool
    last_intent: Optional[str]
    conversation_stage: str  # greeting, verification, authenticated, confirming, etc.
    appointments_context: List[Dict[str, Any]]
    error_count: int
    metadata: Dict[str, Any]


class LumaHealthAgent:
    """
    Advanced conversational agent using LangGraph StateGraph with Claude LLM.
    
    Provides natural language understanding, state management, and tool routing
    for healthcare appointment management conversations.
    """
    
    def __init__(self, anthropic_api_key: str, session_manager: SessionManager):
        self.anthropic_api_key = anthropic_api_key
        self.session_manager = session_manager
        
        # Initialize Claude LLM
        self.llm = ChatAnthropic(
            model="claude-3-5-sonnet-20241022",
            api_key=anthropic_api_key,
            temperature=0.1,
            max_tokens=1024
        )
        
        # State persistence
        self.memory = MemorySaver()
        
        # Build the conversation graph
        self.graph = self._build_graph()
        
        logger.info("LumaHealth LangGraph Agent initialized")
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph StateGraph for conversation flow."""
        
        # Create the StateGraph
        workflow = StateGraph(ConversationState)
        
        # Add nodes
        workflow.add_node("process_message", self._process_message_node)
        workflow.add_node("verify_user", self._verify_user_node)
        workflow.add_node("list_appointments", self._list_appointments_node)
        workflow.add_node("manage_appointment", self._manage_appointment_node)
        workflow.add_node("handle_error", self._handle_error_node)
        workflow.add_node("generate_response", self._generate_response_node)
        
        # Add edges with conditional routing
        workflow.add_edge(START, "process_message")
        
        workflow.add_conditional_edges(
            "process_message",
            self._route_conversation,
            {
                "verify": "verify_user",
                "list": "list_appointments", 
                "manage": "manage_appointment",
                "error": "handle_error",
                "respond": "generate_response"
            }
        )
        
        # All nodes lead to response generation
        workflow.add_edge("verify_user", "generate_response")
        workflow.add_edge("list_appointments", "generate_response")
        workflow.add_edge("manage_appointment", "generate_response")
        workflow.add_edge("handle_error", "generate_response")
        workflow.add_edge("generate_response", END)
        
        # Compile with checkpointer for state persistence
        return workflow.compile(checkpointer=self.memory)
    
    def _get_system_prompt(self, state: ConversationState) -> str:
        """Generate dynamic system prompt based on conversation state."""
        
        base_prompt = """Você é um assistente virtual da LumaHealth, especializado em ajudar pacientes com consultas médicas.

SUAS CAPACIDADES:
- Verificar identidade de pacientes (nome completo + data de nascimento)
- Listar consultas agendadas
- Confirmar consultas pendentes
- Cancelar consultas quando solicitado
- Fornecer informações sobre consultas

REGRAS IMPORTANTES:
1. SEMPRE verifique a identidade antes de mostrar informações médicas
2. Seja empático e profissional
3. Confirme ações importantes antes de executá-las
4. Se não entender algo, peça esclarecimentos
5. Mantenha conversas focadas em consultas médicas

DADOS DO PACIENTE DE TESTE:
- Nome: João Silva
- Data de nascimento: 15/03/1985
- Tem consultas agendadas disponíveis

"""
        
        # Add context based on conversation stage
        if state.get("conversation_stage") == "greeting":
            base_prompt += "\nSITUAÇÃO ATUAL: Paciente iniciou conversa. Precisa verificar identidade primeiro."
        
        elif state.get("conversation_stage") == "verification":
            base_prompt += "\nSITUAÇÃO ATUAL: Processo de verificação em andamento. Aguarde nome e data de nascimento."
        
        elif state.get("is_verified") and state.get("patient_id"):
            base_prompt += f"\nSITUAÇÃO ATUAL: Paciente verificado (ID: {state.get('patient_id')}). Pode acessar consultas."
            
            if state.get("appointments_context"):
                appointments = state["appointments_context"]
                base_prompt += f"\nCONSULTAS CONHECIDAS: {len(appointments)} consulta(s) no contexto."
        
        return base_prompt
    
    async def _process_message_node(self, state: ConversationState) -> ConversationState:
        """Process incoming message and determine conversation context."""
        
        try:
            with trace_operation("process_message", session_id=state["session_id"]):
                # Get the latest human message
                latest_message = state["messages"][-1] if state["messages"] else None
                
                if not latest_message or not isinstance(latest_message, HumanMessage):
                    logger.warning(f"No human message found in state for session {state['session_id']}")
                    return {**state, "conversation_stage": "error"}
                
                message_content = latest_message.content.lower().strip()
                
                # Update session manager
                session_state = self.session_manager.get_or_create_session(state["session_id"])
                session_state.last_activity = datetime.utcnow()
                
                # Analyze message for intent and context
                if not state.get("is_verified"):
                    # Check if message contains identification info
                    if any(keyword in message_content for keyword in ["sou", "me chamo", "nascido", "nascida", "nasci"]):
                        return {**state, "conversation_stage": "verification", "last_intent": "verify_user"}
                    else:
                        return {**state, "conversation_stage": "greeting", "last_intent": "greeting"}
                
                else:
                    # User is verified, analyze intent
                    if any(keyword in message_content for keyword in ["consultas", "appointments", "listar", "mostrar"]):
                        return {**state, "conversation_stage": "authenticated", "last_intent": "list_appointments"}
                    elif any(keyword in message_content for keyword in ["confirmar", "confirm"]):
                        return {**state, "conversation_stage": "authenticated", "last_intent": "confirm_appointment"}
                    elif any(keyword in message_content for keyword in ["cancelar", "cancel"]):
                        return {**state, "conversation_stage": "authenticated", "last_intent": "cancel_appointment"}
                    else:
                        return {**state, "conversation_stage": "authenticated", "last_intent": "general_query"}
        
        except Exception as e:
            logger.error(f"Error in process_message_node: {e}", exc_info=True)
            return {**state, "conversation_stage": "error", "error_count": state.get("error_count", 0) + 1}
    
    def _route_conversation(self, state: ConversationState) -> str:
        """Route conversation based on state and intent."""
        
        stage = state.get("conversation_stage", "greeting")
        intent = state.get("last_intent", "unknown")
        
        # Error handling
        if stage == "error" or state.get("error_count", 0) > 3:
            return "error"
        
        # Verification flow
        if stage == "verification" and intent == "verify_user":
            return "verify"
        
        # Authenticated user flows
        if state.get("is_verified"):
            if intent == "list_appointments":
                return "list"
            elif intent in ["confirm_appointment", "cancel_appointment"]:
                return "manage"
        
        # Default to response generation for greetings and general queries
        return "respond"
    
    async def _verify_user_node(self, state: ConversationState) -> ConversationState:
        """Handle user verification using MCP tools."""
        
        try:
            with trace_operation("verify_user", session_id=state["session_id"]):
                # Import MCP verification tool
                from .mcp_server import verify_user_tool
                
                # Extract name and DOB from message
                latest_message = state["messages"][-1]
                message_content = latest_message.content
                
                # Simple extraction (could be enhanced with NER)
                extracted_info = self._extract_user_info(message_content)
                
                if extracted_info.get("name") and extracted_info.get("dob"):
                    # Call MCP verification tool
                    result = await verify_user_tool({
                        "session_id": state["session_id"],
                        "full_name": extracted_info["name"],
                        "dob": extracted_info["dob"]
                    })
                    
                    if result.get("success"):
                        # Update state with verified info
                        return {
                            **state,
                            "is_verified": True,
                            "patient_id": result.get("patient_id"),
                            "conversation_stage": "authenticated",
                            "metadata": {**state.get("metadata", {}), "verification_result": result}
                        }
                    else:
                        return {
                            **state,
                            "conversation_stage": "verification_failed",
                            "metadata": {**state.get("metadata", {}), "verification_error": result.get("message")}
                        }
                else:
                    return {
                        **state,
                        "conversation_stage": "verification_incomplete",
                        "metadata": {**state.get("metadata", {}), "extraction_result": extracted_info}
                    }
        
        except Exception as e:
            logger.error(f"Error in verify_user_node: {e}", exc_info=True)
            return {**state, "conversation_stage": "error", "error_count": state.get("error_count", 0) + 1}
    
    async def _list_appointments_node(self, state: ConversationState) -> ConversationState:
        """Handle appointment listing using MCP tools."""
        
        try:
            with trace_operation("list_appointments", session_id=state["session_id"]):
                from .mcp_server import list_appointments_tool
                
                # Call MCP tool to get appointments
                appointments = await list_appointments_tool({
                    "session_id": state["session_id"]
                })
                
                return {
                    **state,
                    "appointments_context": appointments,
                    "metadata": {**state.get("metadata", {}), "last_appointment_list": appointments}
                }
        
        except Exception as e:
            logger.error(f"Error in list_appointments_node: {e}", exc_info=True)
            return {**state, "conversation_stage": "error", "error_count": state.get("error_count", 0) + 1}
    
    async def _manage_appointment_node(self, state: ConversationState) -> ConversationState:
        """Handle appointment confirmation/cancellation using MCP tools."""
        
        try:
            with trace_operation("manage_appointment", session_id=state["session_id"]):
                intent = state.get("last_intent")
                latest_message = state["messages"][-1]
                
                # Determine which appointment to manage
                appointment_ref = self._extract_appointment_reference(
                    latest_message.content, 
                    state.get("appointments_context", [])
                )
                
                if intent == "confirm_appointment":
                    from .mcp_server import confirm_appointment_tool
                    result = await confirm_appointment_tool({
                        "session_id": state["session_id"],
                        **appointment_ref
                    })
                elif intent == "cancel_appointment":
                    from .mcp_server import cancel_appointment_tool
                    result = await cancel_appointment_tool({
                        "session_id": state["session_id"],
                        **appointment_ref
                    })
                else:
                    result = {"success": False, "message": "Ação não reconhecida"}
                
                return {
                    **state,
                    "metadata": {**state.get("metadata", {}), "appointment_action_result": result}
                }
        
        except Exception as e:
            logger.error(f"Error in manage_appointment_node: {e}", exc_info=True)
            return {**state, "conversation_stage": "error", "error_count": state.get("error_count", 0) + 1}
    
    async def _handle_error_node(self, state: ConversationState) -> ConversationState:
        """Handle errors and provide helpful responses."""
        
        error_count = state.get("error_count", 0)
        
        if error_count > 3:
            # Too many errors, reset conversation
            return {
                **state,
                "conversation_stage": "reset",
                "is_verified": False,
                "patient_id": None,
                "error_count": 0,
                "metadata": {**state.get("metadata", {}), "reset_reason": "too_many_errors"}
            }
        
        return {
            **state,
            "conversation_stage": "error_handled",
            "metadata": {**state.get("metadata", {}), "error_handled": True}
        }
    
    async def _generate_response_node(self, state: ConversationState) -> ConversationState:
        """Generate natural language response using Claude."""
        
        try:
            with trace_operation("generate_response", session_id=state["session_id"]):
                # Build context for Claude
                system_prompt = self._get_system_prompt(state)
                
                # Add system message if not present
                messages = []
                if not any(isinstance(msg, SystemMessage) for msg in state["messages"]):
                    messages.append(SystemMessage(content=system_prompt))
                
                # Add conversation history
                messages.extend(state["messages"])
                
                # Add context about current action results
                metadata = state.get("metadata", {})
                if "verification_result" in metadata:
                    result = metadata["verification_result"]
                    if result.get("success"):
                        context_msg = "O usuário foi verificado com sucesso. Agora pode acessar suas consultas."
                    else:
                        context_msg = f"Falha na verificação: {result.get('message', 'Dados incorretos')}"
                    messages.append(SystemMessage(content=f"CONTEXTO: {context_msg}"))
                
                if "last_appointment_list" in metadata:
                    appointments = metadata["last_appointment_list"]
                    if appointments and not any("error" in apt for apt in appointments):
                        apt_summary = "\\n".join([
                            f"- {apt['date']} às {apt['time']} - {apt['doctor']} ({apt['status']})"
                            for apt in appointments[:5]  # Limit to first 5
                        ])
                        messages.append(SystemMessage(content=f"CONSULTAS ATUAIS:\\n{apt_summary}"))
                
                if "appointment_action_result" in metadata:
                    result = metadata["appointment_action_result"]
                    action_context = f"Resultado da ação: {result.get('message', 'Ação processada')}"
                    messages.append(SystemMessage(content=f"CONTEXTO: {action_context}"))
                
                # Generate response with Claude
                response = await self.llm.ainvoke(messages)
                
                return {
                    **state,
                    "messages": [response],
                    "metadata": {**metadata, "response_generated": True, "timestamp": datetime.utcnow().isoformat()}
                }
        
        except Exception as e:
            logger.error(f"Error generating response: {e}", exc_info=True)
            # Fallback response
            fallback_response = AIMessage(content="Desculpe, houve um problema. Pode tentar novamente?")
            return {
                **state,
                "messages": [fallback_response],
                "error_count": state.get("error_count", 0) + 1
            }
    
    def _extract_user_info(self, message: str) -> Dict[str, str]:
        """Extract user name and date of birth from message."""
        import re
        
        result = {}
        
        # Extract name patterns
        name_patterns = [
            r"(?:eu sou|me chamo|meu nome é|sou)\\s+([A-ZÁÉÍÓÚÀÂÊÔÃÇ][a-záéíóúàâêôãç]+(?:\\s+[A-ZÁÉÍÓÚÀÂÊÔÃÇ][a-záéíóúàâêôãç]+)*)",
            r"([A-ZÁÉÍÓÚÀÂÊÔÃÇ][a-záéíóúàâêôãç]+\\s+[A-ZÁÉÍÓÚÀÂÊÔÃÇ][a-záéíóúàâêôãç]+)(?=.*(?:nascido|nascida|nasci))"
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                result["name"] = match.group(1).strip()
                break
        
        # Extract date patterns
        date_patterns = [
            r"(\\d{1,2}/\\d{1,2}/\\d{4})",
            r"(\\d{4}-\\d{2}-\\d{2})",
            r"(?:nascido|nascida|nasci).*?(\\d{1,2}/\\d{1,2}/\\d{4})",
            r"(?:em|dia)\\s+(\\d{1,2}/\\d{1,2}/\\d{4})"
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, message)
            if match:
                date_str = match.group(1)
                # Convert DD/MM/YYYY to YYYY-MM-DD if needed
                if "/" in date_str:
                    parts = date_str.split("/")
                    if len(parts) == 3:
                        result["dob"] = f"{parts[2]}-{parts[1]:0>2}-{parts[0]:0>2}"
                else:
                    result["dob"] = date_str
                break
        
        return result
    
    def _extract_appointment_reference(self, message: str, appointments: List[Dict]) -> Dict[str, Any]:
        """Extract appointment reference from message."""
        import re
        
        message_lower = message.lower()
        
        # Look for appointment ID
        id_match = re.search(r'(?:consulta|appointment)\\s*(?:id\\s*)?(?:#)?([0-9]+)', message_lower)
        if id_match:
            return {"appointment_id": int(id_match.group(1))}
        
        # Look for ordinal references (primeira, segunda, etc.)
        ordinals = {
            "primeira": 0, "primeiro": 0, "1a": 0, "1o": 0,
            "segunda": 1, "segundo": 1, "2a": 1, "2o": 1,
            "terceira": 2, "terceiro": 2, "3a": 2, "3o": 2,
            "última": -1, "ultimo": -1
        }
        
        for ordinal, index in ordinals.items():
            if ordinal in message_lower:
                if appointments and 0 <= index < len(appointments):
                    return {"appointment_id": appointments[index]["id"]}
                elif index == -1 and appointments:
                    return {"appointment_id": appointments[-1]["id"]}
        
        # Look for date references
        date_match = re.search(r'(\\d{1,2}/\\d{1,2}/\\d{4}|\\d{4}-\\d{2}-\\d{2})', message)
        if date_match:
            return {"date": date_match.group(1)}
        
        # Look for relative date references
        if "amanhã" in message_lower or "amanha" in message_lower:
            from datetime import date, timedelta
            tomorrow = (date.today() + timedelta(days=1)).isoformat()
            return {"date": tomorrow}
        
        # Default to first appointment if available
        if appointments:
            return {"appointment_id": appointments[0]["id"]}
        
        return {}
    
    async def process_conversation(self, session_id: str, message: str) -> Dict[str, Any]:
        """
        Process a conversation message and return AI response.
        
        This is the main entry point for conversation processing.
        """
        try:
            with trace_operation("process_conversation", session_id=session_id):
                # Get or create session state
                session_state = self.session_manager.get_or_create_session(session_id)
                
                # Build initial conversation state
                initial_state = ConversationState(
                    messages=[HumanMessage(content=message)],
                    session_id=session_id,
                    patient_id=session_state.patient_id,
                    is_verified=session_state.is_verified,
                    last_intent=session_state.last_intent,
                    conversation_stage="greeting",
                    appointments_context=[],
                    error_count=0,
                    metadata={}
                )
                
                # Process through the graph
                config = {"configurable": {"thread_id": session_id}}
                result = await self.graph.ainvoke(initial_state, config=config)
                
                # Extract response
                ai_response = result["messages"][-1] if result["messages"] else None
                response_text = ai_response.content if ai_response else "Desculpe, não consegui processar sua mensagem."
                
                # Update session manager
                if result.get("is_verified") != session_state.is_verified:
                    session_state.is_verified = result["is_verified"]
                    session_state.patient_id = result.get("patient_id")
                
                session_state.last_intent = result.get("last_intent")
                session_state.last_activity = datetime.utcnow()
                self.session_manager.update_session(session_id, session_state)
                
                return {
                    "reply": response_text,
                    "state": {
                        "is_verified": result.get("is_verified", False),
                        "patient_id": result.get("patient_id"),
                        "last_intent": result.get("last_intent"),
                        "conversation_stage": result.get("conversation_stage")
                    },
                    "observability": {
                        "intent": result.get("last_intent", "unknown"),
                        "stage": result.get("conversation_stage", "unknown"),
                        "tools_used": ["langgraph", "claude"],
                        "appointments_count": len(result.get("appointments_context", []))
                    }
                }
        
        except Exception as e:
            logger.error(f"Error in process_conversation: {e}", exc_info=True)
            return {
                "reply": "Desculpe, houve um erro interno. Pode tentar novamente?",
                "state": {"is_verified": False, "error": str(e)},
                "observability": {"error": str(e), "tools_used": ["error_handler"]}
            }
