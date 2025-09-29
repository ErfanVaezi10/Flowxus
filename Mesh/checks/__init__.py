# -*- coding: utf-8 -*-
# Flowxus/mesh/check/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
Public API for running mesh checks and returning normalized findings suitable
for CLI/CI/GUI consumption.

Main Tasks
----------
   - Provide defaults (`DEFAULTS`) for enable/disable policy and thresholds.
   - Orchestrate registry-defined rules over a MeshView and shared cache.
   - Aggregate findings and compute a top-level `ok` status.

Returned Schema:
----------------
{
  "ok": bool,
  "rules": { <rule_id>: finding_dict, ... },
  "meta": {
    "mesh_path": str, "n_points": int, "n_tris": int, "n_quads": int,
    "thresholds": dict, "enabled": dict
  }
}
"""


from typing import Dict, Any, Optional
import copy
from .helpers import build_mesh_view, precompute_cache
from .registry import REGISTRY, RULES_ORDER, get_enabled_ids


# -------------------------
# Defaults (policy)
# -------------------------
DEFAULTS: Dict[str, Any] = {
    "enabled": {
        # errors
        "surface_orientation": True,
        "negative_jacobians": True,
        "duplicate_elements": True,
        "multiple_edges": True,
        "nonmanifold": True,
        "overlapping_elements": False,
        "uncovered_faces": True,
        "missing_internal_faces": True,
        "missing_physical_groups": True,
        "bl_continuity": True,
        # warnings (if present in registry, these flags apply)
        "two_single_edges": True,
        "tiny_elements": True,
        "min_angle_tris": True,
        "quad_skewness_orthogonality": True,
        "grading_spikes": True,
        "first_layer_height": False,   # enable only if you pass a target
        "boundary_coverage": True,
        "untagged_entities": True,
    },
    "thresholds": {
        "min_angle_deg": 20.0,
        "quad_skew_p95": 0.85,            # as fraction of 90°
        "grading_ratio_max": 2.5,
        "tiny_area_rel": 1e-3,            # relative to mean area
        "tiny_area_abs": 0.0,             # absolute area floor (optional)
        "collinear_eps": 1e-12,
        "overlap_grid_bins": 96,
        "wall_name": "airfoil",
        "first_layer_target": None,        # set (float) to enable first_layer_height
        "required_groups": ["inlet", "outlet", "top", "bottom", "airfoil", "fluid"],
        "group_dims": None,                # e.g., {"fluid": 2, "airfoil": 1, ...}
        "strict_if_no_field_data": False,
    },
}


# -------------------------
# Orchestrator
# -------------------------
def _deep_merge(base: Dict[str, Any], upd: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Deep-merge two nested dicts (right-biased), preserving types and not mutating inputs.
    """
    if not upd:
        return copy.deepcopy(base)
    out = copy.deepcopy(base)
    for k, v in upd.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)  # type: ignore[arg-type]
        else:
            out[k] = copy.deepcopy(v)
    return out


def _meta(mv, cfg):
    """
    Assemble metadata snapshot (sizes, thresholds, enabled map) for the results payload.
    """
    return {
        "mesh_path": mv.mesh_path,
        "n_points": int(len(mv.points) if mv.points is not None else 0),
        "n_tris": int(len(mv.tris) if mv.tris is not None else 0),
        "n_quads": int(len(mv.quads) if mv.quads is not None else 0),
        "thresholds": copy.deepcopy(cfg.get("thresholds", {})),
        "enabled": copy.deepcopy(cfg.get("enabled", {})),
    }


def run_checks(msh_path: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Run all enabled rules (per registry order) against a .msh file and return findings.

    Parameters
    ----------
    msh_path : str
        Path to the Gmsh mesh file.
    config : dict, optional
        Overrides for `DEFAULTS` with the same structure (keys: "enabled", "thresholds").

    Returns
    -------
    dict
        Payload with keys:
          - "ok": bool — False iff any ERROR-severity rule fails.
          - "rules": dict — rule_id -> finding dict.
          - "meta": dict — mesh sizes, thresholds, enabled map, mesh path.
    """
    cfg = _deep_merge(DEFAULTS, config or {})
    mv = build_mesh_view(msh_path)
    cache = precompute_cache(mv, cfg.get("thresholds", {}))

    results: Dict[str, Any] = {}
    enabled_ids = get_enabled_ids(cfg.get("enabled"))

    for rid in enabled_ids:
        spec = REGISTRY.get(rid)
        if spec is None:
            # If a user enabled a rule that isn't registered (e.g., missing warnings.py), skip gracefully
            continue
        finding = spec.fn(mv, cfg.get("thresholds", {}), cache)
        # enforce severity field consistency
        finding["severity"] = spec.severity
        # ensure id matches registry
        finding["id"] = rid
        results[rid] = finding

    ok = True
    for rid, f in results.items():
        sev = REGISTRY[rid].severity
        if sev == "error" and not f.get("ok", False):
            ok = False
            break

    return {
        "ok": ok,
        "rules": results,
        "meta": _meta(mv, cfg),
    }
