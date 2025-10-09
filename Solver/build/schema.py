# -*- coding: utf-8 -*-
# Flowxus/solver/build/schema.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 10/5/2025 (Updated: 10/09/2025)

Purpose
-------
Provide a lightweight schema layer for SU2 (v7+) configuration parameters. This module 
canonicalizes user-friendly keys to SU2’s official names, validates categorical options 
against enumerations, and checks numeric scalars against well-defined ranges—raising 
`SchemaError` with actionable messages on violations.

Main Tasks
----------
    1. Canonicalize params via `normalize_keys` using curated `ALIASES`.
    2. Enforce categorical constraints using `ENUMS` (case-insensitive matching).
    3. Enforce numeric constraints using `RANGES` with inclusive/strict bounds.
    4. Expose a single `validate` entrypoint for post-canonicalization checks.

Notes
-----
- This layer is intentionally minimal: it does not coerce types beyond float
  parsing for ranged keys, nor does it fill defaults. Higher layers should set
  defaults and handle cross-key consistency (e.g., turbulence vs. solver).
- Unknown keys pass through untouched; only listed keys are validated.
"""

from __future__ import absolute_import
from typing import Any, Dict, Mapping
from .errors import SchemaError

__all__ = ["normalize_keys", "validate", "ALIASES", "ENUMS", "RANGES"]

# --------------------------
# Canonicalization (aliases)
# --------------------------
# Map commonly used user keys to SU2 canonical keys.
ALIASES = {
    # Freestream
    "angle_of_attack": "AOA",
    "aoa_deg": "AOA",
    "mach": "MACH_NUMBER",
    "gamma": "GAMMA_VALUE",
    "temperature": "FREESTREAM_TEMPERATURE",
    "pressure": "FREESTREAM_PRESSURE",

    # Turbulence
    "turb_model": "KIND_TURB_MODEL",
    "re": "REYNOLDS_NUMBER",
    "reynolds": "REYNOLDS_NUMBER",
    "ref_length": "REYNOLDS_LENGTH",

    # Numerics / linear solver
    "cfl": "CFL_NUMBER",
    "iter": "ITER",
    "ls_prec": "LINEAR_SOLVER_PREC",
}

# --------------------------
# Enumerations (exact sets)
# --------------------------
# Allowed values (matched case-insensitively at validation time).
ENUMS = {
    "SOLVER": {"RANS", "EULER"},
    "MATH_PROBLEM": {"DIRECT", "CONTINUATION"},
    "KIND_TURB_MODEL": {"SST"},
    "CONV_NUM_METHOD_FLOW": {"ROE", "AUSM", "JST"},
    "CONV_NUM_METHOD_TURB": {"SCALAR_UPWIND"},
    "LINEAR_SOLVER": {"FGMRES", "GMRES", "BCGSTAB"},
    "LINEAR_SOLVER_PREC": {"ILU", "JACOBI", "NONE"},
    "CFL_ADAPT": {"YES", "NO"},
    "MUSCL_FLOW": {"YES", "NO"},
    "SLOPE_LIMITER_FLOW": {"VENKATAKRISHNAN", "NONE"},
}

# --------------------------
# Numeric ranges (inclusive flag)
# --------------------------
# key -> (min, max, inclusive_bounds)
RANGES = {
    "CFL_NUMBER": (1e-9, 1e4, True),
    "ITER": (1, 10**8, True),
    "AOA": (-90.0, 90.0, True),
    "GAMMA_VALUE": (1.0, 2.0, True),
    "REYNOLDS_NUMBER": (0.0, 1e12, True),
    "REYNOLDS_LENGTH": (1e-12, 1e3, True),
    "FREESTREAM_TEMPERATURE": (1.0, 5000.0, True),
    "FREESTREAM_PRESSURE": (1.0, 1e9, True),
}

_NUMERIC = (int, float)


def normalize_keys(params: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Map user-friendly keys to SU2 canonical keys (no value coercion).

    Only keys present in `ALIASES` are rewritten; all others are passed through.

    Args
    ----
    params : Mapping[str, Any]
        Arbitrary parameter dictionary supplied by the caller/UI.

    Returns
    -------
    Dict[str, Any]
        New dict with canonical SU2 key names.

    Notes
    -----
    Value types are preserved; validation/coercion is handled by `validate`.
    """
    out = {}  # type: Dict[str, Any]
    for k, v in params.items():
        can = ALIASES.get(k, k)
        out[can] = v
    return out


def _check_enum(key: str, val: Any) -> None:
    """
    Validate categorical parameters against `ENUMS` (case-insensitive).

    Raises
    ------
    SchemaError
        If `key` is enumerated and `val` is not a permitted option.
    """
    if key in ENUMS:
        sval = str(val).upper()
        if sval not in ENUMS[key]:
            raise SchemaError(
                "Invalid value for {k}: {v!r}. Allowed: {opts}".format(
                    k=key, v=val, opts=sorted(ENUMS[key])
                )
            )


def _check_range(key: str, val: Any) -> None:
    """
    Validate numeric parameters against `RANGES`.

    Attempts to parse `val` as float and checks inclusive/strict bounds.

    Raises
    ------
    SchemaError
        - If the value is non-numeric for a ranged key.
        - If the numeric value violates the configured bounds.
    """
    if key not in RANGES:
        return
    lo, hi, inclusive = RANGES[key]
    # Coerce numeric
    try:
        fval = float(val)
    except Exception:
        raise SchemaError("Non-numeric value for {k}: {v!r}".format(k=key, v=val))
    ok = (lo <= fval <= hi) if inclusive else (lo < fval < hi)
    if not ok:
        raise SchemaError(
            "Out-of-range {k}: {v} (expected {lo} {ineq} {hi}, inclusive={incl})".format(
                k=key, v=fval, lo=lo, ineq="≤ ... ≤" if inclusive else "< ... <", hi=hi, incl=inclusive
            )
        )


def validate(params: Mapping[str, Any]) -> None:
    """
    Validate a parameter dict *after* canonicalization via `normalize_keys`.

    Checks:
      - Enum membership for known categorical keys (case-insensitive).
      - Numeric ranges for known scalar keys (float-parsed).

    Args
    ----
    params : Mapping[str, Any]
        Dictionary whose keys should already be canonical SU2 names.

    Raises
    ------
    SchemaError
        On any violation (bad enum, non-numeric ranged value, or out-of-range).
    """
    for k, v in params.items():
        _check_enum(k, v)
        _check_range(k, v)
