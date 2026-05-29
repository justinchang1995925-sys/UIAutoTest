#!/usr/bin/env python3
"""Unified CLI for UIAutoTest workflows."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SKILL_DIR = PROJECT_ROOT / ".cursor" / "skills" / "ui-auto-pytest-allure" / "scripts"


def _run(script: str, args: list[str]) -> int:
    path = SKILL_DIR / script
    if not path.exists():
        raise SystemExit(f"Missing script: {path}")
    return subprocess.call([sys.executable, str(path), *args], cwd=str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(prog="uiatest", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Run tests (NL, priority, or single test).")
    run_p.add_argument("request", nargs="?", help='Natural language, e.g. "运行P1测试用例"')
    run_p.add_argument("--priority")
    run_p.add_argument("--test")
    run_p.add_argument("--device", help="udid or ip[:port]")
    run_p.add_argument("--skip-install", action="store_true")
    run_p.add_argument("--skip-repair", action="store_true")
    run_p.add_argument("--skip-appium-start", action="store_true")
    run_p.add_argument("--no-open-report", action="store_true")
    run_p.add_argument(
        "--fresh-results",
        action="store_true",
        help="Clear allure-results for this run before pytest.",
    )
    run_p.add_argument(
        "--static-report",
        action="store_true",
        help="Also generate static allure-report/ copy (default: allure serve only).",
    )
    run_p.add_argument("pytest_args", nargs="*", help="Extra pytest args after '--'.")

    imp_p = sub.add_parser("import", help="Import cases from CSV/XLSX sheet.")
    imp_p.add_argument("path", help="CSV/XLSX path")
    imp_p.add_argument("--spec-root", default="specs")
    imp_p.add_argument("--output-root", default="generated-tests/ui")
    imp_p.add_argument("--dry-run", action="store_true")
    imp_p.add_argument("--nl-only", action="store_true")
    imp_p.add_argument("--skip-install", action="store_true")
    imp_p.add_argument("--no-resolve-locators", action="store_true")
    imp_p.add_argument("--udid", help="Device id for locator resolve.")

    gen_p = sub.add_parser("gen", help="Generate case from .nl.")
    gen_p.add_argument("path", help=".nl file path")
    gen_p.add_argument("--spec-root", default="specs")
    gen_p.add_argument("--output-root", default="generated-tests/ui")
    gen_p.add_argument("--skip-install", action="store_true")
    gen_p.add_argument("--no-preview", action="store_true")
    gen_p.add_argument("--no-resolve-locators", action="store_true")
    gen_p.add_argument("--udid", help="Device id for locator resolve.")

    sub.add_parser("doctor", help="Preflight: deps, adb, Appium, capabilities, Allure.")

    clean_p = sub.add_parser("clean", help="Remove allure-results/report and optional logs.")
    clean_p.add_argument("--results", action="store_true")
    clean_p.add_argument("--report", action="store_true")
    clean_p.add_argument("--logs", action="store_true")
    clean_p.add_argument("--artifacts", action="store_true")
    clean_p.add_argument("--dry-run", action="store_true")

    insp_p = sub.add_parser("inspect", help="Open Android Inspector.")
    insp_p.add_argument(
        "--powershell",
        action="store_true",
        help="(Legacy) Same as default on Windows; kept for compatibility.",
    )
    insp_p.add_argument(
        "--skip-powershell-setup",
        action="store_true",
        help="Skip Windows PowerShell Appium/plugin bootstrap.",
    )

    rep_p = sub.add_parser("repair", help="Repair Appium/UiAutomator2 session; optionally open inspector.")
    rep_p.add_argument("--open-inspector", action="store_true")

    args = parser.parse_args()

    if args.cmd == "run":
        forward: list[str] = []
        if args.priority:
            forward += ["--priority", args.priority]
        if args.test:
            forward += ["--test", args.test]
        if args.device:
            forward += ["--device", args.device]
        if args.skip_install:
            forward += ["--skip-install"]
        if args.skip_repair:
            forward += ["--skip-repair"]
        if args.skip_appium_start:
            forward += ["--skip-appium-start"]
        if args.no_open_report:
            forward += ["--no-open-report"]
        if args.fresh_results:
            forward += ["--fresh-results"]
        if args.static_report:
            forward += ["--static-report"]
        if args.request:
            forward = [args.request, *forward]
        forward += list(args.pytest_args)
        raise SystemExit(_run("run_ui_tests.py", forward))

    if args.cmd == "import":
        forward = [args.path, "--spec-root", args.spec_root, "--output-root", args.output_root]
        if args.dry_run:
            forward.append("--dry-run")
        if args.nl_only:
            forward.append("--nl-only")
        if args.skip_install:
            forward.append("--skip-install")
        if args.no_resolve_locators:
            forward.append("--no-resolve-locators")
        if args.udid:
            forward += ["--udid", args.udid]
        raise SystemExit(_run("import_cases_from_sheet.py", forward))

    if args.cmd == "gen":
        forward = [args.path, "--spec-root", args.spec_root, "--output-root", args.output_root]
        if args.skip_install:
            forward.append("--skip-install")
        if args.no_preview:
            forward.append("--no-preview")
        if args.no_resolve_locators:
            forward.append("--no-resolve-locators")
        if args.udid:
            forward += ["--udid", args.udid]
        raise SystemExit(_run("create_case_from_nl.py", forward))

    if args.cmd == "doctor":
        raise SystemExit(_run("uiatest_doctor.py", []))

    if args.cmd == "clean":
        forward: list[str] = []
        if args.results:
            forward.append("--results")
        if args.report:
            forward.append("--report")
        if args.logs:
            forward.append("--logs")
        if args.artifacts:
            forward.append("--artifacts")
        if args.dry_run:
            forward.append("--dry-run")
        raise SystemExit(_run("uiatest_clean.py", forward))

    if args.cmd == "inspect":
        forward: list[str] = []
        if args.skip_powershell_setup:
            forward.append("--skip-powershell-setup")
        raise SystemExit(_run("uiatest_inspect.py", forward))

    if args.cmd == "repair":
        forward = []
        if args.open_inspector:
            forward += ["--open-inspector"]
        raise SystemExit(_run("repair_appium_session.py", forward))


if __name__ == "__main__":
    main()
