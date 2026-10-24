# -*- coding: utf-8 -*-
"""阶段 2：接头局部损失落地 —— 量化接头项对树压降的放大，产出可复现工件。

背景：论文的树压降是「纯黏性下界」（calibrate.tree_dp_pa 约定 A 网络公式），
未含 56 个分叉接头的局部损失。树恰好是接头最集中的拓扑，而直通道/径向无分叉，
所以接头项只会**进一步拉大**树 vs 对照的压降差距——方向利好「负结果」结论。

K 系数在层流微通道 Re<150 区间无可靠标定（P0b 协议 v4 结论），故采用
order-of-magnitude 区间而非单点：

  J1   Rennels 分流式（湍流数据外推）：K = 0.62 - 0.98s + 0.36s^2  —— 下界
  J2   常数 K = 1.8                                                —— 中间参考
  J3   层流插值 K = 1.8*2300/Re，clip [1, 300]                      —— 上界

产出：outputs/junction_loss_summary.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import calibrate as C
import grow as G
import radius as Ra
import field as F
from field import SRC_RADIUS_SYNTHETIC, normalize_field, solve_heat_sources

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"


def k_j1(re, s):
    return 0.62 - 0.98 * s + 0.36 * s * s


def k_j2(re, s):
    return 1.8


def k_j3(re, s):
    return min(max(1.8 * 2300.0 / re, 1.0), 300.0)


FAMILY = [("J1_rennels_split", k_j1, "下界（湍流外推）"),
          ("J2_const_1p8", k_j2, "中间参考"),
          ("J3_laminar_clip", k_j3, "上界（层流插值）")]


def main():
    td = normalize_field(
        solve_heat_sources(grid=50, centers=[(25, 25)],
                           source_radius=SRC_RADIUS_SYNTHETIC).T,
        T_target=100.0)
    edges = G.grow_tree(td, max_nodes=400)
    radii = Ra.assign_radii(edges, grid=50, r0=0.5)
    grid_mm = C.paper_grid_mm(50)
    q_tot = C.coolant_flow_m3s(253.0)

    pure = C.tree_dp_pa(edges, radii, 50, grid_mm, q_tot)["dp_pa"]

    rows = []
    for name, kf, tag in FAMILY:
        d = C.tree_dp_pa(edges, radii, 50, grid_mm, q_tot,
                         with_junctions=True, k_of=kf)
        rows.append({
            "model": name,
            "note": tag,
            "dp_pure_viscous_pa": round(pure, 6),
            "dp_viscous_pa": round(d["dp_viscous_pa"], 6),
            "dp_junctions_pa": round(d["dp_junctions_pa"], 6),
            "dp_total_pa": round(d["dp_pa"], 6),
            "amplification_x": round(d["dp_pa"] / pure, 3),
        })

    lo = min(r["amplification_x"] for r in rows)
    hi = max(r["amplification_x"] for r in rows)
    summary = {
        "tree": "single-source b=400 (61 leaves, 56 forks)",
        "pure_viscous_dp_pa": round(pure, 6),
        "pure_viscous_dp_kpa": round(pure / 1000, 6),
        "junction_amplification_range_x": [lo, hi],
        "models": rows,
        "verdict": (
            "计入接头局部损失后，树的压降由纯黏性下界 %.4f kPa 放大 %.1f–%.1f 倍"
            "（J1 下界 ~%.4f kPa，J3 上界 ~%.4f kPa）。直通道/径向无分叉，接头项"
            "≈0，故接头损失只会进一步拉大树 vs 对照的压降差距——纯黏性下界已足够"
            "证伪树，计入接头项结论方向不变且更强。K 在层流微通道 Re<150 无可靠"
            "标定，此为 order-of-magnitude 区间。"
            % (pure / 1000, lo, hi, rows[0]["dp_total_pa"] / 1000,
               rows[-1]["dp_total_pa"] / 1000)),
    }
    (OUT / "junction_loss_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("wrote outputs/junction_loss_summary.json")
    print("pure viscous dp = %.6f kPa" % (pure / 1000))
    for r in rows:
        print("  %-18s total=%8.4f kPa  junction=%8.4f kPa  x=%.2f  (%s)"
              % (r["model"], r["dp_total_pa"] / 1000, r["dp_junctions_pa"] / 1000,
                 r["amplification_x"], r["note"]))
    print(summary["verdict"])


if __name__ == "__main__":
    main()
