# -*- coding: utf-8 -*-
"""evaluate() 的单元验证：论文数据回归（零 AI）。

对照 outputs/run_report.json 的单源基准：
  tree    T_max=27.596  dp=7.3472  material=651.461
  straight T_max=27.596  dp=0.0237  material=651.461  channels=8
  dp_ratio = 310.17
"""
import sys

import evaluate as E
import field as F

FAIL = []
PASS = 0


def approx(got, exp, tol, label):
    global PASS
    if abs(got - exp) <= tol:
        PASS += 1
        print(f"  [OK]   {label}: got={got:.6g} exp={exp:.6g}")
    else:
        FAIL.append(label)
        print(f"  [FAIL] {label}: got={got:.6g} exp={exp:.6g} (Δ={got-exp:.3g})")


# ---- 单源温度场（复现 run_report 口径：5x5 合成源块）----
T, src = E.solve_field(centers=((24, 24),), source_radius=F.SRC_RADIUS_SYNTHETIC)

# ---- 树 ----
tree = E.make_tree(T, max_nodes=400, r0=0.5)
r_tree = E.evaluate(tree, centers=((24, 24),), source_radius=F.SRC_RADIUS_SYNTHETIC)

approx(r_tree["T_max"], 27.596, 0.001, "tree T_max")
approx(r_tree["dp"], 7.3472, 0.001, "tree dp")
approx(r_tree["material_mm2"], 651.461, 0.5, "tree material")

# ---- 直通道（等材料：与树同 material，8 通道）----
straight = E.Topology(kind="straight", n_channels=8,
                      total_area_mm2=r_tree["material_mm2"])
r_str = E.evaluate(straight, centers=((24, 24),),
                   source_radius=F.SRC_RADIUS_SYNTHETIC)

approx(r_str["T_max"], 27.596, 0.001, "straight T_max")
approx(r_str["dp"], 0.0237, 0.0001, "straight dp")
approx(r_str["n_channels"], 8, 0, "straight channels")

# ---- 压降比 ----
cmp = E.compare(r_tree, r_str)
approx(cmp["dp_ratio"], 310.17, 0.5, "dp_ratio tree/straight")

# ---- 汇总 ----
print(f"\n===== {PASS} PASS / {len(FAIL)} FAIL =====")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
