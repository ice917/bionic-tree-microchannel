# 报告合规性对照（B2）

核验日期：2026-10-18
核验对象：本仓库工作树（HEAD `44e33ae`，`main` 分支；核验时点有 88 项未提交变更，生成本文件后该数只增不减）
判定对象：论文《仿生自适应网络用于芯片散热与布线》及其随附数据与代码

**版本注记（2026-10-24）**：本文件除本行外，其余数值均为 2026-10-18 核验时点的快照，未回改。此后 `MANIFEST.sha256` 刷新为 132 项（`outputs/` 70 项、37 个 `.py`、10 个 `.m`、7 个根目录 `.md`、`LICENSE`、`LICENSE-DATA`、`.zenodo.json` 与 `论文/` 下 5 项），3 个 `.slx` 因包内含每次保存变化的时间戳与随机生成的模型/调度 UUID 而移出清单（理由与替代验证方式见 `DATA_AVAILABILITY.md`）。

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
| 4 | Materials Transparency | 论文 §20 声明数值结果、图与几何文件位于 `outputs/` | `outputs/tree.stl`、`outputs/manifold_assembly.stl`、`manifold_geometry.json`、全部几何/求解源码；`README.md` 目录段列出。`tree_dynamic.stl` 生成器未入库、不可复现，不列为可得材料 | **L1**（已披露，未托管） | 托管 + DOI + 参考文献引用 |
| 5 | Data Transparency | 论文 §20 声明数据集位置、规模与单位警告 | `outputs/` 59 个文件、4.76 MB（4,763,033 字节）；`DATA_DICTIONARY.md` 逐文件说明 | **L1**（已披露，未托管） | 托管 + DOI + 数据引用；单位误标清单须随数据一同发布（已具备） |
| 6 | Analytic Code Transparency | 论文 §19 给出命令，§21 声明代码位置、许可与构建依赖 | 26 个 `.py`（含 `paper_template.py`）、13 个 `.m`/`.slx`；`LICENSE`（MIT）；`README.md` 复现段 | **L1**（已披露，未托管） | 托管 + DOI + 引用；docx 构建链已自包含（模板入仓、同目录相对导入） |
| 7 | Reporting Transparency | 未声明是否使用报告指南 | 无适用清单记录 | **未达 L1** | 论文加一句"未找到适用于计算传热/生成式设计的报告清单，故未使用" |

**计数：L1 = 5 项（第 2–6），未达 L1 = 2 项（第 1、7），L2 = 0 项，L3 = 0 项。**

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
| Data availability statement | 所有原创研究论文必须包含 | 论文 §20「数据可用性」已存在：数据集位置与规模、单位警告、不可得与作废、第三方材料、托管状态五段，标题位于 `19 复现` 与 `参考文献` 之间（docx 段落索引 384） | **形式要件满足**；托管与 DOI 不满足 |
| Code availability（独立小节） | 位于 data availability 之后、参考文献之前，说明获取方式与限制 | 论文 §21「代码可用性」已存在：代码位置、许可、构建依赖、已知不可复现项、托管状态五段（docx 段落索引 391，紧随 §20 之后） | **形式要件满足**；托管与 DOI 不满足 |
| 代码存入 DOI 铸造仓库并引用 | Zenodo / Code Ocean 等，参考文献列出 | `.zenodo.json` 仅为待上传元数据，无 DOI、无 `publication_date` | **不满足**（未托管） |
| OSI 认可许可证 | 鼓励 | `LICENSE` 为 MIT（[LICENSE](LICENSE#L1-L3)） | **满足**（但版权人仍为占位符） |
| 材料可得 | 无不当限制 | STL（`tree.stl`、`manifold_assembly.stl`）、源码在仓库；`tree_dynamic.stl` 不可复现，不作为可得材料主张；`src_extract/` 为第三方论文源码，明确排除在许可外（[LICENSE-DATA](LICENSE-DATA#L51-L53)） | **部分满足**：第三方材料不得随附再分发，须在上传前移除或取得授权 |
| 数据引用 | 数据集以正式引用列入参考文献 | 无数据集 DOI，参考文献中无数据引用 | **不满足** |
| Reporting summary | 物理科学仅对太阳能电池、激光声称等特定领域强制 | 本项目不属于强制领域 | **不适用** |
| "promptly available without undue qualifications" | 发表后即可得 | 当前仅本地目录，未公开 | **不满足**（尚未发表，属预期状态，但不得声称已满足） |

---

## 5. 支撑判定的事实清单（均可在仓库内复核）

1. **当前工作树不对应任何提交。** HEAD 为 `44e33ae81bb37ce58c7a76f745a7f864c6c0d735`（2026-10-15 17:57:50 +0800），`git status --porcelain` 本次核对计 88 行。N4c 修复、A2/A8/A9/A10 之后的论文、台账、`calibrate.py`、`ports_manifold.py` 均未提交。后果：无法用 commit 或 tag 唯一标识"产生这些数字的代码版本"。
2. **无 `CITATION.cff`。** `Glob CITATION*` 返回 0；README 自述"尚未创建"（[README.md](README.md#L84-L86)）。
3. **作者信息为占位符。** `LICENSE#L3`、`LICENSE-DATA#L42-L45`、`.zenodo.json#L4-L9` 均为 `TODO`；论文只有标题、摘要、关键词，无作者与单位行（[generate_heat_tree_paper.py](generate_heat_tree_paper.py#L24-L70)）。
4. **无 DOI、无发布日期。** `.zenodo.json` 中 `version = 0.1.0-draft`，无 `doi`、无 `publication_date`、无 `related_identifiers`。
5. **Zenodo 许可证字段无法表达混合许可。** `.zenodo.json#L12-L14` 为单值 `other-open`，而实际为 MIT + CC BY 4.0；说明写在 `description`/`notes`，机器不可读。可接受但不理想，L2 前应决定"拆分两条记录"或"保留 `other-open` + 说明"。
6. **数据与代码规模已实测。** `outputs/` 59 个文件、4,763,033 字节（4.76 MB），其中 `manifold_assembly.stl` 与 `manifold_geometry.json` 为 A2 新增。
7. **数据字典已披露单位陷阱。** `_C` 后缀不等于摄氏度；`DATA_DICTIONARY.md` 与 `README.md#L71-L76` 均列出三类单位状态。这是报告透明度的实质性加分项，但不改变 Data Transparency 的等级。
8. **论文生成已自包含（原缺口已修）。** `paper_template.py` 已复制入仓，`generate_heat_tree_paper.py` 改为同目录相对导入，不再依赖 `D:\数学建模`；docx 可在干净环境按 README 重建。
9. **第三方材料存在。** `src_extract/` 含他人论文的 `.tex`、`.eps`、`.sty`；`LICENSE-DATA#L51-L53` 明确不覆盖。任何公开托管前必须删除或取得再分发许可。
10. **许可证范围已修正。** `LICENSE-DATA` 原先只列 `REPORT.md`、`DATA_DICTIONARY.md`、`DEFECT_REMEDIATION_PLAN.md`，漏掉 `README.md` 与 `PROJECT.md`，与 README"数据与文档（`*.md`）CC BY 4.0"的表述冲突；现已补入 `README.md`、`PROJECT.md` 与本文件。
11. **完整性清单已生成。** `MANIFEST.sha256` 覆盖 `outputs/`（59 项）、26 个 `.py`（含新入仓的 `paper_template.py`）、13 个 `.m`/`.slx`、6 个根目录 `.md`、`LICENSE`、`LICENSE-DATA`、`.zenodo.json` 与论文 docx，共 108 项；校验 0 不匹配。`src_extract/` 为第三方材料，未纳入清单。
12. **STL 几何已逐三角形核验。** `tree.stl` 与 `manifold_assembly.stl` 均闭合（边界边 0），但非流形边分别为 228 / 236 条，未执行布尔并集；`tree_dynamic.stl` 294 个连通分量、生成器未入库。故"闭合"不等于"流形"，更不等于"可打印"（`DATA_DICTIONARY.md` §6 第 6–7 条）。

---

## 6. 缺口与补齐顺序

### 6.1 阻塞 L2 的项（按依赖顺序）

| ID | 缺口 | 具体动作 | 验收标准 |
|---|---|---|---|
| B2-01 | 作者/单位占位 | 替换 `LICENSE`、`LICENSE-DATA`、`.zenodo.json` 中全部 `TODO` | 全仓库 `TODO: 作者姓名` 0 命中 |
| B2-02 | 工作树未提交 | 提交 N4c 后的全部改动，打 tag（建议 `v0.1.0`） | `git status --porcelain` 为空；tag 指向该提交 |
| B2-03 | 无引用元数据 | 新建 `CITATION.cff`，含作者、标题、版本、许可证、仓库 URL | `cffconvert` 或等价校验通过 |
| B2-04 | ~~论文缺 Data/Code availability~~ **已闭环（2026-10-18）** | 已在 §19 之后、参考文献之前插入 §20 数据可用性、§21 代码可用性 | 已验收：docx 标题顺序为 `19 复现`(363) → `20 数据可用性`(384) → `21 代码可用性`(391) → `参考文献`(397)，两节均存在且顺序正确 |
| B2-05 | 未托管、无 DOI | 先移除/取得 `src_extract/` 授权，再上传 Zenodo，取得 DOI | DOI 可解析；`.zenodo.json` 与 README 写入 DOI |
| B2-06 | 混合许可与单值字段 | 二选一：拆成"代码"与"数据/文档"两条 Zenodo 记录；或保留 `other-open` 并在说明中逐项列明 | 元数据与实际许可一致，无歧义 |
| B2-07 | ~~生成链不自洽~~ **已闭环（2026-10-18）** | `paper_template.py` 已复制入仓、`generate_heat_tree_paper.py` 改为同目录相对导入 | 从干净环境按 README 能重建 docx（已实测：改相对导入后 `python generate_heat_tree_paper.py` 成功生成 docx） |
| B2-08 | 无版本化数值基线 | `MANIFEST.sha256` 已生成并自校验通过，但尚未提交 | 随 B2-02 一并提交；校验命令 0 失败 |

### 6.2 不阻塞 L2、但应在投稿前完成

| ID | 缺口 | 动作 |
|---|---|---|
| B2-09 | 未声明研究未注册 | 论文方法或 §19 加一句"本研究为计算研究，未注册" |
| B2-10 | 未声明报告指南 | 加一句"未找到适用清单，故未使用" |
| B2-11 | 审稿期代码可得性 | Nature 要求审稿人可获取代码；准备匿名化副本或 Code Ocean 链接 |
| B2-12 | 数值容差 | 在复现节给出关键量的容差（如 `dTmax` 四位小数逐位一致），否则"可复现"不可检验 |

---

## 7. 结论

**核实事实**：TOP 2025 七项中，5 项处于 Level 1，2 项未达 Level 1，0 项达到 Level 2；两项 Verification Practices 均未验证；Nature Portfolio 的 Data availability 与 Code availability 两节的形式要件已补齐（论文 §20、§21，docx 回读顺序为 `19 复现` → `20 数据可用性` → `21 代码可用性` → `参考文献`），但托管、DOI 与数据引用仍缺失；当前工作树有至少 88 项未提交变更，不对应任何 commit。

**推理链**：Level 2 的定义要求"公开托管 + 持久标识 + 引用"。本仓库所有数据与代码只存在于本地目录，`.zenodo.json` 无 DOI，参考文献无数据引用，故任何一项都不可能达到 Level 2；即使文件齐全、许可证正确，也不能替代托管与标识。Nature 的条款分两层：形式要件是"论文包含两节声明"，已由 §20/§21 满足；实质要件是"发表后即可得、无不当限制、带持久标识"，因未托管、无 DOI 而不满足。作者与版权人均为 `TODO`，意味着许可在法律上尚无权利人，托管也无法完成归属登记。

**唯一结论**：**本项目当前是"TOP Level 1（5/7）+ 两项未达 L1 + 零项 L2"的预发布状态；Nature Portfolio 的数据与代码可用性条款仅满足形式要件，实质要件（托管与 DOI）不满足。** 在 B2-01 至 B2-06 完成前，不得声称"已归档""已正式发布""符合 TOP Level 2""数据与代码已公开可用"或"完全可复现"；也不得因为存在 §20/§21 就声称"满足 Nature 数据与代码可用性要求"。

**可以准确声称的**：论文已包含独立的 Data availability 与 Code availability 两节，并按 Nature 的位置要求排在参考文献之前；数值结果可在本机按 README 命令重跑；数据与代码以 MIT + CC BY 4.0 随仓库提供（第三方 `src_extract/` 除外）；单位陷阱与失败记录已公开披露；DOI 与作者信息尚未分配。

---

## 8. 复核方式

```powershell
git rev-parse HEAD; git status --porcelain | Measure-Object -Line
(Get-ChildItem outputs -Recurse -File | Measure-Object Length -Sum)
Select-String -Path generate_heat_tree_paper.py -Pattern "数据可用性|代码可用性"
python -c "from docx import Document; d=Document(r'论文\仿生自适应网络芯片散热与布线.docx'); t=[p.text.strip() for p in d.paragraphs]; print([t.index(x) for x in ('19 复现','20 数据可用性','21 代码可用性','参考文献')])"
Test-Path CITATION.cff
```

预期：HEAD 为 `44e33ae`、dirty 行数 ≥88（核验时点为 88）、`outputs` 为 59 文件 / 4,763,033 字节、`MANIFEST.sha256` 为 108 项且校验 0 不匹配、生成脚本命中 2 处可用性标题、docx 中四个标题索引严格递增（核验时点为 363 / 384 / 391 / 397）、`CITATION.cff` 不存在。任一预期变化，本文件的对应判定即需重做。
