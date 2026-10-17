"""Settings, read from environment variables with sensible local defaults."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

DATA_DIR = Path(os.getenv("SELLMATE_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
CATALOG_FILE = DATA_DIR / "catalog.json"
QUESTIONS_FILE = DATA_DIR / "questions.json"
FRONTEND_DIR = BASE_DIR / "frontend"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
# Text model: writes listings and answers buyer questions. 1B runs fine on a CPU laptop.
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b")
# Vision model: looks at the photos. Set to an empty string (or to the same value as
# OLLAMA_MODEL) to send photos straight to the text model, which needs a vision-capable
# model such as gemma3:4b.
VISION_MODEL = os.getenv("VISION_MODEL", "moondream").strip()
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300"))

# Smaller images = much faster CPU inference. 640px is plenty for product photos.
MAX_IMAGE_SIDE = 640
MAX_PHOTOS = 3
MAX_UPLOAD_MB = 8
MAX_KEYWORDS_CHARS = 300

# Buyer chat limits
MAX_QUESTION_CHARS = 500
MAX_HISTORY_TURNS = 6
MAX_SELLER_NOTES_CHARS = 800
MAX_CONTEXT_PRODUCTS = 3
MAX_LOGGED_QUESTIONS = 100

# SELLMATE_DEBUG=1 prints each raw chat reply to the server console.
DEBUG = os.getenv("SELLMATE_DEBUG", "") not in ("", "0", "false")
