---
name: ui-auto-pytest-allure
description: Generate executable Python pytest and Allure UI automation tests from natural-language UI case descriptions. Use when the user asks to create UI automation cases, run tests with phrases like 运行P0测试用例 or 运行test_xxx.py, pytest UI scripts, Allure reports, Appium tests, open an Android UI element inspector, execute P0/P1/P2/P3/P4 cases, or describes UI steps in plain language with optional locators such as id, xpath, accessibility id, or visible text.
---

# UI Auto Pytest Allure

## Goal

Turn a user's **natural-language** UI automation request into executable `python + pytest + Allure` test cases.

The user only needs to describe:
- Case priority: `P0` to `P4`
- Case name and title
- Steps such as tap, input, assert, sleep, and loop
- Optional explicit locators (`id:...`, `xpath:...`) or visible control text

**Do not require device tap recording.** Do not ask the user to click the device and reply `步骤N完成` unless they explicitly request legacy recording.

## Default Stack

- `pytest` + `allure-pytest` + `Appium-Python-Client` + `selenium`
- `Appium Inspector` only for viewing elements when the user asks to open the element inspector plugin

## Primary Workflow: Natural Language → Generated Case

1. Parse the user's natural-language case into a JSON spec (see [reference.md](reference.md) and [examples.md](examples.md)).
2. Prefer stable locators:
   - Explicit: `id:`, `accessibility:`, `xpath:`, `uiautomator:`, coordinates
   - Otherwise: visible text → `android_uiautomator` with `text("...")`
3. Generate files with:

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/create_case_from_nl.py cases/your_case.nl
```

Or inline:

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/create_case_from_nl.py --text "P1
用例名: demo
标题: 演示用例
步骤1: 点击 设置
步骤2: 点击 密码与安全"
```

4. Outputs:
   - `specs/<priority>/<test_name>.json`
   - `generated-tests/ui/<priority>/test_<test_name>.py`
   - `recording/live_spec.json` and `recording/live_test.py` for immediate review and edits
5. If the user wants changes, edit `recording/live_spec.json` or ask in chat, then run:

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/refresh_recording_preview.py
python .cursor/skills/ui-auto-pytest-allure/scripts/create_case_from_nl.py cases/your_case.nl
```

6. Install Python dependencies automatically before running tests:

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/install_ui_dependencies.py
```

`create_case_from_nl.py` and `run_priority.py` call this installer by default.

7. Run tests when the user says natural-language run commands:

| User says | Action |
|-----------|--------|
| `运行P0测试用例` / `执行P1用例` | Run all tests under that priority |
| `运行test_setting_password_idle_lock.py` | Run one test file |

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/run_ui_tests.py "运行P0测试用例"
python .cursor/skills/ui-auto-pytest-allure/scripts/run_ui_tests.py "运行test_setting_password_idle_lock.py"
```

Equivalent forms:

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/run_ui_tests.py --priority P0
python .cursor/skills/ui-auto-pytest-allure/scripts/run_ui_tests.py --test test_setting_password_idle_lock.py
```

When the user message matches a run command, run `run_ui_tests.py` immediately. Do not execute test files with plain `python`.

Before tests, `run_ui_tests.py` **auto-starts Appium** if needed and syncs `capabilities.json` device id from `adb devices`.

After tests finish, it runs **`allure serve`** (local HTTP server) to open the report. Do not open `index.html` via `file://` or widgets stay on Loading. Use `--no-open-report` to skip.

Allure CLI is installed automatically into `.tools/allure-<version>/` by `install_ui_dependencies.py` (also sets Windows user `PATH` and `ALLURE_HOME`). Manual install:

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/install_allure_cli.py
```

**Never run a generated test file directly with `python test_xxx.py`.** Always use `pytest` so fixtures, markers, and Allure hooks work.

Correct:

```bash
python -m pytest generated-tests/ui/P1 -m P1 --alluredir=allure-results/P1
```

Wrong:

```bash
python generated-tests/ui/P1/test_setting_password_idle_lock.py
```

## Batch Import from Excel / 飞书云表格

Table headers (required): **用例等级、用例名、功能模块、子模块、操作步骤**

1. Create the sheet in Excel or Feishu (multi-line steps in one cell).
2. Export as `.csv` or `.xlsx`.
3. Import:

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/import_cases_from_sheet.py cases/your_cases.csv
```

See [docs/CASE_IMPORT.md](../../../docs/CASE_IMPORT.md) and template `cases/import_template.csv`.

## Natural Language Format

Supported lines:

```text
P1
用例名: setting_password_lock
标题: 设置-开启空闲锁定电机
功能: 设置

步骤1: 点击 密码与安全
步骤2: 点击 id:com.example:id/login
步骤3: 输入 账号, demo_user
步骤4: 断言 首页 可见
步骤5: 断言文字 提示, 保存成功
循环步骤1-2 2次
等待 2秒
```

Supported step verbs: `点击` / `设置开关` / `打开开关` / `关闭开关` / `输入` / `断言` / `断言文字` / `等待` / `循环步骤`

Switch state example:

```text
步骤4: 设置开关 空闲时锁电机 打开
步骤4: 设置开关 空闲时锁电机 关闭
步骤4: 打开开关 空闲时锁电机
```

## Android Element Inspector

When the user says `打开界面控件元素插件` or `打开页面元素插件`:

```powershell
powershell -ExecutionPolicy Bypass -File .cursor/skills/ui-auto-pytest-allure/scripts/open_android_inspector.ps1
```

Use Inspector only to **look up locators** when the user needs `id` or `xpath`. Put those locators into the natural-language case or `live_spec.json`.

If Inspector **Refresh Source & Screenshot** fails with `instrumentation process is not running`:

1. Do **not** keep refreshing the old Inspector tab. That session is already dead.
2. Repair and create a fresh healthy session:

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/repair_appium_session.py --open-inspector
```

PowerShell equivalent:

```powershell
powershell -ExecutionPolicy Bypass -File .cursor/skills/ui-auto-pytest-allure/scripts/repair_appium_inspector.ps1 -OpenInspector
```

3. In Inspector choose **Attach to Session** and select the new `session_id` printed by the repair script (also saved in `.appium-inspector-session.json`).
4. Then click **Refresh Source & Screenshot**.

`run_ui_tests.py` now auto-repairs after each test run so Inspector is ready for locator lookup.

## Legacy Recording (Optional)

Only use tap recording if the user explicitly asks to record by clicking the device:

- `scripts/record_ui_case.py`
- `scripts/record_step_done.py`

Otherwise, always prefer `create_case_from_nl.py`.

## Supported Actions

`tap`, `click`, `input`, `set_text`, `set_switch`, `assert_visible`, `assert_not_visible`, `assert_text`, `wait_visible`, `sleep`, `screenshot`, `swipe`, `loop`

## Dependencies

Required packages: `pytest`, `allure-pytest`, `Appium-Python-Client`, `selenium`.

If the user reports `ModuleNotFoundError: No module named 'allure'` or missing `pytest`, run:

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/install_ui_dependencies.py
```

Then run tests with pytest, not by executing the test file directly.

## Examples

See [examples.md](examples.md).
