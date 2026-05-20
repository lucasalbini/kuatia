"""Smoke tests do package — verifica importação e helpers puros sem dependência de modelo."""

from __future__ import annotations

import pytest


def test_package_importa() -> None:
    import kuatia

    assert kuatia.__doc__


def test_main_entrypoints_existem() -> None:
    from kuatia.cli import main as transcribe_main
    from kuatia.convert_model import main as convert_main

    assert callable(convert_main)
    assert callable(transcribe_main)


def test_core_api_importa() -> None:
    from kuatia.core.audio import SAMPLE_RATE, load_audio
    from kuatia.core.errors import (
        AudioLoadError,
        KuatiaError,
        ModelNotFoundError,
        TranscriptionError,
    )
    from kuatia.core.transcriber import Segment, Transcriber
    from kuatia.core.writers import write_srt, write_txt, write_vtt

    assert SAMPLE_RATE == 16_000
    assert callable(load_audio)
    assert callable(Transcriber)
    assert callable(write_txt)
    assert callable(write_srt)
    assert callable(write_vtt)
    assert issubclass(AudioLoadError, KuatiaError)
    assert issubclass(ModelNotFoundError, KuatiaError)
    assert issubclass(TranscriptionError, KuatiaError)
    assert Segment(0.0, 1.0, "x").text == "x"


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "00:00:00,000"),
        (0.5, "00:00:00,500"),
        (61.5, "00:01:01,500"),
        (3661.123, "01:01:01,123"),
        (-1, "00:00:00,000"),  # valores negativos viram 0
    ],
)
def test_format_timestamp(seconds: float, expected: str) -> None:
    from kuatia.core.writers import _format_timestamp

    assert _format_timestamp(seconds) == expected


def test_chunks_to_segments_filtra_vazios_e_sem_start() -> None:
    from kuatia.core.transcriber import Segment, _chunks_to_segments

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
