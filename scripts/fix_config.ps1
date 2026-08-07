$content = @'
from pathlib import Path

APP_NAME = "Motorcycle AI Editor"

WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800

PROJECT_ROOT = Path(__file__).parent

OUTPUT_FOLDER = PROJECT_ROOT / "output"
CACHE_FOLDER = OUTPUT_FOLDER / "cache"
THUMBNAILS_FOLDER = OUTPUT_FOLDER / "thumbnails"
FRAMES_FOLDER = OUTPUT_FOLDER / "frames"
ANALYSIS_FOLDER = OUTPUT_FOLDER / "analysis"
EXPORTS_FOLDER = OUTPUT_FOLDER / "exports"

VIDEO_FOLDER = PROJECT_ROOT / "videos"

THUMBNAIL_SIZE = (500, 300)

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5-vl"
VISION_BATCH_SIZE = 8

FRAME_EXTRACTION_RATE = 1

SCENE_CHANGE_THRESHOLD = 30.0
SCENE_MIN_FRAMES = 15

EXPORT_FORMAT = "mp4"
NVENC_ENABLED = True
EXPORT_RESOLUTION = "1920x1080"
EXPORT_HDR_SUPPORTED = False
CACHE_TTL_HOURS = 168
MAX_AI_RETRIES = 3
@'

$OutFile = "config.py"
$content | Out-File -FilePath $OutFile -Encoding UTF8 -NoNewline
Write-Host "Generated $OutFile with $($content.Split("`n").Count) lines"