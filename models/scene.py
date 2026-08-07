"""Scene model – represents a contiguous segment of a video.

A scene is a group of visually coherent frames that belong together.
Scene detection happens before AI analysis so the vision model receives
contextual groups instead of isolated frames.

Pipeline position:
    Frame Extraction → Scene Detection → AI Analysis
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Scene:
    """A contiguous segment of video with coherent visual content.

    Attributes:
        scene_id: Unique identifier for this scene.
        start_time: Start time in seconds (relative to video start).
        end_time: End time in seconds.
        frame_paths: Ordered list of extracted frames belonging to this scene.
        representative_frame: The single frame that best represents the scene.
        label: Optional human-readable label assigned by AI analysis.
    """

    start_time: float
    end_time: float
    frame_paths: list[Path] = field(default_factory=list)
    representative_frame: Path | None = None
    label: str = ""

    # Assigned during scene detection or after creation
    scene_id: str = ""

    def __post_init__(self) -> None:
        """Auto-generate a unique scene_id if not provided."""
        if not self.scene_id:
            self.scene_id = f"scene_{uuid.uuid4().hex[:10]}"

    @property
    def duration(self) -> float:
        """Duration of this scene in seconds."""
        return self.end_time - self.start_time

    @property
    def frame_count(self) -> int:
        """Number of frames in this scene."""
        return len(self.frame_paths)

    def __repr__(self) -> str:
        return (
            f"Scene(id={self.scene_id}, "
            f"{self.start_time:.1f}s–{self.end_time:.1f}s, "
            f"{self.frame_count} frames)"
        )