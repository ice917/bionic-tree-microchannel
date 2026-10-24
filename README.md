# 仿生自适应网络：芯片散热通道树

在 50×50 的二维导热网格上，让冷却通道网络按"热寻路 + Murray 定径"规则从温度场中生长，并在同一功率、同一网格、同一钉住规则下与放射状通道、均匀格状网逐案比较。项目保留全部失败与修正记录：结论以 `REPORT.md`、`DEFECT_REMEDIATION_PLAN.md` 和 `outputs/` 原始数据为准，不以任何单一摘要为准。

## 已核验的主要结论（截至 2026-10-18，N4c 修复后）

| 项目 | 结果 | 证据 |
|---|---|---|
| 树 vs 最优格状网（18 个可采纳 case） | 峰值温度 11 胜 7 负，`dTmax` −3.5945 至 +0.4985 °C | `outputs/lattice_pitch_summary.json` |
| 2 芯片 / 3 芯片 / 4 芯片 | 6/6、5/6、**0/6** 树胜 | 同上 |
| R7（\|dTmax\| < 0.5 °C） | 12/18 | 同上 |
| R5（某 pitch 热区胜树 > 1 mm²） | 11/18（树热区 7 胜 11 负） | 同上 |
| R6（等钉住 pitch 不唯一） | 18/18，每 case 4–13 个可行 pitch | 同上 |
| 非均功率 4 组 | 树 `T_max` 4/4 胜（−1.3078 至 −0.4170 °C）；热区 2/4 胜 | `outputs/unequal_power_pitch_summary.json` |
| 物理标定（253 W / i7 类） | 60.5 °C，`R_th` = 0.1403 °C/W | `outputs/real_unit_calibration.txt` |
| 与公开冷板比较 | 比 0.0069 °C/W 差 20.3×；比 0.014–0.019 °C/W 差 7.4–10.0×（口径不可比） | 同上，论文 §6.2 |

必须同时阅读的限定：生产网格为 N=50，树的温升相对收敛外推高约 41%，只影响绝对幅值、不影响拓扑排名（`outputs/a4_grid_convergence.json`）；4 芯片下树对格状网的拓扑劣势是真实的，不能表述为"树全面优于均匀格状网"；5 芯片 17×17 源块融合为单连通区，已按 N4b 规则排除，判定分母为 18 而非 19。

## 目录

```
*.py                      Python 求解、扫描与论文生成脚本
*.m / *.slx               MATLAB 交叉验证与 Simulink 模型
outputs/                  全部数值结果、图、STL（70 个文件）
论文/                      论文 docx 成品
REPORT.md                 逐节对比台账（与论文互校）
PROJECT.md                项目方案与目标（历史文档，结论以 REPORT.md 为准）
DEFECT_REMEDIATION_PLAN.md 缺陷台账：机制、证据、修复、作废项
DATA_DICTIONARY.md        每个输出文件的生成脚本、字段与单位状态
REPORTING_COMPLIANCE.md   报告合规性对照（TOP 2025 七项 / Nature 数据与代码可用性）
MANIFEST.sha256           全部随附文件（源码/工件/文档/论文）的 SHA-256 清单（132 项）
DATA_AVAILABILITY.md      数据可用性声明模板（中英）
src_extract/              Physarum 参考文献的 LaTeX 源码（第三方材料）
```

## 环境与复现

已在 Windows + Python 3.13.9、numpy 2.3.5、scipy 1.16.3、matplotlib 3.10.6 下运行。依赖：`numpy`、`scipy`、`matplotlib`、`python-docx`。

```powershell
# 单源基础链（热场 → 生长 → 定径 → 验证 → STL）
python heat_tree.py

# 多芯片与格状网对照（论文第 9、10 节）
python multi_source.py
python spread_source_scan.py
python lattice_scan.py
python unequal_pitch_scan.py

# 物理标定与共轭对流
python calibrate.py
python conjugate_run.py
python conjugate_multi.py

# 稳健性与收敛性
python robin_boundary.py
python a4_grid_convergence.py
python extend_surface.py

# 论文 docx（依赖同目录 paper_template.py，不读外部绝对路径）
python generate_heat_tree_paper.py
python generate_heat_tree_paper_mainstream.py
python generate_heat_tree_paper_journal.py

# 顶刊补强（数据链路断言 / 接头损失 / 3D 维度 / regime map / benchmark 数据集）
python data_link_assertions.py
python junction_loss_landing.py
python conjugate_3d.py
python regime_map.py
python benchmark_dataset.py
```

MATLAB 脚本（`bionic_placement.m`、`multisource_coupled_main.m` 等）用于交叉验证，不是 Python 结果的前置依赖。论文生成脚本只依赖同目录的 `paper_template.py`（已随仓库分发），故 docx 可在干净环境重建。

```powershell
# 校验随附文件完整性（只列出不匹配项；改过任何文件后需重新生成清单）
Get-Content MANIFEST.sha256 | ForEach-Object { $h,$p = $_ -split '  ',2; if ((Get-FileHash $p -Algorithm SHA256).Hash -ne $h) { $p } }
```

## 数据与单位（必读）

- **物理 °C**：`multi_source_*`、`spread_source_thermal_*`、`lattice_pitch_*`、`unequal_power_pitch_*`、`c5_artifact.json`、`conjugate_*.json`、`real_unit_calibration.txt`。这些是 17×17 真实 die 足迹、8.0 W/cm² 口径或 A7 标定后的温度。
- **无量纲/归一化标度，但部分列名带 `_C` 后缀**：`bionic_placement_results.csv`、`bionic_placement_summary.txt`、`multisource_coupled_results.csv`、`matlab_coupled_summary.txt`、`matlab_multisource_coupled_summary.txt`、`matlab_verify.txt`。这些文件来自"峰值归一化到 100 后生长"的 MATLAB 口径，`T_max_C = 27.5962` 是标度值，不是摄氏度。
- **无量纲对照/收敛研究**：`robin_boundary_scan.csv`、`robin_boundary_summary.json`、`robin_boundary_parts.json`、`run_report.json`、`a4_grid_convergence.json`、`extend_surface_results.csv`、`extend_surface_summary.json`（后者把场峰值归一化到 100，属于任意标度）。
- 逐文件说明与作废关系见 [DATA_DICTIONARY.md](DATA_DICTIONARY.md)。引用任何温度数值前，先确认其所在文件属于哪一类。

## 许可证

- 代码（`*.py`、`*.m`、`*.slx`）：MIT，见 [LICENSE](LICENSE)。
- 数据与文档（`outputs/`、`*.md`、`论文/`）：CC BY 4.0，见 [LICENSE-DATA](LICENSE-DATA)。
- `src_extract/` 为第三方论文源码，**不在上述许可覆盖范围内**，版权归原作者。

## 引用与作者

作者、单位与 DOI 尚未分配，仓库中以 `TODO` 占位。**在占位符被替换、DOI 分配之前，不得声称本仓库已完成正式发布或归档。** 引用格式待作者信息确定后补入 `CITATION.cff`（尚未创建）。
