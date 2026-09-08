from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "waraq" / "assets" / "Warraq.iconset" / "icon_512x512.png"
DESTINATION = ROOT / "waraq" / "assets" / "Warraq.ico"


def main() -> None:
    with Image.open(SOURCE) as image:
        image.convert("RGBA").save(
            DESTINATION,
            format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )


if __name__ == "__main__":
    main()
