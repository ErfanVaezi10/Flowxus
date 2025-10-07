# -*- coding: utf-8 -*-
# Flowxus/solver/interface/history.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 9/25/2025 (Updated: 10/07/2025)

Purpose
-------
Robustly parse SU2 history files (plain text or gzip-compressed) and expose them in a
normalized, analysis-friendly form. Handles diverse delimiter styles (comma/semicolon
or whitespace), skips comments and blank lines, maps SU2 header variants to canonical
Flowxus keys, and supports efficient tail reads for live monitoring.

Main Tasks
----------
    1. Read & normalize headers from the first non-comment line; map to canonical keys.
    2. Detect the delimiter (',' / ';' or None → whitespace) and parse all subsequent rows.
    3. Stream rows with a bounded deque when `limit` is set to cap memory.
    4. Provide helpers to fetch the last N rows, extract the last row as a dict,
       and follow a file append-only (tail -f style), including rotation handling.

Notes
-----
- Comment lines starting with '%' or '#' are ignored throughout.
- Header normalization covers common SU2 variants (e.g., DRAG→CD, RMSC*→RES_*).
- Parsing is defensive: ragged/malformed numeric rows are skipped rather than failing.
- `.gz` files are supported transparently via `open_text`; no seeking is assumed.
"""

from __future__ import absolute_import
from typing import Dict, List, Tuple, Iterable, Optional
import os
import time
from collections import deque

from .formats import open_text, sniff_delim

# Map SU2 header variants to canonical keys used by Flowxus.
NORMALIZE = {
    # Coefficients
    "DRAG": "CD",
    "LIFT": "CL",
    "MZ": "CMZ",
    "CMZ": "CMZ",

    # Residuals (common SU2 screen/history names)
    "RMS_DENSITY": "RES_RHO",
    "RMS_MOMENTUM-X": "RES_RHO_U",
    "RMS_MOMENTUM-Y": "RES_RHO_V",
    "RMS_MOMENTUM-Z": "RES_RHO_W",
    "RMS_ENERGY": "RES_RHO_E",

    # Iteration counter (varies by build)
    "INNER_ITER": "ITER",
    "OUTER_ITER": "ITER",
}


def _norm_header(h):
    """
    Normalize a raw header token to a canonical Flowxus key (uppercased).
    Unknown headers are uppercased and returned unchanged.
    """
    s = (h or "").strip().upper()
    return NORMALIZE.get(s, s)


def _split(line, delim, nmax):
    """
    Split a data line using a detected delimiter, or whitespace if `delim` is None.
    If `nmax` is provided, truncate extra fields to the header count.
    """
    parts = (line.split(delim) if delim else line.split())
    if nmax is not None and len(parts) > nmax:
        parts = parts[:nmax]
    return parts


def read_history(path, limit=None):  # type: (str, Optional[int]) -> Tuple[List[str], List[List[float]]]
    """
    Read a SU2 history file (plain or `.gz`), returning normalized headers and numeric rows.

    Args
    ----
    path : str
        History file path; `.gz` is supported transparently.
    limit : Optional[int]
        If provided, only keep the last `limit` numeric rows using a fixed-size deque.

    Returns
    -------
    (List[str], List[List[float]])
        - headers: canonicalized header names (Flowxus keys).
        - rows   : list of numeric rows; each row has len(row) == len(headers).
        Returns ([], []) if no data lines exist.

    Raises
    ------
    FileNotFoundError, PermissionError, OSError
        Propagated from file access if the path cannot be opened.

    Notes
    -----
    - Malformed numeric lines (parse errors or wrong field counts) are skipped.
    - Suitable for both convergence histories and coefficient logs emitted by SU2.
    """
    # Stream the file; if limit is given, bound memory with a deque.
    rows_deque = deque(maxlen=int(limit)) if (limit is not None) else None

    with open_text(path) as f:
        # Find the first non-comment, non-empty line → header.
        header_line = ""
        for line in f:
            if not line:
                continue
            s = line.strip()
            if not s or s.startswith("%") or s.startswith("#"):
                continue
            header_line = line
            break

        if not header_line:
            return ([], [])

        # Determine delimiter from header; normalize header tokens.
        delim = sniff_delim(header_line)
        raw_headers = header_line.strip().split(delim) if delim else header_line.strip().split()
        headers = [_norm_header(h) for h in raw_headers]

        # Stream and parse remaining lines.
        rows = []  # used only if limit is None
        for line in f:
            s = line.strip()
            if not s or s.startswith("%") or s.startswith("#"):
                continue
            parts = _split(line, delim, len(headers))
            # Defensive conversion—skip ragged/bad lines instead of raising.
            try:
                values = [float(x) for x in parts]
            except Exception:
                continue
            if len(values) != len(headers):
                # Tolerate short/ragged lines by skipping; zero-padding is risky.
                continue

            if rows_deque is not None:
                rows_deque.append(values)
            else:
                rows.append(values)

    if rows_deque is not None:
        return (headers, list(rows_deque))
    return (headers, rows)


def read_last_n(path, n=200):
    """
    Efficiently read only the last `n` numeric rows.

    Args
    ----
    path : str
        History file path (plain or `.gz`).
    n : int, optional
        Number of data rows to retain from the end (default: 200).

    Returns
    -------
    (List[str], List[List[float]])
        Canonical headers and the last `n` rows (or fewer if the file is shorter).
    """
    n = max(1, int(n))
    return read_history(path, limit=n)


def last_row(headers_rows):
    """
    Extract the last iteration as a dict mapping {header: value}.

    Args
    ----
    headers_rows : Tuple[List[str], List[List[float]]]
        Output of `read_history`/`read_last_n`.

    Returns
    -------
    Dict[str, float]
        Mapping from canonical header names to the last row's values. Returns {}
        if no data rows are present.
    """
    headers, rows = headers_rows
    if not headers or not rows:
        return {}
    vals = rows[-1]
    # len(vals) == len(headers) by construction
    return dict((headers[i], vals[i]) for i in range(len(headers)))


def tail_follow(path, poll_s=0.5):  # type: (str, float) -> Iterable[str]
    """
    Yield newly appended lines from a file (like `tail -f`), skipping blank/comment lines.

    Designed for live monitoring of SU2 histories. Handles file rotation by re-opening
    when the observed size decreases. Works with `.gz` as it does not rely on seeks;
    for gzip streams, we drain to EOF once after re-open.

    Args
    ----
    path : str
        File to follow (plain text or `.gz`).
    poll_s : float, optional
        Polling interval in seconds (default: 0.5).

    Yields
    ------
    str
        Raw lines as they are appended (without normalization). Combine with
        `sniff_delim`/`_split` for on-the-fly parsing if needed.

    Notes
    -----
    - Caller controls termination (e.g., timeout, external signal).
    - Lines starting with '%' or '#' and empty lines are filtered out.
    """
    poll_s = float(poll_s)
    last_size = -1
    stream = None
    try:
        while True:
            try:
                size = os.path.getsize(path)
            except Exception:
                size = -1

            # Rotate / initial open
            if stream is None or (last_size >= 0 and (size >= 0 and size < last_size)):
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:
                        pass
                stream = open_text(path)
                # Seek to end so we only get newly appended lines.
                try:
                    stream.seek(0, os.SEEK_END)
                except Exception:
                    # Some gzip streams do not support random access—fallback: read to end once.
                    for _ in stream:
                        pass

            last_size = size

            # Drain any new lines
            if stream is not None:
                for line in stream:
                    s = line.strip()
                    if not s or s.startswith("%") or s.startswith("#"):
                        continue
                    yield line

            time.sleep(poll_s)
    finally:
        if stream is not None:
            try:
                stream.close()
            except Exception:
                pass
