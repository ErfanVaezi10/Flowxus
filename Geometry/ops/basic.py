# -*- coding: utf-8 -*-
# Flowxus/geometry/ops/basic.py


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
    if points is None:
        raise ValueError("No geometry provided (points is None).")
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("Expected (N,2) float array for points, got shape {}.".format(points.shape))

def drop_consecutive_duplicates(pts: np.ndarray, tol: float = 0.0) -> np.ndarray:
    """Remove exact (or tol-close) consecutive duplicates to avoid zero-length segments."""
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
    """Leading edge (LE) point = minimum x."""
    _assert_xy(points)
    if points.shape[0] == 0:
        raise ValueError("Empty array provided; no points to evaluate leading edge.")
    return points[int(np.argmin(points[:, 0]))]

def trailing_edge(points: np.ndarray) -> np.ndarray:
    """Trailing edge (TE) point = maximum x."""
    _assert_xy(points)
    if points.shape[0] == 0:
        raise ValueError("Empty array provided; no points to evaluate trailing edge.")
    return points[int(np.argmax(points[:, 0]))]

def chord_length(points: np.ndarray) -> float:
    """Chord length = TE.x − LE.x (≥ 0 for valid, chord-aligned airfoils)."""
    _assert_xy(points)
    le = leading_edge(points)
    te = trailing_edge(points)
    return float(te[0] - le[0])

def normalize(points: np.ndarray,
              translate_to_le: bool = True,
              scale_to_chord1: bool = True) -> np.ndarray:
    """
    Normalize a 2D airfoil polyline (returns a new array):
      (1) translate so LE→(0,0)   (2) scale so chord→1
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
    Cumulative arclength for open or closed polylines.
    Returns S with S[0]=0 and S[-1]=total length.
    """
    _assert_xy(points)
    seg = np.linalg.norm(points[1:] - points[:-1], axis=1)
    return np.concatenate(([0.0], np.cumsum(seg)))
