from working_gemini_client import MCPClient as GeminiClient
from openAI_client import MCPClient as OpenAIClient
from claude_client import MCPClient as ClaudeClient
from dotenv import load_dotenv
from typing import Literal, Optional
from mcp import ClientSession
from contextlib import AsyncExitStack

load_dotenv()


class MainClient:
    def __init__(self, llm_provider: Literal["anthropic", "openai", "gemini"] = "gemini"):
        """
        Initialize the main client manager that can switch between different LLM providers.
        All clients share a single MCP connection.
        """
        self.session: Optional[ClientSession] = None
        self.llm_provider = llm_provider
        self.gemini_client = None
        self.openai_client = None
        self.claude_client = None
        self.current_client = None
        self.exit_stack = AsyncExitStack()
        
        # Initialize all clients but don't connect yet
        self.gemini_client = GeminiClient()
        self.openai_client = OpenAIClient()  
        self.claude_client = ClaudeClient()
        
        # Set the current client based on the provider
        self._switch_client(llm_provider)

    def _switch_client(self, provider: Literal["anthropic", "openai", "gemini"]):
        """Switch the current active client"""
        self.llm_provider = provider
        
        if provider == "anthropic":
            self.current_client = self.claude_client
        elif provider == "openai":
            self.current_client = self.openai_client
        elif provider == "gemini":
            self.current_client = self.gemini_client
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}. Use 'anthropic', 'openai', or 'gemini'.")

    async def connect_to_server(self, server_script_path: str) -> bool:
        """
        Connect to the MCP server and share the connection with all clients.
        This ensures all clients use the same MCP session.
        """
        try:
            # Use the Gemini client to establish the MCP connection since it has the most complete implementation
            connected = await self.gemini_client.connect_to_server(server_script_path)
            if not connected:
                return False
            
            # Share the MCP session with all clients
            self.session = self.gemini_client.session
            self.openai_client.session = self.session
            self.claude_client.session = self.session
            
            # Share the exit_stack for cleanup
            self.exit_stack = self.gemini_client.exit_stack
            self.openai_client.exit_stack = self.exit_stack
            self.claude_client.exit_stack = self.exit_stack
            
            # Set up tools for OpenAI and Claude clients using the shared session
            if self.session:
                response = await self.session.list_tools()
                tools = response.tools
                
                # Set up OpenAI client tools
                self.openai_client.available_tools = [{
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                } for tool in tools]
                
                # Set up Claude client tools  
                self.claude_client.available_tools = [{
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                } for tool in tools]
            
            return True
            
        except Exception as e:
            print(f"Error connecting to server: {e}")
            return False

    async def process_query(self, query: str) -> dict:
        """
        Process a query using the currently selected LLM provider.
        Returns a dictionary with response, tool_executions, and status.
        """
        if not self.current_client:
            return {
                "response": "No client selected. Please set a model first.",
                "tool_executions": [],
                "status": "error"
            }
        
        if not self.session:
            return {
                "response": "Not connected to MCP server. Please connect first.",
                "tool_executions": [],
                "status": "error"
            }
        
        return await self.current_client.process_query(query)

    def clear_conversation_history(self):
        """Clear conversation history for the current client"""
        if self.current_client:
            self.current_client.clear_conversation_history()

    def set_model(self, provider: Literal["anthropic", "openai", "gemini"]):
        """Switch to a different LLM provider"""
        self._switch_client(provider)
        return f"Switched to {provider} model"

    def get_current_model(self) -> str:
        """Get the currently active model"""
        return self.llm_provider

    async def cleanup(self):
        """Clean up resources"""
        if self.gemini_client:
            await self.gemini_client.cleanup()

    async def chat_loop(self):
        """Run an interactive chat session with model switching capability"""
        print("\n🚀 Multi-LLM MCP Client Started!")
        print(f"📱 Current model: {self.llm_provider}")
        print("\n💡 Try queries like:")
        print("  - 'Show me fastest laps from Monaco 2024'")
        print("  - 'Weather conditions at Silverstone 2024 race'")
        print("  - 'Tyre strategies for Spanish Grand Prix 2024'")
        print("\n🔧 Special commands:")
        print("  - 'clear' to reset conversation history")
        print("  - 'model openai' to switch to OpenAI")
        print("  - 'model claude' to switch to Claude")
        print("  - 'model gemini' to switch to Gemini")
        print("  - 'quit' to exit")

        while True:
            query = input(f"\n[{self.llm_provider}] Query: ").strip()
            
            if query.lower() == 'quit':
                break
            elif query.lower() == 'clear':
                self.clear_conversation_history()
                continue
            elif query.lower().startswith('model '):
                model_name = query.lower().split('model ')[1].strip()
                if model_name in ['openai', 'claude', 'anthropic', 'gemini']:
                    if model_name == 'claude':
                        model_name = 'anthropic'  # Map claude to anthropic
                    try:
                        result = self.set_model(model_name)
                        print(f"✅ {result}")
                    except ValueError as e:
                        print(f"❌ {e}")
                else:
                    print("❌ Invalid model. Use: openai, claude, or gemini")
                continue

            # Process the user's query and display the response
            result = await self.process_query(query)
            print("\n" + result["response"])
            
            # Show tool executions if any
            if result.get("tool_executions"):
                print(f"\n🔧 Executed {len(result['tool_executions'])} tools")

async def main():
    """Main function to start the MCP client with model selection"""
    import sys
    if len(sys.argv) < 2:
        print("Usage: python main_client.py <path_to_server_script>")
        sys.exit(1)

    client = MainClient()
    try:
        # Connect to the MCP server and start the chat loop
        connected = await client.connect_to_server(sys.argv[1])
        if not connected:
            print("Failed to connect to MCP server")
            return
        await client.chat_loop()
    finally:
        # Ensure resources are cleaned up
        await client.cleanup()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())


