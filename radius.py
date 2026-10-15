"""Step 3: Murray's law tube radii.

Every LEAF cell carries unit "flow" (the cooling demand of the region it
represents). Internal nodes carry only the demand flowing through them, so
flow(parent) = 1 + sum(flow(child)) and

    r_parent^3 = sum(r_child^3)

holds exactly at every junction, with r = r0 * N^(1/3).

Returns {node_idx: radius_mm}.
"""
from __future__ import annotations

import numpy as np


def build_tree(edges: list[tuple[int, int]]):
    """Return (children, parent, depth, root) for an edge list."""
    children: dict[int, list[int]] = {}
    parent: dict[int, int] = {}
    for p, c in edges:
        children.setdefault(p, []).append(c)
        parent[c] = p
    root = edges[0][0]

    depth: dict[int, int] = {root: 0}
    stack = [root]
    while stack:
        v = stack.pop()
        for ch in children.get(v, []):
            depth[ch] = depth[v] + 1
            stack.append(ch)
    return children, parent, depth, root


def node_flows(edges: list[tuple[int, int]]) -> dict[int, float]:
    """Downstream demand per node: a leaf carries 1, an internal node carries
    the sum of its children's demands (its own demand is not added again)."""
    children, parent, depth, root = build_tree(edges)
    nodes = set(parent) | set(parent.values()) | {root}

    flow = {i: 1 for i in nodes}
    # deepest first: by the time we reach v, every child of v is finalised
    for v in sorted(nodes, key=lambda i: -depth[i]):
        ch = children.get(v)
        if ch:
            flow[v] = sum(flow[c] for c in ch)
    return flow


def assign_radii(
    edges: list[tuple[int, int]],
    grid: int,
    r0: float = 0.5,
) -> dict[int, float]:
    """Murray-law radii for the tree given as an edge list.

    grid = number of columns (idx = y*grid + x).
    """
    if not edges:
        return {}
    flow = node_flows(edges)
    return {i: r0 * (flow[i] ** (1.0 / 3.0)) for i in flow}


def check_murray(edges: list[tuple[int, int]], radii: dict[int, float], tol: float = 1e-9) -> dict:
    """Verify r_parent^3 == sum(r_children^3) at every branching node."""
    children, _, _, _ = build_tree(edges)

    rows = []
    worst = 0.0
    for p, ch in children.items():
        if len(ch) < 2:
            continue
        lhs = radii[p] ** 3
        rhs = sum(radii[c] ** 3 for c in ch)
        err = abs(lhs - rhs) / rhs
        worst = max(worst, err)
        rows.append(
            {
                "parent": p,
                "n_children": len(ch),
                "r_parent": radii[p],
                "sum_r_child_cubed": rhs,
                "rel_err": err,
            }
        )
    return {
        "n_forks": len(rows),
        "max_rel_err": worst,
        "pass": bool(worst < tol),
        "rows": rows,
    }


def radius_profile(radii: dict[int, float], grid_x: int) -> dict:
    """Min/max radius and the share of nodes that are capillaries."""
    vals = np.array(sorted(radii.values()))
    return {
        "min": float(vals.min()),
        "max": float(vals.max()),
        "mean": float(vals.mean()),
        "frac_le_0_6mm": float((vals <= 0.6).mean()),
    }
