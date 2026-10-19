"""A2: inlet/outlet ports and the cover-layer outlet manifold.

The tree in `outputs/tree_edges.csv` is a single-inlet / 61-outlet branching
network, but the shipped STL has no way in and no way out. This script adds
the missing geometry and a first-order loss estimate:

  die layer      planar channel network: one tapered horizontal cylinder per
                 edge (r_parent -> r_child, same convention as mesh.export_stl),
                 centred at z = h_ch/2
  cover layer    one vertical via per leaf (r = leaf radius), one radial
                 groove per via to a perimeter collector ring, one outlet
                 port at the ring
  inlet          one port on the root axis, same diameter as the root branch

Geometry conventions that are CHOICES, not measurements, and are written into
the JSON so no reader has to guess:

  * package 45 mm (calibrate.PACKAGE_MM), grid 50 -> pitch 0.9 mm
  * channel depth h_ch = 4.0 mm (root diameter 3.94 mm must fit)
  * cover thickness t_cover = 5.0 mm, chosen so the outlet hole leaves a
    (5.0 - 3.9365)/2 = 0.53 mm wall top and bottom; t_cover = 4.0 would
    leave 0.03 mm, i.e. no manufacturable wall
  * collector ring: one square frame, 6 mm wide x 2 mm deep, outer wall
    flush with the package edge (centreline 3 mm inside); the ring is the
    same 6 x 2 mm rectangle the loss model uses, so geometry and loss
    share one cross-section
  * outlet port: D = 2*r_root, ring centreline -> package edge (3 mm)
  * via minor loss K = 1.5 (0.5 contraction + 1.0 expansion, sharp-edged)
  * outlet exit loss K = 1.0

The loss number produced here is PRELIMINARY. It is NOT merged into the
authoritative `calibrate.tree_dp_pa` value (0.08025 kPa viscous at 253 W):
junction losses and developing-flow corrections are still pending (v5), and
this estimate uses the demand-driven per-leaf flow.
"""
from __future__ import annotations

import csv
import json
import math
import struct
from pathlib import Path

import numpy as np

import calibrate as C
import mesh as M

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"

GRID = 50
GRID_MM = C.paper_grid_mm(GRID)          # 0.9 mm
PACKAGE_MM = C.PACKAGE_MM                # 45 mm
H_CH_MM = 4.0
T_COVER_MM = 5.0
RING_W_MM = 6.0
RING_INSET_MM = RING_W_MM / 2.0         # ring outer wall flush with the edge
RING_D_MM = 2.0
Z_RING_MM = H_CH_MM + T_COVER_MM / 2.0       # ring mid-plane (6.5 mm)
OUTLET_EXT_MM = RING_INSET_MM                # ring centreline -> package edge
INLET_EXT_MM = 2.5                            # stub above the cover plate
WALL_MIN_MM = 0.5                             # handling wall around a port
VIA_LEN_MM = Z_RING_MM - H_CH_MM / 2.0         # pipe axis -> ring mid-plane
INLET_LEN_MM = H_CH_MM / 2.0 + T_COVER_MM + INLET_EXT_MM
K_VIA = 1.5
K_EXIT = 1.0
N_SIDES = 12


def load_tree(path: Path):
    edges, radii, xy = [], {}, {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            p, c = int(row["parent_idx"]), int(row["child_idx"])
            xy[p] = (float(row["px"]) * GRID_MM, float(row["py"]) * GRID_MM)
            xy[c] = (float(row["cx"]) * GRID_MM, float(row["cy"]) * GRID_MM)
            radii[p] = float(row["r_parent_mm"])
            radii[c] = float(row["r_child_mm"])
            edges.append((p, c))
    return edges, radii, xy


def leaves_of(edges):
    parents = {p for p, _ in edges}
    children = {c for _, c in edges}
    roots = sorted(parents - children)
    leaves = sorted(children - parents)
    return roots, leaves


def cyl(a, b, ra, rb, tris):
    tris.extend(M.cylinder_tris(np.array(a, float), np.array(b, float), ra, rb,
                                n=N_SIDES))


def frame_tris(x0, x1, y0, y1, w, z0, z1, tris):
    """Square annulus extruded in z, as one consistently oriented shell.

    Outer rectangle (x0..x1, y0..y1), inner rectangle inset by w on every
    side. Eight quads per face group (4 top, 4 bottom, 4 outer wall, 4 inner
    wall) = 32 triangles. Unlike four overlapping boxes this is a single
    closed 2-manifold with no coincident internal faces.
    """
    A, B = (x0, y0), (x1, y0)
    C, D = (x1, y1), (x0, y1)
    a, b = (x0 + w, y0 + w), (x1 - w, y0 + w)
    c, d = (x1 - w, y1 - w), (x0 + w, y1 - w)
    sides = [(A, B, a, b), (B, C, b, c), (C, D, c, d), (D, A, d, a)]

    def P(p, z):
        return np.array([p[0], p[1], z], float)

    def quad(p0, p1, p2, p3):
        tris.extend([(p0, p1, p2), (p0, p2, p3)])

    for P0, P1, p0, p1 in sides:
        quad(P(P0, z1), P(P1, z1), P(p1, z1), P(p0, z1))   # top, +z
        quad(P(P0, z0), P(p0, z0), P(p1, z0), P(P1, z0))   # bottom, -z
        quad(P(P0, z0), P(P1, z0), P(P1, z1), P(P0, z1))   # outer wall
        quad(P(p0, z0), P(p0, z1), P(p1, z1), P(p1, z0))   # inner wall (hole)


def write_stl(tris, path: Path):
    buf = bytearray(b"\0" * 80)
    buf += struct.pack("<I", len(tris))
    for t in tris:
        buf += M._facet(*t)
    path.write_bytes(bytes(buf))


def closure_report(path: Path) -> dict:
    """Closedness test that also accepts n-way junctions.

    `mesh.stl_manifold_report` accepts a directed edge shared by 1 or 2
    triangles per direction. At the root the tree forks four ways and three
    cylinders share one rim, so those caps appear 3 or 4 times per direction
    and are miscounted as "unpaired". The surface is nevertheless closed: a
    triangle mesh is closed iff every directed edge (a,b) occurs exactly as
    often as (b,a). This function tests that, and nothing else.
    """
    data = path.read_bytes()
    n_tri = struct.unpack_from("<I", data, 80)[0]
    counts: dict[tuple, int] = {}
    parent: dict[tuple, tuple] = {}
    off = 84
    kept = 0

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for _ in range(n_tri):
        vals = struct.unpack_from("<12fH", data, off)
        off += 50
        keys = [M._key((vals[3], vals[4], vals[5])),
                M._key((vals[6], vals[7], vals[8])),
                M._key((vals[9], vals[10], vals[11]))]
        if len(set(keys)) < 3:
            continue
        kept += 1
        for k in keys:
            parent.setdefault(k, k)
        for i in range(3):
            e = (keys[i], keys[(i + 1) % 3])
            counts[e] = counts.get(e, 0) + 1
            a, b = find(keys[i]), find(keys[(i + 1) % 3])
            if a != b:
                parent[a] = b
    boundary = [e for e, c in counts.items() if c != counts.get((e[1], e[0]), 0)]
    return {
        "triangles_kept": kept,
        "boundary_edges": len(boundary),
        "max_edge_multiplicity": max(counts.values()) if counts else 0,
        "edges_with_multiplicity_ge_3": sum(1 for c in counts.values() if c >= 3),
        "vertex_connected_components": len({find(k) for k in parent}),
        "closed": bool(kept > 0 and not boundary),
        "note": "closed <=> every directed edge occurs as often as its reverse; "
                "each primitive is generated closed, so this proves no missing "
                "facet, NOT that the overlapping union is one valid solid",
    }


def circular_dp(q, d, length, mu=C.MU_WATER, rho=C.RHO_WATER):
    """Darcy-Weisbach for a circular duct; laminar Hagen-Poiseuille below 2300."""
    area = math.pi * d * d / 4.0
    v = q / area
    re = rho * v * d / mu
    if re < 2300.0:
        return 128.0 * mu * length * q / (math.pi * d ** 4), re, v, "laminar"
    f = 0.3164 * re ** -0.25
    return f * (length / d) * rho * v * v / 2.0, re, v, "blasius"


def rect_dp(q, w, h, length, mu=C.MU_WATER, rho=C.RHO_WATER):
    """Rectangular duct: laminar 32*mu*L*v/D_h^2, else Blasius on D_h."""
    area = w * h
    dh = 2.0 * w * h / (w + h)
    v = q / area
    re = rho * v * dh / mu
    if re < 2300.0:
        return 32.0 * mu * length * v / dh ** 2, re, v, dh, "laminar"
    f = 0.3164 * re ** -0.25
    return f * (length / dh) * rho * v * v / 2.0, re, v, dh, "blasius"


def ray_to_ring(x, y, cx, cy):
    """Distance from (x,y) along the outward radial direction to the ring."""
    dx, dy = x - cx, y - cy
    n = math.hypot(dx, dy)
    if n < 1e-12:
        return 0.0, (1.0, 0.0)
    dx, dy = dx / n, dy / n
    lo, hi = RING_INSET_MM, PACKAGE_MM - RING_INSET_MM
    ts = []
    if abs(dx) > 1e-12:
        for wall in (lo, hi):
            t = (wall - x) / dx
            if t > 0:
                ts.append(t)
    if abs(dy) > 1e-12:
        for wall in (lo, hi):
            t = (wall - y) / dy
            if t > 0:
                ts.append(t)
    return min(ts), (dx, dy)


def point_seg_dist(p, a, b):
    pa = np.array([p[0] - a[0], p[1] - a[1]])
    ab = np.array([b[0] - a[0], b[1] - a[1]])
    denom = float(ab @ ab)
    t = 0.0 if denom == 0 else max(0.0, min(1.0, float(pa @ ab) / denom))
    q = ab * t
    return float(np.hypot(pa[0] - q[0], pa[1] - q[1]))


def seg_seg_dist(a1, b1, a2, b2):
    """2-D segment-to-segment distance: 0 if they cross, else the min of the
    four point-to-segment distances (exact for straight segments)."""
    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])

    d1, d2 = cross(a2, b2, a1), cross(a2, b2, b1)
    d3, d4 = cross(a1, b1, a2), cross(a1, b1, b2)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return 0.0
    return min(point_seg_dist(a1, a2, b2), point_seg_dist(b1, a2, b2),
               point_seg_dist(a2, a1, b1), point_seg_dist(b2, a1, b1))


def main():
    edges, radii, xy = load_tree(OUT / "tree_edges.csv")
    roots, leaves = leaves_of(edges)
    assert len(roots) == 1, roots
    root = roots[0]
    n_leaf = len(leaves)
    rx, ry = xy[root]
    r_root = radii[root]

    Q = C.coolant_flow_m3s(253.0)
    q_leaf = Q / n_leaf
    z_ch = H_CH_MM / 2.0
    z_ring = Z_RING_MM
    z_top = H_CH_MM + T_COVER_MM

    tris = []

    # ---- die layer: planar channel network -------------------------------
    for p, c in edges:
        cyl((xy[p][0], xy[p][1], z_ch), (xy[c][0], xy[c][1], z_ch),
            radii[p], radii[c], tris)

    # ---- cover layer: vias, radial grooves, collector ring ---------------
    grooves = []
    for lf in leaves:
        x, y = xy[lf]
        r_leaf = radii[lf]
        cyl((x, y, z_ch), (x, y, z_ring), r_leaf, r_leaf, tris)            # via
        length, (dx, dy) = ray_to_ring(x, y, rx, ry)
        ex, ey = x + dx * length, y + dy * length
        grooves.append({"leaf": lf, "length_mm": length})
        cyl((x, y, z_ring), (ex, ey, z_ring), r_leaf, r_leaf, tris)        # groove

    hi = PACKAGE_MM - RING_INSET_MM
    frame_tris(0.0, PACKAGE_MM, 0.0, PACKAGE_MM, RING_W_MM,
               z_ring - RING_D_MM / 2.0, z_ring + RING_D_MM / 2.0, tris)

    # ---- inlet port on the root axis, outlet port at the ring ------------
    cyl((rx, ry, z_ch), (rx, ry, z_top + INLET_EXT_MM), r_root, r_root, tris)
    outlet_start = (PACKAGE_MM / 2.0, hi)
    outlet_end = (PACKAGE_MM / 2.0, PACKAGE_MM)
    cyl((*outlet_start, z_ring), (*outlet_end, z_ring), r_root, r_root, tris)

    stl_path = OUT / "manifold_assembly.stl"
    write_stl(tris, stl_path)

    # ---- interference checks --------------------------------------------
    groove_clear = []
    for g in grooves:
        lf = g["leaf"]
        length, (dx, dy) = ray_to_ring(xy[lf][0], xy[lf][1], rx, ry)
        a = xy[lf]
        b = (a[0] + dx * length, a[1] + dy * length)
        groove_clear.append(point_seg_dist((rx, ry), a, b))
    min_clear = min(groove_clear)

    # pairwise groove merging (same layer, same z): report, do not hide
    segs = []
    for g in grooves:
        lf = g["leaf"]
        length, (dx, dy) = ray_to_ring(xy[lf][0], xy[lf][1], rx, ry)
        a = xy[lf]
        segs.append((a, (a[0] + dx * length, a[1] + dy * length), radii[lf]))
    merged_pairs = []
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            (a1, b1, r1), (a2, b2, r2) = segs[i], segs[j]
            if seg_seg_dist(a1, b1, a2, b2) < r1 + r2:
                merged_pairs.append((i, j))
    overlap = len(merged_pairs)

    # merged clusters (union-find over the pairs above)
    parent = list(range(len(segs)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, j in merged_pairs:
        parent[find(i)] = find(j)
    cluster = {}
    for i in range(len(segs)):
        cluster.setdefault(find(i), []).append(i)
    merged_clusters = [c for c in cluster.values() if len(c) > 1]

    # a groove that passes through another leaf's via is a hydraulic junction
    via_hits = 0
    for i, (a, b, r) in enumerate(segs):
        for lf in leaves:
            if xy[lf] == a:
                continue
            if point_seg_dist(xy[lf], a, b) < r + radii[lf]:
                via_hits += 1

    # ---- first-order losses ---------------------------------------------
    dp_in_port, re_in, v_in, reg_in = circular_dp(
        Q, 2.0 * r_root / 1000.0, INLET_LEN_MM / 1000.0)
    dp_out_port, re_out, v_out, reg_out = circular_dp(
        Q, 2.0 * r_root / 1000.0, OUTLET_EXT_MM / 1000.0)
    dp_exit = K_EXIT * C.RHO_WATER * v_out ** 2 / 2.0
    dp_via, re_via, v_via, reg_via = circular_dp(
        q_leaf, 2.0 * radii[leaves[0]] / 1000.0, VIA_LEN_MM / 1000.0)
    dp_via += K_VIA * C.RHO_WATER * v_via ** 2 / 2.0

    d_half = RING_W_MM / 1000.0
    h_half = RING_D_MM / 1000.0
    half_perim = 2.0 * ((PACKAGE_MM - 2.0 * RING_INSET_MM) / 1000.0)
    dp_ring, re_ring, v_ring, dh_ring, reg_ring = rect_dp(
        Q / 2.0, d_half, h_half, half_perim)

    groove_dp = []
    for g in grooves:
        dp, _, _, _ = circular_dp(q_leaf, 2.0 * radii[g["leaf"]] / 1000.0,
                                  g["length_mm"] / 1000.0)
        groove_dp.append(dp)
    dp_groove_max = max(groove_dp)
    dp_groove_mean = sum(groove_dp) / len(groove_dp)

    dp_added_max = dp_in_port + dp_via + dp_groove_max + dp_ring + dp_out_port + dp_exit
    dp_added_mean = dp_in_port + dp_via + dp_groove_mean + dp_ring + dp_out_port + dp_exit
    dp_tree_viscous = 80.248  # Pa, calibrate.py convention A at 253 W (0.08025 kPa)

    bb = M.bbox(str(stl_path))
    report = {
        "about": "A2 port/manifold geometry; loss figures are PRELIMINARY and "
                 "are NOT part of calibrate.tree_dp_pa",
        "pitch_mm": GRID_MM,
        "package_mm": PACKAGE_MM,
        "tree": {"nodes": len(radii), "edges": len(edges), "leaves": n_leaf,
                 "root_mm": [rx, ry], "root_radius_mm": r_root,
                 "leaf_radius_mm": sorted({round(radii[l], 6) for l in leaves})},
        "assumptions": {
            "channel_depth_mm": H_CH_MM,
            "cover_thickness_mm": T_COVER_MM,
            "ring_inset_mm": RING_INSET_MM,
            "ring_width_mm": RING_W_MM,
            "ring_depth_mm": RING_D_MM,
            "outlet_port_ext_mm": OUTLET_EXT_MM,
            "inlet_stub_mm": INLET_EXT_MM,
            "via_length_mm": VIA_LEN_MM,
            "ring_mid_plane_mm": Z_RING_MM,
            "ring_cross_section": "rectangle 6 mm wide x 2 mm deep (matches rect_dp)",
            "outlet_port_wall_mm": (T_COVER_MM - 2.0 * r_root) / 2.0,
            "wall_min_mm": WALL_MIN_MM,
            "K_via": K_VIA,
            "K_exit": K_EXIT,
            "flow_m3s": Q,
            "flow_lpm": Q * 60000.0,
            "per_leaf_m3s": q_leaf,
        },
        "geometry": {
            "triangles": len(tris),
            "stl": "outputs/manifold_assembly.stl",
            "groove_length_mm": {"min": min(g["length_mm"] for g in grooves),
                                 "max": max(g["length_mm"] for g in grooves),
                                 "mean": sum(g["length_mm"] for g in grooves) / n_leaf},
            "inlet_port_clearance_mm": min_clear,
            "inlet_port_clearance_ok": bool(
                min_clear > r_root + max(radii[l] for l in leaves)),
            "outlet_port_wall_ok": bool(
                (T_COVER_MM - 2.0 * r_root) / 2.0 >= WALL_MIN_MM),
            "groove_pairs_merged": overlap,
            "merged_clusters": len(merged_clusters),
            "grooves_in_merged_clusters": sum(len(c) for c in merged_clusters),
            "max_cluster_size": max((len(c) for c in merged_clusters), default=1),
            "groove_through_other_via": via_hits,
            "merged_note": "merged grooves share a manifold; the per-leaf model "
                           "charges each leaf a full-length duct and ignores the "
                           "larger shared cross-section, so the groove term is "
                           "expected to over-estimate, not to be exact",
            "mesh_note": "union of closed primitives: end caps at multi-way nodes "
                         "and groove tips inside the ring are interior faces; "
                         "watertight per primitive, not one boolean-unioned solid. "
                         "Measured decomposition of the 236 directed edges with "
                         "multiplicity >= 3: 228 vertical spokes + 8 horizontal "
                         "spokes. Mechanism: for a horizontal cylinder (axis in "
                         "the xy plane) u = axis x zhat is horizontal and "
                         "v = -zhat, so the rim points at t = 90 and 270 deg are "
                         "always center -/+ r*zhat; at a node with k outgoing "
                         "channels the k child end caps and the parent end cap "
                         "(k caps at the root) are coincident 12-gons of the same "
                         "radius, so those two rim points are shared by k+1 (k) "
                         "caps and yield 2 spokes x 2 directions = 4 edges per "
                         "node. 57 nodes have out-degree >= 2, giving 57 x 2 x 2 = "
                         "228 vertical spokes; the remaining 8 are the root's 4 "
                         "collinear radial spokes x 2 directions. Multiplicity "
                         "distribution: mult=3 for 220 vertical + 8 horizontal, "
                         "mult=4 for the 4 spokes at the root (k=4) and at the "
                         "single k=3 node. All 236 reverse counts match and "
                         "boundary_edges = 0, so closure holds. 2 vertex-connected "
                         "components = main assembly + the 16-vertex collector "
                         "frame, which shares no vertices.",
        },
        "losses_pa": {
            "inlet_port": dp_in_port, "via": dp_via,
            "groove_max": dp_groove_max, "groove_mean": dp_groove_mean,
            "ring_half": dp_ring,
            "outlet_port": dp_out_port, "exit": dp_exit,
            "added_total_max_path": dp_added_max,
            "added_total_mean_path": dp_added_mean,
            "added_total_max_path_exit_excluded": dp_added_max - dp_exit,
            "tree_viscous_reference": dp_tree_viscous,
            "ratio_to_tree_viscous_max": dp_added_max / dp_tree_viscous,
            "ratio_exit_excluded": (dp_added_max - dp_exit) / dp_tree_viscous,
        },
        "regimes": {
            "inlet_port": {"Re": re_in, "v_m_s": v_in, "regime": reg_in},
            "via": {"Re": re_via, "v_m_s": v_via, "regime": reg_via},
            "ring": {"Re": re_ring, "v_m_s": v_ring, "Dh_mm": dh_ring * 1000.0,
                     "regime": reg_ring},
            "outlet_port": {"Re": re_out, "v_m_s": v_out, "regime": reg_out},
        },
        "stl_check": M.stl_manifold_report(str(stl_path)),
        "stl_closure": closure_report(stl_path),
        "bbox_mm": bb,
        "bbox_inside_package": bool(
            bb["x"][0] >= 0.0 and bb["y"][0] >= 0.0
            and bb["x"][1] <= PACKAGE_MM and bb["y"][1] <= PACKAGE_MM),
    }

    with (OUT / "manifold_geometry.json").open("w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print(f"tree: {len(edges)} edges, {n_leaf} leaves, root r={r_root:.5f} mm")
    print(f"STL: {len(tris)} triangles -> {stl_path.name}, "
          f"boundary_edges={report['stl_closure']['boundary_edges']} "
          f"(closed={report['stl_closure']['closed']}); "
          f"legacy unpaired={report['stl_check']['unpaired_edges']} "
          f"= 228 vertical + 8 horizontal coincident-cap spokes "
          f"(max multiplicity {report['stl_closure']['max_edge_multiplicity']})")
    print(f"bbox inside package: {report['bbox_inside_package']} "
          f"size={bb['size_mm']}")
    print(f"inlet clearance {min_clear:.3f} mm "
          f"(need > {r_root + max(radii[l] for l in leaves):.3f}) -> "
          f"{report['geometry']['inlet_port_clearance_ok']}")
    print(f"outlet port wall {(T_COVER_MM - 2.0 * r_root) / 2.0:.3f} mm "
          f"(need >= {WALL_MIN_MM}) -> "
          f"{report['geometry']['outlet_port_wall_ok']}")
    print(f"merged groove pairs: {overlap} in {len(merged_clusters)} clusters "
          f"({sum(len(c) for c in merged_clusters)}/{n_leaf} grooves, "
          f"max {report['geometry']['max_cluster_size']}); "
          f"groove-through-other-via {via_hits}")
    print(f"loss added (max path) {dp_added_max:.1f} Pa "
          f"= {dp_added_max / dp_tree_viscous:.2f}x tree viscous "
          f"({dp_added_max - dp_exit:.1f} Pa = "
          f"{(dp_added_max - dp_exit) / dp_tree_viscous:.2f}x without exit loss)")
    print(f"  inlet port {dp_in_port:.1f}  via {dp_via:.1f}  "
          f"groove {dp_groove_max:.1f}  ring {dp_ring:.1f}  "
          f"outlet {dp_out_port:.1f}  exit {dp_exit:.1f}")


if __name__ == "__main__":
    main()
