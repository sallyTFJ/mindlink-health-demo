# 队友接口说明

## 推荐只接 9080

启动 START_WINDOWS.cmd，默认监听 `http://127.0.0.1:9080`。第一次启动生成 `private/api.token`。以下业务请求需带 `Authorization: Bearer <该文件的内容>`；令牌不要放 URL、源码或报告里。

|方法|路径|用途|
|---|---|---|
|GET|/api/state|合并的实时设备状态、脑状态估计和心率|
|POST|/api/v1/infer|提交独立 5 秒窗口解码；不覆盖工作台实时状态|
|GET|/api/v1/model|模型版本、折、权重和原始模型说明|
|GET|/api/v1/health|进程健康，不代表设备或模型效果正常|
|GET|/api/ports|只枚举串口，不打开端口|
|GET|/api/example-input|取离线样例；source=offline|
|POST|/api/v1/check-in|主动反馈 calm / tense / overwhelmed / unsafe / task_complete|
|POST|/api/v1/wearable|写入本地 HR / BP / SpO2 事件，供厂商 SDK 或手机伴侣接入|

`/api/bootstrap` 是本机页面初始化用，远端不返回令牌。未认证 401，非法 Host 403，输入错误 400，不存在的接口 404。POST 使用 application/json，最多 1 MiB，不支持分块请求体。

## 第一个请求

在包根目录打开 PowerShell。以下每条命令均为一整行：

```powershell
$t=(Get-Content -Raw .\private\api.token).Trim(); Invoke-RestMethod -Uri 'http://127.0.0.1:9080/api/state' -Headers @{Authorization="Bearer $t"} | ConvertTo-Json -Depth 30
```

用随包 Python 每 5 秒读取一次：

```text
runtime\python.exe tools\client_example.py --token-file private\api.token --watch
```

提交离线窗口：

```text
runtime\python.exe tools\client_example.py --token-file private\api.token --input examples\attention_window.json
```

## /api/state 字段

字段可能随有效性减少，不能假定始终有分数。MindLink 优化版使用 `mindlink.state.v2`，并保留原始设备字段。

|字段|含义及使用方式|
|---|---|
|schema_version|本次独立包为 biosignal.state.v1；不是旧项目全部接口的兼容承诺|
|generated_at|状态快照生成的 Unix 秒；不表示设备刚更新|
|eeg.valid、eeg.age_s|RAW 是否新鲜及样本年龄；超过 1.5 秒失效|
|eeg.total|采集累计 RAW 数；重复值不能作为新数据|
|eeg.quality|ThinkGear 0–200，0 为该协议良好接触；未知值不送有效推理|
|eeg.raw、envelope|显示用降采样数组；最多 640 点、stride=4，原始 512Hz 的 5 秒窗口；含 null 表示缺失，不可用显示数组重做 512Hz 推理|
|eeg.source|serial 或 existing_eeg_http|
|brain_state.valid|模型窗口是否通过协议/质量检查，不是可信度或准确率|
|brain_state.attention_score|0–100 专注代理，未校准|
|brain_state.valence_score|-1–1 效价代理，未校准|
|brain_state.state_xy|原始模型二维坐标，具体键见原始输出样例|
|brain_state.display_xy|x=效价，y=专注；显示平滑，不应用来替代原始估计评估|
|brain_state.sample_time_end_unix_s|该预测对应的窗口结束时间，避免重复处理同一次预测|
|brain_state.source|device / external_live；离线推理另有 offline / public_replay|
|band_history|最多 60 条频段相对功率，随实际有效输入更新；顺序 δ、θ、α、β、γ|
|heart_rate|valid、bpm、age_s、source、received_unix_ms、history 等；超过 15 秒失效|
|ecg|目前固定 invalid，samples=null，原因 raw_ecg_not_integrated|
|blood_pressure|最近一次血压测量；30 分钟后过期，不伪装成连续实时值|
|spo2|最近一次血氧测量；5 分钟后过期|
|support|保守陪伴状态、语音文本、行动建议、依据及明确安全边界|
|wellness_score|展示用节律分数；不是医学评分或诊断|

## 主动反馈与可穿戴写入

主动反馈：

```json
{"kind":"tense","note":"可选备注，最多 280 字"}
```

可穿戴事件示例：

```json
{"event_type":"wearable.hr","source":"phone_bridge","received_unix_ms":1794900000000,"data":{"bpm":72,"sensor_contact":true}}
{"event_type":"wearable.bp","source":"vendor_health_sdk","received_unix_ms":1794900000000,"data":{"systolic":118,"diastolic":76}}
{"event_type":"wearable.spo2","source":"vendor_health_sdk","received_unix_ms":1794900000000,"data":{"percent":98}}
```

`unsafe` 是用户主动反馈，不是模型预测。被动 EEG/心率组合变化最多产生 `notice`，不会产生紧急判断。

任何一路 valid=false，后端应传递缺失状态，不用 0 替代生理值，不继续沿用上次的“情绪”。导出按钮保存当前快照，不是自动向外推送。

## /api/v1/infer 输入与输出

输入模板见 `examples/attention_window.json` / `valence_window.json`：

```json
{"fs_hz":512,"channel":"Fp1","unit":"neurosky_counts","source":"device","quality":0,"samples":[0,1,2],"request_id":"your-window-id"}
```

上面 samples 只展示格式，实际必须正好 `5 * fs_hz` 个有限数值（512 Hz 需要 2560 点）；不能发送这个三点示例当完整请求。counts 必须有符号 16 位整数，且只支持 512 Hz。uV 支持 128/250/256/512 Hz。source 必填，不得把回放/模拟数据标成真实设备。quality=0 才能产生有效推理，时间字段 sample_time_end_unix_s 可选。

输出包括 schema_version、model_version、fold、source、valid、reason、attention_score、attention_class、valence_score、state_xy、inference_ms。完整固定离线预期见 examples/*_expected_output.json；时间/耗时会变。该接口是按调用方声明解释窗口，不负责证明外部窗口真的实时；调用方必须维护样本顺序和时间。

## 队友在另一台电脑

1. Windows 修改 config.json：host 为 0.0.0.0，重启工作台；原 port=9080 保持。
2. 两台电脑在同一可信局域网；用 ipconfig 确认 Windows 的 IPv4，防火墙只允许所需专用网络上的 TCP 9080。
3. 单独交给指定队友这次新生成的令牌。他在自己后端请求 `http://<Windows局域网IP>:9080/api/state`，携带 Bearer。
4. 可以 1 秒轮询显示波形，每 5 秒取业务状态；按样本时间/累计计数去重，而非每次轮询都生成决策。

工作台不允许任意跨域浏览器读取接口；队友用自己的后端转发，或者直接访问 Windows 工作台页面并输入令牌。不同 WiFi 且不互通时，另建团队 VPN 或由新团队部署认证 HTTPS 中继；本包不预置任何旧云地址，也不承诺公网直连。不要直接把明文 HTTP 端口暴露到公网。

## 8876 与可选 8881 的区别

- 8876 是旧 EEG 采集网页的 HTTP 端口，不是 COM 端口。新包 serial 模式不依赖它。
- http 模式读 8876 的 `/api/state`，需要 live、connected、quality、age、dt=1/512、raw_original、times、raw_mask、gaps、session_id、total；连续 2560 点，mask=false、无窗口内缺口、接触良好。不是所有旧版本都提供这些字段，缺失时不会冒充有效解码。优先用自带 serial 模式。
- 可选 `START_MODEL_API_OPTIONAL.cmd` 启动原始模型 API 8881，仅本机监听，无 Bearer，不可通过反向代理直接公开。完整定义见 `docs/model_openapi.json`。支持窗口/stream 接口，供已有自建采集程序研究集成。
- `tools/serial_bridge_reference.py` 是 COM→8881 的参考桥。不要与工作台 serial 同时打开同一个 COM。8881 的流状态不会自动填充 9080 工作台。
- 本次接口精简为信号交接，不包含旧项目 state_json/decision_json 对话决策、云网关和业务回调；新项目应以本文为准。
