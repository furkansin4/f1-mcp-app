import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "mcp-client"))

from api import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
