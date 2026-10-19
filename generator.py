"""Route A: constraint-driven channel-network GENERATOR.

The project's `grow.py:grow_tree` takes `max_nodes` as a free input and
returns whatever tree fits that budget. That single free parameter is what
made every "tree vs control" verdict budget-dependent (REPORT.md §5 items
8-10; paper §15.5): the answer changes with the budget, and the budget was
never derived from anything.

This module removes that freedom. The design point is now an OUTPUT of a
constraint problem, not an input:

  C1  ADMISSIBILITY (thermal)  -- the tree must physically enter the
      footprint of every chip. This is the `block_to_tree == 0` gate of
      `multi_source.tree_metrics`, i.e. the fairness precondition the
      project already enforces everywhere else.

  C2  GEOMETRY (manufacturing) -- no channel may be wider than the grid
      pitch. Paper §17 item 6 records that the model's 1.0 mm channels on
      a 0.9 mm pitch literally overlap and that this "cannot be fixed by
      rescaling". Under Murray's law r = r0 * N^(1/3) the ROOT is the
      widest tube, so this constraint does not cap the leaf count at a
      fixed r0 -- it DERIVES the r0 that makes a given leaf count
      buildable: r0 = pitch / N_leaves^(1/3). (Used the other way round it
      makes every design infeasible: calibrate.report() measures the
      project's own 61-leaf tree at r_root = 1.6661 mm > 0.9 mm pitch,
      so the historical tree violates C2. That is precisely the defect
      §17 item 6 records.)

  C3  HYDRAULIC BUDGET         -- the demand-driven pressure drop must
      stay inside the pump's shut-off head, evaluated on the SAME root-
      to-leaf convention (`calibrate.tree_dp_pa`, convention A) that the
      paper's authoritative 0.0802 kPa uses. The serial sum is not used:
      that is the 80x over-count retired in paper §10.11.

The deliverable is therefore a PARETO FRONT in (T_max, dp), not a single
design. Along that front the paper's verdict "the advantage depends on the
budget" becomes measurable: the budget is now derived, and both endpoints
have hard bounds (C1 from below, C2 from above, C3 on dp).

NOT included, deliberately, because the paper records both as open:
  * junction loss K (protocol v5, not yet run)
  * the 0.2-0.5 mm fin-pitch r^4 correction (1.0-39.1x, §17 item 4)
So the reported dp is the pure-viscous term, exactly like the paper's
authoritative number. On the measured fronts this leaves only 1.2-1.5x of
headroom below the pump limit at the coldest (eps -> 0) design, which both
omitted corrections would consume. A design point for pump selection must
therefore be taken at a NON-ZERO thermal tolerance -- see
`knee_sensitivity`, not the eps=0 column.
"""
from __future__ import annotations

import numpy as np

import calibrate as C
import field as F
import grow as G
import radius as Ra
import spread_source_scan as SSS
import verify as V


# --- Constraint sources, all from the repository -------------------------
# Pump shut-off head: Alphacool DDC-1RT datasheet, paper reference [15].
# NOT the "20-100 kPa" range the paper retires as unsourced (§6.3).
PUMP_SHUTOFF_PA = 31700.0

# The dimensionless solver pitch is a DEFINITIONAL constant; a real-unit
# dp must use the mapped pitch. calibrate.tree_dp_pa raises if we pass
# the wrong one, which is the guard we want.
GRID_MM = C.paper_grid_mm(50)


def max_feasible_leaves(r0_mm: float, pitch_mm: float) -> int:
    """Largest leaf count whose ROOT still fits inside one cell.

    Murray: r_root = r0 * N_leaves^(1/3). C2 requires r_root <= pitch_mm.
    """
    return int(np.floor((pitch_mm / r0_mm) ** 3))


def max_r0_for_leaves(n_leaves: int, pitch_mm: float) -> float:
    """Inverse of `max_feasible_leaves`: the largest leaf radius that keeps
    an `n_leaves`-leaf Murray tree inside one cell.

    This is the constraint's useful direction. `calibrate.report()` measures
    the project's own 61-leaf tree at r_root = 1.6661 mm on a 0.9 mm pitch,
    i.e. the historical tree VIOLATES C2 -- that is exactly the
    self-inconsistency paper §17 item 6 records ("cannot be fixed by
    rescaling"). So C2 cannot be used to select a leaf count at fixed r0
    (it would make every design infeasible); it is used here to derive the
    r0 that makes a GIVEN leaf count manufacturable.

    `n_leaves` MUST be the tree's ACTUAL leaf count, not the target used to
    size the node budget: `grow_tree` stops on the heap, so a 27-node
    budget can produce far more leaves than requested and the root radius
    follows the realised count, not the asked-for one. Passing a target
    here silently under-estimates r_root and lets C2 pass on geometry that
    does not exist. `n_leaves_of` recovers the realised count.
    """
    if n_leaves < 1:
        raise ValueError("n_leaves must be >= 1")
    return pitch_mm / (n_leaves ** (1.0 / 3.0))


def n_leaves_of(edges: list[tuple[int, int]]) -> int:
    """Realised terminal-cell count of an edge list.

    Counted directly (a node that is nobody's parent), NOT as
    len(children) -- a node with an empty child list simply does not appear
    in the children map, so `len(children)` returns the fork count and
    would read 0 leaves for any tree whose terminals were never expanded.
    """
    if not edges:
        return 0
    parents = {p for p, _ in edges}
    children = {c for _, c in edges}
    # A terminal is a node that is never a parent. The root is a parent by
    # construction, so a single-edge tree has exactly one terminal.
    return len(children - parents)


def node_budget_from_leaves(n_leaves: int) -> int:
    """Node count needed to realise `n_leaves` terminal cells.

    A Prim tree on a 4-neighbour grid branches emergently; the project's
    own histogram (calibrate.report, convention A) measured 61 leaves /
    399 segments, i.e. ~6.5 cells per leaf on the real footprint. We keep
    that measured ratio rather than inventing one.
    """
    return int(np.ceil(n_leaves * 399.0 / 61.0))


def pareto_front(designs: list[dict]) -> list[dict]:
    """Non-dominated set in (T_max, dp) space, both minimised.

    `designs` must already be feasibility-filtered. A design is dominated
    when another is no worse in BOTH objectives and strictly better in at
    least one. Designs with identical (T_max, dp) do not dominate each
    other, so exact ties both survive -- that is the wanted behaviour,
    because they represent the same performance at different budgets.
    """
    front = []
    for a in designs:
        dominated = False
        for b in designs:
            if b is a:
                continue
            if (b["T_max_c"] <= a["T_max_c"] and b["dp_pa"] <= a["dp_pa"]
                    and (b["T_max_c"] < a["T_max_c"]
                         or b["dp_pa"] < a["dp_pa"])):
                dominated = True
                break
        if not dominated:
            front.append(a)
    return sorted(front, key=lambda d: (d["dp_pa"], d["T_max_c"]))


def select_knee(front: list[dict], t_tol_c: float = 0.01) -> dict:
    """Epsilon-constrained knee selection.

    Within `t_tol_c` of the best thermal performance available on the front,
    take the design with the lowest pressure drop. Ties broken by the
    smaller node budget.

    Why this rule and not a weighted sum: a weight on (degC vs Pa) is
    arbitrary and silently decides the answer, which is exactly the kind of
    free parameter this module exists to remove. A thermal tolerance is
    something a designer can state and defend ("I will accept 0.01 K worse
    if it halves the pump"), and it makes the selection reproducible.

    WARNING on the direction of the trade. `t_tol_c` is the price paid in
    temperature for a saving in dp, so a SMALL tolerance favours the
    coldest design and a LARGE tolerance favours the cheapest one. The
    module therefore reports the knee at several tolerances (see
    `knee_sensitivity`) instead of picking one silently: with 0.01 K the
    generator degenerates into "lowest T_max at any dp cost", which is not
    a design decision.
    """
    if not front:
        raise ValueError("empty Pareto front")
    t_best = min(d["T_max_c"] for d in front)
    cand = [d for d in front if d["T_max_c"] <= t_best + t_tol_c]
    return min(cand, key=lambda d: (d["dp_pa"], d["budget"], d["T_max_c"]))


def knee_sensitivity(front: list[dict],
                     tolerances_c=(0.01, 0.1, 0.5, 1.0, 2.0, 5.0)) -> list[dict]:
    """The knee at several thermal tolerances, so the selection rule is
    inspectable rather than hidden in one magic number.

    Returns one row per tolerance. A tolerance whose knee differs from the
    previous one marks a genuine decision boundary; a run where the knee is
    identical for every tolerance means the front has a single dominant
    design and the tolerance is irrelevant.
    """
    rows = []
    for tol in tolerances_c:
        k = select_knee(front, t_tol_c=tol)
        rows.append({
            "t_tol_c": tol,
            "n_leaves": k["n_leaves"],
            "budget": k["budget"],
            "T_max_c": k["T_max_c"],
            "dp_pa": k["dp_pa"],
            "dp_vs_min_front": (k["dp_pa"]
                                / min(d["dp_pa"] for d in front)),
            "T_max_penalty_c": (k["T_max_c"]
                                - min(d["T_max_c"] for d in front)),
        })
    return rows


def control_front(centers, grid: int = 50, radius: float = F.SRC_RADIUS_REAL,
                  powers=None, dT_c: float = 5.0, power_w: float = 253.0,
                  kind: str = "radial", verbose: bool = False) -> dict:
    """Pareto front of a CONTROL topology under the SAME constraints as the
    tree, so the two fronts are comparable rather than merely adjacent.

    `kind`:
      "radial"  -- one straight pipe per chip, marching away from it
                   (`verify.radial_group_pinned`). This is the project's
                   own control, so the comparison reuses a topology whose
                   fairness rules were already corrected four times.
      "lattice" -- a uniform grid of straight channels spanning the plate,
                   at a swept pitch (`verify.straight_group`).

    The controls are held to the tree's constraints:

      C1  every chip footprint must be entered (block_to_tree == 0);
      C3  real-unit dp on convention A must stay under the pump head.

    C2 (root radius <= pitch) has NO analogue for a straight pipe: a pipe
    has one radius, no Murray junction, so the constraint is vacuous. It is
    reported as satisfied rather than silently dropped, so a caller
    comparing the two fronts can see which constraint each side was
    actually tested against.

    The resource convention is the project's own: equal PINNED cells and
    equal total cross-section, i.e. `radial_group_pinned(target_pinned,
    total_area_mm2)` with the tree's realised values. Sweeping the pinned
    target is what generates the front.

    MEASURED (2026-10-19, 3-chip layout): the control front collapses to
    a SINGLE point -- on a straight-pipe family T_max and dp improve
    TOGETHER with the budget (more cells = more parallel paths AND more
    total cross-section), so the largest budget dominates everything.
    That is the structural difference from the tree, whose dp RISES with
    budget (Murray's r^4 on ever-finer leaves): the tree has a genuine
    two-objective trade, the straight control has none. The front is
    therefore degenerate BY MEASUREMENT, not by construction error.

    Also measured: the radial control FAILS C1 below target=200 on this
    layout. `radial_group_pinned` allocates its cell budget to chips in
    cluster order and its bisection trims from the far ends, so at small
    budgets the first chip's pipes consume everything and later chips get
    no channel at all (measured: block distance 18 cells, 16, 13 for
    targets 25/100/150). That is a construction artifact of the control
    builder, not a physical infeasibility, and the C1 gate filters it
    correctly -- but it means the control's feasible range starts at a
    budget the tree already meets at 55 leaves.

    dp is computed in REAL units with the SAME control convention the
    paper's authoritative comparison uses -- `calibrate.report()` (line
    ~561): each occupied cell is one parallel full-span channel,
    r_cell = sqrt(A_total / (n_cells * pi)), flow q_total / n_cells per
    channel, L = plate length, everything converted mm -> m by `calibrate.SI`.
    It is NOT `verify.poiseuille_dp` (the dimensionless toy convention,
    MU = 1, Q_TOTAL = 1, pitch = 1.0 mm): mixing the two would put the
    two fronts on different axes. The convention is crude (a 20-cell pipe
    is costed as 20 parallel full-span channels, i.e. an upper-bound-ish
    estimate -- REPORT.md §17 keeps the project's dp conclusions as
    bounds, not absolutes), but it is the convention every published
    tree-vs-control dp number in this repository was produced with, so
    the generator's fronts stay on the same axes as the paper.
    """
    ok, why = SSS.layout_is_valid(centers, grid=grid, radius=radius)
    if not ok:
        raise ValueError(f"layout inadmissible (N4b): {why}")

    T, src, strength = SSS.solve_spread(centers, grid=grid, radius=radius,
                                        powers=powers)
    q_m3s = C.coolant_flow_m3s(power_w * len(centers), dT_c=dT_c)

    # Pinned-cell targets to sweep. Anchored on the tree's own range so the
    # two fronts overlap in the resource dimension.
    pinned_grid = [25, 50, 100, 150, 200, 300, 400, 500, 600, 700, 800]

    sweep = []
    for target in pinned_grid:
        if kind == "radial":
            # Equal cross-section is derived from the pinned target with
            # the same 1-cell-per-node convention the tree uses, so both
            # sides spend the same material.
            area_mm2 = target * np.pi * (GRID_MM ** 2)
            g = V.radial_group_pinned(T, src, target, area_mm2, grid, grid,
                                      strength=strength)
            # True pipe cells, INCLUDING the ones inside chip blocks that
            # the fairness rule leaves unpinned (returned by the builder).
            ccells = g.channel_cells or []
        elif kind == "lattice":
            # A uniform channel grid: `n_channels` straight channels, each
            # spanning the plate, sharing the same total cross-section.
            n_ch = max(1, target // grid)
            area_mm2 = target * np.pi * (GRID_MM ** 2)
            g = V.straight_group(T, src, n_ch, area_mm2, grid, grid,
                                 strength=strength)
            # straight_group returns no cell list, and its pinned mask
            # CANNOT stand in: the cells where a channel crosses a chip
            # block are never pinned, so the mask has a gap exactly where
            # the channel enters the chip and the C1 gate below would
            # read "did not enter" for a channel that passes straight
            # through. Rebuild the columns analytically instead -- the
            # construction is deterministic (centred columns).
            half = n_ch // 2
            cx0 = grid // 2
            xs = [cx0 - half + k for k in range(n_ch)
                  if 0 <= cx0 - half + k < grid]
            if not xs:
                xs = [cx0]
            ccells = [(y, x) for x in xs for y in range(grid)]
        else:
            raise ValueError(f"unknown control kind: {kind}")

        # C1: does the control enter every chip footprint?
        r_blk = int(radius)
        block_d = []
        for cy, cx in centers:
            cyi, cxi = int(round(cy)), int(round(cx))
            blk = [(y, x) for y in range(cyi - r_blk, cyi + r_blk + 1)
                   for x in range(cxi - r_blk, cxi + r_blk + 1)
                   if 0 <= y < grid and 0 <= x < grid]
            if blk:
                block_d.append(min(abs(y - cy2) + abs(x - cx2)
                                   for y, x in blk for cy2, cx2 in ccells))
        c1_ok = (max(block_d) if block_d else 1) == 0

        # C3 in real units, calibrate.report's control convention:
        # n_cells parallel full-span channels of radius r_cell, each
        # carrying q_total / n_cells. Dimensions must go through SI
        # (mm -> m); without it the r^4 term is off by 1e12 and the
        # whole expression by 1e9, which is what made C3 vacuously true
        # in the first draft of this function.
        n_cells = max(1, len(ccells))
        r_cell_mm = float(np.sqrt(area_mm2 / (n_cells * np.pi)))
        L_m = grid * GRID_MM * C.SI
        dp_pa = (8.0 * C.MU_WATER * L_m * (q_m3s / n_cells)
                 / (np.pi * (r_cell_mm * C.SI) ** 4))

        sweep.append({
            "kind": kind,
            "target_pinned": target,
            # Uniform interface with the tree's sweep rows so select_knee /
            # knee_sensitivity / pareto_front work on either side. The
            # control's budget knob IS the pinned target; it has no leaves.
            "budget": target,
            "n_leaves": None,
            "pinned": int(g.pinned_cells),
            "n_channel_cells": len(ccells),
            "r_cell_mm": r_cell_mm,
            "dp_pa": dp_pa,
            "T_max_c": g.T_max,
            "T_mean_solid_c": g.T_mean_solid,
            "hotspot_area_mm2": g.hotspot_area,
            "C1_enters_all_chips": c1_ok,
            "C2_root_fits_cell": True,   # vacuous for a straight pipe
            "C3_within_pump": dp_pa <= PUMP_SHUTOFF_PA,
        })
        if verbose:
            print(f"  [{kind}] pinned_target={target:4d} got={g.pinned_cells:4d} "
                  f"r={r_cell_mm:.4f} dp={dp_pa:9.1f} Pa "
                  f"T_max={g.T_max:7.3f} C1={int(c1_ok)} C3={int(dp_pa <= PUMP_SHUTOFF_PA)}")

    feasible = [s for s in sweep if s["C1_enters_all_chips"]
                and s["C3_within_pump"]]
    if not feasible:
        raise ValueError(
            f"control kind={kind}: no design satisfies C1 and C3 "
            f"(swept {len(sweep)} pinned targets).")

    front = pareto_front(feasible)
    return {
        "kind": kind,
        "front": front,
        "knee": select_knee(front),
        "knee_sensitivity": knee_sensitivity(front),
        "n_feasible": len(feasible),
        "sweep": sweep,
        "c2_summary": {
            "n_on_front": len(front),
            "n_C2_ok_on_front": len(front),
            "all_satisfy_C2": True,
            "note": ("C2 is vacuous for a straight pipe (no Murray "
                     "junction, single radius); reported as satisfied so "
                     "the constraint each side was tested against stays "
                     "visible"),
        },
        "inputs": {
            "centers": [list(c) for c in centers],
            "grid": grid, "radius": radius, "powers": powers,
            "power_w": power_w, "dT_c": dT_c, "q_m3s": q_m3s,
            "q_lpm": C.lpm(q_m3s), "grid_mm": GRID_MM,
        },
    }


def control_front_total(centers, grid: int = 50,
                        radius: float = F.SRC_RADIUS_REAL, powers=None,
                        dT_c: float = 5.0, power_w: float = 253.0,
                        kind: str = "radial", verbose: bool = False) -> dict:
    """C5 convention: control front matched on TOTAL channel cells.

    The pinned-matched front (`control_front`) spends more total
    occupancy on the control side than the tree's maximum budget, so a
    "control beats tree" verdict there is only a weak statement. This is
    the strict version: the control's TOTAL channel footprint equals the
    tree's, cell for cell, at every budget (`verify.radial_group_total`
    / `verify.lattice_group_total`). Both sides then occupy exactly the
    same number of cells; only the ARRANGEMENT differs.

    The sweep is over total-cell targets, anchored on the tree's
    realised range (a Prim tree spends ~6.5 cells per leaf, so the
    natural anchors are 100..1309). dp uses the same calibrate.report
    control convention as `control_front` (per-cell parallel channel,
    SI-converted), with n_cells = the TOTAL cell count -- that is the
    point of the C5 basis.

    C1 is evaluated on the control's TRUE channel cells (block cells
    included, they are occupancy even when not pinned). C2 is vacuous as
    in `control_front`.

    MEASURED (2026-10-19): on 3+ chip layouts `radial_group_total` FAILS
    C1 at EVERY swept target -- its cell stream is built chip-by-chip in
    cluster order (each chip contributes full-span rows/columns), so the
    first two chips consume the entire target before later chips get any
    cells (measured block distances 14/8/3 for targets 200/800/1309 on
    the 3-chip layout; 2 and 4 on the 4-chip layout). That is a stream-
    ordering artifact of the builder, not a physical infeasibility --
    the missing chip's rows would fit inside the plate with room to
    spare. `lattice_group_total` has no such defect (rows/cols are
    global) and passes C1 everywhere. The radial C5 front therefore only
    exists for 1-2 chip layouts, and the C5 comparison for 3-4 chips
    rests on the lattice alone.
    """
    ok, why = SSS.layout_is_valid(centers, grid=grid, radius=radius)
    if not ok:
        raise ValueError(f"layout inadmissible (N4b): {why}")

    T, src, strength = SSS.solve_spread(centers, grid=grid, radius=radius,
                                        powers=powers)
    q_m3s = C.coolant_flow_m3s(power_w * len(centers), dT_c=dT_c)

    # Total-cell targets. The tree's sweep covers 157..1309 cells
    # (measured on the 2/3/4-chip layouts), so anchor there. 1309 is
    # also below the lattice saturation point (grid^2 = 2500).
    total_grid = [100, 150, 200, 300, 400, 500, 600, 700, 800, 900,
                  1000, 1100, 1200, 1309]

    sweep = []
    for target in total_grid:
        area_mm2 = target * np.pi * (GRID_MM ** 2)
        if kind == "radial":
            g = V.radial_group_total(T, src, target, area_mm2, grid, grid,
                                     strength=strength)
            ccells = g.channel_cells or []
        elif kind == "lattice":
            g = V.lattice_group_total(T, src, target, area_mm2, grid, grid,
                                      strength=strength)
            # lattice_group_total returns no cell list; its geometry is
            # deterministic (rows+cols at the chosen pitch plus centre-
            # out completion). The pinned mask undercounts by the block
            # cells, so use total_area convention: n_cells == target by
            # construction, and the cells are the full line set.
            ccells = []   # filled below from the group's own geometry
        else:
            raise ValueError(f"unknown control kind: {kind}")

        # C1 on TRUE occupancy. For the lattice, reconstruct the line
        # set: rows/cols at every pitch up to the completion density.
        if not ccells:
            cellset = set()
            # densest possible is pitch 1; the builder chose the smallest
            # pitch with total(p) <= target. Recover it by bisection on
            # the combinatorial count (no field solve needed).
            def lines(p):
                rows = list(range(0, grid, p))
                cols = list(range(0, grid, p))
                cs = set()
                for y in rows:
                    cs.update((y, x) for x in range(grid))
                for x in cols:
                    cs.update((y, x) for y in range(grid))
                return cs
            lo, hi, chosen = 1, grid, None
            while lo <= hi:
                mid = (lo + hi) // 2
                if len(lines(mid)) <= target:
                    chosen = mid
                    hi = mid - 1
                else:
                    lo = mid + 1
            cellset = lines(chosen) if chosen else lines(1)
            ccells = sorted(cellset)

        r_blk = int(radius)
        block_d = []
        for cy, cx in centers:
            cyi, cxi = int(round(cy)), int(round(cx))
            blk = [(y, x) for y in range(cyi - r_blk, cyi + r_blk + 1)
                   for x in range(cxi - r_blk, cxi + r_blk + 1)
                   if 0 <= y < grid and 0 <= x < grid]
            if blk:
                block_d.append(min(abs(y - cy2) + abs(x - cx2)
                                   for y, x in blk for cy2, cx2 in ccells))
        c1_ok = (max(block_d) if block_d else 1) == 0

        # C3, same per-cell parallel convention as control_front, with
        # n_cells = TOTAL cells (the C5 resource basis).
        n_cells = max(1, len(ccells))
        r_cell_mm = float(np.sqrt(area_mm2 / (n_cells * np.pi)))
        L_m = grid * GRID_MM * C.SI
        dp_pa = (8.0 * C.MU_WATER * L_m * (q_m3s / n_cells)
                 / (np.pi * (r_cell_mm * C.SI) ** 4))

        sweep.append({
            "kind": kind,
            "target_total": target,
            "budget": target,
            "n_leaves": None,
            "pinned": int(g.pinned_cells),
            "n_channel_cells": n_cells,
            "r_cell_mm": r_cell_mm,
            "dp_pa": dp_pa,
            "T_max_c": g.T_max,
            "T_mean_solid_c": g.T_mean_solid,
            "hotspot_area_mm2": g.hotspot_area,
            "C1_enters_all_chips": c1_ok,
            "C2_root_fits_cell": True,
            "C3_within_pump": dp_pa <= PUMP_SHUTOFF_PA,
        })
        if verbose:
            print(f"  [{kind}/total] target={target:5d} pinned={g.pinned_cells:4d} "
                  f"cells={n_cells:5d} r={r_cell_mm:.4f} "
                  f"dp={dp_pa:9.1f} Pa T_max={g.T_max:7.3f} "
                  f"C1={int(c1_ok)} C3={int(dp_pa <= PUMP_SHUTOFF_PA)}")

    feasible = [s for s in sweep if s["C1_enters_all_chips"]
                and s["C3_within_pump"]]
    if not feasible:
        raise ValueError(
            f"control kind={kind} (C5/total): no design satisfies C1 and "
            f"C3 (swept {len(sweep)} total-cell targets).")

    front = pareto_front(feasible)
    return {
        "kind": kind + "/total",
        "front": front,
        "knee": select_knee(front),
        "knee_sensitivity": knee_sensitivity(front),
        "n_feasible": len(feasible),
        "sweep": sweep,
        "c2_summary": {
            "n_on_front": len(front),
            "n_C2_ok_on_front": len(front),
            "all_satisfy_C2": True,
            "note": ("C2 is vacuous for a straight pipe (no Murray "
                     "junction, single radius); reported as satisfied so "
                     "the constraint each side was tested against stays "
                     "visible"),
        },
        "inputs": {
            "centers": [list(c) for c in centers],
            "grid": grid, "radius": radius, "powers": powers,
            "power_w": power_w, "dT_c": dT_c, "q_m3s": q_m3s,
            "q_lpm": C.lpm(q_m3s), "grid_mm": GRID_MM,
        },
    }


def compare_fronts(tree: dict, control: dict) -> dict:
    """Is the tree Pareto-DOMINANT over the control?

    Dominance is decided on the union of the two fronts: the tree dominates
    iff no control point is better in BOTH objectives than any tree point,
    i.e. every control point is matched or beaten. Reported per objective
    as well, because "the tree wins on temperature but loses on pressure"
    is the honest shape of most results and a single boolean would hide it.

    RESOURCE-BASIS CAVEAT, measured on all four layouts (2026-10-19): the
    tree's front is expressed in LEAVES with a realised pinned count; the
    control's front is expressed in PINNED TARGET, and its total channel
    occupancy (`n_channel_cells`) is larger than its pinned count because
    cells inside chip blocks are exempt from pinning but still occupied
    (radial: 800 pinned / 881-1394 total cells; straight: 528/579/494/256
    pinned at 800 total). So the control fronts spend MORE total occupancy
    than the tree's maximum-budget point (tree max: 1309 cells at 142-151
    leaves). Every dominance verdict below is therefore conservative in
    the tree's favour being UNCLEAR: a verdict of "control beats tree"
    (all four layouts, one point each) holds even though the control
    spent the larger footprint. Callers comparing on an equal-TOTAL-cells
    basis must use `verify.radial_group_total` / `lattice_group_total`
    instead; that convention is the project's C5 and is not wired here.
    """
    tf, cf = tree["front"], control["front"]
    t_best_T = min(d["T_max_c"] for d in tf)
    c_best_T = min(d["T_max_c"] for d in cf)
    t_best_dp = min(d["dp_pa"] for d in tf)
    c_best_dp = min(d["dp_pa"] for d in cf)

    # A control point beats a tree point when it is no worse in both
    # objectives and strictly better in at least one.
    control_beats_tree = []
    for c in cf:
        for t in tf:
            if (c["T_max_c"] <= t["T_max_c"] and c["dp_pa"] <= t["dp_pa"]
                    and (c["T_max_c"] < t["T_max_c"]
                         or c["dp_pa"] < t["dp_pa"])):
                control_beats_tree.append(
                    {"control_target": c.get("target_pinned",
                                             c.get("target_total")),
                     "control_basis": ("pinned" if "target_pinned" in c
                                       else "total"),
                     "control_T_max_c": c["T_max_c"],
                     "control_dp_pa": c["dp_pa"],
                     "tree_leaves": t["n_leaves"],
                     "tree_T_max_c": t["T_max_c"],
                     "tree_dp_pa": t["dp_pa"]})
                break

    return {
        "tree_dominates": len(control_beats_tree) == 0,
        "n_control_points_beating_tree": len(control_beats_tree),
        "examples": control_beats_tree[:5],
        "best_T_max_c": {"tree": t_best_T, "control": c_best_T,
                         "tree_better": t_best_T < c_best_T},
        "best_dp_pa": {"tree": t_best_dp, "control": c_best_dp,
                       "tree_better": t_best_dp < c_best_dp},
        "front_sizes": {"tree": len(tf), "control": len(cf)},
    }


def solve_design(centers, grid: int = 50, radius: float = F.SRC_RADIUS_REAL,
                 powers=None, r0_mm: float | None = None, dT_c: float = 5.0,
                 power_w: float = 253.0, t_tol_c: float = 0.01,
                 verbose: bool = False):
    """Generate the constraint-feasible designs for one chip layout.

    Returns a dict with the PARETO FRONT (not a single design), the
    epsilon-constrained knee selection, and the provenance of every
    constraint. Raises ValueError if C1-C3 have no common solution (the
    honest answer when the load cannot be carried).

    `t_tol_c` is the thermal tolerance of the knee selection: how much
    T_max may degrade from the front's best in exchange for lower dp.
    """
    ok, why = SSS.layout_is_valid(centers, grid=grid, radius=radius)
    if not ok:
        raise ValueError(f"layout inadmissible (N4b): {why}")

    # The field the tree grows on, and the REAL per-cell source term.
    # `strength` must be carried through or the re-solve silently reverts
    # to equal power per cell (defect #2, paper §16b).
    T, src, strength = SSS.solve_spread(centers, grid=grid, radius=radius,
                                        powers=powers)

    q_m3s = C.coolant_flow_m3s(power_w * len(centers), dT_c=dT_c)

    # Leaf counts to try. The project's own 61-leaf tree needed 399
    # segments, so the sweep is anchored on that measured point and
    # extended both ways.
    leaf_grid = sorted({int(x) for x in
                        (4, 8, 16, 24, 32, 48, 61, 80, 100, 128, 160, 200)
                        if x >= 4})

    sweep = []
    for n_target in leaf_grid:
        budget = node_budget_from_leaves(n_target)
        edges = G.grow_tree(T, max_nodes=budget)
        if not edges:
            continue

        # C2 derives the leaf radius from the tree's REALISED leaf count,
        # not from `n_target` -- `grow_tree` stops on the heap, so the
        # realised count differs from the target and the root radius
        # follows the realised one. (Using the target here made C2 pass on
        # geometry that was never built.)
        n_leaf_real = n_leaves_of(edges)
        r0_c2 = max_r0_for_leaves(n_leaf_real, GRID_MM)
        r0_use = r0_c2 if r0_mm is None else r0_mm
        radii = Ra.assign_radii(edges, grid=grid, r0=r0_use)
        r_root = max(radii.values())
        c2_ok = r_root <= GRID_MM + 1e-12

        # C1: the tree must enter every chip footprint.
        cells = sorted(set([p for p, _ in edges] + [c for _, c in edges]))
        r_blk = int(radius)
        block_d = []
        for cy, cx in centers:
            cyi, cxi = int(round(cy)), int(round(cx))
            blk = [(y, x) for y in range(cyi - r_blk, cyi + r_blk + 1)
                   for x in range(cxi - r_blk, cxi + r_blk + 1)
                   if 0 <= y < grid and 0 <= x < grid]
            if blk:
                block_d.append(min(abs(y - i // grid) + abs(x - i % grid)
                                   for y, x in blk for i in cells))
        c1_ok = (max(block_d) if block_d else 1) == 0

        # C3: demand-driven dp on convention A, pure viscous term.
        dp = C.tree_dp_pa(edges, radii, grid, GRID_MM, q_m3s)
        c3_ok = dp["dp_pa"] <= PUMP_SHUTOFF_PA

        # Objective + the thermal reading itself.
        tg = V.tree_group(T, src, edges, radii, grid_x=grid,
                          strength=strength)

        sweep.append({
            "n_leaves": n_leaf_real,
            "n_target_leaves": n_target,
            "budget": budget,
            "n_edges": len(edges),
            "n_cells": len(cells),
            "r0_mm": r0_use,
            "r0_from_C2_mm": r0_c2,
            "r_root_mm": r_root,
            "dp_pa": dp["dp_pa"],
            "dp_kirchhoff_pa": dp["dp_kirchhoff_reference_pa"],
            "T_max_c": tg.T_max,
            "T_mean_solid_c": tg.T_mean_solid,
            "hotspot_area_mm2": tg.hotspot_area,
            "pinned": tg.pinned_cells,
            "C1_enters_all_chips": c1_ok,
            "C2_root_fits_cell": c2_ok,
            "C3_within_pump": c3_ok,
        })
        if verbose:
            print(f"  target={n_target:4d} realised_leaves={n_leaf_real:4d} "
                  f"budget={budget:4d} r0={r0_use:.4f} "
                  f"r_root={r_root:.3f} dp={dp['dp_pa']:9.1f} Pa "
                  f"T_max={tg.T_max:7.3f} C1={int(c1_ok)} "
                  f"C2={int(c2_ok)} C3={int(c3_ok)}")

    feasible = [s for s in sweep if s["C1_enters_all_chips"]
                and s["C3_within_pump"]]
    # C2 is NOT a hard filter here. When the caller FORCES an r0 that
    # violates the geometry (e.g. the historical r0 = 0.5 mm, whose
    # 61-leaf tree measures r_root = 1.6661 mm > 0.9 mm pitch), dropping
    # every design would leave the caller with nothing to inspect -- and
    # the violation is exactly what they came to measure. The filter is
    # C1 + C3 (admissibility and pumpability); C2 is reported per design
    # and summarised, so a violating r0 yields a front with every row
    # flagged rather than an exception.
    if not feasible:
        # Report WHY, per constraint, so the caller can see which one binds.
        diag = {
            "n_swept": len(sweep),
            "pass_C1": sum(1 for s in sweep if s["C1_enters_all_chips"]),
            "pass_C3": sum(1 for s in sweep if s["C3_within_pump"]),
            "pass_C1_C3": len(feasible),
            "min_T_max_c": min((s["T_max_c"] for s in sweep), default=None),
            "min_dp_pa": min((s["dp_pa"] for s in sweep), default=None),
        }
        raise ValueError(
            f"no design satisfies C1 and C3. Diagnostics: {diag}. "
            f"C1 is the fairness precondition and must not be relaxed; "
            f"if C3 binds, lower the power or raise dT_c (more flow).")

    front = pareto_front(feasible)
    knee = select_knee(front, t_tol_c=t_tol_c)
    n_c2_ok = sum(1 for d in front if d["C2_root_fits_cell"])

    return {
        "front": front,
        "knee": knee,
        "knee_sensitivity": knee_sensitivity(front),
        "n_feasible": len(feasible),
        "c2_summary": {
            "n_on_front": len(front),
            "n_C2_ok_on_front": n_c2_ok,
            "all_satisfy_C2": n_c2_ok == len(front),
            "note": ("with r0=None every front row satisfies C2 by "
                     "construction (r0 is derived from it); a non-zero "
                     "count of violations means r0 was forced"),
        },
        "sweep": sweep,
        "constraints": {
            "C1": "tree enters every chip footprint (block_to_tree == 0)",
            "C2": f"r_root <= grid pitch ({GRID_MM} mm); r0 SOLVED as "
                  f"pitch / N_leaves^(1/3), not fixed",
            "C3": f"dp <= pump shut-off head ({PUMP_SHUTOFF_PA:.0f} Pa, "
                  f"convention A, pure viscous)",
            "objective": "Pareto front in (T_max, dp), both minimised; "
                         f"knee = lowest dp within {t_tol_c} K of the "
                         f"front's best T_max",
            "C1_C3_are_hard_filters": (
                "C1 and C3 gate admissibility; C2 is reported per design "
                "and satisfied by construction when r0 is derived from it"),
            "NOT_counted": "junction K (v5 not run) and 0.2-0.5 mm fin-pitch "
                           "r^4 correction (1.0-39.1x): dp is optimistic",
        },
        "inputs": {
            "centers": [list(c) for c in centers],
            "grid": grid,
            "radius": radius,
            "powers": powers,
            "r0_mm": r0_mm,
            "power_w": power_w,
            "dT_c": dT_c,
            "q_m3s": q_m3s,
            "q_lpm": C.lpm(q_m3s),
            "grid_mm": GRID_MM,
        },
    }


def format_front(r: dict) -> str:
    """Human-readable Pareto front with the knee marked."""
    lines = []
    lines.append(f"  {'leaves':>6} {'budget':>7} {'r0 mm':>7} {'T_max C':>9} "
                 f"{'dp Pa':>10} {'C1':>2} {'C2':>2} {'C3':>2}")
    for d in r["front"]:
        mark = " <- knee" if d is r["knee"] else ""
        lines.append(
            f"  {d['n_leaves']:6d} {d['budget']:7d} {d['r0_mm']:7.4f} "
            f"{d['T_max_c']:9.4f} {d['dp_pa']:10.1f} "
            f"{int(d['C1_enters_all_chips']):2d} "
            f"{int(d['C2_root_fits_cell']):2d} "
            f"{int(d['C3_within_pump']):2d}{mark}")
    lines.append("  knee sensitivity (how the choice moves with the "
                 "tolerance):")
    lines.append(f"  {'tol K':>6} {'leaves':>7} {'T_max C':>9} {'dp Pa':>10} "
                 f"{'dp/min':>7} {'dT K':>7}")
    for s in r["knee_sensitivity"]:
        lines.append(
            f"  {s['t_tol_c']:6.2f} {s['n_leaves']:7d} {s['T_max_c']:9.4f} "
            f"{s['dp_pa']:10.1f} {s['dp_vs_min_front']:7.2f} "
            f"{s['T_max_penalty_c']:7.4f}")
    return "\n".join(lines)


if __name__ == "__main__":
    import json
    import sys

    cases = {
        "1 chip": [(24, 24)],
        "2 chip d=16": [(12, 24), (36, 24)],
        "3 chip": [(12, 12), (36, 12), (24, 36)],
        "4 chip": [(12, 12), (36, 12), (12, 36), (36, 36)],
    }
    out = {}
    for label, centers in cases.items():
        print(f"== {label} ==")
        try:
            r = solve_design(centers, verbose=False)
            out[label] = r
            print(format_front(r))
            k = r["knee"]
            c2 = r["c2_summary"]
            print(f"  -> knee: leaves={k['n_leaves']} budget={k['budget']} "
                  f"T_max={k['T_max_c']:.4f} C dp={k['dp_pa']:.1f} Pa "
                  f"({r['n_feasible']} feasible, {len(r['front'])} on front)")
            if not c2["all_satisfy_C2"]:
                print(f"  !! C2 VIOLATED on {c2['n_on_front'] - c2['n_C2_ok_on_front']}"
                      f"/{c2['n_on_front']} front rows -- r0 was forced; "
                      f"these designs are not manufacturable at this pitch")
        except ValueError as e:
            print(f"  -> INFEASIBLE: {e}")
            out[label] = {"error": str(e)}
    print("\n--- knees ---")
    print(json.dumps({k: v.get("knee", {"error": v.get("error")})
                      for k, v in out.items()}, indent=2, ensure_ascii=False))
    sys.stdout.flush()
