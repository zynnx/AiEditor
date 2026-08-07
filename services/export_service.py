"""Export service – receives TimelineEvents and builds FFmpeg commands."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Codec enums
# ---------------------------------------------------------------------------

class VideoCodec(Enum):
    H264 = "libx264"
    H265 = "libx265"
    NV_H264 = "h264_nvenc"
    NV_H265 = "hevc_nvenc"


class AudioCodec(Enum):
    AAC = "aac"
    COPY = "copy"
    NONE = None

# ---------------------------------------------------------------------------
# Export settings (used by controller)
# ---------------------------------------------------------------------------

ExportSettings = Dict[str, Any]
"""Convenience alias – the controller passes a dict-like settings object.

Keys:
    output_path      – Path to the output file
    video_codec      – codec string ("h264", "h265", ...)
    use_nvenc        – bool (prefer NVENC when available)
    quality_crf      – int CRF/CQ value
    preset           – FFmpeg preset string ("medium", "fast", …)
"""

# ---------------------------------------------------------------------------
# Preset dataclass (internal)
# ---------------------------------------------------------------------------

@dataclass
class ExportPreset:
    name: str
    video_codec: VideoCodec
    audio_codec: AudioCodec = AudioCodec.AAC
    resolution: Optional[str] = None
    crf: int = 23
    fps: Optional[str] = None
    extra_args: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Export job (internal)
# ---------------------------------------------------------------------------

@dataclass
class ExportJob:
    source_path: str
    output_path: str
    segments: List[tuple]
    preset: ExportPreset
    ffmpeg_path: str = "ffmpeg"

    @property
    def output_dir(self) -> Path:
        return Path(self.output_path).parent


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ExportService:
    """Build FFmpeg commands from TimelineEvents.

    This service **never** decides what to export.
    It receives TimelineEvents and builds the FFmpeg graph.
    """

    DEFAULT_PRESETS: Dict[str, ExportPreset] = {}

    # ------------------------------------------------------------------
    def __init__(self) -> None:
        self._register_defaults()

    # ------------------------------------------------------------------
    def _register_defaults(self) -> None:
        self.DEFAULT_PRESETS: Dict[str, ExportPreset] = {
            "h264": ExportPreset(
                name="H264",
                video_codec=VideoCodec.H264,
                audio_codec=AudioCodec.AAC,
                crf=23,
            ),
            "nvenc_h264": ExportPreset(
                name="NVENC H264",
                video_codec=VideoCodec.NV_H264,
                audio_codec=AudioCodec.AAC,
                crf=23,
            ),
            "h265": ExportPreset(
                name="H265",
                video_codec=VideoCodec.H265,
                audio_codec=AudioCodec.AAC,
                crf=28,
            ),
            "nvenc_h265": ExportPreset(
                name="NVENC H265",
                video_codec=VideoCodec.NV_H265,
                audio_codec=AudioCodec.AAC,
                crf=28,
            ),
        }

    # ------------------------------------------------------------------
    def get_preset(self, name: str) -> Optional[ExportPreset]:
        """Return a preset by key."""
        return self.DEFAULT_PRESETS.get(name)

    # ------------------------------------------------------------------
    def _resolve_codec(
        self, codec_key: str, use_nvenc: bool
    ) -> VideoCodec:
        """Map a codec string to a VideoCodec enum value."""
        if use_nvenc:
            return VideoCodec.NV_H264 if "h264" in codec_key else VideoCodec.NV_H265

        if "h265" in codec_key or "hevc" in codec_key:
            return VideoCodec.H265
        return VideoCodec.H264

    # ------------------------------------------------------------------
    def _build_filter_complex(self, job: ExportJob) -> str:
        """Build FFmpeg filter_complex string for concatenating segments."""
        n = len(job.segments)
        if n == 0:
            raise ValueError("No segments to export")

        parts: list[str] = []
        for i, (start, end) in enumerate(job.segments):
            dur = end - start
            parts.append(
                f"[0:v]trim=start={start}:duration={dur},"
                f"setpts=PTS-STARTPTS[v{i}]"
            )

        concat_inputs = "".join(f"[v{i}]" for i in range(n))
        parts.append(f"{concat_inputs}concat=n={n}:v=1:a=0[outv]")
        sep = ";"
        return sep.join(parts) if n > 1 else parts[0].replace("[v0]", "[outv]")

    # ------------------------------------------------------------------
    def _build_command(self, job: ExportJob) -> list[str]:
        """Construct the full FFmpeg command list."""
        cmd = [job.ffmpeg_path, "-i", job.source_path]

        codec = job.preset.video_codec.value
        cmd.extend(["-c:v", codec])

        if codec.startswith("lib") and job.preset.crf:
            cmd.extend(["-crf", str(job.preset.crf)])
        elif "nvenc" in codec:
            cmd.extend(["-cq", str(job.preset.crf)])

        ac = job.preset.audio_codec
        if ac == AudioCodec.AAC:
            cmd.extend(["-c:a", "aac"])
        elif ac == AudioCodec.COPY:
            cmd.extend(["-c:a", "copy"])
        elif ac == AudioCodec.NONE:
            cmd.append("-an")

        if job.preset.resolution:
            cmd.extend(["-vf", f"scale={job.preset.resolution}:-1"])
        elif len(job.segments) > 1:
            cmd.extend(["-filter_complex", self._build_filter_complex(job)])
        elif len(job.segments) == 1:
            s, e = job.segments[0]
            cmd.extend(["-ss", str(s), "-to", str(e)])

        cmd.extend(["-y", job.output_path])
        return cmd

    # ------------------------------------------------------------------
    def export(
        self,
        source_video: str | Path,
        timeline: Any,
        settings: ExportSettings,
    ) -> Path:
        """Export the current timeline to a video file.

        Args:
            source_video: Path to the original source video.
            timeline: A Timeline containing events to export.
            settings: Dict with keys output_path, video_codec, use_nvenc,
                      quality_crf, preset.

        Returns:
            Path to the exported file.
        """
        from models.timeline import Timeline  # local import to avoid cycle

        output_path = Path(settings.get("output_path", "output/exports/out.mp4"))
        codec_key = str(settings.get("video_codec", "h264"))
        use_nvenc = bool(settings.get("use_nvenc", True))
        crf = int(settings.get("quality_crf", 23))

        # Resolve codec
        video_codec = self._resolve_codec(codec_key, use_nvenc)

        # Build segment list from timeline events
        segments: List[tuple] = []
        if isinstance(timeline, Timeline):
            for evt in timeline.events:
                segments.append((evt.start_time, evt.end_time))

        if not segments:
            raise ValueError("Timeline has no events to export")

        # Build preset
        preset = ExportPreset(
            name=f"{codec_key} export",
            video_codec=video_codec,
            audio_codec=AudioCodec.AAC,
            crf=crf,
        )

        # Create job and run
        job = ExportJob(
            source_path=str(source_video),
            output_path=str(output_path),
            segments=segments,
            preset=preset,
        )

        success = self._run_export(job)
        if not success:
            raise RuntimeError(f"Export failed for {output_path}")

        return output_path

    # ------------------------------------------------------------------
    def _run_export(self, job: ExportJob) -> bool:
        """Execute FFmpeg subprocess."""
        job.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"[ExportService] Starting export to {job.output_path}")

        try:
            cmd = self._build_command(job)
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"[ExportService] FFmpeg error: {result.stderr}")
                return False
            print(f"[ExportService] Export complete: {job.output_path}")
            return True
        except FileNotFoundError:
            print("[ExportService] ffmpeg not found in PATH")
            return False


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    pass