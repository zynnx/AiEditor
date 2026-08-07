from pathlib import Path

import cv2

from models.video_info import VideoInfo


class VideoService:

    @staticmethod
    def load(filename: str) -> VideoInfo:

        path = Path(filename)

        if not path.exists():
            raise FileNotFoundError(
                f"Vídeo não encontrado: {filename}"
            )

        capture = cv2.VideoCapture(str(path))

        if not capture.isOpened():
            raise ValueError(
                f"Não foi possível abrir o vídeo: {filename}"
            )

        try:
            width = int(
                capture.get(cv2.CAP_PROP_FRAME_WIDTH)
            )

            height = int(
                capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
            )

            fps = float(
                capture.get(cv2.CAP_PROP_FPS)
            )

            frames = int(
                capture.get(cv2.CAP_PROP_FRAME_COUNT)
            )

            duration = frames / fps if fps > 0 else 0

            fourcc = int(
                capture.get(cv2.CAP_PROP_FOURCC)
            )

            codec = "".join(
                chr((fourcc >> 8 * i) & 0xFF)
                for i in range(4)
            ).strip()

        finally:
            capture.release()

        return VideoInfo(
            path=path,
            filename=path.name,
            width=width,
            height=height,
            fps=fps,
            frames=frames,
            duration=duration,
            codec=codec,
            size=path.stat().st_size,
        )