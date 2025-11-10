# -*- coding: utf-8 -*-
# Flowxus/geometry/topology/_validation.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 11/10/2025

Purpose:
--------
Centralized validation utilities for topology operations to eliminate code duplication
and ensure consistent geometry quality checking across all topology modules.

Main Tasks:
   1. Validate point array structure and data integrity across all topology operations
   2. Provide consistent closure checking and validation for closed polyline operations
   3. Enable configurable validation levels with optional finite value checking
"""

from typing import Optional
import numpy as np


def _assert_xy(points: Optional[np.ndarray], check_finite: bool = False) -> None:
    """
    Validate that points array is (N, 2) with optional finite value checking.

    Parameters
    ----------
    points : Optional[np.ndarray]
        Points array to validate
    check_finite : bool, optional
        If True, check for finite values (no NaN/Inf), by default False

    Raises
    ------
    ValueError
        If points array fails validation checks
    """
    if points is None:
        raise ValueError("No geometry provided (points is None).")

    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError(f"Expected (N, 2) array for points, got shape {points.shape}.")

    if check_finite and not np.isfinite(points).all():
        bad_indices = np.argwhere(~np.isfinite(points))
        raise ValueError(f"Non-finite coordinates detected at indices: {bad_indices.tolist()}")


def _require_closed(points: np.ndarray, tol: float = 1e-12) -> None:
    """
    Require that polyline is closed (first == last within tolerance).

    Parameters
    ----------
    points : np.ndarray
        Points array to check
    tol : float, optional
        Absolute tolerance for closure check, by default 1e-12

    Raises
    ------
    ValueError
        If polyline is not closed within tolerance
    """
    if points.shape[0] < 2 or not np.allclose(points[0], points[-1], atol=tol, rtol=0.0):
        raise ValueError("Expected a CLOSED polyline (first==last within tolerance).")


def _is_exactly_closed(points: np.ndarray, tol: float) -> bool:
    """
    Check if polyline is explicitly closed (first == last within tolerance).

    Parameters
    ----------
    points : np.ndarray
        Points array to check
    tol : float
        Absolute tolerance for closure check

    Returns
    -------
    bool
        True if polyline is closed within tolerance
    """
    if points.shape[0] < 2:
        return False
    return np.allclose(points[0], points[-1], atol=tol, rtol=0.0)
