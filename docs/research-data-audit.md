# Nature PHA 开源资料审计

审计日期：2026-11-16（Asia/Shanghai）

## 官方来源

- 论文：<https://doi.org/10.1038/s41586-026-11161-8>
- Google Health 论文代码：<https://github.com/Google-Health/consumer-health-research/tree/main/personal_health_agent>
- Google Research 论文页：<https://research.google/pubs/the-anatomy-of-a-personal-health-agent/>
- Europe PMC 补充文件接口：<https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13736220/supplementaryFiles>

## 本地归档

### 官方代码仓库

- 下载包：`research/consumer-health-research-main.zip`
- SHA-256：`9B3C9F5F8772EB4D4ACE47626E3BB39680562818368E8C99B5D7DA2C24659B97`
- 解压目录：`research/consumer-health-research-main/`
- 主要许可：Apache License 2.0
- 官方免责声明：演示研究代码，不是医疗器械，也不用于任何临床用途。

`personal_health_agent/data/sample/` 只有四类合成 CSV：

| 文件 | 内容 | 性质 |
| --- | --- | --- |
| `summary.csv` | 约 365 天步数、睡眠、心率、HRV 等日汇总 | 完全合成 |
| `activities.csv` | 运动事件 | 完全合成 |
| `profile.csv` | 单个虚构用户资料 | 完全合成 |
| `population_percentiles.csv` | 年龄/性别人群百分位参考样例 | 演示参考，不是临床数据库 |

### Nature/PMC 补充资料

- 下载包：`research/nature-supplementary/europepmc-supplementary.zip`
- SHA-256：`CCCEA9A8603E6EEC3101A89055E0645A4307DB1F475C28D9A727020B88B83A7C`
- 有效 ZIP 大小：10,363,797 bytes
- `MOESM1`：Supplementary Information PDF；
- `MOESM2`：Reporting Summary PDF；
- `MOESM3`：Peer Review File PDF；
- `MOESM4`：研究评测 CSV 数据。

`MOESM4` 解压后的 README 明确限定为 **non-commercial research use only**。因此这些 CSV 仅保存在 `research/` 中用于论文复现和设计参考，没有被复制进可部署网页，也不得作为商业产品训练数据、临床决策数据或收费服务数据。

## 不可直接获取或商用的内容

论文说明 WEAR-ME 研究共 1,165 人，包含可穿戴纵向数据、血液检测和问卷。全量数据需要完成论文指定的数据访问申请。公开论文页面还提到 50 persona 子集和 2,000 条去标识症状数据，但在本次下载到的 `main` 分支中没有发现可直接使用的相应原始文件；不能仅凭论文描述推定已获得使用权。

结论：当前项目可以合法、安全地使用 Apache-2.0 研究代码和完全合成样例进行原型展示；Nature 补充评测 CSV 只能用于非商业研究；真实商业产品应使用用户明确授权的自有设备数据，或另行获得合规数据许可。
