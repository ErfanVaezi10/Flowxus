# -*- coding: utf-8 -*-
# Flowxus/post/plot_mesh.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose
-------
Quick visualization utilities for 2D meshes using matplotlib and meshio.

Main Tasks
----------
    1) Read `.msh` meshes (MSH2/MSH4) safely via meshio with file checks.
    2) Plot mesh nodes (`plot_msh_2d_nodes`) as a scatter for density overview.
    3) Plot mesh elements (`plot_msh_2d_elements`) as wireframes (tri/quad),
       with optional downsampling for very large meshes.
"""

import os


def _safe_read_mesh(filename):
    """
    Safely read a mesh file using meshio.

    Parameters
    ----------
    filename : str
        Path to the `.msh` file (MSH2 or MSH4).

    Returns
    -------
    meshio.Mesh
        Mesh object containing points, cells, and field data.

    Raises
    ------
    ImportError
        If meshio is not installed.
    ValueError
        If the file does not exist or looks empty/invalid.
    """
    try:
        import meshio  # lazy import
    except ImportError:
        raise ImportError("meshio is required for plotting. Install via: pip install meshio")

    if not os.path.exists(filename) or os.path.getsize(filename) < 200:
        raise ValueError("Mesh file '{}' looks empty or invalid; cannot plot.".format(filename))
    return meshio.read(filename)


def _get_pyplot():
    """
    Import matplotlib.pyplot with a headless-safe backend if needed.

    Returns
    -------
    module
        The matplotlib.pyplot module.

    Raises
    ------
    RuntimeError
        If matplotlib cannot be imported.
    """
    try:
        import matplotlib
        # Choose Agg when DISPLAY is not set to avoid GUI backend errors in headless/CI.
        if not os.environ.get("DISPLAY"):
            try:
                matplotlib.use("Agg")  # must be set before importing pyplot
            except Exception:
                pass
        import matplotlib.pyplot as plt
        return plt
    except Exception as e:
        raise RuntimeError("matplotlib is required for plotting: {}".format(e))


def plot_msh_2d_nodes(filename, show=True, save_path=None, *, s=2, alpha=0.6):
    """
    Quick 2D scatter plot of mesh nodes from a .msh file.

    Parameters
    ----------
    filename : str
        Path to .msh file (MSH2 or MSH4).
    show : bool, optional
        Whether to display the figure (ignored if running in a non-GUI backend).
        Default True.
    save_path : str, optional
        If given, save the figure (PNG) to this path.
    s : float, optional
        Scatter marker size. Default 2.
    alpha : float, optional
        Scatter marker transparency. Default 0.6.
    """
    plt = _get_pyplot()
    mesh = _safe_read_mesh(filename)
    points = mesh.points

    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111)
    ax.scatter(points[:, 0], points[:, 1], s=s, alpha=alpha)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_title("Mesh Nodes")

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        print("Mesh plot saved to:", save_path)

    backend = plt.get_backend().lower()
    if show and not backend.startswith("agg"):
        plt.show()
    else:
        plt.close(fig)


def plot_msh_2d_elements(
    filename,
    show=True,
    save_path=None,
    *,
    linewidth=0.3,
    alpha=1.0,
    max_elements=None,
):
    """
    Quick 2D plot of mesh elements (triangles/quads) as wireframes.

    Parameters
    ----------
    filename : str
        Path to .msh file (MSH2 or MSH4).
    show : bool, optional
        Whether to display the figure (ignored if running in a non-GUI backend).
        Default True.
    save_path : str, optional
        If given, save the figure (PNG) to this path.
    linewidth : float, optional
        Line width for element edges. Default 0.3.
    alpha : float, optional
        Line transparency. Default 1.0.
    max_elements : int, optional
        If provided, randomly down-sample to this number of elements to keep
        plots responsive for very large meshes.

    Raises
    ------
    ValueError
        If the mesh contains no triangle or quad elements.
    """
    import numpy as np
    from matplotlib.collections import LineCollection

    plt = _get_pyplot()
    mesh = _safe_read_mesh(filename)
    points = mesh.points

    tris = None
    quads = None
    for cell_block in mesh.cells:
        ctype = getattr(cell_block, "type", None)
        if ctype == "triangle":
            data = cell_block.data
            tris = data if tris is None else data
        elif ctype in ("quad", "quadrilateral"):
            data = cell_block.data
            quads = data if quads is None else data

    if tris is None and quads is None:
        raise ValueError("No triangle or quad elements found in the mesh.")

    # Optional downsampling to keep plots responsive
    rng = np.random.RandomState(0)
    if max_elements is not None:
        if tris is not None and len(tris) > max_elements:
            idx = rng.choice(len(tris), size=max_elements, replace=False)
            tris = tris[idx]
        if quads is not None and len(quads) > max_elements:
            idx = rng.choice(len(quads), size=max_elements, replace=False)
            quads = quads[idx]

    # Build edge segments for a LineCollection (faster than per-polygon fill)
    segs = []

    if tris is not None:
        a = points[tris[:, 0]]
        b = points[tris[:, 1]]
        c = points[tris[:, 2]]
        segs.extend(np.stack([a, b], axis=1))
        segs.extend(np.stack([b, c], axis=1))
        segs.extend(np.stack([c, a], axis=1))

    if quads is not None:
        a = points[quads[:, 0]]
        b = points[quads[:, 1]]
        c = points[quads[:, 2]]
        d = points[quads[:, 3]]
        segs.extend(np.stack([a, b], axis=1))
        segs.extend(np.stack([b, c], axis=1))
        segs.extend(np.stack([c, d], axis=1))
        segs.extend(np.stack([d, a], axis=1))

    segs = np.asarray(segs)  # (Nseg, 2, 3) -> we use x,y only

    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111)

    lc = LineCollection(segs[:, :, :2], colors="k", linewidths=linewidth, alpha=alpha)
    ax.add_collection(lc)
    ax.autoscale()
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_title("Mesh Elements (tri/quad)")

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        print("Mesh plot saved to:", save_path)

    backend = plt.get_backend().lower()
    if show and not backend.startswith("agg"):
        plt.show()
    else:
        plt.close(fig)
