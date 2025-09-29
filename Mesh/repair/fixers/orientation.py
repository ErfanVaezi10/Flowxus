# -*- coding: utf-8 -*-
# Flowxus/mesh/repair/fixers/orientation.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
Reorient cells to counter-clockwise (CCW) by reversing node order, based on indices
reported by the checker.

Main Tasks:
-----------
- Parse ('tri'|'quad', idx) examples from findings.
- Flip local connectivity order for listed cells.
- Report applied count and notes.
"""

from typing import Dict, Any, List, Tuple
import numpy as np

from ..ops import Mesh, reorient_cells


def fix(mesh: Mesh, finding: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reorient listed cells to CCW by flipping node order.
    Assumes 'examples' contains tuples like ("tri", idx) or ("quad", idx) from the checker.
    """
    ex = finding.get("examples", []) or []

    tri_idxs = [int(i) for (k, i) in ex if k == "tri"]
    quad_idxs = [int(i) for (k, i) in ex if k == "quad"]

    applied = 0
    if tri_idxs:
        applied += reorient_cells(mesh, "tri", tri_idxs)
    if quad_idxs:
        applied += reorient_cells(mesh, "quad", quad_idxs)

    notes = f"Reoriented {applied} cells." if applied else "No cells to reorient."
    return {"applied": applied, "waived": 0, "notes": notes}
