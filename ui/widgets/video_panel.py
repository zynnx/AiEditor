from pathlib import Path

from PySide6.QtCore import Signal

from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class VideoPanel(QFrame):

    videoSelected = Signal(str)

    def __init__(self):

        super().__init__()

        self.setObjectName("card")

        self.pathLabel = QLabel("Nenhum vídeo selecionado")

        self.button = QPushButton("Escolher vídeo")

        self.button.clicked.connect(self.open)

        layout = QVBoxLayout(self)

        layout.addWidget(self.pathLabel)

        layout.addWidget(self.button)

    def open(self):

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Escolher vídeo",
            "",
            "Videos (*.mp4 *.mov *.mkv)"
        )

        if not filename:
            return

        self.pathLabel.setText(Path(filename).name)

        self.videoSelected.emit(filename)