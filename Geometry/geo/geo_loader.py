# -*- coding: utf-8 -*-
# Flowxus/geometry/geo/geo_loader.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 7/9/2025 (Updated: 10/10/2025)

Purpose:
--------
Dependency-light loader that reads 2D airfoil/curve geometry from supported formats
(.dat, .stp/.step, .igs/.iges), validates/sanitizes points, and exposes convenience
utilities (LE/TE, chord length, normalization, plotting).

Pipeline:
---------
load() → ndarray(float64, shape=(N,2)) → drop consecutive duplicates → ensure CLOSED → enforce CCW
"""

import os
import logging
from typing import Optional
import numpy as np
from ..loaders.dat_loader import load_dat
from ..loaders.step_loader import load_step
from ..loaders.iges_loader import load_iges
from ..topology.loop import ensure_closed as topo_ensure_closed, sort_loop_ccw
from ..ops import (
    drop_consecutive_duplicates,
    leading_edge as _le,
    trailing_edge as _te,
    chord_length as _chord_len,
    normalize as _normalize,
)

logger = logging.getLogger(__name__)


class GeometryLoader:
    """
    Unified loader for 2D airfoil/geometry data.

    Parameters
    ----------
    filename : str
        Path to the geometry file (.dat, .stp/.step, .igs/.iges).

    Attributes
    ----------
    filename : str
        Input filename provided by the user.
    name : str
        Basename (without extension).
    filetype : str
        Lowercased extension (e.g., ".dat").
    points : Optional[np.ndarray]
        Geometry as an (N, 2) float64 array. After load(): CLOSED and CCW.
    """

    def __init__(self, filename: str):
        self.filename = filename
        self.name = os.path.splitext(os.path.basename(filename))[0]
        self.filetype = os.path.splitext(filename)[-1].lower()
        self.points: Optional[np.ndarray] = None

    # --------------------
    # Core API
    # --------------------
    def load(self) -> None:
        """
        Load geometry into self.points as an (N, 2) float64 array.

        Steps
        -----
        1) Validate file exists.
        2) Dispatch loader by extension.
        3) np.asarray(..., float64).
        4) Sanity checks: shape (N,2), finite, non-empty after dedup.
        5) Canonicalize: ensure CLOSED, enforce CCW.
        """
        if not os.path.exists(self.filename):
            raise FileNotFoundError(f"[GeometryLoader] File not found: {self.filename}")

        # Dispatch based on file extension
        if self.filetype == ".dat":
            pts = load_dat(self.filename)
        elif self.filetype in (".stp", ".step"):
            pts = load_step(self.filename, samples_per_curve=200)
        elif self.filetype in (".igs", ".iges"):
            pts = load_iges(self.filename, samples_per_curve=200)
        else:
            raise ValueError(f"[GeometryLoader] Unsupported file type: {self.filetype}")

        # Standardize → numpy float64 array
        pts = np.asarray(pts, dtype=np.float64)

        # Must be 2D, with exactly 2 columns
        if pts.ndim != 2 or pts.shape[1] != 2:
            raise ValueError(f"[GeometryLoader] Geometry must be 2D (Nx2). Got shape: {pts.shape}")

        # Must contain only finite numbers
        if not np.isfinite(pts).all():
            bad = np.argwhere(~np.isfinite(pts))
            raise ValueError(f"[GeometryLoader] Non-finite values in geometry at indices {bad.tolist()}")

        # Remove consecutive duplicates (avoids zero-length segments downstream)
        pts = drop_consecutive_duplicates(pts)
        if pts.size == 0:
            raise ValueError(f"[GeometryLoader] Empty geometry loaded from {self.filename}")

        # Canonicalization: explicit closure + CCW orientation
        pts = topo_ensure_closed(pts, tol=1e-12)
        pts = sort_loop_ccw(pts)

        self.points = pts
        logger.info(
            "[GeometryLoader] Loaded '%s' (%s) with %d points (closed+CCW).",
            self.name, self.filetype, self.points.shape[0]
        )

    def get_closed_points(self, tol: float = 1e-9) -> np.ndarray:
        """
        Return closed points. Since `load()` already ensures explicit closure,
        this simply returns `self.points` (and validates presence).

        Parameters
        ----------
        tol : float
            Unused (kept for backward compatibility with older callers).

        Returns
        -------
        np.ndarray
            Closed (M, 2) point array.
        """
        if self.points is None:
            raise ValueError("[GeometryLoader] No geometry loaded. Call `.load()` first.")
        return self.points

    def plot(self, show: bool = True, save_path: Optional[str] = None, ax=None) -> None:
        """
        Plot the loaded geometry (lazy import to avoid hard matplotlib dependency).
        """
        if self.points is None:
            raise ValueError("[GeometryLoader] No geometry loaded. Call `.load()` first.")
        from post.plot_geo import plot_points
        plot_points(self.points, name=self.name, show=show, save_path=save_path, ax=ax)
        if save_path:
            logger.info("[GeometryLoader] Plot saved to: %s", save_path)

    # --------------------
    # Helpful utilities
    # --------------------
    def leading_edge(self) -> np.ndarray:
        """Leading edge (LE) point = minimum x."""
        if self.points is None:
            raise ValueError("[GeometryLoader] No geometry loaded.")
        return _le(self.points)

    def trailing_edge(self) -> np.ndarray:
        """Trailing edge (TE) point = maximum x."""
        if self.points is None:
            raise ValueError("[GeometryLoader] No geometry loaded.")
        return _te(self.points)

    def chord_length(self) -> float:
        """Chord length = TE.x - LE.x."""
        if self.points is None:
            raise ValueError("[GeometryLoader] No geometry loaded.")
        return _chord_len(self.points)

    def normalize(self, translate_to_le: bool = True, scale_to_chord1: bool = True) -> None:
        """
        Normalize geometry in-place (LE→(0,0), chord→1) using ops.normalize.
        """
        if self.points is None:
            raise ValueError("[GeometryLoader] No geometry loaded.")
        self.points = _normalize(
            self.points,
            translate_to_le=translate_to_le,
            scale_to_chord1=scale_to_chord1
        )
        logger.info(
            "[GeometryLoader] Normalization applied: translate_to_le=%s, scale_to_chord1=%s",
            translate_to_le, scale_to_chord1
        )
