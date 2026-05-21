"""Tests do `gui/output.py` — export multi-formato e abrir pasta no SO."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from kuatia.core.transcriber import Segment
from kuatia.core.writers import DocxMeta
from kuatia.gui.output import (
    at_least_one_selected,
    export_outputs,
    open_in_file_manager,
    selected_formats,
)


@pytest.fixture
def three_segments() -> list[Segment]:
    return [
        Segment(0.0, 1.0, "um"),
        Segment(1.0, 2.0, "dois"),
        Segment(2.0, 3.0, "três"),
    ]


def test_selected_formats_filtra_checked() -> None:
    assert selected_formats({"txt": True, "srt": False, "docx": True}) == ["txt", "docx"]


def test_at_least_one_selected_mapping_true() -> None:
    assert at_least_one_selected({"txt": True, "srt": False}) is True


def test_at_least_one_selected_mapping_false() -> None:
    assert at_least_one_selected({"txt": False, "srt": False}) is False


def test_at_least_one_selected_iterable() -> None:
    assert at_least_one_selected([("a", False), ("b", True)]) is True
    assert at_least_one_selected([("a", False), ("b", False)]) is False


def test_export_outputs_so_formatos_marcados(tmp_path: Path, three_segments: list[Segment]) -> None:
    base = tmp_path / "exemplo"
    paths = export_outputs(
        three_segments,
        base,
        {"txt": True, "srt": False, "vtt": False, "docx": False},
    )
    assert paths == [base.with_suffix(".txt")]
    assert base.with_suffix(".txt").exists()
    assert not base.with_suffix(".srt").exists()
    assert not base.with_suffix(".vtt").exists()


def test_export_outputs_todos_formatos(tmp_path: Path, three_segments: list[Segment]) -> None:
    base = tmp_path / "exemplo"
    meta = DocxMeta(input_name="exemplo.mp4", model_name="m")
    paths = export_outputs(
        three_segments,
        base,
        {"txt": True, "srt": True, "vtt": True, "docx": True},
        docx_meta=meta,
    )
    sufixos = [p.suffix for p in paths]
    assert set(sufixos) == {".txt", ".srt", ".vtt", ".docx"}
    for p in paths:
        assert p.exists() and p.stat().st_size > 0


def test_export_outputs_segments_vazios_gera_arquivos_vazios(tmp_path: Path) -> None:
    """Mesmo sem segments, writers geram arquivos (txt vazio, srt vazio) — não crasha."""
    base = tmp_path / "vazio"
    paths = export_outputs([], base, {"txt": True, "srt": True})
    assert all(p.exists() for p in paths)


def test_open_in_file_manager_path_inexistente(tmp_path: Path) -> None:
    assert open_in_file_manager(tmp_path / "naoexiste") is False


def test_open_in_file_manager_linux(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("kuatia.gui.output.sys.platform", "linux")
    calls: list[list[str]] = []

    def fake_popen(args: list[str], **_kwargs: Any) -> object:
        calls.append(args)
        return object()

    monkeypatch.setattr("kuatia.gui.output.subprocess.Popen", fake_popen)
    assert open_in_file_manager(tmp_path) is True
    assert calls == [["xdg-open", str(tmp_path)]]


def test_open_in_file_manager_macos(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("kuatia.gui.output.sys.platform", "darwin")
    calls: list[list[str]] = []

    def fake_popen(args: list[str], **_kwargs: Any) -> object:
        calls.append(args)
        return object()

    monkeypatch.setattr("kuatia.gui.output.subprocess.Popen", fake_popen)
    assert open_in_file_manager(tmp_path) is True
    assert calls == [["open", str(tmp_path)]]


def test_open_in_file_manager_windows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("kuatia.gui.output.sys.platform", "win32")
    calls: list[str] = []

    def fake_startfile(path: str) -> None:
        calls.append(path)

    monkeypatch.setattr("kuatia.gui.output.os.startfile", fake_startfile, raising=False)
    assert open_in_file_manager(tmp_path) is True
    assert calls == [str(tmp_path)]


def test_open_in_file_manager_oserror_retorna_false(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("kuatia.gui.output.sys.platform", "linux")

    def fake_popen(*_args: Any, **_kwargs: Any) -> object:
        raise OSError("falhou")

    monkeypatch.setattr("kuatia.gui.output.subprocess.Popen", fake_popen)
    assert open_in_file_manager(tmp_path) is False


# Smoke import pra subprocess fica mais explícito
def test_subprocess_module_disponivel() -> None:
    assert subprocess.Popen is not None
