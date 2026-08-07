"""Frame extraction service – delegates to FFmpeg, never OpenCV."""

from __future__ import annotations

import os
from pathlib import Path

from core.ffmpeg import extract_frame_at, extract_frames_by_rate
from models.video_info import VideoInfo


class FrameExtractor:
    """Extract individual frames or frame batches from a video via FFmpeg."""

    def __init__(self, frames_dir: Path = Path("output/frames")):
        self.frames_dir = frames_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_thumbnail_frame(
        self,
        video: VideoInfo,
        timestamp: float,
    ) -> Path:
        """Extract a single frame suitable for use as a thumbnail."""
        safe_name = _safe_filename(video.filename)
        output = self.frames_dir / f"{safe_name}_{timestamp:.2f}.png"
        return extract_frame_at(video.path, timestamp, output)

    def extract_all_frames(
        self,
        video: VideoInfo,
        rate_fps: float = 1.0,
    ) -> list[Path]:
        """Extract frames at the given rate (frames per second).

        Returns an ordered list of frame paths.
        """
        safe_name = _safe_filename(video.filename)
        self.frames_dir.mkdir(parents=True, exist_ok=True)

        pattern = self.frames_dir / f"{safe_name}_{rate_fps}fps_%04d.png"

        # Clean old frames for this video + rate
        ext = ".png"
        stem = f"{safe_name}_{rate_fps}fps_"
        old_frames = sorted(self.frames_dir.glob(f"{stem}*{ext}"))
        for old in old_frames:
            old.unlink()

        return extract_frames_by_rate(video.path, rate_fps, pattern)

    def clear_frames(self, video: VideoInfo) -> None:
        """Remove all extracted frames for a given video."""
        safe_name = _safe_filename(video.filename)
        for f in self.frames_dir.glob(f"{safe_name}*"):
            f.unlink()


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _safe_filename(name: str) -> str:
    """Sanitize a video filename for use as a prefix."""
    stem = Path(name).stem
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in stem)