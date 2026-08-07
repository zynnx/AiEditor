from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel


class Card(QFrame):
    """
    Cartão reutilizável para a interface.
    """

    def __init__(self, title: str):

        super().__init__()

        self.setObjectName("card")

        layout = QVBoxLayout(self)

        self.title = QLabel(title)

        self.title.setObjectName("cardTitle")

        layout.addWidget(self.title)