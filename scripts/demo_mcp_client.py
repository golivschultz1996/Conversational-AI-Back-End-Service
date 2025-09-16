"""
Demo MCP Client for LumaHealth Conversational AI Service.

This script demonstrates how to use the LumaHealth MCP server with LangChain
and LangGraph for conversational AI interactions. It shows the power of 
composing multiple MCP servers and using them with LangGraph agents.
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import create_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage


class LumaHealthMCPDemo:
    """
    Demonstration client for LumaHealth MCP integration.
    
    Shows how to connect to the MCP server and use it with LangGraph
    for natural language appointment management.
    """
    
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.tools = None
        self.agent = None
        
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
    
    async def setup_mcp_connection(self):
        """Setup connection to LumaHealth MCP server."""
        print("🔌 Connecting to LumaHealth MCP Server...")
        
        # Configure server parameters for stdio transport
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "app.mcp_server"],
            env=None
        )
        
        try:
            # Connect to MCP server
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    print("✅ Connected to MCP server successfully!")
                    
                    # Create tools from MCP session
                    self.tools = await create_mcp_tools(session)
                    print(f"🛠️  Loaded {len(self.tools)} tools from MCP server")
                    
                    for tool in self.tools:
                        print(f"   - {tool.name}: {tool.description}")
                    
                    # Create LangGraph agent with MCP tools
                    llm = ChatAnthropic(
                        model="claude-3-5-sonnet-20241022",
                        api_key=self.anthropic_api_key,
                        temperature=0.1
                    )
                    
                    self.agent = create_react_agent(llm, self.tools)
                    print("🤖 Created LangGraph agent with MCP tools")
                    
                    # Run interactive demo
                    await self.run_demo()
                    
        except Exception as e:
            print(f"❌ Error connecting to MCP server: {e}")
            print("Make sure the MCP server is running with: python -m app.mcp_server")
            raise
    
    async def run_demo(self):
        """Run interactive demonstration scenarios."""
        print("\\n" + "="*60)
        print("🩺 LumaHealth MCP Demo - Conversational AI Appointment Management")
        print("="*60)
        
        # Demo scenarios
        scenarios = [
            {
                "name": "User Verification",
                "message": f"Olá! Eu sou João Silva, nascido em 15/03/1985. Meu session ID é {self.session_id}. Por favor, verifique minha identidade.",
                "expected": "User should be verified successfully"
            },
            {
                "name": "List Appointments", 
                "message": f"Agora que estou verificado, você pode listar minhas consultas? Session ID: {self.session_id}",
                "expected": "Should list user's appointments"
            },
            {
                "name": "Confirm Appointment",
                "message": f"Quero confirmar minha consulta de amanhã com Dr. Carlos Mendes. Session ID: {self.session_id}",
                "expected": "Should confirm the specific appointment"
            },
            {
                "name": "Get Session Info",
                "message": f"Você pode me mostrar informações sobre minha sessão atual? Session ID: {self.session_id}",
                "expected": "Should show session status and info"
            }
        ]
        
        for i, scenario in enumerate(scenarios, 1):
            print(f"\\n📋 Scenario {i}: {scenario['name']}")
            print(f"Expected: {scenario['expected']}")
            print("-" * 40)
            
            try:
                # Execute scenario with agent
                response = await self.agent.ainvoke({
                    "messages": [HumanMessage(content=scenario['message'])]
                })
                
                # Extract and display response
                final_message = response['messages'][-1].content
                print(f"🤖 Agent Response:\\n{final_message}")
                
                # Add small delay between scenarios
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ Error in scenario: {e}")
        
        print("\\n" + "="*60)
        print("✅ Demo completed successfully!")
        print("="*60)
    
    async def run_interactive_mode(self):
        """Run interactive chat mode for manual testing."""
        print("\\n🗣️  Interactive Mode - Type 'quit' to exit")
        print(f"Your session ID: {self.session_id}")
        print("-" * 40)
        
        while True:
            try:
                user_input = input("\\nYou: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                # Add session ID to user input if not present
                if "session" not in user_input.lower():
                    user_input += f" (Session ID: {self.session_id})"
                
                # Get agent response
                response = await self.agent.ainvoke({
                    "messages": [HumanMessage(content=user_input)]
                })
                
                final_message = response['messages'][-1].content
                print(f"🤖 Assistant: {final_message}")
                
            except KeyboardInterrupt:
                print("\\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")


async def test_mcp_server_directly():
    """
    Test MCP server directly without LangChain for debugging.
    """
    print("🔧 Testing MCP server directly...")
    
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "app.mcp_server"]
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # List available tools
                tools = await session.list_tools()
                print(f"Available tools: {[tool.name for tool in tools.tools]}")
                
                # Test verify_user tool directly
                session_id = str(uuid.uuid4())
                result = await session.call_tool("verify_user", {
                    "session_id": session_id,
                    "full_name": "João Silva",
                    "dob": "1985-03-15"
                })
                
                print(f"Verification result: {result.content}")
                
                # Test list_appointments
                result = await session.call_tool("list_appointments", {
                    "session_id": session_id
                })
                
                print(f"Appointments: {result.content}")
                
    except Exception as e:
        print(f"❌ Direct test failed: {e}")


async def main():
    """Main function to run the demo."""
    print("🚀 Starting LumaHealth MCP Demo")
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="LumaHealth MCP Demo Client")
    parser.add_argument("--mode", choices=["demo", "interactive", "test"], 
                       default="demo", help="Demo mode to run")
    args = parser.parse_args()
    
    if args.mode == "test":
        await test_mcp_server_directly()
        return
    
    try:
        demo = LumaHealthMCPDemo()
        await demo.setup_mcp_connection()
        
        if args.mode == "interactive":
            await demo.run_interactive_mode()
            
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Make sure we have the required environment
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY environment variable is required")
        print("Please set it in your .env file or environment")
        sys.exit(1)
    
    asyncio.run(main())
