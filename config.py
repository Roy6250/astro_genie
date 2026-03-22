import os
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

LLM_API_KEY = os.getenv("LLM_API_KEY", "mock")
ASTRO_API_KEY = os.getenv("ASTRO_API_KEY", "mock")

# Prokerala daily horoscope (optional)
PROKERALA_CLIENT_ID = os.getenv("PROKERALA_CLIENT_ID", "")
PROKERALA_CLIENT_SECRET = os.getenv("PROKERALA_CLIENT_SECRET", "")

# MCP server URL for orchestrator (SSE endpoint, e.g. http://localhost:8001/sse)
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001/sse")

# Mock/test mode: messages are logged, not sent to any provider
# This allows testing with curl commands only
MOCK_MODE = True
