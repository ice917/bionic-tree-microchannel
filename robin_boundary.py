"""Task 3, corrected: Robin boundary on the RAW (un-normalised) field.

WHY THE FIRST RUN WAS INVALID: `normalize_field` rescales the field so its
peak is exactly 100 C. That is an affine map, so it preserves every
*relative* statement -- but it DESTROYS every absolute one, and the whole
point of the Robin boundary is absolute: a finite-convection edge makes the
plate hotter than an ideal cold sink. After normalisation the peak is 100
for every h, so T_max, T_mean and the hot-zone area came out identical and
the experiment measured nothing. (Verified: raw T_max moves by up to
0.21 C across the sweep, and the normalisation scale moves by 1.4%, yet
"T_max after norm" is 100.000000 for all h.)

So this version uses the raw field. The T_cool pinning in `apply_channels`
is unchanged -- the coolant is still an ideal sink, only the PLATE EDGE is
now finite. The comparison stays fair: both groups get the same h.

Pre-registered:
  R11  Does the single-source three-way TIE survive the Robin edge?
  R12  Does the multi-source tree ADVANTAGE survive?
  R13  Does the RANKING of tree vs control flip anywhere in the sweep?
  R14  How large must h be before the absolute temperature moves by more
       than the 0.05 C measurement floor? (i.e. is the idealisation
       material at all, or is the Dirichlet edge a harmless approximation?)
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import field as F
import grow as G
import multi_source as MS
import radius as R
import verify as V

OUT = Path(__file__).resolve().parent / "outputs"

GRID = 50
# Bi = h_conv * PITCH_MM / k with k=1, h=1 mm. Bi=0.01 -> a weak edge,
# Bi=100 -> essentially Dirichlet again. The sweep brackets the physical
# range: a 1 mm silicon fin with h=1e4 W/m2K gives Bi ~ 0.07.
H_SWEEP = [0.0, 0.001, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 100.0]


def sweep_single():
    print("=" * 78)
    print("B1: single source, tree vs straight-channel control, RAW field")
    print("=" * 78)
    rows = []
    for h in H_SWEEP:
        src = F.source_mask(GRID, (25, 25), radius=F.SRC_RADIUS_SYNTHETIC)
        res = F.solve_heat(grid=GRID, source_center=(25, 25),
                           source_radius=F.SRC_RADIUS_SYNTHETIC, h_conv=h)
        T = res.T                      # NO normalisation
        edges = G.grow_tree(T, max_nodes=400)
        radii = R.assign_radii(edges, grid=GRID, r0=0.5)
        tg = V.tree_group(T, src, edges, radii, grid_x=GRID, h_conv=h)
        n_cells = len(set([p for p, _ in edges] + [c for _, c in edges]))
        n_ctrl = max(1, n_cells // GRID)
        sg = V.straight_group(T, src, n_channels=n_ctrl,
                              total_area_mm2=tg.total_area_mm2, grid_x=GRID,
                              grid_y=GRID, h_conv=h)
        rows.append({
            "h_conv": h, "Bi": round(h * F.PITCH_MM, 5),
            "iters": res.iterations,
            "raw_T_max": round(float(T.max()), 4),
            "tree_T_max": round(tg.T_max, 4),
            "ctrl_T_max": round(sg.T_max, 4),
            "dT_max": round(tg.T_max - sg.T_max, 6),
            "tree_T_mean": round(tg.T_mean_solid, 4),
            "ctrl_T_mean": round(sg.T_mean_solid, 4),
            "dT_mean": round(tg.T_mean_solid - sg.T_mean_solid, 6),
            "tree_hot": round(tg.hotspot_area, 3),
            "ctrl_hot": round(sg.hotspot_area, 3),
            "dHotspot": round(tg.hotspot_area - sg.hotspot_area, 3),
            "tree_pinned": tg.pinned_cells, "ctrl_pinned": sg.pinned_cells,
            "dp_ratio": round(tg.dp / sg.dp, 1),
        })
        r = rows[-1]
        print(f"  h={h:<7} Bi={h:<6} iters={res.iterations:<6} "
              f"raw T_max={r['raw_T_max']:<9} "
              f"T_max {r['tree_T_max']}/{r['ctrl_T_max']} d={r['dT_max']:+.6f}  "
              f"T_mean d={r['dT_mean']:+.6f}  hot d={r['dHotspot']:+.3f}")
    return rows


def sweep_multi():
    print("\n" + "=" * 78)
    print("B2: multi source (3 chips), tree vs radial control, RAW field")
    print("=" * 78)
    centers = MS.LAYOUTS["3 chips, triangle"]
    rows = []
    for h in H_SWEEP:
        res = F.solve_heat_sources(grid=GRID, centers=centers,
                                   source_radius=F.SRC_RADIUS_REAL, h_conv=h)
        T = res.T                      # NO normalisation
        src = F.source_mask_multi(GRID, centers, radius=F.SRC_RADIUS_REAL)
        edges = G.grow_tree(T, max_nodes=600)
        radii = R.assign_radii(edges, grid=GRID, r0=0.5)
        tg = V.tree_group(T, src, edges, radii, grid_x=GRID, h_conv=h)
        rg = V.radial_group_pinned(T, src, target_pinned=tg.pinned_cells,
                                   total_area_mm2=tg.total_area_mm2,
                                   grid_x=GRID, grid_y=GRID, h_conv=h)
        rows.append({
            "h_conv": h, "Bi": round(h * F.PITCH_MM, 5),
            "iters": res.iterations,
            "raw_T_max": round(float(T.max()), 4),
            "tree_T_max": round(tg.T_max, 4),
            "ctrl_T_max": round(rg.T_max, 4),
            "dT_max": round(tg.T_max - rg.T_max, 6),
            "tree_T_mean": round(tg.T_mean_solid, 4),
            "ctrl_T_mean": round(rg.T_mean_solid, 4),
            "dT_mean": round(tg.T_mean_solid - rg.T_mean_solid, 6),
            "tree_hot": round(tg.hotspot_area, 3),
            "ctrl_hot": round(rg.hotspot_area, 3),
            "dHotspot": round(tg.hotspot_area - rg.hotspot_area, 3),
            "tree_pinned": tg.pinned_cells, "ctrl_pinned": rg.pinned_cells,
            "dp_ratio": round(tg.dp / rg.dp, 1),
        })
        r = rows[-1]
        print(f"  h={h:<7} Bi={h:<6} iters={res.iterations:<6} "
              f"raw T_max={r['raw_T_max']:<9} "
              f"T_max {r['tree_T_max']}/{r['ctrl_T_max']} d={r['dT_max']:+.6f}  "
              f"T_mean d={r['dT_mean']:+.6f}  hot d={r['dHotspot']:+.3f}  "
              f"pin={r['tree_pinned']}/{r['ctrl_pinned']}")
    return rows


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    part_file = OUT / "robin_boundary_parts.json"
    parts = {}
    if part_file.exists():
        parts = json.loads(part_file.read_text(encoding="utf-8"))
    single = sweep_single() if which in ("all", "b1") else parts.get("single", [])
    multi = sweep_multi() if which in ("all", "b2") else parts.get("multi", [])
    if single:
        parts["single"] = single
    if multi:
        parts["multi"] = multi
    # Persist BEFORE writing the merged CSV, so a later b1-only rerun cannot
    # wipe the b2 rows (the first version overwrote the CSV on every run and
    # silently lost whichever half was not re-run).
    part_file.write_text(json.dumps(parts, indent=2), encoding="utf-8")
    single, multi = parts.get("single", []), parts.get("multi", [])

    with open(OUT / "robin_boundary_scan.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["experiment", "h_conv", "Bi", "iters", "raw_T_max",
                    "tree_T_max", "ctrl_T_max", "dT_max", "tree_T_mean",
                    "ctrl_T_mean", "dT_mean", "tree_hot", "ctrl_hot",
                    "dHotspot", "tree_pinned", "ctrl_pinned", "dp_ratio"])
        for tag, rr in (("single", single), ("multi", multi)):
            for r in rr:
                w.writerow([tag, r["h_conv"], r["Bi"], r["iters"],
                            r["raw_T_max"], r["tree_T_max"], r["ctrl_T_max"],
                            r["dT_max"], r["tree_T_mean"], r["ctrl_T_mean"],
                            r["dT_mean"], r["tree_hot"], r["ctrl_hot"],
                            r["dHotspot"], r["tree_pinned"],
                            r["ctrl_pinned"], r["dp_ratio"]])
    (OUT / "robin_boundary_summary.json").write_text(
        json.dumps({"grid": GRID, "h_sweep": H_SWEEP,
                    "note": "raw field, NOT normalised",
                    "single": single, "multi": multi}, indent=2),
        encoding="utf-8")
    print("\nwrote outputs/robin_boundary_scan.csv (+ summary.json)")

    if single:
        print("\nR11 single-source tie under Robin:")
        broken = [r for r in single
                  if abs(r["dT_max"]) > 1e-4 or abs(r["dT_mean"]) > 1e-4
                  or abs(r["dHotspot"]) > 1e-3]
        print(f"  tie broken at {len(broken)}/{len(single)} h values")
        for r in broken:
            print(f"    h={r['h_conv']}: dT_max={r['dT_max']:+.4f} "
                  f"dT_mean={r['dT_mean']:+.4f} dHot={r['dHotspot']:+.2f}")
        print("\nR14 materiality of the idealisation (raw T_max vs Dirichlet):")
        base = single[0]["raw_T_max"]
        for r in single:
            d = r["raw_T_max"] - base
            flag = "  <-- exceeds 0.05 C floor" if abs(d) > 0.05 else ""
            print(f"    h={r['h_conv']:<8} raw T_max={r['raw_T_max']:<9} "
                  f"shift={d:+.4f} C{flag}")
    if multi:
        print("\nR12/R13 multi-source advantage under Robin:")
        flips = [r for r in multi
                 if r["dT_max"] > 0 or r["dHotspot"] > 0]
        print(f"  ranking flips at {len(flips)}/{len(multi)} h values")
        for r in flips:
            print(f"    h={r['h_conv']}: dT_max={r['dT_max']:+.4f} "
                  f"dHot={r['dHotspot']:+.2f} dT_mean={r['dT_mean']:+.4f}")
        adv = [r for r in multi if r["dT_mean"] < 0]
        print(f"  tree keeps a T_mean advantage at {len(adv)}/{len(multi)} h values")
        worst = min(multi, key=lambda r: r["dT_mean"])
        best = max(multi, key=lambda r: r["dT_mean"])
        print(f"  dT_mean range: {best['dT_mean']:+.4f} (h={best['h_conv']}) "
              f"to {worst['dT_mean']:+.4f} (h={worst['h_conv']})")


if __name__ == "__main__":
    main()
