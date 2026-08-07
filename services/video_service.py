"""Video loading and metadata service – uses ffprobe, NOT OpenCV."""

from __future__ import annotations

from pathlib import Path

from core.ffmpeg import ProbeResult, probe as ffmpeg_probe
from models.video_info import VideoInfo


class VideoService:
    """Delegates to ffprobe for all video metadata extraction."""

    @staticmethod
    def load(video_path: Path) -> VideoInfo:
        """Load video metadata and return a ``VideoInfo`` instance.

        This method **must not** use OpenCV.  All probing goes through
        :func:`core.ffmpeg.probe`.
        """
        if not video_path.is_file():
            raise FileNotFoundError(f"Video not found: {video_path}")

        probe_result: ProbeResult = ffmpeg_probe(video_path)

        return VideoInfo(
            path=video_path,
            filename=video_path.name,
            width=probe_result.width,
            height=probe_result.height,
            fps=probe_result.fps,
            frames=probe_result.frame_count,
            duration=probe_result.duration,
            codec=probe_result.video_codec,
            size=probe_result.size,
        )