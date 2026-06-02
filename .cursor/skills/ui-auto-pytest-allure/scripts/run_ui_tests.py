#!/usr/bin/env python3
"""Run UI tests from natural language, priority, or single test file name."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

PRIORITIES = {"P0", "P1", "P2", "P3", "P4"}
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from allure_cli import augmented_path_env, resolve_allure_command  # noqa: E402
from appium_server import (  # noqa: E402
    connect_device,
    ensure_appium_server,
    set_capabilities_app_entry,
    set_capabilities_device_id,
    sync_capabilities_device,
)
from project_paths import resolve_project_root  # noqa: E402
from sheet_import_sync import maybe_sync_sheet_import, sheet_import_path  # noqa: E402
from sheet_run_order import ordered_test_paths_for_priority  # noqa: E402
from sheet_write_results import (  # noqa: E402
    junit_path_for_run,
    merge_junit_files,
    parse_junit_results,
    write_results_to_sheet,
)
from inspector_session import (  # noqa: E402
    DEFAULT_SERVER,
    delete_session,
    is_keepalive_running,
    load_session_info,
    stop_keepalive,
)

PROJECT_ROOT = resolve_project_root(SCRIPT_DIR)

CONNECT_AND_RUN_RE = re.compile(r"连接设备\s*([^\s]+)\s*并\s*(.+)$", re.IGNORECASE)
START_ACTIVITY_RE = re.compile(r"(?:起始页面的)?appActivity名\s*[:：]\s*([^\s，,]+)", re.IGNORECASE)
START_PACKAGE_RE = re.compile(r"(?:起始页面的)?appPackage名\s*[:：]\s*([^\s，,]+)", re.IGNORECASE)

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


def _inspector_restore_enabled(skip_restore: bool) -> bool:
    if skip_restore:
        return False
    if os.getenv("UIATEST_SKIP_INSPECTOR_RESTORE", "").lower() in {"1", "true", "yes"}:
        return False
    if os.getenv("UIATEST_AUTO_RESTORE_INSPECTOR", "").lower() in {"1", "true", "yes"}:
        return True
    if os.getenv("UIATEST_INSPECTOR_WAS_ACTIVE", "").lower() in {"1", "true", "yes"}:
        return True
    return False


def pause_inspector_for_tests(project_root: Path) -> None:
    """Stop inspector keepalive and close its Appium session before tests."""
    if not is_keepalive_running(project_root):
        return

    info = load_session_info(project_root) or {}
    os.environ["UIATEST_INSPECTOR_WAS_ACTIVE"] = "1"
    stop_keepalive(project_root)
    print("Paused inspector keepalive for test run.")

    session_id = str(info.get("session_id") or "").strip()
    server_url = str(info.get("server_url") or DEFAULT_SERVER).strip()
    if session_id:
        delete_session(server_url, session_id)
        print(f"Closed inspector Appium session: {session_id}")


def restore_inspector_after_tests(project_root: Path, *, skip_restore: bool = False) -> None:
    """Recreate a dedicated Inspector session after tests so Refresh works again."""
    if not _inspector_restore_enabled(skip_restore):
        return
    if os.getenv("APPIUM_SKIP_AUTO_REPAIR", "").lower() in {"1", "true", "yes"}:
        return

    repair_script = SCRIPT_DIR / "repair_appium_session.py"
    if not repair_script.exists():
        return

    print("Restoring Appium Inspector session after test run...")
    result = subprocess.run(
        [
            sys.executable,
            str(repair_script),
            "--project-root",
            str(project_root),
            "--for-inspector",
            "--start-keepalive",
        ],
        cwd=str(project_root),
        check=False,
    )
    if result.returncode != 0:
        print(
            "Could not restore Inspector session. Run manually:\n"
            f"  python uiatest.py inspect"
        )
        return

    info = load_session_info(project_root) or {}
    session_id = str(info.get("session_id") or "").strip()
    print("")
    print("=" * 60)
    print("Inspector: test run ended the previous session.")
    print("To make Refresh work again in the browser:")
    print("  1. Session Builder -> Attach to Session")
    print(f"  2. Select NEW session id: {session_id or '(see .appium-inspector-session.json)'}")
    print("  3. Click 'Refresh Source & Screenshot'")
    print("=" * 60)
    print("")


def repair_inspector_session(auto_repair: bool) -> None:
    if not auto_repair:
        return
    if os.getenv("APPIUM_SKIP_AUTO_REPAIR", "").lower() in {"1", "true", "yes"}:
        return

    repair_script = SCRIPT_DIR / "repair_appium_session.py"
    if not repair_script.exists():
        return

    print("Repairing Appium session for Inspector...")
    result = subprocess.run(
        [
            sys.executable,
            str(repair_script),
            "--project-root",
            str(PROJECT_ROOT),
            "--for-inspector",
            "--start-keepalive",
        ],
        cwd=str(PROJECT_ROOT),
        check=False,
    )
    if result.returncode != 0:
        print(
            "Inspector repair did not complete. "
            "Run manually:\n"
            f"  python {repair_script} --open-inspector"
        )


def _python_deps_satisfied() -> bool:
    try:
        import pytest  # noqa: F401
        import allure  # noqa: F401
        import appium  # noqa: F401
        import selenium  # noqa: F401
        return True
    except ImportError:
        return False


def ensure_dependencies(skip_install: bool) -> None:
    if skip_install:
        return
    if _python_deps_satisfied() and resolve_allure_command(PROJECT_ROOT, auto_install=False):
        print("Python dependencies and Allure CLI are ready; skipping install.")
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

    # Fallback: when terminal encoding mangles Chinese words, still accept a bare P0-P4 token.
    match = re.search(r"P([0-4])", raw, re.IGNORECASE)
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
        "  连接设备 192.168.1.8:5555 并运行P1测试用例\n"
        "  运行test_setting_password_idle_lock.py"
    )


def parse_connect_and_run(text: str) -> tuple[str | None, str]:
    """Return (device_ip_port or None, remaining request text)."""
    raw = text.strip()
    match = CONNECT_AND_RUN_RE.match(raw)
    if not match:
        return None, raw
    return match.group(1).strip(), match.group(2).strip()


def extract_entry_overrides(text: str) -> tuple[str | None, str | None, str]:
    """Extract appPackage/appActivity overrides from natural language; return (pkg, act, remaining)."""
    raw = text.strip()
    pkg = None
    act = None
    m = START_PACKAGE_RE.search(raw)
    if m:
        pkg = m.group(1).strip()
        raw = START_PACKAGE_RE.sub("", raw).strip()
    m = START_ACTIVITY_RE.search(raw)
    if m:
        act = m.group(1).strip()
        raw = START_ACTIVITY_RE.sub("", raw).strip()
    return pkg or None, act or None, raw


def _is_activity_configured(activity: str | None) -> bool:
    value = (activity or "").strip()
    if not value:
        return False
    if value.startswith("<") and value.endswith(">"):
        return False
    return True


def _load_capabilities_for_entry(project_root: Path) -> dict:
    """Load capabilities using the same precedence as the pytest fixture."""
    import json

    raw = os.getenv("APPIUM_CAPABILITIES")
    if raw:
        return json.loads(raw)

    preferred = os.getenv("APPIUM_CAPABILITIES_FILE", "").strip()
    if preferred:
        path = Path(preferred)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))

    candidates = [
        project_root / "capabilities.local.json",
        project_root / "capabilities.json",
        project_root / "capabilities.template.json",
    ]
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    return {}


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
    return any(results_dir.rglob("*-result.json"))


def clean_allure_results(results_dir: Path) -> None:
    """Remove prior Allure JSON/attachments for a fresh run."""
    if results_dir.is_dir():
        shutil.rmtree(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    print(f"Cleared Allure results: {results_dir}")


def open_allure_html_report(
    results_dir: Path,
    report_name: str,
    *,
    static_report: bool = False,
) -> bool:
    """Generate HTML from Allure results and open the report UI in the browser."""
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

    print(f"Generating Allure HTML report: {report_dir}")
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
        print("Allure generate failed; cannot open HTML report.")
        return False

    if not (report_dir / "index.html").is_file():
        print(f"Allure report index.html not found under {report_dir}.")
        return False

    print(f"Opening Allure report UI for {report_name}")
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]

    # allure open expects a generated HTML report dir, NOT raw allure-results JSON.
    proc = subprocess.Popen(
        [allure_cmd, "open", str(report_dir)],
        cwd=str(PROJECT_ROOT),
        env=env,
        creationflags=creationflags,
    )
    time.sleep(1.5)
    if proc.poll() is not None and proc.returncode not in (None, 0):
        print(f"Allure open failed (exit {proc.returncode}). Open manually:\n  allure open {report_dir}")
        return False
    if static_report or os.getenv("UIATEST_ALLURE_STATIC", "").lower() in {"1", "true", "yes"}:
        print(f"Static report directory: {report_dir}")
    print(f"Report URL will be served from: {report_dir}")
    print("If the browser shows a file list, run: allure open allure-report/<name> (not allure-results/).")
    return True


def _sheet_results_enabled(skip_sheet_results: bool) -> bool:
    if skip_sheet_results:
        return False
    return os.getenv("UIATEST_SKIP_SHEET_RESULTS", "").lower() not in {"1", "true", "yes"}


def _write_sheet_results_after_run(
    sheet_path: Path,
    junit_xml: Path,
    *,
    priority_filter: str | None,
    clear_missing: bool = True,
) -> None:
    results = parse_junit_results(junit_xml)
    if not results:
        print("No junit results to write back to the import sheet.")
        return
    try:
        write_results_to_sheet(
            sheet_path,
            results,
            priority_filter=priority_filter,
            clear_missing=clear_missing,
        )
        from sheet_import_sync import save_synced_fingerprint, sheet_cases_fingerprint

        save_synced_fingerprint(PROJECT_ROOT, sheet_cases_fingerprint(sheet_path), sheet_path)
    except PermissionError as exc:
        print(f"Warning: {exc}")
    except SystemExit as exc:
        print(f"Warning: could not write sheet results: {exc}")


def _isolated_priority_run_enabled() -> bool:
    if os.getenv("UIATEST_BATCH_PYTEST", "").lower() in {"1", "true", "yes"}:
        return False
    return os.getenv("UIATEST_ISOLATED_RUN", "1").lower() not in {"0", "false", "no"}


def _run_pytest_command(
    command: list[str],
    project_root: Path,
    *,
    defer_u2_repair: bool = False,
) -> int:
    env = os.environ.copy()
    if defer_u2_repair:
        env["UIATEST_DEFER_U2_REPAIR"] = "1"
    print("Running:", " ".join(command))
    print(f"Working directory: {project_root}")
    return subprocess.call(command, cwd=str(project_root), env=env)


def _repair_u2_after_batch(project_root: Path) -> None:
    if os.getenv("APPIUM_SKIP_U2_REPAIR", "").lower() in {"1", "true", "yes"}:
        return
    if is_keepalive_running(project_root):
        return
    from adb_utils import force_stop_packages

    try:
        force_stop_packages(
            (
                "io.appium.uiautomator2.server",
                "io.appium.uiautomator2.server.test",
            )
        )
    except Exception:
        pass


def _should_fresh_results(mode: str, explicit_flag: bool) -> bool:
    if explicit_flag:
        return True
    if mode != "priority":
        return False
    return os.getenv("UIATEST_NO_FRESH_RESULTS", "").lower() not in {"1", "true", "yes"}


def run_priority_tests(
    priority: str,
    test_root: Path,
    allure_root: Path,
    extra_args: list[str],
    *,
    project_root: Path,
    skip_sheet_results: bool = False,
) -> tuple[int, Path]:
    if priority not in PRIORITIES:
        raise SystemExit(f"Unsupported priority: {priority}")

    test_dir = test_root / priority
    if not test_dir.exists():
        raise SystemExit(f"No generated tests found for {priority}: {test_dir}")

    allure_dir = allure_root / priority
    sheet_path = sheet_import_path(project_root)
    junit_xml = junit_path_for_run(project_root, priority)
    junit_xml.parent.mkdir(parents=True, exist_ok=True)
    if junit_xml.exists():
        junit_xml.unlink()

    test_targets: list[str] = []
    if sheet_path.is_file():
        ordered = ordered_test_paths_for_priority(sheet_path, test_root, priority)
        if ordered:
            test_targets = [str(path) for path in ordered]
            print("Test order (from import sheet):")
            for path in ordered:
                print(f"  - {path.relative_to(project_root)}")
    if not test_targets:
        test_targets = [str(test_dir)]

    if len(test_targets) > 1 and _isolated_priority_run_enabled():
        print("Isolated run: one pytest process per case (same as single-case execution).")
        exit_code = 0
        part_junits: list[Path] = []
        for index, target in enumerate(test_targets, start=1):
            part_junit = junit_xml.parent / f"pytest-{priority}-part{index}.xml"
            if part_junit.exists():
                part_junit.unlink()
            command = [
                sys.executable,
                "-m",
                "pytest",
                target,
                f"--alluredir={allure_dir}",
                "-v",
                f"--junitxml={part_junit}",
            ]
            command.extend(extra_args)
            code = _run_pytest_command(command, project_root, defer_u2_repair=True)
            if code != 0:
                exit_code = code
            part_junits.append(part_junit)
        merge_junit_files(part_junits, junit_xml)
        _repair_u2_after_batch(project_root)
    else:
        command = [
            sys.executable,
            "-m",
            "pytest",
            *test_targets,
            f"--alluredir={allure_dir}",
            "-m",
            priority,
            "-v",
            f"--junitxml={junit_xml}",
        ]
        command.extend(extra_args)
        exit_code = _run_pytest_command(command, project_root)

    if sheet_path.is_file() and _sheet_results_enabled(skip_sheet_results):
        _write_sheet_results_after_run(sheet_path, junit_xml, priority_filter=priority)

    return exit_code, allure_dir


def run_single_test(
    file_name: str,
    test_root: Path,
    allure_root: Path,
    extra_args: list[str],
    *,
    project_root: Path,
    skip_sheet_results: bool = False,
) -> tuple[int, Path]:
    test_path = find_test_file(test_root, file_name)
    allure_dir = allure_root / "single"
    allure_dir.mkdir(parents=True, exist_ok=True)

    sheet_path = sheet_import_path(project_root)
    run_key = test_path.stem
    junit_xml = junit_path_for_run(project_root, run_key)
    junit_xml.parent.mkdir(parents=True, exist_ok=True)
    if junit_xml.exists():
        junit_xml.unlink()

    command = [
        sys.executable,
        "-m",
        "pytest",
        str(test_path),
        "-v",
        f"--alluredir={allure_dir}",
        f"--junitxml={junit_xml}",
    ]
    command.extend(extra_args)
    exit_code = _run_pytest_command(command, project_root)

    if sheet_path.is_file() and _sheet_results_enabled(skip_sheet_results):
        _write_sheet_results_after_run(
            sheet_path,
            junit_xml,
            priority_filter=None,
            clear_missing=False,
        )

    return exit_code, allure_dir


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
        "--auto-repair",
        action="store_true",
        help="Repair Appium/UiAutomator2 after tests (for Inspector). Default: off.",
    )
    parser.add_argument(
        "--skip-repair",
        action="store_true",
        help="(Legacy) Same as default; post-run repair is off unless --auto-repair.",
    )
    parser.add_argument(
        "--skip-restore-inspector",
        action="store_true",
        help="Do not recreate Appium Inspector session after tests.",
    )
    parser.add_argument(
        "--skip-appium-start",
        action="store_true",
        help="Do not auto-start Appium before running tests.",
    )
    parser.add_argument(
        "--device",
        help="Target device udid or ip[:port]. If ip is given without port, tries common ports (e.g. 5555).",
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
    parser.add_argument(
        "--fresh-results",
        action="store_true",
        help="Clear allure-results before pytest. Priority runs clear by default (UIATEST_NO_FRESH_RESULTS=1 to disable).",
    )
    parser.add_argument(
        "--static-report",
        action="store_true",
        help="Alias: HTML is always generated under allure-report/ (same as default report open).",
    )
    parser.add_argument(
        "--skip-sheet-sync",
        action="store_true",
        help="Do not auto-import cases/import_template.csv even if it changed.",
    )
    parser.add_argument(
        "--sheet-rewrite-on-sync",
        action="store_true",
        help="Rewrite CSV steps/expected with 步骤N: during auto-import sync.",
    )
    parser.add_argument(
        "--skip-sheet-rewrite",
        action="store_true",
        help="During auto-import sync, do not rewrite CSV with 步骤N: (same as UIATEST_SKIP_SHEET_REWRITE=1).",
    )
    parser.add_argument(
        "--auto-restore-inspector",
        action="store_true",
        help="Recreate Appium Inspector session after tests (opt-in).",
    )
    parser.add_argument(
        "--skip-sheet-results",
        action="store_true",
        help="Do not write PASS/FAIL back to the import sheet after the run.",
    )
    parser.add_argument("--start-package", help="Override entry appPackage (writes to capabilities.local.json).")
    parser.add_argument("--start-activity", help="Override entry appActivity (writes to capabilities.local.json).")
    parser.add_argument(
        "--per-test-entry",
        action="store_true",
        help="Ensure each test starts from entry activity (requires appActivity configured).",
    )
    parser.add_argument(
        "--no-per-test-entry",
        action="store_true",
        help="Disable per-test entry activity reset (default: on when appActivity is configured).",
    )
    parser.add_argument("pytest_args", nargs="*", help="Extra pytest arguments.")
    args = parser.parse_args()

    ensure_dependencies(args.skip_install)

    test_root = Path(args.test_root)
    allure_root = Path(args.allure_root)

    requested_device = args.device.strip() if args.device else None
    if args.priority:
        mode, target = "priority", args.priority.upper()
    elif args.test:
        mode, target = "test", normalize_test_file_name(args.test)
    elif args.request:
        nl_device, remaining = parse_connect_and_run(args.request)
        if nl_device:
            requested_device = nl_device
        nl_pkg, nl_act, remaining = extract_entry_overrides(remaining)
        if nl_pkg:
            args.start_package = nl_pkg
        if nl_act:
            args.start_activity = nl_act
        mode, target = parse_natural_language_request(remaining)
    else:
        parser.print_help()
        raise SystemExit(2)

    if requested_device:
        udid = connect_device(requested_device)
        set_capabilities_device_id(PROJECT_ROOT / "capabilities.local.json", udid)
    if args.start_package or args.start_activity:
        set_capabilities_app_entry(
            PROJECT_ROOT / "capabilities.local.json",
            app_package=args.start_package,
            app_activity=args.start_activity,
        )

    if not args.skip_appium_start:
        ensure_appium_server(PROJECT_ROOT)
        sync_capabilities_device(PROJECT_ROOT / "capabilities.local.json")

    # Decide per-test entry reset:
    # - default: OFF unless appActivity is configured (or overridden)
    # - can be forced on/off via flags
    activity = args.start_activity or os.getenv("UIATEST_START_ACTIVITY", "").strip()
    if not activity:
        try:
            caps = _load_capabilities_for_entry(PROJECT_ROOT)
            activity = str(caps.get("appium:appActivity") or caps.get("appActivity") or "").strip()
        except Exception:
            activity = ""

    configured = _is_activity_configured(activity)
    if args.no_per_test_entry:
        os.environ["UIATEST_PER_TEST_ENTRY"] = "0"
    elif args.per_test_entry:
        os.environ["UIATEST_PER_TEST_ENTRY"] = "1" if configured else "0"
    else:
        os.environ["UIATEST_PER_TEST_ENTRY"] = "1" if configured else "0"

    if args.auto_restore_inspector:
        os.environ["UIATEST_AUTO_RESTORE_INSPECTOR"] = "1"

    os.environ.setdefault("UIATEST_TAP_SKIP_IF_VISIBLE", "1")

    maybe_sync_sheet_import(
        PROJECT_ROOT,
        SCRIPT_DIR,
        skip_install=args.skip_install,
        disabled=args.skip_sheet_sync,
        rewrite_sheet=args.sheet_rewrite_on_sync and not args.skip_sheet_rewrite,
    )

    pause_inspector_for_tests(PROJECT_ROOT)

    if mode == "priority":
        allure_dir = allure_root / target
        if _should_fresh_results(mode, args.fresh_results):
            clean_allure_results(allure_dir)
        exit_code, allure_dir = run_priority_tests(
            target,
            test_root,
            allure_root,
            args.pytest_args,
            project_root=PROJECT_ROOT,
            skip_sheet_results=args.skip_sheet_results,
        )
        report_name = target
    else:
        allure_dir = allure_root / "single"
        if args.fresh_results:
            clean_allure_results(allure_dir)
        exit_code, allure_dir = run_single_test(
            target,
            test_root,
            allure_root,
            args.pytest_args,
            project_root=PROJECT_ROOT,
            skip_sheet_results=args.skip_sheet_results,
        )
        report_name = "single"

    auto_repair = args.auto_repair or os.getenv("UIATEST_AUTO_REPAIR", "").lower() in {
        "1",
        "true",
        "yes",
    }
    restore_inspector_after_tests(PROJECT_ROOT, skip_restore=args.skip_restore_inspector)
    if auto_repair and args.skip_restore_inspector:
        repair_inspector_session(True)

    if args.open_report:
        open_allure_html_report(allure_dir, report_name, static_report=args.static_report)

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
