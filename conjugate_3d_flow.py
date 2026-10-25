# -*- coding: utf-8 -*-
"""3-D conduction coupled to a 1-D coolant march (NOT a CFD solver).

WHAT THIS IS
------------
`conjugate_3d.py` resolved the third dimension but kept every channel column
pinned at a single coolant temperature, which means the model cannot express
streamwise heating. This module lifts exactly that one idealisation and
nothing else:

  * the SOLID is the same 3-D block as `conjugate_3d.py` -- same grid, same
    depth, same top skin (`channel_top_gap = 1`), same source, solved by the
    same `field.solve_heat_3d` (imported, not re-implemented);
  * each channel column is held at ONE wall temperature, but that temperature
    is now the LOCAL coolant temperature, which rises along the flow as heat
    is absorbed;
  * the coolant is a 1-D slug: T_out = T_in + q_absorbed / (rho*cp*Q_share).

WHAT THIS IS NOT
----------------
No flow field is solved. There is no velocity profile, no wall-to-bulk
gradient inside the channel, no entry length, no conjugate convection
coefficient. The wall is the bulk: a lumped assumption whose error is the
channel's own Biot number (small for a 1 mm passage). The correct name for
this model is "3-D conduction with a 1-D coolant march". It must not be
called CFD in the paper.

THE ONE FREE PARAMETER
----------------------
Non-dimensionalise with T* = (T - T_in)*k/(q*h**2). The solid problem is
unchanged (Laplacian = -1 over the source block); the coolant advance becomes

    dT*_n = h*_n / (Pi * share_n),      Pi = rho*cp*Qdot / (k*h)

so `Pi` is the only fluid-solid coupling parameter left once the geometry,
the Biot number of the base and the flow split are fixed. Pi -> infinity is
the pinned (Dirichlet) limit, i.e. exactly `conjugate_3d.py`; that is the
regression guard R15 carried over into 3-D.

THREE DELIBERATE DEVIATIONS FROM `conjugate.py`
-----------------------------------------------
  (1) `conjugate.coolant_temperatures` deposits heat only on EDGES, so heat
      absorbed by the ROOT cell -- which has no incoming edge -- is silently
      discarded and the enthalpy balance does not close. Here every NODE
      deposits its own absorbed heat before the flow continues downstream,
      including the root.
  (2) `conjugate.solve_conjugate` clips absorbed heat at max(s, 0). That
      destroys the discrete energy balance whenever a channel cell is a net
      SOURCE of heat (it can be: the wall is warmer than a local solid
      neighbour). Nothing is clipped here; negative cells are counted and
      reported.
  (3) `conjugate` counts the base-face exchange of every pinned cell as
      coolant heat. Here a pinned cell REPLACES the boundary condition on
      the face it occupies, so that face carries no solid-side flux by
      construction and is excluded.

ENERGY ACCOUNTING (asserted, not assumed)
-----------------------------------------
`field.solve_heat_3d` closes the four sides with MIRROR copies
(`Tn[:,0,:] = Tn[:,1,:]`, `Tn[:,:,-1] = Tn[:,:,-2]`, likewise z), so rows and
columns 0 and grid-1 are ghosts: no equation is ever solved for them and
their value duplicates a real cell. Every sum below is therefore restricted
to the interior (y, x in 1..grid-2), and a channel<->solid face is counted
only when the SOLID side is interior. Both restrictions matter: the straight
group spans the full plate length, so its end rows sit on ghosts, and counting
them inflated P_chan by 4% and P_base by 8% (measured in the development
log). With the ghosts included the closure error was 7.2e-2; with them
excluded it is 1.6e-5 at worst.

With that bookkeeping the discrete steady equation of every solid cell,

    sum_faces (T_nb - T_P) = -q*h**2/k   (source cells)   or 0,

summed over the real unknowns, telescopes every solid-solid face away -- except
at the top skin. `field.solve_heat_3d` couples z=depth-1 to z=depth-2 with
weight 2 in the skin's own equation (the adiabatic-ghost form) and weight 1 in
the neighbour's, so every SOLID-SOLID 8-9 face fails to cancel and leaks
(T_top - T_below). The exact identity is therefore

    P_inj = P_chan + P_base_out + D,   D = sum_{free interior} (T[9] - T[8])

with P_inj = 25 (25 source cells x 1), P_chan the flux from SOLID cells into
channel cells (the skin face carries weight 2, matching the skin's own
equation; weight 1 leaves a residual of exactly 0.500 and is wrong), and
P_base_out the flux through the cooled base.

D is measured, never assumed small: 0.09% of P_inj in the pinned (Pi -> inf)
Bi=1 reference, 0.69% (tree) and 5.8% (straight) at the calibration flow, and
6.3% / 10.4% at the lowest flow, where a warmer interior drives more heat
through the solid-solid 9-8 faces; the worst value anywhere in the sweep is
11.6%. It sits entirely on solid-solid faces -- the skin-to-coolant faces are
weight-consistent -- so the PEAK, which is above the source (a channel cell),
is not the quantity it biases; the COOLANT heat load is. The march therefore
runs on the absorbed distribution renormalised to P_inj (`renormalise=True`,
gain reported per case) so that the tree-vs-straight comparison is made at
equal delivered power, and the raw run is reported alongside for the
reference case.

An enthalpy identity, sum_leaves share*T*_leaf == sum_nodes h*_n / Pi, is
checked separately; it validates the MARCH rather than the solid solve.

Writes outputs/conjugate_3d_flow.json.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"
sys.path.insert(0, str(ROOT))

import calibrate as C  # noqa: E402
import conjugate as CJ  # noqa: E402
import field as F  # noqa: E402
from conjugate_3d import (  # noqa: E402
    CHANNEL_TOP_GAP,
    DEPTH,
    GRID_CHECK,
    GRID_MAIN,
    build_pair,
)
from field import SRC_RADIUS_SYNTHETIC  # noqa: E402

T_IN = C.T_COOL_C
RHO_CP = C.RHO_WATER * C.CP_WATER                    # J/(m3 K)
K_SI = C.K_SI                                        # W/(m K)
PITCH_M = C.paper_grid_mm(50) * C.SI                 # 0.9 mm, the real-unit pitch
Q_CELL_W = C.TDP_I7_W / 25.0                         # 10.12 W per source cell
# Solver -> physical temperature. One solver temperature unit is the rise a
# single source cell creates in the discrete scheme: Q_cell/(k*h), NOT
# q_vol*h^2/k with the source smeared over the full depth (that would be 10x
# too small; the source lives on ONE layer of the block).
K_SCALE = Q_CELL_W / (K_SI * PITCH_M)                # K per solver unit
N_SRC = 25
P_INJ = float(N_SRC)                                 # dimensionless, q=h=k=1

PI_REF = None                                        # filled in main()


def pi_from_flow(q_m3s: float) -> float:
    """Pi = rho*cp*Qdot/(k*h) for a volumetric flow in m3/s."""
    return RHO_CP * q_m3s / (K_SI * PITCH_M)


def flow_from_pi(pi: float) -> float:
    return pi * K_SI * PITCH_M / RHO_CP


def cells_of(mask: np.ndarray) -> list[tuple[int, int]]:
    """Channel cells in EXACTLY the order `field` writes them.

    `Tn[:d, mask] = T_cool` flattens the boolean mask over the trailing two
    axes in C order, which is `np.nonzero` order: y ascending, x ascending.
    Any other order would attach wall temperatures to the wrong columns.
    """
    ys, xs = np.nonzero(mask)
    return list(zip(ys.tolist(), xs.tolist()))


# ------------------------------------------------------------------ physics
def interior_mask(grid):
    """Cells that are genuine unknowns of `field.solve_heat_3d`.

    The solver closes the four sides with MIRROR copies
    (`Tn[:,0,:] = Tn[:,1,:]`, `Tn[:,:,-1] = Tn[:,:,-2]`, likewise z), so rows
    and columns 0 and grid-1 are ghosts: they hold a duplicated value and no
    equation is ever solved for them. Every energy sum below therefore has to
    range over the interior only, otherwise a face is counted twice (once for
    the real cell, once for its mirror image).
    """
    m = np.zeros((grid, grid), dtype=bool)
    m[1:-1, 1:-1] = True
    return m


def absorbed_heat(T, mask, h_base, depth=DEPTH, gap=CHANNEL_TOP_GAP):
    """Heat each channel column absorbs from the SOLID, per cell.

    Faces between two channel cells are interior to the same coolant passage
    and carry no solid heat; faces between two imposed cells (the isothermal
    base plane) exist only because the boundary condition is discretised, so
    they are not solid either. Out-of-plane faces at the plate edge are
    adiabatic (mirror) and contribute zero -- implemented by clipping the
    index onto the cell itself, whose value is the wall temperature.

    A face whose SOLID side is a ghost cell (row/column 0 or grid-1) is
    skipped: that solid cell has no equation, and its mirror image already
    carries the same flux. The straight group spans the full plate length, so
    its end cells sit ON the boundary rows and the omission matters (8% of
    P_chan at Bi=1); for the tree, which never reaches the edge, it is a
    no-op. `probe9` in the development log closes the identity from 2.5e-1 to
    1.3e-4 by this exclusion alone.

    Sign is NOT clipped: a cell may be a net heat source for the solid.
    """
    grid = mask.shape[0]
    d = depth - gap
    itr = interior_mask(grid)
    own = T[:d][:, mask]                       # (d, n_chan)
    acc = np.zeros_like(own)
    base_is_solid = h_base is not None          # False -> z=0 is imposed
    yy, xx = np.mgrid[0:grid, 0:grid]
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ny = np.clip(yy + dy, 0, grid - 1)
        nx = np.clip(xx + dx, 0, grid - 1)
        nbr_is_solid = (~mask[ny, nx]) & itr[ny, nx]
        for z in range(d):
            if z == 0 and not base_is_solid:
                continue
            val = T[z][ny, nx][mask]
            acc[z] += np.where(nbr_is_solid[mask], val - own[z], 0.0)
    if gap >= 1:
        # weight 2: the skin's own equation couples to z=d-1 with weight 2, so
        # the face flux is 2*(T_skin - T_wall). Weight 1 leaves a residual of
        # exactly 0.500 in the block balance and is wrong. A skin cell on the
        # plate edge is a ghost, so those channel cells contribute nothing.
        acc[-1] += 2.0 * (T[d][mask] - own[-1]) * itr[mask]
    return acc.sum(axis=0)


def absorbed_heat_loop(T, mask, h_base, depth=DEPTH, gap=CHANNEL_TOP_GAP):
    """Slow reference implementation of `absorbed_heat` (cross-check)."""
    grid = mask.shape[0]
    d = depth - gap
    itr = interior_mask(grid)
    out = []
    for y, x in cells_of(mask):
        s = 0.0
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if not (0 <= ny < grid and 0 <= nx < grid):
                continue
            if mask[ny, nx] or not itr[ny, nx]:
                continue
            for z in range(d):
                if z == 0 and h_base is None:
                    continue
                s += T[z, ny, nx] - T[z, y, x]
        if gap >= 1 and itr[y, x]:
            s += 2.0 * (T[d, y, x] - T[d - 1, y, x])
        out.append(s)
    return np.array(out)


def skin_residual(T, mask, depth=DEPTH, gap=CHANNEL_TOP_GAP):
    """D: the unresolved leak on solid-solid faces at the top-skin interface.

    `field.solve_heat_3d` gives the z=depth-1 <-> z=depth-2 coupling weight 2
    in the skin's equation and weight 1 in the neighbour's, so faces between
    two SOLID cells fail to cancel. The leftover is exactly the sum of
    (T_top - T_below) over the free INTERIOR footprint. Faces into a channel
    cell are weight-consistent and do not contribute, and so do ghost cells
    (row/column 0 and grid-1), which have no equation. Measured, never
    assumed zero.
    """
    if gap < 1:
        return 0.0
    d = depth - gap
    free = (~mask) & interior_mask(mask.shape[0])
    return float(np.sum(T[d][free] - T[d - 1][free]))


def base_out(T, mask, h_base, t_b=T_IN):
    """Heat leaving through the cooled base, solid INTERIOR cells only.

    `mask` is a (grid, grid) channel footprint and applies to every z layer,
    so the free footprint is `~mask` -- not `~mask[0]`, which would index
    whole rows of the plate. The mirror ghost cells are excluded: they carry
    no equation and their value duplicates a real cell, so including them
    inflates the base flux by the 12.9% edge fraction of the plate.
    """
    if h_base == 0.0:
        return 0.0                              # adiabatic base
    free = (~mask) & interior_mask(mask.shape[0])
    if h_base is None:
        # base is Dirichlet: the flux into it is the z=1 -> z=0 face sum
        return float(np.sum(T[1][free] - T[0][free]))
    bi = h_base * F.PITCH_MM / 1.0               # k = 1 in solver units
    return float(np.sum(bi * (T[0][free] - t_b)))


def energy_balance(T, mask, h_base):
    """Closure of P_inj = P_chan + P_base_out + D.

    `residual_rel` is the DELIVERY gap |P_inj - delivered|/P_inj -- it is not
    a numerical error, it is D/P_inj. `closure_rel` is the genuine closure
    check and is the one asserted.
    """
    absorbed = absorbed_heat(T, mask, h_base)
    p_chan = float(absorbed.sum())
    p_base = base_out(T, mask, h_base)
    p_skin = skin_residual(T, mask)
    delivered = p_chan + p_base
    return {"p_inj": P_INJ, "p_chan": p_chan, "p_base_out": p_base,
            "skin_leak": p_skin,
            "delivered": delivered,
            "delivered_fraction": delivered / P_INJ,
            "closure_rel": abs(P_INJ - delivered - p_skin) / P_INJ,
            "residual_rel": abs(P_INJ - delivered) / P_INJ,
            "n_negative_cells": int((absorbed < 0.0).sum()),
            "min_cell_flux": float(absorbed.min()),
            "max_cell_flux": float(absorbed.max())}


# ------------------------------------------------------------ coolant march
def march_tree(edges, cells, absorbed, grid, pi, t_in=T_IN):
    """Wall temperature of every tree channel cell (root absorbs too)."""
    order, parents = CJ.chain_order(edges)
    shares = CJ.flow_shares(edges)
    by_node = {y * grid + x: absorbed[i] for i, (y, x) in enumerate(cells)}
    T: dict[int, float] = {}
    for n in order:
        p = parents[n]
        h = by_node.get(n, 0.0)
        w = shares[n]
        step = h / (pi * w) if (pi * w) > 0.0 else 0.0
        T[n] = t_in + step if p is None else T[p] + step
    return np.array([T[y * grid + x] for (y, x) in cells]), T, shares


def march_straight(cells, absorbed, grid, pi, feed="centre", t_in=T_IN):
    """Wall temperature of a straight-channel bank.

    feed="centre"  the manifold feeds the middle row and the flow splits into
                   two half-banks running to the two edges. This is the
                   apple-to-apple control for a tree whose inlet sits at the
                   source centre: both designs admit the coolant where the
                   heat is, so the comparison isolates the TOPOLOGY.
    feed="edge"    a single inlet at y=0, i.e. the usual cold-plate layout.
                   Reported as a sensitivity case: it leaves the coolant
                   warmest exactly where the source is.
    """
    cols = sorted({x for _, x in cells})
    ncol = len(cols)
    by_cell = {c: absorbed[i] for i, c in enumerate(cells)}
    out: dict[tuple[int, int], float] = {}
    if feed == "edge":
        w = 1.0 / ncol
        for x in cols:
            temp = t_in
            for y in range(grid):
                temp += by_cell[(y, x)] / (pi * w)
                out[(y, x)] = temp
        return np.array([out[c] for c in cells]), out

    c = grid // 2
    w = 1.0 / (2.0 * ncol)                       # share of ONE half-bank
    for x in cols:
        half = 0.5 * by_cell[(c, x)]             # centre cell feeds both ways
        temp = t_in + half / (pi * w)
        out[(c, x)] = temp
        t_up = temp
        for y in range(c + 1, grid):
            t_up += by_cell[(y, x)] / (pi * w)
            out[(y, x)] = t_up
        t_dn = temp
        for y in range(c - 1, -1, -1):
            t_dn += by_cell[(y, x)] / (pi * w)
            out[(y, x)] = t_dn
    return np.array([out[c] for c in cells]), out


def leaf_shares(kind, cells, grid, edges=None, feed="centre"):
    """(index into `cells`, flow share) of every flow terminus.

    Tree: nodes that appear as no one's parent. Straight centre feed: the two
    end rows of every column, each carrying half of that column's flow.
    Straight edge feed: the far end row of every column.
    """
    idx = {c: i for i, c in enumerate(cells)}
    if kind == "tree":
        shares = CJ.flow_shares(edges)
        # a terminus is a node that is nobody's PARENT; `{c for _, c in edges}`
        # is the set of CHILDREN and selecting its complement returns the root.
        has_child = {p for p, _ in edges}
        return [(idx[(y, x)], shares[y * grid + x]) for (y, x) in cells
                if (y * grid + x) not in has_child]
    cols = sorted({x for _, x in cells})
    ncol = len(cols)
    if feed == "edge":
        w = 1.0 / ncol
        return [(idx[(grid - 1, x)], w) for x in cols]
    w = 1.0 / (2.0 * ncol)
    out = []
    for x in cols:
        out.append((idx[(0, x)], w))
        out.append((idx[(grid - 1, x)], w))
    return out


def enthalpy_identity(kind, cells, absorbed, wall, pi, grid, edges=None,
                      feed="centre"):
    """sum_leaves share_l*(T_l - T_in)  ==  sum_nodes h_n / pi.

    Independent of the solid solve: it validates the MARCH alone. The proof
    is that the flow share of a node equals the sum of the shares of the
    leaves downstream of it, so the leaf-weighted path sum telescopes to the
    node sum.
    """
    leaves = leaf_shares(kind, cells, grid, edges=edges, feed=feed)
    lhs = float(sum(s * (wall[i] - T_IN) for i, s in leaves))
    rhs = float(np.sum(absorbed)) / pi
    scale = max(abs(lhs), abs(rhs), 1e-30)
    return {"lhs": lhs, "rhs": rhs, "rel": abs(lhs - rhs) / scale}


# ------------------------------------------------------------------- driver
def solve_case(grid, pair, kind, h_base, pi, feed="centre",
               field_tol=1e-8, field_max=20000, outer_tol=1e-7,
               max_iter=200, damping=0.5, t_in=T_IN, renormalise=True):
    """Picard: solid field -> absorbed flux -> wall march -> solid field ...

    `pi = inf` is the pinned limit: the wall is the inlet temperature and the
    call is a single `field.solve_heat_3d` identical to `conjugate_3d.solve`.

    Convergence is declared on the CHANGE in the wall vector, not on the
    march's own delta, and the solid field is always re-solved for the wall
    that is returned -- so `(T, wall)` leaving this function are mutually
    consistent to `outer_tol`.

    `renormalise=True` scales the absorbed distribution by
    `gain = P_inj / (p_chan + p_base)` before it is marched, so tree and
    straight are compared at equal DELIVERED power. The leak D is a property
    of the inherited top-skin stencil and never reaches the coolant, so
    without this the straight mask would look 5% colder than it is fed. The
    gain is reported per case; `renormalise=False` reproduces the raw run.
    """
    mask = pair["tree_mask"] if kind == "tree" else pair["straight_mask"]
    cells = cells_of(mask)
    n = len(cells)
    c = grid // 2
    edges = pair["edges"] if kind == "tree" else None

    def solid(w):
        return F.solve_heat_3d(grid=grid, depth=DEPTH, source_center=(c, c),
                               source_radius=SRC_RADIUS_SYNTHETIC,
                               channels_2d=mask, T_cool=w,
                               channel_top_gap=CHANNEL_TOP_GAP, h_base=h_base,
                               tol=field_tol, max_iter=field_max)

    def march(T):
        a_raw = absorbed_heat(T, mask, h_base)
        total = float(a_raw.sum()) + base_out(T, mask, h_base)
        gain = P_INJ / total if abs(total) > 1e-12 else 1.0
        a = a_raw * gain if renormalise else a_raw
        if kind == "tree":
            w_new, _, _ = march_tree(edges, cells, a, grid, pi, t_in)
        else:
            w_new, _ = march_straight(cells, a, grid, pi, feed, t_in)
        return a, w_new, gain

    wall = np.full(n, float(t_in))
    info = {"iterations": 0, "converged": True, "outer_delta": 0.0,
            "damping_final": damping, "renormalised": bool(renormalise)}
    t0 = time.perf_counter()

    T = solid(wall)
    if not T.converged:
        raise RuntimeError("3-D solid solve did not converge (pinned start)")

    absorbed = absorbed_heat(T.T, mask, h_base)
    info["march_gain"] = P_INJ / (float(absorbed.sum())
                                  + base_out(T.T, mask, h_base))
    if np.isfinite(pi):
        info["converged"] = False
        damp = damping
        prev = np.inf
        for it in range(max_iter):
            absorbed, w_new, gain = march(T.T)
            delta = float(np.max(np.abs(w_new - wall)))
            if delta > prev:
                damp = max(0.05, damp * 0.7)
            else:
                damp = min(damping, damp * 1.1 + 0.01)
            prev = delta
            wall_new = (1.0 - damp) * wall + damp * w_new
            step = float(np.max(np.abs(wall_new - wall)))
            wall = wall_new
            info["iterations"] = it + 1
            info["outer_delta"] = delta
            info["march_gain"] = gain
            T = solid(wall)
            if not T.converged:
                raise RuntimeError(
                    "3-D solid solve did not converge (picard iter %d)" % it)
            if step < outer_tol:
                info["converged"] = True
                break
        info["damping_final"] = damp
        absorbed, _, info["march_gain"] = march(T.T)
    info["solid_iters"] = T.iterations
    info["solid_residual"] = T.residual
    info["seconds"] = time.perf_counter() - t0
    return T, wall, absorbed, info


def diagnostics(T, mask, h_base, wall, absorbed, cells, grid, pi, kind,
                edges=None, feed="centre"):
    """All numbers a reader needs, from ONE converged field.

    The solver works in dimensionless temperature with a 25.0 datum, so every
    kelvin figure is `(solver value - T_IN) * K_SCALE`; the datum is never
    scaled.
    """
    bal = energy_balance(T, mask, h_base)
    rise_c = (float(T[-1].max()) - T_IN) * K_SCALE
    wall_min_c = T_IN + (float(wall.min()) - T_IN) * K_SCALE
    wall_max_c = T_IN + (float(wall.max()) - T_IN) * K_SCALE
    d = {
        "top_max_dimensionless": float(T[-1].max()),
        "top_max_C": T_IN + rise_c,
        "rise_C": rise_c,
        "energy": bal,
        "wall_min_C": wall_min_c,
        "wall_max_C": wall_max_c,
        "coolant_rise_C": wall_max_c - wall_min_c,
        "wall_spread_mK": 1000.0 * (wall_max_c - wall_min_c),
        "wall_spread_percent_of_rise": (100.0 * (wall_max_c - wall_min_c) / rise_c
                                        if rise_c else 0.0),
        "R_th_C_per_W": rise_c / C.TDP_I7_W,
    }
    if np.isfinite(pi):
        d["enthalpy"] = enthalpy_identity(kind, cells, absorbed, wall, pi,
                                          grid, edges=edges, feed=feed)
    return d


def run(grid, pair, kind, h_base, pi, feed="centre", **kw):
    T, wall, absorbed, info = solve_case(grid, pair, kind, h_base, pi, feed, **kw)
    mask = pair["tree_mask"] if kind == "tree" else pair["straight_mask"]
    cells = cells_of(mask)
    edges = pair["edges"] if kind == "tree" else None
    d = diagnostics(T.T, mask, h_base, wall, absorbed, cells, grid, pi, kind,
                    edges=edges, feed=feed)
    d.update({"kind": kind, "feed": feed, "h_base": h_base,
              "Bi": None if h_base is None else round(h_base * F.PITCH_MM, 6),
              "Pi": None if not np.isfinite(pi) else round(pi, 3),
              "flow_lpm": None if not np.isfinite(pi)
              else round(C.lpm(flow_from_pi(pi)), 4),
              "renormalised": info["renormalised"],
              "march_gain": round(info["march_gain"], 6),
              "picard_iters": info["iterations"],
              "picard_converged": info["converged"],
              "picard_damping_final": round(info["damping_final"], 4),
              "outer_delta": info["outer_delta"],
              "solid_iters": info["solid_iters"],
              "solid_residual": info["solid_residual"],
              "seconds": round(info["seconds"], 3)})
    return d


def main():
    global PI_REF
    pair = build_pair(GRID_MAIN)
    PI_REF = pi_from_flow(C.coolant_flow_m3s(C.TDP_I7_W, 5.0))
    pi_list = [PI_REF / 10.0, PI_REF, PI_REF * 10.0]      # 38.1, 381, 3808

    # ---- geometry identity (same construction as Fig. 11) ----------------
    geom = {
        "grid": GRID_MAIN, "depth": DEPTH, "channel_top_gap": CHANNEL_TOP_GAP,
        "tree_cells": pair["n_tree"], "straight_cells": pair["n_straight"],
        "straight_columns": pair["n_columns"],
        "source_cells": pair["source_cells"],
        "source_covered_tree": pair["source_covered_tree"],
        "source_covered_straight": pair["source_covered_straight"],
        "C5": "exact: tree cells == straight cells",
    }

    # ---- self-checks before any physics --------------------------------
    T0, _, _, info0 = solve_case(GRID_MAIN, pair, "tree", 1.0, np.inf,
                                 field_tol=1e-6, field_max=20000)
    cells_t = cells_of(pair["tree_mask"])
    fast = absorbed_heat(T0.T, pair["tree_mask"], 1.0)
    slow = absorbed_heat_loop(T0.T, pair["tree_mask"], 1.0)
    dual = float(np.max(np.abs(fast - slow)) / max(abs(slow).max(), 1e-30))
    bal0 = energy_balance(T0.T, pair["tree_mask"], 1.0)

    # ---- R15: Pi -> inf must reproduce conjugate_3d bit-for-bit ---------
    ref = json.loads((OUT / "dimension_sensitivity.json").read_text("utf-8"))
    ref_bi1 = next(k for k in ref["runs"] if k["h_base"] == 1.0)
    T_case1, _, _, _ = solve_case(GRID_MAIN, pair, "straight", 1.0, np.inf,
                                  field_tol=1e-6, field_max=20000)
    reg = {
        "tree": {"ours": float(T0.T[-1].max()), "reference": ref_bi1["tree_top_C"],
                 "abs_diff": abs(float(T0.T[-1].max()) - ref_bi1["tree_top_C"])},
        "straight": {"ours": float(T_case1.T[-1].max()),
                     "reference": ref_bi1["straight_top_C"],
                     "abs_diff": abs(float(T_case1.T[-1].max())
                                     - ref_bi1["straight_top_C"])},
    }
    # the stored reference carries 6 decimals, so compare at that resolution
    assert (round(reg["tree"]["ours"], 6) == round(reg["tree"]["reference"], 6)
            and round(reg["straight"]["ours"], 6)
            == round(reg["straight"]["reference"], 6)), (
        "R15 failed: the Pi->inf limit must reproduce conjugate_3d to 1e-6")

    # ---- main sweep: Bi x Pi x geometry ---------------------------------
    main_cases = []
    for h_base in (0.0, 1.0, None):
        pair_h = []
        for pi in (np.inf, pi_list[1], pi_list[0]):
            r_tree = run(GRID_MAIN, pair, "tree", h_base, pi)
            r_str = run(GRID_MAIN, pair, "straight", h_base, pi, feed="centre")
            pair_h.append({
                "Pi": r_tree["Pi"], "flow_lpm": r_tree["flow_lpm"],
                "tree": r_tree, "straight": r_str,
                "dT_tree_minus_straight_C": r_tree["rise_C"] - r_str["rise_C"],
            })
        main_cases.append({"h_base": h_base,
                           "Bi": pair_h[0]["tree"]["Bi"],
                           "runs": pair_h})

    # ---- high-flow decile (does the tree win at high flow?) -------------
    hi_flow = []
    for pi in (pi_list[2],):
        r_tree = run(GRID_MAIN, pair, "tree", 0.0, pi)
        r_str = run(GRID_MAIN, pair, "straight", 0.0, pi, feed="centre")
        hi_flow.append({"Pi": r_tree["Pi"], "flow_lpm": r_tree["flow_lpm"],
                        "tree": r_tree, "straight": r_str,
                        "dT_tree_minus_straight_C": r_tree["rise_C"] - r_str["rise_C"]})

    # ---- edge-fed straight bank (usual cold-plate layout) ---------------
    edge = []
    for h_base in (0.0, 1.0):
        r_str = run(GRID_MAIN, pair, "straight", h_base, pi_list[0], feed="edge")
        r_ctr = run(GRID_MAIN, pair, "straight", h_base, pi_list[0], feed="centre")
        r_tree = run(GRID_MAIN, pair, "tree", h_base, pi_list[0])
        edge.append({"h_base": h_base, "Bi": r_str["Bi"], "Pi": r_str["Pi"],
                     "centre": r_ctr, "edge": r_str, "tree": r_tree,
                     "dT_edge_minus_centre_C": r_str["rise_C"] - r_ctr["rise_C"],
                     "dT_tree_minus_edge_C": r_tree["rise_C"] - r_str["rise_C"]})

    # ---- grid check ------------------------------------------------------
    # Run at BOTH the calibration flow and the low flow, so that the reported
    # grid effect is a like-for-like comparison at the same Pi (a grid-40
    # number taken at Pi/10 minus a grid-30 number taken at Pi would be a
    # flow effect, not a resolution effect).
    pair_c = build_pair(GRID_CHECK)
    grid_check = []
    for h_base in (0.0, 1.0):
        for pi in (pi_list[1], pi_list[0]):
            r_tree = run(GRID_CHECK, pair_c, "tree", h_base, pi)
            r_str = run(GRID_CHECK, pair_c, "straight", h_base, pi)
            grid_check.append({"h_base": h_base, "Bi": r_tree["Bi"],
                               "Pi": r_tree["Pi"],
                               "tree_cells": pair_c["n_tree"],
                               "straight_cells": pair_c["n_straight"],
                               "tree": r_tree, "straight": r_str,
                               "dT_tree_minus_straight_C":
                                   r_tree["rise_C"] - r_str["rise_C"]})

    # ---- raw vs equal-delivery at the reference operating point ---------
    ref_closure = []
    for ren in (False, True):
        r_tree = run(GRID_MAIN, pair, "tree", 1.0, pi_list[1], renormalise=ren)
        r_str = run(GRID_MAIN, pair, "straight", 1.0, pi_list[1],
                    feed="centre", renormalise=ren)
        ref_closure.append({
            "renormalise": ren,
            "tree": r_tree, "straight": r_str,
            "dT_tree_minus_straight_C": r_tree["rise_C"] - r_str["rise_C"],
        })

    # ---- assertions over every run ---------------------------------------
    all_runs = ([row[k] for case in main_cases for row in case["runs"]
                 for k in ("tree", "straight")]
                + [row[k] for row in hi_flow for k in ("tree", "straight")]
                + [row[k] for row in edge for k in ("centre", "edge", "tree")]
                + [row[k] for row in grid_check for k in ("tree", "straight")]
                + [row[k] for row in ref_closure for k in ("tree", "straight")])
    worst_closure = max(r["energy"]["closure_rel"] for r in all_runs)
    worst_delivery = max(r["energy"]["residual_rel"] for r in all_runs)
    assert worst_closure < 1e-3, "energy closure failed: %.3e" % worst_closure
    assert all(r["picard_converged"] for r in all_runs), (
        "a Picard loop did not converge")

    # ---- verdict ---------------------------------------------------------
    # `Pi` is stored rounded to 3 decimals, so select by position (index 1 of
    # every sweep is PI_REF) rather than by an exact float match.
    prim = next(row for row in main_cases if row["h_base"] == 1.0)["runs"][1]
    assert abs(prim["Pi"] - round(PI_REF, 3)) < 1e-9, "index 1 is not PI_REF"
    dts = [r["dT_tree_minus_straight_C"] for row in main_cases for r in row["runs"]]
    sign_stable = all(d <= 0 for d in dts) or all(d >= 0 for d in dts)

    def d_main(h_base, idx):
        """Grid-%d difference at sweep position `idx` (0=inf, 1=Pi_ref, 2=low)."""
        row = next(c for c in main_cases if c["h_base"] == h_base)
        return row["runs"][idx]["dT_tree_minus_straight_C"]

    def d_coarse(h_base, pi):
        """Grid-%d difference at the same Pi."""
        row = next(r for r in grid_check
                   if r["h_base"] == h_base
                   and abs(r["Pi"] - round(pi, 3)) < 1e-9)
        return row["dT_tree_minus_straight_C"]

    # Like-for-like resolution effect: same Pi on both grids.
    shifts = {}
    for tag, idx, pi in (("Pi_ref", 1, PI_REF), ("Pi_low", 2, pi_list[0])):
        shifts[tag] = [d_coarse(h, pi) - d_main(h, idx) for h in (0.0, 1.0)]
    shift_ref = max(abs(s) for s in shifts["Pi_ref"])
    verdict = (
        "3-D conduction with a 1-D coolant march, %d x %d x %d cells, equal "
        "occupancy (%d = %d) and equal source coverage (%d/%d both). At the "
        "calibration flow %.3f L/min (Pi = %.1f, coolant rise %.2f C for "
        "%.0f W) the peak difference at Bi=1 is %+.4f C on a %+.2f C total "
        "coolant rise; over Bi in {0, 1, inf} and Pi in {%.0f, %.1f, %.0f} "
        "the sign is %s and the extremes are %+.4f / %+.4f C. Rebuilding at "
        "grid %d at fixed flow moves the difference by at most %.1e C at the "
        "calibration flow (%+.2f -> %+.2f C at Bi=1) and by %.1e C at the "
        "lowest flow. The exact "
        "identity P_inj = P_chan + P_base + D, summed over interior cells only "
        "(the solver closes the lateral boundaries with mirror copies), closes "
        "to %.1e relative on every run; the heat D escaping through the "
        "nominally adiabatic top skin is %.3f%% of P_inj for the "
        "tree mask and %.2f%% for the straight mask, so the march is run at "
        "equal DELIVERED power (gain reported per case) and the raw run is "
        "reported alongside, where the same difference is %+.4f C."
        % (GRID_MAIN, GRID_MAIN, DEPTH, pair["n_tree"], pair["n_straight"],
           pair["source_covered_tree"], pair["source_cells"],
           prim["tree"]["flow_lpm"], PI_REF, prim["tree"]["coolant_rise_C"],
           C.TDP_I7_W, prim["dT_tree_minus_straight_C"],
           prim["tree"]["coolant_rise_C"], pi_list[0], PI_REF, pi_list[2],
           "stable" if sign_stable else "NOT stable",
           min(dts), max(dts), GRID_CHECK, shift_ref,
           d_main(1.0, 1), d_coarse(1.0, PI_REF),
           max(abs(s) for s in shifts["Pi_low"]), worst_closure,
           100.0 * prim["tree"]["energy"]["residual_rel"],
           100.0 * prim["straight"]["energy"]["residual_rel"],
           ref_closure[0]["dT_tree_minus_straight_C"]))

    out = {
        "model": ("3-D steady conduction (7-point Laplacian, tree/straight "
                  "masks identical to dimension_sensitivity.json) coupled to "
                  "a 1-D coolant march; one wall temperature per channel "
                  "column; no velocity field is solved, so this is NOT CFD"),
        "geometry": geom,
        "t_inlet_C": T_IN,
        "pi_definition": "Pi = rho*cp*Qdot/(k*h); dT*_n = h*_n/(Pi*share_n)",
        "physical_anchor": {
            "pitch_mm": round(PITCH_M / C.SI, 6),
            "k_W_mK": K_SI, "rho_cp_J_m3K": RHO_CP,
            "power_W": C.TDP_I7_W,
            "q_per_source_cell_W": Q_CELL_W,
            "K_per_solver_unit": K_SCALE,
            "note": ("K_SCALE = q_cell/(k*h) because the source sits on ONE "
                     "layer of the block. The 3-D block is 27x27x9 mm against "
                     "the 2-D slab's 45x45x5 mm, so its R_th is NOT the "
                     "section 4.5 value and the two must not be swapped."),
            "pi_reference": PI_REF,
            "flow_reference_lpm": C.lpm(flow_from_pi(PI_REF)),
        },
        "self_checks": {
            "absorbed_vectorised_vs_loop_rel": dual,
            "energy_balance_pinned_tree": bal0,
            "R15_pi_infinity": reg,
            "worst_closure_rel": worst_closure,
            "worst_delivery_gap_rel": worst_delivery,
        },
        "energy_accounting": {
            "identity": "P_inj = P_chan + P_base_out + D",
            "summation_domain": (
                "interior cells only, y and x in 1..grid-2. field.solve_heat_3d "
                "closes the four sides with mirror copies (Tn[:,0,:]=Tn[:,1,:] "
                "etc.), so rows and columns 0 and grid-1 are ghosts that carry "
                "no equation and duplicate a real cell; a channel<->solid face "
                "is counted only when the SOLID side is interior. Including the "
                "ghosts double-counted faces and broke the identity at 7.2e-2; "
                "excluding them closes it to %.1e over the whole sweep."
                % worst_closure),
            "D": ("leak on solid-solid faces of the top skin: "
                  "field.solve_heat_3d couples z=9 to z=8 with weight 2 in the "
                  "skin's equation and weight 1 in the neighbour's, so those "
                  "faces do not cancel"),
            "bias": ("D sits only on solid-solid faces; the peak is above the "
                     "source, i.e. under a channel cell, so the peak is not "
                     "the quantity D biases -- the coolant load is"),
            "treatment": ("the march renormalises the absorbed distribution "
                          "to P_inj (renormalise=True), so tree and straight "
                          "are compared at equal delivered power; the raw run "
                          "is reported in closure_sensitivity"),
        },
        "closure_sensitivity": ref_closure,
        "main_sweep": main_cases,
        "high_flow": hi_flow,
        "edge_feed_sensitivity": edge,
        "grid_check": grid_check,
        "verdict": verdict,
    }
    (OUT / "conjugate_3d_flow.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8",
        newline="\n")

    print("wrote outputs/conjugate_3d_flow.json")
    print("geometry: %d/%d cells, coverage %d/%d both, straight %d columns"
          % (pair["n_tree"], pair["n_straight"], pair["source_covered_tree"],
             pair["source_cells"], pair["n_columns"]))
    print("self-check absorbed rel=%.1e, closure rel=%.1e, R15 diff=%.1e / %.1e"
          % (dual, bal0["closure_rel"], reg["tree"]["abs_diff"],
             reg["straight"]["abs_diff"]))
    print("worst closure rel=%.1e, worst delivery gap (D/P_inj)=%.2f%%"
          % (worst_closure, 100.0 * worst_delivery))
    print("Pi_ref = %.2f (%.3f L/min), K = %.2f K/unit"
          % (PI_REF, C.lpm(flow_from_pi(PI_REF)), K_SCALE))
    for row in main_cases:
        print("  Bi=%-5s" % row["Bi"])
        for r in row["runs"]:
            # Pi = inf (the pinned limit) stores None for Pi and flow
            pi_txt = "inf" if r["tree"]["Pi"] is None else "%.1f" % r["tree"]["Pi"]
            flow_txt = ("pinned" if r["tree"]["flow_lpm"] is None
                        else "%.3f L/min" % r["tree"]["flow_lpm"])
            print("    Pi=%-8s %-11s tree=%8.3f C straight=%8.3f C "
                  "dT=%+.4f C cool_rise=%6.2f C gain=%.4f it=%d"
                  % (pi_txt, flow_txt,
                     r["tree"]["top_max_C"], r["straight"]["top_max_C"],
                     r["dT_tree_minus_straight_C"],
                     r["tree"]["coolant_rise_C"], r["tree"]["march_gain"],
                     r["tree"]["picard_iters"]))
    for row in ref_closure:
        print("  reference Bi=1: renormalise=%-5s dT=%+.4f C "
              "(gain tree=%.4f straight=%.4f)"
              % (row["renormalise"], row["dT_tree_minus_straight_C"],
                 row["tree"]["march_gain"], row["straight"]["march_gain"]))
    for r in hi_flow:
        print("  high flow Pi=%.0f dT=%+.4f C" % (r["Pi"], r["dT_tree_minus_straight_C"]))
    for r in edge:
        print("  edge feed Bi=%s: edge-centre=%+.3f C, tree-edge=%+.4f C"
              % (r["Bi"], r["dT_edge_minus_centre_C"], r["dT_tree_minus_edge_C"]))
    for r in grid_check:
        print("  grid %d Bi=%s Pi=%.1f dT=%+.4f C"
              % (GRID_CHECK, r["Bi"], r["Pi"],
                 r["dT_tree_minus_straight_C"]))
    print(verdict)


if __name__ == "__main__":
    main()
