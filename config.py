import os
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

LLM_API_KEY = os.getenv("LLM_API_KEY", "mock")
ASTRO_API_KEY = os.getenv("ASTRO_API_KEY", "mock")

# Prokerala daily horoscope (optional)
PROKERALA_CLIENT_ID = os.getenv("PROKERALA_CLIENT_ID", "4c93b113-82ce-4f1a-9c20-548e043ca38d")
PROKERALA_CLIENT_SECRET = os.getenv("PROKERALA_CLIENT_SECRET", "i6dEokjLj8iFR78at7N6ZU1Mxn1qw2YSacxlXIUY")

# MCP server URL for orchestrator (SSE endpoint, e.g. http://localhost:8001/sse)
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001/sse")
