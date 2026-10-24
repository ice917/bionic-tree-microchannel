# -*- coding: utf-8 -*-
"""Actor-Critic 生长策略（对比 GA）：REINFORCE + value baseline 网络。

与朴素 REINFORCE 的区别：加一个 critic（线性 value 网络 V(s)=w·s）估计
"当前生长状态的价值"，用优势 A = G - V(s) 替代原始 reward 更新 actor，
从而压低稀疏奖励带来的梯度方差。状态 s = [进度, 边界最大温升, 源覆盖比例]。
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
N_SRC = int(src.sum())

yy, xx = np.mgrid[0:GRID, 0:GRID]
dist_src = np.stack([np.hypot(yy - cy, xx - cx) for cy, cx in CENTERS]).min(axis=0)
F_T = T_rise / float(T_rise.max())
F_D = -dist_src / float(dist_src.max())


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
    """生长并记录：edges, log_probs, grad_terms, states（每步状态特征）。"""
    in_tree = np.zeros(GRID * GRID, dtype=bool)
    start = int(np.argmax(T_rise))
    in_tree[start] = True
    edges = []
    log_probs = []
    grad_terms = []
    states = []

    for step in range(MAX_NODES - 1):
        b = _boundary(in_tree)
        if not b:
            break
        feats = np.array([[F_T.flat[j], F_D.flat[j], 1.0] for j in b])
        scores = feats @ theta
        scores = scores - scores.max()
        e = np.exp(scores)
        probs = e / e.sum()
        idx = int(rng.choice(len(b), p=probs))
        j = b[idx]
        log_probs.append(float(np.log(probs[idx] + 1e-12)))
        grad_terms.append(feats[idx] - (probs @ feats))

        # 状态特征（本步，附着前）
        n_in = int(in_tree.sum())
        progress = n_in / MAX_NODES
        rise_b = np.array([T_rise.flat[k] for k in b])
        max_b_rise = float(rise_b.max()) if len(rise_b) else 0.0
        covered = float((in_tree & src.reshape(-1)).sum()) / N_SRC
        states.append([progress, max_b_rise / float(T_rise.max()), covered])

        # 附着
        y, x = divmod(j, GRID)
        best_parent = None
        best_val = -np.inf
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
    return edges, log_probs, grad, states


def evaluate_edges(edges):
    radii = Ra.assign_radii(edges, grid=GRID, r0=R0)
    g = V.tree_group(T, src, edges, radii, GRID)
    return float(g.T_max), float(g.dp)


def greedy_tmax():
    import grow as G
    edges = G.grow_tree(T, max_nodes=MAX_NODES)
    return evaluate_edges(edges)


if __name__ == "__main__":
    base_t, base_d = greedy_tmax()
    print(f"基准（贪心追热）: T_max={base_t:.4f}  dp={base_d:.3f}")

    # actor 参数 θ（3 维），critic 参数 w（3 维，线性 value V=w·s）
    theta = np.array([1.0, 0.0, 0.0])
    w = np.zeros(3)
    lr_actor = 0.02
    lr_critic = 0.1
    N_EP = 600
    lam = 0.0

    hist = []
    for ep in range(N_EP):
        rng = np.random.default_rng(ep)
        edges, log_probs, grad, states = grow_rl(theta, rng)
        t, d = evaluate_edges(edges)
        G = -(t + lam * d)

        # critic 更新（value baseline 拟合 G）
        S = np.array(states) if states else np.zeros((0, 3))
        if len(S):
            V_pred = S @ w
            w -= lr_critic * (V_pred - G) @ S / len(S)  # 平均梯度

        # actor 更新（REINFORCE + value baseline）
        if len(states):
            adv = G - float(states[0] @ w)  # 用初始状态的价值做 baseline
            theta += lr_actor * adv * grad

        hist.append((t, d, float(w @ states[0]) if states else 0.0, G))

    recent = np.array([h[:2] for h in hist[-50:]])
    print(f"\nActor-Critic 训练后（最后 50 ep 平均）: "
          f"T_max={recent[:,0].mean():.4f}  dp={recent[:,1].mean():.3f}")
    print(f"最终 θ = [{theta[0]:.3f}, {theta[1]:.3f}, {theta[2]:.3f}]  "
          f"critic w = [{w[0]:.3f}, {w[1]:.3f}, {w[2]:.3f}]")

    print("\n每 100 ep 平均 (T_max, dp):")
    for i in range(0, N_EP, 100):
        seg = np.array(hist[i:i+100])
        print(f"  ep {i:4d}-{i+99:4d}: T_max={seg[:,0].mean():.4f}  "
              f"dp={seg[:,1].mean():.3f}")

    print(f"\n对比 GA/贪心基准 T_max={base_t:.4f}："
          f"{'达到/超越' if recent[:,0].mean() <= base_t + 0.05 else '未达到'}")
