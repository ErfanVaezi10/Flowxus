# -*- coding: utf-8 -*-
# Flowxus/solver/ops/history.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 9/15/2025 (Updated: 10/09/2025)

Purpose
-------
Plot SU2 residual histories from `history.*` files. Reads normalized headers,
separates Navier–Stokes vs. turbulence residual families, converts log10-like
series to linear magnitudes when needed, and renders log-scale residual plots
with a consistent project style.

Main Tasks
----------
    1. Read and normalize SU2 history (csv/dat[.gz]) and extract iteration axis.
    2. Split residual columns into NS vs. turbulence via `split_residual_headers`.
    3. Heuristically convert log10 residuals to linear magnitudes for plotting.
    4. Produce quick-look PNG-ready figures for NS and turbulence residuals.

Notes
-----
- Uses `ops.style.figure()` as a context manager to create (fig, ax).
- If ITER is absent, iteration index falls back to 1..N.
- Heuristic `_as_linear_residual` treats mostly-nonpositive sequences as log10.
"""

from __future__ import absolute_import
from typing import Optional, List, Dict
import os
import math
from ..interface.history import read_history
from .style import figure
from .utils import split_residual_headers


def _as_linear_residual(y):
    """
    Convert a residual series to linear scale if it appears to be log10 values.

    Heuristic: if at least half of the finite points are <= 0, assume log10 and
    return 10**y (clamped to avoid overflow). Ensures strictly positive outputs
    for log-scale plotting.

    Args
    ----
    y : Sequence[float]
        Residual series as parsed from history.

    Returns
    -------
    List[float]
        Linear-scale residual magnitudes (>0).
    """
    if not y:
        return y
    n = len(y)
    n_nonpos = sum(1 for v in y if v <= 0.0 and math.isfinite(v))
    # Heuristic: if a majority are <= 0 and not too extreme, assume log10.
    if n_nonpos >= max(1, n // 2):
        # Clamp exponent to a sane range to avoid overflow.
        out = [10.0 ** max(-99.0, min(99.0, float(v))) if math.isfinite(v) else float("nan") for v in y]
    else:
        out = [float(v) for v in y]
    # Ensure strictly positive for log scale.
    eps = 1e-16
    return [max(eps, v) for v in out]


def _extract_columns(headers: List[str], rows: List[List[float]], cols: List[str]) -> Dict[str, List[float]]:
    """
    Gather selected columns from parsed history rows.

    Args
    ----
    headers : List[str]
        Canonicalized header names.
    rows : List[List[float]]
        Numeric data rows, each aligned to `headers`.
    cols : List[str]
        Subset of header names to extract.

    Returns
    -------
    Dict[str, List[float]]
        Mapping column name → series values.
    """
    idx = {h: i for i, h in enumerate(headers)}
    out: Dict[str, List[float]] = {}
    for c in cols:
        if c in idx:
            out[c] = [r[idx[c]] for r in rows]
    return out


def _iters(headers: List[str], rows: List[List[float]]) -> List[float]:
    """
    Extract iteration counter series if present; otherwise 1..N fallback.
    """
    idx = {h: i for i, h in enumerate(headers)}
    k = "ITER" if "ITER" in idx else None
    if k is None:
        # Fallback to enumerated iteration index (1..N)
        return list(range(1, len(rows) + 1))
    return [r[idx[k]] for r in rows]


def plot_ns_residuals(workdir: str, filename: str = "history.csv", limit: Optional[int] = 2000):
    """
    Plot Navier–Stokes residuals vs. iteration.

    Targets canonical NS keys among: RES_RHO, RES_RHO_U, RES_RHO_V, RES_RHO_W, RES_RHO_E.
    Handles empty/missing data gracefully.

    Args
    ----
    workdir : str
        Directory containing the SU2 history file.
    filename : str, optional
        History filename to read (default: "history.csv").
    limit : Optional[int], optional
        Max rows to parse (streamed). Default: 2000.

    Returns
    -------
    (matplotlib.figure.Figure, matplotlib.axes.Axes)
        Figure and axes with log-scale residual plot.
    """
    path = os.path.join(workdir, filename)
    headers, rows = read_history(path, limit=limit)
    if not rows:
        with figure() as (fig, ax):
            ax.text(0.5, 0.5, "No history data", ha="center", va="center")
            ax.set_axis_off()
            return fig, ax

    ns, _ = split_residual_headers(headers)
    its = _iters(headers, rows)
    series = _extract_columns(headers, rows, ns)

    with figure() as (fig, ax):
        for name in ns:
            y = series.get(name)
            if y:
                y_lin = _as_linear_residual(y)
                ax.plot(its, y_lin, label=name)
        ax.set_yscale("log")
        ax.set_xlabel("Iteration")
        ax.set_ylabel("Residual")
        ax.set_title("NS residuals")
        ax.legend()
        return fig, ax


def plot_turb_residuals(workdir: str, filename: str = "history.csv", limit: Optional[int] = 2000):
    """
    Plot turbulence residuals vs. iteration.

    Selects any `RES_*` headers not in the NS set (e.g., turbulence model variables).
    Handles empty data or absence of turbulence residuals gracefully.

    Args
    ----
    workdir : str
        Directory containing the SU2 history file.
    filename : str, optional
        History filename to read (default: "history.csv").
    limit : Optional[int], optional
        Max rows to parse (streamed). Default: 2000.

    Returns
    -------
    (matplotlib.figure.Figure, matplotlib.axes.Axes)
        Figure and axes with log-scale residual plot.
    """
    path = os.path.join(workdir, filename)
    headers, rows = read_history(path, limit=limit)
    if not rows:
        with figure() as (fig, ax):
            ax.text(0.5, 0.5, "No history data", ha="center", va="center")
            ax.set_axis_off()
            return fig, ax

    _, turb = split_residual_headers(headers)
    its = _iters(headers, rows)
    series = _extract_columns(headers, rows, turb)

    with figure() as (fig, ax):
        if not turb:
            ax.text(0.5, 0.5, "No turbulence residuals detected", ha="center", va="center")
            ax.set_axis_off()
            return fig, ax
        nplotted = 0
        for name in turb:
            y = series.get(name)
            if y:
                y_lin = _as_linear_residual(y)
                ax.plot(its, y_lin, label=name)
                nplotted += 1
        ax.set_yscale("log")
        ax.set_xlabel("Iteration")
        ax.set_ylabel("Residual")
        ax.set_title("Turbulence residuals")
        if nplotted:
            ax.legend()
        return fig, ax


def plot_all_residuals(workdir: str, filename: str = "history.csv", limit: Optional[int] = 2000):
    """
    Convenience: generate both NS and turbulence residual plots.

    Returns
    -------
    ((Figure, Axes), (Figure, Axes))
        Tuple of (fig_ns, ax_ns), (fig_turb, ax_turb).
    """
    return plot_ns_residuals(workdir, filename, limit), plot_turb_residuals(workdir, filename, limit)
