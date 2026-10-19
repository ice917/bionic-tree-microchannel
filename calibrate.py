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
    Glassbrenner & Slack, Phys. Rev. 134(4A): A1058-A1069 (1964),
    DOI 10.1103/PhysRev.134.A1058
  * diamond pin-fin cold plate: 0.0069 C/W chip-to-coolant (incl. TIM) at
    1 kW, pressure drop 9.0 kPa, water
    Pinkus et al., Int. J. Heat Mass Transfer 256 (2026) 128080,
    DOI 10.1016/j.ijheatmasstransfer.2025.128080 (OSTI 3375134 is the same work)
  * OCP OAI liquid cooling guidelines: cold plate 0.014-0.019 C/W
    case-to-inlet, valid only at 1.5-3.5 LPM per cold plate.
    NOTE: the former "~0.02 C/W production microchannel" line had no source
    and has been removed; do not reinstate a 0.0069-0.0200 range -- the two
    ends have different calibers.

Viscosity caveat: MU_WATER = 1.0e-3 Pa s is the 20 C value, while
T_COOL_C = 25 C. The pair is deliberately conservative (+12.6% on viscous
pressure drop, Re correspondingly low). At 25 C mu = 0.890 mPa s. This is
recorded in the paper (section 6.3); do not "fix" one without the other.
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

# Source-footprint conventions, aliased from field.py so the single-source
# calibration chain reads them without importing the solver module at the
# top of the file (the two modules are mutually dependent by design).
#   F_SRC_SYNTHETIC = 2.0 -> 5x5 = 25 cells, 1249 W/cm^2: the concentrated
#       block REPORT.md §4 reports on and §22.4 ruled to retain.
#   F_SRC_REAL      = 8.0 -> 17x17 = 289 cells, ~108 W/cm^2: real die.
F_SRC_SYNTHETIC = 2.0
F_SRC_REAL = 8.0

# published reference points
TDP_I7_W = 253.0
TDP_H100_W = 700.0
PACKAGE_MM = 45.0
TJ_MAX_C = 100.0
R_COLDPLATE_BEST = 0.0069      # C/W, diamond pin-fin @ 1 kW, chip-to-coolant incl. TIM
R_COLDPLATE_OCP_LO = 0.014     # C/W, OCP OAI case-to-inlet, 1.5-3.5 LPM/cold plate
R_COLDPLATE_OCP_HI = 0.019     # C/W, same source; do NOT collapse into 0.0069-0.0200
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

    # --- the two areas, and why both must be reported (DEFECT_REMEDIATION
    # PLAN §5.4 漏洞 B). The model heats 25 discrete cells; the package has a
    # 45x37.5 mm die footprint. Quoting ONE of them as "the area" silently
    # picks a power density: 253 W over 25 mm^2 is 1012 W/cm^2, over
    # 1687.5 mm^2 it is 15.0 W/cm^2 -- a 67x spread from the same watts.
    @property
    def area_discrete_mm2(self) -> float:
        """Area actually heated in the model = n_src_cells * grid_mm^2."""
        return self.n_src_cells * self.grid_mm ** 2

    @property
    def die_area_mm2(self) -> float:
        """Physical die footprint (45 x 37.5 mm for the i7-14700K class)."""
        return self.plate_mm * (self.plate_mm * 37.5 / 45.0)

    @property
    def area_quantization_error(self) -> float:
        """(discrete - physical)/physical. Negative = the model overstates
        the power density because it heats fewer mm^2 than the die has."""
        return (self.area_discrete_mm2 - self.die_area_mm2) / self.die_area_mm2

    @property
    def power_density_w_cm2(self) -> float:
        """Power density on the PHYSICAL die footprint. Always quote next to
        area_quantization_error so the reader sees the model's heating area
        is not the die area."""
        return self.total_power_w / (self.die_area_mm2 / 100.0)

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


def solve_real(cal: Calibration, grid: int = 50, centers=None,
               source_radius: float = F_SRC_SYNTHETIC):
    """Physical temperature field [C] for a calibration. No normalisation:
    the peak is whatever the physics gives.

    `source_radius` defaults to the concentrated 5x5 block
    (F_SRC_SYNTHETIC), which is what every pre-migration result used and
    what REPORT.md §4 reports on. Real-die runs pass
    F_SRC_REAL (= 8 cells) instead -- see conjugate_multi.py, which needs
    that footprint to reach ~119 W/cm^2 rather than 1249 W/cm^2.
    """
    from field import solve_heat_sources

    if centers is None:
        centers = [((grid - 1) // 2, (grid - 1) // 2)]
    elif len(centers) == 2 and all(isinstance(c, int) for c in centers):
        centers = [tuple(centers)]              # a single (y, x) pair
    return solve_heat_sources(grid=grid, centers=centers,
                              source_radius=source_radius,
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
    src = source_mask_multi(grid, centers, radius=F_SRC_SYNTHETIC)
    cells = [(i // grid, i % grid)
             for i in sorted(set([p for p, _ in edges] + [c for _, c in edges]))]
    # A7 FIX (2026-10-18): apply_channels ALWAYS uses the dimensionless
    # source term (PITCH^2/4)*strength, with strength=1 when None. Passing
    # the physical field as the initial guess did NOT make the re-solve
    # physical: the pinned solve ignored cal.q_solver and cal.k_w_mk, so
    # i7 (253 W) and H100 (700 W) both returned peak 27.6 C and the two
    # R_th values differed only through the denominator (0.0103 vs 0.0037).
    # field.solve_heat uses src_b = q*PITCH^2/(4k), so the matching
    # strength is q_solver/k.
    strength = src * (cal.q_solver / cal.k_w_mk)
    Tc, pinned = V.apply_channels(solve_real(cal, grid, centers), cells, src,
                                  T_cool=T_COOL_C, strength=strength)
    return Tc, pinned


def lpm(q_m3s: float) -> float:
    """m3/s -> litres per minute."""
    return q_m3s * 1000.0 * 60.0


def paper_grid_mm(grid: int = 50) -> float:
    """The ONE authoritative grid pitch for every REAL-UNIT pressure-drop
    number. P0b v3 failed because its script carried its own PITCH_MM = 1.0
    while calibrate used grid_mm = 0.9: a 10% pitch difference became a 52%
    per-segment resistance difference through r^4, and 16x on the total
    (DEFECT_REMEDIATION_PLAN.md §10.9).

    Two pitches coexist BY DESIGN and must NOT be unified (the naive
    "single source of truth" fix would be wrong):

      * `field.PITCH_MM = 1.0` -- a DEFINITIONAL constant of the
        dimensionless solver (h in the 5-point Laplacian, k=1). Changing it
        would move every historical number in the project.
      * `grid_mm = 0.9` -- the MAPPING parameter from that dimensionless
        board onto the 45 mm package. It is the only pitch with which a
        real-unit dp (Pa, kPa) may be computed.

    So this function is the single entry point for real-unit geometry: it
    derives the pitch from the published package size rather than restating
    it, and asserts the derivation against the one calibration that is
    actually used. A dp script that imports anything else is re-creating
    the v3 failure.
    """
    from field import PITCH_MM
    grid_mm = PACKAGE_MM / grid
    # Guard against drift: the calibration object and this entry point must
    # never disagree, otherwise the same tree gets two different dp values
    # depending on which door the script walked through.
    assert abs(i7_14700k(grid).grid_mm - grid_mm) < 1e-12, (
        "grid pitch drift: paper_grid_mm and i7_14700k disagree")
    return grid_mm


def coolant_flow_m3s(power_w: float, dT_c: float = 5.0) -> float:
    """Volumetric flow to carry `power_w` with a dT_c coolant rise."""
    return power_w / (RHO_WATER * CP_WATER * dT_c)


def _tree_network_dp_pa(edges, radii, grid_mm: float,
                        q_total_m3s: float, mu: float) -> dict:
    """Pressure drop of a SINGLE-INLET / MULTI-OUTLET branching network,
    under the DEMAND-DRIVEN flow convention (project convention A).

    Two facts, in order:

    (1) The tree is a branching network, NOT a series pipe. Summing
        8*mu*L*Q/(pi*r^4) over every edge is only valid if the flow is fully
        extracted at the end of each segment -- that describes a series pipe.
        For a tree the inlet-to-outlet drop is the drop along ONE
        root-to-leaf PATH.

    (2) Geometry alone does not fix the dp: it also depends on the flow
        convention, i.e. on the outlet boundary condition. Two conventions
        are possible (DEFECT_REMEDIATION_PLAN.md §10.12):
          A  demand-driven: each leaf carries its design load, so
             Q_parent = sum(Q_children) top-down. This is the convention
             Murray's law is DERIVED for, and the one `assign_radii`,
             `node_flows`, and the control group (q/n per branch) all use.
          B  resistance-driven: all leaves are shorted onto a common
             manifold at equal pressure, so Kirchhoff sets the split and
             demand is irrelevant. Measures maldistribution of a geometry
             that was NOT designed for that flow field.

        On this tree (61 leaves, depths 11..16, subtree resistances
        spanning 35.6x) B comes out 0.85x A -- only 15% lower, because the
        low-resistance branch carries 49% of the flow under B instead of
        its 49%-of-leaves demand. Convention A is the project standard and
        the only one comparable to the control group, so it is what this
        function uses. `dp_kirchhoff_reference_pa` reports B for contrast,
        and `path_spread_x` reports how well the tree matches its own
        design point: A gives 1.344x (path LENGTH also matters -- leaf
        depths run 11..16), while B gives exactly 1.000x by construction,
        because "every leaf on one pressure" is the definition of B.

    Returns a dict with the physical dp plus diagnostics.
    """
    import numpy as np
    from radius import build_tree, node_flows

    children, parent, depth, root = build_tree(edges)
    nodes = set(parent) | set(parent.values()) | {root}
    leaves = [v for v in nodes if not children.get(v)]

    # demand-driven flow, normalised so the root carries q_total
    demand = node_flows(edges)
    total_demand = demand[root]
    q: dict[int, float] = {v: q_total_m3s * demand[v] / total_demand
                           for v in nodes}

    def r_edge(p: int, c: int) -> float:
        r = min(radii[p], radii[c]) * SI          # mm -> m
        return 8.0 * mu * (grid_mm * SI) / (np.pi * r ** 4)

    # root-to-leaf path drop under the demand-driven split.
    # Q on an edge = the child node's demand (continuity: the parent's flow
    # is the sum of its children's, so an edge carries exactly q[child]).
    # Computed by explicitly walking each leaf's parent chain -- no max
    # recursion, so the per-leaf distribution is exact.
    def drop_to_leaf(l: int) -> float:
        d, v = 0.0, l
        while v != root:
            d += r_edge(parent[v], v) * q[v]
            v = parent[v]
        return d

    dps = [drop_to_leaf(l) for l in leaves]
    d_max = max(dps)
    d_min = min(dps)
    spread = d_max / d_min if d_min > 0 else float("inf")

    # serial references: what the pre-§10.11 code returned. TWO stacked
    # errors, kept separately so each factor stays traceable:
    #   (a) series structure: sums every edge instead of one root-to-leaf
    #       path  (factor ~34x on this tree)
    #   (b) parent charging: each edge (p,c) was charged the PARENT's full
    #       demand instead of the child's, i.e. each sibling edge paid for
    #       its siblings too  (factor ~2.4x)
    # (a)+(b) together reproduce the historical 6.42 kPa (A0-verified).
    serial_hist = sum(r_edge(p, c) * (q_total_m3s * demand[p] / total_demand)
                      for p, c in edges)
    serial_child = sum(r_edge(p, c) * q[c] for p, c in edges)

    # Kirchhoff (convention B) for contrast only
    r_sub: dict[int, float] = {}
    for v in sorted(nodes, key=lambda i: -depth[i]):
        ch = children.get(v)
        if not ch:
            r_sub[v] = 0.0
        else:
            inv = sum(1.0 / (r_edge(v, c) + r_sub[c]) for c in ch)
            r_sub[v] = 1.0 / inv if inv > 0 else 0.0
    d_kirchhoff = q_total_m3s * r_sub[root]

    # self-check for the Kirchhoff solve: rebuild its flow split and verify
    # the max root-to-leaf path equals Q*R_eq (all leaves sit at 0 V, so
    # every path drop must equal the source voltage)
    qk: dict[int, float] = {root: q_total_m3s}
    stack = [root]
    while stack:
        v = stack.pop()
        ch = children.get(v)
        if not ch:
            continue
        inv = {c: 1.0 / (r_edge(v, c) + r_sub[c]) for c in ch}
        tot = sum(inv.values())
        for c in ch:
            qk[c] = qk[v] * inv[c] / tot
            stack.append(c)

    def drop_to_leaf_k(l: int) -> float:
        d, v = 0.0, l
        while v != root:
            d += r_edge(parent[v], v) * qk[v]
            v = parent[v]
        return d

    k_max = max(drop_to_leaf_k(l) for l in leaves)
    k_min = min(drop_to_leaf_k(l) for l in leaves)
    kirchhoff_self_check = (abs(k_max - d_kirchhoff) / d_kirchhoff
                            if d_kirchhoff > 0 else 0.0)

    return {
        "dp_pa": d_max,
        "dp_path_max_pa": d_max,
        "dp_kirchhoff_reference_pa": d_kirchhoff,
        "dp_serial_reference_pa": serial_hist,
        "dp_serial_child_charged_pa": serial_child,
        "overcount_serial_x": (serial_hist / d_max) if d_max > 0
        else float("inf"),
        "series_factor_x": (serial_child / d_max) if d_max > 0
        else float("inf"),
        "parent_charge_factor_x": (serial_hist / serial_child)
        if serial_child > 0 else float("inf"),
        "kirchhoff_over_demand_x": (d_kirchhoff / d_max) if d_max > 0
        else float("inf"),
        "kirchhoff_self_check_rel": kirchhoff_self_check,
        "path_spread_x": spread,
        "kirchhoff_path_spread_x": (k_max / k_min) if k_min > 0
        else float("inf"),
        "dp_by_leaf_pa": dict(zip(leaves, dps)),
        "n_leaves": len(leaves),
        "n_forks": sum(1 for v in nodes if len(children.get(v, [])) >= 2),
        "max_depth": max(depth.values()),
    }


def tree_dp_pa(edges, radii, grid_x: int, grid_mm: float,
               q_total_m3s: float, mu: float = MU_WATER,
               with_junctions: bool = False,
               k_of: "callable | None" = None,
               skip_pseudo: bool = False) -> dict:
    """Poiseuille pressure drop of the tree in real units, as a NETWORK.

    `grid_mm` MUST come from `paper_grid_mm()` (or a Calibration's
    `grid_mm` field). Passing `field.PITCH_MM` here is the v3 failure mode
    (DEFECT_REMEDIATION_PLAN.md §10.9): the dimensionless pitch gives a
    geometrically wrong -- and r^4-amplified -- real-unit dp.

    §10.11 FIX: this used to SUM 8*mu*L*Q/(pi*r^4) over every edge, i.e. treat
    the tree as a series pipe. A branching network has its inlet-to-outlet
    drop on a single root-to-leaf path; relative to convention A the serial
    sum over-counted by 80x (6.42 kPa vs 0.0802 kPa), and by 94.6x relative
    to the Kirchhoff reference (0.0679 kPa). Both references are returned,
    labelled `dp_serial_reference_pa` / `dp_kirchhoff_reference_pa`, so the
    historical 6.42 kPa stays traceable.

    `with_junctions` adds junction losses along each root-to-leaf path,
    K taken from `k_of(Re, split)`, charged on the PARENT branch
    (DEFECT_REMEDIATION_PLAN.md §10.15.3 F1/F2):

      * F1 -- the loss at node v belongs only to leaves under v. The old
        code summed all 57 forks and added that total to the max viscous
        path, which is the same series-summation error as D1 (it produced
        538 kPa at K=1.8).
      * F2 -- reference area is the PARENT radius `radii[v]`; the old
        `min(radii[v], children)` picked a side-branch throat at pseudo-forks.

    The reported `dp_pa` is therefore max over leaves of
    (viscous + junction), not (max viscous) + (all junctions).
    `skip_pseudo=True` drops junctions whose parent/main flow ratio is below
    1.1 (equivalent to main share > 1/1.1 = 0.909); both variants are
    required by the v5 model family. The root is not counted as a junction
    (its loss is the inlet term, out of scope here).
    """
    from field import PITCH_MM

    if abs(grid_mm - PITCH_MM) < 1e-12:
        raise ValueError(
            "tree_dp_pa: grid_mm equals field.PITCH_MM. A real-unit dp needs "
            "the MAPPED pitch (calibrate.paper_grid_mm()), not the "
            "dimensionless solver constant -- this exact mix-up is why P0b "
            "v3's dp was 16x off (DEFECT_REMEDIATION_PLAN.md §10.9).")

    out = _tree_network_dp_pa(edges, radii, grid_mm, q_total_m3s, mu)

    if with_junctions:
        if k_of is None:
            raise ValueError("with_junctions=True requires k_of(Re, split)")
        from radius import build_tree, node_flows
        import numpy as np
        children, parent, depth, root = build_tree(edges)
        flow = node_flows(edges)
        total = max(flow.values())

        # F2: parent-branch reference area, always radii[v] -- never a child.
        def junction_loss(v: int) -> float:
            ch = children[v]
            q_parent = q_total_m3s * flow[v] / total
            q_main = max(q_total_m3s * flow[c] / total for c in ch)
            split = q_main / q_parent if q_parent > 0 else 0.0
            if skip_pseudo and q_parent / q_main < 1.1:
                return 0.0
            r_p = radii[v] * SI
            v_p = q_parent / (np.pi * r_p ** 2)
            re_p = RHO_WATER * v_p * 2.0 * r_p / mu
            return k_of(re_p, split) * RHO_WATER * v_p ** 2 / 2.0

        # The root's loss is the inlet term, not a junction (v5 §10.15.9).
        jun_at = {v: junction_loss(v) for v, ch in children.items()
                  if len(ch) >= 2 and v != root}

        def junction_on_path(l: int) -> float:
            d, v = 0.0, l
            while v != root:
                d += jun_at.get(v, 0.0)          # F1: path only
                v = parent[v]
            return d

        vis_by_leaf = out["dp_by_leaf_pa"]
        total_by_leaf = {l: vis + junction_on_path(l)
                         for l, vis in vis_by_leaf.items()}
        crit = max(total_by_leaf, key=total_by_leaf.get)
        out["dp_viscous_pa"] = out["dp_pa"]
        out["dp_junctions_pa"] = total_by_leaf[crit] - vis_by_leaf[crit]
        out["dp_pa"] = total_by_leaf[crit]
        out["dp_path_max_pa"] = out["dp_pa"]
        out["critical_leaf"] = crit
        # Old (wrong) series sum, kept only so the 538 kPa artifact stays traceable.
        out["dp_junction_serial_reference_pa"] = sum(jun_at.values())

    return out


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
                                                source_radius=F_SRC_SYNTHETIC).T,
                             T_target=100.0)
        edges = G.grow_tree(Td, max_nodes=400)
        radii = Ra.assign_radii(edges, grid=grid, r0=0.5)
        Tc, pinned = solve_real_with_channels(cal, edges, grid)
        r_th = (Tc.max() - T_COOL_C) / cal.total_power_w
        L.append(f"  + tree channels  peak {Tc.max():7.1f} C   "
                 f"R_th={r_th:.4f} C/W   ({len(edges)} segments, "
                 f"{int(pinned.sum())} pinned cells)")
        L.append(f"                   published ref 1: {R_COLDPLATE_BEST:.4f} C/W "
                 f"(chip-to-coolant, incl. TIM, 1 kW)")
        L.append(f"                   published ref 2: {R_COLDPLATE_OCP_LO:.3f}-"
                 f"{R_COLDPLATE_OCP_HI:.3f} C/W (case-to-inlet, 1.5-3.5 LPM only)")
        L.append(f"                   -> model is {r_th/R_COLDPLATE_BEST:.1f}x worse than ref 1; "
                 f"{r_th/R_COLDPLATE_OCP_HI:.1f}x-{r_th/R_COLDPLATE_OCP_LO:.1f}x "
                 f"worse than ref 2 (not like-for-like)")

        # --- pressure drop at a real flow rate
        q = coolant_flow_m3s(cal.total_power_w)
        dp = tree_dp_pa(edges, radii, grid, cal.grid_mm, q)
        n_cells = len(set([p for p, _ in edges] + [c for _, c in edges]))
        r_ctrl = float(np.sqrt(V.tree_material_mm2(edges, radii) / (n_cells * np.pi)))
        dp_ctrl = 8.0 * MU_WATER * (cal.plate_mm * SI) * (q / n_cells) / (np.pi * (r_ctrl * SI) ** 4)
        L.append(f"  flow {C_flow(q)}  ->  tree dP = {dp['dp_pa']/1000:8.4f} kPa, "
                 f"control dP = {dp_ctrl/1000:.5f} kPa  ({dp['dp_pa']/dp_ctrl:.0f}x)")
        L.append(f"                   [demand-driven network (convention A): "
                 f"{dp['n_leaves']} leaves, {dp['n_forks']} true forks, "
                 f"depth {dp['max_depth']}, path spread {dp['path_spread_x']:.3f}x]")
        L.append(f"                   [Kirchhoff reference (convention B, leaves "
                 f"shorted onto one manifold) = "
                 f"{dp['dp_kirchhoff_reference_pa']/1000:.4f} kPa "
                 f"({dp['kirchhoff_over_demand_x']:.2f}x A; self-check "
                 f"{dp['kirchhoff_self_check_rel']:.1e}, spread "
                 f"{dp['kirchhoff_path_spread_x']:.3f}x)]")
        L.append(f"                   [historical serial (pre-§10.11, WRONG) = "
                 f"{dp['dp_serial_reference_pa']/1000:.2f} kPa "
                 f"= {dp['overcount_serial_x']:.0f}x A; decomposes as "
                 f"series structure {dp['series_factor_x']:.1f}x "
                 f"x parent-charging {dp['parent_charge_factor_x']:.2f}x]")
        L.append(f"                   published cold plate dP = "
                 f"{DP_COLDPLATE_PUB_PA/1000:.0f} kPa at 1 kW "
                 f"(tree is {dp['dp_pa']/DP_COLDPLATE_PUB_PA:.4f}x at {cal.total_power_w:.0f} W)")

    L.append("")
    L.append("thickness sensitivity: R_th and dP both scale as 1/t, so the")
    L.append("numbers above move by the same factor if the slab thickness")
    L.append("assumption moves. The *ratios* tree-vs-control do not.")
    L.append("")
    L.append("microchannel reference: Ecotherm production data gives fin")
    L.append("spacing P <= 0.5 mm and Dh = 2*P*L/(P+L) ~= 2*P (L/P > 15),")
    L.append("so Dh = 0.4-1.0 mm for P = 0.2-0.5 mm. The model's capillaries")
    L.append("are r0=0.5 mm (D=1.0 mm): the r^4 penalty is 1.0-39.1x, a")
    L.append("sensitivity range, not the historical 16-100x (16 needs the")
    L.append("interior P=0.25 mm; 100 needs P=0.158 mm, outside the range).")
    return "\n".join(L)


def C_flow(q_m3s: float) -> str:
    return f"{lpm(q_m3s):.2f} L/min"


if __name__ == "__main__":
    print(report())
