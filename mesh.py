"""Step 4: cylinder-per-edge mesher writing a binary STL by hand (no deps).

Every edge becomes a closed tapered cylinder between its two nodes. All
cylinders lie in ONE z plane (z = height/2), so at a node the end caps of
all incident edges share the node centre and the solid is volume-connected;
the old z=0 -> z=height slope left a 4.23 mm gap at every node
(DEFECT_REMEDIATION_PLAN.md 10.20). Each primitive is closed and
outward-facing; coincident caps at multi-way nodes still make 228 edges
non-manifold (shared by 3 or 4 triangles), reported separately.

height: slab thickness in mm; the mesh sits on its mid-plane.
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np


def _facet(p1, p2, p3) -> bytes:
    n = np.cross(p2 - p1, p3 - p1)
    norm = np.linalg.norm(n)
    n = n / norm if norm > 0 else np.array([0.0, 0.0, 1.0])
    return struct.pack(
        "<12fH",
        n[0], n[1], n[2],
        p1[0], p1[1], p1[2],
        p2[0], p2[1], p2[2],
        p3[0], p3[1], p3[2],
        0,
    )


def cylinder_tris(a, b, ra: float, rb: float, n: int = 12):
    """Closed tapered cylinder a->b: side quads + two cap fans, consistently
    wound so every directed edge is shared by exactly two triangles."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    axis = b - a
    L = np.linalg.norm(axis)
    if L < 1e-12:
        return []

    axis = axis / L
    ref = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(axis, ref)) > 0.9:
        ref = np.array([1.0, 0.0, 0.0])
    u = np.cross(axis, ref)
    u /= np.linalg.norm(u)
    v = np.cross(axis, u)

    ang = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    ring_a = np.array([a + ra * (np.cos(t) * u + np.sin(t) * v) for t in ang])
    ring_b = np.array([b + rb * (np.cos(t) * u + np.sin(t) * v) for t in ang])

    tris = []
    for i in range(n):
        j = (i + 1) % n
        # side quad (ring_a[i], ring_b[i], ring_b[j], ring_a[j])
        tris.append((ring_a[i], ring_b[i], ring_b[j]))
        tris.append((ring_a[i], ring_b[j], ring_a[j]))
    # end caps: fans from the centre. Winding must agree with the side quads,
    # which traverse each rim edge ring[i] -> ring[j]; hence cap at a uses
    # (a, ring[i], ring[j]) and cap at b uses (b, ring[j], ring[i]).
    for i in range(n):
        j = (i + 1) % n
        tris.append((a, ring_a[i], ring_a[j]))
        tris.append((b, ring_b[j], ring_b[i]))
    # The construction above is consistently CLOSED but inward-facing:
    # (u, v, axis) is right-handed, so ring_a[i] -> ring_b[i] -> ring_b[j]
    # yields a normal of -outward. Measured: signed volume of a r=0.5, h=1
    # cylinder is -0.75 mm^3 (12-gon area 0.75 x h 1), i.e. every facet
    # normal points into the solid (DEFECT_REMEDIATION_PLAN.md 10.22).
    # Reverse each triangle once, at the end, so all primitives in the file
    # (including the ports_manifold frame, which is already outward) agree.
    return [(c, b, a) for a, b, c in tris]


def export_stl(
    edges: list[tuple[int, int]],
    radii: dict[int, float],
    grid: int,
    height: float,
    path: str,
    n_sides: int = 12,
    pitch_mm: float = 1.0,
) -> int:
    """Write binary STL. Returns the number of triangles."""
    tris_all = []
    for p, c in edges:
        py, px = divmod(p, grid)
        cy, cx = divmod(c, grid)
        # Both ends on the SAME z plane. Previously the parent sat at z=0 and
        # the child at z=height, so every edge sloped through the full slab and
        # the end caps of two edges meeting at a node were 4.23 mm apart: the
        # STL was not a connected channel (DEFECT_REMEDIATION_PLAN.md 10.20).
        a = np.array([px * pitch_mm, py * pitch_mm, height / 2.0])
        b = np.array([cx * pitch_mm, cy * pitch_mm, height / 2.0])
        rp = radii.get(p, 0.5)
        rc = radii.get(c, 0.5)
        tris_all.extend(cylinder_tris(a, b, rp, rc, n=n_sides))

    buf = bytearray()
    buf += b"\0" * 80
    buf += struct.pack("<I", len(tris_all))
    for t in tris_all:
        buf += _facet(*t)

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bytes(buf))
    return len(tris_all)


def _key(vals) -> tuple:
    """Canonical vertex key: round to 4 decimals and kill signed zeros."""
    return tuple(round(c, 4) + 0.0 for c in vals)


def stl_manifold_report(path: str) -> dict:
    """Structural check of the binary STL.

    Three levels:
      * per-triangle sanity: every triangle counted once, no degenerate tris
      * closure: every directed edge (a,b) has the same count as (b,a) =>
        boundary_edges = 0 (volume can be sealed even when non-manifold)
      * manifoldness: an edge shared by exactly 2 triangles (once each
        direction). Coincident end caps at a multi-way node make some edges
        span 3 or 4 triangles; those are counted in `nonmanifold_edges`.
    """
    data = Path(path).read_bytes()
    n_tri = struct.unpack_from("<I", data, 80)[0]
    edge_count: dict[tuple, int] = {}
    off = 84
    for _ in range(n_tri):
        vals = struct.unpack_from("<12fH", data, off)
        off += 50
        vs = [(vals[3], vals[4], vals[5]), (vals[6], vals[7], vals[8]),
              (vals[9], vals[10], vals[11])]
        keys = [_key(v) for v in vs]
        if len(set(keys)) < 3:
            continue                      # degenerate triangle, ignore
        for i in range(3):
            a, b = keys[i], keys[(i + 1) % 3]
            edge_count[(a, b)] = edge_count.get((a, b), 0) + 1

    paired = sum(1 for (a, b), cnt in edge_count.items()
                 if cnt == 1 and edge_count.get((b, a), 0) == 1)
    junction = sum(1 for (a, b), cnt in edge_count.items()
                   if cnt == 2 and edge_count.get((b, a), 0) == 2)
    unpaired = sum(1 for (a, b), cnt in edge_count.items()
                   if not (cnt == 1 and edge_count.get((b, a), 0) == 1)
                   and not (cnt == 2 and edge_count.get((b, a), 0) == 2))
    boundary = sum(1 for (a, b), cnt in edge_count.items()
                   if edge_count.get((b, a), 0) != cnt)
    nonmanifold = sum(1 for (a, b), cnt in edge_count.items() if cnt >= 3)
    return {
        "triangles": n_tri,
        "unique_directed_edges": len(edge_count),
        "edges_paired_once": paired,
        "junction_edges_shared_twice": junction,
        "unpaired_edges": unpaired,
        "boundary_edges": boundary,
        "closed": bool(n_tri > 0 and boundary == 0),
        "nonmanifold_edges": nonmanifold,
        "is_manifold": bool(n_tri > 0 and unpaired == 0),
    }


def bbox(path: str) -> dict:
    data = Path(path).read_bytes()
    n_tri = struct.unpack_from("<I", data, 80)[0]
    off = 84
    xs, ys, zs = [], [], []
    for _ in range(n_tri):
        vals = struct.unpack_from("<12fH", data, off)
        off += 50
        xs += [vals[3], vals[6], vals[9]]
        ys += [vals[4], vals[7], vals[10]]
        zs += [vals[5], vals[8], vals[11]]
    return {
        "x": (min(xs), max(xs)),
        "y": (min(ys), max(ys)),
        "z": (min(zs), max(zs)),
        "size_mm": (round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3),
                    round(max(zs) - min(zs), 3)),
    }
