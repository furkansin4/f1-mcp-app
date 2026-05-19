# Formula 1 Model Context Protocol

## What's the project?

This is my Formula 1 MCP Platform application that MSc Project. It lets you ask questions about F1 data and get answers from AI models like OpenAI, Claude, and Gemini. The cool part is that the AI can actually look up real F1 data from a database to answer your questions and with MCP tool calling works properly.

## How it works?

The app has two main parts:
- **Frontend**: A React website where you can chat with the AI
- **Backend**: A Python server that handles the AI and database stuff

The backend uses MCP (Model Context Protocol) which basically lets the AI use tools to look up F1 data from a PostgreSQL database.

## What can you ask?

You can ask questions like:
- "Who won the Monaco Grand Prix in 2023?"
- "What were Hamilton's lap times in the last race?"
- "Show me the fastest laps from Silverstone 2025"
- "HAM and VER telemetry data in 2021 Abu Dhabi final lap"

## Tech Stack

**Frontend:**
- React with TypeScript
- Vite for development
- Tailwind CSS for styling
- React Router for navigation

**Backend:**
- Python with FastAPI
- PostgreSQL database
- Multiple AI providers (OpenAI, Claude, Gemini)
- MCP for tool calling
- FastF1 library for F1 data

## Setup Instructions

### Prerequisites
- Node.js and npm
- Python 3.11+
- PostgreSQL database or Amazon RDS host
- API keys for OpenAI, Claude, and/or Gemini

### Backend Setup

1. Go to the backend folder:
```bash
cd backend
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```
(or if you have uv: `uv install`)

3. Create a `.env` file with your database and API credentials:
```
DB_HOST=your_db_host
DB_PORT=5432
DB_NAME=your_db_name 
DB_USER=your_username
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_claude_key
GOOGLE_API_KEY=your_gemini_key
```

4. Make sure your PostgreSQL database has F1 data (you might need to run the data fetching script)
5. If you want to use Amazon RDS don't forget to clone data and paste your host link.

6. Start the backend server:
```bash
uvicorn main:app --reload
```

### Frontend Setup

1. Go to the frontend folder:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

4. Open your browser to `http://localhost:5173`

## Project Structure

```
f1-mcp-app/
├── backend/                 # Python backend
│   ├── mcp-server/         # MCP server with F1 tools
│   ├── mcp-client/         # AI clients (OpenAI, Claude, Gemini)
│   ├── fetch-data/         # Scripts to fetch F1 data
│   └── main.py             # FastAPI main server
├── frontend/               # React frontend
│   └── src/
│       ├── components/     # React components
│       ├── routes/         # Page components
│       └── services/       # API calls
└── db.sql                  # Database schema
```

## Features

- **Multi-AI Support**: Switch between OpenAI, Claude, and Gemini
- **Real F1 Data**: AI can query actual F1 database for accurate info
- **Chat Interface**: Clean chat UI
- **Tool Execution**: See what database queries the AI runs
- **Conversation History**: Save and load previous chats

## Must Known

- Sometimes the AI might stuck API rate limitations, make sure do not overload too many queries in one question.
- In 2025 data, make sure to use latest models by provider. 
- API keys are required for the AI models

## Future Ideas

- Add different F1 data sources
- Better visualization of race data
- Add more comphrensive tools

## Notes

This was built as a MSc project to understand how AI can interact with external data sources and provide real-time information. The MCP protocol is pretty cool - it lets the AI use tools just like a human would!

Feel free to ask me questions if you want to know more about how any part works.

contact: f.s.sahaplioglu@se24.qmul.ac.uk
