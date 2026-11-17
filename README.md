# 心脑灵犀 MindLink

> 看见身心同频，提前守护健康。

在线演示：<https://sallytfj.github.io/mindlink-health-demo/>

实时陪伴台（网页合成演示）：<https://sallytfj.github.io/mindlink-health-demo/live/>

当前版本：2026-11-18 已集成 ThinkGear EEG、标准 BLE 可穿戴桥、状态自报与可控中文语音陪伴。

项目仓库：<https://github.com/sallyTFJ/mindlink-health-demo>

![微信扫码体验 MindLink](MindLink-微信扫码体验.png)

心脑灵犀是一个面向日常健康管理的交互式 BCI + 可穿戴设备 + AI 智能体原型。它把 EEG、心率、HRV、睡眠、运动、情绪、血压、血糖、生理周期和体检资料放到统一时间线上，帮助用户理解趋势、形成微行动，并在持续异常时建议寻求专业帮助。

本仓库同时包含：

- `web/`：可安装的响应式 PWA 网站，支持桌面和手机浏览器；
- `miniprogram/`：原生微信小程序工程；
- `docs/`：数据协议、系统架构、比赛提交文案和商业化边界；
- `research/`：论文资料索引、官方来源、许可边界和下载校验信息。第三方原始归档不在本仓库重复发布。
- `live-demo/`：Windows 本地实时版，支持 ThinkGear EEG、标准 BLE 心率/血压、状态自报与可控中文语音陪伴。

## 快速体验

### 完全离线单文件版

直接双击项目根目录中的 `MindLink-离线版.html`。该文件已内嵌全部 CSS、JavaScript、Logo 和示例 JSON，不需要安装软件、启动服务器或连接互联网。论文与开源仓库链接属于可选外部链接，离线时不影响仪表盘、设备模拟、AI 演示、报告导入和自我探索功能。

### 网页

进入 `web` 目录，用任意静态服务器托管 `dist/`。不要直接双击 HTML，因为 Service Worker 和部分文件读取能力需要 HTTP 环境。

```powershell
cd web
python -m http.server 4173 --directory dist
```

浏览器打开 `http://localhost:4173`。网页不需要后端或 API Key 即可完成演示；“灵犀陪伴”当前使用安全的规则型演示回复。

也可以直接克隆本仓库：

```bash
git clone https://github.com/sallyTFJ/mindlink-health-demo.git
cd mindlink-health-demo
python -m http.server 4173 --directory web/dist
```

推送到 `main` 分支后，`.github/workflows/pages.yml` 会自动把 `web/dist/` 发布到 GitHub Pages。

### Windows 实时硬件演示

1. 进入 `live-demo/`，首次运行双击 `SETUP_WINDOWS.cmd` 安装本地依赖；
2. 无设备演示双击 `START_MINDLINK_DEMO.cmd`；
3. ThinkGear 脑电帽接入后，在 `config.json` 设置 COM 端口，再双击 `START_MINDLINK_LIVE.cmd`；
4. 标准 BLE 心率设备可运行 `START_WEARABLE_BRIDGE.cmd`；不能直接暴露标准 BLE 服务的手表需要官方健康平台或手机伴侣转发。

比赛现场建议先用合成模式完整演示，再切换真实设备。详细步骤与安全边界见 [实时陪伴台说明](live-demo/README_MINDLINK.md)。

### 微信小程序

使用微信开发者工具导入 `miniprogram/`。演示阶段可使用 `touristappid`；正式发布前替换为团队小程序 AppID，并完成隐私保护指引、业务域名与数据安全配置。

## 已实现能力

- 阳光治愈系品牌首页与原创 SVG 标识；
- EEG α 波、放松度、专注变化与心率实时合成数据流；
- 身心同频度、24 小时趋势、风险雷达与微行动；
- 睡眠、运动、心率、HRV、血压、血糖、生理周期、情绪概览；
- CSV / JSON 健康数据本地导入；
- PDF / 图片 / CSV / JSON 体检资料入口；
- 数据科学、健康领域、温暖教练三角色 AI 陪伴界面；
- 优势倾向、人格光谱、职业动力自我反思工具；
- PWA 安装、离线缓存和移动端底部导航；
- 微信小程序原生仪表盘、实时演示、AI 对话与报告导入。
- ThinkGear EEG 串口解码、标准 BLE 心率/血压桥、状态自报和浏览器中文语音陪伴；
- 保守分层提示：被动信号只提示暂停与自我确认，安全升级只由用户主动反馈触发。

## 论文与数据结论

本项目参考：Heydari, A. A. et al. *The anatomy of a personal health agent*. Nature 659, 197–207 (2026). DOI: `10.1038/s41586-026-11161-8`。

论文不是一份可直接商用的“全量健康大数据库”。官方公开内容分为三类：

1. Google Health PHA 框架、提示词、前后端、笔记本和约 365 天完全合成的可穿戴样例，Apache-2.0；
2. Nature 补充资料中的论文图表、评测结果和量表数据，仅限非商业研究使用；
3. WEAR-ME 全量 1,165 人数据，需要提交单独的数据访问申请，不能擅自下载或商用。

详见 [research-data-audit.md](docs/research-data-audit.md)。原始开源仓库的许可证和免责声明保留在 `research/consumer-health-research-main/personal_health_agent/`。

## 从原型到真实产品

真实硬件接入采用设备网关：EEG 脑电帽通过 BLE/USB/厂商 SDK 进入手机或边缘网关，手表数据通过厂商授权接口或 Health Connect / HealthKit 导入，统一转换为 [data-contract.md](docs/data-contract.md) 中的事件结构。AI 服务端再接入 PHA 的三个专家智能体。

正式商用前必须完成：

- 明确健康管理与医疗器械/互联网诊疗边界；
- 敏感个人信息单独同意、最小化收集、撤回、删除和导出；
- 端到端加密、密钥管理、访问审计、数据保留周期；
- 高风险内容分流、自伤危机升级、医生复核和模型安全评估；
- 设备精度、算法有效性、偏差与临床可用性验证；
- 不复制官方盖洛普 CliftonStrengths 题库或声称官方测评资质。

## 重要声明

当前版本是黑客松产品原型，不是医疗器械，不用于诊断、预后或治疗。页面中的用户、报告和健康数值全部为合成演示数据。出现胸痛、呼吸困难、意识改变、严重过敏或自伤风险等紧急情况，应立即联系当地急救与专业人员。

