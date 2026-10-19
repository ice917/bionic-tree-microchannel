"""Reproducible artifact generator for the constraint-driven Pareto fronts.

Runs the Route-A generator (`generator.solve_design`) and the equal-total
control fronts (`generator.control_front_total`, the C5 basis) on the four
canonical chip layouts, then persists:

  * outputs/generator_fronts.json   -- machine-readable fronts + dominance
  * outputs/generator_front_compare.png -- T_max / dp vs budget, 3-chip case

Every number written here is computed by this repository's own solvers at
run time; nothing is hard-coded. Re-run any time with `python
generator_front_artifacts.py` to regenerate both artifacts bit-for-bit
(matplotlib figure aside, which is deterministic given the same data).
"""
from __future__ import annotations

import json

import generator as GEN

# Canonical layouts -- identical to generator.py __main__ so the fronts are
# directly comparable across scripts.
CASES = {
    "1 chip": [(24, 24)],
    "2 chip d=16": [(12, 24), (36, 24)],
    "3 chip": [(12, 12), (36, 12), (24, 36)],
    "4 chip": [(12, 12), (36, 12), (12, 36), (36, 36)],
}


def _slim_front(rows):
    """Keep only the columns a paper table needs (drop bulky masks)."""
    out = []
    for d in rows:
        out.append({k: d.get(k) for k in (
            "budget", "n_leaves", "pinned", "n_cells", "T_max_c",
            "dp_pa", "target_total", "n_channel_cells",
            "C1_enters_all_chips", "C3_within_pump") if k in d})
    return out


def main():
    result = {}
    for label, centers in CASES.items():
        print(f"== {label} ==", flush=True)
        entry = {"centers": [list(c) for c in centers]}

        # Tree front (constraints C1/C2/C3, budget is the OUTPUT).
        tree = GEN.solve_design(centers, verbose=False)
        entry["tree"] = {
            "front": _slim_front(tree["front"]),
            "n_feasible": tree["n_feasible"],
            "knee": {k: tree["knee"].get(k) for k in
                     ("n_leaves", "budget", "T_max_c", "dp_pa")},
            "knee_sensitivity": tree["knee_sensitivity"],
            "c2_summary": tree["c2_summary"],
        }
        print(f"   tree front={len(tree['front'])} "
              f"best_T={min(d['T_max_c'] for d in tree['front']):.4f} C",
              flush=True)

        # Equal-total (C5) control fronts.
        for kind in ("radial", "lattice"):
            try:
                c = GEN.control_front_total(centers, kind=kind, verbose=False)
                entry[kind + "_total"] = {
                    "front": _slim_front(c["front"]),
                    "n_feasible": c["n_feasible"],
                }
                cmp = GEN.compare_fronts(tree, c)
                entry["dominance_vs_" + kind] = cmp
                print(f"   {kind}/total front={len(c['front'])} "
                      f"tree_dominates={cmp['tree_dominates']} "
                      f"n_beating={cmp['n_control_points_beating_tree']}",
                      flush=True)
            except ValueError as e:
                entry[kind + "_total"] = {"infeasible": str(e)}
                entry["dominance_vs_" + kind] = {"infeasible": str(e)}
                print(f"   {kind}/total INFEASIBLE: {e}", flush=True)

        result[label] = entry

    out_json = "outputs/generator_fronts.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"\nwrote {out_json}", flush=True)

    _plot(result)


def _plot(result):
    """T_max and dp vs total occupied cells for the 3-chip case.

    The 3-chip layout is the representative multi-source geometry (the
    1-chip front saturates; 2/4-chip show the same trend). Both panels use
    ONLY points from the saved fronts, so the figure is a faithful picture
    of the computed data.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    entry = result["3 chip"]

    def xy(front, xkey):
        xs = [d[xkey] for d in front if d.get(xkey) is not None]
        ys = [d["T_max_c"] for d in front if d.get(xkey) is not None]
        dps = [d["dp_pa"] for d in front if d.get(xkey) is not None]
        return xs, ys, dps

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    series = [
        ("tree", "n_cells", "Tree (this work)", "tab:red", "o"),
        ("radial_total", "n_channel_cells", "Radial (equal-total)",
         "tab:blue", "s"),
        ("lattice_total", "n_channel_cells", "Lattice (equal-total)",
         "tab:green", "^"),
    ]
    for key, xkey, lab, col, mk in series:
        blk = entry.get(key)
        if not blk or "infeasible" in blk:
            continue
        xs, ys, dps = xy(blk["front"], xkey)
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        xs = [xs[i] for i in order]
        ys = [ys[i] for i in order]
        dps = [dps[i] for i in order]
        ax1.plot(xs, ys, marker=mk, color=col, label=lab, markersize=5)
        ax2.plot(xs, dps, marker=mk, color=col, label=lab, markersize=5)

    ax1.set_xlabel("Total occupied channel cells")
    ax1.set_ylabel(r"$T_{max}$ ($^\circ$C)")
    ax1.set_title("(a) Peak temperature")
    ax1.grid(alpha=0.3)
    ax1.legend(fontsize=8)

    ax2.set_xlabel("Total occupied channel cells")
    ax2.set_ylabel(r"$\Delta p$ (Pa)")
    ax2.set_yscale("log")
    ax2.set_title("(b) Pressure drop (log scale)")
    ax2.grid(alpha=0.3, which="both")
    ax2.legend(fontsize=8)

    fig.suptitle("3-chip layout: constraint-feasible fronts (equal-total basis)",
                 fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out_png = "outputs/generator_front_compare.png"
    fig.savefig(out_png, dpi=200)
    print(f"wrote {out_png}", flush=True)


if __name__ == "__main__":
    main()
