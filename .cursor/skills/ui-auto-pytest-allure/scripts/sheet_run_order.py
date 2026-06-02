#!/usr/bin/env python3
"""Resolve pytest test file order from import sheet row order."""

from __future__ import annotations

from pathlib import Path

from generate_ui_test import slugify  # noqa: E402
from import_cases_from_sheet import _load_sheet  # noqa: E402
from sheet_case_parser import _cell, _map_headers, _normalize_priority  # noqa: E402


def ordered_test_paths_for_priority(
    sheet_path: Path,
    test_root: Path,
    priority: str,
) -> list[Path]:
    """Return generated test file paths in spreadsheet row order for the given priority."""
    headers, data_rows = _load_sheet(sheet_path)
    header_map = _map_headers(headers)
    priority_col = header_map["priority"]
    test_name_col = header_map["test_name"]

    ordered: list[Path] = []
    seen: set[Path] = set()
    target = priority.upper()

    for row in data_rows:
        if not any(str(cell or "").strip() for cell in row):
            continue
        row_priority = _normalize_priority(_cell(row, priority_col))
        if row_priority != target:
            continue
        test_name = slugify(_cell(row, test_name_col))
        if not test_name:
            continue
        test_path = test_root / target / f"test_{test_name}.py"
        if not test_path.is_file():
            print(
                f"Warning: sheet case '{test_name}' has no generated test: "
                f"{test_path.relative_to(test_root.parent.parent)}"
            )
            continue
        if test_path in seen:
            continue
        seen.add(test_path)
        ordered.append(test_path.resolve())

    return ordered
