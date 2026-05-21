"""Dialog de primeira execução: oferece baixar o modelo ou apontar um manual.

`QDialog` simples + widgets Fluent dentro — comportamento previsível em tests
(windowTitle, exec, result funcionam como QDialog padrão).
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, PrimaryPushButton, PushButton, SubtitleLabel

# Mesmo sentinela usado por `core.model_manager.is_model_ready`.
_READY_SENTINEL = "openvino_encoder_model.xml"


class FirstRunChoice(Enum):
    """Resultado do `FirstRunDialog.exec()`."""

    DOWNLOAD = "download"
    SKIP = "skip"
    MANUAL = "manual"
    CLOSED = "closed"  # usuário fechou pelo X


class FirstRunDialog(QDialog):
    """Dialog modal apresentando 3 opções pro 1º uso sem modelo cacheado."""

    def __init__(
        self,
        model_name: str,
        size_mb: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Kuatia — Primeira execução")
        self.setMinimumWidth(500)
        self._choice: FirstRunChoice = FirstRunChoice.CLOSED
        self._build_ui(model_name, size_mb)

    def _build_ui(self, model_name: str, size_mb: int) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)

        title = SubtitleLabel(f"Baixar modelo {model_name}?")

        body = BodyLabel(
            f"É necessário baixar o modelo Whisper {model_name} (~{size_mb} MB).\n"
            "O download acontece uma vez; runs seguintes usam o cache local.\n\n"
            "Você também pode apontar um diretório com um modelo OpenVINO IR já "
            "convertido (gerado por `kuatia-convert` ou outra ferramenta)."
        )
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(title)
        layout.addSpacing(4)
        layout.addWidget(body)
        layout.addSpacing(12)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        self.skip_button = PushButton("Pular")
        self.skip_button.clicked.connect(self._on_skip)

        self.manual_button = PushButton("Apontar modelo manualmente…")
        self.manual_button.clicked.connect(self._on_manual)

        self.download_button = PrimaryPushButton(f"Baixar agora (~{size_mb} MB)")
        self.download_button.setDefault(True)
        self.download_button.clicked.connect(self._on_download)

        button_row.addWidget(self.skip_button)
        button_row.addStretch(1)
        button_row.addWidget(self.manual_button)
        button_row.addWidget(self.download_button)

        layout.addLayout(button_row)

    @property
    def choice(self) -> FirstRunChoice:
        return self._choice

    def _on_download(self) -> None:
        self._choice = FirstRunChoice.DOWNLOAD
        self.accept()

    def _on_skip(self) -> None:
        self._choice = FirstRunChoice.SKIP
        self.reject()

    def _on_manual(self) -> None:
        self._choice = FirstRunChoice.MANUAL
        self.accept()


def is_manual_model_dir_valid(path: Path) -> bool:
    """Diretório apontado pelo usuário é um modelo OpenVINO IR utilizável?"""
    if not path.is_dir():
        return False
    return (path / _READY_SENTINEL).exists()
