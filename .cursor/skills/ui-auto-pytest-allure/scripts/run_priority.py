#!/usr/bin/env python3
"""Run generated UI regression tests by priority."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from run_ui_tests import ensure_dependencies, run_priority_tests  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("priority", help="Priority to run: P0, P1, P2, P3, or P4.")
    parser.add_argument("--test-root", default="generated-tests/ui", help="Generated pytest root directory.")
    parser.add_argument("--allure-root", default="allure-results", help="Allure results root directory.")
    parser.add_argument("--skip-install", action="store_true", help="Skip automatic pip install.")
    parser.add_argument("pytest_args", nargs="*", help="Additional pytest arguments.")
    args = parser.parse_args()

    ensure_dependencies(args.skip_install)
    raise SystemExit(
        run_priority_tests(
            args.priority.upper(),
            Path(args.test_root),
            Path(args.allure_root),
            args.pytest_args,
        )
    )


if __name__ == "__main__":
    main()
