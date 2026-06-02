#!/usr/bin/env python3
"""Remove generated Allure artifacts and optional runtime logs."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from project_paths import resolve_project_root  # noqa: E402

PROJECT_ROOT = resolve_project_root(SCRIPT_DIR)
KEEPALIVE_LOG = "inspector-keepalive.log"


def _remove_tree(path: Path, label: str, dry_run: bool) -> None:
    if not path.exists():
        print(f"Skip {label} (not found): {path}")
        return
    if dry_run:
        print(f"Would remove {label}: {path}")
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    print(f"Removed {label}: {path}")


def _remove_logs_preserve_keepalive(logs_dir: Path, dry_run: bool) -> None:
    if not logs_dir.is_dir():
        print(f"Skip logs (not found): {logs_dir}")
        return
    keepalive = logs_dir / KEEPALIVE_LOG
    preserved = keepalive.is_file()
    if dry_run:
        suffix = f" (preserve {KEEPALIVE_LOG})" if preserved else ""
        print(f"Would remove logs: {logs_dir}{suffix}")
        return
    if preserved:
        backup = keepalive.read_bytes()
    shutil.rmtree(logs_dir)
    if preserved:
        logs_dir.mkdir(parents=True, exist_ok=True)
        keepalive.write_bytes(backup)
        print(f"Removed logs (preserved {KEEPALIVE_LOG}): {logs_dir}")
    else:
        print(f"Removed logs: {logs_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", action="store_true", help="Remove allure-results/")
    parser.add_argument("--report", action="store_true", help="Remove allure-report/")
    parser.add_argument("--logs", action="store_true", help="Remove logs/")
    parser.add_argument("--artifacts", action="store_true", help="Remove artifacts/ (failure videos)")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Remove results, report, logs, and artifacts (default when no flag given).",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not any((args.results, args.report, args.logs, args.artifacts)):
        args.all = True

    if args.all or args.results:
        _remove_tree(PROJECT_ROOT / "allure-results", "allure-results", args.dry_run)
    if args.all or args.report:
        _remove_tree(PROJECT_ROOT / "allure-report", "allure-report", args.dry_run)
    if args.all or args.logs:
        _remove_logs_preserve_keepalive(PROJECT_ROOT / "logs", args.dry_run)
    if args.all or args.artifacts:
        _remove_tree(PROJECT_ROOT / "artifacts", "artifacts", args.dry_run)


if __name__ == "__main__":
    main()
