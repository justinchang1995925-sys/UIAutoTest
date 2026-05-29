# 录制预览（实时更新）

- 更新时间: 2026-05-29 10:36:25
- 用例名称: `setting_password_idle_lock`
- 用例等级: `P1`
- 已录制步骤: 4

## 文件说明

- `live_spec.json`：步骤与定位器（推荐手动修改这个文件）
- `live_test.py`：根据 spec 自动生成的 pytest 脚本预览

## 修改方式

1. 直接编辑 `live_spec.json` 中的 `steps`，然后运行：
   `python .cursor/skills/ui-auto-pytest-allure/scripts/refresh_recording_preview.py`
2. 或在对话里告诉 Agent：例如「把步骤2的 locator 改成 id=xxx」

## 当前步骤一览

### 步骤 1: Step 1 Tap id:com.pudutech.business.function:id/tvSettings

```json
{
  "name": "Step 1 Tap id:com.pudutech.business.function:id/tvSettings",
  "action": "tap",
  "locator": {
    "id": "com.pudutech.business.function:id/tvSettings"
  }
}
```

```python
# Step 1: Step 1 Tap id:com.pudutech.business.function:id/tvSettings
driver.find_element(..., "com.pudutech.business.function:id/tvSettings").click()  # id
```

### 步骤 2: Step 2 Tap 密码与安全

```json
{
  "name": "Step 2 Tap 密码与安全",
  "action": "tap",
  "locator": {
    "android_uiautomator": "new UiSelector().resourceId(\"com.pudutech.business.function:id/tv_name\").text(\"密码与安全\")"
  },
  "locators_fallback": [
    {
      "android_uiautomator": "new UiSelector().text(\"密码与安全\")"
    }
  ]
}
```

```python
# Step 2: Step 2 Tap 密码与安全
driver.find_element(..., "new UiSelector().resourceId("com.pudutech.business.function:id/tv_name").text("密码与安全")").click()  # android_uiautomator
```

### 步骤 3: Step 3 Tap 电机锁

```json
{
  "name": "Step 3 Tap 电机锁",
  "action": "tap",
  "locator": {
    "id": "com.pudutech.business.function:id/tv_motorLockTab"
  },
  "locators_fallback": [
    {
      "android_uiautomator": "new UiSelector().text(\"电机锁\")"
    }
  ]
}
```

```python
# Step 3: Step 3 Tap 电机锁
driver.find_element(..., "com.pudutech.business.function:id/tv_motorLockTab").click()  # id
```

### 步骤 4: Step 4 set switch id:com.pudutech.business.function:id/idle_lock_switch 关闭

```json
{
  "name": "Step 4 set switch id:com.pudutech.business.function:id/idle_lock_switch 关闭",
  "action": "set_switch",
  "locator": {
    "id": "com.pudutech.business.function:id/idle_lock_switch"
  },
  "state": "off"
}
```

```python
# Step 4: {"name": "Step 4 set switch id:com.pudutech.business.function:id/idle_lock_switch 关闭", "action": "set_switch", "locator": {"id": "com.pudutech.business.function:id/idle_lock_switch"}, "state": "off"}
```
