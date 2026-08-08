# Architecture Gap Analysis — AiEditor

Last verified: 2026-08-08
Repository: zynnx/AiEditor
Branch: main

## Purpose

This file describes the ACTUAL current codebase versus the target architecture.
It must not describe old implementation states as current gaps.

## Current pipeline

```text
Video
  -> Metadata
  -> Frame Extraction
  -> Scene Detection
  -> Vision AI
  -> AnalysisResult
  -> Timeline
  -> Prompt Filter
  -> Export
```

## Already implemented

### Models

| Component | Status |
|---|---|
| VideoInfo | IMPLEMENTED |
| FrameAnalysis | IMPLEMENTED |
| AnalysisResult | IMPLEMENTED |
| Scene | IMPLEMENTED |
| EventType | IMPLEMENTED |
| RoadQualityScores | IMPLEMENTED |
| TelemetryData | MODEL ONLY / NO IMPORTER |
| TimelineEvent | IMPLEMENTED |
| Timeline | IMPLEMENTED |

`TimelineEvent` already contains event_id, importance, tags, thumbnail, scene_id,
quality_scores, telemetry and event_type.

Do NOT recreate these models.

### Services

| Service | Status |
|---|---|
| VideoService | IMPLEMENTED |
| FrameExtractor | IMPLEMENTED |
| SceneDetector | IMPLEMENTED |
| AIService | IMPLEMENTED |
| CacheService | IMPLEMENTED |
| ThumbnailService | IMPLEMENTED |
| TimelineService | IMPLEMENTED |
| PromptService | IMPLEMENTED |
| ExportService | IMPLEMENTED |

### AI pipeline

`AIService.analyze_scenes()` already sends scene frames to Ollama in batches and
returns structured analysis.

The application already performs:

```text
Frame Extraction
  -> Scene Detection
  -> Scene-based AI Analysis
  -> Timeline
```

Do NOT add another Scene model or SceneDetector.

### Prompt engine

`PromptService` already filters an existing Timeline without calling Vision AI.

Current supported intent includes:

- duration
- top-N
- cinematic/scenic
- action
- event types
- score-based highlights

This is implemented.

The future enhancement is an LLM-based `EditIntent` parser, but that is NOT a
missing PromptService.

### Export

Current export supports:

- H.264
- H.265
- NVIDIA NVENC
- AAC
- timeline segment concatenation

## Real architectural gaps

### 1. Project System — MISSING

The application is still fundamentally video/session oriented.

Target:

```text
Project
├── metadata
├── videos[]
├── telemetry[]
├── analysis
├── timeline
├── settings
└── exports[]
```

Future components:

```text
models/project.py
services/project_service.py
repository/project_repository.py
```

### 2. Repository Layer — MISSING

Target:

```text
repository/
├── project_repository.py
├── analysis_repository.py
└── cache_repository.py
```

Initial persistence may use JSON. It should later be replaceable by SQLite.

### 3. Project-scoped cache — MISSING

Current cache uses global paths:

```text
output/cache
output/frames
output/thumbnails
```

Target:

```text
Project/
├── project.json
├── cache/
├── analysis/
├── thumbnails/
└── exports/
```

### 4. Task/Job System — MISSING

The UI has a worker thread, but not a full job system.

Target:

```text
TaskManager
├── FrameExtractionJob
├── SceneDetectionJob
├── AIAnalysisJob
└── ExportJob
```

Jobs should support progress, status, cancellation and errors.

### 5. Visual Timeline UI — PARTIAL

The Timeline domain model and editing operations exist.

Still missing:

- visual thumbnail timeline
- event browser
- drag/resize
- visual score indicators
- timeline zoom/navigation

### 6. Telemetry ingestion — MISSING

`TelemetryData` exists, but there is no GPX/DJI/GoPro/Garmin importer.

### 7. Plugin architecture — FUTURE

Not implemented. Do not implement until Project and Repository architecture are stable.

## Real technical debt / bugs

### AIService field mismatch

`TimelineEvent` defines:

```python
quality_scores
```

but `AIService.analyze_scenes()` currently passes:

```python
road_quality=...
```

This can cause a runtime TypeError.

The correct field is:

```python
quality_scores=RoadQualityScores(...)
```

### Analysis cache serialization

`MainController` attempts to cache an AnalysisResult using `__dict__`.
The result contains nested dataclasses and Path objects, so a proper serialization
boundary is required.

This should eventually belong to the repository/serialization layer.

### Global cache

CacheService is currently global rather than project-scoped. This is acceptable
for the current MVP but must change when Project is introduced.

### MainController size

MainController coordinates many services and is becoming a God Controller.
Do not rewrite it immediately. ProjectService and TaskManager should gradually
reduce its responsibilities.

### core/ vs services/

There are overlapping/legacy responsibilities in `core/` and `services/`.
Trace imports before deleting anything. Do not create duplicate replacements.

## Recommended order

### Phase 0 — Stabilization

1. Fix AIService `road_quality` -> `quality_scores`.
2. Fix/verify AnalysisResult cache serialization.
3. Add basic tests for models and PromptService.
4. Trace legacy `core/` modules before removing anything.

### Phase 1 — Project

1. Project model
2. ProjectRepository
3. ProjectService
4. project.json persistence
5. project-scoped cache
6. migrate current single-video workflow into a Project

### Phase 2 — Tasks

1. Job abstraction
2. TaskManager
3. progress
4. cancellation
5. UI task/status panel

### Phase 3 — Timeline UI

1. event browser
2. thumbnail timeline
3. selection/removal
4. manual editing

### Phase 4 — Advanced Prompt Engine

1. EditIntent
2. LLM intent parsing
3. deterministic timeline filtering

### Phase 5 — Plugins

Only after the above is stable.

## Rules for AI coding agents

1. Read this file before changing architecture.
2. Inspect the actual repository before assuming something is missing.
3. Never recreate existing Scene, TimelineEvent, EventType, RoadQualityScores,
   SceneDetector, PromptService or TimelineService.
4. Do not rewrite working subsystems unnecessarily.
5. Implement one phase at a time.
6. Do not implement future phases automatically.
7. Keep changes small and testable.
8. Update this file when implementation materially changes.

## Bottom line

The existing AI pipeline is already implemented.

The next major architectural milestone is:

```text
Project
  -> ProjectRepository
  -> ProjectService
  -> Project-scoped persistence/cache
```

Do not rebuild the existing AI pipeline.
