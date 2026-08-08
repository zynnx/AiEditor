# Architecture Gap Analysis: AiEditor

## Date: 2026-08-07

---

## ✅ WHAT EXISTS (Current State)

### Models
| Model | Status | Notes |
|-------|--------|-------|
| `VideoInfo` | ✅ Complete | path, duration, resolution, fps, codec, size |
| `AnalysisResult` | ✅ Complete | timestamp, score, category, reason, details |
| `Timeline` | ✅ Complete | list of Clips, total_duration property |
| `Clip` | ✅ Complete | start_time, end_time, score, category, reason |

### Services
| Service | Status | Notes |
|---------|--------|-------|
| `VideoService` | ✅ Complete | load() returns VideoInfo |
| `FrameExtractor` | ✅ Complete | extract_all_frames(), single_frame() |
| `AIService` | ✅ Complete | analyze_batch(), _analyze_batch(), prompt templates |
| `CacheService` | ✅ Complete | video hashing, frame/analysis cache |
| `ExportService` | ✅ Complete | export() with NVENC support |
| `ThumbnailService` | ✅ Complete | generate_thumbnail(), get_thumbnail() |

### Core
| Component | Status | Notes |
|-----------|--------|-------|
| `ffmpeg.py` | ✅ Complete | probe, extract_frame, concat_segments |
| `ollama_client.py` | ✅ Complete | OllamaVisionClient, batch processing |

### Controller
| Component | Status | Notes |
|-----------|--------|-------|
| `MainController` | ✅ Complete | Orchestrates full pipeline |

### UI
| Component | Status | Notes |
|-----------|--------|-------|
| `MainWindow` | ✅ Basic | Open, Analyze, Export workflow |

---

## ❌ GAPS (Missing vs Specification)

### Phase 1: Missing Models

#### Gap 1.1 - No `Scene` model
**Spec says:** "Frames should first be grouped into scenes. The AI analyzes scenes instead of isolated frames."

**Required fields:**
```python
@dataclass
class Scene:
    scene_id: str
    start_time: float
    end_time: float
    frame_paths: list[Path]
    representative_frame: Path  # best frame for preview
```

#### Gap 1.2 - No `TimelineEvent` model (spec differs from current Clip)
**Spec says:** TimelineEvents have id, importance, description, reason, tags, thumbnail, scene_id

**Current Clip is missing:**
- `id: str` - unique identifier
- `importance: float` - separate from score
- `tags: list[str]` - structured tagging
- `thumbnail: Path | None` - per-event preview
- `scene_id: str` - link to source scene

#### Gap 1.3 - No Event Types enumeration
**Spec lists:** Motorcycle, Curve, Hairpin, Bridge, Tunnel, Forest, Mountain, Sea, Village, City, Highway, Traffic, Overtake, Wheelie, Danger, Interesting road, Scenic road, Sunset, Sunrise, Rain, Night

#### Gap 1.4 - No Road Quality Score model
**Spec requires:** Visual beauty, Road quality, Traffic density, Camera stability, Lighting, Action level

Each category receives a score (0-10).

#### Gap 1.5 - No Telemetry support
**Future requirement:** speed, lean_angle, acceleration, altitude, coordinates

### Phase 2: Missing Services

#### Gap 2.1 - No `SceneDetector` service
**Critical.** Spec says scene detection happens BEFORE AI analysis.

Group frames into scenes using:
- Visual similarity thresholds
- Motion vector analysis
- Or optical flow differences between consecutive frames

#### Gap 2.2 - No `PromptService` / Prompt Engine
**Spec says:** "The AI analysis should be independent from editing."

Required prompts:
- `"Create a 3 minute highlight"` → filter timeline by duration
- `"Create only curves"` → filter by tags
- `"Create cinematic sunset edit"` → filter by tags + score

Current `filter_timeline()` reruns AI analysis. **This violates the spec.**

#### Gap 2.3 - No `TimelineService`
**Spec says:** Timeline generation is its own pipeline phase. Should be a dedicated service, not embedded in MainController.

### Phase 3: Architecture Issues

#### Gap 3.1 - `filter_timeline()` reruns AI analysis
**Current code (line 272):**
```python
def filter_timeline(self, prompt: str, ...) -> Timeline:
    timeline = self.analyze_video(prompt=prompt)  # RERUNS AI!
```

**Spec says:** "Never rerun Vision AI unless the source video changes."

Must be replaced with pure filtering of existing timeline events.

#### Gap 3.2 - Analysis doesn't use scenes
AI receives all frames individually instead of grouped by scene.

#### Gap 3.3 - No repository layer
**Spec requires:** `analysis_repository.py`, `cache_repository.py`

### Phase 4: UI Gaps

#### Gap 4.1 - No visual timeline editor
**Spec says:** "The result is an editable timeline."

Missing:
- Timeline visualization (waveform/thumbnail track)
- Clip selection/removal
- Duration adjustment
- Score/importance indicators

#### Gap 4.2 - No prompt input for re-editing
User cannot write "Create a 3 minute highlight" without triggering re-analysis.

---

## PRIORITY IMPLEMENTATION ORDER

### Priority 1: Foundational (Required for spec compliance)
1. Add `Scene` model
2. Add `SceneDetector` service
3. Update `TimelineEvent`/`Clip` with missing fields
4. Add `EventType` enum
5. Add `RoadQualityScores` dataclass

### Priority 2: Pipeline Correction
6. Fix `filter_timeline()` to NOT rerun AI
7. Create `PromptService` for natural language filtering
8. Create `TimelineService` for timeline generation
9. Update AI prompt to return structured tags and scores

### Priority 3: UI Enhancement
10. Add visual timeline component
11. Add prompt input field for re-editing
12. Add event browser/filter panel 


                ### Priority 4: Future-Proofing
13. Add telemetry fields to models
14. Implement repository layer
15. Add unit test framework