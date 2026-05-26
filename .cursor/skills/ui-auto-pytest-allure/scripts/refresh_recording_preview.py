#!/usr/bin/env python3
"""Refresh live preview files after manual edits to recording/live_spec.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from recording_preview import LIVE_SPEC_FILE, SESSION_FILE, update_live_preview, print_live_preview  # noqa: E402


def main() -> None:
    if LIVE_SPEC_FILE.exists():
        spec = json.loads(LIVE_SPEC_FILE.read_text(encoding="utf-8"))
    elif SESSION_FILE.exists():
        session = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        spec = {
            "suite": session.get("suite", "UI Automation"),
            "feature": session.get("feature", "Recorded UI Case"),
            "story": session.get("title", "Recorded case"),
            "test_name": session.get("test_name", "recorded_case"),
            "title": session.get("title", "Recorded case"),
            "priority": session.get("priority", "P2"),
            "description": session.get("description", ""),
            "timeout": session.get("timeout", 10),
            "steps": session.get("steps", []),
        }
    else:
        raise SystemExit("No recording session found. Record at least one step first.")
    session = {
        "suite": spec.get("suite", "UI Automation"),
        "feature": spec.get("feature", "Recorded UI Case"),
        "title": spec.get("title", spec.get("story", "Recorded case")),
        "test_name": spec.get("test_name", "recorded_case"),
        "priority": spec.get("priority", "P2"),
        "description": spec.get("description", ""),
        "timeout": spec.get("timeout", 10),
        "steps": spec.get("steps", []),
    }
    update_live_preview(session)
    print_live_preview(session)


if __name__ == "__main__":
    main()
