"""Entry point da GUI Kuatia — cria `QApplication`, aplica tema Fluent e abre a janela."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme, setThemeColor

from kuatia.gui.main_window import MainWindow

# Win11 accent blue — bate com o tema Fluent default do sistema.
_ACCENT_COLOR = "#0078d4"


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Kuatia")
    app.setOrganizationName("Kuatia")

    # Tema segue o SO (claro/escuro). setThemeColor define a cor de acento dos
    # PrimaryPushButton, ProgressBar, focus rings etc.
    setTheme(Theme.AUTO)
    setThemeColor(_ACCENT_COLOR)

    window = MainWindow()
    window.show()
    window.check_first_run()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
