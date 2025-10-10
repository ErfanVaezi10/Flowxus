# -*- coding: utf-8 -*-
# Flowxus/geometry/ops/basic.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 7/15/2025 (Updated: 10/10/2025)

Purpose
-------
Foundational 2D polyline utilities for airfoil/curve preprocessing. Provide robust
checks for input shape, deduplicate consecutive points, locate LE/TE, compute chord,
normalize geometry to a standard frame, and compute cumulative arclength.

Main Tasks
----------
    1. Validate inputs as (N,2) arrays and sanitize with consecutive-duplicate removal.
    2. Extract leading/trailing edges, compute chord length, and normalize geometry.
    3. Provide cumulative arclength for open/closed polylines (S[0]=0, S[-1]=L).

Notes
-----
- Functions assume Cartesian coordinates (x, y) and do not re-order points.
- `normalize` uses LE as the translation anchor and chord (TE.x-LE.x) as scale.
"""

from typing import Optional
import numpy as np

__all__ = [
    "drop_consecutive_duplicates",
    "leading_edge",
    "trailing_edge",
    "chord_length",
    "normalize",
    "cumulative_arclength",
]


def _assert_xy(points: Optional[np.ndarray]) -> None:
    """
    Ensure `points` is a NumPy array of shape (N, 2).

    Raises
    ------
    ValueError
        If `points` is None or does not have shape (N, 2).
    """
    if points is None:
        raise ValueError("No geometry provided (points is None).")
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("Expected (N,2) float array for points, got shape {}.".format(points.shape))


def drop_consecutive_duplicates(pts: np.ndarray, tol: float = 0.0) -> np.ndarray:
    """
    Remove exact (or tolerance-close) consecutive duplicates.

    Useful to avoid zero-length segments that can break finite-difference
    operations or arclength accumulation.

    Args
    ----
    pts : np.ndarray
        Input polyline points, shape (N, 2).
    tol : float, optional
        Absolute tolerance for equality (`np.allclose` with rtol=0). Default: 0.0.

    Returns
    -------
    np.ndarray
        Filtered points retaining original order.

    Raises
    ------
    ValueError
        If `pts` is not an (N, 2) array.
    """
    if pts is None or pts.ndim != 2 or pts.shape[1] != 2:
        raise ValueError("Expected (N,2) float array for points.")
    if pts.shape[0] <= 1:
        return pts
    keep = [0]
    for i in range(1, pts.shape[0]):
        if not np.allclose(pts[i], pts[i - 1], atol=tol, rtol=0.0):
            keep.append(i)
    return pts[np.array(keep, dtype=int)]


def leading_edge(points: np.ndarray) -> np.ndarray:
    """
    Return the leading-edge (LE) point as the minimum-x vertex.

    Args
    ----
    points : np.ndarray
        Polyline points, shape (N, 2).

    Returns
    -------
    np.ndarray
        The LE point (shape (2,)).

    Raises
    ------
    ValueError
        If the input array is empty or malformed.
    """
    _assert_xy(points)
    if points.shape[0] == 0:
        raise ValueError("Empty array provided; no points to evaluate leading edge.")
    return points[int(np.argmin(points[:, 0]))]


def trailing_edge(points: np.ndarray) -> np.ndarray:
    """
    Return the trailing-edge (TE) point as the maximum-x vertex.

    Args
    ----
    points : np.ndarray
        Polyline points, shape (N, 2).

    Returns
    -------
    np.ndarray
        The TE point (shape (2,)).

    Raises
    ------
    ValueError
        If the input array is empty or malformed.
    """
    _assert_xy(points)
    if points.shape[0] == 0:
        raise ValueError("Empty array provided; no points to evaluate trailing edge.")
    return points[int(np.argmax(points[:, 0]))]


def chord_length(points: np.ndarray) -> float:
    """
    Compute the chord length as TE.x − LE.x.

    Args
    ----
    points : np.ndarray
        Polyline points, shape (N, 2).

    Returns
    -------
    float
        Chord length (non-negative for chord-aligned airfoils).
    """
    _assert_xy(points)
    le = leading_edge(points)
    te = trailing_edge(points)
    return float(te[0] - le[0])


def normalize(points: np.ndarray,
              translate_to_le: bool = True,
              scale_to_chord1: bool = True) -> np.ndarray:
    """
    Normalize a 2D airfoil polyline and return a new array.

    Steps
    -----
    (1) Translate so LE → (0, 0) if `translate_to_le` is True.
    (2) Scale so chord length → 1 if `scale_to_chord1` is True.

    Args
    ----
    points : np.ndarray
        Polyline points, shape (N, 2).
    translate_to_le : bool, optional
        If True, subtract the LE point so geometry is LE-anchored at the origin.
    scale_to_chord1 : bool, optional
        If True, divide coordinates by the chord length.

    Returns
    -------
    np.ndarray
        Normalized polyline points.

    Raises
    ------
    ValueError
        If chord length is non-positive or input is malformed.
    """
    _assert_xy(points)
    out = points.copy()
    if translate_to_le:
        out = out - leading_edge(out)
    if scale_to_chord1:
        chord = chord_length(out)
        if chord <= 0:
            raise ValueError("Invalid chord length (<=0). Check geometry alignment.")
        out = out / chord
    return out


def cumulative_arclength(points: np.ndarray) -> np.ndarray:
    """
    Compute cumulative arclength for open or closed polylines.

    Returns an array S with S[0] = 0 and S[-1] = total length.

    Args
    ----
    points : np.ndarray
        Polyline points, shape (N, 2).

    Returns
    -------
    np.ndarray
        Cumulative arclength array of shape (N,).

    Raises
    ------
    ValueError
        If input shape is invalid.
    """
    _assert_xy(points)
    seg = np.linalg.norm(points[1:] - points[:-1], axis=1)
    return np.concatenate(([0.0], np.cumsum(seg)))
