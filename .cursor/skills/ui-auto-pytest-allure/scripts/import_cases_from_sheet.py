#!/usr/bin/env python3
"""Import UI cases from Excel (.xlsx) or CSV (Feishu export) into NL specs and pytest tests."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from project_paths import resolve_project_root  # noqa: E402

PROJECT_ROOT = resolve_project_root(SCRIPT_DIR)

from generate_ui_test import validate_spec, write_outputs  # noqa: E402
from nl_case_parser import parse_natural_language_case  # noqa: E402
from resolve_locators import resolve_spec_locators  # noqa: E402
from sheet_case_parser import (  # noqa: E402
    _format_expected_lines,
    _format_step_lines,
    _map_headers,
    rows_to_nl_cases,
)
from sheet_import_sync import save_synced_fingerprint, sheet_cases_fingerprint  # noqa: E402
from inspector_session import is_keepalive_running, stop_keepalive  # noqa: E402


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.reader(handle)
                rows = list(reader)
            break
        except UnicodeDecodeError:
            rows = None
    else:
        raise SystemExit(f"Could not decode CSV file: {path}")

    if not rows:
        raise SystemExit(f"CSV file is empty: {path}")
    return rows[0], rows[1:]


def _read_xlsx(path: Path) -> tuple[list[str], list[list[str]]]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise SystemExit(
            "Reading .xlsx requires openpyxl. Install with:\n"
            "  pip install openpyxl"
        ) from exc

    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    rows: list[list[str]] = []
    for row in sheet.iter_rows(values_only=True):
        rows.append(["" if cell is None else str(cell).strip() for cell in row])
    workbook.close()

    if not rows:
        raise SystemExit(f"Excel file is empty: {path}")
    return rows[0], rows[1:]


def _load_sheet(path: Path) -> tuple[list[str], list[list[str]]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path)
    if suffix in {".xlsx", ".xlsm"}:
        return _read_xlsx(path)
    raise SystemExit(f"Unsupported file type: {suffix}. Use .csv or .xlsx")


def _rewrite_csv_with_step_numbers(sheet_path: Path, headers: list[str], rows: list[list[str]]) -> None:
    """Rewrite CSV in-place: add '步骤N:' prefixes to steps and expected."""
    header_map = _map_headers(headers)
    steps_col = header_map.get("steps")
    expected_col = header_map.get("expected")
    if steps_col is None:
        return

    for row in rows:
        if steps_col >= len(row):
            continue
        steps_text = str(row[steps_col] or "")
        try:
            step_lines = _format_step_lines(steps_text)
        except ValueError:
            continue
        row[steps_col] = "\n".join(step_lines)

        if expected_col is None:
            continue
        if expected_col >= len(row):
            row.extend([""] * (expected_col - len(row) + 1))
        expected_lines = _format_expected_lines(str(row[expected_col] or ""))
        numbered_expected: list[str] = []
        for idx in range(len(step_lines)):
            value = expected_lines[idx] if idx < len(expected_lines) else "-"
            numbered_expected.append(f"步骤{idx + 1}预期结果：{value}")
        row[expected_col] = "\n".join(numbered_expected)

    out_path = sheet_path
    try:
        handle = sheet_path.open("w", encoding="utf-8-sig", newline="")
    except PermissionError as exc:
        raise SystemExit(
            f"Cannot overwrite {sheet_path} (file may be open in Excel). "
            "Close the file and retry, or import without --rewrite-sheet."
        ) from exc

    with handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def _write_nl_file(cases_root: Path, nl_text: str, test_name: str, priority: str) -> Path:
    out_path = cases_root / f"{test_name}.nl"
    out_path.write_text(nl_text, encoding="utf-8")
    return out_path


def _generate_from_nl(
    nl_text: str,
    spec_root: Path,
    output_root: Path,
    resolve_locators: bool = True,
    udid: str | None = None,
) -> tuple[Path, Path]:
    spec = parse_natural_language_case(nl_text)
    if resolve_locators:
        resolve_spec_locators(spec, udid=udid)
    validate_spec(spec)

    priority = spec["priority"]
    spec_path = spec_root / priority / f"{spec['test_name']}.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

    output_dir = output_root / priority
    test_path = write_outputs(spec, output_dir)

    return spec_path, test_path


def _restore_inspector_if_paused() -> None:
    if os.environ.get("UIATEST_INSPECTOR_WAS_ACTIVE") != "1":
        return
    if os.getenv("UIATEST_SKIP_INSPECTOR_RESTORE", "").lower() in {"1", "true", "yes"}:
        return
    if os.getenv("APPIUM_SKIP_AUTO_REPAIR", "").lower() in {"1", "true", "yes"}:
        return

    repair_script = SCRIPT_DIR / "repair_appium_session.py"
    if not repair_script.is_file():
        return

    print("Restoring Appium Inspector session after import...")
    subprocess.run(
        [
            sys.executable,
            str(repair_script),
            "--project-root",
            str(PROJECT_ROOT),
            "--for-inspector",
            "--start-keepalive",
        ],
        cwd=str(PROJECT_ROOT),
        check=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import cases from Excel/CSV (Feishu cloud sheet export supported)."
    )
    parser.add_argument(
        "sheet",
        type=Path,
        help="Path to .csv or .xlsx file exported from Excel / 飞书云表格",
    )
    parser.add_argument(
        "--cases-root",
        type=Path,
        default=PROJECT_ROOT / "cases",
        help="Directory to write .nl case files.",
    )
    parser.add_argument("--spec-root", type=Path, default=PROJECT_ROOT / "specs")
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "generated-tests/ui")
    parser.add_argument(
        "--nl-only",
        action="store_true",
        help="Only write .nl files, do not generate specs and pytest scripts.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print results without writing files.",
    )
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument(
        "--no-resolve-locators",
        action="store_true",
        help="Skip adb UI dump to resolve text locators to id.",
    )
    parser.add_argument(
        "--rewrite-sheet",
        action="store_true",
        help="(CSV only) Rewrite sheet in-place: prefix steps/expected with 步骤N: for alignment.",
    )
    parser.add_argument("--udid", help="Device id for locator resolve.")
    args = parser.parse_args()

    sheet_path = args.sheet.resolve()
    if not sheet_path.exists():
        raise SystemExit(f"Sheet file not found: {sheet_path}")

    headers, data_rows = _load_sheet(sheet_path)
    if args.rewrite_sheet and sheet_path.suffix.lower() == ".csv" and not args.dry_run:
        _rewrite_csv_with_step_numbers(sheet_path, headers, data_rows)
    cases = rows_to_nl_cases(data_rows, headers)

    print(f"Loaded {len(cases)} case(s) from {sheet_path.name}")
    print("Required headers: 用例等级、用例名、功能模块、子模块、操作步骤")
    print("Optional headers: 预期结果、标题、套件")
    print()

    imported_priorities: set[str] = set()

    if not args.no_resolve_locators and not args.dry_run and is_keepalive_running(PROJECT_ROOT):
        os.environ["UIATEST_INSPECTOR_WAS_ACTIVE"] = "1"
        stop_keepalive(PROJECT_ROOT)
        print("Paused inspector keepalive for locator resolve during import.")

    for row_number, test_name, nl_text in cases:
        print(f"--- Row {row_number}: {test_name} ---")
        if args.dry_run:
            print(nl_text)
            print()
            continue

        nl_path = _write_nl_file(args.cases_root, nl_text, test_name, "")
        print(f"  NL: {nl_path}")

        if args.nl_only:
            continue

        spec_path, test_path = _generate_from_nl(
            nl_text,
            args.spec_root,
            args.output_root,
            resolve_locators=not args.no_resolve_locators,
            udid=args.udid,
        )
        imported_priorities.add(spec_path.parent.name)
        print(f"  Spec: {spec_path}")
        print(f"  Test: {test_path}")
        print()

    if args.dry_run:
        print("Dry run complete. No files written.")
    else:
        try:
            if not args.nl_only and not args.skip_install:
                installer = SCRIPT_DIR / "install_ui_dependencies.py"
                subprocess.run([sys.executable, str(installer)], check=False)
            print(f"Imported {len(cases)} case(s).")
            if not args.nl_only:
                save_synced_fingerprint(PROJECT_ROOT, sheet_cases_fingerprint(sheet_path), sheet_path)
            for priority in sorted(imported_priorities):
                print(f"  Run {priority}: python uiatest.py run --priority {priority}")
        finally:
            _restore_inspector_if_paused()


if __name__ == "__main__":
    main()
