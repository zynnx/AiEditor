"""AI vision analysis service – runs locally via Ollama.

This service is the only component that communicates with the vision AI.
It sends scene frames (never the whole video) in batches and receives
structured JSON back.

Key design decisions:
- The prompt asks for **per-scene** analysis, not per-frame.
- The AI returns TimelineEvent-ready data plus road quality scores.
- Results are converted to domain models before leaving this service.

Pipeline position:
    Scene Detection → AIService → AnalysisResult
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from core.ollama_client import generate_vision, parse_json_from_response, is_ollama_running
from models.analysis import AnalysisResult, FrameAnalysis, RoadQualityScores
from models.event import TimelineEvent, EventType
from models.scene import Scene
from models.video_info import VideoInfo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt – motorcycle-focused, scene-aware
# ---------------------------------------------------------------------------

MOTORCYCLE_VISION_PROMPT = """\
You are a professional motorcycle riding highlight detector. You will receive
a batch of frames that belong to the same scene (contiguous time segment).

For each frame, analyze and return ONLY valid JSON with this structure:

[
  {
    "timestamp": 42,
    "score": 9.2,
    "reason": "Beautiful mountain hairpin curve",
    "tags": ["curve", "mountain", "forest"],
    "event_type": "curve",
    "road_quality": {
      "visual_beauty": 9.0,
      "road_quality": 8.5,
      "traffic_density": 9.5,
      "camera_stability": 7.0,
      "lighting": 8.0,
      "action_level": 9.0
    }
  }
]

Tag and event_type must come from this allowed set:
  [motorcycle, curve, hairpin, bridge, tunnel, forest, mountain, sea,
   village, city, highway, traffic, overtake, wheelie, danger,
   good_scenery, cinematic, rider_action, sunset, sunrise, rain, night]

Scoring guidelines:
  - Beautiful mountain roads, curves, hairpins: 7-10
  - Overtakes, wheelies, rider actions: 8-10
  - Sunset/sunrise scenic views: 7-9
  - Dangerous moments: 5-7 with "danger" tag
  - Boring straight highways: 1-3
  - City traffic (unless cinematic): 1-4

Rules:
  - Return ONLY a JSON array. No markdown, no prose.
  - Every frame must appear in the output.
  - timestamps should match the input order.
""".lstrip()


# ---------------------------------------------------------------------------
# AIService
# ---------------------------------------------------------------------------

class AIService:
    """Analyze video frames using a local vision model via Ollama."""

    def __init__(self, model: str | None = None, batch_size: int = 8) -> None:
        """
        Args:
            model: Ollama model name override (e.g. "qwen2.5-vl").
            batch_size: How many frames to send per API call.
        """
        self._model = model
        self._batch_size = batch_size

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_frames(
        self,
        frames: list[Path],
        *,
        custom_prompt: str | None = None,
    ) -> list[FrameAnalysis]:
        """Analyze a list of extracted frames in batches.

        Args:
            frames: Ordered list of frame image paths.
            custom_prompt: Optional user-defined prompt override.

        Returns:
            List of structured frame analyses.
        """
        if not is_ollama_running():
            raise RuntimeError(
                "Ollama server is not reachable. "
                "Make sure Ollama is running at http://localhost:11434"
            )

        prompt = custom_prompt or MOTORCYCLE_VISION_PROMPT
        results: list[FrameAnalysis] = []

        for batch in _chunk(frames, self._batch_size):
            text = generate_vision(prompt, batch, model=self._model)
            parsed = parse_json_from_response(text)
            for item in parsed:
                results.append(FrameAnalysis(**item))

        return results

    def analyze_scenes(
        self,
        scenes: list[Scene],
        *,
        custom_prompt: str | None = None,
    ) -> AnalysisResult:
        """Analyze scene-by-scene and produce a full AnalysisResult.

        This is the preferred entry point when scene detection has already
        been performed.  Each scene's frames are sent as a batch.

        Args:
            scenes: Detected scene segments with frame paths.
            custom_prompt: Optional prompt override.

        Returns:
            Complete analysis with frame scores, events, and road quality.
        """
        if not is_ollama_running():
            raise RuntimeError(
                "Ollama server is not reachable. "
                "Make sure Ollama is running at http://localhost:11434"
            )

        prompt = custom_prompt or MOTORCYCLE_VISION_PROMPT
        all_frame_analyses: list[FrameAnalysis] = []
        all_events: list[TimelineEvent] = []
        all_road_scores: list[RoadQualityScores] = []

        for scene in scenes:
            # Send up to batch_size frames from this scene
            scene_frames = _chunk(scene.frame_paths, self._batch_size)

            for batch in scene_frames:
                text = generate_vision(prompt, batch, model=self._model)
                parsed = parse_json_from_response(text)

                for item in parsed:
                    ts = float(item.get("timestamp", 0))
                    score = float(item.get("score", 0))
                    reason = item.get("reason", "")
                    tags = item.get("tags", [])

                    fa = FrameAnalysis(
                        timestamp=ts,
                        score=score,
                        reason=reason,
                        tags=tags,
                    )
                    all_frame_analyses.append(fa)

                    # Promote to TimelineEvent if score >= 5.0
                    if score >= 5.0:
                        event_type = self._parse_event_type(item.get("event_type"))
                        rq_data = item.get("road_quality", {})

                        evt = TimelineEvent(
                            start_time=ts,
                            end_time=min(ts + 5.0, ts + (scene.end_time - scene.start_time)),
                            score=score,
                            description=reason,
                            reason=reason,
                            tags=tags,
                            event_type=event_type,
                            quality_scores=RoadQualityScores(**rq_data) if rq_data else RoadQualityScores(),
                            scene_id=scene.scene_id,
                        )
                        all_events.append(evt)

            # Aggregate road quality for the whole scene
            scene_scores = self._aggregate_road_quality(parsed)
            all_road_scores.append(scene_scores)

        # Build final result
        best_moments = [f for f in all_frame_analyses if f.score >= 7.0]
        avg_score = 0.0
        if all_frame_analyses:
            avg_score = sum(f.score for f in all_frame_analyses) / len(all_frame_analyses)

        return AnalysisResult(
            overall_score=round(avg_score, 2),
            frame_analyses=all_frame_analyses,
            best_moments=best_moments,
            scenes=scenes,
            events=all_events,
            road_scores=all_road_scores,
        )

    def analyze_video(
        self,
        video: VideoInfo,
        frames: list[Path],
        *,
        user_prompt: str | None = None,
    ) -> AnalysisResult:
        """High-level convenience: analyze all frames and wrap in AnalysisResult.

        Legacy method for backward compatibility when scene detection is
        not used.
        """
        frame_analyses = self.analyze_frames(frames, custom_prompt=user_prompt)

        avg_score = 0.0
        if frame_analyses:
            avg_score = sum(f.score for f in frame_analyses) / len(frame_analyses)

        best_moments = [f for f in frame_analyses if f.score >= 7.0]

        return AnalysisResult(
            overall_score=round(avg_score, 2),
            frame_analyses=frame_analyses,
            best_moments=best_moments,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_event_type(raw: str | None) -> EventType:
        """Map a string from the AI to an EventType enum."""
        if not raw:
            return EventType.GENERIC
        try:
            return EventType(raw.lower())
        except (ValueError, AttributeError):
            return EventType.GENERIC

    @staticmethod
    def _aggregate_road_quality(parsed_items: list[dict]) -> RoadQualityScores:
        """Average road_quality dicts across all items in a batch."""
        if not parsed_items:
            return RoadQualityScores()

        totals = {
            "visual_beauty": 0.0,
            "road_quality": 0.0,
            "traffic_density": 0.0,
            "camera_stability": 0.0,
            "lighting": 0.0,
            "action_level": 0.0,
        }
        count = 0

        for item in parsed_items:
            rq = item.get("road_quality")
            if not rq:
                continue
            for key in totals:
                totals[key] += float(rq.get(key, 5.0))
            count += 1

        if count == 0:
            return RoadQualityScores()

        return RoadQualityScores(
            **{k: round(v / count, 1) for k, v in totals.items()}
        )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _chunk(iterable: list[Any], size: int) -> list[list[Any]]:
    """Split *iterable* into chunks of length *size*."""
    return [iterable[i : i + size] for i in range(0, len(iterable), size)]