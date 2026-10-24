# -*- coding: utf-8 -*-
"""Regime map: where the tree still wins against the radial baseline.

DATA SOURCE: the 8 spacing-sweep rows of outputs/multi_source_summary.json
(two chips, d = 6-30 mm, tree vs one-pipe-per-chip radial control, b = 600).
Pressure-drop ratio uses the network formula (convention A).

The figure carries NO numbers of its own -- every point is read from the JSON
at run time, so a stale PNG can only mean the script was not re-run after the
sweep. That is exactly what happened between 2026-10-21 and 2026-10-24: the
control was re-solved with balanced pin allocation, ctrl T_max dropped
(e.g. d = 12: 33.7477 -> 32.8972 C) and dp_ratio rose (8.2 -> 42.0), while
the PNG kept the old curve. Always re-run this script after multi_source.py.

OUTPUT:
  outputs/regime_map.png  two y axes: dT (tree - control, C) and dp_ratio (log)
  outputs/regime_map.json raw rows + quantitative verdict

The labels are English because this PNG is inserted into BOTH the Chinese and
the English manuscript (_work/insert_figures.py inserts the same file twice).

CRITERION (positive anchor, consistent with "the tree is only worth
considering for a multi-source layout whose control cannot feed every chip
evenly"):
  the thermal advantage of the tree over the radial baseline decays overall
  as the chips spread apart (non-monotonic: a local rebound at d = 20 mm,
  where the grown topology changes branch), while the pressure-drop penalty
  rises with spacing -> the useful regime is "multi-source, small spacing".
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = "DejaVu Sans"
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"

ms = json.loads((OUT / "multi_source_summary.json").read_text(encoding="utf-8"))

rows = []
for r in ms["rows"]:
    if "tree_cells" not in r:
        continue
    m = re.match(r"^d=(\d+)mm$", r["case"])
    if not m:
        continue
    d = int(m.group(1))
    rows.append({
        "d_mm": d,
        "dT_max_C": r["dT_max_tree_minus_ctrl"],
        "dT_mean_C": r["dT_mean_tree_minus_ctrl"],
        "dp_ratio": r["dp_ratio_tree_over_ctrl"],
        "tree_T_max": r["tree_T_max"],
        "ctrl_T_max": r["ctrl_T_max"],
        "tree_pinned": r["tree_pinned"],
        "ctrl_pinned": r["ctrl_pinned"],
    })
rows.sort(key=lambda x: x["d_mm"])

ds = [r["d_mm"] for r in rows]
dTmax = [r["dT_max_C"] for r in rows]
dTmean = [r["dT_mean_C"] for r in rows]
dprat = [r["dp_ratio"] for r in rows]

# ------------------------------------------------------------------ plot
fig, ax1 = plt.subplots(figsize=(7.4, 4.8), dpi=140)
ax1.axhline(0, color="0.4", lw=0.8, ls="--")
ax1.plot(ds, dTmax, "o-", color="#c0392b", lw=1.6,
         label="$\\Delta T_{max}$ (tree $-$ radial)")
ax1.plot(ds, dTmean, "s--", color="#e67e22", lw=1.2,
         label="$\\Delta T_{mean}$ (tree $-$ radial)")
ax1.set_xlabel("Heat-source spacing $d$ (mm)")
ax1.set_ylabel("Temperature difference, tree $-$ radial (°C)", color="#c0392b")
ax1.tick_params(axis="y", labelcolor="#c0392b")
ax1.set_xticks(ds)

ax2 = ax1.twinx()
ax2.plot(ds, dprat, "^-", color="#2980b9", lw=1.2,
         label="pressure-drop ratio (tree / radial)")
ax2.set_ylabel("Pressure-drop ratio, tree / radial", color="#2980b9")
ax2.tick_params(axis="y", labelcolor="#2980b9")
ax2.set_yscale("log")

# d = 20 mm branch change: the grown tree changes topology (pinned-cell count
# stops falling and turns back up), so the thermal advantage rebounds locally.
# The label is placed BELOW the red curve, in empty space, so it cannot cover
# either curve or the legend.
i20 = ds.index(20)
ax1.annotate("branch change at $d$ = 20 mm\n"
             "(pinned cells %d $\\rightarrow$ %d)"
             % (rows[i20 - 1]["tree_pinned"], rows[i20]["tree_pinned"]),
             xy=(20, dTmax[i20]), xytext=(21.6, -3.72),
             arrowprops=dict(arrowstyle="->", color="0.3", lw=0.9),
             ha="left", va="top", fontsize=7.5, color="0.25")

# Headroom above the curves so the three-entry legend clears every marker;
# the legend sits OUTSIDE the axes (above the panel) instead of in the
# upper-right corner, where it used to cover the d = 30 point of the blue
# pressure-drop curve.
ax1.set_ylim(min(dTmax + dTmean) - 0.55, 1.35)
ax1.set_title("Tree vs radial baseline: the thermal advantage decays with "
              "spacing (non-monotonic)", fontsize=10.5, pad=24)
h1, l1 = ax1.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax1.legend(h1 + h2, l1 + l2, loc="lower center", bbox_to_anchor=(0.5, 1.005),
           ncol=3, fontsize=7.5, frameon=False, handlelength=1.8,
           columnspacing=1.4)
fig.tight_layout()
fig.savefig(OUT / "regime_map.png", dpi=600, bbox_inches="tight")
plt.close(fig)

# ------------------------------------------------------------------ verdict
d_small = [d for d in ds if d <= 16]
d_large = [d for d in ds if d >= 24]
small_adv = min(abs(r["dT_max_C"]) for r in rows if r["d_mm"] in d_small)
large_adv = max(abs(r["dT_max_C"]) for r in rows if r["d_mm"] in d_large)
small_dp = max(r["dp_ratio"] for r in rows if r["d_mm"] in d_small)
large_dp = min(r["dp_ratio"] for r in rows if r["d_mm"] in d_large)
rebound = abs(rows[i20]["dT_max_C"]) - abs(rows[i20 - 1]["dT_max_C"])

verdict = {
    "small_spacing_mm": d_small,
    "large_spacing_mm": d_large,
    "small_spacing_min_advantage_C": round(small_adv, 4),
    "large_spacing_max_advantage_C": round(large_adv, 4),
    "small_spacing_max_dp_ratio": round(small_dp, 1),
    "large_spacing_min_dp_ratio": round(large_dp, 1),
    # |dT_max| is NOT monotone in d: it falls 5.23 -> 2.60 C over 6-16 mm,
    # rebounds to 2.83 C at d = 20 mm, then falls to 1.05 C at 30 mm. The
    # rebound coincides with a discrete change of the grown tree (pinned
    # cells 107 -> 135, max_src_to_tree_dist 4 -> 6), so it is a topology
    # branch, not noise -- but it is only 0.23 C, i.e. a local wiggle on a
    # decay trend, not a second regime.
    "non_monotonic_rebound_C": round(rebound, 4),
    "non_monotonic_at_mm": rows[i20]["d_mm"],
    "regime_statement": (
        "The tree's thermal advantage over the radial baseline decays overall "
        "as the chips spread apart (non-monotonic: a %.2f C rebound at "
        "d = %d mm where the grown topology changes branch): at small spacing "
        "(d <= 16 mm) the advantage is >= %.2f C at a pressure-drop cost of "
        "<= %.1f x; at large spacing (d >= 24 mm) it is <= %.2f C at a cost of "
        ">= %.1f x. The useful regime is therefore multi-source, small spacing."
        % (rebound, rows[i20]["d_mm"], small_adv, small_dp,
           large_adv, large_dp)),
}

(OUT / "regime_map.json").write_text(
    json.dumps({"rows": rows, "verdict": verdict}, ensure_ascii=False, indent=2),
    encoding="utf-8")

print("wrote outputs/regime_map.png + regime_map.json")
print("regime:", verdict["regime_statement"])
for r in rows:
    print("  d=%-3dmm  dT_max=%+7.4f  dT_mean=%+7.4f  dp_ratio=%6.1f"
          % (r["d_mm"], r["dT_max_C"], r["dT_mean_C"], r["dp_ratio"]))
