#!/usr/bin/env python3
"""Ensure Appium server is running before UI tests."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from java_runtime import apply_java_env
from project_paths import resolve_project_root

DEFAULT_SERVER_URL = "http://127.0.0.1:4723"
STARTUP_TIMEOUT_SEC = 90


def parse_server_url(server_url: str) -> tuple[str, int]:
    match = re.match(r"^https?://([^:/]+):(\d+)", server_url.strip())
    if not match:
        return "127.0.0.1", 4723
    return match.group(1), int(match.group(2))


def is_appium_ready(server_url: str = DEFAULT_SERVER_URL) -> bool:
    try:
        with urlopen(f"{server_url.rstrip('/')}/status", timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return bool(payload.get("value", {}).get("ready"))
    except (URLError, TimeoutError, json.JSONDecodeError, OSError):
        return False


def _which_appium() -> str | None:
    return shutil.which("appium")


def _configure_android_env(env: dict[str, str], project_root: Path) -> dict[str, str]:
    env = apply_java_env(env, project_root)
    for key in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def start_appium_server(
    project_root: Path,
    server_url: str = DEFAULT_SERVER_URL,
) -> subprocess.Popen | None:
    appium_cmd = _which_appium()
    if not appium_cmd:
        raise SystemExit(
            "Appium is not installed. Install Node.js, then run: npm install -g appium"
        )

    host, port = parse_server_url(server_url)
    env = _configure_android_env(os.environ.copy(), project_root)
    command = [
        appium_cmd,
        "--use-plugins=inspector",
        "--allow-insecure=*:session_discovery",
        "--address",
        host,
        "--port",
        str(port),
    ]

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]

    print(f"Starting Appium server at {server_url} ...")
    return subprocess.Popen(
        command,
        cwd=str(project_root),
        env=env,
        creationflags=creationflags,
    )


def ensure_appium_server(
    project_root: Path | None = None,
    server_url: str | None = None,
) -> None:
    root = resolve_project_root(project_root or Path.cwd())
    url = server_url or os.getenv("APPIUM_SERVER_URL", DEFAULT_SERVER_URL)

    if is_appium_ready(url):
        print(f"Appium is already running at {url}")
        return

    process = start_appium_server(root, url)
    deadline = time.monotonic() + STARTUP_TIMEOUT_SEC
    while time.monotonic() < deadline:
        if is_appium_ready(url):
            print(f"Appium is ready at {url}")
            return
        if process and process.poll() is not None:
            raise SystemExit(
                f"Appium exited early with code {process.returncode}. "
                "Check the Appium console window for errors."
            )
        time.sleep(2)

    raise SystemExit(
        f"Appium did not become ready within {STARTUP_TIMEOUT_SEC}s at {url}. "
        "Check the Appium console window."
    )


def get_connected_device_id() -> str | None:
    adb = shutil.which("adb")
    if not adb:
        return None
    try:
        output = subprocess.run(
            [adb, "devices"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None

    for line in output.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            return parts[0]
    return None


def sync_capabilities_device(capabilities_path: Path) -> str | None:
    device_id = get_connected_device_id()
    if not device_id:
        print("Warning: no authorized Android device found for capabilities sync.")
        return None

    if not capabilities_path.exists():
        print(f"Warning: capabilities file not found: {capabilities_path}")
        return device_id

    caps = json.loads(capabilities_path.read_text(encoding="utf-8-sig"))
    if caps.get("appium:udid") == device_id and caps.get("appium:deviceName") == device_id:
        return device_id

    caps["appium:udid"] = device_id
    caps["appium:deviceName"] = device_id
    capabilities_path.write_text(
        json.dumps(caps, ensure_ascii=False, indent=4) + "\n",
        encoding="utf-8",
    )
    print(f"Updated capabilities device id: {device_id}")
    return device_id
