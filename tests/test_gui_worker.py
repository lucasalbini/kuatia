"""Tests do `gui/worker.py` — chamamos `run()` direto (sem QThread)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

pytest.importorskip("PySide6")

from kuatia.core.errors import AudioLoadError, ModelNotFoundError, TranscriptionError  # noqa: E402
from kuatia.core.transcriber import Segment  # noqa: E402
from kuatia.gui.worker import TranscribeWorker, make_transcriber  # noqa: E402


def _make_worker(
    transcriber: Any,
    qapp: object,
    *,
    load_audio: Any = None,
    input_path: Path = Path("/tmp/foo.mp4"),
) -> TranscribeWorker:
    del qapp  # garante que QApplication existe via fixture
    worker = TranscribeWorker(
        transcriber=transcriber,
        input_path=input_path,
        model_dir=Path("/tmp/model"),
        device="CPU",
        language="portuguese",
        task="transcribe",
    )
    if load_audio is not None:
        worker._load_audio = load_audio
    else:
        worker._load_audio = lambda _p: np.zeros(16_000, dtype=np.float32)
    return worker


def _connect_signals(worker: TranscribeWorker) -> dict[str, list[Any]]:
    captured: dict[str, list[Any]] = {
        "progress": [],
        "log": [],
        "finished": [],
        "error": [],
        "cancelled": [],
    }
    worker.progress.connect(lambda p: captured["progress"].append(p))
    worker.log_line.connect(lambda m: captured["log"].append(m))
    worker.finished.connect(lambda s: captured["finished"].append(s))
    worker.error.connect(lambda e: captured["error"].append(e))
    worker.cancelled.connect(lambda: captured["cancelled"].append(True))
    return captured


def test_worker_run_emite_finished_com_segments(qapp: object) -> None:
    transcriber = MagicMock()
    segments = [Segment(0.0, 1.0, "olá")]

    def fake_transcribe(
        audio: Any, language: str, task: str, on_progress: Any, on_log: Any
    ) -> list[Segment]:
        on_progress(0.0)
        on_log("transcrição: iniciando")
        on_progress(1.0)
        return segments

    transcriber.transcribe.side_effect = fake_transcribe
    worker = _make_worker(transcriber, qapp)
    captured = _connect_signals(worker)

    worker.run()

    assert captured["finished"] == [segments]
    assert captured["error"] == []
    assert captured["cancelled"] == []
    # Progress vira percentuais 0..100
    assert 0 in captured["progress"] and 100 in captured["progress"]
    # load_model chamado com (model_dir, device)
    transcriber.load_model.assert_called_once_with(Path("/tmp/model"), "CPU")
    # Args de transcribe
    _, kwargs = transcriber.transcribe.call_args
    assert kwargs["language"] == "portuguese"
    assert kwargs["task"] == "transcribe"


def test_worker_error_audio_emite_error(qapp: object) -> None:
    def bad_load(_p: Path) -> Any:
        raise AudioLoadError("ffmpeg fora do PATH")

    transcriber = MagicMock()
    worker = _make_worker(transcriber, qapp, load_audio=bad_load)
    captured = _connect_signals(worker)

    worker.run()

    assert captured["error"] == ["ffmpeg fora do PATH"]
    assert captured["finished"] == []
    transcriber.load_model.assert_not_called()


def test_worker_error_modelo_emite_error(qapp: object) -> None:
    transcriber = MagicMock()
    transcriber.load_model.side_effect = ModelNotFoundError("modelo ausente")
    worker = _make_worker(transcriber, qapp)
    captured = _connect_signals(worker)

    worker.run()

    assert captured["error"] == ["modelo ausente"]
    transcriber.transcribe.assert_not_called()


def test_worker_error_transcribe_emite_error(qapp: object) -> None:
    transcriber = MagicMock()
    transcriber.transcribe.side_effect = TranscriptionError("falhou")
    worker = _make_worker(transcriber, qapp)
    captured = _connect_signals(worker)

    worker.run()

    assert captured["error"] == ["falhou"]


def test_worker_cancel_antes_de_iniciar(qapp: object) -> None:
    transcriber = MagicMock()
    worker = _make_worker(transcriber, qapp)
    captured = _connect_signals(worker)

    worker.request_cancel()
    assert worker.cancel_requested is True
    worker.run()

    assert captured["cancelled"] == [True]
    assert captured["finished"] == []
    assert captured["error"] == []
    transcriber.load_model.assert_not_called()
    transcriber.transcribe.assert_not_called()


def test_worker_cancel_depois_de_load_audio(qapp: object) -> None:
    transcriber = MagicMock()

    def load_audio_marks_cancel(_p: Path) -> Any:
        # Simula: usuário cancela enquanto load_audio rodava.
        worker.request_cancel()
        return np.zeros(16_000, dtype=np.float32)

    worker = _make_worker(transcriber, qapp, load_audio=load_audio_marks_cancel)
    captured = _connect_signals(worker)

    worker.run()

    assert captured["cancelled"] == [True]
    transcriber.load_model.assert_not_called()
    transcriber.transcribe.assert_not_called()


def test_worker_cancel_depois_de_load_model(qapp: object) -> None:
    transcriber = MagicMock()

    def load_model_marks_cancel(*_args: Any, **_kwargs: Any) -> None:
        worker.request_cancel()

    transcriber.load_model.side_effect = load_model_marks_cancel
    worker = _make_worker(transcriber, qapp)
    captured = _connect_signals(worker)

    worker.run()

    assert captured["cancelled"] == [True]
    transcriber.transcribe.assert_not_called()


def test_worker_cancel_depois_de_transcribe_descarta_resultado(qapp: object) -> None:
    """Cancelamento mid-transcrição: resultado existe mas não é emitido."""
    transcriber = MagicMock()

    def transcribe_marks_cancel(
        audio: Any, language: str, task: str, on_progress: Any, on_log: Any
    ) -> list[Segment]:
        on_progress(1.0)
        worker.request_cancel()
        return [Segment(0.0, 1.0, "olá")]

    transcriber.transcribe.side_effect = transcribe_marks_cancel
    worker = _make_worker(transcriber, qapp)
    captured = _connect_signals(worker)

    worker.run()

    assert captured["cancelled"] == [True]
    assert captured["finished"] == []  # NÃO emite o resultado


def test_worker_progress_clamp() -> None:
    """`_emit_progress` clampa a [0, 100] mesmo com fração fora da faixa."""
    captured: list[int] = []

    transcriber = MagicMock()
    worker = TranscribeWorker(
        transcriber=transcriber,
        input_path=Path("/tmp/x"),
        model_dir=Path("/tmp/m"),
        device="CPU",
        language="portuguese",
        task="transcribe",
    )
    worker.progress.connect(captured.append)
    worker._emit_progress(-0.5)
    worker._emit_progress(1.5)
    worker._emit_progress(0.42)
    assert captured == [0, 100, 42]


def test_make_transcriber_retorna_instancia() -> None:
    from kuatia.core.transcriber import Transcriber

    assert isinstance(make_transcriber(), Transcriber)
