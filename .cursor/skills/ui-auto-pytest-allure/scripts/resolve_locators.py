#!/usr/bin/env python3
"""Resolve text locators to id-first chains using on-device UI dump."""

from __future__ import annotations

import re
import time
from typing import Any
from xml.etree import ElementTree as ET

from appium_server import get_connected_device_ids
from record_ui_case import dump_ui_xml, locator_from_node, parse_bounds, run_adb

TEXT_UIAUTOMATOR_RE = re.compile(r'text\("((?:\\.|[^"])*)"\)')
DEFAULT_APP_PACKAGE = "com.pudutech.business.function"
DEFAULT_APP_ACTIVITY = "com.pudutech.function.homepage.ui.HomeActivity"


def extract_text_label(locator: dict[str, Any]) -> str | None:
    """Return visible label if locator is text-based."""
    if not isinstance(locator, dict) or len(locator) != 1:
        return None
    key = next(iter(locator))
    value = locator[key]
    if key == "android_uiautomator" and isinstance(value, str):
        match = TEXT_UIAUTOMATOR_RE.search(value)
        if match:
            return match.group(1).replace('\\"', '"').replace("\\\\", "\\")
    if key == "xpath" and isinstance(value, str) and '@text="' in value:
        match = re.search(r'@text="([^"]*)"', value)
        if match:
            return match.group(1)
    return None


def locator_priority_key(locator: dict[str, Any]) -> int:
    """Lower is better (id preferred)."""
    key = next(iter(locator))
    order = {
        "id": 0,
        "accessibility_id": 1,
        "android_uiautomator": 2,
        "xpath": 3,
        "coordinates": 4,
    }
    return order.get(key, 9)


def _node_area(node: ET.Element) -> int:
    bounds = node.attrib.get("bounds", "")
    match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
    if not match:
        return 10**12
    left, top, right, bottom = (int(match.group(i)) for i in range(1, 5))
    return max(0, right - left) * max(0, bottom - top)


def _is_clickable(node: ET.Element) -> bool:
    return node.attrib.get("clickable", "").lower() == "true"


def find_best_node_by_text(root: ET.Element, label: str) -> ET.Element | None:
    label = label.strip()
    if not label:
        return None

    candidates: list[ET.Element] = []
    for node in root.iter("node"):
        text = (node.attrib.get("text") or "").strip()
        desc = (node.attrib.get("content-desc") or "").strip()
        if text != label and desc != label:
            continue
        candidates.append(node)

    if not candidates:
        return None

    def sort_key(node: ET.Element) -> tuple[int, int, int]:
        has_id = 0 if (node.attrib.get("resource-id") or "").strip() else 1
        clickable = 0 if _is_clickable(node) else 1
        return (has_id, clickable, _node_area(node))

    return sorted(candidates, key=sort_key)[0]


def find_node_by_resource_id(root: ET.Element, resource_id: str) -> ET.Element | None:
    resource_id = resource_id.strip()
    if not resource_id:
        return None
    for node in root.iter("node"):
        if (node.attrib.get("resource-id") or "").strip() == resource_id:
            return node
    return None


def find_node_by_locator(root: ET.Element, locator: dict[str, Any]) -> ET.Element | None:
    if not isinstance(locator, dict) or len(locator) != 1:
        return None
    key, value = next(iter(locator.items()))
    if key == "id" and isinstance(value, str):
        return find_node_by_resource_id(root, value)
    if key == "accessibility_id" and isinstance(value, str):
        for node in root.iter("node"):
            if (node.attrib.get("content-desc") or "").strip() == value.strip():
                return node
    label = extract_text_label(locator)
    if label:
        return find_best_node_by_text(root, label)
    return None


def find_navigation_node(step: dict[str, Any], root: ET.Element) -> ET.Element | None:
    """Pick the node to tap when advancing the UI during sequential resolve."""
    for fallback in step.get("locators_fallback") or []:
        label = extract_text_label(fallback)
        if label:
            node = find_best_node_by_text(root, label)
            if node is not None:
                return node

    locator = step.get("locator")
    if isinstance(locator, dict):
        label = extract_text_label(locator)
        if label:
            node = find_best_node_by_text(root, label)
            if node is not None:
                return node
        return find_node_by_locator(root, locator)
    return None


def tap_node_center(udid: str, node: ET.Element) -> bool:
    bounds = parse_bounds(node.attrib.get("bounds", ""))
    if not bounds:
        return False
    left, top, right, bottom = bounds
    x = (left + right) // 2
    y = (top + bottom) // 2
    result = run_adb(["shell", "input", "tap", str(x), str(y)], udid=udid, timeout=10)
    return result.returncode == 0


def activate_target_app(
    udid: str,
    package: str = DEFAULT_APP_PACKAGE,
    activity: str = DEFAULT_APP_ACTIVITY,
) -> None:
    run_adb(
        ["shell", "am", "start", "-n", f"{package}/{activity}"],
        udid=udid,
        timeout=15,
    )
    time.sleep(1.5)


def count_resource_id(root: ET.Element, resource_id: str) -> int:
    resource_id = resource_id.strip()
    if not resource_id:
        return 0
    return sum(
        1
        for node in root.iter("node")
        if (node.attrib.get("resource-id") or "").strip() == resource_id
    )


def android_uiautomator_resource_id_text(resource_id: str, label: str) -> str:
    escaped_id = resource_id.replace("\\", "\\\\").replace('"', '\\"')
    escaped_label = label.replace("\\", "\\\\").replace('"', '\\"')
    return f'new UiSelector().resourceId("{escaped_id}").text("{escaped_label}")'


def resolve_chain_from_root(
    original: dict[str, Any],
    root: ET.Element,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return (primary_locator, fallback_locators) from an existing UI dump."""
    if not isinstance(original, dict) or len(original) != 1:
        return original, []

    key = next(iter(original))
    if key in {"id", "accessibility_id", "coordinates"}:
        return original, []

    label = extract_text_label(original)
    if not label:
        return original, []

    node = find_best_node_by_text(root, label)
    if node is None:
        print(f"Warning: no UI node matched text {label!r}; keep text locator.")
        return original, []

    resolved = locator_from_node(node, 0, 0)
    if resolved == original:
        return original, []

    if "id" in resolved:
        resource_id = resolved["id"]
        if count_resource_id(root, resource_id) > 1:
            compound = {
                "android_uiautomator": android_uiautomator_resource_id_text(resource_id, label)
            }
            return compound, [original]
        return {"id": resource_id}, [original]
    if "accessibility_id" in resolved:
        return {"accessibility_id": resolved["accessibility_id"]}, [original]
    return original, []


def build_resolved_chain(
    original: dict[str, Any],
    udid: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return (primary_locator, fallback_locators).

    If already id/accessibility, returns original with no fallbacks.
    If text-only and dump finds id, returns id primary + [original] fallback.
    """
    if not isinstance(original, dict) or len(original) != 1:
        return original, []

    key = next(iter(original))
    if key in {"id", "accessibility_id", "coordinates"}:
        return original, []

    label = extract_text_label(original)
    if not label:
        return original, []

    device_ids = get_connected_device_ids()
    if not device_ids:
        return original, []
    device = udid or device_ids[0]

    try:
        root = dump_ui_xml(device)
    except Exception as exc:
        print(f"Warning: UI dump failed for locator resolve ({label!r}): {exc}")
        return original, []

    return resolve_chain_from_root(original, root)


def resolve_locator_field(
    locator: dict[str, Any] | None,
    udid: str | None = None,
    root: ET.Element | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not locator:
        return None, []
    if root is not None:
        primary, fallbacks = resolve_chain_from_root(locator, root)
    else:
        primary, fallbacks = build_resolved_chain(locator, udid=udid)
    return primary, fallbacks


def apply_resolved_locator(
    target: dict[str, Any],
    locator: dict[str, Any] | None,
    fallbacks: list[dict[str, Any]],
) -> None:
    if locator:
        target["locator"] = locator
    if fallbacks:
        target["locators_fallback"] = fallbacks
    elif "locators_fallback" in target:
        target.pop("locators_fallback", None)


def resolve_step_locators(
    step: dict[str, Any],
    udid: str | None = None,
    root: ET.Element | None = None,
) -> None:
    """Mutate step: id-first locator + text fallbacks when possible."""
    if step.get("action") in {"sleep", "loop", "screenshot", "swipe"}:
        return

    locator = step.get("locator")
    if isinstance(locator, dict):
        primary, fallbacks = resolve_locator_field(locator, udid=udid, root=root)
        apply_resolved_locator(step, primary, fallbacks)

    for field in ("expect_visible", "expect_not_visible"):
        field_loc = step.get(field)
        if isinstance(field_loc, dict):
            primary, fallbacks = resolve_locator_field(field_loc, udid=udid, root=root)
            if primary:
                step[field] = primary
            if fallbacks:
                step[f"{field}_locators_fallback"] = fallbacks


def _was_text_upgraded(before: Any, after: Any) -> bool:
    if not isinstance(before, dict) or "android_uiautomator" not in before:
        return False
    if not isinstance(after, dict):
        return False
    if "id" in after:
        return True
    after_value = after.get("android_uiautomator", "")
    return isinstance(after_value, str) and "resourceId(" in after_value


def resolve_spec_locators(spec: dict[str, Any], udid: str | None = None) -> int:
    """Resolve steps sequentially: dump current screen, upgrade locators, tap to advance."""
    device_ids = get_connected_device_ids()
    if not device_ids:
        return 0
    device = udid or device_ids[0]
    upgraded = 0

    package = str(spec.get("app_package") or DEFAULT_APP_PACKAGE).strip()
    activity = str(spec.get("app_activity") or DEFAULT_APP_ACTIVITY).strip()
    try:
        activate_target_app(device, package=package, activity=activity)
    except Exception as exc:
        print(f"Warning: could not activate app before locator resolve: {exc}")

    for step in spec.get("steps", []):
        action = step.get("action")
        if action in {"sleep", "loop", "screenshot", "swipe"}:
            continue

        try:
            root = dump_ui_xml(device)
        except Exception as exc:
            print(f"Warning: UI dump failed during sequential resolve: {exc}")
            break

        before = step.get("locator")
        resolve_step_locators(step, udid=device, root=root)
        after = step.get("locator")
        if _was_text_upgraded(before, after):
            upgraded += 1

        if action in {"tap", "click"}:
            node = find_navigation_node(step, root)
            if node is not None and tap_node_center(device, node):
                time.sleep(1.5)

    return upgraded
