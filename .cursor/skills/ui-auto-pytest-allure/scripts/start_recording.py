#!/usr/bin/env python3
"""Initialize a new UI recording session with live preview files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from generate_ui_test import slugify  # noqa: E402
from recording_preview import SESSION_FILE, update_live_preview, print_live_preview  # noqa: E402

PRIORITIES = {"P0", "P1", "P2", "P3", "P4"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-name", default="recorded_case")
    parser.add_argument("--title")
    parser.add_argument("--priority", default="P2", choices=sorted(PRIORITIES))
    parser.add_argument("--suite", default="UI Automation")
    parser.add_argument("--feature", default="Recorded UI Case")
    args = parser.parse_args()

    test_name = slugify(args.test_name)
    title = args.title or test_name.replace("_", " ")
    session = {
        "steps": [],
        "priority": args.priority.upper(),
        "test_name": test_name,
        "title": title,
        "suite": args.suite,
        "feature": args.feature,
        "description": f"Recorded UI case: {title}",
    }
    SESSION_FILE.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    update_live_preview(session)
    print_live_preview(session)
    print("开始录制：在设备点击控件后回复「步骤1完成」，或运行 record_step_done.py 步骤1")


if __name__ == "__main__":
    main()
