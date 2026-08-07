"""Event model – represents a detected point of interest in the video.

This module contains:
    - EventType enumeration (all recognized categories)
    - RoadQualityScores (multi-dimensional quality assessment)
    - TelemetryData (future GPS/sensor support)
    - TimelineEvent (the core building block of an editable timeline)

Pipeline position:
    AI Analysis → TimelineEvents → Timeline → Prompt Filter → Export
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ---------------------------------------------------------------------------
# Event Types
# ---------------------------------------------------------------------------

class EventType(Enum):
    """All recognizable event categories for motorcycle videos.

    The vision AI classifies each moment into one or more of these types.
    Tags on a TimelineEvent are drawn from this enumeration.
    """

    # -- Road geometry --
    MOTORCYCLE = "motorcycle"
    CURVE = "curve"
    HAIRPIN = "hairpin"
    BRIDGE = "bridge"
    TUNNEL = "tunnel"

    # -- Environment / scenery --
    FOREST = "forest"
    MOUNTAIN = "mountain"
    SEA = "sea"
    VILLAGE = "village"
    CITY = "city"
    HIGHWAY = "highway"

    # -- Action / behaviour --
    TRAFFIC = "traffic"
    OVERTAKE = "overtake"
    WHEELIE = "wheelie"
    DANGER = "danger"

    # -- Road quality descriptors --
    INTERESTING_ROAD = "interesting_road"
    SCENIC_ROAD = "scenic_road"

    # -- Lighting / weather --
    SUNSET = "sunset"
    SUNRISE = "sunrise"
    RAIN = "rain"
    NIGHT = "night"

    # -- Fallback --
    GENERIC = "generic"

    @classmethod
    def from_string(cls, value: str) -> EventType | None:
        """Look up an event type by its string value.

        Returns ``None`` if *value* does not match any member.
        """
        try:
            return cls(value.lower().replace(" ", "_"))
        except ValueError:
            return None

    @property
    def display_name(self) -> str:
        """Human-readable label (e.g. ``'Scenic Road'``)."""
        return self.value.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Road Quality Scores
# ---------------------------------------------------------------------------

@dataclass
class RoadQualityScores:
    """Multi-dimensional quality assessment for a video segment.

    Each dimension is scored on a 0–10 scale where higher is better
    (except *traffic_density*, where lower is better for riding enjoyment).

    These scores are produced by the vision AI for every detected event
    and stored alongside the TimelineEvent.
    """

    visual_beauty: float = 5.0
    road_quality: float = 5.0
    traffic_density: float = 5.0  # 0 = empty road, 10 = heavy traffic
    camera_stability: float = 5.0
    lighting: float = 5.0
    action_level: float = 5.0

    @property
    def average(self) -> float:
        """Overall average score (traffic inverted so higher is better)."""
        inverted_traffic = 10.0 - self.traffic_density
        return (
            self.visual_beauty
            + self.road_quality
            + inverted_traffic
            + self.camera_stability
            + self.lighting
            + self.action_level
        ) / 6.0

    def __post_init__(self) -> None:
        """Clamp all scores to [0, 10]."""
        for name in ("visual_beauty", "road_quality", "traffic_density",
                      "camera_stability", "lighting", "action_level"):
            val = getattr(self, name)
            setattr(self, name, max(0.0, min(10.0, float(val))))


# ---------------------------------------------------------------------------
# Telemetry (future support)
# ---------------------------------------------------------------------------

@dataclass
class TelemetryData:
    """Optional sensor/GPS data that can be fused with visual events.

    This structure is forward-compatible with future telemetry sources
    such as GPX files, GoPro GPS metadata, DJI telemetry, Garmin logs,
    or phone GPS recordings.
    """

    speed_kmh: float | None = None
    lean_angle: float | None = None
    acceleration: float | None = None
    altitude: float | None = None
    latitude: float | None = None
    longitude: float | None = None

    @property
    def has_data(self) -> bool:
        """Whether any telemetry field is populated."""
        return any([
            self.speed_kmh is not None,
            self.lean_angle is not None,
            self.acceleration is not None,
            self.altitude is not None,
            self.latitude is not None,
            self.longitude is not None,
        ])


# ---------------------------------------------------------------------------
# Timeline Event
# ---------------------------------------------------------------------------

@dataclass
class TimelineEvent:
    """A single point of interest detected by AI analysis.

    Every TimelineEvent corresponds to one moment identified as
    noteworthy (curve, scenic view, action, etc.) and carries enough
    metadata for the prompt engine to filter and assemble highlights
    without re-running the AI.

    Attributes:
        event_id: Unique identifier.
        start_time: Start offset in seconds.
        end_time: End offset in seconds.
        score: Overall highlight score (0–10).
        importance: Editor's priority score (0–10), may differ from score.
        description: Human-readable description of the moment.
        reason: Why the AI flagged this moment.
        tags: List of EventType string values.
        thumbnail: Path to a representative thumbnail image.
        scene_id: Link back to the source Scene.
        quality_scores: Multi-dimensional road quality assessment.
        telemetry: Optional GPS/sensor data.
    """

    start_time: float
    end_time: float
    score: float
    description: str = ""
    reason: str = ""
    tags: list[str] = field(default_factory=list)

    # Populated after creation or by defaults
    event_id: str = ""
    importance: float = 5.0
    thumbnail: Path | None = None
    scene_id: str = ""
    quality_scores: RoadQualityScores = field(default_factory=RoadQualityScores)
    telemetry: TelemetryData | None = None

    # Primary classification (from AI event_type field)
    event_type: EventType = EventType.GENERIC

    def __post_init__(self) -> None:
        """Auto-generate event_id and derive importance if needed."""
        if not self.event_id:
            self.event_id = f"evt_{uuid.uuid4().hex[:12]}"
        # If importance was not explicitly set, derive from score
        if self.importance == 5.0 and self.score != 5.0:
            self.importance = self.score

    @property
    def duration(self) -> float:
        """Duration of this event in seconds."""
        return max(0.0, self.end_time - self.start_time)

    def matches_event_type(self, event_type: EventType) -> bool:
        """Check if this event matches a given EventType."""
        return (
            self.event_type == event_type
            or event_type.value in self.tags
        )

    def __repr__(self) -> str:
        return (
            f"TimelineEvent(id={self.event_id}, "
            f"{self.start_time:.1f}s–{self.end_time:.1f}s, "
            f"score={self.score:.1f}, tags={self.tags})"
        )