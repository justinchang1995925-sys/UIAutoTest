#!/usr/bin/env python3
"""Generate pytest + Allure + Appium UI tests from a JSON case spec."""

from __future__ import annotations

import argparse
import json
import re
import textwrap
from pathlib import Path
from typing import Any


SUPPORTED_ACTIONS = {
    "tap",
    "click",
    "input",
    "set_text",
    "set_switch",
    "assert_visible",
    "assert_not_visible",
    "assert_text",
    "wait_visible",
    "sleep",
    "screenshot",
    "swipe",
    "loop",
}

SUPPORTED_LOCATORS = {
    "id",
    "accessibility_id",
    "xpath",
    "css",
    "name",
    "class_name",
    "android_uiautomator",
    "ios_predicate",
    "ios_class_chain",
    "coordinates",
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip()).strip("_").lower()
    return slug or "generated_ui_case"


def load_spec(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON spec: {path}: {exc}") from exc


def validate_spec(spec: dict[str, Any]) -> None:
    priority = str(spec.get("priority", "P2")).upper()
    if priority not in {"P0", "P1", "P2", "P3", "P4"}:
        raise SystemExit("Spec priority must be one of: P0, P1, P2, P3, P4.")

    if not isinstance(spec.get("steps"), list) or not spec["steps"]:
        raise SystemExit("Spec must contain a non-empty 'steps' list.")

    for index, step in enumerate(spec["steps"], start=1):
        if not isinstance(step, dict):
            raise SystemExit(f"Step {index} must be an object.")

        action = step.get("action")
        if action not in SUPPORTED_ACTIONS:
            supported = ", ".join(sorted(SUPPORTED_ACTIONS))
            raise SystemExit(f"Step {index} has unsupported action '{action}'. Supported: {supported}")

        if action == "sleep":
            if "seconds" not in step:
                raise SystemExit(f"Step {index} sleep action requires 'seconds'.")
            continue

        if action == "screenshot":
            continue

        if action == "swipe":
            if not isinstance(step.get("start"), dict) or not isinstance(step.get("end"), dict):
                raise SystemExit(f"Step {index} swipe action requires 'start' and 'end' coordinates.")
            continue

        if action == "loop":
            if not isinstance(step.get("from_step"), int) or not isinstance(step.get("to_step"), int):
                raise SystemExit(f"Step {index} loop action requires integer 'from_step' and 'to_step'.")
            if int(step.get("times", 1)) < 1:
                raise SystemExit(f"Step {index} loop action requires 'times' greater than 0.")
            continue

        locator = step.get("locator")
        if not isinstance(locator, dict) or len(locator) != 1:
            raise SystemExit(f"Step {index} requires a locator object with exactly one locator key.")

        key = next(iter(locator))
        if key not in SUPPORTED_LOCATORS:
            supported = ", ".join(sorted(SUPPORTED_LOCATORS))
            raise SystemExit(f"Step {index} has unsupported locator '{key}'. Supported: {supported}")

        fallbacks = step.get("locators_fallback")
        if fallbacks is not None:
            if not isinstance(fallbacks, list):
                raise SystemExit(f"Step {index} locators_fallback must be a list.")
            for fb_index, fb in enumerate(fallbacks, start=1):
                if not isinstance(fb, dict) or len(fb) != 1:
                    raise SystemExit(
                        f"Step {index} locators_fallback[{fb_index}] must be a single-key locator object."
                    )
                fb_key = next(iter(fb))
                if fb_key not in SUPPORTED_LOCATORS:
                    raise SystemExit(
                        f"Step {index} locators_fallback[{fb_index}] has unsupported locator '{fb_key}'."
                    )

        if action in {"input", "set_text", "assert_text"} and "value" not in step:
            raise SystemExit(f"Step {index} action '{action}' requires 'value'.")

        if action == "set_switch":
            state = str(step.get("state", "")).strip().lower()
            if state not in {"on", "off"}:
                raise SystemExit(f"Step {index} set_switch action requires state 'on' or 'off'.")


def json_literal(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=4)


def build_test_file(spec: dict[str, Any]) -> str:
    test_name = slugify(str(spec.get("test_name") or spec.get("title") or "generated_ui_case"))
    suite = spec.get("suite", "UI Automation")
    feature = spec.get("feature", "Generated UI Case")
    story = spec.get("story", test_name.replace("_", " ").title())
    title = spec.get("title", story)
    description = spec.get("description", "")
    priority = str(spec.get("priority", "P2")).upper()
    severity_map = {
        "P0": "blocker",
        "P1": "critical",
        "P2": "normal",
        "P3": "minor",
        "P4": "trivial",
    }
    severity = severity_map.get(priority, "normal")
    timeout = int(spec.get("timeout", 15))
    steps_literal = json_literal(spec["steps"])

    return f'''"""Generated UI automation test.

Source spec: {test_name}
"""

from __future__ import annotations

import sys
from pathlib import Path

import allure
import pytest

# Ensure generated-tests/ui is on sys.path so we can import shared helpers.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _lib.ui_runtime import run_steps  # noqa: E402


DEFAULT_TIMEOUT = {timeout}

STEPS = {steps_literal}


@allure.suite({suite!r})
@allure.feature({feature!r})
@allure.story({story!r})
@allure.title({title!r})
@allure.description({description!r})
@allure.severity({severity!r})
@pytest.mark.ui
@pytest.mark.{priority}
def test_{test_name}(driver):
    run_steps(driver, STEPS, DEFAULT_TIMEOUT)
'''


def build_requirements() -> str:
    return """pytest
allure-pytest
Appium-Python-Client
selenium
"""


def build_pytest_ini() -> str:
    return """[pytest]
markers =
    ui: generated UI automation tests
    P0: blocker smoke/regression cases
    P1: critical regression cases
    P2: normal regression cases
    P3: minor regression cases
    P4: trivial regression cases
"""


def write_outputs(spec: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    test_name = slugify(str(spec.get("test_name") or spec.get("title") or "generated_ui_case"))
    test_path = output_dir / f"test_{test_name}.py"
    test_path.write_text(build_test_file(spec), encoding="utf-8")

    ui_root = output_dir.parent
    shared_files = {
        "requirements.txt": build_requirements(),
        "pytest.ini": build_pytest_ini(),
    }
    for name, content in shared_files.items():
        path = ui_root / name
        if not path.exists():
            path.write_text(content, encoding="utf-8")

    return test_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="Path to the JSON UI test spec.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("generated-tests/ui"),
        help="Output test root directory (priority subfolder is added from spec).",
    )
    args = parser.parse_args()

    spec = load_spec(args.spec)
    validate_spec(spec)
    priority = str(spec.get("priority", "P2")).upper()
    test_path = write_outputs(spec, args.output / priority)
    print(f"Generated: {test_path}")
    print(f"Run: python uiatest.py run --priority {priority}")


if __name__ == "__main__":
    main()
