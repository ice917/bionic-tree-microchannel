# -*- coding: utf-8 -*-
"""阶段 4：公平比较协议泛化 —— 汇总可复现 benchmark 数据集。

把本项目全部可复现工件汇总成一个单一的 benchmark_dataset.json，作为「三重公平
比较协议 + 约束驱动生成器」的公开数据集，供第三方套用自己的拓扑对照。协议口径：

  等钉住格点 (equal pinned)   —— 树与对照组钉住（设为 T_cool）的格点数相同
  等材料     (equal material) —— 相同总截面积，故相同压降预算
  等总占用格点 (equal total)   —— 两侧通道占用总格点数逐格相等（最严口径）

产出 outputs/benchmark_dataset.json
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def main():
    run = _load("run_report.json")["compare"]
    ms = _load("multi_source_summary.json")
    c5 = _load("c5_artifact.json")
    fronts = _load("generator_fronts.json")
    jun = _load("junction_loss_summary.json")
    dim = _load("dimension_sensitivity.json")
    regime = _load("regime_map.json")

    # 多源等钉住：18 成功组
    ms_rows = [r for r in ms["rows"] if "tree_cells" in r and "| budget" in r["case"]]
    # 等总占用代表工况（400/1300 × 3 布局）
    c5_rep = [r for r in c5["rows"] if r["budget"] in (400, 1300)]

    ds = {
        "protocol": {
            "bases": ["equal_pinned", "equal_material", "equal_total_occupied"],
            "generator_constraints": ["C1_admissibility", "C2_geometry", "C3_hydraulic_budget"],
            "dp_convention": "convention A (deepest root-to-leaf path, network solve)",
        },
        "single_source_equal_occupancy": {
            "tree_T_max_C": run["tree"]["T_max_C"],
            "straight_T_max_C": run["straight"]["T_max_C"],
            "dp_ratio_tree_over_straight": run["dp_ratio_tree_over_straight"],
            "tree_dp": run["tree"]["pressure_drop"],
            "straight_dp": run["straight"]["pressure_drop"],
        },
        "multi_source_equal_pinned": {
            "n_solved": len(ms_rows),
            "dT_max_range_C": [
                min(r["dT_max_tree_minus_ctrl"] for r in ms_rows),
                max(r["dT_max_tree_minus_ctrl"] for r in ms_rows),
            ],
            "dp_ratio_max": max(r["dp_ratio_tree_over_ctrl"] for r in ms_rows),
            "rows": ms_rows,
        },
        "multi_source_equal_total_occupied": c5_rep,
        "pareto_fronts": {
            tag: {"n_feasible": fronts[tag]["tree"]["n_feasible"],
                  "front": fronts[tag]["tree"]["front"]}
            for tag in fronts
        },
        "junction_loss": {
            "pure_viscous_dp_kpa": jun["pure_viscous_dp_kpa"],
            "amplification_range_x": jun["junction_amplification_range_x"],
        },
        "dimension_sensitivity": {
            "dT_tree_minus_straight_3d_C": dim["dT_tree_minus_straight_3d"],
            "verdict": dim["verdict"],
        },
        "spacing_regime": {
            "rows": regime["rows"],
            "verdict": regime["verdict"],
        },
    }
    (OUT / "benchmark_dataset.json").write_text(
        json.dumps(ds, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote outputs/benchmark_dataset.json")
    print("keys:", sorted(ds.keys()))
    print("等钉住 dT_max 范围:", ds["multi_source_equal_pinned"]["dT_max_range_C"],
          "dp_ratio_max:", ds["multi_source_equal_pinned"]["dp_ratio_max"])


if __name__ == "__main__":
    main()
