# -*- coding: utf-8 -*-
"""最小闭环：遗传算法（生成器）× evaluate 裁判。

多热源 3 芯片三角形布局，搜索树的节点预算 max_nodes，目标最小化 T_max。
温度场与 max_nodes 无关，故只解一次；每个个体只做 grow_tree + tree_group。
手写 GA（无 DEAP 依赖），种群操作用 numpy 向量化。
"""
import numpy as np

import field as F
import grow as G
import radius as Ra
import verify as V

GRID = 50
CENTERS = ((12, 12), (36, 12), (24, 36))   # 3 chips triangle（论文布局）
SRC_RADIUS = F.SRC_RADIUS_SYNTHETIC

# ---- 温度场只解一次（与 max_nodes 无关）----
T = F.solve_heat_sources(grid=GRID, centers=CENTERS,
                         source_radius=SRC_RADIUS).T
src = F.source_mask_multi(GRID, CENTERS, radius=SRC_RADIUS)


def evaluate_tree(max_nodes, r0=0.5):
    """复用预计算温度场，评估一个 max_nodes 对应的树。"""
    edges = G.grow_tree(T, max_nodes=int(max_nodes))
    radii = Ra.assign_radii(edges, grid=GRID, r0=r0)
    g = V.tree_group(T, src, edges, radii, GRID)
    return {"T_max": float(g.T_max), "dp": float(g.dp),
            "pinned": int(g.pinned_cells), "segments": int(g.n_segments)}


def genetic_search(bounds, fitness, pop_size=16, n_gen=12,
                   mut_rate=0.3, seed=0):
    """手写遗传算法：整数基因，锦标赛选择 + 算术交叉 + 变异 + 精英保留。

    fitness(x) 返回越小越好的标量。返回 (best_x, best_score, history)。
    """
    rng = np.random.default_rng(seed)
    lo, hi = bounds

    # 初始化种群（整数，numpy 向量）
    pop = rng.integers(lo, hi + 1, size=pop_size)
    history = []

    def score_all(p):
        # 评估整个种群（grow_tree 串行，但种群间无依赖）
        return np.array([fitness(x) for x in p], dtype=float)

    scores = score_all(pop)
    best_idx = int(np.argmin(scores))
    best_x, best_score = int(pop[best_idx]), float(scores[best_idx])
    history.append(best_score)

    for gen in range(n_gen):
        # 精英保留（最优个体直接进下一代）
        elite = pop[best_idx]

        # 锦标赛选择 pop_size 个父代（numpy 向量化）
        idx = rng.integers(0, pop_size, size=(pop_size, 2))
        winners = idx[np.arange(pop_size), np.argmin(scores[idx], axis=1)]
        parents = pop[winners].astype(float)

        # 算术交叉：每个父代与下一个（环形）配对，保持 pop_size 个
        partner = np.roll(parents, 1)
        alpha = rng.random(pop_size)
        offspring = np.round(alpha * parents + (1 - alpha) * partner).astype(int)

        # 变异（随机 +/- delta，numpy 向量化）
        mask = rng.random(pop_size) < mut_rate
        delta = rng.integers(-30, 31, size=pop_size)
        offspring = np.clip(offspring + mask * delta, lo, hi)

        # 精英替换第一个子代，保持 pop_size 个
        offspring[0] = elite
        pop = offspring

        scores = score_all(pop)
        best_idx = int(np.argmin(scores))
        if scores[best_idx] < best_score:
            best_x, best_score = int(pop[best_idx]), float(scores[best_idx])
        history.append(best_score)

    return best_x, best_score, history


if __name__ == "__main__":
    # 基准：论文的 max_nodes=400（r0=0.5）
    base = evaluate_tree(400)
    print(f"基准 max_nodes=400 : T_max={base['T_max']:.4f}  "
          f"dp={base['dp']:.3f}  pinned={base['pinned']}")

    best_x, best_score, history = genetic_search(
        bounds=(60, 600), fitness=lambda n: evaluate_tree(n)["T_max"],
        pop_size=16, n_gen=12, seed=0)

    best = evaluate_tree(best_x)
    print(f"\nGA 最优 max_nodes={best_x} : T_max={best['T_max']:.4f}  "
          f"dp={best['dp']:.3f}  pinned={best['pinned']}  segments={best['segments']}")

    print(f"\n收敛历史（每代最优 T_max）: "
          + " ".join(f"{h:.3f}" for h in history))

    gain = base["T_max"] - best["T_max"]
    print(f"\n相比基准 max_nodes=400，T_max 改善 {gain:+.4f} °C "
          f"({'更优' if gain > 0 else '无改善/更差'})")
