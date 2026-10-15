"""Step 2: heat-seeking channel tree (Prim variant).

Graph = grid (nodes = cells, edges = 4-neighbour, weight 1).
Start at the hottest cell; repeatedly absorb the tree-adjacent cell with the
HIGHEST temperature. Branching is emergent (a cell has only 4 neighbours),
never coded.

PROJECT.md says "until the tree covers the field" -- taken literally that
produces a spanning tree of every cell, which (a) fills the plate with
channel and (b) makes Step 5 degenerate (all cells pinned at T_cool). We
therefore grow to a budget of `max_nodes` cells: the tree is a *channel
network* embedded in the solid, exactly as in the leaf-vein analogy.

Returns edges as [(parent_idx, child_idx)] with idx = y*grid + x.
"""
from __future__ import annotations

import heapq

import numpy as np


def grow_tree(T: np.ndarray, max_nodes: int | None = None) -> list[tuple[int, int]]:
    """Grow the tree from the hottest cell of T.

    Selection rule: among all cells adjacent to the current tree, take the
    one with the maximum temperature. Ties broken deterministically by
    (temperature desc, index asc).
    """
    grid_y, grid_x = T.shape
    n = grid_y * grid_x
    if max_nodes is None:
        max_nodes = n

    in_tree = np.zeros(n, dtype=bool)
    edges: list[tuple[int, int]] = []

    start = int(np.argmax(T))
    in_tree[start] = True

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

    while heap and len(edges) + 1 < max_nodes:
        _, j = heapq.heappop(heap)
        if in_tree[j]:
            continue                      # stale heap entry
        in_tree[j] = True

        # parent = hottest already-in-tree neighbour
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
        push_neighbors(j)

    return edges


def tree_cells(edges: list[tuple[int, int]]) -> list[int]:
    """Node indices of the tree (root first, BFS order)."""
    if not edges:
        return []
    children: dict[int, list[int]] = {}
    for p, c in edges:
        children.setdefault(p, []).append(c)
    root = edges[0][0]
    order, stack = [root], [root]
    while stack:
        v = stack.pop(0)
        for ch in children.get(v, []):
            order.append(ch)
            stack.append(ch)
    return order


def coverage_stats(edges: list[tuple[int, int]], grid_x: int) -> dict:
    cells = tree_cells(edges)
    return {"nodes": len(cells), "edges": len(edges), "cells": cells}


def branching_histogram(edges: list[tuple[int, int]]) -> dict:
    """Degree distribution (emergent-branching evidence)."""
    deg: dict[int, int] = {}
    for p, c in edges:
        deg[p] = deg.get(p, 0) + 1
        deg[c] = deg.get(c, 0) + 1
    hist: dict[int, int] = {}
    for d in deg.values():
        hist[d] = hist.get(d, 0) + 1
    return dict(sorted(hist.items()))


def shape_signature(edges: list[tuple[int, int]], grid_x: int, grid_y: int) -> dict:
    """Cheap shape fingerprint used to prove that moving the source moves the
    tree (field-driven, not hard-coded)."""
    cells = tree_cells(edges)
    ys = np.array([i // grid_x for i in cells])
    xs = np.array([i % grid_x for i in cells])
    return {
        "centroid_x": round(float(xs.mean()), 3),
        "centroid_y": round(float(ys.mean()), 3),
        "bbox_x": [int(xs.min()), int(xs.max())],
        "bbox_y": [int(ys.min()), int(ys.max())],
        "cell_hash": int(sum((int(x) * 31 + int(y) * 17) for x, y in zip(xs, ys)) % 1000003),
    }
