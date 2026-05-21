"""Mede o tempo de cada etapa do boot da GUI.

Uso (no Windows, raiz do repo):
    uv run python bench_startup.py
"""

from __future__ import annotations

import sys
import time

t0 = time.perf_counter()


def stamp(label: str) -> None:
    print(f"[{time.perf_counter() - t0:5.2f}s] {label}")


stamp("inicio")

from PySide6.QtWidgets import QApplication  # noqa: E402

stamp("PySide6 importado")

from qfluentwidgets import Theme, setTheme  # noqa: E402

stamp("qfluentwidgets importado")

from kuatia.gui.main_window import MainWindow  # noqa: E402

stamp("MainWindow importado")

app = QApplication(sys.argv)
stamp("QApplication criado")

setTheme(Theme.AUTO)
stamp("tema setado")

w = MainWindow()
stamp("MainWindow construído")

w.show()
stamp("janela visível")

print(f"\nTOTAL: {time.perf_counter() - t0:.2f}s")
# Não chamamos app.exec() — script termina após medir.
