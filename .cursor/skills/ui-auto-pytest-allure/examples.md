# Examples

## Natural Language → Full Case

用户说：

```text
P1用例：设置里进入密码与安全，打开空闲时锁定电机开关

用例名: setting_idle_lock
步骤1: 点击 密码与安全
步骤2: 点击 密码
步骤3: 打开 空闲时锁定电机
```

生成命令：

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/create_case_from_nl.py cases/setting_password_lock.nl
```

或直接：

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/create_case_from_nl.py --text "P1
用例名: setting_idle_lock
标题: 设置-空闲锁定电机
步骤1: 点击 密码与安全
步骤2: 打开 空闲时锁定电机"
```

## Natural Language With Explicit Locators

```text
P0
用例名: login_success
标题: 登录成功

步骤1: 输入 id:com.example:id/username, demo_user
步骤2: 输入 id:com.example:id/password, 123456
步骤3: 点击 accessibility:Login
步骤4: 断言 id:com.example:id/home_title 可见
```

## Loop And Sleep

```text
P2
用例名: loop_demo
标题: 循环示例

步骤1: 点击 通用
步骤2: 点击 机器人功能
循环步骤1-2 3次
等待 2秒
```

## Chat-Only (Agent Writes Spec)

用户说：

```text
帮我写个 P0 用例：点击登录按钮（id 是 com.example:id/login），然后校验首页标题（id com.example:id/home_title）
```

Agent 直接写出 JSON spec，再执行：

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/generate_ui_test.py specs/P0/login_flow.json --output generated-tests/ui/P0
```

## Run Regression By Priority

用户说：

```text
运行P0测试用例
```

执行：

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/run_ui_tests.py "运行P0测试用例"
```

## Run Single Test File

用户说：

```text
运行test_setting_password_idle_lock.py
```

执行：

```bash
python .cursor/skills/ui-auto-pytest-allure/scripts/run_ui_tests.py "运行test_setting_password_idle_lock.py"
```

查看报告：

```bash
allure serve allure-results/P0
allure serve allure-results/single
```

## Open Element Inspector

```text
打开界面控件元素插件
```

```powershell
powershell -ExecutionPolicy Bypass -File .cursor/skills/ui-auto-pytest-allure/scripts/open_android_inspector.ps1
```
