# UI 自动化项目（由 ui-auto-pytest-allure Skill 初始化）

## 快速开始

```powershell
python uiatest.py doctor
python uiatest.py inspect
```

编辑 `capabilities.template.json` 中的 `appPackage` / `appActivity`，或生成 `capabilities.local.json` 覆盖设备 UDID。

编写用例：`cases/template.nl`，然后：

```powershell
python uiatest.py gen cases/your_case.nl
python uiatest.py run --priority P1
```

详细说明见：`.cursor/skills/ui-auto-pytest-allure/DISTRIBUTION.md`
