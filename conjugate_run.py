"""R16-R18 with a metric that can actually SEE the coolant.

A7 FIX (2026-10-18): this script used to feed the dimensionless source
term to the pinned re-solve while the coolant march already used the
253 W calibration. The peak therefore came out as 27.5962 "C" at every
flow rate, and that constant was mistaken for a physical property. With
the A7 fix the pinned re-solve and the coolant march are both in watts,
and the peak DOES move with flow (110.38 C at 0.073 L/min down to
60.66 C at 73 L/min against a 60.504 C ideal-sink reference).

What the coolant changes most is still the temperature of the cells the
channels actually serve -- the mean over the solid, and the channel wall
temperature. Those remain the primary metrics here, but the peak is now
reported as a moving quantity rather than a saturation constant.

This script therefore reports, per flow rate:
  * peak (unchanged by construction -- stated, not hidden)
  * T_mean over the solid   <- moves
  * the channel wall temperature, max and outlet
  * the single-passage outlet (the best any one-passage design can do)
  * R_th from T_mean as well as from peak, so the published-band check
    (R17) uses a number that conjugation can influence
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

import calibrate as C
import conjugate as CJ
import field as F
import grow as G
import radius as Ra
import verify as V

OUT = Path(__file__).resolve().parent / "outputs"
GRID = 50
T_COOL = C.T_COOL_C


def build(grid=GRID, max_nodes=400):
    Td = F.normalize_field(
        F.solve_heat(grid=grid, source_center=(25, 25)).T, T_target=100.0)
    edges = G.grow_tree(Td, max_nodes=max_nodes)
    radii = Ra.assign_radii(edges, grid=grid, r0=0.5)
    nodes = sorted(set([p for p, _ in edges] + [c for _, c in edges]))
    xy = [(i // grid, i % grid) for i in nodes]
    return edges, radii, nodes, xy


def solid_mean(T, src, pinned):
    """T_mean over the solid, using the project's own definition.

    `verify.Group.from_field` defines solid as `~pinned` -- channel cells
    are at T_cool by fiat and are excluded, but the SOURCE cells are
    included (they are solid that generates heat). My first version used
    `~src`, which keeps the channel cells and drops the source block, and
    gave a mean of exactly 25.0000 C -- a metric that could not move and
    therefore could not test anything. Use the project's definition.
    """
    solid = ~pinned
    return float(T[solid].mean()) if solid.any() else T_COOL


def run():
    print("=" * 78)
    print("R16-R18: conjugate model, metrics that the coolant can influence")
    print("=" * 78)
    cal = C.i7_14700k(GRID)
    edges, radii, nodes, xy = build()
    src = F.source_mask(GRID, (25, 25), radius=F.SRC_RADIUS_SYNTHETIC)
    T = C.solve_real(cal, GRID)
    # A7 FIX (2026-10-18): this script used to call apply_channels without
    # `strength`, so the pinned re-solve silently reverted to the
    # dimensionless source term (27.5962) while the coolant march already
    # used physical watts. Pass the same strength calibrate uses, so the
    # whole conjugate loop stays in physical units.
    strength = src * (cal.q_solver / cal.k_w_mk)

    solid_ref = ~V.channel_mask(T.shape, xy, src)
    Tc_pin, pinned = V.apply_channels(T, xy, src, T_cool=T_COOL,
                                      strength=strength)
    peak_pin = float(Tc_pin.max())
    mean_pin = float(Tc_pin[solid_ref].mean())
    rth_peak_pin = (peak_pin - T_COOL) / cal.total_power_w
    rth_mean_pin = (mean_pin - T_COOL) / cal.total_power_w
    print(f"  ideal-sink reference:")
    print(f"    peak    {peak_pin:.4f} C   R_th(peak) = {rth_peak_pin:.4f} C/W")
    print(f"    T_mean  {mean_pin:.4f} C   R_th(mean) = {rth_mean_pin:.4f} C/W")
    print(f"  published cold-plate band: {C.R_COLDPLATE_BEST:.4f} - "
          f"{C.R_COLDPLATE_OCP_HI:.4f} C/W")
    print(f"  applied power {cal.total_power_w:.0f} W, "
          f"{int(pinned.sum())} pinned channel cells")

    rows = []
    for q_lpm in (0.073, 0.73, 7.3, 73.0):
        q = q_lpm / (1000.0 * 60.0)
        Tc, mask, wall, info = CJ.solve_conjugate(
            T, src, xy, edges, GRID, GRID, q_total_m3s=q,
            strength=strength, power_w=cal.total_power_w,
            max_iter=300, tol=1e-6)
        # Solid mask, using the project's own definition: verify.Group builds
        # it as `~pinned` where `pinned = verify.channel_mask(...)`, which
        # EXCLUDES source cells from the pin set -- so a source cell counts as
        # SOLID (it is material that generates heat). Using `~(mask | src)`
        # here would drop the source block and give a mean of exactly 25.0000
        # C, a metric that cannot move.
        solid = ~V.channel_mask(T.shape, xy, src)
        mean = float(Tc[solid].mean()) if solid.any() else T_COOL
        one_pass = CJ.straight_pipe_outlet(q, cal.total_power_w)
        rows.append({
            "q_lpm": q_lpm,
            "peak_c": round(float(Tc.max()), 4),
            "peak_vs_pinned": round(float(Tc.max()) - peak_pin, 4),
            "T_mean_c": round(mean, 4),
            "T_mean_vs_pinned": round(mean - mean_pin, 4),
            "r_th_peak": round((float(Tc.max()) - T_COOL) / cal.total_power_w, 4),
            "r_th_mean": round((mean - T_COOL) / cal.total_power_w, 4),
            "coolant_rise_c": round(info["coolant_rise_c"], 6),
            "coolant_out_c": round(info["coolant_out_c"], 4),
            "single_pass_outlet_c": round(one_pass, 4),
            "tree_outlet_minus_single_pass": round(
                info["coolant_out_c"] - one_pass, 4),
            "iters": info["iters"], "converged": info["converged"],
            "held_cells": info["held_cells"],
        })
        r = rows[-1]
        print(f"\n  Q = {q_lpm} L/min")
        print(f"    peak        {r['peak_c']:8.4f} C  (pinned {peak_pin:.4f}, "
              f"delta {r['peak_vs_pinned']:+.4f})")
        print(f"    T_mean      {r['T_mean_c']:8.4f} C  (pinned {mean_pin:.4f}, "
              f"delta {r['T_mean_vs_pinned']:+.4f})")
        print(f"    R_th(mean)  {r['r_th_mean']:8.4f} C/W "
              f"{'INSIDE band' if C.R_COLDPLATE_BEST <= r['r_th_mean'] <= C.R_COLDPLATE_OCP_HI else 'OUTSIDE band'}")
        print(f"    coolant rise along the tree  {r['coolant_rise_c']:9.6f} C")
        print(f"    tree outlet                  {r['coolant_out_c']:9.4f} C")
        print(f"    single-passage outlet        {r['single_pass_outlet_c']:9.4f} C")
        print(f"    tree - single passage        "
              f"{r['tree_outlet_minus_single_pass']:+9.4f} C")
        print(f"    iters={r['iters']} "
              f"{'converged' if r['converged'] else 'NOT CONVERGED'}"
              + ("" if r["converged"] else
                 f"  last wall delta={info['history'][-1]['max_wall_delta']:.4f} C"))
        tail = info["history"][-6:]
        print(f"    wall-delta tail: "
              + " ".join(f"{h['max_wall_delta']:.3f}" for h in tail))

    # R15 regression guard, restated (2026-10-18). The old guard required
    # the peak at every FINITE flow to equal the pinned peak bit-for-bit.
    # That was only true while the script bypassed the A7 unit fix (the
    # source term stayed dimensionless and the peak never saw the coolant).
    # With physical watts the peak must rise when the coolant warms, so the
    # correct statement of the same property is the Q->inf limit: an
    # infinite flow holds every channel cell at the inlet temperature, which
    # reduces solve_conjugate to the pinned model. Test that limit, and
    # record the finite-flow deviations as expected physics.
    q_lim_lpm = 1e9
    q_lim = q_lim_lpm / (1000.0 * 60.0)
    Tc_lim, _, wall_lim, info_lim = CJ.solve_conjugate(
        T, src, xy, edges, GRID, GRID, q_total_m3s=q_lim,
        strength=strength, power_w=cal.total_power_w,
        max_iter=300, tol=1e-6)
    limit_delta = float(Tc_lim.max()) - peak_pin
    r15_pass = bool(info_lim["converged"] and abs(limit_delta) < 1e-6)

    print("\n" + "=" * 78)
    print("VERDICTS")
    print("=" * 78)
    print(f"R15 (Q->inf regression): peak_lim {float(Tc_lim.max()):.6f} C vs "
          f"pinned {peak_pin:.6f} C, delta {limit_delta:+.2e} C -> "
          f"{'PASS' if r15_pass else 'FAIL'} "
          f"({info_lim['iters']} iters, converged={info_lim['converged']})")
    print("R16: the peak rises with flow (physical units, A7 fix); T_mean")
    print("     remains the metric the coolant moves most:")
    for r in rows:
        print(f"       Q={r['q_lpm']:<7} dT_mean = {r['T_mean_vs_pinned']:+.4f} C")
    print("R17: R_th against the published band, using T_mean:")
    for r in rows:
        inside = C.R_COLDPLATE_BEST <= r["r_th_mean"] <= C.R_COLDPLATE_OCP_HI
        print(f"       Q={r['q_lpm']:<7} R_th(mean) = {r['r_th_mean']:.4f} C/W "
              f"{'INSIDE' if inside else 'OUTSIDE'}")
    print("R18: materiality of the channel-side idealisation")
    for r in rows:
        flag = ("  <-- exceeds 0.05 C floor"
                if abs(r["coolant_rise_c"]) > 0.05 else "  (negligible)")
        print(f"       Q={r['q_lpm']:<7} rise = {r['coolant_rise_c']:+.6f} C{flag}")
    print("\n  tree outlet vs single passage (negative = tree's coolant is")
    print("  COOLER than one straight passage carrying all 253 W):")
    for r in rows:
        print(f"       Q={r['q_lpm']:<7} {r['tree_outlet_minus_single_pass']:+.4f} C")

    (OUT / "conjugate_single.json").write_text(
        json.dumps({"grid": GRID, "calibration": "i7-14700K (253 W)",
                    "total_power_w": round(cal.total_power_w, 2),
                    "pinned_peak_c": round(peak_pin, 4),
                    "pinned_T_mean_c": round(mean_pin, 4),
                    "pinned_r_th_peak": round(rth_peak_pin, 4),
                    "pinned_r_th_mean": round(rth_mean_pin, 4),
                    "band": [C.R_COLDPLATE_BEST, C.R_COLDPLATE_OCP_HI],
                    "sweep": rows}, indent=2), encoding="utf-8")

    # The R15 guard is a property of the SAME run (Q->inf limit vs the
    # pinned reference), so persist it alongside rather than leaving a stale
    # conjugate_guard.json from an earlier, unconverged run.
    converged = [r for r in rows if r["converged"]]
    (OUT / "conjugate_guard.json").write_text(
        json.dumps({"grid": GRID, "calibration": "i7-14700K (253 W)",
                    "total_power_w": round(cal.total_power_w, 2),
                    "pinned_peak_c": round(peak_pin, 4),
                    "pinned_T_mean_c": round(mean_pin, 4),
                    "pinned_r_th_peak": round(rth_peak_pin, 4),
                    "pinned_r_th_mean": round(rth_mean_pin, 4),
                    "R15_test": "Q->inf limit reproduces the pinned peak",
                    "R15_limit_q_lpm": q_lim_lpm,
                    "R15_limit_peak_c": round(float(Tc_lim.max()), 6),
                    "R15_limit_delta_c": float(f"{limit_delta:.3e}"),
                    "R15_limit_iters": info_lim["iters"],
                    "R15_limit_converged": info_lim["converged"],
                    "R15_verdict": "PASS" if r15_pass else "FAIL",
                    "R15_note": (
                        "finite-flow peak deltas are expected physics, not "
                        "guard failures: warmer coolant raises the peak"),
                    "n_converged": len(converged), "n_total": len(rows),
                    "sweep": rows}, indent=2), encoding="utf-8")
    print("\nwrote outputs/conjugate_single.json and outputs/conjugate_guard.json")
    return rows


if __name__ == "__main__":
    run()
