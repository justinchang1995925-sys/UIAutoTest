#!/usr/bin/env python3
"""Auto-import cases/import_template.csv when it changed since the last test run."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_SHEET = "cases/import_template.csv"
STATE_FILE = "import-template.sync.json"


def sheet_import_path(project_root: Path) -> Path:
    rel = os.getenv("UIATEST_IMPORT_SHEET", DEFAULT_SHEET).strip() or DEFAULT_SHEET
    return (project_root / rel).resolve()


def _state_path(project_root: Path) -> Path:
    return project_root / ".tools" / STATE_FILE


def file_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def sheet_cases_fingerprint(sheet: Path) -> str:
    """Hash case-definition columns only (excludes 测试结果) so result writeback won't re-import."""
    from import_cases_from_sheet import _load_sheet  # noqa: E402
    from sheet_case_parser import _map_headers  # noqa: E402

    headers, rows = _load_sheet(sheet)
    header_map = _map_headers(headers)
    result_col = header_map.get("result")
    cols = [index for index in range(len(headers)) if index != result_col]

    digest = hashlib.sha256()
    digest.update("\x1f".join(headers[index] for index in cols).encode("utf-8"))
    digest.update(b"\n")
    for row in rows:
        cells = [str(row[index] if index < len(row) else "") for index in cols]
        digest.update("\x1f".join(cells).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def load_synced_fingerprint(project_root: Path) -> str | None:
    state_path = _state_path(project_root)
    if not state_path.is_file():
        return None
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    sheet = sheet_import_path(project_root)
    recorded_sheet = data.get("sheet", "")
    try:
        if recorded_sheet and Path(recorded_sheet).resolve() != sheet.resolve():
            return None
    except OSError:
        return None
    value = data.get("sha256")
    return value if isinstance(value, str) and value else None


def save_synced_fingerprint(project_root: Path, fingerprint: str, sheet: Path) -> None:
    state_path = _state_path(project_root)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        sheet_ref = str(sheet.relative_to(project_root))
    except ValueError:
        sheet_ref = str(sheet)
    state_path.write_text(
        json.dumps({"sha256": fingerprint, "sheet": sheet_ref}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def maybe_sync_sheet_import(
    project_root: Path,
    script_dir: Path,
    *,
    skip_install: bool = False,
    disabled: bool = False,
    rewrite_sheet: bool = False,
) -> bool:
    """Import the template sheet when its content changed. Returns True if import ran."""
    if disabled or os.getenv("UIATEST_SKIP_SHEET_SYNC", "").lower() in {"1", "true", "yes"}:
        return False

    sheet = sheet_import_path(project_root)
    if not sheet.is_file():
        return False

    current = sheet_cases_fingerprint(sheet)
    previous = load_synced_fingerprint(project_root)
    if current == previous:
        print(f"Import sheet unchanged; skip import ({sheet.relative_to(project_root)}).")
        return False

    print(f"Import sheet changed; importing {sheet.relative_to(project_root)} ...")
    importer = script_dir / "import_cases_from_sheet.py"
    if not importer.is_file():
        raise SystemExit(f"Missing import script: {importer}")

    command = [sys.executable, str(importer), str(sheet)]
    if (
        rewrite_sheet
        and sheet.suffix.lower() == ".csv"
        and os.getenv("UIATEST_SKIP_SHEET_REWRITE", "").lower() not in {"1", "true", "yes"}
    ):
        command.append("--rewrite-sheet")
    if skip_install:
        command.append("--skip-install")

    result = subprocess.run(command, cwd=str(project_root), check=False)
    if result.returncode != 0:
        raise SystemExit(f"Auto-import failed for {sheet} (exit code {result.returncode}).")

    save_synced_fingerprint(project_root, sheet_cases_fingerprint(sheet), sheet)
    print("Auto-import completed.")
    return True
