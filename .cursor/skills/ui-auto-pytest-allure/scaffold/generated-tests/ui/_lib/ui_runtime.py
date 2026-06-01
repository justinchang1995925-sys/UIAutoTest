from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable

import allure
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from _lib.locator_chain import field_locators, step_locators


def _step_settle_seconds() -> float:
    raw = os.getenv("UIATEST_STEP_SETTLE_SEC", "0.5").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.5


def _settle_after_action() -> None:
    delay = _step_settle_seconds()
    if delay > 0:
        time.sleep(delay)


def _post_assert_timeout(step_timeout: int) -> int:
    raw = os.getenv("UIATEST_POST_ASSERT_TIMEOUT", "8").strip()
    try:
        cap = max(1, int(raw))
    except ValueError:
        cap = 8
    return min(int(step_timeout), cap)


def safe_click(element, retries: int = 3, refind: Callable[[], Any] | None = None) -> None:
    """Click with short retries; optionally re-find the element after stale errors."""
    last_error: Exception | None = None
    current = element
    for _ in range(max(1, retries)):
        try:
            current.click()
            return
        except (
            StaleElementReferenceException,
            ElementClickInterceptedException,
            ElementNotInteractableException,
        ) as exc:
            last_error = exc
            if refind is not None:
                try:
                    current = refind()
                except Exception:
                    pass
            time.sleep(0.35)
    if last_error is not None:
        raise last_error
    current.click()


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


def _chain_deadline(timeout: int) -> float:
    return time.monotonic() + max(1, int(timeout))


def _remaining_timeout(deadline: float) -> float:
    return max(0.1, deadline - time.monotonic())


def wait_visible_chain(driver, locators: list[dict[str, Any]], timeout: int):
    if not locators:
        raise ValueError("No locators provided.")
    if len(locators) == 1:
        return wait_visible(driver, locators[0], timeout)

    deadline = _chain_deadline(timeout)
    last_error: Exception | None = None
    for locator in locators:
        remaining = _remaining_timeout(deadline)
        if remaining <= 0.1:
            break
        try:
            element = wait_visible(driver, locator, max(1, int(remaining)))
            allure.attach(
                str(locator),
                name="locator_used_visible",
                attachment_type=allure.attachment_type.TEXT,
            )
            return element
        except TimeoutException as exc:
            last_error = exc
    raise TimeoutException(
        f"None of the locators became visible within {timeout}s: {locators}"
    ) from last_error


def wait_clickable_chain(driver, locators: list[dict[str, Any]], timeout: int):
    if not locators:
        raise ValueError("No locators provided.")
    if len(locators) == 1:
        return wait_clickable(driver, locators[0], timeout)

    deadline = _chain_deadline(timeout)
    last_error: Exception | None = None
    for locator in locators:
        if "coordinates" in locator:
            return locator
        remaining = _remaining_timeout(deadline)
        if remaining <= 0.1:
            break
        try:
            element = wait_clickable(driver, locator, max(1, int(remaining)))
            allure.attach(
                str(locator),
                name="locator_used_clickable",
                attachment_type=allure.attachment_type.TEXT,
            )
            return element
        except TimeoutException as exc:
            last_error = exc
    raise TimeoutException(
        f"None of the locators became clickable within {timeout}s: {locators}"
    ) from last_error


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


def _looks_like_switch(element) -> bool:
    class_name = str(
        element.get_attribute("className") or element.get_attribute("class") or ""
    )
    return "Switch" in class_name or "switch" in class_name.lower()


def _resolve_switch_element(label_element):
    if _looks_like_switch(label_element):
        return label_element
    return find_switch_near_label(label_element) or label_element


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


def _wait_not_visible_chain(driver, locators: list[dict[str, Any]], timeout: int) -> None:
    if not locators:
        raise AssertionError("No locators provided for not-visible assertion.")
    if len(locators) == 1:
        _by = by(locators[0])
        WebDriverWait(driver, timeout).until_not(EC.visibility_of_element_located(_by))
        return

    deadline = _chain_deadline(timeout)
    last_error: Exception | None = None
    for locator in locators:
        remaining = _remaining_timeout(deadline)
        if remaining <= 0.1:
            break
        _by = by(locator)
        try:
            WebDriverWait(driver, max(1, int(remaining))).until_not(
                EC.visibility_of_element_located(_by)
            )
            return
        except TimeoutException as exc:
            last_error = exc
    raise AssertionError(
        f"Element is still visible within {timeout}s: {locators}"
    ) from last_error


def set_switch_state(driver, locators: list[dict[str, Any]], desired_on: bool, timeout: int):
    label = wait_visible_chain(driver, locators, timeout)
    switch = _resolve_switch_element(label)

    def _refind_switch():
        refreshed = wait_visible_chain(driver, locators, timeout)
        return _resolve_switch_element(refreshed)

    if element_is_checked(switch) != desired_on:
        safe_click(switch, refind=_refind_switch)
        _settle_after_action()
        switch = _refind_switch()
    final_on = element_is_checked(switch)
    expected = "on" if desired_on else "off"
    actual = "on" if final_on else "off"
    assert final_on == desired_on, (
        f"Switch state mismatch for {locators}: expected {expected}, got {actual}"
    )


def post_assert(driver, step: dict[str, Any], timeout: int):
    assert_timeout = _post_assert_timeout(timeout)
    expect_visible = step.get("expect_visible")
    if isinstance(expect_visible, dict):
        wait_visible_chain(driver, field_locators(step, "expect_visible"), assert_timeout)
    expect_not_visible = step.get("expect_not_visible")
    if isinstance(expect_not_visible, dict):
        _wait_not_visible_chain(driver, field_locators(step, "expect_not_visible"), assert_timeout)
    expect_text = step.get("expect_text")
    if isinstance(expect_text, dict):
        locator = expect_text.get("locator")
        expected_value = expect_text.get("value")
        if isinstance(locator, dict) and expected_value is not None:
            locators = [locator]
            for item in expect_text.get("locators_fallback") or []:
                if isinstance(item, dict):
                    locators.append(item)
            element = wait_visible_chain(driver, locators, assert_timeout)
            actual = element.text or element.get_attribute("text") or ""
            expected = str(expected_value)
            if expect_text.get("contains", True):
                assert expected in actual, (
                    f"Expected text containing {expected!r}, got {actual!r}"
                )
            else:
                assert actual == expected, (
                    f"Expected text {expected!r}, got {actual!r}"
                )
    expect_switch = step.get("expect_switch")
    if expect_switch in {"on", "off"} and step.get("action") != "set_switch":
        desired_on = expect_switch == "on"
        locators = step_locators(step)
        label = wait_visible_chain(driver, locators, assert_timeout)
        switch = _resolve_switch_element(label)
        actual_on = element_is_checked(switch)
        expected = "on" if desired_on else "off"
        actual = "on" if actual_on else "off"
        assert actual_on == desired_on, (
            f"Switch state mismatch for {locators}: expected {expected}, got {actual}"
        )
    expect_activity = step.get("expect_activity")
    if isinstance(expect_activity, str) and expect_activity.strip():
        try:
            current = str(getattr(driver, "current_activity", "") or "")
        except Exception as exc:
            raise AssertionError(
                f"Could not read current activity for expect_activity {expect_activity!r}: {exc}"
            ) from exc
        assert expect_activity in current, (
            f"Expected activity containing {expect_activity!r}, got {current!r}"
        )


def run_step(driver, step: dict[str, Any], default_timeout: int):
    action = step["action"]
    timeout = int(step.get("timeout", default_timeout))
    locators = step_locators(step)

    if action in {"tap", "click"}:
        if locators and "coordinates" in locators[0]:
            point = locators[0]["coordinates"]
            tap_coordinates(driver, int(point["x"]), int(point["y"]))
            post_assert(driver, step, timeout)
            return
        element = wait_clickable_chain(driver, locators, timeout)

        def _refind_clickable():
            return wait_clickable_chain(driver, locators, timeout)

        safe_click(element, refind=_refind_clickable)
        _settle_after_action()
        post_assert(driver, step, timeout)
        return

    if action in {"input", "set_text"}:
        element = wait_visible_chain(driver, locators, timeout)
        if step.get("clear", True):
            element.clear()
        element.send_keys(str(step["value"]))
        _settle_after_action()
        post_assert(driver, step, timeout)
        return

    if action == "set_switch":
        desired_on = str(step.get("state", "")).lower() == "on"
        set_switch_state(driver, locators, desired_on, timeout)
        post_assert(driver, step, timeout)
        return

    if action == "assert_visible":
        wait_visible_chain(driver, locators, timeout)
        return

    if action == "assert_not_visible":
        _wait_not_visible_chain(driver, locators, timeout)
        return

    if action == "assert_text":
        element = wait_visible_chain(driver, locators, timeout)
        actual = element.text or element.get_attribute("text") or ""
        expected = str(step["value"])
        if step.get("contains", True):
            assert expected in actual, f"Expected text containing {expected!r}, got {actual!r}"
        else:
            assert actual == expected, f"Expected text {expected!r}, got {actual!r}"
        return

    if action == "wait_visible":
        wait_visible_chain(driver, locators, timeout)
        return

    if action == "sleep":
        time.sleep(float(step["seconds"]))
        return

    if action == "screenshot":
        file_name = str(step.get("file_name", "screenshot.png"))
        output_dir = Path("screenshots")
        output_dir.mkdir(exist_ok=True)
        file_path = output_dir / file_name
        driver.save_screenshot(str(file_path))
        allure.attach.file(
            str(file_path),
            name=file_name,
            attachment_type=allure.attachment_type.PNG,
        )
        return

    if action == "swipe":
        swipe(driver, step["start"], step["end"], int(step.get("duration_ms", 500)))
        return

    if action == "loop":
        raise ValueError("Loop steps must be handled by run_steps.")

    raise ValueError(f"Unsupported action: {action}")


def run_steps(driver, steps: list[dict[str, Any]], default_timeout: int):
    strict_warmup = os.getenv("UIATEST_STRICT_WARMUP", "").lower() in {"1", "true", "yes"}
    enable_warmup = os.getenv("UIATEST_WARMUP", "").lower() in {"1", "true", "yes"}

    if enable_warmup:
        for first in steps:
            if first.get("action") == "loop":
                continue
            locators = step_locators(first)
            if locators and "coordinates" not in locators[0]:
                try:
                    wait_visible_chain(driver, locators, int(first.get("timeout", default_timeout)))
                except TimeoutException as exc:
                    if strict_warmup:
                        raise TimeoutException(
                            f"First step target not visible before run: {locators}"
                        ) from exc
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
