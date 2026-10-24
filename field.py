"""Step 1: 2D steady heat field (finite difference) + sanity checks.

Solves  lap T = -q/k  on a square grid with fixed-temperature boundaries,
by Jacobi iteration to steady state (max|dT| < tol).

Discretisation (5-point Laplacian, h = PITCH_MM, k = 1):

    (T_E + T_W + T_N + T_S - 4*T_P)/h^2 = -q_P
    =>  T_P = (T_E + T_W + T_N + T_S)/4 + q_P*h^2/4

Sanity check: a *point* heat source in 2D must decay logarithmically,
T ~ -(Q/2*pi)*ln(r) + const, where Q = q_P*h^2 is the power of one cell.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# 1 mm grid spacing -> grid cells * PITCH_MM = plate size (see PROJECT.md 2.1)
PITCH_MM = 1.0

# Source footprint. TWO calibrated conventions, both explicit:
#   SRC_RADIUS_REAL = 8.0  -> 17x17 = 289 cells = 234 mm^2 per die,
#       108 W/cm^2 at 253 W. This is the REAL-scale footprint (i7-14700K:
#       98 W/cm^2) and the default for every multi-chip / physical run.
#   SRC_RADIUS_SYNTHETIC = 2.0  -> 5x5 = 25 cells, 1249 W/cm^2. This is the
#       concentrated block the single-source chain was BUILT on (REPORT.md §4)
#       and §22.4 ruled a deliberately retained synthetic extreme, NOT an
#       oversight. Any script that needs the synthetic case must now pass
#       this constant explicitly -- it is no longer reachable by omission.
# The old default (2.0 everywhere) is what let a caller run the physical
# comparison at 12.7x the real power density without noticing; see
# DEFECT_REMEDIATION_PLAN.md §4 (conservation was caller discipline, not a
# structural guarantee).
SRC_RADIUS_REAL = 8.0
SRC_RADIUS_SYNTHETIC = 2.0

# Real-unit calibration (REPORT.md §11). The default run is dimensionless
# (k=1, q in grid units); PHYSICAL below holds the published constants the
# dimensionless numbers were mapped onto, with sources.
K_SILICON = 148.0        # W/(m K), single-crystal Si near 300 K
                         # https://www.universitywafer.com/silicon-wafer-thermal-conductivity.html
K_COPPER = 400.0         # W/(m K)
                         # same source


@dataclass
class FieldResult:
    T: np.ndarray                 # (grid, grid) steady temperature [C]
    iterations: int               # Jacobi steps used
    converged: bool
    residual: float               # final max|dT|


def source_mask(grid: int, center: tuple[int, int],
                radius: float = SRC_RADIUS_REAL) -> np.ndarray:
    """Square source mask of half-width `radius` cells around `center`=(y, x).

    Default is the REAL-scale footprint (SRC_RADIUS_REAL). The synthetic
    5x5 block is still available as SRC_RADIUS_SYNTHETIC.
    """
    cy, cx = center
    yy, xx = np.mgrid[0:grid, 0:grid]
    return (np.abs(yy - cy) <= radius) & (np.abs(xx - cx) <= radius)


def source_mask_multi(grid: int, centers, radius: float = SRC_RADIUS_REAL,
                      powers=None) -> np.ndarray:
    """Union of square source masks around several centres.

    `centers` is an iterable of (y, x). Overlapping blocks merge, so two
    sources closer than 2*radius+1 cells behave as one elongated source.
    """
    yy, xx = np.mgrid[0:grid, 0:grid]
    m = np.zeros((grid, grid), dtype=bool)
    for cy, cx in centers:
        m |= (np.abs(yy - cy) <= radius) & (np.abs(xx - cx) <= radius)
    return m


def source_strength_multi(grid: int, centers,
                          radius: float = SRC_RADIUS_REAL, powers=None) -> np.ndarray:
    """Per-cell source strength for several chips.

    `powers` holds the RELATIVE weight of each centre. The weights are
    normalised so that a chip carrying `powers[k]` receives the share

        q_cell[k] = base * powers[k] / mean(powers)

    i.e. [1, 2, 3] and [2, 4, 6] give the IDENTICAL field, and the TOTAL
    power of the layout is base * len(centers) regardless of the weights.
    This is the "total power is an input, distribution is a shape" split
    used by MOOSE (TotalPower + power_shape_function) and SimScale
    (absolute vs specific power source), and it is what makes the layout's
    total power independent of how unevenly the chips are loaded.

    The previous behaviour -- powers as ABSOLUTE per-cell multipliers, so
    [1, 2, 3] carried 6 units of total power -- made the layout's total
    power a silent function of the power ratios: raising one chip's load
    raised the whole board's dissipation. Experiments run under that
    convention (REPORT.md §10 unequal-power rows, DEFECT_REMEDIATION_PLAN
    §5.11 R26) are archived under the absolute convention and are NOT
    comparable with post-migration runs; see §5.9a.
    """
    yy, xx = np.mgrid[0:grid, 0:grid]
    s = np.zeros((grid, grid), dtype=float)
    if powers is None:
        w = [1.0] * len(list(centers))
    else:
        w = [float(p) for p in powers]
        mean = sum(w) / len(w)
        if mean <= 0.0:
            raise ValueError(f"powers must have a positive mean, got {powers}")
        w = [p / mean for p in w]
    for k, (cy, cx) in enumerate(centers):
        s[(np.abs(yy - cy) <= radius) & (np.abs(xx - cx) <= radius)] += w[k]
    return s


def _solve_poisson(src_b: np.ndarray, grid: int, T_init: float,
                   T_boundary: float, max_iter: int, tol: float,
                   h_conv: float = 0.0, T_ambient: float | None = None) -> FieldResult:
    """Jacobi to steady state for a fixed interior source term.

    Split out of solve_heat so the single- and multi-source solvers share one
    discretisation (and therefore one sanity check).

    `h_conv` selects the boundary condition:
      h_conv = 0  -> Dirichlet: the boundary ring is held at T_boundary.
                     This is the ideal-cold-sink model used by every result
                     in REPORT.md up to and including section 17, and it is
                     reproduced BIT-FOR-BIT when h_conv is left at 0.
      h_conv > 0  -> Robin (finite convection): the boundary ring exchanges
                     heat with the ambient at rate h_conv [a.u.] and the
                     boundary ring itself is now an unknown that is solved
                     for, not prescribed. This is the physically real case
                     (a plate edge bolted to a cold plate, not welded to a
                     perfect heat sink), and it is the only idealisation
                     REPORT.md section 14.6 listed as untested.

    Robin discretisation, ghost-node form for a boundary cell P with one
    outside neighbour at T_amb:

        (T_in + T_amb - 2*T_P)/h^2 + q_P = h_conv*(T_amb - T_P)
        =>  T_P = (T_in + T_amb*(1 + Bi)) / (2 + Bi),   Bi = h_conv*h/k

    With k = 1 and h = PITCH_MM = 1 this reduces to (T_in + T_amb*(1+Bi))/(2+Bi).
    At Bi -> 0 it collapses to (T_in + T_amb)/2, NOT to the Dirichlet value --
    so h_conv=0 must keep taking the Dirichlet branch, which it does.
    """
    T = np.full((grid, grid), float(T_init))
    if T_ambient is None:
        T_ambient = T_boundary
    Bi = h_conv * PITCH_MM          # k = 1, h = PITCH_MM
    it = 0
    converged = False
    residual = np.inf
    while it < max_iter:
        Tn = T.copy()
        Tn[1:-1, 1:-1] = (
            0.25 * (T[2:, 1:-1] + T[:-2, 1:-1] + T[1:-1, 2:] + T[1:-1, :-2])
            + src_b
        )
        if Bi > 0.0:
            # Robin on all four edges: each edge cell has exactly one interior
            # neighbour and one ghost at T_ambient.
            a = 1.0 + Bi
            b = 2.0 + Bi
            Tn[0, 1:-1] = (Tn[1, 1:-1] + a * T_ambient) / b
            Tn[-1, 1:-1] = (Tn[-2, 1:-1] + a * T_ambient) / b
            Tn[1:-1, 0] = (Tn[1:-1, 1] + a * T_ambient) / b
            Tn[1:-1, -1] = (Tn[1:-1, -2] + a * T_ambient) / b
            # corners: two interior neighbours
            Tn[0, 0] = (Tn[1, 0] + Tn[0, 1] + 2.0 * a * T_ambient) / (2.0 * b)
            Tn[0, -1] = (Tn[1, -1] + Tn[0, -2] + 2.0 * a * T_ambient) / (2.0 * b)
            Tn[-1, 0] = (Tn[-2, 0] + Tn[-1, 1] + 2.0 * a * T_ambient) / (2.0 * b)
            Tn[-1, -1] = (Tn[-2, -1] + Tn[-1, -2] + 2.0 * a * T_ambient) / (2.0 * b)
        else:
            Tn[0, :] = T_boundary
            Tn[-1, :] = T_boundary
            Tn[:, 0] = T_boundary
            Tn[:, -1] = T_boundary

        residual = float(np.max(np.abs(Tn - T)))
        T = Tn
        it += 1
        if residual < tol:
            converged = True
            break

    return FieldResult(T=T, iterations=it, converged=converged, residual=residual)


def solve_heat(
    grid: int = 50,
    source_radius: float = SRC_RADIUS_REAL,
    q: float = 1.0,
    T_boundary: float = 25.0,
    T_init: float = 25.0,
    max_iter: int = 20000,
    tol: float = 1e-6,
    source_center: tuple[int, int] | None = None,
    k: float = 1.0,
    h_conv: float = 0.0,
    T_ambient: float | None = None,
) -> FieldResult:
    """Return the steady temperature field on a grid x grid plate.

    k is the plate conductivity in the same length units as PITCH_MM. With
    the default k=1 the update is the dimensionless PROJECT.md 2.1 form, and
    every number reported before the real-unit calibration is reproduced
    bit-for-bit. Passing a physical k rescales the field by exactly 1/k
    (the Poisson problem is linear), so it can be applied post-hoc instead.

    h_conv / T_ambient switch the boundary condition from the ideal Dirichlet
    cold sink to a finite-convection (Robin) edge. h_conv=0 (the default)
    reproduces every pre-2026-10-16 result bit-for-bit; see _solve_poisson.

    source_radius defaults to SRC_RADIUS_REAL (the real die footprint). The
    synthetic 5x5 block of REPORT.md §4 is SRC_RADIUS_SYNTHETIC and must be
    requested explicitly.
    """
    if grid < 5:
        raise ValueError("grid too small")

    cy, cx = source_center if source_center is not None else ((grid - 1) // 2, (grid - 1) // 2)
    src = source_mask(grid, (cy, cx), source_radius)
    src_b = (q * PITCH_MM**2 / (4.0 * k)) * src[1:-1, 1:-1]
    return _solve_poisson(src_b, grid, T_init, T_boundary, max_iter, tol,
                          h_conv=h_conv, T_ambient=T_ambient)


def solve_heat_sources(
    grid: int = 50,
    centers=((24, 24),),
    source_radius: float = SRC_RADIUS_REAL,
    q: float = 1.0,
    T_boundary: float = 25.0,
    T_init: float = 25.0,
    max_iter: int = 20000,
    tol: float = 1e-6,
    k: float = 1.0,
    powers=None,
    h_conv: float = 0.0,
    T_ambient: float | None = None,
) -> FieldResult:
    """Steady field for several sources (multi-chip layout).

    q is the default per-cell source strength, applied UNCONDITIONALLY to
    every cell (scaling it only when `powers` is given makes it a silent
    no-op in the equal-power case -- the bug that let the concentrated 5x5
    model's power quietly change by the cell-count ratio). `powers` holds
    the chips' RELATIVE weights, normalised to a constant layout total; see
    source_strength_multi. Real-scale runs use source_radius =
    SRC_RADIUS_REAL; the synthetic 5x5 block of REPORT.md §4 is
    SRC_RADIUS_SYNTHETIC.
    """
    if grid < 5:
        raise ValueError("grid too small")
    # `q` scales every cell's strength. It must be applied UNCONDITIONALLY:
    # scaling only when `powers` is given makes `q` a silent no-op in the
    # (by far most common) equal-power case, which is how the concentrated
    # 5x5 model's 253 W could never be re-spread over a real die footprint
    # without the total power quietly changing by the cell-count ratio.
    strength = source_strength_multi(grid, centers, source_radius, powers)
    strength = strength * (q / 1.0)
    src_b = (PITCH_MM**2 / (4.0 * k)) * strength[1:-1, 1:-1]
    return _solve_poisson(src_b, grid, T_init, T_boundary, max_iter, tol,
                          h_conv=h_conv, T_ambient=T_ambient)


def solve_heat_3d(
    grid: int = 50,
    depth: int = 10,
    source_radius: float = SRC_RADIUS_REAL,
    q: float = 1.0,
    T_boundary: float = 25.0,
    T_init: float = 25.0,
    max_iter: int = 20000,
    tol: float = 1e-6,
    source_center: tuple[int, int] | None = None,
    k: float = 1.0,
    channels_2d: np.ndarray | None = None,
    T_cool: float = 25.0,
    channel_top_gap: int = 0,
    h_base: float | None = None,
) -> FieldResult:
    """Steady conduction on a grid x grid x depth block, physically a cold plate.

    This is the CORRECT 3D analogue of the 2D model (the previous version used
    fixed-temperature on all six faces and a source column through the full
    depth, which the paper records as 'pseudo-3D' with no z-direction
    spreading). The physical model here is:

      * bottom face z=0      : fixed temperature T_boundary (cooled base)
      * top face z=depth-1   : adiabatic, with the heat source on the top layer
                               (the chip sits on top and dissipates downward)
      * side faces x/y       : adiabatic (insulated package)

    In 2D a point source decays as -ln(r), in 3D as 1/r; every conclusion drawn
    on the 2D field therefore rests on an assumption that this solver exists to
    test. Discretisation: 7-point Laplacian in the interior; adiabatic faces are
    enforced by first-order mirror (zero normal flux).

    Two idealisations are lifted by keyword, both OFF by default so every
    stored result is reproduced bit-for-bit:

      channel_top_gap > 0
          Clamp the channel columns only below the top skin, i.e. z in
          [0, depth-1-gap), leaving `gap` solid layers carrying the source.
          With the default 0 the clamp runs through the full depth; because
          the tree sprouts from the hottest cell and the straight group
          always spans the source footprint, the mask then covers every
          source cell, the injected heat is overwritten by T_cool on the
          first sweep, and the solver converges in one iteration to the
          uniform field T_cool. That degeneracy is why a full-depth clamp
          cannot be used for a tree-vs-straight comparison.

      h_base (finite convection at the cooled base)
          None keeps the base isothermal at T_boundary (infinite sink).
          h_base > 0 makes the base an unknown exchanging heat with the
          coolant at T_boundary, with the same Bi = h*PITCH_MM/k convention
          as the 2D Robin branch in _solve_poisson:

              (sum of 4 in-plane + 1 vertical conduction neighbours
               + Bi*T_boundary) / (5 + Bi)

          i.e. one conduction conductance is replaced by a convective one.
    """
    if grid < 5 or depth < 3:
        raise ValueError("grid too small or depth too shallow")
    if not 0 <= channel_top_gap <= depth - 2:
        raise ValueError("channel_top_gap must leave at least one source layer")
    if h_base is not None and h_base < 0.0:
        raise ValueError("h_base must be non-negative")

    cy, cx = source_center if source_center is not None else ((grid - 1) // 2, (grid - 1) // 2)
    yy, xx = np.mgrid[0:grid, 0:grid]
    mask2 = (np.abs(yy - cy) <= source_radius) & (np.abs(xx - cx) <= source_radius)
    # source only on the TOP layer (z=depth-1): the chip injects heat at the
    # top surface, which then conducts down to the cooled base.
    src = np.zeros((depth, grid, grid), dtype=bool)
    src[depth - 1, mask2] = True

    T = np.full((depth, grid, grid), float(T_init))
    c = q * PITCH_MM**2 / (6.0 * k)
    Bi_base = 0.0 if h_base is None else h_base * PITCH_MM / k
    it = 0
    converged = False
    residual = np.inf
    while it < max_iter:
        Tn = T.copy()
        # interior z=1..depth-2: 7-point Laplacian (no source here)
        Tn[1:-1, 1:-1, 1:-1] = (
            T[2:, 1:-1, 1:-1] + T[:-2, 1:-1, 1:-1]
            + T[1:-1, 2:, 1:-1] + T[1:-1, :-2, 1:-1]
            + T[1:-1, 1:-1, 2:] + T[1:-1, 1:-1, :-2]
        ) / 6.0
        # top layer z=depth-1: adiabatic top face (mirror -> duplicate the
        # lower z-neighbour) + the surface source term
        Tn[-1, 1:-1, 1:-1] = (
            T[-1, 1:-1, 2:] + T[-1, 1:-1, :-2]
            + T[-1, 2:, 1:-1] + T[-1, :-2, 1:-1]
            + 2.0 * T[-2, 1:-1, 1:-1]
        ) / 6.0 + c * src[-1, 1:-1, 1:-1]
        # bottom face z=0: isothermal sink, or finite convection to the coolant
        if h_base is None:
            Tn[0, :, :] = T_boundary
        else:
            Tn[0, 1:-1, 1:-1] = (
                T[0, 1:-1, 2:] + T[0, 1:-1, :-2]
                + T[0, 2:, 1:-1] + T[0, :-2, 1:-1]
                + T[1, 1:-1, 1:-1] + Bi_base * T_boundary
            ) / (5.0 + Bi_base)
        # side faces x/y: adiabatic (mirror)
        Tn[:, 0, :] = Tn[:, 1, :]
        Tn[:, -1, :] = Tn[:, -2, :]
        Tn[:, :, 0] = Tn[:, :, 1]
        Tn[:, :, -1] = Tn[:, :, -2]
        # channels: fixed-temperature columns below the solid top skin
        if channels_2d is not None:
            Tn[:depth - channel_top_gap, channels_2d] = T_cool
        residual = float(np.max(np.abs(Tn - T)))
        T = Tn
        it += 1
        if residual < tol:
            converged = True
            break
    return FieldResult(T=T, iterations=it, converged=converged, residual=residual)


def normalize_field(T: np.ndarray, T_boundary: float = 25.0, T_target: float = 100.0) -> np.ndarray:
    """Rescale a linear field so its peak is T_target (PROJECT.md: centre ~100 C).

    The Poisson problem is affine in q, so this is exactly the solution for a
    different source strength -- no approximation.
    """
    rise = float(T.max() - T_boundary)
    if rise <= 0:
        return T.copy()
    return T_boundary + (T - T_boundary) * (T_target - T_boundary) / rise


def solve_heat_point_source(
    grid: int = 121,
    q_point: float = 1.0,
    T_boundary: float = 25.0,
    max_iter: int = 60000,
    tol: float = 1e-9,
) -> np.ndarray:
    """Point (single-cell) heat source field, used only by the sanity check."""
    T = np.full((grid, grid), float(T_boundary))
    c = grid // 2
    src = np.zeros((grid, grid), dtype=bool)
    src[c, c] = True
    src_b = (q_point * PITCH_MM**2 / 4.0) * src[1:-1, 1:-1]

    for _ in range(max_iter):
        Tn = T.copy()
        Tn[1:-1, 1:-1] = (
            0.25 * (T[2:, 1:-1] + T[:-2, 1:-1] + T[1:-1, 2:] + T[1:-1, :-2])
            + src_b
        )
        Tn[0, :] = T_boundary
        Tn[-1, :] = T_boundary
        Tn[:, 0] = T_boundary
        Tn[:, -1] = T_boundary
        if float(np.max(np.abs(Tn - T))) < tol:
            return Tn
        T = Tn
    return T


def sanity_check_log_decay(T: np.ndarray, q_point: float = 1.0, rings: int = 12) -> dict:
    """Check the T ~ -ln(r) decay around a point source.

    Compares the measured slope dT/d(ln r) with the 2D analytic value
    -Q/(2*pi) where Q = q_point*h^2 is the power of the single source cell.
    """
    grid = T.shape[0]
    c = (grid - 1) / 2.0
    yy, xx = np.mgrid[0:grid, 0:grid]
    r = np.hypot(yy - c, xx - c)

    rs, Ts = [], []
    for rad in range(1, rings + 1):
        mask = (np.abs(r - rad) < 0.5) & (r > 0.5)
        if not np.any(mask):
            continue
        rs.append(float(np.mean(r[mask])))
        Ts.append(float(np.mean(T[mask])))

    lnr = np.log(np.array(rs))
    Tv = np.array(Ts)
    slope = float(np.polyfit(lnr, Tv, 1)[0])
    analytic = -q_point * PITCH_MM**2 / (2.0 * np.pi)
    pred = np.polyval(np.polyfit(lnr, Tv, 1), lnr)
    r2 = float(1.0 - np.sum((Tv - pred) ** 2) / np.sum((Tv - Tv.mean()) ** 2))

    return {
        "r": rs,
        "T": Ts,
        "slope_measured": slope,
        "slope_analytic": analytic,
        "r2_log_fit": r2,
        "pass": bool(r2 > 0.999 and 0.8 < slope / analytic < 1.25),
    }
