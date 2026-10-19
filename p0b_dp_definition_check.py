"""Diagnostic: is the historical tree dp measuring the tree's actual dp?

The tree is a SINGLE-inlet / 61-outlet branching network (root =
edges[0][0], leaves = nodes with no children). For such a network the
pressure drop between the inlet and the outlets is the drop along ONE
root-to-leaf path, NOT the sum over all 399 edges.

  D1  sum over all edges (the pre-§10.11 definition; historical 6.42 kPa)
  D2  max path drop under the physical Kirchhoff split  (convention B)
  D3  Q_total * R_sub(root), the network solution of B
  DA  max path drop under equal-leaf demand (convention A, ADOPTED, §10.12)

D2 and D3 must agree: with all leaves shorted onto one manifold, Kirchhoff
forces every root-to-leaf path to the same drop, so a mismatch means the
solve is broken. DA is a different question (each leaf delivers its design
load) and need NOT equal D2/D3; see DEFECT_REMEDIATION_PLAN.md §10.12.
"""
from __future__ import annotations

from collections import deque

import numpy as np

import calibrate as C
import grow as G
import radius as Ra
import verify as V
from field import solve_heat_sources, normalize_field, SRC_RADIUS_SYNTHETIC
from radius import build_tree, node_flows

GRID = 50


def main() -> None:
    cal = C.i7_14700k(GRID)
    Td = normalize_field(
        solve_heat_sources(grid=GRID, centers=[(25, 25)],
                           source_radius=SRC_RADIUS_SYNTHETIC).T,
        T_target=100.0)
    edges = G.grow_tree(Td, max_nodes=400)
    radii = Ra.assign_radii(edges, grid=GRID, r0=0.5)
    children, parent, depth, root = build_tree(edges)
    nodes = set(parent) | set(parent.values()) | {root}
    leaves = [v for v in nodes if not children.get(v)]
    forks = [v for v in nodes if len(children.get(v, [])) >= 2]

    grid_mm = C.paper_grid_mm(GRID)
    q = C.coolant_flow_m3s(cal.total_power_w)
    h_m = grid_mm * C.SI
    mu = C.MU_WATER

    # ---- D1: the authoritative entry point --------------------------------
    res = C.tree_dp_pa(edges, radii, GRID, grid_mm, q)
    D1 = res["dp_serial_reference_pa"]
    DA = res["dp_pa"]

    # ---- network solve ----------------------------------------------------
    def R_edge(p: int, c: int) -> float:
        """Resistance of one edge, matching tree_dp_pa's min() convention."""
        r = min(radii[p], radii[c]) * C.SI
        return 8.0 * mu * h_m / (np.pi * r ** 4)

    # bottom-up subtree resistance (leaves sit on the common outlet manifold)
    Rsub: dict[int, float] = {}
    for v in sorted(nodes, key=lambda i: -depth[i]):
        ch = children.get(v)
        if not ch:
            Rsub[v] = 0.0
        else:
            Rsub[v] = 1.0 / sum(1.0 / (R_edge(v, c) + Rsub[c]) for c in ch)

    # top-down physical flow split
    Q: dict[int, float] = {root: q}
    Qe: dict[tuple[int, int], float] = {}
    dq = deque([root])
    while dq:
        v = dq.popleft()
        ch = children.get(v)
        if not ch:
            continue
        inv = {c: 1.0 / (R_edge(v, c) + Rsub[c]) for c in ch}
        tot = sum(inv.values())
        for c in ch:
            Q[c] = Q[v] * inv[c] / tot
            Qe[(v, c)] = Q[c]
            dq.append(c)

    D3 = q * Rsub[root]

    # max root-to-leaf path drop under the PHYSICAL split
    def path_dp(v: int) -> float:
        ch = children.get(v)
        if not ch:
            return 0.0
        return max(R_edge(v, c) * Qe[(v, c)] + path_dp(c) for c in ch)

    D2 = path_dp(root)

    # ---- control, built exactly as calibrate.py:322-323 -------------------
    n_cells = len(nodes)
    mat_mm2 = V.tree_material_mm2(edges, radii)
    r_ctrl = float(np.sqrt(mat_mm2 / (n_cells * np.pi)))
    dp_ctrl = (8.0 * mu * (cal.plate_mm * C.SI) * (q / n_cells)
               / (np.pi * (r_ctrl * C.SI) ** 4))

    # ---- equal-leaf-flow path drop (the node_flows convention) ------------
    flow = node_flows(edges)
    tot_flow = max(flow.values())

    def path_dp_uniform(v: int) -> float:
        ch = children.get(v)
        if not ch:
            return 0.0
        return max(R_edge(v, c) * (q * flow[c] / tot_flow) + path_dp_uniform(c)
                   for c in ch)

    D2u = path_dp_uniform(root)

    print("=" * 74)
    print("dp DEFINITION CHECK -- is tree_dp_pa measuring the tree's dp?")
    print("=" * 74)
    print(f"tree              {len(edges)} edges, {len(nodes)} nodes, "
          f"{len(leaves)} leaves, {len(forks)} forks (>=2 children)")
    print(f"max depth         {max(depth.values())}")
    print(f"flow              {C.C_flow(q)}   grid_mm {grid_mm:.4f}")
    print(f"material          {mat_mm2:.4f} mm^2")
    print()
    print(f"DA  max path, equal-leaf demand  ADOPTED {DA/1000:10.5f} kPa")
    print(f"D1  sum over ALL edges (historical)      {D1/1000:10.4f} kPa")
    print(f"D2  max path, Kirchhoff split (B ref)    {D2/1000:10.5f} kPa")
    print(f"D3  Q_total * R_sub(root)  (B ref)       {D3/1000:10.5f} kPa")
    print()
    print(f"A cross-check  |DA-D2u|/DA              {abs(DA-D2u)/DA:.3e}"
          "   <- same convention, two solvers")
    print(f"self-check  |D2-D3|/D3                  {abs(D2-D3)/D3:.3e}"
          "   <- B: Kirchhoff forces all paths equal")
    print(f"overcount   D1/DA  (vs adopted)         {D1/DA:10.2f} x")
    print(f"overcount   D1/D3  (vs B reference)     {D1/D3:10.2f} x")
    print(f"convention  D3/DA  (B / A)              {D3/DA:10.4f} x")
    print()
    print(f"control (equal material, n parallel)    {dp_ctrl/1000:10.5f} kPa")
    print(f"ratio tree/control  DA (adopted)        {DA/dp_ctrl:10.2f} x")
    print(f"ratio tree/control  D1 (historical)     {D1/dp_ctrl:10.0f} x")
    print()
    print(f"20 kPa budget:  DA {'OVER' if DA > 20e3 else 'under'}   "
          f"D1 {'OVER' if D1 > 20e3 else 'under'}")
    print(f"9 kPa published cold plate: "
          f"DA {DA/9e3:.3f}x   D1 {D1/9e3:.2f}x")


if __name__ == "__main__":
    main()
