# -*- coding: utf-8 -*-
# Flowxus/mesh/repair/fixers/duplicates.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
Remove exact duplicate elements. Reconfirms duplicates via canonical connectivity
and deletes extras.

Main Tasks:
-----------
   - Recompute duplicate sets by canonical tri/quad keys.
   - Remove extras (MVP policy: keep first occurrence).
   - Report applied count and notes.
"""

from typing import Dict, Any, List, Tuple
from ..ops import Mesh, remove_cells
from ..utils import canon_tri, canon_quad


def _reconfirm_duplicates(mesh: Mesh, examples: List[Tuple[str, int]]) -> Dict[str, List[int]]:
    """
    Rebuild duplicate indices by hashing canonical node tuples (tri/quad).
    """
    # Build hash maps by canonical connectivity to be safe
    tri_dups: List[int] = []
    quad_dups: List[int] = []

    if mesh.tris is not None and len(mesh.tris):
        seen = {}
        for i, conn in enumerate(mesh.tris):
            key = canon_tri(conn)
            if key in seen:
                tri_dups.append(i)
            else:
                seen[key] = i

    if mesh.quads is not None and len(mesh.quads):
        seen = {}
        for i, conn in enumerate(mesh.quads):
            key = canon_quad(conn)
            if key in seen:
                quad_dups.append(i)
            else:
                seen[key] = i

    return {"tri": tri_dups, "quad": quad_dups}


def fix(mesh: Mesh, finding: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove exact duplicates (keep first); returns {'applied','waived','notes'}.
    """
    # Reconfirm independently for safety
    buckets = _reconfirm_duplicates(mesh, finding.get("examples", []))

    applied = 0
    notes = ""

    # Remove duplicates (keep the earliest index)
    if buckets["tri"]:
        applied += remove_cells(mesh, "tri", buckets["tri"])
    if buckets["quad"]:
        applied += remove_cells(mesh, "quad", buckets["quad"])

    if applied == 0:
        notes = "No duplicates after reconfirmation."
    else:
        notes = f"Removed {applied} duplicate elements."

    return {"applied": applied, "waived": 0, "notes": notes}
