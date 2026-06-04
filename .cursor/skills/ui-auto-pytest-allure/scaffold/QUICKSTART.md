# Skill 接收方快速上手（5 分钟）

## 前提

| 必装 | 说明 |
|------|------|
| Python 3.10+ | `python --version` |
| Node.js LTS | 含 npm，https://nodejs.org/ |
| adb | Android SDK platform-tools，已加入 PATH |
| Android 设备 | USB 调试已授权（`adb devices` 显示 `device`） |

## 步骤

```powershell
# 0. 将 ui-auto-pytest-allure 放到项目的 .cursor/skills/ 下

# 1. 初始化脚手架（只需一次）
python .cursor/skills/ui-auto-pytest-allure/scripts/uiatest_init.py --with-setup

# 2. 编辑被测 App（必做）
#    修改 capabilities.template.json 中的 appium:appPackage / appium:appActivity
#    或首次运行后编辑自动生成的 capabilities.local.json

# 3. 预检（连接手机后再跑，udid 会自动写入）
python uiatest.py doctor

# 4. 编写并运行
python uiatest.py gen cases/template.nl
python uiatest.py run --test test_<用例名>.py
```

## Cursor Agent 用户

对 Agent 说：**「初始化 UI 自动化并执行 setup」**，然后 **「doctor 检查环境」**，通过后再 **「运行 P1」**。

Agent 不得在未 `setup` 的机器上直接 `run`（会缺 Appium CLI）。

## 常见报错

| 报错 | 处理 |
|------|------|
| `Missing script: .../scripts/...` | 未复制 skill 或未 `init` |
| `Appium is not installed` | `python uiatest.py setup`（需 Node.js） |
| `placeholder udid` | 连接手机后重跑 `doctor` 或 `run` |
| `com.yourcompany.yourapp` | 改成真实包名/Activity |

详细说明：`.cursor/skills/ui-auto-pytest-allure/DISTRIBUTION.md`
