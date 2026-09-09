from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path
from typing import Final


SYSTEM_SOUNDS: Final[tuple[dict[str, str], ...]] = (
    {"id": "bell", "name": "جرس"},
    {"id": "chime", "name": "رنين"},
    {"id": "pop", "name": "نقرة"},
    {"id": "soft", "name": "هادئ"},
    {"id": "deep", "name": "عميق"},
)
SYSTEM_SOUND_IDS: Final[frozenset[str]] = frozenset(
    sound["id"] for sound in SYSTEM_SOUNDS
)

_MACOS_SOUND_NAMES: Final[dict[str, str]] = {
    "bell": "Glass",
    "chime": "Ping",
    "pop": "Pop",
    "soft": "Purr",
    "deep": "Submarine",
}

_WINDOWS_SOUND_ALIASES: Final[dict[str, str]] = {
    "bell": "SystemAsterisk",
    "chime": "SystemExclamation",
    "pop": "SystemDefault",
    "soft": "SystemQuestion",
    "deep": "SystemHand",
}


def play_system_sound(sound_id: str) -> None:
    """Play an operating-system sound without shipping audio files."""
    selected = sound_id if sound_id in SYSTEM_SOUND_IDS else SYSTEM_SOUNDS[0]["id"]
    system = platform.system()
    if system == "Darwin" and _play_macos_sound(selected):
        return
    if system == "Windows" and _play_windows_sound(selected):
        return
    _play_default_beep()


def _play_macos_sound(sound_id: str) -> bool:
    sound_path = Path("/System/Library/Sounds") / f"{_MACOS_SOUND_NAMES[sound_id]}.aiff"
    if not sound_path.is_file():
        return False
    try:
        subprocess.Popen(
            ["/usr/bin/afplay", str(sound_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return True


def _play_windows_sound(sound_id: str) -> bool:
    try:
        import winsound

        winsound.PlaySound(
            _WINDOWS_SOUND_ALIASES[sound_id],
            winsound.SND_ALIAS | winsound.SND_ASYNC,
        )
    except (ImportError, RuntimeError):
        return False
    return True


def _play_default_beep() -> None:
    try:
        sys.stderr.write("\a")
        sys.stderr.flush()
    except OSError:
        return
