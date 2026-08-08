# AiEditor Architecture

## Vision

Motorcycle AI Editor is a local-first desktop AI video editor specialized for
motorcycle/action-camera footage.

The AI understands the source video and creates an editable timeline.
The AI does not directly edit the video.

```text
Video
  -> Analysis
  -> Timeline
  -> User Intent
  -> Edited Timeline
  -> Export
```

Analysis should happen once. Editing should be repeatable without rerunning
Vision AI.

## Target pipeline

```text
Project
  -> Media Library
  -> Metadata
  -> Frame Extraction
  -> Scene Detection
  -> Vision AI
  -> AnalysisResult
  -> Timeline
  -> EditIntent
  -> Edited Timeline
  -> Export
```

## Project

Project is the long-term root domain object.

A project may contain:

- multiple videos
- telemetry
- analysis
- timeline
- settings
- exports
- cache

Target layout:

```text
Project/
├── project.json
├── media/
├── cache/
├── analysis/
├── thumbnails/
└── exports/
```

## Domain models

Target models:

```text
Project
VideoInfo
Scene
AnalysisResult
TimelineEvent
Timeline
TelemetryData
EditIntent
ExportJob
```

## Services

Target services:

```text
ProjectService
VideoService
MetadataService
FrameExtractor
SceneDetector
AIService
TimelineService
PromptService
CacheService
TelemetryService
ExportService
TaskManager
```

Each service should have a single responsibility.

## Repository layer

Persistence is isolated from business logic.

```text
repository/
├── project_repository.py
├── analysis_repository.py
└── cache_repository.py
```

JSON is acceptable initially. The architecture should allow a future SQLite
implementation without changing domain logic.

## AI

Current provider: Ollama.

Future providers may include LM Studio and cloud/local alternatives.

Vision AI receives frames grouped into scenes and returns structured JSON.

## Prompt architecture

Long-term design:

```text
User Prompt
  -> Intent Parser
  -> EditIntent
  -> PromptService
  -> Timeline filtering/ranking
  -> Edited Timeline
```

The actual timeline selection remains deterministic.

## Export

```text
Edited Timeline
  -> ExportJob
  -> Exporter
  -> FFmpeg
```

Future exporters may include DaVinci Resolve XML, Premiere XML and EDL.

## Task system

Long-running operations must not block the UI.

```text
TaskManager
├── FrameExtractionJob
├── SceneDetectionJob
├── AIAnalysisJob
└── ExportJob
```

Jobs should support status, progress, cancellation, errors and results.

## Plugin architecture

Future plugin categories:

```text
AI
├── Ollama
├── LM Studio
└── other providers

Telemetry
├── GPX
├── DJI
├── GoPro
└── Garmin

Export
├── FFmpeg
├── Resolve XML
├── Premiere XML
└── EDL
```

Do not implement plugins before Project and Repository architecture is stable.

## UI

The UI must not contain business logic.

```text
MainWindow
  -> MainController
  -> Services
```

The UI must never directly call Ollama, FFmpeg, scene detection or cache logic.

Future UI:

```text
MainWindow
├── ProjectPanel
├── MediaLibrary
├── PreviewPanel
├── AnalysisPanel
├── PromptPanel
├── TimelinePanel
├── TaskPanel
└── ExportPanel
```

## Development rules

1. Prefer incremental changes.
2. Search for existing functionality before creating new code.
3. Keep domain models independent from Qt.
4. Keep services independent from the UI.
5. Keep external integrations behind clear boundaries.
6. Use type hints.
7. Add tests for business logic.
8. Do not implement future roadmap items during unrelated tasks.
9. Keep ARCHITECTURE.md as the target architecture.
10. Keep ARCHITECTURE_GAP_ANALYSIS.md synchronized with the real codebase.

## Development priority

```text
Stabilize existing pipeline
  -> Project System
  -> Repository Layer
  -> Task/Job System
  -> Timeline UI
  -> Advanced Prompt Intent
  -> Plugin Architecture
  -> Telemetry integrations
```
