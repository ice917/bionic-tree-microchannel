"""Scan the lattice pitch under the equal-pinned rule, allowing per-cell
trimming (which is how `lattice_group` actually hits an exact count).

WHY THE FIRST TWO VERSIONS WERE WRONG:

v1 swept every pitch and let pitch 1 (full density, ~2400 pinned cells)
compete against a 650-cell tree. That measures the budget, not the
topology -- the exact §7.2 mistake.

v2 restricted to |pinned - target| <= 40 at a FIXED pitch. It worked for
2/3/4 chips at budgets 600-800, but returned "no admissible pitch" for
every 5-chip case and every 1300 budget -- because a pure pitch jumps the
pinned count by ~100-200 cells between adjacent pitches. `lattice_group`
hits an exact count only because it TRIMS INDIVIDUAL CELLS after choosing
a pitch. So v2's "NONE" was an artefact of the search space, not a fact
about the plate.

v3 (this file): for each pitch, build the lattice, then trim/add cells one
at a time until the measured pinned count equals the tree's exactly. The
pitch is now a genuine free parameter of the CONTROL, and the fairness
constraint (equal pinned) is enforced exactly, not approximately. This is
the fair version of "let the lattice choose its own density".

Pre-registered:
  R5  at some pitch, does the trimmed lattice beat the tree's hot-spot area
      by more than 1 mm^2?  -> the tree's hotspot edge is not robust.
  R6  do different pitches disagree about who wins?  -> §16.5's bisection
      silently picked one pitch; if the answer depends on the choice, the
      "1.2x" figure is a choice, not a fact.
  R7  at the pitch with the lowest lattice T_max, is |dTmax| < 0.5 C?
      -> "adaptive" vs "covers more" stays confounded at T_max too.
"""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import field as F
import multi_source as MS
import spread_source_scan as SS
import verify as V

OUT = Path(__file__).resolve().parent / "outputs"
PARTS = OUT / "_pitch_parts"
PARTS.mkdir(exist_ok=True)

GRID = 50
PITCHES = list(range(1, 14))
TRIMMED = True

# Aligned with the R24/R25 authority's case set (spread_source_scan.run:
# MS.LAYOUTS x MS.BUDGETS). The previous chunking used a different budget
# subset (700/800/1300, with 600 in place of the authority's 400/600/1000),
# so its rows could not be matched one-to-one against the CSV they were
# meant to corroborate.
CHUNKS = {
    0: ("2chips", "2 chips, 20 mm apart", list(MS.BUDGETS)),
    1: ("3chips", "3 chips, triangle", list(MS.BUDGETS)),
    2: ("4chips", "4 chips, corners", list(MS.BUDGETS)),
    3: ("5chips", "5 chips, corners+centre", list(MS.BUDGETS)),
}


def lattice_cells(pitch: int) -> set:
    cells = set()
    for y in range(0, GRID, pitch):
        cells.update((y, x) for x in range(GRID))
    for x in range(0, GRID, pitch):
        cells.update((y, x) for y in range(GRID))
    return cells


def solve_lattice(T, src, cells, total_area_mm2, strength):
    Tc, pinned = V.apply_channels(T, sorted(cells), src, V.T_COOL,
                                  strength=strength)
    rows = sorted({y for (y, _) in cells})
    cols = sorted({x for (_, x) in cells})
    n_ch = len(rows) + len(cols)
    L = 0.5 * (GRID + GRID) * V.PITCH_MM
    r = float((total_area_mm2 / max(1, len(cells)) / 3.141592653589793) ** 0.5)
    dp = (8.0 * V.MU * L * (V.Q_TOTAL / n_ch)
          / (3.141592653589793 * r ** 4)) if r > 0 else 0.0
    return V.Group.from_field("lattice", Tc, pinned, dp, total_area_mm2,
                              len(cells), n_ch, V.T_COOL, 0.25, V.PITCH_MM)


def trim_to_target(T, src, cells, target, total_area_mm2, strength, chip_cells):
    """Delete individual cells (farthest from the centre first) until the
    measured pinned count equals `target` exactly. Source cells are never
    deletable. Returns (cells, pinned_after, ok)."""
    g = solve_lattice(T, src, cells, total_area_mm2, strength)
    if g.pinned_cells < target:
        return cells, g.pinned_cells, False   # cannot add without new channels
    order = []
    for y in sorted({yy for (yy, _) in cells}):
        order += [(y, x) for x in range(GRID - 1, -1, -1) if (y, x) in cells]
    for x in sorted({xx for (_, xx) in cells}):
        order += [(y, x) for y in range(GRID - 1, -1, -1)
                  if (y, x) in cells and (y, x) not in set(order)]
    for cell in order:
        if g.pinned_cells <= target:
            break
        if cell in chip_cells:
            continue
        trial = cells - {cell}
        g2 = solve_lattice(T, src, trial, total_area_mm2, strength)
        if g2.pinned_cells < g.pinned_cells:
            cells, g = trial, g2
    return cells, g.pinned_cells, (g.pinned_cells == target)


def run_case(label, centers, budget):
    # N4b gate (migrated from spread_source_scan.layout_is_valid): at the
    # real 17x17 footprint the 5-chip corners+centre layout fuses into one
    # connected region, so its per-die numbers are undefined. 2026-10-18
    # wave-3 re-generation: this script used to run that layout and its
    # output fed REPORT §9.6 -- those rows are now known invalid.
    src_probe = F.source_mask_multi(GRID, centers, radius=F.SRC_RADIUS_REAL)
    if len(V._cluster_centers(src_probe)) != len(centers):
        return {"case": f"{label} | budget {budget}",
                "skipped": "N4b: source blocks fuse into fewer regions "
                           "than chips at radius 8.0 -- per-die metrics undefined"}

    # The field must come from the N4-GUARDED entry point, not from
    # `multi_source.solve_layout`'s default-q path. The two differ by 5.9e-4 C
    # in the normalised field (solve_layout does not apply the per-cell q
    # that keeps total die power constant when source blocks overlap), which
    # is enough to send `grow_tree` down a different branch: measured on the
    # 3-chip triangle at budget 600, solve_layout gives src_to_tree=6 while
    # the guarded path gives src_to_tree=13 -- a different tree, so different
    # numbers. A topology difference is NOT a tolerable floating-point
    # difference. spread_source_scan.run_case (the R24/R25 authority) uses
    # solve_spread, so this script must too or it measures a different
    # experiment.
    T, src, strength = SS.solve_spread(centers, grid=GRID, radius=F.SRC_RADIUS_REAL,
                                       powers=None)
    # N4c (2026-10-18): `strength` MUST be forwarded. Omitting it makes
    # verify.apply_channels fall back to a boolean source (q=1 per heated
    # cell = 289 units/die on the 17x17 footprint), while solve_lattice /
    # trim_to_target below are solved at the guarded 25 units/die. Measured
    # on "2 chips, 20 mm apart | budget 400": T_max 67.5917 C without
    # strength vs 28.6844 C with it (11.56x power), i.e. the two sides of
    # every row of lattice_pitch_scan.csv were solved at different die power.
    tg, edges, radii, cells, src_to_tree, block_to_tree = MS.tree_metrics(
        T, src, budget, grid=GRID, centers=centers, radius=F.SRC_RADIUS_REAL,
        strength=strength)
    # ADMISSIBILITY GATE, corrected 2026-10-18. This script used to gate on
    # `max(src_to_tree) != 0`, i.e. "every heated cell has a tree cell on top
    # of it" -- a condition no budget-limited tree meets on a 17x17 footprint
    # (measured src_to_tree 13-20 at budgets 600-800), so 10 of 12 cases were
    # skipped as "disconnected" while being perfectly admissible. The metric
    # CONNECTED_FROM is about -- and the one spread_source_scan's "connected"
    # verdict uses -- is block_to_tree: does the tree physically enter every
    # chip's footprint. Gate on that; keep src_to_tree as a diagnostic.
    if block_to_tree != 0:
        return {"case": f"{label} | budget {budget}",
                "skipped": f"tree misses a chip block, block_to_tree="
                           f"{block_to_tree} (src_to_tree={src_to_tree[0]})"}

    # The piped-around block is the whole 17x17 real-die footprint, not the
    # 5x5 concentrated block. At radius 2.0 these two coincide; at the real
    # 8.0 footprint the old 5x5 left 264 heat cells per chip unprotected,
    # so the lattice control was measured on a different problem than the
    # tree. (Same class as the exempt_per_chip=25 stale constant,
    # DEFECT_REMEDIATION_PLAN.md §10.13.)
    half = int(F.SRC_RADIUS_REAL)
    chip_cells = set()
    for cy, cx in centers:
        for dy in range(-half, half + 1):
            for dx in range(-half, half + 1):
                chip_cells.add((int(round(cy)) + dy, int(round(cx)) + dx))

    out = {"case": f"{label} | budget {budget}",
           "tree_pinned": tg.pinned_cells,
           "tree_T_max": round(tg.T_max, 4),
           "tree_T_mean": round(tg.T_mean_solid, 4),
           "tree_hotspot": round(tg.hotspot_area, 3),
           "tree_dp": round(tg.dp, 3),
           "src_to_tree": int(src_to_tree[0]),
           "lattice": []}
    for p in PITCHES:
        cells_l = lattice_cells(p)
        if TRIMMED:
            cells_l, got, ok = trim_to_target(T, src, cells_l, tg.pinned_cells,
                                              tg.total_area_mm2, strength, chip_cells)
        else:
            g = solve_lattice(T, src, cells_l, tg.total_area_mm2, strength)
            got, ok = g.pinned_cells, (g.pinned_cells == tg.pinned_cells)
        if not ok:
            out["lattice"].append({"pitch": p, "pinned": got, "ok": False,
                                   "note": "no exact equal-pinned lattice at this pitch"})
            continue
        g = solve_lattice(T, src, cells_l, tg.total_area_mm2, strength)
        out["lattice"].append({
            "pitch": p, "pinned": g.pinned_cells, "ok": True,
            "T_max": round(g.T_max, 4), "T_mean": round(g.T_mean_solid, 4),
            "hotspot": round(g.hotspot_area, 3), "dp": round(g.dp, 3),
            "n_segments": g.n_segments,
        })
    good = [d for d in out["lattice"] if d.get("ok")]
    out["n_admissible"] = len(good)
    if good:
        bh = min(good, key=lambda d: d["hotspot"])
        bt = min(good, key=lambda d: d["T_max"])
        out["best_hotspot_pitch"] = bh["pitch"]
        out["best_Tmax_pitch"] = bt["pitch"]
        out["tree_vs_best_hotspot"] = round(tg.hotspot_area - bh["hotspot"], 3)
        out["tree_vs_best_Tmax"] = round(tg.T_max - bt["T_max"], 4)
        out["tree_vs_best_Tmean"] = round(
            tg.T_mean_solid - min(d["T_mean"] for d in good), 4)
        out["hotspot_spread"] = round(max(d["hotspot"] for d in good)
                                      - min(d["hotspot"] for d in good), 3)
    return out


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "0"
    if which == "merge":
        merge()
        return
    name, key, budgets = CHUNKS[int(which)]
    t0 = time.perf_counter()
    rows = []
    for b in budgets:
        r = run_case(key, MS.LAYOUTS[key], b)
        rows.append(r)
        if "skipped" in r:
            print(f"  {r['case']}: SKIPPED ({r['skipped']})")
            continue
        good = [d["pitch"] for d in r["lattice"] if d.get("ok")]
        print(f"  {r['case']}: tree pin={r['tree_pinned']} T_max={r['tree_T_max']} "
              f"hot={r['tree_hotspot']} | exact-equal-pitch pitches: {good}")
        if r["n_admissible"]:
            print(f"    best-hot p{r['best_hotspot_pitch']} dHot={r['tree_vs_best_hotspot']:+.1f} "
                  f"best-Tmax p{r['best_Tmax_pitch']} dTmax={r['tree_vs_best_Tmax']:+.4f} "
                  f"dTmean={r['tree_vs_best_Tmean']:+.4f} spread={r['hotspot_spread']:.1f}")
    (PARTS / f"{name}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"[{name}] {len(rows)} cases in {time.perf_counter() - t0:.1f}s")


def merge():
    rows = []
    for k in sorted(CHUNKS):
        p = PARTS / f"{CHUNKS[k][0]}.json"
        if p.exists():
            rows += json.loads(p.read_text(encoding="utf-8"))
    live = [r for r in rows if "skipped" not in r]
    with open(OUT / "lattice_pitch_scan.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["case", "tree_pinned", "tree_T_max", "tree_T_mean",
                    "tree_hotspot", "tree_dp", "pitch", "lat_pinned",
                    "lat_T_max", "lat_T_mean", "lat_hotspot", "lat_dp",
                    "lat_segments", "dTmax", "dTmean", "dHotspot"])
        for r in live:
            for d in r["lattice"]:
                if not d.get("ok"):
                    continue
                w.writerow([r["case"], r["tree_pinned"], r["tree_T_max"],
                            r["tree_T_mean"], r["tree_hotspot"], r["tree_dp"],
                            d["pitch"], d["pinned"], d["T_max"], d["T_mean"],
                            d["hotspot"], d["dp"], d["n_segments"],
                            round(d["T_max"] - r["tree_T_max"], 4),
                            round(d["T_mean"] - r["tree_T_mean"], 4),
                            round(d["hotspot"] - r["tree_hotspot"], 3)])
    (OUT / "lattice_pitch_summary.json").write_text(
        json.dumps({"grid": GRID, "pitches": PITCHES,
                    "budgets": MS.BUDGETS, "cases": live}, indent=2),
        encoding="utf-8")

    ok = [r for r in live if r["n_admissible"]]
    print(f"merged {len(live)} live cases, {len(ok)} with >=1 exact-equal pitch")
    print(f"\n{'case':<44}{'treePin':>8}{'#p':>5}{'bestHot':>9}{'dHot':>8}"
          f"{'bestTmax':>9}{'dTmax':>9}{'dTmean':>9}{'spread':>8}")
    for r in live:
        if not r["n_admissible"]:
            print(f"{r['case']:<44}{r['tree_pinned']:>8}{0:>5}{'-':>9}{'-':>8}"
                  f"{'-':>9}{'-':>9}{'-':>9}{'-':>8}")
            continue
        print(f"{r['case']:<44}{r['tree_pinned']:>8}{r['n_admissible']:>5}"
              f"p{r['best_hotspot_pitch']:<8}{r['tree_vs_best_hotspot']:+8.1f}"
              f"p{r['best_Tmax_pitch']:<8}{r['tree_vs_best_Tmax']:+9.4f}"
              f"{r['tree_vs_best_Tmean']:+9.4f}{r['hotspot_spread']:>8.1f}")
    r5 = [r for r in ok if r["tree_vs_best_hotspot"] > 1.0]
    r6 = [r for r in ok if r["n_admissible"] > 1]
    r7 = [r for r in ok if abs(r["tree_vs_best_Tmax"]) < 0.5]
    print(f"\nR5 (some exact-equal pitch beats tree hotspot by >1 mm2): {len(r5)}/{len(ok)}")
    print(f"R6 (more than one exact-equal pitch exists): {len(r6)}/{len(ok)}")
    print(f"R7 (|dTmax| < 0.5 C at best exact-equal pitch): {len(r7)}/{len(ok)}")


if __name__ == "__main__":
    main()
