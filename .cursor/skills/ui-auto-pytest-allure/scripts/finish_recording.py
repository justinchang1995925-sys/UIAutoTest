#!/usr/bin/env python3
"""Finalize .recording_session.json into spec and pytest files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from generate_ui_test import slugify, validate_spec, write_outputs  # noqa: E402
from record_ui_case import build_capabilities, get_device_id, save_json  # noqa: E402
from recording_preview import LIVE_SPEC_FILE, SESSION_FILE, update_live_preview  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec-root", default="specs")
    parser.add_argument("--output-root", default="generated-tests/ui")
    args = parser.parse_args()

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

    if not spec.get("steps"):
        raise SystemExit("Recording session has no steps.")

    validate_spec(spec)
    priority = str(spec.get("priority", "P2")).upper()
    test_name = slugify(str(spec.get("test_name", "recorded_case")))
    title = str(spec.get("title", test_name.replace("_", " ")))
    spec["story"] = spec.get("story", title)
    spec["test_name"] = test_name
    spec["title"] = title
    spec["priority"] = priority

    udid = get_device_id()
    save_json(Path("capabilities.json"), build_capabilities(udid))

    spec_path = Path(args.spec_root) / priority / f"{test_name}.json"
    save_json(spec_path, spec)
    test_path = write_outputs(spec, Path(args.output_root) / priority)

    update_live_preview({
        "suite": spec["suite"],
        "feature": spec["feature"],
        "title": title,
        "test_name": test_name,
        "priority": priority,
        "description": spec.get("description", ""),
        "timeout": spec.get("timeout", 10),
        "steps": spec["steps"],
    })

    print(f"已生成规格：{spec_path}")
    print(f"已生成脚本：{test_path}")
    print(f"执行：python .cursor/skills/ui-auto-pytest-allure/scripts/run_priority.py {priority}")


if __name__ == "__main__":
    main()
