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
    run_p.add_argument("pytest_args", nargs="*", help="Extra pytest args after '--'.")

    imp_p = sub.add_parser("import", help="Import cases from CSV/XLSX sheet.")
    imp_p.add_argument("path", help="CSV/XLSX path")
    imp_p.add_argument("--spec-root", default="specs")
    imp_p.add_argument("--output-root", default="generated-tests/ui")

    gen_p = sub.add_parser("gen", help="Generate case from .nl.")
    gen_p.add_argument("path", help=".nl file path")
    gen_p.add_argument("--spec-root", default="specs")
    gen_p.add_argument("--output-root", default="generated-tests/ui")
    gen_p.add_argument("--skip-install", action="store_true")

    insp_p = sub.add_parser("inspect", help="Open Android Inspector.")
    insp_p.add_argument("--powershell", action="store_true", help="Use PowerShell script on Windows.")

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
        if args.request:
            forward = [args.request, *forward]
        forward += list(args.pytest_args)
        raise SystemExit(_run("run_ui_tests.py", forward))

    if args.cmd == "import":
        raise SystemExit(
            _run(
                "import_cases_from_sheet.py",
                [args.path, "--spec-root", args.spec_root, "--output-root", args.output_root],
            )
        )

    if args.cmd == "gen":
        forward = [args.path, "--spec-root", args.spec_root, "--output-root", args.output_root]
        if args.skip_install:
            forward += ["--skip-install"]
        raise SystemExit(_run("create_case_from_nl.py", forward))

    if args.cmd == "inspect":
        ps1 = SKILL_DIR / "open_android_inspector.ps1"
        if sys.platform == "win32" and ps1.exists():
            raise SystemExit(
                subprocess.call(
                    ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
                    cwd=str(PROJECT_ROOT),
                )
            )
        raise SystemExit("Inspector launcher is only supported on Windows via open_android_inspector.ps1.")

    if args.cmd == "repair":
        forward = []
        if args.open_inspector:
            forward += ["--open-inspector"]
        raise SystemExit(_run("repair_appium_session.py", forward))


if __name__ == "__main__":
    main()

