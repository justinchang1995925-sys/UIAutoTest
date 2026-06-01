#!/usr/bin/env python3
"""Resolve UIAutoTest project root from any script path."""

from __future__ import annotations

from pathlib import Path


def _has_skill(candidate: Path) -> bool:
    return (candidate / ".cursor" / "skills" / "ui-auto-pytest-allure" / "SKILL.md").is_file()


def resolve_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "generated-tests").is_dir() and (candidate / "cases").is_dir():
            return candidate
        if (candidate / "uiatest.py").is_file() and _has_skill(candidate):
            return candidate
        if (candidate / "capabilities.local.json").is_file():
            return candidate
        if (candidate / "capabilities.json").is_file():
            return candidate
        if (candidate / "capabilities.template.json").is_file():
            return candidate
        if _has_skill(candidate):
            return candidate
    raise RuntimeError(
        f"Could not resolve project root from {current}. "
        "Run from project root, or run: "
        "python .cursor/skills/ui-auto-pytest-allure/scripts/uiatest_init.py"
    )
