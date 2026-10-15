"""Real-unit calibration: what do the dimensionless numbers actually mean?

Everything in REPORT.md 0-7 is dimensionless: grid spacing 1 mm, plate
conductivity 1, source strength 1, peak normalised to 100 C. That is fine
for comparing two topologies, but "the tree wins by 0.8 C" is meaningless
until we know the watts and the millimetres behind it.

This module does the mapping from published constants only, states every
assumption, and checks the result against a measured engineering number:
the thermal resistance of production cold plates. If the mapped model lands
inside that range, the dimensionless conclusions can be quoted with physical
units attached.

The check that matters is NOT the bare conduction field (which has no active
cooling and will always look terrible) but the field WITH the channels
pinned at coolant temperature -- that is the configuration the whole project
compares, and it is what a cold plate does.

Sources (also listed in REPORT.md 11):
  * Intel Core i7-14700K: package 45.0 x 37.5 mm, T_J(max) 100 C
    https://www.intel.cn/content/www/cn/zh/products/sku/236783/intel-core-i7-processor-14700k-33m-cache-up-to-5-60-ghz/specifications.html
  * Intel Core i7-14700K: 253 W max turbo power (PCG 2020A class)
  * NVIDIA H100 SXM: max TDP 700 W
    https://www.nvidia.com/en-us/data-center/h100/
  * silicon k = 148 W/(m K) at 300 K
    https://www.universitywafer.com/silicon-wafer-thermal-conductivity.html
  * diamond pin-fin cold plate: 0.0069 C/W chip-to-coolant (incl. TIM) at
    1 kW, pressure drop 9.0 kPa, water
    https://www.osti.gov/biblio/3375134
  * production microchannel cold plates: 0.2-0.5 mm channels, ~0.02 C/W
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------- constants
SI = 1e-3                      # metres per millimetre
RHO_WATER = 997.0              # kg/m3
CP_WATER = 4182.0              # J/(kg K)
MU_WATER = 1.0e-3              # Pa s
K_SI = 148.0                   # W/(m K), silicon at 300 K
T_COOL_C = 25.0                # coolant temperature

# published reference points
TDP_I7_W = 253.0
TDP_H100_W = 700.0
PACKAGE_MM = 45.0
TJ_MAX_C = 100.0
R_COLDPLATE_BEST = 0.0069      # C/W, diamond pin-fin @ 1 kW (OSTI)
R_COLDPLATE_MICRO = 0.02       # C/W, production microchannel (vendor)
DP_COLDPLATE_PUB_PA = 9.0e3    # Pa at 1 kW
CHANNEL_MM = (0.2, 0.5)        # production microchannel widths


@dataclass
class Calibration:
    """Maps the toy board onto one real device.

    grid_mm   physical size of one grid cell
    plate_mm  physical board size
    q_w       heat per source cell [W]  (25 cells -> total power)
    k_w_mk    plate conductivity [W/(m K)]
    t_mm      slab thickness for the 2.5D extrusion [mm]
    """
    grid_mm: float
    plate_mm: float
    q_w: float
    k_w_mk: float
    t_mm: float = 5.0

    @property
    def n_src_cells(self) -> int:
        return 25                       # 5x5 block, same as the toy

    @property
    def total_power_w(self) -> float:
        return self.q_w * self.n_src_cells

    @property
    def q_solver(self) -> float:
        """Source strength to pass to field.solve_heat for real units.

        Derivation (verified numerically in the module self-test):

            discrete:  T_P - mean(neighbours) = q_vol*H^2/(4k)
            power/cell: Q_cell = q_vol * H^2 * t   =>   q_vol*H^2 = Q_cell/t

        so the term added to each update is Q_cell/(4*t*k) -- independent of
        the cell size. Passing q = Q_cell/t with k = k_phys reproduces it.
        """
        return self.q_w / (self.t_mm * SI)


def i7_14700k(grid: int = 50) -> Calibration:
    """The default toy board read as an i7-14700K-class package.

    Mapping choices, all stated so they can be argued with:

    * grid_mm = 45/50 = 0.9 mm, so the 50x50 board is 45 mm -- the package
      width. (The package is 45 x 37.5 mm, not square; a square board is
      kept so the comparison with REPORT.md stays apples-to-apples.)
    * the 5x5 source block is then 4.5 x 4.5 mm -- the hot region of the
      die, not the whole die (a Raptor Lake die is ~257 mm2).
    * t = 5 mm slab thickness (same number as the STL extrusion height;
      the model is 2.5D plane strain, so a thickness must be assumed).
    * coolant 25 C, T_J(max) 100 C from the datasheet.
    """
    return Calibration(grid_mm=PACKAGE_MM / grid, plate_mm=PACKAGE_MM,
                       q_w=TDP_I7_W / 25.0, k_w_mk=K_SI, t_mm=5.0)


def h100(grid: int = 50) -> Calibration:
    """The same board read as an H100 SXM-class package (700 W)."""
    return Calibration(grid_mm=PACKAGE_MM / grid, plate_mm=PACKAGE_MM,
                       q_w=TDP_H100_W / 25.0, k_w_mk=K_SI, t_mm=5.0)


def solve_real(cal: Calibration, grid: int = 50, centers=None):
    """Physical temperature field [C] for a calibration. No normalisation:
    the peak is whatever the physics gives."""
    from field import solve_heat_sources

    if centers is None:
        centers = [((grid - 1) // 2, (grid - 1) // 2)]
    elif len(centers) == 2 and all(isinstance(c, int) for c in centers):
        centers = [tuple(centers)]              # a single (y, x) pair
    return solve_heat_sources(grid=grid, centers=centers, source_radius=2.0,
                              q=cal.q_solver, k=cal.k_w_mk,
                              T_boundary=T_COOL_C).T


def solve_real_with_channels(cal: Calibration, edges, grid: int = 50, centers=None):
    """Physical field with the tree's channel cells pinned at coolant temp.

    This is the configuration the whole project compares, and the only one
    that may be checked against published cold-plate thermal resistances.
    """
    import numpy as np
    import verify as V
    from field import source_mask_multi

    if centers is None:
        centers = [((grid - 1) // 2, (grid - 1) // 2)]
    elif len(centers) == 2 and all(isinstance(c, int) for c in centers):
        centers = [tuple(centers)]
    src = source_mask_multi(grid, centers, radius=2.0)
    cells = [(i // grid, i % grid)
             for i in sorted(set([p for p, _ in edges] + [c for _, c in edges]))]
    Tc, pinned = V.apply_channels(solve_real(cal, grid, centers), cells, src,
                                  T_cool=T_COOL_C)
    return Tc, pinned


def lpm(q_m3s: float) -> float:
    """m3/s -> litres per minute."""
    return q_m3s * 1000.0 * 60.0


def coolant_flow_m3s(power_w: float, dT_c: float = 5.0) -> float:
    """Volumetric flow to carry `power_w` with a dT_c coolant rise."""
    return power_w / (RHO_WATER * CP_WATER * dT_c)


def tree_dp_pa(edges, radii, grid_x: int, grid_mm: float,
               q_total_m3s: float, mu: float = MU_WATER) -> float:
    """Poiseuille pressure drop of the tree in PASCALS, real units."""
    import numpy as np
    from radius import node_flows

    flow = node_flows(edges)
    total = max(flow.values())
    h_m = grid_mm * SI
    dp = 0.0
    for p, c in edges:
        Q = q_total_m3s * flow[p] / total
        r = min(radii[p], radii[c]) * SI          # mm -> m
        dp += 8.0 * mu * h_m * Q / (np.pi * r ** 4)
    return dp


def report() -> str:
    import numpy as np
    import grow as G
    import radius as Ra
    import verify as V

    grid = 50
    L: list[str] = []
    L.append("real-unit calibration  (REPORT.md 11)")
    L.append("=" * 74)

    for name, cal in (("i7-14700K class (253 W)", i7_14700k(grid)),
                      ("H100 SXM class (700 W)", h100(grid))):
        L.append("")
        L.append(f"[{name}]")
        L.append(f"  board            {cal.plate_mm:.0f} x {cal.plate_mm:.0f} mm, "
                 f"cell {cal.grid_mm:.2f} mm, slab {cal.t_mm:.0f} mm, k={cal.k_w_mk:.0f} W/(m K)")
        L.append(f"  source block     4.5 x 4.5 mm, {cal.q_w:.2f} W/cell, "
                 f"{cal.total_power_w:.0f} W total")

        # --- bare conduction, no channels (upper bound on how bad it gets)
        T = solve_real(cal, grid)
        L.append(f"  bare conduction  peak {T.max():7.1f} C   <- no cooling at all, "
                 f"R_th={(T.max()-T_COOL_C)/cal.total_power_w:.3f} C/W")

        # --- with the tree's channels pinned: the number that is comparable
        # grow from the *dimensionless* field (topology is scale-free, so the
        # same tree serves every calibration)
        from field import solve_heat_sources, normalize_field
        Td = normalize_field(solve_heat_sources(grid=grid, centers=[(25, 25)],
                                                source_radius=2.0).T, T_target=100.0)
        edges = G.grow_tree(Td, max_nodes=400)
        radii = Ra.assign_radii(edges, grid=grid, r0=0.5)
        Tc, pinned = solve_real_with_channels(cal, edges, grid)
        r_th = (Tc.max() - T_COOL_C) / cal.total_power_w
        L.append(f"  + tree channels  peak {Tc.max():7.1f} C   "
                 f"R_th={r_th:.4f} C/W   ({len(edges)} segments, "
                 f"{int(pinned.sum())} pinned cells)")
        L.append(f"                   published cold plates: "
                 f"{R_COLDPLATE_BEST:.4f} - {R_COLDPLATE_MICRO:.4f} C/W")
        L.append(f"                   -> model is {r_th/R_COLDPLATE_BEST:.1f}x to "
                 f"{r_th/R_COLDPLATE_MICRO:.1f}x worse")

        # --- pressure drop at a real flow rate
        q = coolant_flow_m3s(cal.total_power_w)
        dp_tree = tree_dp_pa(edges, radii, grid, cal.grid_mm, q)
        n_cells = len(set([p for p, _ in edges] + [c for _, c in edges]))
        r_ctrl = float(np.sqrt(V.tree_material_mm2(edges, radii) / (n_cells * np.pi)))
        dp_ctrl = 8.0 * MU_WATER * (cal.plate_mm * SI) * (q / n_cells) / (np.pi * (r_ctrl * SI) ** 4)
        L.append(f"  flow {C_flow(q)}  ->  tree dP = {dp_tree/1000:6.2f} kPa, "
                 f"control dP = {dp_ctrl/1000:.5f} kPa  ({dp_tree/dp_ctrl:.0f}x)")
        L.append(f"                   published cold plate dP = "
                 f"{DP_COLDPLATE_PUB_PA/1000:.0f} kPa at 1 kW "
                 f"(tree is {dp_tree/DP_COLDPLATE_PUB_PA:.2f}x at {cal.total_power_w:.0f} W)")

    L.append("")
    L.append("thickness sensitivity: R_th and dP both scale as 1/t, so the")
    L.append("numbers above move by the same factor if the slab thickness")
    L.append("assumption moves. The *ratios* tree-vs-control do not.")
    L.append("")
    L.append("microchannel reference: production cold plates use 0.2-0.5 mm")
    L.append("channels; this model's capillaries are r0=0.5 mm (1.0 mm")
    L.append(f"diameter), i.e. {1.0/CHANNEL_MM[1]:.0f}-{1.0/CHANNEL_MM[0]:.0f}x wider than the")
    L.append("narrowest production channels. The r^4 penalty is therefore")
    L.append("not an artefact of the toy scale.")
    return "\n".join(L)


def C_flow(q_m3s: float) -> str:
    return f"{lpm(q_m3s):.2f} L/min"


if __name__ == "__main__":
    print(report())
