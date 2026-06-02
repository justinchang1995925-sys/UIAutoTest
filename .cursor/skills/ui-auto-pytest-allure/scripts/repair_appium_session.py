#!/usr/bin/env python3
"""Repair Appium / UiAutomator2 after tests so Inspector refresh works again."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from adb_utils import AdbNotFoundError, ensure_single_authorized_device, force_stop_packages, resolve_adb
from inspector_session import (  # noqa: E402
    append_keepalive_log,
    inspector_capabilities,
    is_keepalive_running,
    load_session_info,
    save_session_info,
    session_is_healthy,
    stop_keepalive,
)

UIAUTOMATOR2_PACKAGES = (
    "io.appium.uiautomator2.server",
    "io.appium.uiautomator2.server.test",
)


def _request(method: str, url: str, payload: dict | None = None, timeout: int = 30) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed ({exc.code}): {detail}") from exc


def _server_ready(server_url: str) -> bool:
    try:
        status = _request("GET", f"{server_url}/status", timeout=5)
        return bool(status.get("value", {}).get("ready"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return False


def _list_sessions(server_url: str) -> list[dict]:
    try:
        response = _request("GET", f"{server_url}/appium/sessions", timeout=10)
        return list(response.get("value") or [])
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return []


def _delete_sessions(server_url: str) -> None:
    for session in _list_sessions(server_url):
        session_id = session.get("id")
        if not session_id:
            continue
        try:
            _request("DELETE", f"{server_url}/session/{session_id}", timeout=20)
            print(f"Deleted Appium session: {session_id}")
        except (HTTPError, URLError, TimeoutError) as exc:
            print(f"Could not delete session {session_id}: {exc}")


def _ensure_adb_device_ready() -> None:
    try:
        adb = resolve_adb()
        device = ensure_single_authorized_device()
    except AdbNotFoundError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Using adb from PATH: {adb}")
    if device:
        print(f"Target device: {device}")


def _repair_uiautomator2_on_device() -> None:
    try:
        resolve_adb()
    except AdbNotFoundError:
        print("adb not found in PATH. Skip on-device UiAutomator2 repair.")
        return

    _ensure_adb_device_ready()

    print("Restarting UiAutomator2 instrumentation on device...")
    force_stop_packages(UIAUTOMATOR2_PACKAGES)
    time.sleep(3)


def _load_capabilities(project_root: Path) -> dict:
    candidates = [
        project_root / "capabilities.local.json",
        project_root / "capabilities.json",
        project_root / "capabilities.template.json",
    ]
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    raise SystemExit(
        "No capabilities file found. Expected one of:\n"
        + "\n".join(f"  - {p}" for p in candidates)
    )


def _create_session(server_url: str, capabilities: dict) -> str:
    payload = {
        "capabilities": {
            "alwaysMatch": capabilities,
            "firstMatch": [{}],
        }
    }
    response = _request("POST", f"{server_url}/session", payload, timeout=120)
    session_id = response.get("value", {}).get("sessionId")
    if not session_id:
        raise RuntimeError(f"Could not create Appium session: {response}")
    return session_id


def _session_is_healthy(server_url: str, session_id: str) -> bool:
    return session_is_healthy(server_url, session_id)


def _start_keepalive_daemon(project_root: Path, server_url: str) -> None:
    keepalive_script = SCRIPT_DIR / "inspector_keepalive.py"
    if not keepalive_script.is_file():
        return
    log_path = project_root / "logs" / "inspector-keepalive.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("a", encoding="utf-8")
    popen_kwargs: dict = {
        "cwd": str(project_root),
        "stdout": log_handle,
        "stderr": subprocess.STDOUT,
        "close_fds": True,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    subprocess.Popen(
        [
            sys.executable,
            str(keepalive_script),
            "--project-root",
            str(project_root),
            "--server-url",
            server_url,
        ],
        **popen_kwargs,
    )
    time.sleep(0.5)
    if is_keepalive_running(project_root):
        print("Inspector keepalive started (session stays online; see logs/inspector-keepalive.log).")
    else:
        print("Warning: could not verify inspector keepalive process.")


def repair(
    server_url: str = "http://127.0.0.1:4723",
    project_root: Path | None = None,
    recreate_session: bool = True,
    open_inspector: bool = False,
    *,
    for_inspector: bool = False,
    start_keepalive: bool = False,
) -> str | None:
    root = project_root or Path.cwd()
    if not _server_ready(server_url):
        raise SystemExit(
            f"Appium server is not ready at {server_url}. "
            "Start Appium first, then run this repair script."
        )

    print(f"Repairing Appium / UiAutomator2 at {server_url} ...")
    _ensure_adb_device_ready()

    session_id: str | None = None
    existing = load_session_info(root) if for_inspector else None
    existing_id = str((existing or {}).get("session_id") or "").strip()
    if for_inspector and existing_id and session_is_healthy(server_url, existing_id):
        print(f"Reusing healthy inspector session: {existing_id}")
        session_id = existing_id
    else:
        _delete_sessions(server_url)
        if not (for_inspector and is_keepalive_running(root)):
            _repair_uiautomator2_on_device()

    if session_id is None and recreate_session:
        base_caps = _load_capabilities(root)
        capabilities = inspector_capabilities(base_caps) if for_inspector else base_caps
        last_error = None
        session_id = None
        for attempt in range(1, 4):
            try:
                session_id = _create_session(server_url, capabilities)
                break
            except RuntimeError as exc:
                last_error = exc
                print(f"Session create attempt {attempt} failed: {exc}")
                _repair_uiautomator2_on_device()
                time.sleep(2)
        if not session_id:
            raise SystemExit(f"Could not create Appium session: {last_error}")

        if not _session_is_healthy(server_url, session_id):
            print("New session is unhealthy. Retrying once...")
            _delete_sessions(server_url)
            _repair_uiautomator2_on_device()
            session_id = _create_session(server_url, capabilities)
            if not _session_is_healthy(server_url, session_id):
                raise SystemExit(
                    "Created Appium session but page source is still unavailable. "
                    "Check device connection and Appium server logs."
                )

        save_session_info(
            root,
            {
                "server_url": server_url,
                "session_id": session_id,
                "inspector_url": f"{server_url}/inspector",
                "keepalive": bool(for_inspector or start_keepalive),
            },
        )
        session_file = root / ".appium-inspector-session.json"
        print(f"Created healthy Appium session: {session_id}")
        print(f"Saved session info: {session_file}")
        print("In Inspector: Session Builder -> Attach to Session -> select this session id.")
    elif session_id and for_inspector:
        save_session_info(
            root,
            {
                "server_url": server_url,
                "session_id": session_id,
                "inspector_url": f"{server_url}/inspector",
                "keepalive": True,
            },
        )

    if session_id and (for_inspector or start_keepalive):
        stop_keepalive(root)
        _start_keepalive_daemon(root, server_url)
        append_keepalive_log(root, f"Inspector opened with session {session_id}")

    if open_inspector:
        import webbrowser

        webbrowser.open(f"{server_url}/inspector")
        print(
            "Inspector keepalive is running; the session stays online. "
            "If refresh fails after a long idle, re-attach using the latest session id "
            "from .appium-inspector-session.json"
        )

    return session_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-url", default="http://127.0.0.1:4723")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--no-recreate-session", action="store_true")
    parser.add_argument("--open-inspector", action="store_true")
    parser.add_argument(
        "--for-inspector",
        action="store_true",
        help="Long-lived session + optional keepalive (used by uiatest inspect).",
    )
    parser.add_argument(
        "--start-keepalive",
        action="store_true",
        help="Start background keepalive after creating session.",
    )
    parser.add_argument(
        "--stop-keepalive",
        action="store_true",
        help="Stop inspector keepalive daemon only.",
    )
    args = parser.parse_args()

    if args.stop_keepalive:
        stop_keepalive(args.project_root)
        print("Inspector keepalive stopped.")
        return

    for_inspector = args.for_inspector or args.open_inspector
    repair(
        server_url=args.server_url,
        project_root=args.project_root,
        recreate_session=not args.no_recreate_session,
        open_inspector=args.open_inspector,
        for_inspector=for_inspector,
        start_keepalive=args.start_keepalive or for_inspector,
    )


if __name__ == "__main__":
    main()
