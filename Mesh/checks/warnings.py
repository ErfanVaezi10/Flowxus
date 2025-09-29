# -*- coding: utf-8 -*-
# Flowxus/mesh/checks/warnings.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
WARN-tier mesh validation rules. These are advisory checks: they do not fail
the mesh outright, but highlight potential quality issues or missing metadata.
Each rule inspects a read-only `MeshView` and returns a normalized "finding"
record suitable for CLI/CI/GUI aggregation.

Main Tasks:
-----------
   - Define checks with the uniform signature: `chk_<rule_id>(mv, th, cache) -> dict`.
   - Keep heavy geometry in shared helpers; keep these rules lightweight.
   - Emit findings with a stable schema for downstream tools.

Inputs/Contracts:
-----------------
- `mv` : MeshView (immutable)
    Required: `points (N,2)`, optional: `tris (T,3)`, `quads (Q,4)`,
    `line_tags`, `cell_tags`.
- `th` : dict (thresholds/options)
    Tunables like `min_angle_deg`, `tiny_area_rel`, `grading_ratio_max`,
    `wall_name`, etc. Unknown keys are ignored.
- `cache` : dict (precomputations)
    Example: `edge_cells`, `boundary_edges`, `unified_cells`, `centroids`.

Finding Schema:
---------------
    {
      "id": "<rule_id>",
      "severity": "warn",
      "ok": bool,
      "count": int,
      "examples": [...],
      "details": {...},
      "fixable": bool,
    }

Notes:
------
- Scope: 2D surface meshes (triangles and/or quads).
- Performance: neighborhood/edge data is expected via `cache`; if missing,
  checks return `ok=True` with `details["skipped"]`.
- “Warn” severity: guidance for refinement/cleanup; not correctness failures.
"""


from __future__ import annotations
from typing import Dict, List
import numpy as np


# ---- Shared finding builder ----
def _finding(rule_id: str, ok: bool, count: int, examples: List, details: Dict, fixable: bool = True):
    return {
        "id": rule_id,
        "severity": "warn",
        "ok": bool(ok),
        "count": int(count),
        "examples": examples[:25],
        "details": details or {},
        "fixable": bool(fixable),
    }


# ------------------------------------------------------------------------------------
# 1) two_single_edges (dangling edge pairs)
# ------------------------------------------------------------------------------------
def two_single_edges(mv, th, cache) -> Dict:
    """
    Detect dangling edges (degree ≤ 1) that meet tip-to-tip (share exactly one node).
    Advisory: often indicates sliver remnants or tiny holes.
    """
    edge_cells = cache.get("edge_cells", {})
    dangling = [e for e, cells in edge_cells.items() if len(cells) <= 1]

    # Heuristic: look for pairs sharing a node
    pairs = []
    seen = set()
    for (u, v) in dangling:
        for (a, b) in dangling:
            if (u, v) == (a, b): continue
            if len({u, v, a, b}) == 3:  # share exactly one node
                key = tuple(sorted([(u, v), (a, b)]))
                if key not in seen:
                    seen.add(key)
                    pairs.append(key)

    ok = len(pairs) == 0
    return _finding(
        "two_single_edges",
        ok=ok,
        count=len(pairs),
        examples=pairs[:10],
        details={"note": "Dangling edges may indicate tiny holes or geometry defects."},
        fixable=True,
    )


# ------------------------------------------------------------------------------------
# 2) tiny_elements (area << typical)
# ------------------------------------------------------------------------------------
def tiny_elements(mv, th, cache) -> Dict:
    """
    Flag cells whose area is below either a relative threshold (`tiny_area_rel` × mean)
    or an absolute threshold (`tiny_area_abs`). Tri/quad areas computed consistently.
    """
    pts = mv.points
    areas = []

    if mv.tris is not None and len(mv.tris):
        tri_pts = pts[mv.tris]  # (T,3,2)
        a = 0.5 * np.abs(
            (tri_pts[:,1,0]-tri_pts[:,0,0])*(tri_pts[:,2,1]-tri_pts[:,0,1])
          - (tri_pts[:,1,1]-tri_pts[:,0,1])*(tri_pts[:,2,0]-tri_pts[:,0,0])
        )
        areas.append(a)

    if mv.quads is not None and len(mv.quads):
        quad_pts = pts[mv.quads]  # (Q,4,2)
        # split into two tris
        a1 = 0.5 * np.abs((quad_pts[:,1,0]-quad_pts[:,0,0])*(quad_pts[:,2,1]-quad_pts[:,0,1])
                        - (quad_pts[:,1,1]-quad_pts[:,0,1])*(quad_pts[:,2,0]-quad_pts[:,0,0]))
        a2 = 0.5 * np.abs((quad_pts[:,3,0]-quad_pts[:,0,0])*(quad_pts[:,2,1]-quad_pts[:,0,1])
                        - (quad_pts[:,3,1]-quad_pts[:,0,1])*(quad_pts[:,2,0]-quad_pts[:,0,0]))
        areas.append(a1+a2)

    if not areas:
        return _finding("tiny_elements", ok=True, count=0, examples=[], details={}, fixable=True)

    areas = np.concatenate(areas)
    mean_a = float(areas.mean()) if len(areas) else 1.0
    rel_thr = th.get("tiny_area_rel", 1e-3)
    abs_thr = th.get("tiny_area_abs", 0.0)

    bad_ids = np.nonzero((areas < rel_thr*mean_a) | (areas < abs_thr))[0]
    ok = len(bad_ids) == 0
    return _finding(
        "tiny_elements",
        ok=ok,
        count=len(bad_ids),
        examples=bad_ids[:20].tolist(),
        details={"mean_area": mean_a, "rel_thr": rel_thr, "abs_thr": abs_thr},
        fixable=True,
    )


# ------------------------------------------------------------------------------------
# 3) min_angle_tris
# ------------------------------------------------------------------------------------
def min_angle_tris(mv, th, cache) -> Dict:
    """
    Flag triangles with minimum interior angle below `min_angle_deg` (degrees).
    Uses Law-of-Cosines per element; robust to almost-degenerate edges.
    """
    if mv.tris is None or not len(mv.tris):
        return _finding("min_angle_tris", ok=True, count=0, examples=[], details={}, fixable=True)

    pts = mv.points[mv.tris]  # (T,3,2)
    # edge vectors
    v0 = pts[:,1,:] - pts[:,0,:]
    v1 = pts[:,2,:] - pts[:,1,:]
    v2 = pts[:,0,:] - pts[:,2,:]
    lens = [np.linalg.norm(v, axis=1) for v in (v0, v1, v2)]
    # law of cosines
    angles = []
    for i in range(3):
        a = lens[i-1]; b = lens[i-2]; c = lens[i]
        cosang = (a*a + b*b - c*c) / (2*a*b + 1e-30)
        cosang = np.clip(cosang, -1.0, 1.0)
        angles.append(np.degrees(np.arccos(cosang)))
    min_angles = np.min(np.stack(angles, axis=1), axis=1)

    thr = th.get("min_angle_deg", 20.0)
    bad_ids = np.nonzero(min_angles < thr)[0]
    ok = len(bad_ids) == 0
    return _finding(
        "min_angle_tris",
        ok=ok,
        count=len(bad_ids),
        examples=bad_ids[:20].tolist(),
        details={"thr_deg": thr, "p5": float(np.percentile(min_angles,5)) if len(min_angles) else None},
        fixable=True,
    )


# ------------------------------------------------------------------------------------
# 4) quad_skewness_orthogonality
# ------------------------------------------------------------------------------------
def quad_skewness_orthogonality(mv, th, cache) -> Dict:
    """
    Flag quads with excessive angular deviation from 90°. Computes four internal
    angles per quad; defines skew as max|angle−90°| and compares to `quad_skew_p95`.
    """
    if mv.quads is None or not len(mv.quads):
        return _finding("quad_skewness_orthogonality", ok=True, count=0, examples=[], details={}, fixable=True)

    pts = mv.points[mv.quads]  # (Q,4,2)
    # internal angles
    v01 = pts[:,1,:]-pts[:,0,:]; v12 = pts[:,2,:]-pts[:,1,:]
    v23 = pts[:,3,:]-pts[:,2,:]; v30 = pts[:,0,:]-pts[:,3,:]
    def angle(u,v):
        cosang = np.dot(u,v)/(np.linalg.norm(u,axis=1)*np.linalg.norm(v,axis=1)+1e-30)
        return np.degrees(np.arccos(np.clip(cosang,-1.0,1.0)))
    a0 = angle(v30,v01); a1 = angle(v01,v12); a2 = angle(v12,v23); a3 = angle(v23,v30)
    angles = np.stack([a0,a1,a2,a3],axis=1)
    skew = np.max(np.abs(angles-90.0),axis=1)  # deviation from 90°
    ortho = np.min(np.cos(np.radians(np.abs(angles-90.0))),axis=1)

    skew_thr = th.get("quad_skew_p95",0.85)
    bad_ids = np.nonzero(skew > skew_thr*90.0)[0]
    ok = len(bad_ids)==0
    return _finding(
        "quad_skewness_orthogonality",
        ok=ok,
        count=len(bad_ids),
        examples=bad_ids[:20].tolist(),
        details={"skew_thr": skew_thr, "p95_skew": float(np.percentile(skew,95))},
        fixable=True,
    )


# ------------------------------------------------------------------------------------
# 5) grading_spikes
# ------------------------------------------------------------------------------------
def grading_spikes(mv, th, cache) -> Dict:
    """
    Flag large size jumps across interior edges. Size proxy = sqrt(area).
    An edge is flagged if the size ratio of its two incident cells exceeds
    `grading_ratio_max`.
    """
    edge_cells = cache.get("edge_cells",{})
    centroids = cache.get("centroids",{})
    pts = mv.points

    # estimate size = sqrt(cell area)
    def cell_size(conn):
        P = pts[conn]
        return np.sqrt(0.5*abs((P[1,0]-P[0,0])*(P[2,1]-P[0,1]) - (P[1,1]-P[0,1])*(P[2,0]-P[0,0]))) if len(conn)==3 \
            else np.sqrt(abs((P[0,0]*P[1,1]-P[0,1]*P[1,0])+(P[1,0]*P[2,1]-P[1,1]*P[2,0])+(P[2,0]*P[3,1]-P[2,1]*P[3,0])+(P[3,0]*P[0,1]-P[3,1]*P[0,0]))/2)

    unified = cache.get("unified_cells",[])
    sizes = [cell_size(conn) for conn in unified]

    bad_edges=[]
    r_thr=th.get("grading_ratio_max",2.5)
    for e,cells in edge_cells.items():
        if len(cells)==2:
            s0,s1=sizes[cells[0]],sizes[cells[1]]
            r=max(s0/s1,s1/s0)
            if r>r_thr: bad_edges.append((e,r))
    ok=len(bad_edges)==0
    return _finding(
        "grading_spikes",
        ok=ok,
        count=len(bad_edges),
        examples=bad_edges[:20],
        details={"thr": r_thr, "pct_edges_over": 100*len(bad_edges)/max(1,len(edge_cells))},
        fixable=True,
    )


# ------------------------------------------------------------------------------------
# 6) first_layer_height
# ------------------------------------------------------------------------------------
def first_layer_height(mv, th, cache) -> Dict:
    """
    Advisory only. Compare a crude first-layer height proxy against
    `first_layer_target` (if provided). Skips when no quads or target is unset.
    """
    target = th.get("first_layer_target", None)
    if target is None:
        return _finding("first_layer_height", ok=True, count=0, examples=[], details={"skipped":"no target"}, fixable=False)

    centroids = cache.get("centroids",{})
    q_c = centroids.get("quad")
    if q_c is None or not len(q_c):
        return _finding("first_layer_height", ok=True, count=0, examples=[], details={"skipped":"no quads"}, fixable=False)

    # crude: just take min distance of quad centroid to origin as proxy (real impl: dist to wall curve)
    dists = np.linalg.norm(q_c,axis=1)
    ratios=dists/target
    return _finding(
        "first_layer_height",
        ok=True,
        count=len(ratios),
        examples=[],
        details={"target":target,"p50":float(np.percentile(ratios,50)),"p90":float(np.percentile(ratios,90))},
        fixable=False,
    )


# ------------------------------------------------------------------------------------
# 7) boundary_coverage
# ------------------------------------------------------------------------------------
def boundary_coverage(mv, th, cache) -> Dict:
    """
    Verify that the wall boundary tag (`wall_name`, default 'airfoil') exists
    and covers at least one line segment. Skips if no such tag is present.
    """
    wall=th.get("wall_name","airfoil")
    if mv.line_tags is None or wall not in mv.line_tags:
        return _finding("boundary_coverage", ok=True, count=0, examples=[], details={"skipped":"no wall tag"}, fixable=False)
    idxs=mv.line_tags[wall]
    ok=len(idxs)>0
    return _finding(
        "boundary_coverage",
        ok=ok,
        count=0 if ok else 1,
        examples=[],
        details={"note":"line coverage present" if ok else "missing wall segments"},
        fixable=True,
    )


# ------------------------------------------------------------------------------------
# 8) untagged_entities
# ------------------------------------------------------------------------------------
def untagged_entities(mv, th, cache):
    """
    Verify that the wall boundary tag (`wall_name`, default 'airfoil') exists
    and covers at least one line segment. Skips if no such tag is present.
    """
    # type (object, Dict, Dict) -> Dict
    total = (len(mv.tris) if mv.tris is not None else 0) + \
            (len(mv.quads) if mv.quads is not None else 0)

    # Build the set of all unified cell ids [0..total-1]
    allc = set(range(total))

    # Collect tagged ids into a concrete List[int]
    tagged_ids = []  # type: List[int]
    if mv.cell_tags:
        # mv.cell_tags: Dict[str, np.ndarray]-like. Normalize + flatten to ints.
        for arr in mv.cell_tags.values():
            if arr is None:
                continue
            # np.asarray(..., dtype=int).ravel().tolist() -> List[int]
            tagged_ids.extend(np.asarray(arr, dtype=int).ravel().tolist())

    # Now this is type-safe: difference expects an Iterable, we give a List[int]
    missing = allc.difference(tagged_ids)

    ok = len(missing) == 0
    return {
        "id": "untagged_entities",
        "severity": "warn",
        "ok": ok,
        "count": len(missing),
        "examples": list(missing)[:20],
        "details": {"note": "cells without tags"},
        "fixable": True,
    }
