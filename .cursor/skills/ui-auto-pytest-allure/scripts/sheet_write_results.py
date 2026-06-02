#!/usr/bin/env python3
"""Write pytest PASS/FAIL results back to the import spreadsheet."""

from __future__ import annotations

import csv
import xml.etree.ElementTree as ET
from pathlib import Path

from generate_ui_test import slugify  # noqa: E402
from import_cases_from_sheet import _load_sheet  # noqa: E402
from sheet_case_parser import (  # noqa: E402
    RESULT_COLUMN_DEFAULT,
    _cell,
    _map_headers,
    _normalize_priority,
)


def junit_path_for_run(project_root: Path, run_key: str) -> Path:
    return project_root / ".tools" / f"pytest-{run_key}-junit.xml"


def merge_junit_files(sources: list[Path], destination: Path) -> None:
    """Merge per-case junit XML files into one report for sheet writeback."""
    testcases: list[ET.Element] = []
    total_time = 0.0
    for source in sources:
        if not source.is_file():
            continue
        try:
            root = ET.parse(source).getroot()
        except ET.ParseError:
            continue
        for suite in root.findall("testsuite"):
            try:
                total_time += float(suite.get("time") or 0)
            except ValueError:
                pass
            for testcase in suite.findall("testcase"):
                testcases.append(testcase)

    failures = sum(1 for tc in testcases if tc.find("failure") is not None)
    errors = sum(1 for tc in testcases if tc.find("error") is not None)
    skipped = sum(1 for tc in testcases if tc.find("skipped") is not None)

    suite = ET.Element(
        "testsuite",
        {
            "name": "pytest",
            "tests": str(len(testcases)),
            "failures": str(failures),
            "errors": str(errors),
            "skipped": str(skipped),
            "time": f"{total_time:.3f}",
        },
    )
    for testcase in testcases:
        suite.append(testcase)

    root = ET.Element("testsuites", {"name": "pytest tests"})
    root.append(suite)
    destination.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)


def parse_junit_results(junit_xml: Path) -> dict[str, str]:
    """Map case test_name (without test_ prefix) to PASS or FAIL."""
    if not junit_xml.is_file():
        return {}

    try:
        root = ET.parse(junit_xml).getroot()
    except ET.ParseError:
        return {}

    outcomes: dict[str, str] = {}
    for testcase in root.iter("testcase"):
        name = (testcase.get("name") or "").strip()
        if not name:
            continue
        test_name = name[5:] if name.startswith("test_") else name
        if testcase.find("failure") is not None or testcase.find("error") is not None:
            outcomes[test_name] = "FAIL"
        elif testcase.find("skipped") is not None:
            outcomes[test_name] = "SKIP"
        else:
            outcomes[test_name] = "PASS"
    return outcomes


def _ensure_result_column(headers: list[str], rows: list[list[str]]) -> tuple[list[str], list[list[str]], int]:
    header_map = _map_headers(headers)
    if "result" in header_map:
        result_col = header_map["result"]
        return headers, rows, result_col

    headers = list(headers)
    headers.append(RESULT_COLUMN_DEFAULT)
    result_col = len(headers) - 1
    for row in rows:
        while len(row) < len(headers):
            row.append("")
    return headers, rows, result_col


def _apply_results_to_rows(
    headers: list[str],
    rows: list[list[str]],
    results: dict[str, str],
    *,
    priority_filter: str | None,
    clear_missing: bool,
) -> tuple[list[str], list[list[str]]]:
    headers, rows, result_col = _ensure_result_column(headers, rows)
    header_map = _map_headers(headers)
    priority_col = header_map["priority"]
    test_name_col = header_map["test_name"]
    target_priority = priority_filter.upper() if priority_filter else None

    for row in rows:
        if not any(str(cell or "").strip() for cell in row):
            continue
        if target_priority:
            if _normalize_priority(_cell(row, priority_col)) != target_priority:
                continue
        test_name = slugify(_cell(row, test_name_col))
        if not test_name:
            continue
        while len(row) < len(headers):
            row.append("")
        if test_name in results:
            row[result_col] = results[test_name]
        elif clear_missing:
            row[result_col] = ""

    return headers, rows


def _write_csv(sheet_path: Path, headers: list[str], rows: list[list[str]]) -> None:
    try:
        handle = sheet_path.open("w", encoding="utf-8-sig", newline="")
    except PermissionError as exc:
        raise PermissionError(
            f"Cannot write results to {sheet_path} (file may be open in Excel). Close it and retry."
        ) from exc
    with handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def _write_xlsx(sheet_path: Path, headers: list[str], rows: list[list[str]]) -> None:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise SystemExit(
            "Writing .xlsx requires openpyxl. Install with:\n  pip install openpyxl"
        ) from exc

    try:
        workbook = load_workbook(sheet_path)
    except PermissionError as exc:
        raise PermissionError(
            f"Cannot write results to {sheet_path} (file may be open in Excel). Close it and retry."
        ) from exc

    sheet = workbook.active
    for col_index, header in enumerate(headers, start=1):
        sheet.cell(row=1, column=col_index, value=header)
    for row_index, row in enumerate(rows, start=2):
        for col_index in range(len(headers)):
            value = row[col_index] if col_index < len(row) else ""
            sheet.cell(row=row_index, column=col_index + 1, value=value)
    try:
        workbook.save(sheet_path)
    except PermissionError as exc:
        raise PermissionError(
            f"Cannot save results to {sheet_path} (file may be open in Excel). Close it and retry."
        ) from exc
    finally:
        workbook.close()


def write_results_to_sheet(
    sheet_path: Path,
    results: dict[str, str],
    *,
    priority_filter: str | None = None,
    clear_missing: bool = True,
) -> None:
    """Update the 测试结果 column for rows matching priority_filter."""
    if not results and not clear_missing:
        return

    headers, data_rows = _load_sheet(sheet_path)
    # Work on mutable row copies.
    rows = [list(row) for row in data_rows]
    headers, rows = _apply_results_to_rows(
        headers,
        rows,
        results,
        priority_filter=priority_filter,
        clear_missing=clear_missing,
    )

    suffix = sheet_path.suffix.lower()
    if suffix == ".csv":
        _write_csv(sheet_path, headers, rows)
    elif suffix in {".xlsx", ".xlsm"}:
        _write_xlsx(sheet_path, headers, rows)
    else:
        raise SystemExit(f"Unsupported sheet type for writing results: {sheet_path.suffix}")

    rel = sheet_path.name
    print(f"Wrote test results to {rel} ({len(results)} case(s) updated).")
