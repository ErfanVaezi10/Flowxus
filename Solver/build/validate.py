# -*- coding: utf-8 -*-
# Flowxus/solver/build/validate.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 10/1/2025

Purpose
-------
Post-merge, cross-key validation for SU2 configs. Enforces solver–turbulence consistency,
Reynolds constraints, marker presence/format, and basic math problem sanity; fails fast
with informative ValidationError

Main Tasks
----------
    1. Require core keys: SOLVER, MATH_PROBLEM, ITER, MESH_FILENAME, MESH_FORMAT.
    2. Enforce solver rules:
       - RANS → KIND_TURB_MODEL≠'NONE', REYNOLDS_NUMBER>0, REYNOLDS_LENGTH>0.
       - EULER → KIND_TURB_MODEL='NONE'.
    3. Check markers: at least one MARKER_* with a non-empty SU2 tuple "(...)".
    4. Guard MATH_PROBLEM ∈ {'DIRECT','CONTINUATION'}.
    5. Helpers: _require(), _is_su2_tuple().

Notes
-----
- Runs after defaults+params merge; per-key schema checks occur elsewhere.
- Raises ValidationError with compact context; extend here for future rules.
"""

from __future__ import absolute_import
from typing import Any, Mapping
from .errors import ValidationError


def _require(cfg, key):
    # type: (Mapping[str, Any], str) -> None
    """
    Ensure a required key exists in the final config dict.
    """
    if key not in cfg:
        raise ValidationError("Missing required key: {}".format(key), {"key": key})


def _is_su2_tuple(val):
    # type: (Any) -> bool
    """
    Return True if val looks like an SU2 tuple literal: "(a, b, c)" or "(airfoil)".
    Accepts strings only; everything else returns False.
    """
    if not isinstance(val, str):
        return False
    s = val.strip()
    if len(s) < 2 or s[0] != "(" or s[-1] != ")":
        return False
    # Allow empty whitespace inside, but consider it empty if there's nothing between parentheses.
    inner = s[1:-1].strip()
    return len(inner) > 0


def cross_validate(cfg):
    # type: (Mapping[str, Any]) -> None
    """
    Cross-key logical validation (post-merge).

    Raises
    ------
    ValidationError
        If an inconsistent or incomplete configuration is detected.
    """
    # ---- Basic presence checks (final config must have these) ----
    for k in ("SOLVER", "MATH_PROBLEM", "ITER", "MESH_FILENAME", "MESH_FORMAT"):
        _require(cfg, k)

    solver = str(cfg.get("SOLVER"))
    turb = str(cfg.get("KIND_TURB_MODEL", "NONE"))

    # ---- Solver ↔ turbulence consistency ----
    if solver == "RANS":
        # RANS must have a turbulence model (not NONE)
        if turb == "NONE":
            raise ValidationError(
                "RANS requires a turbulence model (e.g., KIND_TURB_MODEL='SA').",
                {"SOLVER": solver, "KIND_TURB_MODEL": turb},
            )
        # Reynolds consistency (RANS with Re>0 requires positive reference length)
        Re = float(cfg.get("REYNOLDS_NUMBER", 0.0))
        L = float(cfg.get("REYNOLDS_LENGTH", 0.0))
        if Re <= 0.0:
            raise ValidationError(
                "RANS expects REYNOLDS_NUMBER > 0 (got {}). For inviscid flow use SOLVER='EULER'.".format(Re),
                {"REYNOLDS_NUMBER": Re},
            )
        if L <= 0.0:
            raise ValidationError(
                "REYNOLDS_LENGTH must be > 0 when using RANS (got {}).".format(L),
                {"REYNOLDS_LENGTH": L},
            )

    elif solver == "EULER":
        # Euler is inviscid; if a turbulence model is specified, it must be NONE.
        if turb != "NONE":
            raise ValidationError(
                "EULER (inviscid) must use KIND_TURB_MODEL='NONE' (got {}).".format(turb),
                {"SOLVER": solver, "KIND_TURB_MODEL": turb},
            )

    # ---- Marker sanity (lightweight, not solver-specific) ----
    # We only ensure that at least one boundary marker group is present and non-empty.
    # (Do NOT enforce specific types here to avoid breaking current builder defaults.)
    marker_keys = [k for k in cfg.keys() if k.startswith("MARKER_")]
    if not marker_keys:
        raise ValidationError(
            "No boundary markers found; at least one MARKER_* entry is required.",
            {"hint": "Provide marker_map or legacy marker_euler/marker_far."},
        )

    nonempty = [k for k in marker_keys if _is_su2_tuple(cfg.get(k))]
    if not nonempty:
        raise ValidationError(
            "All MARKER_* entries appear empty; expected non-empty SU2 tuples like '(airfoil)' or '(top, bottom)'.",
            {"example": "MARKER_FAR= (top, bottom)"},
        )

    # ---- Math problem quick check ----
    # (Keep it permissive; add rules here if you later introduce transient/time-marching keys.)
    math_problem = str(cfg.get("MATH_PROBLEM"))
    if math_problem not in ("DIRECT", "CONTINUATION"):
        # Schema should typically catch this; keep as a guardrail.
        raise ValidationError(
            "Unsupported MATH_PROBLEM '{}' after merge.".format(math_problem),
            {"allowed": ["DIRECT", "CONTINUATION"]},
        )

    # If future keys introduce contradictions (e.g., time marching + DIRECT), add checks here.
