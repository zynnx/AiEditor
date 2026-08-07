"""Timeline model – the editable collection of events generated from AI analysis.

The Timeline is the central artifact produced by the analysis pipeline.
It contains every detected TimelineEvent and serves as the source for
all subsequent edits.  The same Timeline can be filtered multiple times
by the PromptService without re-running the vision AI.

Pipeline position:
    AI Analysis → TimelineEvents → Timeline → Prompt Filter → Export
"""

from __future__ import annotations

from dataclasses import dataclass, field
from models.event import TimelineEvent


@dataclass
class Timeline:
    """Ordered collection of timeline events representing the full analysis.

    Attributes:
        events: Every detected point of interest, sorted by start_time.
    """

    events: list[TimelineEvent] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def total_duration(self) -> float:
        """Combined duration of all events in seconds."""
        return sum(evt.duration for evt in self.events)

    @property
    def event_count(self) -> int:
        """Number of events in this timeline."""
        return len(self.events)

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def add_event(self, event: TimelineEvent) -> None:
        """Append an event and keep the list sorted by start_time."""
        self.events.append(event)
        self.events.sort(key=lambda e: e.start_time)

    def clear(self) -> None:
        """Remove all events."""
        self.events.clear()

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def filter_by_min_score(self, min_score: float) -> list[TimelineEvent]:
        """Return events whose score >= *min_score*."""
        return [e for e in self.events if e.score >= min_score]

    def filter_by_tags(self, tags: list[str]) -> list[TimelineEvent]:
        """Return events that contain **all** of the given tags."""
        tag_set = set(t.lower() for t in tags)
        return [
            e for e in self.events
            if tag_set.issubset(set(t.lower() for t in e.tags))
        ]

    def filter_by_time_range(
        self, start: float | None = None, end: float | None = None
    ) -> list[TimelineEvent]:
        """Return events that overlap the given time window."""
        result: list[TimelineEvent] = []
        for e in self.events:
            if start is not None and e.end_time < start:
                continue
            if end is not None and e.start_time > end:
                continue
            result.append(e)
        return result

    def top_n(self, n: int) -> list[TimelineEvent]:
        """Return the *n* highest-scored events."""
        sorted_events = sorted(self.events, key=lambda e: e.score, reverse=True)
        return sorted_events[:n]

    def __repr__(self) -> str:
        return f"Timeline(events={self.event_count}, total_duration={self.total_duration:.1f}s)"