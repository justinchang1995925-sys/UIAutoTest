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

import time
from pathlib import Path

import allure
import pytest
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


DEFAULT_TIMEOUT = {timeout}

STEPS = {steps_literal}


def _by(locator: dict):
    key, value = next(iter(locator.items()))
    mapping = {{
        "id": AppiumBy.ID,
        "accessibility_id": AppiumBy.ACCESSIBILITY_ID,
        "xpath": AppiumBy.XPATH,
        "css": AppiumBy.CSS_SELECTOR,
        "name": AppiumBy.NAME,
        "class_name": AppiumBy.CLASS_NAME,
        "android_uiautomator": AppiumBy.ANDROID_UIAUTOMATOR,
        "ios_predicate": AppiumBy.IOS_PREDICATE,
        "ios_class_chain": AppiumBy.IOS_CLASS_CHAIN,
    }}
    if key == "coordinates":
        return None
    if key not in mapping:
        raise ValueError(f"Unsupported locator type: {{key}}")
    return mapping[key], value


def _wait_for_element(driver, locator: dict, timeout: int = DEFAULT_TIMEOUT):
    by = _by(locator)
    if by is None:
        raise ValueError("Coordinate locator cannot be used to find an element.")
    return WebDriverWait(driver, timeout).until(EC.visibility_of_element_located(by))


def _tap_coordinates(driver, x: int, y: int):
    finger = PointerInput("touch", "finger")
    actions = ActionBuilder(driver, mouse=finger)
    actions.pointer_action.move_to_location(x, y)
    actions.pointer_action.pointer_down()
    actions.pointer_action.pause(0.05)
    actions.pointer_action.pointer_up()
    actions.perform()


def _swipe(driver, start: dict, end: dict, duration_ms: int = 500):
    finger = PointerInput("touch", "finger")
    actions = ActionBuilder(driver, mouse=finger)
    actions.pointer_action.move_to_location(start["x"], start["y"])
    actions.pointer_action.pointer_down()
    actions.pointer_action.pause(duration_ms / 1000)
    actions.pointer_action.move_to_location(end["x"], end["y"])
    actions.pointer_action.pointer_up()
    actions.perform()


def _screenshot(driver, file_name: str):
    output_dir = Path("screenshots")
    output_dir.mkdir(exist_ok=True)
    file_path = output_dir / file_name
    driver.save_screenshot(str(file_path))
    allure.attach.file(str(file_path), name=file_name, attachment_type=allure.attachment_type.PNG)


def _element_is_checked(element) -> bool:
    for attribute in ("checked", "selected"):
        value = element.get_attribute(attribute)
        if value is not None:
            return str(value).lower() == "true"
    return False


def _find_switch_near_label(label_element):
    switch_xpaths = [
        "./following-sibling::android.widget.Switch",
        "./following-sibling::*[contains(@class,'Switch')]",
        "./parent::*/android.widget.Switch",
        "./parent::*//android.widget.Switch",
        "./ancestor::*[1]//android.widget.Switch",
        "./ancestor::*[2]//android.widget.Switch",
    ]
    for xpath in switch_xpaths:
        elements = label_element.find_elements(AppiumBy.XPATH, xpath)
        if elements:
            return elements[0]
    return None


def _set_switch_state(driver, locator: dict, desired_on: bool, timeout: int):
    label = _wait_for_element(driver, locator, timeout)
    switch = _find_switch_near_label(label) or label
    if _element_is_checked(switch) != desired_on:
        switch.click()
    final_on = _element_is_checked(switch)
    expected = "on" if desired_on else "off"
    actual = "on" if final_on else "off"
    assert final_on == desired_on, (
        f"Switch state mismatch for {{locator}}: expected {{expected}}, got {{actual}}"
    )


def _run_step(driver, step: dict):
    action = step["action"]
    timeout = int(step.get("timeout", DEFAULT_TIMEOUT))
    locator = step.get("locator")

    if action in {{"tap", "click"}}:
        if locator and "coordinates" in locator:
            point = locator["coordinates"]
            _tap_coordinates(driver, int(point["x"]), int(point["y"]))
            return
        _wait_for_element(driver, locator, timeout).click()
        return

    if action in {{"input", "set_text"}}:
        element = _wait_for_element(driver, locator, timeout)
        if step.get("clear", True):
            element.clear()
        element.send_keys(str(step["value"]))
        return

    if action == "set_switch":
        desired_on = str(step.get("state", "")).lower() == "on"
        _set_switch_state(driver, locator, desired_on, timeout)
        return

    if action == "assert_visible":
        _wait_for_element(driver, locator, timeout)
        return

    if action == "assert_not_visible":
        by = _by(locator)
        try:
            WebDriverWait(driver, timeout).until_not(EC.visibility_of_element_located(by))
        except TimeoutException as exc:
            raise AssertionError(f"Element is still visible: {{locator}}") from exc
        return

    if action == "assert_text":
        element = _wait_for_element(driver, locator, timeout)
        actual = element.text or element.get_attribute("text") or ""
        expected = str(step["value"])
        if step.get("contains", True):
            assert expected in actual, f"Expected text containing {{expected!r}}, got {{actual!r}}"
        else:
            assert actual == expected, f"Expected text {{expected!r}}, got {{actual!r}}"
        return

    if action == "wait_visible":
        _wait_for_element(driver, locator, timeout)
        return

    if action == "sleep":
        time.sleep(float(step["seconds"]))
        return

    if action == "screenshot":
        _screenshot(driver, step.get("file_name", "screenshot.png"))
        return

    if action == "swipe":
        _swipe(driver, step["start"], step["end"], int(step.get("duration_ms", 500)))
        return

    if action == "loop":
        raise ValueError("Loop steps must be handled by _run_steps.")

    raise ValueError(f"Unsupported action: {{action}}")


def _run_steps(driver, steps: list[dict]):
    for index, step in enumerate(steps, start=1):
        if step["action"] == "loop":
            from_step = int(step["from_step"])
            to_step = int(step["to_step"])
            times = int(step.get("times", 1))
            loop_steps = steps[from_step - 1:to_step]
            for loop_index in range(1, times + 1):
                with allure.step(f"{{step.get('name', 'Loop')}} #{{loop_index}}"):
                    _run_steps(driver, loop_steps)
            continue

        with allure.step(step.get("name", step["action"])):
            _run_step(driver, step)


@allure.suite({suite!r})
@allure.feature({feature!r})
@allure.story({story!r})
@allure.title({title!r})
@allure.description({description!r})
@allure.severity({severity!r})
@pytest.mark.ui
@pytest.mark.{priority}
def test_{test_name}(driver):
    _run_steps(driver, STEPS)
'''


def build_conftest() -> str:
    return '''"""Shared Appium driver fixture for generated UI tests."""

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
