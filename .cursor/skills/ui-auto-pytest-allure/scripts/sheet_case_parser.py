#!/usr/bin/env python3
"""Parse spreadsheet rows into natural-language UI case text."""

from __future__ import annotations

import re
from typing import Any

from generate_ui_test import slugify

# Canonical headers and aliases (Feishu / Excel may vary slightly).
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "priority": ("用例等级", "等级", "优先级", "priority", "用例级别"),
    "test_name": ("用例名", "用例名称", "test_name", "case_name"),
    "feature": ("功能模块", "功能", "feature", "模块功能"),
    "module": ("子模块", "模块", "module", "子功能"),
    "steps": ("操作步骤", "步骤", "steps", "用例步骤", "操作"),
    "title": ("标题", "用例标题", "title"),
    "suite": ("套件", "suite"),
}

STEP_LINE_RE = re.compile(r"^步骤\s*(\d+)\s*[:：]\s*(.+)$", re.IGNORECASE)
PRIORITY_RE = re.compile(r"^P?([0-4])$", re.IGNORECASE)


def _normalize_header(value: str) -> str:
    return str(value or "").strip().replace("\ufeff", "")


def _map_headers(headers: list[str]) -> dict[str, int]:
    normalized = {_normalize_header(header): index for index, header in enumerate(headers)}
    mapping: dict[str, int] = {}

    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            key = _normalize_header(alias)
            if key in normalized:
                mapping[field] = normalized[key]
                break

    required = ("priority", "test_name", "feature", "module", "steps")
    missing = [field for field in required if field not in mapping]
    if missing:
        readable = {
            "priority": "用例等级",
            "test_name": "用例名",
            "feature": "功能模块",
            "module": "子模块",
            "steps": "操作步骤",
        }
        labels = "、".join(readable[field] for field in missing)
        found = "、".join(headers) if headers else "(empty)"
        raise ValueError(
            f"Missing required column(s): {labels}. Found headers: {found}"
        )
    return mapping


def _cell(row: list[Any], index: int) -> str:
    if index >= len(row):
        return ""
    value = row[index]
    if value is None:
        return ""
    return str(value).strip()


def _normalize_priority(value: str) -> str:
    text = value.strip().upper()
    if not text:
        return "P2"
    match = PRIORITY_RE.match(text)
    if match:
        return f"P{match.group(1)}"
    if text.startswith("P") and len(text) == 2 and text[1].isdigit():
        return text
    raise ValueError(f"Invalid priority: {value!r}. Use P0 to P4.")


def _format_step_lines(steps_text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in steps_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = STEP_LINE_RE.match(line)
        if match:
            lines.append(f"步骤{match.group(1)}: {match.group(2).strip()}")
        else:
            lines.append(line)

    if not lines:
        raise ValueError("操作步骤 is empty.")

    numbered: list[str] = []
    auto_index = 1
    for line in lines:
        if STEP_LINE_RE.match(line):
            numbered.append(line)
            auto_index = int(STEP_LINE_RE.match(line).group(1)) + 1
        else:
            numbered.append(f"步骤{auto_index}: {line}")
            auto_index += 1
    return numbered


def row_to_nl_text(row: list[Any], header_map: dict[str, int], row_number: int) -> str:
    test_name = _cell(row, header_map["test_name"])
    if not test_name:
        raise ValueError(f"Row {row_number}: 用例名 is required.")

    priority = _normalize_priority(_cell(row, header_map["priority"]))
    feature = _cell(row, header_map["feature"])
    module = _cell(row, header_map["module"])
    steps_text = _cell(row, header_map["steps"])

    title = ""
    if "title" in header_map:
        title = _cell(row, header_map["title"])
    if not title:
        parts = [part for part in (feature, module, test_name) if part]
        title = "-".join(parts)

    suite = "UI Automation"
    if "suite" in header_map:
        suite = _cell(row, header_map["suite"]) or suite

    step_lines = _format_step_lines(steps_text)
    lines = [
        priority,
        f"用例名: {slugify(test_name)}",
        f"标题: {title}",
        f"功能: {feature}" if feature else "",
        f"模块: {module}" if module else "",
        "",
        *step_lines,
        "",
    ]
    return "\n".join(line for line in lines if line is not None)


def rows_to_nl_cases(rows: list[list[Any]], headers: list[str]) -> list[tuple[int, str, str]]:
    """Return list of (row_number, test_name, nl_text)."""
    header_map = _map_headers(headers)
    cases: list[tuple[int, str, str]] = []

    for index, row in enumerate(rows, start=2):
        if not any(str(cell or "").strip() for cell in row):
            continue
        try:
            nl_text = row_to_nl_text(row, header_map, index)
            test_name_match = re.search(r"^用例名:\s*(.+)$", nl_text, re.MULTILINE)
            test_name = test_name_match.group(1).strip() if test_name_match else f"row_{index}"
            cases.append((index, test_name, nl_text))
        except ValueError as exc:
            raise ValueError(f"Row {index}: {exc}") from exc

    if not cases:
        raise ValueError("No data rows found below the header row.")
    return cases
