import os
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

LLM_API_KEY = os.getenv("LLM_API_KEY", "mock")
ASTRO_API_KEY = os.getenv("ASTRO_API_KEY", "mock")
