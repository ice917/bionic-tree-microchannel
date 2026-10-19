"""Task 1: unequal power x lattice pitch scan -- the one combination missing.

§16.4 (extend_surface.py) showed that under UNEQUAL power the tree's
"adaptive" claim reverses for the 1/1/5 power set -- the greedy tree
over-concentrates on the dominant chip and leaves a LARGER hot zone under
the low-power chips than a uniform lattice does. But that lattice was
built by `lattice_group`, whose pitch is reverse-engineered by bisection
to match the tree's pinned count.

§17 (lattice_scan.py) showed that when the pitch is FREE, the tree's
hot-spot edge is 6 win / 4 tie / 2 loss and is never unique.

The combination has not been run. It is the decisive test of the
"adaptive" story: the tree's claim to fame is that it moves material
toward heat. Under equal power, "toward heat" and "toward where the
channels happen to be" are hard to tell apart. Under unequal power they
should separate -- IF the tree is really adapting, it must beat a lattice
that is free to choose its density but cannot concentrate.

Pre-registered:
  R8   For the 1/1/5 power set, does SOME admissible pitch give a lattice
       whose hot zone beats the tree's by more than 1 mm^2?
       -> "adaptive" is dead as a general claim.
  R9   Count of cases where the tree's best-pitch deficit gets WORSE under
       unequal power than under equal power.
       -> unequal power hurts the tree more than it hurts a free lattice.
  R10  Does the tree's hot zone concentrate on the dominant chip? Measured
       as the fraction of the tree's hot-zone area inside the 5x block of
       the dominant chip. If "adaptive" is real this should RISE with the
       power ratio; if it is constant, the tree is not adapting at all.
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
PARTS = OUT / "_comb_parts"
PARTS.mkdir(exist_ok=True)

GRID = 50
PITCHES = list(range(1, 14))
LAYOUT = "3 chips, triangle"
CENTERS = MS.LAYOUTS[LAYOUT]
POWER_SETS = [
    ("equal 1/1/1", [1.0, 1.0, 1.0]),
    ("unequal 1/1/5", [1.0, 1.0, 5.0]),
    ("unequal 3/1/1", [3.0, 1.0, 1.0]),
    ("unequal 1/2/3", [1.0, 2.0, 3.0]),
]
BUDGET = 600

CHUNKS = {
    0: [("equal 1/1/1", [1.0, 1.0, 1.0]), ("unequal 1/1/5", [1.0, 1.0, 5.0])],
    1: [("unequal 3/1/1", [3.0, 1.0, 1.0]), ("unequal 1/2/3", [1.0, 2.0, 3.0])],
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


def chip_blocks():
    """The 17x17 real-die footprint of each chip centre.

    Was 5x5 (the concentrated-block footprint). At the real source radius
    8.0 the 5x5 window misses 264 of each die's 289 heated cells, so
    "hot-zone area per chip" was measuring a small patch of a much larger
    heated region. Same stale-constant class as exempt_per_chip=25
    (DEFECT_REMEDIATION_PLAN.md §10.13).
    """
    half = int(F.SRC_RADIUS_REAL)
    blocks = []
    for cy, cx in CENTERS:
        b = set()
        for dy in range(-half, half + 1):
            for dx in range(-half, half + 1):
                b.add((cy + dy, cx + dx))
        blocks.append(b)
    return blocks


def run_case(pname, powers):
    # N4b gate: this layout is a triangle, which is valid at radius 8, but
    # the gate is kept so a future layout change cannot silently re-run an
    # inadmissible one (the pre-gate 5-chip rows are void,
    # DEFECT_REMEDIATION_PLAN.md §10.8).
    src_probe = F.source_mask_multi(GRID, CENTERS, radius=F.SRC_RADIUS_REAL)
    if len(V._cluster_centers(src_probe)) != len(CENTERS):
        return {"case": f"{pname} | budget {BUDGET}",
                "skipped": "N4b: source blocks fuse into fewer regions "
                           "than chips at radius 8.0 -- per-die metrics undefined"}

    # N4-guarded field entry point -- see the identical note in
    # lattice_scan.py: multi_source.solve_layout's default-q path differs
    # from spread_source_scan.solve_spread by 5.9e-4 C in the normalised
    # field, which flips grow_tree branches and changes the tree that gets
    # grown (src_to_tree 6 vs 13 on the 3-chip triangle at budget 600). The
    # R24/R25 authority uses solve_spread, so this script must too.
    T, src, strength = SS.solve_spread(CENTERS, grid=GRID, radius=F.SRC_RADIUS_REAL,
                                       powers=powers)
    # N4c (2026-10-18): `strength` MUST be forwarded -- see the identical
    # note in lattice_scan.py. Without it the tree is re-solved at q=1 per
    # heated cell (11.56x the guarded die power) while the comb/lattice
    # controls use the correct `strength`.
    tg, edges, radii, cells, src_to_tree, block_to_tree = MS.tree_metrics(
        T, src, BUDGET, grid=GRID, centers=CENTERS, radius=F.SRC_RADIUS_REAL,
        strength=strength)
    # Gate on block_to_tree (tree enters every chip footprint), not on
    # src_to_tree (every heated cell covered) -- the latter is never 0 on a
    # 17x17 footprint and would skip every case. See lattice_scan.run_case.
    if block_to_tree != 0:
        return {"case": f"{pname} | budget {BUDGET}",
                "skipped": f"tree misses a chip block, block_to_tree="
                           f"{block_to_tree} (src_to_tree={src_to_tree[0]})"}

    blocks = chip_blocks()

    def hot_in_block(group):
        """Hot-zone area (mm^2) inside each chip's 17x17 real-die block."""
        out = []
        for b in blocks:
            n = 0
            for (y, x) in b:
                if group.T[y, x] > group.hotspot_threshold:
                    n += 1
            out.append(n * V.PITCH_MM ** 2)
        return out

    tree_hot_blocks = hot_in_block(tg)
    out = {"case": f"{pname} | budget {BUDGET}",
           "powers": powers,
           "tree_pinned": tg.pinned_cells,
           "tree_T_max": round(tg.T_max, 4),
           "tree_T_mean": round(tg.T_mean_solid, 4),
           "tree_hotspot": round(tg.hotspot_area, 3),
           "tree_hot_per_chip": tree_hot_blocks,
           "src_to_tree": int(src_to_tree[0]),
           "lattice": []}
    for p in PITCHES:
        cells_l = lattice_cells(p)
        g = solve_lattice(T, src, cells_l, tg.total_area_mm2, strength)
        if g.pinned_cells < tg.pinned_cells:
            continue                     # cannot reach the target from below
        # trim to exactly the tree's pinned count
        cells_l, got, ok = _trim(T, src, cells_l, tg.pinned_cells,
                                 tg.total_area_mm2, strength, blocks)
        if not ok:
            continue
        g = solve_lattice(T, src, cells_l, tg.total_area_mm2, strength)
        out["lattice"].append({
            "pitch": p, "pinned": g.pinned_cells,
            "T_max": round(g.T_max, 4), "T_mean": round(g.T_mean_solid, 4),
            "hotspot": round(g.hotspot_area, 3),
            "hot_per_chip": hot_in_block(g),
        })
    good = out["lattice"]
    out["n_admissible"] = len(good)
    if good:
        bh = min(good, key=lambda d: d["hotspot"])
        bt = min(good, key=lambda d: d["T_max"])
        out["best_hotspot_pitch"] = bh["pitch"]
        out["best_Tmax_pitch"] = bt["pitch"]
        out["tree_minus_best_hotspot"] = round(tg.hotspot_area - bh["hotspot"], 3)
        out["tree_minus_best_Tmax"] = round(tg.T_max - bt["T_max"], 4)
        out["best_lat_hot_per_chip"] = bh["hot_per_chip"]
        out["hotspot_spread"] = round(max(d["hotspot"] for d in good)
                                      - min(d["hotspot"] for d in good), 3)
    return out


def _trim(T, src, cells, target, total_area_mm2, strength, blocks):
    """Delete individual cells (never inside a chip block) until the measured
    pinned count equals `target` exactly."""
    g = solve_lattice(T, src, cells, total_area_mm2, strength)
    protected = set().union(*blocks)
    order = []
    for y in sorted({yy for (yy, _) in cells}):
        order += [(y, x) for x in range(GRID - 1, -1, -1) if (y, x) in cells]
    for x in sorted({xx for (_, xx) in cells}):
        order += [(y, x) for y in range(GRID - 1, -1, -1)
                  if (y, x) in cells and (y, x) not in set(order)]
    for cell in order:
        if g.pinned_cells <= target:
            break
        if cell in protected:
            continue
        trial = cells - {cell}
        g2 = solve_lattice(T, src, trial, total_area_mm2, strength)
        if g2.pinned_cells < g.pinned_cells:
            cells, g = trial, g2
    return cells, g.pinned_cells, (g.pinned_cells == target)


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "0"
    if which == "merge":
        merge()
        return
    t0 = time.perf_counter()
    rows = []
    for pname, powers in CHUNKS[int(which)]:
        r = run_case(pname, powers)
        rows.append(r)
        if "skipped" in r:
            print(f"  {r['case']}: SKIPPED ({r['skipped']})")
            continue
        print(f"  {r['case']}: tree pin={r['tree_pinned']} T_max={r['tree_T_max']} "
              f"hot={r['tree_hotspot']} per-chip={r['tree_hot_per_chip']}")
        print(f"    admissible pitches: {[d['pitch'] for d in r['lattice']]}")
        if r["n_admissible"]:
            print(f"    best-hot p{r['best_hotspot_pitch']} "
                  f"tree-best={r['tree_minus_best_hotspot']:+.1f} "
                  f"bestTmax p{r['best_Tmax_pitch']} "
                  f"dTmax={r['tree_minus_best_Tmax']:+.4f} "
                  f"spread={r['hotspot_spread']:.1f}")
            print(f"    best lattice per-chip={r['best_lat_hot_per_chip']}")
    (PARTS / f"comb{which}.json").write_text(json.dumps(rows, indent=1),
                                             encoding="utf-8")
    print(f"[comb{which}] {len(rows)} cases in {time.perf_counter() - t0:.1f}s")


def merge():
    rows = []
    for k in sorted(CHUNKS):
        p = PARTS / f"comb{k}.json"
        if p.exists():
            rows += json.loads(p.read_text(encoding="utf-8"))
    live = [r for r in rows if "skipped" not in r]
    with open(OUT / "unequal_power_pitch_scan.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["case", "powers", "tree_pinned", "tree_T_max", "tree_T_mean",
                    "tree_hotspot", "pitch", "lat_pinned", "lat_T_max",
                    "lat_T_mean", "lat_hotspot", "dTmax", "dTmean", "dHotspot"])
        for r in live:
            for d in r["lattice"]:
                w.writerow([r["case"], "/".join(str(x) for x in r["powers"]),
                            r["tree_pinned"], r["tree_T_max"], r["tree_T_mean"],
                            r["tree_hotspot"], d["pitch"], d["pinned"],
                            d["T_max"], d["T_mean"], d["hotspot"],
                            round(d["T_max"] - r["tree_T_max"], 4),
                            round(d["T_mean"] - r["tree_T_mean"], 4),
                            round(d["hotspot"] - r["tree_hotspot"], 3)])
    (OUT / "unequal_power_pitch_summary.json").write_text(
        json.dumps({"grid": GRID, "pitches": PITCHES, "budget": BUDGET,
                    "layout": LAYOUT, "cases": live}, indent=2),
        encoding="utf-8")

    print(f"merged {len(live)} live cases")
    print(f"\n{'case':<24}{'pin':>6}{'#p':>4}{'bestHot':>9}{'tree-best':>11}"
          f"{'bestTmax':>9}{'dTmax':>9}{'spread':>8}")
    for r in live:
        if not r["n_admissible"]:
            print(f"{r['case']:<24}{r['tree_pinned']:>6}{0:>4}{'-':>9}"
                  f"{'-':>11}{'-':>9}{'-':>9}{'-':>8}")
            continue
        print(f"{r['case']:<24}{r['tree_pinned']:>6}{r['n_admissible']:>4}"
              f"p{r['best_hotspot_pitch']:<8}{r['tree_minus_best_hotspot']:+11.1f}"
              f"p{r['best_Tmax_pitch']:<8}{r['tree_minus_best_Tmax']:+9.4f}"
              f"{r['hotspot_spread']:>8.1f}")

    ok = [r for r in live if r["n_admissible"]]
    r8 = [r for r in ok if r["tree_minus_best_hotspot"] < -1.0]
    print(f"\nR8 (some admissible pitch beats the tree by >1 mm^2): "
          f"{len(r8)}/{len(ok)}")
    for r in r8:
        print(f"    {r['case']}: {r['tree_minus_best_hotspot']:+.1f} mm^2")

    print("\nR10: hot-zone concentration per chip (mm^2 in each 17x17 block)")
    for r in ok:
        print(f"    {r['case']:<24} tree={r['tree_hot_per_chip']} "
              f"best-lattice={r['best_lat_hot_per_chip']}")

    eq = next((r for r in ok if r["powers"] == [1.0, 1.0, 1.0]), None)
    print("\nR9: tree deficit vs the equal-power baseline")
    if eq:
        for r in ok:
            if r is eq:
                continue
            print(f"    {r['case']:<24} equal={eq['tree_minus_best_hotspot']:+.1f} "
                  f"this={r['tree_minus_best_hotspot']:+.1f} "
                  f"delta={r['tree_minus_best_hotspot'] - eq['tree_minus_best_hotspot']:+.1f}")


if __name__ == "__main__":
    main()
