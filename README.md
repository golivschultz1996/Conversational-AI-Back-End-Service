# 🏥 Medical Appointment Assistant

![Demo](demo.gif)

*Demo showing authentication test - first I intentionally made an error, then used a real name from the database to show successful authentication. After authentication, I proceed with appointment interactions like listing, confirming, and cancelling appointments.*

## 🚀 Quick Start with Docker

The easiest way to run this is with Docker:

```bash
# Clone and enter the project
git clone <your-repo>
cd your-folder

# Set your API key (modify env.example with your credentials)
cp env.example .env
# Edit .env with your ANTHROPIC_API_KEY

# Start everything
docker-compose up --build
```

Visit `http://localhost:8080` and start chatting!

## 🤖 What This Does

A conversational AI that helps patients manage medical appointments through natural language. Patients can:

- **Verify identity** using full name and date of birth
- **List appointments** - see all scheduled appointments  
- **Confirm appointments** - confirm pending appointments
- **Cancel appointments** - cancel existing appointments

All conversations happen in English and feel natural thanks to Claude Sonnet 4.

## 🔧 MCP Integration (Model Context Protocol)

This system uses MCP to expose appointment management as tools that the AI can use:

- `verify_user` - Authenticates patients using name + birthdate + phone number
- `list_appointments` - Fetches patient's appointments from database
- `confirm_appointment` - Updates appointment status to confirmed
- `cancel_appointment` - Cancels specific appointments

The MCP server runs alongside the main app and provides these tools to the LangGraph agent. This makes the system modular - you could easily swap out the appointment backend or add new tools.

## 💾 Database

Uses SQLite with two main tables:

**Patients**
- Full name, date of birth, phone hash
- Used for identity verification

**Appointments** 
- Date/time, location, doctor, status (pending/confirmed/cancelled)
- Linked to patients

The database comes pre-seeded with test data. You can add more using:

```bash
python scripts/seed_db.py
```

## 🧪 Testing Examples

Here are some conversations you can try:

### 1. Identity Verification
```
"I'm Maria Santos, born on July 22, 1990, phone +5511876543210"
```

### 2. List Appointments
```
"What are my appointments?"
"List my scheduled appointments"
```

### 3. Confirm Appointment
```
"I want to confirm my first appointment"
"Confirm tomorrow's appointment"
```

### 4. Cancel Appointment
```
"I need to cancel an appointment"
"Cancel the appointment with Dr. Pedro"
```

### Test Patients in Database

The system comes with these test patients:

- **Maria Santos** - DOB: 1990-07-22 - Phone: +5511876543210
- **Pedro Oliveira** - DOB: 1988-12-10 - Phone: +5511765432109
- **Ana Rodrigues** - DOB: 1992-05-18 - Phone: +5511654321098
- **Carlos Mendes** - DOB: 1975-09-03 - Phone: +5511543210987
- **Lucia Fernandes** - DOB: 1983-11-30 - Phone: +5511432109876

Try authenticating with any of these to see the system in action.

## 🛠️ Development

Local development without Docker:

```bash
# Setup environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt

# Set environment variables
cp env.example .env
# Edit .env with your ANTHROPIC_API_KEY

# Initialize database
python scripts/seed_db.py

# Run the server
uvicorn app.main:app --reload --port 8080
```

## 📊 Monitoring

- Health check: `http://localhost:8080/health`
- API status: `http://localhost:8080/api/status`
- Security summary: `http://localhost:8080/security/summary`

## 🔒 Security Features

- Rate limiting (different limits for verified vs unverified users)
- PII protection in logs
- Session isolation between patients
- Input validation and content filtering

---

The system uses FastAPI + LangGraph + MCP server + Claude Sonnet 4 for natural conversations with robust security and monitoring built-in.