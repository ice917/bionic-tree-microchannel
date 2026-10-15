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

    @staticmethod
    def from_field(name: str, Tc: np.ndarray, pinned: np.ndarray, dp: float,
                   area: float, n_segments: int, n_channels: int,
                   T_cool: float = T_COOL, hotspot_frac: float = 0.25,
                   pitch_mm: float = PITCH_MM) -> "Group":
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
        )


def channel_mask(T_shape, channel_cells, src: np.ndarray) -> np.ndarray:
    """Boolean mask of cells held at T_cool (never a source cell)."""
    mask = np.zeros(T_shape, dtype=bool)
    for (y, x) in channel_cells:
        mask[y, x] = True
    return mask & ~src


def apply_channels(T: np.ndarray, channel_cells, src: np.ndarray,
                   T_cool: float = T_COOL, max_iter: int = 20000,
                   tol: float = 1e-7):
    """Re-solve conduction with channel cells pinned at T_cool.

    Returns (field, pinned_mask). The heat source is preserved: source cells
    keep generating heat and are never pinned (a channel that swallowed the
    source would delete the heat it is meant to remove).
    """
    mask = channel_mask(T.shape, channel_cells, src)

    src_b = (PITCH_MM**2 / 4.0) * src[1:-1, 1:-1]
    Tc = T.copy()
    Tc[mask] = T_cool
    for _ in range(max_iter):
        Tn = Tc.copy()
        Tn[1:-1, 1:-1] = (
            0.25 * (Tc[2:, 1:-1] + Tc[:-2, 1:-1] + Tc[1:-1, 2:] + Tc[1:-1, :-2])
            + src_b
        )
        Tn[mask] = T_cool
        Tn[0, :] = T_cool
        Tn[-1, :] = T_cool
        Tn[:, 0] = T_cool
        Tn[:, -1] = T_cool
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
               hotspot_frac: float = 0.25) -> Group:
    cells = [(i // grid_x, i % grid_x)
             for i in sorted(set([p for p, _ in edges] + [c for _, c in edges]))]
    Tc, pinned = apply_channels(T, cells, src, T_cool)
    dp = poiseuille_dp(edges, radii, grid_x, pitch_mm)
    area = tree_material_mm2(edges, radii)
    return Group.from_field("tree", Tc, pinned, dp, area, len(edges), len(edges),
                            T_cool, hotspot_frac, pitch_mm)


def straight_group(T: np.ndarray, src: np.ndarray, n_channels: int, total_area_mm2: float,
                   grid_x: int, grid_y: int, pitch_mm: float = PITCH_MM,
                   T_cool: float = T_COOL, hotspot_frac: float = 0.25) -> Group:
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
    Tc, pinned = apply_channels(T, cells, src, T_cool)

    L = grid_y * pitch_mm
    dp = 8.0 * MU * L * (Q_TOTAL / len(xs)) / (np.pi * r ** 4)
    return Group.from_field(f"straight x{len(xs)}", Tc, pinned, dp, total_area_mm2,
                            len(xs), len(xs), T_cool, hotspot_frac, pitch_mm)


def poiseuille_dp(edges, radii, grid_x: int, pitch_mm: float = PITCH_MM) -> float:
    """Sum 8*mu*L*Q/(pi*r^4) over segments.

    Flow through a segment = downstream leaf demand, normalised so the root
    carries Q_TOTAL. Radius of a tapered segment = the smaller end (throat).
    """
    from radius import build_tree, node_flows
    children, parent, depth, root = build_tree(edges)
    flow = node_flows(edges)

    total_flow = flow[root]
    dp = 0.0
    for p, c in edges:
        L = pitch_mm
        Q = flow[p] / total_flow
        r = min(radii[p], radii[c])
        dp += 8.0 * MU * L * Q / (np.pi * r ** 4)
    return dp


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
