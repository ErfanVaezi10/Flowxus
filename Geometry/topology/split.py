# -*- coding: utf-8 -*-
# Flowxus/geometry/topology/split.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 9/2/2025 (Updated: 9/26/2025)

Purpose:
--------
Partition a CLOSED 2D loop into the two paths connecting LE→TE, and label them as
pressure/suction in a deterministic, rotation-stable way.

Conventions:
------------
   - Input is a CLOSED polyline (first == last within tolerance).
   - Indices are 0-based over the CLOSED array (0..N-1); the duplicate last row
     is ignored for path construction and labeling.
   - Returned 1-based ranges are inclusive and refer to indices on the CLOSED array.

Notes:
----------------------
   - LE/TE indices should be computed in a chord-aligned frame (LE→TE ~ +x). If callers pass
     rotated loops, they should align before computing indices to avoid ambiguous paths.
"""


from __future__ import division
from typing import Tuple, List
import numpy as np
from ._validation import _assert_xy, _require_closed


def _split_le_te_paths(points_closed: np.ndarray,
                       le_idx: int,
                       te_idx: int) -> Tuple[np.ndarray, np.ndarray,
                                             Tuple[int, int], Tuple[int, int]]:
    """
    Return the two LE→TE paths along the loop and their 0-based ranges on the CLOSED array.
    Ranges are inclusive and may wrap (represented as (start, end) with start > end).

    Notes
    -----
    - Paths are built from the UNIQUE-vertex array P = points_closed[:-1].
    - Each path includes both endpoints (LE and TE) exactly once.
    """
    P = points_closed[:-1]  # unique vertices
    N = P.shape[0]
    if le_idx == te_idx:
        raise ValueError("LE and TE indices coincide; invalid geometry or indices.")
    if not (0 <= le_idx < N and 0 <= te_idx < N):
        raise ValueError("LE/TE indices out of range for the given loop.")
    # FIX (optional): guard very short paths (adjacent indices); keep disabled if acceptable.
    if (le_idx - te_idx) % N in (1, N-1):
        raise ValueError("LE and TE are adjacent; paths are degenerate.")

    if le_idx < te_idx:
        path1 = P[le_idx:te_idx + 1]
        path2 = np.vstack((P[te_idx:N], P[:le_idx + 1]))
        r1 = (le_idx, te_idx)
        r2 = (te_idx, le_idx)  # wrap
    else:
        path1 = np.vstack((P[le_idx:N], P[:te_idx + 1]))
        path2 = P[te_idx:le_idx + 1]
        r1 = (le_idx, te_idx)  # wrap
        r2 = (te_idx, le_idx)
    return path1, path2, r1, r2


def _rotate_into_chord_frame(points_closed: np.ndarray,
                             le_idx: int,
                             te_idx: int) -> Tuple[np.ndarray, float]:
    """
    Rotate a CLOSED loop so that the chord vector (LE→TE) aligns with +x.
    Returns the rotated CLOSED array and the rotation angle (radians).

    Implementation notes
    --------------------
    - Input and output remain CLOSED (rotation preserves equality of endpoints).
    - We rotate the full CLOSED array for numerical consistency, then rebuild paths.
    """
    P = points_closed
    v = P[te_idx] - P[le_idx]
    theta = -np.arctan2(float(v[1]), float(v[0]))  # rotate by -angle to align with +x
    c, s = np.cos(theta), np.sin(theta)
    R = np.array([[c, -s], [s, c]], dtype=float)
    Prot = P @ R.T
    return Prot, float(theta)


def split_by_le_te(points_closed: np.ndarray,
                   le_idx: int,
                   te_idx: int,
                   *,
                   tol: float = 1e-12) -> Tuple[np.ndarray, np.ndarray,
                                                Tuple[int, int], Tuple[int, int]]:
    """
    Extract the two LE→TE paths without labeling.

    Returns
    -------
    (pathA, pathB, rangeA, rangeB)
      - pathA, pathB: arrays of shape (M,2) each.
      - rangeA, rangeB: 0-based inclusive index ranges on the CLOSED array;
        if start > end the range wraps around the end of the array.
    """
    _assert_xy(points_closed, check_finite=True)
    _require_closed(points_closed, tol=tol)
    return _split_le_te_paths(points_closed, le_idx, te_idx)


def label_suction_pressure(points_closed: np.ndarray,
                           le_idx: int,
                           te_idx: int,
                           pathA: np.ndarray,
                           pathB: np.ndarray,
                           *,
                           mode: str = "mean-y",
                           align_to_chord: bool = True,
                           tol: float = 1e-12) -> Tuple[str, str]:
    """
    Decide which of the two paths is 'suction' vs 'pressure'.

    Modes
    -----
    - mode="mean-y": higher mean y is labeled 'suction' (after optional chord alignment).
      (Future modes could be added; keep signature stable.)

    Notes
    -----
    - If align_to_chord=True, the provided pathA/pathB are ignored and rebuilt in the rotated frame.
      This is intentional for rotation invariance; documented to avoid confusion.
    - Tie handling: if mean-y values are numerically equal, we default to labeling B as suction;
      see the FIX below for a deterministic tie-break using tol.
    """
    _assert_xy(points_closed, check_finite=True)
    _require_closed(points_closed, tol=tol)
    if mode != "mean-y":
        raise ValueError("Unsupported mode '{}'; only 'mean-y' is available.".format(mode))

    if align_to_chord:
        Prot, _ = _rotate_into_chord_frame(points_closed, le_idx, te_idx)
        # Rebuild paths in the rotated frame for stable statistics
        A, B, _, _ = _split_le_te_paths(Prot, le_idx, te_idx)
    else:
        A, B = pathA, pathB

    muA = float(np.mean(A[:, 1]))
    muB = float(np.mean(B[:, 1]))

    # FIX: deterministic tie-break when muA≈muB within tol.
    if abs(muA - muB) <= tol:
        # Prefer the path with smaller average |y| as suction; if still tied, prefer the one
        # whose midpoint has larger y (arbitrary but deterministic next step).
        ayA = float(np.mean(np.abs(A[:, 1])))
        ayB = float(np.mean(np.abs(B[:, 1])))
        if abs(ayA - ayB) <= tol:
            return ("suction", "pressure") if muA >= muB else ("pressure", "suction")
        return ("suction", "pressure") if ayA > ayB else ("pressure", "suction")

    if muA > muB:
        return "suction", "pressure"
    else:
        return "pressure", "suction"


def _range_to_1based(range0: Tuple[int, int]) -> List[int]:
    """Convert a 0-based inclusive (start, end) range on CLOSED array to 1-based inclusive [i0, i1]."""
    i0, i1 = int(range0[0]) + 1, int(range0[1]) + 1
    return [i0, i1]


def split_sides(points_closed: np.ndarray,
                le_idx: int,
                te_idx: int,
                *,
                mode: str = "mean-y",
                align_to_chord: bool = True,
                tol: float = 1e-12) -> Tuple[np.ndarray, np.ndarray, List[int], List[int]]:
    """
    Full convenience API:
      - builds the two LE→TE paths,
      - labels them as suction/pressure (rotation-stable),
      - returns the two polylines + their 1-based inclusive ranges on the CLOSED array.

    Returns
    -------
    (pressure, suction, pressure_range_1b, suction_range_1b)
    """
    _assert_xy(points_closed, check_finite=True)  # NEW: Enable finite checking
    _require_closed(points_closed, tol=tol)

    A, B, rA, rB = _split_le_te_paths(points_closed, le_idx, te_idx)
    labA, labB = label_suction_pressure(points_closed, le_idx, te_idx, A, B,
                                        mode=mode, align_to_chord=align_to_chord, tol=tol)

    # FIX: keep output order as documented (pressure first), with stable mapping.
    if labA == "suction":
        suction, pressure = A, B
        r_su, r_pr = rA, rB
    else:
        suction, pressure = B, A
        r_su, r_pr = rB, rA

    # FIX (optional): sanity assert non-empty paths and inclusive ranges.
    if suction.shape[0] < 2 or pressure.shape[0] < 2:
        raise ValueError("Degenerate path produced; check LE/TE indices.")
    return pressure, suction, _range_to_1based(r_pr), _range_to_1based(r_su)
