#!/usr/bin/env python3
"""Record one UI step from a device tap and append it to .recording_session.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from record_ui_case import get_device_id, record_single_step  # noqa: E402
from recording_preview import update_live_preview, print_live_preview  # noqa: E402

SESSION_FILE = Path(".recording_session.json")


def load_session() -> dict:
    if SESSION_FILE.exists():
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    return {
        "steps": [],
        "priority": "P2",
        "test_name": "recorded_case",
        "title": "Recorded case",
        "suite": "UI Automation",
        "feature": "Recorded UI Case",
    }


def save_session(session: dict) -> None:
    SESSION_FILE.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help='Step name, e.g. "步骤1".')
    parser.add_argument("--action", default="tap", help="tap, input, assert_visible")
    parser.add_argument("--value", help="Input text when action is input.")
    parser.add_argument("--udid", help="Android device id.")
    parser.add_argument("--tap-timeout", type=int, default=60)
    args = parser.parse_args()

    udid = args.udid or get_device_id()
    step = record_single_step(udid, args.name, action=args.action, value=args.value, tap_timeout=args.tap_timeout)

    session = load_session()
    session["steps"].append(step)
    save_session(session)
    update_live_preview(session, latest_step=step)
    print_live_preview(session, latest_step=step)
    print("继续录制：设备点击后回复「步骤N完成」，或运行 record_step_done.py")
    print("完成录制：python .cursor/skills/ui-auto-pytest-allure/scripts/finish_recording.py")


if __name__ == "__main__":
    main()
