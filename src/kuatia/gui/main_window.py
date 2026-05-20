"""Janela principal da GUI.

Layout: área de drop à esquerda (drag-and-drop + browse), painel de opções
à direita, progress bar escondida abaixo do split, e log read-only no rodapé.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from kuatia.core.model_manager import available_models, is_model_ready, model_dir
from kuatia.core.transcriber import Segment
from kuatia.gui.devices import default_device, detect_devices, device_label
from kuatia.gui.file_picker import (
    FILE_DIALOG_FILTER,
    all_supported,
    format_duration_short,
    get_audio_duration,
    is_supported,
)
from kuatia.gui.worker import TranscribeWorker, make_transcriber


class MainWindow(QMainWindow):
    """Janela principal — drag-and-drop, picker e controles de transcrição."""

    LANGUAGE_CHOICES = (
        ("Português", "portuguese"),
        ("Inglês", "english"),
        ("Espanhol", "spanish"),
        ("Detectar (auto)", "auto"),
    )
    TASK_CHOICES = (
        ("Transcrever", "transcribe"),
        ("Traduzir (→ inglês)", "translate"),
    )

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Kuatia — Transcrição local")
        self.resize(960, 640)
        self.setAcceptDrops(True)
        self._selected_file: Path | None = None
        self._worker: TranscribeWorker | None = None
        self._worker_thread: QThread | None = None
        self._last_segments: list[Segment] = []
        self._build_ui()
        self.transcribe_button.clicked.connect(self._on_transcribe_clicked)

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal, central)
        splitter.addWidget(self._build_drop_area())
        splitter.addWidget(self._build_options_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, stretch=1)

        self.progress = QProgressBar(central)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        log_box = QGroupBox("Log", central)
        log_layout = QVBoxLayout(log_box)
        log_layout.setContentsMargins(8, 16, 8, 8)
        self.log_view = QPlainTextEdit(log_box)
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Logs da transcrição aparecerão aqui.")
        self.log_view.setMaximumBlockCount(2000)
        log_layout.addWidget(self.log_view)
        root.addWidget(log_box, stretch=0)

        self.setCentralWidget(central)

    def _build_drop_area(self) -> QWidget:
        self.drop_frame = QFrame()
        self.drop_frame.setObjectName("dropArea")
        self.drop_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.drop_frame.setMinimumSize(360, 240)
        self.drop_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._apply_drop_style(state="idle")

        layout = QVBoxLayout(self.drop_frame)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.drop_title = QLabel("Solte um arquivo aqui")
        self.drop_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self.drop_title.font()
        font.setPointSize(16)
        font.setBold(True)
        self.drop_title.setFont(font)

        self.drop_subtitle = QLabel("…ou clique em Procurar (mp4, mp3, wav, m4a, flac, ogg, webm)")
        self.drop_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_subtitle.setStyleSheet("color: palette(mid);")
        self.drop_subtitle.setWordWrap(True)

        self.browse_button = QPushButton("Procurar…")
        self.browse_button.setMinimumHeight(32)
        self.browse_button.clicked.connect(self._on_browse_clicked)

        layout.addWidget(self.drop_title)
        layout.addWidget(self.drop_subtitle)
        layout.addSpacing(12)
        layout.addWidget(self.browse_button, alignment=Qt.AlignmentFlag.AlignCenter)
        return self.drop_frame

    def _build_options_panel(self) -> QWidget:
        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        opts = QGroupBox("Opções", panel)
        form = QFormLayout(opts)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.model_combo = QComboBox()
        for info in available_models():
            label = f"{info.name} (~{info.size_mb} MB)"
            self.model_combo.addItem(label, userData=info.name)
        form.addRow("Modelo:", self.model_combo)

        self.device_combo = QComboBox()
        devices = detect_devices()
        for dev in devices:
            self.device_combo.addItem(device_label(dev), userData=dev)
        chosen = default_device(devices)
        idx = self.device_combo.findData(chosen)
        if idx >= 0:
            self.device_combo.setCurrentIndex(idx)
        form.addRow("Device:", self.device_combo)

        self.language_combo = QComboBox()
        for label, value in self.LANGUAGE_CHOICES:
            self.language_combo.addItem(label, userData=value)
        form.addRow("Idioma:", self.language_combo)

        self.task_combo = QComboBox()
        for label, value in self.TASK_CHOICES:
            self.task_combo.addItem(label, userData=value)
        form.addRow("Tarefa:", self.task_combo)

        outer.addWidget(opts)

        export_box = QGroupBox("Formatos de saída", panel)
        export_layout = QHBoxLayout(export_box)
        self.export_checks: dict[str, QCheckBox] = {}
        for fmt, default_on in (("txt", True), ("srt", True), ("vtt", False), ("docx", False)):
            cb = QCheckBox(f".{fmt}")
            cb.setChecked(default_on)
            export_layout.addWidget(cb)
            self.export_checks[fmt] = cb
        export_layout.addStretch(1)
        outer.addWidget(export_box)

        self.transcribe_button = QPushButton("Transcrever")
        self.transcribe_button.setMinimumHeight(36)
        outer.addWidget(self.transcribe_button)

        outer.addStretch(1)
        return panel

    # ---- Drag-and-drop ----

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 (Qt API)
        paths = self._paths_from_event(event)
        if paths and all_supported(paths):
            event.acceptProposedAction()
            self._apply_drop_style(state="accept")
        else:
            event.ignore()
            if paths:
                self._apply_drop_style(state="reject")

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802 (Qt API)
        del event  # apenas restauramos o estilo
        self._apply_drop_style(state="idle")

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 (Qt API)
        paths = self._paths_from_event(event)
        if not paths or not all_supported(paths):
            event.ignore()
            self._apply_drop_style(state="idle")
            return
        event.acceptProposedAction()
        self._apply_drop_style(state="idle")
        self.set_selected_file(paths[0])

    @staticmethod
    def _paths_from_event(event: QDragEnterEvent | QDropEvent) -> list[Path]:
        mime = event.mimeData()
        if not mime.hasUrls():
            return []
        out: list[Path] = []
        for url in mime.urls():
            local = url.toLocalFile()
            if local:
                out.append(Path(local))
        return out

    def _apply_drop_style(self, state: str) -> None:
        """Atualiza a borda da área de drop conforme o estado da operação."""
        color = {
            "idle": "palette(mid)",
            "accept": "palette(highlight)",
            "reject": "#c0392b",
        }.get(state, "palette(mid)")
        self.drop_frame.setStyleSheet(
            f"#dropArea {{"
            f" border: 2px dashed {color};"
            f" border-radius: 12px;"
            f" background-color: palette(alternate-base);"
            f"}}"
        )

    # ---- Browse + estado do arquivo ----

    def _on_browse_clicked(self) -> None:
        start_dir = (
            str(self._selected_file.parent) if self._selected_file is not None else str(Path.home())
        )
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Escolher arquivo de áudio/vídeo",
            start_dir,
            FILE_DIALOG_FILTER,
        )
        if not path_str:
            return
        path = Path(path_str)
        if not is_supported(path):
            self.append_log(f"Ignorado: {path.name} (extensão não suportada).")
            return
        self.set_selected_file(path)

    def set_selected_file(self, path: Path) -> None:
        """Atualiza o estado interno e a UI da drop area com o arquivo escolhido."""
        self._selected_file = path
        duration = get_audio_duration(path)
        self.drop_title.setText(path.name)
        if duration is None:
            self.drop_subtitle.setText(
                "Duração: --:-- (ffprobe ausente ou arquivo não inspecionável)"
            )
        else:
            self.drop_subtitle.setText(f"Duração: {format_duration_short(duration)}")
        self.browse_button.setText("Trocar arquivo…")
        self.append_log(f"selecionado: {path}")

    @property
    def selected_file(self) -> Path | None:
        return self._selected_file

    # ---- Utilitário ----

    def append_log(self, message: str) -> None:
        """Linha nova no log da UI. Usado por DnD, browse e worker."""
        self.log_view.appendPlainText(message)

    # ---- Transcribe button / worker thread ----

    @property
    def is_running(self) -> bool:
        return self._worker is not None

    def _on_transcribe_clicked(self) -> None:
        if self.is_running:
            self._request_cancel()
            return

        if self._selected_file is None:
            self._show_message("Escolha um arquivo de áudio/vídeo antes de transcrever.")
            return

        model_name = self.model_combo.currentData()
        if not is_model_ready(model_name):
            self._show_message(
                f"O modelo {model_name!r} ainda não foi baixado.\n\n"
                "Esse passo será automatizado pelo dialog da issue #11. Por enquanto, "
                "rode `kuatia-transcribe --model " + model_name + " <arquivo>` uma vez "
                "no CLI pra cachear o modelo, ou aponte um diretório existente."
            )
            return

        target_dir = model_dir(model_name)
        device = self.device_combo.currentData() or "CPU"
        language = self.language_combo.currentData() or "portuguese"
        task = self.task_combo.currentData() or "transcribe"

        self._start_worker(self._selected_file, target_dir, device, language, task)

    def _start_worker(
        self,
        input_path: Path,
        target_model_dir: Path,
        device: str,
        language: str,
        task: str,
    ) -> None:
        transcriber = make_transcriber()
        worker = TranscribeWorker(
            transcriber=transcriber,
            input_path=input_path,
            model_dir=target_model_dir,
            device=device,
            language=language,
            task=task,
        )
        thread = QThread(self)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._on_worker_progress)
        worker.log_line.connect(self.append_log)
        worker.finished.connect(self._on_worker_finished)
        worker.error.connect(self._on_worker_error)
        worker.cancelled.connect(self._on_worker_cancelled)
        # Limpa thread em qualquer terminação.
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        thread.finished.connect(self._teardown_worker)

        self._worker = worker
        self._worker_thread = thread
        self._enter_running_state()
        thread.start()

    def _request_cancel(self) -> None:
        if self._worker is not None:
            self.append_log("Solicitando cancelamento…")
            self._worker.request_cancel()
            self.transcribe_button.setEnabled(False)

    def _enter_running_state(self) -> None:
        self.transcribe_button.setText("Cancelar")
        self.transcribe_button.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.browse_button.setEnabled(False)

    def _leave_running_state(self) -> None:
        self.transcribe_button.setText("Transcrever")
        self.transcribe_button.setEnabled(True)
        self.progress.setVisible(False)
        self.progress.setValue(0)
        self.browse_button.setEnabled(True)

    def _on_worker_progress(self, percent: int) -> None:
        self.progress.setValue(percent)

    def _on_worker_finished(self, segments: list[Segment]) -> None:
        self._last_segments = segments
        self.append_log(f"Transcrição concluída: {len(segments)} segments.")
        self._leave_running_state()

    def _on_worker_error(self, message: str) -> None:
        self.append_log(f"ERRO: {message}")
        self._show_message(f"Falha na transcrição:\n\n{message}")
        self._leave_running_state()

    def _on_worker_cancelled(self) -> None:
        self.append_log("Transcrição cancelada.")
        self._leave_running_state()

    def _teardown_worker(self) -> None:
        if self._worker_thread is not None:
            self._worker_thread.deleteLater()
        if self._worker is not None:
            self._worker.deleteLater()
        self._worker = None
        self._worker_thread = None

    def _show_message(self, text: str) -> None:
        QMessageBox.information(self, "Kuatia", text)

    @property
    def last_segments(self) -> list[Segment]:
        """Último resultado emitido por `finished` — vazio se nada rodou ainda."""
        return list(self._last_segments)
