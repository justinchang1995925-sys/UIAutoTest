#!/usr/bin/env python3
"""Generate and refresh live recording preview files for user review and edits."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from generate_ui_test import build_test_file, slugify, validate_spec

PREVIEW_DIR = Path("recording")
SESSION_FILE = Path(".recording_session.json")
LIVE_SPEC_FILE = PREVIEW_DIR / "live_spec.json"
LIVE_TEST_FILE = PREVIEW_DIR / "live_test.py"
LIVE_README_FILE = PREVIEW_DIR / "README.md"


def session_to_spec(session: dict[str, Any]) -> dict[str, Any]:
    test_name = slugify(str(session.get("test_name", "recorded_case")))
    title = str(session.get("title", test_name.replace("_", " ")))
    return {
        "suite": session.get("suite", "UI Automation"),
        "feature": session.get("feature", "Recorded UI Case"),
        "story": title,
        "test_name": test_name,
        "title": title,
        "priority": str(session.get("priority", "P2")).upper(),
        "description": session.get("description", f"Recorded UI case: {title}"),
        "timeout": session.get("timeout", 10),
        "steps": session.get("steps", []),
    }


def step_code_snippet(step: dict[str, Any], index: int) -> str:
    action = step.get("action", "tap")
    name = step.get("name", f"step_{index}")
    locator = step.get("locator", {})
    locator_key, locator_value = next(iter(locator.items())) if locator else ("", "")

    if action in {"tap", "click"}:
        if locator_key == "coordinates":
            point = locator_value
            return f'# Step {index}: {name}\n_wait_for_element / tap at ({point["x"]}, {point["y"]})'
        return f'# Step {index}: {name}\ndriver.find_element(..., "{locator_value}").click()  # {locator_key}'
    if action in {"input", "set_text"}:
        value = step.get("value", "")
        return (
            f'# Step {index}: {name}\n'
            f'element = driver.find_element(..., "{locator_value}")  # {locator_key}\n'
            f'element.clear(); element.send_keys("{value}")'
        )
    if action == "assert_visible":
        return f'# Step {index}: {name}\nassert visible: {locator_key} = {locator_value!r}'
    if action == "sleep":
        return f'# Step {index}: sleep {step.get("seconds", 1)}s'
    if action == "loop":
        return (
            f'# Step {index}: loop steps {step.get("from_step")}-{step.get("to_step")} '
            f'x {step.get("times", 1)}'
        )
    return f"# Step {index}: {json.dumps(step, ensure_ascii=False)}"


def build_readme(session: dict[str, Any], spec: dict[str, Any]) -> str:
    lines = [
        "# 录制预览（实时更新）",
        "",
        f"- 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 用例名称: `{spec['test_name']}`",
        f"- 用例等级: `{spec['priority']}`",
        f"- 已录制步骤: {len(spec['steps'])}",
        "",
        "## 文件说明",
        "",
        "- `live_spec.json`：步骤与定位器（推荐手动修改这个文件）",
        "- `live_test.py`：根据 spec 自动生成的 pytest 脚本预览",
        "",
        "## 修改方式",
        "",
        "1. 直接编辑 `live_spec.json` 中的 `steps`，然后运行：",
        "   `python .cursor/skills/ui-auto-pytest-allure/scripts/refresh_recording_preview.py`",
        "2. 或在对话里告诉 Agent：例如「把步骤2的 locator 改成 id=xxx」",
        "",
        "## 当前步骤一览",
        "",
    ]
    for index, step in enumerate(spec["steps"], start=1):
        lines.append(f"### 步骤 {index}: {step.get('name', step.get('action'))}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(step, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
        lines.append("```python")
        lines.append(step_code_snippet(step, index))
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def update_live_preview(session: dict[str, Any], latest_step: dict[str, Any] | None = None) -> tuple[Path, Path]:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    spec = session_to_spec(session)

    if spec["steps"]:
        validate_spec(spec)

    LIVE_SPEC_FILE.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    SESSION_FILE.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")

    if spec["steps"]:
        LIVE_TEST_FILE.write_text(build_test_file(spec), encoding="utf-8")
    elif LIVE_TEST_FILE.exists():
        LIVE_TEST_FILE.unlink()

    LIVE_README_FILE.write_text(build_readme(session, spec), encoding="utf-8")
    return LIVE_SPEC_FILE, LIVE_TEST_FILE


def print_live_preview(session: dict[str, Any], latest_step: dict[str, Any] | None = None) -> None:
    spec = session_to_spec(session)
    step_count = len(spec["steps"])

    print("\n" + "=" * 60)
    print("实时代码预览已更新")
    print("=" * 60)
    print(f"用例: {spec['test_name']}  |  等级: {spec['priority']}  |  步骤数: {step_count}")
    print(f"规格文件: {LIVE_SPEC_FILE}")
    print(f"脚本预览: {LIVE_TEST_FILE}")
    print(f"说明文档: {LIVE_README_FILE}")

    if latest_step is not None:
        print("\n--- 本步已记录 ---")
        print(json.dumps(latest_step, ensure_ascii=False, indent=2))
        print("\n--- 本步代码片段 ---")
        print(step_code_snippet(latest_step, step_count))

    if LIVE_TEST_FILE.exists():
        print("\n--- 当前完整脚本预览 ---")
        print(LIVE_TEST_FILE.read_text(encoding="utf-8"))
    print("=" * 60 + "\n")
