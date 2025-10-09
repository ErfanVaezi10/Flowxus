# -*- coding: utf-8 -*-
# Flowxus/solver/ops/style.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 9/17/2025 (Updated: 10/09/2025)

Purpose
-------
Provide a single place to enforce consistent Matplotlib styling across all plots,
and expose a lightweight `figure()` context manager that applies the style and
returns a ready-to-use (fig, ax) pair with tight layout.

Main Tasks
----------
    1. Define and apply base rcParams (DPI, grid, fonts, linewidths) via `apply_base_style()`.
    2. Offer `figure(width, height)` to create styled figures with safe tight_layout.

Notes
-----
- `figure()` calls `apply_base_style()` every time to avoid dependence on import order.
- Tight layout is attempted in `finally`; any exceptions are swallowed (best-effort).
"""

from __future__ import absolute_import
import contextlib
import matplotlib.pyplot as plt

DEFAULT_DPI = 120


def apply_base_style():
    """
    Apply project-wide Matplotlib rcParams.

    Sets sensible defaults for DPI, grid appearance, label sizes, and line widths
    to keep all visualizations uniform across modules.
    """
    plt.rcParams.update({
        "figure.dpi": DEFAULT_DPI,
        "savefig.dpi": DEFAULT_DPI,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 9,
        "lines.linewidth": 1.6,
        "axes.linewidth": 0.8,
    })


@contextlib.contextmanager
def figure(width=6.0, height=4.0):
    """
    Context manager yielding a styled Matplotlib `(fig, ax)`.

    Args
    ----
    width : float, optional
        Figure width in inches (default: 6.0).
    height : float, optional
        Figure height in inches (default: 4.0).

    Yields
    ------
    (matplotlib.figure.Figure, matplotlib.axes.Axes)
        Newly created figure and axes with Flowxus base style applied.

    Notes
    -----
    - `tight_layout()` is called on exit; errors are ignored by design.
    """
    apply_base_style()
    fig, ax = plt.subplots(figsize=(float(width), float(height)))
    try:
        yield fig, ax
    finally:
        try:
            fig.tight_layout()
        except Exception:
            pass
