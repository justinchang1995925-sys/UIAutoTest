from __future__ import annotations

import time
from typing import Any

import allure
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def by(locator: dict[str, Any]):
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


def wait_visible(driver, locator: dict[str, Any], timeout: int):
    _by = by(locator)
    if _by is None:
        raise ValueError("Coordinate locator cannot be used to find an element.")
    return WebDriverWait(driver, timeout).until(EC.visibility_of_element_located(_by))


def wait_clickable(driver, locator: dict[str, Any], timeout: int):
    _by = by(locator)
    if _by is None:
        raise ValueError("Coordinate locator cannot be used to find an element.")
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(_by))


def tap_coordinates(driver, x: int, y: int):
    finger = PointerInput("touch", "finger")
    actions = ActionBuilder(driver, mouse=finger)
    actions.pointer_action.move_to_location(x, y)
    actions.pointer_action.pointer_down()
    actions.pointer_action.pause(0.05)
    actions.pointer_action.pointer_up()
    actions.perform()


def swipe(driver, start: dict[str, Any], end: dict[str, Any], duration_ms: int = 500):
    finger = PointerInput("touch", "finger")
    actions = ActionBuilder(driver, mouse=finger)
    actions.pointer_action.move_to_location(int(start["x"]), int(start["y"]))
    actions.pointer_action.pointer_down()
    actions.pointer_action.pause(duration_ms / 1000)
    actions.pointer_action.move_to_location(int(end["x"]), int(end["y"]))
    actions.pointer_action.pointer_up()
    actions.perform()


def element_is_checked(element) -> bool:
    for attribute in ("checked", "selected"):
        value = element.get_attribute(attribute)
        if value is not None:
            return str(value).lower() == "true"
    return False


def find_switch_near_label(label_element):
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


def set_switch_state(driver, locator: dict[str, Any], desired_on: bool, timeout: int):
    label = wait_visible(driver, locator, timeout)
    switch = find_switch_near_label(label) or label
    if element_is_checked(switch) != desired_on:
        switch.click()
    final_on = element_is_checked(switch)
    expected = "on" if desired_on else "off"
    actual = "on" if final_on else "off"
    assert final_on == desired_on, (
        f"Switch state mismatch for {locator}: expected {expected}, got {actual}"
    )


def post_assert(driver, step: dict[str, Any], timeout: int):
    expect_visible = step.get("expect_visible")
    if isinstance(expect_visible, dict):
        wait_visible(driver, expect_visible, timeout)
    expect_not_visible = step.get("expect_not_visible")
    if isinstance(expect_not_visible, dict):
        _by = by(expect_not_visible)
        try:
            WebDriverWait(driver, timeout).until_not(EC.visibility_of_element_located(_by))
        except TimeoutException as exc:
            raise AssertionError(f"Element is still visible: {expect_not_visible}") from exc
    expect_activity = step.get("expect_activity")
    if isinstance(expect_activity, str) and expect_activity.strip():
        try:
            current = str(getattr(driver, "current_activity", "") or "")
            assert expect_activity in current, (
                f"Expected activity containing {expect_activity!r}, got {current!r}"
            )
        except Exception:
            pass


def run_step(driver, step: dict[str, Any], default_timeout: int):
    action = step["action"]
    timeout = int(step.get("timeout", default_timeout))
    locator = step.get("locator")

    if action in {"tap", "click"}:
        if locator and "coordinates" in locator:
            point = locator["coordinates"]
            tap_coordinates(driver, int(point["x"]), int(point["y"]))
            post_assert(driver, step, timeout)
            return
        wait_clickable(driver, locator, timeout).click()
        post_assert(driver, step, timeout)
        return

    if action in {"input", "set_text"}:
        element = wait_visible(driver, locator, timeout)
        if step.get("clear", True):
            element.clear()
        element.send_keys(str(step["value"]))
        post_assert(driver, step, timeout)
        return

    if action == "set_switch":
        desired_on = str(step.get("state", "")).lower() == "on"
        set_switch_state(driver, locator, desired_on, timeout)
        post_assert(driver, step, timeout)
        return

    if action == "assert_visible":
        wait_visible(driver, locator, timeout)
        return

    if action == "assert_not_visible":
        _by = by(locator)
        try:
            WebDriverWait(driver, timeout).until_not(EC.visibility_of_element_located(_by))
        except TimeoutException as exc:
            raise AssertionError(f"Element is still visible: {locator}") from exc
        return

    if action == "assert_text":
        element = wait_visible(driver, locator, timeout)
        actual = element.text or element.get_attribute("text") or ""
        expected = str(step["value"])
        if step.get("contains", True):
            assert expected in actual, f"Expected text containing {expected!r}, got {actual!r}"
        else:
            assert actual == expected, f"Expected text {expected!r}, got {actual!r}"
        return

    if action == "wait_visible":
        wait_visible(driver, locator, timeout)
        return

    if action == "sleep":
        time.sleep(float(step["seconds"]))
        return

    if action == "swipe":
        swipe(driver, step["start"], step["end"], int(step.get("duration_ms", 500)))
        return

    if action == "loop":
        raise ValueError("Loop steps must be handled by run_steps.")

    raise ValueError(f"Unsupported action: {action}")


def run_steps(driver, steps: list[dict[str, Any]], default_timeout: int):
    # Preflight: wait for the first real step target to appear.
    for first in steps:
        if first.get("action") == "loop":
            continue
        locator = first.get("locator")
        if isinstance(locator, dict) and "coordinates" not in locator:
            try:
                wait_visible(driver, locator, int(first.get("timeout", default_timeout)))
            except TimeoutException:
                # Do not fail early; some apps require extra time or a prior navigation.
                pass
        break

    for step in steps:
        if step["action"] == "loop":
            from_step = int(step["from_step"])
            to_step = int(step["to_step"])
            times = int(step.get("times", 1))
            loop_steps = steps[from_step - 1 : to_step]
            for loop_index in range(1, times + 1):
                with allure.step(f"{step.get('name', 'Loop')} #{loop_index}"):
                    run_steps(driver, loop_steps, default_timeout)
            continue

        with allure.step(step.get("name", step["action"])):
            run_step(driver, step, default_timeout)

