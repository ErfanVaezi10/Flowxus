# -*- coding: utf-8 -*-
# Flowxus/mesh/repair/plan.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
Policy for automated mesh repair. Defines a default plan and a deep-merge
utility for user overrides.

Main Tasks:
-----------
   - DEFAULT_PLAN: per-rule actions (remove/dedupe/reorient), verify/write flags.
   - merge_plan: deep, right-biased merge without mutating inputs.

Notes:
------
   - Scope: targeted fixes for duplicates, multi-edges, and orientation (MVP).
   - Unknown rule keys in overrides are preserved but ignored by fixers.
   - `verify` is a placeholder in MVP (no automatic re-check).
"""

from typing import Dict, Any
import copy

DEFAULT_PLAN: Dict[str, Any] = {
    "rules": {
        "duplicate_elements": {"action": "remove", "prefer": "first"},  # or "last"
        "multiple_edges": {"action": "dedupe"},                          # keep two, drop extras (smallest area first)
        "surface_orientation": {"action": "reorient", "target": "CCW"},
    },
    "verify": False,               # (MVP) no automatic re-check
    "write_in_place": False,
    "keep_backup": True,
}


def merge_plan(base: Dict[str, Any], upd: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep-merge two plan dicts (right-biased), preserving nested structure and immutability.
    """
    if not upd:
        return copy.deepcopy(base)
    out = copy.deepcopy(base)
    for k, v in upd.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge_plan(out[k], v)  # type: ignore[arg-type]
        else:
            out[k] = copy.deepcopy(v)
    return out
