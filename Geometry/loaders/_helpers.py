# -*- coding: utf-8 -*-
# Flowxus/geometry/loaders/_helpers.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 11/10/2025

Purpose:
--------
Shared helper functions for CAD file loaders to eliminate code duplication and provide
consistent entity processing and curve evaluation across different format loaders.

Main Tasks:
-----------
   1) Remove duplicate Gmsh entities while preserving order for efficient curve processing
   2) Evaluate curve geometry at specified parameter values to generate discrete point arrays
   3) Validate point arrays for consistent geometry quality across all loaders
"""

from typing import List, Sequence, Tuple
import numpy as np
import gmsh


def _unique_entities(entities: Sequence[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """
    Return entities with duplicates removed, preserving order.

    Parameters
    ----------
    entities : Sequence[Tuple[int, int]]
        Sequence of Gmsh entities as (dimension, tag) tuples.

    Returns
    -------
    List[Tuple[int, int]]
        Unique entities in original order.
    """
    seen = set()
    out: List[Tuple[int, int]] = []
    for ent in entities:
        if ent not in seen:
            seen.add(ent)
            out.append(ent)
    return out


def _eval_curve(dim: int, tag: int, ts: np.ndarray) -> np.ndarray:
    """
    Evaluate a curve at parameter values `ts` using Gmsh's model evaluator.

    Parameters
    ----------
    dim : int
        Gmsh entity dimension (1 for curves).
    tag : int
        Gmsh entity tag.
    ts : np.ndarray
        Parameter values for curve evaluation.

    Returns
    -------
    np.ndarray
        (M, 3) array of xyz points.
    """
    xyz_list = gmsh.model.getValue(dim, tag, ts.tolist())
    xyz = np.array(xyz_list, dtype=float).reshape(-1, 3)
    return xyz


def _validate_point_array(points: np.ndarray, min_points: int = 3) -> None:
    """
    Validate that points array meets basic geometry requirements.

    Ensures consistent quality checking across all geometry loaders by
    verifying array structure, data validity, and minimum point count.

    Parameters
    ----------
    points : np.ndarray
        Array of points to validate
    min_points : int, optional
        Minimum number of points required (default: 3)

    Raises
    ------
    ValueError
        If points array fails any validation check
    """
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError(f"Expected (N,2) array for points, got shape {points.shape}")

    if points.shape[0] < min_points:
        raise ValueError(f"Need at least {min_points} points, got {points.shape[0]}")

    if not np.isfinite(points).all():
        bad_indices = np.argwhere(~np.isfinite(points))
        raise ValueError(f"Non-finite values detected in geometry at indices: {bad_indices.tolist()}")
