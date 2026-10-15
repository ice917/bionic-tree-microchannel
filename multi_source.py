"""Multi-source experiment: does a tree beat one-pipe-per-chip?

The single-source result (REPORT.md) was a tie on every thermal metric and a
25000x pressure-drop loss. The stated reason: with one chip, "an optimal
transport network" has no topology to exploit. This module tests the design
premise by putting N chips on the plate.

Model changes vs the single-source pipeline:

  * field.solve_heat_sources -- N equal 5x5 blocks, q per source cell, so the
    total power scales with N (N identical chips).
  * verify.radial_group_pinned -- one straight pipe per chip, budgeted so the
    control's PINNED cell count equals the tree's exactly. Equal pinned
    occupancy matters more here than in the single-source case, because a
    tree that grows through a chip block has those cells exempted from
    pinning (a channel may not delete the heat it must remove).

Metrics are unchanged (T_max, mean solid T, hot-zone area, Poiseuille dP) so
the numbers are directly comparable with REPORT.md.

    python multi_source.py                 # layouts + spacing sweep + figures
    python multi_source.py --no-fig
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

import field as F
import grow as G
import radius as Ra
import verify as V

OUT = Path(__file__).resolve().parent / "outputs"

# (label, centres) -- all on a 50x50 grid, chips are 5x5
LAYOUTS: dict[str, list[tuple[int, int]]] = {
    "2 chips, 20 mm apart": [(15, 25), (35, 25)],
    "3 chips, triangle": [(15, 15), (35, 15), (25, 35)],
    "4 chips, corners": [(12, 12), (12, 38), (38, 12), (38, 38)],
    "5 chips, corners+centre": [(12, 12), (12, 38), (38, 12), (38, 38), (25, 25)],
}

BUDGETS = (400, 600, 700, 800, 1000, 1300)

# A budget below the point where the tree touches every chip makes the
# comparison meaningless: a tree that never reaches a chip has not done its
# job, so "the tree is worse" would measure the budget, not the topology.
# CONNECTED_FROM is the smallest budget at which every layout is connected.
CONNECTED_FROM = 700


def solve_layout(centers, grid=50, source_radius=2.0):
    rs = F.solve_heat_sources(grid=grid, centers=centers, source_radius=source_radius)
    T = F.normalize_field(rs.T, T_target=100.0)
    src = F.source_mask_multi(grid, centers, radius=source_radius)
    return T, src, rs


def tree_metrics(T, src, max_nodes, grid=50, r0=0.5):
    edges = G.grow_tree(T, max_nodes=max_nodes)
    radii = Ra.assign_radii(edges, grid=grid, r0=r0)
    tg = V.tree_group(T, src, edges, radii, grid_x=grid)
    cells = sorted(set([p for p, _ in edges] + [c for _, c in edges]))
    # connectivity: worst manhattan distance from any chip to the nearest
    # tree cell. 0 means the tree physically enters that chip's block.
    blobs = V._cluster_centers(src)
    dists = [min(abs(i // grid - int(round(cy))) + abs(i % grid - int(round(cx))) for i in cells)
             for cy, cx in blobs]
    return tg, edges, radii, cells, dists


def control_metrics(T, src, tg, grid=50):
    return V.radial_group_pinned(T, src, target_pinned=tg.pinned_cells,
                                 total_area_mm2=tg.total_area_mm2,
                                 grid_x=grid, grid_y=grid)


def row(label, tg, rg, maxdist, n_cells):
    return {
        "case": label,
        "tree_cells": n_cells,
        "tree_pinned": tg.pinned_cells,
        "ctrl_pinned": rg.pinned_cells,
        "tree_T_max": round(tg.T_max, 4),
        "ctrl_T_max": round(rg.T_max, 4),
        "tree_T_mean_solid": round(tg.T_mean_solid, 4),
        "ctrl_T_mean_solid": round(rg.T_mean_solid, 4),
        "tree_hotspot_mm2": round(tg.hotspot_area, 3),
        "ctrl_hotspot_mm2": round(rg.hotspot_area, 3),
        "tree_dp": round(tg.dp, 3),
        "ctrl_dp": round(rg.dp, 4),
        "dp_ratio_tree_over_ctrl": round(tg.dp / rg.dp, 1) if rg.dp else None,
        "dT_mean_tree_minus_ctrl": round(tg.T_mean_solid - rg.T_mean_solid, 4),
        "dT_max_tree_minus_ctrl": round(tg.T_max - rg.T_max, 4),
        "max_chip_to_tree_dist": int(maxdist),
        "material_mm2": round(tg.total_area_mm2, 3),
    }


def sweep_spacing(grid=50, max_nodes=600):
    """Two chips, centre-to-centre distance d, tree vs one-pipe-per-chip."""
    c = grid // 2
    rows = []
    for d in (6, 8, 10, 12, 16, 20, 24, 30):
        centers = [(c - d // 2, c), (c + d - d // 2, c)]
        T, src, _ = solve_layout(centers, grid=grid)
        tg, _, _, cells, dists = tree_metrics(T, src, max_nodes, grid=grid)
        rg = control_metrics(T, src, tg, grid=grid)
        rows.append(row(f"d={d}mm", tg, rg, max(dists), len(cells)))
    return rows


def heatmap(T, path, title, edges=None, grid_x=50, src=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 5.4), dpi=140)
    im = ax.imshow(T, cmap="inferno", origin="lower")
    fig.colorbar(im, ax=ax, label="T [C]")
    if src is not None:
        ys, xs = np.nonzero(src)
        ax.add_patch(plt.Rectangle((xs.min() - 0.5, ys.min() - 0.5),
                                   xs.max() - xs.min() + 1, ys.max() - ys.min() + 1,
                                   fill=False, edgecolor="cyan", lw=1.2))
    if edges is not None:
        ys, xs = [], []
        for p, ch in edges:
            py, px = divmod(p, grid_x)
            cy, cx = divmod(ch, grid_x)
            ys += [py, cy]
            xs += [px, cx]
        ax.plot(xs, ys, color="cyan", lw=0.8, alpha=0.9)
    ax.set_title(title)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", type=int, default=50)
    ap.add_argument("--no-fig", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    grid = args.grid

    all_rows: list[dict] = []

    # ---- part 1: layouts x node budget ----
    for label, centers in LAYOUTS.items():
        T, src, rs = solve_layout(centers, grid=grid)
        n_chips = len(V._cluster_centers(src))
        for n in BUDGETS:
            if n > grid * grid:
                continue
            tg, edges, radii, cells, dists = tree_metrics(T, src, n, grid=grid)
            rg = control_metrics(T, src, tg, grid=grid)
            all_rows.append(row(f"{label} | budget {n}", tg, rg, max(dists), len(cells)))
        rows_n = [r for r in all_rows if r["case"].startswith(label)]
        conn = [r for r in rows_n if r["max_chip_to_tree_dist"] == 0]
        first_conn = next((r for r in rows_n if r["max_chip_to_tree_dist"] == 0), None)
        print(f"[layout] {label}: chips={n_chips}, field iters={rs.iterations}")
        if first_conn is not None:
            print(f"          connected from budget {first_conn['case'].split('budget ')[1]}: "
                  f"dT_mean={first_conn['dT_mean_tree_minus_ctrl']:+.4f} C, "
                  f"dT_max={first_conn['dT_max_tree_minus_ctrl']:+.4f} C, "
                  f"dp_ratio={first_conn['dp_ratio_tree_over_ctrl']}")
        worst = rows_n[-1]
        print(f"          budget {BUDGETS[-1]}: dT_mean={worst['dT_mean_tree_minus_ctrl']:+.4f} C, "
              f"dT_max={worst['dT_max_tree_minus_ctrl']:+.4f} C, "
              f"dp_ratio={worst['dp_ratio_tree_over_ctrl']}, "
              f"max_chip_dist={worst['max_chip_to_tree_dist']}")
        # budgets where the tree misses a chip are reported but flagged
        missed = [r for r in rows_n if r["max_chip_to_tree_dist"] > 0]
        if missed:
            print(f"          !! tree MISSES a chip at budgets "
                  f"{[r['case'].split('budget ')[1] for r in missed]} "
                  f"(not a fair comparison, see CONNECTED_FROM)")

    # ---- part 2: spacing sweep ----
    sweep = sweep_spacing(grid=grid, max_nodes=600)
    all_rows += sweep
    print("[sweep] two chips, spacing d:")
    for r in sweep:
        print(f"  d={r['case']:>7}: dT_mean={r['dT_mean_tree_minus_ctrl']:+.4f} C, "
              f"dT_max={r['dT_max_tree_minus_ctrl']:+.4f} C, "
              f"dp_ratio={r['dp_ratio_tree_over_ctrl']}")

    # ---- figures: the 3-chip case, tree vs control ----
    if not args.no_fig:
        centers = LAYOUTS["3 chips, triangle"]
        T, src, _ = solve_layout(centers, grid=grid)
        tg, edges, radii, _, _ = tree_metrics(T, src, 600, grid=grid)
        rg = control_metrics(T, src, tg, grid=grid)
        heatmap(T, OUT / "step6_multisource_field.png",
                "3 chips: heat field (cyan box = chip blocks)", src=src)
        heatmap(tg.T, OUT / "step6_multisource_tree.png",
                f"tree: T_max={tg.T_max:.3f} C, T_mean={tg.T_mean_solid:.4f} C",
                edges, grid, src)
        heatmap(rg.T, OUT / "step6_multisource_control.png",
                f"one pipe per chip: T_max={rg.T_max:.3f} C, T_mean={rg.T_mean_solid:.4f} C",
                src=src)

    with open(OUT / "multi_source_results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        w.writeheader()
        w.writerows(all_rows)

    (OUT / "multi_source_summary.json").write_text(
        json.dumps({"grid": grid, "layouts": {k: v for k, v in LAYOUTS.items()},
                    "budgets": list(BUDGETS), "rows": all_rows},
                   indent=2), encoding="utf-8")
    print(f"\nDone. {len(all_rows)} cases -> outputs/multi_source_results.csv")


if __name__ == "__main__":
    main()
