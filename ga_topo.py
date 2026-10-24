# -*- coding: utf-8 -*-
"""拓扑结构搜索：遗传算法搜索 (max_nodes, r0, gamma) 三维。

gamma = 生长热场敏感度：score = gamma*(T-Tmin) + (1-gamma)*noise。
  gamma=1  → 纯热场驱动（等价原 grow_tree）
  gamma=0  → 纯随机生长（完全放弃热场）
搜索 gamma 观察树形态如何随"偏离热场"变化，从而检验"热场驱动是否已是最优"。

温度场只解一次；每个个体只做 grow_tree_gamma + tree_group。
"""
import numpy as np

import field as F
import radius as Ra
import verify as V

GRID = 50
CENTERS = ((12, 12), (36, 12), (24, 36))   # 3 chips triangle
SRC_RADIUS = F.SRC_RADIUS_SYNTHETIC
RNG_SEED = 7

# ---- 温度场只解一次 ----
T = F.solve_heat_sources(grid=GRID, centers=CENTERS,
                         source_radius=SRC_RADIUS).T
src = F.source_mask_multi(GRID, CENTERS, radius=SRC_RADIUS)
T_rise = T - float(T.min())              # 温升（0 起）
NOISE = np.random.default_rng(RNG_SEED).standard_normal((GRID, GRID))


def grow_tree_gamma(max_nodes, gamma):
    """score = gamma*(T-Tmin) + (1-gamma)*noise 的热场敏感生长。

    gamma=1 恢复纯热场贪心（grow_tree）；gamma<1 引入与热场无关的随机偏差。
    返回 edges（[(parent, child)]），idx = y*grid + x。
    """
    grid_y, grid_x = T.shape
    n = grid_y * grid_x
    score = gamma * T_rise + (1.0 - gamma) * NOISE

    import heapq
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


def evaluate_tree(max_nodes, gamma, r0=0.5):
    edges = grow_tree_gamma(int(max_nodes), float(gamma))
    radii = Ra.assign_radii(edges, grid=GRID, r0=r0)
    g = V.tree_group(T, src, edges, radii, GRID)
    return {"T_max": float(g.T_max), "dp": float(g.dp),
            "pinned": int(g.pinned_cells), "segments": int(g.n_segments)}


def genetic_search(bounds, fitness, pop_size=18, n_gen=12,
                   mut_rate=0.3, seed=0):
    """二维连续基因 (max_nodes, gamma) 的遗传算法（numpy 向量化）。"""
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
        # 锦标赛选择
        idx = rng.integers(0, pop_size, size=(pop_size, 2))
        winners = idx[np.arange(pop_size), np.argmin(scores[idx], axis=1)]
        parents = pop[winners]
        # 算术交叉（环形配对）
        partner = np.roll(parents, 1, axis=0)
        alpha = rng.random((pop_size, 1))
        off = alpha * parents + (1 - alpha) * partner
        # 变异
        mask = rng.random((pop_size, dim)) < mut_rate
        delta = rng.normal(0, (hi - lo) * 0.1, size=(pop_size, dim))
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
    # 基准：gamma=1（纯热场）max_nodes=400
    base = evaluate_tree(400, 1.0)
    print(f"基准 gamma=1.0 max_nodes=400 : T_max={base['T_max']:.4f}  "
          f"dp={base['dp']:.3f}  pinned={base['pinned']}")

    # 观察 gamma 对拓扑形态的影响（固定 max_nodes=400）
    print("\ngamma 扫描（max_nodes=400，T_max 越小越好）:")
    for g in (0.0, 0.25, 0.5, 0.75, 1.0):
        r = evaluate_tree(400, g)
        print(f"  gamma={g:.2f} : T_max={r['T_max']:.4f}  "
              f"dp={r['dp']:.3f}  pinned={r['pinned']}")

    # GA 二维搜索 (max_nodes, gamma)
    best_x, best_score, history = genetic_search(
        bounds=((60, 600), (0.0, 1.0)),
        fitness=lambda row: evaluate_tree(row[0], row[1])["T_max"],
        pop_size=18, n_gen=12, seed=0)

    mn, g = int(round(best_x[0])), float(best_x[1])
    best = evaluate_tree(mn, g)
    print(f"\nGA 最优 max_nodes={mn} gamma={g:.3f} : "
          f"T_max={best['T_max']:.4f}  dp={best['dp']:.3f}  pinned={best['pinned']}")
    print("收敛历史: " + " ".join(f"{h:.4f}" for h in history))
    print(f"\n结论: gamma 收敛到 {g:.3f}（1.0=纯热场），"
          f"{'热场驱动生长已是最优' if g > 0.8 else '偏离热场反而更优'}")
