# 手动使用指南（不依赖 Cursor Agent）

本文说明**不使用 AI Agent** 时，如何在本地完成：编写用例 → 生成脚本 → 运行测试 → 查看报告。

若你使用 Cursor Agent，只需把按规则填好的 Excel/CSV 交给 Agent，并说明「导入并运行 P1」即可；Agent 会代为执行下文中的命令。  
**自己操作时**，在项目根目录 `D:\UIAutoTest` 打开终端，按顺序执行即可。

---

## 流程总览

```text
编写用例（CSV / .nl）
        ↓
  import 或 gen（生成）
        ↓
  specs/*.json + generated-tests/ui/*/test_*.py
        ↓
  run（pytest + Appium）
        ↓
  allure serve（浏览器报告）
```

---

## 1. 一次性环境准备

### 1.1 安装项目依赖

```powershell
cd D:\UIAutoTest
python .cursor/skills/ui-auto-pytest-allure/scripts/install_ui_dependencies.py
```

将自动安装：pytest、allure-pytest、Appium-Python-Client，以及 `.tools/` 下的 **Allure CLI** 与 **JRE**。

也可使用统一 CLI 查看子命令：

```powershell
python uiatest.py --help
```

### 1.2 设备与 Appium

| 项目 | 要求 |
|------|------|
| Android 设备 | USB 调试已开启 |
| adb | `adb devices` 能看到 `device` 状态 |
| Appium | 运行脚本时会**自动启动**；也可手动运行 `appium` |

Wi‑Fi 连接（可选）：

```powershell
adb connect 192.168.140.172:5555
adb devices
```

### 1.3 Appium 能力配置

首次运行测试时，若没有 `capabilities.local.json`，会从 `capabilities.template.json` 自动生成一份（本地文件，不提交 Git）。

加载优先级：`APPIUM_CAPABILITIES` 环境变量 → `capabilities.local.json` → `capabilities.template.json`。

---

## 2. 编写用例

两种方式任选其一（也可混用）。

### 方式 A：Excel / 飞书表格（推荐批量）

1. 复制模板：`cases/import_template.csv`
2. 在 Excel 中编辑（模板为 **UTF-8 带 BOM**，双击打开中文不乱码）
3. 必填列：**用例等级、用例名、功能模块、子模块、操作步骤**
4. 推荐列：**预期结果**（与操作步骤逐行对应，生成每步断言）

飞书云表格：按相同表头填写 → **导出 CSV 或 Excel** → 放入 `cases/` 目录。

详细表头、预期结果写法见 [CASE_IMPORT.md](CASE_IMPORT.md)。

### 方式 B：自然语言 `.nl` 文件

在 `cases/` 下新建 `.nl`，参考：

- `cases/template.nl` — 模板
- `cases/setting_password_idle_lock.nl` — 完整示例

示例片段：

```text
P1
用例名: setting_password_idle_lock
标题: 进入设置-密码与安全-电机锁-关闭空闲时锁电机
功能: 设置
模块: 密码与安全

步骤1: 点击 id:com.pudutech.business.function:id/tvSettings，期望出现 密码与安全
步骤2: 点击 密码与安全，期望出现 电机锁
步骤3: 点击 电机锁
步骤4: 设置开关 id:com.pudutech.business.function:id/idle_lock_switch 关闭，期望开关关闭
```

步骤语法摘要见 [README.md](../README.md#用例步骤语法摘要) 与 [reference.md](../.cursor/skills/ui-auto-pytest-allure/reference.md)。

---

## 3. 生成测试脚本

生成后会得到三类文件：

| 输出 | 路径 |
|------|------|
| 自然语言用例 | `cases/<用例名>.nl` |
| JSON 规格 | `specs/<Px>/<用例名>.json` |
| pytest 脚本 | `generated-tests/ui/<Px>/test_<用例名>.py` |

### 3.1 从表格导入（CSV / xlsx）

**先预览**（不写文件）：

```powershell
python .cursor/skills/ui-auto-pytest-allure/scripts/import_cases_from_sheet.py cases/import_template.csv --dry-run
```

**正式生成**：

```powershell
python .cursor/skills/ui-auto-pytest-allure/scripts/import_cases_from_sheet.py cases/import_template.csv
```

统一 CLI：

```powershell
python uiatest.py import cases/your_cases.csv
```

设备已连接时，导入默认会 dump UI，将纯文字步骤尽量解析为 **id 优先 + text 兜底**。不需要时可加：

```powershell
python .../import_cases_from_sheet.py cases/xxx.csv --no-resolve-locators
```

Excel（`.xlsx`）需安装：`pip install openpyxl`

### 3.2 从 `.nl` 生成

```powershell
python .cursor/skills/ui-auto-pytest-allure/scripts/create_case_from_nl.py cases/setting_password_idle_lock.nl
```

统一 CLI：

```powershell
python uiatest.py gen cases/setting_password_idle_lock.nl
```

跳过 UI 定位解析：

```powershell
python .../create_case_from_nl.py cases/xxx.nl --no-resolve-locators
```

---

## 4. 运行测试

> **注意：** 请通过 pytest 运行，**不要**直接 `python test_xxx.py`。

### 4.1 自然语言指令（推荐）

```powershell
# 运行某优先级全部用例（如 P1）
python .cursor/skills/ui-auto-pytest-allure/scripts/run_ui_tests.py "运行P1测试用例"

# 运行单条用例（用例名或 test_ 文件名均可）
python .cursor/skills/ui-auto-pytest-allure/scripts/run_ui_tests.py "运行 setting_password_idle_lock"

# 先 adb connect 指定 IP:port 再运行
python .cursor/skills/ui-auto-pytest-allure/scripts/run_ui_tests.py "连接设备 192.168.140.172:5555 并运行P1测试用例"
```

### 4.2 统一 CLI `uiatest.py`

```powershell
python uiatest.py run "运行P1测试用例"
python uiatest.py run --test test_setting_password_idle_lock.py
python uiatest.py run --priority P1
python uiatest.py run --device 192.168.140.172:5555 --priority P1
```

### 4.3 参数形式（等价）

```powershell
python .cursor/skills/ui-auto-pytest-allure/scripts/run_ui_tests.py --priority P1
python .cursor/skills/ui-auto-pytest-allure/scripts/run_ui_tests.py --test test_setting_password_idle_lock.py
python .cursor/skills/ui-auto-pytest-allure/scripts/run_ui_tests.py --device 192.168.140.172:5555 --priority P1
```

### 4.4 运行时会自动完成

- 检查并安装 Python 依赖
- 启动 Appium（若未运行）
- 写入/更新 `capabilities.local.json` 中的设备 id
- 执行 `pytest`，结果写入 `allure-results/`
- 默认 `allure serve` 在浏览器打开报告

不自动打开报告：

```powershell
python .../run_ui_tests.py "运行P1测试用例" --no-open-report
```

---

## 5. 查看测试报告

| 类型 | 路径 | 说明 |
|------|------|------|
| 原始结果 | `allure-results/P1/` 或 `allure-results/single/` | pytest 写入的 JSON，**会随运行次数追加** |
| 在线报告 | 由 `allure serve` 打开 | **推荐**，不要用 `file://` 打开 `index.html` |
| 静态副本 | `allure-report/P1/` | `allure generate` 生成，可整目录删除 |

手动打开某次结果：

```powershell
allure serve allure-results/P1
```

### 清理报告（避免磁盘堆积）

```powershell
# 清原始结果（最重要，堆积源头）
Remove-Item -Recurse -Force allure-results\* -ErrorAction SilentlyContinue

# 清静态 HTML 副本（可选）
Remove-Item -Recurse -Force allure-report\* -ErrorAction SilentlyContinue
```

---

## 6. 查元素与排错（可选）

### 6.1 打开 Appium Inspector

```powershell
python uiatest.py inspect
```

或：

```powershell
powershell -ExecutionPolicy Bypass -File .cursor/skills/ui-auto-pytest-allure/scripts/open_android_inspector.ps1
```

在 Inspector 中查看 `resource-id`，写入用例：`步骤1: 点击 id:com.xxx:id/btn`。

### 6.2 修复 UiAutomator2 会话

```powershell
python uiatest.py repair --open-inspector
```

Inspector 中选择 **Attach to Session**，使用脚本输出的 session id，勿刷新已失效的旧标签页。

---

## 7. 最短上手示例

假设已按模板写好 `cases/my_cases.csv`：

```powershell
cd D:\UIAutoTest
python uiatest.py import cases/my_cases.csv
python uiatest.py run "运行P1测试用例"
```

若仓库中**已有**生成好的脚本（例如 P1 的 `test_setting_password_idle_lock.py`），只需运行：

```powershell
python uiatest.py run "运行P1测试用例"
```

---

## 8. 与 Agent 模式对比

| 步骤 | 使用 Cursor Agent | 手动操作 |
|------|-------------------|----------|
| 写用例 | 发送 Excel/CSV 或自然语言描述 | 编辑 `cases/import_template.csv` 或 `cases/*.nl` |
| 生成 | Agent 执行 import / gen | `python uiatest.py import ...` 或 `python uiatest.py gen ...` |
| 运行 | 「运行 P1 测试用例」等自然语言 | `python uiatest.py run "运行P1测试用例"` |
| 看报告 | Agent 触发 allure serve | 浏览器自动打开，或 `allure serve allure-results/P1` |

**记三个命令即可：** `uiatest.py import` → `uiatest.py gen`（二选一）→ `uiatest.py run`。

---

## 9. 相关文档

- [表格批量导入](CASE_IMPORT.md)
- [项目 README](../README.md)
- [用例规格参考](../.cursor/skills/ui-auto-pytest-allure/reference.md)
