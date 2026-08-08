"""Scene detection service – groups consecutive frames into coherent scenes.

Before AI analysis runs, every video's extracted frames are passed through
this detector to form logical scene boundaries.  The vision AI then receives
frames grouped by scene instead of as isolated images, which dramatically
improves context understanding and reduces redundant API calls.

Algorithm
---------
For each pair of consecutive frames:
    1. Resize both frames to a small comparison size (64×64).
    2. Compute the Mean Absolute Difference (MAD) between them.
    3. If MAD exceeds the configured threshold → new scene boundary.

Threshold tuning:
    - Higher values = fewer, longer scenes
    - Lower values = more, shorter scenes

Pipeline position:
    Frame Extraction → Scene Detection → AI Analysis
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from models.scene import Scene

logger = logging.getLogger(__name__)


@dataclass
class SceneDetectorConfig:
    """Configuration for scene boundary detection.

    Attributes:
        mad_threshold: Mean Absolute Difference threshold (0-255).
                       Values above this mark a new scene.
                        Default is 35 (good for motorcycle dashcam footage).
        min_scene_duration: Minimum scene length in seconds.
                            Shorter segments are merged with neighbors.
        comparison_size: Width×Height to resize frames before comparison.
                         Smaller = faster, larger = more precise.
    """

    mad_threshold: float = 35.0
    min_scene_duration: float = 2.0
    comparison_size: tuple[int, int] = (64, 64)


class SceneDetector:
    """Detects scene boundaries in an ordered list of timestamped frames.

    Args:
        config: Detection parameters. Uses sensible defaults if omitted.
    """

    def __init__(self, config: SceneDetectorConfig | None = None) -> None:
        self._config = config or SceneDetectorConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_scenes(
        self,
        frames: list[tuple[float, Path]],
        fps: float = 1.0,
    ) -> list[Scene]:
        """Group timestamped frames into contiguous scenes.

        Args:
            frames: List of ``(timestamp_seconds, frame_path)`` tuples,
                    ordered chronologically.
            fps: Frames-per-second rate used to estimate scene duration
                 when timestamps are uniform.

        Returns:
            Ordered list of Scene objects.  Each scene's *frame_paths*
            is pre-populated and *representative_frame* is set to the
            middle frame of the segment.
        """
        if not frames:
            return []

        # Step 1: find boundary indices
        boundaries = self._find_boundaries(frames)

        # Step 2: build Scene objects from boundaries
        scenes = self._build_scenes(frames, boundaries, fps)

        logger.info(
            "Detected %d scenes from %d frames", len(scenes), len(frames)
        )
        return scenes

    def detect_from_video(
        self,
        video_path: Path,
        *,
        target_fps: float = 1.0,
        frames_dir: Path | None = None,
    ) -> list[Scene]:
        """Convenience method: load extracted frames from disk and detect scenes.

        This method assumes frames were already extracted by FrameExtractor
        using the naming pattern ``<safe_name>_<rate>fps_%04d.png`` inside
        ``frames_dir`` (default ``output/frames``).

        Args:
            video_path: Path to the source video (used to derive frame pattern).
            target_fps: The extraction rate used (default 1.0).
            frames_dir: Directory containing extracted frames.

        Returns:
            Ordered list of Scene objects.
        """
        if frames_dir is None:
            frames_dir = Path("output/frames")

        # Derive the safe filename used by FrameExtractor
        stem = Path(video_path).stem
        safe_name = "".join(
            ch if ch.isalnum() or ch == "_" else "_" for ch in stem
        )

        pattern = frames_dir / f"{safe_name}_{target_fps}fps_*.png"
        frame_files = sorted(frame_files for frame_files in frames_dir.glob(pattern))

        if not frame_files:
            logger.warning("No extracted frames found for %s", video_path)
            return []

        # Build (timestamp, path) tuples – one frame per second
        timestamped_frames: list[tuple[float, Path]] = [
            (float(i) / target_fps, fp) for i, fp in enumerate(frame_files)
        ]

        logger.info(
            "Loaded %d frames from disk for scene detection", len(timestamped_frames)
        )
        return self.detect_scenes(timestamped_frames, fps=target_fps)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_boundaries(
        self,
        frames: list[tuple[float, Path]],
    ) -> list[int]:
        """Return the starting index of each new scene.

        Always includes 0 (first frame starts a scene).
        """
        boundaries: list[int] = [0]

        for i in range(1, len(frames)):
            prev_img = self._load_frame(frames[i - 1][1])
            curr_img = self._load_frame(frames[i][1])

            if prev_img is None or curr_img is None:
                continue

            mad = self._mean_absolute_difference(prev_img, curr_img)

            if mad > self._config.mad_threshold:
                boundaries.append(i)

        return boundaries

    def _build_scenes(
        self,
        frames: list[tuple[float, Path]],
        boundaries: list[int],
        fps: float,
    ) -> list[Scene]:
        """Convert boundary indices into Scene dataclasses."""
        scenes: list[Scene] = []

        for idx, start in enumerate(boundaries):
            end = boundaries[idx + 1] if idx + 1 < len(boundaries) else len(frames)
            segment = frames[start:end]

            if not segment:
                continue

            start_time = segment[0][0]
            end_time = segment[-1][0]

            # Enforce minimum duration → merge with previous scene if too short
            if (end_time - start_time) < self._config.min_scene_duration and scenes:
                prev = scenes[-1]
                prev.frame_paths.extend(p for _, p in segment)
                # Update representative frame to middle of extended scene
                mid = len(prev.frame_paths) // 2
                prev.representative_frame = prev.frame_paths[mid]
                prev.end_time = end_time
            else:
                paths = [p for _, p in segment]
                mid_idx = len(paths) // 2
                scene = Scene(
                    start_time=start_time,
                    end_time=end_time,
                    frame_paths=paths,
                    representative_frame=paths[mid_idx] if paths else None,
                )
                scenes.append(scene)

        return scenes

    # ------------------------------------------------------------------
    # Low-level image comparison
    # ------------------------------------------------------------------

    @staticmethod
    def _load_frame(path: Path) -> np.ndarray | None:
        """Load an image and convert to grayscale for comparison."""
        img = cv2.imread(str(path))
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return gray

    @staticmethod
    def _mean_absolute_difference(
        img1: np.ndarray,
        img2: np.ndarray,
        size: tuple[int, int] = (64, 64),
    ) -> float:
        """Compute the Mean Absolute Difference between two grayscale images.

        Both images are resized to *size* before comparison to ensure
        a consistent scale.
        """
        a = cv2.resize(img1, size)
        b = cv2.resize(img2, size)

        diff = cv2.absdiff(a, b).astype(np.float32)
        return np.mean(diff)