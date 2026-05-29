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

Author cases in `.nl` files or CSV/Excel sheets — **not** by tapping the device to record.

## Default Stack

- `pytest` + `allure-pytest` + `Appium-Python-Client` + `selenium`
- `Appium Inspector` for viewing elements when the user asks to open the element inspector

## Unified CLI (recommended)

Project root entry point:

```bash
python uiatest.py --help
python uiatest.py doctor
python uiatest.py import cases/your_cases.csv
python uiatest.py gen cases/your_case.nl
python uiatest.py run "运行P1测试用例"
python uiatest.py inspect
python uiatest.py clean
```

| Subcommand | Purpose |
|------------|---------|
| `run` | Run by NL, `--priority`, or `--test` |
| `import` | CSV/XLSX → `.nl` + spec + pytest |
| `gen` | `.nl` → spec + pytest |
| `doctor` | Preflight checks |
| `clean` | Remove allure-results/report, logs |
| `inspect` | Start Appium session + open Inspector once |
| `repair` | Repair UiAutomator2 session |

Long-form scripts under `.cursor/skills/ui-auto-pytest-allure/scripts/` still work; prefer `uiatest.py` for users.

## Primary Workflow: Natural Language → Generated Case

1. Parse the user's natural-language case into a JSON spec (see [reference.md](reference.md) and [examples.md](examples.md)).
2. Prefer stable locators:
   - Explicit: `id:`, `accessibility:`, `xpath:`, `uiautomator:`, coordinates
   - Otherwise: visible text → `android_uiautomator` with `text("...")`
3. Generate files with:

```bash
python uiatest.py gen cases/your_case.nl
```

Or inline:

```bash
python uiatest.py gen cases/_inline.nl --text "P1
用例名: demo
标题: 演示用例
步骤1: 点击 设置
步骤2: 点击 密码与安全"
```

4. Outputs:
   - `specs/<priority>/<test_name>.json`
   - `generated-tests/ui/<priority>/test_<test_name>.py`
   - Shared fixtures: `generated-tests/ui/conftest.py`, `pytest.ini`

5. Install Python dependencies automatically before running tests:

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/install_ui_dependencies.py
```

6. Run tests when the user says natural-language run commands:

| User says | Action |
|-----------|--------|
| `运行P0测试用例` / `执行P1用例` | Run all tests under that priority |
| `运行test_setting_password_idle_lock.py` | Run one test file |

```bash
python uiatest.py run "运行P0测试用例"
python uiatest.py run --test test_setting_password_idle_lock.py
```

When the user message matches a run command, run `uiatest.py run` (or `run_ui_tests.py`) immediately. Do not execute test files with plain `python`.

Before tests, the runner **auto-starts Appium** if needed and ensures a usable capabilities file exists.

### Device connection (USB or IP)

Default: `运行P1测试用例` uses the current connected Android device.

If the user says `连接设备 192.168.140.172:5555 并运行P1测试用例`, the runner will `adb connect`, update `capabilities.local.json`, start Appium, and run tests.

### Capabilities files (template + local)

Load order:

- `APPIUM_CAPABILITIES` env (JSON string)
- `APPIUM_CAPABILITIES_FILE` env (path)
- `capabilities.local.json` (local overrides, **gitignored**)
- `capabilities.json` (legacy placeholder in repo)
- `capabilities.template.json` (committed template)

`capabilities.local.json` is created from template on first run when missing. Inspector writes to **`capabilities.local.json`**, not the tracked file.

After tests finish, the runner uses **`allure serve`** (local HTTP). Use `--no-open-report` to skip. Static HTML copy: `--static-report`.

**Never run a generated test file directly with `python test_xxx.py`.** Always use `pytest` or `uiatest run`.

### Failure attachments (Allure)

On failure, `generated-tests/ui/conftest.py` attaches screenshot, page source, activity, logcat, optional screenrecord.

## Batch Import from Excel / 飞书云表格

Required headers: **用例等级、用例名、功能模块、子模块、操作步骤**  
Recommended: **预期结果** (per-step post assertions).

```bash
python uiatest.py import cases/your_cases.csv
```

See [docs/CASE_IMPORT.md](../../../docs/CASE_IMPORT.md) and `cases/import_template.csv`.

## Natural Language Format

```text
P1
用例名: setting_password_lock
标题: 设置-开启空闲锁定电机
功能: 设置

步骤1: 点击 密码与安全
步骤2: 点击 id:com.example:id/login
步骤3: 输入 账号, demo_user
步骤4: 断言 首页 可见
循环步骤1-2 2次
等待 2秒
```

### Locator resolve (id-first + text fallback)

When generating (`gen` / `import`), if a device is connected:

- Plain text steps are dumped from the UI tree
- Matching `resource-id` becomes primary; text kept in `locators_fallback`
- Runtime tries primary → fallbacks

Skip resolve: `--no-resolve-locators`

## Android Element Inspector

When the user asks to open the element inspector:

```bash
python uiatest.py inspect
```

Opens Inspector **once** after a healthy Appium session is created. In Inspector: **Attach to Session** with the printed session id.

If refresh fails with instrumentation errors:

```bash
python uiatest.py repair --open-inspector
```

Do not refresh dead Inspector tabs. `run_ui_tests.py` auto-repairs after test runs when Inspector may be used next.

## Supported Actions

`tap`, `click`, `input`, `set_text`, `set_switch`, `assert_visible`, `assert_not_visible`, `assert_text`, `wait_visible`, `sleep`, `screenshot`, `swipe`, `loop`

## Dependencies

Required: `pytest`, `allure-pytest`, `Appium-Python-Client`, `selenium`.

If imports fail, run:

```bash
python uiatest.py doctor
python .cursor/skills/ui-auto-pytest-allure/scripts/install_ui_dependencies.py
```

## Examples

See [examples.md](examples.md).
