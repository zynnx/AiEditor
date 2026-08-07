$content = @'
"""Export service - receives TimelineEvents and builds FFmpeg cuts."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional


class VideoCodec(Enum):
    H264 = "libx264"
    H265 = "libx265"
    NV_H264 = "h264_nvenc"
    NV_H265 = "hevc_nvenc"


class AudioCodec(Enum):
    AAC = "aac"
    COPY = "copy"
    NONE = None


@dataclass
class ExportPreset:
    name: str
    video_codec: VideoCodec
    audio_codec: AudioCodec
    resolution: Optional[str] = None
    crf: int = 23
    fps: Optional[str] = None
    extra_args: List[str] = field(default_factory=list)


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


class ExportService:
    """Build FFmpeg commands from TimelineEvents."""

    DEFAULT_PRESETS: dict[str, ExportPreset] = {}

    def __init__(self) -> None:
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.DEFAULT_PRESETS = {
            "h264": ExportPreset(
                name="H264", video_codec=VideoCodec.H264,
                audio_codec=AudioCodec.AAC, crf=23),
            "nvenc_h264": ExportPreset(
                name="NVENC H264", video_codec=VideoCodec.NV_H264,
                audio_codec=AudioCodec.AAC, crf=23),
            "h265": ExportPreset(
                name="H265", video_codec=VideoCodec.H265,
                audio_codec=AudioCodec.AAC, crf=28),
            "nvenc_h265": ExportPreset(
                name="NVENC H265", video_codec=VideoCodec.NV_H265,
                audio_codec=AudioCodec.AAC, crf=28),
        }

    def get_preset(self, name: str) -> Optional[ExportPreset]:
        return self.DEFAULT_PRESETS.get(name)

    def _build_filter_complex(self, job: ExportJob) -> str:
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

    def _build_command(self, job: ExportJob) -> list[str]:
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

    def export(self, job: ExportJob) -> bool:
        """Execute FFmpeg and return success status."""
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


if __name__ == "__main__":
    pass
'@

$OutFile = "services/export_service.py"
$content | Out-File -FilePath $OutFile -Encoding UTF8 -NoNewline
Write-Host "Generated $OutFile with $($content.Split("`n").Count) lines"