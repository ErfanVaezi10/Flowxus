# -*- coding: utf-8 -*-
# Flowxus/mesh/repair/ops.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
Atomic mesh edit operations and a minimal mutable Mesh wrapper suitable for
post-validation repairs (remove/reorient) and optional re-export.

Main Tasks:
-----------
   - Provide a lightweight `Mesh` dataclass (points, tris/quads, tags, dim).
   - Construct `Mesh` from a reader object; optionally write with meshio.
   - Edit ops: batch remove cells and flip local orientation (CW↔CCW).

Notes:
------
   - Scope: 2D surface meshes (XY used; Z ignored if present).
   - Idempotent ops: safe on empty selections; defensive on None arrays.
   - meshio is an optional dependency; writing is skipped if unavailable.
"""

from typing import Dict, Optional, List
from dataclasses import dataclass
import numpy as np
try:
    import meshio  # optional, for writing
    _HAS_MESHIO = True
except Exception:
    _HAS_MESHIO = False


@dataclass
class Mesh:
    """
    Mutable mesh container for repair: points, tris/quads, tags, and dimensionality.
    """
    path: str
    points: np.ndarray                 # (N,2) or (N,3); we use XY
    tris: Optional[np.ndarray]         # (T,3) or None
    quads: Optional[np.ndarray]        # (Q,4) or None
    cell_tags: Dict[str, np.ndarray]   # name -> np.ndarray of cell ids (unified not guaranteed)
    line_tags: Dict[str, np.ndarray]   # name -> np.ndarray
    # simple bookkeeping
    dim: int                           # 2 or 3


def mesh_from_reader(R, path: str) -> Mesh:
    """
    Build a mutable Mesh from a reader object (numpy arrays, tags copied verbatim).
    """
    pts = np.asarray(R.points, dtype=float)
    dim = pts.shape[1]
    tris = np.asarray(R.tris, dtype=np.int64) if getattr(R, "tris", None) is not None and len(R.tris) else None
    quads = np.asarray(R.quads, dtype=np.int64) if getattr(R, "quads", None) is not None and len(R.quads) else None
    cell_tags = dict(getattr(R, "cell_tags", {}) or {})
    line_tags = dict(getattr(R, "line_tags", {}) or {})
    return Mesh(path=path, points=pts, tris=tris, quads=quads, cell_tags=cell_tags, line_tags=line_tags, dim=dim)


def write_mesh_safe(mesh: Mesh, out_path: str) -> str:
    """
    Write triangles/quads with meshio (XY→XYZ if needed); raises if meshio is missing.
    """
    if not _HAS_MESHIO:
        raise RuntimeError("meshio not installed; cannot write repaired mesh. Use dry_run=True or install meshio.")
    cells = []
    if mesh.tris is not None and len(mesh.tris):
        cells.append(("triangle", mesh.tris.astype(np.int64)))
    if mesh.quads is not None and len(mesh.quads):
        cells.append(("quad", mesh.quads.astype(np.int64)))
    pts = mesh.points
    if pts.shape[1] == 2:
        pts3 = np.zeros((pts.shape[0], 3), dtype=float)
        pts3[:, :2] = pts
    else:
        pts3 = pts
    # field_data writing is optional; we skip preserving tags in MVP write
    meshio.write(out_path, meshio.Mesh(points=pts3, cells=cells))
    return out_path


# ---------- Invariants ----------
_EPS_AREA = 1e-14


def _tri_area_xy(P: np.ndarray) -> float:
    """
    Signed triangle area in XY (CCW > 0).
    """
    return 0.5 * float((P[1,0]-P[0,0])*(P[2,1]-P[0,1]) - (P[1,1]-P[0,1])*(P[2,0]-P[0,0]))


def _quad_area_xy(P: np.ndarray) -> float:
    """
    Signed quad polygon area in XY via shoelace (CCW > 0).
    """
    return 0.5 * float(
        P[0,0]*P[1,1]-P[0,1]*P[1,0] +
        P[1,0]*P[2,1]-P[1,1]*P[2,0] +
        P[2,0]*P[3,1]-P[2,1]*P[3,0] +
        P[3,0]*P[0,1]-P[3,1]*P[0,0]
    )


# ---------- Edit ops (idempotent & defensive) ----------
def remove_cells(mesh: Mesh, kind: str, idxs: List[int]) -> int:
    """
    Remove a batch of 'tri' or 'quad' cells by local indices; returns count removed.
    """
    if not idxs:
        return 0
    idxs = sorted(set(int(i) for i in idxs), reverse=True)
    if kind == "tri":
        if mesh.tris is None: return 0
        arr = mesh.tris
        mask = np.ones(len(arr), dtype=bool)
        mask[idxs] = False
        mesh.tris = arr[mask] if mask.any() else np.empty((0,3), dtype=np.int64)
        return int(len(idxs))
    elif kind == "quad":
        if mesh.quads is None: return 0
        arr = mesh.quads
        mask = np.ones(len(arr), dtype=bool)
        mask[idxs] = False
        mesh.quads = arr[mask] if mask.any() else np.empty((0,4), dtype=np.int64)
        return int(len(idxs))
    else:
        raise ValueError("kind must be 'tri' or 'quad'")


def reorient_cells(mesh: Mesh, kind: str, idxs: List[int]) -> int:
    """
    Flip local node order for 'tri'/'quad' cells (CW↔CCW); returns count changed.
    """
    if not idxs:
        return 0
    if kind == "tri":
        if mesh.tris is None: return 0
        A = mesh.tris
        for i in idxs:
            A[i, :] = A[i, ::-1]
        return len(idxs)
    elif kind == "quad":
        if mesh.quads is None: return 0
        A = mesh.quads
        for i in idxs:
            A[i, :] = A[i, ::-1]
        return len(idxs)
    else:
        raise ValueError("kind must be 'tri' or 'quad'")
