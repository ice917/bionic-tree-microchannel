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


def solve_layout(centers, grid=50, source_radius=F.SRC_RADIUS_REAL,
                 powers=None):
    """Multi-chip field at the REAL die footprint, N4-guarded.

    The footprint is the single most consequential parameter in the whole
    comparison: at SRC_RADIUS_SYNTHETIC (2.0) a 253 W die carries 1249
    W/cm^2, at SRC_RADIUS_REAL (8.0) it carries ~108 W/cm^2 -- a 12x change
    in the power density the tree is being asked to manage. The default is
    therefore REAL; the synthetic block is SRC_RADIUS_SYNTHETIC and is only
    for the single-source REPORT.md §4 chain (see field.py).

    Returns (T, src, strength). `strength` is the REAL per-cell source term
    (die power divided by the cells the layout actually heats) and must be
    passed to every `apply_channels` re-solve; without it the channel solve
    silently reverts to equal-per-cell power, which is defect #2 again.
    Delegating to spread_source_scan keeps this module on the same entry
    point as the R24/R25 authority -- a 5.9e-4 C field difference between the
    two paths is enough to send grow_tree down a different branch.
    """
    import spread_source_scan as SS   # local: SS imports this module
    return SS.solve_spread(centers, grid=grid, radius=source_radius,
                           powers=powers)


def tree_metrics(T, src, max_nodes, grid=50, r0=0.5, centers=None,
                 radius=None, strength=None, pitch_mm=None):
    """Grow a tree on `T` and return (group, edges, radii, cells,
    src_to_tree, block_to_tree).

    The last two are DISTINCT connectivity readings and both are returned so
    no caller can silently pick the one that suits it:

      src_to_tree  -- worst manhattan distance from any SOURCE cell to the
                      nearest tree cell. 0 only if a tree cell lands on
                      EVERY heated cell, which a budget-limited tree never
                      does (measured 13-20 at budgets 600-800 on the real
                      footprint). A diagnostic, NOT an admissibility test.
      block_to_tree -- worst distance from any cell of a chip's source BLOCK
                      to the tree. 0 means the tree physically enters every
                      chip's footprint, which is the fairness precondition
                      CONNECTED_FROM is about and the verdict
                      spread_source_scan reports as "connected".

    The old single return value was src_to_tree, so any caller gating on
    `max(dist) != 0` skipped every case that was in fact admissible
    (lattice_scan/unequal_pitch_scan skipped 10 of 12 cases this way,
    2026-10-18). It also measured tree cell -> chip centroid, which is 0
    only if a tree cell lands exactly on a centroid -- fine for the 5x5
    concentrated block, wrong for a real 17x17 block.

    `radius` is the half-width of each chip's source block in cells. Pass it
    (field.SRC_RADIUS_REAL) whenever the blocks are real; without it the
    half-width is inferred from the cell count, which is only correct while
    no two blocks overlap.

    `strength` is the real per-cell source term; it MUST be passed whenever
    the caller has it, otherwise the channel re-solve falls back to
    equal-per-cell power (defect #2) and the reported T is about the bug, not
    about the topology. `pitch_mm` defaults to field.PITCH_MM (the
    dimensionless solver pitch); a real-unit dp must go through
    calibrate.tree_dp_pa instead.
    """
    edges = G.grow_tree(T, max_nodes=max_nodes)
    radii = Ra.assign_radii(edges, grid=grid, r0=r0)
    kw = {} if pitch_mm is None else {"pitch_mm": pitch_mm}
    tg = V.tree_group(T, src, edges, radii, grid_x=grid, strength=strength,
                      **kw)
    cells = sorted(set([p for p, _ in edges] + [c for _, c in edges]))
    # Two DISTINCT connectivity readings, both returned so callers cannot
    # silently pick the one that suits them:
    #
    #   src_to_tree  -- worst manhattan distance from any SOURCE cell to the
    #                   nearest tree cell. 0 only if a tree cell lands on
    #                   EVERY heated cell, which a budget-limited tree never
    #                   does (measured 13-20 at budgets 600-800 on the real
    #                   footprint). A diagnostic, NOT an admissibility test.
    #   block_to_tree -- worst distance from any cell of a chip's source
    #                   BLOCK to the tree. 0 means the tree physically
    #                   enters every chip's footprint, which is the fairness
    #                   precondition CONNECTED_FROM is about and the metric
    #                   spread_source_scan uses for its "connected" verdict.
    #
    # The old single return value was src_to_tree, so any caller gating on
    # `max(dist) != 0` skipped every case that was in fact admissible
    # (lattice_scan/unequal_pitch_scan skipped 10 of 12 cases this way,
    # 2026-10-18). The previous reading also measured tree cell -> chip
    # centroid, which is 0 only if a tree cell lands exactly on a centroid
    # -- fine for the 5x5 concentrated block, wrong for a real 17x17 block.
    src_ys, src_xs = np.nonzero(src)
    dists = [min(abs(y - (i // grid)) + abs(x - (i % grid)) for i in cells)
             for y, x in zip(src_ys, src_xs)]
    if not dists:
        dists = [0]
    src_to_tree = max(dists)

    block_to_tree = 0
    if centers:
        # Half-width of each chip block: the caller's radius when given
        # (the real 17x17 footprint), otherwise inferred from the cell
        # count -- valid only while no two blocks overlap, which is exactly
        # what layout_is_valid / the N4b gate checks.
        if radius is not None:
            r = int(radius)
        else:
            r = int(np.sqrt(src.sum() / max(1, len(centers)))) // 2
        block_d = []
        for cy, cx in centers:
            cyi, cxi = int(round(cy)), int(round(cx))
            blk = [(y, x) for y in range(cyi - r, cyi + r + 1)
                   for x in range(cxi - r, cxi + r + 1)
                   if 0 <= y < grid and 0 <= x < grid]
            if blk:
                block_d.append(min(abs(y - i // grid) + abs(x - i % grid)
                                   for y, x in blk for i in cells))
        block_to_tree = max(block_d) if block_d else 0
    return tg, edges, radii, cells, [src_to_tree], block_to_tree


def control_metrics(T, src, tg, grid=50, strength=None):
    return V.radial_group_pinned(T, src, target_pinned=tg.pinned_cells,
                                 total_area_mm2=tg.total_area_mm2,
                                 grid_x=grid, grid_y=grid, strength=strength)


def row(label, tg, rg, maxdist, n_cells, src_to_tree=None):
    out = {
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
    # The admissibility metric is block_to_tree (see tree_metrics); the
    # src_to_tree reading is carried alongside as a diagnostic so a future
    # reader cannot re-derive the old mistake of treating it as a gate.
    if src_to_tree is not None:
        out["max_src_to_tree_dist"] = int(src_to_tree)
    return out


def sweep_spacing(grid=50, max_nodes=600):
    """Two chips, centre-to-centre distance d, tree vs one-pipe-per-chip."""
    c = grid // 2
    rows = []
    for d in (6, 8, 10, 12, 16, 20, 24, 30):
        centers = [(c - d // 2, c), (c + d - d // 2, c)]
        T, src, strength = solve_layout(centers, grid=grid)
        tg, _, _, cells, src_to_tree, block_to_tree = tree_metrics(
            T, src, max_nodes, grid=grid, centers=centers,
            radius=F.SRC_RADIUS_REAL, strength=strength)
        rg = control_metrics(T, src, tg, grid=grid, strength=strength)
        rows.append(row(f"d={d}mm", tg, rg, block_to_tree, len(cells),
                        src_to_tree[0]))
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
        T, src, strength = solve_layout(centers, grid=grid)
        n_chips = len(V._cluster_centers(src))
        for n in BUDGETS:
            if n > grid * grid:
                continue
            # N4b: the 5-chip corners+centre layout fuses into one region at
            # the real footprint, so its rows are excluded rather than
            # reported as if the layout were what it claims to be.
            # (spread_source_scan imports this module, hence the local
            # import -- a module-level one would be a cycle.)
            import spread_source_scan as SS
            ok, why = SS.layout_is_valid(centers, grid=grid,
                                         radius=F.SRC_RADIUS_REAL)
            if not ok:
                all_rows.append({"case": f"{label} | budget {n}",
                                 "skipped": f"N4b: {why}"})
                continue
            tg, edges, radii, cells, src_to_tree, block_to_tree = tree_metrics(
                T, src, n, grid=grid, centers=centers,
                radius=F.SRC_RADIUS_REAL, strength=strength)
            rg = control_metrics(T, src, tg, grid=grid, strength=strength)
            all_rows.append(row(f"{label} | budget {n}", tg, rg,
                                block_to_tree, len(cells), src_to_tree[0]))
        rows_n = [r for r in all_rows
                  if r["case"].startswith(label) and "skipped" not in r]
        skipped_n = [r for r in all_rows
                     if r["case"].startswith(label) and "skipped" in r]
        conn = [r for r in rows_n if r["max_chip_to_tree_dist"] == 0]
        first_conn = conn[0] if conn else None
        print(f"[layout] {label}: chips={n_chips}, "
              f"src_cells={int(src.sum())}, strength_sum={float(strength.sum()):.4f}"
              + (f", {len(skipped_n)} rows N4b-skipped" if skipped_n else ""))
        if first_conn is not None:
            print(f"          connected from budget {first_conn['case'].split('budget ')[1]}: "
                  f"dT_mean={first_conn['dT_mean_tree_minus_ctrl']:+.4f} C, "
                  f"dT_max={first_conn['dT_max_tree_minus_ctrl']:+.4f} C, "
                  f"dp_ratio={first_conn['dp_ratio_tree_over_ctrl']}")
        if skipped_n and not rows_n:
            print(f"          all {len(skipped_n)} budgets N4b-skipped: "
                  f"{skipped_n[0]['skipped']}")
            continue
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
        T, src, strength = solve_layout(centers, grid=grid)
        tg, edges, radii, _, _, _ = tree_metrics(T, src, 600, grid=grid,
                                                 centers=centers,
                                                 radius=F.SRC_RADIUS_REAL,
                                                 strength=strength)
        rg = control_metrics(T, src, tg, grid=grid, strength=strength)
        heatmap(T, OUT / "step6_multisource_field.png",
                "3 chips: heat field (cyan box = chip blocks)", src=src)
        heatmap(tg.T, OUT / "step6_multisource_tree.png",
                f"tree: T_max={tg.T_max:.3f} C, T_mean={tg.T_mean_solid:.4f} C",
                edges, grid, src)
        heatmap(rg.T, OUT / "step6_multisource_control.png",
                f"one pipe per chip: T_max={rg.T_max:.3f} C, T_mean={rg.T_mean_solid:.4f} C",
                src=src)

    # N4b-skipped rows carry only `case` + `skipped`, so the field list must
    # be the union over every row, not all_rows[0]'s keys.
    keys: list[str] = []
    for r in all_rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(OUT / "multi_source_results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, restval="")
        w.writeheader()
        w.writerows(all_rows)

    (OUT / "multi_source_summary.json").write_text(
        json.dumps({"grid": grid, "layouts": {k: v for k, v in LAYOUTS.items()},
                    "budgets": list(BUDGETS), "rows": all_rows},
                   indent=2), encoding="utf-8")
    print(f"\nDone. {len(all_rows)} cases -> outputs/multi_source_results.csv")


if __name__ == "__main__":
    main()
