#!/usr/bin/env python3
"""Run generated UI regression tests by priority.

Deprecated: prefer `python uiatest.py run --priority P1`.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("priority", help="Priority to run: P0, P1, P2, P3, or P4.")
    parser.add_argument("--test-root", default="generated-tests/ui", help="Generated pytest root directory.")
    parser.add_argument("--allure-root", default="allure-results", help="Allure results root directory.")
    parser.add_argument("--skip-install", action="store_true", help="Skip automatic pip install.")
    parser.add_argument("pytest_args", nargs="*", help="Additional pytest arguments.")
    args = parser.parse_args()

    print(
        "Note: run_priority.py is deprecated. "
        f"Use: python uiatest.py run --priority {args.priority.upper()}"
    )

    forward = [
        "--priority",
        args.priority.upper(),
        "--test-root",
        args.test_root,
        "--allure-root",
        args.allure_root,
        *args.pytest_args,
    ]
    if args.skip_install:
        forward.append("--skip-install")

    runner = SCRIPT_DIR / "run_ui_tests.py"
    raise SystemExit(subprocess.call([sys.executable, str(runner), *forward], cwd=str(Path.cwd())))


if __name__ == "__main__":
    main()
