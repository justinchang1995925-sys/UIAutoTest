#!/usr/bin/env python3
"""Install Appium CLI, UiAutomator2 driver, and Inspector plugin via npm."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from project_paths import resolve_project_root  # noqa: E402

PROJECT_ROOT = resolve_project_root(SCRIPT_DIR)


def _npm_global_bin_dirs() -> list[Path]:
    dirs: list[Path] = []
    try:
        result = subprocess.run(
            ["npm", "prefix", "-g"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            prefix = result.stdout.strip()
            if prefix:
                dirs.append(Path(prefix))
                dirs.append(Path(prefix) / "bin")
    except (OSError, subprocess.TimeoutExpired):
        pass

    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        dirs.append(Path(appdata) / "npm")
    return dirs


def _augment_path_env(env: dict[str, str]) -> dict[str, str]:
    extra: list[str] = []
    for directory in _npm_global_bin_dirs():
        if directory.is_dir():
            extra.append(str(directory))
    if not extra:
        return env
    current = env.get("PATH", "")
    merged = os.pathsep.join(extra + ([current] if current else []))
    env = dict(env)
    env["PATH"] = merged
    return env


def _which(command: str, env: dict[str, str] | None = None) -> str | None:
    return shutil.which(command, path=env.get("PATH") if env else None)


def _run(command: list[str], *, env: dict[str, str] | None = None, timeout: int = 600) -> int:
    print("Running:", " ".join(command))
    result = subprocess.run(command, env=env, check=False, timeout=timeout)
    return result.returncode


def _driver_installed(appium_cmd: str, env: dict[str, str]) -> bool:
    result = subprocess.run(
        [appium_cmd, "driver", "list", "--installed", "--json"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        return False
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return "uiautomator2" in (result.stdout or "")
    return bool(data.get("uiautomator2"))


def install_appium_stack(*, install_inspector_plugin: bool = True) -> None:
    if not _which("npm"):
        raise SystemExit(
            "npm is not installed or not in PATH.\n"
            "Install Node.js LTS from https://nodejs.org/ then run:\n"
            "  python uiatest.py setup\n"
            "or:\n"
            "  python .cursor/skills/ui-auto-pytest-allure/scripts/install_appium_stack.py"
        )

    env = _augment_path_env(os.environ.copy())

    appium_cmd = _which("appium", env)
    if not appium_cmd:
        print("Installing Appium globally (npm install -g appium)...")
        code = _run(["npm", "install", "-g", "appium"], env=env)
        if code != 0:
            raise SystemExit(f"npm install -g appium failed (exit {code}).")
        env = _augment_path_env(env)
        appium_cmd = _which("appium", env)
        if not appium_cmd:
            raise SystemExit(
                "Appium was installed but is not in PATH for this terminal.\n"
                "Close and reopen the terminal, then run: python uiatest.py doctor"
            )

    print(f"Appium CLI: {appium_cmd}")

    if not _driver_installed(appium_cmd, env):
        print("Installing Appium driver: uiautomator2 ...")
        code = _run([appium_cmd, "driver", "install", "uiautomator2"], env=env)
        if code != 0:
            raise SystemExit(f"appium driver install uiautomator2 failed (exit {code}).")
    else:
        print("Appium driver uiautomator2 is already installed.")

    if install_inspector_plugin:
        print("Installing Appium Inspector plugin (optional, for uiatest inspect)...")
        _run([appium_cmd, "plugin", "install", "inspector"], env=env)

    print("Appium stack is ready. Verify with: python uiatest.py doctor")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-inspector-plugin",
        action="store_true",
        help="Do not install the Appium Inspector plugin.",
    )
    args = parser.parse_args()
    install_appium_stack(install_inspector_plugin=not args.skip_inspector_plugin)


if __name__ == "__main__":
    main()
