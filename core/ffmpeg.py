"""FFmpeg/FFprobe interface – the ONLY place that spawns external processes."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_executable(name: str) -> str | None:
    """Return the full path to *name* on PATH, or ``None``."""
    return shutil.which(name)


FFMPEG_BIN: str | None = _find_executable("ffmpeg")
FFPROBE_BIN: str | None = _find_executable("ffprobe")


def _require_tool(which: str) -> str:
    path = _find_executable(which)
    if path is None:
        raise RuntimeError(
            f"'{which}' executable not found on PATH. "
            f"Install FFmpeg and ensure it is in your system PATH."
        )
    return path


def _run(cmd: list[str], *, capture_stderr: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a command, raising on non-zero exit."""
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE if capture_stderr else None,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{' '.join(cmd)} failed (exit {result.returncode}):\n{result.stderr}"
        )
    return result


# ---------------------------------------------------------------------------
# Probe – metadata extraction
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class ProbeResult:
    """Raw probe information from ffprobe."""

    width: int
    height: int
    fps: float
    frame_count: int
    duration: float
    video_codec: str
    audio_codec: str
    bit_rate: int
    size: int


def probe(video_path: Path) -> ProbeResult:
    """Use **ffprobe** to extract video metadata."""
    if not video_path.is_file():
        raise FileNotFoundError(f"No such file: {video_path}")

    ffprobe = _require_tool("ffprobe")

    # JSON stream output
    cmd = [
        ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]
    result = _run(cmd)
    data = json.loads(result.stdout)

    # Find video stream
    video_stream = None
    audio_stream = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and video_stream is None:
            video_stream = stream
        elif stream.get("codec_type") == "audio" and audio_stream is None:
            audio_stream = stream

    if video_stream is None:
        raise ValueError(f"No video stream found in {video_path}")

    # Parse fps as a fraction (e.g. "24000/1001")
    fps_str = video_stream.get("r_frame_rate", "30/1")
    if "/" in fps_str:
        num, den = fps_str.split("/")
        fps = float(num) / float(den) if float(den) else 30.0
    else:
        fps = float(fps_str)

    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))

    # Duration: prefer format-level, fallback to stream
    fmt = data.get("format", {})
    duration_str = fmt.get("duration")
    if duration_str:
        duration = float(duration_str)
    else:
        duration = 0.0

    frame_count = int(fps * duration) if fps and duration else 0

    bit_rate = int(fmt.get("bit_rate", 0))
    size = int(fmt.get("size", video_path.stat().st_size))

    return ProbeResult(
        width=width,
        height=height,
        fps=fps,
        frame_count=frame_count,
        duration=duration,
        video_codec=video_stream.get("codec_name", "unknown"),
        audio_codec=audio_stream.get("codec_name", "none") if audio_stream else "none",
        bit_rate=bit_rate,
        size=size,
    )


# ---------------------------------------------------------------------------
# Frame extraction
# ---------------------------------------------------------------------------

def extract_frame_at(
    video_path: Path,
    timestamp: float,
    output_path: Path,
) -> Path:
    """Extract a single frame at *timestamp* (seconds) as a PNG."""
    ffmpeg = _require_tool("ffmpeg")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg,
        "-ss", str(timestamp),
        "-i", str(video_path),
        "-frames:v", "1",
        "-y",
        str(output_path),
    ]
    _run(cmd)
    return output_path


def extract_frames_by_rate(
    video_path: Path,
    rate_fps: float,
    output_pattern: Path,
) -> list[Path]:
    """Extract frames at *rate_fps* (e.g. 1, 2, 5) matching *output_pattern*.

    *output_pattern* must contain a ``%04d`` placeholder for the frame index,
    e.g. ``Path("frames/%04d.png")``.
    """
    output_pattern.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = _require_tool("ffmpeg")
    cmd = [
        ffmpeg,
        "-i", str(video_path),
        "-vf", f"fps={rate_fps}",
        "-y",
        str(output_pattern),
    ]
    _run(cmd)

    # Collect generated frames
    ext = output_pattern.suffix or ".png"
    stem = output_pattern.stem.replace("%04d", "")
    directory = output_pattern.parent

    frames: list[Path] = sorted(
        directory.glob(f"{stem}*{ext}"),
        key=lambda p: p.name,
    )
    return frames


# ---------------------------------------------------------------------------
# Export / concat segments
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class ExportSegment:
    """One segment to include in the export."""

    start: float
    duration: float


def concat_segments(
    source: Path,
    segments: list[ExportSegment],
    output: Path,
    *,
    codec: str = "h264_nvenc",
    crf: int | None = None,
    preset: str | None = None,
    audio: bool = True,
) -> Path:
    """Concatenate *segments* from *source* into a single output file.

    Uses FFmpeg's complex filter to cut and join segments efficiently.
    """
    if not segments:
        raise ValueError("At least one segment is required for export.")

    ffmpeg = _require_tool("ffmpeg")
    output.parent.mkdir(parents=True, exist_ok=True)

    # Build filter_complex
    filter_parts: list[str] = []
    stream_tags: list[str] = []

    for idx, seg in enumerate(segments):
        label = f"[v{idx}]"
        filter_parts.append(
            f"[0:v]trim=start={seg.start}:duration={seg.duration}"
            f",setpts=PTS-STARTPTS,{label}"
        )
        stream_tags.append(label)

    # Concat all trimmed segments
    concat_input = "".join(stream_tags)
    filter_parts.append(
        f"{concat_input}concat=n={len(segments)}:v=1:a=0[outv]"
    )

    filter_complex = ";".join(filter_parts)

    cmd = [
        ffmpeg,
        "-y",
        "-i", str(source),
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-c:v", codec,
    ]

    if crf is not None:
        cmd.extend(["-crf", str(crf)])
    if preset is not None:
        cmd.extend(["-preset", preset])

    if audio:
        # For audio we also need to concat audio segments
        audio_filter_parts: list[str] = []
        audio_tags: list[str] = []
        for idx, seg in enumerate(segments):
            label = f"[a{idx}]"
            audio_filter_parts.append(
                f"[0:a]atrim=start={seg.start}:duration={seg.duration}"
                f",asetpts=PTS-STARTPTS,{label}"
            )
            audio_tags.append(label)

        audio_concat_input = "".join(audio_tags)
        audio_filter_parts.append(
            f"{audio_concat_input}concat=n={len(segments)}:v=0:a=1[outa]"
        )

        # Rebuild filter_complex with both video and audio
        filter_parts_full = filter_parts[:-1] + audio_filter_parts + [
            f"{filter_parts[-1].replace('[outv]', '')};[outa]anullsink[outa]".split(";")[0]
            if False else ""
        ]
        # Simpler: rebuild everything together
        all_filters: list[str] = []
        for idx, seg in enumerate(segments):
            all_filters.append(
                f"[0:v]trim=start={seg.start}:duration={seg.duration}"
                f",setpts=PTS-STARTPTS,[v{idx}]"
            )
            all_filters.append(
                f"[0:a]atrim=start={seg.start}:duration={seg.duration}"
                f",asetpts=PTS-STARTPTS,[a{idx}]"
            )

        v_concat = "".join(f"[v{i}]" for i in range(len(segments)))
        a_concat = "".join(f"[a{i}]" for i in range(len(segments)))
        all_filters.append(f"{v_concat}{a_concat}concat=n={len(segments)}:v=1:a=1[outv][outa]")

        filter_complex = ";".join(all_filters)

        cmd = [
            ffmpeg,
            "-y",
            "-i", str(source),
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "[outa]",
            "-c:v", codec,
            "-c:a", "aac",
        ]

        if crf is not None:
            cmd.extend(["-crf", str(crf)])
        if preset is not None:
            cmd.extend(["-preset", preset])

    cmd.append(str(output))

    _run(cmd)
    return output


def get_nvidia_codecs() -> dict[str, str]:
    """Return available NVENC codec names."""
    return {
        "h264_nvenc": "H.264 (NVIDIA NVENC)",
        "hevc_nvenc": "H.265/HEVC (NVIDIA NVENC)",
    }