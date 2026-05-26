#!/usr/bin/env python3
"""Parse natural-language UI case descriptions into JSON specs."""

from __future__ import annotations

import re
from typing import Any

from generate_ui_test import slugify

PRIORITY_RE = re.compile(r"^P([0-4])$", re.IGNORECASE)
META_PATTERNS = {
    "priority": re.compile(r"^(?:等级|优先级)[:：]?\s*(P[0-4])\s*$", re.IGNORECASE),
    "test_name": re.compile(r"^(?:用例名|用例名称|test_name)[:：]\s*(.+)$", re.IGNORECASE),
    "title": re.compile(r"^(?:标题|用例标题|title)[:：]\s*(.+)$", re.IGNORECASE),
    "suite": re.compile(r"^(?:套件|suite)[:：]\s*(.+)$", re.IGNORECASE),
    "feature": re.compile(r"^(?:功能|模块|feature)[:：]\s*(.+)$", re.IGNORECASE),
    "description": re.compile(r"^(?:描述|说明|description)[:：]\s*(.+)$", re.IGNORECASE),
}
STEP_PATTERNS = [
    (
        "loop",
        re.compile(
            r"^(?:步骤\s*)?循环(?:步骤)?\s*(\d+)\s*[-~到]\s*(\d+)(?:\s*[,，]?\s*(\d+)\s*次)?$",
            re.IGNORECASE,
        ),
    ),
    (
        "sleep",
        re.compile(r"^(?:步骤\s*)?等待\s*(\d+(?:\.\d+)?)\s*秒?$", re.IGNORECASE),
    ),
    (
        "input",
        re.compile(
            r"^步骤\s*(\d+)[:：]\s*(?:输入|填写)\s*(.+?)[，,]\s*(.+)$",
            re.IGNORECASE,
        ),
    ),
    (
        "input",
        re.compile(
            r"^步骤\s*(\d+)[:：]\s*(?:输入|填写)\s*[「\"'](.+?)[」\"']\s*(.+)$",
            re.IGNORECASE,
        ),
    ),
    (
        "assert_text",
        re.compile(
            r"^步骤\s*(\d+)[:：]\s*断言文字\s*(.+?)[，,]\s*(.+)$",
            re.IGNORECASE,
        ),
    ),
    (
        "assert_visible",
        re.compile(
            r"^步骤\s*(\d+)[:：]\s*断言\s*(.+?)(?:可见|出现|存在)?$",
            re.IGNORECASE,
        ),
    ),
    (
        "set_switch",
        re.compile(
            r"^步骤\s*(\d+)[:：]\s*设置开关\s+(.+?)\s+(打开|开启|关闭|开|关|on|off)\s*$",
            re.IGNORECASE,
        ),
    ),
    (
        "set_switch",
        re.compile(
            r"^步骤\s*(\d+)[:：]\s*(打开|关闭)开关\s+(.+?)\s*$",
            re.IGNORECASE,
        ),
    ),
    (
        "tap",
        re.compile(r"^步骤\s*(\d+)[:：]\s*(?:点击|点按|切换)\s+(.+)$", re.IGNORECASE),
    ),
    (
        "tap",
        re.compile(r"^(\d+)[.、]\s*(?:点击|点按|打开|关闭)\s+(.+)$", re.IGNORECASE),
    ),
]


def normalize_switch_state(value: str) -> str:
    text = value.strip().lower()
    if text in {"on", "open", "true", "1", "打开", "开启", "开"}:
        return "on"
    if text in {"off", "close", "false", "0", "关闭", "关"}:
        return "off"
    raise ValueError(f"Unsupported switch state: {value!r}. Use 打开 or 关闭.")


def escape_uiautomator_text(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'new UiSelector().text("{escaped}")'


def parse_locator(target: str) -> dict[str, Any]:
    text = target.strip()
    patterns = [
        ("id", re.compile(r"^(?:id|resource-id|资源id)[:：]\s*(.+)$", re.IGNORECASE)),
        ("accessibility_id", re.compile(r"^(?:accessibility|content-desc|无障碍)[:：]\s*(.+)$", re.IGNORECASE)),
        ("xpath", re.compile(r"^xpath[:：]\s*(.+)$", re.IGNORECASE)),
        ("android_uiautomator", re.compile(r"^uiautomator[:：]\s*(.+)$", re.IGNORECASE)),
        (
            "coordinates",
            re.compile(
                r"^(?:坐标|coordinate)[:：]?\s*x\s*[=:]\s*(\d+)\s*[,，]?\s*y\s*[=:]\s*(\d+)$",
                re.IGNORECASE,
            ),
        ),
        ("id", re.compile(r"^(?:元素\s*)?id\s*(?:是|为)?\s*([\w.:]+)$", re.IGNORECASE)),
    ]
    for key, pattern in patterns:
        match = pattern.match(text)
        if not match:
            continue
        if key == "coordinates":
            return {"coordinates": {"x": int(match.group(1)), "y": int(match.group(2))}}
        return {key: match.group(1).strip()}

    stripped = text.strip("「」\"' ")
    if stripped:
        return {"android_uiautomator": escape_uiautomator_text(stripped)}
    raise ValueError(f"Cannot build locator from target: {target!r}")


def parse_step_line(line: str) -> dict[str, Any] | None:
    raw = line.strip()
    if not raw or raw.startswith("#"):
        return None

    for action, pattern in STEP_PATTERNS:
        match = pattern.match(raw)
        if not match:
            continue

        if action == "loop":
            return {
                "name": f"Loop steps {match.group(1)}-{match.group(2)}",
                "action": "loop",
                "from_step": int(match.group(1)),
                "to_step": int(match.group(2)),
                "times": int(match.group(3) or "1"),
            }

        if action == "sleep":
            seconds = float(match.group(1))
            return {"name": f"Sleep {seconds}s", "action": "sleep", "seconds": seconds}

        step_number = match.group(1)
        if action == "input":
            field, value = match.group(2), match.group(3)
            return {
                "name": f"Step {step_number} input {field}",
                "action": "input",
                "locator": parse_locator(field),
                "value": value.strip(),
            }

        if action == "assert_text":
            target, expected = match.group(2), match.group(3)
            return {
                "name": f"Step {step_number} assert text {target}",
                "action": "assert_text",
                "locator": parse_locator(target),
                "value": expected.strip(),
            }

        if action == "set_switch":
            first, second = match.group(2), match.group(3)
            try:
                state = normalize_switch_state(first)
                target = second
            except ValueError:
                state = normalize_switch_state(second)
                target = first
            state_label = "打开" if state == "on" else "关闭"
            return {
                "name": f"Step {step_number} set switch {target} {state_label}",
                "action": "set_switch",
                "locator": parse_locator(target),
                "state": state,
            }

        target = match.group(2) if action != "sleep" else ""
        if action == "assert_visible":
            return {
                "name": f"Step {step_number} assert visible {target}",
                "action": "assert_visible",
                "locator": parse_locator(target),
            }

        return {
            "name": f"Step {step_number} Tap {target}",
            "action": "tap",
            "locator": parse_locator(target),
        }

    return None


def parse_natural_language_case(text: str) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Case description is empty.")

    meta: dict[str, Any] = {
        "priority": "P2",
        "suite": "UI Automation",
        "feature": "Generated UI Case",
        "title": "",
        "test_name": "",
        "description": "",
    }
    steps: list[dict[str, Any]] = []

    for line in lines:
        priority_match = PRIORITY_RE.match(line)
        if priority_match:
            meta["priority"] = f"P{priority_match.group(1)}"
            continue

        matched_meta = False
        for key, pattern in META_PATTERNS.items():
            match = pattern.match(line)
            if match:
                meta[key] = match.group(1).strip()
                matched_meta = True
                break
        if matched_meta:
            continue

        if line.startswith("P") and len(line) == 2 and line[1].isdigit():
            meta["priority"] = line.upper()
            continue

        step = parse_step_line(line)
        if step:
            steps.append(step)
            continue

        if not meta["title"]:
            meta["title"] = line
        elif not meta["description"]:
            meta["description"] = line

    if not steps:
        raise ValueError("No steps found. Use lines like: 步骤1: 点击 密码与安全")

    if not meta["test_name"]:
        meta["test_name"] = slugify(meta["title"] or "generated_ui_case")
    if not meta["title"]:
        meta["title"] = meta["test_name"].replace("_", " ")

    return {
        "suite": meta["suite"],
        "feature": meta["feature"],
        "story": meta["title"],
        "test_name": slugify(meta["test_name"]),
        "title": meta["title"],
        "priority": meta["priority"].upper(),
        "description": meta.get("description") or f"Generated from natural language: {meta['title']}",
        "steps": steps,
    }
