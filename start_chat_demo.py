#!/usr/bin/env python3
"""
LumaHealth Chat Demo Startup Script

This script starts the necessary services and provides easy access
to different chat interfaces for testing the conversational AI system.
"""

import os
import sys
import time
import signal
import subprocess
import threading
import webbrowser
from pathlib import Path


class ChatDemoManager:
    """Manages the startup and coordination of chat demo services."""
    
    def __init__(self):
        self.processes = []
        self.base_dir = Path(__file__).parent
        self.venv_python = self.base_dir / "venv" / "bin" / "python"
        
        if not self.venv_python.exists():
            self.venv_python = self.base_dir / "venv" / "Scripts" / "python.exe"  # Windows
        
        if not self.venv_python.exists():
            self.venv_python = "python"  # Fallback to system python
    
    def print_banner(self):
        """Print welcome banner."""
        print("🩺" + "="*70)
        print("    LumaHealth Conversational AI - Chat Demo Manager")  
        print("="*73)
        print("🚀 Starting services for interactive chat testing...")
        print()
    
    def check_dependencies(self):
        """Check if required dependencies are available."""
        try:
            import requests
            import fastapi
            import uvicorn
            print("✅ Dependencies check passed")
            return True
        except ImportError as e:
            print(f"❌ Missing dependency: {e}")
            print("💡 Run: pip install -r requirements.txt")
            return False
    
    def start_api_server(self):
        """Start the FastAPI server."""
        print("📡 Starting FastAPI server on port 8000...")
        
        api_cmd = [
            str(self.venv_python), "-m", "uvicorn", 
            "app.main:app", 
            "--host", "0.0.0.0", 
            "--port", "8000",
            "--reload"
        ]
        
        process = subprocess.Popen(
            api_cmd,
            cwd=self.base_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        self.processes.append(("API Server", process))
        return process
    
    def start_web_chat(self):
        """Start the web chat interface."""
        print("🌐 Starting Web Chat interface on port 8001...")
        
        web_cmd = [str(self.venv_python), "app/web_chat.py"]
        
        process = subprocess.Popen(
            web_cmd,
            cwd=self.base_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        self.processes.append(("Web Chat", process))
        return process
    
    def wait_for_server(self, url, timeout=30):
        """Wait for a server to become available."""
        import requests
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    return True
            except requests.RequestException:
                pass
            time.sleep(1)
        return False
    
    def show_menu(self):
        """Show the main menu options."""
        print("\\n" + "="*50)
        print("🎯 CHAT INTERFACES AVAILABLE:")
        print("="*50)
        print("1️⃣  Terminal Chat (Interactive CLI)")
        print("    → Rich terminal interface with commands")
        print("    → Best for testing and development")
        print()
        print("2️⃣  Web Chat (Browser Interface)")  
        print("    → Beautiful web interface")
        print("    → Real-time WebSocket communication")
        print("    → Open: http://localhost:8001")
        print()
        print("3️⃣  Quick Test (Automated)")
        print("    → Run predefined test conversation")
        print("    → Good for quick functionality check")
        print()
        print("4️⃣  API Testing (curl examples)")
        print("    → Direct HTTP API calls")
        print("    → For API integration testing")
        print()
        print("💡 Commands:")
        print("   1/terminal  - Start terminal chat")
        print("   2/web       - Open web chat")
        print("   3/test      - Run quick test")
        print("   4/api       - Show API examples")
        print("   status      - Show service status")
        print("   quit/exit   - Stop all services")
        print("="*50)
    
    def start_terminal_chat(self):
        """Start the terminal chat interface."""
        print("\\n🖥️  Starting Terminal Chat Interface...")
        print("💡 Type 'help' in chat for available commands")
        print("💡 Use Ctrl+C to return to main menu")
        print("-" * 50)
        
        try:
            chat_cmd = [str(self.venv_python), "app/chat_client.py"]
            subprocess.run(chat_cmd, cwd=self.base_dir)
        except KeyboardInterrupt:
            print("\\n👋 Returning to main menu...")
        except Exception as e:
            print(f"❌ Error starting terminal chat: {e}")
    
    def open_web_chat(self):
        """Open web chat in browser."""
        url = "http://localhost:8001"
        print(f"\\n🌐 Opening web chat: {url}")
        
        try:
            webbrowser.open(url)
            print("✅ Web chat opened in browser")
            print("💡 If browser didn't open, visit: http://localhost:8001")
        except Exception as e:
            print(f"❌ Could not open browser: {e}")
            print(f"💡 Manually visit: {url}")
    
    def run_quick_test(self):
        """Run quick automated test."""
        print("\\n🧪 Running Quick Test Conversation...")
        print("-" * 40)
        
        try:
            test_cmd = [str(self.venv_python), "app/chat_client.py", "--test"]
            result = subprocess.run(test_cmd, cwd=self.base_dir, 
                                  capture_output=True, text=True)
            
            print(result.stdout)
            if result.stderr:
                print("Errors:", result.stderr)
                
        except Exception as e:
            print(f"❌ Test failed: {e}")
    
    def show_api_examples(self):
        """Show API testing examples."""
        print("\\n🔧 API Testing Examples:")
        print("-" * 40)
        print("💡 Make sure the API server is running on port 8000")
        print()
        
        examples = [
            ("Health Check", "curl http://localhost:8000/health"),
            ("Chat Message", """curl -X POST http://localhost:8000/chat \\
  -H "Content-Type: application/json" \\
  -d '{"message": "Eu sou João Silva, nascido em 15/03/1985", "session_id": "test"}'"""),
            ("Verify User", """curl -X POST http://localhost:8000/verify \\
  -H "Content-Type: application/json" \\
  -d '{"session_id": "test", "full_name": "João Silva", "dob": "1985-03-15"}'"""),
            ("List Appointments", "curl http://localhost:8000/appointments/test")
        ]
        
        for i, (name, command) in enumerate(examples, 1):
            print(f"{i}. {name}:")
            print(f"   {command}")
            print()
    
    def show_status(self):
        """Show status of running services."""
        print("\\n📊 Service Status:")
        print("-" * 30)
        
        # Check processes
        for name, process in self.processes:
            if process.poll() is None:
                print(f"✅ {name}: Running (PID: {process.pid})")
            else:
                print(f"❌ {name}: Stopped")
        
        # Check server endpoints
        endpoints = [
            ("API Server", "http://localhost:8000/health"),
            ("Web Chat", "http://localhost:8001/health")
        ]
        
        for name, url in endpoints:
            try:
                import requests
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    print(f"🌐 {name}: Accessible ({url})")
                else:
                    print(f"⚠️  {name}: Error {response.status_code}")
            except Exception:
                print(f"❌ {name}: Not accessible ({url})")
    
    def cleanup(self):
        """Stop all running processes."""
        print("\\n🛑 Stopping all services...")
        
        for name, process in self.processes:
            try:
                if process.poll() is None:
                    print(f"   Stopping {name}...")
                    process.terminate()
                    time.sleep(1)
                    
                    if process.poll() is None:
                        process.kill()
                        
            except Exception as e:
                print(f"   Error stopping {name}: {e}")
        
        print("✅ All services stopped")
    
    def run(self):
        """Run the main demo manager."""
        try:
            self.print_banner()
            
            if not self.check_dependencies():
                return 1
            
            # Start services
            api_process = self.start_api_server()
            time.sleep(2)  # Give API server time to start
            
            web_process = self.start_web_chat()
            time.sleep(2)  # Give web chat time to start
            
            # Wait for services to be ready
            print("⏳ Waiting for services to start...")
            
            if self.wait_for_server("http://localhost:8000/health"):
                print("✅ API server ready")
            else:
                print("❌ API server failed to start")
                return 1
            
            if self.wait_for_server("http://localhost:8001/health"):
                print("✅ Web chat ready")
            else:
                print("⚠️  Web chat may not be fully ready")
            
            # Main interaction loop
            while True:
                self.show_menu()
                
                try:
                    choice = input("\\n👉 Choose an option: ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    break
                
                if choice in ['1', 'terminal']:
                    self.start_terminal_chat()
                elif choice in ['2', 'web']:
                    self.open_web_chat()
                elif choice in ['3', 'test']:
                    self.run_quick_test()
                elif choice in ['4', 'api']:
                    self.show_api_examples()
                elif choice == 'status':
                    self.show_status()
                elif choice in ['quit', 'exit', 'q']:
                    break
                else:
                    print("❌ Invalid option. Try again.")
            
        except KeyboardInterrupt:
            print("\\n👋 Interrupted by user")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
        finally:
            self.cleanup()
        
        return 0


def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == '--auto-web':
        # Quick start mode - just open web interface
        manager = ChatDemoManager()
        api_process = manager.start_api_server()
        web_process = manager.start_web_chat()
        
        time.sleep(3)
        manager.open_web_chat()
        
        try:
            input("\\nPress Enter to stop services...")
        except KeyboardInterrupt:
            pass
        finally:
            manager.cleanup()
    else:
        # Full interactive mode
        manager = ChatDemoManager()
        return manager.run()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
