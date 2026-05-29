# UI Test Spec Reference

## Minimal Spec

```json
{
  "suite": "Login",
  "feature": "Authentication",
  "story": "Successful login",
  "test_name": "login_success",
  "title": "User can log in with valid account",
  "description": "Open the app, enter account data, tap login, and verify the home page.",
  "steps": [
    {
      "name": "Input username",
      "action": "input",
      "locator": {"id": "com.example:id/username"},
      "value": "demo_user"
    },
    {
      "name": "Input password",
      "action": "input",
      "locator": {"id": "com.example:id/password"},
      "value": "123456"
    },
    {
      "name": "Tap login",
      "action": "tap",
      "locator": {"accessibility_id": "Login"}
    },
    {
      "name": "Verify home page",
      "action": "assert_visible",
      "locator": {"id": "com.example:id/home_title"}
    }
  ]
}
```

## Top-Level Fields

- `suite`: Allure suite name.
- `feature`: Allure feature name.
- `story`: Allure story name.
- `test_name`: Python test function suffix. Use lowercase letters, numbers, and underscores.
- `title`: Allure test title.
- `description`: Optional Allure description.
- `timeout`: Optional default wait timeout in seconds. Default is `10`.
- `priority`: Optional case priority. Use `P0`, `P1`, `P2`, `P3`, or `P4`. Default is `P2`.
- `steps`: Ordered operation list.

## Step Fields

- `name`: Human-readable Allure step name.
- `action`: Supported action.
- `locator`: Required for element actions unless using coordinate-only actions.
- `value`: Text for input or expected text assertions.
- `timeout`: Optional per-step wait timeout.
- `clear`: Optional boolean for input actions. Default is `true`.
- `contains`: Optional boolean for `assert_text`. Default is `true`.
- `seconds`: Required for `sleep`.
- `file_name`: Optional for `screenshot`.
- `start` and `end`: Coordinates for `swipe`, each shaped as `{"x": 100, "y": 500}`.
- `duration_ms`: Optional swipe duration.
- `from_step`, `to_step`, and `times`: Required for `loop`.

## Supported Locators

Use one locator key per `locator` object:

- `id`
- `accessibility_id`
- `xpath`
- `css`
- `name`
- `class_name`
- `android_uiautomator`
- `ios_predicate`
- `ios_class_chain`
- `coordinates`

Coordinate locator:

```json
{"coordinates": {"x": 120, "y": 640}}
```

## Spreadsheet Batch Import (Excel / Feishu CSV)

Required columns:

| Column | Maps to |
|--------|---------|
| 用例等级 | `P0`–`P4` priority folder |
| 用例名 | `用例名:` / `test_name` |
| 功能模块 | `功能:` / Allure feature |
| 子模块 | `模块:` |
| 操作步骤 | `步骤1:` … (one operation per line in the cell) |

Feishu: export cloud sheet as CSV or Excel, then:

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/import_cases_from_sheet.py cases/import.csv
python .cursor/skills/ui-auto-pytest-allure/scripts/import_cases_from_sheet.py cases/import.xlsx
```

Template: `cases/import_template.csv`. Full guide: `docs/CASE_IMPORT.md`.

For `.xlsx`, install `openpyxl` (`pip install openpyxl`).

## Natural Language Case Authoring

Primary command:

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/create_case_from_nl.py cases/your_case.nl
```

Template file: `cases/template.nl`

Natural language syntax:

| Line | Example |
|------|---------|
| Priority | `P1` or `等级: P1` |
| Case name | `用例名: setting_demo` |
| Title | `标题: 设置演示` |
| Feature | `功能: 设置` |
| Tap by text | `步骤1: 点击 密码与安全` |
| Tap by id | `步骤2: 点击 id:com.example:id/btn` |
| Input | `步骤3: 输入 账号, demo_user` |
| Assert visible | `步骤4: 断言 首页 可见` |
| Assert text | `步骤5: 断言文字 提示, 成功` |
| Loop | `循环步骤1-2 2次` |
| Sleep | `等待 2秒` |
| Set switch | `设置开关 id:com.example:id/switch 关闭` |
| Open/Close switch | `打开开关 空闲时锁电机` |

When only visible text is given, the parser generates:

```json
{"android_uiautomator": "new UiSelector().text(\"密码与安全\")"}
```

## Generation Command

From JSON spec:

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/generate_ui_test.py specs/P1/login_success.json --output generated-tests/ui
```

Or from natural language:

```bash
python uiatest.py gen cases/your_case.nl
```

Generated files:

- `generated-tests/ui/<priority>/test_<test_name>.py`
- `generated-tests/ui/conftest.py` (shared across priorities)
- `generated-tests/ui/requirements.txt`
- `generated-tests/ui/pytest.ini`

## Python Dependencies

Install automatically:

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/install_ui_dependencies.py
```

Requirements file:

```text
generated-tests/ui/requirements.txt
```

Do not execute `test_*.py` directly with `python`. Use:

```bash
python uiatest.py run --priority P1
```

## Runtime Configuration

The shared `driver` fixture in `generated-tests/ui/conftest.py` reads capabilities in this order:

- `APPIUM_CAPABILITIES` (env JSON string)
- `APPIUM_CAPABILITIES_FILE` (env path)
- `capabilities.local.json` (local, gitignored)
- `capabilities.json` (legacy placeholder)
- `capabilities.template.json`

Also uses `APPIUM_SERVER_URL` (default `http://127.0.0.1:4723`).

Do not store passwords, tokens, or production credentials in generated specs.

## Running Tests

Primary command:

```bash
python uiatest.py run "运行P0测试用例"
python uiatest.py run --test test_setting_password_idle_lock.py
```

Supported natural-language patterns:

| Pattern | Example |
|---------|---------|
| Batch by priority | `运行P0测试用例`, `执行P1用例`, `运行 P2` |
| Single test file | `运行test_setting_password_idle_lock.py`, `运行 test_demo` |

This runs tests with `python -m pytest`, auto-starts Appium, and writes Allure results to `allure-results/<priority>` or `allure-results/single`. Default report: `allure serve`.

## Android Element Inspector

Recommended:

```bash
python uiatest.py inspect
```

Opens Inspector once after creating a healthy Appium session. Attach to the printed session id in the Inspector UI.

The bootstrap flow installs Appium plugins/drivers when needed, detects the connected device, writes **`capabilities.local.json`**, and starts Appium with the Inspector plugin.

Manual startup:

```bash
appium --use-plugins=inspector --allow-insecure=*:session_discovery
python uiatest.py repair --open-inspector
```

Then open:

```text
http://127.0.0.1:4723/inspector
```

The Inspector page does not display the Android screen until a session exists. The script creates a session automatically with capabilities like:

```json
{
  "platformName": "Android",
  "appium:automationName": "UiAutomator2",
  "appium:deviceName": "0123456789",
  "appium:noReset": true,
  "appium:appPackage": "your.app.package",
  "appium:appActivity": "your.app.MainActivity"
}
```

For APK installation testing, use `appium:app` instead of `appium:appPackage` and `appium:appActivity`.

The Appium Inspector plugin does not expose a stable URL API for directly pre-filling the Capability Builder. Avoid depending on browser DOM automation for this. Use the generated session and the Inspector Attach to Session flow instead; with `session_discovery` enabled, Inspector can discover the active session.

Recommended locator priority for Android:

1. `accessibility_id` from `content-desc`.
2. `id` from Android `resource-id`.
3. `android_uiautomator` when resource ids are unavailable.
4. `xpath` only when no stable native locator exists.
5. `coordinates` only for non-accessible or canvas-like UI.

Fallback tool: `uiautomatorviewer`.

Use `uiautomatorviewer` only when Appium Inspector cannot connect or the Appium environment is not ready. It is useful for quick Android hierarchy snapshots, but it does not match the generated Appium execution flow as closely.
