"""Smoke tests do package — verifica importação e helpers puros sem dependência de modelo."""

from __future__ import annotations

import pytest


def test_package_importa() -> None:
    import kuatia

    assert kuatia.__doc__


def test_main_entrypoints_existem() -> None:
    from kuatia.convert_model import main as convert_main
    from kuatia.transcribe import main as transcribe_main

    assert callable(convert_main)
    assert callable(transcribe_main)


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
    from kuatia.transcribe import _format_timestamp

    assert _format_timestamp(seconds) == expected


def test_iter_valid_chunks_filtra_vazios_e_sem_start() -> None:
    from kuatia.transcribe import _iter_valid_chunks

    chunks = [
        {"timestamp": (0.0, 1.0), "text": "olá"},
        {"timestamp": (None, 2.0), "text": "ignorado (sem start)"},
        {"timestamp": (3.0, None), "text": "fim faltando"},
        {"timestamp": (4.0, 5.0), "text": "   "},  # texto vazio após strip
        {"timestamp": (6.0, 7.0), "text": "mundo"},
    ]
    valid = _iter_valid_chunks(chunks)
    assert valid == [
        (0.0, 1.0, "olá"),
        (3.0, 4.0, "fim faltando"),
        (6.0, 7.0, "mundo"),
    ]
