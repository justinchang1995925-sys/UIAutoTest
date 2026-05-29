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
    logs_dir = project_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "appium-server.log"
    command = [
        appium_cmd,
        "--use-plugins=inspector",
        "--allow-insecure=*:session_discovery",
        "--log",
        str(log_file),
        "--log-level",
        "info",
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


def get_connected_device_ids() -> list[str]:
    adb = shutil.which("adb")
    if not adb:
        return []
    try:
        output = subprocess.run(
            [adb, "devices"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []

    ids: list[str] = []
    for line in output.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            ids.append(parts[0])
    return ids


def get_connected_device_id() -> str | None:
    ids = get_connected_device_ids()
    if len(ids) == 1:
        return ids[0]
    return None


def _preferred_device_id_from_existing_caps(
    capabilities_path: Path, connected_ids: list[str]
) -> str | None:
    """If capabilities already contain a udid that is currently connected, keep it."""
    try:
        if capabilities_path.exists():
            caps = json.loads(capabilities_path.read_text(encoding="utf-8-sig"))
            udid = str(caps.get("appium:udid") or "").strip()
            if udid and udid in connected_ids:
                return udid
    except Exception:
        return None
    return None


def sync_capabilities_device(capabilities_path: Path) -> str | None:
    connected = get_connected_device_ids()
    if not connected:
        print("Warning: no authorized Android device found for capabilities sync.")
        return None

    if capabilities_path.is_dir():
        capabilities_path = capabilities_path / "capabilities.local.json"

    if not capabilities_path.exists():
        template = capabilities_path.parent / "capabilities.template.json"
        fallback = capabilities_path.parent / "capabilities.json"
        if template.exists():
            capabilities_path.write_text(template.read_text(encoding="utf-8-sig"), encoding="utf-8")
            print(f"Created local capabilities from template: {capabilities_path}")
        elif fallback.exists():
            capabilities_path.write_text(fallback.read_text(encoding="utf-8-sig"), encoding="utf-8")
            print(f"Created local capabilities from capabilities.json: {capabilities_path}")
        else:
            print(
                "Warning: no capabilities file found for sync. "
                f"Expected one of: {capabilities_path}, {template}, {fallback}"
            )
            return None

    # Choose device:
    # - Prefer the udid already recorded in the capabilities file (if connected)
    # - Else if exactly one device is connected, use it
    # - Else refuse to guess
    preferred = _preferred_device_id_from_existing_caps(capabilities_path, connected)
    if preferred:
        device_id = preferred
    elif len(connected) == 1:
        device_id = connected[0]
    else:
        print(
            "Warning: multiple Android devices connected; cannot auto-select udid. "
            f"Connected: {', '.join(connected)}"
        )
        return None

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


def get_device_state(device_id: str) -> str | None:
    """Return adb state for device_id: device, offline, unauthorized, or None if absent."""
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
        parts = line.split()
        if parts and parts[0] == device_id and len(parts) >= 2:
            return parts[1]
    return None


def wait_for_device_ready(device_id: str, timeout_sec: int = 20) -> bool:
    """Poll until device_id appears as authorized ``device`` in adb devices."""
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        state = get_device_state(device_id)
        if state == "device":
            return True
        if state in {"unauthorized", "offline"}:
            print(f"Warning: device {device_id} is {state}; waiting for authorization...")
        time.sleep(1)
    return False


def adb_connect(device: str) -> bool:
    """Connect a device over network, e.g. 192.168.1.8:5555.

    Returns True when adb reports connected/already connected.
    """
    value = device.strip()
    if not value:
        return False
    adb = shutil.which("adb")
    if not adb:
        raise SystemExit("adb is not available in PATH.")
    result = subprocess.run([adb, "connect", value], check=False, capture_output=True, text=True)
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    output = output.strip().lower()
    if result.returncode == 0 and ("connected" in output or "already connected" in output):
        print(f"adb connect ok: {device}")
        if not wait_for_device_ready(value, timeout_sec=20):
            state = get_device_state(value) or "missing"
            print(
                f"Warning: adb connect succeeded but device is not ready (state={state}). "
                "Check USB debugging authorization or network pairing."
            )
            return False
        return True
    print(f"adb connect failed: {device}\n{output}".rstrip())
    return False


def adb_connect_ip(ip: str, ports: list[int] | None = None) -> str | None:
    """Try adb connect to an IP with common ports.

    Returns the successful ip:port string, or None.
    """
    value = ip.strip()
    if not value:
        return None
    candidates = ports or [5555, 5556, 37099, 37100]
    for port in candidates:
        target = f"{value}:{port}"
        if adb_connect(target):
            return target
    return None


def connect_device(target: str) -> str:
    """Ensure a target device is connected via adb.

    - If target is ip:port -> adb connect ip:port
    - If target is ip only -> try common ports and connect
    - Otherwise treat as udid (USB) and do not connect

    Returns the udid to use in capabilities (possibly normalized to ip:port).
    """
    value = target.strip()
    if not value:
        raise ValueError("Empty device target.")

    if re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{1,3}){3}:\d{2,5}", value):
        adb_connect(value)
        return value

    if re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{1,3}){3}", value):
        connected = adb_connect_ip(value)
        if not connected:
            raise SystemExit(
                f"Could not adb-connect to {value}. "
                "Provide an explicit port, e.g. 192.168.1.8:5555."
            )
        return connected

    # Assume it's an adb udid (USB or already-connected network device).
    if not wait_for_device_ready(value, timeout_sec=10):
        state = get_device_state(value) or "missing"
        raise SystemExit(
            f"Device {value} is not ready for tests (adb state={state}). "
            "Check USB debugging, authorization, or adb connect."
        )
    return value


def set_capabilities_device_id(capabilities_path: Path, device_id: str) -> None:
    """Force capabilities file to use a specific udid/deviceName."""
    if capabilities_path.is_dir():
        capabilities_path = capabilities_path / "capabilities.local.json"
    if not capabilities_path.exists():
        sync_capabilities_device(capabilities_path)
    caps = json.loads(capabilities_path.read_text(encoding="utf-8-sig"))
    caps["appium:udid"] = device_id
    caps["appium:deviceName"] = device_id
    capabilities_path.write_text(
        json.dumps(caps, ensure_ascii=False, indent=4) + "\n",
        encoding="utf-8",
    )
    print(f"Set capabilities device id: {device_id}")
