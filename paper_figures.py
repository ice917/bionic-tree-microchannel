# -*- coding: utf-8 -*-
"""Supplementary figures for the paper (300 dpi, written to outputs/).

  junction_loss.png         junction-loss amplification (log bars)
  dimension_compare.png     3D check: peak temperatures + dT vs Bi
  single_source_cooled.png  single source, tree vs equal-occupancy straight
  multi_source_field.png    three chips: driver field / tree / one pipe per chip

Every panel is solved here, not copied from another PNG. The previous
composition used matplotlib.image.imread + imshow, which rasterised each
panel a SECOND time: the published figure carried nested pixel-index axes,
a duplicated colour bar, and a resolution loss on top of the 300 dpi save.
Composing from the model is also the only way the panels can share one
colour scale -- the old version stacked three independent scales, so a
0.02 C field and a 7 C field looked equally bright.

The recomputed states are checked against the published JSON
(outputs/run_report.json, outputs/multi_source_summary.json) and the script
refuses to write a figure if the model has drifted.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = "DejaVu Sans"
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
from matplotlib.colors import PowerNorm
from matplotlib.patches import Rectangle

import calibrate as C

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"

T_COOL = 25.0          # verify.T_COOL
GRID = 50
TOL_ASSERT = 5e-3      # published JSON is rounded to 3-4 decimals


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _check(got: float, want: float, what: str) -> None:
    """Refuse to publish a figure whose state no longer matches the tables."""
    if abs(got - want) > TOL_ASSERT:
        raise SystemExit(
            f"{what}: recomputed {got:.6f} vs published {want:.6f} "
            f"(|diff| = {abs(got - want):.2e} > {TOL_ASSERT:g}). "
            "The model changed; re-run the pipeline before rebuilding figures.")


def _source_box(ax, src, pitch, color="white"):
    ys, xs = np.nonzero(src)
    ax.add_patch(Rectangle((xs.min() * pitch, ys.min() * pitch),
                           (xs.max() - xs.min() + 1) * pitch,
                           (ys.max() - ys.min() + 1) * pitch,
                           fill=False, edgecolor=color, lw=1.0, ls="--",
                           alpha=0.85, zorder=6))


def _chip_boxes(ax, centers, radius, pitch, color="cyan"):
    for cy, cx in centers:
        ax.add_patch(Rectangle(((cx - radius) * pitch, (cy - radius) * pitch),
                               (2 * radius + 1) * pitch,
                               (2 * radius + 1) * pitch,
                               fill=False, edgecolor=color, lw=1.1, zorder=6))


# ------------------------------------------------------------ Fig. 10 junction loss
def junction_loss_fig():
    jun = _load("junction_loss_summary.json")
    labels = ["Pure viscous\n(bound)", "J1\nRennels split", "J2\n$K$ = 1.8",
              "J3\nlaminar fit"]
    kpa = [jun["pure_viscous_dp_kpa"]]
    kpa += [m["dp_total_pa"] / 1000.0 for m in jun["models"]]
    factors = [v / kpa[0] for v in kpa]

    fig, ax = plt.subplots(figsize=(5.6, 4.0), dpi=300)
    bars = ax.bar(labels, kpa, color=["#7f8c8d", "#2980b9", "#e67e22", "#c0392b"],
                  width=0.62)
    ax.set_yscale("log")
    for b, v, f in zip(bars, kpa, factors):
        ax.text(b.get_x() + b.get_width() / 2, v * 1.14,
                f"{v:.3f} kPa\n$\\times${f:.1f}", ha="center", va="bottom",
                fontsize=8)
    ax.set_ylabel("Tree pressure drop (kPa, log scale)")
    ax.set_title("Junction losses amplify the tree pressure drop (2.6-98.8$\\times$)",
                 fontsize=10.5)
    ax.set_ylim(0.03, 300)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "junction_loss.png", bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------ Fig. 11 3D check
def dimension_compare_fig():
    """Two panels, one message: the 2D tie survives the third dimension.

    Left  -- peak temperature of the bare plate vs the two channel families at
             the primary boundary (Bi = 1). Bars are drawn from T_cool so the
             bar length IS the temperature rise; a bar chart with a truncated
             25-27 C axis would magnify a 0.001 C difference into a visual
             difference of the same size as the 0.79 C cooling effect.
    Right -- dT = T_tree - T_straight as the base boundary is opened up
             (Bi = 0 ... infinity) and the mesh is refined (grid 30 -> 40),
             with the legacy full-depth-clamp value plotted SEPARATELY and
             marked as degenerate rather than as a fifth equal-weight point.
    """
    dim = _load("dimension_sensitivity.json")
    by_h = {r["h_base"]: r for r in dim["runs"]}
    prim = by_h[dim["primary_h_base"]]
    oc = dim["equal_occupancy"]
    gc = dim["grid_check"]
    gc_by_h = {r["h_base"]: r for r in gc["runs"]}
    leg = dim["legacy_full_depth_clamp"]

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(10.2, 4.3), dpi=300,
                                   gridspec_kw={"width_ratios": [1.0, 1.35]})

    # ---------------- left: peak temperatures at the primary Bi ----------------
    labels = ["no channel\n(bare plate)", "tree", "equal-occupancy\nstraight"]
    vals = [prim["bare_top_C"], prim["tree_top_C"], prim["straight_top_C"]]
    bars = axL.bar(labels, [v - T_COOL for v in vals], bottom=T_COOL,
                   color=["#7f8c8d", "#2980b9", "#e67e22"], width=0.58)
    for b, v in zip(bars, vals):
        axL.text(b.get_x() + b.get_width() / 2, v + 0.03, f"{v:.4f}",
                 ha="center", va="bottom", fontsize=9)
    axL.set_ylim(T_COOL, max(vals) + 0.70)
    axL.set_ylabel("peak temperature (°C)", fontsize=9)
    axL.set_title(f"peak at Bi = {prim['Bi']:.0f}, "
                  f"occupancy {oc['tree_cells']}/{oc['straight_cells']} cells\n"
                  "bars drawn from $T_{cool}$ = 25 °C, so bar length = temperature rise",
                  fontsize=9)
    axL.tick_params(labelsize=8)
    drop = vals[0] - vals[1]
    axL.text(0.5, 0.985,
             f"channels lower the peak by {drop:.4f} °C\n"
             f"tree - straight = {prim['dT_tree_minus_straight_C']:+.4f} °C"
             f" ({abs(prim['dT_tree_minus_straight_C']) / drop * 100:.4f} % of the effect)",
             transform=axL.transAxes, ha="center", va="top", fontsize=7.5,
             bbox=dict(fc="white", ec="0.7", alpha=0.9))

    # ---------------- right: dT vs Bi, with the mesh check ---------------------
    order = [0.0, 1.0, 10.0, None]
    xs = list(range(len(order)))
    tick = ["0", "1", "10", "∞\n(isothermal)"]
    d30 = [by_h[h]["dT_tree_minus_straight_C"] for h in order]
    d40 = [gc_by_h[h]["dT_tree_minus_straight_C"] for h in order]

    axR.axhline(0.0, color="0.25", lw=0.9)
    axR.plot(xs, d30, "o-", color="#2980b9", ms=6, lw=1.2,
             label=f"grid {dim['grid']} (published)")
    axR.plot(xs, d40, "s", mfc="none", mec="#c0392b", ms=6, mew=1.2,
             label=f"grid {gc['grid']} (mesh check)")
    for x, v in zip(xs, d30):
        axR.annotate(f"{v * 1e3:+.3f}", (x, v), textcoords="offset points",
                     xytext=(0, -13), ha="center", fontsize=7.5, color="#2980b9")

    # legacy point: its own slot, excluded from the sweep, labelled degenerate
    xl = len(order) + 0.35
    axR.axvline(xl - 0.55, color="0.85", lw=0.9, ls=":")
    axR.plot([xl], [leg["tree_top_C"] - leg["straight_top_C"]], "x",
             color="0.45", ms=9, mew=2.2, label="legacy clamp (excluded)")
    axR.annotate("degenerate solve\niters = "
                 f"{leg['iters'][0]}, both runs pinned\nat 25.0000 °C",
                 (xl, 0.0), textcoords="offset points", xytext=(0, 26),
                 ha="center", fontsize=7, color="0.35")

    axR.set_xticks(xs + [xl])
    axR.set_xticklabels(tick + ["legacy\nfull-depth\nclamp"], fontsize=8)
    axR.set_xlim(-0.5, xl + 0.55)
    axR.set_ylim(-0.0035, 0.0035)
    axR.set_ylabel("$\\Delta T = T_{max}$(tree) $-\\ T_{max}$(straight)  [°C]",
                   fontsize=9)
    axR.set_xlabel("Biot number at the cooled base", fontsize=9)
    axR.set_title("the tie is flat in Bi and in the mesh", fontsize=9.5)
    axR.legend(fontsize=7.5, frameon=False, loc="upper left", ncol=1)
    axR.tick_params(labelsize=8)

    spread = max(d30) - min(d30)
    axR.text(0.98, 0.03,
             f"|ΔT| ≤ {max(abs(min(d30)), abs(max(d30))) * 1e3:.2f}"
             f" × 10$^{{-3}}$ °C on a {drop:.3f} °C cooling effect;\n"
             f"spread over the Bi sweep {spread * 1e3:.2f}"
             f" × 10$^{{-3}}$ °C",
             transform=axR.transAxes, ha="right", va="bottom", fontsize=7.5,
             color="0.3")

    fig.suptitle("3D check with the source kept live (solid top skin, "
                 "channels as isothermal columns below it)", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(OUT / "dimension_compare.png", bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------ Fig. 7 single source
def _single_source_state():
    """Recompute exactly the Step-5 state that produced run_report.json."""
    import field as F
    import grow as G
    import radius as Ra
    import verify as V

    src = F.source_mask(GRID, (25, 25), radius=F.SRC_RADIUS_SYNTHETIC)
    T = F.normalize_field(
        F.solve_heat(grid=GRID, source_center=(25, 25),
                     source_radius=F.SRC_RADIUS_SYNTHETIC).T, T_target=100.0)
    edges = G.grow_tree(T, max_nodes=400)
    radii = Ra.assign_radii(edges, grid=GRID, r0=0.5)
    tg = V.tree_group(T, src, edges, radii, grid_x=GRID)
    n_cells = len(set([p for p, _ in edges] + [c for _, c in edges]))
    sg = V.straight_group(T, src, n_channels=max(1, n_cells // GRID),
                          total_area_mm2=tg.total_area_mm2,
                          grid_x=GRID, grid_y=GRID)
    rep = _load("run_report.json")["compare"]
    _check(tg.T_max, rep["tree"]["T_max_C"], "single-source tree T_max")
    _check(sg.T_max, rep["straight"]["T_max_C"], "single-source straight T_max")
    return src, edges, tg, sg


def single_source_cooled_fig():
    """The Step-5 fields, plotted as a rise above the coolant.

    Plotted as absolute temperature the whole plate reads 25.02 C and the
    channels are invisible: the two panels differ by 0.000 C on a 2.6 C
    colour range, which is exactly what made the old figure look empty.
    dT = T - T_cool with a power norm puts the 0-0.1 C bulk structure and the
    2.6 C source peak on one scale, and ONE colour bar serves both panels so
    the two topologies are compared, not two independent autoscalings.
    """
    import heat_tree as H
    import verify as V

    src, edges, tg, sg = _single_source_state()
    pitch = C.paper_grid_mm(GRID)
    plate = GRID * pitch

    dT_tree = tg.T - V.T_COOL
    dT_str = sg.T - V.T_COOL
    vmax = float(max(dT_tree.max(), dT_str.max()))
    norm = PowerNorm(gamma=0.4, vmin=0.0, vmax=vmax)
    max_diff = float(np.max(np.abs(tg.T - sg.T)))

    fig = plt.figure(figsize=(10.0, 4.8), dpi=300)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.0, 0.030],
                          wspace=0.09, left=0.065, right=0.945,
                          bottom=0.125, top=0.855)
    axA = fig.add_subplot(gs[0, 0])
    axB = fig.add_subplot(gs[0, 1], sharex=axA, sharey=axA)
    cax = fig.add_subplot(gs[0, 2])
    axes = [axA, axB]
    for ax, dT, g in zip(axes, (dT_tree, dT_str), (tg, sg)):
        im = ax.imshow(dT, cmap="inferno", origin="lower", norm=norm,
                       extent=(0.0, plate, 0.0, plate),
                       interpolation="nearest")
        if g is tg:
            H._draw_tree_edges(ax, edges, GRID, pitch)
        else:
            # mark the PINNED CELLS, not their columns: a full-height vline would
            # also be drawn through the live source block, which carries no channel
            ys_p, xs_p = np.nonzero(sg.pinned_mask)
            ax.scatter((xs_p + 0.5) * pitch, (ys_p + 0.5) * pitch, s=3.2,
                       c="cyan", marker="s", linewidths=0, zorder=4)
        _source_box(ax, src, pitch)
        ax.set_xlim(0.0, plate)
        ax.set_ylim(0.0, plate)
        ax.set_xlabel("x (mm)", fontsize=9)
        ax.tick_params(labelsize=7.5)
    axes[0].set_ylabel("y (mm)", fontsize=9)

    n_ctrl = sg.n_channels
    axes[0].set_title(f"(a) tree, {tg.n_segments} segments\n"
                      f"$T_{{max}}$ = {tg.T_max:.4f} °C", fontsize=9.5)
    axes[1].set_title(f"(b) equal-occupancy straight, {n_ctrl} channels "
                      f"({sg.pinned_cells} pinned cells)\n"
                      f"$T_{{max}}$ = {sg.T_max:.4f} °C", fontsize=9.5)

    cbar = fig.colorbar(im, cax=cax)
    ticks = [t for t in (0.0, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0)
             if t < vmax * 0.98] + [round(vmax, 3)]
    cbar.set_ticks(ticks)
    cbar.ax.tick_params(labelsize=7.5)
    cbar.set_label("$\\Delta T = T - T_{cool}$  (°C)", fontsize=8.5)
    fig.suptitle(f"Maximum pointwise difference between the two fields: "
                 f"{max_diff:.4f} °C  (0.9 mm pitch, 45 × 45 mm plate);  "
                 f"cyan = channel cells held at $T_{{cool}}$",
                 fontsize=9)
    fig.savefig(OUT / "single_source_cooled.png", bbox_inches="tight")
    plt.close(fig)
    return max_diff


# ------------------------------------------------------------ Fig. 8 multi source
def _multi_source_state():
    import field as F
    import multi_source as MS

    centers = MS.LAYOUTS["3 chips, triangle"]
    T, src, strength = MS.solve_layout(centers, grid=GRID)
    tg, edges, radii, cells, _, _ = MS.tree_metrics(
        T, src, 600, grid=GRID, centers=centers,
        radius=F.SRC_RADIUS_REAL, strength=strength)
    rg = MS.control_metrics(T, src, tg, grid=GRID, strength=strength)

    rows = _load("multi_source_summary.json")["rows"]
    key = "3 chips, triangle | budget 600"
    ref = next(r for r in rows if r["case"] == key)
    _check(tg.T_max, ref["tree_T_max"], "3-chip tree T_max")
    _check(rg.T_max, ref["ctrl_T_max"], "3-chip control T_max")
    return centers, T, src, edges, tg, rg, ref


def multi_source_fig():
    """Three panels, two colour scales, one chip outline per die.

    (a) is the NORMALISED growth driver (peak scaled to 100): it is a design
        field, not a physical temperature, so it keeps its own scale and its
        own label. (b) and (c) are the channel-pinned solutions of the same
        case and therefore share ONE scale -- the whole point is that the tree
        peak (28.17 C) sits 4.57 C below the per-chip-pipe control (32.74 C)
        once both sides carry the SAME pinned count (123 cells, C1 exact).
    """
    import heat_tree as H
    import field as F

    centers, T, src, edges, tg, rg, ref = _multi_source_state()
    pitch = C.paper_grid_mm(GRID)
    plate = GRID * pitch
    radius = int(F.SRC_RADIUS_REAL)

    v_lo = float(min(tg.T.min(), rg.T.min()))
    v_hi = float(max(tg.T.max(), rg.T.max()))

    fig = plt.figure(figsize=(13.8, 4.6), dpi=300)
    gs = fig.add_gridspec(1, 5, width_ratios=[1.0, 0.042, 1.0, 1.0, 0.042],
                          wspace=0.10, left=0.045, right=0.955,
                          bottom=0.13, top=0.83)
    ax0 = fig.add_subplot(gs[0, 0])
    cax0 = fig.add_subplot(gs[0, 1])
    ax1 = fig.add_subplot(gs[0, 2], sharex=ax0, sharey=ax0)
    ax2 = fig.add_subplot(gs[0, 3], sharex=ax0, sharey=ax0)
    ax1.tick_params(labelleft=False)
    ax2.tick_params(labelleft=False)
    cax1 = fig.add_subplot(gs[0, 4])
    axes = [ax0, ax1, ax2]
    ext = (0.0, plate, 0.0, plate)

    # (a) driver field
    im0 = axes[0].imshow(T, cmap="inferno", origin="lower", extent=ext,
                         interpolation="nearest")
    _chip_boxes(axes[0], centers, radius, pitch)
    cb0 = fig.colorbar(im0, cax=cax0)
    cb0.ax.tick_params(labelsize=7)
    cb0.set_ticks([20, 40, 60, 80, 100])
    cb0.set_label("")          # the panel title already names the quantity
    axes[0].set_title("(a) growth driver (normalised peak 100)\n"
                      "3 chips, 17 × 17 cells each", fontsize=9.5)

    # (b) tree
    im1 = axes[1].imshow(tg.T, cmap="inferno", origin="lower", extent=ext,
                         vmin=v_lo, vmax=v_hi, interpolation="nearest")
    H._draw_tree_edges(axes[1], edges, GRID, pitch)
    _chip_boxes(axes[1], centers, radius, pitch)
    axes[1].set_title(f"(b) tree, 600 cells\n$T_{{max}}$ = {tg.T_max:.4f} °C, "
                      f"$\\bar T_{{solid}}$ = {tg.T_mean_solid:.4f} °C",
                      fontsize=9.5)

    # (c) one pipe per chip
    im2 = axes[2].imshow(rg.T, cmap="inferno", origin="lower", extent=ext,
                         vmin=v_lo, vmax=v_hi, interpolation="nearest")
    ys, xs = np.nonzero(rg.pinned_mask)
    axes[2].scatter((xs + 0.5) * pitch, (ys + 0.5) * pitch, s=1.6,
                    c="cyan", marker="s", linewidths=0, zorder=4)
    _chip_boxes(axes[2], centers, radius, pitch)
    axes[2].set_title(f"(c) one pipe per chip, {rg.pinned_cells} pinned cells\n"
                      f"$T_{{max}}$ = {rg.T_max:.4f} °C  "
                      f"({rg.T_max - tg.T_max:+.4f} °C vs tree)", fontsize=9.5)

    cb1 = fig.colorbar(im2, cax=cax1)
    cb1.ax.tick_params(labelsize=7)
    cb1.set_label("solid temperature (°C), (b) and (c)", fontsize=8)

    for ax in axes:
        ax.set_xlabel("x (mm)", fontsize=9)
        ax.tick_params(labelsize=7.5)
    axes[0].set_ylabel("y (mm)", fontsize=9)

    fig.suptitle("Equal pinned occupancy on both sides "
                 f"({ref['tree_pinned']} = {ref['ctrl_pinned']} cells); "
                 f"$\\Delta T_{{mean}}$ = {ref['dT_mean_tree_minus_ctrl']:+.4f} °C, "
                 f"$\\Delta p$ ratio = {ref['dp_ratio_tree_over_ctrl']:.1f}×",
                 fontsize=9)
    fig.savefig(OUT / "multi_source_field.png", bbox_inches="tight")
    plt.close(fig)


def main():
    junction_loss_fig()
    print("wrote junction_loss.png")
    dimension_compare_fig()
    print("wrote dimension_compare.png")
    max_diff = single_source_cooled_fig()
    print(f"wrote single_source_cooled.png (max |dT| between fields "
          f"{max_diff:.4f} C)")
    multi_source_fig()
    print("wrote multi_source_field.png")


if __name__ == "__main__":
    main()
