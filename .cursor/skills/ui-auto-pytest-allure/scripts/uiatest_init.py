#!/usr/bin/env python3
"""Bootstrap a UI automation project from the skill scaffold (skill-only distribution)."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCAFFOLD_ROOT = SKILL_DIR / "scaffold"
SKIP_NAMES = {".git", ".gitkeep"}


def _skill_marker(path: Path) -> bool:
    return (path / ".cursor" / "skills" / "ui-auto-pytest-allure" / "SKILL.md").is_file()


def _resolve_target(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    current = Path.cwd().resolve()
    for candidate in [current, *current.parents]:
        if _skill_marker(candidate):
            return candidate
    return current


def _iter_scaffold_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(SCAFFOLD_ROOT.rglob("*")):
        if path.is_file() and path.name not in SKIP_NAMES:
            files.append(path.relative_to(SCAFFOLD_ROOT))
    return files


def _copy_scaffold(target: Path, *, force: bool, dry_run: bool) -> tuple[int, int]:
    if not SCAFFOLD_ROOT.is_dir():
        raise SystemExit(f"Missing scaffold directory: {SCAFFOLD_ROOT}")

    created = 0
    skipped = 0
    for rel in _iter_scaffold_files():
        src = SCAFFOLD_ROOT / rel
        dest = target / rel
        if dest.exists() and not force:
            skipped += 1
            continue
        if dry_run:
            print(f"{'OVERWRITE' if dest.exists() else 'CREATE'} {dest}")
            created += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"Wrote {dest}")
        created += 1

    for sub in ("specs", "allure-results", "allure-report", "logs"):
        folder = target / sub
        if not folder.exists() and not dry_run:
            folder.mkdir(parents=True, exist_ok=True)
            print(f"Created {folder}/")

    return created, skipped


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize UIAutoTest project files from skill scaffold.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Project root (default: cwd or nearest folder containing this skill).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing scaffold files (e.g. conftest, uiatest.py).",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--with-setup",
        action="store_true",
        help="After scaffold copy, run install_ui_dependencies.py (pip + Allure + Appium stack).",
    )
    args = parser.parse_args()

    target = _resolve_target(args.target)
    if not _skill_marker(target):
        skill_dest = target / ".cursor" / "skills" / "ui-auto-pytest-allure"
        if not skill_dest.exists():
            print(
                "Warning: .cursor/skills/ui-auto-pytest-allure not found under target.\n"
                "Copy the skill folder into the project first, then re-run init.",
                file=sys.stderr,
            )

    print(f"Project root: {target}")
    print(f"Scaffold: {SCAFFOLD_ROOT}")
    created, skipped = _copy_scaffold(target, force=args.force, dry_run=args.dry_run)
    print(f"Done. wrote={created} skipped={skipped} (use --force to overwrite skipped)")

    if args.dry_run:
        return

    uiatest = target / "uiatest.py"
    if uiatest.is_file():
        print("\nNext steps:")
        print(f"  cd {target}")
        if not args.with_setup:
            print("  python uiatest.py setup          # pip + Allure + Appium (needs Node.js/npm)")
        print("  # Edit capabilities.template.json (appPackage / appActivity — required)")
        print("  python uiatest.py doctor         # connect Android device first")
        print("  python uiatest.py gen cases/template.nl")
        print("  python uiatest.py run --priority P1")
        print("\nSee: .cursor/skills/ui-auto-pytest-allure/scaffold/QUICKSTART.md")

    if args.with_setup and not args.dry_run:
        installer = SKILL_DIR / "scripts" / "install_ui_dependencies.py"
        if installer.is_file():
            print("\nRunning environment setup (uiatest setup)...")
            result = subprocess.run(
                [sys.executable, str(installer)],
                cwd=str(target),
                check=False,
            )
            if result.returncode != 0:
                print(
                    "Setup exited with errors. Install Node.js LTS if npm is missing, "
                    "then run: python uiatest.py setup",
                    file=sys.stderr,
                )
        else:
            print(f"Warning: installer not found: {installer}", file=sys.stderr)


if __name__ == "__main__":
    main()
