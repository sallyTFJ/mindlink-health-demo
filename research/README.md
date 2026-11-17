# 研究资料获取说明

本目录只提交资料索引，不在本仓库重复发布约 98 MB 的第三方论文归档与数据文件。这样可以避免仓库膨胀，并保留上游项目各自的许可边界。

## 官方来源

- Nature 论文：<https://doi.org/10.1038/s41586-026-11161-8>
- Google Health 开源代码：<https://github.com/Google-Health/consumer-health-research/tree/main/personal_health_agent>
- Google Research 论文页：<https://research.google/pubs/the-anatomy-of-a-personal-health-agent/>
- Europe PMC 补充文件：<https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13736220/supplementaryFiles>

## 获取代码

```bash
git clone https://github.com/Google-Health/consumer-health-research.git
```

重点目录为 `personal_health_agent/`。其中 `data/sample/` 提供完全合成的可穿戴样例，可用于复现实验和原型开发。

## 许可边界

- Google Health 研究代码以其上游 Apache-2.0 许可证为准；
- Nature 补充评测数据注明仅限非商业研究使用；
- WEAR-ME 全量真实研究数据需要单独申请访问，未包含在本仓库中；
- 本项目网页中的人物与健康数值均为合成演示数据。

更完整的来源、校验值和使用结论见 [`../docs/research-data-audit.md`](../docs/research-data-audit.md)。

