"""Step 5: two-metric verification, tree vs equal-material straight channels.

Model (both groups, identical conventions):
  * steady 2D conduction on the same plate with the same heat source
  * channel cells are held at T_cool (Dirichlet) -- the liquid is a perfect
    heat sink, so this is the *upper bound* of convective cooling. It is a
    fair comparison because both groups get the same idealisation.
  * flow splits evenly among the channels of a group

Metrics:
  * T_max             -- hottest solid cell (worst-case hotspot)
  * thermal resistance R_th = (T_max - T_cool)/Q_total
  * pressure drop     -- Poiseuille, summed per segment:
                         dP = 8*mu*L*Q / (pi*r^4)

Control group: the SAME total cross-section material, arranged as N parallel
straight channels running from the source to the plate edge.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from field import PITCH_MM, source_mask

MU = 1.0        # dynamic viscosity [a.u.] (cancels in the ratio, kept explicit)
T_COOL = 25.0   # coolant / boundary temperature [C]
Q_TOTAL = 1.0   # total coolant flow [a.u.]
# Convergence settings for the channel re-solve in apply_channels. Exposed
# so conjugate.py uses the SAME tolerance rather than a private copy.
APPLY_MAX_ITER = 20000
APPLY_TOL = 1e-7


@dataclass
class Group:
    name: str
    T: np.ndarray
    T_max: float
    R_th: float
    dp: float
    total_area_mm2: float
    n_segments: int
    n_channels: int
    Q: float = Q_TOTAL
    # discriminating metrics -- T_max saturates when the source itself is the
    # hottest unpinned cell, so we also track the solid's bulk temperature and
    # the area that stays above the hot-spot threshold.
    T_mean_solid: float = 0.0
    hotspot_area: float = 0.0
    pinned_cells: int = 0
    hotspot_threshold: float = 0.0
    # The pinned mask itself. `from_field` used to discard it, which made it
    # impossible to re-measure a group's hot zone at a SHARED absolute
    # threshold -- the relative threshold each group computes for itself is
    # lower for whichever group has the lower T_max, so the metric is biased
    # in favour of the T_max winner. Default None keeps every historical
    # construction working.
    pinned_mask: np.ndarray | None = None
    # Raw channel cell list, when the builder has one (radial pipes). None
    # keeps every historical construction working. The coupled (conjugate)
    # model needs the ACTUAL cells: the pinned mask loses the pipe cells that
    # fall inside a source block (never pinned, by the fairness rule).
    channel_cells: list | None = None

    @staticmethod
    def from_field(name: str, Tc: np.ndarray, pinned: np.ndarray, dp: float,
                   area: float, n_segments: int, n_channels: int,
                   T_cool: float = T_COOL, hotspot_frac: float = 0.25,
                   pitch_mm: float = PITCH_MM,
                   cells: list | None = None) -> "Group":
        """Build a Group from a solved field.

        hotspot_frac: the hot-zone threshold is taken as a *fraction of the
        achievable rise* (T_cool -> T_max) rather than an absolute number.
        An absolute threshold is meaningless here because with 16% of the plate
        pinned the whole field sits between 25 and 27.6 C, so any fixed
        threshold (e.g. 40 C) yields an empty hot zone for every group.
        """
        solid = ~pinned                       # channel cells are at T_cool by fiat
        T_max = float(Tc.max())
        rise = T_max - T_cool
        thresh = T_cool + hotspot_frac * rise
        T_mean = float(Tc[solid].mean()) if solid.any() else T_cool
        hot = solid & (Tc > thresh)
        return Group(
            name=name, T=Tc, T_max=T_max, R_th=rise / Q_TOTAL, dp=dp,
            total_area_mm2=area, n_segments=n_segments, n_channels=n_channels,
            T_mean_solid=T_mean, hotspot_area=float(hot.sum()) * pitch_mm**2,
            pinned_cells=int(pinned.sum()), hotspot_threshold=thresh,
            pinned_mask=pinned, channel_cells=cells,
        )


def hotspot_at(g: "Group", threshold_c: float) -> float:
    """Hot-zone area (mm^2) of a group at a SHARED absolute threshold.

    TASK-3 (2026-10-17). The per-group relative threshold used by
    `from_field` (T_cool + frac * that group's own rise) is LOWER for
    whichever group has the smaller T_max, so the metric is biased in
    favour of the T_max winner -- and when two groups have close T_max the
    bias can flip the sign of the comparison (gamma sweep: 13 of 48 cases
    flipped under the own-threshold rule, see DEFECT_REMEDIATION_PLAN.md
    §5.9a). Re-measuring every group of a comparison at ONE absolute
    threshold removes that bias: the threshold no longer knows which group
    is measuring.

    Requires `pinned_mask` (added 2026-10-17). Groups built before that
    field existed carry None and raise instead of silently falling back to
    the biased rule.
    """
    if g.pinned_mask is None:
        raise ValueError(
            f"{g.name}: pinned_mask is None, cannot re-measure at a shared "
            "threshold. Rebuild the group with the current from_field.")
    solid = ~g.pinned_mask
    if not solid.any():
        return 0.0
    return float((solid & (g.T > threshold_c)).sum()) * PITCH_MM**2


def channel_mask(T_shape, channel_cells, src: np.ndarray) -> np.ndarray:
    """Boolean mask of cells held at T_cool (never a source cell)."""
    mask = np.zeros(T_shape, dtype=bool)
    for (y, x) in channel_cells:
        mask[y, x] = True
    return mask & ~src


def apply_channels(T: np.ndarray, channel_cells, src: np.ndarray,
                   T_cool: float | np.ndarray = T_COOL,
                   max_iter: int = APPLY_MAX_ITER,
                   tol: float = APPLY_TOL, strength: np.ndarray | None = None,
                   h_conv: float = 0.0, T_ambient: float | None = None):
    """Re-solve conduction with channel cells pinned at T_cool.

    Returns (field, pinned_mask). The heat source is preserved: source cells
    keep generating heat and are never pinned (a channel that swallowed the
    source would delete the heat it is meant to remove).

    `strength` is the per-cell source term. When it is None the boolean mask
    `src` is used, i.e. every source cell carries the same q -- the behaviour
    of every experiment up to and including REPORT.md section 11. Passing the
    weighted field from `field.source_strength_multi` is what makes an
    unequal-power experiment possible: without it the re-solve silently
    reverts to equal power and the controls come out identical across power
    sets (which is exactly how the bug was found).

    `h_conv` / `T_ambient` switch the PLATE EDGE from the ideal Dirichlet cold
    sink to a finite-convection (Robin) boundary, the same switch
    `field.solve_heat` gained. The CHANNELS stay pinned at T_cool -- they are
    the coolant, and modelling them as a finite-convection surface too would
    require a flow model the project does not have. h_conv=0 reproduces every
    pre-2026-10-16 result bit-for-bit.

    N3 FIX (2026-10-17): T_cool may also be a PER-CELL array shaped like T;
    channel cells are then pinned at their own local value instead of one
    uniform temperature. This is what lets the conjugate solver hold each
    channel cell at its own wall temperature -- previously the uniform pin
    decoupled the solid from the warm coolant entirely. A scalar T_cool
    reproduces every earlier result bit-for-bit.
    """
    mask = channel_mask(T.shape, channel_cells, src)

    if strength is None:
        src_b = (PITCH_MM**2 / 4.0) * src[1:-1, 1:-1]
    else:
        src_b = (PITCH_MM**2 / 4.0) * np.asarray(strength, dtype=float)[1:-1, 1:-1]
    per_cell = np.asarray(T_cool, dtype=float) if np.ndim(T_cool) else None
    # Scalar path must stay bit-for-bit identical to pre-N3 behaviour, so the
    # edge/ambient fallback is exactly float(T_cool). With a per-cell array
    # the coldest pinned cell is the inlet, so the plate edge sees the inlet
    # temperature (the minimum of the wall values).
    t_edge = float(np.min(per_cell)) if per_cell is not None else float(T_cool)
    if T_ambient is None:
        T_ambient = t_edge
    Bi = h_conv * PITCH_MM
    grid_y, grid_x = T.shape
    Tc = T.copy()
    Tc[mask] = per_cell[mask] if per_cell is not None else t_edge
    for _ in range(max_iter):
        Tn = Tc.copy()
        Tn[1:-1, 1:-1] = (
            0.25 * (Tc[2:, 1:-1] + Tc[:-2, 1:-1] + Tc[1:-1, 2:] + Tc[1:-1, :-2])
            + src_b
        )
        Tn[mask] = per_cell[mask] if per_cell is not None else t_edge
        if Bi > 0.0:
            a = 1.0 + Bi
            b = 2.0 + Bi
            Tn[0, 1:-1] = (Tn[1, 1:-1] + a * T_ambient) / b
            Tn[-1, 1:-1] = (Tn[-2, 1:-1] + a * T_ambient) / b
            Tn[1:-1, 0] = (Tn[1:-1, 1] + a * T_ambient) / b
            Tn[1:-1, -1] = (Tn[1:-1, -2] + a * T_ambient) / b
            Tn[0, 0] = (Tn[1, 0] + Tn[0, 1] + 2.0 * a * T_ambient) / (2.0 * b)
            Tn[0, -1] = (Tn[1, -1] + Tn[0, -2] + 2.0 * a * T_ambient) / (2.0 * b)
            Tn[-1, 0] = (Tn[-2, 0] + Tn[-1, 1] + 2.0 * a * T_ambient) / (2.0 * b)
            Tn[-1, -1] = (Tn[-2, -1] + Tn[-1, -2] + 2.0 * a * T_ambient) / (2.0 * b)
        else:
            Tn[0, :] = t_edge
            Tn[-1, :] = t_edge
            Tn[:, 0] = t_edge
            Tn[:, -1] = t_edge
        if float(np.max(np.abs(Tn - Tc))) < tol:
            return Tn, mask
        Tc = Tn
    return Tc, mask


def tree_material_mm2(edges, radii) -> float:
    """Cross-section area the tree actually occupies, counting each shared
    junction once. Summing per-edge areas double-counts junctions and is what
    produced an unbuildable control group (573 channels in a 2500-cell plate).

    A node's footprint is pi*r^2 with r = max(its own radius, the largest
    radius of the segments touching it); every node is counted exactly once.
    """
    r_at: dict[int, float] = {}
    for p, c in edges:
        for node, other in ((p, c), (c, p)):
            r = max(radii[node], radii[other])
            r_at[node] = max(r_at.get(node, 0.0), r)
    return float(sum(np.pi * r ** 2 for r in r_at.values()))


def tree_group(T: np.ndarray, src: np.ndarray, edges, radii, grid_x: int,
               pitch_mm: float = PITCH_MM, T_cool: float = T_COOL,
               hotspot_frac: float = 0.25,
               strength: np.ndarray | None = None,
               h_conv: float = 0.0, T_ambient: float | None = None) -> Group:
    cells = [(i // grid_x, i % grid_x)
             for i in sorted(set([p for p, _ in edges] + [c for _, c in edges]))]
    Tc, pinned = apply_channels(T, cells, src, T_cool, strength=strength,
                                h_conv=h_conv, T_ambient=T_ambient)
    dp = poiseuille_dp(edges, radii, grid_x, pitch_mm)
    area = tree_material_mm2(edges, radii)
    return Group.from_field("tree", Tc, pinned, dp, area, len(edges), len(edges),
                            T_cool, hotspot_frac, pitch_mm)


def straight_group(T: np.ndarray, src: np.ndarray, n_channels: int, total_area_mm2: float,
                   grid_x: int, grid_y: int, pitch_mm: float = PITCH_MM,
                   T_cool: float = T_COOL, hotspot_frac: float = 0.25,
                   strength: np.ndarray | None = None,
                   h_conv: float = 0.0, T_ambient: float | None = None) -> Group:
    """Equal-material straight channels.

    Fairness rules (PROJECT.md 2.4: "the control group must use the same amount of material"):
      * same number of 1-cell-wide channels as the tree has cells -> the same
        amount of plate is occupied by channel in both groups;
      * same total cross-section -> the same material, hence the same
        pressure-drop budget;
      * channels span the full plate length along y, which is the natural
        "dumb but adequate" baseline a designer would draw by hand.
    """
    n_ch = max(1, int(n_channels))
    r = float(np.sqrt(total_area_mm2 / (n_ch * np.pi)))

    c = grid_x // 2
    half = n_ch // 2
    xs = [c - half + k for k in range(n_ch) if 0 <= c - half + k < grid_x]
    if not xs:
        xs = [c]

    cells = [(y, x) for x in xs for y in range(grid_y)]
    Tc, pinned = apply_channels(T, cells, src, T_cool, strength=strength,
                                h_conv=h_conv, T_ambient=T_ambient)

    L = grid_y * pitch_mm
    dp = 8.0 * MU * L * (Q_TOTAL / len(xs)) / (np.pi * r ** 4)
    return Group.from_field(f"straight x{len(xs)}", Tc, pinned, dp, total_area_mm2,
                            len(xs), len(xs), T_cool, hotspot_frac, pitch_mm)


def radial_group_pinned(T: np.ndarray, src: np.ndarray, target_pinned: int,
                        total_area_mm2: float, grid_x: int, grid_y: int,
                        pitch_mm: float = PITCH_MM, T_cool: float = T_COOL,
                        hotspot_frac: float = 0.25,
                        strength: np.ndarray | None = None,
                        h_conv: float = 0.0, T_ambient: float | None = None) -> Group:
    """Straight pipes, one family per chip, scaled to the tree's PINNED count.

    `radial_group` fixes the cell budget and lets the pinned count fall out
    of it, which is unfair in the multi-source case: a tree that grows
    *through* a chip block has those cells exempted from pinning, so the
    same 400-cell budget yields 325 pinned cells for the tree and 398 for
    the control. The control would silently get 73 extra cold cells.

    Here the budget is set so that len(cells) - (cells inside a source
    block) == target_pinned exactly. Same occupancy, same exemption rule,
    both sides.

    BALANCE FIX (2026-10-24). Two defects made the multi-chip control serve
    only the first chip:
      * `exempt_per_chip` was a hard-wired 25, left over from the 5x5
        synthetic block. On the real 17x17 footprint (SRC_RADIUS_REAL=8) a
        block is 289 cells, so the budget was over-estimated by ~20% and the
        per-chip pipe count was ~5x too high;
      * Stage 1 bisected one FLAT `per_pipe` list built from the concatenated
        cell stream, i.e. it kept a PREFIX of the pipes in generation order.
        Measured on "3 chips, triangle" / budget 600: 13 vertical pipes in
        x=15..27, all belonging to chip (15,15); the other two chips got zero
        pinned cells inside their blocks.
    Pipes are now recorded per chip (`pipes_by_chip`) and the budget is
    expressed in EFFECTIVE pinned length -- a pipe starts inside its chip
    block, so only `span - (blk_half + 1)` of its cells can ever pin.
    """
    centers = _cluster_centers(src)
    n_src = max(1, len(centers))
    src_cells = int(src.sum())

    per_chip_src = max(1, src_cells // n_src)
    blk_side = int(round(np.sqrt(per_chip_src)))
    blk_half = max(0, (blk_side - 1) // 2)

    target = int(target_pinned)
    per_chip_target = target / n_src

    pipes_by_chip: dict[int, list[list[tuple[int, int]]]] = {}
    pipe_len_by_chip: dict[int, list[int]] = {}
    for ci, (cy, cx) in enumerate(centers):
        cy, cx = int(round(cy)), int(round(cx))
        d_top, d_bot = cy, grid_y - 1 - cy
        d_left, d_right = cx, grid_x - 1 - cx
        d = min(d_top, d_bot, d_left, d_right)
        if d == d_top:
            orient, span, up = "v", d_top + 1, True
        elif d == d_bot:
            orient, span, up = "v", d_bot + 1, False
        elif d == d_left:
            orient, span, up = "h", d_left + 1, True
        else:
            orient, span, up = "h", d_right + 1, False

        # A pipe that starts inside the chip block can only pin the part of
        # its run that lies OUTSIDE the block: it leaves the chip after
        # `blk_half + 1` cells, so its effective length is span - blk_half - 1.
        pinned_per_pipe = max(1, span - (blk_half + 1))
        k = max(1, int(np.ceil(per_chip_target / pinned_per_pipe)))

        pipes: list[list[tuple[int, int]]] = []
        lens: list[int] = []
        # Offsets are emitted CENTRE-OUT: 0, +1, -1, +2, -2, ... so the pipe
        # bundle is symmetric about the chip centroid, matching
        # `radial_group_c5` below. The previous rule (off = j, i.e. all pipes
        # on ONE side of the centroid) put the whole cooled bundle 2-3 cells
        # off-axis and cooled the control 0.09 C more than it should; it also
        # made the result depend on which side of the plate was nearer.
        # Centre-out is also PREFIX-SAFE: Stage 1 keeps the first k pipes per
        # chip, and every prefix of this fan is still centred, whereas a
        # literal `j - k//2` prefix drifts back to one side when k is cut.
        # Runs past the plate edge are simply clipped (`min`/`max` below);
        # they add no new track, which is why pipes alone cannot cover a wide
        # plate.
        fan: list[int] = [0]
        for d_ in range(1, k + 1):
            fan += [d_, -d_]
        for j in range(k):
            off = fan[j]
            if orient == "v":
                x = min(grid_x - 1, max(0, cx + off))
                ys = range(cy, -1, -1) if up else range(cy, grid_y)
                pipe = [(y, x) for y in ys]
            else:
                y = min(grid_y - 1, max(0, cy + off))
                xs = range(cx, -1, -1) if up else range(cx, grid_x)
                pipe = [(y, x) for x in xs]
            pipes.append(pipe)
            lens.append(len(pipe))
        pipes_by_chip[ci] = pipes
        pipe_len_by_chip[ci] = lens

    def cells_for(kk: int) -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        seen_: set[tuple[int, int]] = set()
        for ci_ in sorted(pipes_by_chip):
            for p in pipes_by_chip[ci_][:kk]:
                for c in p:
                    if c not in seen_:
                        seen_.add(c)
                        out.append(c)
        return out

    def lens_for(kk: int) -> list[int]:
        return [n for ci_ in sorted(pipe_len_by_chip)
                for n in pipe_len_by_chip[ci_][:kk]]

    max_k = max(len(v) for v in pipes_by_chip.values())
    uniq = cells_for(max_k)
    lengths = lens_for(max_k)

    Tc, pinned = apply_channels(T, uniq, src, T_cool, strength=strength,
                                h_conv=h_conv, T_ambient=T_ambient)

    # The algebra above is an estimate: the block edge is not exactly
    # `blk_half + 1` cells from the centroid, and pipes clip against the grid
    # edge, leaving a residual gap. Correct it by BISECTING THE PER-CHIP PIPE
    # COUNT, not by deleting cells one at a time -- removing one pipe moves the
    # pinned count by several cells, so a bisection over k reaches the target
    # in O(log k) re-solves, whereas per-cell deletion needs one re-solve per
    # cell and takes minutes.
    def solve_with(pipe_list: list[tuple[int, int]]) -> tuple[np.ndarray, np.ndarray, int]:
        s: set[tuple[int, int]] = set()
        for c in pipe_list:
            s.add(c)
        Tc_, p_ = apply_channels(T, sorted(s), src, T_cool, strength=strength,
                                 h_conv=h_conv, T_ambient=T_ambient)
        return Tc_, p_, int(p_.sum())

    cur_cells = list(uniq)
    Tc, pinned, got = solve_with(cur_cells)

    # Stage 1: bisect k = pipes retained PER CHIP. Every chip keeps its first
    # k pipes, so no chip can be starved -- the old prefix bisection on one
    # flat list dropped whole chips. `best_gap` guards non-monotonicity
    # (overlapping or edge-clipped pipes can make the count flat).
    if got != target:
        lo, hi = 1, max_k
        best_cells, best_Tc, best_p, best_got = cur_cells, Tc, pinned, got
        best_gap = abs(got - target)
        best_k = max_k
        while lo <= hi:
            mid = (lo + hi) // 2
            trial_cells = cells_for(mid)
            t_Tc, t_p, g = solve_with(trial_cells)
            if abs(g - target) < best_gap:
                best_cells, best_Tc, best_p, best_got = trial_cells, t_Tc, t_p, g
                best_gap = abs(g - target)
                best_k = mid
            if g >= target:
                hi = mid - 1
            else:
                lo = mid + 1
        cur_cells, Tc, pinned, got = best_cells, best_Tc, best_p, best_got
        lengths = lens_for(best_k)

    # Stage 2: shave individual cells until the gap is exactly zero. The
    # bisection alone can only land within ~one pipe of the target (measured
    # -12 cells on the 2-chip layout), which is still a 3% occupancy
    # advantage for the tree. Each single-cell deletion moves the count by
    # exactly 1, so the gap can be driven to 0 -- at the cost of one re-solve
    # per cell, which is fine for a gap of a few dozen.
    #
    # Cells are removed from pipe ENDS first (farthest from the chip), since
    # that is where a straight radial pipe is least useful.
    if got > target:
        keep = set(cur_cells)
        dist = {(y, x): min(abs(y - cy) + abs(x - cx) for cy, cx in centers)
                for (y, x) in keep}
        for cell in sorted(keep, key=dist.get, reverse=True):
            if got <= target:
                break
            trial = keep - {cell}
            t_Tc, t_p, g = solve_with(sorted(trial))
            if g < got:
                keep, Tc, pinned, got = trial, t_Tc, t_p, g
        cur_cells = sorted(keep)

    # Stage 3: if still short of the target, EXTEND pipes rather than add
    # whole new ones. A pipe runs from its chip to the plate edge; the ones
    # that were truncated by the bisection can be lengthened one cell at a
    # time, which moves the pinned count by exactly 1 and closes a small gap
    # without the ~20-50 cell jump of adding a whole pipe.
    #
    # Candidate cells are restricted to the NEIGHBOURS OF EXISTING PIPE CELLS
    # that are NOT already pinned and NOT inside a chip block. Testing every
    # cell on the plate costs O(N) full re-solves per step (76 s for one
    # group); testing only pipe-adjacent cells costs O(perimeter) and lands
    # on the same answer, because a cell that is not pipe-adjacent cannot
    # extend any pipe.
    if got < target:
        keep = set(cur_cells)
        chip_cells = {(y, x) for (y, x) in
                      zip(*np.where(src))} if hasattr(src, "shape") else set()
        for _ in range(8 * (target - got) + 16):
            if got >= target:
                break
            cands = set()
            for (y, x) in keep:
                for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                    c = (y + dy, x + dx)
                    if not (0 <= c[0] < grid_y and 0 <= c[1] < grid_x):
                        continue
                    if c in keep or c in chip_cells:
                        continue
                    cands.add(c)
            if not cands:
                break
            best_cell, best_gain = None, 0
            for c in sorted(cands):
                g = solve_with(sorted(keep | {c}))[2]
                gain = g - got
                if gain > best_gain or (gain == best_gain == 1
                                        and best_cell is None):
                    best_cell, best_gain = c, gain
                if gain == 1:
                    best_cell, best_gain = c, 1
                    break
            if best_cell is None:
                break
            keep.add(best_cell)
            got += best_gain
        cur_cells = sorted(keep)
        Tc, pinned, got = solve_with(cur_cells)

    uniq = cur_cells
    # CONSISTENCY FIX (2026-10-24): r used the BUDGET (`need`) while the flow
    # was split over the MEASURED cell count (`len(uniq)`), so dp carried a
    # spurious (need/len(uniq))^2 factor -- 20.1x on "3 chips, triangle" /
    # budget 600 (915 vs 204 cells), which made the reported 5.3x tree/control
    # ratio an artefact. `straight_group`, `radial_group`, `lattice_group` and
    # `radial_group_total` all back-calculate r from the cells they actually
    # place; this function now does the same.
    r = float(np.sqrt(total_area_mm2 / (max(1, len(uniq)) * np.pi)))
    L = (float(np.mean(lengths)) * pitch_mm) if lengths else float(grid_y) * pitch_mm
    dp = 8.0 * MU * L * (Q_TOTAL / max(1, len(uniq))) / (np.pi * r ** 4)
    return Group.from_field(f"radial-per-chip x{len(uniq)}", Tc, pinned, dp,
                            total_area_mm2, len(uniq), len(uniq), T_cool,
                            hotspot_frac, pitch_mm, cells=uniq)


def lattice_group(T: np.ndarray, src: np.ndarray, target_pinned: int,
                  total_area_mm2: float, grid_x: int, grid_y: int,
                  pitch_mm: float = PITCH_MM, T_cool: float = T_COOL,
                  hotspot_frac: float = 0.25,
                  strength: np.ndarray | None = None) -> Group:
    """Uniform lattice of straight channels, matched to an exact pinned count.

    A third topology for the same plate: parallel channels in BOTH
    directions, crossing at nodes, with no taper and no Steiner points. This
    is the grid a packaging engineer actually draws for power delivery, and
    it separates two things the tree conflates -- uniform coverage of the
    plate vs adaptive concentration near hot spots.

    Fairness, and why this is constructed rather than budgeted: `radial_
    group_pinned` can hit an exact pinned count by algebra, because its pipes
    run from a chip to an edge and only pass through the blocks they start
    in. A lattice crosses everything, so its pinned count cannot be predicted
    from a budget -- it has to be measured. Here the lattice density is
    chosen by bisection so the MEASURED pinned count equals the tree's
    exactly. Skipping that measurement is the §2.2/§7.2 mistake all over
    again, and it is silently large: a pitch-5 lattice on a 50x50 plate pins
    873 cells against the tree's 525.

    Equal total cross-section also holds (same `total_area_mm2`).
    """
    target = int(target_pinned)

    def build(pitch: int) -> tuple[set, int]:
        rows = range(0, grid_y, pitch)
        cols = range(0, grid_x, pitch)
        cells = set()
        for y in rows:
            cells.update((y, x) for x in range(grid_x))
        for x in cols:
            cells.update((y, x) for y in range(grid_y))
        # measure, do not predict: source cells are exempt from pinning
        _, pinned = apply_channels(T, sorted(cells), src, T_cool, strength=strength)
        return cells, int(pinned.sum())

    # densest possible = pitch 1 (every row and every column). If even that
    # cannot reach the target the tree is denser than a full lattice, which
    # cannot happen for any budget below grid^2.
    best_cells, best_pinned = build(1)
    if best_pinned < target:
        # The tree pins more cells than a saturated lattice: fall back to the
        # densest lattice and say so in the name rather than silently lying.
        Tc, pinned = apply_channels(T, sorted(best_cells), src, T_cool,
                                    strength=strength)
        L = 0.5 * (grid_x + grid_y) * pitch_mm
        n_ch = grid_y + grid_x
        r = float(np.sqrt(total_area_mm2 / (len(best_cells) * np.pi)))
        dp = 8.0 * MU * L * (Q_TOTAL / n_ch) / (np.pi * r ** 4) if r > 0 else 0.0
        return Group.from_field(
            f"lattice p1 (UNDERSHOOT {best_pinned}<{target})", Tc, pinned, dp,
            total_area_mm2, len(best_cells), n_ch, T_cool, hotspot_frac, pitch_mm)

    # bisect the pitch: coarse pitch = sparse = fewer pinned cells
    lo, hi = 1, max(grid_x, grid_y)
    chosen = None
    while lo <= hi:
        mid = (lo + hi) // 2
        cells, pinned = build(mid)
        if pinned >= target:
            chosen = (mid, cells, pinned)
            lo = mid + 1
        else:
            hi = mid - 1
    assert chosen is not None, "lattice bisection failed"

    pitch, cells, pinned = chosen
    Tc, pinned_mask = apply_channels(T, sorted(cells), src, T_cool,
                                     strength=strength)

    # Fine-tune by deleting INDIVIDUAL CELLS, not whole channels. Dropping a
    # column of a lattice moves the pinned count by ~50, which overshoots the
    # ~20-cell gap and makes "equal occupancy" impossible to reach. Removing
    # cells one at a time from the least useful end of each channel moves the
    # count by exactly 1, so the gap can be driven to zero.
    cols = sorted(range(0, grid_x, pitch))
    rows = sorted(range(0, grid_y, pitch))
    gap = int(pinned_mask.sum()) - target
    if gap > 0:
        # too many pinned cells: shave cells off channel ends, farthest from
        # the centre first
        order = []
        for y in rows:
            order += [(y, x) for x in range(grid_x - 1, -1, -1)
                      if (y, x) in cells]
        for x in cols:
            order += [(y, x) for y in range(grid_y - 1, -1, -1)
                      if (y, x) in cells and (y, x) not in set(order)]
        for cell in order:
            if gap <= 0:
                break
            if cell not in cells:
                continue
            trial = cells - {cell}
            _, mask = apply_channels(T, sorted(trial), src, T_cool,
                                     strength=strength)
            if int(mask.sum()) < int(pinned_mask.sum()):
                cells = trial
                pinned_mask = mask
                gap -= 1
    elif gap < 0:
        # too few: add back cells at channel ends (cannot happen with a full
        # lattice, but keeps the function honest if the bisection is replaced)
        pass

    gap = int(pinned_mask.sum()) - target
    Tc, pinned_mask = apply_channels(T, sorted(cells), src, T_cool,
                                     strength=strength)

    L = 0.5 * (grid_x + grid_y) * pitch_mm
    n_ch = len(rows) + len(cols)
    r = float(np.sqrt(total_area_mm2 / (max(1, len(cells)) * np.pi)))
    dp = 8.0 * MU * L * (Q_TOTAL / n_ch) / (np.pi * r ** 4) if r > 0 else 0.0
    return Group.from_field(f"lattice p{pitch} {len(rows)}x{len(cols)} gap{gap}", Tc,
                            pinned_mask, dp, total_area_mm2, len(cells), n_ch,
                            T_cool, hotspot_frac, pitch_mm)


def radial_group_total(T: np.ndarray, src: np.ndarray, target_total: int,
                       total_area_mm2: float, grid_x: int, grid_y: int,
                       pitch_mm: float = PITCH_MM, T_cool: float = T_COOL,
                       hotspot_frac: float = 0.25,
                       strength: np.ndarray | None = None,
                       h_conv: float = 0.0, T_ambient: float | None = None) -> Group:
    """Per-chip straight-pipe family matched on TOTAL channel cells (C5).

    C5 / TASK-5 (2026-10-17), protocol pre-registered in
    DEFECT_REMEDIATION_PLAN.md §10.13. The standing convention
    (`radial_group_pinned`) matches the control to the tree on PINNED
    cells -- equal ACTIVE cooling capacity, in-model. C5 asks the opposite
    convention: equal TOTAL channel footprint (a manufacturing-length
    proxy). Under equal totals the control usually converts more of its
    length into pinned cells than the tree, because the tree's greedy
    growth deliberately spends budget inside the source blocks (exempt
    from pinning by the fairness rule). That asymmetry is an in-model
    artifact -- over-the-die channels are the most valuable ones in a real
    plate -- so the E2 verdict rule requires the pinned asymmetry to be
    reported alongside any direction flip before a topology claim.

    Construction (pre-registered): for each chip (cluster order), straight
    pipes spanning the FULL line through the chip (v: entire column, h:
    entire row; orientation by nearest plate edge, same rule as
    radial_group_pinned), fanned around the chip at offsets
    0, +1, -1, +2, -2, ...; chip streams concatenated; first
    `target_total` unique cells. Total-cell matching is purely
    combinatorial, so ONE apply_channels at the end suffices.
    """
    centers = _cluster_centers(src)
    target = int(target_total)

    # Per-chip geometry: orientation and the fan-offset order around it.
    plans = []
    for cy, cx in centers:
        cy, cx = int(round(cy)), int(round(cx))
        d_top, d_bot = cy, grid_y - 1 - cy
        d_left, d_right = cx, grid_x - 1 - cx
        d = min(d_top, d_bot, d_left, d_right)
        orient = "v" if (d == d_top or d == d_bot) else "h"
        offs = [0]
        for k in range(1, max(grid_x, grid_y)):
            offs += [k, -k]
        plans.append((cy, cx, orient, offs))

    # Round-robin stream: at each fan offset every chip contributes one line
    # before any chip advances to the next offset. This places every chip's
    # centre line (offset 0) before the target is exhausted, so C1 is
    # satisfiable on 3+ chip layouts. The old chip-by-chip concatenation
    # starved later chips of any cells and made radial C1 fail at every
    # swept target.
    stream: list[tuple[int, int]] = []
    max_offs = max(len(p[3]) for p in plans)
    for k in range(max_offs):
        for cy, cx, orient, offs in plans:
            if k >= len(offs):
                continue
            off = offs[k]
            if orient == "v":
                x = cx + off
                if not (0 <= x < grid_x):
                    continue
                stream += [(y, x) for y in range(grid_y)]
            else:
                y = cy + off
                if not (0 <= y < grid_y):
                    continue
                stream += [(y, x) for x in range(grid_x)]

    seen: set[tuple[int, int]] = set()
    uniq: list[tuple[int, int]] = []
    for c in stream:
        if c in seen:
            continue
        seen.add(c)
        uniq.append(c)
        if len(uniq) >= target:
            break
    if len(uniq) < target:
        raise ValueError(f"radial fan saturates at {len(uniq)} < {target} cells")

    Tc, pinned = apply_channels(T, uniq, src, T_cool, strength=strength,
                                h_conv=h_conv, T_ambient=T_ambient)
    r = float(np.sqrt(total_area_mm2 / (len(uniq) * np.pi)))
    L = 0.5 * (grid_x + grid_y) * pitch_mm
    dp = (8.0 * MU * L * (Q_TOTAL / max(1, len(uniq))) / (np.pi * r ** 4)
          if r > 0 else 0.0)
    return Group.from_field(f"radial-total x{len(uniq)}", Tc, pinned, dp,
                            total_area_mm2, len(uniq), len(uniq), T_cool,
                            hotspot_frac, pitch_mm, cells=uniq)


def lattice_group_total(T: np.ndarray, src: np.ndarray, target_total: int,
                        total_area_mm2: float, grid_x: int, grid_y: int,
                        pitch_mm: float = PITCH_MM, T_cool: float = T_COOL,
                        hotspot_frac: float = 0.25,
                        strength: np.ndarray | None = None) -> Group:
    """Uniform lattice matched on TOTAL channel cells (C5, §10.13).

    Pitch bisection on the COMBINATORIAL count (no field re-solve is
    needed to count cells):

        total(p) = R*grid_x + C*grid_y - R*C,
        R = ceil(grid_y/p), C = ceil(grid_x/p)

    Take the SMALLEST p with total(p) <= target -- the DENSEST lattice
    that does not exceed the target. (The first implementation bisected
    the other way and found the LARGEST such p, i.e. the SPARSEST lattice:
    on a 50x50 plate p=50 is just two lines / 99 cells, so every control
    starved at 196 cells against tree totals of 400-1300 and the tree
    "won" 18/18 against a phantom. Caught before any E-verdict was
    consumed; see DEFECT_REMEDIATION_PLAN.md §10.13.) Then complete to
    the exact total with the cells of the next-denser lattice (p-1) that
    are absent from the p lattice, ordered centre-out by manhattan
    distance to the plate centre. Deterministic; single-cell completion
    mirrors the shaving philosophy of `lattice_group`. By minimality of
    p, total(p-1) > target, so the completion can always reach the exact
    target; an assertion enforces it.
    """
    target = int(target_total)

    def lines(p: int) -> tuple[list[int], list[int], set]:
        rows = list(range(0, grid_y, p))
        cols = list(range(0, grid_x, p))
        cells: set = set()
        for y in rows:
            cells.update((y, x) for x in range(grid_x))
        for x in cols:
            cells.update((y, x) for y in range(grid_y))
        return rows, cols, cells

    _, _, dense = lines(1)
    if len(dense) < target:
        raise ValueError(f"lattice saturates at {len(dense)} < {target} cells")

    lo, hi = 1, max(grid_x, grid_y)
    chosen = None
    while lo <= hi:
        mid = (lo + hi) // 2
        rows, cols, cells = lines(mid)
        if len(cells) <= target:
            chosen = (mid, rows, cols, cells)
            hi = mid - 1   # densest feasible: try SMALLER p (more cells)
        else:
            lo = mid + 1   # too dense: total exceeds target, go sparser
    if chosen is None:
        raise ValueError(f"lattice bisection failed for target {target}")
    pitch, rows, cols, cells = chosen

    if len(cells) < target:
        _, _, denser = lines(max(1, pitch - 1))
        cy0, cx0 = (grid_y - 1) / 2.0, (grid_x - 1) / 2.0
        extra = sorted((c for c in denser if c not in cells),
                       key=lambda c: (abs(c[0] - cy0) + abs(c[1] - cx0),
                                      c[0], c[1]))
        for c in extra:
            if len(cells) >= target:
                break
            cells.add(c)
    if len(cells) != target:
        raise ValueError(
            f"lattice-total completion reached {len(cells)} != {target}")

    cell_list = sorted(cells)
    Tc, pinned = apply_channels(T, cell_list, src, T_cool, strength=strength)
    L = 0.5 * (grid_x + grid_y) * pitch_mm
    n_ch = len(rows) + len(cols)
    r = float(np.sqrt(total_area_mm2 / (max(1, len(cells)) * np.pi)))
    dp = 8.0 * MU * L * (Q_TOTAL / n_ch) / (np.pi * r ** 4) if r > 0 else 0.0
    return Group.from_field(f"lattice-total p{pitch} x{len(cells)}", Tc,
                            pinned, dp, total_area_mm2, len(cells), n_ch,
                            T_cool, hotspot_frac, pitch_mm, cells=cell_list)


def _cluster_centers(src: np.ndarray) -> list[tuple[int, int]]:
    """Centroids of the connected components of the source mask (one per chip)."""
    m = src.copy()
    out: list[tuple[int, int]] = []
    while m.any():
        ys, xs = np.nonzero(m)
        stack = [(int(ys[0]), int(xs[0]))]
        m[stack[0]] = False
        pts: list[tuple[int, int]] = []
        while stack:
            y, x = stack.pop()
            pts.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < m.shape[0] and 0 <= nx < m.shape[1] and m[ny, nx]:
                    m[ny, nx] = False
                    stack.append((ny, nx))
        ay = np.array([p[0] for p in pts])
        ax = np.array([p[1] for p in pts])
        out.append((float(ay.mean()), float(ax.mean())))
    return out


def poiseuille_dp(edges, radii, grid_x: int, pitch_mm: float = PITCH_MM,
                  as_network: bool = True) -> float:
    """Dimensionless pressure drop of the tree, default = NETWORK solve.

    §10.11 FIX: this used to SUM 8*mu*L*Q/(pi*r^4) over every segment, i.e.
    treat the tree as a SERIES pipe. The tree is a single-inlet /
    multi-outlet branching network, so its inlet-to-outlet drop is the drop
    along ONE root-to-leaf PATH.

    §10.12: the flow convention is DEMAND-DRIVEN (project convention A):
    each leaf carries its design load, Q_parent = sum(Q_children). This is
    the convention Murray's law is derived for and the one `node_flows`,
    `assign_radii`, and the control group all use. The alternative
    (resistance-driven, all leaves shorted onto one manifold) is reported
    by `calibrate.tree_dp_pa` as `dp_kirchhoff_reference_pa`; on this tree
    it gives 2.9x the demand-driven value because the geometry is deeply
    asymmetric (leaf depths 11..16, subtree resistances spanning 35.6x).

    `as_network=False` restores the serial sum, kept ONLY for reproducing
    historical numbers.

    PITCH WARNING (DEFECT_REMEDIATION_PLAN.md §10.9, P0b v3): the default
    `pitch_mm = field.PITCH_MM = 1.0` is the DIMENSIONLESS solver constant.
    The resulting dp is in arbitrary units and is only meaningful as a
    tree-vs-control ratio on the toy board. Any REAL-UNIT dp (Pa, kPa) must
    instead be computed by `calibrate.tree_dp_pa(..., calibrate.paper_grid_mm())`,
    which uses the mapped 0.9 mm pitch and refuses the dimensionless one.
    """
    from radius import build_tree, node_flows
    children, parent, depth, root = build_tree(edges)
    nodes = set(parent) | set(parent.values()) | {root}
    demand = node_flows(edges)
    total_demand = demand[root]

    def r_edge(p: int, c: int) -> float:
        r = min(radii[p], radii[c])
        return 8.0 * MU * pitch_mm / (np.pi * r ** 4)

    q = {v: demand[v] / total_demand for v in nodes}

    if not as_network:
        return sum(r_edge(p, c) * q[c] for p, c in edges)

    def path_dp(v: int) -> float:
        ch = children.get(v)
        if not ch:
            return 0.0
        return max(r_edge(v, c) * q[c] + path_dp(c) for c in ch)

    return path_dp(root)


def compare(tree: Group, straight: Group) -> dict:
    def fmt(g: Group) -> dict:
        return {
            "T_max_C": round(g.T_max, 3),
            "R_th_C_per_W": round(g.R_th, 4),
            "T_mean_solid_C": round(g.T_mean_solid, 3),
            "hotspot_area_mm2": round(g.hotspot_area, 3),
            "pressure_drop": round(g.dp, 4),
            "material_mm2": round(g.total_area_mm2, 3),
            "segments": g.n_segments,
            "channels": g.n_channels,
        }

    bits = []
    d = tree.T_max - straight.T_max
    bits.append("cooler" if d < -1e-6 else "hotter" if d > 1e-6 else "tied on T_max")
    dm = tree.T_mean_solid - straight.T_mean_solid
    # 1e-6 C is far below the solver tolerance (1e-7 on the update, ~1e-3 on
    # the converged field), so treat anything smaller as a genuine tie.
    bits.append("lower mean solid T" if dm < -1e-3
                else "higher mean solid T" if dm > 1e-3 else "tied on mean solid T")
    da = tree.hotspot_area - straight.hotspot_area
    bits.append("smaller hot zone" if da < -1e-6
                else "larger hot zone" if da > 1e-6 else "tied on hot zone")
    if tree.dp < straight.dp:
        bits.append("lower pressure drop")
    elif tree.dp > straight.dp:
        bits.append("higher pressure drop")
    else:
        bits.append("tied on pressure drop")

    return {
        "tree": fmt(tree),
        "straight": fmt(straight),
        "verdict": "tree: " + ", ".join(bits),
        "dT_max_tree_minus_straight": round(d, 3),
        "dT_mean_solid_tree_minus_straight": round(dm, 3),
        "dHotspot_area_tree_minus_straight": round(da, 3),
        "dp_ratio_tree_over_straight": round(tree.dp / straight.dp, 3) if straight.dp else None,
    }
