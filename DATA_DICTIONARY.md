# 数据字典

本表覆盖 `outputs/` 下全部 59 个文件（含两个中间件目录）。**路径相对于仓库根目录。** 读取任何温度数值前，先看"单位状态"一栏；`T` 只在标注"物理 °C"时才是摄氏度。

## 0. 单位状态总则

| 状态 | 含义 | 文件 |
|---|---|---|
| **物理 °C** | 17×17 真实 die 足迹、8.0 W/cm² 口径，或 A7 修复后的真实单位标定 | `multi_source_*`、`spread_source_thermal_*`、`lattice_pitch_*`、`unequal_power_pitch_*`、`c5_artifact.json`、`p0a_artifact.json`、`conjugate_*.json`、`real_unit_calibration.txt` |
| **无量纲标度（部分列名误带 `_C`）** | "峰值归一化到 100 后生长"的 MATLAB/早期 Python 口径；`27.5962` 是标度值，不是 °C | `bionic_placement_results.csv`、`bionic_placement_summary.txt`、`multisource_coupled_results.csv`、`matlab_coupled_summary.txt`、`matlab_multisource_coupled_summary.txt`、`matlab_verify.txt`、`COMPARISON.txt` |
| **无量纲/归一化（无 `_C` 后缀）** | 只用于相对比较或收敛研究，绝对幅值无物理意义 | `robin_boundary_*`、`run_report.json`、`a4_grid_convergence.json`、`extend_surface_*` |

`extend_surface_*` 的场在生长前被归一化到峰值 100，故 `tree_T_max = 61.6695` 属任意标度；该文件不得与 `multi_source_*` 的 °C 数值混用。

## 1. 单源基础链（`heat_tree.py`）

| 文件 | 内容 | 单位状态 |
|---|---|---|
| `outputs/run_report.json` | 热场（50×50，中心 5×5 源）、解析校验（对数斜率比 1.0064）、树统计（400 节点/399 边/度分布）、偏源生长签名、Murray 误差、STL 统计、树 vs 直通道对比 | 无量纲（场中心被归一化到 100） |
| `outputs/tree_edges.csv` | 399 条边：`parent_idx,child_idx,py,px,cy,cx,r_parent_mm,r_child_mm` | 坐标=格点，半径=mm |
| `outputs/murray_check.csv` | 每个父节点的 `r_parent`、子节点 `r³` 和、相对误差；57 行 | 半径=mm |
| `outputs/tree.stl` | 芯片层通道树骨架：19152 三角形、5790 顶点、边界边 0、非流形边 228、连通分量 1；两端共面于 `z=2.5`，z 跨度 3.936497 mm 由最大管半径决定 | mm |
| `outputs/manifold_assembly.stl`, `outputs/manifold_geometry.json` | A2 封装级冷却通道装配（`ports_manifold.py`）：25136 三角形、边界边 0、非流形边 236、连通分量 2；JSON 记录通道/盖板/集流环/端口几何参数 | mm |
| `outputs/tree_dynamic.stl` | 耦合树 STL。**不可复现**：生成器未入库，`tree_edges_dynamic.csv` 无半径列。实测 294 个连通分量、有向体积 −2891.090 mm³（法向朝内）、bbox 48.120 × 45.211 × 5.615 mm（超出 45 mm 封装）。保留为历史产物，不参与可制造性主张 | mm |
| `outputs/step1_heatmap.png` | 单源温度场 | 图；标度随 run_report |
| `outputs/step2_tree.png`, `step2b_tree_offsource.png`, `step2c_coupled_tree.png` | 树形态、偏源对照、共轭场上的树 | 图 |
| `outputs/step5_straight_cooled.png`, `step5_tree_cooled.png` | 直通道 vs 树冷却后的场 | 图 |
| `outputs/COMPARISON.txt` | 静态树（Python）/耦合树（MATLAB）/直通道 ×8 的指标对照；`T_max [C] = 27.5962` | **无量纲标度，列名 `[C]` 误标** |

## 2. 多芯片布局与格状网对照（论文 §9、§10）

| 文件 | 生成 | 内容 | 单位 |
|---|---|---|---|
| `outputs/multi_source_results.csv` | `multi_source.py` | 32 行 = 4 布局 × 6 预算（5 芯片 6 行 N4b-skip）。列含 `tree/ctrl` 的 `T_max`、`T_mean_solid`、`hotspot_mm2`、`dp`、钉住数、连接距离、材料量、`skipped` | **物理 °C / mm²** |
| `outputs/multi_source_summary.json` | `multi_source.py` | 同上全量 + `grid/layouts/budgets` 元数据 | **物理 °C** |
| `outputs/spread_source_thermal.csv` | `spread_source_scan.py` | 24 行：树 / 放射状 / 格状网三方的 `T_max`、`T_mean`、热区、`dp`，共享阈值热区（`*_shared`）与连接诊断 | **物理 °C / mm²** |
| `outputs/spread_source_thermal_summary.json` | `spread_source_scan.py` | 同上 + `source_radius_cells=8`、`src_cells_per_die=289`、`die_area_mm2`、`power_density_w_cm2`、`q_per_cell`、R26 非均功率块 | **物理 °C** |
| `outputs/lattice_pitch_scan.csv` | `lattice_scan.py` | 185 行：每个 (case, pitch) 的树侧与格状网 `T_max/T_mean/hotspot/dp`、`dTmax/dTmean/dHotspot`（树 − 格状，负=树更优） | **物理 °C / mm²** |
| `outputs/lattice_pitch_summary.json` | `lattice_scan.py` | 18 个 live case 的 `best_*_pitch`、`dTmax`、`dHotspot`、`n_admissible`（4–13）；键 `cases/rows` | **物理 °C** |
| `outputs/unequal_power_pitch_scan.csv` | `unequal_pitch_scan.py` | 52 行：4 个功率集 × 13 个 pitch 的树/格状指标 | **物理 °C** |
| `outputs/unequal_power_pitch_summary.json` | `unequal_pitch_scan.py` | 4 个 case：`tree_minus_best_Tmax`、`tree_minus_best_hotspot`、`best_lat_hot_per_chip`、`tree_hot_per_chip`、`hotspot_spread` | **物理 °C** |
| `outputs/c5_artifact.json` | 一次性预登记脚本（已删，协议见 `DEFECT_REMEDIATION_PLAN.md` §10.13） | 等总格点（T5-5）：树 / 放射状 / 格状网的 `T_max`、共享阈值热区（26.0 °C）、钉住数、`dp` | **物理 °C** |
| `outputs/extend_surface_results.csv` | `extend_surface.py` | 4 个功率集 × 树/放射/格状；含等材料压降比 | **任意归一化标度**（峰值先归一化到 100） |
| `outputs/extend_surface_summary.json` | `extend_surface.py` | 同上全量 + 配置 | **任意归一化标度** |
| `outputs/bionic_placement_results.csv` | `bionic_placement_main.m` | 36 行 EA 搜索：`seed,gen,x1..y3,T_max_C,T_mean_solid_C,hotspot_mm2,tree_dp,best_so_far` | **无量纲标度；`_C` 列名误标** |
| `outputs/bionic_placement_summary.txt` | `bionic_placement_main.m` | 三角布局复现校验、三布局对比、EA 配置与收敛记录 | **无量纲标度** |
| `outputs/multisource_coupled_results.csv` | `multisource_coupled_main.m` | 4 行耦合重算：`T_max_C,T_mean_solid_C,hotspot_mm2,dp,material_mm2,...` | **无量纲标度；`_C` 列名误标** |
| `outputs/matlab_multisource_coupled_summary.txt` | `multisource_coupled_main.m` | MATLAB 耦合重算日志 | **无量纲标度** |
| `outputs/matlab_coupled_summary.txt` | `multisource_coupled_main.m` | 耦合摘要（论文表 4） | **无量纲标度** |
| `outputs/scan_recalc_frequency.txt` | `multisource_coupled_main.m` | 重算频率扫描 | **无量纲标度** |
| `outputs/matlab_verify.txt` | MATLAB 手工输出（无生成脚本） | `TREE_Tmax=27.5962`、`TREE_Tmean=25.0196`、逐行 `TREE_hot=0` | **无量纲标度** |
| `outputs/step6_multisource_*.png`, `step7_coupled_multisource.png` | `multi_source.py` / MATLAB | 多源场、树、对照、耦合场 | 图 |
| `outputs/_pitch_parts/{2,3,4,5}chips.json` | `lattice_scan.py` 分块中间件 | 并行分块的原始 case 结果，供合并 | 同 `lattice_pitch_summary.json` |
| `outputs/_comb_parts/{comb0,comb1}.json` | 分块合并中间件 | 合并前后的中间结果 | 同上 |

## 3. 物理标定与共轭对流（论文 §5、§6、§11）

| 文件 | 生成 | 内容 | 单位 |
|---|---|---|---|
| `outputs/real_unit_calibration.txt` | `calibrate.py`（`report()`） | i7-14700K 类（253 W）与 H100 类（700 W）：裸导热峰值、树+通道峰值、`R_th`、两组公开冷板参照与倍数、`dP`、路径铺展、厚度敏感性、微通道尺度说明 | **物理 °C / °C·W⁻¹ / kPa** |
| `outputs/conjugate_single.json` | `conjugate_run.py` | 单源共轭：`pinned_peak_c=60.5042`、`pinned_r_th_peak=0.1403`、带宽、流量扫描 | **物理 °C** |
| `outputs/conjugate_guard.json` | `conjugate_run.py` | 同上的守卫版：R15 限流/限温测试 | **物理 °C** |
| `outputs/conjugate_multi_real.json` | `conjugate_multi.py` | 3 die × 253 W = 759 W：`pinned_peak_c=65.3562`、`power_density_w_cm2=108.1`、叶片份额 | **物理 °C** |
| `outputs/p0a_artifact.json` | 一次性预登记脚本（已删，协议见 `DEFECT_REMEDIATION_PLAN.md` §439 附近） | 759 W 等流量：Dirichlet 峰值 59.113 °C、流量扫描的 `peak_c/T_mean_c/pinned_peak_c/erosion_c/converged` | **物理 °C** |

## 4. 稳健性、收敛性与路由

| 文件 | 生成 | 内容 | 单位 |
|---|---|---|---|
| `outputs/robin_boundary_scan.csv` | `robin_boundary.py` | 20 行：不同 `h_conv`（Bi）下 `raw/tree/ctrl` 的 `T_max`、热区、钉住数、`dp_ratio` | **无量纲标度** |
| `outputs/robin_boundary_summary.json`, `robin_boundary_parts.json` | `robin_boundary.py` | 单源/多源的完整扫描与分块原始值 | **无量纲标度** |
| `outputs/a4_grid_convergence.json` | `a4_grid_convergence.py` | N=50/100/200/400/800 五级网格、GCI、三拓扑逐位一致性、解析校验、源块包络 | **无量纲**（求解本身尺度无关；报告含换算常数） |
| `outputs/physarum_route_results.csv` | `physarum_route_main.m` | 6 个路由验证 case：边数、欧氏/曼哈顿长度、连通性、MST/RSMT 比、障碍穿越、收敛残差 | 长度=格步；非温度 |
| `outputs/physarum_route_summary.txt` | `physarum_route_main.m` | 路由验证摘要 | 同上 |
| `outputs/chip_route_iso.png`, `chip_route_iso_summary.txt` | `chip_route_iso.m` | 芯片级等距路由图与摘要 | 同上 |
| `outputs/chip_route_circuit.png`, `chip_route_circuit_summary.txt` | `chip_physarum_circuit.m` | 电路类比路由图与摘要 | 同上 |
| `outputs/tree_edges_dynamic.csv` | 旧版动态生长输出（无现存生成脚本） | 399 条边：`parent_idx,child_idx,py,px,cy,cx`，无半径列 | 坐标=格点 |

## 5. 台账与说明文件

| 文件 | 内容 |
|---|---|
| `outputs/REPORT.md` | 2026-10-16 历史快照（理论、对比、STL 几何、产物清单）。与根目录 `REPORT.md` 内容不同（后者是对比数据与口径台账），二者**不是副本**。**其 dp 口径已被取代**：`588.10/583.54`、`6.42 kPa`、`24827×`、`R7=5/12`、`R25=17/19`、§24 "T_max 19/19" 均为旧口径，不作现行结论；现行值以论文 §16b 与根目录 `REPORT.md` 为准 |
| `outputs/COMPARISON.txt` | MATLAB 三方对照；温度列为无量纲标度（见 §1） |

## 6. 已知限制（引用数据前必须核对）

1. **`_C` 后缀不可信**：`bionic_placement_results.csv`、`multisource_coupled_results.csv` 的 `T_max_C/T_mean_solid_C` 是无量纲标度；与之同源的 `COMPARISON.txt`、`matlab_verify.txt` 同理。物理 °C 请改用 `multi_source_results.csv` 或 `real_unit_calibration.txt`。
2. **两个 artifact 的生成脚本已删除**：`p0a_artifact.json`、`c5_artifact.json` 的协议与调用序列记录在 `DEFECT_REMEDIATION_PLAN.md`，仅凭仓库不能逐行重跑这两个文件。
3. **5 芯片 N4b 排除**：17×17 源块在 r=8.0 融合为单连通区（1381 格），`multi_source_results.csv` 中 6 行 `skipped` 不得计入任何分母；格状网判定的分母是 18。
4. **网格误差**：生产网格 N=50，树的温升比收敛外推高约 41%（`a4_grid_convergence.json`）。绝对温度只能读作"N=50 下的值"，相对排名不受影响。
5. **`extend_surface_*` 不可与 °C 混用**：其场在生长前被归一化到峰值 100。
6. **`closed ≠ manifold ≠ printable`**：`tree.stl` 与 `manifold_assembly.stl` 的边界边均为 0（闭合），但非流形边分别为 228 / 236 条（节点处端盖共面重合）。切片前必须布尔并集；本仓库未执行该步骤，故不得据本节数字声称"已可打印"。
7. **`tree_dynamic.stl` 不可复现**：生成器未入库、CSV 无半径列；实测 294 个连通分量、负有向体积（法向朝内），只作历史产物保留，不参与可制造性主张。
