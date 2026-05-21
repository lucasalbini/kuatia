"""Entry point da GUI Kuatia — cria `QApplication` e abre a janela principal."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from kuatia.gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Kuatia")
    app.setOrganizationName("Kuatia")
    window = MainWindow()
    window.show()
    window.check_first_run()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
