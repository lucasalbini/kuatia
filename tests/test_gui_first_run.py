"""Tests do `gui/first_run.py` e do `gui/download_worker.py`."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

pytest.importorskip("PySide6")

from kuatia.gui.download_worker import DownloadWorker  # noqa: E402
from kuatia.gui.first_run import (  # noqa: E402
    FirstRunChoice,
    FirstRunDialog,
    is_manual_model_dir_valid,
)


def test_is_manual_model_dir_valid_diretorio_inexistente(tmp_path: Path) -> None:
    assert is_manual_model_dir_valid(tmp_path / "naoexiste") is False


def test_is_manual_model_dir_valid_sem_sentinela(tmp_path: Path) -> None:
    assert is_manual_model_dir_valid(tmp_path) is False


def test_is_manual_model_dir_valid_com_sentinela(tmp_path: Path) -> None:
    (tmp_path / "openvino_encoder_model.xml").write_text("<xml />")
    assert is_manual_model_dir_valid(tmp_path) is True


def test_first_run_dialog_inicial(qapp: object) -> None:
    dialog = FirstRunDialog(model_name="large-v3", size_mb=3000)
    assert dialog.windowTitle().startswith("Kuatia")
    assert dialog.choice == FirstRunChoice.CLOSED
    assert dialog.download_button.text().startswith("Baixar")
    assert dialog.skip_button.text() == "Pular"
    assert "manualmente" in dialog.manual_button.text().lower()


def test_first_run_dialog_click_download(qapp: object) -> None:
    dialog = FirstRunDialog(model_name="large-v3", size_mb=3000)
    dialog.download_button.click()
    assert dialog.choice == FirstRunChoice.DOWNLOAD
    assert dialog.result() == FirstRunDialog.DialogCode.Accepted


def test_first_run_dialog_click_skip(qapp: object) -> None:
    dialog = FirstRunDialog(model_name="medium", size_mb=1500)
    dialog.skip_button.click()
    assert dialog.choice == FirstRunChoice.SKIP
    assert dialog.result() == FirstRunDialog.DialogCode.Rejected


def test_first_run_dialog_click_manual(qapp: object) -> None:
    dialog = FirstRunDialog(model_name="small", size_mb=500)
    dialog.manual_button.click()
    assert dialog.choice == FirstRunChoice.MANUAL
    assert dialog.result() == FirstRunDialog.DialogCode.Accepted


# ---- DownloadWorker ----


def _connect_download_signals(worker: DownloadWorker) -> dict[str, list[Any]]:
    captured: dict[str, list[Any]] = {
        "progress": [],
        "log": [],
        "finished": [],
        "error": [],
    }
    worker.progress.connect(lambda p: captured["progress"].append(p))
    worker.log_line.connect(lambda m: captured["log"].append(m))
    worker.finished.connect(lambda p: captured["finished"].append(p))
    worker.error.connect(lambda e: captured["error"].append(e))
    return captured


def test_download_worker_sucesso_emite_finished(
    qapp: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "large-v3"
    target.mkdir()

    def fake_dac(name: str, on_progress: Any = None) -> Path:
        if on_progress is not None:
            on_progress(0.0)
            on_progress(1.0)
        return target

    monkeypatch.setattr("kuatia.gui.download_worker.download_and_convert", fake_dac)

    worker = DownloadWorker("large-v3")
    captured = _connect_download_signals(worker)
    worker.run()

    assert captured["finished"] == [target]
    assert captured["error"] == []
    assert 0 in captured["progress"] and 100 in captured["progress"]


def test_download_worker_falha_emite_error(qapp: object, monkeypatch: pytest.MonkeyPatch) -> None:
    def bad_dac(_name: str, on_progress: Any = None) -> Path:
        raise RuntimeError("rede caiu")

    monkeypatch.setattr("kuatia.gui.download_worker.download_and_convert", bad_dac)

    worker = DownloadWorker("large-v3")
    captured = _connect_download_signals(worker)
    worker.run()

    assert captured["error"] == ["Falha ao baixar/converter modelo: rede caiu"]
    assert captured["finished"] == []


# ---- MainWindow.check_first_run ----


def test_check_first_run_pula_se_modelo_pronto(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kuatia.gui.main_window import MainWindow

    monkeypatch.setattr("kuatia.gui.main_window.is_model_ready", lambda _name: True)
    # FirstRunDialog não deve ser instanciado.
    monkeypatch.setattr(
        "kuatia.gui.main_window.FirstRunDialog",
        lambda *_a, **_kw: pytest.fail("dialog não deveria abrir"),
    )

    window = MainWindow()
    window.check_first_run()


def test_check_first_run_skip_desabilita_botao(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kuatia.gui.main_window import MainWindow

    monkeypatch.setattr("kuatia.gui.main_window.is_model_ready", lambda _name: False)

    fake_dialog = MagicMock()
    fake_dialog.choice = FirstRunChoice.SKIP
    monkeypatch.setattr("kuatia.gui.main_window.FirstRunDialog", lambda *_a, **_kw: fake_dialog)

    window = MainWindow()
    window.check_first_run()
    assert window.transcribe_button.isEnabled() is False
    assert "não carregado" in window.transcribe_button.toolTip().lower()


def test_check_first_run_download_inicia_worker(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kuatia.gui.main_window import MainWindow

    monkeypatch.setattr("kuatia.gui.main_window.is_model_ready", lambda _name: False)

    fake_dialog = MagicMock()
    fake_dialog.choice = FirstRunChoice.DOWNLOAD
    monkeypatch.setattr("kuatia.gui.main_window.FirstRunDialog", lambda *_a, **_kw: fake_dialog)

    started: list[str] = []

    class _FakeSignal:
        def connect(self, _fn: object) -> None:
            pass

    class _FakeThread:
        started = _FakeSignal()
        finished = _FakeSignal()

        def __init__(self, _parent: object | None = None) -> None:
            pass

        def start(self) -> None:
            started.append("start")

        def quit(self) -> None:
            started.append("quit")

        def deleteLater(self) -> None:  # noqa: N802
            pass

    monkeypatch.setattr("kuatia.gui.main_window.QThread", _FakeThread)
    monkeypatch.setattr("kuatia.gui.main_window.DownloadWorker", lambda _name: MagicMock())

    window = MainWindow()
    window.check_first_run()
    assert started == ["start"]
    assert window.transcribe_button.isEnabled() is False


def test_check_first_run_manual_valido_aceita(
    qapp: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from kuatia.gui.main_window import MainWindow

    (tmp_path / "openvino_encoder_model.xml").write_text("<xml />")

    monkeypatch.setattr("kuatia.gui.main_window.is_model_ready", lambda _name: False)
    fake_dialog = MagicMock()
    fake_dialog.choice = FirstRunChoice.MANUAL
    monkeypatch.setattr("kuatia.gui.main_window.FirstRunDialog", lambda *_a, **_kw: fake_dialog)

    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getExistingDirectory",
        lambda *_a, **_kw: str(tmp_path),
    )

    window = MainWindow()
    window.check_first_run()
    assert window.manual_model_dir == tmp_path
    assert window.transcribe_button.isEnabled() is True


def test_check_first_run_manual_invalido_marca_nao_carregado(
    qapp: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from kuatia.gui.main_window import MainWindow

    # tmp_path sem sentinela → dir inválido
    monkeypatch.setattr("kuatia.gui.main_window.is_model_ready", lambda _name: False)
    fake_dialog = MagicMock()
    fake_dialog.choice = FirstRunChoice.MANUAL
    monkeypatch.setattr("kuatia.gui.main_window.FirstRunDialog", lambda *_a, **_kw: fake_dialog)

    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getExistingDirectory",
        lambda *_a, **_kw: str(tmp_path),
    )
    monkeypatch.setattr(
        "kuatia.gui.main_window.MainWindow._show_message",
        lambda self, text: None,
    )

    window = MainWindow()
    window.check_first_run()
    assert window.manual_model_dir is None
    assert window.transcribe_button.isEnabled() is False


def test_check_first_run_manual_cancelado(qapp: object, monkeypatch: pytest.MonkeyPatch) -> None:
    from kuatia.gui.main_window import MainWindow

    monkeypatch.setattr("kuatia.gui.main_window.is_model_ready", lambda _name: False)
    fake_dialog = MagicMock()
    fake_dialog.choice = FirstRunChoice.MANUAL
    monkeypatch.setattr("kuatia.gui.main_window.FirstRunDialog", lambda *_a, **_kw: fake_dialog)
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getExistingDirectory",
        lambda *_a, **_kw: "",  # usuário cancelou
    )

    window = MainWindow()
    window.check_first_run()
    assert window.manual_model_dir is None
    assert window.transcribe_button.isEnabled() is False


def test_resolve_model_dir_usa_manual_quando_setado(
    qapp: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from kuatia.gui.main_window import MainWindow

    monkeypatch.setattr("kuatia.gui.main_window.is_model_ready", lambda _name: False)
    window = MainWindow()
    window._manual_model_dir = tmp_path
    assert window._resolve_model_dir("large-v3") == tmp_path


def test_resolve_model_dir_cache_quando_pronto(
    qapp: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from kuatia.gui.main_window import MainWindow

    monkeypatch.setattr("kuatia.gui.main_window.is_model_ready", lambda _name: True)
    monkeypatch.setattr("kuatia.gui.main_window.model_dir", lambda name: tmp_path / name)
    window = MainWindow()
    assert window._resolve_model_dir("large-v3") == tmp_path / "large-v3"


def test_resolve_model_dir_none_quando_nada_pronto(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kuatia.gui.main_window import MainWindow

    monkeypatch.setattr("kuatia.gui.main_window.is_model_ready", lambda _name: False)
    window = MainWindow()
    assert window._resolve_model_dir("large-v3") is None
