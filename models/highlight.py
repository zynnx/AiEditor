"""Highlight configuration and output models."""
from dataclasses import dataclass
from enum import Enum



class HighlightStyle(Enum):
    """Style of the highlight edit."""
    STANDARD = "standard"
    CINEMATIC = "cinematic"
    YOUTUBE = "youtube"
    SHORTS = "shorts"



@dataclass(slots=True, frozen=True)
class HighlightConfig:
    """Configuration for highlight generation."""
    style: HighlightStyle = HighlightStyle.STANDARD
    min_score: float = 6.0
    max_duration: float = 300.0
    transition_duration: float = 0.5
    prompt: str = ""



@dataclass(slots=True, frozen=True)
class HighlightClip:
    """A single clip in the highlight."""
    start: float
    end: float
    score: float
    reason: str


    @property
    def duration(self) -> float:
        return self.end - self.start



@dataclass(slots=True, frozen=True)
class HighlightResult:
    """Result of highlight generation."""
    clips: list[HighlightClip]
    total_duration: float


