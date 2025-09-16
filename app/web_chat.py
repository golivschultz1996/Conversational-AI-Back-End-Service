"""
Simple Web Chat Interface for LumaHealth Conversational AI Service.

This module provides a simple web-based chat interface using FastAPI
static files and WebSocket for real-time communication.
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .session_manager import SessionManager
from .observability import setup_logging


# Setup logging
logger = setup_logging()

# Initialize web chat app (separate from main API)
web_app = FastAPI(title="LumaHealth Web Chat", version="0.1.0")

# Session manager for web chat
web_session_manager = SessionManager()

# Store active WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.session_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.session_connections[session_id] = websocket
        logger.info(f"WebSocket connected for session: {session_id}")

    def disconnect(self, websocket: WebSocket, session_id: str):
        self.active_connections.remove(websocket)
        if session_id in self.session_connections:
            del self.session_connections[session_id]
        logger.info(f"WebSocket disconnected for session: {session_id}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def send_to_session(self, message: str, session_id: str):
        if session_id in self.session_connections:
            websocket = self.session_connections[session_id]
            await self.send_personal_message(message, websocket)

manager = ConnectionManager()


# HTML template for the chat interface
CHAT_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>LumaHealth - Chat de Consultas</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .chat-container {
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 800px;
            height: 600px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .chat-header {
            background: #2c3e50;
            color: white;
            padding: 20px;
            text-align: center;
        }
        
        .chat-header h1 {
            margin: 0;
            font-size: 1.5em;
        }
        
        .chat-header .subtitle {
            opacity: 0.8;
            font-size: 0.9em;
            margin-top: 5px;
        }
        
        .session-info {
            background: #34495e;
            color: white;
            padding: 10px 20px;
            font-size: 0.8em;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .status-indicator {
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.7em;
            font-weight: bold;
        }
        
        .status-verified {
            background: #27ae60;
            color: white;
        }
        
        .status-unverified {
            background: #e74c3c;
            color: white;
        }
        
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: #f8f9fa;
        }
        
        .message {
            margin-bottom: 15px;
            display: flex;
            align-items: flex-start;
        }
        
        .message.user {
            justify-content: flex-end;
        }
        
        .message.assistant {
            justify-content: flex-start;
        }
        
        .message-content {
            max-width: 70%;
            padding: 12px 16px;
            border-radius: 18px;
            position: relative;
            word-wrap: break-word;
        }
        
        .message.user .message-content {
            background: #007bff;
            color: white;
            border-bottom-right-radius: 4px;
        }
        
        .message.assistant .message-content {
            background: white;
            border: 1px solid #e9ecef;
            border-bottom-left-radius: 4px;
        }
        
        .message-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            margin: 0 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2em;
            flex-shrink: 0;
        }
        
        .message.user .message-avatar {
            background: #007bff;
            color: white;
            order: 1;
        }
        
        .message.assistant .message-avatar {
            background: #28a745;
            color: white;
        }
        
        .message-time {
            font-size: 0.7em;
            opacity: 0.6;
            margin-top: 4px;
        }
        
        .chat-input {
            padding: 20px;
            background: white;
            border-top: 1px solid #e9ecef;
            display: flex;
            gap: 10px;
        }
        
        .chat-input input {
            flex: 1;
            padding: 12px 16px;
            border: 1px solid #ddd;
            border-radius: 25px;
            outline: none;
            font-size: 1em;
        }
        
        .chat-input input:focus {
            border-color: #007bff;
        }
        
        .chat-input button {
            padding: 12px 24px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-weight: bold;
            transition: background 0.3s;
        }
        
        .chat-input button:hover {
            background: #0056b3;
        }
        
        .chat-input button:disabled {
            background: #6c757d;
            cursor: not-allowed;
        }
        
        .connection-status {
            padding: 10px 20px;
            background: #28a745;
            color: white;
            text-align: center;
            font-size: 0.8em;
        }
        
        .connection-status.disconnected {
            background: #dc3545;
        }
        
        .typing-indicator {
            display: none;
            padding: 10px 20px;
            font-style: italic;
            color: #666;
            font-size: 0.9em;
        }
        
        .help-text {
            padding: 15px 20px;
            background: #e3f2fd;
            border-left: 4px solid #2196f3;
            margin: 10px 20px;
            border-radius: 4px;
            font-size: 0.9em;
            color: #1565c0;
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <h1>🩺 LumaHealth</h1>
            <div class="subtitle">Assistente Virtual para Consultas Médicas</div>
        </div>
        
        <div class="session-info">
            <span>Sessão: <span id="sessionId">Carregando...</span></span>
            <span class="status-indicator status-unverified" id="statusIndicator">Não Verificado</span>
        </div>
        
        <div class="connection-status" id="connectionStatus">Conectando...</div>
        
        <div class="help-text">
            💡 <strong>Como começar:</strong> Me diga seu nome completo e data de nascimento para verificar sua identidade.
            <br>Exemplo: "Eu sou João Silva, nascido em 15/03/1985"
        </div>
        
        <div class="chat-messages" id="chatMessages">
            <div class="message assistant">
                <div class="message-avatar">🤖</div>
                <div class="message-content">
                    Olá! Sou seu assistente virtual da LumaHealth. Para começar, preciso verificar sua identidade.
                    <br><br>Por favor, me informe seu nome completo e data de nascimento.
                    <div class="message-time" id="welcomeTime"></div>
                </div>
            </div>
        </div>
        
        <div class="typing-indicator" id="typingIndicator">
            🤖 Assistente está digitando...
        </div>
        
        <div class="chat-input">
            <input type="text" id="messageInput" placeholder="Digite sua mensagem..." maxlength="500">
            <button id="sendButton" onclick="sendMessage()">Enviar</button>
        </div>
    </div>

    <script>
        let ws = null;
        let sessionId = generateSessionId();
        let isVerified = false;
        
        function generateSessionId() {
            return 'web-' + Math.random().toString(36).substr(2, 9);
        }
        
        function formatTime(date = new Date()) {
            return date.toLocaleTimeString('pt-BR', { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
        }
        
        function updateSessionInfo() {
            document.getElementById('sessionId').textContent = sessionId;
            document.getElementById('welcomeTime').textContent = formatTime();
        }
        
        function updateConnectionStatus(connected) {
            const status = document.getElementById('connectionStatus');
            if (connected) {
                status.textContent = '🟢 Conectado ao servidor';
                status.className = 'connection-status';
            } else {
                status.textContent = '🔴 Desconectado do servidor';
                status.className = 'connection-status disconnected';
            }
        }
        
        function updateVerificationStatus(verified) {
            isVerified = verified;
            const indicator = document.getElementById('statusIndicator');
            if (verified) {
                indicator.textContent = '✅ Verificado';
                indicator.className = 'status-indicator status-verified';
            } else {
                indicator.textContent = '❌ Não Verificado';
                indicator.className = 'status-indicator status-unverified';
            }
        }
        
        function addMessage(content, isUser = false, timestamp = new Date()) {
            const messagesContainer = document.getElementById('chatMessages');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;
            
            const avatar = isUser ? '👤' : '🤖';
            const timeStr = formatTime(timestamp);
            
            messageDiv.innerHTML = `
                <div class="message-avatar">${avatar}</div>
                <div class="message-content">
                    ${content}
                    <div class="message-time">${timeStr}</div>
                </div>
            `;
            
            messagesContainer.appendChild(messageDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
        
        function showTyping(show = true) {
            const typing = document.getElementById('typingIndicator');
            typing.style.display = show ? 'block' : 'none';
        }
        
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/${sessionId}`;
            
            ws = new WebSocket(wsUrl);
            
            ws.onopen = function(event) {
                console.log('WebSocket connected');
                updateConnectionStatus(true);
                document.getElementById('sendButton').disabled = false;
            };
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                console.log('Received:', data);
                
                showTyping(false);
                
                if (data.type === 'chat_response') {
                    addMessage(data.reply, false);
                    
                    // Update verification status
                    if (data.state && data.state.is_verified !== undefined) {
                        updateVerificationStatus(data.state.is_verified);
                    }
                    
                    // Show observability info in console
                    if (data.observability) {
                        console.log('AI Metrics:', data.observability);
                    }
                } else if (data.type === 'error') {
                    addMessage(`❌ Erro: ${data.message}`, false);
                } else if (data.type === 'typing') {
                    showTyping(data.show);
                }
            };
            
            ws.onclose = function(event) {
                console.log('WebSocket disconnected');
                updateConnectionStatus(false);
                document.getElementById('sendButton').disabled = true;
                
                // Try to reconnect after 3 seconds
                setTimeout(connectWebSocket, 3000);
            };
            
            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
                updateConnectionStatus(false);
            };
        }
        
        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            
            if (!message || !ws || ws.readyState !== WebSocket.OPEN) {
                return;
            }
            
            // Add user message to chat
            addMessage(message, true);
            
            // Show typing indicator
            showTyping(true);
            
            // Send message via WebSocket
            ws.send(JSON.stringify({
                type: 'chat_message',
                message: message,
                session_id: sessionId
            }));
            
            // Clear input
            input.value = '';
        }
        
        // Event listeners
        document.getElementById('messageInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
        
        // Initialize
        updateSessionInfo();
        updateVerificationStatus(false);
        connectWebSocket();
        
        console.log('LumaHealth Web Chat initialized');
        console.log('Session ID:', sessionId);
    </script>
</body>
</html>
"""


@web_app.get("/", response_class=HTMLResponse)
async def get_chat_page():
    """Serve the chat interface."""
    return HTMLResponse(content=CHAT_HTML)


@web_app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time chat."""
    await manager.connect(websocket, session_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get('type') == 'chat_message':
                # Process the chat message
                user_message = message_data.get('message', '')
                
                # Import the chat processing logic from main app
                # For now, we'll simulate the response
                await process_websocket_message(websocket, session_id, user_message)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        manager.disconnect(websocket, session_id)


async def process_websocket_message(websocket: WebSocket, session_id: str, message: str):
    """Process a chat message and send response via WebSocket."""
    try:
        # Import here to avoid circular imports
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        import requests
        
        # Send to the main chat API
        response = requests.post(
            "http://localhost:8000/chat",
            json={
                "session_id": session_id,
                "message": message,
                "metadata": {"client": "web_chat"}
            },
            timeout=10
        )
        
        if response.status_code == 200:
            chat_response = response.json()
            
            # Send response back to client
            await websocket.send_text(json.dumps({
                "type": "chat_response",
                "reply": chat_response.get("reply", "Desculpe, não consegui processar sua mensagem."),
                "state": chat_response.get("state", {}),
                "observability": chat_response.get("observability", {})
            }))
        else:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Erro interno do servidor. Tente novamente."
            }))
            
    except Exception as e:
        logger.error(f"Error processing WebSocket message: {e}")
        await websocket.send_text(json.dumps({
            "type": "error", 
            "message": "Erro ao processar mensagem."
        }))


@web_app.get("/health")
async def web_health():
    """Health check for web chat service."""
    return {"status": "healthy", "service": "web_chat"}


if __name__ == "__main__":
    import uvicorn
    
    print("🌐 Starting LumaHealth Web Chat Interface...")
    print("💡 Access at: http://localhost:8001")
    print("📱 Open in your browser to start chatting!")
    
    uvicorn.run(
        web_app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
