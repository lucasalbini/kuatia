"""Tests dos helpers de `gui/file_picker.py` (sem Qt)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from kuatia.gui import file_picker
from kuatia.gui.file_picker import (
    FILE_DIALOG_FILTER,
    SUPPORTED_EXTENSIONS,
    all_supported,
    format_duration_short,
    get_audio_duration,
    is_supported,
)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("video.mp4", True),
        ("audio.MP3", True),  # case-insensitive
        ("song.flac", True),
        ("speech.ogg", True),
        ("stream.webm", True),
        ("note.txt", False),
        ("data.json", False),
        ("naoexiste", False),
    ],
)
def test_is_supported(name: str, expected: bool) -> None:
    assert is_supported(Path(name)) is expected


def test_all_supported_lista_vazia_false() -> None:
    assert all_supported([]) is False


def test_all_supported_todos_validos() -> None:
    assert all_supported([Path("a.mp4"), Path("b.wav")]) is True


def test_all_supported_um_invalido_false() -> None:
    assert all_supported([Path("a.mp4"), Path("b.txt")]) is False


def test_supported_extensions_cobre_lista_da_issue() -> None:
    """Bate com o que está documentado no AC da issue #7."""
    assert (
        frozenset({".mp4", ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".webm"})
        == SUPPORTED_EXTENSIONS
    )


def test_file_dialog_filter_inclui_todas_extensoes() -> None:
    for ext in SUPPORTED_EXTENSIONS:
        assert f"*{ext}" in FILE_DIALOG_FILTER


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (None, "--:--"),
        (-1, "--:--"),
        (0, "0s"),
        (45, "45s"),
        (60, "1m 00s"),
        (125, "2m 05s"),
        (3725, "1h 02m"),
    ],
)
def test_format_duration_short(seconds: float | None, expected: str) -> None:
    assert format_duration_short(seconds) == expected


def test_get_audio_duration_ffprobe_ausente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kuatia.gui.file_picker.shutil.which", lambda _name: None)
    assert get_audio_duration(Path("/tmp/foo.mp4")) is None


def test_get_audio_duration_sucesso(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kuatia.gui.file_picker.shutil.which", lambda _name: "/fake/ffprobe")

    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["ffprobe"], returncode=0, stdout="125.345\n", stderr=""
        )

    monkeypatch.setattr("kuatia.gui.file_picker.subprocess.run", fake_run)
    assert get_audio_duration(Path("/tmp/foo.mp4")) == pytest.approx(125.345)


def test_get_audio_duration_ffprobe_falha(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kuatia.gui.file_picker.shutil.which", lambda _name: "/fake/ffprobe")

    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(returncode=1, cmd=["ffprobe"])

    monkeypatch.setattr("kuatia.gui.file_picker.subprocess.run", fake_run)
    assert get_audio_duration(Path("/tmp/foo.mp4")) is None


def test_get_audio_duration_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kuatia.gui.file_picker.shutil.which", lambda _name: "/fake/ffprobe")

    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=["ffprobe"], timeout=10)

    monkeypatch.setattr("kuatia.gui.file_picker.subprocess.run", fake_run)
    assert get_audio_duration(Path("/tmp/foo.mp4")) is None


def test_get_audio_duration_stdout_invalido(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kuatia.gui.file_picker.shutil.which", lambda _name: "/fake/ffprobe")

    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["ffprobe"], returncode=0, stdout="N/A\n", stderr=""
        )

    monkeypatch.setattr("kuatia.gui.file_picker.subprocess.run", fake_run)
    assert get_audio_duration(Path("/tmp/foo.mp4")) is None


def test_get_audio_duration_stdout_vazio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kuatia.gui.file_picker.shutil.which", lambda _name: "/fake/ffprobe")

    def fake_run(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["ffprobe"], returncode=0, stdout="", stderr="")

    monkeypatch.setattr("kuatia.gui.file_picker.subprocess.run", fake_run)
    assert get_audio_duration(Path("/tmp/foo.mp4")) is None


def test_module_exposes_logger() -> None:
    assert file_picker.log.name == "kuatia"
