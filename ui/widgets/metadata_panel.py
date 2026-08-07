from PySide6.QtWidgets import QFrame, QLabel, QFormLayout

from models.video_info import VideoInfo


class MetadataPanel(QFrame):
    """
    Widget responsável por mostrar os metadados do vídeo.
    """

    def __init__(self):
        super().__init__()

        self.setObjectName("card")

        self.duration = QLabel("-")
        self.resolution = QLabel("-")
        self.fps = QLabel("-")
        self.frames = QLabel("-")
        self.size = QLabel("-")

        layout = QFormLayout(self)

        layout.addRow("Duração:", self.duration)
        layout.addRow("Resolução:", self.resolution)
        layout.addRow("FPS:", self.fps)
        layout.addRow("Frames:", self.frames)
        layout.addRow("Tamanho:", self.size)

    def update(self, video: VideoInfo):

        self.duration.setText(video.duration_text)
        self.resolution.setText(video.resolution)
        self.fps.setText(f"{video.fps:.2f}")
        self.frames.setText(str(video.frames))
        self.size.setText(video.size_text)