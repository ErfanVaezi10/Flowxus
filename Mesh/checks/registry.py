# -*- coding: utf-8 -*-
# Flowxus/mesh/check/registry.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
Central registry of mesh validation rules. Each rule is defined once here with its
metadata (id, function, severity, fixability), providing a single source of truth
for execution order and selection.

Main Tasks:
-----------
   - Import rule functions from `errors.py` (mandatory) and `warnings.py` (optional).
   - Bind them into `RuleSpec` objects with metadata (id, fn, severity, fixable).
   - Populate `REGISTRY` (id → spec) and `RULES_ORDER` (deterministic ordering).
   - Provide helper lists by severity and a filter function for enabling/disabling.

Inputs/Contracts:
-----------------
   - Error rules: hard failures, must be addressed before downstream use.
   - Warning rules: advisory quality signals; may be skipped if module absent.
   - Enabled/disabled maps: user- or config-driven booleans applied via `get_enabled_ids`.

Notes:
------
   - Scope: 2D meshing checks, but registry design allows extension.
   - Duplicates are disallowed: adding a rule with an existing id raises ValueError.
   - Severity is constrained to {"error", "warn"}.
"""


from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

# ---- Import rules (errors are mandatory; warnings are optional in v1) ----
from . import errors as _err  # must exist

try:
    from . import warnings as _wrn  # may not exist yet
    _HAS_WARNINGS = True
except Exception:
    _HAS_WARNINGS = False
    _wrn = None  # type: ignore


# ---- Rule spec ----

@dataclass(frozen=True)
class RuleSpec:
    id: str
    fn: Callable  # signature: fn(mv, thresholds_dict, cache_dict) -> finding_dict
    severity: str  # "error" | "warn"
    fixable: bool = True


# ---- Build registry ----

REGISTRY: Dict[str, RuleSpec] = {}

def _add(spec: RuleSpec) -> None:
    if spec.id in REGISTRY:
        raise ValueError(f"Duplicate rule id in registry: {spec.id}")
    if spec.severity not in ("error", "warn"):
        raise ValueError(f"Invalid severity for {spec.id}: {spec.severity}")
    REGISTRY[spec.id] = spec


# Errors (hard failures)
_add(RuleSpec("surface_orientation",    _err.surface_orientation,    "error", True))
_add(RuleSpec("negative_jacobians",     _err.negative_jacobians,     "error", True))
_add(RuleSpec("duplicate_elements",     _err.duplicate_elements,     "error", True))
_add(RuleSpec("multiple_edges",         _err.multiple_edges,         "error", True))
_add(RuleSpec("nonmanifold",            _err.nonmanifold,            "error", True))
_add(RuleSpec("overlapping_elements",   _err.overlapping_elements,   "error", True))
_add(RuleSpec("uncovered_faces",        _err.uncovered_faces,        "error", True))
_add(RuleSpec("missing_internal_faces", _err.missing_internal_faces, "error", True))
_add(RuleSpec("bl_continuity",          _err.bl_continuity,          "error", True))
_add(RuleSpec("missing_physical_groups",_err.missing_physical_groups,"error", False))


# Warnings (advisories) — register only if module is present
if _HAS_WARNINGS:
    _add(RuleSpec("two_single_edges",          _wrn.two_single_edges,          "warn",  True))
    _add(RuleSpec("tiny_elements",             _wrn.tiny_elements,             "warn",  True))
    _add(RuleSpec("min_angle_tris",            _wrn.min_angle_tris,            "warn",  True))
    _add(RuleSpec("quad_skewness_orthogonality", _wrn.quad_skewness_orthogonality, "warn", True))
    _add(RuleSpec("grading_spikes",            _wrn.grading_spikes,            "warn",  True))
    _add(RuleSpec("first_layer_height",        _wrn.first_layer_height,        "warn",  False))
    _add(RuleSpec("boundary_coverage",         _wrn.boundary_coverage,         "warn",  True))
    _add(RuleSpec("untagged_entities",         _wrn.untagged_entities,         "warn",  True))


# ---- Deterministic execution order ----
# Topology/validity first; coverage; then quality/BL; then tagging.
RULES_ORDER: List[str] = [
    "surface_orientation",
    "negative_jacobians",
    "duplicate_elements",
    "multiple_edges",
    "nonmanifold",
    "overlapping_elements",
    "uncovered_faces",
    "missing_internal_faces",
    "missing_physical_groups",
    "bl_continuity",
]

if _HAS_WARNINGS:
    RULES_ORDER += [
        "two_single_edges",
        "tiny_elements",
        "min_angle_tris",
        "quad_skewness_orthogonality",
        "grading_spikes",
        "first_layer_height",
        "boundary_coverage",
        "untagged_entities",
    ]


# ---- Convenience: severity lists ----

SEVERITY = {
    "error": [rid for rid, spec in REGISTRY.items() if spec.severity == "error"],
    "warn":  [rid for rid, spec in REGISTRY.items() if spec.severity == "warn"],
}


def get_enabled_ids(enabled_map: Optional[Dict[str, bool]]) -> List[str]:
    """
    Filter the canonical RULES_ORDER based on a user-provided enable/disable map.

    Parameters
    ----------
    enabled_map : dict[str, bool] or None
        Mapping of rule_id → bool. If a rule_id is absent, it defaults to enabled.
        If None, all rules in RULES_ORDER are considered enabled.

    Returns
    -------
    List[str]
        Ordered list of rule ids that remain enabled, preserving RULES_ORDER.
    """
    if not enabled_map:
        return list(RULES_ORDER)
    return [rid for rid in RULES_ORDER if enabled_map.get(rid, True)]
