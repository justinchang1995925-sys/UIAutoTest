#!/usr/bin/env python3
"""Start Appium (if needed), create a healthy session, open Inspector once."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from appium_server import ensure_appium_server, is_appium_ready  # noqa: E402
from project_paths import resolve_project_root  # noqa: E402

PROJECT_ROOT = resolve_project_root(SCRIPT_DIR)
PS1 = SCRIPT_DIR / "open_android_inspector.ps1"
REPAIR = SCRIPT_DIR / "repair_appium_session.py"


def _run_powershell_setup() -> int:
    if not PS1.exists():
        return 1
    return subprocess.call(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PS1),
            "-NoOpenInspector",
            "-NoAutoSession",
        ],
        cwd=str(PROJECT_ROOT),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-powershell-setup",
        action="store_true",
        help="On Windows, skip plugin install / Appium bootstrap via PowerShell.",
    )
    args = parser.parse_args()

    if sys.platform == "win32" and PS1.exists() and not args.skip_powershell_setup:
        code = _run_powershell_setup()
        if code != 0:
            raise SystemExit(code)
    elif not is_appium_ready():
        ensure_appium_server(PROJECT_ROOT)

    if not REPAIR.exists():
        raise SystemExit(f"Missing script: {REPAIR}")

    raise SystemExit(
        subprocess.call(
            [
                sys.executable,
                str(REPAIR),
                "--open-inspector",
                "--project-root",
                str(PROJECT_ROOT),
            ],
            cwd=str(PROJECT_ROOT),
        )
    )


if __name__ == "__main__":
    main()
