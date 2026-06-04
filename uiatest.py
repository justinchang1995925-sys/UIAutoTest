#!/usr/bin/env python3
"""Unified CLI for UIAutoTest workflows."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SKILL_DIR = PROJECT_ROOT / ".cursor" / "skills" / "ui-auto-pytest-allure" / "scripts"


def _run(script: str, args: list[str]) -> int:
    path = SKILL_DIR / script
    if not path.exists():
        skill_root = PROJECT_ROOT / ".cursor" / "skills" / "ui-auto-pytest-allure"
        raise SystemExit(
            f"Missing skill script: {path}\n\n"
            "Skill-only setup:\n"
            f"  1. Copy folder ui-auto-pytest-allure to: {skill_root}\n"
            "  2. Run: python .cursor/skills/ui-auto-pytest-allure/scripts/uiatest_init.py\n"
            "  3. Run: python uiatest.py setup\n"
            "See: .cursor/skills/ui-auto-pytest-allure/DISTRIBUTION.md"
        )
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
    run_p.add_argument(
        "--auto-repair",
        action="store_true",
        help="Repair Appium session after tests (for Inspector).",
    )
    run_p.add_argument("--skip-appium-start", action="store_true")
    run_p.add_argument("--no-open-report", action="store_true")
    run_p.add_argument(
        "--fresh-results",
        action="store_true",
        help="Clear allure-results before pytest. Priority runs clear by default.",
    )
    run_p.add_argument(
        "--static-report",
        action="store_true",
        help="Alias: HTML is always generated under allure-report/ (default report open).",
    )
    run_p.add_argument(
        "--skip-sheet-sync",
        action="store_true",
        help="Skip auto-import when cases/import_template.csv changed.",
    )
    run_p.add_argument(
        "--sheet-rewrite-on-sync",
        action="store_true",
        help="Rewrite CSV steps/expected with 步骤N: during auto-import sync.",
    )
    run_p.add_argument(
        "--skip-sheet-rewrite",
        action="store_true",
        help="During auto-import sync, do not rewrite CSV with 步骤N:.",
    )
    run_p.add_argument(
        "--auto-restore-inspector",
        action="store_true",
        help="Recreate Appium Inspector session after tests.",
    )
    run_p.add_argument(
        "--skip-sheet-results",
        action="store_true",
        help="Do not write PASS/FAIL back to the import sheet after the run.",
    )
    run_p.add_argument(
        "--skip-restore-inspector",
        action="store_true",
        help="Do not recreate Appium Inspector session after tests.",
    )
    run_p.add_argument("--start-package", help="Override entry appPackage (writes to capabilities.local.json).")
    run_p.add_argument("--start-activity", help="Override entry appActivity (writes to capabilities.local.json).")
    run_p.add_argument(
        "--no-per-test-entry",
        action="store_true",
        help="Disable per-test entry activity reset (default: on when appActivity is configured).",
    )
    run_p.add_argument(
        "--per-test-entry",
        action="store_true",
        help="Force per-test entry activity reset (requires appActivity configured).",
    )
    run_p.add_argument("pytest_args", nargs="*", help="Extra pytest args after '--'.")

    imp_p = sub.add_parser("import", help="Import cases from CSV/XLSX sheet.")
    imp_p.add_argument("path", help="CSV/XLSX path")
    imp_p.add_argument("--spec-root", default="specs")
    imp_p.add_argument("--output-root", default="generated-tests/ui")
    imp_p.add_argument("--dry-run", action="store_true")
    imp_p.add_argument("--nl-only", action="store_true")
    imp_p.add_argument("--skip-install", action="store_true")
    imp_p.add_argument(
        "--rewrite-sheet",
        action="store_true",
        help="(CSV only) Rewrite sheet in-place: prefix steps/expected with 步骤N: for alignment.",
    )
    imp_p.add_argument("--no-resolve-locators", action="store_true")
    imp_p.add_argument("--udid", help="Device id for locator resolve.")

    gen_p = sub.add_parser("gen", help="Generate case from .nl.")
    gen_p.add_argument("path", nargs="?", help=".nl file path (optional if --text is given)")
    gen_p.add_argument("--spec-root", default="specs")
    gen_p.add_argument("--output-root", default="generated-tests/ui")
    gen_p.add_argument("--skip-install", action="store_true")
    gen_p.add_argument("--text", help="Natural-language case text inline.")
    gen_p.add_argument("--no-resolve-locators", action="store_true")
    gen_p.add_argument("--udid", help="Device id for locator resolve.")

    init_p = sub.add_parser(
        "init",
        help="Bootstrap project files from skill scaffold (for skill-only distribution).",
    )
    init_p.add_argument("--target", type=Path, default=None, help="Project root directory.")
    init_p.add_argument("--force", action="store_true", help="Overwrite existing scaffold files.")
    init_p.add_argument("--dry-run", action="store_true")
    init_p.add_argument(
        "--with-setup",
        action="store_true",
        help="After copying scaffold, run python uiatest.py setup (pip + Allure + Appium).",
    )

    sub.add_parser("doctor", help="Preflight: deps, adb, Appium, capabilities, Allure.")

    setup_p = sub.add_parser(
        "setup",
        help="One-shot install: Python deps, Allure CLI, Appium + uiautomator2 driver (requires Node.js/npm).",
    )
    setup_p.add_argument(
        "--skip-appium",
        action="store_true",
        help="Only install Python packages and Allure CLI.",
    )

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
    rep_p.add_argument(
        "--stop-inspector-keepalive",
        action="store_true",
        help="Stop inspector background keepalive only.",
    )

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
        if args.auto_repair:
            forward += ["--auto-repair"]
        if args.skip_appium_start:
            forward += ["--skip-appium-start"]
        if args.no_open_report:
            forward += ["--no-open-report"]
        if args.fresh_results:
            forward += ["--fresh-results"]
        if args.static_report:
            forward += ["--static-report"]
        if args.skip_sheet_sync:
            forward += ["--skip-sheet-sync"]
        if args.sheet_rewrite_on_sync:
            forward += ["--sheet-rewrite-on-sync"]
        if args.skip_sheet_rewrite:
            forward += ["--skip-sheet-rewrite"]
        if args.skip_sheet_results:
            forward += ["--skip-sheet-results"]
        if args.skip_restore_inspector:
            forward += ["--skip-restore-inspector"]
        if args.auto_restore_inspector:
            forward += ["--auto-restore-inspector"]
        if args.start_package:
            forward += ["--start-package", args.start_package]
        if args.start_activity:
            forward += ["--start-activity", args.start_activity]
        if args.no_per_test_entry:
            forward += ["--no-per-test-entry"]
        if args.per_test_entry:
            forward += ["--per-test-entry"]
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
        if args.rewrite_sheet:
            forward.append("--rewrite-sheet")
        if args.no_resolve_locators:
            forward.append("--no-resolve-locators")
        if args.udid:
            forward += ["--udid", args.udid]
        raise SystemExit(_run("import_cases_from_sheet.py", forward))

    if args.cmd == "gen":
        if not args.path and not args.text:
            raise SystemExit("Provide a .nl path or --text.")
        forward: list[str] = []
        if args.path:
            forward.append(args.path)
        forward += ["--spec-root", args.spec_root, "--output-root", args.output_root]
        if args.skip_install:
            forward.append("--skip-install")
        if args.text:
            forward += ["--text", args.text]
        if args.no_resolve_locators:
            forward.append("--no-resolve-locators")
        if args.udid:
            forward += ["--udid", args.udid]
        raise SystemExit(_run("create_case_from_nl.py", forward))

    if args.cmd == "init":
        forward: list[str] = []
        if args.target is not None:
            forward += ["--target", str(args.target)]
        if args.force:
            forward.append("--force")
        if args.dry_run:
            forward.append("--dry-run")
        if args.with_setup:
            forward.append("--with-setup")
        code = _run("uiatest_init.py", forward)
        raise SystemExit(code)

    if args.cmd == "doctor":
        raise SystemExit(_run("uiatest_doctor.py", []))

    if args.cmd == "setup":
        if args.skip_appium:
            os.environ["UIATEST_SKIP_APPIUM_INSTALL"] = "1"
        raise SystemExit(_run("install_ui_dependencies.py", []))

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
        if args.stop_inspector_keepalive:
            forward += ["--stop-keepalive"]
        raise SystemExit(_run("repair_appium_session.py", forward))


if __name__ == "__main__":
    main()
