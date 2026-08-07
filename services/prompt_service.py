"""Prompt Service – natural language → TimelineEvent filtering.

This service is the bridge between what the user asks for (in plain text)
and the already-analyzed TimelineEvents stored in the Timeline.

The AI analysis should be independent from editing.  This service
**never calls the vision AI**.  It only filters, sorts, and slices
existing TimelineEvents based on the user's intent expressed as a prompt.

Pipeline position:
    Prompt → PromptService → filtered TimelineEvents → ExportService
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from models.event import EventType, TimelineEvent
from models.timeline import Timeline

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Intent types recognized by the prompt engine
# ---------------------------------------------------------------------------

class Intent(Enum):
    """High-level editing intent extracted from a user prompt."""
    HIGHLIGHTS = "highlights"          # Best moments by score
    DURATION = "duration"             # Create N-minute edit
    EVENT_TYPE_FILTER = "event_type"  # Only curves, only scenic, etc.
    CINEMATIC = "cinematic"           # Sunset + beautiful + slow pace
    ACTION = "action"                # High action_level score
    TOP_N = "top_n"                   # Top N clips

    @classmethod
    def from_keyword(cls, keyword: str) -> Intent:
        """Map a single keyword to an intent."""
        kw = keyword.lower()
        if any(w in kw for w in ("highlight", "best", "top")):
            return cls.HIGHLIGHTS
        if any(w in kw for w in ("minute", "min", "duration", "seconds", "sec")):
            return cls.DURATION
        if any(w in kw for w in ("cinematic", "beautiful", "scenic", "sunset")):
            return cls.CINEMATIC
        if any(w in kw for w in ("action", "intense", "fast", "adrenaline")):
            return cls.ACTION
        # Default to event type filter (e.g. "only curves")
        return cls.EVENT_TYPE_FILTER


# ---------------------------------------------------------------------------
# Filter predicates
# ---------------------------------------------------------------------------

def _by_score(events: list[TimelineEvent], min_score: float = 7.0) -> list[TimelineEvent]:
    """Keep only events above *min_score*."""
    return [e for e in events if e.score >= min_score]


def _by_event_type(events: list[TimelineEvent], et: EventType) -> list[TimelineEvent]:
    """Keep only events matching *et*."""
    return [e for e in events if e.matches_event_type(et)]


def _by_duration(events: list[TimelineEvent], target_minutes: float) -> list[TimelineEvent]:
    """Trim or extend the event list to roughly *target_minutes*.

    Events are sorted by score descending until the total duration
    approaches the target.
    """
    target_seconds = target_minutes * 60
    sorted_events = sorted(events, key=lambda e: e.score, reverse=True)

    selected: list[TimelineEvent] = []
    total = 0.0

    for evt in sorted_events:
        if total >= target_seconds:
            break
        selected.append(evt)
        total += evt.duration

    # Re-sort by start_time so the export engine sees chronological order
    return sorted(selected, key=lambda e: e.start_time)


def _by_cinematic(events: list[TimelineEvent]) -> list[TimelineEvent]:
    """Select events with high visual beauty and good lighting."""
    cinematic = []
    for e in events:
        rq = e.quality_scores
        if rq.visual_beauty >= 7.0 and rq.lighting >= 6.0:
            cinematic.append(e)
        elif any(t in e.tags for t in ("sunset", "sunrise", "scenic_road", "mountain")):
            cinematic.append(e)
    return sorted(cinematic, key=lambda e: e.start_time)


def _by_action(events: list[TimelineEvent]) -> list[TimelineEvent]:
    """Select events with high action_level."""
    selected = [e for e in events if e.quality_scores.action_level >= 6.0]
    return sorted(selected, key=lambda e: e.start_time)


# ---------------------------------------------------------------------------
# Keyword extraction helpers
# ---------------------------------------------------------------------------

def _extract_event_types(text: str) -> list[EventType]:
    """Pull EventType values from free text."""
    found: list[EventType] = []
    words = set(re.sub(r'[^\w\s]', '', text.lower()).split())
    for et in EventType:
        # Match "curve", "curves", "mountain", etc.
        stem = et.value.rstrip("s")
        if stem in words or et.value in words:
            found.append(et)
    return found


def _extract_duration(text: str) -> float | None:
    """Pull a duration (in minutes) from text like '3 minute', '45 seconds'."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(minute|min|hour|hr|h|seconds?|sec|s)\b", text.lower())
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2)
    if unit in ("hour", "hr", "h"):
        return value * 60
    if unit in ("seconds", "second", "sec", "s"):
        return value / 60
    return value


def _extract_top_n(text: str) -> int | None:
    """Pull a number from 'top 10 clips', 'best 5 moments', etc."""
    m = re.search(r"(?:top|best)\s*(\d+)", text.lower())
    if m:
        return int(m.group(1))
    return None


# ---------------------------------------------------------------------------
# PromptService
# ---------------------------------------------------------------------------

class PromptService:
    """Translate natural-language prompts into filtered TimelineEvents.

    This service never calls the AI.  It works entirely with pre-analyzed
    data stored in the Timeline.

    Example usage:
        svc = PromptService()
        events = svc.apply(timeline, "Create a 3 minute highlight")
        events = svc.apply(timeline, "Only curves and hairpins")
        events = svc.apply(timeline, "Cinematic sunset edit")
    """

    def apply(
        self,
        timeline: Timeline,
        prompt: str,
    ) -> list[TimelineEvent]:
        """Apply a natural-language prompt to an existing Timeline.

        Args:
            timeline: The analyzed timeline (must contain events).
            prompt: User's edit intent in plain text.

        Returns:
            Filtered list of TimelineEvents matching the prompt.
        """
        if not timeline.events:
            logger.warning("Timeline has no events – nothing to filter")
            return []

        events = timeline.events

        # -- 1. Duration-based filter (highest priority) --
        duration = _extract_duration(prompt)
        if duration is not None:
            min_score = self._infer_min_score(prompt)
            filtered = _by_score(events, min_score)
            return _by_duration(filtered, duration)

        # -- 2. Top-N filter --
        top_n = _extract_top_n(prompt)
        if top_n is not None:
            sorted_events = sorted(events, key=lambda e: e.score, reverse=True)
            return sorted_events[:top_n]

        # -- 3. Cinematic intent --
        if self._has_intent(events, prompt, Intent.CINEMATIC):
            return _by_cinematic(events)

        # -- 4. Action intent --
        if self._has_intent(events, prompt, Intent.ACTION):
            return _by_action(events)

        # -- 5. Event type filter --
        event_types = _extract_event_types(prompt)
        if event_types:
            for et in event_types:
                events = _by_event_type(events, et)
            return sorted(events, key=lambda e: e.start_time)

        # -- 6. Fallback: best highlights --
        return _by_score(events, min_score=7.0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _has_intent(
        events: list[TimelineEvent],
        prompt: str,
        intent: Intent,
    ) -> bool:
        """Check whether the prompt expresses *intent*."""
        words = set(re.sub(r'[^\w\s]', '', prompt.lower()).split())
        match intent:
            case Intent.CINEMATIC:
                return bool(
                    {"cinematic", "beautiful", "scenic", "sunset", "artistic"} & words
                )
            case Intent.ACTION:
                return bool(
                    {"action", "intense", "fast", "adrenaline", "rider", "wheelie"} & words
                )
        return False

    @staticmethod
    def _infer_min_score(prompt: str) -> float:
        """Infer a minimum score threshold from prompt quality words."""
        words = set(re.sub(r'[^\w\s]', '', prompt.lower()).split())
        if any(w in words for w in ("epic", "best", "amazing", "incredible")):
            return 8.5
        if any(w in words for w in ("great", "good", "nice")):
            return 7.0
        return 6.0