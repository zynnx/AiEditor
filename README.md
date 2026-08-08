# 🏍️ Motorcycle AI Editor

Desktop application that automatically creates motorcycle ride highlights using local AI (Ollama vision model).

Analyze your moto rides, detect scenic curves, action moments, and exports polished highlight videos — all offline.

## Requirements

- **Python 3.10+**
- **[Ollama](https://ollama.ai)** running locally with a vision model loaded (e.g. qwen2.5-vl, llava, akllava)
- **[FFmpeg](https://ffmpeg.org/download.html)** installed and available on your system PATH

### Recommended Ollama Model

The default model is **qwen2.5-vl** (configured in config.py). Pull it with:

`ash
ollama pull qwen2.5-vl
`

Other vision-compatible models work too: llava, akllava, moondream, etc.

## Installation

1. **Clone the repository:**
   `ash
   git clone https://github.com/yourusername/AiEditor.git
   cd AiEditor
   `

2. **Create a virtual environment:**
   `ash
   python -m venv .venv
   .venv\\Scripts\\activate    # Windows
   source .venv/bin/activate   # macOS / Linux
   `

3. **Install dependencies:**
   `ash
   pip install -r requirements.txt
   `

## Running the App

`ash
python app.py
`

Make sure Ollama is running before launching (ollama serve or check it's in your system tray).

## How It Works

1. **Open a video** → selects a moto ride MP4 from disk
2. **Extract frames** → FFmpeg extracts 1 frame/second
3. **Detect scenes** → consecutive frames grouped by visual similarity (MAD threshold)
4. **AI analysis** → Ollama vision model scores each scene for beauty, action, curves, etc.
5. **Build timeline** → scored events form an editable highlight timeline
6. **Filter / Edit** → natural-language prompts filter the timeline (\"only curves\", \"3-minute highlight\")
7. **Export** → FFmpeg concatenates selected segments into a final highlight video

## Project Structure

`
AiEditor/
├── app.py                  # Entry point
├── config.py               # Configuration constants
├── requirements.txt        # Python dependencies
├── controllers/
│   └── main_controller.py  # Orchestrates the full pipeline
├── core/
│   ├── ffmpeg.py           # FFmpeg/FFprobe interface
│   └── ollama_client.py    # Ollama HTTP client
├── models/
│   ├── event.py            # EventType, RoadQualityScores, TimelineEvent, TelemetryData
│   ├── scene.py            # Scene model
│   ├── timeline.py         # Timeline (collection of events)
│   ├── video_info.py       # Video metadata
│   └── analysis.py         # AnalysisResult, FrameAnalysis
├── services/
│   ├── ai_service.py       # Vision AI analysis via Ollama
│   ├── scene_detector.py   # Groups frames into scenes (MAD comparison)
│   ├── prompt_service.py   # Natural-language → timeline filtering
│   ├── timeline_service.py # AnalysisResult → Timeline conversion
│   └── ...                 # Video, Frame, Export, Cache, Thumbnail services
└── ui/
    └── windows/
        └── main_window.py  # Main application window
`

## Pipeline Architecture

`
Video → Metadata → Frames → Scenes → AI Analysis → Timeline → Prompt Filter → Export
`

Key design principle: **AI analysis runs ONCE per video.** Filtering and prompting reuse cached results.

## Dependencies

| Package | Purpose |
|---------|---------|
| PySide6 | Qt6 GUI framework |
| opencv-python | Scene detection (frame comparison) |
| numpy | Numerical operations for image diffing |
| ollama | Ollama Python client library |
| requests | HTTP client for Ollama API |
| httpx | Async HTTP (Ollama transport) |
| ffmpeg-python | FFmpeg subprocess wrapper |

## License

MIT