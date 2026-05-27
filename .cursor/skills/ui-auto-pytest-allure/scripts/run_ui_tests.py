#!/usr/bin/env python3
"""Run UI tests from natural language, priority, or single test file name."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

PRIORITIES = {"P0", "P1", "P2", "P3", "P4"}
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from allure_cli import augmented_path_env, resolve_allure_command  # noqa: E402
from appium_server import ensure_appium_server, sync_capabilities_device  # noqa: E402
from project_paths import resolve_project_root  # noqa: E402

PROJECT_ROOT = resolve_project_root(SCRIPT_DIR)

PRIORITY_PATTERNS = [
    re.compile(r"运行\s*P([0-4])\s*测试用例", re.IGNORECASE),
    re.compile(r"执行\s*P([0-4])\s*(?:测试)?用例", re.IGNORECASE),
    re.compile(r"运行\s*P([0-4])\b", re.IGNORECASE),
    re.compile(r"^P([0-4])$", re.IGNORECASE),
]

TEST_FILE_PATTERNS = [
    re.compile(r"运行\s+(test_[\w]+\.py)", re.IGNORECASE),
    re.compile(r"运行\s+(test_[\w]+)", re.IGNORECASE),
    re.compile(r"运行\s+([\w]+\.py)", re.IGNORECASE),
    re.compile(r"运行\s+([\w]+)", re.IGNORECASE),
    re.compile(r"^([\w]+\.py)$", re.IGNORECASE),
    re.compile(r"^(test_[\w]+)$", re.IGNORECASE),
    re.compile(r"^([\w]+)$", re.IGNORECASE),
]


def repair_inspector_session(skip_repair: bool) -> None:
    if skip_repair or os.getenv("APPIUM_SKIP_AUTO_REPAIR", "").lower() in {"1", "true", "yes"}:
        return

    repair_script = SCRIPT_DIR / "repair_appium_session.py"
    if not repair_script.exists():
        return

    print("Repairing Appium session for Inspector...")
    result = subprocess.run(
        [sys.executable, str(repair_script), "--project-root", str(PROJECT_ROOT)],
        cwd=str(PROJECT_ROOT),
        check=False,
    )
    if result.returncode != 0:
        print(
            "Inspector repair did not complete. "
            "Run manually:\n"
            f"  python {repair_script} --open-inspector"
        )


def ensure_dependencies(skip_install: bool) -> None:
    if skip_install:
        return
    installer = SCRIPT_DIR / "install_ui_dependencies.py"
    print("Checking and installing UI test dependencies...")
    result = subprocess.run([sys.executable, str(installer)], check=False)
    if result.returncode != 0:
        raise SystemExit("Dependency installation failed.")


def parse_natural_language_request(text: str) -> tuple[str, str | None]:
    """Return ('priority', P0) or ('test', test_file_name)."""
    raw = text.strip()
    if not raw:
        raise ValueError("Run request is empty.")

    for pattern in PRIORITY_PATTERNS:
        match = pattern.search(raw)
        if match:
            return "priority", f"P{match.group(1)}"

    for pattern in TEST_FILE_PATTERNS:
        match = pattern.search(raw)
        if match:
            return "test", normalize_test_file_name(match.group(1))

    if raw.upper() in PRIORITIES:
        return "priority", raw.upper()

    if re.fullmatch(r"test_[\w]+", raw, re.IGNORECASE) or re.fullmatch(r"[\w]+\.py", raw, re.IGNORECASE):
        return "test", normalize_test_file_name(raw)

    if re.fullmatch(r"[\w]+", raw, re.IGNORECASE) and raw.upper() not in PRIORITIES:
        return "test", normalize_test_file_name(raw)

    raise ValueError(
        "Unsupported run request. Examples:\n"
        "  运行P0测试用例\n"
        "  运行test_setting_password_idle_lock.py"
    )


def normalize_test_file_name(name: str) -> str:
    value = name.strip()
    if not value.endswith(".py"):
        if value.startswith("test_"):
            value = f"{value}.py"
        else:
            value = f"test_{value}.py"
    return value


def find_test_file(test_root: Path, file_name: str) -> Path:
    matches = sorted(test_root.rglob(file_name))
    if not matches:
        available = sorted(test_root.rglob("test_*.py"))
        hint = "\n".join(f"  - {path.relative_to(test_root)}" for path in available) or "  (none)"
        raise SystemExit(f"Test file not found: {file_name}\nAvailable tests:\n{hint}")
    if len(matches) > 1:
        lines = "\n".join(f"  - {path}" for path in matches)
        raise SystemExit(f"Multiple tests match {file_name}:\n{lines}")
    return matches[0]


def _allure_results_dir_has_data(results_dir: Path) -> bool:
    if not results_dir.is_dir():
        return False
    return any(results_dir.glob("*.json"))


def open_allure_html_report(results_dir: Path, report_name: str) -> bool:
    """Serve Allure results over HTTP and open the report in the browser."""
    results_dir = results_dir.resolve()
    if not _allure_results_dir_has_data(results_dir):
        print(f"No Allure result files in {results_dir}. Skip opening HTML report.")
        return False

    allure_cmd = resolve_allure_command(PROJECT_ROOT, auto_install=True)
    if not allure_cmd:
        print(
            "Allure CLI is not available, so the HTML report was not opened.\n"
            "Run:\n"
            "  python .cursor/skills/ui-auto-pytest-allure/scripts/install_allure_cli.py"
        )
        return False

    report_dir = (PROJECT_ROOT / "allure-report" / report_name).resolve()
    report_dir.parent.mkdir(parents=True, exist_ok=True)
    env = augmented_path_env(PROJECT_ROOT)

    print(f"Generating static report copy: {report_dir}")
    generate = subprocess.run(
        [
            allure_cmd,
            "generate",
            str(results_dir),
            "-o",
            str(report_dir),
            "--clean",
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        check=False,
    )
    if generate.returncode != 0:
        print("Warning: allure generate failed; will still try allure serve.")

    print(f"Starting Allure report server for {results_dir}")
    print("Do not open index.html directly with file:// — use the browser opened by allure serve.")

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]

    subprocess.Popen(
        [allure_cmd, "serve", str(results_dir)],
        cwd=str(PROJECT_ROOT),
        env=env,
        creationflags=creationflags,
    )
    print("Allure report server started. Close its console window to stop the server.")
    return True


def run_priority_tests(
    priority: str,
    test_root: Path,
    allure_root: Path,
    extra_args: list[str],
) -> tuple[int, Path]:
    if priority not in PRIORITIES:
        raise SystemExit(f"Unsupported priority: {priority}")

    test_dir = test_root / priority
    if not test_dir.exists():
        raise SystemExit(f"No generated tests found for {priority}: {test_dir}")

    allure_dir = allure_root / priority
    command = [
        sys.executable,
        "-m",
        "pytest",
        str(test_dir),
        f"--alluredir={allure_dir}",
        "-m",
        priority,
        "-v",
    ]
    command.extend(extra_args)
    print("Running:", " ".join(command))
    return subprocess.call(command), allure_dir


def run_single_test(
    file_name: str,
    test_root: Path,
    allure_root: Path,
    extra_args: list[str],
) -> tuple[int, Path]:
    test_path = find_test_file(test_root, file_name)
    allure_dir = allure_root / "single"
    allure_dir.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "pytest",
        str(test_path),
        "-v",
        f"--alluredir={allure_dir}",
    ]
    command.extend(extra_args)
    print("Running:", " ".join(command))
    return subprocess.call(command), allure_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "request",
        nargs="?",
        help='Natural language request, e.g. "运行P0测试用例" or "运行test_xxx.py"',
    )
    parser.add_argument("--priority", help="Run all tests for P0-P4.")
    parser.add_argument("--test", help="Run one test file name, e.g. test_setting_password_idle_lock.py")
    parser.add_argument("--test-root", default="generated-tests/ui")
    parser.add_argument("--allure-root", default="allure-results")
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument(
        "--skip-repair",
        action="store_true",
        help="Skip Appium/UiAutomator2 repair after tests (not recommended for Inspector).",
    )
    parser.add_argument(
        "--skip-appium-start",
        action="store_true",
        help="Do not auto-start Appium before running tests.",
    )
    parser.add_argument(
        "--open-report",
        action="store_true",
        default=True,
        help="Generate and open Allure HTML report after tests (default: on).",
    )
    parser.add_argument(
        "--no-open-report",
        action="store_false",
        dest="open_report",
        help="Do not open Allure HTML report after tests.",
    )
    parser.add_argument("pytest_args", nargs="*", help="Extra pytest arguments.")
    args = parser.parse_args()

    ensure_dependencies(args.skip_install)

    if not args.skip_appium_start:
        ensure_appium_server(PROJECT_ROOT)
        sync_capabilities_device(PROJECT_ROOT / "capabilities.json")

    test_root = Path(args.test_root)
    allure_root = Path(args.allure_root)

    if args.priority:
        mode, target = "priority", args.priority.upper()
    elif args.test:
        mode, target = "test", normalize_test_file_name(args.test)
    elif args.request:
        mode, target = parse_natural_language_request(args.request)
    else:
        parser.print_help()
        raise SystemExit(2)

    if mode == "priority":
        exit_code, allure_dir = run_priority_tests(target, test_root, allure_root, args.pytest_args)
        report_name = target
    else:
        exit_code, allure_dir = run_single_test(target, test_root, allure_root, args.pytest_args)
        report_name = "single"

    repair_inspector_session(args.skip_repair)

    if args.open_report:
        open_allure_html_report(allure_dir, report_name)

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
