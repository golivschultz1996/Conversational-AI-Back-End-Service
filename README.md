# LumaHealth Conversational AI Service

A conversational AI back-end service for healthcare appointment management, demonstrating advanced integration between **FastAPI**, **LangGraph**, and **Model Context Protocol (MCP)**.

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)
![LangChain](https://img.shields.io/badge/LangChain-0.3+-purple.svg)
![MCP](https://img.shields.io/badge/MCP-1.14+-orange.svg)

## 🎯 Overview

This project implements a conversational AI service that allows patients to:
- ✅ **Verify identity** using name and date of birth
- 📋 **List appointments** with natural language queries
- ✅ **Confirm appointments** through conversational interaction
- ❌ **Cancel appointments** when needed

### 🏗️ Architecture Highlights

- **Dual Interface**: Both REST API and MCP protocol support
- **LangGraph Integration**: State-managed conversational flows
- **Multi-Server MCP**: Composable microservices architecture
- **Production Ready**: Observability, security, and testing built-in

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Anthropic API key (for Claude integration)

### Installation

1. **Clone and setup:**
   ```bash
   git clone <repository-url>
   cd LumaHealth
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   cp env.example .env
   # Edit .env and add your ANTHROPIC_API_KEY
   ```

4. **Initialize database:**
   ```bash
   python scripts/seed_db.py
   ```

### Running the Services

#### Start REST API Server
```bash
make run-api
# OR
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Start MCP Server (separate terminal)
```bash
make run-mcp
# OR  
python -m app.mcp_server
```

#### Run Demo Client
```bash
make demo
# OR
python scripts/demo_mcp_client.py
```

## 📡 API Usage

### REST API Examples

```bash
# Health check
curl http://localhost:8000/health

# Chat endpoint
curl -X POST http://localhost:8000/chat \\
  -H "Content-Type: application/json" \\
  -d '{
    "message": "Olá, eu sou João Silva, nascido em 15/03/1985",
    "session_id": "test-session"
  }'

# Verify user
curl -X POST http://localhost:8000/verify \\
  -H "Content-Type: application/json" \\
  -d '{
    "session_id": "test-session",
    "full_name": "João Silva", 
    "dob": "1985-03-15"
  }'

# List appointments (after verification)
curl http://localhost:8000/appointments/test-session
```

### MCP Integration Examples

#### Python Client with LangChain
```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import create_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic

# Connect to MCP server
server_params = StdioServerParameters(
    command="python", args=["-m", "app.mcp_server"]
)

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        
        # Create tools from MCP
        tools = await create_mcp_tools(session)
        
        # Create agent
        llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")
        agent = create_react_agent(llm, tools)
        
        # Use agent
        response = await agent.ainvoke({
            "messages": ["Listar minhas consultas para sessão test-123"]
        })
```

#### Multi-Server Composition
```python
from langchain_mcp_adapters.client import MultiServerMCPClient

# Connect to multiple MCP servers
client = MultiServerMCPClient({
    "clinic": {
        "command": "python", 
        "args": ["-m", "app.mcp_server"],
        "transport": "stdio"
    },
    "text": {
        "command": "python", 
        "args": ["scripts/text_server.py"],
        "transport": "stdio"  
    }
})

# Agent automatically chooses appropriate tools
tools = await client.get_tools()
agent = create_react_agent(llm, tools)
```

## 🛠️ Development

### Project Structure
```
LumaHealth/
├── app/
│   ├── main.py              # FastAPI application
│   ├── mcp_server.py        # MCP server implementation
│   ├── models.py            # Data models & schemas
│   ├── db.py                # Database & CRUD operations
│   ├── session_manager.py   # Session state management
│   ├── observability.py     # Logging & metrics
│   └── tests/               # Test suite
├── scripts/
│   ├── demo_mcp_client.py   # MCP demo client
│   ├── text_server.py       # Text processing MCP server
│   └── seed_db.py           # Database seeding
├── data/                    # Sample data & fixtures
├── requirements.txt         # Python dependencies
├── Makefile                 # Development commands
└── README.md               # This file
```

### Available Commands

```bash
# Development
make install                 # Install dependencies
make dev                     # Setup development environment

# Running services
make run-api                 # Start FastAPI server
make run-mcp                 # Start MCP server  
make demo                    # Run demo client

# Testing & Quality
make test                    # Run tests
make lint                    # Run linting
make format                  # Format code

# Database
python scripts/seed_db.py    # Seed database with sample data

# Docker
make docker-build            # Build Docker image
make docker-up              # Run with Docker Compose
```

## 🔧 MCP Tools Available

### Clinic Assistant Tools (`app.mcp_server`)

| Tool | Description | Parameters |
|------|-------------|------------|
| `verify_user` | Verify patient identity | `session_id`, `full_name`, `dob` |
| `list_appointments` | List patient appointments | `session_id` |
| `confirm_appointment` | Confirm an appointment | `session_id`, `appointment_id?`, `date?`, `time?` |
| `cancel_appointment` | Cancel an appointment | `session_id`, `appointment_id?`, `date?`, `time?` |
| `get_session_info` | Get session status | `session_id` |

### Text Processor Tools (`scripts.text_server`)

| Tool | Description | Parameters |
|------|-------------|------------|
| `normalize_date_pt_br` | Normalize Portuguese dates | `date_text` |
| `normalize_time_pt_br` | Normalize Portuguese times | `time_text` |
| `extract_patient_info` | Extract patient info from text | `text` |
| `clean_and_validate_text` | Clean and validate text | `text`, `max_length?` |

## 🔒 Security & Privacy

- **PII Protection**: Phone numbers are hashed, no plain text PII in logs
- **Session Isolation**: Session-based verification prevents cross-patient access
- **Input Sanitization**: Text cleaning and validation for all inputs
- **Rate Limiting**: Built-in protection against abuse
- **Guardrails**: Content filtering and safety checks

## 📊 Observability

### Structured Logging
All interactions are logged with:
- Session ID and patient ID (anonymized)
- Intent detection and tool usage
- Response times and success rates
- Conversation flow tracking

### Metrics Collection
- Request counts and error rates
- Average response times (p50/p95)
- Tool usage statistics
- Session lifecycle metrics

### Example Log Output
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "session_id": "abc123",
  "intent": "list_appointments", 
  "latency_ms": 145,
  "success": true,
  "tools_used": ["list_appointments"],
  "masked_message": "listar minhas consultas"
}
```

## 🧪 Testing

### Sample Test Data

The database is seeded with sample patients and appointments:

**Test Patient:**
- Name: João Silva
- DOB: 1985-03-15  
- Phone: +5511987654321

**Test Conversations:**
```
User: "Olá, eu sou João Silva, nascido em 15/03/1985"
Bot: "Verificação realizada com sucesso!"

User: "Quais são minhas consultas?"
Bot: "Você tem 2 consulta(s): 1. 2024-01-16 às 14:00 - Dr. Carlos Mendes..."

User: "Quero confirmar a consulta de amanhã"  
Bot: "Consulta confirmada com sucesso!"
```

### Running Tests
```bash
# Unit tests
pytest app/tests/unit -v

# Integration tests  
pytest app/tests/integration -v

# Conversation tests
pytest app/tests/conversations -v

# Full test suite
make test
```

## 🚀 Deployment

### Docker Deployment
```bash
# Build and run
make docker-build
make docker-up

# Or with Docker Compose
docker-compose up --build
```

### Production Considerations

1. **Environment Variables:**
   - Set `ENVIRONMENT=production`
   - Configure `DATABASE_URL` for PostgreSQL
   - Add `REDIS_URL` for session storage
   - Set proper `SESSION_SECRET_KEY`

2. **Security:**
   - Enable HTTPS/TLS
   - Configure CORS properly  
   - Set up rate limiting
   - Use secrets management

3. **Monitoring:**
   - Enable OpenTelemetry tracing
   - Configure log aggregation
   - Set up health checks
   - Monitor MCP server availability

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Run the test suite (`make test`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## 📚 Architecture Deep Dive

### MCP Integration Benefits

1. **Interoperability**: Tools work with any MCP-compatible client
2. **Composability**: Multiple servers can be combined seamlessly  
3. **Standardization**: Following MCP protocol ensures compatibility
4. **Tool Reuse**: Same tools work in different contexts

### LangGraph State Management

The system uses LangGraph for conversation state management:
- **Session State**: User verification, patient ID, conversation context
- **Tool Routing**: Automatic selection of appropriate MCP tools
- **Error Handling**: Graceful fallbacks and error recovery
- **Checkpoints**: Conversation state persistence

### Performance Characteristics

- **REST API**: ~100-200ms average response time
- **MCP Tools**: ~50-150ms per tool call
- **Database**: SQLite for development, PostgreSQL recommended for production
- **Concurrency**: FastAPI's async support for high throughput

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Anthropic** for the Claude API and MCP protocol
- **LangChain** for the excellent integration framework  
- **FastAPI** for the robust async web framework
- **LumaHealth** for the healthcare use case inspiration

---

**Built with ❤️ for the future of conversational AI in healthcare**
