# -*- coding: utf-8 -*-
# Flowxus/geometry/loaders/dat_loader.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 6/12/2025 (Updated: 8/10/2025)

Purpose:
--------
Read curve geometry from `.dat`-style files and return the coordinates as a NumPy array of
shape (N, 2). This parser is robust against common formatting quirks in airfoil datasets.

Main Features:
--------------
   1) Handles headers, blank lines, and mixed whitespace.
   2) Supports inline/full-line comments starting with '#' or '//' .
   3) Accepts comma- or whitespace-separated columns.
   4) Optional heuristic to auto-skip non-numeric leading lines.

Notes:
------
   - This module does *no* plotting, meshing, or normalization—just I/O parsing.
   - It returns raw points; downstream code may close the curve, normalize, etc.
"""

from typing import List
import numpy as np


def load_dat(filename: str, skip_header_guess: bool = True) -> np.ndarray:
    """
    Load a 2D airfoil from a `.dat`-like file into an (N, 2) float64 array.

    The function is robust to:
      - One or more header lines at the top of the file,
      - Blank lines and mixed whitespace,
      - Inline or full-line comments starting with '#' or '//' ,
      - Comma- or whitespace-separated columns.

    Parameters
    ----------
    filename : str
        Path to the `.dat` file.
    skip_header_guess : bool, optional
        If True (default), automatically detects and **skips non-numeric leading lines**
        by collecting only lines that *start* with a digit, sign, or dot.
        If False, a faster path using `numpy.loadtxt` with `skiprows=1` is used
        (works for well-formed files with a single header line).

    Returns
    -------
    np.ndarray
        (N, 2) float64 array of (x, y) points.

    Raises
    ------
    RuntimeError
        If parsing fails or the file does not contain exactly 2 columns.
    """
    try:
        if skip_header_guess:
            # --------
            # Robust cleaning pass:
            #   - Strip comments (#, //),
            #   - Drop blank lines,
            #   - Keep only lines that *start* with a numeric indicator.
            # --------
            cleaned: List[str] = []
            with open(filename, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    # Remove comments (order matters; strip both styles)
                    line = line.split("#", 1)[0]
                    line = line.split("//", 1)[0]
                    line = line.strip()
                    if not line:
                        continue
                    # Accept lines that start with a digit, sign, or dot
                    # (typical of numeric lines like "0.123 0.456" or "-0.1, 0.2")
                    if line[0] in "0123456789-+.":
                        cleaned.append(line)

            if not cleaned:
                raise RuntimeError("No numeric data found after cleaning.")

            # Parse numeric tokens (comma-or-space separated).
            data = []
            for line in cleaned:
                parts = line.replace(",", " ").split()
                if len(parts) < 2:
                    # Tolerate short lines; simply skip
                    continue
                x = float(parts[0])
                y = float(parts[1])
                data.append((x, y))
            pts = np.asarray(data, dtype=np.float64)

        else:
            # --------
            # Fast path with fallback:
            #   - First try skiprows=1 (common case: one header line).
            #   - If that fails, retry with skiprows=0 (no header).
            #   - Uses numpy's tokenizer (handles whitespace, '#' comments).
            #   - Will still fail if the file has more complex headers or '//' comments.
            # --------
            try:
                pts = np.loadtxt(
                    filename,
                    comments="#",
                    delimiter=None,   # auto-detect whitespace
                    ndmin=2,
                    dtype=np.float64,
                    skiprows=1
                )
            except Exception:
                pts = np.loadtxt(
                    filename,
                    comments="#",
                    delimiter=None,
                    ndmin=2,
                    dtype=np.float64,
                    skiprows=0
                )

        # Sanity check: (N, 2) array expected
        if pts.ndim != 2 or pts.shape[1] != 2:
            raise RuntimeError("Expected 2 columns (x, y). Got shape {}.".format(pts.shape))

        return pts

    except Exception as e:
        # Wrap any exception as a RuntimeError with file context for easier debugging upstream
        raise RuntimeError("[dat_loader] Failed to load airfoil from {}: {}".format(filename, e))
