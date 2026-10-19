"""Re-run the multi-source thermal comparison (§16) with SPREAD SOURCES.

WHY THIS EXISTS
---------------
The architecture audit (REPORT §22) found a structural defect: every
multi-source result up to §23 used `source_radius = 2.0`, i.e. all of a
die's 253 W was dumped into 25 cells -- 1249 W/cm^2, 12.7x the real
i7-14700K's 98 W/cm^2. Only 1.0% of the plate was thermally active and
571 cells were pinned at exactly 25.0 C by construction.

`conjugate_multi.py` (§23) fixed this LOCALLY, inside its own script, by
passing source_radius=8.0. It never propagated: `multi_source.solve_layout`,
`extend_surface.solve` and every other entry point still default to 2.0.
So the fix was demonstrated on one coupling experiment and then abandoned
by the experiment that actually carries the project's headline claims.

This script re-runs §16's 32-case comparison (4 layouts x 6 budgets x tree
vs radial-per-chip vs lattice) with the source spread over the whole die
footprint, keeping every other convention identical.

FAIRNESS (three constraints, all measured, none assumed)
-------------------------------------------------------
  1. EQUAL PINNED CELLS. The control's pinned count is driven to the tree's
     exactly, by the existing bisection in `verify.radial_group_pinned` /
     `verify.lattice_group`. Source cells are exempt on both sides (a
     channel may not delete the heat it must remove).
  2. EQUAL CROSS-SECTION. Both groups are handed the tree's measured
     material area, so the Poiseuille budget is the same.
  3. EQUAL TOTAL POWER. With a spread source the per-cell q must be
     RESCALED, not copied. `field.solve_heat_sources(q=...)` is affine, so
     total power scales with the number of source cells: 17x17 = 289 cells
     instead of 5x5 = 25. If q were left alone each die would dissipate
     11.6x more power than before and the comparison would be about power,
     not topology. `q_per_cell` below is the tree's own value divided by
     the source-cell count ratio, so total die power is preserved.

PRE-REGISTERED
--------------
  R24  With a real power density, does the tree's T_max advantage over
       one-pipe-per-chip survive?  (§16 said 27.5962 vs 30.3-ish.)
  R25  Does the tree beat the UNIFORM LATTICE at equal pinned count?
       (§9.2 said the gap collapses to 1.2x; §9.6 said it is not even a
       well-defined question because pitch is a free parameter. This
       re-measures it at a realistic source, and reports the BEST pitch,
       which is the strongest possible control.)
  R26  Does "the tree is adaptive" survive?  The §10 signature was that the
       tree's hot-zone distribution is stuck at 25/25/25 regardless of the
       power ratios. With a spread source there is no 25-cell block any
       more, so the metric has to be redefined -- and if the tree's
       distribution still does not move, the claim is dead for good.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

import field as F
import grow as G
import multi_source as MS
import radius as Ra
import verify as V

OUT = Path(__file__).resolve().parent / "outputs"
GRID = 50

# Real-scale source: radius 8 cells -> 17x17 = 289 cells = 234 mm^2 per die.
# 253 W / 23.4 cm^2 = 108 W/cm^2, within 10% of the i7-14700K's 98 W/cm^2.
SRC_RADIUS = 8.0
DIE_POWER_W = 253.0
N_DIES = 3

# Die power in the model's internal units. The concentrated 5x5 block used
# q = 1.0 per cell = 25 units per die; keep the die total identical.
BASE_Q_PER_CELL = 1.0
BASE_SRC_CELLS = 25.0          # (2*2+1)^2

# Per-die total in model units, i.e. what ONE chip must dissipate no matter
# how many chips share the board or how close together they sit. Every
# earlier scaling was written as `BASE_Q_PER_CELL * BASE_SRC_CELLS /
# src_cell_count(radius)` -- a per-chip ARITHMETIC that assumed each chip
# owns (2r+1)^2 distinct cells. That assumption fails as soon as two 17x17
# blocks overlap (chips closer than 34 cells apart on a 50-cell board):
# the union has fewer cells than n_chips * 289, so the intended total is
# silently reduced -- 0.956x for the 5-chip corners+centre layout and
# 0.676x for two chips 6 mm apart. That is the N2 failure mode again
# (total power a by-product of caller arithmetic instead of an input), so
# the scale is now derived from the MEASURED cell count of the actual
# layout. See DEFECT_REMEDIATION_PLAN.md §10.8 (N4).
DIE_POWER_UNITS = BASE_Q_PER_CELL * BASE_SRC_CELLS   # 25.0 per die


def src_cell_count(radius: float) -> int:
    r = int(radius)
    return (2 * r + 1) ** 2


def q_per_cell(radius: float, centers=None, grid: int = GRID,
               powers=None) -> float:
    """Per-cell strength that keeps TOTAL DIE POWER constant per die.

    Affine in q, so total power is proportional to (number of source cells)
    x (q per cell). Spreading the source therefore forces q down by the
    cell-count ratio, otherwise each die silently gains 11.6x power.

    N4 FIX (2026-10-17): the denominator is the number of source cells the
    ACTUAL layout heats, not `n_chips * src_cell_count(radius)`. With
    overlapping blocks those differ (5-chip: 1381 vs 1445; two chips 6 mm
    apart: 391 vs 578) and the difference is exactly the power the layout
    quietly lost. Passing `centers` is therefore required for any layout
    whose blocks may overlap; with centers=None the isolated-block count is
    used, which is correct only for non-overlapping layouts.
    """
    if centers is None:
        n_cells = src_cell_count(radius)
    else:
        n_cells = int(F.source_mask_multi(grid, centers, radius=radius).sum())
    if n_cells <= 0:
        raise ValueError(f"layout heats no cells (radius={radius})")
    # Distribute DIE_POWER_UNITS per chip over the cells that chip actually
    # owns. `powers` shifts the share between chips but never the total.
    n_dies = len(list(centers)) if centers is not None else 1
    return DIE_POWER_UNITS * n_dies / float(n_cells)


def solve_spread(centers, grid=GRID, radius=SRC_RADIUS, powers=None):
    """Field + source mask with the die power spread over its footprint.

    Returns (T_driver, src, strength). T_driver is the NORMALISED field the
    tree grows on (peak = 100, as every other experiment); `strength` is the
    real per-cell term that `apply_channels` must be given so the re-solve
    does not silently revert to equal power.

    N4 FIX: `q` is scaled against the layout's MEASURED source-cell count,
    so the total power is 25 units per die regardless of how the blocks
    overlap (see q_per_cell).
    """
    q = q_per_cell(radius, centers=centers, grid=grid)
    rs = F.solve_heat_sources(grid=grid, centers=centers,
                              source_radius=radius, q=q, powers=powers)
    T = F.normalize_field(rs.T, T_target=100.0)
    src = F.source_mask_multi(grid, centers, radius=radius)
    # `q` must scale the strength UNCONDITIONALLY. Scaling only when
    # `powers` is given is the exact bug that hid in field.solve_heat_sources
    # until this round: with powers=None the re-solve silently ran at 11.56x
    # the intended power, which is what made the first spread-source run
    # report a 61.7 C peak instead of the real 28.2 C.
    strength = F.source_strength_multi(grid, centers, radius=radius,
                                       powers=powers) * q
    return T, src, strength


def layout_is_valid(centers, grid=GRID, radius=SRC_RADIUS) -> tuple[bool, str]:
    """Geometric admissibility of a layout at the real die footprint.

    N4b (2026-10-17): a 17x17 block per die only stays a SEPARATE thermal
    region while the blocks do not touch. `_cluster_centers` works on
    4-neighbour connectivity, so two blocks that share an edge become ONE
    connected component and the layout silently becomes a single chip --
    every "per-die" metric then measures nothing. The 5-chip
    corners+centre layout fails this at radius 8: the centre block
    (rows 17-33) abuts the corner blocks (rows 4-20 / 30-46) with a gap of
    zero cells, so all five fuse into one 1381-cell region.

    Returns (ok, reason). `ok=False` cases must be EXCLUDED from any
    per-die comparison, not run and reported as if they were valid.
    """
    src = F.source_mask_multi(grid, centers, radius=radius)
    n_blocks = len(centers)
    n_clusters = len(V._cluster_centers(src))
    if n_clusters != n_blocks:
        return False, (f"source blocks fuse into {n_clusters} connected "
                       f"region(s) instead of {n_blocks} -- per-die metrics "
                       f"are undefined at radius {radius}")
    return True, ""


def run_case(label, centers, budget, powers=None, grid=GRID,
             radius=SRC_RADIUS, controls=("radial", "lattice")):
    # N4b gate: a layout whose source blocks fuse is not a multi-chip
    # layout at all, and every per-die metric on it is meaningless. Report
    # the case as skipped with the reason instead of silently measuring a
    # single fused region (which is what produced the invalid 5-chip rows
    # of the pre-N4b run).
    ok, why = layout_is_valid(centers, grid=grid, radius=radius)
    if not ok:
        return {"case": label, "budget": budget, "skipped": f"N4b: {why}"}

    T, src, strength = solve_spread(centers, grid=grid, radius=radius,
                                    powers=powers)
    n_src_cells = int(src.sum())
    # Expected cell count for an isolated-block layout; the N4 fix makes the
    # power scale use the MEASURED count instead, so this is only a diagnostic.
    n_assumed = src_cell_count(radius) * len(centers)

    # --- tree ---
    edges = G.grow_tree(T, max_nodes=budget)
    radii = Ra.assign_radii(edges, grid=grid, r0=0.5)
    tg = V.tree_group(T, src, edges, radii, grid_x=grid, strength=strength)
    cells = sorted(set([p for p, _ in edges] + [c for _, c in edges]))
    # CONNECTIVITY, correctly oriented. The old expression measured, for
    # every TREE cell, the manhattan distance to the nearest chip CENTROID
    # and took the max -- a quantity that is large precisely when the tree
    # is well spread out, and that is ~0 only when a tree cell sits exactly
    # on a centroid. That accidentally worked for the 5x5 concentrated block
    # (radius 2.0: the centroid is a cell the tree can land on) and became
    # meaningless for the real 17x17 footprint (radius 8.0: the centroid is
    # an interior cell of the block, so maxdist is never 0 and every case
    # reads as "disconnected" -- the connected-case count collapsed to 0 of
    # 18 after the N4 fix made the footprint real).
    #
    # The metric that was INTENDED -- and the one the CONNECTED_FROM
    # fairness rule depends on -- is: for every cell of every chip's source
    # block, the distance to the nearest tree cell, maximised. 0 means
    # every source cell has a tree cell on top of it.
    src_ys, src_xs = np.nonzero(src)
    dists = [min(abs(y - (i // grid)) + abs(x - (i % grid)) for i in cells)
             for y, x in zip(src_ys, src_xs)]
    maxdist = max(dists) if dists else 0
    # Also record the tree's distance to each chip's BLOCK EDGE, which is
    # the physically meaningful "did the coolant reach this die" number.
    # `cells` holds flat indices (i = y*grid + x), as built above.
    chip_dist = []
    for cy, cx in centers:
        cyi, cxi = int(round(cy)), int(round(cx))
        block = [(y, x) for y in range(cyi - int(radius), cyi + int(radius) + 1)
                 for x in range(cxi - int(radius), cxi + int(radius) + 1)
                 if 0 <= y < grid and 0 <= x < grid]
        d = min(abs(y - i // grid) + abs(x - i % grid)
                for y, x in block for i in cells)
        chip_dist.append(d)
    maxdist_block = max(chip_dist)

    row = {
        "case": label,
        "budget": budget,
        "tree_cells": len(cells),
        "tree_pinned": tg.pinned_cells,
        "tree_T_max": round(tg.T_max, 4),
        "tree_T_mean": round(tg.T_mean_solid, 4),
        "tree_hotspot": round(tg.hotspot_area, 2),
        "tree_dp": round(tg.dp, 4),
        "tree_material_mm2": round(tg.total_area_mm2, 4),
        "src_cells": n_src_cells,
        "src_cells_if_isolated": n_assumed,
        "power_scale_vs_isolated": round(n_src_cells / n_assumed, 4),
        "maxdist": int(maxdist),
        "max_chip_to_tree_dist": int(maxdist_block),
    }
    # N4 GUARD: with the measured-cell scaling the total strength must be
    # 25 units per die, whatever the geometry. A layout that fails this is
    # silently running at the wrong power and its numbers may not leave the
    # lab.
    expect = DIE_POWER_UNITS * len(centers)
    got = float(strength.sum())
    if abs(got - expect) > 1e-9 * max(1.0, expect):
        raise AssertionError(
            f"N4 guard failed for {label}: total strength {got:.6f} != "
            f"{expect:.6f} (25 per die). The power scale is not "
            f"layout-independent -- results would be about power, not "
            f"topology.")

    # R26: per-die mean source temperature. With a spread source the §10
    # signature (a hot-zone distribution stuck at 25/25/25) no longer exists,
    # so the replacement signature is whether the TREE's per-die mean moves
    # with the power ratios the way a control's does. Computed on the solved
    # field, one mean per die footprint.
    #
    # N4b: the masks are built from the DECLARED centres, not from
    # `_cluster_centers(src)`. The blob centroids are only equal to the
    # declared centres while every block stays a separate connected
    # component; on a fused layout they collapse to one centroid and the
    # "per-die" signature would silently become a whole-board average.
    if powers is not None:
        yy, xx = np.mgrid[0:grid, 0:grid]
        per_die = []
        for cy, cx in centers:
            cy, cx = int(round(cy)), int(round(cx))
            sub = (np.abs(yy - cy) <= radius) & (np.abs(xx - cx) <= radius)
            per_die.append(sub)
        row["_per_die_masks"] = per_die

    if "radial" in controls:
        rg = V.radial_group_pinned(T, src, target_pinned=tg.pinned_cells,
                                   total_area_mm2=tg.total_area_mm2,
                                   grid_x=grid, grid_y=grid, strength=strength)
        row.update({
            "radial_pinned": rg.pinned_cells,
            "radial_T_max": round(rg.T_max, 4),
            "radial_T_mean": round(rg.T_mean_solid, 4),
            "radial_hotspot": round(rg.hotspot_area, 2),
            "radial_dp": round(rg.dp, 4),
            "d_T_max": round(rg.T_max - tg.T_max, 4),
            "d_hotspot": round(rg.hotspot_area - tg.hotspot_area, 2),
            "d_T_mean": round(rg.T_mean_solid - tg.T_mean_solid, 4),
        })
        # TASK-3: shared-threshold re-measurement. `_groups` is consumed by
        # apply_shared_threshold() after the whole case runs, so the hot-zone
        # columns stop being biased by each group's own T_max.
        row["_groups"] = {"tree": tg, "radial": rg}
    if "lattice" in controls:
        lg = V.lattice_group(T, src, target_pinned=tg.pinned_cells,
                             total_area_mm2=tg.total_area_mm2,
                             grid_x=grid, grid_y=grid, strength=strength)
        row.update({
            "lattice_pinned": lg.pinned_cells,
            "lattice_T_max": round(lg.T_max, 4),
            "lattice_T_mean": round(lg.T_mean_solid, 4),
            "lattice_hotspot": round(lg.hotspot_area, 2),
            "lattice_dp": round(lg.dp, 4),
            "lat_d_T_max": round(lg.T_max - tg.T_max, 4),
            "lat_d_hotspot": round(lg.hotspot_area - tg.hotspot_area, 2),
            "lat_d_T_mean": round(lg.T_mean_solid - tg.T_mean_solid, 4),
        })
        g = row.setdefault("_groups", {"tree": tg})
        g["lattice"] = lg

    # R26: per-die mean source temperature for every group that was solved.
    # The masks are popped before the row is written, but the means are
    # kept -- they are the only way to tell "the tree adapted" from "the
    # unequal power made the temperatures unequal".
    masks = row.pop("_per_die_masks", None)
    if masks:
        for nm, g in (("tree", tg),):
            if g is not None:
                row["per_die_tree"] = [round(float(g.T[m].mean()), 4)
                                       for m in masks]
        if "radial" in controls:
            row["per_die_radial"] = [round(float(rg.T[m].mean()), 4)
                                     for m in masks]
        if "lattice" in controls:
            row["per_die_lattice"] = [round(float(lg.T[m].mean()), 4)
                                      for m in masks]
    return row


# TASK-3: shared absolute threshold for the hot-zone columns.
#
# WHY: `Group.hotspot_area` comes from `from_field`, which takes the
# threshold as T_cool + 0.25 * THAT GROUP's own rise. The group with the
# smaller T_max therefore gets the lower bar, so the metric is biased in
# favour of the T_max winner -- and with two groups of close T_max the bias
# can flip the sign. The gamma sweep measured 13 of 48 cases flipping under
# the own-threshold rule (§5.9a).
#
# WHAT: re-measure every group of a case at ONE absolute threshold. The
# threshold is shared, so it cannot know which group is measuring. The
# per-group `*_hotspot` / `d_hotspot` columns are kept for continuity but
# the `*_hotspot_shared` / `d_hotspot_shared` columns are the ones the
# verdicts are read from.
#
# THRESHOLD CHOICE (2026-10-17, settled by a candidate sweep -- see
# _t3_thr_tmp.py, 18 cases x 3 layouts):
#
#   mid_frac f   thr = min(T_max) + f*(max-min)   -> tree HS is 0 in 18/18
#                                                     (the tree has the lower
#                                                     T_max, so ANY threshold
#                                                     between the two peaks
#                                                     sits above its whole
#                                                     field: metric has no
#                                                     resolution)
#   rise_off o   thr = T_cool + o                  -> 12/18 (matches the own-
#                                                     threshold reading) AND
#                                                     18/18 both sides non-empty
#
# So the bar is anchored on the INLET side, not between the two peaks. That
# also removes the bias the task was about: the threshold no longer depends
# on any group's T_max, so it cannot favour the T_max winner. The offset is
# in ABSOLUTE degrees above T_cool and is independent of how hot the board
# gets; 1.0 C was chosen because it sits above the numerical noise floor of
# the solver (sub-0.01 C) yet far below the smallest observed rise (~2 C).
SHARED_HOTSPOT_OFFSET_C = 1.0


def apply_shared_threshold(rows, offset_c: float = SHARED_HOTSPOT_OFFSET_C,
                           t_cool: float = V.T_COOL):
    """Add shared-threshold hot-zone columns to every row that has _groups.

    thr = t_cool + offset_c, identical for every group of the case. Positive
    differences mean the control has the LARGER hot zone.
    """
    base = float(t_cool) + offset_c
    for row in rows:
        groups = row.pop("_groups", None)
        if not groups:
            continue
        out = {}
        for nm, g in groups.items():
            out[f"{nm}_hotspot_shared"] = round(V.hotspot_at(g, base), 2)
        row.update(out)
        row["shared_hotspot_threshold_c"] = round(base, 4)
        if "tree" in groups:
            t = groups["tree"]
            for nm in ("radial", "lattice"):
                if nm in groups:
                    row[f"d_hotspot_shared_{nm}"] = round(
                        V.hotspot_at(groups[nm], base)
                        - V.hotspot_at(t, base), 2)
    return rows


def write_thermal_csv(rows, path=None):
    """Write the comparison rows to CSV via csv.writer (RFC 4180 quoting).

    WHY NOT the old `",".join(...)`: MS.LAYOUTS keys carry unquoted commas
    ("2 chips, 20 mm apart", "3 chips, triangle", "5 chips, corners+centre"),
    so the hand-joined file had MORE columns than the header on every such
    row and csv.DictReader read the whole file one field off (case ->
    "2 chips", budget -> " 20 mm apart", lat_d_T_mean -> restkey None).

    LIST FIELDS (per_die_tree / per_die_radial / per_die_lattice): the row
    value is a list of floats, so it is serialised as a JSON array, e.g.

        [28.1234, 29.5, 30.0]  ->  "[28.1234, 29.5, 30.0]"

    i.e. one quoted CSV field (the inner commas must NOT be split). To read
    it back: `json.loads(row["per_die_tree"])` returns the list of floats;
    do not `str.split(",")` it. Empty/absent list fields come back as "".

    Field order is the ordered union of all row keys, so a row that carries
    the per_die_* lists (unequal-power cases) cannot shift the columns of
    the rows that do not.
    """
    if path is None:
        path = OUT / "spread_source_thermal.csv"
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(fields)
        for r in rows:
            w.writerow([json.dumps(v) if isinstance(v := r.get(k), list) else v
                        for k in fields])


def run():
    print("=" * 78)
    print("MULTI-SOURCE THERMAL COMPARISON, SPREAD SOURCE (REAL SCALE)")
    print("=" * 78)
    n_cells = src_cell_count(SRC_RADIUS)
    area_mm2 = n_cells * 0.9 ** 2
    print(f"source radius {SRC_RADIUS} cells -> {n_cells} cells = "
          f"{area_mm2:.1f} mm^2 per die")
    print(f"die power {DIE_POWER_W:.0f} W -> "
          f"{DIE_POWER_W/(area_mm2/100.0):.1f} W/cm^2 "
          f"(real i7-14700K: 98 W/cm^2)")
    print(f"per-cell q {q_per_cell(SRC_RADIUS):.6f} "
          f"(concentrated model used {BASE_Q_PER_CELL}; die total preserved)")

    rows = []
    for name, centers in MS.LAYOUTS.items():
        for budget in MS.BUDGETS:
            r = run_case(name, centers, budget)
            rows.append(r)
            if "skipped" in r:
                print(f"  {name:<26} b={budget:<5} SKIPPED: {r['skipped']}")
                continue
            print(f"  {name:<26} b={budget:<5} "
                  f"pin={r['tree_pinned']:<5} "
                  f"Tmax={r['tree_T_max']:<9} "
                  f"rad={r.get('radial_T_max', float('nan')):<9} "
                  f"lat={r.get('lattice_T_max', float('nan')):<9} "
                  f"dH={r.get('d_hotspot', float('nan')):>8} "
                  f"latdH={r.get('lat_d_hotspot', float('nan')):>8}")

    n_skipped = sum(1 for r in rows if "skipped" in r)
    if n_skipped:
        print(f"\n  !! {n_skipped} case(s) EXCLUDED by the N4b geometry gate; "
              f"they are recorded in the json/csv with their reason and are "
              f"NOT part of any verdict.")

    # ---- R26: unequal power x spread source. Does the tree adapt? ----
    # §10's signature was a hot-zone distribution frozen at 25/25/25 while a
    # uniform lattice shifted its coverage toward the high-power die. With a
    # spread source there is no 25-cell block, so the signature is re-cast as
    # the per-die mean source temperature: if the tree adapts, raising one
    # die's power must lower that die's mean relative to the others in a way
    # a non-adaptive control cannot match.
    print("\n" + "-" * 78)
    print("R26  unequal power x spread source (3 chips, budget 600)")
    print("-" * 78)
    C3 = MS.LAYOUTS["3 chips, triangle"]
    r26 = []
    for lbl, pw in (("1/1/1", [1.0, 1.0, 1.0]),
                    ("1/2/3", [1.0, 2.0, 3.0]),
                    ("3/1/1", [3.0, 1.0, 1.0]),
                    ("1/1/5", [1.0, 1.0, 5.0])):
        r = run_case(f"unequal {lbl}", C3, 600, powers=pw)
        ent = {"powers": lbl}
        for nm in ("tree", "radial", "lattice"):
            v = r.get(f"per_die_{nm}")
            if v:
                ent[nm] = v
                ent[f"spread_{nm}"] = round(max(v) - min(v), 4)
        r26.append(ent)
        print(f"  {lbl:<8} " + "  ".join(
            f"{nm}: spread={ent.get(f'spread_{nm}')}" for nm in ent
            if f"spread_{nm}" in ent))
    print("\n  per-die mean T (the raw signature):")
    for e in r26:
        for nm in ("tree", "radial", "lattice"):
            if nm in e:
                print(f"    {e['powers']:<8} {nm:<8} {e[nm]}")

    # The test. Unequal power ALONE makes the per-die means unequal, for any
    # topology. "Adaptive" can only mean: the tree's spread is SMALLER than a
    # non-adaptive control's, i.e. the tree moved cold capacity toward the
    # hot die and flattened the profile. A spread that merely grows with the
    # power ratio proves nothing -- that is the confound this guards against.
    print("\n  verdict: a growing spread proves nothing on its own "
          "(unequal power alone produces it).")
    for e in r26:
        if "spread_tree" in e and "spread_radial" in e:
            d = e["spread_radial"] - e["spread_tree"]
            print(f"    {e['powers']:<8} radial-tree spread gap = {d:+.4f} C "
                  f"({'tree flatter' if d > 0.05 else ('tie' if abs(d) <= 0.05 else 'radial flatter')})")
    flat = [e for e in r26
            if "spread_tree" in e and "spread_radial" in e
            and e["spread_radial"] - e["spread_tree"] > 0.05]
    print(f"\n  R26: tree flatter than one-pipe-per-chip in "
          f"{len(flat)} of {sum(1 for e in r26 if 'spread_tree' in e and 'spread_radial' in e)} "
          f"power sets")

    # TASK-3: re-measure every hot-zone column at one shared absolute
    # threshold before anything reads them.
    apply_shared_threshold(rows)

    write_thermal_csv(rows)

    # ---- verdicts ----
    # "connected" = the tree physically enters every chip's source block
    # (max_chip_to_tree_dist == 0), which is the fairness precondition of
    # MS.CONNECTED_FROM. The old key `maxdist` measured the opposite
    # direction (tree cell -> chip centroid) and is kept only as a
    # diagnostic; see the comment in run_case.
    conn = [r for r in rows if r.get("max_chip_to_tree_dist") == 0]
    print(f"\nconnected cases: {len(conn)} of {len(rows) - n_skipped} "
          f"ran ({n_skipped} excluded by the N4b gate)")

    def frac(rows, key, better):
        sub = [r for r in rows if key in r and r[key] is not None]
        if not sub:
            return 0, 0
        win = sum(1 for r in sub if better(r[key]))
        return win, len(sub)

    # d_T_max = control - tree, so POSITIVE means the tree is cooler.
    w, n = frac(conn, "d_T_max", lambda v: v > 1e-9)
    print(f"R24 tree T_max below radial-per-chip: {w}/{n}")
    # TASK-3: the hot-zone verdicts are read from the SHARED-threshold
    # columns. The own-threshold `d_hotspot` columns are still printed for
    # continuity but are the biased metric and must not be quoted.
    w_own, n_own = frac(conn, "d_hotspot", lambda v: v > 1.0)
    w, n = frac(conn, "d_hotspot_shared_radial", lambda v: v > 1.0)
    print(f"    tree hot-zone below radial (>1 mm^2): {w}/{n} shared "
          f"[own-threshold biased reading was {w_own}/{n_own}]")
    w, n = frac(conn, "lat_d_T_max", lambda v: v > 1e-9)
    print(f"R25 tree T_max below best-pitch lattice: {w}/{n}")
    w_own, n_own = frac(conn, "lat_d_hotspot", lambda v: v > 1.0)
    w, n = frac(conn, "d_hotspot_shared_lattice", lambda v: v > 1.0)
    print(f"    tree hot-zone below lattice (>1 mm^2): {w}/{n} shared "
          f"[own-threshold biased reading was {w_own}/{n_own}]")

    # equal-pinned audit -- the fairness constraint that failed before
    bad = [r for r in conn
           if r.get("radial_pinned") != r["tree_pinned"]
           or r.get("lattice_pinned") != r["tree_pinned"]]
    print(f"\nequal-pinned violations: {len(bad)} of {len(conn)}")
    for r in bad[:10]:
        print(f"    {r['case']} b={r['budget']}: tree={r['tree_pinned']} "
              f"radial={r.get('radial_pinned')} lattice={r.get('lattice_pinned')}")

    (OUT / "spread_source_thermal_summary.json").write_text(
        json.dumps({
            "source_radius_cells": SRC_RADIUS,
            "src_cells_per_die": n_cells,
            "die_area_mm2": round(area_mm2, 1),
            "power_density_w_cm2": round(DIE_POWER_W / (area_mm2 / 100.0), 1),
            "real_i7_power_density_w_cm2": 98.0,
            "q_per_cell": q_per_cell(SRC_RADIUS),
            "base_q_per_cell": BASE_Q_PER_CELL,
            "n_cases": len(rows),
            "n_connected": len(conn),
            "r26_unequal_power": r26,
            "rows": rows,
        }, indent=2), encoding="utf-8")
    print("\nwrote outputs/spread_source_thermal.csv + _summary.json")
    return rows


if __name__ == "__main__":
    run()
