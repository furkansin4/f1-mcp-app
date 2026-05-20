# Import necessary libraries
import asyncio  # For handling asynchronous operations
import os       # For environment variable access
import sys      # For system-specific parameters and functions
import json     # For handling JSON data (used when printing function declarations)

# Import MCP client components
from typing import Optional, Literal  # For type hinting optional values
from contextlib import AsyncExitStack  # For managing multiple async tasks
from mcp import ClientSession, StdioServerParameters  # MCP session management
from mcp.client.stdio import stdio_client  # MCP client for standard I/O communication
import logging

# Import LLM providers
# from anthropic import Anthropic
# from openai import AsyncOpenAI
from google import genai
from google.genai import types
from google.genai.types import Tool, FunctionDeclaration
from google.genai.types import GenerateContentConfig

from dotenv import load_dotenv
from history_utils import build_turns

load_dotenv()



class MCPClient:
    def __init__(self):
        """Initialize the MCP client and configure the Gemini API."""
        self.session: Optional[ClientSession] = None  # MCP session for communication
        self.exit_stack = AsyncExitStack()  # Manages async resource cleanup
        self.conversation_history = []  # Persistent conversation history for Gemini
                
        # Retrieve the Gemini API key from environment variables
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY not found. Please add it to your .env file.")

        # Configure the Gemini AI client
        self.genai_client = genai.Client(api_key=gemini_api_key)

    async def connect_to_server(self, server_script_path: str):
        """Connect to the MCP server and list available tools."""
        try:
            # Determine whether the server script is written in Python or JavaScript
            # This allows us to execute the correct command to start the MCP server
            command = "python" if server_script_path.endswith('.py') else "node"

            # Define the parameters for connecting to the MCP server
            server_params = StdioServerParameters(command=command, args=[server_script_path])

            # Establish communication with the MCP server using standard input/output (stdio)
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))

            # Extract the read/write streams from the transport object
            self.stdio, self.write = stdio_transport

            # Initialize the MCP client session, which allows interaction with the server
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

            # Send an initialization request to the MCP server
            await self.session.initialize()

            # Request the list of available tools from the MCP server
            response = await self.session.list_tools()
            tools = response.tools  # Extract the tool list from the response

            self.function_declarations = convert_mcp_tools_to_gemini(tools)

            return True

        except Exception as e:
            return False



    async def process_query(self, query: str) -> dict:
        """Process a query using Gemini API and available tools - returns detailed results"""
        
        # Store tool execution history for user display
        tool_executions = []
        
        # Create enhanced user prompt that includes system instructions
        enhanced_query = f"""You are an F1 data assistant. Follow these CRITICAL rules for tool execution:

        🔴 MANDATORY WORKFLOW RULES:
        1. For ANY F1-related query mentioning events/races or qualifying/sessions:
        - STEP 1: ALWAYS call get_session_id(event_name, year, session_name?) FIRST
        - STEP 2: Extract the session_id from the result
        - STEP 3: Use that session_id for all subsequent tool calls

        2. NEVER call these tools without first getting session_id:
        - get_fastest_lap_and_sector_comparison
        - get_driver_results
        - get_laps
        - get_weekend_weather
        - get_tyre_strategies
        - get_weather_impact_laps
        - get_telemetry
        - get_session_performance_summary
        - get_race_control_messages
        - get_top_speed_session

        3. Examples of correct workflow:
        ✅ "Fastest laps Monaco 2024" → get_session_id("Monaco", 2024) → get_fastest_lap_and_sector_comparison(session_id=X)
        ✅ "Weather Silverstone 2024" → get_session_id("Silverstone", 2024) → get_weekend_weather(session_id=X)
        ❌ WRONG: get_fastest_lap_and_sector_comparison(session_id=123) without calling get_session_id first

        User's actual question: {query}

        Remember: Always extract session_id from get_session_id results before using other tools!"""
        
        # Format user input with enhanced instructions
        user_prompt_content = types.Content(
            role='user',
            parts=[types.Part.from_text(text=enhanced_query)]
        )

        # Add current user query to persistent conversation history
        self.conversation_history.append(user_prompt_content)

        
        while True:
 
            
            # Send to Gemini with full conversation history
            response = self.genai_client.models.generate_content(
                model='gemini-2.5-pro',
                contents=self.conversation_history,
                config=types.GenerateContentConfig(
                    tools=self.function_declarations, # thinking_config=types.ThinkingConfig(thinking_budget=0) # Disables thinking
                    max_output_tokens=10000,
                ),
            )

            # Process the response received from Gemini
            has_function_call = False
            final_text = []
            
            for candidate in response.candidates:
                if candidate.content.parts:
                    for part in candidate.content.parts:
                        if isinstance(part, types.Part):
                            if part.function_call:
                                has_function_call = True
                                
                                # Extract function call details
                                function_call_part = part
                                tool_name = function_call_part.function_call.name
                                tool_args = function_call_part.function_call.args

                                # Execute the tool using the MCP server
                                try:
                                    result = await self.session.call_tool(tool_name, tool_args)
                                    function_response = {"result": result.content}
                                    
                                    # Store tool execution for user display
                                    tool_executions.append({
                                        "tool_name": tool_name,
                                        "tool_args": tool_args,
                                        "result": result.content,
                                        "status": "success"
                                    })
                                    
                                except Exception as e:
                                    function_response = {"error": str(e)}
                                    
                                    # Store tool execution error for user display
                                    tool_executions.append({
                                        "tool_name": tool_name,
                                        "tool_args": tool_args,
                                        "error": str(e),
                                        "status": "error"
                                    })

                                # Add function call to conversation history
                                self.conversation_history.append(types.Content(
                                    role='model',
                                    parts=[function_call_part]
                                ))

                                # Format the tool response for Gemini
                                function_response_part = types.Part.from_function_response(
                                    name=tool_name,
                                    response=function_response
                                )

                                # Structure the tool response as a Content object
                                function_response_content = types.Content(
                                    role='function',
                                    parts=[function_response_part]
                                )

                                # Add tool response to conversation history
                                self.conversation_history.append(function_response_content)
                                break

                            else:
                                # If no function call was requested, collect the text response
                                if hasattr(part, 'text') and part.text:
                                    final_text.append(part.text)
                    
                    # If we found a function call, break out of the candidate loop
                    if has_function_call:
                        break
            
            # If no function call was made, we have our final response
            if not has_function_call:
                if final_text:
                    response_text = "\n".join(final_text)
                    # Add the assistant's response to conversation history
                    self.conversation_history.append(types.Content(
                        role='model',
                        parts=[types.Part.from_text(text=response_text)]
                    ))
                    
                    # Return comprehensive result
                    return {
                        "response": response_text,
                        "tool_executions": tool_executions,
                        "status": "success"
                    }
                else:
                    error_response = "I apologize, but I couldn't generate a proper response. Please try again."
                    self.conversation_history.append(types.Content(
                        role='model',
                        parts=[types.Part.from_text(text=error_response)]
                    ))
                    
                    return {
                        "response": error_response,
                        "tool_executions": tool_executions,
                        "status": "error"
                    }
        


    def clear_conversation_history(self):
        self.conversation_history = []

    def get_text_history(self) -> list:
        result = []
        for content in self.conversation_history:
            role = content.role
            if role == "model":
                role = "assistant"
            elif role != "user":
                continue
            text_parts = [p.text for p in content.parts if hasattr(p, "text") and p.text]
            if text_parts:
                result.append({"role": role, "content": " ".join(text_parts)})
        return result

    def load_conversation_history(self, messages: list, tool_executions: list = None):
        """Restore conversation history, including tool call/result pairs when available."""
        self.conversation_history = []

        if not tool_executions:
            for m in messages:
                if m.get("role") not in ("user", "assistant"):
                    continue
                gemini_role = "model" if m["role"] == "assistant" else "user"
                self.conversation_history.append(
                    types.Content(role=gemini_role, parts=[types.Part.from_text(text=m["content"])])
                )
            return

        for turn in build_turns(messages, tool_executions):
            self.conversation_history.append(
                types.Content(role="user", parts=[types.Part.from_text(text=turn["user"]["content"])])
            )

            for t in turn["tools"]:
                args = t["tool_request"] if isinstance(t["tool_request"], dict) else json.loads(t["tool_request"])
                self.conversation_history.append(
                    types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name=t["tool_name"], args=args))])
                )
                resp = t["tool_response"]
                if isinstance(resp, str):
                    try:
                        resp = json.loads(resp)
                    except Exception:
                        resp = {"result": resp}
                self.conversation_history.append(
                    types.Content(role="function", parts=[types.Part.from_function_response(name=t["tool_name"], response={"result": resp})])
                )

            if turn["assistant"]:
                self.conversation_history.append(
                    types.Content(role="model", parts=[types.Part.from_text(text=turn["assistant"]["content"])])
                )

    def get_conversation_length(self):
        """Get the number of messages in conversation history."""

        return len(self.conversation_history)

    async def chat_loop(self):
        """Run an interactive chat session with the user."""
        print("\nMCP Client Started! Type 'quit' to exit.")
        print(" Try queries like:")
        print("  - 'Show me fastest laps from Monaco 2024'")
        print("  - 'Weather conditions at Silverstone 2024 race'")
        print("  - 'Tyre strategies for Spanish Grand Prix 2024'")
        print("\n Special commands:")
        print("  - 'clear' to reset conversation history")
        print("  - 'history' to see conversation length")

        while True:
            query = input("\nQuery: ").strip()
            if query.lower() == 'quit':
                break
            elif query.lower() == 'clear':
                self.clear_conversation_history()
                continue
            elif query.lower() == 'history':
                print(f" Conversation has {self.get_conversation_length()} messages")
                continue

            # Process the user's query and display the response
            result = await self.process_query(query)
            print("\n" + result["response"])

    async def cleanup(self):
        """Clean up resources before exiting."""
        await self.exit_stack.aclose()

def clean_schema(schema):
    """
    Recursively removes 'title' fields from the JSON schema.
    """
    if isinstance(schema, dict):
        schema.pop("title", None)

        if "properties" in schema and isinstance(schema["properties"], dict):
            for key in schema["properties"]:
                schema["properties"][key] = clean_schema(schema["properties"][key])

    return schema

def convert_mcp_tools_to_gemini(mcp_tools):
    """
    Converts MCP tool definitions to the correct format for Gemini API function calling.
    """
    gemini_tools = []

    for tool in mcp_tools:
        # Ensure inputSchema is a valid JSON schema and clean it
        parameters = clean_schema(tool.inputSchema.copy() if tool.inputSchema else {})

        # Construct the function declaration
        function_declaration = FunctionDeclaration(
            name=tool.name,
            description=tool.description,
            parameters=parameters
        )

        # Wrap in a Tool object
        gemini_tool = Tool(function_declarations=[function_declaration])
        gemini_tools.append(gemini_tool)

    return gemini_tools

async def main():
    """Main function to start the MCP client."""
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    client = MCPClient()
    try:
        # Connect to the MCP server and start the chat loop
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        # Ensure resources are cleaned up
        await client.cleanup()

if __name__ == "__main__":
    # Run the main function within the asyncio event loop
    asyncio.run(main())