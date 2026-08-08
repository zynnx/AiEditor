"""Cache service – manages extracted frames and analysis cache."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any

from models.analysis import AnalysisResult, FrameAnalysis
from models.event import EventType, RoadQualityScores, TelemetryData
from models.scene import Scene
from models.event import TimelineEvent

logger = logging.getLogger(__name__)


class CacheService:
    """Manages frame cache and AI analysis cache to avoid redundant work."""

    def __init__(self) -> None:
        self._cache_dir = Path("output/cache")
        self._frames_dir = Path("output/frames")
        self._thumbs_dir = Path("output/thumbnails")
        for d in (self._cache_dir, self._frames_dir, self._thumbs_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Serialization helpers (analysis cache)
    # ------------------------------------------------------------------

    @staticmethod
    def _make_json_default() -> Any:
        """Return a JSON encoder default function that handles Path and Enum."""
        def _default(obj: Any) -> Any:
            if isinstance(obj, Path):
                return obj.as_posix()
            if isinstance(obj, Enum):
                return obj.value
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
        return _default

    @staticmethod
    def _serialize_analysis(result: AnalysisResult) -> dict[str, Any]:
        """Convert AnalysisResult and all nested objects to a plain dict."""
        return asdict(result)

    @staticmethod
    def _deserialize_analysis(data: dict[str, Any]) -> AnalysisResult:
        """Reconstruct an AnalysisResult from a plain JSON dict."""
        frames = [
            FrameAnalysis(**f) for f in data.get("frame_analyses", [])
        ]
        moments = [
            FrameAnalysis(**f) for f in data.get("best_moments", [])
        ]
        scenes = [
            Scene(
                start_time=s["start_time"],
                end_time=s["end_time"],
                frame_paths=[Path(p) for p in s.get("frame_paths", [])],
                representative_frame=Path(s["representative_frame"]) if s.get("representative_frame") else None,
                label=s.get("label", ""),
                scene_id=s.get("scene_id", ""),
            )
            for s in data.get("scenes", [])
        ]
        events = [
            TimelineEvent(
                start_time=e["start_time"],
                end_time=e["end_time"],
                score=e["score"],
                description=e.get("description", ""),
                reason=e.get("reason", ""),
                tags=e.get("tags", []),
                event_id=e.get("event_id", ""),
                importance=e.get("importance", 5.0),
                thumbnail=Path(e["thumbnail"]) if e.get("thumbnail") else None,
                scene_id=e.get("scene_id", ""),
                quality_scores=RoadQualityScores(**e["quality_scores"]) if e.get("quality_scores") else RoadQualityScores(),
                telemetry=TelemetryData(**e["telemetry"]) if e.get("telemetry") else None,
                event_type=EventType.from_string(e.get("event_type", "generic")) or EventType.GENERIC,
            )
            for e in data.get("events", [])
        ]
        road = [
            RoadQualityScores(**r) for r in data.get("road_scores", [])
        ]
        return AnalysisResult(
            overall_score=data.get("overall_score", 0.0),
            frame_analyses=frames,
            best_moments=moments,
            scenes=scenes,
            events=events,
            road_scores=road,
        )

    # ------------------------------------------------------------------
    # Frame cache
    # ------------------------------------------------------------------

    def get_frames_dir(self, video_hash: str) -> Path:
        """Return the directory where frames for a video are stored."""
        return self._frames_dir / video_hash

    def has_frames(self, video_hash: str, rate_fps: float) -> bool:
        """Check if frames were already extracted at the given rate."""
        frames_dir = self.get_frames_dir(video_hash)
        marker = frames_dir / f"{rate_fps}.fps.done"
        return marker.exists() and len(list(frames_dir.glob("*.png"))) > 0

    def mark_frames_done(self, video_hash: str, rate_fps: float) -> None:
        """Mark frame extraction as complete."""
        marker = self.get_frames_dir(video_hash) / f"{rate_fps}.fps.done"
        marker.touch()

    def clear_frames(self, video_hash: str) -> None:
        """Remove all cached frames for a video."""
        import shutil
        frames_dir = self.get_frames_dir(video_hash)
        if frames_dir.exists():
            shutil.rmtree(frames_dir)

    # ------------------------------------------------------------------
    # AI analysis cache
    # ------------------------------------------------------------------

    def _analysis_path(self, video_hash: str, prompt_hash: str) -> Path:
        """Return the file path for a cached AI analysis result."""
        return self._cache_dir / f"{video_hash}_{prompt_hash}.json"

    def get_cached_analysis(
        self,
        video_hash: str,
        prompt_hash: str,
    ) -> list[dict[str, Any]] | None:
        """Return cached analysis results, or None if not available."""
        cache_file = self._analysis_path(video_hash, prompt_hash)
        if cache_file.is_file():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def save_analysis(
        self,
        video_hash: str,
        prompt_hash: str,
        results: list[dict[str, Any]],
    ) -> None:
        """Save AI analysis results to cache.

        Handles Path and Enum objects via a custom JSON default encoder.
        """
        cache_file = self._analysis_path(video_hash, prompt_hash)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=self._make_json_default())

    def save_analysis_result(
        self,
        video_hash: str,
        prompt_hash: str,
        result: AnalysisResult,
    ) -> None:
        """Save a typed AnalysisResult to cache with full serialization."""
        data = self._serialize_analysis(result)
        cache_file = self._analysis_path(video_hash, prompt_hash)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump([data], f, indent=2, default=self._make_json_default())
        logger.info("Analysis cached for video hash %s (type-safe)", video_hash)

    def load_cached_analysis(
        self,
        video_hash: str,
        prompt_hash: str,
    ) -> AnalysisResult | None:
        """Load a cached AnalysisResult, fully reconstructed from disk.

        Returns ``None`` if the cache file is missing or corrupt.
        """
        cache_file = self._analysis_path(video_hash, prompt_hash)
        if not cache_file.is_file():
            return None
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data_list = json.load(f)
            if isinstance(data_list, list) and len(data_list) >= 1:
                return self._deserialize_analysis(data_list[0])
            # Legacy single-dict format (if any)
            if isinstance(data_list, dict):
                return self._deserialize_analysis(data_list)
            return None
        except (json.JSONDecodeError, OSError, KeyError, TypeError) as exc:
            logger.warning("Corrupt analysis cache for %s: %s", video_hash, exc)
            return None

    # ------------------------------------------------------------------
    # General cleanup
    # ------------------------------------------------------------------

    def clear_all(self) -> None:
        """Clear all cached data."""
        import shutil
        for d in (self._cache_dir, self._frames_dir, self._thumbs_dir):
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)

    def get_cache_size(self) -> int:
        """Return total cache size in bytes."""
        total = 0
        for d in (self._cache_dir, self._frames_dir, self._thumbs_dir):
            if d.exists():
                for p in d.rglob("*"):
                    if p.is_file():
                        total += p.stat().st_size
        return total