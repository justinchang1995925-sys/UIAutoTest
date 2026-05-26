"""Generated UI automation test.

Source spec: setting_password_idle_lock
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


DEFAULT_TIMEOUT = 10

STEPS = [
    {
        "name": "Step 1 Tap id:com.pudutech.business.function:id/tvSettings",
        "action": "tap",
        "locator": {
            "id": "com.pudutech.business.function:id/tvSettings"
        }
    },
    {
        "name": "Step 2 Tap 密码与安全",
        "action": "tap",
        "locator": {
            "android_uiautomator": "new UiSelector().text(\"密码与安全\")"
        }
    },
    {
        "name": "Step 3 Tap 电机锁",
        "action": "tap",
        "locator": {
            "android_uiautomator": "new UiSelector().text(\"电机锁\")"
        }
    },
    {
        "name": "Step 4 set switch id:com.pudutech.business.function:id/idle_lock_switch 关闭",
        "action": "set_switch",
        "locator": {
            "id": "com.pudutech.business.function:id/idle_lock_switch"
        },
        "state": "off"
    }
]


def _by(locator: dict):
    key, value = next(iter(locator.items()))
    mapping = {
        "id": AppiumBy.ID,
        "accessibility_id": AppiumBy.ACCESSIBILITY_ID,
        "xpath": AppiumBy.XPATH,
        "css": AppiumBy.CSS_SELECTOR,
        "name": AppiumBy.NAME,
        "class_name": AppiumBy.CLASS_NAME,
        "android_uiautomator": AppiumBy.ANDROID_UIAUTOMATOR,
        "ios_predicate": AppiumBy.IOS_PREDICATE,
        "ios_class_chain": AppiumBy.IOS_CLASS_CHAIN,
    }
    if key == "coordinates":
        return None
    if key not in mapping:
        raise ValueError(f"Unsupported locator type: {key}")
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
        f"Switch state mismatch for {locator}: expected {expected}, got {actual}"
    )


def _run_step(driver, step: dict):
    action = step["action"]
    timeout = int(step.get("timeout", DEFAULT_TIMEOUT))
    locator = step.get("locator")

    if action in {"tap", "click"}:
        if locator and "coordinates" in locator:
            point = locator["coordinates"]
            _tap_coordinates(driver, int(point["x"]), int(point["y"]))
            return
        _wait_for_element(driver, locator, timeout).click()
        return

    if action in {"input", "set_text"}:
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
            raise AssertionError(f"Element is still visible: {locator}") from exc
        return

    if action == "assert_text":
        element = _wait_for_element(driver, locator, timeout)
        actual = element.text or element.get_attribute("text") or ""
        expected = str(step["value"])
        if step.get("contains", True):
            assert expected in actual, f"Expected text containing {expected!r}, got {actual!r}"
        else:
            assert actual == expected, f"Expected text {expected!r}, got {actual!r}"
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

    raise ValueError(f"Unsupported action: {action}")


def _run_steps(driver, steps: list[dict]):
    for index, step in enumerate(steps, start=1):
        if step["action"] == "loop":
            from_step = int(step["from_step"])
            to_step = int(step["to_step"])
            times = int(step.get("times", 1))
            loop_steps = steps[from_step - 1:to_step]
            for loop_index in range(1, times + 1):
                with allure.step(f"{step.get('name', 'Loop')} #{loop_index}"):
                    _run_steps(driver, loop_steps)
            continue

        with allure.step(step.get("name", step["action"])):
            _run_step(driver, step)


@allure.suite('UI Automation')
@allure.feature('密码与安全')
@allure.story('进入设置-密码与安全-电机锁-关闭空闲时锁电机')
@allure.title('进入设置-密码与安全-电机锁-关闭空闲时锁电机')
@allure.description('Generated from natural language: 进入设置-密码与安全-电机锁-关闭空闲时锁电机')
@allure.severity('critical')
@pytest.mark.ui
@pytest.mark.P1
def test_setting_password_idle_lock(driver):
    _run_steps(driver, STEPS)
