import asyncio
from typing import Optional
from contextlib import AsyncExitStack
import logging

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()
        self.conversation_history = []
        self.available_tools = []

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        self.available_tools = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in tools]

        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> dict:
        """Process a query using Claude and available tools - returns detailed results"""
        
        # Store tool execution history for user display
        tool_executions = []

        try:
            # Add user message to conversation history
            user_message = {"role": "user", "content": query}
            self.conversation_history.append(user_message)

            # Prepare messages for API call (include full conversation history)
            messages = self.conversation_history.copy()

            while True:
                response = self.anthropic.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1000,
                    messages=messages,
                    tools=self.available_tools
                )

                # Check if Claude wants to use tools
                tool_calls = [content for content in response.content if content.type == 'tool_use']
                text_content = [content for content in response.content if content.type == 'text']

                # Add Claude's response to conversation history
                assistant_message = {
                    "role": "assistant", 
                    "content": response.content
                }
                self.conversation_history.append(assistant_message)
                messages.append(assistant_message)

                # If no tool calls, we're done
                if not tool_calls:
                    # Return the text content
                    if text_content:
                        response_text = text_content[0].text
                    else:
                        response_text = "No response generated."
                    
                    return {
                        "response": response_text,
                        "tool_executions": tool_executions,
                        "status": "success"
                    }

                # Process tool calls
                tool_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call.name
                    tool_args = tool_call.input
                    tool_id = tool_call.id

                    try:
                        # Execute tool call
                        result = await self.session.call_tool(tool_name, tool_args)
                        
                        # Store tool execution for user display
                        tool_executions.append({
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "result": result.content,
                            "status": "success"
                        })
                        
                        tool_result = {
                            "type": "tool_result",
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "tool_use_id": tool_id,
                            "content": result.content
                        }
                        tool_results.append(tool_result)

                        print(f"Tool {tool_name} executed successfully")

                    except Exception as e:
                        logging.error(f"Error calling tool {tool_name}: {str(e)}")
                        
                        # Store tool execution error for user display
                        tool_executions.append({
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "error": str(e),
                            "status": "error"
                        })
                        
                        tool_result = {
                            "type": "tool_result", 
                            "tool_use_id": tool_id,
                            "content": f"Error: {str(e)}",
                            "is_error": True
                        }
                        tool_results.append(tool_result)

                # Add tool results to conversation
                if tool_results:
                    tool_message = {
                        "role": "user",
                        "content": tool_results
                    }
                    self.conversation_history.append(tool_message)
                    messages.append(tool_message)

        except Exception as e:
            logging.error(f"Error processing query: {str(e)}")
            error_response = "An error occurred while processing your request. Please try again."
            return {
                "response": error_response,
                "tool_executions": tool_executions,
                "status": "error"
            }

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == 'quit':
                    break

                elif query.lower() == 'clear':
                    self.clear_conversation_history()
                    continue

                result = await self.process_query(query)
                print("\n" + result["response"])

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

    def clear_conversation_history(self):
        """Clear the conversation history to start fresh."""
        self.conversation_history = []
        print("🧹 Conversation history cleared!")

async def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())