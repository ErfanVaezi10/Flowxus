# -*- coding: utf-8 -*-
# Flowxus/geometry/plot.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 7/14/2025 (Updated: 8/24/2025)

Purpose:
--------
Unified plotting utilities for 2D geometry and far-field domains using matplotlib. Add an optional
QA helper `plot_sides(...)` to visualize suction/pressure segmentation and highlight LE/TE points
on the closed polyline. This aids quick validation of the metadata driving meshing/ML.
"""

from typing import Optional, Dict, List
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.axes import Axes


def plot_points(points: np.ndarray,
                *,
                name: str = "geometry",
                show: bool = True,
                save_path: Optional[str] = None,
                ax: Optional[Axes] = None) -> None:
    """
        Plot a 2D polyline.

        Parameters
        ----------
        points : np.ndarray
            (N,2) array of (x,y) points.
        name : str
            Title label for the figure.
        show : bool
            If True and we created the figure, display it.
        save_path : Optional[str]
            If given, save the figure to this path.
        ax : Optional[matplotlib.axes.Axes]
            Existing Axes to draw on; if None, a figure is created.
        """

    if points is None or points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("Expected (N,2) float array for points.")
    created_fig = False
    if ax is None:
        plt.figure(figsize=(8, 3))
        ax = plt.gca()
        created_fig = True
    ax.plot(points[:, 0], points[:, 1], lw=1.5)
    ax.set_aspect('equal', adjustable='box')
    ax.set_title("Geometry: {}".format(name))
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.grid(True)
    if save_path:
        ax.figure.savefig(save_path, dpi=300)
    if show and created_fig:
        plt.show()
    elif created_fig:
        plt.close(ax.figure)


def plot_domain(
    airfoil_pts: np.ndarray,
    bbox: Dict[str, float],
    physical_tags: Dict[str, str],
    *,
    show: bool = True,
    save_path: Optional[str] = None,
    ax=None
) -> None:
    """
       Plot an airfoil with its rectangular far-field domain and boundary labels.

       Parameters
       ----------
       airfoil_pts : np.ndarray
           (N,2) array of the airfoil polyline (open or closed).
       bbox : Dict[str, float]
           Rect bounds with keys {"xmin","xmax","ymin","ymax"}.
       physical_tags : Dict[str, str]
           Names for {"inlet","outlet","top","bottom"}.
       show, save_path, ax
           Same semantics as `plot_points`.
       """

    if airfoil_pts is None or airfoil_pts.ndim != 2 or airfoil_pts.shape[1] != 2:
        raise ValueError("Expected (N,2) array for airfoil_pts.")
    created_fig = False
    if ax is None:
        plt.figure(figsize=(8, 4))
        ax = plt.gca()
        created_fig = True

    ax.plot(airfoil_pts[:, 0], airfoil_pts[:, 1], 'k-', lw=1.5, label="Airfoil")

    corners = np.array([
        [bbox["xmin"], bbox["ymin"]],
        [bbox["xmax"], bbox["ymin"]],
        [bbox["xmax"], bbox["ymax"]],
        [bbox["xmin"], bbox["ymax"]],
        [bbox["xmin"], bbox["ymin"]],
    ])
    ax.plot(corners[:, 0], corners[:, 1], 'b--', lw=1.2, label="Farfield")

    label_style = dict(color='blue', fontsize=10, fontweight='bold')
    cx = 0.5 * (bbox["xmin"] + bbox["xmax"])
    cy = 0.5 * (bbox["ymin"] + bbox["ymax"])
    ax.text(bbox["xmin"] - 0.5, cy, physical_tags.get('inlet', 'inlet'), **label_style)
    ax.text(bbox["xmax"] + 0.2, cy, physical_tags.get('outlet', 'outlet'), **label_style)
    ax.text(cx - 1.0, bbox["ymax"] + 0.2, physical_tags.get('top', 'top'), **label_style)
    ax.text(cx - 1.0, bbox["ymin"] - 0.5, physical_tags.get('bottom', 'bottom'), **label_style)

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("Airfoil and Farfield with Boundary Tags")
    ax.grid(True)
    ax.legend()

    if save_path:
        ax.figure.savefig(save_path, dpi=300)
    if show and created_fig:
        plt.show()
    elif created_fig:
        plt.close(ax.figure)


def plot_sides(
    points_closed: np.ndarray,
    *,
    ranges: Dict[str, List[int]],
    le_idx: int,
    te_idx: int,
    show: bool = True,
    save_path: Optional[str] = None,
    ax=None,
) -> None:
    """
       QA helper: visualize pressure/suction segmentation and mark LE/TE.

       Parameters
       ----------
       points_closed : np.ndarray
           Closed (N,2) array; first point must equal last.
       ranges : Dict[str, List[int]]
           1-based inclusive index ranges on the CLOSED array:
           - ranges["pressure"] = [i0, i1]
           - ranges["suction"]  = [i0, i1]
           Wrapping across the end is supported.
       le_idx, te_idx : int
           1-based indices of LE and TE on the CLOSED array.
       show, save_path, ax
           Same semantics as `plot_points`.
       """
    if points_closed is None or points_closed.ndim != 2 or points_closed.shape[1] != 2:
        raise ValueError("Expected (N,2) array for points_closed.")
    P = points_closed[:-1]
    N = P.shape[0]

    created_fig = False
    if ax is None:
        plt.figure(figsize=(8, 3))
        ax = plt.gca()
        created_fig = True

    # Full loop (light gray)
    ax.plot(P[:, 0], P[:, 1], color=(0.6, 0.6, 0.6), lw=1.0, label="loop")

    def idx_span(i0_1b, i1_1b):
        i0, i1 = int(i0_1b) - 1, int(i1_1b) - 1
        if i0 <= i1:
            return list(range(i0, i1 + 1))
        else:
            return list(range(i0, N)) + list(range(0, i1 + 1))

    pr = ranges.get('pressure', None)
    su = ranges.get('suction', None)
    if pr:
        pr_idx = idx_span(pr[0], pr[1])
        ax.plot(P[pr_idx, 0], P[pr_idx, 1], 'b-', lw=1.8, label='pressure')
    if su:
        su_idx = idx_span(su[0], su[1])
        ax.plot(P[su_idx, 0], P[su_idx, 1], 'r-', lw=1.8, label='suction')

    # Mark LE/TE
    le_i = int(le_idx) - 1
    te_i = int(te_idx) - 1
    ax.plot(P[le_i, 0], P[le_i, 1], 'go', ms=6, label='LE')
    ax.plot(P[te_i, 0], P[te_i, 1], 'mo', ms=6, label='TE')

    ax.set_aspect('equal', adjustable='box')
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_title('Pressure/Suction segmentation + LE/TE markers')
    ax.grid(True)
    ax.legend()

    if save_path:
        ax.figure.savefig(save_path, dpi=300)
    if show and created_fig:
        plt.show()
    elif created_fig:
        plt.close(ax.figure)
