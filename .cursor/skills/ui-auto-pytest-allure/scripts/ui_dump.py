#!/usr/bin/env python3
"""Shared adb UI dump and locator helpers for locator resolve."""

from __future__ import annotations

import re
import subprocess
from typing import Any
from xml.etree import ElementTree as ET

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


def dump_ui_xml(udid: str) -> ET.Element:
    remote_path = "/sdcard/window_dump.xml"
    dump_result = run_adb(["shell", "uiautomator", "dump", remote_path], udid=udid, timeout=20)
    if dump_result.returncode != 0:
        raise RuntimeError(f"Could not dump UI XML: {dump_result.stderr or dump_result.stdout}")

    command = ["adb"]
    if udid:
        command.extend(["-s", udid])
    command.extend(["exec-out", "cat", remote_path])
    exec_result = subprocess.run(
        command,
        capture_output=True,
        timeout=20,
        check=False,
    )
    if exec_result.returncode == 0 and exec_result.stdout.strip():
        xml_text = exec_result.stdout.decode("utf-8", errors="replace").strip()
    else:
        cat_result = run_adb(["shell", "cat", remote_path], udid=udid, timeout=20)
        if cat_result.returncode != 0 or not cat_result.stdout.strip():
            raise RuntimeError(f"Could not read UI XML: {cat_result.stderr or cat_result.stdout}")
        xml_text = cat_result.stdout.strip()

    if xml_text.startswith("\ufeff"):
        xml_text = xml_text[1:]
    return ET.fromstring(xml_text)


def parse_bounds(bounds: str) -> tuple[int, int, int, int] | None:
    match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds or "")
    if not match:
        return None
    return tuple(int(group) for group in match.groups())


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
