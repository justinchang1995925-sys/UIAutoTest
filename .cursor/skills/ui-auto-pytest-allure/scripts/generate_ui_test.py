#!/usr/bin/env python3
"""Generate pytest + Allure + Appium UI tests from a JSON case spec."""

from __future__ import annotations

import argparse
import json
import re
import textwrap
from pathlib import Path
from typing import Any


SUPPORTED_ACTIONS = {
    "tap",
    "click",
    "input",
    "set_text",
    "set_switch",
    "assert_visible",
    "assert_not_visible",
    "assert_text",
    "wait_visible",
    "sleep",
    "screenshot",
    "swipe",
    "loop",
}

SUPPORTED_LOCATORS = {
    "id",
    "accessibility_id",
    "xpath",
    "css",
    "name",
    "class_name",
    "android_uiautomator",
    "ios_predicate",
    "ios_class_chain",
    "coordinates",
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip()).strip("_").lower()
    return slug or "generated_ui_case"


def load_spec(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON spec: {path}: {exc}") from exc


def validate_spec(spec: dict[str, Any]) -> None:
    priority = str(spec.get("priority", "P2")).upper()
    if priority not in {"P0", "P1", "P2", "P3", "P4"}:
        raise SystemExit("Spec priority must be one of: P0, P1, P2, P3, P4.")

    if not isinstance(spec.get("steps"), list) or not spec["steps"]:
        raise SystemExit("Spec must contain a non-empty 'steps' list.")

    for index, step in enumerate(spec["steps"], start=1):
        if not isinstance(step, dict):
            raise SystemExit(f"Step {index} must be an object.")

        action = step.get("action")
        if action not in SUPPORTED_ACTIONS:
            supported = ", ".join(sorted(SUPPORTED_ACTIONS))
            raise SystemExit(f"Step {index} has unsupported action '{action}'. Supported: {supported}")

        if action == "sleep":
            if "seconds" not in step:
                raise SystemExit(f"Step {index} sleep action requires 'seconds'.")
            continue

        if action == "screenshot":
            continue

        if action == "swipe":
            if not isinstance(step.get("start"), dict) or not isinstance(step.get("end"), dict):
                raise SystemExit(f"Step {index} swipe action requires 'start' and 'end' coordinates.")
            continue

        if action == "loop":
            if not isinstance(step.get("from_step"), int) or not isinstance(step.get("to_step"), int):
                raise SystemExit(f"Step {index} loop action requires integer 'from_step' and 'to_step'.")
            if int(step.get("times", 1)) < 1:
                raise SystemExit(f"Step {index} loop action requires 'times' greater than 0.")
            continue

        locator = step.get("locator")
        if not isinstance(locator, dict) or len(locator) != 1:
            raise SystemExit(f"Step {index} requires a locator object with exactly one locator key.")

        key = next(iter(locator))
        if key not in SUPPORTED_LOCATORS:
            supported = ", ".join(sorted(SUPPORTED_LOCATORS))
            raise SystemExit(f"Step {index} has unsupported locator '{key}'. Supported: {supported}")

        fallbacks = step.get("locators_fallback")
        if fallbacks is not None:
            if not isinstance(fallbacks, list):
                raise SystemExit(f"Step {index} locators_fallback must be a list.")
            for fb_index, fb in enumerate(fallbacks, start=1):
                if not isinstance(fb, dict) or len(fb) != 1:
                    raise SystemExit(
                        f"Step {index} locators_fallback[{fb_index}] must be a single-key locator object."
                    )
                fb_key = next(iter(fb))
                if fb_key not in SUPPORTED_LOCATORS:
                    raise SystemExit(
                        f"Step {index} locators_fallback[{fb_index}] has unsupported locator '{fb_key}'."
                    )

        if action in {"input", "set_text", "assert_text"} and "value" not in step:
            raise SystemExit(f"Step {index} action '{action}' requires 'value'.")

        if action == "set_switch":
            state = str(step.get("state", "")).strip().lower()
            if state not in {"on", "off"}:
                raise SystemExit(f"Step {index} set_switch action requires state 'on' or 'off'.")


def json_literal(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=4)


def build_test_file(spec: dict[str, Any]) -> str:
    test_name = slugify(str(spec.get("test_name") or spec.get("title") or "generated_ui_case"))
    suite = spec.get("suite", "UI Automation")
    feature = spec.get("feature", "Generated UI Case")
    story = spec.get("story", test_name.replace("_", " ").title())
    title = spec.get("title", story)
    description = spec.get("description", "")
    priority = str(spec.get("priority", "P2")).upper()
    severity_map = {
        "P0": "blocker",
        "P1": "critical",
        "P2": "normal",
        "P3": "minor",
        "P4": "trivial",
    }
    severity = severity_map.get(priority, "normal")
    timeout = int(spec.get("timeout", 10))
    steps_literal = json_literal(spec["steps"])

    return f'''"""Generated UI automation test.

Source spec: {test_name}
"""

from __future__ import annotations

import sys
from pathlib import Path

import allure
import pytest

# Ensure generated-tests/ui is on sys.path so we can import shared helpers.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _lib.ui_runtime import run_steps  # noqa: E402


DEFAULT_TIMEOUT = {timeout}

STEPS = {steps_literal}


@allure.suite({suite!r})
@allure.feature({feature!r})
@allure.story({story!r})
@allure.title({title!r})
@allure.description({description!r})
@allure.severity({severity!r})
@pytest.mark.ui
@pytest.mark.{priority}
def test_{test_name}(driver):
    run_steps(driver, STEPS, DEFAULT_TIMEOUT)
'''


def build_conftest() -> str:
    return '''"""Shared Appium driver fixture for generated UI tests."""

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

    logcat_text = None
    try:
        entries = driver.get_log("logcat")
        if entries:
            logcat_text = "\\n".join(
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
'''


def build_requirements() -> str:
    return """pytest
allure-pytest
Appium-Python-Client
selenium
"""


def build_pytest_ini() -> str:
    return """[pytest]
markers =
    ui: generated UI automation tests
    P0: blocker smoke/regression cases
    P1: critical regression cases
    P2: normal regression cases
    P3: minor regression cases
    P4: trivial regression cases
"""


def write_outputs(spec: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    test_name = slugify(str(spec.get("test_name") or spec.get("title") or "generated_ui_case"))
    test_path = output_dir / f"test_{test_name}.py"
    test_path.write_text(build_test_file(spec), encoding="utf-8")

    conftest_path = output_dir / "conftest.py"
    if not conftest_path.exists():
        conftest_path.write_text(build_conftest(), encoding="utf-8")

    requirements_path = output_dir / "requirements.txt"
    if not requirements_path.exists():
        requirements_path.write_text(build_requirements(), encoding="utf-8")

    pytest_ini_path = output_dir / "pytest.ini"
    if not pytest_ini_path.exists():
        pytest_ini_path.write_text(build_pytest_ini(), encoding="utf-8")

    return test_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="Path to the JSON UI test spec.")
    parser.add_argument("--output", type=Path, default=Path("tests/ui"), help="Output test directory.")
    args = parser.parse_args()

    spec = load_spec(args.spec)
    validate_spec(spec)
    test_path = write_outputs(spec, args.output)
    print(f"Generated: {test_path}")
    print(f"Run: pytest {args.output} --alluredir=allure-results")


if __name__ == "__main__":
    main()
