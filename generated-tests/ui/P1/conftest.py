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


def _device_udid() -> str | None:
    serial = os.getenv("ANDROID_SERIAL", "").strip()
    if serial:
        return serial
    try:
        caps = _load_capabilities()
        udid = str(caps.get("appium:udid") or caps.get("udid") or "").strip()
        if udid and udid not in {"<ANDROID_UDID>", ""}:
            return udid
    except Exception:
        return None
    return None


def _adb_command(*args: str) -> list[str]:
    command = ["adb"]
    udid = _device_udid()
    if udid:
        command.extend(["-s", udid])
    command.extend(args)
    return command


def _repair_uiautomator2_on_device() -> None:
    packages = (
        "io.appium.uiautomator2.server",
        "io.appium.uiautomator2.server.test",
    )
    try:
        subprocess.run(_adb_command("version"), check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return

    for package in packages:
        subprocess.run(
            _adb_command("shell", "am", "force-stop", package),
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
            _adb_command("logcat", "-d", "-v", "time", "-t", str(lines)),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    output = (result.stdout or "").strip()
    return output or None


def _project_root() -> Path:
    current = Path.cwd().resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "generated-tests").is_dir() and (candidate / "cases").is_dir():
            return candidate
        if (candidate / "capabilities.local.json").is_file():
            return candidate
        if (candidate / "capabilities.json").is_file():
            return candidate
        if (candidate / "capabilities.template.json").is_file():
            return candidate
    return current


def _tail_text_file(path: Path, max_chars: int = 20000) -> str | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not text.strip():
        return None
    if len(text) > max_chars:
        return text[-max_chars:]
    return text


def _attach_appium_server_log_tail() -> None:
    log_path = _project_root() / "logs" / "appium-server.log"
    text = _tail_text_file(log_path)
    if text:
        _safe_attach_text("appium_server_log_tail", text)


def _screenrecord_on_failure(seconds: int = 12) -> Path | None:
    """Record a short failure video via adb and return local path."""
    if os.getenv("UIATEST_SCREENRECORD_ON_FAIL", "").lower() not in {"1", "true", "yes"}:
        return None
    try:
        subprocess.run(_adb_command("version"), check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return None

    remote = f"/sdcard/uiatest_fail_{int(time.time())}.mp4"
    local_dir = _project_root() / "artifacts"
    local_dir.mkdir(parents=True, exist_ok=True)
    local = local_dir / Path(remote).name

    subprocess.run(
        _adb_command("shell", "screenrecord", "--time-limit", str(int(seconds)), remote),
        check=False,
        capture_output=True,
        text=True,
    )
    subprocess.run(_adb_command("pull", remote, str(local)), check=False, capture_output=True, text=True)
    subprocess.run(_adb_command("shell", "rm", "-f", remote), check=False, capture_output=True, text=True)
    if local.exists() and local.stat().st_size > 0:
        return local
    return None


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

    _attach_appium_server_log_tail()

    video = _screenrecord_on_failure()
    if video:
        try:
            allure.attach.file(str(video), name=video.name, attachment_type=allure.attachment_type.MP4)
        except Exception:
            pass


@pytest.fixture
def driver():
    server_url = os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723")
    capabilities = _load_capabilities()
    options = AppiumOptions().load_capabilities(capabilities)
    app_driver = webdriver.Remote(command_executor=server_url, options=options)
    # Best-effort: bring target app to foreground to reduce flakiness.
    package = str(capabilities.get("appium:appPackage") or capabilities.get("appPackage") or "").strip()
    activity = str(capabilities.get("appium:appActivity") or capabilities.get("appActivity") or "").strip()
    try:
        if package and hasattr(app_driver, "activate_app"):
            app_driver.activate_app(package)
        if package and activity and hasattr(app_driver, "start_activity"):
            app_driver.start_activity(package, activity)
    except Exception:
        pass
    try:
        yield app_driver
    finally:
        try:
            app_driver.quit()
        except Exception:
            pass
        if os.getenv("APPIUM_SKIP_U2_REPAIR", "").lower() not in {"1", "true", "yes"}:
            _repair_uiautomator2_on_device()
