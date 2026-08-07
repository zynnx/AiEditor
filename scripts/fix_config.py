import sys
content = """from pathlib import Path

APP_NAME = "Motorcycle AI Editor"

WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800

PROJECT_ROOT = Path(__file__).parent

OUTPUT_FOLDER = PROJECT_ROOT / "output"

VIDEO_FOLDER = PROJECT_ROOT / "videos"

THUMBNAIL_SIZE = (500, 300)

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5-vl"

FRAME_EXTRACTION_RATE = 1

SCENE_CHANGE_THRESHOLD = 30.0

SCENE_MIN_FRAMES = 15

EXPORT_FORMAT = "mp4"

NVENC_ENABLED = True
"""
with open("config.py", "w") as f:
    f.write(content)
print("config.py restored")