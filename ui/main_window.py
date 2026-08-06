from PySide6.QtCore import Qt
from core.video import Video
from core.thumbnail import ThumbnailGenerator
import cv2


from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QWidget):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("🏍 Motorcycle AI Editor")

        self.resize(1000,700)

        self.videoLabel = QLabel("Nenhum vídeo selecionado")

        self.videoLabel.setAlignment(Qt.AlignCenter)

        self.selectButton = QPushButton("Escolher vídeo")

        self.selectButton.clicked.connect(self.selectVideo)

        self.preview = QLabel()

        self.preview.setFixedHeight(300)

        self.preview.setAlignment(Qt.AlignCenter)

        self.preview.setText("Sem preview")

        self.preview.setMinimumHeight(250)

        self.info = QLabel(
            "Duração:\n"
            "Resolução:\n"
            "FPS:\n"
            "Codec:\n"
            "Tamanho:"
        )

        layout = QVBoxLayout()

        layout.addWidget(QLabel("<h2>Vídeo</h2>"))

        layout.addWidget(self.videoLabel)

        layout.addWidget(self.selectButton)

        layout.addWidget(QLabel("<h2>Preview</h2>"))

        layout.addWidget(self.preview)

        layout.addWidget(QLabel("<h2>Informações</h2>"))

        layout.addWidget(self.info)

        self.setLayout(layout)

    def selectVideo(self):

        frame = ThumbnailGenerator.get_frame(filename)

        if frame is not None:

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            h, w, ch = frame.shape

            image = QImage(
                frame.data,
                w,
                h,
                ch * w,
                QImage.Format_RGB888,
            )

            pixmap = QPixmap.fromImage(image)

            self.preview.setPixmap(
            pixmap.scaled(
                500,
                300,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
                )
            )

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Escolher vídeo",
            "",
            "Vídeos (*.mp4 *.mov *.mkv)"
        )

        if filename:

            self.videoLabel.setText(filename)

            video = Video(filename)

            self.info.setText(
            f"""
            Duração: {video.duration_text}

            Resolução: {video.resolution}

            FPS: {video.fps:.2f}

            Frames: {video.frames}

            Tamanho: {video.size_text}
            """)