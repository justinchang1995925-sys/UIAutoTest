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

**运行前自检**（依赖、adb 设备、Appium、capabilities、Allure CLI）：

```powershell
python uiatest.py doctor
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

加载优先级：`APPIUM_CAPABILITIES` 环境变量 → `capabilities.local.json` → `capabilities.json`（legacy 占位）→ `capabilities.template.json`。

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

# 本次运行前清空 allure-results（避免历史用例混入报告）
python uiatest.py run "运行P1测试用例" --fresh-results

# 除 allure serve 外，再生成静态 allure-report/ 副本
python uiatest.py run "运行P1测试用例" --static-report

# 需要跑完后自动 repair / 打开 Inspector 时（默认关闭，可省约 20s）
python uiatest.py run --priority P1 --auto-repair
```

依赖与 Allure CLI 已就绪时会**自动跳过 pip install**；日常回归建议不加 `--auto-repair`。

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

常用环境变量（可选）：

| 变量 | 说明 |
|------|------|
| `UIATEST_STEP_SETTLE_SEC` | 点击/输入/开关操作后等待 UI 稳定秒数（默认 `0.5`） |
| `UIATEST_POST_ASSERT_TIMEOUT` | 每步「预期结果」断言超时上限（默认 `8`，不超过步骤 timeout） |
| `UIATEST_APP_STARTUP_SEC` | driver 启动后等待 App 就绪秒数（默认 `0.5`） |
| `UIATEST_WARMUP=1` | 执行前预热等待首步元素可见（默认关闭，避免与第 1 步重复等待） |
| `UIATEST_STRICT_WARMUP=1` | 预热失败时直接失败 |
| `UIATEST_AUTO_REPAIR=1` / `--auto-repair` | 跑完后 repair Appium（默认关闭，省 ~20s） |
| `APPIUM_SKIP_U2_REPAIR=1` | teardown 时跳过 UiAutomator2 force-stop（快跑时可选） |
| `UIATEST_ALLURE_STATIC=1` | 等同 `--static-report` |
| `ANDROID_SERIAL` | 指定 adb 设备（多设备时） |
| `UIATEST_SCREENRECORD_ON_FAIL=1` | 失败时 adb 录屏并附加到 Allure |

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
# 一键清理（默认：allure-results、allure-report、logs、artifacts）
python uiatest.py clean

# 仅清原始结果
python uiatest.py clean --results

# 预览将删除的内容
python uiatest.py clean --dry-run
```

或手动：

```powershell
Remove-Item -Recurse -Force allure-results\* -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force allure-report\* -ErrorAction SilentlyContinue
```

**提示：** 若不想每次手动清理，运行时可加 `--fresh-results`，只清空当前优先级/单测对应的结果目录。

---

## 6. 查元素与排错（Appium Inspector）

Inspector 用于在 Android 设备当前界面上**查看控件树**，读取 `resource-id`、可见文本、class 等属性，便于编写用例中的定位信息。

**访问地址：** http://127.0.0.1:4723/inspector（需 Appium 已启动并加载 Inspector 插件）

---

### 6.1 前置条件

打开 Inspector 前请确认：

| 检查项 | 命令 / 说明 |
|--------|-------------|
| 项目目录 | 在 `D:\UIAutoTest` 下执行后续命令 |
| Android 设备 | USB 调试已开启，或已通过 `adb connect` 连接 |
| adb 可见设备 | `adb devices` 中至少一行以 `device` 结尾（非 `unauthorized` / `offline`） |
| Node.js / Appium | 已安装 Appium CLI（`appium --version` 有输出） |
| Inspector 插件 | 首次使用 PowerShell 脚本会自动安装；或手动：`appium plugin install inspector` |

可选自检：

```powershell
cd D:\UIAutoTest
python uiatest.py doctor
```

`doctor` 中 Appium 未就绪属正常（尚未启动）；设备与 capabilities 应通过。

---

### 6.2 一键打开（推荐）

在项目根目录执行**一条命令**即可（会自动启动 Appium、创建会话、**只打开一次** Inspector）：

```powershell
cd D:\UIAutoTest
python uiatest.py inspect
```

`inspect --powershell` 与上述命令等价（保留兼容旧用法）。

内部流程：Windows 下先通过 PowerShell 安装/启动 Appium（不打开浏览器）→ 创建健康 session → 打开 http://127.0.0.1:4723/inspector 。

成功时会输出 session id，在 Inspector 中选择 **Attach to Session** 附着即可查看控件。

---

### 6.3 分步手动打开（Appium 未运行或跨平台）

适用于需要逐步排查，或非 Windows 环境。

#### 步骤 1：连接设备

```powershell
cd D:\UIAutoTest
adb devices
```

Wi‑Fi 设备示例：

```powershell
adb connect 192.168.140.172:5555
adb devices
```

#### 步骤 2：启动 Appium（带 Inspector 插件）

**方式 A — 新开终端窗口（推荐）：**

```powershell
appium --use-plugins=inspector --allow-insecure=*:session_discovery --address 127.0.0.1 --port 4723
```

保持该窗口**不要关闭**；看到 `Appium REST http interface listener started` 即表示就绪。

**方式 B — 运行测试时自动启动（无 Inspector 插件）：**

```powershell
python uiatest.py run "运行P1测试用例" --no-open-report
```

此方式仅启动普通 Appium，**不能**直接打开 Inspector；仍需按步骤 3～5 单独处理。

#### 步骤 3：创建可 Attach 的会话

Appium 就绪后，在项目根目录执行：

```powershell
python uiatest.py repair --open-inspector
```

成功时会输出类似：

```text
Created healthy Appium session: e5ea9018-8ac0-49e0-8926-afdb9aeca822
Saved session info: D:\UIAutoTest\.appium-inspector-session.json
In Inspector: Session Builder -> Attach to Session -> select this session id.
```

会话信息保存在 `.appium-inspector-session.json`（本地文件，已在 `.gitignore` 中忽略）。

#### 步骤 4：在浏览器打开 Inspector

若 `repair --open-inspector` 未自动打开浏览器，手动访问：

```text
http://127.0.0.1:4723/inspector
```

也可使用统一 CLI（要求 Appium **已在运行**）：

```powershell
python uiatest.py inspect
```

等价于 `repair_appium_session.py --open-inspector`。

#### 步骤 5：Attach 到已有会话

在 Inspector 网页中：

1. 左侧选择 **Session Builder**（或顶部进入会话配置）  
2. 切换为 **Attach to Session**（附着到已有会话，而非新建）  
3. 在会话列表中选择步骤 3 输出的 **session id**  
   - 或打开 `.appium-inspector-session.json` 中的 `"session_id"` 字段  
4. 点击 **Attach Session** / 确认附着  

附着成功后，中间区域显示当前设备界面截图，右侧显示 **App Source** 控件树。

> **重要：** 不要刷新已失效的旧 Inspector 标签页。测试跑完后旧 session 会销毁，需重新执行 `python uiatest.py repair --open-inspector` 再 Attach 新 session。

---

### 6.4 在 Inspector 中查看控件

Attach 成功后：

1. 在设备上切换到要查的界面（Inspector 会随操作刷新，或点击 Inspector 上的刷新按钮）  
2. 在右侧 **App Source** 树中点击某个节点  
3. 查看 **Selected Element** 面板中的属性，常用字段：

| 属性 | 用途 |
|------|------|
| `resource-id` | 写入用例：`点击 id:com.xxx:id/btn` |
| `text` / `content-desc` | 写入用例：`点击 设置` 或 `点击 accessibility id:xxx` |
| `class` | 辅助判断控件类型（Button、TextView 等） |
| `bounds` | 查看坐标，一般不必手写 |

4. 需要验证点击时，可在 Inspector 中对选中元素执行 **Tap**，确认是否为预期控件  

---

### 6.5 将控件信息写入用例

查到 `resource-id` 后，在自然语言或 CSV 步骤中使用：

```text
步骤1: 点击 id:com.pudutech.business.function:id/tvSettings
```

仅有可见文字、无稳定 id 时：

```text
步骤2: 点击 密码与安全
```

导入 / 生成时，若设备已连接，工具会尝试 dump UI，将文字步骤解析为 **id 优先 + text 兜底** 的定位链。

---

### 6.6 修复会话与常见问题

#### 运行测试后 Inspector 无法刷新

测试结束会关闭 Appium session，Inspector 附着会失效。重新执行：

```powershell
python uiatest.py repair --open-inspector
```

然后在 Inspector 中 **Attach to Session** 选择新的 session id。

#### 提示「adb.exe 正由另一进程使用」/ Copy-Item 失败

adb 正在运行时，脚本**不会**再强制复制 `adb.exe` 到 `platform-tools`，会直接使用当前可用的 adb 路径。请重新执行：

```powershell
python uiatest.py inspect --powershell
```

若 Appium 刚启动，再执行 `python uiatest.py repair --open-inspector`。

#### 提示「Appium server is not ready」

- 确认步骤 2 的 Appium 窗口仍在运行  
- 浏览器访问 http://127.0.0.1:4723/status ，应看到 `"ready": true`  
- 等待数秒后重试 `python uiatest.py repair --open-inspector`

#### Inspector 页面空白或一直 Loading

- 勿用旧 session；重新 `repair --open-inspector`  
- 确认 `adb devices` 仍为 `device` 状态  
- 关闭 Appium 窗口后重新用 `--powershell` 或手动 `appium --use-plugins=inspector ...` 启动  

#### 多设备时 Attach 到了错误设备

指定 adb 设备后再 repair：

```powershell
$env:ANDROID_SERIAL = "0123456789"
python uiatest.py repair --open-inspector
```

或在 `capabilities.local.json` 中设置正确的 `appium:udid`。

#### 直接调用 PowerShell 脚本（与 `inspect --powershell` 等价）

```powershell
powershell -ExecutionPolicy Bypass -File .cursor/skills/ui-auto-pytest-allure/scripts/open_android_inspector.ps1
```

---

## 7. 最短上手示例

假设已按模板写好 `cases/my_cases.csv`：

```powershell
cd D:\UIAutoTest
python uiatest.py doctor
python uiatest.py import cases/my_cases.csv
python uiatest.py run "运行P1测试用例" --fresh-results
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
