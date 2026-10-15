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


def source_mask(grid: int, center: tuple[int, int], radius: float = 2.0) -> np.ndarray:
    """Square source mask of half-width `radius` cells around `center`=(y, x)."""
    cy, cx = center
    yy, xx = np.mgrid[0:grid, 0:grid]
    return (np.abs(yy - cy) <= radius) & (np.abs(xx - cx) <= radius)


def source_mask_multi(grid: int, centers, radius: float = 2.0) -> np.ndarray:
    """Union of square source masks around several centres.

    `centers` is an iterable of (y, x). Overlapping blocks merge, so two
    sources closer than 2*radius+1 cells behave as one elongated source.
    """
    yy, xx = np.mgrid[0:grid, 0:grid]
    m = np.zeros((grid, grid), dtype=bool)
    for cy, cx in centers:
        m |= (np.abs(yy - cy) <= radius) & (np.abs(xx - cx) <= radius)
    return m


def _solve_poisson(src_b: np.ndarray, grid: int, T_init: float,
                   T_boundary: float, max_iter: int, tol: float) -> FieldResult:
    """Jacobi to steady state for a fixed interior source term.

    Split out of solve_heat so the single- and multi-source solvers share one
    discretisation (and therefore one sanity check).
    """
    T = np.full((grid, grid), float(T_init))
    it = 0
    converged = False
    residual = np.inf
    while it < max_iter:
        Tn = T.copy()
        Tn[1:-1, 1:-1] = (
            0.25 * (T[2:, 1:-1] + T[:-2, 1:-1] + T[1:-1, 2:] + T[1:-1, :-2])
            + src_b
        )
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
    source_radius: float = 2.0,
    q: float = 1.0,
    T_boundary: float = 25.0,
    T_init: float = 25.0,
    max_iter: int = 20000,
    tol: float = 1e-6,
    source_center: tuple[int, int] | None = None,
    k: float = 1.0,
) -> FieldResult:
    """Return the steady temperature field on a grid x grid plate.

    k is the plate conductivity in the same length units as PITCH_MM. With
    the default k=1 the update is the dimensionless PROJECT.md 2.1 form, and
    every number reported before the real-unit calibration is reproduced
    bit-for-bit. Passing a physical k rescales the field by exactly 1/k
    (the Poisson problem is linear), so it can be applied post-hoc instead.
    """
    if grid < 5:
        raise ValueError("grid too small")

    cy, cx = source_center if source_center is not None else ((grid - 1) // 2, (grid - 1) // 2)
    src = source_mask(grid, (cy, cx), source_radius)
    src_b = (q * PITCH_MM**2 / (4.0 * k)) * src[1:-1, 1:-1]
    return _solve_poisson(src_b, grid, T_init, T_boundary, max_iter, tol)


def solve_heat_sources(
    grid: int = 50,
    centers=((24, 24),),
    source_radius: float = 2.0,
    q: float = 1.0,
    T_boundary: float = 25.0,
    T_init: float = 25.0,
    max_iter: int = 20000,
    tol: float = 1e-6,
    k: float = 1.0,
) -> FieldResult:
    """Steady field for several equal-strength sources (multi-chip layout).

    q is per source cell, so N sources of the same size carry N times the
    total power -- the intended "N identical chips" reading.
    """
    if grid < 5:
        raise ValueError("grid too small")
    src = source_mask_multi(grid, centers, source_radius)
    src_b = (q * PITCH_MM**2 / (4.0 * k)) * src[1:-1, 1:-1]
    return _solve_poisson(src_b, grid, T_init, T_boundary, max_iter, tol)


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
