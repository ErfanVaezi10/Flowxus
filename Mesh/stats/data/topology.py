# -*- coding: utf-8 -*-
# Flowxus/mesh/stats/data/topology.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
Compute basic topological statistics of the mesh: global inventory of nodes/elements and
per-node valence distribution.

Main Tasks:
-----------
    1) `inventory`:
        - Count nodes, tris, quads, and total cells.
        - Report bounding box and its area.
        - List available physical markers (from cell_tags and line_tags).
    2) `valence`:
        - Count how many elements (tris/quads) are incident on each node.
        - Summarize valence distribution with min/max/mean/std and histogram.

Notes:
------
- Assumes planar meshes (bbox derived from XY extents).
- Histogram is returned as {valence: frequency}.
"""

import numpy as np
from .reader import MeshData


def inventory(m: MeshData) -> dict:
    """
    Build a global inventory of mesh size and markers.

    Parameters
    ----------
    m : MeshData
        Mesh container.

    Returns
    -------
    dict
        {
          "n_nodes": int,
          "n_tris": int,
          "n_quads": int,
          "n_cells": int,
          "bbox": {"xmin","xmax","ymin","ymax"},
          "area_bbox": float,
          "markers": [list of str]
        }
    """
    n_nodes = m.points.shape[0]
    n_tris = 0 if m.tris is None else m.tris.shape[0]
    n_quads = 0 if m.quads is None else m.quads.shape[0]
    n_cells = n_tris + n_quads

    xmin, xmax, ymin, ymax = m.bbox
    area = (xmax - xmin) * (ymax - ymin)

    markers = list(m.cell_tags.keys()) + list(m.line_tags.keys())

    return {
        "n_nodes": n_nodes,
        "n_tris": n_tris,
        "n_quads": n_quads,
        "n_cells": n_cells,
        "bbox": {"xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax},
        "area_bbox": area,
        "markers": markers,
    }


def valence(m: MeshData) -> dict:
    """
    Compute node valence distribution (cells incident per node).

    Parameters
    ----------
    m : MeshData
        Mesh container.

    Returns
    -------
    dict
        {
          "min": int,       # min valence
          "max": int,       # max valence
          "mean": float,    # mean valence
          "std": float,     # std deviation
          "hist": {valence: frequency}
        }
        Returns zeros and empty hist if no elements exist.
    """
    N = m.points.shape[0]
    counts = np.zeros(N, dtype=int)

    if m.tris is not None:
        for tri in m.tris:
            counts[tri] += 1

    if m.quads is not None:
        for q in m.quads:
            counts[q] += 1

    nonzero = counts[counts > 0]
    if nonzero.size == 0:
        return {"min": 0, "max": 0, "mean": 0.0, "std": 0.0, "hist": {}}

    unique, freq = np.unique(nonzero, return_counts=True)
    hist = {int(u): int(f) for u, f in zip(unique, freq)}

    return {
        "min": int(nonzero.min()),
        "max": int(nonzero.max()),
        "mean": float(nonzero.mean()),
        "std": float(nonzero.std()),
        "hist": hist,
    }
