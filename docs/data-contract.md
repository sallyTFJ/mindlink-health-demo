# MindLink 多模态健康事件协议 v1

目标：让 EEG 脑电帽、手表、手动记录、体检报告和 AI 服务使用同一种可追溯数据结构。所有时间使用 ISO 8601，并保留时区。

## 通用事件

```json
{
  "schema_version": "1.0",
  "event_id": "uuid",
  "user_id": "pseudonymous-id",
  "device_id": "mindcap-eeg-001",
  "source_type": "eeg",
  "recorded_at": "2026-11-16T20:30:15.320+08:00",
  "received_at": "2026-11-16T20:30:15.480+08:00",
  "quality": {"score_0_100": 92, "flags": []},
  "consent_scope": "personal_wellness",
  "payload": {}
}
```

## EEG 实时窗口

```json
{
  "source_type": "eeg",
  "payload": {
    "sampling_rate_hz": 250,
    "channels": ["Fp1", "Fp2", "F3", "F4", "C3", "C4", "O1", "O2"],
    "window_seconds": 2,
    "band_power_uv2": {"delta": 12.4, "theta": 8.1, "alpha": 10.2, "beta": 6.8, "gamma": 1.4},
    "derived": {"focus_0_100": 74, "calm_0_100": 68, "fatigue_0_100": 31},
    "artifact_ratio": 0.04
  }
}
```

原始波形不进入通用事件总线；它应按短期加密文件或专用时序存储处理，事件只携带窗口特征与原始分片引用。眨眼、肌电、掉电极等伪迹必须进入 `quality.flags`。

## 可穿戴与体征

```json
{
  "source_type": "vitals",
  "payload": {
    "heart_rate_bpm": 72,
    "hrv_rmssd_ms": 46,
    "blood_pressure_mmhg": {"systolic": 118, "diastolic": 76, "method": "manual"},
    "glucose_mmol_l": {"value": 5.2, "context": "fasting"}
  }
}
```

## 日汇总

```json
{
  "source_type": "daily_summary",
  "payload": {
    "local_date": "2026-11-16",
    "steps": 8642,
    "active_minutes": 38,
    "sleep": {"total_minutes": 452, "deep_minutes": 91, "rem_minutes": 103, "score": 86},
    "mood": {"label": "calm", "valence_minus2_to2": 1, "energy_0_10": 7},
    "cycle": {"day": 12, "regularity": "regular"}
  }
}
```

## 设备网关

1. EEG 设备层：BLE GATT、USB 串口或厂商 SDK；
2. 手机/边缘层：时间同步、伪迹标记、窗口特征、本地加密缓存；
3. 网关层：HTTPS 批量上传 + WebSocket 低延迟事件；
4. 数据层：事件库、时序库、加密对象存储、不可变审计日志；
5. 智能体层：数据科学智能体只访问最小必要的去标识特征；健康领域智能体访问授权后的摘要；教练智能体不直接读取原始 EEG。

## 预警原则

- 单次越界只提示“复测/观察”，不直接给疾病标签；
- 预警需要持续性、信号质量和多模态交叉证据；
- 用户可查看“依据、置信度、缺失数据、下一步”；
- 高风险内容进入人工/专业服务分流，不由普通聊天模型独立处置。
