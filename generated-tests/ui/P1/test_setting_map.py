"""Generated UI automation test.

Source spec: setting_map
"""

from __future__ import annotations

import sys
from pathlib import Path

import allure
import pytest

# Ensure generated-tests/ui is on sys.path so we can import shared helpers.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _lib.ui_runtime import run_steps  # noqa: E402


DEFAULT_TIMEOUT = 15

STEPS = [{'name': 'Step 1 Tap id:com.pudutech.business.function:id/btnSettings', 'action': 'tap', 'locator': {'id': 'com.pudutech.business.function:id/btnSettings'}, 'expect_visible': {'android_uiautomator': 'new UiSelector().resourceId("com.pudutech.business.function:id/tv_name").text("地图设置")'}, 'expect_visible_locators_fallback': [{'android_uiautomator': 'new UiSelector().text("地图设置")'}]}, {'name': 'Step 2 Tap 地图设置', 'action': 'tap', 'locator': {'android_uiautomator': 'new UiSelector().resourceId("com.pudutech.business.function:id/tv_name").text("地图设置")'}, 'expect_visible': {'id': 'com.pudutech.business.function:id/tv_edit_map'}, 'locators_fallback': [{'android_uiautomator': 'new UiSelector().text("地图设置")'}], 'expect_visible_locators_fallback': [{'android_uiautomator': 'new UiSelector().text("编辑地图")'}]}, {'name': 'Step 3 Tap 编辑地图', 'action': 'tap', 'locator': {'id': 'com.pudutech.business.function:id/tv_edit_map'}, 'expect_visible': {'id': 'com.pudutech.business.function:id/et_pwd'}, 'locators_fallback': [{'android_uiautomator': 'new UiSelector().text("编辑地图")'}]}]


@allure.suite('UI Automation')
@allure.feature('地图')
@allure.story('设置-地图-setting_map')
@allure.title('设置-地图-setting_map')
@allure.description('Generated from natural language: 设置-地图-setting_map')
@allure.severity('critical')
@pytest.mark.ui
@pytest.mark.P1
def test_setting_map(driver):
    run_steps(driver, STEPS, DEFAULT_TIMEOUT)
