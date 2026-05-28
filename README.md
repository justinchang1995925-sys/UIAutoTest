# UIAutoTest

基于 **自然语言 / 表格** 描述 UI 操作，自动生成 **pytest + Allure + Appium** 可执行用例，支持 Android 真机自动化与 HTML 测试报告。

## 功能概览

- 用 `.nl` 自然语言或 **Excel / 飞书云表格（CSV）** 批量编写用例
- 按优先级 `P0`～`P4` 生成测试脚本
- 一键运行用例，自动生成并打开 **Allure HTML** 报告
- 自动安装 Python 依赖、Allure CLI、JRE（Windows）
- Appium Inspector 查元素、修复会话脚本
- 支持两种运行说法：默认 USB/已连接设备；或先 `adb connect` 指定 IP:port 再运行

## 环境要求

| 项目 | 说明 |
|------|------|
| Python | 3.10+（推荐 3.13） |
| Node.js | 用于 Appium Server |
| Android 设备 | USB 调试已开启 |
| Appium | 脚本可辅助安装，需设备已授权 `adb` |

首次使用建议在本项目根目录执行：

```powershell
cd D:\UIAutoTest
python .cursor/skills/ui-auto-pytest-allure/scripts/install_ui_dependencies.py
```

将自动安装：`pytest`、`allure-pytest`、`Appium-Python-Client`，以及项目内 `.tools/` 下的 **Allure CLI** 与 **JRE**，并配置用户环境变量。

## 目录结构

```text
UIAutoTest/
├── cases/                    # 自然语言用例（.nl）
├── cases/import_template.csv # 表格导入模板
├── specs/                    # JSON 用例规格
├── generated-tests/ui/       # 生成的 pytest 脚本
│   └── P1/
├── allure-results/           # 测试原始结果（JSON，可删）
├── allure-report/            # HTML 报告（自动生成）
├── capabilities.template.json # Appium 连接配置模板（提交到仓库）
├── capabilities.local.json    # 本地覆盖（自动生成，git 忽略）
├── capabilities.json          # 兼容旧版（legacy）
├── docs/CASE_IMPORT.md       # 表格批量导入说明
└── .cursor/skills/ui-auto-pytest-allure/  # 生成与运行脚本
```

## 快速开始

### 1. 启动 Appium 并打开 Inspector（查元素）

```powershell
powershell -ExecutionPolicy Bypass -File .cursor/skills/ui-auto-pytest-allure/scripts/open_android_inspector.ps1
```

在 Inspector 中查看控件的 `resource-id`，写入用例。

若刷新失败：

```powershell
python .cursor/skills/ui-auto-pytest-allure/scripts/repair_appium_session.py --open-inspector
```

### 2. 编写用例（自然语言）

参考 `cases/setting_password_idle_lock.nl` 或 `cases/template.nl`：

```text
P1
用例名: setting_password_idle_lock
标题: 进入设置-密码与安全-电机锁-关闭空闲时锁电机
功能: 设置
模块: 密码与安全

步骤1: 点击 id:com.pudutech.business.function:id/tvSettings
步骤2: 点击 密码与安全
步骤3: 点击 电机锁
步骤4: 设置开关 id:com.pudutech.business.function:id/idle_lock_switch 关闭
```

生成脚本：

```powershell
python .cursor/skills/ui-auto-pytest-allure/scripts/create_case_from_nl.py cases/setting_password_idle_lock.nl
```

### 3. 从 Excel / 飞书表格批量导入

表头：**用例等级、用例名、功能模块、子模块、操作步骤**（详见 [docs/CASE_IMPORT.md](docs/CASE_IMPORT.md)）

```powershell
python .cursor/skills/ui-auto-pytest-allure/scripts/import_cases_from_sheet.py cases/import_template.csv
```

### 4. 运行用例

运行前会**自动启动 Appium**（若未运行），并确保能力文件可用（优先使用 `capabilities.local.json`）。

```powershell
# 运行单条用例（自动启动 Appium + 跑完后 allure serve 打开报告）
python .cursor/skills/ui-auto-pytest-allure/scripts/run_ui_tests.py "运行 setting_password_idle_lock"

# 运行某优先级全部用例（默认：使用当前已连接设备，通常为 USB）
python .cursor/skills/ui-auto-pytest-allure/scripts/run_ui_tests.py "运行P1测试用例"

# 先连接指定设备 IP:port 再运行（adb over Wi‑Fi）
python .cursor/skills/ui-auto-pytest-allure/scripts/run_ui_tests.py "连接设备 192.168.140.172:5555 并运行P1测试用例"
```

等价命令：

```powershell
python .cursor/skills/ui-auto-pytest-allure/scripts/run_ui_tests.py --test test_setting_password_idle_lock.py
python .cursor/skills/ui-auto-pytest-allure/scripts/run_ui_tests.py --priority P1
```

> 请使用 `pytest` 运行，不要直接 `python test_xxx.py`。

### 5. 查看测试报告

跑完后会**自动启动 Allure 本地服务**并在浏览器打开报告（不要用 `file://` 直接打开 `index.html`，否则会一直 Loading）。

| 类型 | 路径 |
|------|------|
| 原始结果 | `allure-results/single/` 或 `allure-results/P1/` |
| 静态副本 | `allure-report/single/`（可选备份） |
| 在线查看 | 由 `allure serve` 自动打开 |

不自动打开报告：

```powershell
python .cursor/skills/ui-auto-pytest-allure/scripts/run_ui_tests.py --test test_setting_password_idle_lock.py --no-open-report
```

手动查看（推荐）：

```powershell
allure serve allure-results/P1
```

### 6. capabilities 文件说明（建议使用 template + local）

能力文件加载优先级：

1. `APPIUM_CAPABILITIES`（环境变量，JSON 字符串）
2. `APPIUM_CAPABILITIES_FILE`（环境变量，文件路径）
3. `capabilities.local.json`（本地覆盖，**不提交**）
4. `capabilities.json`（旧版兼容）
5. `capabilities.template.json`（仓库模板）

首次运行时，如果没有 `capabilities.local.json`，会从 `capabilities.template.json` 自动生成一份。

## 用例步骤语法（摘要）

| 操作 | 示例 |
|------|------|
| 点击 | `步骤1: 点击 设置` / `步骤1: 点击 id:com.xxx:id/btn` |
| 设置开关 | `步骤4: 设置开关 id:com.xxx:id/switch 关闭` |
| 输入 | `步骤2: 输入 账号, demo_user` |
| 断言可见 | `步骤3: 断言 首页 可见` |
| 等待 | `等待 2秒` |
| 循环 | `循环步骤1-2 2次` |

完整说明见：`.cursor/skills/ui-auto-pytest-allure/reference.md`

## 当前示例用例

| 优先级 | 用例 | 说明 |
|--------|------|------|
| P1 | `setting_password_idle_lock` | 设置 → 密码与安全 → 电机锁 → 关闭空闲时锁电机 |

## 常见问题

**Q: GitHub 克隆后没有 `.tools/`？**  
A: 首次运行 `install_ui_dependencies.py` 会自动下载 Allure 与 JRE。

**Q: `allure-results` 里 JSON 可以删吗？**  
A: 生成 HTML 后可以删；下次跑测试会重新生成。

**Q: Inspector 报 instrumentation process is not running？**  
A: 执行 `repair_appium_session.py`，在 Inspector 中 **Attach to Session** 选择新 session，勿刷新旧标签页。

**Q: adb unauthorized？**  
A: 手机上允许 USB 调试，执行 `adb kill-server` 后 `adb devices`。

## 相关文档

- [表格批量导入](docs/CASE_IMPORT.md)
- [技能与脚本说明](.cursor/skills/ui-auto-pytest-allure/SKILL.md)
- [规格参考](.cursor/skills/ui-auto-pytest-allure/reference.md)

## License

Private / internal use — 按团队约定使用。
