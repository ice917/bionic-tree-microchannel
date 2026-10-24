# -*- coding: utf-8 -*-
"""Regenerate outputs/c5_artifact.json (§10.13 C5 equal-total, T5-5).

The original generator for this artifact no longer exists in the repo (it
was an orphan file that `_work/verify_repro_scripts.py` attributes to
generator.py but which generator.py does not produce). This script rebuilds
it from the repository's own functions so the equal-total data matches the
CURRENT code -- in particular the two controls whose builders were fixed on
2026-10-21:

  * `verify.radial_group_total`  -- round-robin fan across chips (was
    chip-by-chip in cluster order, which starved later chips of cells on
    3/4-chip layouts and made radial C1 fail / report inflated T_max);
  * `verify.lattice_group_total` -- now returns its true cell list via
    `channel_cells` (was reconstructed without the centre-out completion).

Only the equal-total columns are recomputed. The two equal-pinned reference
columns (`dT_pinned_radial`, `dT_pinned_lattice`) are copied from the
previous artifact because their source builders (`radial_group_pinned` /
`lattice_group` in lattice_scan.py) were NOT touched by the fix.

Protocol (§10.13, pre-registered): total_area matched (r = sqrt(area/(N*pi))
with the tree's material), shared hot-zone threshold T_cool+1.0 = 26.0 C,
dp reported on the dimensionless solver convention (verify.Group.dp).
"""
from __future__ import annotations

import json
from pathlib import Path

import field as F
import multi_source as MS
import verify as V

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"

SHARED_THRESHOLD_C = 26.0
BUDGETS = (400, 600, 700, 800, 1000, 1300)
# 2/3/4-chip layouts only; the 5-chip corners+centre layout is N4b-excluded
# (it fuses into one region at the real footprint) and has no rows here.
LAYOUT_NAMES = ["2 chips, 20 mm apart", "3 chips, triangle", "4 chips, corners"]


def main() -> None:
    old = json.loads((OUT / "c5_artifact.json").read_text(encoding="utf-8"))
    old_rows = {(r["case"], r["budget"]): r for r in old["rows"]}

    rows = []
    for label in LAYOUT_NAMES:
        centers = MS.LAYOUTS[label]
        T, src, strength = MS.solve_layout(centers)
        grid = int(T.shape[0])
        for budget in BUDGETS:
            tg, _edges, _radii, cells, _s2t, _b2t = MS.tree_metrics(
                T, src, budget, grid=grid, centers=centers,
                radius=F.SRC_RADIUS_REAL, strength=strength)
            rg = V.radial_group_total(T, src, budget, tg.total_area_mm2,
                                      grid, grid, strength=strength)
            lg = V.lattice_group_total(T, src, budget, tg.total_area_mm2,
                                       grid, grid, strength=strength)

            tree_hs = V.hotspot_at(tg, SHARED_THRESHOLD_C)
            rg_hs = V.hotspot_at(rg, SHARED_THRESHOLD_C)
            lg_hs = V.hotspot_at(lg, SHARED_THRESHOLD_C)

            prev = old_rows.get((label, budget), {})

            rows.append({
                "case": label,
                "budget": budget,
                "tree_cells": len(cells),
                "tree_T_max": round(tg.T_max, 4),
                "tree_pinned": tg.pinned_cells,
                "tree_hotspot_shared": round(tree_hs, 1),
                "radial_total_T_max": round(rg.T_max, 4),
                "radial_total_pinned": rg.pinned_cells,
                "radial_total_hotspot_shared": round(rg_hs, 1),
                "dT_total_radial": round(rg.T_max - tg.T_max, 4),
                "d_hs_total_radial": round(rg_hs - tree_hs, 1),
                "d_pinned_radial": rg.pinned_cells - tg.pinned_cells,
                "dp_radial_total": round(rg.dp, 3),
                "lattice_total_T_max": round(lg.T_max, 4),
                "lattice_total_pinned": lg.pinned_cells,
                "lattice_total_hotspot_shared": round(lg_hs, 1),
                "dT_total_lattice": round(lg.T_max - tg.T_max, 4),
                "d_hs_total_lattice": round(lg_hs - tree_hs, 1),
                "d_pinned_lattice": lg.pinned_cells - tg.pinned_cells,
                "dp_lattice_total": round(lg.dp, 3),
                # equal-pinned reference columns (source builders untouched)
                "dT_pinned_radial": prev.get("dT_pinned_radial"),
                "dT_pinned_lattice": prev.get("dT_pinned_lattice"),
            })

    payload = {
        "protocol": ("\u00a710.13 C5 equal-total, pre-registered; radial/lattice "
                     "controls regenerated with round-robin + true-cells fixes "
                     "(2026-10-21)"),
        "shared_threshold_c": SHARED_THRESHOLD_C,
        "e0_anchor_failures": [],
        "rows": rows,
    }
    (OUT / "c5_artifact.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1))
    print(f"wrote outputs/c5_artifact.json ({len(rows)} rows)")


if __name__ == "__main__":
    main()
