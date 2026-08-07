from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class VideoInfo:
    path: Path
    filename: str

    width: int
    height: int

    fps: float
    frames: int
    duration: float

    codec: str
    size: int

    @property
    def resolution(self) -> str:
        return f"{self.width} x {self.height}"

    @property
    def duration_text(self) -> str:
        total_seconds = int(self.duration)

        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours:
            return f"{hours}h {minutes:02}m {seconds:02}s"

        return f"{minutes}m {seconds:02}s"

    @property
    def size_text(self) -> str:
        gb = self.size / (1024 ** 3)

        if gb >= 1:
            return f"{gb:.2f} GB"

        mb = self.size / (1024 ** 2)

        return f"{mb:.2f} MB"