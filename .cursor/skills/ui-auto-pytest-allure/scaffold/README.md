# UI 自动化项目（ui-auto-pytest-allure Skill）

## 首次使用（按顺序）

```powershell
python uiatest.py setup
python uiatest.py doctor
```

1. 安装 **Node.js LTS**（若 `doctor` 提示缺少 npm）
2. 手机 USB 连接并授权调试
3. 编辑 `capabilities.template.json` 中的 `appium:appPackage`、`appium:appActivity`（不要用占位符 `com.yourcompany.yourapp`）

更短说明见 [QUICKSTART.md](QUICKSTART.md)。

## 日常命令

```powershell
python uiatest.py gen cases/your_case.nl
python uiatest.py run --priority P1
python uiatest.py inspect
```

完整文档：`.cursor/skills/ui-auto-pytest-allure/DISTRIBUTION.md`
