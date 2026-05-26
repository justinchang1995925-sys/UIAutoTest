#!/usr/bin/env python3
"""Install Python dependencies for generated UI automation tests."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from allure_cli import ensure_allure_cli  # noqa: E402
from project_paths import resolve_project_root  # noqa: E402

PROJECT_ROOT = resolve_project_root(SCRIPT_DIR)


DEFAULT_REQUIREMENTS = Path("generated-tests/ui/requirements.txt")
FALLBACK_REQUIREMENTS = [
    Path("generated-tests/ui/P0/requirements.txt"),
    Path("generated-tests/ui/P1/requirements.txt"),
]


def find_requirements_file(explicit: Path | None) -> Path:
    if explicit and explicit.exists():
        return explicit
    if DEFAULT_REQUIREMENTS.exists():
        return DEFAULT_REQUIREMENTS
    for path in FALLBACK_REQUIREMENTS:
        if path.exists():
            return path
    raise SystemExit(
        "No requirements.txt found. Generate a case first or pass --requirements."
    )


def install_requirements(requirements_path: Path) -> None:
    command = [sys.executable, "-m", "pip", "install", "-r", str(requirements_path)]
    print("Running:", " ".join(command))
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(f"pip install failed with exit code {result.returncode}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--requirements",
        type=Path,
        help="Path to requirements.txt. Defaults to generated-tests/ui/requirements.txt",
    )
    args = parser.parse_args()

    requirements_path = find_requirements_file(args.requirements)
    install_requirements(requirements_path)
    print(f"Installed dependencies from {requirements_path}")

    print("Installing Allure CLI into project .tools/ ...")
    try:
        ensure_allure_cli(PROJECT_ROOT)
    except Exception as exc:
        print(f"Warning: Allure CLI auto-install failed: {exc}")
        print("You can retry with:")
        print("  python .cursor/skills/ui-auto-pytest-allure/scripts/install_allure_cli.py")

    print("Run tests with pytest, for example:")
    print("  python -m pytest generated-tests/ui/P1 -m P1 --alluredir=allure-results/P1")


if __name__ == "__main__":
    main()
