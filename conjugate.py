"""Conjugate (flow-thermal) model: the coolant is no longer an ideal sink.

Every result in REPORT.md up to section 20 pinned the channel cells at
T_cool exactly. That is the assumption this module tests: a real cold
plate moves water through the channels, and the water heats up as it
absorbs heat, so the channel wall temperature rises along the flow path.
The consequence is that a channel deep in the network sees warmer coolant
than one near the inlet -- and a TREE has long capillaries, while a
straight channel does not.

WHY THE FIRST TWO ATTEMPTS BLEW UP (kept as a warning):
  attempt 1 -- used `radius.node_flows` raw as a flow share. It is a LEAF
      COUNT (root = 61 for the single-source tree), not a share, so the
      flow was up to 61x too large and the coolant march mis-scaled.
  attempt 2 -- normalised the flow but wrote the SI source term as
      SI^2/(4*t*SI*k)*strength, which is 200x smaller than what
      `field.solve_heat` uses (field already divides by t inside q), and
      ~1e7x smaller than the physical value. The plate then absorbed
      almost nothing, the flux estimate was noise, and the Picard
      iteration diverged to 1e60 C.

This version therefore does NOT invent a source term. It calls
`verify.apply_channels`, whose source convention is already regression-
tested against run_report.json, and adds only the coolant march around
it. The channel cells are held at their LOCAL coolant temperature instead
of the uniform T_cool, which is the single physical change.

MODEL
-----
1. Flow topology. `radius.node_flows` gives the leaf count; dividing by the
   root's count gives the flow share per node (Murray radii => flow split).
2. Coolant temperature along each edge:
       T_out = T_in + Q_heat / (rho * cp * Q)
3. Coupling. Picard iteration on the wall temperature:
     a. impose the current wall temperature on the channel cells,
     b. re-solve conduction via verify.apply_channels (same source term,
        same tolerance as every other section),
     c. recompute the heat each channel cell absorbed,
     d. march the coolant temperature,
     e. damp and repeat.
4. Wall temperature, not pinning. The channel cell is held at the local
   coolant temperature -- a lumped assumption that neglects the wall-to-
   bulk gradient INSIDE the channel (the channel's own Biot number, small
   for a 1 mm water passage). The point of the model is the ALONG-FLOW
   rise, which is what the tree is exposed to and the straight pipe is
   not.

PRE-REGISTERED
--------------
  R15  As the flow rate goes to infinity the coolant rise goes to zero, so
       the conjugate model must converge to the PINNED (Dirichlet) model.
       Regression guard. Failure means the coupling is wrong.
  R16  Does the tree's peak temperature rise above the control's under
       conjugation?  -> if yes, the tree's advantage was an artefact of
       the ideal sink and the §16 ranking is at risk.
  R17  Does the tree's R_th still fall inside the published cold-plate
       band (0.0069 - 0.0200 C/W) at the calibration flow rate?
  R18  How much does the coolant actually heat up along the tree? If the
       rise is a small fraction of a degree, the idealisation was
       harmless and §20's conclusion extends to the channel side.
"""
from __future__ import annotations

import numpy as np

import calibrate as C
import radius as Ra
import verify as V

RHO_CP = C.RHO_WATER * C.CP_WATER        # J/(m3 K)
T_COOL = C.T_COOL_C


# ------------------------------------------------------------------ flow
def flow_shares(edges) -> dict[int, float]:
    """Per-node volumetric flow SHARE (sums to 1 at the root).

    `radius.node_flows` returns a leaf COUNT -- a leaf carries 1 and the
    root carries the total number of leaves (61 for the single-source
    tree). Using it raw multiplies the flow by up to 61x. Divide by the
    root's count so every caller gets a share.
    """
    flow = Ra.node_flows(edges)
    if not flow:
        return {}
    children = {c for _, c in edges}
    roots = [n for n in flow if n not in children]
    root = roots[0] if roots else max(flow, key=flow.get)
    total = float(flow[root])
    if total <= 0.0:
        return {n: 0.0 for n in flow}
    return {n: flow[n] / total for n in flow}


def chain_order(edges):
    """Topological order of the tree, plus each node's upstream parent."""
    children: dict[int, list[int]] = {}
    indeg: dict[int, int] = {}
    for p, c in edges:
        children.setdefault(p, []).append(c)
        indeg[c] = indeg.get(c, 0) + 1
        indeg.setdefault(p, 0)
    roots = [n for n in indeg if indeg[n] == 0]
    order: list[int] = []
    parents: dict[int, int | None] = {r: None for r in roots}
    stack = list(roots)
    while stack:
        n = stack.pop()
        order.append(n)
        for c in children.get(n, []):
            parents[c] = n
            indeg[c] -= 1
            if indeg[c] == 0:
                stack.append(c)
    if len(order) != len(indeg):
        raise ValueError("tree edges are not a DAG")
    return order, parents


def coolant_temperatures(edges, q_total_m3s, heat_per_edge_w, t_inlet_c=T_COOL):
    """Coolant temperature at every node, marching from the inlet."""
    order, parents = chain_order(edges)
    shares = flow_shares(edges)
    T: dict[int, float] = {}
    for n in order:
        p = parents[n]
        if p is None:
            T[n] = float(t_inlet_c)
            continue
        q_here = q_total_m3s * shares.get(n, 0.0)
        q_heat = heat_per_edge_w.get((p, n), 0.0)
        T[n] = T[p] + (q_heat / (RHO_CP * q_here) if q_here > 0.0 else 0.0)
    return T


# -------------------------------------------------------------- conjugate
def solve_conjugate(T_field, src, channel_cells, edges, grid_x, grid_y,
                    q_total_m3s, strength=None, t_inlet_c=T_COOL,
                    power_w=None, max_iter=200, tol=1e-5, damping=0.35):
    """Plate conduction with channel cells at their LOCAL coolant temperature.

    Returns (field, held_mask, wall_by_cell, info).

    `held_mask` covers exactly the channel cells that are held at the wall
    temperature -- i.e. every channel cell EXCEPT the source cells, which
    the project's fairness rule forbids pinning. Build the solid mask the
    way `verify.Group.from_field` does (`~pinned`, with the full channel
    mask from `verify.channel_mask`) rather than re-deriving it here.

    The conduction solve itself is delegated to `verify.apply_channels` so
    the source term and tolerance are identical to every other section; the
    only difference is that `T_cool` is replaced by the per-cell wall
    temperature.

    Coupling is a damped Picard iteration. At low flow the coolant rise is
    tens of degrees and the exchange is stiff; a fixed damping oscillates
    (observed: wall delta stuck near 28 C for 120 iterations at 0.073
    L/min), so the damping is reduced whenever the residual grows.

    N2 FIX (2026-10-17): `power_w` is the PHYSICAL heat the coolant must
    carry (W). With power_w=None the energy balance is normalized by
    `src.sum()` -- a CELL COUNT (867 for the spread 3-die layout), not
    watts -- which decoupled coolant_out from the real 759 W and inflated
    REPORT 23's outlet temperatures (R23). Passing power_w restores
    dT_total = power_w / (rho*cp*Q).

    N3 FIX (2026-10-17): the Picard re-solve now pins each channel cell at
    its own wall temperature (per-cell T_cool array) instead of the uniform
    inlet temperature. Previously the solid was re-solved against a 25 C
    boundary at every flow rate and only the channel cells themselves were
    overwritten afterwards, so the solid never responded to the warm
    coolant -- the coupling was one-way (coolant depended on the solid,
    not vice versa) and T_mean was bitwise-identical across all flow rates.
    """
    cells = sorted(channel_cells)
    idx = {c: i for i, c in enumerate(cells)}
    n = len(cells)
    held_mask = np.zeros((grid_y, grid_x), dtype=bool)
    for c in cells:
        held_mask[c] = True

    # Source cells are NEVER held at the coolant temperature: a channel must
    # not delete the heat it is meant to remove. verify.channel_mask enforces
    # the same rule by not pinning them. Re-imposing the wall on them would,
    # in the Q->inf limit, pin the heat source itself at T_cool and give a
    # peak of exactly 25 C -- 2.596 C below the pinned reference. That was
    # the first version's R15 failure.
    src_cells = set(zip(*np.nonzero(src))) if hasattr(src, "shape") else set()
    held = [c for c in cells if c not in src_cells]
    held_idx = [idx[c] for c in held]

    def node_of(cell):
        return cell[0] * grid_x + cell[1]

    wall = np.full(n, float(t_inlet_c))
    info = {"iters": 0, "history": [], "converged": False,
            "held_cells": len(held), "source_cells_skipped": len(src_cells),
            "damping": damping}
    Tc = np.array(T_field, dtype=float, copy=True)
    prev_delta = np.inf
    damp = damping

    for it in range(max_iter):
        # 1. impose the current wall temperature on the held channel cells
        base = np.array(T_field, dtype=float, copy=True)
        for i in held_idx:
            base[cells[i]] = wall[i]
        # 2. re-solve conduction with those cells held. N3 FIX: pass the
        #    per-cell wall array so apply_channels pins each channel cell at
        #    ITS OWN wall value. Previously it pinned at the uniform inlet
        #    temperature and the post-hoc overwrite only changed the channel
        #    cells themselves -- the solid was always solved against a 25 C
        #    boundary and never responded to the warm coolant (T_mean was
        #    bitwise-identical across all five flow rates). apply_channels
        #    now returns the held cells at exactly these values, so no
        #    post-hoc overwrite is needed. In the Q->inf limit wall ==
        #    t_inlet_c uniformly and the old scalar behaviour is recovered
        #    bit-for-bit (the R15 regression guard).
        pin_T = np.full(T_field.shape, float(t_inlet_c))
        for i in held_idx:
            pin_T[cells[i]] = wall[i]
        Tc, _ = V.apply_channels(base, held, src, T_cool=pin_T,
                                 strength=strength,
                                 max_iter=V.APPLY_MAX_ITER, tol=V.APPLY_TOL)

        # 3. heat each held channel cell absorbed: discrete flux from
        #    neighbours. Only held cells take part -- a source cell that a
        #    channel happens to overlap is not a coolant wall.
        src_arr = src if strength is None else np.asarray(strength, dtype=float)
        # N2 FIX: coolant energy balance in PHYSICAL WATTS. strength=None
        # made total_source a CELL COUNT (867), not watts -- see docstring.
        total_source = (float(power_w) if power_w is not None
                        else float(src_arr.sum()))
        raw = np.zeros(n)
        for i in held_idx:
            c = cells[i]
            y, x = c
            s = 0.0
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < grid_y and 0 <= xx < grid_x:
                    s += (Tc[yy, xx] - Tc[y, x])
            raw[i] = max(s, 0.0)
        # rescale so the extracted power equals the applied power
        s_raw = float(raw.sum())
        scale = (total_source / s_raw) if (s_raw > 0.0 and total_source > 0.0) else 0.0
        flux = raw * scale
        total_w = float(flux.sum())

        # 4. march the coolant
        heat_per_edge = {}
        for p, c_ in edges:
            cell = (c_ // grid_x, c_ % grid_x)
            i = idx.get(cell)
            if i is not None and cell not in src_cells:
                heat_per_edge[(p, c_)] = flux[i]
        T_node = coolant_temperatures(edges, q_total_m3s, heat_per_edge,
                                      t_inlet_c)
        wall_new = np.array([T_node.get(node_of(c), t_inlet_c) for c in cells])

        delta = float(np.max(np.abs(wall_new - wall))) if n else 0.0
        # adaptive damping: if the residual grew, back off. Without this the
        # low-flow cases oscillate instead of converging.
        if delta > prev_delta:
            damp = max(0.05, damp * 0.7)
        else:
            damp = min(damping, damp * 1.1 + 0.01)
        prev_delta = delta
        wall = (1.0 - damp) * wall + damp * wall_new
        info["iters"] = it + 1
        info["history"].append({"iter": it + 1, "max_wall_delta": delta,
                                "damping": damp, "total_heat_w": total_w})
        if it >= 1 and delta < tol:
            info["converged"] = True
            break

    info["damping_final"] = damp
    info["coolant_rise_c"] = float(wall.max() - wall.min()) if n else 0.0
    info["coolant_out_c"] = float(wall.max()) if n else t_inlet_c
    info["total_heat_w"] = total_w
    return Tc, held_mask, wall, info


def straight_pipe_outlet(q_total_m3s, power_w, t_inlet_c=T_COOL):
    """Outlet temperature of ONE straight pipe carrying all the heat.

    The control has no branching, so its coolant rise is simply the total
    power over the total flow -- the best case any single-passage design
    can achieve. This is the yardstick the tree is measured against.
    """
    return t_inlet_c + power_w / (RHO_CP * q_total_m3s)
