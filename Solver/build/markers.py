# -*- coding: utf-8 -*-
# Flowxus/solver/build/markers.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 10/3/2025

Purpose
-------
Format and apply boundary markers and per-marker BC parameters for SU2 configs. Accept labels
or physical IDs, normalizes to canonical tuple strings, and updates the config dict without
side effects

Main Tasks
----------
    1. fmt_tuple(names) → SU2-style "(a, b, c)" string (or None).
    2. apply_marker_map(cfg, marker_map, id_map): group labels by SU2 key, translate via
       id_map when available, and write tuples to cfg.
    3. apply_bc_params(cfg, bc_params): append expert per-marker key/values verbatim.

Notes
-----
- Ignores None/empty inputs; tokens may be str or int.
- Only formatting/writing; semantic checks occur in validation steps.
"""

from __future__ import absolute_import
from typing import Any, Dict, Mapping, Optional, List, Union

Token = Union[str, int]


def fmt_tuple(names):
    """
    Return SU2-style tuple string '(a, b, c)' or None if names is None.
    """
    if names is None:
        return None
    if isinstance(names, (list, tuple)):
        return "(" + ", ".join(str(x) for x in names) + ")"
    return "(" + str(names) + ")"


def apply_marker_map(cfg,                # type: Dict[str, Any]
                     marker_map,         # type: Optional[Mapping[str, str]]
                     id_map              # type: Optional[Mapping[str, int]]
                     ):
    # type: (...) -> None
    """
    marker_map: label -> SU2 key (e.g., 'airfoil' -> 'MARKER_EULER')
    id_map:     label -> numeric id (optional). If absent, keep label as token.
    """
    if not marker_map:
        return
    id_map = id_map or {}
    grouped = {}  # type: Dict[str, List[Token]]
    for label, su2_key in marker_map.items():
        token = id_map.get(label, label)  # type: Token
        grouped.setdefault(su2_key, []).append(token)
    for su2_key, tokens in grouped.items():
        cfg[su2_key] = fmt_tuple(tokens)


def apply_bc_params(cfg,        # type: Dict[str, Any]
                    bc_params   # type: Optional[Mapping[str, Mapping[str, Any]]]
                    ):
    """
    bc_params: {"MARKER_INLET": {"TOTAL_CONDITIONS": "(inlet)", ...}, ...}
    Appends verbatim (expert mode).
    """
    if not bc_params:
        return
    for _marker_key, kv in bc_params.items():
        if hasattr(kv, "items"):
            for subk, v in kv.items():
                cfg[str(subk)] = v
