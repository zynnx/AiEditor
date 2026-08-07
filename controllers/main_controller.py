"""Main Controller – single point of business logic for the UI.

The UI must NEVER call services directly.  Everything flows through
MainController, which coordinates the full pipeline:

    Video → Metadata → Thumbnail → Frames → Scenes → AI Analysis
        → Timeline → Prompt Filter → Export

Key design principle:
    AI analysis happens ONCE per video.
    Filtering/prompting reuses cached results – never reruns AI.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from models.analysis import AnalysisResult, FrameAnalysis, RoadQualityScores
from models.event import TimelineEvent, EventType
from models.scene import Scene
from models.timeline import Timeline
from models.video_info import VideoInfo

from services.ai_service import AIService
from services.cache_service import CacheService
from services.export_service import ExportSettings, ExportService
from services.frame_extractor import FrameExtractor
from services.prompt_service import PromptService
from services.scene_detector import SceneDetector
from services.thumbnail_service import ThumbnailService
from services.timeline_service import TimelineService
from services.video_service import VideoService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class MainController:
    """Orchestrates the entire editing pipeline.

    Public methods are designed to be called directly from the UI.
    No business logic should live outside this class.
    """

    def __init__(self) -> None:
        # -- Infrastructure services (created once) -----------------------
        self._video_service = VideoService()
        self._frame_extractor = FrameExtractor()
        self._scene_detector = SceneDetector()
        self._ai_service = AIService()
        self._timeline_service = TimelineService()
        self._prompt_service = PromptService()
        self._export_service = ExportService()
        self._thumbnail_service = ThumbnailService()
        self._cache_service = CacheService()

        # -- Current session state ----------------------------------------
        self._video_info: VideoInfo | None = None
        self._timeline: Timeline | None = None
        self._analysis_result: AnalysisResult | None = None

    # ------------------------------------------------------------------
    # Read-only properties exposed to the UI
    # ------------------------------------------------------------------

    @property
    def video_info(self) -> VideoInfo | None:
        """Currently loaded video metadata, or ``None``."""
        return self._video_info

    @property
    def timeline(self) -> Timeline | None:
        """Generated timeline, or ``None`` if not yet created."""
        return self._timeline

    @property
    def analysis_result(self) -> AnalysisResult | None:
        """Last AI analysis result, or ``None``."""
        return self._analysis_result

    @property
    def has_video(self) -> bool:
        return self._video_info is not None

    @property
    def has_timeline(self) -> bool:
        return self._timeline is not None and len(self._timeline.events) > 0

    # ------------------------------------------------------------------
    # Video loading
    # ------------------------------------------------------------------

    def open_video(self, path: str | Path) -> VideoInfo:
        """Load a video file and return its metadata.

        Raises:
            FileNotFoundError: if the file does not exist.
        """
        video_info = self._video_service.load(Path(path))
        self._video_info = video_info
        self._timeline = None
        self._analysis_result = None

        # Generate thumbnail at 5 % of duration
        self._thumbnail_service.generate_thumbnail(video_info)

        logger.info("Opened video: %s (%.1fs)", video_info.path.name, video_info.duration)

        return video_info

    def close_video(self) -> None:
        """Reset the controller state (unload current video)."""
        self._video_info = None
        self._timeline = None
        self._analysis_result = None

    # ------------------------------------------------------------------
    # Hash helpers
    # ------------------------------------------------------------------

    def _video_hash(self) -> str:
        """Compute a deterministic hash for the current video.

        The hash is based on file path + file size so that the same
        physical video always produces the same cache key.
        """
        if self._video_info is None:
            raise RuntimeError("No video loaded")
        h = hashlib.sha256()
        h.update(self._video_info.path.as_posix().encode())
        h.update(str(self._video_info.size).encode())
        return h.hexdigest()[:16]

    # ------------------------------------------------------------------
    # Full analysis pipeline
    # ---------------------------------------------------------------------------

    def analyze_video(
        self,
        rate_fps: float = 1.0,
    ) -> Timeline:
        """Run the complete analysis pipeline once.

        Pipeline steps:
            1. Extract frames (cached).
            2. Detect scenes.
            3. Check AI cache – skip if already analyzed.
            4. Send scene frame batches to Ollama vision model.
            5. Build Timeline from structured JSON response.
            6. Cache results.

        This is the ONLY method that calls the vision AI.
        All subsequent filtering uses ``filter_timeline()`` which does
        NOT rerun the AI.

        Raises:
            RuntimeError: if no video is loaded.
        """
        if self._video_info is None:
            raise RuntimeError("No video loaded")

        # -- Step 1: Extract frames (uses cache) --
        frames = self.extract_frames(rate_fps)
        if not frames:
            raise RuntimeError("No frames extracted")

        vhash = self._video_hash()

        # -- Step 2: Detect scenes from extracted frames --
        scenes = self._scene_detector.detect_from_video(
            self._video_info.path, target_fps=rate_fps
        )
        logger.info("Detected %d scenes", len(scenes))

        # -- Step 3: Check AI cache (cache key is video-only, not prompt) --
        cached = self._cache_service.get_cached_analysis(vhash, "default_prompt")
        if cached is not None:
            logger.info("Loading analysis from cache")
            self._analysis_result = AnalysisResult(**cached[0]) if cached else None
        else:
            # -- Step 4: AI vision analysis (scene-based, never duplicates) --
            frame_map = {str(f): f for f in frames}
            self._analysis_result = self._ai_service.analyze_scenes(
                scenes=scenes,
                frame_paths=frames,
            )

            # -- Step 6: Cache results (video-hash only) --
            self._cache_service.save_analysis(
                vhash, "default_prompt", [self._analysis_result.__dict__]
            )
            logger.info("Analysis cached for video hash %s", vhash)

        # -- Step 5: Build Timeline from analysis --
        if self._analysis_result is None:
            raise RuntimeError("AI analysis produced no result")

        self._timeline = self._timeline_service.build_from_analysis(
            self._analysis_result,
            self._video_info.path,
            min_score=4.0,
        )

        logger.info(
            "Timeline built with %d events", len(self._timeline.events)
        )

        return self._timeline

    # ------------------------------------------------------------------
    # Frame extraction
    # ------------------------------------------------------------------

    def extract_frames(self, rate_fps: float = 1.0) -> list[Path]:
        """Extract frames at the given rate.

        Uses cache to skip already-extracted frames.

        Raises:
            RuntimeError: if no video is loaded.
        """
        if self._video_info is None:
            raise RuntimeError("No video loaded")

        vhash = self._video_hash()

        # Check cache
        if self._cache_service.has_frames(vhash, rate_fps):
            frames_dir = self._cache_service.get_frames_dir(vhash)
            return sorted(frames_dir.glob("*.png"))

        frames = self._frame_extractor.extract_all_frames(
            self._video_info, rate_fps
        )

        # Update cache marker
        self._cache_service.mark_frames_done(vhash, rate_fps)
        return frames

    # ------------------------------------------------------------------
    # Prompt-based filtering (NEVER reruns AI)
    # ---------------------------------------------------------------------------

    def filter_timeline(
        self,
        prompt: str,
    ) -> Timeline:
        """Filter the existing timeline using a natural-language prompt.

        This method does NOT call the vision AI.  It only filters, sorts,
        and slices the already-analyzed TimelineEvents stored in the cache.

        Args:
            prompt: Natural language edit intent.
                Examples:
                    "Create a 3 minute highlight"
                    "Only curves and hairpins"
                    "Cinematic sunset edit"
                    "Top 10 best moments"

        Raises:
            RuntimeError: if no timeline exists (call analyze_video first).
        """
        if self._timeline is None or not self._timeline.events:
            raise RuntimeError(
                "No timeline available. Run analyze_video() first."
            )

        # Use PromptService to filter existing events
        filtered_events = self._prompt_service.apply(
            self._timeline, prompt
        )

        logger.info(
            "Prompt '%s' → %d events (from %d total)",
            prompt[:40], len(filtered_events), len(self._timeline.events),
        )

        # Build a new timeline with the filtered events
        filtered_timeline = Timeline(
            video_path=self._timeline.video_path,
            events=filtered_events,
            scenes=self._timeline.scenes,
        )

        self._timeline = filtered_timeline
        return filtered_timeline

    # ------------------------------------------------------------------
    # Event manipulation (manual timeline editing)
    # ------------------------------------------------------------------

    def remove_events(self, event_ids: list[str]) -> None:
        """Remove specific events from the timeline by ID."""
        if self._timeline is None:
            raise RuntimeError("No timeline available")
        self._timeline_service.remove_events(self._timeline, event_ids)

    def add_manual_event(
        self,
        start_time: float,
        end_time: float,
        score: float = 5.0,
        description: str = "Manual selection",
        tags: list[str] | None = None,
    ) -> TimelineEvent:
        """Add a manually created event to the timeline."""
        if self._timeline is None:
            raise RuntimeError("No timeline available")

        evt = TimelineEvent(
            start_time=start_time,
            end_time=end_time,
            score=score,
            description=description,
            reason="Manually added by user",
            tags=tags or ["manual"],
        )

        self._timeline_service.add_events(self._timeline, [evt])
        return evt

    def get_events_by_score_range(
        self,
        low: float,
        high: float,
    ) -> list[TimelineEvent]:
        """Return events whose score falls within [low, high]."""
        if self._timeline is None:
            raise RuntimeError("No timeline available")
        return self._timeline_service.get_events_by_score_range(
            self._timeline, low, high
        )

    def get_total_highlight_duration(self) -> float:
        """Sum of all event durations in seconds."""
        if self._timeline is None:
            return 0.0
        return self._timeline_service.get_total_highlight_duration(self._timeline)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_video(
        self,
        output_path: str | Path,
        codec: str = "h264",
        use_nvenc: bool = True,
        crf: int = 23,
        preset: str = "medium",
    ) -> Path:
        """Export the current timeline to a video file.

        Raises:
            RuntimeError: if no video or timeline is available.
        """
        if self._video_info is None:
            raise RuntimeError("No video loaded")
        if self._timeline is None:
            raise RuntimeError("No timeline generated – run analyze_video() first")

        settings = ExportSettings(
            output_path=Path(output_path),
            video_codec=codec,  # type: ignore[typeddict-item]
            use_nvenc=use_nvenc,
            quality_crf=crf,
            preset=preset,
        )

        return self._export_service.export(
            source_video=self._video_info.path,
            timeline=self._timeline,
            settings=settings,
        )

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def clear_cache(self) -> None:
        """Clear all cached frames and analysis results."""
        self._cache_service.clear_all()

    def get_cache_size(self) -> int:
        """Return total cache size in bytes."""
        return self._cache_service.get_cache_size()

    # ------------------------------------------------------------------
    # Summary info for UI display
    # ------------------------------------------------------------------

    def get_analysis_summary(self) -> dict[str, Any]:
        """Return a human-readable summary of the analysis.

        Suitable for displaying statistics in the UI.
        """
        if self._timeline is None:
            return {"status": "no_analysis"}

        events = self._timeline.events
        if not events:
            return {"status": "no_events"}

        # Tag frequency
        tag_counts: dict[str, int] = {}
        for evt in events:
            for tag in evt.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        score_values = [e.score for e in events]
        return {
            "status": "ready",
            "total_events": len(events),
            "total_duration_sec": sum(e.duration for e in events),
            "min_score": min(score_values),
            "max_score": max(score_values),
            "avg_score": sum(score_values) / len(score_values),
            "top_tags": dict(
                sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
            "scenes_count": len(self._timeline.scenes or []),
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_controller() -> MainController:
    """Create a fully-wired MainController (dependency injection point)."""
    return MainController()