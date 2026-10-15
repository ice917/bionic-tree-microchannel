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


def solve_heat(
    grid: int = 50,
    source_radius: float = 2.0,
    q: float = 1.0,
    T_boundary: float = 25.0,
    T_init: float = 25.0,
    max_iter: int = 20000,
    tol: float = 1e-6,
    source_center: tuple[int, int] | None = None,
) -> FieldResult:
    """Return the steady temperature field on a grid x grid plate."""
    if grid < 5:
        raise ValueError("grid too small")

    cy, cx = source_center if source_center is not None else ((grid - 1) // 2, (grid - 1) // 2)
    src = source_mask(grid, (cy, cx), source_radius)

    # source term of the discrete Poisson update
    src_b = (q * PITCH_MM**2 / 4.0) * src[1:-1, 1:-1]

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
