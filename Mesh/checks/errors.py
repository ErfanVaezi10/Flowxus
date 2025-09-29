# -*- coding: utf-8 -*-
# Flowxus/mesh/checks/errors.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
ERROR-tier mesh validation rules. Each rule inspects a read-only `MeshView` and returns one
normalized "finding" record that downstream tooling (CLI/CI/GUI) can aggregate, pretty-print,
or turn into exit codes.

Main Tasks:
-----------
   - Define checks with the uniform signature: `chk_<rule_id>(mv, th, cache) -> dict`.
   - Use lightweight local helpers; heavy geometry kernels live in `helpers/`.
   - Emit findings with a stable schema for machine consumption.

Inputs/Contracts:
-----------------
- `mv` : MeshView (immutable)
    Required attributes (typical 2D cases): `points (N,2)`, `tris (T,3) or None`,
    `quads (Q,4) or None`. Optional: `line_tags` (name -> list of line IDs),
    `mesh_path` (for I/O-based checks).
- `th` : dict (thresholds / options)
    Tunables such as `collinear_eps`, `required_groups`, `group_dims`,
    `strict_if_no_field_data`, `wall_name`, etc. Unknown keys are ignored.
- `cache` : dict (precomputations from `helpers.precompute_cache(mv, th)`)
    Example entries: `edge_cells`, `boundary_edges`, `node_cells`,
    `unified_cells`, `centroids`, `spatial_grid`, `cell_edges`.

Finding Schema:
---------------
Each check returns a dict:

    {
      "id": "<rule_id>",           # string, stable identifier
      "severity": "error",         # fixed for this module
      "ok": bool,                  # True => pass; False => violation(s) found
      "count": int,                # number of violations (or 0)
      "examples": [...],           # compact sample (capped; indices, pairs, etc.)
      "details": {...},            # extra context (note/metrics/missing names)
      "fixable": bool,             # True if an automatic repair is plausible
    }

Notes:
------
   - Scope: 2D surface meshes (triangles and/or quads). Orientation is checked
     separately from degeneracy (see `surface_orientation` vs `negative_jacobians`).
   - Soft deps: Physical-group checks use `meshio` if available; otherwise they
     skip with `ok=True` and a `details["skipped"]` message.
   - Performance: Pairwise overlap checks use bbox-based neighbor candidates from
     a spatial grid provided via `cache["spatial_grid"]`.
"""


from .kernels import segments_intersect, point_in_triangle, point_in_quad
from typing import Dict, List
import numpy as np

try:
    from mesh.tools.validate import check_physical_groups as _check_pg  # existing module
    _HAS_MESHIO = True
except Exception:
    _HAS_MESHIO = False

    def _check_pg(*_args, **_kwargs):
        return


# ---- Small local helpers (kept minimal; heavy kernels live in helpers/geometry) ----
def _finding(rule_id: str, ok: bool, count: int, examples: List, details: Dict, fixable: bool = True):
    return {
        "id": rule_id,
        "severity": "error",
        "ok": bool(ok),
        "count": int(count),
        "examples": examples[:25],  # cap to keep payload small
        "details": details or {},
        "fixable": bool(fixable),
    }


def _poly_area_xy(coords: np.ndarray) -> float:
    """
    Signed polygon area in XY (positive for CCW). coords shape (m,2).
    """
    x = coords[:, 0]
    y = coords[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _tri_area_xy(p: np.ndarray, q: np.ndarray, r: np.ndarray) -> float:
    return 0.5 * float((q[0]-p[0])*(r[1]-p[1]) - (q[1]-p[1])*(r[0]-p[0]))


def _segments_intersect(p, q, r, s, eps=1e-12) -> bool:
    """
    Robust 2D segment intersection including collinear-overlap.
    """
    p = np.asarray(p); q = np.asarray(q); r = np.asarray(r); s = np.asarray(s)
    def orient(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
    o1 = orient(p, q, r)
    o2 = orient(p, q, s)
    o3 = orient(r, s, p)
    o4 = orient(r, s, q)

    # Proper intersection
    if (o1*o2 < -eps) and (o3*o4 < -eps):
        return True

    # Collinear cases: check projections overlap
    def collinear(u, v, w):  # w on uv ?
        return abs(orient(u, v, w)) <= eps and min(u[0], v[0]) - eps <= w[0] <= max(u[0], v[0]) + eps and \
               min(u[1], v[1]) - eps <= w[1] <= max(u[1], v[1]) + eps

    if abs(o1) <= eps and collinear(p, q, r): return True
    if abs(o2) <= eps and collinear(p, q, s): return True
    if abs(o3) <= eps and collinear(r, s, p): return True
    if abs(o4) <= eps and collinear(r, s, q): return True
    return False


def _point_in_triangle(pt, a, b, c, eps=1e-14) -> bool:
    """
    Barycentric test (includes boundary).
    """
    v0 = c - a; v1 = b - a; v2 = pt - a
    den = v0[0]*v1[1] - v0[1]*v1[0]
    if abs(den) < eps:
        return False
    u = (v2[0]*v1[1] - v2[1]*v1[0]) / den
    v = (v2[0]*v0[1] - v2[1]*v0[0]) / -den
    w = 1.0 - u - v
    return (u >= -eps) and (v >= -eps) and (w >= -eps)


def _point_in_quad(pt, q4, eps=1e-14) -> bool:
    """
    Quad membership as union of two triangles (0-1-2) ∪ (0-2-3).
    """
    a, b, c, d = q4
    return _point_in_triangle(pt, a, b, c, eps) or _point_in_triangle(pt, a, c, d, eps)


# ------------------------------------------------------------------------------------
# 1) duplicate_elements
# ------------------------------------------------------------------------------------
def duplicate_elements(mv, th, cache) -> Dict:
    """
    Identify duplicate elements with identical node sets.
    Implements hash-based dedup for tris/quads (lexicographically sorted nodes).
    Returns examples as ("tri"/"quad", local_index).
    """
    dup_ids = []

    # Triangles
    if mv.tris is not None and len(mv.tris):
        tri_sorted = np.sort(mv.tris, axis=1)
        # lexicographic hashing
        keys = tri_sorted[:, 0].astype(np.int64) * 73856093 \
             ^ tri_sorted[:, 1].astype(np.int64) * 19349663 \
             ^ tri_sorted[:, 2].astype(np.int64) * 83492791
        _, first_idx, counts = np.unique(keys, return_index=True, return_counts=True)
        dup_mask = np.zeros(len(tri_sorted), dtype=bool)
        # mark duplicates (all beyond the first occurrence per key)
        for idx, cnt in zip(first_idx, counts):
            if cnt > 1:
                dup_mask[idx+1: idx+cnt] = True
        dup_ids.extend([("tri", i) for i in np.nonzero(dup_mask)[0].tolist()])

    # Quads
    if mv.quads is not None and len(mv.quads):
        q_sorted = np.sort(mv.quads, axis=1)
        keys = q_sorted[:, 0].astype(np.int64) * 73856093 \
             ^ q_sorted[:, 1].astype(np.int64) * 19349663 \
             ^ q_sorted[:, 2].astype(np.int64) * 83492791 \
             ^ q_sorted[:, 3].astype(np.int64) * 2654435761
        _, first_idx, counts = np.unique(keys, return_index=True, return_counts=True)
        dup_mask = np.zeros(len(q_sorted), dtype=bool)
        for idx, cnt in zip(first_idx, counts):
            if cnt > 1:
                dup_mask[idx+1: idx+cnt] = True
        dup_ids.extend([("quad", i) for i in np.nonzero(dup_mask)[0].tolist()])

    ok = len(dup_ids) == 0
    return _finding(
        "duplicate_elements",
        ok=ok,
        count=len(dup_ids),
        examples=dup_ids[:20],
        details={"note": "Duplicate elements share identical node sets."},
        fixable=True,
    )


# ------------------------------------------------------------------------------------
# 2) surface_orientation
# ------------------------------------------------------------------------------------
def surface_orientation(mv, th, cache) -> Dict:
    """
    Flag cells with negative signed area (CW winding) in XY.
    Triangles via 2D cross; quads via polygon shoelace area.
    Orientation only; degeneracy handled elsewhere.
    """
    bad = []

    if mv.tris is not None and len(mv.tris):
        tri_pts = mv.points[mv.tris]  # (T,3,2)
        areas = 0.5 * ( (tri_pts[:,1,0]-tri_pts[:,0,0])*(tri_pts[:,2,1]-tri_pts[:,0,1])
                      - (tri_pts[:,1,1]-tri_pts[:,0,1])*(tri_pts[:,2,0]-tri_pts[:,0,0]) )
        bad.extend([("tri", i) for i in np.nonzero(areas < 0.0)[0].tolist()])

    if mv.quads is not None and len(mv.quads):
        q_pts = mv.points[mv.quads]  # (Q,4,2)
        # polygon signed area
        x = q_pts[..., 0]; y = q_pts[..., 1]
        areas = 0.5 * ((x * np.roll(y, -1, axis=1)) - (y * np.roll(x, -1, axis=1))).sum(axis=1)
        bad.extend([("quad", i) for i in np.nonzero(areas < 0.0)[0].tolist()])

    ok = len(bad) == 0
    return _finding(
        "surface_orientation",
        ok=ok,
        count=len(bad),
        examples=bad[:20],
        details={"note": "Negative signed area implies CW orientation in XY plane."},
        fixable=True,
    )


# ------------------------------------------------------------------------------------
# 3) negative_jacobians
# ------------------------------------------------------------------------------------
def negative_jacobians(mv, th, cache):
    """
    Detect truly invalid elements:
      • Triangles: zero/near-zero area (degenerate).
      • Quads: zero/near-zero area or bow-tie (self-intersecting opposite edges).
    Orientation is NOT penalized here (handled by surface_orientation).
    """
    import numpy as np

    eps = float(th.get("collinear_eps", 1e-12))
    pts = mv.points

    bad = []  # list of ("tri"| "quad", local_index)

    # --- Triangles: area near zero means degenerate
    if mv.tris is not None and len(mv.tris):
        tri = pts[mv.tris]  # (T,3,2)
        a = 0.5 * np.abs(
            (tri[:, 1, 0] - tri[:, 0, 0]) * (tri[:, 2, 1] - tri[:, 0, 1])
            - (tri[:, 1, 1] - tri[:, 0, 1]) * (tri[:, 2, 0] - tri[:, 0, 0])
        )
        bad_tris = np.nonzero(a <= eps)[0]
        for i in bad_tris:
            bad.append(("tri", int(i)))

    # --- Quads: area near zero OR self-intersecting edges (bow-tie)
    if mv.quads is not None and len(mv.quads):
        Q = pts[mv.quads]  # (Q,4,2)
        # shoelace area
        area = (
            Q[:, 0, 0] * Q[:, 1, 1] - Q[:, 0, 1] * Q[:, 1, 0]
            + Q[:, 1, 0] * Q[:, 2, 1] - Q[:, 1, 1] * Q[:, 2, 0]
            + Q[:, 2, 0] * Q[:, 3, 1] - Q[:, 2, 1] * Q[:, 3, 0]
            + Q[:, 3, 0] * Q[:, 0, 1] - Q[:, 3, 1] * Q[:, 0, 0]
        ) * 0.5
        degenerate = np.nonzero(np.abs(area) <= eps)[0]

        # bow-tie: opposite edges cross -> (0-1) with (2-3) or (1-2) with (3-0)
        bow = []
        for qi, P in enumerate(Q):
            p0, p1, p2, p3 = P[0], P[1], P[2], P[3]
            if segments_intersect(p0, p1, p2, p3, eps) or segments_intersect(p1, p2, p3, p0, eps):
                bow.append(qi)

        bad_quads = set(map(int, degenerate)) | set(map(int, bow))
        for i in sorted(bad_quads):
            bad.append(("quad", int(i)))

    ok = len(bad) == 0
    return {
        "id": "negative_jacobians",
        "severity": "error",
        "ok": ok,
        "count": len(bad),
        "examples": bad[:20],
        "details": {"note": "Flags only degenerate or self-intersecting elements; orientation is allowed."},
        "fixable": True,
    }


# ------------------------------------------------------------------------------------
# 4) overlapping_elements
# ------------------------------------------------------------------------------------
def overlapping_elements(mv, th, cache):
    """
    Report pairs of non-adjacent cells whose polygons intersect or one contains
    the other. Candidates from spatial grid; shared edges are excluded.
    Uses edge-edge tests and centroid-in-polygon heuristics (tri/quad).
    """

    pts = mv.points
    unified = cache.get("unified_cells", [])
    cell_edges = cache.get("cell_edges", {})
    grid = cache.get("spatial_grid", None)
    if grid is None:
        return {
            "id": "overlapping_elements",
            "severity": "error",
            "ok": True,
            "count": 0,
            "examples": [],
            "details": {"skipped": "no spatial grid"},
            "fixable": True,
        }

    # helper: does cell have an edge (u,v)?
    def _share_edge(i, j):
        ei = set(cell_edges.get(i, []))
        ej = set(cell_edges.get(j, []))
        return len(ei.intersection(ej)) > 0

    # helper: iterate polygon edge segments
    def _edges_of(conn):
        k = len(conn)
        for t in range(k):
            u = int(conn[t])
            v = int(conn[(t + 1) % k])
            yield (u, v), pts[u], pts[v]

    overlaps = []

    # We’ll also need simple point-in-polygon using our helpers for tri/quad
    def _centroid_coords(conn):
        P = pts[conn]
        return P.mean(axis=0)

    for i, conn_i in enumerate(unified):
        for j in grid.neighbors(i):  # j > i by construction
            conn_j = unified[j]

            # Skip true neighbors (shared edge): not an overlap, just adjacency
            if _share_edge(i, j):
                continue

            # Edge-edge intersection?
            edge_hit = False
            for (_, a0, a1) in _edges_of(conn_i):
                for (_, b0, b1) in _edges_of(conn_j):
                    # If they merely touch at a point, it's still an intersection;
                    # that's usually benign, but for non-adjacent cells it indicates conflict.
                    if segments_intersect(a0, a1, b0, b1, th.get("collinear_eps", 1e-12)):
                        edge_hit = True
                        break
                if edge_hit:
                    break

            if edge_hit:
                overlaps.append((i, j))
                continue

            # Containment test (either centroid inside the other)
            ci = _centroid_coords(conn_i)
            cj = _centroid_coords(conn_j)

            inside = False
            if len(conn_i) == 3 and len(conn_j) == 3:
                inside = point_in_triangle(ci, pts[conn_j[0]], pts[conn_j[1]], pts[conn_j[2]]) or \
                         point_in_triangle(cj, pts[conn_i[0]], pts[conn_i[1]], pts[conn_i[2]])
            elif len(conn_i) == 4 and len(conn_j) == 4:
                inside = point_in_quad(ci, pts[conn_j]) or point_in_quad(cj, pts[conn_i])
            else:
                # mixed tri-quad: test both ways using tri/quad helpers
                if len(conn_i) == 3 and len(conn_j) == 4:
                    inside = point_in_quad(ci, pts[conn_j]) or \
                             point_in_triangle(cj, pts[conn_i[0]], pts[conn_i[1]], pts[conn_i[2]])
                elif len(conn_i) == 4 and len(conn_j) == 3:
                    inside = point_in_triangle(ci, pts[conn_j[0]], pts[conn_j[1]], pts[conn_j[2]]) or \
                             point_in_quad(cj, pts[conn_i])

            if inside:
                overlaps.append((i, j))

    ok = len(overlaps) == 0
    return {
        "id": "overlapping_elements",
        "severity": "error",
        "ok": ok,
        "count": len(overlaps),
        "examples": overlaps[:20],
        "details": {"note": "Excludes shared edges; counts real overlaps or containment only."},
        "fixable": True,
    }


# ------------------------------------------------------------------------------------
# 5) uncovered_faces (holes)
# ------------------------------------------------------------------------------------
def uncovered_faces(mv, th, cache):
    """
    Edges with degree 1 that are NOT marked as boundary edges.
    Requires `boundary_edges` and `edge_cells` in cache; otherwise skipped.
    """
    edge_cells = cache.get("edge_cells", {})
    boundary_edges = cache.get("boundary_edges", None)

    if boundary_edges is None:
        return {
            "id": "uncovered_faces",
            "severity": "error",
            "ok": True,
            "count": 0,
            "examples": [],
            "details": {"skipped": "boundary edges not provided"},
            "fixable": True,
        }

    uncovered = []
    for e, cells in edge_cells.items():
        if len(cells) == 1 and e not in boundary_edges:
            uncovered.append(e)

    ok = len(uncovered) == 0
    return {
        "id": "uncovered_faces",
        "severity": "error",
        "ok": ok,
        "count": len(uncovered),
        "examples": uncovered[:20],
        "details": {"note": "degree-1 non-boundary edges should not exist"},
        "fixable": True,
    }


# ------------------------------------------------------------------------------------
# 6) missing_internal_faces (T-junctions)
# ------------------------------------------------------------------------------------
def missing_internal_faces(mv, th, cache):
    """
    Internal edges must be shared by exactly two cells.
    Flags edges with degree ≠ 2 after excluding boundary edges.
    Requires `boundary_edges` and `edge_cells` in cache.
    """
    edge_cells = cache.get("edge_cells", {})
    boundary_edges = cache.get("boundary_edges", None)

    if boundary_edges is None:
        return {
            "id": "missing_internal_faces",
            "severity": "error",
            "ok": True,
            "count": 0,
            "examples": [],
            "details": {"skipped": "boundary edges not provided"},
            "fixable": True,
        }

    bad = []
    for e, cells in edge_cells.items():
        if e in boundary_edges:
            continue  # boundary can be degree 1
        if len(cells) != 2:
            bad.append((e, tuple(cells)))

    ok = len(bad) == 0
    return {
        "id": "missing_internal_faces",
        "severity": "error",
        "ok": ok,
        "count": len(bad),
        "examples": bad[:20],
        "details": {"note": "internal edges must be shared by exactly two cells"},
        "fixable": True,
    }


# ------------------------------------------------------------------------------------
# 7) multiple_edges (parallel duplicates between same nodes)
# ------------------------------------------------------------------------------------
def multiple_edges(mv, th, cache) -> Dict:
    """
    Duplicate undirected topological edges between the same node pair (u < v).
    Aggregates counts from `edge_cells` keys and flags edges with count > 1.
    """
    edge_cells = cache.get("edge_cells", {})
    counts = {}
    for e in edge_cells.keys():
        counts[e] = counts.get(e, 0) + 1
    dups = [e for e, c in counts.items() if c > 1]

    ok = len(dups) == 0
    return _finding(
        "multiple_edges",
        ok=ok,
        count=len(dups),
        examples=dups[:20],
        details={"note": "More than one topological edge between the same two nodes."},
        fixable=True,
    )


# ------------------------------------------------------------------------------------
# 8) nonmanifold (edges>2 cells or impossible node incidence)
# ------------------------------------------------------------------------------------
def nonmanifold(mv, th, cache) -> Dict:
    """
    Non-manifold configurations:
      • Edges incident to > 2 cells.
      • Nodes with abnormally high cell incidence (heuristic: > mean + 5σ and ≥ 8).
    Uses `edge_cells` and optionally `node_cells` from cache.
    """
    edge_cells = cache.get("edge_cells", {})
    node_cells = cache.get("node_cells", None)

    edges_gt2 = [e for e, cells in edge_cells.items() if len(cells) > 2]

    high_nodes = []
    if node_cells is not None:
        # heuristic: nodes with cell incidence >> average (e.g., > mean + 5*std)
        incidences = np.array([len(v) for v in node_cells.values()], dtype=int)
        if len(incidences) > 0:
            mu, sd = float(incidences.mean()), float(incidences.std() + 1e-9)
            thr = mu + 5.0 * sd
            for n, cells in node_cells.items():
                if len(cells) > thr and len(cells) >= 8:  # require a minimum absolute level
                    high_nodes.append(n)

    ok = (len(edges_gt2) == 0) and (len(high_nodes) == 0)
    return _finding(
        "nonmanifold",
        ok=ok,
        count=len(edges_gt2) + len(high_nodes),
        examples=[("edge", e) for e in edges_gt2[:10]] + [("node", n) for n in high_nodes[:10]],
        details={"edges_incident_gt2": len(edges_gt2), "high_incidence_nodes": len(high_nodes)},
        fixable=True,
    )


# ------------------------------------------------------------------------------------
# 9) bl_continuity (near-wall quad strip continuity, if BL present)
# ------------------------------------------------------------------------------------
def bl_continuity(mv, th, cache) -> Dict:
    """
    Boundary-layer continuity near `wall_name` (default 'airfoil').
    Advisory in v1: passes if quads exist and wall tag present; placeholder
    for stricter continuity once near-wall distance metrics are integrated.
    """
    wall = th.get("wall_name", "airfoil")
    # Expect helpers to optionally provide a near-wall classifier; if not, do a minimal check:
    quads = mv.quads
    if quads is None or len(quads) == 0:
        return _finding("bl_continuity", ok=True, count=0, examples=[], details={"skipped": "No quads present."}, fixable=False)

    # Minimal heuristic: if any line tag equals wall and there are quads adjacent to it
    has_wall = (mv.line_tags is not None) and (wall in mv.line_tags) and (len(mv.line_tags[wall]) > 0)
    if not has_wall:
        return _finding("bl_continuity", ok=True, count=0, examples=[], details={"skipped": f"Line tag '{wall}' not found."}, fixable=False)

    # Use centroid distance percentile as a proxy: near-wall band should be quad-dominant
    centroids = cache.get("centroids", {})
    quad_c = centroids.get("quad")
    if quad_c is None or len(quad_c) == 0:
        return _finding("bl_continuity", ok=True, count=0, examples=[], details={"skipped": "No quad centroids."}, fixable=False)

    # Without a true distance-to-wall function here, we only report presence (not strict continuity)
    # Integration with mesh.stats.data.bl for richer signal can be added later.
    return _finding(
        "bl_continuity",
        ok=True,  # conservative default in v1
        count=0,
        examples=[],
        details={"note": "Heuristic placeholder in v1; integrate mesh.stats.data.bl for strict continuity."},
        fixable=True,
    )


# ------------------------------------------------------------------------------------
# 10) missing_physical_groups
# ------------------------------------------------------------------------------------
def missing_physical_groups(mv, th, cache) -> Dict:
    """
    Verify required Physical Group names (and optional dimensions) using
    `mesh.validate.check_physical_groups` when `meshio` is available.
    Skips with ok=True if `meshio` is missing (details['skipped'] set).
    """
    required = th.get("required_groups", ["inlet", "outlet", "top", "bottom", "airfoil", "fluid"])
    dim_expect = th.get("group_dims", None)  # e.g., {"fluid": 2, "airfoil": 1, ...}
    strict = bool(th.get("strict_if_no_field_data", False))

    if not _HAS_MESHIO:
        # Soft skip if meshio missing; users can enable strict external validation
        return _finding(
            "missing_physical_groups",
            ok=True,
            count=0,
            examples=[],
            details={"skipped": "meshio not installed; cannot read field_data."},
            fixable=False,
        )

    try:
        _check_pg(
            mv.mesh_path,                     # MeshView should carry this (helpers can attach)
            required=list(required),
            kind_expectations=dim_expect,
            strict_if_no_field_data=strict,
        )
        return _finding(
            "missing_physical_groups",
            ok=True,
            count=0,
            examples=[],
            details={"checked": list(required)},
            fixable=False,
        )
    except Exception as e:
        # Parse missing names from the error message crudely
        msg = str(e)
        details = {"message": msg}
        missing = []
        for name in required:
            if name in msg and "Missing" in msg:
                missing.append(name)
        if missing:
            details["missing"] = missing
        return _finding(
            "missing_physical_groups",
            ok=False,
            count=len(missing) if missing else 1,
            examples=missing[:10],
            details=details,
            fixable=False,  # fix requires re-tagging or re-export
        )
