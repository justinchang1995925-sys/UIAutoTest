"""Shared Appium driver fixture for generated UI tests."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import allure
import pytest
from appium import webdriver
from appium.options.common import AppiumOptions


def _load_capabilities() -> dict:
    raw = os.getenv("APPIUM_CAPABILITIES")
    if raw:
        return json.loads(raw)

    preferred = os.getenv("APPIUM_CAPABILITIES_FILE", "").strip()
    if preferred:
        path = Path(preferred)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))

    candidates = [
        Path("capabilities.local.json"),
        Path("capabilities.json"),
        Path("capabilities.template.json"),
    ]
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))

    raise RuntimeError(
        "Missing Appium capabilities. Set APPIUM_CAPABILITIES or create one of: "
        "capabilities.local.json / capabilities.json / capabilities.template.json"
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


def _safe_attach_text(name: str, content: str) -> None:
    try:
        allure.attach(content, name=name, attachment_type=allure.attachment_type.TEXT)
    except Exception:
        pass


def _safe_attach_png(name: str, png_bytes: bytes) -> None:
    try:
        allure.attach(png_bytes, name=name, attachment_type=allure.attachment_type.PNG)
    except Exception:
        pass


def _adb_logcat_tail(lines: int = 250) -> str | None:
    try:
        result = subprocess.run(
            ["adb", "logcat", "-d", "-v", "time", "-t", str(lines)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    output = (result.stdout or "").strip()
    return output or None


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return

    driver = item.funcargs.get("driver")
    if not driver:
        return

    try:
        _safe_attach_png("failure_screenshot", driver.get_screenshot_as_png())
    except Exception:
        pass

    try:
        _safe_attach_text("page_source.xml", driver.page_source)
    except Exception:
        pass

    try:
        activity = getattr(driver, "current_activity", None)
        if activity:
            _safe_attach_text("current_activity", str(activity))
    except Exception:
        pass

    # Prefer Appium logcat if available; fall back to adb logcat.
    logcat_text = None
    try:
        entries = driver.get_log("logcat")
        if entries:
            logcat_text = "\n".join(
                f'{e.get("timestamp", "")} {e.get("level", "")} {e.get("message", "")}'.rstrip()
                for e in entries
            ).strip()
    except Exception:
        logcat_text = None

    if not logcat_text:
        logcat_text = _adb_logcat_tail()
    if logcat_text:
        _safe_attach_text("logcat_tail", logcat_text)


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
