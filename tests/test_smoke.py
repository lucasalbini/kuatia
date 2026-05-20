"""Smoke tests do package — apenas verifica importações cruzadas entre módulos.

Tests detalhados por módulo ficam em `test_core_audio.py`, `test_core_transcriber.py`
e `test_writers.py`.
"""

from __future__ import annotations


def test_package_importa() -> None:
    import kuatia

    assert kuatia.__doc__


def test_main_entrypoints_existem() -> None:
    from kuatia.cli import main as transcribe_main
    from kuatia.convert_model import main as convert_main

    assert callable(convert_main)
    assert callable(transcribe_main)


def test_core_api_importa() -> None:
    """Garante que a API pública do core é importável em uma única chamada."""
    from kuatia.core.audio import SAMPLE_RATE, load_audio
    from kuatia.core.errors import (
        AudioLoadError,
        KuatiaError,
        ModelNotFoundError,
        TranscriptionError,
    )
    from kuatia.core.transcriber import Segment, Transcriber
    from kuatia.core.writers import DocxMeta, write_docx, write_srt, write_txt, write_vtt

    assert SAMPLE_RATE == 16_000
    assert callable(load_audio)
    assert callable(Transcriber)
    assert callable(write_txt)
    assert callable(write_srt)
    assert callable(write_vtt)
    assert callable(write_docx)
    assert callable(DocxMeta)
    assert issubclass(AudioLoadError, KuatiaError)
    assert issubclass(ModelNotFoundError, KuatiaError)
    assert issubclass(TranscriptionError, KuatiaError)
    assert Segment(0.0, 1.0, "x").text == "x"
