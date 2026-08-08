"""Models package – domain data classes for AiEditor."""

from models.event import EventType, RoadQualityScores, TelemetryData, TimelineEvent
from models.scene import Scene
from models.timeline import Timeline
from models.video_info import VideoInfo
from models.analysis import AnalysisResult, FrameAnalysis
from models.project import (
    Project,
    ProjectStatus,
    ProjectTelemetry,
    ProjectVideo,
    ProjectSettings,
)

__all__ = [
    # Core domain models
    "Scene",
    "Timeline",
    "TimelineEvent",
    "EventType",
    "RoadQualityScores",
    "TelemetryData",
    "VideoInfo",
    # Analysis
    "AnalysisResult",
    "FrameAnalysis",
    # Project
    "Project",
    "ProjectStatus",
    "ProjectTelemetry",
    "ProjectVideo",
    "ProjectSettings",
]

