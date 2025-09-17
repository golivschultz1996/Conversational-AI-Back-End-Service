# 🏥 LumaHealth - Technical Implementation Guide

## 📋 Project Overview

LumaHealth is a conversational AI system for healthcare appointment management. This document explains every technical component, framework, and implementation detail.

## 🎯 What This System Does

The system allows patients to:
1. **Verify Identity** - Using full name and date of birth
2. **List Appointments** - View scheduled medical appointments  
3. **Confirm Appointments** - Confirm pending appointments
4. **Cancel Appointments** - Cancel existing appointments

All through natural language conversations powered by Claude 3.5 Sonnet.

## 🏗️ Architecture Summary

```
Web UI (HTML/JS) → FastAPI → LangGraph Agent → MCP Tools → SQLite Database
                                     ↓
                            Claude 3.5 Sonnet API
```

## 📁 Code Structure & Technical Details

### Core Application Files

```
app/
├── main.py              # FastAPI server + Web UI
├── graph.py             # LangGraph conversation engine  
├── mcp_server.py        # MCP server implementation
├── mcp_tools.py         # MCP tool adapters
├── settings.py          # Configuration management
├── db.py                # Database layer
├── models.py            # Data models
├── security.py          # Security & guardrails
├── session_manager.py   # Session state management
└── observability.py     # Logging system
```

---

## 🚀 1. FastAPI Server (`app/main.py`)

### What it does:
- HTTP server that serves both API endpoints and web UI
- Handles incoming chat requests
- Manages application lifecycle

### Key Frameworks Used:
- **FastAPI**: Modern Python web framework
- **Uvicorn**: ASGI server for production
- **Pydantic**: Data validation and serialization

### Technical Implementation:

#### Web UI Integration:
```python
# Lines 92-280: Complete HTML/CSS/JavaScript chat interface
WEB_UI_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
# Complete responsive chat interface with:
# - Real-time messaging
# - Session management
# - Example buttons
# - Typing indicators
```

#### Main Chat Endpoint:
```python
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, db: Session = Depends(get_session)):
    # Process conversation using LangGraph agent
    result = await langgraph_agent.process_conversation(
        session_id=session_id,
        message=request.message
    )
```

#### Application Lifecycle:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database, LangGraph agent
    create_db_and_tables()
    seed_database()
    langgraph_agent = LumaHealthAgent(anthropic_api_key, session_manager)
    
    yield
    
    # Shutdown: Cleanup resources
```

### Memory Usage:
- **Global Variables**: `session_manager`, `langgraph_agent`
- **Dependency Injection**: Database sessions via `get_session()`
- **Request Scope**: Individual request processing

---

## 🧠 2. LangGraph Conversation Engine (`app/graph.py`)

### What it does:
- Orchestrates conversations using Claude 3.5 Sonnet
- Manages conversation memory and state
- Executes tools based on user intent

### Key Frameworks Used:
- **LangGraph**: Advanced conversation flow framework
- **LangChain**: LLM framework and tool integration
- **Anthropic**: Claude 3.5 Sonnet API client

### Technical Implementation:

#### Agent Initialization:
```python
class LumaHealthAgent:
    def __init__(self, anthropic_api_key: str, session_manager: SessionManager):
        # Claude 3.5 Sonnet LLM
        self.llm = ChatAnthropic(
            model=settings.CLAUDE_MODEL,  # claude-3-5-sonnet-20241022
            api_key=anthropic_api_key,
            temperature=0.1
        )
        
        # Persistent memory across conversations
        self.memory = MemorySaver()
        
        # Initialize tools and build graph
        self._initialize_tools_sync()
```

#### Conversation Processing:
```python
async def process_conversation(self, session_id: str, message: str) -> Dict[str, Any]:
    # 1. Load conversation history
    config = {"configurable": {"thread_id": session_id}}
    
    # 2. Check for existing conversation history
    existing_state = await self.graph.aget_state(config)
    has_history = bool(existing_state.values.get("messages", []))
    
    # 3. Prepare messages (system prompt only for first message)
    if not has_history:
        messages = [
            SystemMessage(content=self._get_base_system_prompt()),
            HumanMessage(content=message)
        ]
    else:
        messages = [HumanMessage(content=message)]
    
    # 4. Execute conversation with tools
    result = await self.graph.ainvoke({"messages": messages}, config=config)
```

#### Memory Management:
- **MemorySaver**: Persistent conversation history per session
- **Thread ID**: Session-based conversation threading
- **State Management**: Automatic state persistence between messages

#### System Prompt:
```python
def _get_base_system_prompt(self) -> str:
    return """Você é um assistente de agendamento de consultas médicas...
    # Detailed instructions for:
    # - Patient verification process
    # - Appointment management
    # - Natural conversation flow
    # - Tool usage guidelines
    """
```

---

## 🔧 3. MCP (Model Context Protocol) Implementation

### What MCP is:
Model Context Protocol - A standardized way to expose functions as tools that AI agents can use.

### Files Involved:
- `app/mcp_server.py` - MCP server exposing tools
- `app/mcp_tools.py` - MCP tool adapters for LangChain

### Key Frameworks Used:
- **FastMCP**: MCP server implementation
- **LangChain MCP Adapters**: Integration with LangChain agents
- **MCP Protocol**: Standardized tool execution protocol

### Technical Implementation:

#### MCP Server (`app/mcp_server.py`):
```python
# Lines 89-449: Complete MCP server implementation

# Tool Registration:
@app.tool("verify_user")
async def verify_user_tool(args: dict) -> Dict[str, Any]:
    """Verify patient identity using full name and date of birth"""
    # Implementation with guardrails protection

@app.tool("list_appointments") 
async def list_appointments_tool(args: dict) -> List[Dict[str, Any]]:
    """List all appointments for verified patient"""
    # Implementation with patient verification check

@app.tool("confirm_appointment")
async def confirm_appointment_tool(args: dict) -> Dict[str, Any]:
    """Confirm a specific appointment"""
    # Implementation with appointment ID validation

@app.tool("cancel_appointment")
async def cancel_appointment_tool(args: dict) -> Dict[str, Any]:
    """Cancel a specific appointment"""
    # Implementation with cancellation logic
```

#### MCP Tool Adapters (`app/mcp_tools.py`):
```python
# Lines 20-180: Adapter functions for LangChain integration

async def create_mcp_tools() -> List[BaseTool]:
    """Create MCP tools using stdio client"""
    # Real MCP protocol implementation
    
def create_fallback_tools() -> List[BaseTool]:
    """Fallback tools if MCP connection fails"""
    # Local implementations for reliability
```

### How MCP Works in the System:
1. **MCP Server** exposes appointment management functions
2. **LangGraph Agent** discovers and calls these tools
3. **Tool Execution** happens via MCP protocol
4. **Results** are returned to the conversation flow

---

## 🗄️ 4. Database Layer (`app/db.py` + `app/models.py`)

### What it does:
- Manages patient and appointment data
- Provides CRUD operations
- Handles database connections and transactions

### Key Frameworks Used:
- **SQLModel**: Type-safe ORM (SQLAlchemy + Pydantic)
- **SQLite**: Embedded database for MVP
- **Pydantic**: Data validation and serialization

### Technical Implementation:

#### Database Models (`app/models.py`):
```python
class Patient(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True)
    full_name: str
    dob: date  # Date of birth for verification
    phone_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Appointment(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True)
    patient_id: int = Field(foreign_key="patient.id")
    when_utc: datetime
    location: str
    doctor_name: str
    status: AppointmentStatus = Field(default=AppointmentStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

#### CRUD Operations (`app/db.py`):
```python
class PatientCRUD:
    @staticmethod
    def get_by_name_and_dob(db: Session, full_name: str, dob: date) -> Optional[Patient]:
        # Patient verification logic
        
class AppointmentCRUD:
    @staticmethod
    def get_by_patient_id(db: Session, patient_id: int) -> List[Appointment]:
        # Fetch patient appointments
        
    @staticmethod
    def confirm_appointment(db: Session, appointment_id: int, patient_id: int) -> Optional[Appointment]:
        # Confirm appointment logic
        
    @staticmethod
    def cancel_appointment(db: Session, appointment_id: int, patient_id: int) -> Optional[Appointment]:
        # Cancel appointment logic
```

#### Database Initialization:
```python
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def seed_database():
    # Creates sample patients and appointments for testing
    # João Silva, Maria Santos, Pedro Costa with appointments
```

---

## 🛡️ 5. Security System (`app/security.py`)

### What it does:
- Protects against abuse and unauthorized access
- Implements rate limiting and content filtering
- Provides guardrails for tool execution

### Key Frameworks Used:
- **Custom Guardrails**: Proprietary security system
- **Rate Limiting**: Per-session request limiting
- **Content Filtering**: PII detection and blocking

### Technical Implementation:

#### Security Architecture:
```python
class Guardrails:
    def __init__(self):
        self.rate_limits = {}  # Per-session rate tracking
        self.blocked_sessions = set()  # Blocked session IDs
        self.security_violations = {}  # Violation tracking
```

#### Tool Protection Decorator:
```python
def with_guardrails(tool_name: str):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 1. Before-tool security checks
            allowed, reason, violations = guardrails.before_tool_guardrails(...)
            
            if not allowed:
                return {"error": reason, "violations": violations}
            
            # 2. Execute tool
            result = await func(*args, **kwargs)
            
            # 3. After-tool security checks
            guardrails.after_tool_guardrails(...)
            
            return result
```

#### Rate Limiting Logic:
```python
def check_rate_limit(self, session_id: str, is_verified: bool = False) -> Tuple[bool, str]:
    limit = settings.RATE_LIMIT_VERIFIED_PER_MIN if is_verified else settings.RATE_LIMIT_UNVERIFIED_PER_MIN
    current_time = time.time()
    
    # Sliding window rate limiting implementation
```

---

## 💾 6. Session Management (`app/session_manager.py`)

### What it does:
- Tracks conversation state per user session
- Manages user verification status
- Provides thread-safe session operations

### Technical Implementation:

#### Session State Model:
```python
@dataclass
class SessionState:
    session_id: str
    is_verified: bool = False
    patient_id: Optional[int] = None
    last_intent: Optional[str] = None
    last_list: List[Dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
```

#### Thread-Safe Operations:
```python
class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        self._lock = threading.RLock()  # Thread safety
    
    def get_or_create_session(self, session_id: str) -> SessionState:
        with self._lock:
            # Thread-safe session creation/retrieval
```

#### Memory Management:
```python
def cleanup_expired_sessions(self, max_age_hours: int = 24):
    # Automatic cleanup of old sessions
    cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
```

---

## 📊 7. Observability (`app/observability.py`)

### What it does:
- Structured logging for debugging and monitoring
- PII masking for security compliance
- Performance tracking

### Key Frameworks Used:
- **Structlog**: Structured logging framework
- **JSON Logging**: Machine-readable log format

### Technical Implementation:

#### Logging Setup:
```python
def setup_logging():
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            mask_pii,  # Custom PII masking
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ]
    )
```

#### PII Masking:
```python
def mask_pii(logger, method_name, event_dict):
    # Automatically mask sensitive information in logs
    # Names, dates of birth, phone numbers, etc.
```

---

## ⚙️ 8. Configuration (`app/settings.py`)

### What it does:
- Centralized configuration management
- Environment-based settings
- Google Cloud Run compatibility

### Key Frameworks Used:
- **Pydantic Settings**: Type-safe configuration
- **Environment Variables**: 12-factor app compliance

### Technical Implementation:

#### Settings Model:
```python
class Settings(BaseSettings):
    # Claude API Configuration
    ANTHROPIC_API_KEY: str | None = Field(default=None)
    CLAUDE_MODEL: str = Field(default="claude-3-5-sonnet-20241022")
    
    # Database Configuration  
    DATABASE_URL: str = Field(default="sqlite:///./clinic.db")
    
    # Server Configuration
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8080)  # Cloud Run standard
    
    # Security Configuration
    RATE_LIMIT_VERIFIED_PER_MIN: int = Field(default=30)
    RATE_LIMIT_UNVERIFIED_PER_MIN: int = Field(default=10)
```

#### Cloud Detection:
```python
def is_cloud_run(self) -> bool:
    """Detect if running in Google Cloud Run"""
    return os.getenv("K_SERVICE") is not None
```

---

## 🐳 9. Containerization & Deployment

### Docker Configuration (`Dockerfile`):
```dockerfile
# Production-ready container
FROM python:3.11-slim

# Security: Non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

# Health check for Cloud Run
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Production command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
```

### Google Cloud Run Deployment (`deploy.sh`):
```bash
# Automated deployment script
gcloud run deploy lumahealth-api \
    --image gcr.io/${PROJECT_ID}/lumahealth-api \
    --platform managed \
    --region us-central1 \
    --set-secrets ANTHROPIC_API_KEY=anthropic-api-key:latest
```

---

## 🔄 System Flow: How Everything Works Together

### 1. User Interaction Flow:
```
User types message → Web UI JavaScript → POST /chat → FastAPI
```

### 2. Conversation Processing:
```
FastAPI → LangGraph Agent → Claude API → Tool Selection → MCP Tools
```

### 3. Database Operations:
```
MCP Tools → Database CRUD → SQLite → Response → User
```

### 4. Security & Logging:
```
Every request → Security Guardrails → Logging → Response
```

### 5. Memory Management:
```
Session Manager (in-memory) ↔ LangGraph Memory (persistent)
```

---

## 🧪 Testing the System

### 1. Start the Application:
```bash
# Local development
python -m uvicorn app.main:app --port 8080 --reload

# Docker
docker-compose up --build
```

### 2. Access the Web UI:
```
http://localhost:8080
```

### 3. Test Conversations:
```
1. "Sou João Silva, nascido em 15/03/1985" (verify identity)
2. "Liste minhas consultas" (list appointments)  
3. "Confirmar a primeira consulta" (confirm appointment)
4. "Cancelar consulta" (cancel appointment)
```

### 4. Monitor the System:
```
- Health: http://localhost:8080/health
- API Status: http://localhost:8080/api/status  
- Security: http://localhost:8080/security/summary
```

---

## 🚀 Production Deployment

### Environment Variables:
```bash
ANTHROPIC_API_KEY=your_claude_api_key
CLAUDE_MODEL=claude-3-5-sonnet-20241022
ENVIRONMENT=production
DEBUG=false
DATABASE_URL=sqlite:///./clinic.db
```

### Google Cloud Run:
```bash
./deploy.sh your-project-id us-central1
```

---

This system demonstrates a complete production-ready conversational AI implementation with modern frameworks, robust security, and cloud-native deployment capabilities.
