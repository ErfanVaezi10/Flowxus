# -*- coding: utf-8 -*-
# Flowxus/solver/interface/formats.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 9/23/2025 (Updated: 10/07/2025)

Purpose
-------
Tiny I/O helpers for reading text files (optionally gzip-compressed) in UTF-8 and for sniffing 
simple CSV-like delimiters in header lines. These utilities are used across SU2/Gmsh interfaces 
and post-processing where logs and histories may be plain text or `.gz`.

Main Tasks
----------
    1. Provide `open_text(path)` that transparently opens `.gz` and plain files as
       UTF-8 text streams.
    2. Provide `sniff_delim(first_line)` to detect ',' or ';' and fall back to
       whitespace-delimited parsing when neither is present.

Notes
-----
- `open_text` wraps `gzip.open(..., 'rb')` with `io.TextIOWrapper` for UTF-8 decoding.
  With `newline=""`, line endings are passed through unchanged (suitable for parsers
  that handle '\n'/'\r\n' consistently).
- `sniff_delim` is intentionally conservative: if neither comma nor semicolon appears,
  callers should treat the line as whitespace-delimited (spaces/tabs).
"""

from __future__ import absolute_import
import io
import gzip
from typing import IO, Optional


def open_text(path):  # type: (str) -> IO[str]
    """
    Open a text file as UTF-8, transparently supporting gzip-compressed inputs.

    Args
    ----
    path : str
        Filesystem path to a plain text file or a `.gz`-compressed text file.

    Returns
    -------
    IO[str]
        A readable text stream positioned at the start of the file.

    Raises
    ------
    FileNotFoundError, PermissionError, OSError
        Propagated from the underlying open if the file cannot be accessed.

    Notes
    -----
    - `newline=""` is used to avoid newline translation; most line-oriented parsers
      will handle '\n' and '\r\n' seamlessly.
    """
    if path.lower().endswith(".gz"):
        # Decode gzip bytes as UTF-8; keep raw newlines (no translation).
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", newline="")
    # Plain text open with explicit UTF-8 and no newline translation.
    return open(path, "r", encoding="utf-8", newline="")


def sniff_delim(first_line):  # type: (str) -> Optional[str]
    """
    Heuristically detect a delimiter for CSV-like lines.

    Args
    ----
    first_line : str
        A representative line (typically a header) used to infer the delimiter.

    Returns
    -------
    Optional[str]
        ',' or ';' if found; otherwise `None` to indicate whitespace-delimited data.
    """
    # Keep it permissive—history/logs often vary by locale/tooling.
    if "," in first_line:
        return ","
    if ";" in first_line:
        return ";"
    return None
