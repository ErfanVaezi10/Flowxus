# -*- coding: utf-8 -*-
# Flowxus/mesh/stats/export.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
Utility functions to export summary statistics (arbitrary nested dictionaries/lists)
into different human-readable formats: CSV, JSON, and Excel. The module flattens
nested structures into key-value rows and ensures compatibility with numpy scalars
and other non-standard types by JSON-encoding them.

Main Tasks:
-----------
    1. Flatten nested dictionaries/lists into ("dot.path.key", value) rows.
    2. Export summary data as:
        - CSV: 2-column "key,value" table.
        - JSON: structured, indented JSON.
        - Excel: single-sheet file (requires pandas).
    3. Handle numpy scalars and arrays gracefully via string/JSON encoding.
"""

from typing import Dict, Any, List, Tuple, Optional
import os, csv, json


try:
    import numpy as _np  # optional; used for dtype checks
except Exception:
    _np = None


# ------------------------------
# Internal helpers
# ------------------------------
def _is_scalar(x: Any) -> bool:
    """
    Check if `x` is a scalar-like type (str, bool, int, float, or numpy scalar).
    """
    if isinstance(x, (str, bool, int, float)):
        return True
    if _np is not None:
        if isinstance(x, (_np.generic,)):
            return True
    return False


def _to_json_str(x: Any) -> str:
    """
    Convert an object to a JSON string, handling numpy scalars cleanly.

    Parameters
    ----------
    x : Any
        Input object.

    Returns
    -------
    str
        JSON string representation.
    """
    def _default(o):
        try:
            if _np is not None and isinstance(o, (_np.generic,)):
                return o.item()
        except Exception:
            pass
        return str(o)

    return json.dumps(x, default=_default, ensure_ascii=False)


def _flatten(prefix: str, obj: Any, out: List[Tuple[str, Any]]) -> None:
    """
    Recursively flatten nested dictionaries/lists into (key_path, value) rows.

    Rules:
    ------
    - Scalars are stored as-is.
    - dicts: recurse into sorted keys, joined with '.'.
    - lists/tuples: stored as JSON string (to avoid exploding rows).
    - other objects (e.g., numpy arrays): stored as JSON string.

    Parameters
    ----------
    prefix : str
        Current key path (dot-separated).
    obj : Any
        Value to flatten.
    out : list of (str, Any)
        Accumulated flat key-value pairs.
    """
    if _is_scalar(obj):
        out.append((prefix, obj))
        return

    if isinstance(obj, dict):
        for k in sorted(obj.keys()):
            key = str(k)
            p2 = key if prefix == "" else "{}.{}".format(prefix, key)
            _flatten(p2, obj[k], out)
        return

    if isinstance(obj, (list, tuple)):
        out.append((prefix, _to_json_str(obj)))
        return

    out.append((prefix, _to_json_str(obj)))


# ------------------------------
# Public API: Writers
# ------------------------------
def write_summary_csv(summary: Dict[str, Any], path: str) -> str:
    """
    Write summary dictionary to a 2-column CSV file ("key,value").

    Parameters
    ----------
    summary : dict
        Nested dictionary of statistics/metadata.
    path : str
        Output path for the CSV file.

    Returns
    -------
    str
        Written file path.
    """
    rows: List[Tuple[str, Any]] = []
    _flatten("", summary, rows)

    folder = os.path.dirname(os.path.abspath(path))
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["key", "value"])
        for k, v in rows:
            if not _is_scalar(v):
                v = _to_json_str(v)
            w.writerow([k, v])

    return path


def write_summary_json(summary: Dict[str, Any], path: str, indent: int = 2) -> str:
    """
    Write summary dictionary to a JSON file.

    Parameters
    ----------
    summary : dict
        Nested dictionary of statistics/metadata.
    path : str
        Output path for the JSON file.
    indent : int, optional
        Indentation level for pretty-printing (default=2).

    Returns
    -------
    str
        Written file path.
    """
    folder = os.path.dirname(os.path.abspath(path))
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=indent, ensure_ascii=False)

    return path


def write_summary_excel(summary: Dict[str, Any], path: str) -> Optional[str]:
    """
    Write summary dictionary to a single-sheet Excel file.

    Requires `pandas`. If unavailable, returns None.

    Parameters
    ----------
    summary : dict
        Nested dictionary of statistics/metadata.
    path : str
        Output path for the Excel file.

    Returns
    -------
    str or None
        Written file path, or None if pandas is not installed.
    """
    try:
        import pandas as pd
    except Exception:
        return None

    rows: List[Tuple[str, Any]] = []
    _flatten("", summary, rows)

    df = pd.DataFrame(rows, columns=["key", "value"])
    folder = os.path.dirname(os.path.abspath(path))
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

    df.to_excel(path, index=False)  # engine auto-selected by pandas
    return path
