"""extend_surface.py -- widen the comparison surface (REPORT.md section 16).

Three things the earlier report never varied, all of them suspected of being
the reason the temperature metrics saturated:

  1. UNEQUAL chip power. Every earlier experiment gave every chip the same
     q, so the hot-zone area was exactly the sum of the chip blocks BY
     CONSTRUCTION and the tree could never be tested on "does it send
     material where the heat is". Real packages differ by multiples.

  2. A LATTICE control. The tree was only ever compared against
     one-pipe-per-chip. A uniform lattice (parallel channels both ways, no
     taper, no Steiner points) separates "the tree is adaptive" from "the
     tree just covers more plate".

  3. PRESSURE-DROP-NORMALISED material cost. The tree loses 1e3-1e4x on
     Poiseuille dp, so "the tree uses less material" was never a meaningful
     statement. Here every topology is re-scaled to the SAME dp, and the
     material that costs is the number that is compared.

Fairness is unchanged from REPORT.md 2.3 / 7.2: equal PINNED cell count and
equal total cross-section within each comparison. The dp-normalised variant
sacrifices equal material (that is the point of it) and is reported
separately, never mixed with the equal-material rows.

Pre-registered decision rules (fixed before the run, so the result cannot be
reinterpreted afterwards):

  R1  "the tree is adaptive" holds iff, under UNEQUAL power, the tree's
      hot-zone area is smaller than the lattice's by more than the solver
      noise, i.e. dHotspot < -1.0 mm2.
  R2  "the lattice is competitive" holds iff the lattice's T_mean is within
      0.05 C of the tree's under unequal power.
  R3  "the tree's material advantage is real" holds iff, at equal dp, the
      tree's material is more than 5% below the lattice's.
  R4  If none of R1-R3 fires, the honest report is "widening the surface did
      not change the conclusion", and the numbers are published as-is.

    python extend_surface.py [--grid 50] [--budget 600] [--no-fig]
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

# Triangle layout, the one REPORT.md section 7 and section 11 both use, so
# the unequal-power rows are directly comparable with the equal-power ones.
CENTERS = [(15, 15), (35, 15), (25, 35)]

# (label, powers) -- powers are per-cell q, so total power = 25 * q.
POWER_SETS = [
    ("equal 1/1/1", [1.0, 1.0, 1.0]),
    ("unequal 1/2/3", [1.0, 2.0, 3.0]),
    ("unequal 3/1/1", [3.0, 1.0, 1.0]),
    ("unequal 1/1/5", [1.0, 1.0, 5.0]),
]

# Solver noise floor. apply_channels converges to 1e-7 on the update, which
# leaves ~1e-3 on a converged field; the hotspot area is an integer count of
# cells, so 1 mm2 (one cell) is the smallest difference that means anything.
NOISE_MM2 = 1.0
NOISE_C = 0.05


def solve(centers, powers, grid=50, source_radius=F.SRC_RADIUS_REAL):
    rs = F.solve_heat_sources(grid=grid, centers=centers,
                              source_radius=source_radius, powers=powers)
    T = F.normalize_field(rs.T, T_target=100.0)
    src = F.source_mask_multi(grid, centers, radius=source_radius)
    return T, src, rs


def dp_for_material(material_mm2, n_segments, L_mm, q_share):
    """Poiseuille dp of a channel of radius r and length L carrying q_share.

    r is chosen so that n_segments of it use `material_mm2` of cross-section:
    material ~ n * pi * r^2 (a 1-cell-wide channel's footprint).
    """
    r = float(np.sqrt(material_mm2 / (n_segments * np.pi)))
    if r <= 0:
        return 0.0
    return 8.0 * V.MU * L_mm * q_share / (np.pi * r ** 4)


def run_case(label, powers, budget, grid=50):
    T, src, rs = solve(CENTERS, powers, grid=grid)
    # The weighted source term. apply_channels re-solves the field from
    # scratch, so it must be told the real per-cell q -- otherwise every
    # power set is silently re-solved as equal-power and the controls come
    # out identical.
    strength = F.source_strength_multi(grid, CENTERS, radius=F.SRC_RADIUS_REAL,
                                       powers=powers)

    # --- tree (the subject) ---
    edges = G.grow_tree(T, max_nodes=budget)
    radii = Ra.assign_radii(edges, grid=grid, r0=0.5)
    tg = V.tree_group(T, src, edges, radii, grid_x=grid, strength=strength)
    cells = sorted(set([p for p, _ in edges] + [c for _, c in edges]))
    blobs = V._cluster_centers(src)
    dists = [min(abs(i // grid - int(round(cy))) + abs(i % grid - int(round(cx)))
                 for i in cells) for cy, cx in blobs]
    maxdist = max(dists)

    # --- two controls, both matched to the tree's pinned count ---
    rg = V.radial_group_pinned(T, src, target_pinned=tg.pinned_cells,
                               total_area_mm2=tg.total_area_mm2,
                               grid_x=grid, grid_y=grid, strength=strength)
    lg = V.lattice_group(T, src, target_pinned=tg.pinned_cells,
                         total_area_mm2=tg.total_area_mm2,
                         grid_x=grid, grid_y=grid, strength=strength)

    # --- dp-normalised variant: rescale every group to the tree's dp ---
    # The tree's material is the budget. Each control is re-sized so that its
    # own Poiseuille dp equals the tree's, and the material it then needs is
    # the reported cost. This is the only comparison in which "the tree is
    # efficient" could be true.
    def normalise(g: V.Group, n_seg: int, L_mm: float) -> tuple[float, float]:
        """Return (material_at_equal_dp, scale_factor).

        dp ~ Q/(n r^4) and material ~ n r^2, so at fixed dp and fixed segment
        count, material ~ dp^(1/2): doubling dp costs sqrt(2) in material.
        Solved directly for r, then converted to material.
        """
        q_share = V.Q_TOTAL / max(1, n_seg)
        if g.dp <= 0:
            return g.total_area_mm2, 1.0
        # r that gives the TARGET dp
        r_target = (8.0 * V.MU * L_mm * q_share / (np.pi * tg.dp)) ** 0.25
        r_now = float(np.sqrt(g.total_area_mm2 / (n_seg * np.pi)))
        if r_now <= 0:
            return g.total_area_mm2, 1.0
        scale = r_target / r_now
        return g.total_area_mm2 * scale ** 2, scale

    n_tree = max(1, len(edges))
    # radial pipes run chip -> nearest edge, so their length is the mean of
    # those spans, not the plate size.
    rg_L = float(np.mean([min(cy, grid - 1 - cy, cx, grid - 1 - cx) + 1
                          for cy, cx in blobs]))
    rg_mat, rg_scale = normalise(rg, max(1, rg.n_segments), rg_L)
    lg_mat, lg_scale = normalise(lg, max(1, lg.n_channels), 0.5 * (grid + grid))

    return {
        "case": label,
        "powers": "/".join(f"{p:g}" for p in powers),
        "budget": budget,
        "max_chip_dist": int(maxdist),
        "tree": tg, "radial": rg, "lattice": lg,
        "dp_normalised": {
            "tree_material": tg.total_area_mm2,
            "radial_material_at_equal_dp": rg_mat,
            "radial_scale": rg_scale,
            "lattice_material_at_equal_dp": lg_mat,
            "lattice_scale": lg_scale,
            "tree_dp": tg.dp,
        },
        "field_iters": rs.iterations,
    }


def row(r: dict) -> dict:
    tg, rg, lg = r["tree"], r["radial"], r["lattice"]
    dn = r["dp_normalised"]
    return {
        "case": r["case"],
        "powers": r["powers"],
        "max_chip_dist": r["max_chip_dist"],
        "tree_T_max": round(tg.T_max, 4),
        "tree_T_mean": round(tg.T_mean_solid, 4),
        "tree_hotspot": round(tg.hotspot_area, 1),
        "tree_dp": round(tg.dp, 3),
        "tree_material": round(tg.total_area_mm2, 3),
        "radial_T_mean": round(rg.T_mean_solid, 4),
        "radial_hotspot": round(rg.hotspot_area, 1),
        "radial_dp": round(rg.dp, 4),
        "lattice_T_mean": round(lg.T_mean_solid, 4),
        "lattice_hotspot": round(lg.hotspot_area, 1),
        "lattice_dp": round(lg.dp, 4),
        "lattice_pinned_gap": lg.pinned_cells - tg.pinned_cells,
        "pinned_tree": tg.pinned_cells,
        "pinned_radial": rg.pinned_cells,
        "pinned_lattice": lg.pinned_cells,
        "dTmean_tree_minus_lattice": round(tg.T_mean_solid - lg.T_mean_solid, 5),
        "dHotspot_tree_minus_lattice": round(tg.hotspot_area - lg.hotspot_area, 2),
        "dHotspot_tree_minus_radial": round(tg.hotspot_area - rg.hotspot_area, 2),
        "material_ratio_tree_over_lattice_equal_dp": round(
            dn["tree_material"] / dn["lattice_material_at_equal_dp"], 4)
        if dn["lattice_material_at_equal_dp"] else None,
        "material_ratio_tree_over_radial_equal_dp": round(
            dn["tree_material"] / dn["radial_material_at_equal_dp"], 4)
        if dn["radial_material_at_equal_dp"] else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", type=int, default=50)
    ap.add_argument("--budget", type=int, default=600)
    ap.add_argument("--no-fig", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    results = [run_case(lbl, p, args.budget, grid=args.grid)
               for lbl, p in POWER_SETS]
    rows = [row(r) for r in results]

    with open(OUT / "extend_surface_results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    (OUT / "extend_surface_summary.json").write_text(json.dumps(
        {"grid": args.grid, "budget": args.budget, "centers": CENTERS,
         "power_sets": {l: p for l, p in POWER_SETS}, "rows": rows},
        indent=2), encoding="utf-8")

    # ---------------- pre-registered decisions ----------------
    print("=" * 74)
    print("WIDENED SURFACE -- pre-registered rules R1-R4")
    print("=" * 74)
    for r in rows:
        print(f"\n[{r['case']}] powers={r['powers']}  max_chip_dist={r['max_chip_dist']}")
        print(f"  tree     T_max={r['tree_T_max']:8.4f}  T_mean={r['tree_T_mean']:.5f}"
              f"  hotspot={r['tree_hotspot']:7.1f}  dp={r['tree_dp']:10.3f}"
              f"  mat={r['tree_material']:9.3f}")
        print(f"  lattice  T_max={'':8}  T_mean={r['lattice_T_mean']:.5f}"
              f"  hotspot={r['lattice_hotspot']:7.1f}  dp={r['lattice_dp']:10.4f}")
        print(f"  radial   T_max={'':8}  T_mean={r['radial_T_mean']:.5f}"
              f"  hotspot={r['radial_hotspot']:7.1f}  dp={r['radial_dp']:10.4f}")
        print(f"  pinned: tree={r['pinned_tree']} lattice={r['pinned_lattice']}"
              f" radial={r['pinned_radial']}"
              f"  gap: lattice={r['lattice_pinned_gap']:+d}"
              f" radial={r['pinned_radial'] - r['pinned_tree']:+d}"
              f"  (|gap|<=2 required for fairness)")

    print("\n" + "=" * 74)
    print("DECISIONS")
    print("=" * 74)
    r1 = [r for r in rows if r["dHotspot_tree_minus_lattice"] < -NOISE_MM2]
    r2 = [r for r in rows if abs(r["dTmean_tree_minus_lattice"]) <= NOISE_C]
    r3 = [r for r in rows
          if r["material_ratio_tree_over_lattice_equal_dp"] is not None
          and r["material_ratio_tree_over_lattice_equal_dp"] < 0.95]

    print(f"R1 tree adaptive (hotspot < lattice by >{NOISE_MM2} mm2): "
          f"{len(r1)}/{len(rows)} cases -> "
          f"{'FIRES' if r1 else 'does NOT fire'}")
    for r in r1:
        print(f"     {r['case']}: dHotspot={r['dHotspot_tree_minus_lattice']} mm2")

    print(f"R2 lattice competitive (|dT_mean| <= {NOISE_C} C): "
          f"{len(r2)}/{len(rows)} cases -> "
          f"{'FIRES' if r2 else 'does NOT fire'}")

    print(f"R3 tree material advantage at equal dp (>5% below lattice): "
          f"{len(r3)}/{len(rows)} cases -> "
          f"{'FIRES' if r3 else 'does NOT fire'}")
    for r in r3:
        print(f"     {r['case']}: mat ratio="
              f"{r['material_ratio_tree_over_lattice_equal_dp']}")

    if not (r1 or r2 or r3):
        print("\nR4: no rule fired -> widening the surface did NOT change the")
        print("    conclusion. Numbers published as-is.")
    else:
        print("\nAt least one rule fired; see the case lines above for which.")

    print(f"\nDone -> outputs/extend_surface_results.csv")


if __name__ == "__main__":
    main()
