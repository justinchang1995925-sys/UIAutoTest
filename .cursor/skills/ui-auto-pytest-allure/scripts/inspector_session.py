#!/usr/bin/env python3
"""Shared helpers for Appium Inspector session persistence."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SESSION_FILE = ".appium-inspector-session.json"
KEEPALIVE_PID_FILE = ".appium-inspector-keepalive.pid"
DEFAULT_SERVER = "http://127.0.0.1:4723"


def session_info_path(project_root: Path) -> Path:
    return project_root / SESSION_FILE


def keepalive_pid_path(project_root: Path) -> Path:
    return project_root / KEEPALIVE_PID_FILE


def keepalive_log_path(project_root: Path) -> Path:
    return project_root / "logs" / "inspector-keepalive.log"


def _request(method: str, url: str, payload: dict | None = None, timeout: int = 30) -> dict:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def load_session_info(project_root: Path) -> dict[str, Any] | None:
    path = session_info_path(project_root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def save_session_info(project_root: Path, info: dict[str, Any]) -> None:
    path = session_info_path(project_root)
    path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")


def inspector_command_timeout() -> int:
    raw = os.getenv("UIATEST_INSPECTOR_COMMAND_TIMEOUT", "86400").strip()
    try:
        return max(300, int(raw))
    except ValueError:
        return 86400


def inspector_capabilities(base: dict[str, Any]) -> dict[str, Any]:
    caps = dict(base)
    caps["appium:newCommandTimeout"] = inspector_command_timeout()
    return caps


def session_is_healthy(server_url: str, session_id: str) -> bool:
    try:
        _request("GET", f"{server_url}/session/{session_id}/source", timeout=30)
        return True
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return False


def list_sessions(server_url: str) -> list[dict[str, Any]]:
    try:
        response = _request("GET", f"{server_url}/appium/sessions", timeout=10)
        return list(response.get("value") or [])
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return []


def delete_session(server_url: str, session_id: str) -> None:
    try:
        _request("DELETE", f"{server_url}/session/{session_id}", timeout=20)
    except (HTTPError, URLError, TimeoutError, OSError):
        pass


def is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def is_keepalive_running(project_root: Path) -> bool:
    pid_path = keepalive_pid_path(project_root)
    if not pid_path.is_file():
        return False
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    return is_process_alive(pid)


def stop_keepalive(project_root: Path) -> None:
    pid_path = keepalive_pid_path(project_root)
    if not pid_path.is_file():
        return
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        pid_path.unlink(missing_ok=True)
        return
    if pid > 0:
        if os.name == "nt":
            subprocess_run = __import__("subprocess").run
            subprocess_run(
                ["taskkill", "/PID", str(pid), "/F"],
                check=False,
                capture_output=True,
            )
        else:
            try:
                os.kill(pid, 15)
            except OSError:
                pass
    pid_path.unlink(missing_ok=True)


def append_keepalive_log(project_root: Path, message: str) -> None:
    log_path = keepalive_log_path(project_root)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] {message}\n")
