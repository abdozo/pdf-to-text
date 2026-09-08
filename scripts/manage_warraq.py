from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import venv
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = PROJECT_ROOT / ".waraq-runtime"
STATE_FILE = RUNTIME_DIR / "process.json"
STOP_FILE = RUNTIME_DIR / "stop-requested"
LOG_FILE = RUNTIME_DIR / "waraq.log"
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements-desktop.txt"


def _venv_dir() -> Path:
    return PROJECT_ROOT / (".venv-windows" if os.name == "nt" else ".venv-desktop")


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _requirements_digest() -> str:
    return hashlib.sha256(REQUIREMENTS_FILE.read_bytes()).hexdigest()


def ensure_environment() -> Path:
    if sys.version_info < (3, 11):
        raise RuntimeError("Warraq requires Python 3.11 or newer.")

    venv_dir = _venv_dir()
    python = _venv_python(venv_dir)
    if not python.is_file():
        print(f"Creating Python environment at {venv_dir.name}...")
        venv.EnvBuilder(with_pip=True).create(venv_dir)

    digest = _requirements_digest()
    stamp_file = venv_dir / ".requirements.sha256"
    try:
        installed_digest = stamp_file.read_text(encoding="utf-8").strip()
    except OSError:
        installed_digest = ""

    if installed_digest != digest:
        print("Installing Warraq dependencies...")
        subprocess.run(
            [str(python), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)],
            cwd=PROJECT_ROOT,
            check=True,
        )
        stamp_file.write_text(digest + "\n", encoding="utf-8")
    return python


def _load_state() -> dict[str, Any] | None:
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(state, dict) or not isinstance(state.get("pid"), int):
        return None
    return state


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        open_process.restype = ctypes.c_void_p
        wait_for_single_object = kernel32.WaitForSingleObject
        wait_for_single_object.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        wait_for_single_object.restype = ctypes.c_uint32
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [ctypes.c_void_p]
        close_handle.restype = ctypes.c_int

        handle = open_process(0x00100000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5
        try:
            return wait_for_single_object(handle, 0) == 0x00000102
        finally:
            close_handle(handle)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _process_command(pid: int) -> str:
    try:
        if os.name == "nt":
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-Command",
                    (
                        f"(Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}')"
                        ".CommandLine"
                    ),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        else:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "command="],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip()


def _state_is_live(state: dict[str, Any]) -> bool:
    if state.get("project_root") != str(PROJECT_ROOT):
        return False
    return _pid_exists(state["pid"])


def _command_is_warraq_process(pid: int) -> bool:
    command = _process_command(pid)
    if not command:
        return False
    return "run_desktop.py" in command and str(PROJECT_ROOT) in command


def _clear_stale_runtime() -> None:
    STATE_FILE.unlink(missing_ok=True)
    STOP_FILE.unlink(missing_ok=True)


def _show_recent_log() -> None:
    try:
        lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    if lines:
        print("\n".join(lines[-40:]), file=sys.stderr)


def start() -> int:
    state = _load_state()
    if state and _state_is_live(state):
        print(f"Warraq is already running (PID {state['pid']}).")
        return 0
    _clear_stale_runtime()

    try:
        python = ensure_environment()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Could not prepare Warraq: {error}", file=sys.stderr)
        return 1

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["WARRAQ_RUNTIME_DIR"] = str(RUNTIME_DIR)
    command = [str(python), str(PROJECT_ROOT / "run_desktop.py")]
    popen_options: dict[str, Any] = {
        "cwd": PROJECT_ROOT,
        "env": environment,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        pythonw = python.with_name("pythonw.exe")
        if pythonw.is_file():
            command[0] = str(pythonw)
        popen_options["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        popen_options["start_new_session"] = True

    with LOG_FILE.open("a", encoding="utf-8") as log:
        log.write(f"\n--- Starting Warraq at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        log.flush()
        process = subprocess.Popen(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            **popen_options,
        )

    STATE_FILE.write_text(
        json.dumps({"pid": process.pid, "project_root": str(PROJECT_ROOT)}) + "\n",
        encoding="utf-8",
    )
    time.sleep(1)
    exit_code = process.poll()
    if exit_code is not None:
        _clear_stale_runtime()
        print(f"Warraq exited during startup with code {exit_code}.", file=sys.stderr)
        _show_recent_log()
        return 1

    print(f"Warraq started (PID {process.pid}).")
    print(f"Log: {LOG_FILE}")
    return 0


def stop() -> int:
    state = _load_state()
    if not state:
        _clear_stale_runtime()
        print("Warraq is not running.")
        return 0

    pid = state["pid"]
    if not _state_is_live(state):
        _clear_stale_runtime()
        print("Warraq is not running. Removed a stale process record.")
        return 0

    STOP_FILE.touch()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and _pid_exists(pid):
        time.sleep(0.2)

    if _pid_exists(pid):
        if not _command_is_warraq_process(pid):
            print(
                f"Warraq did not close, and PID {pid} could not be verified safely.",
                file=sys.stderr,
            )
            return 1
        print("Warraq did not close in time. Stopping it now...")
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and _pid_exists(pid):
        time.sleep(0.1)
    if _pid_exists(pid):
        print(f"Could not stop Warraq (PID {pid}).", file=sys.stderr)
        return 1

    _clear_stale_runtime()
    print("Warraq stopped.")
    return 0


def restart() -> int:
    stop_result = stop()
    if stop_result != 0:
        return stop_result
    return start()


def status() -> int:
    state = _load_state()
    if state and _state_is_live(state):
        print(f"Warraq is running (PID {state['pid']}).")
        return 0
    _clear_stale_runtime()
    print("Warraq is not running.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the local Warraq desktop process.")
    parser.add_argument("action", choices=("start", "stop", "restart", "status"))
    arguments = parser.parse_args()
    return globals()[arguments.action]()


if __name__ == "__main__":
    raise SystemExit(main())
