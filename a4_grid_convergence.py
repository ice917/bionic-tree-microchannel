"""A4: grid-convergence (GCI) study of the conduction discretisation.

WHAT THIS TESTS
---------------
Every thermal number in the paper (T_max, R_th, the tree-vs-control margin,
R7's 0/18) is produced by ONE discretisation: the 5-point Laplacian on a
50x50 lattice, solved by Jacobi to 1e-7. The paper has never reported a
grid-refinement study, so its discretisation error is unknown. This script
measures it with a geometry-preserving refinement (Richardson / Roache GCI,
Fs = 1.25).

WHAT CAN AND CANNOT BE REFINED
------------------------------
The hydraulic network is an ALGEBRAIC solve on a fixed graph (radii from
Murray's law, dp from Poiseuille); it has no mesh and no h to refine. GCI
therefore applies ONLY to the conduction field.

The thermal geometry (source blocks, channel cells, 1-unit boundary
frame) is defined as a union of unit cells, so it can be refined EXACTLY by
nearest-neighbour upsampling: coarse cell (y,x) -> k x k fine cells. That
keeps the physical regions bit-identical (same area, same width, same
outline), which removes the staircase error that usually pollutes a GCI and
leaves only the discretisation error of the PDE. The 1-unit-thick outer
Dirichlet frame is upsampled too -- pinning only the outermost fine cell
would change the boundary condition, not the mesh.

CASES (all at 50x50 physical units, total power fixed)
  bare    no channels (the dimensionless q=1 bare field)
  tree    the canonical 400-node heat-grown tree, channels pinned at 25 C
  ctrl    the equal-occupancy straight-channel control (8 full-height pipes)
  margin  T_max(ctrl) - T_max(tree): the ranking the paper actually uses

SOURCE CONVENTION: q = 1 per source cell, in the "4T - sum(T_nb) = rhs"
form this is rhs = 1. That is exactly what `verify.apply_channels` uses
when `strength` is None, i.e. the convention behind EVERY thermal number in
the paper (table 5, table 10's tree row, all topology margins). The GCI is
computed on the temperature RISE, which is linear in the source strength,
so p and the relative GCI carry over to any rescaling of the same problem.

Regression: at N=50 the same cases are re-solved with the project's own
`verify.apply_channels` (Jacobi) and compared with the direct solver used
here, so a difference in the solver -- not in the grid -- cannot be mistaken
for a convergence result.

Output: outputs/a4_grid_convergence.json (+ console table).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

import field as F
import grow as G
import verify as V

OUT = Path(__file__).resolve().parent / "outputs"
OUT.mkdir(exist_ok=True)

GRID0 = 50                    # coarse level
PLATE_UNITS = 50.0            # physical plate width in coarse-cell units
FRAME_UNITS = 1.0             # thickness of the 25 C outer frame
LEVELS = (50, 100, 200, 400, 800)  # refinement sequence, ratio 2
T0 = 25.0
SRC_RADIUS = F.SRC_RADIUS_SYNTHETIC   # 5x5 block = the table-10 case
MAX_NODES = 400

# Source strength in the "4T - sum(T_nb) = rhs" form. q=1 per source cell
# is the production convention (verify.apply_channels with strength=None).
RHS_CELL = 1.0

# Physical calibration constants, recorded only for rescaling the report
# (rise_phys = rise_dimensionless * Q_CELL_W/(K_SI*T_SLAB_M)); not used in
# the solve, which is linear and scale-free.
Q_CELL_W = 253.0 / 25.0       # W per coarse source cell
K_SI = 148.0                  # W/(m K)
T_SLAB_M = 5.0e-3             # m


def upsample(mask: np.ndarray, k: int) -> np.ndarray:
    return np.repeat(np.repeat(mask, k, axis=0), k, axis=1)


def frame_mask(n: int, k: int) -> np.ndarray:
    """Outer frame of FRAME_UNITS physical thickness = k fine cells."""
    m = np.zeros((n, n), dtype=bool)
    m[:k, :] = m[-k:, :] = True
    m[:, :k] = m[:, -k:] = True
    return m


def solve_dirichlet(pinned: np.ndarray, rhs: np.ndarray, t0: float = T0) -> np.ndarray:
    """Exact (to CG tolerance) solution of 4T - sum(T_nb) = rhs.

    Dirichlet cells (pinned) and their contribution move to the RHS.
    """
    n = pinned.shape[0]
    unk = ~pinned.ravel()
    idx = -np.ones(n * n, dtype=np.int64)
    idx[unk] = np.arange(int(unk.sum()))
    m = int(unk.sum())

    rows, cols, vals = [], [], []
    b = np.zeros(m, dtype=float)
    r = rhs.ravel()
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb = -np.ones((n, n), dtype=np.int64)
        y0, y1 = (0, n - dy) if dy >= 0 else (-dy, n)
        x0, x1 = (0, n - dx) if dx >= 0 else (-dx, n)
        nb[y0:y1, x0:x1] = np.arange(n * n).reshape(n, n)[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
        valid = nb >= 0
        cell = np.arange(n * n)
        src_ok = unk
        # unknown cell p with unknown neighbour nb -> -1 in the matrix
        sel = valid.ravel() & src_ok & (unk[nb.ravel()])
        rows.append(idx[cell[sel]])
        cols.append(idx[nb.ravel()[sel]])
        vals.append(-np.ones(int(sel.sum())))
        # unknown cell p with Dirichlet neighbour -> +T0 on the RHS
        sel2 = valid.ravel() & src_ok & (~unk[nb.ravel()])
        b[idx[cell[sel2]]] += t0

    rows.append(idx[unk])
    cols.append(idx[unk])
    vals.append(4.0 * np.ones(m))

    A = sp.csr_matrix((np.concatenate(vals),
                       (np.concatenate(rows), np.concatenate(cols))),
                      shape=(m, m))
    b += r[unk]
    x, info = spla.cg(A, b, rtol=1e-14, atol=0.0, maxiter=20000)
    if info != 0:
        raise RuntimeError(f"CG did not converge, info={info}")
    res = float(np.max(np.abs(A @ x - b)))
    T = np.full(n * n, t0, dtype=float)
    T[unk] = x
    return T.reshape(n, n), res


def build_cases():
    """Coarse-level geometry: masks for bare / tree / straight control."""
    src = F.source_mask(GRID0, ((GRID0 - 1) // 2, (GRID0 - 1) // 2), radius=SRC_RADIUS)
    Td = F.normalize_field(
        F.solve_heat_sources(grid=GRID0, centers=[(25, 25)],
                             source_radius=SRC_RADIUS).T, T_target=100.0)
    edges = G.grow_tree(Td, max_nodes=MAX_NODES)
    nodes = sorted(set([p for p, _ in edges] + [c for _, c in edges]))
    tree_cells = [(i // GRID0, i % GRID0) for i in nodes]
    tree_mask = V.channel_mask((GRID0, GRID0), tree_cells, src)

    n_ctrl = max(1, len(nodes) // GRID0)          # same rule as heat_tree.py
    c = GRID0 // 2
    half = n_ctrl // 2
    xs = [c - half + k for k in range(n_ctrl) if 0 <= c - half + k < GRID0]
    ctrl_cells = [(y, x) for x in xs for y in range(GRID0)]
    ctrl_mask = V.channel_mask((GRID0, GRID0), ctrl_cells, src)

    return src, tree_mask, ctrl_mask, len(nodes), len(xs)


def run_case(src, chan, n, k, rhs_coarse):
    """One level. rhs_coarse is the RHS per coarse source cell (q=1)."""
    fine = n // GRID0
    assert fine == k
    src_f = upsample(src, k)
    pin_f = upsample(chan, k) | frame_mask(n, k)
    rhs = np.zeros((n, n), dtype=float)
    rhs[src_f] = rhs_coarse / (k * k)     # same source strength per unit area
    T, res = solve_dirichlet(pin_f, rhs)
    return T, src_f, pin_f, res


def gci(f1: float, f2: float, f3: float, r: float = 2.0) -> dict:
    d21, d32 = f2 - f1, f3 - f2
    out = {"f": [f1, f2, f3], "d21": d21, "d32": d32}
    if d21 == 0.0 or d32 == 0.0 or d21 * d32 <= 0.0:
        out.update(p=None, f_ext=None, gci_fine_pct=None,
                   note="no monotone convergence (sign change or zero delta)")
        return out
    p = abs(math.log(abs(d32 / d21)) / math.log(r))
    denom = r ** p - 1.0
    f_ext = f3 + d32 / denom
    gci_fine = 1.25 * abs(d32 / f3) / denom if f3 != 0.0 else float("nan")
    out.update(p=p, f_ext=f_ext, gci_fine_pct=100.0 * gci_fine,
               coarse_err_pct=100.0 * abs(f1 - f_ext) / abs(f_ext),
               note="")
    return out


def source_ring(src: np.ndarray) -> list[tuple[int, int]]:
    """8-connected ring of non-source cells immediately outside the source block."""
    ys, xs = np.where(src)
    y0, y1, x0, x1 = ys.min() - 1, ys.max() + 1, xs.min() - 1, xs.max() + 1
    return [(y, x) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)
            if 0 <= y < src.shape[0] and 0 <= x < src.shape[1] and not src[y, x]]


def square_peak_coeff(m_max: int = 399) -> float:
    """Centre value of -laplacian(T) = 1 on the unit square, T = 0 on all sides.

    Fourier series: T(1/2,1/2) = (16/pi^4) sum_{m,n odd} sin(m pi/2)
    sin(n pi/2) / (m n (m^2+n^2)). Converges fast; m_max = 399 is ample.
    Used as an INDEPENDENT check on the Richardson extrapolation: the ringed
    5x5 source block is, in the continuum limit, exactly this problem with
    a = 5h, so rise -> coeff * 5^2.
    """
    s = 0.0
    for m in range(1, m_max + 1, 2):
        for n in range(1, m_max + 1, 2):
            s += (math.sin(m * math.pi / 2) * math.sin(n * math.pi / 2)
                  / (m * n * (m * m + n * n)))
    return 16.0 * s / math.pi ** 4


def main() -> None:
    src, tree_mask, ctrl_mask, n_nodes, n_ctrl = build_cases()
    print(f"coarse: nodes={n_nodes}  straight channels={n_ctrl}  "
          f"src cells={int(src.sum())}  tree pinned={int(tree_mask.sum())}  "
          f"ctrl pinned={int(ctrl_mask.sum())}")

    rhs_coarse = RHS_CELL   # K per coarse source cell in 4T - sum(T_nb) = rhs

    # Degeneracy check: if every cell of the ring around the source block is
    # pinned, T_max is the solution of the isolated 5x5 block with a Dirichlet
    # ring and does not depend on the network beyond that ring.
    ring = source_ring(src)
    enclosure = {name: {"ring_cells": len(ring),
                        "ring_pinned": int(sum(bool(m[y, x]) for y, x in ring))}
                 for name, m in (("tree", tree_mask), ("ctrl", ctrl_mask))}
    for name, e in enclosure.items():
        print(f"  source ring pinned ({name}): {e['ring_pinned']}/{e['ring_cells']}")

    results = {}
    for name, chan in (("bare", np.zeros_like(src)),
                       ("tree", tree_mask),
                       ("ctrl", ctrl_mask)):
        rec = []
        for n in LEVELS:
            k = n // GRID0
            T, src_f, pin_f, res = run_case(src, chan, n, k, rhs_coarse)
            rec.append({"N": n, "T_max": float(T.max()),
                        "rise": float(T.max() - T0),
                        "solid_mean": float(T[~pin_f].mean()),
                        "lin_residual": res,
                        "n_unknown": int((~pin_f).sum())})
            print(f"  {name:4s} N={n:4d}  T_max={T.max():9.4f} C  "
                  f"rise={T.max()-T0:8.4f} K  res={res:.2e}")
        results[name] = rec

    # margin between control and tree at each level
    results["margin"] = [
        {"N": a["N"], "rise": b["rise"] - a["rise"]}
        for a, b in zip(results["tree"], results["ctrl"])
    ]
    for r in results["margin"]:
        print(f"  margin N={r['N']:4d}  dTmax(ctrl-tree)={r['rise']:+8.4f} K")

    print("\nGCI (r = 2, Fs = 1.25), every consecutive triple:")
    summary = {}
    for name, rec in results.items():
        key = "rise"
        f = [x[key] for x in rec]
        triples = []
        for i in range(len(f) - 2):
            g = gci(f[i], f[i + 1], f[i + 2], 2.0)
            g["levels"] = [LEVELS[i], LEVELS[i + 1], LEVELS[i + 2]]
            triples.append(g)
            if g["p"] is None:
                print(f"  {name:6s} {str(g['levels']):>20s}  {g['note']}")
            else:
                print(f"  {name:6s} {str(g['levels']):>20s}  p={g['p']:.3f}  "
                      f"f_ext={g['f_ext']:.6f}  GCI_fine={g['gci_fine_pct']:.4f}%  "
                      f"coarse_err={g['coarse_err_pct']:.4f}%")
        g = gci(f[-3], f[-2], f[-1], 2.0)
        g["levels"] = list(LEVELS[-3:])
        g["triples"] = triples
        summary[name] = g

    # ---- independent analytic check of the extrapolated limit -----------
    # In the continuum limit the innermost pinned ring cell approaches the
    # block edge, so the problem -> -laplacian(T)=1 on a square of side
    # a = 2*SRC_RADIUS+1 with T=0 on the boundary. Its centre value is exact.
    side = 2.0 * SRC_RADIUS + 1.0
    coeff = square_peak_coeff()
    rise_analytic = coeff * side * side
    f_ext = summary["tree"]["f_ext"]
    n50_rise = results["tree"][0]["rise"]
    err_ext_pct = 100.0 * (f_ext - rise_analytic) / rise_analytic
    err_n50_pct = 100.0 * (n50_rise - rise_analytic) / rise_analytic
    print(f"\nanalytic limit (a={side:g}, T=0 on block edge): "
          f"rise={rise_analytic:.9f} K  (coeff={coeff:.15f})")
    print(f"  Richardson f_ext = {f_ext:.6f} K  -> {err_ext_pct:+.3f}% vs analytic")
    print(f"  N=50 rise        = {n50_rise:.6f} K  -> {err_n50_pct:+.2f}% vs analytic")

    # ---- regression against the project's Jacobi solver at N=50 ----------
    field_bare = F.solve_heat_sources(grid=GRID0, centers=[(24, 24)],
                                      source_radius=SRC_RADIUS,
                                      q=RHS_CELL, k=1.0, T_boundary=T0,
                                      max_iter=200000, tol=1e-12)
    mine, _, _, _ = run_case(src, np.zeros_like(src), GRID0, 1, rhs_coarse)
    d_bare = float(np.max(np.abs(mine - field_bare.T)))
    print(f"\nregression bare  N=50 vs field.solve_heat_sources: "
          f"max|dT|={d_bare:.2e} K")

    # channel case: reproduce the paper's table-10 configuration and compare
    cells_tree = [(y, x) for y in range(GRID0) for x in range(GRID0)
                  if tree_mask[y, x]]
    T_jac, _ = V.apply_channels(np.full((GRID0, GRID0), T0), cells_tree, src,
                                T_cool=T0, max_iter=400000, tol=1e-10)
    T_mine, _, _, _ = run_case(src, tree_mask, GRID0, 1, rhs_coarse)
    d_tree = float(np.max(np.abs(T_mine - T_jac)))
    print(f"regression tree  N=50 vs verify.apply_channels(tol=1e-10): "
          f"max|dT|={d_tree:.2e} K  (mine {T_mine.max():.4f}, "
          f"jacobi {T_jac.max():.4f})")

    # production tolerance: the 20 000-iteration Jacobi the paper actually uses
    T_prod, _ = V.apply_channels(np.full((GRID0, GRID0), T0), cells_tree, src,
                                 T_cool=T0)
    d_prod = float(np.max(np.abs(T_prod - T_mine)))
    print(f"production tree  N=50 verify.apply_channels(default tol): "
          f"max|dT|={d_prod:.2e} K  (T_max {T_prod.max():.4f})")

    payload = {
        "levels": list(LEVELS),
        "gci": summary,
        "cases": results,
        "regression": {"bare_vs_field_max_dT": d_bare,
                       "tree_vs_jacobi_1e-10_max_dT": d_tree,
                       "production_tol_max_dT": d_prod,
                       "table10_T_max_N50": results["tree"][0]["T_max"]},
        "source_enclosure": enclosure,
        "analytic_check": {"side_units": side, "centre_coeff": coeff,
                           "rise_analytic": rise_analytic,
                           "richardson_f_ext": f_ext,
                           "richardson_vs_analytic_pct": err_ext_pct,
                           "n50_rise": n50_rise,
                           "n50_vs_analytic_pct": err_n50_pct},
        "config": {"grid0": GRID0, "plate_units": PLATE_UNITS,
                   "frame_units": FRAME_UNITS, "src_radius": SRC_RADIUS,
                   "max_nodes": MAX_NODES, "rhs_cell": RHS_CELL,
                   "source_center": [24, 24], "growth_center": [25, 25],
                   "physical_rescale": Q_CELL_W / (K_SI * T_SLAB_M),
                   "q_cell_w": Q_CELL_W, "k_si": K_SI, "t_slab_m": T_SLAB_M},
    }
    (OUT / "a4_grid_convergence.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {OUT / 'a4_grid_convergence.json'}")


if __name__ == "__main__":
    main()
