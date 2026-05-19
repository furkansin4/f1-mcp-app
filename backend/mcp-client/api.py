from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from datetime import datetime
from main_client import MainClient
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import uvicorn
import os
import json


load_dotenv()

def create_db_connection():
    """Create SQLAlchemy engine for PostgreSQL connection"""
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD', '')
    host = os.getenv('DB_HOST')
    port = os.getenv('DB_PORT', '5432')
    database = os.getenv('DB_NAME')

    connection_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    return create_engine(
        connection_string,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


def truncate_tool_response(tool_response_data, max_length=250):
    """Truncate tool response to max_length characters"""
    tool_response_str = json.dumps(tool_response_data)
    if len(tool_response_str) <= max_length:
        return tool_response_data
    
    truncated_str = tool_response_str[:max_length-3] + "..."
    return truncated_str


class Settings(BaseSettings):
    server_script_path: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "mcp-server", "f1_mcp.py"
    )

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = MainClient()
    try:
        connected = await client.connect_to_server(settings.server_script_path)
        if not connected:
            raise HTTPException(
                status_code=500, detail="Failed to connect to MCP server"
            )
        app.state.client = client
        yield
    except Exception as e:
        print(f"Error during lifespan: {e}")
        # Clean up the client if it was created
        if hasattr(app.state, 'client'):
            await app.state.client.cleanup()
        raise HTTPException(status_code=500, detail=f"Error during startup: {str(e)}") from e
    finally:
        # shutdown
        if hasattr(app.state, 'client'):
            await app.state.client.cleanup()


app = FastAPI(title="MCP Client API", lifespan=lifespan)


_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    query: str
    conversation_id: Optional[int] = None


class ChatResponse(BaseModel):
    response: str
    timestamp: datetime
    conversation_id: int
    status: str = "success"
    tools: Optional[list] = []


class ModelRequest(BaseModel):
    model: str


class UpdateTitleRequest(BaseModel):
    title: str


class Conversation(BaseModel):
    id: int
    title: str
    created_at: datetime

class Message(BaseModel):
    id: int
    conversation_id: int
    message: str
    role: str
    created_at: datetime




@app.get("/")
async def root():
    return {"status": "F1 API is running"}


@app.post("/chat")
async def process_query(request: ChatRequest):
    """Process a query and return the response"""
    db = create_db_connection()
    
    try:
        with db.connect() as conn:
            if request.conversation_id is not None and request.conversation_id > 0:
                # Use existing conversation
                conversation_id = request.conversation_id

                result = conn.execute(text("SELECT id FROM conversations WHERE id = :id"), {"id": conversation_id})
                if not result.fetchone():
                    raise HTTPException(status_code=404, detail="Conversation not found")
            else:

                app.state.client.clear_conversation_history()
                result = conn.execute(text("INSERT INTO conversations (title, created_at) VALUES (:title, :created_at) RETURNING id"), {
                    "title": request.query[:50] + "..." if len(request.query) > 50 else request.query,
                    "created_at": datetime.now()
                })
                conversation_id = result.fetchone()[0]
                conn.commit()

            # Insert user message
            conn.execute(text("INSERT INTO messages (message, role, conversation_id, created_at) VALUES (:message, :role, :conversation_id, :created_at)"), {
                "message": request.query,
                "role": "user",
                "conversation_id": conversation_id,
                "created_at": datetime.now()
            })
            conn.commit()

            # Get assistant response
            
            response_data = await app.state.client.process_query(request.query)
            response_text = response_data.get("response", "")
            tools = response_data.get("tool_executions", [])
            
            # Store tool executions
            for tool in tools:

                tool_response = []
                if isinstance(tool["result"], list):
                    for item in tool["result"]:
                        if hasattr(item, "text"):
                            tool_response.append({"text": item.text})
                        else:
                            tool_response.append(item)
                else:
                    tool_response = tool["result"]

                truncated_response = truncate_tool_response(tool_response, max_length=250)


                conn.execute(text("""
                    INSERT INTO tool_executions (conversation_id, tool_name, tool_request, tool_response, created_at)
                    VALUES (:conversation_id, :tool_name, :tool_request, :tool_response, :created_at)
                """), {
                    "conversation_id": conversation_id,
                    "tool_name": tool["tool_name"],
                    "tool_request": json.dumps(tool["tool_args"]),
                    "tool_response": json.dumps(truncated_response),
                    "created_at": datetime.now()
                })
            conn.commit()
            
            # Insert assistant message
            conn.execute(text("INSERT INTO messages (message, role, conversation_id, created_at) VALUES (:message, :role, :conversation_id, :created_at)"), {
                "message": response_text,
                "role": "assistant",
                "conversation_id": conversation_id,
                "created_at": datetime.now()
            })
            conn.commit()

            return ChatResponse(
                response=response_text, 
                conversation_id=conversation_id,
                timestamp=datetime.now(),
                tools=tools
            )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post("/model")
async def set_model(request: ModelRequest):
    """Set the model for the client"""
    try:
        # Map model names to provider names
        model_mapping = {
            "openai": "openai",
            "claude": "anthropic", 
            "anthropic": "anthropic",
            "gemini": "gemini"
        }
        
        provider = model_mapping.get(request.model.lower())
        if not provider:
            raise HTTPException(status_code=400, detail=f"Unsupported model: {request.model}. Use 'openai', 'claude', or 'gemini'.")
        
        result = app.state.client.set_model(provider)
        return {"status": "success", "message": result, "current_model": provider}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/model")
async def get_current_model():
    """Get the currently active model"""
    try:
        current_model = app.state.client.get_current_model()
        return {"current_model": current_model, "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/recents")
async def get_recents():
    """Get recent chat history"""
    try:
        db = create_db_connection()
        with db.connect() as conn:
            result = conn.execute(text("SELECT id, title, created_at FROM conversations ORDER BY created_at DESC"))
            conversations = result.fetchall()
            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "created_at": row[2]
                }
                for row in conversations
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/conversation/{conversation_id}")
async def get_conversation(conversation_id: int):
    """Get a conversation by id"""
    try:
        db = create_db_connection()
        with db.connect() as conn:
            result = conn.execute(text("SELECT id, title, created_at FROM conversations WHERE id = :conversation_id"), {"conversation_id": conversation_id})
            conversation = result.fetchone()
            if conversation:
                return {
                    "id": conversation[0],
                    "title": conversation[1],
                    "created_at": conversation[2]
                }
            else:
                raise HTTPException(status_code=404, detail="Conversation not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.put("/conversation/{conversation_id}")
async def update_conversation_title(conversation_id: int, request: UpdateTitleRequest):
    """Update the title of a conversation"""
    try:
        db = create_db_connection()
        with db.connect() as conn:
            # Verify the conversation exists
            result = conn.execute(text("SELECT id FROM conversations WHERE id = :conversation_id"), {"conversation_id": conversation_id})
            if not result.fetchone():
                raise HTTPException(status_code=404, detail="Conversation not found")
            
            conn.execute(text("UPDATE conversations SET title = :title WHERE id = :conversation_id"), {
                "title": request.title,
                "conversation_id": conversation_id
            })
            conn.commit()
            
            return {"status": "Conversation title updated successfully", "title": request.title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/conversation/{conversation_id}")
async def delete_conversation(conversation_id: int):
    """Delete a conversation by id"""
    try:
        db = create_db_connection()
        with db.connect() as conn:
            result = conn.execute(text("SELECT id FROM conversations WHERE id = :conversation_id"), {"conversation_id": conversation_id})
            if not result.fetchone():
                raise HTTPException(status_code=404, detail="Conversation not found")
            
            conn.execute(text("DELETE FROM tool_executions WHERE conversation_id = :conversation_id"), {"conversation_id": conversation_id})
            
            conn.execute(text("DELETE FROM messages WHERE conversation_id = :conversation_id"), {"conversation_id": conversation_id})
            
            conn.execute(text("DELETE FROM conversations WHERE id = :conversation_id"), {"conversation_id": conversation_id})
            
            conn.commit()
            return {"status": "Conversation deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    



@app.get("/conversation/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: int):
    """Get all messages for a conversation"""
    try:
        db = create_db_connection()
        with db.connect() as conn:
            result = conn.execute(text("""
                SELECT id, conversation_id, message, role, created_at FROM messages WHERE conversation_id = :conversation_id
                ORDER BY created_at ASC
            """), {"conversation_id": conversation_id})
            messages = result.fetchall()
            return [
                {
                    "id": row[0],
                    "conversation_id": row[1],
                    "message": row[2],
                    "role": row[3],
                    "created_at": row[4]
                }
                for row in messages
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tools")
async def get_tools():
    """Get the list of available tools"""
    try:
        tools_response = await app.state.client.session.list_tools()
        tools = tools_response.tools
        tools_list = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": dict(tool.inputSchema) if tool.inputSchema else {},
            }
            for tool in tools
        ]
        
        return {
            "tools": tools_list,
            "count": len(tools_list)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/conversation/{conversation_id}/tools")
async def get_conversation_tools(conversation_id: int):
    """Get all tool executions for a conversation"""
    try:
        db = create_db_connection()
        with db.connect() as conn:
            result = conn.execute(text("""
                SELECT id, conversation_id, tool_name, tool_request, tool_response, created_at 
                FROM tool_executions 
                WHERE conversation_id = :conversation_id
                ORDER BY created_at ASC
            """), {"conversation_id": conversation_id})
            tools = result.fetchall()
            return [
                {
                    "id": row[0],
                    "conversation_id": row[1],
                    "tool_name": row[2],
                    "tool_request": row[3],
                    "tool_response": row[4],
                    "created_at": row[5]
                }
                for row in tools
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)




