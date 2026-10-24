# -*- coding: utf-8 -*-
"""Stage 3a: dimensionality check on a reduced 3D cold plate.

The question: does the 2D finding "tree and equal-occupancy straight channels
tie on peak temperature" survive when the third dimension is resolved? What
this model is and is not:

  * solved: steady 3D conduction on grid x grid x depth cells. The heat source
    sits on the TOP layer only (the chip on top of the plate); the top and the
    four sides are adiabatic; the base is cooled.
  * the channels are cold columns at the coolant temperature.
  * NOT solved: the flow field. The coolant temperature along the channel is
    fixed, so the model cannot express streamwise heating. That limitation is
    stated in the paper; it is the price of a conduction-only check.

Two defects in the previous version are fixed here, both recorded in the
output JSON so the old numbers stay auditable:

  D1  The channel clamp covered the FULL depth, including the top layer that
      carries the source. The tree sprouts from the hottest cell and the
      straight group always spans the source, so in both groups the mask
      covered 25/25 source cells and `Tn[:, mask] = T_cool` erased the
      injected heat. The solver then converged in ONE iteration to a uniform
      field at the coolant temperature: tree = straight = 25.0000 exactly.
      The published "3D tie" was therefore a tautology, not a result.
      Fix: leave a solid top skin (`channel_top_gap=1`), so the source stays
      active and heat must conduct through the skin into the channels.

  D2  The straight group used max(n_cells // grid, 2r+1) columns, i.e. 5
      columns = 150 cells against the tree's 120: 25% more occupied plate,
      violating the equal-occupancy constraint C5 that the whole comparison
      rests on. Fix: fix the column count at the odd value 2r+1 (so the group
      is centred on the source) and grow the tree to exactly that many cells,
      (2r+1)*grid, BEFORE growing. C5 is then exact by construction and
      asserted, not assumed.

The base boundary is also relaxed from an isothermal sink to finite
convection (Robin), because an infinite sink hides whatever the topology
does. A sweep over Bi is reported instead of a single hand-picked value, so
the reader can see whether the conclusion depends on that choice.

Writes outputs/dimension_sensitivity.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"
sys.path.insert(0, str(ROOT))

import grow as G  # noqa: E402
import field as F  # noqa: E402
from field import SRC_RADIUS_SYNTHETIC, normalize_field  # noqa: E402

DEPTH = 10
CHANNEL_TOP_GAP = 1          # solid skin above the channels; keeps the source live
GRID_MAIN = 30
GRID_CHECK = 40
H_SWEEP = [None, 0.0, 1.0, 10.0]   # None = isothermal base, 0 = adiabatic base
# Bi = 0 is admissible only with channels present (they are the sole sink);
# the bare-plate reference has no steady state there and is reported as n/a.


def channel_mask_from_edges(edges, grid):
    cells = set()
    for p, c in edges:
        cells.add((p // grid, p % grid))
        cells.add((c // grid, c % grid))
    m = np.zeros((grid, grid), dtype=bool)
    for y, x in cells:
        m[y, x] = True
    return m, len(cells)


def straight_mask_centred(grid, n_columns):
    """`n_columns` full-length channels centred on the plate's middle column.

    The column count is odd (2r+1) so the group is symmetric about the centre
    and therefore spans the whole source footprint; an even count cannot be
    centred on an odd-width source and would leave one source column exposed,
    which flatters the tree.
    """
    c = grid // 2
    half = n_columns // 2
    xs = [c - half + k for k in range(n_columns) if 0 <= c - half + k < grid]
    if not xs:
        xs = [c]
    m = np.zeros((grid, grid), dtype=bool)
    for x in xs:
        m[:, x] = True
    return m, len(xs)


def build_pair(grid):
    """Tree and straight masks with identical occupied-cell counts (C5 exact)."""
    c = grid // 2
    n_cols = int(2 * SRC_RADIUS_SYNTHETIC + 1)
    target = n_cols * grid

    td = normalize_field(
        F.solve_heat_sources(grid=grid, centers=[(c, c)],
                             source_radius=SRC_RADIUS_SYNTHETIC).T,
        T_target=100.0)
    edges = G.grow_tree(td, max_nodes=target)
    tree_mask, n_tree = channel_mask_from_edges(edges, grid)
    str_mask, n_cols = straight_mask_centred(grid, n_cols)
    n_str = int(str_mask.sum())

    src = F.source_mask(grid, (c, c), SRC_RADIUS_SYNTHETIC)
    cov_tree = int((src & tree_mask).sum())
    cov_str = int((src & str_mask).sum())

    if n_tree != n_str:
        raise AssertionError(
            f"C5 violated: tree has {n_tree} occupied cells, straight has {n_str}")
    if cov_tree != cov_str:
        raise AssertionError(
            f"source coverage differs: tree {cov_tree}, straight {cov_str}")

    return {
        "edges": edges,
        "tree_mask": tree_mask,
        "straight_mask": str_mask,
        "n_tree": n_tree,
        "n_straight": n_str,
        "n_columns": n_cols,
        "source_cells": int(src.sum()),
        "source_covered_tree": cov_tree,
        "source_covered_straight": cov_str,
    }


def solve(grid, h_base, gap, mask, c):
    kw = dict(grid=grid, depth=DEPTH, source_center=(c, c),
              source_radius=SRC_RADIUS_SYNTHETIC,
              channel_top_gap=gap, h_base=h_base)
    r = F.solve_heat_3d(channels_2d=mask, **kw)
    if not r.converged:
        raise RuntimeError(f"3D solve did not converge (grid={grid}, h={h_base})")
    top = r.T[-1]
    return {
        "bare_top_C": None,
        "top_max_C": float(top.max()),
        "iters": r.iterations,
        "top_unique_values": int(np.unique(np.round(top, 9)).size),
    }


def run_case(grid, pair, h_base):
    """One Bi operating point. The bare-plate reference does not exist at
    h_base = 0: an adiabatic base with no channel in the mask leaves the
    injected heat with no escape path, so no steady state exists and the
    solver cannot converge. That is a property of the boundary condition, not
    a numerical failure, and it is recorded rather than hidden.
    """
    c = grid // 2
    if h_base == 0.0:
        bare = None
        bare_note = ("no steady state: adiabatic base and no channel in the "
                     "mask means the source heat has no escape path")
    else:
        bare = solve(grid, h_base, CHANNEL_TOP_GAP, None, c)
        bare_note = None
    tree = solve(grid, h_base, CHANNEL_TOP_GAP, pair["tree_mask"], c)
    strt = solve(grid, h_base, CHANNEL_TOP_GAP, pair["straight_mask"], c)
    dT = tree["top_max_C"] - strt["top_max_C"]
    return {
        "h_base": h_base,
        "Bi": None if h_base is None else round(h_base * F.PITCH_MM, 6),
        "bare_top_C": None if bare is None else round(bare["top_max_C"], 6),
        "bare_note": bare_note,
        "tree_top_C": round(tree["top_max_C"], 6),
        "straight_top_C": round(strt["top_max_C"], 6),
        "dT_tree_minus_straight_C": round(dT, 6),
        "iters": {"bare": None if bare is None else bare["iters"],
                  "tree": tree["iters"], "straight": strt["iters"]},
        "tree_unique_top_values": tree["top_unique_values"],
        "straight_unique_top_values": strt["top_unique_values"],
    }


def main():
    pair = build_pair(GRID_MAIN)
    cases = [run_case(GRID_MAIN, pair, h) for h in H_SWEEP]

    # Legacy reproduction: full-depth clamp, no solid skin.
    c = GRID_MAIN // 2
    legacy_tree = F.solve_heat_3d(grid=GRID_MAIN, depth=DEPTH,
                                  source_center=(c, c),
                                  source_radius=SRC_RADIUS_SYNTHETIC,
                                  channels_2d=pair["tree_mask"])
    legacy_str = F.solve_heat_3d(grid=GRID_MAIN, depth=DEPTH,
                                 source_center=(c, c),
                                 source_radius=SRC_RADIUS_SYNTHETIC,
                                 channels_2d=pair["straight_mask"])

    # Grid check: same construction, finer plate, odd column count preserved.
    pair_check = build_pair(GRID_CHECK)
    cases_check = [run_case(GRID_CHECK, pair_check, h) for h in H_SWEEP]

    primary = next(k for k in cases if k["h_base"] == 1.0)
    dTs = [k["dT_tree_minus_straight_C"] for k in cases]
    same_sign = all(d <= 0.0 for d in dTs) or all(d >= 0.0 for d in dTs)
    dT_min, dT_max = min(dTs), max(dTs)
    max_abs = max(abs(d) for d in dTs)
    range_span = primary["bare_top_C"] - primary["tree_top_C"]
    grid_shift = max(abs(a["dT_tree_minus_straight_C"] - b["dT_tree_minus_straight_C"])
                     for a, b in zip(cases, cases_check))

    verdict = (
        "With the source kept live (solid top skin) and equal occupancy "
        "(tree %d cells = straight %d cells, both covering %d/%d source "
        "cells), the 3D peak difference is %+.4f C at Bi=1 and spans "
        "[%+.4f, %+.4f] C over Bi in {0, 1, 10} plus the isothermal-base "
        "limit; the sign is %s across the sweep. Rebuilding at grid %d moves "
        "each difference by at most %.1e C. On a peak that the channels lower "
        "by %.4f C against the bare plate, |dT| is %.2f%% of the cooling "
        "effect. Because occupancy AND source coverage are equalised by "
        "construction, this comparison cannot attribute the tie to coverage; "
        "what it does establish is that the tie survives the third dimension "
        "rather than being an artefact of the 2D reduction.%s"
        % (pair["n_tree"], pair["n_straight"],
           pair["source_covered_tree"], pair["source_cells"],
           primary["dT_tree_minus_straight_C"], dT_min, dT_max,
           "stable" if same_sign else "NOT stable",
           GRID_CHECK, grid_shift,
           range_span, 100.0 * max_abs / range_span if range_span else float("nan"),
           "" if same_sign else
           " Sign reversal means the 3D check does not confirm the 2D "
           "ordering and must be reported as inconclusive."))

    out = {
        "model": ("3D conduction, source on the top layer, adiabatic top and "
                  "sides, cooled base, channels as isothermal columns below a "
                  "solid top skin; no streamwise flow model"),
        "grid": GRID_MAIN, "depth": DEPTH,
        "source_radius": SRC_RADIUS_SYNTHETIC,
        "channel_top_gap": CHANNEL_TOP_GAP,
        "equal_occupancy": {
            "tree_cells": pair["n_tree"],
            "straight_cells": pair["n_straight"],
            "straight_columns": pair["n_columns"],
            "constraint_C5": "exact (asserted)",
        },
        "source_coverage": {
            "tree": pair["source_covered_tree"],
            "straight": pair["source_covered_straight"],
            "of": pair["source_cells"],
        },
        "runs": cases,
        "primary_h_base": 1.0,
        "grid_check": {
            "grid": GRID_CHECK,
            "tree_cells": pair_check["n_tree"],
            "straight_cells": pair_check["n_straight"],
            "runs": cases_check,
        },
        "legacy_full_depth_clamp": {
            "tree_top_C": round(float(legacy_tree.T[-1].max()), 6),
            "straight_top_C": round(float(legacy_str.T[-1].max()), 6),
            "iters": [legacy_tree.iterations, legacy_str.iterations],
            "defect": ("channel clamp covered the source layer, the injected "
                       "heat was overwritten, and both runs converged in one "
                       "iteration to a uniform field at the coolant "
                       "temperature; the published 25.0000/25.0000 tie was a "
                       "degenerate solve, not a physical result"),
        },
        # kept for benchmark_dataset.py
        "dT_tree_minus_straight_3d": primary["dT_tree_minus_straight_C"],
        "verdict": verdict,
    }
    (OUT / "dimension_sensitivity.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("wrote outputs/dimension_sensitivity.json")
    print("C5: tree=%d straight=%d cells, source covered %d/%d both"
          % (pair["n_tree"], pair["n_straight"],
             pair["source_covered_tree"], pair["source_cells"]))
    for k in cases:
        bare = "n/a" if k["bare_top_C"] is None else "%9.6f" % k["bare_top_C"]
        print("  h=%-6s Bi=%-5s bare=%s tree=%9.6f straight=%9.6f dT=%+.6f"
              % (k["h_base"], k["Bi"], bare, k["tree_top_C"],
                 k["straight_top_C"], k["dT_tree_minus_straight_C"]))
    print("  grid %d check: " % GRID_CHECK +
          "  ".join("dT=%+.6f" % k["dT_tree_minus_straight_C"]
                    for k in cases_check))
    print("  legacy (full-depth clamp) tree=%.6f straight=%.6f iters=%s"
          % (out["legacy_full_depth_clamp"]["tree_top_C"],
             out["legacy_full_depth_clamp"]["straight_top_C"],
             out["legacy_full_depth_clamp"]["iters"]))
    print(verdict)


if __name__ == "__main__":
    main()
