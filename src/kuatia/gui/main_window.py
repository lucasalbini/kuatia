"""Janela principal da GUI — esqueleto sem lógica (issue #6).

Layout: área de drop à esquerda, painel de opções à direita, progress bar
escondida abaixo do split, e log read-only no rodapé. Nenhum widget conectado
a comportamento ainda — issues seguintes (#7-#11) plugam drag-and-drop,
worker thread, export e first-run dialog.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from kuatia.core.model_manager import available_models


class MainWindow(QMainWindow):
    """Janela principal — apresenta layout sem comportamento ligado."""

    DEVICE_CHOICES = ("GPU", "CPU", "NPU", "AUTO")
    LANGUAGE_CHOICES = ("Português", "Inglês", "Espanhol", "Detectar (auto)")
    TASK_CHOICES = (
        ("Transcrever", "transcribe"),
        ("Traduzir (→ inglês)", "translate"),
    )

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Kuatia — Transcrição local")
        self.resize(960, 640)
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal, central)
        splitter.addWidget(self._build_drop_area())
        splitter.addWidget(self._build_options_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, stretch=1)

        self.progress = QProgressBar(central)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        log_box = QGroupBox("Log", central)
        log_layout = QVBoxLayout(log_box)
        log_layout.setContentsMargins(8, 16, 8, 8)
        self.log_view = QPlainTextEdit(log_box)
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Logs da transcrição aparecerão aqui.")
        self.log_view.setMaximumBlockCount(2000)
        log_layout.addWidget(self.log_view)
        root.addWidget(log_box, stretch=0)

        self.setCentralWidget(central)

    def _build_drop_area(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("dropArea")
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setMinimumSize(360, 240)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        frame.setStyleSheet(
            "#dropArea {"
            " border: 2px dashed palette(mid);"
            " border-radius: 12px;"
            " background-color: palette(alternate-base);"
            "}"
        )
        layout = QVBoxLayout(frame)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("Solte um arquivo aqui")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        subtitle = QLabel("…ou clique pra escolher (mp4, mp3, wav, m4a, …)")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: palette(mid);")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        return frame

    def _build_options_panel(self) -> QWidget:
        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        opts = QGroupBox("Opções", panel)
        form = QFormLayout(opts)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.model_combo = QComboBox()
        for info in available_models():
            label = f"{info.name} (~{info.size_mb} MB)"
            self.model_combo.addItem(label, userData=info.name)
        form.addRow("Modelo:", self.model_combo)

        self.device_combo = QComboBox()
        self.device_combo.addItems(self.DEVICE_CHOICES)
        form.addRow("Device:", self.device_combo)

        self.language_combo = QComboBox()
        self.language_combo.addItems(self.LANGUAGE_CHOICES)
        form.addRow("Idioma:", self.language_combo)

        self.task_combo = QComboBox()
        for label, value in self.TASK_CHOICES:
            self.task_combo.addItem(label, userData=value)
        form.addRow("Tarefa:", self.task_combo)

        outer.addWidget(opts)

        export_box = QGroupBox("Formatos de saída", panel)
        export_layout = QHBoxLayout(export_box)
        self.export_checks: dict[str, QCheckBox] = {}
        for fmt, default_on in (("txt", True), ("srt", True), ("vtt", False), ("docx", False)):
            cb = QCheckBox(f".{fmt}")
            cb.setChecked(default_on)
            export_layout.addWidget(cb)
            self.export_checks[fmt] = cb
        export_layout.addStretch(1)
        outer.addWidget(export_box)

        self.transcribe_button = QPushButton("Transcrever")
        self.transcribe_button.setMinimumHeight(36)
        outer.addWidget(self.transcribe_button)

        outer.addStretch(1)
        return panel
