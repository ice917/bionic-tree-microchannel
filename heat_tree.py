"""heat_tree.py -- one-command pipeline (PROJECT.md Definition of Done).

    python heat_tree.py [--source-x 25] [--source-y 25] [--max-nodes 400]
                       [--r0 0.5] [--height 5] [--no-fig]

Runs Step 1..5 and writes everything into outputs/.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

import calibrate as C
import field as F
import grow as G
import mesh as M
import radius as R
import verify as V

OUT = Path(__file__).resolve().parent / "outputs"


def save_heatmap(T: np.ndarray, path: Path, title: str, edges=None, grid_x=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 5.4), dpi=140)
    im = ax.imshow(T, cmap="inferno", origin="lower")
    fig.colorbar(im, ax=ax, label="T [C]")
    if edges is not None:
        ys, xs = [], []
        for p, c in edges:
            py, px = divmod(p, grid_x)
            cy, cx = divmod(c, grid_x)
            ys += [py, cy]
            xs += [px, cx]
        ax.plot(xs, ys, color="cyan", lw=0.8, alpha=0.9)
    ax.set_title(title)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-x", type=int, default=25)
    ap.add_argument("--source-y", type=int, default=25)
    ap.add_argument("--grid", type=int, default=50)
    ap.add_argument("--max-nodes", type=int, default=400,
                    help="tree cell budget (channels embedded in the solid)")
    ap.add_argument("--r0", type=float, default=0.5)
    ap.add_argument("--height", type=float, default=5.0)
    ap.add_argument("--no-fig", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    grid = args.grid
    report: dict = {"params": vars(args)}

    # ---------------- Step 1: heat field ----------------
    print("[Step 1] solving heat field ...")
    src = F.source_mask(grid, (args.source_y, args.source_x),
                        radius=F.SRC_RADIUS_SYNTHETIC)
    res = F.solve_heat(grid=grid, source_center=(args.source_y, args.source_x),
                       source_radius=F.SRC_RADIUS_SYNTHETIC)
    T = F.normalize_field(res.T, T_target=100.0)
    report["field"] = {
        "grid": grid,
        "T_centre_C": round(float(T[args.source_y, args.source_x]), 3),
        "T_edge_C": round(float(T[0, 0]), 3),
        "converged": res.converged,
        "iterations": res.iterations,
    }

    # sanity check: point source must decay as -(Q/2pi)*ln(r)
    Tp = F.solve_heat_point_source(grid=121, q_point=1.0)
    sc = F.sanity_check_log_decay(Tp)
    report["sanity_check"] = {
        "slope_measured": round(sc["slope_measured"], 5),
        "slope_analytic": round(sc["slope_analytic"], 5),
        "ratio": round(sc["slope_measured"] / sc["slope_analytic"], 4),
        "r2_log_fit": round(sc["r2_log_fit"], 6),
        "pass": sc["pass"],
    }
    print(f"  centre {report['field']['T_centre_C']} C, edge {report['field']['T_edge_C']} C, "
          f"iters={res.iterations}, converged={res.converged}")
    print(f"  sanity check pass={sc['pass']}: slope {sc['slope_measured']:.4f} "
          f"vs analytic {sc['slope_analytic']:.4f}, R^2={sc['r2_log_fit']:.6f}")

    # ---------------- Step 2: grow tree ----------------
    print("[Step 2] growing tree ...")
    edges = G.grow_tree(T, max_nodes=args.max_nodes)
    cov = G.coverage_stats(edges, grid)
    hist = G.branching_histogram(edges)
    report["tree"] = {"nodes": cov["nodes"], "edges": cov["edges"],
                      "degree_hist": {str(k): v for k, v in hist.items()}}
    print(f"  nodes={cov['nodes']} edges={cov['edges']} degree hist={hist}")

    # off-centre source -> different shape (field-driven proof)
    src_off = F.source_mask(grid, (25, 10), radius=F.SRC_RADIUS_SYNTHETIC)
    T_off = F.normalize_field(
        F.solve_heat(grid=grid, source_center=(25, 10),
                     source_radius=F.SRC_RADIUS_SYNTHETIC).T, T_target=100.0)
    edges_off = G.grow_tree(T_off, max_nodes=args.max_nodes)
    sig_a = G.shape_signature(edges, grid, grid)
    sig_b = G.shape_signature(edges_off, grid, grid)
    report["tree_offsource"] = {
        "source_xy": [10, 25], "nodes": G.coverage_stats(edges_off, grid)["nodes"],
        "signature": sig_b, "differs_from_baseline": bool(sig_a != sig_b),
    }
    print(f"  off-centre source (10,25): nodes={report['tree_offsource']['nodes']}, "
          f"centroid=({sig_b['centroid_x']},{sig_b['centroid_y']}) "
          f"vs baseline ({sig_a['centroid_x']},{sig_a['centroid_y']}) "
          f"-> differs={sig_a != sig_b}")

    # ---------------- Step 3: Murray radii ----------------
    print("[Step 3] assigning Murray radii ...")
    radii = R.assign_radii(edges, grid=grid, r0=args.r0)
    mc = R.check_murray(edges, radii)
    prof = R.radius_profile(radii, grid)
    report["murray"] = {"forks": mc["n_forks"],
                        "max_rel_err": float(f"{mc['max_rel_err']:.3e}"),
                        "pass": mc["pass"],
                        "profile": {k: round(v, 4) for k, v in prof.items()}}
    print(f"  forks={mc['n_forks']} max rel err={mc['max_rel_err']:.2e} pass={mc['pass']}; "
          f"r in [{prof['min']:.3f}, {prof['max']:.3f}] mm, "
          f"{prof['frac_le_0_6mm']*100:.0f}% capillaries <=0.6 mm")

    # ---------------- Step 4: STL ----------------
    print("[Step 4] exporting STL ...")
    stl_path = OUT / "tree.stl"
    pitch_mm = C.paper_grid_mm(grid)
    n_tri = M.export_stl(edges, radii, grid=grid, height=args.height,
                         path=str(stl_path), n_sides=12, pitch_mm=pitch_mm)
    mrep = M.stl_manifold_report(str(stl_path))
    bb = M.bbox(str(stl_path))
    report["stl"] = {"triangles": n_tri, "manifold": mrep, "bbox_mm": bb,
                     "height_mm": args.height, "pitch_mm": pitch_mm}
    print(f"  {n_tri} triangles, closed={mrep['closed']} "
          f"(boundary_edges={mrep['boundary_edges']}), "
          f"nonmanifold_edges={mrep['nonmanifold_edges']}, "
          f"pitch={pitch_mm} mm, bbox={bb['size_mm']} mm (height={args.height})")

    # ---------------- Step 5: verification ----------------
    # Fairness: the control must occupy the SAME NUMBER OF CELLS as the tree
    # and have the SAME total cross-section. (Equal material alone is not
    # enough: 50 full-length channels occupy 2500 cells vs the tree's 400,
    # handing the control 6.6x more cold boundary. See REPORT.md 2.2.)
    print("[Step 5] verifying (tree vs equal-occupancy straight channels) ...")
    tg = V.tree_group(T, src, edges, radii, grid_x=grid)
    n_cells = len(set([p for p, _ in edges] + [c for _, c in edges]))
    n_ctrl = max(1, n_cells // grid)
    sg = V.straight_group(T, src, n_channels=n_ctrl,
                          total_area_mm2=tg.total_area_mm2, grid_x=grid, grid_y=grid)
    cmp = V.compare(tg, sg)
    report["compare"] = cmp
    print(f"  occupancy: tree {tg.pinned_cells} pinned cells, "
          f"straight {sg.pinned_cells} pinned cells (equal by construction)")
    print(f"  T_max  tree={cmp['tree']['T_max_C']} C  straight={cmp['straight']['T_max_C']} C"
          f"   (tree - straight = {cmp['dT_max_tree_minus_straight']} C)")
    print(f"  T_mean tree={cmp['tree']['T_mean_solid_C']} C  "
          f"straight={cmp['straight']['T_mean_solid_C']} C"
          f"   (diff = {cmp['dT_mean_solid_tree_minus_straight']} C)")
    print(f"  hot    tree={cmp['tree']['hotspot_area_mm2']} mm^2  "
          f"straight={cmp['straight']['hotspot_area_mm2']} mm^2")
    print(f"  dP     tree={cmp['tree']['pressure_drop']}  "
          f"straight={cmp['straight']['pressure_drop']}  "
          f"ratio={cmp['dp_ratio_tree_over_straight']}")
    print(f"  material: tree={cmp['tree']['material_mm2']} mm^2, "
          f"straight={cmp['straight']['material_mm2']} mm^2 -> {cmp['verdict']}")

    # ---------------- outputs ----------------
    if not args.no_fig:
        print("[figures] writing png/csv ...")
        save_heatmap(T, OUT / "step1_heatmap.png", "Step 1: steady heat field (peak 100 C)")
        save_heatmap(T, OUT / "step2_tree.png", "Step 2: heat-seeking tree", edges, grid)
        save_heatmap(T_off, OUT / "step2b_tree_offsource.png",
                     "Step 2b: off-centre source -> different tree", edges_off, grid)
        save_heatmap(tg.T, OUT / "step5_tree_cooled.png", "Step 5: tree group, channels at 25 C")
        save_heatmap(sg.T, OUT / "step5_straight_cooled.png",
                     "Step 5: straight group, channels at 25 C")

    with open(OUT / "tree_edges.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["parent_idx", "child_idx", "py", "px", "cy", "cx",
                    "r_parent_mm", "r_child_mm"])
        for p, c in edges:
            py, px = divmod(p, grid)
            cy, cx = divmod(c, grid)
            w.writerow([p, c, py, px, cy, cx, round(radii[p], 5), round(radii[c], 5)])

    with open(OUT / "murray_check.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["parent_idx", "n_children", "r_parent", "sum_r_child_cubed", "rel_err"])
        for row in mc["rows"]:
            w.writerow([row["parent"], row["n_children"], round(row["r_parent"], 5),
                        round(row["sum_r_child_cubed"], 5), f"{row['rel_err']:.3e}"])

    (OUT / "run_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nDone. Outputs in {OUT}")


if __name__ == "__main__":
    main()
