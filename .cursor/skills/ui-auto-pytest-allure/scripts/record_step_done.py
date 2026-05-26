#!/usr/bin/env python3
"""Record a step after the user has tapped a control on the Android device."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from record_ui_case import (  # noqa: E402
    dump_ui_xml,
    find_node_at,
    get_device_id,
    locator_from_node,
    parse_bounds,
    node_area,
)
from recording_preview import update_live_preview, print_live_preview  # noqa: E402

SESSION_FILE = Path(".recording_session.json")


GENERIC_IDS = {
    "android:id/content",
    "android:id/decor_content",
    "android:id/statusBarBackground",
    "android:id/navigationBarBackground",
}


def find_focused_node(root: ET.Element) -> ET.Element | None:
    candidates: list[ET.Element] = []
    for node in root.iter("node"):
        if (
            node.attrib.get("focused") != "true"
            and node.attrib.get("selected") != "true"
            and node.attrib.get("checked") != "true"
        ):
            continue
        resource_id = node.attrib.get("resource-id", "")
        if resource_id in GENERIC_IDS:
            continue
        if node.attrib.get("clickable") != "true" and not resource_id and not node.attrib.get("text"):
            continue
        candidates.append(node)
    if not candidates:
        return None
    return sorted(candidates, key=node_area)[0]


def find_node_by_text(root: ET.Element, text: str) -> ET.Element | None:
    matches: list[ET.Element] = []
    for node in root.iter("node"):
        node_text = node.attrib.get("text", "") or node.attrib.get("content-desc", "")
        if text not in node_text:
            continue
        if node.attrib.get("clickable") == "true" or node.attrib.get("resource-id"):
            matches.append(node)
    if not matches:
        return None
    return sorted(matches, key=node_area)[0]


def list_clickable_candidates(root: ET.Element, limit: int = 12) -> list[dict[str, str]]:
    candidates: list[tuple[int, dict[str, str]]] = []
    for node in root.iter("node"):
        if node.attrib.get("clickable") != "true":
            continue
        resource_id = node.attrib.get("resource-id", "")
        text = node.attrib.get("text", "") or node.attrib.get("content-desc", "")
        if not text and not resource_id:
            continue
        if resource_id in GENERIC_IDS:
            continue
        candidates.append((
            node_area(node),
            {
                "text": text,
                "resource-id": resource_id,
                "bounds": node.attrib.get("bounds", ""),
            },
        ))
    candidates.sort(key=lambda item: item[0])
    return [item[1] for item in candidates[:limit]]


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
    parser.add_argument("--action", default="tap")
    parser.add_argument("--value")
    parser.add_argument("--x", type=int, help="Optional tap x when focus detection fails.")
    parser.add_argument("--y", type=int, help="Optional tap y when focus detection fails.")
    parser.add_argument("--match-text", help="Match control by visible text or content-desc.")
    parser.add_argument("--udid")
    args = parser.parse_args()

    udid = args.udid or get_device_id()
    root = dump_ui_xml(udid)
    node = find_focused_node(root)

    if node is None and args.match_text:
        node = find_node_by_text(root, args.match_text)
    if node is None and args.x is not None and args.y is not None:
        node = find_node_at(root, args.x, args.y)
    elif node is None:
        candidates = list_clickable_candidates(root)
        candidates_path = Path("recording/clickable_candidates.json")
        candidates_path.parent.mkdir(parents=True, exist_ok=True)
        candidates_path.write_text(
            json.dumps(candidates, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("未找到 focused/selected 控件。可选控件已写入 recording/clickable_candidates.json：")
        for index, item in enumerate(candidates, start=1):
            print(f"{index}. text={item['text']!r} id={item['resource-id']!r} bounds={item['bounds']}")
        raise SystemExit(
            "请重新点击目标控件后立即回复「步骤1完成」，"
            "或回复「步骤1完成 控件文字」例如：步骤1完成 密码与安全"
        )

    bounds = parse_bounds(node.attrib.get("bounds", ""))
    if bounds:
        x = (bounds[0] + bounds[2]) // 2
        y = (bounds[1] + bounds[3]) // 2
    else:
        x = args.x or 0
        y = args.y or 0

    step = {
        "name": args.name,
        "action": "tap" if args.action == "click" else args.action,
        "locator": locator_from_node(node, x, y),
    }
    if args.action in {"input", "set_text"} and args.value:
        step["value"] = args.value

    session = load_session()
    replaced = False
    for index, existing in enumerate(session["steps"]):
        if existing.get("name") == args.name:
            session["steps"][index] = step
            replaced = True
            break
    if not replaced:
        session["steps"].append(step)
    save_session(session)
    update_live_preview(session, latest_step=step)
    print_live_preview(session, latest_step=step)


if __name__ == "__main__":
    main()
