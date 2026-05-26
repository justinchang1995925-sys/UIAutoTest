#!/usr/bin/env python3
"""Resolve or install Allure CLI inside the project (.tools/allure-*)."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

from java_runtime import apply_java_env, ensure_java_runtime
from project_paths import resolve_project_root

ALLURE_VERSION = "2.32.2"
GITHUB_RELEASE_BASE = (
    f"https://github.com/allure-framework/allure2/releases/download/{ALLURE_VERSION}"
)


def _tools_root(project_root: Path) -> Path:
    return project_root / ".tools"


def _install_dir(project_root: Path) -> Path:
    return _tools_root(project_root) / f"allure-{ALLURE_VERSION}"


def _manifest_path(project_root: Path) -> Path:
    return _tools_root(project_root) / "allure-cli.json"


def _download_name() -> str:
    system = platform.system().lower()
    if system == "windows":
        return f"allure-{ALLURE_VERSION}.zip"
    if system == "darwin":
        return f"allure-{ALLURE_VERSION}.tgz"
    return f"allure-{ALLURE_VERSION}.tgz"


def _allure_executable(install_dir: Path) -> Path:
    if platform.system().lower() == "windows":
        return install_dir / "bin" / "allure.bat"
    return install_dir / "bin" / "allure"


def _is_executable_ready(executable: Path, project_root: Path) -> bool:
    if not executable.exists():
        return False
    try:
        env = apply_java_env(os.environ.copy(), project_root)
        result = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=env,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _download_allure(archive_path: Path) -> None:
    url = f"{GITHUB_RELEASE_BASE}/{_download_name()}"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading Allure CLI {ALLURE_VERSION} ...")
    print(url)
    urlretrieve(url, archive_path)


def _extract_archive(archive_path: Path, tools_dir: Path) -> Path:
    tools_dir.mkdir(parents=True, exist_ok=True)
    if archive_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(tools_dir)
    else:
        import tarfile

        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(tools_dir)

    install_dir = tools_dir / f"allure-{ALLURE_VERSION}"
    if not install_dir.exists():
        candidates = sorted(tools_dir.glob("allure-*"))
        if not candidates:
            raise RuntimeError(f"Allure archive extracted but folder not found under {tools_dir}")
        install_dir = candidates[-1]
    return install_dir


def _write_manifest(project_root: Path, install_dir: Path) -> None:
    manifest = {
        "version": ALLURE_VERSION,
        "install_dir": str(install_dir.resolve()),
        "bin_dir": str((install_dir / "bin").resolve()),
        "executable": str(_allure_executable(install_dir).resolve()),
    }
    _manifest_path(project_root).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_project_env_scripts(project_root: Path, install_dir: Path) -> None:
    bin_dir = install_dir / "bin"
    allure_home = install_dir.resolve()

    ps1 = project_root / "allure-env.ps1"
    ps1.write_text(
        "\n".join(
            [
                f'$env:ALLURE_HOME = "{allure_home}"',
                f'$env:Path = "{bin_dir.resolve()}" + [IO.Path]::PathSeparator + $env:Path',
                "",
            ]
        ),
        encoding="utf-8",
    )

    cmd = project_root / "allure-env.cmd"
    cmd.write_text(
        "\n".join(
            [
                f'set "ALLURE_HOME={allure_home}"',
                f'set "PATH={bin_dir.resolve()};%PATH%"',
                "",
            ]
        ),
        encoding="utf-8",
    )


def _configure_windows_user_environment(bin_dir: Path, install_dir: Path) -> None:
    if platform.system().lower() != "windows":
        return

    try:
        import winreg
    except ImportError:
        return

    bin_text = str(bin_dir.resolve())
    home_text = str(install_dir.resolve())

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Environment",
        0,
        winreg.KEY_READ | winreg.KEY_WRITE,
    )
    try:
        try:
            current_path, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current_path = ""

        parts = [part for part in str(current_path).split(";") if part]
        if not any(Path(part).resolve() == Path(bin_text) for part in parts):
            parts.append(bin_text)
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, ";".join(parts))

        winreg.SetValueEx(key, "ALLURE_HOME", 0, winreg.REG_EXPAND_SZ, home_text)
    finally:
        winreg.CloseKey(key)

    print(f"Updated user environment: ALLURE_HOME={home_text}")
    print(f"Added to user PATH: {bin_text}")
    print("Open a new terminal if `allure` is still not recognized.")


def ensure_allure_cli(
    project_root: Path | None = None,
    *,
    configure_user_env: bool = True,
    force_download: bool = False,
) -> Path:
    """Install Allure CLI under project_root/.tools if needed. Returns executable path."""
    project_root = resolve_project_root(project_root or Path.cwd())
    ensure_java_runtime(project_root, configure_user_env=configure_user_env)
    install_dir = _install_dir(project_root)
    executable = _allure_executable(install_dir)

    if not force_download and _is_executable_ready(executable, project_root):
        _write_manifest(project_root, install_dir)
        _write_project_env_scripts(project_root, install_dir)
        if configure_user_env:
            _configure_windows_user_environment(install_dir / "bin", install_dir)
        return executable

    existing = shutil.which("allure")
    if not force_download and existing and _is_executable_ready(Path(existing), project_root):
        print(f"Using existing Allure CLI on PATH: {existing}")
        return Path(existing)

    tools_dir = _tools_root(project_root)
    archive_path = tools_dir / _download_name()

    if install_dir.exists() and force_download:
        shutil.rmtree(install_dir, ignore_errors=True)

    if not _is_executable_ready(executable, project_root):
        if not archive_path.exists():
            _download_allure(archive_path)
        install_dir = _extract_archive(archive_path, tools_dir)
        executable = _allure_executable(install_dir)

    if not _is_executable_ready(executable, project_root):
        raise RuntimeError(f"Allure CLI installation failed: {executable}")

    _write_manifest(project_root, install_dir)
    _write_project_env_scripts(project_root, install_dir)
    if configure_user_env:
        _configure_windows_user_environment(install_dir / "bin", install_dir)

    print(f"Allure CLI ready: {executable}")
    return executable


def load_manifest(project_root: Path) -> dict | None:
    path = _manifest_path(project_root)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_allure_command(project_root: Path | None = None, *, auto_install: bool = True) -> str | None:
    """Return Allure CLI path, installing into .tools when auto_install is True."""
    root = resolve_project_root(project_root or Path.cwd())
    existing = shutil.which("allure")
    if existing and _is_executable_ready(Path(existing), root):
        return existing

    manifest = load_manifest(root)
    if manifest:
        executable = Path(manifest["executable"])
        if _is_executable_ready(executable, root):
            return str(executable)

    install_dir = _install_dir(root)
    executable = _allure_executable(install_dir)
    if _is_executable_ready(executable, root):
        return str(executable)

    if not auto_install:
        return None

    try:
        return str(ensure_allure_cli(root))
    except Exception as exc:
        print(f"Could not install Allure CLI automatically: {exc}")
        return None


def augmented_path_env(project_root: Path | None = None) -> dict[str, str]:
    """Environment with Java, Allure bin, and ALLURE_HOME configured."""
    root = resolve_project_root(project_root or Path.cwd())
    env = apply_java_env(os.environ.copy(), root)
    command = resolve_allure_command(root, auto_install=False)
    if not command:
        command = resolve_allure_command(root, auto_install=True)
    if command:
        bin_dir = str(Path(command).parent)
        env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
        env["ALLURE_HOME"] = str(Path(bin_dir).parent)
    return env
