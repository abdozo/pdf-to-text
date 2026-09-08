from __future__ import annotations

import os
import sys
import struct
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPainterPath


ROOT = Path(__file__).resolve().parents[1]
ICONSET = ROOT / "waraq" / "assets" / "Warraq.iconset"


def draw(size: int, path: Path) -> None:
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    margin = size * 0.07
    shape = QPainterPath()
    shape.addRoundedRect(QRectF(margin, margin, size - 2 * margin, size - 2 * margin), size * 0.2, size * 0.2)
    painter.fillPath(shape, QColor("#6256d9"))
    page = QRectF(size * 0.22, size * 0.17, size * 0.56, size * 0.66)
    page_path = QPainterPath()
    page_path.addRoundedRect(page, size * 0.035, size * 0.035)
    painter.fillPath(page_path, QColor("#fffdfa"))
    painter.fillRect(QRectF(size * 0.70, size * 0.17, size * 0.08, size * 0.66), QColor("#1c9a77"))
    painter.setPen(QColor("#18203a"))
    font = QFont("Noto Naskh Arabic")
    font.setBold(True)
    font.setPixelSize(round(size * 0.34))
    painter.setFont(font)
    painter.drawText(page, Qt.AlignCenter, "و")
    painter.end()
    image.save(str(path), "PNG")


def main() -> None:
    application = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    ICONSET.mkdir(parents=True, exist_ok=True)
    for points in (16, 32, 128, 256, 512):
        draw(points, ICONSET / f"icon_{points}x{points}.png")
        draw(points * 2, ICONSET / f"icon_{points}x{points}@2x.png")
    sources = [
        (b"icp4", ICONSET / "icon_16x16.png"),
        (b"icp5", ICONSET / "icon_32x32.png"),
        (b"icp6", ICONSET / "icon_32x32@2x.png"),
        (b"ic07", ICONSET / "icon_128x128.png"),
        (b"ic08", ICONSET / "icon_256x256.png"),
        (b"ic09", ICONSET / "icon_512x512.png"),
        (b"ic10", ICONSET / "icon_512x512@2x.png"),
    ]
    chunks = []
    for kind, source in sources:
        payload = source.read_bytes()
        chunks.append(kind + struct.pack(">I", len(payload) + 8) + payload)
    body = b"".join(chunks)
    (ROOT / "waraq" / "assets" / "Warraq.icns").write_bytes(b"icns" + struct.pack(">I", len(body) + 8) + body)
    application.quit()


if __name__ == "__main__":
    main()
