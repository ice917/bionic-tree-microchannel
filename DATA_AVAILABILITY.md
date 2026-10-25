# Data Availability Statement（数据可用性声明模板）

> 投稿时按期刊要求把对应语言的一段贴进论文（IJHMT / Applied Thermal Engineering
> 等 Elsevier 期刊用英文，正文 References 之前新增「Data Availability」节）。
> DOI 与仓库 URL 均已回填为真实值（v1.0.0 记录 23620419、v1.0.1 记录 23621256、
> v1.0.2 记录 23622141、v1.0.3 记录 23622506、v1.0.4 记录 23622840、
> v1.0.5 记录 23631211，分别于 2026-10-24 / 2026-10-25 发布；v1.0.5 为本轮投稿版本）。
> 概念 DOI `10.5281/zenodo.23620418` 始终指向最新归档版本。

## English（英文版，供 Elsevier 期刊）

**Data Availability**

The source code and all numerical artefacts that support the findings of this
study — including the Python/MATLAB reproduction scripts, the raw results in
`outputs/` (JSON/CSV/TXT files), the figures (PNG), and the manufacturable
geometry (STL) — are openly available in the Zenodo repository at
`https://doi.org/10.5281/zenodo.23620418` (concept DOI, which always resolves to the
latest archived version; each archived snapshot also carries its own version DOI,
for example `https://doi.org/10.5281/zenodo.23631211` for v1.0.5 (the version
submitted with this manuscript),
`https://doi.org/10.5281/zenodo.23622840` for v1.0.4,
`https://doi.org/10.5281/zenodo.23622506` for v1.0.3,
`https://doi.org/10.5281/zenodo.23622141` for v1.0.2,
`https://doi.org/10.5281/zenodo.23621256` for v1.0.1 and
`https://doi.org/10.5281/zenodo.23620419` for v1.0.0) and in the GitHub repository at
`https://github.com/ice917/bionic-tree-microchannel`. The code is
licensed under MIT (`LICENSE`); the data and documentation are licensed under
CC BY 4.0 (`LICENSE-DATA`). Every number in the manuscript is loaded at run time
from these artefacts and can be reproduced end-to-end by running the commands
listed in the Appendix ("Reproduction Commands"); the SHA-256 checksums of all
distributed files are recorded in `MANIFEST.sha256`. The three Simulink models
(`*.slx`) are distributed as part of the repository but are excluded from that
checksum list, because an `.slx` package embeds per-save timestamps and
randomly generated model/schedule UUIDs, so its byte-level hash changes on
every rebuild even when the modelled system is unchanged. Reproducibility of
the electrical model is instead guaranteed by the network construction code
(`chip_route_iso.m`) and by the solver-agreement diagnostics written to
`outputs/chip_route_iso_summary.txt`.

## 中文（对照版）

**数据可用性**

支撑本研究发现的源代码与全部数值工件——包括 Python/MATLAB 复现脚本、`outputs/`
下的原始结果（JSON/CSV/TXT）、图（PNG）与可制造几何（STL）——已在 Zenodo 仓库
`https://doi.org/10.5281/zenodo.23620418`（概念 DOI，始终指向最新归档版本；各归档快照
另带版本 DOI，例如 v1.0.5 为 `https://doi.org/10.5281/zenodo.23631211`（本轮投稿版本）、
v1.0.4 为 `https://doi.org/10.5281/zenodo.23622840`、v1.0.3 为
`https://doi.org/10.5281/zenodo.23622506`、v1.0.2 为
`https://doi.org/10.5281/zenodo.23622141`、v1.0.1 为
`https://doi.org/10.5281/zenodo.23621256`、v1.0.0 为
`https://doi.org/10.5281/zenodo.23620419`）与 GitHub 仓库
`https://github.com/ice917/bionic-tree-microchannel`
开放获取。代码采用 MIT 许可
（`LICENSE`），数据与文档采用 CC BY 4.0（`LICENSE-DATA`）。本文全部数值均在运行时
从这些工件加载，可依据附录「复现命令」端到端复现；所有随附文件的 SHA-256 校验值
记录于 `MANIFEST.sha256`。三个 Simulink 模型（`*.slx`）随仓库分发，但不纳入该校验
清单：`.slx` 包内含每次保存的时间戳与随机生成的模型/调度 UUID，即使所建模的系统
完全未变，其字节级哈希也会在每次重建后改变。该电路模型的可复现性改由网络构建代码
（`chip_route_iso.m`）与写入 `outputs/chip_route_iso_summary.txt` 的求解器一致性
诊断量保证。

## 提交前待办（占位符清单）

1. ~~作者姓名、单位、ORCID~~（已填：Haoran Wu / Wuchang University of Technology / 0009-0005-1975-1511）。
2. ~~Zenodo DOI~~（已填：概念 DOI `10.5281/zenodo.23620418`（引用用）；v1.0.5 版本 DOI `10.5281/zenodo.23631211`（记录 23631211，2026-10-25T02:02:10Z 发布，`metadata.version=1.0.5`；本轮投稿版本）；v1.0.4 版本 DOI `10.5281/zenodo.23622840`（记录 23622840，2026-10-24T16:58:39Z 发布，`metadata.version=1.0.4`；内容与 v1.0.3 相同，仅修正 `.zenodo.json` 版本字段）；v1.0.3 版本 DOI `10.5281/zenodo.23622506`（记录 23622506，2026-10-24T16:36:43Z 发布；该记录 `metadata.version` 误为 `1.0.2`，见 `REPORTING_COMPLIANCE.md` §5 项 17）；v1.0.2 版本 DOI `10.5281/zenodo.23622141`（记录 23622141，2026-10-24T16:14:08Z 发布）；v1.0.1 版本 DOI `10.5281/zenodo.23621256`（记录 23621256，2026-10-24T15:29:28Z 发布）；v1.0.0 版本 DOI `10.5281/zenodo.23620419`（记录 23620419，2026-10-24T14:45:14Z 发布，不含 AI 声明）。）
3. ~~GitHub 仓库 URL~~（已填：https://github.com/ice917/bionic-tree-microchannel，main 分支已推送）。
4. ~~`.zenodo.json` 的 `version` 由 `0.1.0-draft` 改为正式版本号~~（v1.0.0 已发布；现为 `1.0.5`）。
