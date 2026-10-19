"""Why is the flow-split convention not unique?

Diagnostic: measure the tree's ASYMMETRY and show that the two flow
conventions coincide only for a symmetric tree.

A branching network's inlet-to-outlet dp is not determined by geometry
alone: it also depends on the OUTLET boundary condition.

  Convention A (demand-driven): each leaf is an independent outlet whose
      flow is set by the thermal load it serves. Continuity is enforced
      top-down: Q_parent = sum(Q_children). Murray's law is DERIVED for
      this case (minimise pumping power for GIVEN leaf flows).

  Convention B (resistance-driven): all leaves discharge into one common
      manifold at equal pressure, so Kirchhoff sets the split:
      Q_child = Q_parent * (1/R_child) / sum(1/R_j). Demand is irrelevant.

For a SYMMETRIC tree the two coincide. This tree is grown toward a single
hot spot, so branches have different depths -- measure by how much.
"""
from __future__ import annotations

from collections import Counter

import numpy as np

import grow as G
import radius as Ra
import verify as V
from field import SRC_RADIUS_SYNTHETIC, normalize_field, solve_heat_sources
from radius import build_tree, node_flows

Td = normalize_field(
    solve_heat_sources(grid=50, centers=[(25, 25)],
                       source_radius=SRC_RADIUS_SYNTHETIC).T,
    T_target=100.0)
edges = G.grow_tree(Td, max_nodes=400)
radii = Ra.assign_radii(edges, grid=50, r0=0.5)

ch, pa, de, root = build_tree(edges)
flow = node_flows(edges)
nodes = set(pa) | set(pa.values()) | {root}
leaves = [v for v in nodes if not ch.get(v)]
MU, pitch = V.MU, 1.0


def r_edge(p, c):
    return 8.0 * MU * pitch / (np.pi * min(radii[p], radii[c]) ** 4)


# ---- subtree resistance, bottom-up -------------------------------------
rs = {}
for v in sorted(nodes, key=lambda i: -de[i]):
    c = ch.get(v)
    rs[v] = 0.0 if not c else 1.0 / sum(1.0 / (r_edge(v, x) + rs[x]) for x in c)

print("=" * 72)
print("WHY THE FLOW CONVENTION IS NOT UNIQUE")
print("=" * 72)
print(f"tree: {len(edges)} edges, {len(nodes)} nodes, {len(leaves)} leaves, "
      f"{sum(1 for v in nodes if len(ch.get(v, [])) >= 2)} true forks")

# ---- 1. asymmetry of leaf depth ---------------------------------------
depths = Counter(de[l] for l in leaves)
print(f"\n[1] LEAF DEPTH DISTRIBUTION (max depth = {max(de.values())})")
for d in sorted(depths):
    print(f"      depth {d:2d}: {depths[d]:2d} leaves  {'#' * depths[d]}")
print(f"    symmetric binary tree with {len(leaves)} leaves would have "
      f"depth ~{int(np.ceil(np.log2(len(leaves))))}")
print(f"    actual max depth = {max(de.values())}  "
      f"=> the tree is DEEPLY asymmetric")

# ---- 2. subtree resistance spread at the root's children --------------
rc = ch[root]
print(f"\n[2] ROOT'S {len(rc)} CHILDREN -- subtree resistance")


def descendants(v: int) -> int:
    """Leaves in v's subtree."""
    c = ch.get(v)
    if not c:
        return 1
    return sum(descendants(x) for x in c)


invs = {c: 1.0 / (r_edge(root, c) + rs[c]) for c in rc}
tot = sum(invs.values())
for c in sorted(rc, key=lambda x: -invs[x]):
    print(f"      child {str(c):>18}: R_sub = {r_edge(root, c) + rs[c]:12.4f}   "
          f"share under convention B = {invs[c]/tot:6.1%}   "
          f"leaves below = {descendants(c)}")
print(f"    spread = {max(invs.values())/min(invs.values()):.1f}x "
      f"between the lowest- and highest-resistance branch")

# ---- 3. the two conventions on the same tree --------------------------
# Convention A = node_flows (demand-driven), normalised so the root carries
# n_leaves -- i.e. exactly what assign_radii / Murray's law assume.
# Convention B = Kirchhoff split (all leaves shorted onto a common manifold).


# Convention A: the edge into v carries exactly the demand of subtree v.
qA_edge = {v: flow[v] / flow[root] for v in nodes}

qB = {root: float(len(leaves))}
qB_edge = {}
st = [root]
while st:
    v = st.pop()
    c = ch.get(v)
    if not c:
        continue
    inv = {x: 1.0 / (r_edge(v, x) + rs[x]) for x in c}
    t = sum(inv.values())
    for x in c:
        qB[x] = qB[v] * inv[x] / t
        qB_edge[(v, x)] = qB[x]
        st.append(x)


def chain_drop(leaf, q_edge):
    """Exact drop along ONE root-to-leaf path (no max recursion: a max over
    siblings does not belong to this leaf and must not be mixed in)."""
    d, v = 0.0, leaf
    while v != root:
        d += r_edge(pa[v], v) * q_edge[v]
        v = pa[v]
    return d


allA = [chain_drop(l, qA_edge) for l in leaves]
# B was solved with root = n_leaves; rescale to the SAME inlet flow as A,
# otherwise the comparison is a normalisation artefact, not physics.
allB = [chain_drop(l, qB) / qB[root] for l in leaves]
print(f"\n[3] ROOT-TO-LEAF PATH DROP UNDER EACH CONVENTION")
print(f"    A (demand / node_flows):  min = {min(allA):8.4f}  "
      f"max = {max(allA):8.4f}  spread = {max(allA)/min(allA):.3f}x")
print(f"       -> NOT exactly equal: equal path LENGTH is also required, and")
print(f"          this tree's leaf depths run {min(depths)}..{max(depths)}")
print(f"    B (resistance / Kirchhoff): min = {min(allB):8.4f}  "
      f"max = {max(allB):8.4f}  spread = {max(allB)/min(allB):.6f}x")
print(f"       -> exactly equal BY CONSTRUCTION (all leaves shorted to one")
print(f"          pressure); that is the definition of B, not a merit")
print()
print(f"    inlet dp, convention A (max path) = {max(allA):.4f}")
print(f"    inlet dp, convention B (max path) = {max(allB):.4f}")
print(f"    ratio B/A = {max(allB)/max(allA):.3f}x")
print()
edge_flows_B = sorted(qB_edge.values(), reverse=True)
print(f"[4] CONVENTION B'S FLOW FIELD (root carries {qB[root]:.0f})")
print(f"    max edge flow = {edge_flows_B[0]:.2f}   "
      f"min edge flow = {edge_flows_B[-1]:.2f}   "
      f"ratio = {edge_flows_B[0]/edge_flows_B[-1]:.0f}x")
print(f"    under convention A every leaf gets exactly "
      f"{flow[root]/len(leaves):.2f}")
print(f"    convention B's leaf flows: max = {max(qB[l] for l in leaves):.2f}  "
      f"min = {min(qB[l] for l in leaves):.2f}  "
      f"spread = {max(qB[l] for l in leaves)/min(qB[l] for l in leaves):.0f}x")
print()
print("=" * 72)
print("CONCLUSION")
print("=" * 72)
print("The two conventions are NOT two answers to one question -- they are")
print("two different questions:")
print("  A: 'what does this tree cost when each outlet carries its design")
print("      load?'  -> the number Murray's law was built to minimise")
print("  B: 'what does this tree cost when its outlets are shorted onto a")
print("      common manifold?'  -> measures maldistribution of a geometry")
print("      that was NOT designed for that flow field")
print()
print("They coincide only for a symmetric tree. This tree reaches toward a")
print(f"single hot spot, so leaf depths run {min(depths)}..{max(depths)} and")
print("subtree resistances differ by orders of magnitude -- hence the gap.")
