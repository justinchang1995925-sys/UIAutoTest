P1
用例名: setting_password_idle_lock
标题: 设置-密码与安全-setting_password_idle_lock
功能: 设置
模块: 密码与安全

步骤1: 点击 id:com.pudutech.business.function:id/btnSettings，期望出现 密码与安全
步骤2: 点击 密码与安全，期望出现 电机锁
步骤3: 点击 电机锁，期望出现 id:com.pudutech.business.function:id/idle_lock_switch
步骤4: 设置开关 id:com.pudutech.business.function:id/idle_lock_switch 关闭，期望开关关闭
步骤5: 点击 id:com.pudutech.business.function:id/idle_lock_switch，期望开关切换
步骤6: 循环5-5,10次，期望出现 每次点击，开关状态都要发生切换
