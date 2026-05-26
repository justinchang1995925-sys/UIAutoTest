#!/usr/bin/env python3
"""Install Allure CLI into the project and configure environment variables."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from allure_cli import ALLURE_VERSION, ensure_allure_cli  # noqa: E402
from project_paths import resolve_project_root  # noqa: E402

PROJECT_ROOT = resolve_project_root(SCRIPT_DIR)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Project root (default: UIAutoTest).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download and reinstall Allure CLI.",
    )
    parser.add_argument(
        "--skip-user-env",
        action="store_true",
        help="Do not update Windows user PATH / ALLURE_HOME.",
    )
    args = parser.parse_args()

    executable = ensure_allure_cli(
        args.project_root.resolve(),
        configure_user_env=not args.skip_user_env,
        force_download=args.force,
    )
    print(f"Allure {ALLURE_VERSION} installed.")
    print(f"Executable: {executable}")
    print(f"Project env scripts: {args.project_root / 'allure-env.cmd'}")


if __name__ == "__main__":
    main()
