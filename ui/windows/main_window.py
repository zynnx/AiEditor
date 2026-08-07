"""Main Window – professional UI for Motorcycle AI Editor.

Rules enforced:
    • NEVER imports OpenCV (cv2).
    • NEVER imports FFmpeg directly.
    • NEVER calls Ollama directly.
    • All business logic goes through MainController.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controllers.main_controller import MainController


# ---------------------------------------------------------------------------
# Background worker thread for long-running operations
# ---------------------------------------------------------------------------

class _WorkerThread(QThread):
    """Runs a callable in a background thread and signals completion."""

    finished = Signal(object, Exception)  # result, error

    def __init__(self, target: callable) -> None:
        super().__init__()
        self._target = target

    def run(self) -> None:  # noqa: N802 – Qt override
        try:
            result = self._target()
            self.finished.emit(result, None)
        except Exception as exc:
            self.finished.emit(None, exc)


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class MainWindow(QWidget):
    """Primary window of the Motorcycle AI Editor application."""

    def __init__(self, controller: MainController) -> None:
        super().__init__()

        self._controller = controller

        # -- Window basics --------------------------------------------------
        self.setWindowTitle("🏍️  Motorcycle AI Editor")
        self.resize(1100, 750)

        # -- Widgets --------------------------------------------------------
        self._video_name_label = QLabel("Nenhum vídeo selecionado")
        self._video_name_label.setAlignment(Qt.AlignCenter)
        self._video_name_label.setStyleSheet("font-size: 14px; padding: 8px;")

        self._info_label = QLabel()
        self._info_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._info_label.setStyleSheet("padding: 8px; font-family: monospace;")

        self._preview_label = QLabel()
        self._preview_label.setFixedHeight(320)
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setText("Sem preview")
        self._preview_label.setStyleSheet(
            "border: 1px solid #555; background: #1e1e1e; color: #888;"
        )

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignLeft)
        self._status_label.setStyleSheet("padding: 4px; color: #0f0;")

        # -- Buttons --------------------------------------------------------
        self._btn_open = QPushButton("📂  Escolher Vídeo")
        self._btn_open.clicked.connect(self._on_open_video)

        self._btn_analyze = QPushButton("🤖  Analyze Video")
        self._btn_analyze.clicked.connect(self._on_analyze)
        self._btn_analyze.setEnabled(False)

        self._btn_export = QPushButton("💾  Export Highlight")
        self._btn_export.clicked.connect(self._on_export)
        self._btn_export.setEnabled(False)

        # -- Layout ---------------------------------------------------------
        layout = QVBoxLayout()

        layout.addWidget(QLabel("<h2>🏍️  Motorcycle AI Editor</h2>"))
        layout.addWidget(self._video_name_label)
        layout.addWidget(self._btn_open)
        layout.addWidget(self._btn_analyze)
        layout.addWidget(self._btn_export)

        layout.addSpacing(10)
        layout.addWidget(QLabel("<b>Preview:</b>"))
        layout.addWidget(self._preview_label)

        layout.addSpacing(10)
        layout.addWidget(QLabel("<b>Video Info:</b>"))
        layout.addWidget(self._info_label)

        layout.addStretch()
        layout.addWidget(self._status_label)

        self.setLayout(layout)

        # -- State tracking -------------------------------------------------
        self._analysis_thread: _WorkerThread | None = None

    # ------------------------------------------------------------------
    # Slot: Open video
    # ------------------------------------------------------------------

    def _on_open_video(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video",
            "",
            "Videos (*.mp4 *.mov *.mkv *.avi)",
        )

        if not file_path:
            return

        try:
            video_info = self._controller.open_video(file_path)
        except FileNotFoundError:
            self._set_status(f"ERROR: Video not found: {file_path}")
            return

        # Update UI
        display_name = Path(file_path).name
        self._video_name_label.setText(display_name)
        self._info_label.setText(self._format_video_info(video_info))

        # Load thumbnail via controller (goes through ThumbnailService)
        self._load_preview()

        # Enable analyze button
        self._btn_analyze.setEnabled(True)
        self._btn_export.setEnabled(False)
        self._set_status(f"Loaded: {display_name}")

    # ------------------------------------------------------------------
    # Slot: Analyze video
    # ------------------------------------------------------------------

    def _on_analyze(self) -> None:
        if not self._controller.has_video:
            self._set_status("ERROR: No video loaded")
            return

        self._btn_analyze.setEnabled(False)
        self._set_status("Analyzing video with AI... this may take a while.")

        def _analyze() -> tuple[int, float]:
            timeline = self._controller.analyze_video(
                prompt="Find the best motorcycle riding moments",
                rate_fps=1.0,
            )
            total_clips = len(timeline.clips)
            total_duration = sum(c.duration for c in timeline.clips)
            return total_clips, total_duration

        self._analysis_thread = _WorkerThread(_analyze)
        self._analysis_thread.finished.connect(self._on_analysis_finished)
        self._analysis_thread.start()

    def _on_analysis_finished(
        self, result: tuple[int, float] | None, error: Exception | None
    ) -> None:
        if error:
            self._set_status(f"ERROR during analysis: {error}")
            self._btn_analyze.setEnabled(True)
            return

        clips, duration = result
        self._set_status(
            f"Analysis complete: {clips} clips, "
            f"{duration:.0f}s total highlight duration"
        )
        self._btn_export.setEnabled(True)

        # Show timeline summary in info label
        if self._controller.timeline:
            info_text = self._format_video_info(self._controller.video_info)
            info_text += "\n\n--- Timeline ---\n"
            for clip in self._controller.timeline.clips:
                stars = "⭐" * int(clip.score / 2)
                info_text += (
                    f"[{clip.start_time:.0f}s - {clip.end_time:.0f}s] "
                    f"{stars} {clip.category}: {clip.reason}\n"
                )
            self._info_label.setText(info_text)

    # ------------------------------------------------------------------
    # Slot: Export video
    # ------------------------------------------------------------------

    def _on_export(self) -> None:
        if not self._controller.timeline:
            self._set_status("ERROR: No timeline to export")
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Video",
            "highlight.mp4",
            "MP4 Files (*.mp4)",
        )

        if not output_path:
            return

        self._btn_export.setEnabled(False)
        self._set_status("Exporting video... please wait.")

        def _export() -> str:
            path = self._controller.export_video(
                output_path=output_path,
                codec="h264",
                use_nvenc=True,
                crf=23,
                preset="medium",
            )
            return str(path)

        thread = _WorkerThread(_export)
        thread.finished.connect(self._on_export_finished)
        thread.start()

    def _on_export_finished(
        self, result: str | None, error: Exception | None
    ) -> None:
        if error:
            self._set_status(f"ERROR during export: {error}")
            self._btn_export.setEnabled(True)
            return

        self._set_status(f"Export complete: {result}")
        self._btn_export.setEnabled(True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_preview(self) -> None:
        """Load the video thumbnail using the controller."""
        thumb_path = self._controller._thumbnail_service.get_thumbnail(
            self._controller.video_info
        )
        if thumb_path and thumb_path.exists():
            pixmap = QPixmap(str(thumb_path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self._preview_label.width(),
                    self._preview_label.height(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                self._preview_label.setPixmap(scaled)
            else:
                self._preview_label.setText("Sem preview")
        else:
            self._preview_label.setText("Sem preview")

    @staticmethod
    def _format_video_info(video_info) -> str:
        """Format video metadata as a readable string."""
        from models.video_info import VideoInfo

        info: VideoInfo = video_info
        return (
            f"Duration: {info.duration_text}\n"
            f"Resolution: {info.resolution}\n"
            f"FPS: {info.fps:.2f}\n"
            f"Frames: {info.frames}\n"
            f"Codec: {info.codec}\n"
            f"Size: {info.size_text}"
        )

    def _set_status(self, message: str) -> None:
        """Update the status bar label."""
        self._status_label.setText(message)