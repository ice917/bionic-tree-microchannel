# -*- coding: utf-8 -*-
"""神经代理模型（surrogate）：用 MLP 替代 evaluate() 的慢 Jacobi 求解。

输入 = 拓扑参数 genes（max_nodes + 3x3 偏置场 = 10 维）
输出 = (T_max, dp) 2 维
流程：随机采 N 个真实 (genes → T_max/dp) → 训练 sklearn MLPRegressor → 验证误差 + 提速。
"""
import time
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, r"d:\解释token\heat_tree")
import ga_field as GF  # 复用 grow_tree_field / decode_bias / evaluate

DATA_DIR = Path(r"d:\解释token\heat_tree\gen_design\data")
SUR_DIR = Path(r"d:\解释token\heat_tree\gen_design\surrogate")

N_TRAIN = 250
N_TEST = 50


def real_evaluate(genes):
    r = GF.evaluate(genes, lam=0.0)
    return np.array([r["T_max"], r["dp"]], dtype=float)


def sample(n, seed):
    rng = np.random.default_rng(seed)
    # max_nodes ∈ [100, 450]，偏置场 9 维 ∈ [-2, 2]
    return np.column_stack([
        rng.integers(100, 451, n),
        rng.uniform(-2.0, 2.0, (n, 9)),
    ])


def main():
    # ---- 1. 采集数据（慢，真实 Jacobi 求解）----
    X = sample(N_TRAIN + N_TEST, seed=0)
    t0 = time.time()
    Y = np.array([real_evaluate(x) for x in X])
    t_collect = time.time() - t0
    print(f"采集 {len(X)} 样本用时 {t_collect:.1f}s "
          f"（平均 {t_collect/len(X)*1000:.0f} ms/个）")

    Xtr, Xte = X[:N_TRAIN], X[N_TRAIN:]
    Ytr, Yte = Y[:N_TRAIN], Y[N_TRAIN:]

    np.savez(DATA_DIR / "surrogate_data.npz", Xtr=Xtr, Ytr=Ytr, Xte=Xte, Yte=Yte)
    print(f"数据已存 {DATA_DIR / 'surrogate_data.npz'}")

    # ---- 2. 训练 MLP 代理 ----
    from sklearn.preprocessing import StandardScaler
    from sklearn.neural_network import MLPRegressor
    from sklearn.pipeline import make_pipeline

    model = make_pipeline(
        StandardScaler(),
        MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=2000,
                     early_stopping=True, random_state=0),
    )
    model.fit(Xtr, Ytr)

    # ---- 3. 验证 ----
    Yhat = model.predict(Xte)
    err_tmax = np.abs(Yhat[:, 0] - Yte[:, 0])
    err_dp = np.abs(Yhat[:, 1] - Yte[:, 1])
    print(f"\n测试集误差（N={N_TEST}）:")
    print(f"  T_max  MAE = {err_tmax.mean():.4f} °C   "
          f"max = {err_tmax.max():.4f} °C")
    print(f"  dp     MAE = {err_dp.mean():.4f}   "
          f"相对 = {err_dp.mean()/Yte[:,1].mean()*100:.1f}%")

    # ---- 4. 提速对比 ----
    t0 = time.time()
    for x in Xte:
        _ = real_evaluate(x)
    t_real = time.time() - t0

    t0 = time.time()
    for x in Xte:
        _ = model.predict(x.reshape(1, -1))
    t_sur = time.time() - t0

    print(f"\n提速: 真实 {t_real*1000:.0f} ms vs 代理 {t_sur*1000:.1f} ms "
          f"（{t_real/t_sur:.0f}×）")

    # 保存模型（sklearn pipeline 用 joblib）
    import joblib
    joblib.dump(model, SUR_DIR / "surrogate_model.joblib")
    print(f"模型已存 {SUR_DIR / 'surrogate_model.joblib'}")


if __name__ == "__main__":
    main()
