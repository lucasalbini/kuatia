"""Tests da GUI rodando headless (`QT_QPA_PLATFORM=offscreen`).

Valida estrutura do widget tree e estado inicial — sem testar comportamento,
porque #6 entrega só o esqueleto. Issues #7+ adicionam tests de interação.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QCheckBox,
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
    assert window.progress.isHidden() is True
    assert window.progress.value() == 0


def test_log_view_readonly_e_vazio(qapp: object) -> None:
    window = MainWindow()
    assert isinstance(window.log_view, QPlainTextEdit)
    assert window.log_view.isReadOnly()
    assert window.log_view.toPlainText() == ""


def test_combo_model_lista_modelos_disponiveis(qapp: object) -> None:
    """`model_combo` é um Fluent ComboBox (duck-typed: tem `itemData` e `count`)."""
    window = MainWindow()
    items = [window.model_combo.itemData(i) for i in range(window.model_combo.count())]
    names = [m.name for m in available_models()]
    assert items == names


def test_combo_device_populado_da_deteccao(qapp: object, monkeypatch: pytest.MonkeyPatch) -> None:
    """Dropdown de device vem de `detect_devices()`. NPU ganha sufixo de aviso."""
    monkeypatch.setattr(
        "kuatia.gui.main_window.detect_devices",
        lambda: ["CPU", "GPU", "NPU", "AUTO"],
    )
    monkeypatch.setattr("kuatia.gui.main_window.default_device", lambda _devices: "GPU")
    window = MainWindow()
    data = [window.device_combo.itemData(i) for i in range(window.device_combo.count())]
    texts = [window.device_combo.itemText(i) for i in range(window.device_combo.count())]
    assert data == ["CPU", "GPU", "NPU", "AUTO"]
    assert "NPU" in texts[2] and "INT8" in texts[2]
    assert window.device_combo.currentData() == "GPU"


def test_combo_device_default_cpu_quando_sem_gpu(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("kuatia.gui.main_window.detect_devices", lambda: ["CPU", "AUTO"])
    monkeypatch.setattr("kuatia.gui.main_window.default_device", lambda _devices: "CPU")
    window = MainWindow()
    assert window.device_combo.currentData() == "CPU"


def test_combo_task_mapeia_para_valor_interno(qapp: object) -> None:
    window = MainWindow()
    data = [window.task_combo.itemData(i) for i in range(window.task_combo.count())]
    assert data == ["transcribe", "translate"]


def test_combo_language_mapeia_para_codigo_whisper(qapp: object) -> None:
    window = MainWindow()
    data = [window.language_combo.itemData(i) for i in range(window.language_combo.count())]
    assert data == ["portuguese", "english", "spanish", "auto"]


def test_checkboxes_de_export_defaults(qapp: object) -> None:
    window = MainWindow()
    assert set(window.export_checks.keys()) == {"txt", "srt", "vtt", "docx"}
    assert window.export_checks["txt"].isChecked() is True
    assert window.export_checks["srt"].isChecked() is True
    assert window.export_checks["vtt"].isChecked() is False
    assert window.export_checks["docx"].isChecked() is True
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


# ---- Worker / botão Transcrever (issue #9) ----


def test_transcribe_sem_arquivo_mostra_mensagem(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem arquivo selecionado, click no botão exibe mensagem e não inicia worker."""
    msgs: list[str] = []
    monkeypatch.setattr(
        "kuatia.gui.main_window.MainWindow._show_message",
        lambda self, text: msgs.append(text),
    )
    window = MainWindow()
    assert window.selected_file is None
    window.transcribe_button.click()
    assert any("Escolha um arquivo" in m for m in msgs)
    assert window.is_running is False


def test_transcribe_modelo_nao_pronto_mostra_mensagem(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Modelo não cacheado: dispara mensagem (issue #11 vai fazer o dialog)."""
    from pathlib import Path

    msgs: list[str] = []
    monkeypatch.setattr(
        "kuatia.gui.main_window.MainWindow._show_message",
        lambda self, text: msgs.append(text),
    )
    monkeypatch.setattr("kuatia.gui.main_window.is_model_ready", lambda _name: False)
    monkeypatch.setattr("kuatia.gui.main_window.get_audio_duration", lambda _p: None)

    window = MainWindow()
    window.set_selected_file(Path("/tmp/foo.mp4"))
    window.transcribe_button.click()
    assert any("ainda não está pronto" in m for m in msgs)
    assert window.is_running is False


def test_transcribe_inicia_worker_e_botao_vira_cancelar(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Click no botão com tudo certo: cria worker, thread, transforma botão em Cancelar."""
    from pathlib import Path
    from unittest.mock import MagicMock

    monkeypatch.setattr("kuatia.gui.main_window.is_model_ready", lambda _name: True)
    monkeypatch.setattr(
        "kuatia.gui.main_window.model_dir",
        lambda name: Path("/tmp/cache") / name,
    )
    monkeypatch.setattr("kuatia.gui.main_window.get_audio_duration", lambda _p: 60.0)

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
    monkeypatch.setattr("kuatia.gui.main_window.make_transcriber", lambda: object())

    fake_worker = MagicMock()
    monkeypatch.setattr(
        "kuatia.gui.main_window.TranscribeWorker",
        lambda **_kwargs: fake_worker,
    )

    window = MainWindow()
    window.set_selected_file(Path("/tmp/foo.mp4"))
    window.transcribe_button.click()

    assert window.is_running is True
    assert window.transcribe_button.text() == "Cancelar"
    # janela não está show()ada nos tests; isHidden() reflete o setVisible(True)
    assert window.progress.isHidden() is False
    assert started == ["start"]


def test_on_worker_progress_atualiza_progress_bar(qapp: object) -> None:
    window = MainWindow()
    window._on_worker_progress(42)
    assert window.progress.value() == 42


def test_on_worker_finished_guarda_segments_e_volta_estado(qapp: object) -> None:
    from kuatia.core.transcriber import Segment

    window = MainWindow()
    window._enter_running_state()
    segs = [Segment(0.0, 1.0, "olá")]
    window._on_worker_finished(segs)
    assert window.last_segments == segs
    assert window.transcribe_button.text() == "Transcrever"
    assert window.progress.isHidden() is True


def test_on_worker_error_mostra_no_log_e_volta_estado(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    msgs: list[str] = []
    monkeypatch.setattr(
        "kuatia.gui.main_window.MainWindow._show_message",
        lambda self, text: msgs.append(text),
    )
    window = MainWindow()
    window._enter_running_state()
    window._on_worker_error("boom")
    assert "ERRO: boom" in window.log_view.toPlainText()
    assert any("boom" in m for m in msgs)
    assert window.transcribe_button.text() == "Transcrever"


def test_on_worker_cancelled_volta_estado(qapp: object) -> None:
    window = MainWindow()
    window._enter_running_state()
    window._on_worker_cancelled()
    assert "cancelada" in window.log_view.toPlainText().lower()
    assert window.transcribe_button.text() == "Transcrever"
    assert window.progress.isHidden() is True


# ---- Export checkboxes / abrir pasta (issue #10) ----


def test_transcribe_sem_formato_marcado_mostra_mensagem(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathlib import Path

    msgs: list[str] = []
    monkeypatch.setattr(
        "kuatia.gui.main_window.MainWindow._show_message",
        lambda self, text: msgs.append(text),
    )
    monkeypatch.setattr("kuatia.gui.main_window.get_audio_duration", lambda _p: None)
    monkeypatch.setattr("kuatia.gui.main_window.is_model_ready", lambda _name: True)

    window = MainWindow()
    window.set_selected_file(Path("/tmp/foo.mp4"))
    for cb in window.export_checks.values():
        cb.setChecked(False)
    window.transcribe_button.click()
    assert any("Marque pelo menos" in m for m in msgs)
    assert window.is_running is False


def test_open_folder_button_hidden_inicialmente(qapp: object) -> None:
    window = MainWindow()
    assert window.open_folder_button.isHidden() is True
    assert window.last_output_dir is None


def test_on_worker_finished_exporta_e_revela_botao(
    qapp: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from kuatia.core.transcriber import Segment

    monkeypatch.setattr("kuatia.gui.main_window.get_audio_duration", lambda _p: None)
    captured: dict[str, object] = {}

    def fake_export(
        segments: list[Segment],
        base_path: Path,
        formats: dict[str, bool],
        docx_meta: object = None,
    ) -> list[Path]:
        captured["segments"] = list(segments)
        captured["base"] = base_path
        captured["formats"] = dict(formats)
        return [base_path.with_suffix(".txt"), base_path.with_suffix(".srt")]

    monkeypatch.setattr("kuatia.gui.main_window.export_outputs", fake_export)

    input_path = tmp_path / "exemplo.mp4"
    input_path.write_bytes(b"")  # arquivo só pro Path.parent existir

    window = MainWindow()
    window.set_selected_file(input_path)
    segs = [Segment(0.0, 1.0, "olá")]
    window._on_worker_finished(segs)

    assert captured["segments"] == segs
    assert captured["base"] == input_path.parent / input_path.stem
    formats = captured["formats"]
    assert isinstance(formats, dict)
    assert formats["txt"] is True
    assert formats["docx"] is True  # default novo
    assert window.last_output_dir == input_path.parent
    assert window.open_folder_button.isHidden() is False


def test_on_worker_finished_export_oserror_loga_erro(
    qapp: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from kuatia.core.transcriber import Segment

    monkeypatch.setattr("kuatia.gui.main_window.get_audio_duration", lambda _p: None)

    def bad_export(*_args: object, **_kwargs: object) -> list[Path]:
        raise OSError("disco cheio")

    monkeypatch.setattr("kuatia.gui.main_window.export_outputs", bad_export)

    input_path = tmp_path / "exemplo.mp4"
    input_path.write_bytes(b"")

    window = MainWindow()
    window.set_selected_file(input_path)
    window._on_worker_finished([Segment(0.0, 1.0, "olá")])
    assert "ERRO ao salvar" in window.log_view.toPlainText()
    assert window.open_folder_button.isHidden() is True


def test_open_folder_clicked_chama_helper(
    qapp: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Path] = []

    def fake_open(path: Path) -> bool:
        calls.append(path)
        return True

    monkeypatch.setattr("kuatia.gui.main_window.open_in_file_manager", fake_open)

    window = MainWindow()
    window._last_output_dir = tmp_path
    window.open_folder_button.setVisible(True)
    window.open_folder_button.click()
    assert calls == [tmp_path]


def test_open_folder_falha_mostra_mensagem(
    qapp: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("kuatia.gui.main_window.open_in_file_manager", lambda _p: False)
    msgs: list[str] = []
    monkeypatch.setattr(
        "kuatia.gui.main_window.MainWindow._show_message",
        lambda self, text: msgs.append(text),
    )

    window = MainWindow()
    window._last_output_dir = tmp_path
    window.open_folder_button.setVisible(True)
    window.open_folder_button.click()
    assert any("Não consegui abrir" in m for m in msgs)
