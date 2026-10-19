"""v5 order estimate -- INDEPENDENT re-implementation of the junction-aware
root-to-leaf pressure drop (DEFECT_REMEDIATION_PLAN.md §10.15).

WHY THIS FILE EXISTS
--------------------
DEFECT_REMEDIATION_PLAN.md L1162 claims: "the repaired path sum agrees
digit-for-digit with the independent implementation `v5_order_estimate.py`
(J1 0.1415 / J2 3.8175 / J3 7.8653 kPa, pseudo-forks included, inlet
excluded)". That file had been lost, so the claim had no artefact behind
it. This is a from-scratch reconstruction, written to be genuinely
independent of `calibrate.py`:

  quantity            calibrate.py path          this file
  ------------------  -------------------------  --------------------------
  topology            radius.build_tree           explicit edge scan here
  demand              radius.node_flows           reverse post-order here
  viscous term        R = 8*mu*L/(pi*r^4)         f*(L/D)*rho*v^2/2, f=64/Re
  junction reference  radii[v]                    radii[v]  (must match: F2)
  path accumulation   junction_on_path            explicit walk here

Agreement to ~1e-12 therefore validates the algebra, not a shared helper.
Any disagreement is a real finding and must be reported, not smoothed over.

UNITS
-----
The recorded values are kPa at 253 W (Q = 0.7282 L/min), grid_mm from
`calibrate.paper_grid_mm(50)` = 0.90 mm, tree b=400.
"""
from __future__ import annotations

import math

import numpy as np

import calibrate as C
import grow as G
import radius as Ra
from field import SRC_RADIUS_SYNTHETIC, normalize_field, solve_heat_sources

SI = 1e-3   # mm -> m


# ---------------------------------------------------------------- topology
def topology(edges):
    """children / parent / nodes / leaves -- written out, no helper import."""
    children: dict[int, list[int]] = {}
    parent: dict[int, int] = {}
    for p, c in edges:
        children.setdefault(p, []).append(c)
        parent[c] = p
    root = edges[0][0]
    nodes = set(parent) | set(parent.values()) | {root}
    leaves = sorted(v for v in nodes if not children.get(v))
    return children, parent, nodes, leaves, root


def demand_dfs(children, parent, nodes, leaves, root):
    """Leaf demand = 1; internal node = sum of children. Iterative post-order
    from the LEAVES upward (radius.node_flows sorts by depth instead)."""
    dem = {v: 0.0 for v in nodes}
    for l in leaves:
        dem[l] = 1.0
    # Kahn-style peel: a node is ready when all its children are done
    pending = {v: len(children.get(v, [])) for v in nodes}
    ready = [v for v in nodes if pending[v] == 0]
    while ready:
        v = ready.pop()
        p = parent.get(v)
        if p is None:
            continue
        dem[p] += dem[v]
        pending[p] -= 1
        if pending[p] == 0:
            ready.append(p)
    assert all(pending[v] == 0 for v in nodes), "cycle or orphan in edge list"
    assert abs(dem[root] - float(len(leaves))) < 1e-12, "demand must equal n_leaves"
    return dem


# ------------------------------------------------------------- loss models
def k_j0(re, s):
    return 0.0


def k_j1(re, s):
    """Rennels split formula, turbulence data extrapolated to laminar."""
    return 0.62 - 0.98 * s + 0.36 * s * s


def k_j2(re, s):
    return 1.8


def k_j3(re, s):
    """Constructive laminar interpolation: K = 1.8*2300/Re, clipped [1, 300]."""
    return min(max(1.8 * 2300.0 / re, 1.0), 300.0)


FAMILY = [("J0", k_j0), ("J1", k_j1), ("J2", k_j2), ("J3", k_j3)]


# ------------------------------------------------------------------ solver
def solve(edges, radii, grid_mm, q_total, mu, rho,
          k_of, skip_pseudo=False, k_in=0.0):
    children, parent, nodes, leaves, root = topology(edges)
    dem = demand_dfs(children, parent, nodes, leaves, root)
    total = dem[root]
    q = {v: q_total * dem[v] / total for v in nodes}

    L = grid_mm * SI

    def viscous(p, c):
        """Darcy-Weisbach with f = 64/Re  (NOT 8*mu*L*Q/(pi*r^4))."""
        r = min(radii[p], radii[c]) * SI
        d = 2.0 * r
        area = math.pi * r * r
        v = q[c] / area
        re = rho * v * d / mu
        f = 64.0 / re
        return f * (L / d) * rho * v * v / 2.0

    # junction at node v (v != root): reference is the PARENT branch radii[v]
    jun = {}
    pseudo = 0
    forks = 0
    for v in nodes:
        ch = children.get(v, [])
        if len(ch) < 2 or v == root:
            continue
        forks += 1
        q_par = q[v]
        q_main = max(q[c] for c in ch)
        if q_par / q_main < 1.1:
            pseudo += 1
            if skip_pseudo:
                continue
        s = q_main / q_par if q_par > 0 else 0.0
        r_p = radii[v] * SI
        v_p = q_par / (math.pi * r_p * r_p)
        re_p = rho * v_p * 2.0 * r_p / mu
        jun[v] = (k_of(re_p, s) * rho * v_p * v_p / 2.0,
                  re_p, s)

    def path(l):
        vis = 0.0
        jl = 0.0
        v = l
        while v != root:
            p = parent[v]
            vis += viscous(p, v)
            if v in jun:
                jl += jun[v][0]
            v = p
        return vis, jl

    per_leaf = {l: path(l) for l in leaves}
    vis_by = {l: per_leaf[l][0] for l in leaves}
    tot_by = {l: per_leaf[l][0] + per_leaf[l][1] for l in leaves}
    crit = max(tot_by, key=tot_by.get)

    # inlet term: K_in on the ROOT branch dynamic head, counted once
    r_root = radii[root] * SI
    v_root = q_total / (math.pi * r_root * r_root)
    re_root = rho * v_root * 2.0 * r_root / mu
    inlet = k_in * rho * v_root * v_root / 2.0

    return {
        "dp_viscous": max(vis_by.values()),
        "dp_junction": tot_by[crit] - vis_by[crit],
        "dp_total": tot_by[crit],
        "dp_with_inlet": tot_by[crit] + inlet,
        "inlet": inlet,
        "v_root": v_root,
        "re_root": re_root,
        "root_degree": len(children.get(root, [])),
        "forks": forks,
        "pseudo": pseudo,
        "n_leaves": len(leaves),
        "n_edges": len(edges),
        "critical_leaf": crit,
        "jun_max": max(((v,) + t for v, t in jun.items()),
                       key=lambda z: z[1]) if jun else None,
    }


def main() -> None:
    td = normalize_field(
        solve_heat_sources(grid=50, centers=[(25, 25)],
                           source_radius=SRC_RADIUS_SYNTHETIC).T,
        T_target=100.0)
    edges = G.grow_tree(td, max_nodes=400)
    radii = Ra.assign_radii(edges, grid=50, r0=0.5)

    grid_mm = C.paper_grid_mm(50)
    q_tot = C.coolant_flow_m3s(253.0)
    print(f"edges={len(edges)}  grid_mm={grid_mm:.4f}  "
          f"Q={C.lpm(q_tot):.4f} L/min  mu={C.MU_WATER:.6e}  "
          f"rho={C.RHO_WATER:.2f}")

    base = solve(edges, radii, grid_mm, q_tot, C.MU_WATER, C.RHO_WATER,
                 k_j0)
    print(f"leaves={base['n_leaves']}  root_degree={base['root_degree']}  "
          f"forks={base['forks']}  pseudo={base['pseudo']}  "
          f"v_root={base['v_root']:.4f} m/s  Re_root={base['re_root']:.1f}")
    print(f"viscous dp = {base['dp_viscous']/1000:.9f} kPa "
          f"(paper/A0 = 0.080248475)")

    print("\n--- family, pseudo-forks INCLUDED, inlet EXCLUDED ---")
    print(f"{'':4} {'viscous':>10} {'junction':>10} {'total kPa':>12} "
          f"{'x control':>10}")
    # L1162 records the JUNCTION term, not the total dp. Compare like with like.
    recorded = {"J1": 0.1415, "J2": 3.8175, "J3": 7.8653}
    control = None
    for name, kf in FAMILY:
        r = solve(edges, radii, grid_mm, q_tot, C.MU_WATER, C.RHO_WATER, kf)
        if name == "J0":
            control = r["dp_total"]
        tag = ""
        if name in recorded:
            rel = abs(r["dp_junction"] / 1000 - recorded[name]) / recorded[name]
            tag = (f"  recorded_junction={recorded[name]:.4f} "
                   f"rel={rel:.2e}")
        print(f"{name:4} {r['dp_viscous']/1000:10.6f} "
              f"{r['dp_junction']/1000:10.6f} {r['dp_total']/1000:12.6f} "
              f"{r['dp_total']/control:10.2f}{tag}")

    print("\n--- family, pseudo-forks DROPPED, inlet EXCLUDED ---")
    for name, kf in FAMILY:
        r = solve(edges, radii, grid_mm, q_tot, C.MU_WATER, C.RHO_WATER, kf,
                  skip_pseudo=True)
        print(f"{name:4} total={r['dp_total']/1000:10.6f} kPa  "
              f"x={r['dp_total']/control:7.2f}")

    print("\n--- family, K_in=0.5 on v_root, counted once ---")
    j0_in = solve(edges, radii, grid_mm, q_tot, C.MU_WATER, C.RHO_WATER,
                  k_j0, k_in=0.5)
    print(f"inlet = {j0_in['inlet']/1000:.6f} kPa")
    for name, kf in FAMILY:
        r = solve(edges, radii, grid_mm, q_tot, C.MU_WATER, C.RHO_WATER, kf,
                  k_in=0.5)
        print(f"{name:4} total={r['dp_with_inlet']/1000:10.6f} kPa  "
              f"x={r['dp_with_inlet']/control:7.2f}")

    print("\n--- max non-root junction (J2) ---")
    r2 = solve(edges, radii, grid_mm, q_tot, C.MU_WATER, C.RHO_WATER, k_j2)
    v, jv, re_p, s = r2["jun_max"]
    print(f"node {v}: {jv/1000:.6f} kPa  Re_parent={re_p:.1f}  s={s:.4f}")

    # ---- cross-check against calibrate.py -------------------------------
    print("\n--- cross-check vs calibrate.tree_dp_pa (same tree) ---")
    for name, kf in FAMILY:
        d = C.tree_dp_pa(edges, radii, 50, grid_mm, q_tot,
                         with_junctions=True, k_of=kf)
        mine = solve(edges, radii, grid_mm, q_tot, C.MU_WATER, C.RHO_WATER, kf)
        a, b = d["dp_pa"], mine["dp_total"]
        rel = abs(a - b) / b
        print(f"{name:4} calibrate={a/1000:10.6f}  independent={b/1000:10.6f}  "
              f"rel={rel:.2e}  {'PASS' if rel < 1e-12 else 'FAIL'}")


if __name__ == "__main__":
    main()
