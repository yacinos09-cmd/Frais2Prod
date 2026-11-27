"""
Point d'entrée de l'application « Gestion de Production ».

    python main.py

Variables d'environnement utiles :
    GESTION_PROD_DB  chemin d'une base alternative (tests, démonstration…)
"""
from __future__ import annotations

import logging
import os
import sys
import traceback

# Rend les modules du projet importables, y compris une fois packagé.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import QLocale  # noqa: E402
from PySide6.QtGui import QFont, QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from database import Database  # noqa: E402
from styles import STYLESHEET  # noqa: E402
from ui_main import MainWindow  # noqa: E402
from utils import (  # noqa: E402
    APP_AUTHOR, APP_DISPLAY_NAME, APP_NAME, APP_VERSION, default_db_path, resource_path,
    user_data_dir,
)


def _setup_logging() -> None:
    log_file = user_data_dir() / "application.log"
    logging.basicConfig(
        filename=str(log_file), level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s : %(message)s",
    )


def _install_excepthook() -> None:
    """Affiche les erreurs inattendues (utile pour un .exe/.app sans console)."""
    def hook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        logging.error("Erreur non gérée :\n%s", text)
        app = QApplication.instance()
        if app is not None:
            box = QMessageBox(QMessageBox.Critical, "Erreur inattendue",
                              f"{exc_type.__name__} : {exc}", QMessageBox.Ok)
            box.setDetailedText(text)
            box.exec()
        else:
            sys.__excepthook__(exc_type, exc, tb)
    sys.excepthook = hook


def _platform_font() -> QFont:
    if sys.platform == "darwin":
        return QFont(".AppleSystemUIFont", 13)
    if sys.platform.startswith("win"):
        return QFont("Segoe UI", 10)
    return QFont("Sans Serif", 10)


def main() -> int:
    _setup_logging()
    _install_excepthook()

    QLocale.setDefault(QLocale(QLocale.French, QLocale.France))
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_DISPLAY_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_AUTHOR)
    app.setStyle("Fusion")
    app.setFont(_platform_font())
    app.setStyleSheet(STYLESHEET)
    icon = resource_path(os.path.join("assets", "icon.png"))
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))

    db_path = default_db_path()
    logging.info("Ouverture de la base : %s", db_path)
    db = Database(db_path)
    if db.is_new:
        db.load_demo_data()  # premier lancement : données de démonstration

    window = MainWindow(db)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
