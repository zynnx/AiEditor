"""Cache service – manages extracted frames and analysis cache."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CacheService:
    """Manages frame cache and AI analysis cache to avoid redundant work."""

    def __init__(self) -> None:
        self._cache_dir = Path("output/cache")
        self._frames_dir = Path("output/frames")
        self._thumbs_dir = Path("output/thumbnails")
        for d in (self._cache_dir, self._frames_dir, self._thumbs_dir):
            d.mkdir(parents=True, exist_ok=True)

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
        """Save AI analysis results to cache."""
        cache_file = self._analysis_path(video_hash, prompt_hash)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

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