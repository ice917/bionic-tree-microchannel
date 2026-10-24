# 报告合规性对照（B2）

核验日期：2026-10-24（第二次核验；首次为 2026-10-18）
核验对象：本仓库工作树（`main` 分支；核验起点 HEAD `fa01e46`，该时点 `git status --porcelain` 为 0 行；本文件的 2026-10-24 修正随其后的一个提交入库）
判定对象：论文《仿生自适应网络用于芯片散热与布线》及其随附数据与代码

**版本注记（2026-10-24 复验）**：本文件已按 2026-10-24 实测值回改。2026-10-18 首次核验的三项主要判定——"零项 L2""无 DOI""未托管"——因 Zenodo 记录 `23620419`（v1.0.0，2026-10-24T14:45:14Z 发布）而失效，现按实测重判。凡保留的历史值一律以"（2026-10-18：…）"标注，不作静默替换。

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
| 1 | Study Registration | 全文无"是否注册"声明 | 无注册记录 | **未达 L1**（研究类型为计算设计，应声明"不适用/未注册"） | 论文加一句不适用声明；无需注册 |
| 2 | Study Protocol | §19"复现"列出全部命令与产物（[generate_heat_tree_paper.py](generate_heat_tree_paper.py#L2389-L2411)），但未声明"协议可获取、位于何处" | `DEFECT_REMEDIATION_PLAN.md` 记录方法、判据 R1–R26 与修复过程 | **L1（弱）**：步骤已披露，缺显式可得性声明 | 在论文中写明协议载体与版本；托管并引用 |
| 3 | Analysis Plan | 无预先注册的分析计划；判据是事后台账 | `DEFECT_REMEDIATION_PLAN.md`（判定规则与作废项）、`REPORT.md` | **L1** | 分析计划无法追溯为"事前"；只能以"追溯性披露"托管并说明 |
| 4 | Materials Transparency | 论文 §20 声明数值结果、图与几何文件位于 `outputs/` | `outputs/tree.stl`、`outputs/manifold_assembly.stl`、`manifold_geometry.json`、全部几何/求解源码；`README.md` 目录段列出。`tree_dynamic.stl` 生成器未入库、不可复现，不列为可得材料 | **托管与 DOI 已具备，缺参考文献引用** | 在参考文献中列入数据集条目 |
| 5 | Data Transparency | 论文 §20 声明数据集位置、规模与单位警告 | `outputs/` 74 个文件、7,778,123 字节（7.42 MB）；`DATA_DICTIONARY.md` 逐文件说明；Zenodo 记录 `23620419` + GitHub 公开托管 | **托管与 DOI 已具备，缺参考文献引用** | 在参考文献中列入数据集条目；单位误标清单须随数据一同发布（已具备） |
| 6 | Analytic Code Transparency | 论文 §19 给出命令，§21 声明代码位置、许可与构建依赖 | 46 个 `.py`、10 个 `.m`、3 个 `.slx`；`LICENSE`（MIT）；`README.md` 复现段；与数据同处 Zenodo 记录 `23620419` | **托管与 DOI 已具备，缺参考文献引用** | 在参考文献中列入数据集条目；docx 构建链已自包含（模板入仓、同目录相对导入） |
| 7 | Reporting Transparency | 未声明是否使用报告指南 | 无适用清单记录 | **未达 L1** | 论文加一句"未找到适用于计算传热/生成式设计的报告清单，故未使用" |

**计数（2026-10-24）：L1 = 2 项（第 2–3），未达 L1 = 2 项（第 1、7），"托管 + DOI 已具备但缺参考文献引用" = 3 项（第 4–6），严格满足三项条件的 L2 = 0 项，L3 = 0 项。**（2026-10-18：L1 = 5 项、L2 = 0 项。）

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
| Data availability statement | 所有原创研究论文必须包含 | 论文 §20「数据可用性」已存在：数据集位置与规模、单位警告、不可得与作废、第三方材料、托管状态五段，标题位于 `19 复现` 与 `参考文献` 之间（docx 段落索引 379） | **形式要件与实质要件均满足**（托管 + 可解析 DOI 已写入该段） |
| Code availability（独立小节） | 位于 data availability 之后、参考文献之前，说明获取方式与限制 | 论文 §21「代码可用性」已存在：代码位置、许可、构建依赖、已知不可复现项、托管状态五段（docx 段落索引 386，紧随 §20 之后） | **形式要件与实质要件均满足** |
| 代码存入 DOI 铸造仓库并引用 | Zenodo / Code Ocean 等，参考文献列出 | 已存入 Zenodo（记录 `23620419`，v1.0.0）；`.zenodo.json` 的 `version` 为 `1.0.0`，记录含 `related_identifiers` 指向 GitHub tag | **部分满足**：托管与 DOI 已满足，参考文献尚未列入数据集条目 |
| OSI 认可许可证 | 鼓励 | `LICENSE` 为 MIT，版权人已由占位符改为 `Haoran Wu (Wuchang University of Technology)`（[LICENSE](LICENSE#L3)） | **满足** |
| 材料可得 | 无不当限制 | STL（`tree.stl`、`manifold_assembly.stl`）、源码随仓库及 Zenodo 归档公开；`tree_dynamic.stl` 不可复现，不作为可得材料主张；`src_extract/`、`参考论文/` 已由 `.gitignore` 排除，不随分发（[LICENSE-DATA](LICENSE-DATA#L51-L53)） | **满足**（第三方材料已不随附） |
| 数据引用 | 数据集以正式引用列入参考文献 | 数据集 DOI 已存在（版本 `10.5281/zenodo.23620419` / 概念 `10.5281/zenodo.23620418`），但参考文献中仍无该条目 | **不满足**（仅缺引用动作，非缺 DOI） |
| Reporting summary | 物理科学仅对太阳能电池、激光声称等特定领域强制 | 本项目不属于强制领域 | **不适用** |
| "promptly available without undue qualifications" | 发表后即可得 | 已于 2026-10-24 公开托管于 Zenodo 与 GitHub，读者无需申请即可下载 | **满足**（发表前即可得，强于条款要求） |

---

## 5. 支撑判定的事实清单（均可在仓库内复核）

1. **工作树与 HEAD 一致。** HEAD 为 `fa01e46`（`docs: 回填 Zenodo DOI…`），`git status --porcelain` 本次核对为 0 行。tag `v1.0.0` 指向 `3e02b70`，其 `MANIFEST.sha256` 182 项对该 tag 的逐文件校验为 `mismatch 0 / missing 0`。（2026-10-18：HEAD `44e33ae`，88 行未提交。）
2. **无 `CITATION.cff`。** `Test-Path CITATION.cff` 为 `False`；README 已改为在创建前以 DOI 段落作为临时规范引用格式（[README.md](README.md#L120-L131)）。
3. **作者信息已落实。** `LICENSE#L3` 为 `Copyright (c) 2026 Haoran Wu (Wuchang University of Technology)`；`LICENSE-DATA` 的署名样例已改为 `Wu, Haoran (2026)`；`.zenodo.json` 的 `creators` 为 `Wu, Haoran` + ORCID `0009-0005-1975-1511`，且已被 Zenodo 记录 `23620419` 实际采用。全仓库 `TODO: 作者姓名` 现为 0 命中。
4. **DOI 已分配且可解析。** Zenodo 记录 `23620419`：`status=published`、`created=2026-10-24T14:45:14Z`、`version=1.0.0`、`doi=10.5281/zenodo.23620419`、`conceptdoi=10.5281/zenodo.23620418`、`license.id=other-open`；`related_identifiers` 含 GitHub tag `v1.0.0`（`isSupplementTo`）。两个 DOI 经 `doi.org` 均 302 → `zenodo.org/records/23620419`（200）。（2026-10-18：无 DOI、`version=0.1.0-draft`。）
5. **Zenodo 许可证字段无法表达混合许可。** `.zenodo.json` 的 `license` 为单值 `other-open`，而实际为 MIT + CC BY 4.0；说明写在 `description` 与 `notes`，机器不可读。该选择已在记录 `23620419` 上生效（`license.id=other-open`）；若需机器可读，仍应拆成两条记录。
6. **数据与代码规模已实测。** `outputs/` 74 个文件、7,778,123 字节（7.42 MB，按 `MANIFEST.sha256` 收录项统计）；另有 2 个 `*.bak_20261020_200638` 备份文件被 `.gitignore` 排除，不计入。（2026-10-18：59 个文件、4,763,033 字节。）
7. **数据字典已披露单位陷阱。** `_C` 后缀不等于摄氏度；`DATA_DICTIONARY.md` 与 `README.md#L71-L76` 均列出三类单位状态。这是报告透明度的实质性加分项，但不改变 Data Transparency 的等级。
8. **论文生成已自包含（原缺口已修）。** `paper_template.py` 已复制入仓，`generate_heat_tree_paper.py` 改为同目录相对导入，不再依赖 `D:\数学建模`；docx 可在干净环境按 README 重建。
9. **第三方材料已隔离。** `src_extract/` 含他人论文的 `.tex`、`.eps`、`.sty`；`LICENSE-DATA#L51-L53` 明确不覆盖。处置方式为"不随仓库分发"而非"取得再分发许可"：`src_extract/` 与 `参考论文/` 已由 `.gitignore` 排除，`git ls-files` 0 命中，归档 zip 内亦 0 命中（已用 GitHub codeload zip 核对，`forbidden hits 0`）。本地文件仍存在，但不在任何公开产物中。
10. **许可证范围已修正。** `LICENSE-DATA` 原先只列 `REPORT.md`、`DATA_DICTIONARY.md`、`DEFECT_REMEDIATION_PLAN.md`，漏掉 `README.md` 与 `PROJECT.md`，与 README"数据与文档（`*.md`）CC BY 4.0"的表述冲突；现已补入 `README.md`、`PROJECT.md` 与本文件。
11. **完整性清单已生成。** `MANIFEST.sha256` 共 182 项，构成为：`outputs/` 74 项、46 个 `.py`、10 个 `.m`、11 个 `.md`（10 个根目录 + `论文/_dump_journal.md`）、9 个 `.docx`、2 个 `.pdf`、22 个 `.tif`、`.zenodo.json`、`LICENSE`、`LICENSE-DATA`、`.gitattributes`、`.gitignore`、`gen_design/` 的 `.npz` 与 `.joblib` 各 1、`设备连接设计图.svg` 1；对 v1.0.0 tag 的逐文件校验为 `mismatch 0 / missing 0`。3 个 `.slx` 随仓库分发，但因其包内含每次保存变化的时间戳与随机 UUID 而不纳入清单（已在论文 §21 披露）。`src_extract/`、`参考论文/` 为第三方材料，已由 `.gitignore` 排除，不随仓库或归档分发。（2026-10-18：108 项。）
12. **STL 几何已逐三角形核验。** `tree.stl` 与 `manifold_assembly.stl` 均闭合（边界边 0），但非流形边分别为 228 / 236 条，未执行布尔并集；`tree_dynamic.stl` 294 个连通分量、生成器未入库。故"闭合"不等于"流形"，更不等于"可打印"（`DATA_DICTIONARY.md` §6 第 6–7 条）。
13. **提交作者身份。** `fa01e46` 及之前的提交作者为 `cms2026 <cms2026@local>`（本机默认身份），与论文署名不一致。**不改写历史**：tag `v1.0.0`（指向 `3e02b70`）与 Zenodo 记录 `23620419` 的归档 zip 均已固定在这些提交的对象哈希上，改写会使归档快照与仓库失去可核对的一一对应。处置为：仓库级 `user.name`/`user.email` 改为 `Haoran Wu` / `3973349767@qq.com`，仅对后续提交生效；历史提交的身份不一致本文件如实披露。
14. **v1.0.1 已归档并完成字节级校验，用于消除"归档稿件无 AI 声明"的不一致。** v1.0.0（记录 `23620419`）的归档树不含生成式 AI 声明，与投稿件不符；为此发布 tag `v1.0.1`（指向提交 `2b45125`，tag 对象 `256d686`）及对应 GitHub Release，Zenodo 自动生成记录 `23621256`：`status=published`、`created=2026-10-24T15:29:28Z`、`version=1.0.1`、`doi=10.5281/zenodo.23621256`、`conceptdoi=10.5281/zenodo.23620418`、`creators=['Wu, Haoran']`、`license.id=other-open`、`files=[('ice917/bionic-tree-microchannel-v1.0.1.zip', 35291943)]`、`related_identifiers` 含 GitHub tag `v1.0.1`。归档包已下载并按 `--resolve zenodo.org:443:188.185.45.63` 绕过 DNS 污染，逐项校验结果见 §7「可以准确声称的」。包内稿件 `论文/submission_ijts/Manuscript_IJTS.docx` 经回读确认：`References` 索引 198，其前两段分别为 AI 声明标题与正文（含 `Trae`），正文含概念 DOI `23620418` 与 v1.0.0 版本 DOI `23620419`；**包内不含 v1.0.1 自身版本 DOI `23621256`**，原因是该 DOI 在 tag 与归档完成后才由 Zenodo 分配，任何版本的归档包都不可能包含自身版本 DOI，此为不可消除的时序事实。**另一已知边界**：tag 之后仍有提交（`4417071`），仅更新 DOI 记录与 README 引用行，不改动论文或数据内容；归档包的权威定义始终是 tag `v1.0.1` = `2b45125`。

---

## 6. 缺口与补齐顺序

### 6.1 阻塞 L2 的项（按依赖顺序）

| ID | 缺口 | 具体动作 | 验收标准 |
|---|---|---|---|
| B2-01 | ~~作者/单位占位~~ **已闭环（2026-10-24）** | 已替换 `LICENSE`、`LICENSE-DATA`、`.zenodo.json` 中全部占位符 | 已验收：全仓库 `TODO: 作者姓名` 0 命中；Zenodo 记录 `23620419` 的 `creators` 为 `Wu, Haoran` + ORCID `0009-0005-1975-1511` |
| B2-02 | ~~工作树未提交~~ **已闭环（2026-10-24）** | 发布前改动已提交（`3e02b70`）并打 tag `v1.0.0`；DOI 回填提交为 `fa01e46` | 已验收：核验时点 `git status --porcelain` 为 0 行；`v1.0.0` 指向 `3e02b70`，其 MANIFEST 182 项校验 `mismatch 0 / missing 0` |
| B2-03 | 无引用元数据 | 新建 `CITATION.cff`，含作者、标题、版本、许可证、仓库 URL | `cffconvert` 或等价校验通过（**仍未完成**） |
| B2-04 | ~~论文缺 Data/Code availability~~ **已闭环（2026-10-18）** | 已在 §19 之后、参考文献之前插入 §20 数据可用性、§21 代码可用性 | 已验收：docx 标题顺序为 `19 复现`(357) → `20 数据可用性`(379) → `21 代码可用性`(386) → `参考文献`(392)，两节均存在且顺序正确 |
| B2-05 | ~~未托管、无 DOI~~ **已闭环（2026-10-24）** | 第三方材料（`src_extract/`、`参考论文/`）改由 `.gitignore` 排除而非取得授权；数据集已随 tag `v1.0.0` 归档至 Zenodo（记录 `23620419`） | 已验收：`doi.org` 对 `10.5281/zenodo.23620419` 与 `10.5281/zenodo.23620418` 均 302 → `zenodo.org/records/23620419`（200）；DOI 已写入 `.zenodo.json`、`README.md`、`DATA_AVAILABILITY.md` 与论文 §20 |
| B2-06 | ~~混合许可与单值字段~~ **已闭环（2026-10-24，采用第二方案）** | 保留 `other-open`，在 `.zenodo.json` 的 `description` 与 `notes` 中逐项写明 MIT（代码）+ CC BY 4.0（数据与文档）及第三方材料不分发 | 已验收：记录 `23620419` 的 `license.id=other-open`；两条许可文字均在记录元数据内。机器可读性仍不足，属已披露的残留限制 |
| B2-07 | ~~生成链不自洽~~ **已闭环（2026-10-18）** | `paper_template.py` 已复制入仓、`generate_heat_tree_paper.py` 改为同目录相对导入 | 从干净环境按 README 能重建 docx（已实测：改相对导入后 `python generate_heat_tree_paper.py` 成功生成 docx） |
| B2-08 | ~~无版本化数值基线~~ **已闭环（2026-10-24）** | `MANIFEST.sha256` 182 项已随 `3e02b70` 提交，并重新对 `v1.0.0` 逐文件校验 | 已验收：对 tag `v1.0.0` 的 `git show` 内容重算，`182 verified / mismatch 0 / missing 0` |

### 6.2 不阻塞 L2、但应在投稿前完成

| ID | 缺口 | 动作 |
|---|---|---|
| B2-09 | 未声明研究未注册 | 论文方法或 §19 加一句"本研究为计算研究，未注册" |
| B2-10 | 未声明报告指南 | 加一句"未找到适用清单，故未使用" |
| B2-11 | 审稿期代码可得性 | Nature 要求审稿人可获取代码；准备匿名化副本或 Code Ocean 链接 |
| B2-12 | 数值容差 | 在复现节给出关键量的容差（如 `dTmax` 四位小数逐位一致），否则"可复现"不可检验 |

---

## 7. 结论

**核实事实**：TOP 2025 七项中，2 项处于 Level 1（第 2–3），2 项未达 Level 1（第 1、7），3 项（第 4–6）已具备"公开托管 + 持久标识（DOI）"但缺参考文献引用；严格满足三项条件的 Level 2 = 0 项，Level 3 = 0 项；两项 Verification Practices 均未验证。Nature Portfolio 的 Data availability 与 Code availability 两节的形式要件已具备（docx 段落索引 379 / 386，标题顺序 357 → 379 → 386 → 392）；实质要件中"发表后即可得、无不当限制、带持久标识"已由 Zenodo 记录 `23620419`（2026-10-24T14:45:14Z 发布）与 GitHub 公共仓库满足；唯一未满足的是"数据集以正式引用列入参考文献"。

**推理链**：Level 2 的三项条件为"公开托管 + 持久标识 + 在参考文献中引用"，三者缺一不可。前两项已由 Zenodo 版本 DOI `10.5281/zenodo.23620419`（概念 DOI `10.5281/zenodo.23620418`，二者经 `doi.org` 均 302 → `zenodo.org/records/23620419` 200）满足；第三项因参考文献中无数据集条目而未满足，故第 4–6 项只能判为"接近 L2 但非 L2"。Nature 的条款不要求在参考文献引用之外的额外动作：托管、DOI、无限制下载、OSI 许可（MIT）均已具备，故其实质要件仅在数据引用一项上缺失。作者与版权人已由占位符改为 `Wu, Haoran`，许可在法律上已有权利人；Zenodo 记录的 `creators` 亦为该姓名与 ORCID `0009-0005-1975-1511`。

**唯一结论**：**本项目当前为"TOP 2025：2 项 L1 + 2 项未达 L1 + 3 项'托管与 DOI 已具备、缺参考文献引用'，严格 L2 = 0、L3 = 0"；Nature Portfolio 的数据与代码可用性条款除"参考文献引用数据集"外均已满足。** 可以声称"数据与代码已公开归档并取得可解析 DOI"；不得声称"符合 TOP Level 2"或"已满足 Nature 全部数据与代码条款"。补齐路径只剩一步：在参考文献中增列数据集条目（`CITATION.cff` 为加分项，非 L2 的必要条件）。

**可以准确声称的**：数据与代码已永久归档于 Zenodo（v1.0.0 版本 DOI `10.5281/zenodo.23620419`、v1.0.1 版本 DOI `10.5281/zenodo.23621256`、概念 DOI `10.5281/zenodo.23620418` 始终指向最新版），并公开托管于 GitHub；作者、单位、ORCID 与许可权利人已落实到文件；论文含独立的 Data availability 与 Code availability 两节且位置符合 Nature 要求；数值结果可按 README 命令在本机重跑；单位陷阱、失败与作废记录已公开披露；3 个 `.slx` 因含易变时间戳而未纳入 MANIFEST（已在论文 §21 披露）。**v1.0.1 归档包已完成字节级校验**（2026-10-24 实测）：zip 大小 35,291,943 B 与 Zenodo API 的 `files[0].size` 相同；MD5 `e3933702bc9ebc2caf23f0d8853cbd27` 与 API 的 `files[0].checksum` 相同；包内 186 个文件与 tag `v1.0.1` 的 186 个 git blob 逐一重算 SHA-1 **全部相同（186/186，0 不同）**；包内 `MANIFEST.sha256` 182 项对包内文件重算 **182/182 吻合**；`src_extract/`、`参考论文/`、`_work/` 命中 **0**。

**不能声称**的：第三方独立复现、第三方认证、TOP Level 2；以及"Zenodo 归档 zip 与 GitHub 按同一 tag 重新生成的 zip 字节相同"——后者为假命题，实测 v1.0.0 两包差 3,582 B（34,817,027 vs 34,813,445），原因是 zip 容器的压缩时机与元数据不同。**须区分三个命题**：(a) 归档包内文件内容 = tag 文件内容 → 已证为真（186/186）；(b) 归档包字节 = 重新打包字节 → 已证为假；(c) 归档包 MD5 = Zenodo 声明的 MD5 → 已证为真。承诺可复现时只能引用 (a) 与 (c)。

---

## 8. 复核方式

```powershell
git rev-parse HEAD; git status --porcelain | Measure-Object -Line
(Get-ChildItem outputs -Recurse -File | Measure-Object Length -Sum)
(Get-Content MANIFEST.sha256 | Measure-Object -Line)
Test-Path CITATION.cff
python -c "from docx import Document; d=Document(r'论文\submission_ijts\Manuscript_IJTS.docx'); t=[p.text.strip() for p in d.paragraphs]; i=t.index('References'); print(i, t[i-1])"
python -c "import fitz; s=''.join(p.get_text() for p in fitz.open(r'论文\submission_ijts\Manuscript_IJTS.pdf')); print('10.5281/zenodo.23620419' in s, '10.5281/zenodo.23620418' in s)"
```

预期：`git status --porcelain` 为 0 行；`outputs` 磁盘为 76 文件 / 8,041,323 字节（其中 2 个 `*.bak_*` 被 `.gitignore` 排除），`MANIFEST.sha256` 收录 74 文件 / 7,778,123 字节、共 182 行；`CITATION.cff` 不存在（`False`）；IJTS 稿件的 `References` 前一段为生成式 AI 声明，且 `References` 索引随声明插入而较 196 后移；PDF 文本层同时含版本 DOI 与概念 DOI。任一预期变化，本文件的对应判定即需重做。
