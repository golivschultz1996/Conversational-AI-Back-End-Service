"""
Interactive Chat Client for LumaHealth Conversational AI Service.

This module provides a terminal-based interactive chat interface for testing
the conversational AI system. Users can chat naturally and see the full flow.
"""

import asyncio
import requests
import json
import uuid
import os
import sys
from datetime import datetime
from typing import Optional

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class LumaHealthChatClient:
    """
    Interactive chat client for testing the LumaHealth AI system.
    
    Provides a natural conversation interface with the FastAPI backend,
    managing sessions automatically and providing a rich chat experience.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session_id = str(uuid.uuid4())
        self.conversation_history = []
        self.is_verified = False
        self.patient_name = None
        
    def print_welcome(self):
        """Print welcome message and instructions."""
        print("🩺" + "="*60)
        print("   LumaHealth Conversational AI - Interactive Chat")
        print("="*63)
        print(f"📱 Session ID: {self.session_id}")
        print("💡 Commands:")
        print("   - Type normally to chat with the AI")
        print("   - 'clear' to clear screen")
        print("   - 'history' to see conversation history")  
        print("   - 'status' to see session status")
        print("   - 'quit' or 'exit' to quit")
        print("="*63)
        print("🤖 AI Assistant: Olá! Sou seu assistente para consultas médicas.")
        print("   Para começar, preciso verificar sua identidade.")
        print("   Por favor, me diga seu nome completo e data de nascimento.")
        print()
    
    def print_message(self, sender: str, message: str, timestamp: Optional[datetime] = None):
        """Print a formatted message."""
        if timestamp is None:
            timestamp = datetime.now()
        
        time_str = timestamp.strftime("%H:%M:%S")
        
        if sender == "user":
            icon = "👤"
            prefix = "Você"
        else:
            icon = "🤖"
            prefix = "Assistente"
        
        print(f"[{time_str}] {icon} {prefix}: {message}")
    
    def check_server_health(self) -> bool:
        """Check if the server is running and healthy."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=3)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def send_message(self, message: str) -> dict:
        """Send a message to the chat API."""
        try:
            payload = {
                "session_id": self.session_id,
                "message": message,
                "metadata": {"client": "interactive_terminal"}
            }
            
            response = requests.post(
                f"{self.base_url}/chat",
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "error": f"Server error: {response.status_code}",
                    "detail": response.text
                }
                
        except requests.exceptions.RequestException as e:
            return {
                "error": f"Connection error: {str(e)}",
                "suggestion": "Make sure the server is running with: uvicorn app.main:app --reload --port 8000"
            }
    
    def verify_user_directly(self, full_name: str, dob: str) -> dict:
        """Verify user directly using the verify endpoint."""
        try:
            payload = {
                "session_id": self.session_id,
                "full_name": full_name,
                "dob": dob
            }
            
            response = requests.post(
                f"{self.base_url}/verify",
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Verification failed: {response.status_code}"}
                
        except requests.exceptions.RequestException as e:
            return {"error": f"Connection error: {str(e)}"}
    
    def get_appointments(self) -> dict:
        """Get user appointments directly."""
        try:
            response = requests.get(
                f"{self.base_url}/appointments/{self.session_id}",
                timeout=5
            )
            
            if response.status_code == 200:
                return {"appointments": response.json()}
            else:
                return {"error": f"Failed to get appointments: {response.status_code}"}
                
        except requests.exceptions.RequestException as e:
            return {"error": f"Connection error: {str(e)}"}
    
    def handle_command(self, command: str) -> bool:
        """Handle special commands. Returns True if command was handled."""
        command = command.lower().strip()
        
        if command in ['quit', 'exit', 'q']:
            print("\\n👋 Obrigado por usar o LumaHealth! Até logo!")
            return True
        
        elif command == 'clear':
            os.system('clear' if os.name == 'posix' else 'cls')
            self.print_welcome()
            
        elif command == 'history':
            print("\\n📜 Histórico da Conversa:")
            print("-" * 40)
            for entry in self.conversation_history:
                self.print_message(entry['sender'], entry['message'], entry['timestamp'])
            print()
            
        elif command == 'status':
            print(f"\\n📊 Status da Sessão:")
            print(f"   Session ID: {self.session_id}")
            print(f"   Verificado: {'✅ Sim' if self.is_verified else '❌ Não'}")
            print(f"   Paciente: {self.patient_name or 'Não identificado'}")
            print(f"   Mensagens: {len(self.conversation_history)}")
            print()
            
        elif command.startswith('verify '):
            # Quick verification command: verify João Silva 1985-03-15
            parts = command.split(' ', 3)
            if len(parts) >= 4:
                name = f"{parts[1]} {parts[2]}"
                dob = parts[3]
                result = self.verify_user_directly(name, dob)
                if result.get('success'):
                    self.is_verified = True
                    self.patient_name = name
                    print(f"✅ {result['message']}")
                else:
                    print(f"❌ {result.get('message', 'Falha na verificação')}")
            else:
                print("❌ Uso: verify <Nome> <Sobrenome> <YYYY-MM-DD>")
            print()
            
        elif command == 'appointments':
            if self.is_verified:
                result = self.get_appointments()
                if 'appointments' in result:
                    appointments = result['appointments']
                    print(f"\\n📅 Suas Consultas ({len(appointments)}):")
                    for i, apt in enumerate(appointments, 1):
                        print(f"   {i}. {apt['when_utc'][:16]} - {apt['doctor_name']} ({apt['status']})")
                    print()
                else:
                    print(f"❌ {result.get('error', 'Erro ao buscar consultas')}")
            else:
                print("❌ Você precisa se verificar primeiro!")
                print()
        
        elif command == 'help':
            print("\\n💡 Comandos Disponíveis:")
            print("   clear          - Limpar tela")
            print("   history        - Ver histórico de conversa")
            print("   status         - Ver status da sessão")
            print("   verify <nome> <sobrenome> <data> - Verificação rápida")
            print("   appointments   - Listar consultas (se verificado)")
            print("   help           - Esta ajuda")
            print("   quit/exit      - Sair")
            print()
            
        else:
            return False  # Not a command
        
        return True
    
    def process_chat_response(self, response: dict):
        """Process and display chat response."""
        if 'error' in response:
            print(f"❌ Erro: {response['error']}")
            if 'suggestion' in response:
                print(f"💡 Sugestão: {response['suggestion']}")
            return
        
        # Display AI response
        reply = response.get('reply', 'Desculpe, não consegui processar sua mensagem.')
        self.print_message("assistant", reply)
        
        # Update session state
        state = response.get('state', {})
        if state.get('is_verified') and not self.is_verified:
            self.is_verified = True
            print("✅ Identidade verificada com sucesso!")
        
        # Show observability info if available
        obs = response.get('observability', {})
        if obs:
            intent = obs.get('intent', 'unknown')
            latency = obs.get('latency_ms', 0)
            print(f"   ℹ️  Intent: {intent} | Latência: {latency}ms")
        
        print()
    
    def run_interactive_chat(self):
        """Run the main interactive chat loop."""
        # Check server health
        if not self.check_server_health():
            print("❌ Erro: Não foi possível conectar ao servidor!")
            print("💡 Certifique-se de que o servidor está rodando:")
            print("   uvicorn app.main:app --reload --port 8000")
            return
        
        self.print_welcome()
        
        try:
            while True:
                # Get user input
                try:
                    user_input = input("👤 Você: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\\n👋 Até logo!")
                    break
                
                if not user_input:
                    continue
                
                # Add to history
                self.conversation_history.append({
                    'sender': 'user',
                    'message': user_input,
                    'timestamp': datetime.now()
                })
                
                # Handle commands
                if self.handle_command(user_input):
                    if user_input.lower().strip() in ['quit', 'exit', 'q']:
                        break
                    continue
                
                # Send to AI
                print("   ⏳ Processando...")
                response = self.send_message(user_input)
                
                # Process response
                self.process_chat_response(response)
                
                # Add AI response to history
                if 'reply' in response:
                    self.conversation_history.append({
                        'sender': 'assistant', 
                        'message': response['reply'],
                        'timestamp': datetime.now()
                    })
        
        except Exception as e:
            print(f"❌ Erro inesperado: {e}")
            
        finally:
            print("\\n📊 Estatísticas da Sessão:")
            print(f"   Mensagens trocadas: {len(self.conversation_history)}")
            print(f"   Status final: {'Verificado' if self.is_verified else 'Não verificado'}")


def main():
    """Main function to run the chat client."""
    import argparse
    
    parser = argparse.ArgumentParser(description="LumaHealth Interactive Chat Client")
    parser.add_argument("--url", default="http://localhost:8000", 
                       help="Base URL of the LumaHealth API server")
    parser.add_argument("--test", action="store_true",
                       help="Run a quick test conversation")
    
    args = parser.parse_args()
    
    client = LumaHealthChatClient(base_url=args.url)
    
    if args.test:
        # Quick test mode
        print("🧪 Modo de teste rápido...")
        if not client.check_server_health():
            print("❌ Servidor não está rodando!")
            return 1
        
        # Test conversation
        test_messages = [
            "Olá!",
            "Eu sou João Silva, nascido em 15/03/1985",
            "Quais são minhas consultas?",
            "Quero confirmar a primeira consulta"
        ]
        
        for msg in test_messages:
            print(f"👤 Teste: {msg}")
            response = client.send_message(msg)
            if 'reply' in response:
                print(f"🤖 Resposta: {response['reply'][:80]}...")
            print()
    
    else:
        # Interactive mode
        client.run_interactive_chat()
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
