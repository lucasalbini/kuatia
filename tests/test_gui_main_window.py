"""Tests da GUI rodando headless (`QT_QPA_PLATFORM=offscreen`).

Valida estrutura do widget tree e estado inicial — sem testar comportamento,
porque #6 entrega só o esqueleto. Issues #7+ adicionam tests de interação.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QCheckBox,
    QComboBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
)

from kuatia.core.model_manager import available_models  # noqa: E402
from kuatia.gui.main_window import MainWindow  # noqa: E402


def test_main_window_inicializa(qapp: object) -> None:
    window = MainWindow()
    assert window.windowTitle().startswith("Kuatia")
    assert window.centralWidget() is not None


def test_progress_bar_escondida_no_inicio(qapp: object) -> None:
    window = MainWindow()
    assert isinstance(window.progress, QProgressBar)
    assert not window.progress.isVisible()
    assert window.progress.value() == 0


def test_log_view_readonly_e_vazio(qapp: object) -> None:
    window = MainWindow()
    assert isinstance(window.log_view, QPlainTextEdit)
    assert window.log_view.isReadOnly()
    assert window.log_view.toPlainText() == ""


def test_combo_model_lista_modelos_disponiveis(qapp: object) -> None:
    window = MainWindow()
    assert isinstance(window.model_combo, QComboBox)
    items = [window.model_combo.itemData(i) for i in range(window.model_combo.count())]
    names = [m.name for m in available_models()]
    assert items == names


def test_combo_device_tem_opcoes_esperadas(qapp: object) -> None:
    window = MainWindow()
    texts = [window.device_combo.itemText(i) for i in range(window.device_combo.count())]
    assert texts == list(MainWindow.DEVICE_CHOICES)


def test_combo_task_mapeia_para_valor_interno(qapp: object) -> None:
    window = MainWindow()
    data = [window.task_combo.itemData(i) for i in range(window.task_combo.count())]
    assert data == ["transcribe", "translate"]


def test_checkboxes_de_export_defaults(qapp: object) -> None:
    window = MainWindow()
    assert set(window.export_checks.keys()) == {"txt", "srt", "vtt", "docx"}
    assert window.export_checks["txt"].isChecked() is True
    assert window.export_checks["srt"].isChecked() is True
    assert window.export_checks["vtt"].isChecked() is False
    assert window.export_checks["docx"].isChecked() is False
    for cb in window.export_checks.values():
        assert isinstance(cb, QCheckBox)


def test_botao_transcrever_existe(qapp: object) -> None:
    window = MainWindow()
    assert isinstance(window.transcribe_button, QPushButton)
    assert window.transcribe_button.text() == "Transcrever"


def test_janela_redimensiona_sem_erro(qapp: object) -> None:
    """Smoke de responsividade do layout — apenas resize sem exception."""
    window = MainWindow()
    window.resize(400, 300)
    window.resize(1280, 800)
    assert window.size().width() == 1280


def test_app_entry_point_importa(qapp: object) -> None:
    """`kuatia-gui` entry point: import + função `main` callable."""
    from kuatia.gui.app import main

    assert callable(main)
