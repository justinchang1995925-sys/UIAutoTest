"""Shared Appium driver fixture for generated UI tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import allure
import pytest
from appium import webdriver
from appium.options.common import AppiumOptions
from appium.webdriver.common.appiumby import AppiumBy


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


def _adb_executable() -> str:
    return shutil.which("adb") or "adb"


def _adb_command(*args: str) -> list[str]:
    command = [_adb_executable()]
    udid = _device_udid()
    if udid:
        command.extend(["-s", udid])
    command.extend(args)
    return command


def _inspector_keepalive_active() -> bool:
    root = _project_root()
    scripts = root / ".cursor" / "skills" / "ui-auto-pytest-allure" / "scripts"
    if scripts.is_dir():
        script_str = str(scripts)
        if script_str not in sys.path:
            sys.path.insert(0, script_str)
        try:
            from inspector_session import is_keepalive_running

            return is_keepalive_running(root)
        except Exception:
            pass
    return False


def _repair_uiautomator2_on_device() -> None:
    if os.getenv("APPIUM_SKIP_U2_REPAIR", "").lower() in {"1", "true", "yes"}:
        return
    if _inspector_keepalive_active():
        return
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


def _app_startup_delay() -> float:
    raw = os.getenv("UIATEST_APP_STARTUP_SEC", "0.5").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.5


def _entry_settle_seconds() -> float:
    raw = os.getenv("UIATEST_ENTRY_SETTLE_SEC", "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
    return _app_startup_delay()


def _entry_ready_timeout() -> int:
    raw = os.getenv("UIATEST_ENTRY_READY_TIMEOUT", "30").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 30


def _entry_ready_locators(package: str) -> list[dict[str, str]]:
    raw = os.getenv("UIATEST_ENTRY_READY_LOCATORS", "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict) and parsed:
            return [parsed]
        if isinstance(parsed, list):
            locators = [item for item in parsed if isinstance(item, dict) and item]
            if locators:
                return locators

    ready_id = os.getenv("UIATEST_ENTRY_READY_ID", "").strip()
    if ready_id and ready_id.lower() not in {"0", "false", "none", "skip"}:
        if ready_id.startswith("//"):
            return [{"xpath": ready_id}]
        if ready_id.startswith("new UiSelector"):
            return [{"android_uiautomator": ready_id}]
        if ":id/" in ready_id or ready_id.count(":") >= 2:
            return [{"id": ready_id}]
        if package:
            suffix = ready_id if ready_id.startswith("id/") else f"id/{ready_id}"
            return [{"id": f"{package}:{suffix}"}]
        return [{"id": ready_id}]

    if not package:
        return []

    # Home screen: settings entry may be tvSettings, its parent btnSettings, or ivSettings.
    default_ids = ("btnSettings", "tvSettings", "ivSettings")
    return [{"id": f"{package}:id/{resource_id}"} for resource_id in default_ids]


def _wait_for_entry_ready(driver, package: str) -> None:
    settle = _entry_settle_seconds()
    if settle > 0:
        time.sleep(settle)

    locators = _entry_ready_locators(package)
    if not locators:
        return

    timeout = _entry_ready_timeout()
    from _lib.ui_runtime import wait_visible_chain

    wait_visible_chain(driver, locators, timeout)


def _entry_visible(driver, package: str, timeout: int = 2) -> bool:
    locators = _entry_ready_locators(package)
    if not locators:
        return True
    from _lib.ui_runtime import wait_visible_chain

    try:
        wait_visible_chain(driver, locators, timeout)
        return True
    except Exception:
        return False


def _try_dismiss_overlay(driver, package: str) -> bool:
    for resource_id in ("iv_close", "btn_close", "iv_back", "btn_back"):
        try:
            element = driver.find_element(AppiumBy.ID, f"{package}:id/{resource_id}")
            if element.is_displayed():
                element.click()
                time.sleep(0.4)
                return True
        except Exception:
            continue
    return False


def _start_entry_activity_adb(pkg: str, act: str) -> None:
    subprocess.run(
        _adb_command(
            "shell",
            "am",
            "start",
            "-S",
            "-n",
            f"{pkg}/{act}",
        ),
        check=False,
        capture_output=True,
        text=True,
    )


def _leave_settings_to_home(driver, pkg: str) -> None:
    for _ in range(8):
        if _entry_visible(driver, pkg, timeout=1):
            return
        if _try_dismiss_overlay(driver, pkg):
            continue
        clicked = False
        for resource_id in ("back", "iv_back", "btn_back"):
            try:
                element = driver.find_element(AppiumBy.ID, f"{pkg}:id/{resource_id}")
                if element.is_displayed():
                    element.click()
                    clicked = True
                    time.sleep(0.35)
                    break
            except Exception:
                continue
        if clicked:
            continue
        try:
            driver.press_keycode(4)
        except Exception:
            pass
        time.sleep(0.35)


def _navigate_to_home_entry(driver, pkg: str, act: str) -> None:
    """Return to HomeActivity even when a settings/password overlay is still open."""
    if os.getenv("UIATEST_SKIP_START_ACTIVITY", "").lower() in {"1", "true", "yes"}:
        _wait_for_entry_ready(driver, pkg)
        return

    max_backs = 6
    raw = os.getenv("UIATEST_ENTRY_MAX_BACK", "").strip()
    if raw:
        try:
            max_backs = max(1, int(raw))
        except ValueError:
            pass

    def _restart_app() -> None:
        if pkg and hasattr(driver, "terminate_app"):
            try:
                driver.terminate_app(pkg)
                time.sleep(0.6)
            except Exception:
                pass
        if pkg and act:
            _start_entry_activity_adb(pkg, act)
        elif pkg and hasattr(driver, "activate_app"):
            try:
                driver.activate_app(pkg)
                time.sleep(0.6)
            except Exception:
                pass
        if pkg and act and hasattr(driver, "start_activity"):
            try:
                driver.start_activity(pkg, act)
            except Exception:
                pass

    _restart_app()
    settle = _entry_settle_seconds()
    if settle > 0:
        time.sleep(settle)

    if not _entry_visible(driver, pkg, timeout=4):
        _leave_settings_to_home(driver, pkg)

    if _entry_visible(driver, pkg, timeout=2):
        return

    for _ in range(max_backs):
        _try_dismiss_overlay(driver, pkg)
        _leave_settings_to_home(driver, pkg)
        if _entry_visible(driver, pkg, timeout=2):
            return
        try:
            driver.press_keycode(4)
        except Exception:
            pass
        time.sleep(0.35)

    _restart_app()
    if settle > 0:
        time.sleep(settle)
    _leave_settings_to_home(driver, pkg)
    _wait_for_entry_ready(driver, pkg)


def _reset_to_entry_activity(driver, pkg: str, act: str) -> None:
    """Gently launch entry Activity via Appium APIs only (no adb force-stop)."""
    _navigate_to_home_entry(driver, pkg, act)


@pytest.fixture
def driver():
    server_url = os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723")
    capabilities = _load_capabilities()
    options = AppiumOptions().load_capabilities(capabilities)
    app_driver = webdriver.Remote(command_executor=server_url, options=options)
    try:
        app_driver.implicitly_wait(0)
    except Exception:
        pass
    package = str(capabilities.get("appium:appPackage") or capabilities.get("appPackage") or "").strip()
    activity = str(capabilities.get("appium:appActivity") or capabilities.get("appActivity") or "").strip()
    if (
        package
        and activity
        and _per_test_entry_enabled(activity)
        and hasattr(app_driver, "start_activity")
        and os.getenv("UIATEST_SKIP_START_ACTIVITY", "").lower() not in {"1", "true", "yes"}
    ):
        _reset_to_entry_activity(app_driver, package, activity)
    else:
        startup_delay = _app_startup_delay()
        if startup_delay > 0:
            time.sleep(startup_delay)
    try:
        yield app_driver
    finally:
        try:
            app_driver.quit()
        except Exception:
            pass


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    if os.getenv("APPIUM_SKIP_U2_REPAIR", "").lower() in {"1", "true", "yes"}:
        return
    if os.getenv("UIATEST_DEFER_U2_REPAIR", "").lower() in {"1", "true", "yes"}:
        return
    _repair_uiautomator2_on_device()


def _entry_package_activity() -> tuple[str, str]:
    caps = _load_capabilities()
    pkg = os.getenv("UIATEST_START_PACKAGE", "").strip() or str(
        caps.get("appium:appPackage") or caps.get("appPackage") or ""
    ).strip()
    act = os.getenv("UIATEST_START_ACTIVITY", "").strip() or str(
        caps.get("appium:appActivity") or caps.get("appActivity") or ""
    ).strip()
    return pkg, act


def _is_activity_configured(activity: str) -> bool:
    value = (activity or "").strip()
    if not value:
        return False
    # Treat template placeholders as "not configured".
    if value.startswith("<") and value.endswith(">"):
        return False
    return True


def _per_test_entry_enabled(activity: str) -> bool:
    raw = os.getenv("UIATEST_PER_TEST_ENTRY", "").strip().lower()
    if raw in {"0", "false", "no"}:
        return False
    if raw in {"1", "true", "yes"}:
        return _is_activity_configured(activity)
    return _is_activity_configured(activity)
