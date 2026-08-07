"""Motorcycle AI Editor – application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from controllers.main_controller import create_controller
from ui.styles import STYLE
from ui.windows.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Motorcycle AI Editor")
    app.setApplicationVersion("0.1.0")

    app.setStyleSheet(STYLE)

    # Dependency injection: create controller, pass to UI
    controller = create_controller()
    window = MainWindow(controller)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
