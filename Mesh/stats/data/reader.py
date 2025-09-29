# -*- coding: utf-8 -*-
# Flowxus/mesh/stats/data/reader.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
Provide a lightweight `MeshData` container class and a `read` function to load mesh
geometry/connectivity from files using `meshio`. The loader extracts points, tris,
quads, bounding box, and Gmsh physical tags for cells and lines.

Main Tasks:
-----------
    1) Define `MeshData` with geometry (points, tris, quads), tags, and bbox.
    2) Read mesh file with `meshio.read`.
    3) Parse connectivity: triangles, quads, lines.
    4) Build bounding box from node coordinates.
    5) Map Gmsh "physical" IDs → human-readable names via `field_data`.
    6) Extract per-physical group indices for triangles, quads, and lines.

Notes:
------
- Supports both meshio ≥5 (`cell_data_dict`) and meshio <5 (fallback to `cell_data`).
- Tagging relies on Gmsh-style "gmsh:physical" data and `field_data` mappings.
"""

import numpy as np
from typing import Dict, Optional, Tuple


class MeshData:
    """
    Lightweight container for 2D mesh data and tags.

    Attributes
    ----------
    points : np.ndarray
        (N,3) array of node coordinates.
    tris : np.ndarray or None
        (T,3) triangle connectivity, or None if absent.
    quads : np.ndarray or None
        (Q,4) quad connectivity, or None if absent.
    cell_tags : dict
        { group_name: {"triangle": idx_array, "quad": idx_array, ...}, ... }
        Mapping physical names → element indices by type.
    line_tags : dict
        { group_name: idx_array } for boundary line segments.
    bbox : tuple of float
        (xmin, xmax, ymin, ymax) domain bounding box.
    """

    def __init__(
        self,
        points: np.ndarray,
        tris: Optional[np.ndarray],
        quads: Optional[np.ndarray],
        cell_tags: Dict[str, Dict[str, np.ndarray]],
        line_tags: Dict[str, np.ndarray],
        bbox: Tuple[float, float, float, float],
    ):
        self.points = points
        self.tris = tris
        self.quads = quads
        self.cell_tags = cell_tags
        self.line_tags = line_tags
        self.bbox = bbox


def read(path: str) -> MeshData:
    """
    Load a mesh file into a `MeshData` container.

    Steps
    -----
    1) Read mesh with `meshio.read(path)`.
    2) Extract connectivity arrays (tris, quads, lines).
    3) Compute bounding box from all points.
    4) Map "gmsh:physical" IDs → names from `field_data`.
    5) Collect indices of elements per physical group.

    Parameters
    ----------
    path : str
        Path to the mesh file (e.g., `.msh` from Gmsh).

    Returns
    -------
    MeshData
        Container with geometry, connectivity, tags, and bbox.
    """
    import meshio

    m = meshio.read(path)
    pts = np.asarray(m.points, dtype=float)

    tris = None
    quads = None
    lines = None

    # Connectivity by type
    for cb in m.cells:
        t = getattr(cb, "type", None)
        if t == "triangle":
            tris = np.asarray(cb.data, dtype=int)
        elif t in ("quad", "quadrilateral"):
            quads = np.asarray(cb.data, dtype=int)
        elif t == "line":
            lines = np.asarray(cb.data, dtype=int)

    # Bounding box
    xmin = float(np.min(pts[:, 0]))
    xmax = float(np.max(pts[:, 0]))
    ymin = float(np.min(pts[:, 1]))
    ymax = float(np.max(pts[:, 1]))
    bbox = (xmin, xmax, ymin, ymax)

    # Physical ID → name mapping from field_data
    field_data = getattr(m, "field_data", {}) or {}
    id_to_name = {}
    for name, val in field_data.items():
        if isinstance(val, (list, tuple, np.ndarray)) and len(val) >= 1:
            pid = int(val[0])
            id_to_name[pid] = name

    cell_tags: Dict[str, Dict[str, np.ndarray]] = {}
    line_tags: Dict[str, np.ndarray] = {}

    # --- meshio version handling ---
    cd = getattr(m, "cell_data_dict", None)
    if cd is None:
        # meshio < 5 fallback
        cell_data = getattr(m, "cell_data", [])
        phys_by_type = {}
        for arr, cb in zip(cell_data, m.cells):
            t = getattr(cb, "type", None)
            if isinstance(arr, dict) and "gmsh:physical" in arr:
                phys_by_type[t] = np.asarray(arr["gmsh:physical"], dtype=int)

        if tris is not None and "triangle" in phys_by_type:
            ids = phys_by_type["triangle"]
            for pid in np.unique(ids):
                name = id_to_name.get(int(pid))
                if name:
                    cell_tags.setdefault(name, {})
                    cell_tags[name]["triangle"] = np.where(ids == pid)[0]

        if quads is not None and ("quad" in phys_by_type or "quadrilateral" in phys_by_type):
            key = "quad" if "quad" in phys_by_type else "quadrilateral"
            ids = phys_by_type[key]
            for pid in np.unique(ids):
                name = id_to_name.get(int(pid))
                if name:
                    cell_tags.setdefault(name, {})
                    cell_tags[name]["quad"] = np.where(ids == pid)[0]

        if lines is not None and "line" in phys_by_type:
            ids = phys_by_type["line"]
            for pid in np.unique(ids):
                name = id_to_name.get(int(pid))
                if name:
                    line_tags[name] = np.where(ids == pid)[0]

    else:
        # meshio ≥ 5 path
        phys = cd.get("gmsh:physical", {})

        if tris is not None and "triangle" in phys:
            ids = np.asarray(phys["triangle"], dtype=int)
            for pid in np.unique(ids):
                name = id_to_name.get(int(pid))
                if name:
                    cell_tags.setdefault(name, {})
                    cell_tags[name]["triangle"] = np.where(ids == pid)[0]

        if quads is not None:
            key = "quad" if "quad" in phys else ("quadrilateral" if "quadrilateral" in phys else None)
            if key is not None:
                ids = np.asarray(phys[key], dtype=int)
                for pid in np.unique(ids):
                    name = id_to_name.get(int(pid))
                    if name:
                        cell_tags.setdefault(name, {})
                        cell_tags[name]["quad"] = np.where(ids == pid)[0]

        if lines is not None and "line" in phys:
            ids = np.asarray(phys["line"], dtype=int)
            for pid in np.unique(ids):
                name = id_to_name.get(int(pid))
                if name:
                    line_tags[name] = np.where(ids == pid)[0]

    return MeshData(
        points=pts,
        tris=tris,
        quads=quads,
        cell_tags=cell_tags,
        line_tags=line_tags,
        bbox=bbox,
    )
