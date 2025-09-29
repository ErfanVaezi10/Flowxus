# -*- coding: utf-8 -*-
# Flowxus/mesh/repair/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose
-------
Public API to apply targeted mesh repairs based on check findings.

Main Tasks:
-----------
   - Load mesh via `mesh.stats.data.reader.read`, wrap into mutable `Mesh`.
   - Execute fixers in registry order per a repair plan (default + overrides).
   - Optionally write a repaired mesh (meshio) and a JSON log.

Notes:
------
   - MVP scope: duplicate removal, multi-edge dedupe, CCW reorientation.
   - Dry-run by default; writing requires `meshio` to be installed.
   - Output path defaults to input path unless overridden.
"""


from typing import Dict, Any, Optional
import json
from pathlib import Path
from mesh.stats.data.reader import read as _read_mesh
from .registry import FIXERS, ORDER
from .ops import Mesh, mesh_from_reader, write_mesh_safe
from .plan import DEFAULT_PLAN, merge_plan


def run_repair(
    msh_path: str,
    findings: Dict[str, Any],
    *,
    plan: Optional[Dict[str, Any]] = None,
    dry_run: bool = True,
    out_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Apply enabled fixers to a mesh using a (merged) repair plan and check findings.

    Parameters
    ----------
    msh_path : str
        Path to the input mesh (.msh).
    findings : dict
        Results from `mesh.check.run_checks` (expects "rules" → finding dicts).
    plan : dict, optional
        Overrides for DEFAULT_PLAN (nested structure under "rules", and flags).
    dry_run : bool, optional
        If True, perform in-memory edits only; do not write to disk.
    out_path : str, optional
        Destination mesh path when `dry_run=False`. Defaults to `msh_path`.

    Returns
    -------
    dict
        {
          "ok": bool,
          "msh_path": str,                 # output path (input if dry-run)
          "applied": [ {rule, count, notes}, ... ],
          "skipped": [ {rule, reason}, ... ],
          "waived":  [ {rule, count, notes}, ... ],
          "log": Optional[str]             # JSON log path if written
        }
    """
    cfg = merge_plan(DEFAULT_PLAN, plan or {})

    # Load mutable mesh model
    R = _read_mesh(msh_path)
    mesh = mesh_from_reader(R, path=msh_path)

    applied = []
    skipped = []
    waived = []

    # Execute in a stable order
    for rule_id in ORDER:
        spec = FIXERS.get(rule_id)
        if not spec:
            continue

        rule_cfg = (cfg.get("rules", {}) or {}).get(rule_id, {})
        # Skip disabled rules explicitly (action = "skip")
        if rule_cfg.get("action", "").lower() in ("skip", "disabled", "off"):
            skipped.append({"rule": rule_id, "reason": "disabled by plan"})
            continue

        fixer_fn = spec.fn

        # Look up the corresponding finding (may be absent if check disabled)
        finding = (findings or {}).get("rules", {}).get(rule_id)
        if not finding:
            skipped.append({"rule": rule_id, "reason": "no finding for rule"})
            continue

        # Fixer returns dict with 'applied', 'waived', 'notes'
        result = fixer_fn(mesh, finding, rule_cfg)

        a = int(result.get("applied", 0))
        w = int(result.get("waived", 0))
        n = result.get("notes", "")
        if a > 0:
            applied.append({"rule": rule_id, "count": a, "notes": n})
        elif w > 0:
            waived.append({"rule": rule_id, "count": w, "notes": n})
        else:
            skipped.append({"rule": rule_id, "reason": "no-op"})

    # Decide output path
    out_path = out_path or msh_path
    if dry_run:
        # No changes written
        return {
            "ok": True,
            "msh_path": msh_path,
            "applied": applied,
            "skipped": skipped,
            "waived": waived,
            "log": None,
        }

    # Write mesh (requires meshio); if not available, raise a clear error
    written_path = write_mesh_safe(mesh, out_path)

    # Optional: write a JSON log next to mesh
    log_path = str(Path(written_path).with_suffix(".repair.json"))
    Path(log_path).write_text(json.dumps({
        "applied": applied,
        "skipped": skipped,
        "waived": waived,
        "plan": cfg,
    }, indent=2))

    return {
        "ok": True,
        "msh_path": written_path,
        "applied": applied,
        "skipped": skipped,
        "waived": waived,
        "log": log_path,
    }
