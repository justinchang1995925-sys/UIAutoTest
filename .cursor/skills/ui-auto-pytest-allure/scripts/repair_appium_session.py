#!/usr/bin/env python3
"""Repair Appium / UiAutomator2 after tests so Inspector refresh works again."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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


def _candidate_adb_paths() -> list[Path]:
    candidates: list[Path] = []
    if shutil.which("adb"):
        candidates.append(Path(shutil.which("adb")))

    for root in (
        os.getenv("ANDROID_HOME"),
        os.getenv("ANDROID_SDK_ROOT"),
        r"D:\adb_new_for_android12",
        r"D:\platform-tools",
        "D:\\",
    ):
        if not root:
            continue
        root_path = Path(root)
        candidates.append(root_path / "platform-tools" / "adb.exe")
        candidates.append(root_path / "adb.exe")

    unique: list[Path] = []
    for path in candidates:
        if path and path not in unique:
            unique.append(path)
    return unique


def _adb_devices_output(adb_path: Path) -> str:
    return subprocess.run(
        [str(adb_path), "devices"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _resolve_authorized_adb() -> Path:
    for adb_path in _candidate_adb_paths():
        if not adb_path.exists():
            continue
        try:
            output = _adb_devices_output(adb_path)
        except (OSError, subprocess.CalledProcessError):
            continue
        if any("\tdevice" in line for line in output.splitlines()[1:]):
            return adb_path

    raise SystemExit(
        "No authorized Android device found. Unlock the phone, allow USB debugging, then run:\n"
        "  adb kill-server\n"
        "  adb devices\n"
        "If you have multiple adb installations, authorize the one Appium uses "
        "(often ANDROID_HOME/platform-tools/adb.exe)."
    )


def _ensure_platform_tools_layout(sdk_root: Path) -> Path:
    platform_tools = sdk_root / "platform-tools"
    adb_in_root = sdk_root / "adb.exe"
    if not adb_in_root.exists():
        return platform_tools

    platform_tools.mkdir(parents=True, exist_ok=True)
    for file_name in ("adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll"):
        source = sdk_root / file_name
        if source.exists():
            target = platform_tools / file_name
            if not target.exists() or source.stat().st_mtime > target.stat().st_mtime:
                target.write_bytes(source.read_bytes())
    return platform_tools


def _configure_android_sdk_env() -> Path:
    adb_path = _resolve_authorized_adb()
    if adb_path.parent.name == "platform-tools":
        sdk_root = adb_path.parent.parent
    else:
        sdk_root = adb_path.parent
        platform_tools = _ensure_platform_tools_layout(sdk_root)
        adb_path = platform_tools / "adb.exe"

    os.environ["ANDROID_HOME"] = str(sdk_root)
    os.environ["ANDROID_SDK_ROOT"] = str(sdk_root)
    if shutil.which("adb") != str(adb_path):
        os.environ["PATH"] = f"{adb_path.parent};{os.environ.get('PATH', '')}"
    print(f"Using ANDROID_HOME={sdk_root}")
    print(f"Using adb={adb_path}")
    return adb_path


def _ensure_adb_device_ready() -> None:
    _configure_android_sdk_env()


def _repair_uiautomator2_on_device() -> None:
    try:
        subprocess.run(["adb", "version"], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        print("adb not found. Skip on-device UiAutomator2 repair.")
        return

    _ensure_adb_device_ready()

    print("Restarting UiAutomator2 instrumentation on device...")
    for package in UIAUTOMATOR2_PACKAGES:
        subprocess.run(
            ["adb", "shell", "am", "force-stop", package],
            check=False,
            capture_output=True,
            text=True,
        )
    time.sleep(3)


def _load_capabilities(project_root: Path) -> dict:
    path = project_root / "capabilities.json"
    if not path.exists():
        raise SystemExit(f"capabilities.json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


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
    try:
        _request("GET", f"{server_url}/session/{session_id}/source", timeout=30)
        return True
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return False


def repair(
    server_url: str = "http://127.0.0.1:4723",
    project_root: Path | None = None,
    recreate_session: bool = True,
    open_inspector: bool = False,
) -> str | None:
    root = project_root or Path.cwd()
    if not _server_ready(server_url):
        raise SystemExit(
            f"Appium server is not ready at {server_url}. "
            "Start Appium first, then run this repair script."
        )

    print(f"Repairing Appium / UiAutomator2 at {server_url} ...")
    _ensure_adb_device_ready()
    _delete_sessions(server_url)
    _repair_uiautomator2_on_device()

    session_id = None
    if recreate_session:
        capabilities = _load_capabilities(root)
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

        session_file = root / ".appium-inspector-session.json"
        session_file.write_text(
            json.dumps(
                {
                    "server_url": server_url,
                    "session_id": session_id,
                    "inspector_url": f"{server_url}/inspector",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Created healthy Appium session: {session_id}")
        print(f"Saved session info: {session_file}")
        print("In Inspector: Session Builder -> Attach to Session -> select this session id.")
        print("Do not refresh an old/dead session tab.")

    if open_inspector:
        import webbrowser

        webbrowser.open(f"{server_url}/inspector")

    return session_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-url", default="http://127.0.0.1:4723")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--no-recreate-session", action="store_true")
    parser.add_argument("--open-inspector", action="store_true")
    args = parser.parse_args()

    repair(
        server_url=args.server_url,
        project_root=args.project_root,
        recreate_session=not args.no_recreate_session,
        open_inspector=args.open_inspector,
    )


if __name__ == "__main__":
    main()
