"""Janela principal da GUI — visual Fluent Design.

Layout: drop area em card à esquerda, painel de opções à direita, progress bar
abaixo do split (escondida) e log read-only no rodapé. Widgets vêm de
`qfluentwidgets` pra ter a estética Win11 (Mica/Acrílico, transparência sutil,
tipografia Segoe UI Variable).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QMainWindow,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    CheckBox,
    ComboBox,
    FluentIcon,
    IconWidget,
    MessageBox,
    PlainTextEdit,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    SubtitleLabel,
    TitleLabel,
)

from kuatia.core.model_manager import (
    available_models,
    get_model_info,
    is_model_ready,
    model_dir,
)
from kuatia.core.transcriber import Segment
from kuatia.core.writers import DocxMeta
from kuatia.gui.devices import default_device, detect_devices, device_label
from kuatia.gui.download_worker import DownloadWorker
from kuatia.gui.file_picker import (
    FILE_DIALOG_FILTER,
    all_supported,
    format_duration_short,
    get_audio_duration,
    is_supported,
)
from kuatia.gui.first_run import (
    FirstRunChoice,
    FirstRunDialog,
    is_manual_model_dir_valid,
)
from kuatia.gui.output import (
    at_least_one_selected,
    export_outputs,
    open_in_file_manager,
    selected_formats,
)
from kuatia.gui.worker import TranscribeWorker, make_transcriber


class MainWindow(QMainWindow):
    """Janela principal — Fluent Design com drag-and-drop e controles modernos."""

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
        self.resize(1080, 720)
        self.setMinimumSize(880, 600)
        self.setAcceptDrops(True)
        self._selected_file: Path | None = None
        self._worker: TranscribeWorker | None = None
        self._worker_thread: QThread | None = None
        self._download_worker: DownloadWorker | None = None
        self._download_thread: QThread | None = None
        self._manual_model_dir: Path | None = None
        self._last_segments: list[Segment] = []
        self._last_output_dir: Path | None = None
        self._build_ui()
        self.transcribe_button.clicked.connect(self._on_transcribe_clicked)

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        header = TitleLabel("Kuatia")
        header_sub = CaptionLabel("Transcrição local com Whisper + OpenVINO")
        root.addWidget(header)
        root.addWidget(header_sub)
        root.addSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal, central)
        splitter.setHandleWidth(8)
        splitter.addWidget(self._build_drop_area())
        splitter.addWidget(self._build_options_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([580, 420])
        root.addWidget(splitter, stretch=1)

        self.progress = ProgressBar(central)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        self.progress.setFixedHeight(6)
        root.addWidget(self.progress)

        log_card = CardWidget(central)
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 12, 16, 16)
        log_layout.setSpacing(8)
        log_header = QHBoxLayout()
        log_header.setSpacing(8)
        log_icon = IconWidget(FluentIcon.MESSAGE, log_card)
        log_icon.setFixedSize(16, 16)
        log_header.addWidget(log_icon)
        log_header.addWidget(SubtitleLabel("Log"))
        log_header.addStretch(1)
        log_layout.addLayout(log_header)
        self.log_view = PlainTextEdit(log_card)
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Logs da transcrição aparecerão aqui.")
        self.log_view.setMaximumBlockCount(2000)
        self.log_view.setMinimumHeight(140)
        log_layout.addWidget(self.log_view)
        root.addWidget(log_card, stretch=0)

        self.setCentralWidget(central)

    def _build_drop_area(self) -> QWidget:
        self.drop_frame = CardWidget()
        self.drop_frame.setObjectName("dropArea")
        self.drop_frame.setMinimumSize(380, 280)
        self.drop_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._apply_drop_style(state="idle")

        layout = QVBoxLayout(self.drop_frame)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(10)

        self.drop_icon = IconWidget(FluentIcon.CLOUD_DOWNLOAD, self.drop_frame)
        self.drop_icon.setFixedSize(56, 56)
        icon_wrap = QHBoxLayout()
        icon_wrap.addStretch(1)
        icon_wrap.addWidget(self.drop_icon)
        icon_wrap.addStretch(1)
        layout.addLayout(icon_wrap)
        layout.addSpacing(6)

        self.drop_title = SubtitleLabel("Solte um arquivo aqui")
        self.drop_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.drop_subtitle = CaptionLabel(
            "…ou clique em Procurar (mp4, mp3, wav, m4a, flac, ogg, webm)"
        )
        self.drop_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_subtitle.setWordWrap(True)

        self.browse_button = PushButton(FluentIcon.FOLDER, "Procurar…")
        self.browse_button.setMinimumHeight(34)
        self.browse_button.clicked.connect(self._on_browse_clicked)

        layout.addWidget(self.drop_title)
        layout.addWidget(self.drop_subtitle)
        layout.addSpacing(14)
        layout.addWidget(self.browse_button, alignment=Qt.AlignmentFlag.AlignCenter)
        widget: QWidget = self.drop_frame
        return widget

    def _build_options_panel(self) -> QWidget:
        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        # Card de opções de transcrição
        opts_card = CardWidget(panel)
        opts_layout = QVBoxLayout(opts_card)
        opts_layout.setContentsMargins(20, 16, 20, 20)
        opts_layout.setSpacing(10)

        opts_header = QHBoxLayout()
        opts_header.setSpacing(8)
        opts_icon = IconWidget(FluentIcon.SETTING, opts_card)
        opts_icon.setFixedSize(16, 16)
        opts_header.addWidget(opts_icon)
        opts_header.addWidget(SubtitleLabel("Opções"))
        opts_header.addStretch(1)
        opts_layout.addLayout(opts_header)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.model_combo = ComboBox()
        for info in available_models():
            label = f"{info.name} (~{info.size_mb} MB)"
            self.model_combo.addItem(label, userData=info.name)
        form.addRow(BodyLabel("Modelo"), self.model_combo)

        self.device_combo = ComboBox()
        devices = detect_devices()
        for dev in devices:
            self.device_combo.addItem(device_label(dev), userData=dev)
        chosen = default_device(devices)
        idx = self.device_combo.findData(chosen)
        if idx >= 0:
            self.device_combo.setCurrentIndex(idx)
        form.addRow(BodyLabel("Device"), self.device_combo)

        self.language_combo = ComboBox()
        for label, value in self.LANGUAGE_CHOICES:
            self.language_combo.addItem(label, userData=value)
        form.addRow(BodyLabel("Idioma"), self.language_combo)

        self.task_combo = ComboBox()
        for label, value in self.TASK_CHOICES:
            self.task_combo.addItem(label, userData=value)
        form.addRow(BodyLabel("Tarefa"), self.task_combo)

        opts_layout.addLayout(form)
        outer.addWidget(opts_card)

        # Card de formatos de saída
        export_card = CardWidget(panel)
        export_layout_v = QVBoxLayout(export_card)
        export_layout_v.setContentsMargins(20, 16, 20, 20)
        export_layout_v.setSpacing(10)

        export_header = QHBoxLayout()
        export_header.setSpacing(8)
        export_icon = IconWidget(FluentIcon.SAVE, export_card)
        export_icon.setFixedSize(16, 16)
        export_header.addWidget(export_icon)
        export_header.addWidget(SubtitleLabel("Formatos de saída"))
        export_header.addStretch(1)
        export_layout_v.addLayout(export_header)

        export_row = QHBoxLayout()
        export_row.setSpacing(14)
        self.export_checks: dict[str, CheckBox] = {}
        for fmt, default_on in (("txt", True), ("srt", True), ("vtt", False), ("docx", True)):
            cb = CheckBox(f".{fmt}")
            cb.setChecked(default_on)
            export_row.addWidget(cb)
            self.export_checks[fmt] = cb
        export_row.addStretch(1)
        export_layout_v.addLayout(export_row)

        outer.addWidget(export_card)

        # Ação primária
        self.transcribe_button = PrimaryPushButton(FluentIcon.PLAY_SOLID, "Transcrever")
        self.transcribe_button.setMinimumHeight(40)
        outer.addWidget(self.transcribe_button)

        self.open_folder_button = PushButton(FluentIcon.FOLDER_ADD, "Abrir pasta de saída")
        self.open_folder_button.setMinimumHeight(34)
        self.open_folder_button.setVisible(False)
        self.open_folder_button.clicked.connect(self._on_open_folder_clicked)
        outer.addWidget(self.open_folder_button)

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
            "idle": "rgba(120, 120, 120, 120)",
            "accept": "rgba(0, 120, 212, 220)",  # Win11 accent blue
            "reject": "rgba(196, 43, 28, 220)",
        }.get(state, "rgba(120, 120, 120, 120)")
        self.drop_frame.setStyleSheet(
            f"#dropArea {{ border: 2px dashed {color}; border-radius: 12px;}}"
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
        self.drop_icon.setIcon(FluentIcon.MUSIC)
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

        if not at_least_one_selected(self._formats_state()):
            self._show_message("Marque pelo menos um formato de saída antes de transcrever.")
            return

        model_name = self.model_combo.currentData()
        target_dir = self._resolve_model_dir(model_name)
        if target_dir is None:
            self._show_message(
                f"O modelo {model_name!r} ainda não está pronto.\n\n"
                "Reabra o app pra ver o diálogo de download, ou aponte uma pasta "
                "com modelo OpenVINO IR via 'Apontar modelo manualmente'."
            )
            return
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
        self.transcribe_button.setIcon(FluentIcon.PAUSE)
        self.transcribe_button.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.browse_button.setEnabled(False)
        self.open_folder_button.setVisible(False)

    def _leave_running_state(self) -> None:
        self.transcribe_button.setText("Transcrever")
        self.transcribe_button.setIcon(FluentIcon.PLAY_SOLID)
        self.transcribe_button.setEnabled(True)
        self.progress.setVisible(False)
        self.progress.setValue(0)
        self.browse_button.setEnabled(True)

    def _on_worker_progress(self, percent: int) -> None:
        self.progress.setValue(percent)

    def _on_worker_finished(self, segments: list[Segment]) -> None:
        self._last_segments = segments
        self.append_log(f"Transcrição concluída: {len(segments)} segments.")
        if self._selected_file is not None:
            self._export_and_record(segments, self._selected_file)
        self._leave_running_state()

    def _export_and_record(self, segments: list[Segment], input_path: Path) -> None:
        formats = self._formats_state()
        if not any(formats.values()):
            self.append_log("Nenhum formato marcado — pulando export.")
            return
        out_dir = input_path.parent
        base = out_dir / input_path.stem
        meta = DocxMeta(
            input_name=input_path.name,
            duration_sec=None,
            model_name=self.model_combo.currentData(),
            generated_at=datetime.now(),
        )
        try:
            generated = export_outputs(segments, base, formats, docx_meta=meta)
        except OSError as exc:
            self.append_log(f"ERRO ao salvar arquivos: {exc}")
            return
        for p in generated:
            self.append_log(f"saída: {p}")
        self.append_log(
            f"Formatos exportados ({len(generated)}): "
            f"{', '.join('.' + f for f in selected_formats(formats))}."
        )
        self._last_output_dir = out_dir
        self.open_folder_button.setVisible(True)

    def _formats_state(self) -> dict[str, bool]:
        return {fmt: cb.isChecked() for fmt, cb in self.export_checks.items()}

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
        box = MessageBox("Kuatia", text, self)
        box.cancelButton.hide()
        box.exec()

    # ---- First-run / download de modelo ----

    def check_first_run(self) -> None:
        """Verifica se o modelo default está pronto; se não, mostra dialog modal."""
        model_name = self.model_combo.currentData()
        if model_name is None:
            return
        if is_model_ready(model_name) or self._manual_model_dir is not None:
            return

        info = get_model_info(model_name)
        dialog = FirstRunDialog(model_name=info.name, size_mb=info.size_mb, parent=self)
        dialog.exec()
        choice = dialog.choice

        if choice == FirstRunChoice.DOWNLOAD:
            self._start_download(model_name)
        elif choice == FirstRunChoice.MANUAL:
            self._pick_manual_model_dir()
        else:
            self._mark_model_not_loaded(model_name)

    def _mark_model_not_loaded(self, model_name: str) -> None:
        self.append_log(
            f"Modelo {model_name!r} não carregado. "
            "Use 'Apontar modelo manualmente' ou reabra o app pra baixar."
        )
        self.transcribe_button.setEnabled(False)
        self.transcribe_button.setToolTip(
            "Modelo ainda não carregado — pule o dialog de 1º run pra usar."
        )

    def _pick_manual_model_dir(self) -> None:
        path_str = QFileDialog.getExistingDirectory(
            self,
            "Selecionar pasta do modelo OpenVINO IR",
            str(Path.home()),
        )
        if not path_str:
            self._mark_model_not_loaded(self.model_combo.currentData() or "?")
            return
        candidate = Path(path_str)
        if not is_manual_model_dir_valid(candidate):
            self._show_message(
                f"A pasta {candidate} não parece conter um modelo OpenVINO IR válido "
                "(faltam arquivos `openvino_*.xml`). Tente outra pasta."
            )
            self._mark_model_not_loaded(self.model_combo.currentData() or "?")
            return
        self._manual_model_dir = candidate
        self.append_log(f"Modelo manual registrado: {candidate}")
        self.transcribe_button.setEnabled(True)
        self.transcribe_button.setToolTip("")

    def _start_download(self, model_name: str) -> None:
        worker = DownloadWorker(model_name)
        thread = QThread(self)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._on_worker_progress)
        worker.log_line.connect(self.append_log)
        worker.finished.connect(self._on_download_finished)
        worker.error.connect(self._on_download_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(self._teardown_download)

        self._download_worker = worker
        self._download_thread = thread
        self.transcribe_button.setEnabled(False)
        self.transcribe_button.setToolTip("Aguardando download do modelo terminar.")
        self.progress.setVisible(True)
        self.progress.setValue(0)
        thread.start()

    def _on_download_finished(self, path: Path) -> None:
        self.append_log(f"Modelo baixado e pronto: {path}")
        self.progress.setVisible(False)
        self.progress.setValue(0)
        self.transcribe_button.setEnabled(True)
        self.transcribe_button.setToolTip("")

    def _on_download_error(self, msg: str) -> None:
        self.append_log(f"ERRO no download: {msg}")
        self._show_message(f"Falha ao baixar modelo:\n\n{msg}")
        self.progress.setVisible(False)
        self.progress.setValue(0)
        self._mark_model_not_loaded(self.model_combo.currentData() or "?")

    def _teardown_download(self) -> None:
        if self._download_thread is not None:
            self._download_thread.deleteLater()
        if self._download_worker is not None:
            self._download_worker.deleteLater()
        self._download_worker = None
        self._download_thread = None

    def _resolve_model_dir(self, model_name: str) -> Path | None:
        """Retorna o path do modelo (manual ou cache). `None` se nada está pronto."""
        if self._manual_model_dir is not None:
            return self._manual_model_dir
        if is_model_ready(model_name):
            return model_dir(model_name)
        return None

    @property
    def manual_model_dir(self) -> Path | None:
        return self._manual_model_dir

    def _on_open_folder_clicked(self) -> None:
        if self._last_output_dir is None:
            return
        ok = open_in_file_manager(self._last_output_dir)
        if not ok:
            self._show_message(f"Não consegui abrir {self._last_output_dir}.")

    @property
    def last_segments(self) -> list[Segment]:
        """Último resultado emitido por `finished` — vazio se nada rodou ainda."""
        return list(self._last_segments)

    @property
    def last_output_dir(self) -> Path | None:
        return self._last_output_dir
