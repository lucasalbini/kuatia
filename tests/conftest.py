"""Fixtures comuns aos tests do core e da GUI."""

from __future__ import annotations

import os
import struct
import wave
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

# Qt headless: precisa estar setado ANTES de qualquer import de PySide6 nos tests.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from kuatia.core.transcriber import Segment  # noqa: E402
from kuatia.core.writers import DocxMeta  # noqa: E402


@pytest.fixture
def sample_segments() -> list[Segment]:
    """Três segments curtos para cobrir headers/footers de writers."""
    return [
        Segment(0.0, 1.5, "Olá mundo"),
        Segment(2.0, 3.5, "Segunda fala com acentos: ção, ã"),
        Segment(4.0, 5.5, "Terceira fala"),
    ]


@pytest.fixture
def fixed_meta() -> DocxMeta:
    """`DocxMeta` com `generated_at` fixo pra snapshots reproduzíveis."""
    return DocxMeta(
        input_name="exemplo.mp4",
        duration_sec=125.5,
        model_name="whisper-large-v3",
        generated_at=datetime(2026, 5, 20, 22, 45),
    )


@pytest.fixture
def tiny_wav(tmp_path: Path) -> Path:
    """Gera um `.wav` PCM 16-bit mono 16kHz de ~1s (silêncio) via stdlib `wave`.

    Não depende de ffmpeg pra gerar — só pra decodificar depois em `load_audio`.
    """
    out = tmp_path / "tiny.wav"
    sample_rate = 16_000
    duration_s = 1.0
    n_samples = int(sample_rate * duration_s)
    silence = struct.pack(f"<{n_samples}h", *([0] * n_samples))
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(silence)
    return out


@pytest.fixture(scope="session")
def qapp() -> Iterator[object]:
    """`QApplication` única por sessão — Qt não permite múltiplas instâncias."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
