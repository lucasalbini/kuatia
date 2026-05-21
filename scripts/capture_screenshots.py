"""Captura screenshots da GUI pros docs.

Roda headless (`QT_QPA_PLATFORM=offscreen`) e salva PNGs em `docs/images/`.
Captura múltiplas telas em light + dark mode.

Uso:
    QT_QPA_PLATFORM=offscreen uv run python scripts/capture_screenshots.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Headless: necessário antes de importar PySide6.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from qfluentwidgets import Theme, setTheme, setThemeColor  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "images"


def _apply_dark_palette(app: QApplication) -> None:
    """Força um palette escuro no app pra que o background da janela
    case com o tema Fluent dark em modo offscreen (que não tem composição
    de Mica/Acrílico do Windows)."""
    palette = QPalette()
    bg = QColor(32, 32, 32)
    base = QColor(43, 43, 43)
    text = QColor(245, 245, 245)
    mid = QColor(160, 160, 160)
    palette.setColor(QPalette.ColorRole.Window, bg)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(50, 50, 50))
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, base)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.Mid, mid)
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 212))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
    app.setPalette(palette)


def _apply_light_palette(app: QApplication) -> None:
    palette = app.style().standardPalette()
    app.setPalette(palette)


def _settle(app: QApplication, cycles: int = 3) -> None:
    for _ in range(cycles):
        app.processEvents()


def _save(window: object, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{name}.png"
    pixmap = window.grab()  # type: ignore[attr-defined]
    pixmap.save(str(out))
    size_kb = out.stat().st_size / 1024
    print(f"  -> {out} ({size_kb:.1f} KB)")


def _simulate_drop(window: object, fake_path: str) -> None:
    """Aciona o fluxo de set_selected_file sem precisar de arquivo real."""
    from pathlib import Path as _P

    # Stub get_audio_duration pra evitar shell out ao ffprobe inexistente.
    from kuatia.gui import main_window as mw_module

    mw_module.get_audio_duration = lambda _p: 327.5  # 5m 27s
    window.set_selected_file(_P(fake_path))  # type: ignore[attr-defined]


def _populate_log(window: object) -> None:
    """Mete algumas linhas de log fake pra a screenshot mostrar atividade."""
    window.append_log("Carregando áudio de reuniao-equipe.mp4…")  # type: ignore[attr-defined]
    window.append_log("audio: 5.5 min, 16000 Hz, 5256000 samples (decodificado em 1.8s)")  # type: ignore[attr-defined]
    window.append_log("Carregando modelo em GPU…")  # type: ignore[attr-defined]
    window.append_log("modelo: pronto em 4.2s")  # type: ignore[attr-defined]
    window.append_log("transcrição: iniciando (task=transcribe, lang=portuguese)")  # type: ignore[attr-defined]
    window.append_log("transcrição: 47 segments (de 49 chunks) em 38.4s (8.61x realtime)")  # type: ignore[attr-defined]
    window.append_log("Transcrição concluída: 47 segments.")  # type: ignore[attr-defined]


def capture_in_theme(theme: Theme, suffix: str) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    assert isinstance(app, QApplication)
    setTheme(theme)
    setThemeColor("#0078d4")
    if theme == Theme.DARK:
        _apply_dark_palette(app)
    else:
        _apply_light_palette(app)

    from kuatia.gui.main_window import MainWindow

    print(f"\n== Theme: {theme.name} ==")

    # 1. Estado inicial
    w = MainWindow()
    w.resize(1080, 720)
    w.show()
    _settle(app)
    _save(w, f"01-initial-{suffix}")

    # 2. Com arquivo selecionado + log preenchido + progress visível
    _simulate_drop(w, "/Users/lucas/Videos/reuniao-equipe.mp4")
    w.progress.setVisible(True)
    w.progress.setValue(64)
    _populate_log(w)
    _settle(app)
    _save(w, f"02-transcribing-{suffix}")

    # 3. Estado finalizado (sem progress, com botão "abrir pasta" visível)
    w.progress.setVisible(False)
    w._last_output_dir = Path("/Users/lucas/Videos")  # noqa: SLF001
    w.open_folder_button.setVisible(True)
    _settle(app)
    _save(w, f"03-finished-{suffix}")

    # 4. First-run dialog
    from kuatia.gui.first_run import FirstRunDialog

    dialog = FirstRunDialog(model_name="large-v3", size_mb=3000, parent=w)
    dialog.show()
    _settle(app)
    _save(dialog, f"04-first-run-{suffix}")
    dialog.close()
    w.close()


def main() -> int:
    print(f"Output: {OUT_DIR}")
    capture_in_theme(Theme.LIGHT, "light")
    capture_in_theme(Theme.DARK, "dark")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
