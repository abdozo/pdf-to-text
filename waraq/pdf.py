from __future__ import annotations

import io
import threading
from contextlib import closing
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image


PDF_LOCK = threading.RLock()


def render_page(path: Path, number: int, dpi: int = 220) -> Image.Image:
    with PDF_LOCK, pdfium.PdfDocument(path) as pdf:
        if number < 1 or number > len(pdf):
            raise IndexError("رقم الصفحة خارج نطاق الكتاب")
        with closing(pdf[number - 1]) as page:
            width, height = page.get_size()
            scale = min(dpi / 72, (36_000_000 / (width * height)) ** 0.5)
            bitmap = page.render(scale=scale)
            try:
                return bitmap.to_pil().convert("RGB").copy()
            finally:
                bitmap.close()


def jpeg_bytes(image: Image.Image, quality: int = 94) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=quality, optimize=True)
    return buffer.getvalue()

