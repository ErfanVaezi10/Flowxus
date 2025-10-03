# -*- coding: utf-8 -*-
# Flowxus/post/plot_stats.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
Simple matplotlib-based visualizations for mesh statistics. Utilities here plot:
element-type distribution, node-valence histogram, triangle minimum-angle histogram,
triangle aspect-ratio histogram, quadrilateral skewness histogram, and mean cell-size
vs. distance-to-wall curves.

Main Tasks:
-----------
    1) Provide a safe pyplot getter that works headless (sets Agg if no DISPLAY).
    2) Accept either a MeshData object or a mesh path; auto-load when needed.
    3) Implement plotting helpers for core mesh quality metrics:
       - Element type bars (tris vs quads).
       - Node valence histogram.
       - Triangle min-angle histogram (+ reference line at 20°).
       - Triangle aspect-ratio histogram (optional x-limits).
       - Quad skewness histogram (+ reference line at 0.85).
       - Cell size h versus distance-to-wall (mean with p50–p95 band).

Notes:
------
- No hard dependency on matplotlib until a plotting function is called.
- Uses `stats.data` modules for reading and metric computations.
- All calculations are performed in the XY plane (z ignored).
"""

import os
import numpy as np
from typing import Optional, Tuple

from mesh.stats.data.reader import read, MeshData
from mesh.stats.data.topology import inventory, valence
from mesh.stats.data import sizefield as _sizefield  # module import avoids early symbol errors


# -----------------------
# Internal utilities
# -----------------------
def _get_pyplot():
    """
    Lazy-import matplotlib.pyplot and set non-interactive backend if needed.

    Returns
    -------
    module
        The `matplotlib.pyplot` module.

    Raises
    ------
    RuntimeError
        If matplotlib is unavailable.
    """
    try:
        import matplotlib
        if not os.environ.get("DISPLAY"):
            try:
                matplotlib.use("Agg")
            except Exception:
                pass
        import matplotlib.pyplot as plt
        return plt
    except Exception as e:
        raise RuntimeError("matplotlib required: {}".format(e))


def _ensure_mesh(maybe_path_or_mesh) -> MeshData:
    """
    Accept either `MeshData` or a filesystem path; return `MeshData`.

    Parameters
    ----------
    maybe_path_or_mesh : MeshData or str
        Mesh container or path to a mesh file.

    Returns
    -------
    MeshData
        Loaded or passed-through mesh container.
    """
    if isinstance(maybe_path_or_mesh, MeshData):
        return maybe_path_or_mesh
    return read(str(maybe_path_or_mesh))


def _tri_angles(points: np.ndarray, tris: Optional[np.ndarray]) -> np.ndarray:
    """
    Compute internal angles (deg) for each triangle: (A, B, C) per row.

    Parameters
    ----------
    points : np.ndarray
        (N,3) node coordinates.
    tris : np.ndarray or None
        (T,3) triangle connectivity or None.

    Returns
    -------
    np.ndarray
        (T,3) angles in degrees (empty array if no tris).
    """
    if tris is None or tris.size == 0:
        return np.zeros((0, 3), dtype=float)

    P0 = points[tris[:, 0], :2]
    P1 = points[tris[:, 1], :2]
    P2 = points[tris[:, 2], :2]

    def ang(a, b, c):
        ba = a - b
        bc = c - b
        nba = np.einsum("ij,ij->i", ba, ba)
        nbc = np.einsum("ij,ij->i", bc, bc)
        dot = np.einsum("ij,ij->i", ba, bc)
        cos = np.clip(dot / (np.sqrt(nba) * np.sqrt(nbc) + 1e-30), -1.0, 1.0)
        return np.degrees(np.arccos(cos))

    A = ang(P1, P0, P2)
    B = ang(P2, P1, P0)
    C = 180.0 - (A + B)
    return np.stack([A, B, C], axis=1)


def _tri_aspect(points: np.ndarray, tris: Optional[np.ndarray]) -> np.ndarray:
    """
    Triangle aspect ratio defined as (longest edge) / (altitude to that edge).

    Parameters
    ----------
    points : np.ndarray
        (N,3) node coordinates.
    tris : np.ndarray or None
        (T,3) triangle connectivity or None.

    Returns
    -------
    np.ndarray
        (T,) aspect ratios (0-length if no tris).
    """
    if tris is None or tris.size == 0:
        return np.zeros((0,), dtype=float)

    P0 = points[tris[:, 0], :2]
    P1 = points[tris[:, 1], :2]
    P2 = points[tris[:, 2], :2]

    e01 = np.linalg.norm(P1 - P0, axis=1)
    e12 = np.linalg.norm(P2 - P1, axis=1)
    e20 = np.linalg.norm(P0 - P2, axis=1)

    longest = np.maximum(e01, np.maximum(e12, e20))
    s = 0.5 * (e01 + e12 + e20)
    area = np.maximum(s * (s - e01) * (s - e12) * (s - e20), 0.0)
    area = np.sqrt(area)
    h = np.where(longest > 0, 2.0 * area / longest, 0.0)

    with np.errstate(divide="ignore", invalid="ignore"):
        ar = np.where(h > 0, longest / h, 0.0)

    return ar


def _quad_skewness(points: np.ndarray, quads: Optional[np.ndarray]) -> np.ndarray:
    """
    Quadrilateral skewness in [0,1]: max(|angle - 90°|)/90.

    Parameters
    ----------
    points : np.ndarray
        (N,3) node coordinates.
    quads : np.ndarray or None
        (Q,4) quad connectivity or None.

    Returns
    -------
    np.ndarray
        (Q,) skewness values (0-length if no quads).
    """
    if quads is None or quads.size == 0:
        return np.zeros((0,), dtype=float)

    P0 = points[quads[:, 0], :2]
    P1 = points[quads[:, 1], :2]
    P2 = points[quads[:, 2], :2]
    P3 = points[quads[:, 3], :2]

    def angle(u, v):
        dot = np.einsum("ij,ij->i", u, v)
        nu = np.linalg.norm(u, axis=1)
        nv = np.linalg.norm(v, axis=1)
        cos = np.clip(dot / (nu * nv + 1e-30), -1.0, 1.0)
        return np.degrees(np.arccos(cos))

    a0 = angle(P1 - P0, P3 - P0)
    a1 = angle(P2 - P1, P0 - P1)
    a2 = angle(P3 - P2, P1 - P2)
    a3 = angle(P0 - P3, P2 - P3)

    A = np.stack([a0, a1, a2, a3], axis=1)
    dev = np.abs(A - 90.0)
    max_dev = np.max(dev, axis=1)
    skew = np.clip(max_dev / 90.0, 0.0, 1.0)
    return skew


# -----------------------
# Public plotting API
# -----------------------
def plot_element_type_distribution(mesh_or_path, show=True, save_path: Optional[str] = None):
    """
    Bar chart of element counts: triangles vs quadrilaterals.

    Parameters
    ----------
    mesh_or_path : MeshData or str
        Mesh container or mesh file path.
    show : bool, optional
        If True, show the figure interactively.
    save_path : str or None, optional
        If provided, save the figure to this path.
    """
    plt = _get_pyplot()
    m = _ensure_mesh(mesh_or_path)
    inv = inventory(m)
    ntri = int(inv.get("n_tris", 0))
    nquad = int(inv.get("n_quads", 0))

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(["tris", "quads"], [ntri, nquad])
    ax.set_ylabel("count")
    ax.set_title("Element type distribution")

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_node_valence_hist(mesh_or_path, bins: int = 12, show=True, save_path: Optional[str] = None):
    """
    Histogram of node valence (number of incident elements per node).

    Parameters
    ----------
    mesh_or_path : MeshData or str
        Mesh container or mesh file path.
    bins : int, optional
        Number of histogram bins (unused here because we have discrete bars).
    show : bool, optional
        If True, show the figure interactively.
    save_path : str or None, optional
        If provided, save the figure to this path.
    """
    plt = _get_pyplot()
    m = _ensure_mesh(mesh_or_path)
    v = valence(m)

    hist = v.get("hist", {})
    degrees = sorted(int(k) for k in hist.keys())
    counts = [int(hist[d]) for d in degrees]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([str(d) for d in degrees], counts)
    ax.set_xlabel("valence")
    ax.set_ylabel("nodes")
    ax.set_title("Node valence histogram")

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_tri_min_angle_hist(mesh_or_path, bins: int = 36, show=True, save_path: Optional[str] = None):
    """
    Histogram of triangle minimum angles (degrees).

    Adds a dashed reference line at 20°.

    Parameters
    ----------
    mesh_or_path : MeshData or str
        Mesh container or mesh file path.
    bins : int, optional
        Number of histogram bins (default 36).
    show : bool, optional
        If True, show the figure interactively.
    save_path : str or None, optional
        If provided, save the figure to this path.
    """
    plt = _get_pyplot()
    m = _ensure_mesh(mesh_or_path)
    A = _tri_angles(m.points, m.tris)
    mins = A.min(axis=1) if A.size else np.zeros((0,), dtype=float)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(mins, bins=bins, density=False)
    ax.set_xlabel("min angle (deg)")
    ax.set_ylabel("triangles")
    ax.set_title("Triangle minimum angle")
    ax.axvline(20.0, linestyle="--")

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_tri_aspect_hist(
    mesh_or_path,
    bins: int = 36,
    show=True,
    save_path: Optional[str] = None,
    xlim: Optional[Tuple[float, float]] = None,
):
    """
    Histogram of triangle aspect ratios (longest edge / altitude).

    Parameters
    ----------
    mesh_or_path : MeshData or str
        Mesh container or mesh file path.
    bins : int, optional
        Number of histogram bins (default 36).
    show : bool, optional
        If True, show the figure interactively.
    save_path : str or None, optional
        If provided, save the figure to this path.
    xlim : tuple(float,float) or None, optional
        Optional x-limits for the histogram.
    """
    plt = _get_pyplot()
    m = _ensure_mesh(mesh_or_path)
    ar = _tri_aspect(m.points, m.tris)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(ar, bins=bins, density=False)
    ax.set_xlabel("aspect ratio (longest/height)")
    ax.set_ylabel("triangles")
    ax.set_title("Triangle aspect ratio")
    if xlim is not None:
        ax.set_xlim(xlim)

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_quad_skew_hist(mesh_or_path, bins: int = 36, show=True, save_path: Optional[str] = None):
    """
    Histogram of quadrilateral skewness (0=perfect, 1=worst).

    Adds a dashed reference line at 0.85.

    Parameters
    ----------
    mesh_or_path : MeshData or str
        Mesh container or mesh file path.
    bins : int, optional
        Number of histogram bins (default 36).
    show : bool, optional
        If True, show the figure interactively.
    save_path : str or None, optional
        If provided, save the figure to this path.
    """
    plt = _get_pyplot()
    m = _ensure_mesh(mesh_or_path)
    skew = _quad_skewness(m.points, m.quads)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(skew, bins=bins, density=False)
    ax.set_xlabel("skewness (0=perfect, 1=worst)")
    ax.set_ylabel("quads")
    ax.set_title("Quad skewness")
    ax.axvline(0.85, linestyle="--")

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_h_vs_distance(mesh_or_path, wall_name: str = "airfoil", show=True, save_path: Optional[str] = None):
    """
    Plot mean cell size h versus distance to a named wall, with p50–p95 band.

    Parameters
    ----------
    mesh_or_path : MeshData or str
        Mesh container or mesh file path.
    wall_name : str, optional
        Boundary name used as "wall" for distance computation (default "airfoil").
    show : bool, optional
        If True, show the figure interactively.
    save_path : str or None, optional
        If provided, save the figure to this path.
    """
    plt = _get_pyplot()
    m = _ensure_mesh(mesh_or_path)

    # Note: module-qualified call to avoid symbol resolution at import time
    res = _sizefield.h_vs_distance(m, wall_name=wall_name, nbins=30)
    if not res:
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        if save_path:
            fig.savefig(save_path, dpi=300, bbox_inches="tight")
        if show:
            plt.show()
        else:
            plt.close(fig)
        return

    edges = np.array(res["bin_edges"], dtype=float)
    stats = res["stats"]

    centers = 0.5 * (edges[:-1] + edges[1:])
    mean = np.array([s.get("mean", np.nan) for s in stats], dtype=float)
    p50 = np.array([s.get("p50", np.nan) for s in stats], dtype=float)
    p95 = np.array([s.get("p95", np.nan) for s in stats], dtype=float)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(centers, mean, label="mean h(d)")
    if np.isfinite(p50).any() and np.isfinite(p95).any():
        ax.fill_between(centers, p50, p95, alpha=0.2, label="p50–p95")
    ax.set_xlabel("distance to '{}'".format(wall_name))
    ax.set_ylabel("cell size h")
    ax.set_title("Mean cell size vs wall distance")
    ax.legend()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig)
