from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_macos_launchers_use_the_process_manager():
    for name, action in (
        ("Start-Warraq.command", "start"),
        ("Stop-Warraq.command", "stop"),
        ("Restart-Warraq.command", "restart"),
    ):
        launcher = ROOT / "Mac Commands" / name
        assert launcher.stat().st_mode & 0o111
        text = launcher.read_text(encoding="utf-8")
        assert f"scripts/manage_warraq.py {action}" in text


def test_windows_launchers_use_the_process_manager():
    for name, action in (
        ("Start-Warraq.cmd", "start"),
        ("Stop-Warraq.cmd", "stop"),
        ("Restart-Warraq.cmd", "restart"),
    ):
        text = (ROOT / "Windows Commands" / name).read_text(encoding="utf-8")
        assert f"scripts\\manage_warraq.py {action}" in text


def test_windows_launchers_accept_any_compatible_python_3_runtime():
    for name in (
        "Start-Warraq.cmd",
        "Stop-Warraq.cmd",
        "Restart-Warraq.cmd",
    ):
        text = (ROOT / "Windows Commands" / name).read_text(encoding="utf-8")
        assert "py -3 scripts\\manage_warraq.py" in text
        assert "py -3.12" not in text


def test_windows_update_stops_updates_main_and_starts_in_order():
    text = (ROOT / "Windows Commands" / "Update-Warraq.cmd").read_text(
        encoding="utf-8"
    )
    commands = (
        'call "%~dp0Stop-Warraq.cmd"',
        "git checkout main",
        "git pull",
        'call "%~dp0Start-Warraq.cmd"',
    )
    positions = [text.index(command) for command in commands]
    assert positions == sorted(positions)
