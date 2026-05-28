"""Generated UI automation test.

Source spec: setting_password_idle_lock
"""

from __future__ import annotations

import sys
from pathlib import Path

import allure
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _lib.ui_runtime import run_steps  # noqa: E402


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


@allure.suite('UI Automation')
@allure.feature('密码与安全')
@allure.story('进入设置-密码与安全-电机锁-关闭空闲时锁电机')
@allure.title('进入设置-密码与安全-电机锁-关闭空闲时锁电机')
@allure.description('Generated from natural language: 进入设置-密码与安全-电机锁-关闭空闲时锁电机')
@allure.severity('critical')
@pytest.mark.ui
@pytest.mark.P1
def test_setting_password_idle_lock(driver):
    run_steps(driver, STEPS, DEFAULT_TIMEOUT)
