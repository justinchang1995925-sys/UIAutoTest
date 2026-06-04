#!/usr/bin/env python3
"""Preflight checks for UIAutoTest (dependencies, adb, Appium, capabilities, Allure)."""

from __future__ import annotations

import importlib.util
import json
import shutil
import socket
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from adb_utils import list_authorized_devices, resolve_adb  # noqa: E402
from allure_cli import resolve_allure_command  # noqa: E402
from appium_server import _which_appium, is_appium_ready  # noqa: E402
from inspector_session import is_keepalive_running, load_session_info  # noqa: E402
from project_paths import resolve_project_root  # noqa: E402
from sheet_import_sync import sheet_import_path  # noqa: E402

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
    if importlib.util.find_spec("openpyxl") is None:
        issues.append("Missing openpyxl (needed for .xlsx import): pip install openpyxl")
    return issues


def _check_adb() -> list[str]:
    issues: list[str] = []
    try:
        adb = resolve_adb()
    except RuntimeError as exc:
        issues.append(str(exc))
        return issues
    devices = list_authorized_devices()
    if not devices:
        issues.append("No authorized Android device (adb devices shows none in 'device' state).")
    elif len(devices) > 1:
        issues.append(
            f"Multiple devices connected ({', '.join(devices)}). "
            "Set --device or capabilities.local.json appium:udid."
        )
    else:
        print(f"  adb: {adb}")
        print(f"  device: {devices[0]}")
    return issues


def _check_node_npm() -> list[str]:
    issues: list[str] = []
    if not shutil.which("npm"):
        issues.append(
            "npm is not in PATH. Install Node.js LTS from https://nodejs.org/ "
            "then run: python uiatest.py setup"
        )
    else:
        print("  npm: available")
    return issues


def _check_appium_cli() -> list[str]:
    issues: list[str] = []
    appium_cmd = _which_appium()
    if not appium_cmd:
        issues.append(
            "Appium CLI not found. Run: python uiatest.py setup "
            "(or: npm install -g appium && appium driver install uiautomator2)"
        )
    else:
        print(f"  appium: {appium_cmd}")
    return issues


def _check_appium_server() -> list[str]:
    issues: list[str] = []
    port_open = False
    try:
        with socket.create_connection(("127.0.0.1", 4723), timeout=2):
            port_open = True
    except OSError:
        port_open = False
    if not port_open:
        issues.append(
            "Port 4723 is not open (Appium server not listening). "
            "It will auto-start on first test run if Appium CLI is installed."
        )
    elif not is_appium_ready():
        issues.append("Appium port is open but /status is not ready.")
    else:
        print("  Appium server: ready at http://127.0.0.1:4723")
    return issues


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
    issues: list[str] = []
    if not resolve_allure_command(PROJECT_ROOT, auto_install=False):
        issues.append(
            "Allure CLI not found. Run: python .cursor/skills/ui-auto-pytest-allure/scripts/install_allure_cli.py"
        )
        return issues
    print("  reports: use allure open allure-report/<name> (not allure-results/)")
    return issues


def _check_scaffold_sync() -> list[str]:
    root_cli = PROJECT_ROOT / "uiatest.py"
    scaffold_cli = PROJECT_ROOT / ".cursor" / "skills" / "ui-auto-pytest-allure" / "scaffold" / "uiatest.py"
    if not scaffold_cli.is_file() or not root_cli.is_file():
        return []
    if root_cli.read_bytes() != scaffold_cli.read_bytes():
        return ["uiatest.py differs from scaffold/uiatest.py — copy root uiatest.py to scaffold for distribution."]
    return []


def _check_import_sheet() -> list[str]:
    sheet = sheet_import_path(PROJECT_ROOT)
    if sheet.is_file():
        return []
    return [f"Import sheet not found: {sheet.relative_to(PROJECT_ROOT)}"]


def _check_inspector() -> list[str]:
    issues: list[str] = []
    if is_keepalive_running(PROJECT_ROOT):
        print("  inspector keepalive: running")
    else:
        print("  inspector keepalive: not running")
    info = load_session_info(PROJECT_ROOT)
    if info and info.get("session_id"):
        print(f"  saved inspector session: {info.get('session_id')}")
    return issues


def main() -> None:
    print(f"UIAutoTest doctor — project root: {PROJECT_ROOT}\n")
    sections = [
        ("Python packages", _check_python_modules()),
        ("Node.js / npm", _check_node_npm()),
        ("Appium CLI", _check_appium_cli()),
        ("adb / device", _check_adb()),
        ("Appium server", _check_appium_server()),
        ("Capabilities", _check_capabilities()),
        ("Allure CLI", _check_allure()),
        ("Scaffold sync", _check_scaffold_sync()),
        ("Import sheet", _check_import_sheet()),
        ("Inspector", _check_inspector()),
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
