# -*- coding: utf-8 -*-
"""裁判函数 evaluate()：把 field / verify / calibrate 的分层调用收拢成统一入口。

这是「接轨生成式设计」的第一步：任何拓扑（树 / 直通道 / 径向 / 格状）都通过
同一个接口被评估，输出 T_max / T_mean / hotspot / Δp / 材料 等指标，供生成器
（优化算法或未来的 AI 模型）调用。现有 field.py / verify.py / calibrate.py 零改动。

公平口径 fairness_basis：
  - "equal_pinned"：等钉住格点（论文 §5.3，径向/格状用 target_pinned）
  - "equal_total" ：等总占用格点 C5（论文 §5.4，径向/格状用 target_total）
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

import field as F
import grow as G
import radius as Ra
import verify as V

GRID = 50


@dataclass
class Topology:
    kind: str                       # "tree" | "straight" | "radial" | "lattice"
    # tree（edges/radii 缺省时由 evaluate 内部从温度场生长）
    edges: list | None = None
    radii: dict | None = None
    max_nodes: int = 400
    r0: float = 0.5
    # straight
    n_channels: int | None = None
    # straight / radial / lattice 等材料口径
    total_area_mm2: float | None = None
    # radial / lattice 等钉住口径
    target_pinned: int | None = None
    # radial / lattice 等总占用口径（C5）
    target_total: int | None = None


def make_tree(T_field, max_nodes: int = 400, r0: float = 0.5) -> Topology:
    """从温度场生成树拓扑（热场驱动生长 + Murray 管径）。"""
    edges = G.grow_tree(T_field, max_nodes=max_nodes)
    radii = Ra.assign_radii(edges, grid=GRID, r0=r0)
    return Topology(kind="tree", edges=edges, radii=radii,
                    max_nodes=max_nodes, r0=r0)


def solve_field(centers, source_radius=F.SRC_RADIUS_SYNTHETIC, q=1.0, powers=None):
    """解温度场 + 返回源掩码（供 evaluate 与生成器共用，避免重复求解）。"""
    T = F.solve_heat_sources(grid=GRID, centers=centers,
                             source_radius=source_radius, q=q, powers=powers).T
    src = F.source_mask_multi(GRID, centers, radius=source_radius, powers=powers)
    return T, src


def evaluate(topo: Topology, centers=((24, 24),),
             source_radius=F.SRC_RADIUS_SYNTHETIC, q=1.0, powers=None,
             fairness_basis="equal_pinned") -> dict:
    """评估一个拓扑在给定热源布局下的表现。

    返回 dict（全部 Python 原生类型，方便 JSON / 生成器消费）：
      T_max, T_mean_solid, hotspot_area, dp, material_mm2,
      n_segments, n_channels, pinned_cells
    """
    T, src = solve_field(centers, source_radius, q, powers)

    if topo.kind == "tree":
        if topo.edges is None:
            topo.edges = G.grow_tree(T, max_nodes=topo.max_nodes)
            topo.radii = Ra.assign_radii(topo.edges, grid=GRID, r0=topo.r0)
        g = V.tree_group(T, src, topo.edges, topo.radii, GRID)

    elif topo.kind == "straight":
        g = V.straight_group(T, src, topo.n_channels, topo.total_area_mm2,
                             GRID, GRID)

    elif topo.kind == "radial":
        if fairness_basis == "equal_pinned":
            g = V.radial_group_pinned(T, src, topo.target_pinned,
                                      topo.total_area_mm2, GRID, GRID)
        else:
            g = V.radial_group_total(T, src, topo.target_total,
                                     topo.total_area_mm2, GRID, GRID)

    elif topo.kind == "lattice":
        if fairness_basis == "equal_pinned":
            g = V.lattice_group(T, src, topo.target_pinned,
                                topo.total_area_mm2, GRID, GRID)
        else:
            g = V.lattice_group_total(T, src, topo.target_total,
                                      topo.total_area_mm2, GRID, GRID)

    else:
        raise ValueError(f"unknown topology kind: {topo.kind!r}")

    return {
        "T_max": float(g.T_max),
        "T_mean_solid": float(g.T_mean_solid),
        "hotspot_area": float(g.hotspot_area),
        "dp": float(g.dp),
        "material_mm2": float(g.total_area_mm2),
        "n_segments": int(g.n_segments),
        "n_channels": int(g.n_channels),
        "pinned_cells": int(g.pinned_cells),
    }


def compare(a: dict, b: dict) -> dict:
    """两个评估结果的两两比较（复用 verify.compare 的口径，返回纯 dict）。"""
    dT = a["T_max"] - b["T_max"]
    dT_mean = a["T_mean_solid"] - b["T_mean_solid"]
    return {
        "dT_max_C": round(dT, 4),
        "dT_mean_C": round(dT_mean, 4),
        "dp_ratio": round(a["dp"] / b["dp"], 3) if b["dp"] > 0 else None,
        "dHotspot_mm2": round(a["hotspot_area"] - b["hotspot_area"], 3),
    }
