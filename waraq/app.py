from __future__ import annotations

import atexit
import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QLocale, Qt, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWebEngineQuick import QtWebEngineQuick

from .bridge import Bridge
from .database import Library
from .image_provider import PageImageProvider
from .paths import application_data_dir, resource_path
from .secrets import create_secret_store


def _configure_managed_lifecycle(application: QGuiApplication) -> None:
    """Let the command-file process manager stop this instance cleanly."""
    runtime_value = os.environ.get("WARRAQ_RUNTIME_DIR")
    if not runtime_value:
        return

    runtime_dir = Path(runtime_value).resolve()
    state_file = runtime_dir / "process.json"
    stop_file = runtime_dir / "stop-requested"
    process_id = os.getpid()

    def remove_runtime_files() -> None:
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            state = {}
        if state.get("pid") == process_id:
            state_file.unlink(missing_ok=True)
        stop_file.unlink(missing_ok=True)

    def stop_if_requested() -> None:
        if stop_file.exists():
            application.quit()

    stop_timer = QTimer(application)
    stop_timer.setInterval(250)
    stop_timer.timeout.connect(stop_if_requested)
    stop_timer.start()
    atexit.register(remove_runtime_files)
    application.aboutToQuit.connect(remove_runtime_files)


def main() -> int:
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    QGuiApplication.setApplicationName("ورّاق")
    QGuiApplication.setOrganizationName("Warraq")
    QGuiApplication.setOrganizationDomain("waraq.app")
    QtWebEngineQuick.initialize()
    application = QGuiApplication(sys.argv)
    _configure_managed_lifecycle(application)
    application.setLayoutDirection(Qt.RightToLeft)
    # The layout stays RTL, while counters and page numbers use Latin digits.
    QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedStates))

    library = Library(application_data_dir())
    bridge = Bridge(library, create_secret_store())
    engine = QQmlApplicationEngine()
    engine.addImageProvider("pages", PageImageProvider(library))
    engine.rootContext().setContextProperty("App", bridge)
    engine.load(QUrl.fromLocalFile(str(resource_path("qml", "Main.qml"))))
    if not engine.rootObjects():
        return 1
    return application.exec()
