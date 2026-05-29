#!/usr/bin/env python3
"""Preflight checks for UIAutoTest (dependencies, adb, Appium, capabilities, Allure)."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from allure_cli import resolve_allure_command  # noqa: E402
from appium_server import get_connected_device_ids, is_appium_ready  # noqa: E402
from project_paths import resolve_project_root  # noqa: E402

PROJECT_ROOT = resolve_project_root(SCRIPT_DIR)

REQUIRED_MODULES = (
    "pytest",
    "allure",
    "appium",
    "selenium",
)


def _check_python_modules() -> list[str]:
    issues: list[str] = []
    for name in REQUIRED_MODULES:
        if importlib.util.find_spec(name) is None:
            issues.append(f"Missing Python package: {name}")
    return issues


def _check_adb() -> list[str]:
    issues: list[str] = []
    if not shutil.which("adb"):
        issues.append("adb not found in PATH.")
        return issues
    devices = get_connected_device_ids()
    if not devices:
        issues.append("No authorized Android device (adb devices shows none in 'device' state).")
    elif len(devices) > 1:
        issues.append(
            f"Multiple devices connected ({', '.join(devices)}). "
            "Set --device or capabilities.local.json appium:udid."
        )
    return issues


def _check_appium() -> list[str]:
    if is_appium_ready():
        return []
    if not shutil.which("appium"):
        return ["Appium CLI not found. Install: npm install -g appium"]
    return ["Appium server not ready at http://127.0.0.1:4723 (run tests to auto-start, or start manually)."]


def _check_capabilities() -> list[str]:
    issues: list[str] = []
    candidates = [
        PROJECT_ROOT / "capabilities.local.json",
        PROJECT_ROOT / "capabilities.json",
        PROJECT_ROOT / "capabilities.template.json",
    ]
    path = next((item for item in candidates if item.exists()), None)
    if path is None:
        issues.append("No capabilities file found (expected capabilities.local.json or template).")
        return issues
    try:
        caps = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        issues.append(f"Invalid JSON in {path.name}: {exc}")
        return issues
    udid = str(caps.get("appium:udid") or caps.get("udid") or "").strip()
    if not udid or udid == "<ANDROID_UDID>":
        issues.append(
            f"{path.name} has placeholder udid. Connect a device and run tests once, "
            "or edit capabilities.local.json."
        )
    package = str(caps.get("appium:appPackage") or caps.get("appPackage") or "").strip()
    if not package:
        issues.append(f"{path.name} missing appium:appPackage.")
    return issues


def _check_allure() -> list[str]:
    if resolve_allure_command(PROJECT_ROOT, auto_install=False):
        return []
    return ["Allure CLI not found. Run: python .cursor/skills/ui-auto-pytest-allure/scripts/install_allure_cli.py"]


def main() -> None:
    print(f"UIAutoTest doctor — project root: {PROJECT_ROOT}\n")
    sections = [
        ("Python packages", _check_python_modules()),
        ("adb / device", _check_adb()),
        ("Appium", _check_appium()),
        ("Capabilities", _check_capabilities()),
        ("Allure CLI", _check_allure()),
    ]
    failed = 0
    for title, issues in sections:
        if issues:
            failed += len(issues)
            print(f"[FAIL] {title}")
            for item in issues:
                print(f"  - {item}")
        else:
            print(f"[ OK ] {title}")
    print()
    if failed:
        print(f"Doctor found {failed} issue(s). Fix the items above before running UI tests.")
        raise SystemExit(1)
    print("All checks passed. You can run: python uiatest.py run \"运行P1测试用例\"")


if __name__ == "__main__":
    main()
