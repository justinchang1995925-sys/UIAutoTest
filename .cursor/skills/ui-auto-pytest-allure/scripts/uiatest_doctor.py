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

PLACEHOLDER_PACKAGES = {
    "com.yourcompany.yourapp",
    "your.app.package",
}
PLACEHOLDER_ACTIVITIES = {
    "com.yourcompany.yourapp.mainactivity",
    "your.app.mainactivity",
}


def _check_python_modules() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for name in REQUIRED_MODULES:
        if importlib.util.find_spec(name) is None:
            errors.append(f"Missing Python package: {name} — run: python uiatest.py setup")
    if importlib.util.find_spec("openpyxl") is None:
        warnings.append("Missing openpyxl (only needed for .xlsx import) — run: python uiatest.py setup")
    return errors, warnings


def _check_skill_layout() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    skill_md = PROJECT_ROOT / ".cursor" / "skills" / "ui-auto-pytest-allure" / "SKILL.md"
    scripts = PROJECT_ROOT / ".cursor" / "skills" / "ui-auto-pytest-allure" / "scripts"
    if not skill_md.is_file():
        errors.append(
            "Skill folder missing. Copy ui-auto-pytest-allure to "
            ".cursor/skills/ui-auto-pytest-allure/ then run uiatest_init.py"
        )
    elif not scripts.is_dir():
        errors.append(f"Skill scripts directory missing: {scripts}")
    else:
        print(f"  skill: {skill_md.parent.name}")
    return errors, []


def _check_uiatest_entry() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    cli = PROJECT_ROOT / "uiatest.py"
    if not cli.is_file():
        errors.append(
            "uiatest.py not found in project root. Run: "
            "python .cursor/skills/ui-auto-pytest-allure/scripts/uiatest_init.py"
        )
    else:
        print(f"  CLI: {cli.name}")
    return errors, []


def _check_adb() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        adb = resolve_adb()
    except RuntimeError as exc:
        errors.append(str(exc))
        return errors, warnings
    devices = list_authorized_devices()
    if not devices:
        warnings.append(
            "No authorized Android device yet. Connect USB, allow debugging, then re-run doctor."
        )
    elif len(devices) > 1:
        warnings.append(
            f"Multiple devices ({', '.join(devices)}). Set --device or appium:udid in capabilities.local.json."
        )
    else:
        print(f"  adb: {adb}")
        print(f"  device: {devices[0]}")
    return errors, warnings


def _check_node_npm() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    if not shutil.which("npm"):
        errors.append(
            "npm is not in PATH. Install Node.js LTS from https://nodejs.org/ "
            "then run: python uiatest.py setup"
        )
    else:
        print("  npm: available")
    return errors, []


def _check_appium_cli() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    appium_cmd = _which_appium()
    if not appium_cmd:
        errors.append(
            "Appium CLI not found. Run: python uiatest.py setup "
            "(or: npm install -g appium && appium driver install uiautomator2)"
        )
    else:
        print(f"  appium: {appium_cmd}")
    return errors, []


def _check_appium_server() -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    port_open = False
    try:
        with socket.create_connection(("127.0.0.1", 4723), timeout=2):
            port_open = True
    except OSError:
        port_open = False
    if not port_open:
        warnings.append(
            "Appium server not running on :4723 (OK — it auto-starts on first test run)."
        )
    elif not is_appium_ready():
        warnings.append("Port 4723 is open but Appium /status is not ready.")
    else:
        print("  Appium server: ready at http://127.0.0.1:4723")
    return [], warnings


def _check_capabilities() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    candidates = [
        PROJECT_ROOT / "capabilities.local.json",
        PROJECT_ROOT / "capabilities.json",
        PROJECT_ROOT / "capabilities.template.json",
    ]
    path = next((item for item in candidates if item.exists()), None)
    if path is None:
        errors.append("No capabilities file found. Run uiatest init or add capabilities.template.json.")
        return errors, warnings
    try:
        caps = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {path.name}: {exc}")
        return errors, warnings

    print(f"  capabilities: {path.name}")
    udid = str(caps.get("appium:udid") or caps.get("udid") or "").strip()
    if not udid or udid.upper() == "<ANDROID_UDID>":
        warnings.append(
            f"{path.name}: udid is placeholder. Connect device and run once, or set appium:udid."
        )
    package = str(caps.get("appium:appPackage") or caps.get("appPackage") or "").strip().lower()
    activity = str(caps.get("appium:appActivity") or caps.get("appActivity") or "").strip().lower()
    if not package:
        errors.append(f"{path.name} missing appium:appPackage.")
    elif package in PLACEHOLDER_PACKAGES or "yourcompany" in package or "your.app" in package:
        errors.append(
            f"{path.name} still has placeholder appPackage ({package}). "
            "Edit to your real application id before running tests."
        )
    if not activity:
        errors.append(f"{path.name} missing appium:appActivity.")
    elif activity in PLACEHOLDER_ACTIVITIES or "yourcompany" in activity or "your.app" in activity:
        errors.append(
            f"{path.name} still has placeholder appActivity. "
            "Edit to your real launcher/home activity."
        )
    return errors, warnings


def _check_allure() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    if not resolve_allure_command(PROJECT_ROOT, auto_install=False):
        errors.append("Allure CLI not found. Run: python uiatest.py setup")
        return errors, []
    print("  reports: allure open allure-report/<name>")
    return errors, []


def _check_scaffold_sync() -> tuple[list[str], list[str]]:
    root_cli = PROJECT_ROOT / "uiatest.py"
    scaffold_cli = PROJECT_ROOT / ".cursor" / "skills" / "ui-auto-pytest-allure" / "scaffold" / "uiatest.py"
    if not scaffold_cli.is_file() or not root_cli.is_file():
        return [], []
    if root_cli.read_bytes() != scaffold_cli.read_bytes():
        return [], [
            "uiatest.py differs from skill scaffold — run: python uiatest.py init --force (backup custom edits first)"
        ]
    return [], []


def _check_import_sheet() -> tuple[list[str], list[str]]:
    sheet = sheet_import_path(PROJECT_ROOT)
    if sheet.is_file():
        print(f"  import sheet: {sheet.relative_to(PROJECT_ROOT)}")
        return [], []
    return [], [f"Optional import sheet missing: {sheet.relative_to(PROJECT_ROOT)} (only needed for CSV batch)"]


def _check_inspector() -> tuple[list[str], list[str]]:
    if is_keepalive_running(PROJECT_ROOT):
        print("  inspector keepalive: running")
    else:
        print("  inspector keepalive: not running")
    info = load_session_info(PROJECT_ROOT)
    if info and info.get("session_id"):
        print(f"  saved inspector session: {info.get('session_id')}")
    return [], []


def main() -> None:
    print(f"UIAutoTest doctor — project root: {PROJECT_ROOT}\n")
    sections: list[tuple[str, tuple[list[str], list[str]]]] = [
        ("Skill layout", _check_skill_layout()),
        ("CLI entry (uiatest.py)", _check_uiatest_entry()),
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
    error_count = 0
    warn_count = 0
    for title, (errors, warnings) in sections:
        if errors:
            error_count += len(errors)
            print(f"[FAIL] {title}")
            for item in errors:
                print(f"  - {item}")
        elif warnings:
            warn_count += len(warnings)
            print(f"[WARN] {title}")
            for item in warnings:
                print(f"  - {item}")
        else:
            print(f"[ OK ] {title}")

    print()
    if error_count:
        print(f"Doctor: {error_count} blocking issue(s), {warn_count} warning(s).")
        print("Fix FAIL items, then: python uiatest.py doctor")
        raise SystemExit(1)
    if warn_count:
        print(f"Doctor: ready with {warn_count} warning(s). You can run tests when device/caps are set.")
    else:
        print("All checks passed. You can run: python uiatest.py run \"运行P1测试用例\"")


if __name__ == "__main__":
    main()
