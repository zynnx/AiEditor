"""Project model – self-contained multi-video editing workspace.

A Project is the top-level container in the application.  Users never edit
individual videos directly; instead they work inside a project that may hold
many videos, their analysis results, telemetry data, and all derived caches.

Key design principles:
    - Portability: a project is a folder that can be zipped and moved without
      rebuilding any cache or re-running AI analysis.
    - Global timeline: events from every video are merged into one timeline
      with a shared time axis (the "project timeline").
    - Persistence: the project state is serialised to *project.json* at the
      root of the project folder.

Pipeline position:
    Project → [Video₁, Video₂, …] → AI Analysis → Global Timeline → Export
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Project state enumeration
# ---------------------------------------------------------------------------

class ProjectStatus(Enum):
    """High-level status of the project."""

    EMPTY = "empty"
    ANALYZING = "analyzing"
    READY = "ready"
    EXPORTING = "exporting"



# ---------------------------------------------------------------------------
# Single-video entry inside a project
# ---------------------------------------------------------------------------

@dataclass
class ProjectVideo:
    """Represents one video imported into the project.

    Attributes:
        video_id: Unique identifier within this project.
        source_path: Original absolute path on disk (may differ from stored
                     copy if the user only references an external file).
        stored_path: Path inside the project folder (empty string if not copied).
        filename: Human-readable name for the UI tree view.
        width: Video width in pixels.
        height: Video height in pixels.
        fps: Frames per second.
        duration: Total duration in seconds.
        codec: Primary video codec.
        size_bytes: File size on disk.
        analysis_done: Whether AI analysis has been run for this video.
        cache_valid: Whether cached frames/scenes/thumbnails are still valid.
    """

    source_path: str = ""
    stored_path: str = ""
    filename: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    duration: float = 0.0
    codec: str = ""
    size_bytes: int = 0

    # Analysis state flags
    analysis_done: bool = False
    cache_valid: bool = False

    # Auto-assigned id
    video_id: str = ""

    def __post_init__(self) -> None:
        if not self.video_id:
            self.video_id = f"vid_{uuid.uuid4().hex[:10]}"
        if not self.filename and self.source_path:
            self.filename = Path(self.source_path).name

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def resolution(self) -> str:
        return f"{self.width} x {self.height}"

    @property
    def size_text(self) -> str:
        gb = self.size_bytes / (1024 ** 3)
        if gb >= 1:
            return f"{gb:.2f} GB"
        mb = self.size_bytes / (1024 ** 2)
        return f"{mb:.2f} MB"

    @property
    def duration_text(self) -> str:
        total = int(self.duration)
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes:02}m {seconds:02}s"
        return f"{minutes}m {seconds:02}s"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ProjectVideo:
        return cls(**d)


# ---------------------------------------------------------------------------
# Telemetry container (future GPS / sensor data per project)
# ---------------------------------------------------------------------------

@dataclass
class ProjectTelemetry:
    """Placeholder for GPS and sensor telemetry associated with a project.

    When real telemetry sources are added (GPX, GoPro metadata, phone logs)
    they will be attached here keyed by video_id.
    """

    data: dict[str, Any] = field(default_factory=dict)

    def add_source(self, video_id: str, key: str, value: Any) -> None:
        self.data.setdefault(video_id, {})[key] = value

    def has_data(self, video_id: str) -> bool:
        return video_id in self.data and self.data[video_id]


# ---------------------------------------------------------------------------
# Project settings
# ---------------------------------------------------------------------------

@dataclass
class ProjectSettings:
    """User-adjustable settings that persist with the project."""

    default_prompt: str = ""
    min_score: float = 5.0
    max_duration: float = 300.0
    highlight_style: str = "standard"
    transition_duration: float = 0.5


# ---------------------------------------------------------------------------
# Project – the top-level model
# ---------------------------------------------------------------------------

@dataclass
class Project:
    """A self-contained editing workspace with multiple videos.

    Attributes:
        project_id: Unique UUID for this project.
        name: Human-readable project name.
        path: Root folder of the project on disk.
        videos: Ordered list of imported videos.
        telemetry: GPS / sensor data attached to the project.
        settings: Persisted user settings.
        status: Current pipeline status (empty, analyzing, ready, …).
        created_at: ISO timestamp of creation.
        modified_at: ISO timestamp of last modification.
    """

    name: str = "Untitled Project"
    path: str = ""
    videos: list[ProjectVideo] = field(default_factory=list)
    telemetry: ProjectTelemetry = field(default_factory=ProjectTelemetry)
    settings: ProjectSettings = field(default_factory=ProjectSettings)
    status: ProjectStatus = ProjectStatus.EMPTY

    # Metadata
    project_id: str = ""
    created_at: str = ""
    modified_at: str = ""

    def __post_init__(self) -> None:
        if not self.project_id:
            self.project_id = uuid.uuid4().hex


    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def project_folder(self) -> Path:
        """Resolved path to the project folder."""
        return Path(self.path) if self.path else Path()

    @property
    def media_folder(self) -> Path:
        """Folder inside the project where video files are stored."""
        return self.project_folder / "media"

    @property
    def cache_folder(self) -> Path:
        """Folder inside the project for frames, thumbnails, AI cache."""
        return self.project_folder / "cache"

    @property
    def total_duration(self) -> float:
        """Combined duration of all videos in seconds."""
        return sum(v.duration for v in self.videos)

    @property
    def total_size_bytes(self) -> int:
        """Combined file size of all videos."""
        return sum(v.size_bytes for v in self.videos)

    @property
    def video_count(self) -> int:
        return len(self.videos)

    @property
    def project_file(self) -> Path:
        """Path to the *project.json* manifest."""
        return self.project_folder / "project.json"

    # ------------------------------------------------------------------
    # Video management helpers
    # ------------------------------------------------------------------

    def add_video(self, video: ProjectVideo) -> None:
        """Append a video and mark modified."""
        from datetime import datetime, timezone
        self.videos.append(video)
        self.modified_at = datetime.now(timezone.utc).isoformat()

    def remove_video(self, video_id: str) -> ProjectVideo | None:
        """Remove a video by id. Returns the removed video or None."""
        from datetime import datetime, timezone
        for i, v in enumerate(self.videos):
            if v.video_id == video_id:
                removed = self.videos.pop(i)
                self.modified_at = datetime.now(timezone.utc).isoformat()
                return removed
        return None

    def get_video(self, video_id: str) -> ProjectVideo | None:
        """Look up a video by id."""
        for v in self.videos:
            if v.video_id == video_id:
                return v
        return None


    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise the project to a plain dictionary."""
        return {
            "project_id": self.project_id,
            "name": self.name,
            "path": self.path,
            "videos": [v.to_dict() for v in self.videos],
            "telemetry": self.telemetry.data,
            "settings": asdict(self.settings),
            "status": self.status.value,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Project:
        """Deserialise a project from a dictionary (e.g. loaded JSON)."""
        project = cls()
        project.project_id = d.get("project_id", uuid.uuid4().hex)
        project.name = d.get("name", "Untitled Project")
        project.path = d.get("path", "")
        project.videos = [ProjectVideo.from_dict(vd) for vd in d.get("videos", [])]
        if "telemetry" in d:
            project.telemetry.data = d["telemetry"]
        if "settings" in d:
            project.settings = ProjectSettings(**d["settings"])
        status_val = d.get("status", "empty")
        try:
            project.status = ProjectStatus(status_val)
        except ValueError:
            project.status = ProjectStatus.EMPTY
        project.created_at = d.get("created_at", "")
        project.modified_at = d.get("modified_at", "")
        return project

    # ------------------------------------------------------------------
    # File I/O helpers (delegated to ProjectManager for side-effects)
    # ------------------------------------------------------------------

    def save_to_file(self, filepath: Path | str) -> None:
        """Persist project state to a JSON file."""
        target = Path(filepath)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, filepath: Path | str) -> Project:
        """Load a project from a JSON file."""
        fp = Path(filepath)
        if not fp.is_file():
            raise FileNotFoundError(f"Project file not found: {fp}")
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def __repr__(self) -> str:
        return (
            f"Project(id={self.project_id[:8]}, "
            f"name='{self.name}', "
            f"videos={self.video_count})"
        )

