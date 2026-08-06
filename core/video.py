from pathlib import Path

import cv2


class Video:

    def __init__(self, filename: str):

        self.filename = filename

        self.capture = cv2.VideoCapture(filename)

        if not self.capture.isOpened():
            raise Exception("Unable to open video.")

        self.width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

        self.fps = self.capture.get(cv2.CAP_PROP_FPS)

        self.frames = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))

        self.duration = self.frames / self.fps if self.fps else 0

        self.size = Path(filename).stat().st_size

    @property
    def resolution(self):

        return f"{self.width} x {self.height}"

    @property
    def duration_text(self):

        minutes = int(self.duration // 60)
        seconds = int(self.duration % 60)

        return f"{minutes}m {seconds}s"

    @property
    def size_text(self):

        gb = self.size / 1024 / 1024 / 1024

        if gb >= 1:
            return f"{gb:.2f} GB"

        mb = self.size / 1024 / 1024

        return f"{mb:.2f} MB"