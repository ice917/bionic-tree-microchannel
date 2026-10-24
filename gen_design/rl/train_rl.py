# -*- coding: utf-8 -*-
"""RL 生长策略：REINFORCE 训练一个"学会生长"的策略，替代贪心追热。

策略 = softmax(θ · features(边界格点))，特征 = [温升, -到最近源距离, 1]。
每步按策略采样一个边界格点附着到树；树长满 max_nodes 后，奖励 = -(T_max + λ·dp)。
用策略梯度（REINFORCE + 运行平均 baseline）更新 θ。
"""
import sys

import numpy as np

sys.path.insert(0, r"d:\解释token\heat_tree")
import field as F
import radius as Ra
import verify as V

GRID = 50
CENTERS = ((12, 12), (36, 12), (24, 36))
SRC_RADIUS = F.SRC_RADIUS_SYNTHETIC
R0 = 0.5
MAX_NODES = 400

T = F.solve_heat_sources(grid=GRID, centers=CENTERS,
                         source_radius=SRC_RADIUS).T
src = F.source_mask_multi(GRID, CENTERS, radius=SRC_RADIUS)
T_rise = T - float(T.min())

# 预计算：到最近热源中心的距离（归一化用）
yy, xx = np.mgrid[0:GRID, 0:GRID]
dist_src = np.stack([np.hypot(yy - cy, xx - cx) for cy, cx in CENTERS]).min(axis=0)

# 归一化特征场（量纲统一）
F_T = T_rise / float(T_rise.max())          # 0..1
F_D = -dist_src / float(dist_src.max())     # -1..0（越近越大）


def _boundary(in_tree):
    ys, xs = np.nonzero(in_tree.reshape(GRID, GRID))
    out = set()
    for y, x in zip(ys, xs):
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < GRID and 0 <= nx < GRID:
                j = ny * GRID + nx
                if not in_tree[j]:
                    out.add(j)
    return list(out)


def grow_rl(theta, rng):
    """RL 生长：每步 softmax 采样边界格点。返回 (edges, log_probs, grad_terms)。"""
    in_tree = np.zeros(GRID * GRID, dtype=bool)
    start = int(np.argmax(T_rise))
    in_tree[start] = True
    edges = []
    log_probs = []
    grad_terms = []   # 每个 step 的 ∇θ log π = f(chosen) - E_π[f]

    for _ in range(MAX_NODES - 1):
        b = _boundary(in_tree)
        if not b:
            break
        # 特征矩阵 (n_boundary, 3)
        feats = np.array([[F_T.flat[j], F_D.flat[j], 1.0] for j in b])
        scores = feats @ theta
        scores = scores - scores.max()
        e = np.exp(scores)
        probs = e / e.sum()
        idx = int(rng.choice(len(b), p=probs))
        j = b[idx]
        log_probs.append(float(np.log(probs[idx] + 1e-12)))
        grad_terms.append(feats[idx] - (probs @ feats))

        # 附着到最热的已入树邻居（沿用原 grow_tree 的 parent 规则）
        y, x = divmod(j, GRID)
        best_parent, best_val = None, -np.inf
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < GRID and 0 <= nx < GRID:
                k = ny * GRID + nx
                if in_tree[k] and float(T_rise.flat[k]) > best_val:
                    best_val = float(T_rise.flat[k])
                    best_parent = k
        if best_parent is None:
            continue
        in_tree[j] = True
        edges.append((best_parent, j))

    grad = np.sum(grad_terms, axis=0) if grad_terms else np.zeros(3)
    return edges, log_probs, grad


def evaluate_edges(edges):
    radii = Ra.assign_radii(edges, grid=GRID, r0=R0)
    g = V.tree_group(T, src, edges, radii, GRID)
    return float(g.T_max), float(g.dp)


def greedy_edges():
    """贪心追热（基准）：等价 grow_tree，用 heapq。"""
    import heapq
    import grow as G
    return G.grow_tree(T, max_nodes=MAX_NODES)


if __name__ == "__main__":
    # 基准：贪心追热
    base_edges = greedy_edges()
    base_t, base_d = evaluate_edges(base_edges)
    print(f"基准（贪心追热 max_nodes={MAX_NODES}）: T_max={base_t:.4f}  dp={base_d:.3f}")

    lam = 0.0
    theta = np.array([1.0, 0.0, 0.0])   # 初始：纯追热
    lr = 0.05
    baseline = 0.0
    N_EP = 600

    hist = []
    for ep in range(N_EP):
        rng = np.random.default_rng(ep)
        edges, log_probs, grad = grow_rl(theta, rng)
        t, d = evaluate_edges(edges)
        reward = -(t + lam * d)
        baseline = 0.9 * baseline + 0.1 * reward
        theta += lr * (reward - baseline) * grad
        hist.append((t, d, reward))

    # 用学到的 θ 做一次贪心（取 argmax 而非采样）评估
    # 简单：报最后 50 个 episode 的平均，以及最终 θ
    recent = np.array([h[:2] for h in hist[-50:]])
    print(f"\nRL 训练后（最后 50 episode 平均）: "
          f"T_max={recent[:,0].mean():.4f}  dp={recent[:,1].mean():.3f}")
    print(f"最终 θ = [{theta[0]:.3f}, {theta[1]:.3f}, {theta[2]:.3f}]  "
          f"(初始 [1,0,0] = 纯追热)")

    # 收敛趋势
    print("\n每 100 episode 的平均 (T_max, dp):")
    for i in range(0, N_EP, 100):
        seg = np.array(hist[i:i+100])
        print(f"  ep {i:4d}-{i+99:4d}: T_max={seg[:,0].mean():.4f}  "
              f"dp={seg[:,1].mean():.3f}")
