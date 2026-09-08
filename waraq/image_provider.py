from __future__ import annotations

from urllib.parse import parse_qs

from PIL.ImageQt import ImageQt
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtQuick import QQuickImageProvider

from .database import Library
from .pdf import render_page


class PageImageProvider(QQuickImageProvider):
    def __init__(self, library: Library):
        super().__init__(QQuickImageProvider.Pixmap)
        self.library = library
        self.cache: dict[tuple[str, str, int, int, int], QPixmap] = {}

    def requestPixmap(self, identifier: str, size: QSize, requested_size: QSize):  # noqa: N802, ANN001
        path, _, query = identifier.partition("?")
        book_id, number_text = path.split("/", 1)
        number = int(number_text)
        dpi = int(parse_qs(query).get("dpi", ["150"])[0])
        source = self.library.page_path(book_id)
        key = (book_id, str(source), source.stat().st_mtime_ns, number, dpi)
        pixmap = self.cache.get(key)
        if pixmap is None:
            image = render_page(source, number, dpi=dpi)
            pixmap = QPixmap.fromImage(ImageQt(image))
            self.cache[key] = pixmap
            if len(self.cache) > 10:
                self.cache.pop(next(iter(self.cache)))
        if requested_size.isValid() and requested_size.width() > 0 and requested_size.height() > 0:
            pixmap = pixmap.scaled(requested_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if size is not None:
            size.setWidth(pixmap.width())
            size.setHeight(pixmap.height())
        return pixmap
