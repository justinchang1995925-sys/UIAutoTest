#!/usr/bin/env python3
"""Create pytest UI cases directly from natural-language descriptions."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from generate_ui_test import validate_spec, write_outputs  # noqa: E402
from nl_case_parser import parse_natural_language_case  # noqa: E402
from recording_preview import update_live_preview, print_live_preview  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, help="Natural-language case file, e.g. cases/demo.nl")
    parser.add_argument("--text", help="Natural-language case text inline.")
    parser.add_argument("--spec-root", default="specs", help="Directory for JSON specs.")
    parser.add_argument("--output-root", default="generated-tests/ui", help="Directory for pytest files.")
    parser.add_argument("--no-preview", action="store_true", help="Skip writing recording/live_* preview files.")
    parser.add_argument("--skip-install", action="store_true", help="Skip automatic pip install.")
    args = parser.parse_args()

    if args.text:
        content = args.text
    elif args.source:
        content = args.source.read_text(encoding="utf-8")
    else:
        raise SystemExit("Provide a case file path or --text.")

    spec = parse_natural_language_case(content)
    validate_spec(spec)

    priority = spec["priority"]
    spec_path = Path(args.spec_root) / priority / f"{spec['test_name']}.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

    output_dir = Path(args.output_root) / priority
    test_path = write_outputs(spec, output_dir)

    session = {
        "suite": spec["suite"],
        "feature": spec["feature"],
        "title": spec["title"],
        "test_name": spec["test_name"],
        "priority": priority,
        "description": spec["description"],
        "steps": spec["steps"],
    }
    if not args.no_preview:
        update_live_preview(session)
        print_live_preview(session)

    if not args.skip_install:
        installer = SCRIPT_DIR / "install_ui_dependencies.py"
        print("Installing UI test dependencies...")
        subprocess.run([sys.executable, str(installer)], check=False)

    print(f"已生成规格：{spec_path}")
    print(f"已生成脚本：{test_path}")
    print("运行测试请使用 pytest，不要直接用 python 执行测试文件：")
    print(f"  python -m pytest {output_dir} -m {priority} --alluredir=allure-results/{priority}")
    print(f"或：python .cursor/skills/ui-auto-pytest-allure/scripts/run_priority.py {priority}")


if __name__ == "__main__":
    main()
