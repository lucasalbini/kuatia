"""Worker Qt que roda load_audio + Transcriber numa thread separada.

Padrão recomendado: `QObject` + `moveToThread(QThread)` (não subclasse de `QThread`).
Os callbacks `on_progress`/`on_log` do core são ligados a signals, então a UI
recebe atualizações via thread-safe queued connections.

Limitação conhecida: `transcribe()` é uma chamada bloqueante do pipeline
`transformers` e não tem hook de interrupção mid-execução. `request_cancel()`
seta uma flag; ela é checada nas fronteiras (antes de load_audio, depois,
depois de load_model, depois de transcribe). Em chunk boundary mid-transcrição
o cancelamento é best-effort — segura o emit do `finished` mas não cancela
a inferência em si.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from kuatia.core.audio import load_audio as default_load_audio
from kuatia.core.errors import AudioLoadError, ModelNotFoundError, TranscriptionError
from kuatia.core.transcriber import Transcriber

log = logging.getLogger("kuatia")


class TranscribeWorker(QObject):
    """Executa load_audio + load_model + transcribe; comunica via signals."""

    progress = Signal(int)  # 0..100
    log_line = Signal(str)
    finished = Signal(list)  # list[Segment]
    error = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        transcriber: Transcriber,
        input_path: Path,
        model_dir: Path,
        device: str,
        language: str,
        task: str,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._transcriber = transcriber
        self._input_path = input_path
        self._model_dir = model_dir
        self._device = device
        self._language = language
        self._task = task
        self._cancel_requested = False
        # Injetável pra testes — default usa o core diretamente.
        self._load_audio = default_load_audio

    @Slot()
    def request_cancel(self) -> None:
        """Sinaliza pedido de cancelamento. Idempotente."""
        self._cancel_requested = True

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_requested

    @Slot()
    def run(self) -> None:
        """Pipeline completo. Roda na thread em que o worker foi `moveToThread`."""
        try:
            if self._cancel_requested:
                self._emit_cancelled("Cancelado antes de iniciar.")
                return

            self.log_line.emit(f"Carregando áudio de {self._input_path.name}…")
            audio = self._load_audio(self._input_path)

            if self._cancel_requested:
                self._emit_cancelled("Cancelado após carregar áudio.")
                return

            self.log_line.emit(f"Carregando modelo em {self._device}…")
            self._transcriber.load_model(self._model_dir, self._device)

            if self._cancel_requested:
                self._emit_cancelled("Cancelado após carregar modelo.")
                return

            segments = self._transcriber.transcribe(
                audio,
                language=self._language,
                task=self._task,
                on_progress=self._emit_progress,
                on_log=self.log_line.emit,
            )

            if self._cancel_requested:
                self._emit_cancelled("Cancelado após transcrever (resultado descartado).")
                return

            self.finished.emit(segments)
        except (AudioLoadError, ModelNotFoundError, TranscriptionError) as exc:
            log.exception("worker: erro tipado durante transcrição")
            self.error.emit(str(exc))
        except Exception as exc:  # pragma: no cover — captura defensiva
            log.exception("worker: erro inesperado durante transcrição")
            self.error.emit(f"Erro inesperado: {exc}")

    def _emit_progress(self, fraction: float) -> None:
        self.progress.emit(int(max(0.0, min(1.0, fraction)) * 100))

    def _emit_cancelled(self, msg: str) -> None:
        self.log_line.emit(msg)
        self.cancelled.emit()


def make_transcriber() -> Transcriber:
    """Factory injetável — facilita mock em tests da MainWindow."""
    return Transcriber()
