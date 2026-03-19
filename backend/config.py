import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Fal AI
FAL_KEY = os.getenv("FAL_KEY")
FAL_MODEL_POINT = "fal-ai/moondream3-preview/point"
FAL_MODEL_DETECT = "fal-ai/moondream3-preview/detect"

# Agent (OpenRouter - API compatível com OpenAI)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# Modelo com suporte a visão (imagem)
AGENT_MODEL = os.getenv("AGENT_MODEL", "google/gemini-2.0-flash")

# Queue (Redis/RQ)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Paths (backend/ fica em parent, projeto em parent.parent)
_BACKEND_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BACKEND_DIR.parent
IMAGES_DIR = _PROJECT_ROOT / "images"
FRONTEND_DIR = _PROJECT_ROOT / "frontend"
PROMPTS_DIR = _BACKEND_DIR / "prompts"
UPLOADS_DIR = _BACKEND_DIR / "storage/uploads"
HISTORY_DIR = _BACKEND_DIR / "storage/history"

# Point - desenho dos pontos
POINT_RADIUS = 8
POINT_OUTLINE_WIDTH = 3
POINT_FILL = "red"
POINT_OUTLINE = "white"


def validate_fal_key() -> None:
    """Valida se FAL_KEY está configurada. Levanta ValueError se não."""
    if not FAL_KEY:
        raise ValueError(
            "Defina FAL_KEY no arquivo .env ou export FAL_KEY=..."
        )
    os.environ["FAL_KEY"] = FAL_KEY
