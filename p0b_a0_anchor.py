"""A0 anchor check for P0b protocol v4 (pre-registered, DEFECT_REMEDIATION_PLAN.md §10.10).

Prints, for the SAME tree that §6.3 reports:
  1. material area (measured, not assumed)
  2. dp_tree from calibrate.tree_dp_pa  (the authoritative entry point)
  3. dp_ctrl built exactly as calibrate.py:322-323
  4. the §6.3 published values, for comparison

PASS criterion (pre-registered): the SERIAL reference (the historical
definition) must reproduce the 6.42 kPa order of magnitude, and the
measured material area must be printed so the 651.46 vs 954.51 question
is settled by measurement, not by record.

§10.12 note: the physical dp reported by `tree_dp_pa` is now the
demand-driven (convention A) path drop, 0.0802 kPa. The A0 gate is still
judged on the serial reproduction, because that is what A0 was written to
verify; reproducing it does NOT validate the definition (that is §10.11).
"""
from __future__ import annotations

import numpy as np

import calibrate as C
import grow as G
import radius as Ra
import verify as V
from field import solve_heat_sources, normalize_field, SRC_RADIUS_SYNTHETIC

GRID = 50


def main() -> None:
    cal = C.i7_14700k(GRID)

    # --- the tree, grown exactly as calibrate.report() grows it -------------
    Td = normalize_field(
        solve_heat_sources(grid=GRID, centers=[(25, 25)],
                           source_radius=SRC_RADIUS_SYNTHETIC).T,
        T_target=100.0)
    edges = G.grow_tree(Td, max_nodes=400)
    radii = Ra.assign_radii(edges, grid=GRID, r0=0.5)

    cells = set([p for p, _ in edges] + [c for _, c in edges])
    n_seg = len(edges)
    n_cells = len(cells)

    # --- measured material area (NOT a preset constant) --------------------
    mat_mm2 = V.tree_material_mm2(edges, radii)

    # --- authoritative real-unit dp ----------------------------------------
    grid_mm = C.paper_grid_mm(GRID)
    q = C.coolant_flow_m3s(cal.total_power_w)
    dp_tree = C.tree_dp_pa(edges, radii, GRID, grid_mm, q)

    # --- control, built EXACTLY as calibrate.py:322-323 --------------------
    r_ctrl = float(np.sqrt(mat_mm2 / (n_cells * np.pi)))
    dp_ctrl = (8.0 * C.MU_WATER * (cal.plate_mm * C.SI) * (q / n_cells)
               / (np.pi * (r_ctrl * C.SI) ** 4))

    print("=" * 72)
    print("P0b v4 -- A0 ANCHOR CHECK")
    print("=" * 72)
    print(f"tree                 {n_seg} segments, {n_cells} cells")
    print(f"grid_mm (authority)  {grid_mm:.4f}   <- calibrate.paper_grid_mm()")
    print(f"field.PITCH_MM       {V.PITCH_MM:.4f}   <- dimensionless, NOT used here")
    print(f"flow                 {C.C_flow(q)}")
    print()
    print(f"measured material    {mat_mm2:10.4f} mm^2")
    print(f"  vs §6.3 table      {651.461:10.4f} mm^2   (published table value)")
    print(f"  vs §10.9 record    {954.51:10.4f} mm^2   (v3 anchor record)")
    print()
    print(f"dp_tree (network)    {dp_tree['dp_pa']/1000:10.4f} kPa")
    print(f"dp_ctrl (equal mat)  {dp_ctrl/1000:10.5f} kPa")
    print(f"ratio                {dp_tree['dp_pa']/dp_ctrl:10.0f} x")
    print(f"  network (convention A): {dp_tree['n_leaves']} leaves, "
          f"{dp_tree['n_forks']} true forks, depth {dp_tree['max_depth']}, "
          f"path spread {dp_tree['path_spread_x']:.3f}x")
    print(f"  Kirchhoff reference (B, leaves shorted)  "
          f"{dp_tree['dp_kirchhoff_reference_pa']/1000:10.4f} kPa  "
          f"{dp_tree['kirchhoff_over_demand_x']:.2f}x A, self-check "
          f"{dp_tree['kirchhoff_self_check_rel']:.1e}")
    print(f"  serial reference (pre-§10.11, WRONG)  "
          f"{dp_tree['dp_serial_reference_pa']/1000:10.4f} kPa  "
          f"over-count {dp_tree['overcount_serial_x']:.0f}x A")
    print()
    print(f"§6.3 published tree  {6.42:10.2f} kPa   <- SERIAL definition")
    print(f"§6.3 published ctrl  {0.01294:10.5f} kPa")
    print(f"§10.9 v3 anchor      {7.8189:10.4f} kPa")
    print()
    # --- pre-registered verdict -------------------------------------------
    ok = 5.0 <= dp_tree['dp_serial_reference_pa'] / 1000 <= 8.0
    print(f"A0 VERDICT: {'PASS' if ok else 'FAIL'} "
          f"(serial dp = {dp_tree['dp_serial_reference_pa']/1000:.2f} kPa, "
          f"target 6.42 kPa order)")
    print("  NOTE (§10.11/§10.12): the 6.42 kPa anchor reproduces, but the")
    print("  SERIAL definition it rests on is WRONG -- the tree is a branching")
    print(f"  network, so the physical dp is "
          f"{dp_tree['dp_pa']/1000:.4f} kPa under convention A "
          f"({dp_tree['overcount_serial_x']:.0f}x lower).")
    print("  The 94.6x figure previously recorded was D1/D3 (serial over the")
    print("  Kirchhoff reference, D3 = 0.0679 kPa); D1/A = 80x because A and")
    print("  B are themselves 0.85x apart, not 51.6x.")
    print(f"  material record gap: measured {mat_mm2:.2f} vs §6.3 table "
          f"{651.461:.2f} = {mat_mm2/651.461:.2f}x")
    print(f"  material record gap: measured {mat_mm2:.2f} vs §10.9 record "
          f"{954.51:.2f} = {mat_mm2/954.51:.2f}x")


if __name__ == "__main__":
    main()
