# 报告合规性对照（B2）

核验日期：2026-10-24（第五次核验＝v1.0.2 归档后回填；此前为同日第四次、第三次、第二次与 2026-10-18 首次）
核验对象：本仓库工作树（`main` 分支；本次核验起点 HEAD `bf7eaee`，即 tag `v1.0.2` 所指提交；`git status --porcelain` 在回填前显示 3 项未提交：`CITATION.cff`、`DATA_AVAILABILITY.md`、`README.md`，三处改动均为归档后 DOI 回填。此前：第四次核验起点 HEAD `9057b63`，9 项未提交）
判定对象：论文《仿生自适应网络用于芯片散热与布线》及其随附数据与代码

**归档回填注记（2026-10-24 第五次核验）**：v1.0.2 已发布并完成归档，本节所记均为归档后的实测值，逐项可复核。发布链：提交 `bf7eaee`（`release: v1.0.2 —— 协议载体指认、数据集引用改引概念 DOI、托管状态改为非穷尽表述`）→ annotated tag `v1.0.2`（指向 `bf7eaee`）→ GitHub Release id `422838019` → Zenodo 记录 **`23622141`**。记录实测字段：`status=published`、`created=2026-10-24T16:14:07.999332+00:00`、`version=1.0.2`、`doi=10.5281/zenodo.23622141`、`conceptdoi=10.5281/zenodo.23620418`、`creators=['Wu, Haoran']`、`license.id=other-open`、`files=[('ice917/bionic-tree-microchannel-v1.0.2.zip', 35300596, 'md5:7d04a45e2d87f5aabdc7f0af42929670')]`、`related_identifiers` 含 GitHub tag `v1.0.2`（`isSupplementTo`）。归档包实测：zip 187 个文件、tag `v1.0.2` 187 个文件、逐 blob 内容 **187 相同 / 0 不同**、包内 `MANIFEST.sha256` **183/183 吻合**、`src_extract/`+`参考论文/`+`_work/` 命中 **0**；包内 IJTS 稿 234 段、`[21]` 2 处、概念 DOI `23620418` 2 处、**自身版本 DOI `23622141` 0 处**（时序约束的实测印证）。概念 DOI `10.5281/zenodo.23620418` 现经 `zenodo.org/doi/…` **302 → `https://zenodo.org/records/23622141`**。自本次回填起，`main`（回填工作树）与归档快照（tag `v1.0.2`）仅在 `CITATION.cff`、`README.md`、`DATA_AVAILABILITY.md`、本文件与 `MANIFEST.sha256` 这几个元数据/清单文件上不同；数值工件与稿件完全相同（`git diff --name-status v1.0.2 -- outputs 论文` 实测 0 行，见 §5 项 16）。

**版本注记（2026-10-24 第四次核验）**：本次核验做三件事——(i) 在论文 §19 指认协议载体 `DEFECT_REMEDIATION_PLAN.md`，据 TOP 2025 的"公开托管 + 持久标识 + 参考文献引用"三项条件把第 2 项 Study Protocol 由 Level 1 改判 Level 2；(ii) 把参考文献 [21] 由 v1.0.1 版本 DOI 改为概念 DOI `10.5281/zenodo.23620418`，使 v1.0.2 归档稿所引条目能解析回包含该条目自身的快照（v1.0.1 版本 DOI 的实测缺陷见 §5 项 15）；(iii) 修正 `README.md` 中"`CITATION.cff` 尚未创建"这一已被第三次核验推翻的陈述，并把版本号与托管状态改为非穷尽表述，为 v1.0.2 归档做准备。第三次核验（2026-10-24）闭环了参考文献数据集条目（[21]）、`CITATION.cff`（B2-03）与研究未注册声明（B2-09）。第二次核验（2026-10-24）按 Zenodo 记录 `23620419`（v1.0.0，2026-10-24T14:45:14Z 发布）与 `23621256`（v1.0.1，2026-10-24T15:29:28Z 发布）实测值回改。凡保留的历史值一律以"（此前：…）"标注，不作静默替换。

本文件只回答一个问题：**按公开的期刊透明性标准，本项目现在处于哪一级，缺什么。**
所有等级均按论文层面判定；仓库层面的补充事实单列。凡无仓库内证据支持的，一律标为"未声明"，不按"应该已经具备"推定。

---

## 1. 判定依据（外部标准原文）

| 编号 | 标准 | 本项目采用的具体条款 | 来源 |
|---|---|---|---|
| S1 | TOP Guidelines（2025 版） | 七项 Research Practices：Study Registration、Study Protocol、Analysis Plan、Materials Transparency、Data Transparency、Analytic Code Transparency、Reporting Transparency；三级：Level 1 Disclosed / Level 2 Shared and Cited / Level 3 Certified；另有 Results Transparency、Computational Reproducibility 两项 Verification Practices | Center for Open Science, <https://www.cos.io/initiatives/top-guidelines>；Grant et al., *Research Integrity and Peer Review*, DOI 10.1186/s41073-026-00223-0 |
| S2 | *Science* Journals Editorial Policies | 执行 TOP；Citation standards 要求"All data, program code, and other methods must be appropriately cited using digital object identifiers (DOIs), journal citations, or other persistent identifiers"；另设 Data and Code Deposition 条款 | <https://www.science.org/content/page/science-journals-editorial-policies> |
| S3 | Nature Portfolio Reporting Standards | "All published manuscripts reporting original research in Nature Portfolio journals must include a data availability statement"；代码须单列 "Code availability"（位于 data availability 之后、参考文献之前）；"Code should be deposited in a DOI-minting repository such as Zenodo or Code Ocean and cited in the reference list"；鼓励使用 OSI 认可许可证；"authors are required to make materials, data, code, and associated protocols promptly available to readers without undue qualifications" | <https://www.nature.com/nature-portfolio/editorial-policies/reporting-standards> |

**版本差异必须写明**：TOP 2015 为 8 项标准（含 Citation standards、Replication），TOP 2025 重组为 7 项研究实践 + 2 项验证实践。本文件采用 2025 版七项，以免把 2015 版的 8 项与 2025 版的 7 项混为一谈。*Science* 的编辑政策页面仍按 TOP 框架列示引用与数据标准，故 S1 与 S2 需同时满足。

### 1.1 等级的操作化定义

| 等级 | 定义 | 本项目判定口径 |
|---|---|---|
| 未达 L1 | 论文或仓库均未声明该对象是否存在、位于何处 | 仅"本地有文件"不算披露 |
| L1 披露 | 明确声明是否存在、在哪里、何时可得 | 论文正文或 README/数据字典的显式声明 |
| L2 共享并引用 | 在可信仓库公开托管，有持久标识（DOI），并在参考文献中引用 | 仅"计划上传 Zenodo"不算 L2 |
| L3 认证 | 独立于作者的第三方认证 | 本项目无任何第三方认证 |

---

## 2. TOP 2025 七项逐项判定

| # | 实践 | 论文层面现状 | 仓库层面证据 | 当前等级 | 达到 L2 的缺口 |
|---|---|---|---|---|---|
| 1 | Study Registration | §20 已加"研究注册"段：**本研究为纯计算研究，未进行预注册** | 无注册记录（与声明一致） | **L1**（声明已披露） | 未注册研究按 TOP 定义不再有更高的 L2 形态；该项只能以"如实声明"满足 |
| 2 | Study Protocol | §19"复现"列出全部命令与产物，并在节首新增"协议载体"段，指认 `DEFECT_REMEDIATION_PLAN.md` 为判据 R1–R26、通过门槛、作废项与逐步修复记录的载体（[generate_heat_tree_paper.py](generate_heat_tree_paper.py#L2421-L2423)）；IJTS 稿 Data Availability 段已补同义句 | `DEFECT_REMEDIATION_PLAN.md` 随仓库公开分发、列入 `MANIFEST.sha256`（183 项），并包含在参考文献 [21] 所解析到的 Zenodo 归档（记录 `23622141`，v1.0.2）内 | **L2（三项条件齐备）** | 无，但判定依赖一个明示前提："引用"由数据集/代码条目 [21] 承载、该条目所解析的归档内含协议文件、且 §19 指名该文件；若审稿人要求协议单列一条参考文献，本行应退回 L1（该协议为事后台账而非事前注册，此点由第 1、3 行如实披露，不影响本行判定） |
| 3 | Analysis Plan | 无预先注册的分析计划；判据是事后台账 | `DEFECT_REMEDIATION_PLAN.md`（判定规则与作废项）、`REPORT.md` | **L1** | 分析计划无法追溯为"事前"；只能以"追溯性披露"托管并说明 |
| 4 | Materials Transparency | 论文 §20 声明数值结果、图与几何文件位于 `outputs/` | `outputs/tree.stl`、`outputs/manifold_assembly.stl`、`manifold_geometry.json`、全部几何/求解源码；`README.md` 目录段列出；参考文献 [21] 指向含上述文件的归档版本。`tree_dynamic.stl` 生成器未入库、不可复现，不列为可得材料 | **L2（三项条件齐备：公开托管 + 持久标识 + 参考文献引用）** | 无（生成器缺失已在 §20 披露） |
| 5 | Data Transparency | 论文 §20 声明数据集位置、规模与单位警告 | `outputs/` 74 个文件、7,778,123 字节（7.42 MB，按 `MANIFEST.sha256` 收录项统计；磁盘另有 2 个被 `.gitignore` 排除的 `*.bak_*`，故磁盘计数为 76）；`DATA_DICTIONARY.md` 逐文件说明；Zenodo 记录 `23622141`（v1.0.2，版本 DOI `10.5281/zenodo.23622141`）+ GitHub 公开托管；参考文献 [21]（概念 DOI `10.5281/zenodo.23620418`，现解析到该记录）（此前：记录 `23621256`，v1.0.1） | **L2（三项条件齐备）** | 无 |
| 6 | Analytic Code Transparency | 论文 §19 给出命令，§21 声明代码位置、许可与构建依赖 | 46 个 `.py`、10 个 `.m`、3 个 `.slx`；`LICENSE`（MIT）；`README.md` 复现段；与数据同处 Zenodo 记录 `23622141`（v1.0.2，版本 DOI `10.5281/zenodo.23622141`）；参考文献 [21] 为该记录的数据集与代码条目（此前：记录 `23621256`，v1.0.1） | **L2（三项条件齐备）** | 无（docx 构建链已自包含：模板入仓、同目录相对导入） |
| 7 | Reporting Transparency | 未声明是否使用报告指南 | 无适用清单记录 | **未达 L1** | 论文加一句"未找到适用于计算传热/生成式设计的报告清单，故未使用" |

**计数（2026-10-24 第五次复核＝归档后回填）：满足三项条件的 L2 = 4 项（第 2、4–6：Study Protocol / Materials / Data / Analytic Code），L1 = 2 项（第 1、3），未达 L1 = 1 项（第 7），L3 = 0 项；等级分布较第四次复核无变化。**（2026-10-24 第四次复核：L2 = 4 项（第 2、4–6）、L1 = 2 项（第 1、3）。2026-10-24 第三次复核：L2 = 3 项（第 4–6）、L1 = 3 项（第 1–3）。2026-10-24 早先：L1 = 2 项（第 2–3）、未达 L1 = 2 项（第 1、7）、"托管 + DOI 已具备但缺参考文献引用" = 3 项（第 4–6）、严格 L2 = 0 项。2026-10-18：L1 = 5 项、L2 = 0 项。）

---

## 3. TOP 2025 两项验证实践

| 实践 | 定义（S1） | 本项目现状 | 证据 | 判定 |
|---|---|---|---|---|
| Results Transparency | 独立方核对注册、协议、分析计划与最终报告是否一致，并确认报告承认偏离 | 无注册、无独立方；但作者自行保留了失败与作废记录（N4c 功率口径缺陷、11.56× 偏差） | `DEFECT_REMEDIATION_PLAN.md` §10.18；`REPORT.md` §3 根因段 | **未验证**。负面结果的自我披露是加分项，不等同于独立验证 |
| Computational Reproducibility | 独立方用同一数据与代码复现报告结果 | 仅作者本机自跑（Python 3.13.9 / numpy 2.3.5 / scipy 1.16.3 / matplotlib 3.10.6）；无数值容差清单、无第三方复现。docx 构建链已自包含（模板入仓），但数值复现仍无第三方记录 | `README.md#L38`；无独立复现记录 | **未验证** |

---

## 4. Nature Portfolio 条款逐项判定

| 条款 | 要求 | 现状 | 判定 |
|---|---|---|---|
| Data availability statement | 所有原创研究论文必须包含 | 论文 §20「数据可用性」已存在：数据集位置与规模、单位警告、不可得与作废、第三方材料、托管状态五段，标题位于 `19 复现`(357) 与 `参考文献`(394) 之间（docx 段落索引 380，全文 416 段） | **形式要件与实质要件均满足**（托管 + 可解析 DOI 已写入该段） |
| Code availability（独立小节） | 位于 data availability 之后、参考文献之前，说明获取方式与限制 | 论文 §21「代码可用性」已存在：代码位置、许可、构建依赖、已知不可复现项、托管状态五段（docx 段落索引 388，紧随 §20 之后） | **形式要件与实质要件均满足** |
| 代码存入 DOI 铸造仓库并引用 | Zenodo / Code Ocean 等，参考文献列出 | 已存入 Zenodo：v1.0.2 记录 `23622141`（版本 DOI `10.5281/zenodo.23622141`，`status=published`，2026-10-24T16:14:08Z 发布），v1.0.1 记录 `23621256`，首版记录 `23620419`（v1.0.0）；三者共用概念 DOI `10.5281/zenodo.23620418`；参考文献 [21] 即该数据集/代码条目（引概念 DOI） | **满足**（托管 + DOI + 参考文献引用三项齐备；v1.0.2 归档状态已由 `/api/records/23622141` 实测为 `published`，归档包已完成字节级校验，见 §5 项 16） |
| OSI 认可许可证 | 鼓励 | `LICENSE` 为 MIT，版权人已由占位符改为 `Haoran Wu (Wuchang University of Technology)`（[LICENSE](LICENSE#L3)） | **满足** |
| 材料可得 | 无不当限制 | STL（`tree.stl`、`manifold_assembly.stl`）、源码随仓库及 Zenodo 归档公开；`tree_dynamic.stl` 不可复现，不作为可得材料主张；`src_extract/`、`参考论文/` 已由 `.gitignore` 排除，不随分发（[LICENSE-DATA](LICENSE-DATA#L51-L53)） | **满足**（第三方材料已不随附） |
| 数据引用 | 数据集以正式引用列入参考文献 | 参考文献 [21]：`Wu H. Bionic adaptive network: generation, comparison and defect ledger of chip heat-dissipation channel trees [data set and code]. Zenodo. https://doi.org/10.5281/zenodo.23620418 (concept DOI, always resolving to the latest archived version) (2026).`；中文稿对应条目同引概念 DOI；论文 §20 数据可用性段同时写明"cited as reference [21]" | **满足**（概念 DOI 的解析目标随最新归档版本更新：当前实测 302 → `records/23622141`（v1.0.2）；v1.0.1 版本 DOI 作为 [21] 的缺陷见 §5 项 15） |
| Reporting summary | 物理科学仅对太阳能电池、激光声称等特定领域强制 | 本项目不属于强制领域 | **不适用** |
| "promptly available without undue qualifications" | 发表后即可得 | 已于 2026-10-24 公开托管于 Zenodo 与 GitHub，读者无需申请即可下载 | **满足**（发表前即可得，强于条款要求） |

---

## 5. 支撑判定的事实清单（均可在仓库内复核）

1. **工作树、HEAD 与 tag 的对应关系。** 第五次核验（归档后回填）起点 HEAD 为 `bf7eaee`（`release: v1.0.2 —— 协议载体指认、数据集引用改引概念 DOI、托管状态改为非穷尽表述`），它同时是 tag `v1.0.2` 所指提交（`git rev-list -n 1 v1.0.2` 实测相同）；其父为 `9057b63`，再前序为 `1939eec`（记录 v1.0.1 归档包字节级校验）与 `4417071`（记录 v1.0.1 归档结果）。tag `v1.0.0` 指向 `3e02b70`，其 `MANIFEST.sha256` 182 项对该 tag 的逐文件校验为 `mismatch 0 / missing 0`；tag `v1.0.1` 指向 `2b45125`（tag 对象 `256d686`），归档包对该 tag 的 186 个 blob 校验为 `186/186 相同`；tag `v1.0.2` 指向 `bf7eaee`，归档包对该 tag 的 187 个 blob 校验为 `187/187 相同`（§5 项 16）。回填前 `git status --porcelain` 为 3 项（`CITATION.cff`、`DATA_AVAILABILITY.md`、`README.md`），即本次归档后 DOI 回填；本文件与 `MANIFEST.sha256` 的改动随后一并提交。（此前：第四次核验起点 HEAD 为 `9057b63`，9 项未提交。）
2. **`CITATION.cff` 已建立、校验并完成归档后回填（2026-10-24）。** 文件存在，CFF 1.2.0，`type: software`，`version: 1.0.2`，含 ORCID 与**四个** DOI（`identifiers`：v1.0.2 / v1.0.1 / v1.0.0 / 概念；v1.0.2 条目于归档后插入，`10.5281/zenodo.23622141`）；以官方 `schema.json` + `jsonschema Draft7Validator` 校验，回填后重跑实测 `identifiers 4 / errors 0`。v1.0.2 自身的版本 DOI 由 Zenodo 在归档后分配、打 tag 时不可知，故 `identifiers` 只能在归档后回填，此为时序约束而非遗漏；**该回填条目不会出现在 tag `v1.0.2` 的归档快照内**，这正是 `main` 与归档快照的已知差异之一（§5 项 16）。（2026-10-24 第四次核验：`identifiers` 三条；2026-10-18：`Test-Path CITATION.cff` 为 `False`，README 仅以 DOI 段落充当临时引用格式。）
3. **作者信息已落实。** `LICENSE#L3` 为 `Copyright (c) 2026 Haoran Wu (Wuchang University of Technology)`；`LICENSE-DATA` 的署名样例已改为 `Wu, Haoran (2026)`；`.zenodo.json` 的 `creators` 为 `Wu, Haoran` + ORCID `0009-0005-1975-1511`，且已被 Zenodo 记录 `23620419` 实际采用。全仓库 `TODO: 作者姓名` 现为 0 命中。
4. **DOI 已分配且可解析（截至本次核验为三个版本）。** Zenodo 记录 `23620419`（v1.0.0）：`status=published`、`created=2026-10-24T14:45:14Z`、`version=1.0.0`、`doi=10.5281/zenodo.23620419`、`conceptdoi=10.5281/zenodo.23620418`、`license.id=other-open`、`related_identifiers` 含 GitHub tag `v1.0.0`（`isSupplementTo`）。Zenodo 记录 `23621256`（v1.0.1）：`status=published`、`created=2026-10-24T15:29:28Z`、`version=1.0.1`、`doi=10.5281/zenodo.23621256`、`conceptdoi=10.5281/zenodo.23620418`、`creators=['Wu, Haoran']`、`license.id=other-open`、`files=[('ice917/bionic-tree-microchannel-v1.0.1.zip', 35291943)]`、`related_identifiers` 含 GitHub tag `v1.0.1`。Zenodo 记录 `23622141`（v1.0.2，第五次核验新增）：`status=published`、`created=2026-10-24T16:14:07.999332+00:00`、`version=1.0.2`、`doi=10.5281/zenodo.23622141`、`conceptdoi=10.5281/zenodo.23620418`、`creators=['Wu, Haoran']`、`license.id=other-open`、`files=[('ice917/bionic-tree-microchannel-v1.0.2.zip', 35300596, 'md5:7d04a45e2d87f5aabdc7f0af42929670')]`、`related_identifiers` 含 GitHub tag `v1.0.2`（`isSupplementTo`）。概念 DOI `10.5281/zenodo.23620418` 现经 `zenodo.org/doi/…` **302 → `https://zenodo.org/records/23622141`**，即在本次核验时点解析到最新归档版；v1.0.0、v1.0.1 版本 DOI 仍各自独立解析到 `records/23620419`、`records/23621256`。**时序限定（已兑现）**：概念 DOI 的解析目标随最新归档版更新，v1.0.2 归档后已改指 `23622141`；v1.0.2 的版本 DOI 在打 tag 时不存在，归档后才由 Zenodo 分配。（此前：2026-10-24 第四次核验时点为两个版本、概念 DOI 解析到 `records/23621256`；2026-10-18：无 DOI、`version=0.1.0-draft`。）
5. **Zenodo 许可证字段无法表达混合许可。** `.zenodo.json` 的 `license` 为单值 `other-open`，而实际为 MIT + CC BY 4.0；说明写在 `description` 与 `notes`，机器不可读。该选择已在记录 `23620419` 上生效（`license.id=other-open`）；若需机器可读，仍应拆成两条记录。
6. **数据与代码规模已实测。** `outputs/` 74 个文件、7,778,123 字节（7.42 MB，按 `MANIFEST.sha256` 收录项统计）；另有 2 个 `*.bak_20261020_200638` 备份文件被 `.gitignore` 排除，不计入。（2026-10-18：59 个文件、4,763,033 字节。）
7. **数据字典已披露单位陷阱。** `_C` 后缀不等于摄氏度；`DATA_DICTIONARY.md` 与 `README.md#L71-L76` 均列出三类单位状态。这是报告透明度的实质性加分项，但不改变 Data Transparency 的等级。
8. **论文生成已自包含（原缺口已修）。** `paper_template.py` 已复制入仓，`generate_heat_tree_paper.py` 改为同目录相对导入，不再依赖 `D:\数学建模`；docx 可在干净环境按 README 重建。
9. **第三方材料已隔离。** `src_extract/` 含他人论文的 `.tex`、`.eps`、`.sty`；`LICENSE-DATA#L51-L53` 明确不覆盖。处置方式为"不随仓库分发"而非"取得再分发许可"：`src_extract/` 与 `参考论文/` 已由 `.gitignore` 排除，`git ls-files` 0 命中，归档 zip 内亦 0 命中（已用 GitHub codeload zip 核对，`forbidden hits 0`）。本地文件仍存在，但不在任何公开产物中。
10. **许可证范围已修正。** `LICENSE-DATA` 原先只列 `REPORT.md`、`DATA_DICTIONARY.md`、`DEFECT_REMEDIATION_PLAN.md`，漏掉 `README.md` 与 `PROJECT.md`，与 README"数据与文档（`*.md`）CC BY 4.0"的表述冲突；现已补入 `README.md`、`PROJECT.md` 与本文件。
11. **完整性清单已生成。** `MANIFEST.sha256` 共 **183 项**（新增 `CITATION.cff`），本次核验按扩展名重数的构成为：无扩展名 4 项（`LICENSE`、`LICENSE-DATA`、`.gitattributes`、`.gitignore`）、`.json` 28 项、`.cff` 1 项（`CITATION.cff`）、`.md` 12 项、`.py` 46 项、`.m` 10 项、`.npz` 1 项、`.joblib` 1 项、`.txt` 10 项、`.log` 1 项、`.csv` 12 项、`.png` 20 项、`.stl` 3 项、`.docx` 9 项、`.pdf` 2 项、`.tif` 22 项、`.svg` 1 项（`设备连接设计图.svg`），合计 183 项；其中位于 `outputs/` 的 74 项合计 7,778,123 字节。**目录口径（`outputs/` 74 项）与扩展名口径是两种切分，不可相加。** **本次核验在全部改动落盘后重跑 `_work/regenerate_manifest.py` 并逐项自校验，实测为 `183 verified / mismatch 0 / missing 0`（见 §8）。**（2026-10-24 早先：182 项；本条初稿的构成为"`outputs/` 74 + `.py` 46 + `.tif` 22 + … = 183"，该式把目录子集与全局扩展名计数并列相加、属重复计数，且 `.md`、`.json` 两项计数本身有误，故以逐扩展名重数的实测值替换并留痕。）对 v1.0.0 tag 的逐文件校验为 `mismatch 0 / missing 0`。3 个 `.slx` 随仓库分发，但因其包内含每次保存变化的时间戳与随机 UUID 而不纳入清单（已在论文 §21 披露）。`src_extract/`、`参考论文/` 为第三方材料，已由 `.gitignore` 排除，不随仓库或归档分发。（2026-10-18：108 项。）**归档后回填造成的已知差异**：tag `v1.0.2` 包内的 `MANIFEST.sha256` 为 183 行、对包内文件 **183/183 吻合**（§5 项 16）；本轮回填改动 `CITATION.cff`、`README.md`、`DATA_AVAILABILITY.md` 与本文件后，工作树清单按新内容重签，行数仍为 183 但对应哈希不同。两个清单各自只对各自的文件集自洽，不得交叉引用；归档包的内容边界始终是 tag `v1.0.2`。
12. **STL 几何已逐三角形核验。** `tree.stl` 与 `manifold_assembly.stl` 均闭合（边界边 0），但非流形边分别为 228 / 236 条，未执行布尔并集；`tree_dynamic.stl` 294 个连通分量、生成器未入库。故"闭合"不等于"流形"，更不等于"可打印"（`DATA_DICTIONARY.md` §6 第 6–7 条）。
13. **提交作者身份。** `fa01e46` 及之前的提交作者为 `cms2026 <cms2026@local>`（本机默认身份），与论文署名不一致。**不改写历史**：tag `v1.0.0`（指向 `3e02b70`）与 Zenodo 记录 `23620419` 的归档 zip 均已固定在这些提交的对象哈希上，改写会使归档快照与仓库失去可核对的一一对应。处置为：仓库级 `user.name`/`user.email` 改为 `Haoran Wu` / `3973349767@qq.com`，仅对后续提交生效；历史提交的身份不一致本文件如实披露。
14. **v1.0.1 已归档并完成字节级校验，用于消除"归档稿件无 AI 声明"的不一致。** v1.0.0（记录 `23620419`）的归档树不含生成式 AI 声明，与投稿件不符；为此发布 tag `v1.0.1`（指向提交 `2b45125`，tag 对象 `256d686`）及对应 GitHub Release，Zenodo 自动生成记录 `23621256`：`status=published`、`created=2026-10-24T15:29:28Z`、`version=1.0.1`、`doi=10.5281/zenodo.23621256`、`conceptdoi=10.5281/zenodo.23620418`、`creators=['Wu, Haoran']`、`license.id=other-open`、`files=[('ice917/bionic-tree-microchannel-v1.0.1.zip', 35291943)]`、`related_identifiers` 含 GitHub tag `v1.0.1`。归档包已下载并按 `--resolve zenodo.org:443:188.185.45.63` 绕过 DNS 污染，逐项校验结果见 §7「可以准确声称的」。包内稿件 `论文/submission_ijts/Manuscript_IJTS.docx` 经回读确认：`References` 索引 198，其前两段分别为 AI 声明标题与正文（含 `Trae`），正文含概念 DOI `23620418` 与 v1.0.0 版本 DOI `23620419`；**包内不含 v1.0.1 自身版本 DOI `23621256`**，原因是该 DOI 在 tag 与归档完成后才由 Zenodo 分配，任何版本的归档包都不可能包含自身版本 DOI，此为不可消除的时序事实。**另一已知边界**：tag 之后另有提交（`4417071`、`1939eec`、`9057b63` 及本次 v1.0.2 提交），只更新记录、清单、引用行与稿件文字；`git diff --name-status v1.0.1 HEAD -- outputs` 实测为 0 行，数值工件未变（§5 项 15 (iv)）。归档包的权威定义始终是 tag `v1.0.1` = `2b45125`。
15. **v1.0.1 版本 DOI 不适合作为 [21] 的指针（实测缺陷，2026-10-24，推翻前一轮判定）。** 四条实测事实：(i) `git rev-list -n 1 v1.0.1` = `2b45125fbc80975f1a73cb1923b41a1c809cce30`（tag 对象 `256d686`）；(ii) 该 tag 内的 `论文/submission_ijts/Manuscript_IJTS.docx`（`git show` 取二进制后经 python-docx 回读）共 **233 段**，`[21]`、`cited as reference [21]`、`DEFECT_REMEDIATION_PLAN.md`、`not pre-registered`、`10.5281/zenodo.23621256` 五个串的命中数**均为 0**，参考文献末条为 `[20]`（Alphacool 水泵数据表），仅有 1 处概念 DOI；(iii) `git ls-tree -r v1.0.1` **不含 `CITATION.cff`**，而 HEAD `9057b63` 含；(iv) `git diff --name-status v1.0.1 HEAD -- outputs` 输出 **0 行**，两快照的数值工件逐文件相同。推理链：若 [21] 指向 v1.0.1 版本 DOI，读者循该条目落到的恰是**唯一不含 [21] 自身、也不含 `CITATION.cff`、也不含未注册声明**的快照，v1.0.2 的发布目的（归档稿与投稿件一致）即落空；而 v1.0.2 自身的版本 DOI 在打 tag 时不可知，无法写入其自身快照；概念 DOI 在改动时已知，且归档后必解析到 v1.0.2 自身。故 [21] 改引概念 DOI `10.5281/zenodo.23620418`，此为唯一自洽选项。**（此前判定：保持 v1.0.1 版本 DOI 不变，理由是"最小改动 + 版本 DOI 最精确"；该理由不能抵消上述五个 0 命中与 `CITATION.cff` 缺失，故予推翻并留痕。）**
16. **v1.0.2 已发布、已归档，归档包完成字节级核验（2026-10-24 第五次核验新增）。** 发布链：提交 `bf7eaee` → annotated tag `v1.0.2`（`git rev-list -n 1 v1.0.2` 与 HEAD 相同）→ `git push origin v1.0.2` → GitHub Release `422838019`（`POST /repos/ice917/bionic-tree-microchannel/releases` 返回 201）→ Zenodo 记录 `23622141`。证据分五组：
    (i) **记录元数据**（`GET https://zenodo.org/api/records/23622141`）：`status=published`、`created=2026-10-24T16:14:07.999332+00:00`、`version=1.0.2`、`doi=10.5281/zenodo.23622141`、`conceptdoi=10.5281/zenodo.23620418`、`creators=['Wu, Haoran']`、`license.id=other-open`、`files=[('ice917/bionic-tree-microchannel-v1.0.2.zip', 35300596, 'md5:7d04a45e2d87f5aabdc7f0af42929670')]`、`related_identifiers` 含 `https://github.com/ice917/bionic-tree-microchannel/tree/v1.0.2`（`isSupplementTo`）。
    (ii) **载体一致性**：下载归档 zip 后实测字节数 35,300,596 与 MD5 `7d04a45e2d87f5aabdc7f0af42929670` 均与 API 声明相同（`_work/verify_v102_zip.py`）；解包后 187 个文件，与 `git -c core.quotepath=false ls-tree -r v1.0.2 -z` 的 187 个 blob 逐一重算 SHA-1，**187 相同 / 0 不同**，仅 tag 有与仅 zip 有均为 0。（**方法注记**：首跑未加 `core.quotepath=false` 时 `git ls-tree` 把非 ASCII 路径转义为八进制串，产生 38 项假"仅 tag 有"；该差异是显示层转义问题，不是内容差异，已按上述命令复测。）
    (iii) **包内清单**：包内 `MANIFEST.sha256` 183 行，对包内文件重算 **183 吻合 / 0 不符 / 0 缺失**；`src_extract/`、`参考论文/`、`_work/` 命中 **0**。
    (iv) **包内稿件**：`论文/submission_ijts/Manuscript_IJTS.docx` 234 段，`[21]` 2 处、概念 DOI `23620418` 2 处、**自身版本 DOI `23622141` 0 处**——第三项是时序约束的正面印证（版本 DOI 在归档完成后才分配），不是缺漏；AI 声明串存在。
    (v) **解析与边界**：`zenodo.org/doi/10.5281/zenodo.23620418` **302 → `https://zenodo.org/records/23622141`**；`git diff --name-status v1.0.2 -- outputs 论文` 输出 **0 行**，即归档快照与回填后的工作树在数值工件与稿件上完全相同，唯一差异是四个元数据文件与 `MANIFEST.sha256`（回填内容）。**据此可断言："v1.0.2 已归档且可解析"成立；"归档包含自身版本 DOI"不成立且不可能成立。**

---

## 6. 缺口与补齐顺序

### 6.1 阻塞 L2 的项（按依赖顺序）

| ID | 缺口 | 具体动作 | 验收标准 |
|---|---|---|---|
| B2-01 | ~~作者/单位占位~~ **已闭环（2026-10-24）** | 已替换 `LICENSE`、`LICENSE-DATA`、`.zenodo.json` 中全部占位符 | 已验收：全仓库 `TODO: 作者姓名` 0 命中；Zenodo 记录 `23620419` 的 `creators` 为 `Wu, Haoran` + ORCID `0009-0005-1975-1511` |
| B2-02 | ~~工作树未提交~~ **已闭环（2026-10-24）** | 发布前改动已提交（`3e02b70`）并打 tag `v1.0.0`；DOI 回填提交为 `fa01e46` | 已验收：核验时点 `git status --porcelain` 为 0 行；`v1.0.0` 指向 `3e02b70`，其 MANIFEST 182 项校验 `mismatch 0 / missing 0` |
| B2-03 | ~~无引用元数据~~ **已闭环（2026-10-24）** | 已新建 `CITATION.cff`（CFF 1.2.0，`type: software`，含作者 + ORCID、双语标题、`version: 1.0.2`、`date-released: 2026-10-24`、`license: MIT`、`repository-code`、`url` 指向概念 DOI，`identifiers` 列出四个 DOI：v1.0.2 / v1.0.1 / v1.0.0 / 概念，其中 v1.0.2 条目系 2026-10-24 归档后回填） | 已验收：`cffconvert` 未安装，改用官方 `schema.json`（63,762 B，取自 `citation-file-format` 主仓）+ `jsonschema` `Draft7Validator` 校验；改版本号为 `1.0.2` 后重跑，**errors: 0**。归档后已在 `identifiers` 首位补入 v1.0.2 版本 DOI `10.5281/zenodo.23622141`，重跑校验 **identifiers 4 / errors 0**（2026-10-24 第五次核验） |
| B2-04 | ~~论文缺 Data/Code availability~~ **已闭环（2026-10-18）** | 已在 §19 之后、参考文献之前插入 §20 数据可用性、§21 代码可用性 | 已验收（2026-10-24 第四次核验重测）：docx 标题顺序为 `19 复现`(357) → `20 数据可用性`(380) → `21 代码可用性`(388) → `参考文献`(394)，两节均存在且顺序正确（全文 416 段）（此前：379 / 387 / 393，共 415 段） |
| B2-05 | ~~未托管、无 DOI~~ **已闭环（2026-10-24）** | 第三方材料（`src_extract/`、`参考论文/`）改由 `.gitignore` 排除而非取得授权；数据集已随 tag `v1.0.0` 归档至 Zenodo（记录 `23620419`） | 已验收：`doi.org` 对 `10.5281/zenodo.23620419` 302 → `zenodo.org/records/23620419`（200）；概念 DOI `10.5281/zenodo.23620418` 现 302 → `records/23622141`（v1.0.2，最新归档版）（此前：→ `records/23620419`）；DOI 已写入 `.zenodo.json`、`README.md`、`DATA_AVAILABILITY.md` 与论文 §20 |
| B2-06 | ~~混合许可与单值字段~~ **已闭环（2026-10-24，采用第二方案）** | 保留 `other-open`，在 `.zenodo.json` 的 `description` 与 `notes` 中逐项写明 MIT（代码）+ CC BY 4.0（数据与文档）及第三方材料不分发 | 已验收：记录 `23620419` 的 `license.id=other-open`；两条许可文字均在记录元数据内。机器可读性仍不足，属已披露的残留限制 |
| B2-07 | ~~生成链不自洽~~ **已闭环（2026-10-18）** | `paper_template.py` 已复制入仓、`generate_heat_tree_paper.py` 改为同目录相对导入 | 从干净环境按 README 能重建 docx（已实测：改相对导入后 `python generate_heat_tree_paper.py` 成功生成 docx） |
| B2-08 | ~~无版本化数值基线~~ **已闭环（2026-10-24）** | `MANIFEST.sha256` 182 项已随 `3e02b70` 提交，并重新对 `v1.0.0` 逐文件校验 | 已验收：对 tag `v1.0.0` 的 `git show` 内容重算，`182 verified / mismatch 0 / missing 0` |

### 6.2 不阻塞 L2、但应在投稿前完成

| ID | 缺口 | 动作 |
|---|---|---|
| B2-09 | ~~未声明研究未注册~~ **已闭环（2026-10-24）** | 已执行：论文 §20 数据可用性段末加"本研究为纯计算研究，未进行预注册"（英文稿同义句 `This is a computational study and was not pre-registered.`） |
| B2-10 | 未声明报告指南 | 加一句"未找到适用清单，故未使用" |
| B2-11 | 审稿期代码可得性 | Nature 要求审稿人可获取代码；准备匿名化副本或 Code Ocean 链接 |
| B2-12 | 数值容差 | 在复现节给出关键量的容差（如 `dTmax` 四位小数逐位一致），否则"可复现"不可检验 |

---

## 7. 结论

**核实事实**：TOP 2025 七项中，4 项（第 2、4–6：Study Protocol / Materials / Data / Analytic Code）已同时具备"公开托管 + 持久标识（DOI）+ 参考文献引用"三项条件，判定为 Level 2；2 项处于 Level 1（第 1、3），1 项未达 Level 1（第 7）；Level 3 = 0 项；两项 Verification Practices 均未验证。第 2 项的依据是：`DEFECT_REMEDIATION_PLAN.md` 随仓库公开分发、列入 `MANIFEST.sha256`（183 项）、并位于参考文献 [21] 所解析的归档内，且 §19 新增"协议载体"段指名该文件（[generate_heat_tree_paper.py](generate_heat_tree_paper.py#L2421-L2423)）。参考文献 [21] 为数据集/代码条目，引概念 DOI `10.5281/zenodo.23620418`（第五次核验时实测 302 → 记录 `23622141`，v1.0.2），论文 §20 数据可用性段与之交叉引用（"cited as reference [21]"），并声明研究未预注册。Nature Portfolio 的 Data availability 与 Code availability 两节的形式要件已具备（中文稿 docx 段落索引 380 / 388，标题顺序 357 → 380 → 388 → 394，全文 416 段；IJTS 稿 234 段，`Data Availability Statement` 188、AI 声明标题 196 / 正文 197、`References ` 198、`[21]` 219；PDF 41 页，文本层 `23621256` 命中 0 次、`23620418` 2 次、`[21]` 2 次）。实质要件中"发表后即可得、无不当限制、带持久标识、数据集以正式引用列入参考文献"已由 Zenodo 记录 `23622141`（v1.0.2，2026-10-24T16:14:08Z 发布，`status=published`）、记录 `23621256`（v1.0.1）与 GitHub 公共仓库满足。**v1.0.2 已完成归档，其版本 DOI `10.5281/zenodo.23622141` 存在且可解析；归档包已通过字节级校验（zip 187 / tag 187、逐 blob 187/187 相同、包内 MANIFEST 183/183、禁入目录 0，见 §5 项 16）。**

**推理链**：Level 2 的三项条件为"公开托管 + 持久标识 + 在参考文献中引用"，三者缺一不可。第 4–6 项：前两项由 Zenodo 记录 `23622141`（v1.0.2 版本 DOI `10.5281/zenodo.23622141`；`status=published`）与概念 DOI `10.5281/zenodo.23620418`（始终指向最新归档版，现实测解析到 `records/23622141`）满足，第三项由参考文献 [21] 满足，故在同一时点同时成立，不存在"接近 L2"的中间态。第 2 项：托管由仓库与归档共同满足（文件在 `git ls-tree HEAD` 与 [21] 所解析的归档内）、持久标识由 [21] 的概念 DOI 满足、引用由 §19 指名 + [21] 归档内含该文件合成满足——**此合成是一个明示前提**，若审稿人要求协议单列一条参考文献，则第三项不成立，该项应退回 L1。Nature 的条款在参考文献引用之外不要求额外动作：托管、DOI、无限制下载、OSI 许可（MIT）均已具备，故其数据与代码条款不残留缺口。仍需保留的限制是第 7 项（报告指南）：论文未声明是否使用报告清单，且"未找到适用清单"属不可穷尽的否定断言，只能以如实声明的方式补足，不能以检索次数证明。

**唯一结论**：**本项目当前为"TOP 2025：4 项 Level 2（第 2、4–6）+ 2 项 Level 1（第 1、3）+ 1 项未达 Level 1（第 7），Level 3 = 0"；Nature Portfolio 的数据与代码可用性条款（含数据引用）均已满足。** 可以声称"数据与代码已公开归档、取得可解析 DOI，并在参考文献中正式引用，满足 TOP 2025 Level 2 的三项操作化条件"；不得声称"符合 TOP Level 2 认证"（L3 需独立第三方认证）、不得声称"已通过第三方复现"。剩余可提升项只有两个：第 7 项报告指南声明（B2-10），以及第 2 项若被要求"协议单列参考文献条目"则应如实退回 L1——该项的 L2 判定以 §2 与本节所述明示前提为界，不得省略该前提单独引用"L2 = 4 项"。

**可以准确声称的**：数据与代码已永久归档于 Zenodo，**三个版本**均可独立引用（v1.0.2 版本 DOI `10.5281/zenodo.23622141`、v1.0.1 版本 DOI `10.5281/zenodo.23621256`、v1.0.0 版本 DOI `10.5281/zenodo.23620419`），概念 DOI `10.5281/zenodo.23620418` 始终指向最新归档版（现实测 302 → `records/23622141`），并公开托管于 GitHub；作者、单位、ORCID 与许可权利人已落实到文件；论文含独立的 Data availability 与 Code availability 两节且位置符合 Nature 要求（中文稿索引 380 / 388，IJTS 稿 `Data Availability Statement` 188、`References` 198）；数值结果可按 README 命令在本机重跑；单位陷阱、失败与作废记录已公开披露；3 个 `.slx` 因含易变时间戳而未纳入 MANIFEST（已在论文 §21 披露）。**v1.0.1 归档包已完成字节级校验**（2026-10-24 实测）：zip 大小 35,291,943 B 与 Zenodo API 的 `files[0].size` 相同；MD5 `e3933702bc9ebc2caf23f0d8853cbd27` 与 API 的 `files[0].checksum` 相同；包内 186 个文件与 tag `v1.0.1` 的 186 个 git blob 逐一重算 SHA-1 **全部相同（186/186，0 不同）**；包内 `MANIFEST.sha256` 182 项对包内文件重算 **182/182 吻合**；`src_extract/`、`参考论文/`、`_work/` 命中 **0**。**v1.0.2 归档包亦已完成字节级校验**（2026-10-24 实测，§5 项 16）：zip 大小 35,300,596 B 与 MD5 `7d04a45e2d87f5aabdc7f0af42929670` 均与 API 相同；包内 187 个文件与 tag `v1.0.2` 的 187 个 blob **187/187 相同**；包内 `MANIFEST.sha256` **183/183 吻合**；禁入目录命中 **0**；包内 IJTS 稿 234 段、`[21]` 2 处、概念 DOI 2 处、自身版本 DOI 0 处。**引用元数据与数据集引用已闭环**（2026-10-24，含归档后回填）：`CITATION.cff`（CFF 1.2.0，`version: 1.0.2`，`identifiers` 四条含 v1.0.2 版本 DOI）通过官方 `schema.json` 校验 **errors: 0**；论文参考文献 [21] 为数据集/代码条目并引概念 DOI `10.5281/zenodo.23620418`，§20 数据可用性段写明 "cited as reference [21]"；§20 并声明 "本研究为纯计算研究，未进行预注册"。

**不能声称**的：第三方独立复现、第三方认证、TOP Level 3；以及"Zenodo 归档 zip 与 GitHub 按同一 tag 重新生成的 zip 字节相同"——后者为假命题，实测 v1.0.0 两包差 3,582 B（34,817,027 vs 34,813,445），原因是 zip 容器的压缩时机与元数据不同。**须区分三个命题**：(a) 归档包内文件内容 = tag 文件内容 → 已证为真（v1.0.1：186/186；v1.0.2：187/187）；(b) 归档包字节 = 重新打包字节 → 已证为假；(c) 归档包 MD5 = Zenodo 声明的 MD5 → 已证为真（v1.0.1：`e3933702…`；v1.0.2：`7d04a45e…`）。承诺可复现时只能引用 (a) 与 (c)。**另需注意时序边界**：v1.0.1 归档包早于本轮改动（参考文献 [21]、`CITATION.cff`、研究未注册声明），故包内稿件不含 `[21]` 与 `23621256`（§5 项 15 实测五串 0 命中）；同理，v1.0.2 归档包内亦不含自身版本 DOI（§5 项 16 (iv) 实测 `23622141` 0 处）。归档包与仓库的内容一致性只能以各自 tag 为界，不能以当前 HEAD 为界；也不得声称"概念 DOI 永远指向与 HEAD 相同的快照"——它只指向"最新归档版"。

---

## 8. 复核方式

```powershell
git rev-parse HEAD; git status --porcelain | Measure-Object -Line
(Get-ChildItem outputs -Recurse -File | Measure-Object Length -Sum)
(Get-Content MANIFEST.sha256 | Measure-Object -Line)
Test-Path CITATION.cff
python -c "import json,jsonschema,yaml; c=yaml.safe_load(open('CITATION.cff',encoding='utf-8')); s=json.load(open('_work/cff_schema.json',encoding='utf-8')); print(c['version'], len(list(jsonschema.Draft7Validator(s).iter_errors(c))))"
python -c "from docx import Document; d=Document(r'论文\submission_ijts\Manuscript_IJTS.docx'); t=[p.text.strip() for p in d.paragraphs]; print(len(t), t.index('Data Availability Statement'), [i for i,x in enumerate(t) if x.startswith('References')], [x for x in t if x.startswith('[21]')], [x for x in t if 'not pre-registered' in x])"
python -c "from docx import Document; d=Document(r'论文\仿生自适应网络芯片散热与布线.docx'); t=[p.text.strip() for p in d.paragraphs]; print(len(t), [i for i,x in enumerate(t) if x in ('19 复现','20 数据可用性','21 代码可用性','参考文献')], [i for i,x in enumerate(t) if x.startswith('[21]')])"
python -c "import fitz; s=''.join(p.get_text() for p in fitz.open(r'论文\submission_ijts\Manuscript_IJTS.pdf')); print(s.count('23621256'), s.count('23620418'), s.count('[21]'))"
python _work/validate_ijts.py
python _work/check_pdf_ijts.py
curl.exe --resolve zenodo.org:443:188.185.45.63 -s https://zenodo.org/api/records/23622141 | python -c "import sys,json; r=json.load(sys.stdin); f=r['files'][0]; print(r['status'], r['metadata']['version'], r['doi'], r['conceptdoi'], f['key'], f['size'], f['checksum'])"
curl.exe --resolve zenodo.org:443:188.185.45.63 -s -o NUL -w "%{http_code} %{redirect_url}`n" https://zenodo.org/doi/10.5281/zenodo.23620418
git rev-list -n 1 v1.0.2; git diff --name-status v1.0.2 -- outputs 论文
```

预期：本次回填提交后 `git status --porcelain` 为 0 行（**回填开始时实测为 3 行**：`CITATION.cff`、`DATA_AVAILABILITY.md`、`README.md`；本文件与重签的 `MANIFEST.sha256` 随后一并提交）；`outputs` 磁盘为 76 文件 / 8,041,323 字节（其中 2 个 `*.bak_*` 被 `.gitignore` 排除），`MANIFEST.sha256` 总行数 183（其中位于 `outputs/` 的 74 项合计 7,778,123 字节）；`CITATION.cff` 存在（`True`），`version` 为 `1.0.2`，`identifiers` 为 **4** 条，官方 schema 校验错误数 `0`；IJTS 稿为 **234 段**，`Data Availability Statement` 索引 **188**，`References`（文本带尾随空格，用 `startswith` 匹配）索引 **198**，`[21]` 条目引 **`10.5281/zenodo.23620418`** 且**不含** `23621256`，正文含 `This is a computational study and was not pre-registered.`；中文稿为 **416 段**，标题索引 **357 / 380 / 388 / 394**，`[21]` 索引 **415**；PDF 文本层 `23621256` **0 次**、`23620418` **2 次**、`[21]` **2 次**（41 页）；`validate_ijts.py` 输出 `PASS 35 FAIL 0 PEND 0`，`check_pdf_ijts.py` 输出 `PASS 17 FAIL 0`；Zenodo API 对记录 `23622141` 输出 `published 1.0.2 10.5281/zenodo.23622141 10.5281/zenodo.23620418 ice917/bionic-tree-microchannel-v1.0.2.zip 35300596 md5:7d04a45e2d87f5aabdc7f0af42929670`；概念 DOI 解析输出 `302 https://zenodo.org/records/23622141`；`git rev-list -n 1 v1.0.2` 输出 `bf7eaee`，`git diff --name-status v1.0.2 -- outputs 论文` 为 0 行。任一预期变化，本文件的对应判定即需重做。**第四次核验遗留的"v1.0.2 归档后必须重跑本节第 1 行与 DOI 断言"这一承诺已在第五次核验中兑现**：`README.md`、`DATA_AVAILABILITY.md`、`CITATION.cff`（`identifiers`）与本文件 §5 项 4 的版本数表述均已按归档后实测值更新；若将来再发布新版本，同一承诺随之顺延。
