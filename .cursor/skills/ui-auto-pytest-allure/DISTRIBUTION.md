# 仅用 Skill 分发给他人

把本目录 **`ui-auto-pytest-allure`** 复制到对方项目的：

```text
对方项目/
└── .cursor/
    └── skills/
        └── ui-auto-pytest-allure/    ← 整个文件夹
```

对方**不需要**克隆完整 UIAutoTest 仓库。

---

## 对方操作步骤（3 步）

### 1. 复制 Skill

- 压缩包：只发 `ui-auto-pytest-allure` 文件夹即可  
- 或用 Git 子目录拷贝到 `.cursor/skills/`

### 2. 初始化项目脚手架（只需一次）

在**项目根目录**打开终端（该目录将存放 `cases/`、`uiatest.py` 等）：

```powershell
python .cursor/skills/ui-auto-pytest-allure/scripts/uiatest_init.py
```

初始化完成后根目录会出现：

- `uiatest.py` — 统一 CLI  
- `capabilities.template.json` — Appium 配置模板  
- `cases/`、`specs/`、`generated-tests/ui/`（含 `_lib`、共享 `conftest.py`）  
- `README.md`、`.gitignore`

已有文件默认**不覆盖**；需重装脚手架时加 `--force`。

### 3. 环境与首次运行

**一键安装（推荐，需已安装 Node.js LTS）：**

```powershell
python uiatest.py setup
python uiatest.py doctor
```

`setup` 会自动：pip 安装 pytest/Appium 客户端、项目内 Allure CLI、**npm 全局 Appium + uiautomator2 驱动**。

若 `doctor` 提示缺少 npm，请先安装 Node.js：https://nodejs.org/  ，安装后**重新打开终端**再执行 `setup`。

按 `doctor` 提示连接 Android 设备，编辑 `capabilities.template.json`（或运行后自动生成的 `capabilities.local.json`）中的：

- `appium:appPackage` / `appium:appActivity`  
- `appium:udid`（或连接设备后由 `inspect` / 运行脚本写入 local 文件）

建议将“起始页面 Activity”写在 `capabilities.local.json`，并保持 `capabilities.template.json` 为占位模板，方便不同测试角色各自配置。

也可在运行时覆盖（会写入 `capabilities.local.json`）：

```powershell
python uiatest.py run --priority P1 --start-activity com.example.MainActivity
python uiatest.py run --priority P1 --start-package com.example.app --start-activity com.example.MainActivity
```

Agent 对话时也支持直接说明：

> 起始页面的appActivity名：com.example.MainActivity  
> 执行P1的测试用例

```powershell
python uiatest.py inspect
python uiatest.py gen cases/template.nl
python uiatest.py run --priority P1
```

报告：`allure generate` → `allure open allure-report/P1`（runner 默认自动执行）。表格同步与结果回写见项目内 `docs/CASE_IMPORT.md`（完整仓库）或 Skill 内 `reference.md`。

---

## 在 Cursor 里用 Agent（可选）

1. 用 Cursor 打开已复制 Skill 的项目文件夹  
2. 对 Agent 说：**「初始化 UI 自动化项目」** — Agent 应执行上面的 `uiatest_init.py`  
3. 之后可用自然语言：**「生成 P1 用例 …」「运行 P1 测试用例」**

Skill 的 `SKILL.md` 会指导 Agent 调用 `uiatest.py`，无需完整仓库。

---

## 仅 Skill 时不能省略的内容

| 必须 | 说明 |
|------|------|
| Skill 目录 | 含 `scripts/`、`scaffold/`、`SKILL.md` |
| 一次 `init` | 从 `scaffold/` 展开运行时代码与 CLI |
| 本机环境 | Python 3.10+、**Node.js/npm**、adb、Android 设备已授权 |

`init` 之后项目可独立提交到对方自己的 Git 仓库；`capabilities.local.json` 建议加入 `.gitignore`（脚手架已包含）。

---

## 常见问题

**Q: Agent 生成用例成功，但运行报 `Appium is not installed`？**  
A: Skill 只包含 Python 脚本，**不会自带 Appium 可执行文件**。对方机器需安装 Node.js，并执行 `python uiatest.py setup`（或手动 `npm install -g appium` + `appium driver install uiautomator2`）。Agent 首次在该机器跑用例前应先 `setup` + `doctor`。

**Q: 只复制了 skill，运行 `uiatest.py` 报错找不到？**  
A: 先执行 `uiatest_init.py`，或 `python uiatest.py init`（需已有 `uiatest.py` 时；首次用 init 脚本路径）。

**Q: 想更新 Skill 版本？**  
A: 覆盖 `.cursor/skills/ui-auto-pytest-allure`，再执行 `python uiatest.py init --force`（会覆盖脚手架文件，注意备份自定义的 `conftest`）。

**Q: 不用 Cursor 可以吗？**  
A: 可以，全程用 `python uiatest.py` 命令行即可。
