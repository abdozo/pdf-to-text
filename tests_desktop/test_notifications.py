from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from waraq import notifications


def test_completion_sound_choices_are_small_and_stable() -> None:
    assert 1 <= len(notifications.SYSTEM_SOUNDS) <= 5
    assert len(notifications.SYSTEM_SOUND_IDS) == len(notifications.SYSTEM_SOUNDS)


def test_macos_sound_uses_the_matching_built_in_file(monkeypatch) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(notifications.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(Path, "is_file", lambda _path: True)
    monkeypatch.setattr(
        notifications.subprocess,
        "Popen",
        lambda command, **_options: commands.append(command),
    )

    notifications.play_system_sound("chime")

    assert commands == [
        ["/usr/bin/afplay", "/System/Library/Sounds/Ping.aiff"]
    ]


def test_windows_sound_uses_the_system_alias(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []
    fake_winsound = SimpleNamespace(
        SND_ALIAS=1,
        SND_ASYNC=2,
        PlaySound=lambda name, flags: calls.append((name, flags)),
    )
    monkeypatch.setattr(notifications.platform, "system", lambda: "Windows")
    monkeypatch.setitem(sys.modules, "winsound", fake_winsound)

    notifications.play_system_sound("deep")

    assert calls == [("SystemHand", 3)]
