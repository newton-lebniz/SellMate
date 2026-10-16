"""Settings, read from environment variables with sensible local defaults."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

DATA_DIR = Path(os.getenv("SELLMATE_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
CATALOG_FILE = DATA_DIR / "catalog.json"
FRONTEND_DIR = BASE_DIR / "frontend"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300"))

# Smaller images = much faster CPU inference. 640px is plenty for product photos.
MAX_IMAGE_SIDE = 640
MAX_PHOTOS = 3
MAX_UPLOAD_MB = 8
MAX_KEYWORDS_CHARS = 300
