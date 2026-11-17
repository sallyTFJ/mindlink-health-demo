# 心脑灵犀 MindLink · 实时陪伴台

这是由 Biosignal Team Kit 优化而来的 Windows 本地演示版，保留了原有 ThinkGear EEG 解码、ONNX 研究模型和标准 BLE 心率采集能力，并新增温暖界面、多模态趋势提示、主动状态反馈与中文语音陪伴。

## 30 秒比赛演示

1. 双击 `START_MINDLINK_DEMO.cmd`。
2. 浏览器会打开 `http://127.0.0.1:9080/`，页面上所有数值均明确标为“合成演示”。
3. 点击“开启语音陪伴”。
4. 点击“我有点紧绷”，演示低负担安抚；点击“我完成了难事”，演示肯定与鼓励。
5. 点击“我现在不安全”，演示只基于主动反馈触发的真人支持步骤。

演示模式不会打开串口、蓝牙或读取真实人体数据。

## 真实 EEG 与手表

1. 双击 `EDIT_SETTINGS.cmd`，将 `eeg_mode` 改为 `serial`，并把 `eeg_com` 改为 ThinkGear 的实际 COM 端口。
2. 双击 `START_MINDLINK_LIVE.cmd`，确认 EEG RAW 总数持续增长、接触质量为 0，并等待连续 5 秒有效窗口。
3. Apple Watch：在手表/手机启动 HeartCast，再双击 `START_WEARABLE_BRIDGE.cmd`。
4. 其他支持标准 BLE Heart Rate / Blood Pressure Service 的设备，也可由 `wearable_bridge.py` 按名称或地址连接。
5. 华为健康、Apple Health 等不向 Windows 直接暴露标准 BLE 的平台，需要官方 SDK/健康平台或手机伴侣应用，把数据 POST 到 `/api/v1/wearable`。

“任意品牌”意味着提供统一接入协议，不意味着所有手表都能绕过厂商权限直接蓝牙连接。

## 安全边界

- EEG 的 attention/valence 是未校准研究代理分数，现有证据不足以可靠识别焦虑、抑郁、躁狂、癫痫或伤害意图。
- 被动信号只能触发“暂停并自我确认”的低风险提示；紧急安全步骤只能由用户主动选择“我现在不安全”触发。
- 浏览器语音由用户首次点击后启用，有 45 秒自动提示冷却时间。
- 软件不会自动拨号、发消息或控制电刺激设备。
- 局部电刺激不提供参数、放置位置或自动控制；仅能在合规设备说明和专业人员指导下由本人主动操作。

## 数据流

```text
ThinkGear EEG → COM → 校验/连续窗口 → ONNX 研究代理分数 ┐
标准 BLE/手机伴侣 → wearable.jsonl → HR/BP/SpO2       ├→ 本地状态 → 保守趋势提示 → 可控语音
主动状态反馈 → /api/v1/check-in                        ┘
```

所有本地接口默认使用 Bearer 令牌，首次运行生成在 `private/api.token`。不要把该令牌、`data/` 或个人记录提交到 GitHub。

## 关键文件

- `START_MINDLINK_DEMO.cmd`：合成数据一键演示。
- `START_MINDLINK_LIVE.cmd`：真实 EEG/可穿戴本地服务。
- `START_WEARABLE_BRIDGE.cmd`：标准 BLE 可穿戴桥。
- `app/coach.py`：趋势与安全分层逻辑。
- `app/wearable.py`：HR/BP/SpO2 数据验证与新鲜度管理。
- `web/`：暖色实时陪伴界面和本机语音。
- `docs/API.md`：完整接口说明。

本项目用于黑客松原型与研究展示，不是医疗器械，不替代医生、心理专业人员或当地紧急服务。

公开发布或商业化前，请同时阅读 `PROVENANCE_AND_LICENSE.md` 并确认原始代码、模型权重与设备 SDK 的授权范围。
