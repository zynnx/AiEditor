from pathlib import Path

APP_NAME = "Motorcycle AI Editor"

WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800

PROJECT_ROOT = Path(__file__).parent

OUTPUT_FOLDER = PROJECT_ROOT / "output"

VIDEO_FOLDER = PROJECT_ROOT / "videos"

THUMBNAIL_SIZE = (500, 300)

OLLAMA_MODEL = "qwen2.5vl:7b"