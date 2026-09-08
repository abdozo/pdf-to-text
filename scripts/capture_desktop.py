"""Capture representative Qt Quick screens for local visual QA."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
os.environ.setdefault("QSG_RHI_BACKEND", "software")

from PySide6.QtCore import QObject, QPointF, QLocale, QTimer, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from PySide6.QtWebEngineQuick import QtWebEngineQuick

from waraq.bridge import Bridge
from waraq.database import Library
from waraq.image_provider import PageImageProvider
from waraq.models import Box, ExtractedLine, ExtractedPage, ExtractedRegion
from waraq.paths import resource_path
from waraq.secrets import MemorySecretStore


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tmp" / "qa"


QtWebEngineQuick.initialize()


def main() -> int:
    temporary = Path(tempfile.mkdtemp(prefix="waraq-ui-"))
    library = Library(temporary)
    source = ROOT / "tmp" / "qa" / "synthetic-arabic.pdf"
    if not source.exists():
        raise SystemExit("Missing tmp/qa/synthetic-arabic.pdf")
    book = library.add_book(source, "فتح الباري بشرح صحيح البخاري")
    page = ExtractedPage(
        is_blank=False,
        printed_page="١٢٣",
        regions=[
            ExtractedRegion(kind="heading", source="printed", column=0, order=0, box=Box(x=.2,y=.12,w=.6,h=.25), lines=[ExtractedLine(text="\n  حم  \n", box=Box(x=.28,y=.12,w=.44,h=.25), order=0)]),
            ExtractedRegion(kind="body", source="printed", column=0, order=1, box=Box(x=.1,y=.25,w=.8,h=.28), lines=[
                ExtractedLine(text="هذا نص عربي مستخرج قابل للمراجعة والتصحيح", box=Box(x=.1,y=.27,w=.8,h=.055), order=0),
                ExtractedLine(text="يحافظ ورّاق على السطر وموضعه في الصفحة", box=Box(x=.1,y=.35,w=.8,h=.055), order=1),
            ]),
            ExtractedRegion(kind="margin_note", source="handwritten", column=0, order=2, box=Box(x=.03,y=.42,w=.28,h=.12), lines=[ExtractedLine(text="تعليق بخط اليد", box=Box(x=.03,y=.44,w=.28,h=.05), order=0)]),
            ExtractedRegion(kind="footnote", source="printed", column=0, order=3, box=Box(x=.1,y=.73,w=.8,h=.1), lines=[ExtractedLine(text="١ حاشية مطبوعة مستقلة عن المتن", box=Box(x=.1,y=.75,w=.8,h=.045), order=0)]),
        ],
    )
    library.apply_extraction(book["id"], 1, page, json.dumps(page.model_dump(), ensure_ascii=False))

    application = QGuiApplication([])
    application.setLayoutDirection(Qt.RightToLeft)
    QLocale.setDefault(QLocale(QLocale.Arabic, QLocale.Egypt))
    bridge = Bridge(library, MemorySecretStore())
    engine = QQmlApplicationEngine()
    engine.addImageProvider("pages", PageImageProvider(library))
    engine.rootContext().setContextProperty("App", bridge)
    engine.load(QUrl.fromLocalFile(str(resource_path("qml", "Main.qml"))))
    window = engine.rootObjects()[0]
    window.setWidth(1440); window.setHeight(920)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    def capture_library() -> None:
        window.grabWindow().save(str(OUTPUT / "desktop-library.png"))
        bridge.openBook(book["id"])
        bridge.openPage(1)
        QTimer.singleShot(900, capture_review)

    def capture_review() -> None:
        window.grabWindow().save(str(OUTPUT / "desktop-review.png"))
        bridge.go("settings")
        settings = window.findChild(QObject, "settingsScreen")
        settings.setProperty("tab", 1)
        QTimer.singleShot(500, capture_settings)

    def capture_settings() -> None:
        window.grabWindow().save(str(OUTPUT / "desktop-settings-prompts.png"))
        combos = [item for item in window.findChildren(QObject) if "AppComboBox" in item.metaObject().className() and item.property("visible")]
        if combos:
            combo = combos[0]
            point = combo.mapToItem(window.contentItem(), QPointF(combo.property("width") / 2, combo.property("height") / 2))
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point.toPoint())
            QTimer.singleShot(300, capture_combo)
            return
        application.quit()

    def capture_combo() -> None:
        window.grabWindow().save(str(OUTPUT / "desktop-settings-combo.png"))
        application.quit()

    QTimer.singleShot(900, capture_library)
    code = application.exec()
    shutil.rmtree(temporary, ignore_errors=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
