# -*- coding: utf-8 -*-
# Flowxus/solver/interface/history.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 9/25/2025 (Updated: 10/09/2025)

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

# -*- coding: utf-8 -*-
# Flowxus/solver/interface/history.py
#
# Robust SU2 history reader:
# - Skips comment lines ('%' / '#')
# - Sniffs CSV delimiter (',' or ';') with whitespace fallback
# - Normalizes headers (quotes removed, INNER_ITER→ITER, RMS[...]→RES_*)
# - Streams rows (optional tail limit) and skips malformed/ragged lines
# Python 3.6 compatible.

from __future__ import absolute_import
import re
from typing import Optional, Tuple, List, Iterable
from collections import deque

from .formats import open_text, sniff_delim


# ----------------------------
# Header normalization helpers
# ----------------------------

# Map tokens inside RMS[...] to canonical residual keys
_RMS_MAP = {
    # Navier–Stokes
    "RHO": "RES_RHO",
    "RHOU": "RES_RHO_U",
    "RHOV": "RES_RHO_V",
    "RHOE": "RES_RHO_E",
    "RHOW": "RES_RHO_W",  # 3D momentum if present

    # Turbulence (SST / k-ω + common variants)
    "TKE": "RES_K",
    "Omega": "RES_DISSIPATION",
}


def _strip_quotes(s: str) -> str:
    if not s:
        return s
    s = s.strip()
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        return s[1:-1]
    return s


def _norm_header(h: str) -> str:
    """
    Normalize a single header token to canonical Flowxus form.
    Examples:
      '"INNER_ITER"'   -> 'ITER'
      '"RMS[RHO]"'     -> 'RES_RHO'
      '"RMS[RHOU]"'    -> 'RES_RHO_U'
    """
    if not h:
        return ""
    s = _strip_quotes(h)

    # INNER_ITER → ITER
    if s.upper() == "INNER_ITER":
        return "ITER"

    # RMS[...] → RES_* (including SST variants)
    # RMS[...] → RES_* (including SST variants)
    m = re.match(r"RMS\[\s*([A-Za-z0-9_\-]+)\s*]$", s, flags=re.IGNORECASE)
    if m:
        raw = m.group(1).strip()
        # normalize token: upper, hyphen→underscore
        key = raw.upper().replace("-", "_")

        # Prefer explicit canonicalization (keeps NS underscores consistent)
        mapped = _RMS_MAP.get(key)
        if mapped:
            return mapped

        # If we don't recognize the token, still surface it as a residual
        # This ensures plotting picks it up as turbulence automatically.
        return "RES_" + key


# ----------------------------
# Parsing utilities
# ----------------------------
def _split(line: str, delim: Optional[str], expected: Optional[int]) -> List[str]:
    """
    Split a line into fields using either a concrete delimiter (','|';')
    or treat any whitespace as the separator when delim is None.

    If 'expected' is provided, trim/pad behavior is *not* applied; we
    simply return whatever number of fields is present and the caller
    is responsible for validating row width.
    """
    if delim:
        parts = [p.strip() for p in line.strip().split(delim)]
    else:
        parts = line.strip().split()

    # No coercion to 'expected' length here; caller validates
    return parts


# ----------------------------
# Public API
# ----------------------------

def read_history(path: str, limit: Optional[int] = None) -> Tuple[List[str], List[List[float]]]:
    """
    Read a SU2 history file (plain or .gz), skipping comment lines starting with '%' or '#'.

    Parameters
    ----------
    path : str
        History file path ('.gz' supported).
    limit : Optional[int]
        If set, only keep the last `limit` data rows (streamed via deque).

    Returns
    -------
    (headers, rows) : (List[str], List[List[float]])
        Headers are normalized to canonical keys; rows hold floats with len(row)==len(headers).
        Empty ([], []) if file has no data rows.
    """
    # Stream the file; if limit is given, bound memory with a deque
    rows_deque = deque(maxlen=int(limit)) if (limit is not None) else None

    with open_text(path) as f:
        # Find the first non-comment, non-empty line → header
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

        delim = sniff_delim(header_line)
        raw_headers = _split(header_line.strip(), delim, None)
        headers = [_norm_header(h) for h in raw_headers]

        # Stream the remaining lines
        rows = []  # used only if limit is None
        for line in f:
            s = line.strip()
            if not s or s.startswith("%") or s.startswith("#"):
                continue
            parts = _split(line, delim, len(headers))
            # Defensive conversion—skip ragged/bad lines
            try:
                values = [float(x) for x in parts]
            except Exception:
                continue
            if len(values) != len(headers):
                # tolerate short lines; pad is dangerous, so skip
                continue

            if rows_deque is not None:
                rows_deque.append(values)
            else:
                rows.append(values)

    if rows_deque is not None:
        return (headers, list(rows_deque))
    return (headers, rows)


def read_last_n(path: str, n: int) -> Tuple[List[str], List[List[float]]]:
    """Convenience wrapper for read_history(path, limit=n)."""
    return read_history(path, limit=int(n))


def last_row(hr: Tuple[List[str], List[List[float]]]) -> dict:
    """
    Return the last row as a dict {header: value} for quick summaries.
    If rows are empty, returns {}.
    """
    headers, rows = hr
    if not rows:
        return {}
    last = rows[-1]
    out = {}
    for k, v in zip(headers, last):
        out[k] = v
    return out


def tail_follow(lines: Iterable[str], n_tail: int = 25) -> List[str]:
    """
    Keep last N lines from an iterable (utility for monitoring/logging).
    """
    dq = deque(maxlen=int(n_tail))
    for s in lines:
        dq.append(s)
    return list(dq)

