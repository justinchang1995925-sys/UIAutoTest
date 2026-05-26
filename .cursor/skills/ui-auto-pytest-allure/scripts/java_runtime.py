#!/usr/bin/env python3
"""Detect or install a portable JRE for Allure CLI."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

from project_paths import resolve_project_root

JRE_VERSION = "17.0.13+11"
JRE_DOWNLOAD_URL = (
    "https://github.com/adoptium/temurin17-binaries/releases/download/"
    "jdk-17.0.13%2B11/OpenJDK17U-jre_x64_windows_hotspot_17.0.13_11.zip"
)


def _tools_root(project_root: Path) -> Path:
    return project_root / ".tools"


def _manifest_path(project_root: Path) -> Path:
    return _tools_root(project_root) / "java-jre.json"


def _find_java_in_path() -> Path | None:
    java_cmd = shutil.which("java")
    if not java_cmd:
        return None
    java_path = Path(java_cmd).resolve()
    candidate_home = java_path.parent.parent
    if (candidate_home / "bin" / "java.exe").exists() or (candidate_home / "bin" / "java").exists():
        return candidate_home
    return None


def _find_java_windows_registry() -> Path | None:
    if platform.system().lower() != "windows":
        return None
    try:
        import winreg
    except ImportError:
        return None

    registry_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\JDK"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Eclipse Adoptium\JDK"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\JDK"),
    ]
    for hive, subkey in registry_paths:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                index = 0
                while True:
                    try:
                        version_key_name = winreg.EnumKey(key, index)
                        with winreg.OpenKey(key, version_key_name) as version_key:
                            home, _ = winreg.QueryValueEx(version_key, "JavaHome")
                            home_path = Path(str(home))
                            if home_path.exists():
                                return home_path
                    except OSError:
                        break
                    index += 1
        except OSError:
            continue
    return None


def _portable_jre_dir(project_root: Path) -> Path:
    return _tools_root(project_root) / "jdk-17-jre"


def _java_executable(java_home: Path) -> Path:
    name = "java.exe" if platform.system().lower() == "windows" else "java"
    return java_home / "bin" / name


def _verify_java(java_home: Path) -> bool:
    java_bin = _java_executable(java_home)
    if not java_bin.exists():
        return False
    try:
        result = subprocess.run(
            [str(java_bin), "-version"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _download_portable_jre(archive_path: Path) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading portable JRE {JRE_VERSION} for Allure ...")
    urlretrieve(JRE_DOWNLOAD_URL, archive_path)


def _extract_jre(archive_path: Path, tools_dir: Path) -> Path:
    tools_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "r") as archive:
        archive.extractall(tools_dir)
    candidates = sorted(tools_dir.glob("jdk-*-jre"))
    if not candidates:
        candidates = sorted(tools_dir.glob("jdk*"))
    if not candidates:
        raise RuntimeError(f"JRE archive extracted but folder not found under {tools_dir}")
    return candidates[-1]


def _write_manifest(project_root: Path, java_home: Path) -> None:
    manifest = {"version": JRE_VERSION, "java_home": str(java_home.resolve())}
    _manifest_path(project_root).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _configure_windows_user_java_home(java_home: Path) -> None:
    if platform.system().lower() != "windows":
        return
    try:
        import winreg
    except ImportError:
        return

    home_text = str(java_home.resolve())
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Environment",
        0,
        winreg.KEY_READ | winreg.KEY_WRITE,
    )
    try:
        winreg.SetValueEx(key, "JAVA_HOME", 0, winreg.REG_EXPAND_SZ, home_text)
    finally:
        winreg.CloseKey(key)
    print(f"Updated user JAVA_HOME={home_text}")


def ensure_java_runtime(
    project_root: Path | None = None,
    *,
    configure_user_env: bool = True,
) -> Path:
    root = resolve_project_root(project_root or Path.cwd())

    for finder in (_find_java_in_path, _find_java_windows_registry):
        java_home = finder()
        if java_home and _verify_java(java_home):
            _write_manifest(root, java_home)
            if configure_user_env:
                _configure_windows_user_java_home(java_home)
            return java_home.resolve()

    manifest = None
    if _manifest_path(root).exists():
        manifest = json.loads(_manifest_path(root).read_text(encoding="utf-8-sig"))
        java_home = Path(manifest["java_home"])
        if _verify_java(java_home):
            return java_home.resolve()

    if platform.system().lower() != "windows":
        raise RuntimeError(
            "Java runtime is required for Allure CLI. Install JDK 17+ and set JAVA_HOME."
        )

    tools_dir = _tools_root(root)
    target_dir = _portable_jre_dir(root)
    archive_path = tools_dir / "OpenJDK17U-jre_x64_windows.zip"

    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)

    if not archive_path.exists():
        _download_portable_jre(archive_path)

    extracted = _extract_jre(archive_path, tools_dir)
    if extracted != target_dir and extracted.exists():
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        extracted.rename(target_dir)

    if not _verify_java(target_dir):
        raise RuntimeError(f"Portable JRE installation failed: {target_dir}")

    _write_manifest(root, target_dir)
    if configure_user_env:
        _configure_windows_user_java_home(target_dir)
    print(f"Portable JRE ready: {target_dir}")
    return target_dir.resolve()


def apply_java_env(env: dict[str, str], project_root: Path) -> dict[str, str]:
    try:
        java_home = ensure_java_runtime(project_root, configure_user_env=False)
    except Exception:
        java_home = _find_java_in_path() or _find_java_windows_registry()
    if java_home:
        env["JAVA_HOME"] = str(java_home)
        java_bin = str((java_home / "bin").resolve())
        env["PATH"] = java_bin + os.pathsep + env.get("PATH", "")
    return env
