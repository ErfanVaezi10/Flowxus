# -*- coding: utf-8 -*-
# Flowxus/mesh/repair/fixers/multi_edges.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
Dedupe oversubscribed edges (undirected) with >2 incident cells by dropping the
smallest-area offenders.

Main Tasks:
-----------
   - Build edge→incident cells map (tri/quad).
   - Rank incident cells by area and keep the two largest.
   - Remove extras; report applied count and notes.
"""

from typing import Dict, Any, List
from ..ops import Mesh, remove_cells
from ..utils import build_edge_cells


def _cell_area(mesh: Mesh, kind: str, idx: int) -> float:
    """
    Return absolute area of a triangle/quad (XY shoelace for quads).
    """
    P = mesh.points
    if kind == "tri":
        tri = P[mesh.tris[idx]]
        return 0.5 * abs((tri[1,0]-tri[0,0])*(tri[2,1]-tri[0,1]) - (tri[1,1]-tri[0,1])*(tri[2,0]-tri[0,0]))
    else:
        q = P[mesh.quads[idx]]
        area = (
            q[0,0]*q[1,1]-q[0,1]*q[1,0] +
            q[1,0]*q[2,1]-q[1,1]*q[2,0] +
            q[2,0]*q[3,1]-q[2,1]*q[3,0] +
            q[3,0]*q[0,1]-q[3,1]*q[0,0]
        ) * 0.5
        return abs(area)


def fix(mesh: Mesh, finding: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Oversubscribed edges: if an undirected edge has >2 incident cells, keep 2 and drop extras.
    Heuristic: drop the smallest-area cells first.
    """
    edge_cells = build_edge_cells(mesh.points, mesh.tris, mesh.quads)

    to_remove_tri: List[int] = []
    to_remove_quad: List[int] = []

    for e, inc in edge_cells.items():
        if len(inc) <= 2:
            continue
        # Rank offenders by area ascending
        ranked = sorted(inc, key=lambda k_i: _cell_area(mesh, k_i[0], k_i[1]))
        # Keep two largest; remove the rest
        extras = ranked[:-2]
        for kind, cid in extras:
            if kind == "tri":
                to_remove_tri.append(cid)
            else:
                to_remove_quad.append(cid)

    applied = 0
    applied += remove_cells(mesh, "tri", to_remove_tri)
    applied += remove_cells(mesh, "quad", to_remove_quad)

    notes = f"Edges with >2 incidence fixed; removed {applied} cells." if applied else "No oversubscribed edges."
    return {"applied": applied, "waived": 0, "notes": notes}
