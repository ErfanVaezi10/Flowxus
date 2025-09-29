# -*- coding: utf-8 -*-
# Flowxus/mesh/repair/registry.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
Map repair rule ids to fixer implementations and provide a stable execution order.

Main Tasks:
-----------
   - Bind ids to fix functions via `FixSpec`.
   - Publish FIXERS (id → spec) and ORDER (deterministic sequence).

Notes:
------
   - Topology fixes precede orientation.
   - Fixer signature: fn(mesh, finding_dict, rule_cfg) -> {"applied","waived","notes"}.
   - Registry is extendable; duplicate ids should be avoided upstream.
"""

from typing import Callable, Dict
from dataclasses import dataclass
from .fixers.duplicates import fix as fix_duplicates
from .fixers.multi_edges import fix as fix_multi_edges
from .fixers.orientation import fix as fix_orientation


@dataclass(frozen=True)
class FixSpec:
    """
    Metadata for a repair action: id, function handle, and expected I/O schema.
    """
    id: str
    fn: Callable   # signature: fn(mesh, finding_dict, rule_cfg) -> {"applied": int, "waived": int, "notes": str}


FIXERS: Dict[str, FixSpec] = {
    "duplicate_elements": FixSpec("duplicate_elements", fix_duplicates),
    "multiple_edges":     FixSpec("multiple_edges",     fix_multi_edges),
    "surface_orientation":FixSpec("surface_orientation",fix_orientation),
}

# Topology first, then orientation
ORDER = [
    "duplicate_elements",
    "multiple_edges",
    "surface_orientation",
]
