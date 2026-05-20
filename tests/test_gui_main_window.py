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


# ---- Drag-and-drop / file picker (issue #7) ----


def test_window_aceita_drops(qapp: object) -> None:
    window = MainWindow()
    assert window.acceptDrops() is True


def test_browse_button_existe_e_inicial(qapp: object) -> None:
    window = MainWindow()
    assert isinstance(window.browse_button, QPushButton)
    assert window.browse_button.text() == "Procurar…"


def test_selected_file_inicialmente_none(qapp: object) -> None:
    window = MainWindow()
    assert window.selected_file is None


def test_set_selected_file_atualiza_ui_com_duracao(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Após set_selected_file, drop_title vira o nome e subtitle mostra a duração."""
    from pathlib import Path

    monkeypatch.setattr("kuatia.gui.main_window.get_audio_duration", lambda _p: 125.0)

    window = MainWindow()
    window.set_selected_file(Path("/tmp/exemplo.mp4"))

    assert window.selected_file == Path("/tmp/exemplo.mp4")
    assert window.drop_title.text() == "exemplo.mp4"
    assert "2m 05s" in window.drop_subtitle.text()
    assert window.browse_button.text() == "Trocar arquivo…"
    assert "selecionado:" in window.log_view.toPlainText()


def test_set_selected_file_sem_duracao_mostra_placeholder(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ffprobe ausente → subtitle indica `--:--` mas UI não crasha."""
    from pathlib import Path

    monkeypatch.setattr("kuatia.gui.main_window.get_audio_duration", lambda _p: None)

    window = MainWindow()
    window.set_selected_file(Path("/tmp/sem_ffprobe.wav"))

    assert window.selected_file == Path("/tmp/sem_ffprobe.wav")
    subtitle = window.drop_subtitle.text()
    assert "ffprobe ausente" in subtitle or "--:--" in subtitle


def test_paths_from_event_extrai_urls_locais(qapp: object) -> None:
    """Helper estático: extrai paths locais de mimeData com URLs."""
    from pathlib import Path

    from PySide6.QtCore import QUrl

    class _FakeMime:
        def __init__(self, urls: list[QUrl]) -> None:
            self._urls = urls

        def hasUrls(self) -> bool:
            return bool(self._urls)

        def urls(self) -> list[QUrl]:
            return self._urls

    class _FakeEvent:
        def __init__(self, mime: _FakeMime) -> None:
            self._mime = mime

        def mimeData(self) -> _FakeMime:
            return self._mime

    urls = [QUrl.fromLocalFile("/tmp/a.mp4"), QUrl.fromLocalFile("/tmp/b.txt")]
    paths = MainWindow._paths_from_event(_FakeEvent(_FakeMime(urls)))
    assert paths == [Path("/tmp/a.mp4"), Path("/tmp/b.txt")]


def test_paths_from_event_sem_urls(qapp: object) -> None:
    class _FakeMime:
        def hasUrls(self) -> bool:
            return False

        def urls(self) -> list[object]:
            return []

    class _FakeEvent:
        def mimeData(self) -> _FakeMime:
            return _FakeMime()

    assert MainWindow._paths_from_event(_FakeEvent()) == []


def test_drag_enter_event_aceita_arquivo_valido(qapp: object) -> None:
    """Simula dragEnter com um .mp4 — evento deve ser aceito."""
    from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
    from PySide6.QtGui import QDragEnterEvent

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile("/tmp/foo.mp4")])
    event = QDragEnterEvent(
        QPoint(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    window = MainWindow()
    window.dragEnterEvent(event)
    assert event.isAccepted()


def test_drag_enter_event_rejeita_arquivo_invalido(qapp: object) -> None:
    """Simula dragEnter com um .txt — evento ignorado."""
    from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
    from PySide6.QtGui import QDragEnterEvent

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile("/tmp/foo.txt")])
    event = QDragEnterEvent(
        QPoint(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    window = MainWindow()
    window.dragEnterEvent(event)
    assert not event.isAccepted()


def test_drop_event_arquivo_valido_atualiza_estado(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathlib import Path

    from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
    from PySide6.QtGui import QDropEvent

    monkeypatch.setattr("kuatia.gui.main_window.get_audio_duration", lambda _p: 60.0)

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile("/tmp/foo.mp4")])
    event = QDropEvent(
        QPointF(10.0, 10.0),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    window = MainWindow()
    window.dropEvent(event)
    assert window.selected_file == Path("/tmp/foo.mp4")
    assert event.isAccepted()
