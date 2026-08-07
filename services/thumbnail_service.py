"""Thumbnail generation service – delegates to FFmpeg via FrameExtractor."""

from __future__ import annotations

from pathlib import Path

from services.frame_extractor import FrameExtractor
from models.video_info import VideoInfo


class ThumbnailService:
    """Generate thumbnail previews for videos."""

    def __init__(self, frame_extractor: FrameExtractor | None = None):
        self._extractor = frame_extractor or FrameExtractor()
        self._thumbnail_dir = Path("output/thumbnails")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_thumbnail(
        self,
        video: VideoInfo,
        *,
        timestamp: float | None = None,
    ) -> Path:
        """Create a thumbnail for *video* at the given timestamp.

        If *timestamp* is ``None``, the middle of the video is used.
        """
        if timestamp is None:
            timestamp = video.duration / 2.0

        self._thumbnail_dir.mkdir(parents=True, exist_ok=True)

        # Reuse frame extraction (frames act as thumbnails)
        path = self._extractor.extract_thumbnail_frame(video, timestamp)

        # Also copy to the thumbnails dir for easy UI access
        out = self._thumbnail_dir / f"{Path(video.filename).stem}_thumb.png"
        import shutil
        shutil.copy2(path, out)
        return out

    def generate_sequence_thumbnails(
        self,
        video: VideoInfo,
        count: int = 10,
    ) -> list[Path]:
        """Generate *count* evenly-spaced thumbnails across the video."""
        self._thumbnail_dir.mkdir(parents=True, exist_ok=True)

        if count <= 0:
            return []

        stamps = _even_intervals(video.duration, count)
        thumbs: list[Path] = []
        for i, ts in enumerate(stamps):
            frame = self._extractor.extract_thumbnail_frame(video, ts)
            out = self._thumbnail_dir / f"{Path(video.filename).stem}_seq_{i:03d}.png"
            import shutil
            shutil.copy2(frame, out)
            thumbs.append(out)
        return thumbs


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _even_intervals(total: float, count: int) -> list[float]:
    """Return *count* timestamps evenly distributed over [0, total)."""
    if total <= 0 or count <= 0:
        return []
    step = total / count
    return [step * i + step / 2 for i in range(count)]