"""Analysis result – the complete output of the Vision AI pipeline.

The AnalysisResult is the bridge between raw AI frame analysis and the
editable Timeline.  It contains:

1. **Frame-level scores** from the vision model (never stored permanently).
2. **Detected scenes** with representative frames.
3. **TimelineEvents** that are promoted from high-scoring frames.

Once the AnalysisResult is built, the AI is no longer needed.  The
PromptService can filter the embedded timeline multiple times without
re-running the vision model.

Pipeline position:
    AI Analysis → AnalysisResult → Timeline → Prompt Filter → Export
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from models.event import TimelineEvent, EventType, RoadQualityScores
from models.scene import Scene


# --------------------------------------------------------------------------
# Frame-level AI output (transient – not cached long-term)
# --------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class FrameAnalysis:
    """AI analysis result for a single frame."""

    timestamp: float
    score: float
    reason: str
    tags: list[str]

    @property
    def star_rating(self) -> int:
        if self.score >= 9.0:
            return 5
        if self.score >= 7.5:
            return 4
        if self.score >= 6.0:
            return 3
        if self.score >= 4.0:
            return 2
        return 1

    @property
    def star_text(self) -> str:
        return "⭐" * self.star_rating


# --------------------------------------------------------------------------
# Road quality scores (per scene)
# --------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class RoadQualityScores:
    """Multi-dimensional quality assessment for a scene.

    Attributes:
        visual_beauty: How visually pleasing the scene is (0-10).
        road_quality: Condition and character of the road itself (0-10).
        traffic_density: Inverse – low traffic scores higher (0-10).
        camera_stability: Steadiness of the footage (0-10).
        lighting: Quality of natural/artificial light (0-10).
        action_level: Excitement / rider activity (0-10).
    """

    visual_beauty: float = 5.0
    road_quality: float = 5.0
    traffic_density: float = 5.0
    camera_stability: float = 5.0
    lighting: float = 5.0
    action_level: float = 5.0

    @property
    def average(self) -> float:
        """Overall average across all dimensions."""
        return round(
            (
                self.visual_beauty
                + self.road_quality
                + self.traffic_density
                + self.camera_stability
                + self.lighting
                + self.action_level
            )
            / 6,
            1,
        )


# --------------------------------------------------------------------------
# Complete analysis result
# --------------------------------------------------------------------------


@dataclass
class AnalysisResult:
    """Complete result of analyzing one video through the full pipeline.

    Attributes:
        overall_score: Weighted average score across all frames.
        frame_analyses: Raw per-frame AI output (transient).
        best_moments: Frames that scored >= 7.0.
        scenes: Detected scene segments.
        events: Promoted timeline events ready for editing.
        road_scores: Per-scene quality breakdown.
    """

    overall_score: float = 0.0
    frame_analyses: list[FrameAnalysis] = field(default_factory=list)
    best_moments: list[FrameAnalysis] = field(default_factory=list)
    scenes: list[Scene] = field(default_factory=list)
    events: list[TimelineEvent] = field(default_factory=list)
    road_scores: list[RoadQualityScores] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def scene_count(self) -> int:
        return len(self.scenes)