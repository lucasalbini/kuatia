"""Tests do `core/transcriber.py` — mocka pipeline OpenVINO, sem modelo real."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from kuatia.core.errors import ModelNotFoundError, TranscriptionError
from kuatia.core.transcriber import Segment, Transcriber, _chunks_to_segments


def _patch_pipeline(monkeypatch: pytest.MonkeyPatch, pipeline_return: dict[str, Any]) -> MagicMock:
    """Substitui `_build_pipeline` por um mock que devolve um callable.

    Retorna o `pipeline` mockado (`callable`) pra o teste inspecionar chamadas.
    """
    fake_pipe = MagicMock(return_value=pipeline_return)
    monkeypatch.setattr("kuatia.core.transcriber._build_pipeline", lambda *_a, **_kw: fake_pipe)
    return fake_pipe


def test_chunks_to_segments_filtra_vazios_e_sem_start() -> None:
    chunks = [
        {"timestamp": (0.0, 1.0), "text": "olá"},
        {"timestamp": (None, 2.0), "text": "ignorado (sem start)"},
        {"timestamp": (3.0, None), "text": "fim faltando"},
        {"timestamp": (4.0, 5.0), "text": "   "},  # texto vazio após strip
        {"timestamp": (6.0, 7.0), "text": "mundo"},
    ]
    segments = _chunks_to_segments(chunks)
    assert segments == [
        Segment(0.0, 1.0, "olá"),
        Segment(3.0, 4.0, "fim faltando"),
        Segment(6.0, 7.0, "mundo"),
    ]


def test_chunks_to_segments_lista_vazia() -> None:
    assert _chunks_to_segments([]) == []


def test_load_model_modelo_nao_encontrado(tmp_path: Path) -> None:
    t = Transcriber()
    with pytest.raises(ModelNotFoundError, match="Modelo não encontrado"):
        t.load_model(tmp_path / "naoexiste", "CPU")


def test_load_model_idempotente(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Chamadas com (model_dir, device) idênticos não recarregam o pipeline."""
    _patch_pipeline(monkeypatch, {"chunks": []})
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    t = Transcriber()
    t.load_model(model_dir, "CPU")
    pipe_1 = t._pipeline
    t.load_model(model_dir, "CPU")  # mesmos args
    pipe_2 = t._pipeline
    assert pipe_1 is pipe_2


def test_load_model_recarrega_se_device_muda(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Pipeline é instanciado de novo quando o device muda."""
    # Cada chamada de `_build_pipeline` retorna um MagicMock distinto pra comprovar reload.
    monkeypatch.setattr("kuatia.core.transcriber._build_pipeline", lambda *_a, **_kw: MagicMock())
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    t = Transcriber()
    t.load_model(model_dir, "CPU")
    pipe_1 = t._pipeline
    t.load_model(model_dir, "GPU")  # device diferente
    pipe_2 = t._pipeline
    assert pipe_1 is not pipe_2


def test_transcribe_sem_load() -> None:
    t = Transcriber()
    with pytest.raises(TranscriptionError, match="Modelo não carregado"):
        t.transcribe(np.zeros(16_000, dtype=np.float32))


def test_transcribe_retorna_segments(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pipeline_return = {
        "chunks": [
            {"timestamp": (0.0, 1.0), "text": "olá"},
            {"timestamp": (1.0, 2.0), "text": "mundo"},
        ]
    }
    fake_pipe = _patch_pipeline(monkeypatch, pipeline_return)
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    t = Transcriber()
    t.load_model(model_dir, "CPU")
    segments = t.transcribe(
        np.zeros(16_000, dtype=np.float32),
        language="portuguese",
        task="transcribe",
    )

    assert segments == [Segment(0.0, 1.0, "olá"), Segment(1.0, 2.0, "mundo")]
    # generate_kwargs deve conter language + task
    _, kwargs = fake_pipe.call_args
    assert kwargs["generate_kwargs"] == {"task": "transcribe", "language": "portuguese"}


def test_transcribe_language_auto_omite_language(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`language='auto'` deve omitir o kwarg, deixando Whisper detectar."""
    fake_pipe = _patch_pipeline(monkeypatch, {"chunks": []})
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    t = Transcriber()
    t.load_model(model_dir, "CPU")
    t.transcribe(np.zeros(16_000, dtype=np.float32), language="auto")

    _, kwargs = fake_pipe.call_args
    assert "language" not in kwargs["generate_kwargs"]
    assert kwargs["generate_kwargs"] == {"task": "transcribe"}


def test_transcribe_callbacks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_pipeline(monkeypatch, {"chunks": [{"timestamp": (0.0, 1.0), "text": "a"}]})
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    progress_calls: list[float] = []
    log_calls: list[str] = []

    t = Transcriber()
    t.load_model(model_dir, "CPU")
    t.transcribe(
        np.zeros(16_000, dtype=np.float32),
        on_progress=progress_calls.append,
        on_log=log_calls.append,
    )

    assert progress_calls == [0.0, 1.0]  # início e fim
    assert any("iniciando" in m for m in log_calls)
    assert any("transcrição:" in m for m in log_calls)


def test_transcribe_propaga_falha_do_pipeline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Exception do pipeline vira `TranscriptionError`."""
    fake_pipe = MagicMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr("kuatia.core.transcriber._build_pipeline", lambda *_a, **_kw: fake_pipe)
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    t = Transcriber()
    t.load_model(model_dir, "CPU")
    with pytest.raises(TranscriptionError, match="boom"):
        t.transcribe(np.zeros(16_000, dtype=np.float32))
