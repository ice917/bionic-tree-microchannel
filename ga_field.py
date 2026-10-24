# -*- coding: utf-8 -*-
"""真正的拓扑结构搜索：逐格点生长偏置场（3x3 低分辨率 → 上采样）+ 多目标 Pareto。

每个格点有自己的生长偏好 bias[j]，score = (T-Tmin) + bias[j]。
遗传算法搜索 3x3=9 维偏置场（+ max_nodes），让生成器"塑造"树的形态，
而不是只追最热。目标 = 加权和 T_max + λ·dp，扫描 λ 得到 Pareto 前沿。
"""
import heapq

import numpy as np

import field as F
import radius as Ra
import verify as V

GRID = 50
CENTERS = ((12, 12), (36, 12), (24, 36))   # 3 chips triangle
SRC_RADIUS = F.SRC_RADIUS_SYNTHETIC

T = F.solve_heat_sources(grid=GRID, centers=CENTERS,
                         source_radius=SRC_RADIUS).T
src = F.source_mask_multi(GRID, CENTERS, radius=SRC_RADIUS)
T_rise = T - float(T.min())


def decode_bias(genes):
    """9 维 genes → 3x3 低分辨率偏置场 → 最近邻上采样到 50x50。"""
    low = np.asarray(genes, dtype=float).reshape(3, 3)
    # 最近邻上采样（每块约 17x17，裁剪到 50x50）
    bias = np.kron(low, np.ones((17, 17)))[:GRID, :GRID]
    return bias


def grow_tree_field(max_nodes, bias):
    """score = T_rise + bias 的生长（bias 是 50x50 逐格点偏置场）。"""
    grid_y, grid_x = T.shape
    n = grid_y * grid_x
    score = T_rise + bias

    in_tree = np.zeros(n, dtype=bool)
    edges = []
    start = int(np.argmax(score))
    in_tree[start] = True
    heap = []

    def push(i):
        y, x = divmod(i, grid_x)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < grid_y and 0 <= nx < grid_x:
                j = ny * grid_x + nx
                if not in_tree[j]:
                    heapq.heappush(heap, (-float(score.flat[j]), j))

    push(start)
    while heap and len(edges) + 1 < max_nodes:
        _, j = heapq.heappop(heap)
        if in_tree[j]:
            continue
        in_tree[j] = True
        y, x = divmod(j, grid_x)
        best_parent, best_val = None, -np.inf
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < grid_y and 0 <= nx < grid_x:
                k = ny * grid_x + nx
                if in_tree[k] and float(score.flat[k]) > best_val:
                    best_val = float(score.flat[k])
                    best_parent = k
        if best_parent is None:
            continue
        edges.append((best_parent, j))
        push(j)
    return edges


def evaluate(genes, lam=0.0):
    """genes = [max_nodes, b1..b9]，返回加权目标 + 分量。"""
    max_nodes = int(round(genes[0]))
    bias = decode_bias(genes[1:])
    edges = grow_tree_field(max_nodes, bias)
    radii = Ra.assign_radii(edges, grid=GRID, r0=0.5)
    g = V.tree_group(T, src, edges, radii, GRID)
    tmax, dp = float(g.T_max), float(g.dp)
    return {"fit": tmax + lam * dp, "T_max": tmax, "dp": dp}


def genetic_search(bounds, fitness, pop_size=24, n_gen=12,
                   mut_rate=0.35, seed=0):
    rng = np.random.default_rng(seed)
    lo = np.array([b[0] for b in bounds], dtype=float)
    hi = np.array([b[1] for b in bounds], dtype=float)
    dim = len(bounds)

    pop = rng.random((pop_size, dim)) * (hi - lo) + lo
    history = []

    def score_all(p):
        return np.array([fitness(row) for row in p], dtype=float)

    scores = score_all(pop)
    bi = int(np.argmin(scores))
    best_x, best_score = pop[bi].copy(), float(scores[bi])
    history.append(best_score)

    for _ in range(n_gen):
        elite = pop[bi].copy()
        idx = rng.integers(0, pop_size, size=(pop_size, 2))
        winners = idx[np.arange(pop_size), np.argmin(scores[idx], axis=1)]
        parents = pop[winners]
        partner = np.roll(parents, 1, axis=0)
        alpha = rng.random((pop_size, 1))
        off = alpha * parents + (1 - alpha) * partner
        mask = rng.random((pop_size, dim)) < mut_rate
        delta = rng.normal(0, (hi - lo) * 0.08, size=(pop_size, dim))
        off = off + mask * delta
        off = np.clip(off, lo, hi)
        off[0] = elite
        pop = off
        scores = score_all(pop)
        bi = int(np.argmin(scores))
        if scores[bi] < best_score:
            best_x, best_score = pop[bi].copy(), float(scores[bi])
        history.append(best_score)

    return best_x, best_score, history


if __name__ == "__main__":
    BOUNDS = [(100, 500)] + [(-2.0, 2.0)] * 9   # max_nodes + 9 维偏置场

    # 基准：纯热场（偏置场=0）max_nodes=400
    base_genes = np.array([400.0] + [0.0] * 9)
    base = evaluate(base_genes, lam=0.0)
    print(f"基准 纯热场 max_nodes=400 : T_max={base['T_max']:.4f}  "
          f"dp={base['dp']:.3f}")

    # Pareto 前沿：扫描 λ（压降权重）
    print("\nλ 扫描（加权和 T_max + λ·dp，得到 Pareto 近似）:")
    pareto = []
    for lam in (0.0, 0.005, 0.02, 0.1):
        bx, bs, hist = genetic_search(
            BOUNDS,
            fitness=lambda row, lam=lam: evaluate(row, lam)["fit"],
            pop_size=16, n_gen=8, seed=0)
        r = evaluate(bx, lam=0.0)
        pareto.append((lam, r["T_max"], r["dp"], bx))
        print(f"  λ={lam:<6} → T_max={r['T_max']:.4f}  dp={r['dp']:.3f}  "
              f"(max_nodes={int(round(bx[0]))})")

    # 相对基准的改善
    print(f"\n相对基准（T_max={base['T_max']:.4f}, dp={base['dp']:.3f}）:")
    for lam, t, d, bx in pareto:
        print(f"  λ={lam:<6} ΔT_max={t - base['T_max']:+.4f}°C  "
              f"dp 比 {d / base['dp']:.2f}×")
