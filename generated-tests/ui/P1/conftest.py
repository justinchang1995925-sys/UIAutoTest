"""Shared Appium driver fixture for generated UI tests."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest
from appium import webdriver
from appium.options.common import AppiumOptions


def _load_capabilities() -> dict:
    raw = os.getenv("APPIUM_CAPABILITIES")
    if raw:
        return json.loads(raw)

    path = Path(os.getenv("APPIUM_CAPABILITIES_FILE", "capabilities.json"))
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8-sig"))

    raise RuntimeError(
        "Missing Appium capabilities. Set APPIUM_CAPABILITIES or create capabilities.json."
    )


def _repair_uiautomator2_on_device() -> None:
    packages = (
        "io.appium.uiautomator2.server",
        "io.appium.uiautomator2.server.test",
    )
    try:
        subprocess.run(["adb", "version"], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return

    for package in packages:
        subprocess.run(
            ["adb", "shell", "am", "force-stop", package],
            check=False,
            capture_output=True,
            text=True,
        )
    time.sleep(2)


@pytest.fixture
def driver():
    server_url = os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723")
    options = AppiumOptions().load_capabilities(_load_capabilities())
    app_driver = webdriver.Remote(command_executor=server_url, options=options)
    try:
        yield app_driver
    finally:
        try:
            app_driver.quit()
        except Exception:
            pass
        if os.getenv("APPIUM_SKIP_U2_REPAIR", "").lower() not in {"1", "true", "yes"}:
            _repair_uiautomator2_on_device()
