#!/usr/bin/env python3
"""Shared adb helpers — always use adb from PATH."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Sequence


class AdbNotFoundError(RuntimeError):
    pass


def resolve_adb() -> str:
    adb = shutil.which("adb")
    if not adb:
        raise AdbNotFoundError(
            "adb not found in PATH. Add Android platform-tools to PATH and retry."
        )
    return adb


def adb_command(*args: str, udid: str | None = None) -> list[str]:
    command = [resolve_adb()]
    serial = (udid or os.getenv("ANDROID_SERIAL", "")).strip()
    if serial:
        command.extend(["-s", serial])
    command.extend(list(args))
    return command


def run_adb(
    *args: str,
    udid: str | None = None,
    check: bool = False,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        adb_command(*args, udid=udid),
        check=check,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def list_authorized_devices() -> list[str]:
    try:
        result = run_adb("devices")
    except (OSError, AdbNotFoundError):
        return []
    devices: list[str] = []
    for line in (result.stdout or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


def ensure_single_authorized_device(udid: str | None = None) -> str:
    """Return the target device serial; fail if adb missing or device unauthorized."""
    resolve_adb()
    devices = list_authorized_devices()
    if not devices:
        raise SystemExit(
            "No authorized Android device (adb devices). Unlock the phone, allow USB debugging, "
            "then run: adb kill-server && adb devices"
        )
    target = (udid or os.getenv("ANDROID_SERIAL", "")).strip()
    if target:
        if target not in devices:
            raise SystemExit(
                f"Device {target!r} not authorized. Connected: {', '.join(devices)}"
            )
        return target
    if len(devices) > 1:
        raise SystemExit(
            f"Multiple devices connected ({', '.join(devices)}). "
            "Set capabilities.local.json appium:udid or ANDROID_SERIAL."
        )
    return devices[0]


def force_stop_packages(packages: Sequence[str], *, udid: str | None = None) -> None:
    for package in packages:
        run_adb("shell", "am", "force-stop", package, udid=udid, check=False)
