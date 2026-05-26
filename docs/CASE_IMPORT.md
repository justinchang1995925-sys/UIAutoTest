# 用例表格批量导入规范

支持从 **Excel（.xlsx）** 或 **CSV** 批量导入用例。飞书云表格可先 **导出为 CSV 或 Excel** 再导入。

## 表头（必填）

| 列名 | 对应 NL 规则 | 说明 |
|------|----------------|------|
| 用例等级 | `P0`～`P4` | 决定生成目录 `specs/Px/`、`generated-tests/ui/Px/` |
| 用例名 | `用例名:` | 英文标识，如 `setting_password_idle_lock` |
| 功能模块 | `功能:` | Allure feature，如 `设置` |
| 子模块 | `模块:` | 子模块名，如 `密码与安全` |
| 操作步骤 | `步骤1:`… | 多行文本，每行一条操作 |

可选列：`标题`、`套件`

## 操作步骤写法

单元格内 **一行一步**，无需写「步骤1」前缀（会自动编号）。也可保留完整格式：

```text
点击 id:com.pudutech.business.function:id/tvSettings
点击 密码与安全
点击 电机锁
设置开关 id:com.pudutech.business.function:id/idle_lock_switch 关闭
```

支持的步骤动词与 `cases/*.nl` 相同：

| 操作 | 示例 |
|------|------|
| 点击 | `点击 设置` / `点击 id:com.xxx:id/btn` |
| 设置开关 | `设置开关 id:com.xxx:id/switch 关闭` |
| 打开/关闭开关 | `打开开关 空闲时锁电机` |
| 输入 | `输入 账号, demo_user` |
| 断言 | `断言 首页 可见` |
| 断言文字 | `断言文字 提示, 成功` |
| 等待 | `等待 2秒` |
| 循环 | `循环步骤1-2 2次` |

## 飞书云表格

1. 按上表创建列：用例等级、用例名、功能模块、子模块、操作步骤  
2. 操作步骤列使用单元格内换行（Alt+Enter）  
3. 菜单：**下载为 CSV** 或 **下载为 Excel**  
4. 在项目根目录执行导入命令  

## 导入命令

```bash
cd D:\UIAutoTest

# 仅预览解析结果
python .cursor/skills/ui-auto-pytest-allure/scripts/import_cases_from_sheet.py cases/import_template.csv --dry-run

# 生成 .nl + specs + pytest
python .cursor/skills/ui-auto-pytest-allure/scripts/import_cases_from_sheet.py cases/import_template.csv

# 只生成 .nl 文件
python .cursor/skills/ui-auto-pytest-allure/scripts/import_cases_from_sheet.py cases/import.csv --nl-only
```

Excel 需安装：

```bash
pip install openpyxl
```

## 模板文件

- CSV 模板：`cases/import_template.csv`  
- NL 单条模板：`cases/template.nl`  

## 测试报告（HTML）

跑完用例后 `run_ui_tests.py` 会默认把 `allure-results/` 里的 JSON 生成 HTML 并自动打开浏览器：

- 单条用例：`allure-report/single/index.html`
- 按等级：`allure-report/P1/index.html`

安装 Python 依赖时会**自动完成**（无需手动配置）：

| 组件 | 安装位置 | 环境变量 |
|------|----------|----------|
| Allure CLI | `.tools/allure-2.32.2/` | 用户 `PATH`、`ALLURE_HOME` |
| JRE 17（Allure 依赖） | `.tools/jdk-17-jre/` | 用户 `JAVA_HOME` |

项目内快捷脚本：`allure-env.cmd` / `allure-env.ps1`（在当前终端注入 PATH）

不打开 HTML 报告时加 `--no-open-report`。

手动重装：

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/install_allure_cli.py
python .cursor/skills/ui-auto-pytest-allure/scripts/install_ui_dependencies.py
```

## 生成结果

每条表格行会生成：

- `cases/<用例名>.nl`
- `specs/<等级>/<用例名>.json`
- `generated-tests/ui/<等级>/test_<用例名>.py`

## 表头别名（兼容飞书/Excel 微调列名）

| 标准列 | 可识别别名 |
|--------|------------|
| 用例等级 | 等级、优先级、priority |
| 用例名 | 用例名称、test_name |
| 功能模块 | 功能、feature |
| 子模块 | 模块、module |
| 操作步骤 | 步骤、steps、用例步骤 |
