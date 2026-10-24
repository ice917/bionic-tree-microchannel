# Physarum 多源多汇：研究方案

> 状态：方案（未执行实验）
> 依据：仓库内可复核代码与已归档输出，逐条标注证据位置
> 目的：把"Physarum 多源多汇"从一句方向，压缩成**一组可被否证的命题 + 一套能判定真假的测量**

---

## 0. 先给结论

三条，均可由本文件后续章节复核：

1. **现有实现不能做多源多汇。** [physarum_route.m](file:///d:/解释token/heat_tree/physarum_route.m#L146-L153) 的供给约定是"前 np−1 个 pin 各 +1，最后一个 pin 吸收 −(np−1)"，即**多源单汇**；两点（n=12/20/28）验证全过，但 4 pin 的 `tree/MST = 1.333`、6 pin 随机布局出现 **6 个连通分量、`covers_all_pins = 0`**（[physarum_route_summary.txt](file:///d:/解释token/heat_tree/outputs/physarum_route_summary.txt#L75-L94)）。
2. **现有度量无法给多汇或有环网络打分。** [poiseuille_dp](file:///d:/解释token/heat_tree/verify.py#L841-L890) 明确只服务 "single-inlet / multi-outlet branching network"，内部依赖 [build_tree](file:///d:/解释token/heat_tree/radius.py#L18-L34) 的 `parent[c] = p`（重复 child 被覆盖）与 `root = edges[0][0]`。多汇、环路在数学上无法进入该函数。
3. **现有"多源热收益"尚未归因于拓扑。** 最佳点 "3 chips, triangle | budget 700" 的 `tree_pinned = 152`，而三个 17×17 源块的 N4 环共 `3 × 72 = 216` 格。**152 < 216 ⇒ 该算例的环没有被全部钉住**，因此"环覆盖 ⇒ Tmax 与拓扑无关"的引理前提**不成立**，−4.6886 °C 也不能仅凭此归因于树形拓扑。这是本方案必须首先补的测量缺口。

因此本方案的主线是：**先修测量，再谈结论**；核心可证伪命题是"饱和型自适应律产生的环状网络，能否在等钉住格/等材料/等总占据格下把 Δp 显著降下来，且热性能不退"。

---

## 1. 证据台账

证据等级：**A** = 直接读文件/跑命令得到的数值；**B** = 由 A 级事实经定义或算术推出；**C** = 尚未核对原文，不得当作事实使用。

### F1 模型与离散（A）

[physarum_route.m](file:///d:/解释token/heat_tree/physarum_route.m)：

| 项 | 位置 | 内容 |
|---|---|---|
| 供给 | L146–153 | 前 np−1 个 pin `+1`，最后一个 pin `−(np−1)` |
| 阈值 | L155 | `thresh = 0.5`，**硬编码、绝对量、非尺度不变** |
| 初值 | L168 | `D = 0.5 * ones(ne,1)` |
| 阻尼 | 外部入参 `hval` | 无默认值写死，实测用 0.01–0.5 |
| 迭代 | L172–192 | `Lp = diag(sum(A,2)) − A`，`q = (D./elen).*|Δp|`，`D ← (1−h)D + h q` |
| 收敛 | L186–191 | `max|D−q| / max(D) < 1e-6`，且 `it > 100` |
| 后处理 | L221, L230 | `keep = D > 0.5`，再对支撑集做 Prim MST |
| 障碍 | L126–144 | 先压缩到自由子图，再检查连通分量数，>1 直接报错 |

### F2 两点验证（A）

[physarum_route_summary.txt](file:///d:/解释token/heat_tree/outputs/physarum_route_summary.txt#L24-L31)：

| n | 迭代 | 边数 | 期望 | 欧氏误差 |
|---|---|---|---|---|
| 12 | 990 | 11 | 11 | 3.6e-15 |
| 20 | 1605 | 19 | 19 | 1.1e-14 |
| 28 | 2193 | 27 | 27 | 0 |

→ 在 BMV 有定理保证的两端点区间，实现是**正确**的。这点必须先承认，否则后续否定会成为"实现坏了"而非"模型不够"。

### F3 多端点失效（A）

同文件 L33–94：

| 算例 | raw 边 | raw 分量 | MST 边 | 覆盖全部 pin | tree/MST |
|---|---|---|---|---|---|
| case1 4 角点 | 57 | 1 | 57 | 是 | 1.3333 |
| case2 5 pin + 墙 | 33 | 3 | 26 | 否 | 0.7761 |
| case3 随机 6 pin | 40 | **6** | **5** | **否** | 0.2128 |

case1 的 `tree/MST = 4/3`：支撑集在曼哈顿度量下比最小生成树**长 33%**，且 MST 抽不出来（边数不变 ⇒ 支撑集本身就是树但有冗余绕行）。case3 则是彻底的连通性失败。

### F4 阻尼敏感性（A，且是一条**否定性**证据）

同文件 L96–103，n=16、4 角：`h ∈ {0.01,0.05,0.1,0.2,0.3,0.5}` 六档，`raw_e = tree_e = 45`、`tree_eu = 51.2132`、`tree_mh = 60.0`、`conn = 1` **完全一致**；只有固定点残差从 6.65e-3 单调改善到 1.95e-6。

→ 在这个算例上，**支撑集对 h 不敏感**。任何"Physarum 结果不可复现/对参数高度敏感"的说法，在此区间已被否证，不得写进论文。

### F5 度量缺口（A）

[poiseuille_dp](file:///d:/解释token/heat_tree/verify.py#L841-L890) 的 docstring 自述：

- 只适用于 single-inlet / multi-outlet；
- 流量口径为 demand-driven（convention A，每个叶 1 单位），`q = demand/total_demand`；
- `r_edge = 8μ·pitch/(π r⁴)`；
- 返回 `path_dp(root) = max over children`；
- `as_network=False` 仅用于复现历史串联和。

[build_tree](file:///d:/解释token/heat_tree/radius.py#L18-L34)：`parent[c] = p` 后写覆盖前写；`root = edges[0][0]`；`depth` 只从该 root 出发 DFS，**环上节点不在 `depth` 里**，`node_flows` 的 `sorted(..., key=-depth[i])` 会抛 KeyError 或给出错误流量。

→ **有环网络与多汇网络的 Δp 目前无法定义**，这不是精度问题，是定义域问题。

### F6 热侧接口（A）

- [apply_channels](file:///d:/解释token/heat_tree/verify.py#L131)：`mask = channel_mask(...) & ~src`，通道格钉在 `T_COOL`，内点五点迭代，`Bi=0` 时边界 Dirichlet。
- [control_metrics](file:///d:/解释token/heat_tree/multi_source.py#L175-L178) 只调 `radial_group_pinned(target_pinned=tg.pinned_cells, total_area_mm2=tg.total_area_mm2)`。
  → 对照组只对齐**钉住格数**与**材料量**，**不对齐环覆盖**。这是 G3 缺陷的直接来源。

### F7 单源基准数值（A）

[run_report.json](file:///d:/解释token/heat_tree/outputs/run_report.json) `compare`：

| 量 | 树 | 直管 |
|---|---|---|
| T_max (°C) | 27.596 | 27.596 |
| T_mean_solid (°C) | 25.02 | 25.02 |
| hotspot (mm²) | 25.0 | 25.0 |
| Δp | 7.3472 | 0.0237 |
| 材料 (mm²) | 651.461 | 651.461 |
| 段数 | 399 | 8 |

`dp_ratio_tree_over_straight = 310.17`。

**必须限定解读**：这是"**等材料**"口径下树 vs 单根直管。它不等于"树的水力最优性被否证"，也不等于"直管更好"。等材料 ≠ 等压降 ≠ 等泵功。

### F8 多源算例归档（A，且修正了先前口误）

[multi_source_summary.json](file:///d:/解释token/heat_tree/outputs/multi_source_summary.json) 实测：`rows = 32`，其中

- **24 行** = 4 布局 × 6 预算（`LAYOUTS` 4 种、`BUDGETS = (400,600,700,800,1000,1300)`，[multi_source.py](file:///d:/解释token/heat_tree/multi_source.py#L41-L54)）；
- **8 行** = 芯片间距扫描 `d ∈ {6,8,10,12,16,20,24,30} mm`；
- **6 行 skipped**，全部是 "5 chips, corners+centre"（N4b 门禁）。

→ 正确计数是 **32 行 / 26 个已解 / 6 个被拒**，不是此前口头说的"24 个设计点、18 个解出"。

最佳点：

| case | ΔT_max | ΔT_mean | dp_ratio | tree_pinned | 材料 mm² |
|---|---|---|---|---|---|
| 3 chips, triangle \| 700 | **−4.6886** | −2.0030 | 75.2 | **152** | 1177.433 |
| 3 chips, triangle \| 800 | −4.6468 | −2.0287 | 79.1 | 182 | 1336.776 |
| 3 chips, triangle \| 600 | −4.6318 | −1.9391 | 71.7 | 123 | 1042.740 |

### F9 5 芯片布局在真实尺寸下不可用（A）

[multi_source.py](file:///d:/解释token/heat_tree/multi_source.py#L279-L290)：`layout_is_valid(..., radius=SRC_RADIUS_REAL)` 判定 5-chip 布局的源块**融合成一个区域**，6 个预算全部 skipped。

算术复核（B）：`SRC_RADIUS_REAL = 8`（[field.py](file:///d:/解释token/heat_tree/field.py#L36)），[source_mask_multi](file:///d:/解释token/heat_tree/field.py#L68-L79) 生成的是**方框** `|Δy| ≤ 8 且 |Δx| ≤ 8`，即 17×17 = 289 格/芯片。四角 (12,12)(12,38)(38,12)(38,38) 与中心 (25,25)：

- 角块行域 4–20，中心块行域 17–33 → **17–20 重叠**，故融合。

其余布局不重叠：4 芯片 = 1156/2500 = **46.24%** 板面是源；3 chips 三角布局三块两两不重叠。

### F10 双 pitch 是设计约定，不是缺陷（A）

[calibrate.py](file:///d:/解释token/heat_tree/calibrate.py#L226-L240) 明确：`field.PITCH_MM = 1.0` 是无量纲求解器的**定义性常数**；`paper_grid_mm() = 0.9` 是映射到 45 mm 封装的**映射参数**；真实单位 Δp 必须走 `calibrate.tree_dp_pa(..., paper_grid_mm())`。历史上把两者"统一"会错。

→ 方案里**不得**把"pitch 不统一"列为待修缺陷。

### F11 CTS 中 Physarum 只作电路类比（A）

[_work/dump_manuscript.txt](file:///d:/解释token/heat_tree/_work/dump_manuscript.txt#L46)：

> "This paper borrows its electrical analogy for cross-validation, but the routing itself still uses heat-field-driven growth..."

→ 新工作与 CTS 稿件**无结论重叠**，但也不能在双盲评审期把新稿写成"我们已发表工作的延伸"。

### F12 支撑集阈值不是尺度不变量（A/B）

`D` 的初值 0.5、收敛后 `||D||_1` 在 35–57（F2/F3 表），阈值 0.5 相当于保留约 1%–1.4% 的"质量"；而供给总量随 pin 数变化（np−1）。因此同一 `thresh = 0.5` 在不同 np 下代表**不同的相对严格度**。这是 case2/case3 连通性差异的一个候选解释（**假设，未验证**）。

---

## 2. 两个分析性结果

这两条是本方案真正"新"的部分，也是把方向压成命题的杠杆。**均为可手算复核的推导，不依赖实验。**

### L1 局部决定性引理（源块温度与环外拓扑无关）

**设定**：域 Ω 上五点差分，均匀导热系数，源块 S 上热源 q，S 外无内热源；通道格集合 C 取 Dirichlet 值 T_cool。设 ∂S 为 S 的 N4 邻接格集合（"环"）。

**命题**：若 ∂S ⊆ C，则 T|S 唯一确定于 (q, T_cool, S, ∂S)，与 Ω \ (S ∪ ∂S) 上的任何拓扑选择无关。

**证明**：把离散方程按 (S, ∂S, 其余) 分块：

```
A_SS T_S + A_S∂ T_∂ = q_S
```

∂S 全为 Dirichlet ⇒ T_∂ 已知。`A_SS` 是五点 Laplacian 的主子块：对角占优、不可约（S 连通），且**至少有一行严格占优**（与 ∂S 相邻的 S 格），故 `A_SS` 为非奇异 M-矩阵，`T_S` 唯一。`max_S T` 因而只依赖 `(q_S, T_∂)`。∎

**两条必须写进实验设计的推论**：

1. 引理只管 `max_S T`，**不管全局 T_max**。若全局 argmax 落在源块外（板上），拓扑仍会影响读数。→ 每次求解必须记录 argmax 坐标，并判定 `argmax ∈ S` 与否。
2. 多源同样成立：对每个源块独立套用即可。⇒ **多源下"Tmax 随拓扑改善"在环全覆盖时应当消失**；能区分拓扑的只剩 Δp、材料、热区面积、以及环未覆盖时的部分钉住效应。

**F8 的直接后果**：最佳点 `tree_pinned = 152 < 216 = 3 × 72`，环未全覆盖，引理前提不成立。所以 −4.6886 °C **既可能是拓扑贡献，也可能是"部分环覆盖"贡献**，现有数据无法区分。这就是 P1b 必须做 ring-matched 对照组的原因。

### L2 合并判据（什么自适应律会"催促合并"，什么会"催促铺网"）

设管道单位长度水力传导 `C_e = D_e / L_e`，并把 `D_e` 按 Poiseuille 认同为 `D_e = π r_e⁴ / (8μ)`（即 `C_e = π r_e⁴/(8μL_e)`，与现有 `r_edge = 8μL/(πr⁴)` 严格互逆）。自适应律的平衡映射记为 `D_eq = φ(Q)`。

单段压降：

```
Δp_e = 8μ L Q / (π r⁴) = 8μ L Q / (8μ φ(Q)) = L · Q / φ(Q)
```

即**单位长度压降只由 `Q/φ(Q)` 决定**。把两根各载 q 的等长管合并为一根载 2q：

```
Δp(2q)/Δp(q) = 2 φ(q) / φ(2q)
```

| φ | 合并比 | 含义 |
|---|---|---|
| `φ(Q) = Q`（BMV 线性） | **1（严格中性）** | 合并不省压降；这正是"等成本平衡解不唯一"的机理，与 BMV Thm 8 需要无等成本双平衡的假设一致 |
| `φ(Q) = Q^μ`，μ = 4/3（等价 r ∝ Q^{1/3}，Murray） | `2^{−1/3} = 0.7937` | 合并每段省 20.6% |
| `φ(Q) = Q^μ`，μ > 1（超线性） | `< 1` | 合并有利 |
| `φ(Q) = Q/(1+Q/K)`（饱和） | `2(K+2q)/(K+q) > 2` | **合并被惩罚**，网络倾向并行铺开（网格） |
| Tero `f(Q)=Q^μ/(1+Q^μ)` | `2^{1−μ}(1+2^μ q^μ)/(1+q^μ) > 2` | 同上，饱和 ⇒ 惩罚合并 |

**结论（可写进论文的判据）**：合并是否省压降，取决于平衡映射 `φ` 是否超线性；线性中性、饱和惩罚。**这给出了"BMV 长不出网格、Tero 长得出网格"的一个纯解析解释**，也说明现有 4 角算例 `tree/MST = 1.333`（比 MST 长 33%）不是实现错误，而是线性律没有"铺开"的驱动力。

**必须同时承认的反向事实**：单源树在等材料下 Δp 是直管的 310.17 倍（F7）。这不构成"树水力最优"的证据，也不构成"树水力失败"的证据——口径不同。

**风险标注（C 级）**：`D_e ∝ r⁴` 与 `Tero 的 f` 精确形式需回原文核对（§9）。若 Tero 的传导是 `Q = D γ Δp/L` 且 γ ≠ 1，则上表需重算。**在核对完成前，L2 只作为设计假设，不作为结论。**

---

## 3. 已识别的缺口（每条对应后续一节实验）

| 编号 | 缺口 | 证据 | 阻断什么 |
|---|---|---|---|
| G1 | 无多汇/有环网络 Δp 定义 | F5 | 一切"多汇水力"结论 |
| G2 | 支撑集阈值绝对、非尺度不变 | F12 | 跨 np 比较、连通性归因 |
| G3 | 无环覆盖度量 | F6 + F8 | −4.69 °C 的归因 |
| G4 | 结果只写 .txt，无 JSON/种子/哈希 | [physarum_route_main.m](file:///d:/解释token/heat_tree/physarum_route_main.m) | 可复现、可审计 |
| G5 | 无多端精确基线（ILP/RSMT 仅 np ≤ 6，>6 返回 NaN） | [physarum_route.m](file:///d:/解释token/heat_tree/physarum_route.m#L242-L248) | "接近最优"的任何表述 |
| G6 | 5 芯片在真实尺寸下几何不可行 | F9 | 五源算例 |
| G7 | 对照组未对齐环覆盖 | F6 | 热收益归因 |

---

## 4. 方法：五个阶段，每个都有退出条件

### S0 修度量（**阻塞项**，不通过不得进入 S1）

**S0.1 通用水力求解器** `network_dp(edges, radii, sources, sinks, pitch_mm)`

- 组装 `R_e = 8μL_e/(π r_e⁴)`，`L_e` 用米制（`paper_grid_mm()`，见 F10），节点方程 `G p = b`；
- 源节点注入 `+Q`（总流量归一为 1），汇节点 `p = 0`（Dirichlet），其余节点 KCL；
- 输出：`dp = max_s p_s − 0`、每个汇的分流、质量守恒残差。
- **验收**：(i) 在纯树上与 `poiseuille_dp` 相对误差 < 1e-12；(ii) 8 节点环（1 入 1 出）给出有限 dp 且 Kirchhoff 残差 < 1e-14；(iii) 2 源 2 汇可解且 `ΣQ_in = ΣQ_out` 到 1e-14。

**S0.2 尺度不变阈值**

- 以质量分位替代绝对值：`keep = {e : D_e ≥ q_ε(D)}`，`q_ε` 取使 `Σ_{keep} D ≥ (1−ε) Σ D` 的最小边集；报告 `ε ∈ {1e-1, 1e-2, 1e-3, 1e-4}` 的支撑集 Jaccard 曲线。
- **验收**：两点 n=20 在所有 ε ≤ 1e-2 下仍恰好 19 边（保住 F2）。

**S0.3 连通性口径**

- 分开报告 `n_components`、`pins_covered_raw`、`pins_covered_after_MST`、`tree_over_mst`；MST 必须**逐分量**做并在图上标出失联 pin。
- **验收**：case2/case3 复现 F3 的 3/6 分量与 0 覆盖（作为回归测试）。

**S0.4 归档 schema**

- 写 `outputs/physarum_ms.json`：`instance_hash, family(φ), params, h, ε, seed, iters, fp_residual, support_hash, |support|, components, pins_covered, β1(cycle rank), dp_network, dp_tree_crosscheck, material, ring_coverage_per_chip, argmax_in_source`。

**S0.5 环覆盖度量**（G3 的核心）

- `ring(S) = N4(S) \ S`；`ring_coverage = |ring(S) ∩ C| / |ring(S)|`，逐芯片报告。
- 先做**回溯**：把已归档的 26 个已解算例重算环覆盖，得到"ΔT_max vs ring_coverage"的散点。**这一步不需要任何新优化，只需重算读数**，是性价比最高的验证。

### S1 模型谱系（否定性主实验）

三种平衡映射，同一套网格/初值/收敛判据：

- **M1** `φ(Q)=Q`（BMV，现状）
- **M2** `φ(Q)=Q^μ/(1+Q^μ)`（Tero 型饱和；μ 与尺度参数扫）
- **M3** `φ(Q)=Q^{4/3}`（Murray 一致，对应 r ∝ Q^{1/3}）

实例阶梯：`(1源,1汇)` → `(2源,1汇)` → `(2源,2汇)` → `(3源,3汇)`，网格 20×20 与 40×40，种子 20 个。

**每实例记录**：分量数、pin 覆盖、β1、S0.2 的 ε 曲线、dp、材料。

**退出条件**：三种 φ 在 `(2源,2汇)` 上的 β1 与 dp 有可区分的分布（Mann–Whitney，α = 0.05，效应量报告）；否则说明该实例族分辨不出模型差异，换实例而非改结论。

### S2 热-流耦合（归因实验）

- 复用 [apply_channels](file:///d:/解释token/heat_tree/verify.py#L131)，三级公平基准（等钉住格 / 等材料 / 等总占据格）；
- **新增 ring-matched 对照组**：对每个树，提取每个芯片的 `ring_coverage` 计数，构造一个只钉住"同样数量、同样位置分布"环格 + 同 pinned 总数 + 同材料的径向对照；
- **必记**：`argmax` 坐标、`argmax ∈ S` 端口集合、每个源的 `ring_coverage`。

**退出条件**：给出 `ΔT_max(tree − ringmatched) ` 的分布（种子级），以及它与 `ΔT_max(tree − radial)` 的差值分解。

### S3 多汇水力学

- 用 S0.1 求解多汇分流，报告 `dp`、分流不均衡度 `max|Q_sink| / mean|Q_sink|`；
- **一致性测试**：纯树且全部叶为汇时，S0.1 的解必须与 `node_flows` 的 demand-driven 流量在 1e-10 相对误差内一致。这是一条"证明旧度量在其定义域内正确"的测试，不是新发现。

### S4 与热模型的接口与报告中止规则

- 任何"拓扑更好/更差"的表述，必须同时给出：三级公平基准、环覆盖、argmax 归属、dp 求解器版本；
- 若 S0.5 显示 ΔT_max 与 ring_coverage 的相关性 > 0.9，则**停止**把热收益写作拓扑收益。

---

## 5. 可证伪命题（预登记阈值与判决规则）

阈值取法：数值分辨率 0.001 °C；网格 GCI 约 1.7%（论文已记录）；故 0.2 °C ≈ 4% 的 4.69 °C 效应量，作为"可忽略"边界。

| 编号 | 命题 | 预测 | 否证条件 | 判决后的动作 |
|---|---|---|---|---|
| **P1** | L1 引理在实现中成立：两个拓扑不同但 `ring(S)` 钉住集合相同的树，若 `argmax ∈ S`，则 `|ΔT_max| < 1e-6 °C` | 成立 | `> 0.01 °C` | 实现或模型理解有错，回到 F6/S0.3 审计，不得继续 |
| **P1b** | 热收益归因：`ΔT_max(tree − ringmatched)` 是主要来源，而非拓扑 | 预测 | 若 `> 0.2 °C`（即 >4% 的影响仍由拓扑贡献） | 两种结局都写：若 `< 0.2 °C`，标题句改为"环覆盖效应"；若 `> 2 °C`，拓扑归因成立并需给出机理 |
| **P2** | 饱和律（M2）在多汇下产生环路，且等材料下 `dp_mesh / dp_MST < 0.5` | 成立 | 所有 (μ,K) 下 `> 0.8` | 卖点退回"拓扑稳健性/单段失效容忍"，删除水力优势主张 |
| **P3** | 支撑集对 `(D0, h)` 敏感 | **已知反例**：4 角、n=16、h∈[0.01,0.5] 下 45 边不变（F4） | 若多汇实例 Jaccard ≥ 0.9 | 该区间内"不可复现"主张作废；不稳定主张只允许限定在具体实例上 |
| **P4** | case3 的 6 分量是阈值伪影而非模型失效 | 若 ε 扫描下 pin 覆盖升到 100% | 若所有 ε 仍分 6 分量 | 前者 ⇒ 缺陷定性降级为"阈值选择"；后者 ⇒ 保留"多端点失效"结论 |
| **P5** | S0.1 在纯树上退化为 demand-driven `node_flows` | 1e-10 内一致 | 不一致 | 说明旧度量流量口径与水力解不符，历史 Δp 数字需重算并标注 |
| **P6** | 环路在等总占据格下"有得必有失" | dp 降 ≥ 2× 且 ΔT_max 升 > 0.5 °C | 若两者同时改善 | 则是干净的帕累托改进，可作主结果；若只降 dp 但 ΔT_max 恶化 ≤ 0.5 °C，写成权衡曲线 |

**P3 的写法必须特别小心**：F4 已经是一个**反向证据**，方案里不能预设"Physarum 不稳定"。正确写法是"在不稳定被证实之前，所有跨种子比较都要报告分布，不得用单次运行代表一个模型"。

---

## 6. 与 CTS 稿件的边界

1. **不重叠**：CTS 明确写 Physarum 仅用于电路类比（F11）。新工作不复用 CTS 的树形结果。
2. **不自我引用成既成事实**：CTS 在审（双盲），新稿在评审期不得以"我们已发表"口吻引用；如需引用，标 "under review" 或直接避免。
3. **数字口径必须自洽**：CTS 的 310.17（F7）是等材料下树 vs 直管；新工作若给多汇 dp，必须写清与 310.17 不同口径，不得并列成"同尺度比较"。
4. **热收益复用要标注**：F8 的 −4.6886 °C 属 CTS 多源部分的分析；新工作重算它必须标为"re-analysis"，并披露本方案 S0.5 找到的环覆盖缺口。

---

## 7. 交付物与验收

**代码**（新目录 `physarum_ms/`，与现有 MATLAB 并行而非替换）

```
physarum_ms/
  network.py      S0.1 通用水力求解器
  support.py      S0.2/S0.3 阈值、分量、Jaccard、β1
  adapt.py        S1 三种 φ，固定种子
  ringcov.py      S0.5 环覆盖
  baselines.py    MST / RSMT / 连通子图 ILP
  experiments.py  S1–S3 编排
  tests/          下列验收的自动化测试
```

**验收（全部为可执行断言，不接受"看起来对"）**

1. `network_dp` vs `poiseuille_dp`：树上相对误差 < 1e-12；
2. 环图 Kirchhoff 残差 < 1e-14；
3. 两点 n=20 在 ε ≤ 1e-2 下边数 = 19（回归 F2）；
4. case2/case3 分量数复现 3 / 6（回归 F3）；
5. Python 移植与 `physarum_route.m` 在三个既有算例上逐位一致（|Δ| < 1e-12 或完全相同边集）；
6. `outputs/physarum_ms.json` 含 S0.4 全部字段 + 支撑集 SHA256；
7. 单命令复现：`python -m physarum_ms.experiments --config configs/default.json`。

**风险与止损**

| 风险 | 依据 | 止损 |
|---|---|---|
| 5 源不可测 | F9 | 只报 1–4 源；5 源作为"几何约束"结论单列 |
| 4 源环覆盖 288 格、预算 400 仅余 112 格 | B 级算术 | 4 源只用 ≥ 700 预算；低于则标"预算受限"不入结论 |
| 46.24% 板面是源，热对比被压缩 | F9 算术 | 加 `SRC_RADIUS = 2`（合成尺度）对照，和 `= 8` 一起报 |
| BMV 线性律平衡解不唯一 | L2 | 一切比较用 20 种子分布，不用单次运行 |
| MATLAB 依赖 | 现状 | Python 为首选实现，MATLAB 只作交叉验证 |

---

## 8. 执行顺序（严格串行，前一项不通过不进下一项）

```
S0.1 → S0.2 → S0.3 → S0.4 → S0.5
                                 │
                                 ├─ 回溯 26 个已解算例的环覆盖（不改任何优化）
                                 │      └─ 若相关性 > 0.9 ⇒ 先改写热收益表述，再往下
                                 ↓
                            P1（引理自检）
                                 ↓
                            S1（模型谱系，P2/P4）
                                 ↓
                            S2（环匹配对照，P1b/P6）
                                 ↓
                            S3（多汇水力，P5）
                                 ↓
                            成文（含反例台账）
```

**P3 并行**：它只是已有 F4 的扩展，不阻塞主线。

---

## 9. 文献核对清单（**C 级，未核对前不得引用**）

| 项 | 要核对的具体内容 | 为什么必须核对 |
|---|---|---|
| Tero, Kobayashi, Nakagaki 2007, *JTB* 244:553–564 | `f(Q)` 精确形式；传导与 D 的指数（γ 是否为 1） | L2 的整张判据表依赖它 |
| Tero et al. 2010, *Science* 327:439–442 | 是否给出多源多汇算例；拓扑是否为网格 | "饱和 ⇒ 铺网"的经验依据 |
| Bonifaci, Mehlhorn, Varma 2012, *JTB* 309:121–133 | Thm 7 与 Thm 8 的**确切假设**（尤其"无等成本双平衡"） | F1/摘要里已写，但需原文确认，不得凭转述 |
| Straszak & Vishnoi 2016, arXiv:1601.02712 | eq.(12)、Lemma 5.6（`||D||_1` 单调不增） | 离散格式正确性 |
| Sun 2019, arXiv:1903.08926 | "多源求解器保存的网络不保证是树、不保证连通"的原文表述与条件 | 后处理 MST 的正当性 |
| Nakagaki, Yamada, Tóth 2000, *Nature* 407:470 | 原始实验条件（多源多汇的具体设置） | 与"生物动机"表述的边界 |
| Murray 1926, *PNAS* 12:207–214 | `r³` 律的原始假设（层流、稳态、代谢成本） | F7/310× 的口径限定 |

---

## 10. 反例台账（已有的、必须继承的否定性结果）

| 编号 | 反例 | 数据 | 禁止的表述 |
|---|---|---|---|
| C1 | 4 角 4 pin 支撑集比 MST 长 33% | `tree/MST = 1.333`，F3 | "Physarum 产生近最优树" |
| C2 | 6 pin 随机布局 6 分量、0 覆盖 | F3 | "多端点自然收敛" |
| C3 | h 从 0.01 到 0.5 支撑集完全不变 | F4 | "对阻尼高度敏感/不可复现" |
| C4 | 5 芯片真实尺寸源块融合 | F9 | "五源扩展已验证" |
| C5 | 单源等材料下树 Δp = 直管 310× | F7 | "树水力最优" |
| C6 | 最佳多源热收益算例 `tree_pinned = 152 < 216` | F8 + B 级算术 | "热收益来自树形拓扑" |

---

## 11. 一句话收口

**多源多汇下，只要每个源的 N4 环被通道全覆盖，全局 T_max 的来源就被局部子问题钉死，拓扑不再是热端的自变量（L1）；真正能区分拓扑的只有 Δp、材料与热区面积。而 Physarum 能否在多汇下产生"既连通、又在水力上真正更优"的网络，取决于它的平衡映射是否超线性（L2）——线性律严格中性，饱和律反而惩罚合并。所以本研究的可证伪核心是：饱和型自适应律产生的环状网络，能否在等钉住格/等材料/等总占据格下把 Δp 降下来且热性能不退。**

---

## 附：本文档中所有"已核实"项的复核方式

| 事实 | 复现命令/位置 |
|---|---|
| F1 | 读 [physarum_route.m](file:///d:/解释token/heat_tree/physarum_route.m#L146-L192) |
| F2–F4 | 读 [physarum_route_summary.txt](file:///d:/解释token/heat_tree/outputs/physarum_route_summary.txt) |
| F5 | 读 [verify.py](file:///d:/解释token/heat_tree/verify.py#L841-L890)、[radius.py](file:///d:/解释token/heat_tree/radius.py#L18-L34) |
| F6 | 读 [verify.py](file:///d:/解释token/heat_tree/verify.py#L131)、[multi_source.py](file:///d:/解释token/heat_tree/multi_source.py#L175-L178) |
| F7 | `python -c "import json;print(json.load(open('outputs/run_report.json'))['compare'])"` |
| F8 | `python -c "import json;d=json.load(open('outputs/multi_source_summary.json'));print(len(d['rows']))"` → 32 |
| F9 | 读 [multi_source.py](file:///d:/解释token/heat_tree/multi_source.py#L279-L290) + [field.py](file:///d:/解释token/heat_tree/field.py#L68-L79) |
| F10 | 读 [calibrate.py](file:///d:/解释token/heat_tree/calibrate.py#L226-L240) |
| F11 | 读 [_work/dump_manuscript.txt](file:///d:/解释token/heat_tree/_work/dump_manuscript.txt#L46) |
