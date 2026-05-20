"""Tests do `core/audio.py` — caminhos de erro mockados + smoke com .wav real (CI/ffmpeg)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from kuatia.core.audio import SAMPLE_RATE, load_audio
from kuatia.core.errors import AudioLoadError


def test_load_audio_ffmpeg_ausente(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("kuatia.core.audio.shutil.which", lambda _name: None)
    with pytest.raises(AudioLoadError, match="ffmpeg não encontrado"):
        load_audio(tmp_path / "qualquer.mp4")


def test_load_audio_arquivo_inexistente(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("kuatia.core.audio.shutil.which", lambda _name: "/fake/ffmpeg")
    with pytest.raises(AudioLoadError, match="Arquivo não encontrado"):
        load_audio(tmp_path / "naoexiste.mp4")


def test_load_audio_ffmpeg_falha(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """ffmpeg sai com erro → AudioLoadError com stderr embutido."""
    monkeypatch.setattr("kuatia.core.audio.shutil.which", lambda _name: "/fake/ffmpeg")
    fake_input = tmp_path / "fake.mp4"
    fake_input.write_bytes(b"corrompido")

    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.CalledProcessError(
            returncode=1, cmd=["ffmpeg"], stderr="formato inválido".encode()
        )

    monkeypatch.setattr("kuatia.core.audio.subprocess.run", fake_run)

    with pytest.raises(AudioLoadError, match="formato inválido"):
        load_audio(fake_input)


def test_load_audio_vazio(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """ffmpeg retorna sucesso mas stdout vazio → AudioLoadError."""
    monkeypatch.setattr("kuatia.core.audio.shutil.which", lambda _name: "/fake/ffmpeg")
    fake_input = tmp_path / "vazio.mp4"
    fake_input.write_bytes(b"x")

    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args=["ffmpeg"], returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr("kuatia.core.audio.subprocess.run", fake_run)

    with pytest.raises(AudioLoadError, match="não extraiu áudio"):
        load_audio(fake_input)


def test_load_audio_subprocess_stderr_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """CalledProcessError sem stderr não deve quebrar o handler."""
    monkeypatch.setattr("kuatia.core.audio.shutil.which", lambda _name: "/fake/ffmpeg")
    fake_input = tmp_path / "x.mp4"
    fake_input.write_bytes(b"x")

    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.CalledProcessError(returncode=1, cmd=["ffmpeg"], stderr=None)

    monkeypatch.setattr("kuatia.core.audio.subprocess.run", fake_run)

    with pytest.raises(AudioLoadError, match="ffmpeg falhou"):
        load_audio(fake_input)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg não está no PATH")
def test_load_audio_smoke_wav_real(tiny_wav: Path) -> None:
    """E2E sem mock: chama ffmpeg de verdade num .wav de 1s e valida o array."""
    audio = load_audio(tiny_wav)
    # ~1s de áudio a 16kHz, com margem por causa do header do WAV/encoding
    assert SAMPLE_RATE == 16_000
    assert 0.8 * SAMPLE_RATE <= audio.size <= 1.2 * SAMPLE_RATE
    assert audio.dtype.name == "float32"
