#!/usr/bin/env python3
"""Record Android UI actions from real device taps and generate pytest cases."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from generate_ui_test import slugify, validate_spec, write_outputs  # noqa: E402
from recording_preview import update_live_preview, print_live_preview  # noqa: E402


PRIORITIES = {"P0", "P1", "P2", "P3", "P4"}


ADB_ENCODING = "utf-8"


def run_adb(args: list[str], udid: str | None = None, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    command = ["adb"]
    if udid:
        command.extend(["-s", udid])
    command.extend(args)
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        encoding=ADB_ENCODING,
        errors="replace",
    )


def require_adb() -> None:
    result = subprocess.run(
        ["adb", "version"],
        text=True,
        capture_output=True,
        check=False,
        encoding=ADB_ENCODING,
        errors="replace",
    )
    if result.returncode != 0:
        raise SystemExit("adb is not available. Install Android Platform Tools and add adb to PATH.")


def get_device_id() -> str:
    result = run_adb(["devices"])
    for line in result.stdout.splitlines()[1:]:
        match = re.match(r"^(\S+)\s+device$", line.strip())
        if match:
            return match.group(1)
    raise SystemExit("No Android device is connected. Enable USB debugging and run again.")


def get_foreground_app(udid: str) -> tuple[str, str] | None:
    result = run_adb(["shell", "dumpsys", "window"], udid=udid, timeout=15)
    lines = result.stdout.splitlines()
    focus_lines = [
        line
        for line in lines
        if "mCurrentFocus" in line and re.search(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+/[A-Za-z0-9_.$]+", line)
    ]
    if not focus_lines:
        focus_lines = [
            line
            for line in lines
            if "mFocusedApp" in line and re.search(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+/[A-Za-z0-9_.$]+", line)
        ]
    if not focus_lines:
        return None

    match = re.search(r"([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)/([A-Za-z0-9_.$]+)", focus_lines[-1])
    if not match:
        return None

    package_name = match.group(1)
    activity_name = match.group(2)
    if activity_name.startswith("."):
        activity_name = f"{package_name}{activity_name}"
    return package_name, activity_name


def dump_ui_xml(udid: str) -> ET.Element:
    remote_path = "/sdcard/window_dump.xml"
    dump_result = run_adb(["shell", "uiautomator", "dump", remote_path], udid=udid, timeout=20)
    if dump_result.returncode != 0:
        raise RuntimeError(f"Could not dump UI XML: {dump_result.stderr or dump_result.stdout}")

    cat_result = run_adb(["shell", "cat", remote_path], udid=udid, timeout=20)
    if cat_result.returncode != 0 or not cat_result.stdout.strip():
        raise RuntimeError(f"Could not read UI XML: {cat_result.stderr or cat_result.stdout}")

    xml_text = cat_result.stdout.strip()
    return ET.fromstring(xml_text)


def parse_bounds(bounds: str) -> tuple[int, int, int, int] | None:
    match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds or "")
    if not match:
        return None
    return tuple(int(group) for group in match.groups())


def node_contains(node: ET.Element, x: int, y: int) -> bool:
    bounds = parse_bounds(node.attrib.get("bounds", ""))
    if not bounds:
        return False
    left, top, right, bottom = bounds
    return left <= x <= right and top <= y <= bottom


def node_area(node: ET.Element) -> int:
    bounds = parse_bounds(node.attrib.get("bounds", ""))
    if not bounds:
        return 10**12
    left, top, right, bottom = bounds
    return max(0, right - left) * max(0, bottom - top)


def find_node_at(root: ET.Element, x: int, y: int) -> ET.Element | None:
    matches = [node for node in root.iter("node") if node_contains(node, x, y)]
    if not matches:
        return None
    return sorted(matches, key=node_area)[0]


def android_uiautomator_text(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'new UiSelector().text("{escaped}")'


def build_xpath(node: ET.Element) -> str:
    class_name = node.attrib.get("class", "*")
    text = node.attrib.get("text", "")
    content_desc = node.attrib.get("content-desc", "")
    if text:
        return f'//*[@class="{class_name}" and @text="{text}"]'
    if content_desc:
        return f'//*[@class="{class_name}" and @content-desc="{content_desc}"]'
    return f'//*[@class="{class_name}"]'


def locator_from_node(node: ET.Element | None, x: int, y: int) -> dict[str, Any]:
    if node is None:
        return {"coordinates": {"x": x, "y": y}}

    resource_id = node.attrib.get("resource-id", "")
    content_desc = node.attrib.get("content-desc", "")
    text = node.attrib.get("text", "")
    class_name = node.attrib.get("class", "")

    if resource_id:
        return {"id": resource_id}
    if content_desc:
        return {"accessibility_id": content_desc}
    if text:
        return {"android_uiautomator": android_uiautomator_text(text)}
    if class_name:
        return {"xpath": build_xpath(node)}
    return {"coordinates": {"x": x, "y": y}}


def _parse_event_coord(token: str) -> int:
    token = token.strip()
    try:
        return int(token, 16)
    except ValueError:
        return int(token)


def _read_stdout_line(process: subprocess.Popen[bytes], timeout: float) -> str | None:
    if process.stdout is None:
        return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(process.stdout.readline)
        try:
            raw_line = future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return None
    if not raw_line:
        return None
    return raw_line.decode(ADB_ENCODING, errors="replace")


def _parse_getevent_output(output: str) -> tuple[int, int] | None:
    last_x: int | None = None
    last_y: int | None = None
    last_pair: tuple[int, int] | None = None

    for line in output.splitlines():
        if any(key in line for key in ("ABS_MT_POSITION_X", "ABS_X", "0035")):
            last_x = _parse_event_coord(line.strip().split()[-1])
        elif any(key in line for key in ("ABS_MT_POSITION_Y", "ABS_Y", "0036")):
            last_y = _parse_event_coord(line.strip().split()[-1])
        elif "SYN_REPORT" in line and last_x is not None and last_y is not None:
            last_pair = (last_x, last_y)
        elif "BTN_TOUCH" in line and "DOWN" in line and last_x is not None and last_y is not None:
            last_pair = (last_x, last_y)

    return last_pair


def wait_for_tap(udid: str, timeout: int = 60) -> tuple[int, int]:
    print("请在 Android 设备界面点击目标控件...")
    started_at = time.time()
    capture_window = min(8, max(3, timeout // 4))

    while time.time() - started_at < timeout:
        remaining = timeout - (time.time() - started_at)
        try:
            result = subprocess.run(
                ["adb", "-s", udid, "shell", "getevent", "-lt"],
                capture_output=True,
                timeout=min(capture_window, remaining),
                encoding=ADB_ENCODING,
                errors="replace",
                check=False,
            )
        except subprocess.TimeoutExpired:
            result = None

        if result and result.stdout:
            pair = _parse_getevent_output(result.stdout)
            if pair:
                return pair

        print("未检测到点击，请再次点击目标控件...")

    raise TimeoutError("Timed out waiting for a device tap.")


def record_single_step(udid: str, name: str, action: str = "tap", value: str | None = None, tap_timeout: int = 60) -> dict[str, Any]:
    ui_root = dump_ui_xml(udid)
    x, y = wait_for_tap(udid, timeout=tap_timeout)
    node = find_node_at(ui_root, x, y)
    step: dict[str, Any] = {
        "name": name,
        "action": "tap" if action == "click" else action,
        "locator": locator_from_node(node, x, y),
    }
    if action in {"input", "set_text"} and value is not None:
        step["value"] = value
    return step


def prompt_required(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    if value:
        return value
    if default:
        return default
    return prompt_required(label, default)


def parse_step_command(raw: str) -> tuple[str, str, str | None]:
    parts = [part.strip() for part in raw.split("|")]
    left = parts[0]
    value = parts[1] if len(parts) > 1 else None
    tokens = left.split(maxsplit=1)
    action = tokens[0].lower()
    name = tokens[1] if len(tokens) > 1 else action
    return action, name, value


def build_capabilities(udid: str) -> dict[str, Any]:
    caps: dict[str, Any] = {
        "platformName": "Android",
        "appium:automationName": "UiAutomator2",
        "appium:deviceName": udid,
        "appium:udid": udid,
        "appium:noReset": True,
        "appium:newCommandTimeout": 300,
    }
    foreground_app = get_foreground_app(udid)
    if foreground_app:
        caps["appium:appPackage"] = foreground_app[0]
        caps["appium:appActivity"] = foreground_app[1]
    return caps


def save_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def record_case(args: argparse.Namespace) -> None:
    require_adb()
    udid = args.udid or get_device_id()
    priority = (args.priority or prompt_required("用例等级 P0/P1/P2/P3/P4", "P2")).upper()
    if priority not in PRIORITIES:
        raise SystemExit(f"Unsupported priority: {priority}")

    test_name = slugify(args.test_name or prompt_required("用例名称 test_name"))
    title = args.title or prompt_required("用例标题", test_name.replace("_", " "))
    suite = args.suite or prompt_required("Allure suite", "UI Automation")
    feature = args.feature or prompt_required("Allure feature", "Recorded UI Case")

    session: dict[str, Any] = {
        "suite": suite,
        "feature": feature,
        "title": title,
        "test_name": test_name,
        "priority": priority,
        "description": f"Recorded UI case: {title}",
        "steps": [],
    }
    update_live_preview(session)

    steps: list[dict[str, Any]] = session["steps"]
    print("\n录制命令：")
    print("  tap 步骤名              -> 等待你点击设备控件并记录点击")
    print("  input 步骤名 | 输入文本  -> 等待你点击输入框并记录输入")
    print("  assert_visible 步骤名   -> 等待你点击目标控件并记录可见断言")
    print("  sleep 秒数              -> 记录等待")
    print("  loop 1-3 2              -> 循环执行步骤 1 到 3，共 2 次")
    print("  done                    -> 完成并生成脚本\n")

    while True:
        raw = input(f"步骤{len(steps) + 1}> ").strip()
        if not raw:
            continue
        if raw.lower() in {"done", "结束", "完成"}:
            break

        action, name, value = parse_step_command(raw)
        if action == "sleep":
            step = {"name": f"Sleep {name}s", "action": "sleep", "seconds": float(name)}
            steps.append(step)
            update_live_preview(session, latest_step=step)
            print_live_preview(session, latest_step=step)
            continue
        if action == "loop":
            match = re.match(r"(\d+)-(\d+)\s+(\d+)", name)
            if not match:
                print("循环格式示例：loop 1-3 2")
                continue
            step = {
                "name": f"Loop steps {match.group(1)}-{match.group(2)}",
                "action": "loop",
                "from_step": int(match.group(1)),
                "to_step": int(match.group(2)),
                "times": int(match.group(3)),
            }
            steps.append(step)
            update_live_preview(session, latest_step=step)
            print_live_preview(session, latest_step=step)
            continue

        if action not in {"tap", "click", "input", "set_text", "assert_visible", "wait_visible"}:
            print(f"不支持的录制动作：{action}")
            continue

        ui_root = dump_ui_xml(udid)
        x, y = wait_for_tap(udid, timeout=args.tap_timeout)
        node = find_node_at(ui_root, x, y)
        step: dict[str, Any] = {
            "name": name,
            "action": "tap" if action == "click" else action,
            "locator": locator_from_node(node, x, y),
        }
        if action in {"input", "set_text"}:
            if value is None:
                value = prompt_required("输入文本")
            step["value"] = value
        steps.append(step)
        update_live_preview(session, latest_step=step)
        print_live_preview(session, latest_step=step)

    if not steps:
        raise SystemExit("No steps recorded.")

    spec = {
        "suite": suite,
        "feature": feature,
        "story": title,
        "test_name": test_name,
        "title": title,
        "priority": priority,
        "description": f"Recorded UI case: {title}",
        "steps": steps,
    }
    validate_spec(spec)

    capabilities = build_capabilities(udid)
    save_json(Path("capabilities.local.json"), capabilities)

    spec_path = Path(args.spec_root) / priority / f"{test_name}.json"
    save_json(spec_path, spec)

    output_dir = Path(args.output_root) / priority
    test_path = write_outputs(spec, output_dir)

    print(f"\n已保存用例规格：{spec_path}")
    print(f"已生成 pytest 脚本：{test_path}")
    print(f"执行当前等级：python .cursor/skills/ui-auto-pytest-allure/scripts/run_priority.py {priority}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-name", help="Generated test case name.")
    parser.add_argument("--title", help="Human-readable test title.")
    parser.add_argument("--priority", choices=sorted(PRIORITIES), help="Case priority.")
    parser.add_argument("--suite", help="Allure suite.")
    parser.add_argument("--feature", help="Allure feature.")
    parser.add_argument("--udid", help="Android device id. Defaults to the first connected device.")
    parser.add_argument("--tap-timeout", type=int, default=60, help="Seconds to wait for each device tap.")
    parser.add_argument("--spec-root", default="specs", help="Directory for recorded JSON specs.")
    parser.add_argument("--output-root", default="generated-tests/ui", help="Directory for generated pytest files.")
    args = parser.parse_args()
    record_case(args)


if __name__ == "__main__":
    main()
