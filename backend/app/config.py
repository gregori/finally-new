import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

OPENCODE_API_KEY = os.getenv("OPENCODE_API_KEY", "")
if not OPENCODE_API_KEY:
    msg = "OPENCODE_API_KEY is required but not set. See .env.example."
    raise RuntimeError(msg)

MASSIVE_API_KEY = os.getenv("MASSIVE_API_KEY", "")
LLM_MOCK = os.getenv("LLM_MOCK", "false").lower() == "true"
DATABASE_URL = os.getenv("DATABASE_URL", "/app/db/finally.db")
STATIC_DIR = os.getenv("STATIC_DIR", "/app/static")
