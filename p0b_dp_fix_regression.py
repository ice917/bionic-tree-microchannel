"""Regression check for the §10.11/§10.12 dp fix.

Convention A (demand-driven, the project standard) is checked twice:
  (1) `verify.poiseuille_dp` (toy board) must equal an independent
      explicit root-to-leaf chain walk with q_edge = subtree demand;
  (2) `calibrate.tree_dp_pa` (real units) must equal the same walk at
      the real pitch and flow rate.
Convention B (Kirchhoff, leaves shorted onto one manifold) is checked as
a REFERENCE only:
  (3) `dp_kirchhoff_reference_pa == Q * R_sub(root)` and every path drop
      is identical -- that is what "all leaves at one pressure" means, so
      a spread != 1 would mean the reference solve is broken.
The serial value is checked too, because it is the historical 6.42 kPa
that the paper quotes; it must stay reproducible even though it is wrong.
"""
from __future__ import annotations

import numpy as np

import calibrate as C
import grow as G
import radius as Ra
import verify as V
from field import SRC_RADIUS_SYNTHETIC, normalize_field, solve_heat_sources
from radius import build_tree, node_flows


def main() -> None:
    Td = normalize_field(
        solve_heat_sources(grid=50, centers=[(25, 25)],
                           source_radius=SRC_RADIUS_SYNTHETIC).T,
        T_target=100.0)
    edges = G.grow_tree(Td, max_nodes=400)
    radii = Ra.assign_radii(edges, grid=50, r0=0.5)

    ch, pa, de, root = build_tree(edges)
    nodes = set(pa) | set(pa.values()) | {root}
    leaves = [v for v in nodes if not ch.get(v)]
    demand = node_flows(edges)
    total = demand[root]

    # ---- 1. toy board, convention A: engine vs explicit chain walk ------
    net = V.poiseuille_dp(edges, radii, 50)
    ser = V.poiseuille_dp(edges, radii, 50, as_network=False)

    def R(p, c):
        return 8.0 * V.MU * 1.0 / (np.pi * min(radii[p], radii[c]) ** 4)

    # edge (pa[v], v) carries exactly the demand of subtree v
    qd = {v: demand[v] / total for v in nodes}

    def drop_a(l):
        d, v = 0.0, l
        while v != root:
            d += R(pa[v], v) * qd[v]
            v = pa[v]
        return d

    path = max(drop_a(l) for l in leaves)
    print(f"toy board   network(A) = {net:.6f}   "
          f"explicit chain = {path:.6f}   "
          f"rel = {abs(path - net) / net:.2e}")
    print(f"            serial = {ser:.6f}   overcount = {ser/net:.1f}x")
    ok = abs(path - net) / net < 1e-12
    print(f"REGRESSION: {'PASS' if ok else 'FAIL'} "
          "(verify.poiseuille_dp A == explicit demand-driven chain walk)")

    # ---- 2. real units, convention A ----------------------------------
    grid_mm = C.paper_grid_mm(50)
    q_tot = C.coolant_flow_m3s(253.0)
    d_real = C.tree_dp_pa(edges, radii, 50, grid_mm, q_tot)

    def r_si(p, c):
        r = min(radii[p], radii[c]) * C.SI
        return 8.0 * C.MU_WATER * (grid_mm * C.SI) / (np.pi * r ** 4)

    q_si = {v: q_tot * demand[v] / total for v in nodes}

    def drop_si(l):
        d, v = 0.0, l
        while v != root:
            d += r_si(pa[v], v) * q_si[v]
            v = pa[v]
        return d

    hand = max(drop_si(l) for l in leaves)
    rel = abs(d_real["dp_pa"] - hand) / d_real["dp_pa"]
    print(f"real-unit   calibrate(A) = {d_real['dp_pa']/1000:.6f} kPa   "
          f"explicit chain = {hand/1000:.6f} kPa   rel = {rel:.2e}")
    ok2 = rel < 1e-12
    print(f"REGRESSION: {'PASS' if ok2 else 'FAIL'} "
          "(calibrate.tree_dp_pa A == explicit demand-driven chain walk)")

    # ---- 3. convention B reference: self-consistency --------------------
    rs = {}
    for v in sorted(nodes, key=lambda i: -de[i]):
        c = ch.get(v)
        rs[v] = 0.0 if not c else 1.0 / sum(
            1.0 / (r_si(v, x) + rs[x]) for x in c)
    qk = {root: q_tot}
    st = [root]
    while st:
        v = st.pop()
        for x in ch.get(v, []):
            inv = {y: 1.0 / (r_si(v, y) + rs[y]) for y in ch[v]}
            qk[x] = qk[v] * inv[x] / sum(inv.values())
            st.append(x)

    def drop_b(l):
        d, v = 0.0, l
        while v != root:
            d += r_si(pa[v], v) * qk[v]
            v = pa[v]
        return d

    db = [drop_b(l) for l in leaves]
    spread_b = max(db) / min(db)
    rel_b = abs(max(db) - q_tot * rs[root]) / d_real["dp_kirchhoff_reference_pa"]
    print(f"reference   Q*Rsub = {q_tot*rs[root]/1000:.6f} kPa   "
          f"calibrate B = {d_real['dp_kirchhoff_reference_pa']/1000:.6f} kPa   "
          f"rel = {rel_b:.2e}   path spread = {spread_b:.9f}x")
    ok3 = rel_b < 1e-12 and spread_b < 1 + 1e-9
    print(f"REGRESSION: {'PASS' if ok3 else 'FAIL'} "
          "(Kirchhoff reference: Q*Rsub and uniform path drop)")

    print(f"serial reference = {d_real['dp_serial_reference_pa']/1000:.4f} kPa "
          f"(historical 6.42 kPa), overcount {d_real['overcount_serial_x']:.1f}x A")
    print(f"  decomposition: series structure "
          f"{d_real['series_factor_x']:.1f}x x parent charging "
          f"{d_real['parent_charge_factor_x']:.2f}x")
    print(f"  A path spread = {d_real['path_spread_x']:.4f}x, "
          f"B/A = {d_real['kirchhoff_over_demand_x']:.4f}")


if __name__ == "__main__":
    main()
