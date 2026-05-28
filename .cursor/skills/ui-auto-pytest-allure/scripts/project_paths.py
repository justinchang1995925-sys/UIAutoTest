#!/usr/bin/env python3
"""Resolve UIAutoTest project root from any script path."""

from __future__ import annotations

from pathlib import Path


def resolve_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "generated-tests").is_dir() and (candidate / "cases").is_dir():
            return candidate
        if (candidate / "capabilities.local.json").is_file():
            return candidate
        if (candidate / "capabilities.json").is_file():
            return candidate
        if (candidate / "capabilities.template.json").is_file():
            return candidate
    raise RuntimeError(
        f"Could not resolve project root from {current}. "
        "Run commands from the UIAutoTest repository root."
    )
