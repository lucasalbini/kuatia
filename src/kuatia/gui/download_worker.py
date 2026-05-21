"""Worker Qt para `download_and_convert` rodar fora do main thread.

Mesmo padrão do `TranscribeWorker`: `QObject` + `moveToThread`, signals
`progress(int)`, `log_line(str)`, `finished(Path)`, `error(str)`. Sem cancel
porque `download_and_convert` é monolítico em `optimum.from_pretrained` — o
usuário cancela fechando a janela.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from kuatia.core.model_manager import download_and_convert

log = logging.getLogger("kuatia")


class DownloadWorker(QObject):
    """Baixa e converte um modelo Whisper na thread em que foi `moveToThread`."""

    progress = Signal(int)  # 0..100
    log_line = Signal(str)
    finished = Signal(Path)
    error = Signal(str)

    def __init__(self, model_name: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._model_name = model_name

    @Slot()
    def run(self) -> None:
        try:
            self.log_line.emit(f"Iniciando download de {self._model_name}…")
            target = download_and_convert(self._model_name, on_progress=self._emit_progress)
            self.log_line.emit(f"Modelo pronto em {target}")
            self.finished.emit(target)
        except Exception as exc:  # noqa: BLE001 — qualquer erro vira mensagem na UI
            log.exception("download_worker: falha")
            self.error.emit(f"Falha ao baixar/converter modelo: {exc}")

    def _emit_progress(self, fraction: float) -> None:
        self.progress.emit(int(max(0.0, min(1.0, fraction)) * 100))
