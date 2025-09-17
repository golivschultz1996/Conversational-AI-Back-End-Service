# 🏗️ LumaHealth Architecture Documentation

## 📋 Overview

LumaHealth is a production-ready conversational AI system designed for healthcare appointment management. The architecture follows modern microservices principles with a focus on security, scalability, and observability.

## 🎯 System Goals

- **Conversational AI**: Natural language appointment management
- **Security-First**: PII protection and robust authentication
- **Cloud-Native**: Optimized for containerized deployment
- **Observable**: Comprehensive logging and monitoring
- **Scalable**: Horizontal scaling with stateless design

## 🧩 High-Level Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Browser   │    │   API Client    │    │  Mobile App     │
│                 │    │                 │    │                 │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │                         │
                    │     LumaHealth API      │
                    │   (Docker Container)    │
                    │                         │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
    ┌─────────▼─────────┐ ┌─────▼─────┐ ┌─────────▼─────────┐
    │                   │ │           │ │                   │
    │   Claude 3.5      │ │ SQLite DB │ │ Google Secret     │
    │   Sonnet API      │ │           │ │ Manager           │
    │                   │ │           │ │                   │
    └───────────────────┘ └───────────┘ └───────────────────┘
```

## 📁 Code Structure & Components

### Core Application (`/app`)

```
app/
├── main.py              # 🚀 FastAPI app + Web UI
├── settings.py          # ⚙️  Configuration management
├── graph.py             # 🧠 LangGraph conversation orchestration
├── mcp_server.py        # 🔧 MCP server implementation
├── mcp_tools.py         # 🛠️  MCP tool adapters
├── db.py                # 🗄️  Database layer (SQLModel)
├── models.py            # 📝 Pydantic data models
├── security.py          # 🛡️  Security & guardrails
├── session_manager.py   # 💾 Session state management
└── observability.py     # 📊 Logging & monitoring
```

### Deployment Configuration

```
├── Dockerfile           # 🐳 Production container
├── docker-compose.yml   # 🔧 Local development
└── .dockerignore        # 📋 Container optimization
```

## 🔧 Technology Stack Breakdown

### Web Framework - FastAPI (`main.py`)
- **Purpose**: HTTP API server and web UI hosting
- **Key Features**:
  - Integrated HTML chat interface at root (`/`)
  - RESTful API endpoints (`/chat`, `/health`, `/api/status`)
  - Automatic OpenAPI documentation
  - CORS middleware configuration
  - Lifespan management for startup/shutdown

**Code Example**:
```python
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, db: Session = Depends(get_session)):
    # Main conversational endpoint using LangGraph agent
    result = await langgraph_agent.process_conversation(
        session_id=session_id, message=request.message
    )
```

### Configuration Management (`settings.py`)
- **Framework**: Pydantic Settings
- **Purpose**: Centralized, type-safe configuration
- **Features**:
  - Environment-based configuration
  - Production environment detection
  - Environment variable configuration
  - Production/development modes

**Code Example**:
```python
class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str | None = Field(default=None)
    CLAUDE_MODEL: str = Field(default="claude-3-5-sonnet-20241022")
    ENVIRONMENT: str = Field(default="development")
    
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"
```

### Conversation Engine (`graph.py`)
- **Framework**: LangGraph + LangChain
- **Purpose**: Advanced conversation flow management
- **Architecture**: ReAct agent pattern with tools
- **Features**:
  - Persistent conversation memory
  - Claude 3.5 Sonnet integration
  - Tool execution orchestration
  - Fallback to simple NLU

**Key Components**:
```python
class LumaHealthAgent:
    def __init__(self, anthropic_api_key: str, session_manager: SessionManager):
        self.llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")
        self.memory = MemorySaver()
        self.graph = create_react_agent(self.llm, tools)
```

### MCP Integration (`mcp_server.py`, `mcp_tools.py`)
- **Framework**: FastMCP + LangChain MCP Adapters
- **Purpose**: Expose appointment actions as consumable tools
- **Architecture**: 
  - FastMCP server exposing structured tools
  - LangChain adapters for agent integration
  - Fallback implementations for reliability

**Tools Exposed**:
- `verify_user`: Patient identity verification
- `list_appointments`: Fetch patient appointments
- `confirm_appointment`: Confirm specific appointment
- `cancel_appointment`: Cancel specific appointment

### Database Layer (`db.py`, `models.py`)
- **Framework**: SQLModel (SQLAlchemy + Pydantic)
- **Database**: SQLite (production-ready for MVP)
- **Features**:
  - Type-safe ORM models
  - Automatic table creation
  - CRUD operations with proper relationships
  - Seed data for testing

**Schema Design**:
```python
class Patient(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True)
    full_name: str
    dob: date
    phone_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Appointment(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True)
    patient_id: int = Field(foreign_key="patient.id")
    when_utc: datetime
    location: str
    doctor_name: str
    status: AppointmentStatus = Field(default=AppointmentStatus.PENDING)
```

### Security Layer (`security.py`)
- **Framework**: Custom guardrails system
- **Purpose**: Multi-layered security protection
- **Features**:
  - Rate limiting (verified vs unverified users)
  - Content filtering and PII detection
  - Session blocking for violations
  - Pre/post-tool execution checks

**Security Architecture**:
```python
class Guardrails:
    def before_tool_guardrails(self, session_id: str, message: str, 
                              tool_name: str, is_verified: bool):
        # Rate limiting, content filtering, access control
        
    def after_tool_guardrails(self, session_id: str, tool_name: str, 
                             result: Any):
        # Output validation, PII masking
```

### Session Management (`session_manager.py`)
- **Architecture**: Thread-safe in-memory store
- **Purpose**: Stateful conversation tracking
- **Features**:
  - Session creation and lifecycle management
  - Verification state tracking
  - Automatic cleanup and expiration
  - Concurrent access protection

### Observability (`observability.py`)
- **Framework**: Structlog
- **Purpose**: Production monitoring and debugging
- **Features**:
  - JSON structured logging
  - Automatic PII masking
  - Request/response tracking
  - Performance metrics

## 🔄 Request Flow

### 1. User Interaction Flow
```
User Input → Web UI → FastAPI → LangGraph Agent → Tools → Database → Response
     ↓                                ↓              ↓
Session State              Security Guardrails    Logging
```

### 2. Conversation Processing
```python
# Simplified flow in graph.py
async def process_conversation(self, session_id: str, message: str):
    # 1. Load conversation history
    config = {"configurable": {"thread_id": session_id}}
    
    # 2. Prepare messages
    messages = [HumanMessage(content=message)]
    
    # 3. Execute with tools
    result = await self.graph.ainvoke({"messages": messages}, config=config)
    
    # 4. Update session state
    # 5. Return formatted response
```

### 3. Security Check Flow
```python
# Before every tool execution
@with_guardrails("verify_user")
async def verify_user_tool(args: dict) -> Dict[str, Any]:
    # Security checks applied automatically
    # Rate limiting, content filtering, access control
```

## ☁️ Deployment Architecture

### Production Deployment Configuration
- **Container**: Single container deployment
- **Scaling**: Configurable instances
- **Resources**: 1 CPU, 1GB RAM
- **Network**: Public HTTPS endpoint
- **Secrets**: Environment variable configuration

### Production Optimizations
- **Non-root container user** for security
- **Health checks** for reliability
- **Structured logging** for observability
- **Environment-based configuration**
- **Resource limits** for cost control

### Database Strategy
- **Current**: SQLite in container (stateless-friendly)
- **Production Option**: PostgreSQL or other cloud databases
- **Migration Path**: DATABASE_URL configuration switch

**Database URL Examples**:
```bash
# SQLite (current)
DATABASE_URL=sqlite:///./clinic.db

# PostgreSQL (Production)
DATABASE_URL=postgresql://user:pass@host:5432/lumahealth
```

## 🔐 Security Architecture

### Multi-Layer Security Model
1. **Transport**: HTTPS (production default)
2. **Authentication**: Patient verification via name + DOB
3. **Authorization**: Session-based access control
4. **Rate Limiting**: Per-session and global limits
5. **Content Filtering**: PII detection and blocking
6. **Audit Logging**: All interactions logged securely

### Data Protection
- **PII Masking**: Automatic in logs
- **Session Isolation**: No cross-session data leakage
- **Database Security**: Parameterized queries
- **Secret Management**: Google Secret Manager

## 📊 Monitoring & Observability

### Logging Strategy
```python
# All interactions logged with structure
{
    "timestamp": "2024-01-15T10:30:00Z",
    "session_id": "sess-abc123",
    "intent": "list_appointments",
    "latency_ms": 245,
    "success": true,
    "tools_used": ["verify_user", "list_appointments"],
    "user_message": "[MASKED]",
    "bot_response": "You have 2 appointments..."
}
```

### Health Monitoring
- **Application Health**: `/health` endpoint
- **Service Status**: `/api/status` with component status
- **Security Metrics**: `/security/summary` for guardrails
- **Container Health**: Docker HEALTHCHECK directive

### Performance Metrics
- Response latency per endpoint
- Tool execution timing
- Session creation/expiration rates
- Security violation frequency

## 🚀 Scalability Considerations

### Current Architecture Benefits
- **Stateless Design**: Session data can be externalized
- **Horizontal Scaling**: Container auto-scaling
- **Database Independence**: SQLite → PostgreSQL migration path
- **Tool Modularity**: MCP tools can be distributed

### Future Scaling Options
1. **Database**: Migrate to PostgreSQL or other production databases
2. **Session Store**: Redis for shared session state
3. **Tool Distribution**: Separate MCP services
4. **Load Balancing**: Multiple container instances
5. **Caching**: Response caching for common queries

## 🔄 Development Workflow

### Local Development
```bash
# Environment setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configuration
cp env.example .env
# Edit .env with ANTHROPIC_API_KEY

# Run with auto-reload
uvicorn app.main:app --reload --port 8080
```

### Testing Strategy
- **Unit Tests**: Individual component testing
- **Integration Tests**: Full conversation flows
- **Load Testing**: Performance under scale
- **Security Testing**: Penetration testing

### Deployment Pipeline
```bash
# Local testing
docker-compose up --build

# Production deployment
docker-compose up --build

# Monitoring
docker-compose logs -f
```

## 📈 Future Architecture Evolution

### Microservices Migration Path
1. **MCP Services**: Extract tools to separate services
2. **Session Service**: Dedicated session management
3. **Notification Service**: Appointment reminders
4. **Analytics Service**: Usage analytics and insights
5. **Admin Service**: Healthcare provider dashboard

### Enhanced AI Capabilities
- **Multi-language Support**: I18n for global deployment
- **Voice Interface**: Speech-to-text integration
- **Advanced NLU**: Intent classification improvements
- **Personalization**: User preference learning

---

This architecture provides a solid foundation for a production healthcare conversational AI system with clear paths for scaling and enhancement.
