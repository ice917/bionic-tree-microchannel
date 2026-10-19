"""Multi-source + real-scale flow-thermal coupling (REPORT §13 item 14).

WHY THIS IS A DIFFERENT EXPERIMENT FROM §21
-------------------------------------------
§21's single-source run had a structural defect, found by the architecture
audit: `cal.q_w = total/25` put all 253 W into 25 cells (a 4.5 x 4.5 mm
block), i.e. 1249 W/cm^2. The real i7-14700K is 253 W over a 257 mm^2 die
(TechPowerUp), i.e. 98 W/cm^2 -- the model is a 12.7x power-density
amplifier. Two consequences:

  * only 25 of 2500 cells were above 25.001 C (1.0% of the plate), and
    571 cells were pinned at exactly 25.0 by construction, so T_mean and
    R_th could not move and R17 was meaningless;
  * the source block area equalled the reported "hotspot area" exactly
    (ratio 1.000), so "the topology shrinks the hotspot" was measuring the
    chip, not the topology.

So this script spreads each chip's power over the whole die footprint
(source_radius = 8 cells -> 17 x 17 cells = 14.6 x 14.6 mm, 213 mm^2) and
keeps the per-die power at 253 W, giving 119 W/cm^2 -- within 20% of the
real 98 W/cm^2. That is the "real scale" in the title.

It then runs the CONJUGATE (flow-thermal) model on the multi-source tree,
which §21 never did.

PRE-REGISTERED
--------------
  R20  With a realistically spread source, what fraction of the plate is
       thermally active?  -> must be far above the 1.0% of §21. If it is
       not, the spread did not fix the problem and the audit's diagnosis
       was wrong.
  R21  Does R_th become measurable and land in the OCP-measured band
       0.014 - 0.019 C/W (Open Compute Project, PG25, 1.5-3.5 LPM)?
  R22  Does the multi-source tree need even MORE flow than the
       single-source tree's 61x split?  More leaves and longer paths
       should make it worse.
  R23  Is the tree's coolant outlet temperature lower than a single
       straight passage's? (§21 said yes, by 4.16 C -- check that it holds
       here too, and quantify the flow cost.)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import calibrate as C
import conjugate as CJ
import field as F
import grow as G
import multi_source as MS
import radius as Ra
import verify as V

OUT = Path(__file__).resolve().parent / "outputs"
GRID = 50
T_COOL = C.T_COOL_C

# Real-scale source: 17x17 cells at 0.9 mm = 14.6 x 14.6 mm = 213 mm^2.
# 253 W over 213 mm^2 = 119 W/cm^2, within 20% of the i7-14700K's 98 W/cm^2.
SRC_RADIUS = 8.0
N_DIES = 3
DIE_POWER_W = 253.0


def build(grid=GRID, max_nodes=800):
    """Multi-source tree over the 3-chip triangle, real-scale sources."""
    centers = MS.LAYOUTS["3 chips, triangle"]
    Td = F.normalize_field(
        F.solve_heat_sources(grid=grid, centers=centers,
                             source_radius=SRC_RADIUS).T, T_target=100.0)
    edges = G.grow_tree(Td, max_nodes=max_nodes)
    radii = Ra.assign_radii(edges, grid=grid, r0=0.5)
    nodes = sorted(set([p for p, _ in edges] + [c for _, c in edges]))
    xy = [(i // grid, i % grid) for i in nodes]
    return centers, edges, radii, nodes, xy


def stats(Tc, solid):
    hot = int((Tc > 25.001).sum())
    return {
        "peak_c": round(float(Tc.max()), 4),
        "T_mean_c": round(float(Tc[solid].mean()), 4),
        "active_cells": hot,
        "active_pct": round(100.0 * hot / Tc.size, 2),
        "pinned_at_25": int((np.abs(Tc - 25.0) < 1e-9).sum()),
    }


def run():
    print("=" * 78)
    print("MULTI-SOURCE + REAL-SCALE CONJUGATE COUPLING")
    print("=" * 78)
    cal = C.i7_14700k(GRID)
    centers, edges, radii, nodes, xy = build()
    src = F.source_mask_multi(GRID, centers, radius=SRC_RADIUS)
    # A7 FIX (2026-10-18): C.solve_real applies cal.q_solver = 253 W / 25
    # cells to EVERY source cell. With the real-scale footprint (867 cells)
    # that is 8774 W, not 759 W -- 11.6x the stated power. Build the field
    # and the pinned re-solve from the per-cell power that actually gives
    # 253 W per die, and pass the same strength to the conjugate loop.
    n_cells_per_die = (2 * SRC_RADIUS + 1) ** 2
    q_vol = (DIE_POWER_W / n_cells_per_die) / (cal.t_mm * C.SI)
    strength = src * (q_vol / cal.k_w_mk)
    T = F.solve_heat_sources(grid=GRID, centers=centers,
                             source_radius=SRC_RADIUS,
                             q=q_vol, k=cal.k_w_mk).T
    solid = ~V.channel_mask(T.shape, xy, src)

    total_power = DIE_POWER_W * N_DIES
    print(f"  dies: {N_DIES} x {DIE_POWER_W:.0f} W = {total_power:.0f} W")
    print(f"  source radius: {SRC_RADIUS:.0f} cells = {2*SRC_RADIUS:.0f} mm -> "
          f"{(2*SRC_RADIUS+1)**2 * cal.grid_mm**2:.0f} mm^2 per die")
    print(f"  power density: "
          f"{DIE_POWER_W/((2*SRC_RADIUS+1)**2*cal.grid_mm**2/100.0):.0f} W/cm^2"
          f"  (real i7-14700K: 98 W/cm^2)")
    print(f"  source cells: {int(src.sum())} of {GRID*GRID} "
          f"({100.0*int(src.sum())/GRID**2:.1f}% of the plate)")

    Tc_pin, pinned = V.apply_channels(T, xy, src, T_cool=T_COOL,
                                      strength=strength)
    sp = stats(Tc_pin, solid)
    print(f"\n  ideal-sink reference:")
    print(f"    peak {sp['peak_c']} C, T_mean {sp['T_mean_c']} C")
    print(f"    R_th(peak) {(sp['peak_c']-T_COOL)/total_power:.4f} C/W, "
          f"R_th(mean) {(sp['T_mean_c']-T_COOL)/total_power:.4f} C/W")
    print(f"    thermally active: {sp['active_cells']} cells "
          f"({sp['active_pct']}% of the plate)")
    print(f"    pinned at exactly 25.0: {sp['pinned_at_25']}")

    print(f"\n  R20 verdict: active fraction {sp['active_pct']}% "
          f"vs §21's 1.0% "
          f"-> {'FIXED' if sp['active_pct'] > 5 else 'STILL BROKEN'}")

    rows = []
    for q_lpm in (0.73, 1.8, 3.6, 7.2, 14.4):
        q = q_lpm / (1000.0 * 60.0)
        Tc, mask, wall, info = CJ.solve_conjugate(
            T, src, xy, edges, GRID, GRID, q_total_m3s=q,
            strength=strength, power_w=total_power,
            max_iter=400, tol=1e-6)
        st = stats(Tc, solid)
        one_pass = T_COOL + total_power / (C.RHO_WATER * C.CP_WATER * q)
        r = {
            "q_lpm": q_lpm,
            "peak_c": st["peak_c"],
            "peak_vs_pinned": round(st["peak_c"] - sp["peak_c"], 4),
            "T_mean_c": st["T_mean_c"],
            "T_mean_vs_pinned": round(st["T_mean_c"] - sp["T_mean_c"], 4),
            "r_th_peak": round((st["peak_c"] - T_COOL) / total_power, 4),
            "r_th_mean": round((st["T_mean_c"] - T_COOL) / total_power, 4),
            "active_cells": st["active_cells"],
            "active_pct": st["active_pct"],
            "coolant_rise_c": round(info["coolant_rise_c"], 6),
            "coolant_out_c": round(info["coolant_out_c"], 4),
            "single_pass_outlet_c": round(one_pass, 4),
            "tree_minus_single_pass": round(info["coolant_out_c"] - one_pass, 4),
            "iters": info["iters"], "converged": info["converged"],
            "held_cells": info["held_cells"],
        }
        rows.append(r)
        print(f"\n  Q = {q_lpm} L/min")
        print(f"    peak   {r['peak_c']:8.4f} C  (pinned {sp['peak_c']}, "
              f"delta {r['peak_vs_pinned']:+.4f})")
        print(f"    T_mean {r['T_mean_c']:8.4f} C  (pinned {sp['T_mean_c']}, "
              f"delta {r['T_mean_vs_pinned']:+.4f})")
        print(f"    R_th(peak) {r['r_th_peak']:.4f}  R_th(mean) "
              f"{r['r_th_mean']:.4f} C/W")
        print(f"    active cells {r['active_cells']} ({r['active_pct']}%)")
        print(f"    coolant rise {r['coolant_rise_c']:.6f} C, "
              f"outlet {r['coolant_out_c']:.4f} C")
        print(f"    single-pass outlet {r['single_pass_outlet_c']:.4f} C  "
              f"(tree - single {r['tree_minus_single_pass']:+.4f} C)")
        print(f"    iters={r['iters']} "
              f"{'converged' if r['converged'] else 'NOT CONVERGED'}")

    print("\n" + "=" * 78)
    print("VERDICTS")
    print("=" * 78)
    print(f"R20: thermally active = {sp['active_pct']}% of the plate "
          f"(§21 single-source: 1.0%)")
    print(f"R21: R_th(peak) = {rows[-1]['r_th_peak']:.4f} C/W at "
          f"Q={rows[-1]['q_lpm']} L/min")
    print("     OCP-measured cold-plate band (case-to-inlet, PG25, "
          "1.5-3.5 LPM): 0.014 - 0.019 C/W")
    print("R22/R23: coolant rise and outlet vs a single passage:")
    for r in rows:
        print(f"     Q={r['q_lpm']:<7} rise={r['coolant_rise_c']:+9.6f} C  "
              f"outlet-single={r['tree_minus_single_pass']:+8.4f} C  "
              f"{'conv' if r['converged'] else 'NOT CONV'}")

    # how many leaves does the multi-source tree have?
    children, parent, depth, root = Ra.build_tree(edges)
    n_leaves = sum(1 for n in parent if n not in children)
    shares = CJ.flow_shares(edges)
    leaf_share_sum = sum(shares[n] for n in parent if n not in children)
    print(f"\n  multi-source tree: {len(edges)} edges, {n_leaves} leaves "
          f"(single-source tree had 61)")
    print(f"  sum of leaf shares: {leaf_share_sum:.9f} (must be 1.0)")
    print(f"  smallest leaf share: {min(shares.values()):.6f} "
          f"(single-source: {1/61:.6f})")
    if n_leaves:
        print(f"  => worst-case branch carries {1.0/n_leaves:.6f} of the flow")

    (OUT / "conjugate_multi_real.json").write_text(
        json.dumps({
            "grid": GRID, "source_radius_cells": SRC_RADIUS,
            "n_dies": N_DIES, "die_power_w": DIE_POWER_W,
            "total_power_w": total_power,
            "die_area_mm2": round((2*SRC_RADIUS+1)**2 * cal.grid_mm**2, 1),
            "power_density_w_cm2": round(
                DIE_POWER_W / ((2*SRC_RADIUS+1)**2*cal.grid_mm**2/100.0), 1),
            "real_i7_power_density_w_cm2": 98.0,
            "n_leaves": n_leaves,
            "leaf_share_sum": round(leaf_share_sum, 9),
            "pinned_peak_c": sp["peak_c"], "pinned_T_mean_c": sp["T_mean_c"],
            "pinned_active_pct": sp["active_pct"],
            "ocp_band_c_per_w": [0.014, 0.019],
            "sweep": rows}, indent=2), encoding="utf-8")
    print("\nwrote outputs/conjugate_multi_real.json")
    return rows


if __name__ == "__main__":
    run()
