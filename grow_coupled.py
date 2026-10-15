"""Step 2b: coupled growth -- the tree reshapes the field it grows in.

Static growth (grow.py) computes the field once, then walks it. That is
physically backwards: a real vascular network removes heat as it grows, so
the field it is navigating keeps changing under it.

This module grows the tree step by step and re-solves the field after every
`recalc_every` steps, with the current channel cells pinned at T_cool. The
next step therefore navigates a field that already feels the tree.

Cost: one extra PDE solve per step. With warm-starting (previous field as
the initial guess) the re-solves converge in far fewer iterations than the
cold solve, so the overhead is ~O(1) solves per step rather than O(max_iter).

Determinism is preserved: no randomness anywhere, so repeated runs give
identical trees.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass

import numpy as np

from field import PITCH_MM

T_COOL = 25.0


@dataclass
class CoupledResult:
    edges: list[tuple[int, int]]
    T_final: np.ndarray            # field with the finished tree pinned
    n_recalcs: int                 # how many times the field was re-solved
    total_inner_iters: int         # total Jacobi steps across all re-solves
    history: list[dict]            # per-step record for plotting


def _solve_with_channels(T0: np.ndarray, src: np.ndarray, pinned: np.ndarray,
                         T_cool: float = T_COOL, max_iter: int = 20000,
                         tol: float = 1e-6) -> tuple[np.ndarray, int]:
    """Jacobi solve with `pinned` cells held at T_cool, warm-started at T0.

    Source cells are never pinned -- a channel that swallowed the source
    would delete the heat it is meant to remove.
    """
    src_b = (PITCH_MM**2 / 4.0) * src[1:-1, 1:-1]
    Tc = T0.copy()
    Tc[pinned] = T_cool
    it = 0
    for _ in range(max_iter):
        Tn = Tc.copy()
        Tn[1:-1, 1:-1] = (
            0.25 * (Tc[2:, 1:-1] + Tc[:-2, 1:-1] + Tc[1:-1, 2:] + Tc[1:-1, :-2])
            + src_b
        )
        Tn[pinned] = T_cool
        Tn[0, :] = T_cool
        Tn[-1, :] = T_cool
        Tn[:, 0] = T_cool
        Tn[:, -1] = T_cool
        if float(np.max(np.abs(Tn - Tc))) < tol:
            return Tn, it + 1
        Tc = Tn
        it += 1
    return Tc, it


def grow_coupled(T_init: np.ndarray, src: np.ndarray, max_nodes: int = 400,
                 recalc_every: int = 1, T_cool: float = T_COOL,
                 T_target: float = 100.0) -> CoupledResult:
    """Grow the tree while the field reacts to it.

    T_init must already be normalised (peak = T_target). After each recalc
    the field is re-normalised to the same peak so that the growth rule sees
    a comparable temperature scale throughout (otherwise the absolute level
    drifts down as channels are added and the "hottest neighbour" rule
    becomes dominated by the drift rather than by geometry).
    """
    grid_y, grid_x = T_init.shape
    n = grid_y * grid_x
    max_nodes = min(max_nodes, n)

    in_tree = np.zeros(n, dtype=bool)
    pinned = np.zeros((grid_y, grid_x), dtype=bool)
    edges: list[tuple[int, int]] = []
    history: list[dict] = []

    T = T_init.copy()
    n_recalcs = 0
    total_iters = 0

    def renormalise(field: np.ndarray) -> np.ndarray:
        rise = float(field.max() - T_cool)
        if rise <= 0:
            return field
        return T_cool + (field - T_cool) * (T_target - T_cool) / rise

    start = int(np.argmax(T))
    in_tree[start] = True
    pinned[start] = True

    heap: list[tuple[float, int]] = []

    def push_neighbors(i: int) -> None:
        y, x = divmod(i, grid_x)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < grid_y and 0 <= nx < grid_x:
                j = ny * grid_x + nx
                if not in_tree[j]:
                    heapq.heappush(heap, (-float(T.flat[j]), j))

    push_neighbors(start)
    step = 0
    while heap and len(edges) + 1 < max_nodes:
        _, j = heapq.heappop(heap)
        if in_tree[j]:
            continue
        in_tree[j] = True
        pinned[j] = True

        y, x = divmod(j, grid_x)
        best_parent, best_val = None, -np.inf
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < grid_y and 0 <= nx < grid_x:
                k = ny * grid_x + nx
                if in_tree[k] and float(T.flat[k]) > best_val:
                    best_val = float(T.flat[k])
                    best_parent = k
        if best_parent is None:
            continue
        edges.append((best_parent, j))
        step += 1

        history.append({
            "step": step,
            "T_max_at_choice": round(float(T.max()), 4),
            "chosen_cell_T": round(float(T.flat[j]), 4),
        })

        push_neighbors(j)

        # --- the coupling: the field reacts to the tree ---
        if step % recalc_every == 0:
            T, it = _solve_with_channels(T, src, pinned & ~src, T_cool)
            T = renormalise(T)
            n_recalcs += 1
            total_iters += it
            # temperatures changed -> the heap's keys are stale, rebuild it
            heap = [(-float(T.flat[k]), k) for k in range(n)
                    if not in_tree[k] and _is_frontier(k, in_tree, grid_x, grid_y)]
            heapq.heapify(heap)

    # final field with the whole tree pinned
    T_final, it = _solve_with_channels(T, src, pinned & ~src, T_cool)
    n_recalcs += 1
    total_iters += it

    return CoupledResult(edges=edges, T_final=T_final, n_recalcs=n_recalcs,
                         total_inner_iters=total_iters, history=history)


def _is_frontier(k: int, in_tree: np.ndarray, grid_x: int, grid_y: int) -> bool:
    """True if cell k is not in the tree but touches it."""
    if in_tree[k]:
        return False
    y, x = divmod(k, grid_x)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ny, nx = y + dy, x + dx
        if 0 <= ny < grid_y and 0 <= nx < grid_x:
            if in_tree[ny * grid_x + nx]:
                return True
    return False
