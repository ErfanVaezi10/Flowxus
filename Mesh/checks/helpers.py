# -*- coding: utf-8 -*-
# Flowxus/mesh/check/helpers.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
Provide the shared data model (`MeshView`) and one-time precomputations
(`precompute_cache`) used by all mesh checks. These structures give checks
fast, consistent access to connectivity, adjacency, and geometry.

Main Tasks:
-----------
- MeshView: immutable container built from `mesh.stats.data.reader.read(msh_path)`.
- precompute_cache: build adjacency/geometry maps reused across rules:
    * edge_cells:  {(u,v): [cell_ids]} with u < v (undirected edges).
    * cell_edges:  {cell_id: [(u,v), ...]} for unified cell indexing.
    * node_cells:  {node_id: [cell_ids]} (node → incident cells).
    * centroids:   {"tri": (T,2), "quad": (Q,2)} arrays of XY centroids.
    * cell_bboxes: (C,4) array of AABBs (ax0, ay0, ax1, ay1) per unified cell.
    * spatial_grid: spatial hash / grid for neighbor candidate lookup.
    * boundary_edges (optional): set{(u,v)} if line connectivity is available.

Unification Convention:
-----------------------
- Unified cell ids enumerate all tris first (0..T−1), then all quads (T..T+Q−1).
- All maps in the cache that key by cell id (e.g. `cell_edges`) use this unified indexing.

Notes:
------
- Scope: 2D surface meshes (tris/quads).
- `MeshView` is read-only; checks should not mutate it.
- Cache objects are shared across all rules in a validation pass to avoid recomputation.
"""


from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Iterable
import numpy as np
from typing import Any, cast
from mesh.stats.data.reader import read as _read_mesh


# -------------------------
# Small utility primitives
# -------------------------
def hash_edge(u: int, v: int) -> Tuple[int, int]:
    """Undirected edge key with sorted endpoints."""
    return (u, v) if u < v else (v, u)


def _bbox_xy(coords: np.ndarray) -> Tuple[float, float, float, float]:
    """Axis-aligned bounding box (minx, miny, maxx, maxy) for (k,2) coords."""
    x = coords[:, 0]; y = coords[:, 1]
    return (float(x.min()), float(y.min()), float(x.max()), float(y.max()))


def _centroid(coords: np.ndarray) -> np.ndarray:
    """Average of vertices as a simple centroid (works for tri/quad)."""
    return coords.mean(axis=0)


# -------------------------
# Spatial grid for overlaps
# -------------------------
class _Grid:
    """
    Lightweight uniform spatial grid over cell AABBs for candidate neighbor queries.

    Build once with all cell bboxes; neighbors(i) yields candidate j ≠ i that
    share at least one grid bin with i (not guaranteed intersecting—just candidates).
    """

    __slots__ = ("_bins", "_nx", "_ny", "_x0", "_y0", "_dx", "_dy", "_n")

    def __init__(self, bboxes: np.ndarray, nx: int = 96, ny: Optional[int] = None):
        if bboxes is None or len(bboxes) == 0:
            # empty mesh
            self._bins = {}
            self._nx = self._ny = 1
            self._x0 = self._y0 = 0.0
            self._dx = self._dy = 1.0
            self._n = 0
            return

        self._n = int(len(bboxes))
        x0 = float(bboxes[:, 0].min()); y0 = float(bboxes[:, 1].min())
        x1 = float(bboxes[:, 2].max()); y1 = float(bboxes[:, 3].max())
        self._x0, self._y0 = x0, y0
        self._nx = int(max(1, nx))
        self._ny = int(max(1, ny if ny is not None else nx))
        self._dx = (x1 - x0) / self._nx if self._nx > 0 else 1.0
        self._dy = (y1 - y0) / self._ny if self._ny > 0 else 1.0

        bins: Dict[Tuple[int, int], List[int]] = {}
        for cid, (ax0, ay0, ax1, ay1) in enumerate(bboxes):
            ix0 = self._clamp_x(ax0); iy0 = self._clamp_y(ay0)
            ix1 = self._clamp_x(ax1); iy1 = self._clamp_y(ay1)
            for ix in range(ix0, ix1 + 1):
                for iy in range(iy0, iy1 + 1):
                    bins.setdefault((ix, iy), []).append(cid)
        self._bins = bins

    def _clamp_x(self, x: float) -> int:
        """Map X to integer grid column index, clamped to [0, _nx-1] (robust to zero `_dx`)."""
        ix = int((x - self._x0) / (self._dx if self._dx != 0.0 else 1.0))
        return max(0, min(self._nx - 1, ix))

    def _clamp_y(self, y: float) -> int:
        """Map Y to integer grid row index, clamped to [0, _ny-1] (robust to zero `_dy`)."""
        iy = int((y - self._y0) / (self._dy if self._dy != 0.0 else 1.0))
        return max(0, min(self._ny - 1, iy))

    def neighbors(self, cid: int) -> Iterable[int]:
        """Candidate neighbors for cell cid (excluding cid)."""
        # find bins this bbox occupies; union their contents
        # we don't store per-cell bin list; compute on the fly
        # (cheap: only a few divisions/ints)
        # This relies on the caller having access to the global bboxes.
        # We'll keep bboxes external; orchestrator passes a partial to checks that need it.
        # For simplicity in v1, we iterate over adjacent bins by scanning all bins—still fast for moderate meshes.
        # For better perf, pass bboxes into grid and cache per-cell bins; omitted in v1 for brevity.
        # Here we just return all cells; checks can deduplicate or filter if needed.
        # To make neighbors useful, we will override neighbors in precompute_cache to a closure
        # that uses the actual bboxes; see precompute_cache().
        raise NotImplementedError("Use the neighbors closure from precompute_cache()")


# -------------------------
# Mesh view
# -------------------------
@dataclass(frozen=True)
class MeshView:
    mesh_path: str
    points: np.ndarray            # (N,2)
    tris: Optional[np.ndarray]    # (T,3) or None
    quads: Optional[np.ndarray]   # (Q,4) or None
    cell_tags: Dict[str, np.ndarray]   # name -> cell indices (per cell block)
    line_tags: Dict[str, np.ndarray]   # name -> line indices (if available)
    bbox: Tuple[float, float, float, float]


def build_mesh_view(msh_path: str) -> MeshView:
    """
    Read mesh via existing reader and wrap into an immutable MeshView.
    """
    m = _read_mesh(msh_path)  # MeshData from mesh.stats.data.reader
    # The reader returns points (N,3 or N,2?) — we assume XY; drop Z if present
    pts = np.asarray(m.points, dtype=float)
    if pts.shape[1] > 2:
        pts = pts[:, :2].copy()

    tris = None
    quads = None
    if getattr(m, "tris", None) is not None and len(m.tris):
        tris = np.asarray(m.tris, dtype=np.int64)
    if getattr(m, "quads", None) is not None and len(m.quads):
        quads = np.asarray(m.quads, dtype=np.int64)

    # Tags are already dicts of name -> indices (per reader contract)
    cell_tags = dict(getattr(m, "cell_tags", {}) or {})
    line_tags = dict(getattr(m, "line_tags", {}) or {})
    bbox = tuple(getattr(m, "bbox", (float(pts[:,0].min()), float(pts[:,1].min()),
                                     float(pts[:,0].max()), float(pts[:,1].max()))))

    return MeshView(
        mesh_path=msh_path,
        points=pts,
        tris=tris,
        quads=quads,
        cell_tags=cell_tags,
        line_tags=line_tags,
        bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
    )


# -------------------------
# Precomputations (cache)
# -------------------------
def _build_unified_cells(tris: Optional[np.ndarray], quads: Optional[np.ndarray]) -> List[np.ndarray]:
    """
    Return list of connectivity arrays for unified indexing: all tris then all quads.
    """
    items: List[np.ndarray] = []
    if tris is not None and len(tris):
        for conn in tris:
            items.append(np.asarray(conn, dtype=np.int64))
    if quads is not None and len(quads):
        for conn in quads:
            items.append(np.asarray(conn, dtype=np.int64))
    return items


def _build_cell_bboxes(points: np.ndarray, unified_cells: List[np.ndarray]) -> np.ndarray:
    """Compute per-cell AABBs (ax0, ay0, ax1, ay1) in XY for all unified cells."""
    bboxes = np.zeros((len(unified_cells), 4), dtype=float)
    for cid, conn in enumerate(unified_cells):
        bboxes[cid, :] = _bbox_xy(points[conn])
    return bboxes


def _build_cell_edges(unified_cells: List[np.ndarray]) -> Dict[int, List[Tuple[int, int]]]:
    """
    For each unified cell id, list its (undirected) edges as (u,v) with u<v.
    """
    cell_edges: Dict[int, List[Tuple[int, int]]] = {}
    for cid, conn in enumerate(unified_cells):
        k = len(conn)
        edges = []
        for i in range(k):
            u = int(conn[i]); v = int(conn[(i+1) % k])
            edges.append(hash_edge(u, v))
        cell_edges[cid] = edges
    return cell_edges


def _build_edge_cells(cell_edges: Dict[int, List[Tuple[int, int]]]) -> Dict[Tuple[int, int], List[int]]:
    """
    Invert cell_edges to edge->cells.
    """
    edge_cells: Dict[Tuple[int, int], List[int]] = {}
    for cid, edges in cell_edges.items():
        for e in edges:
            edge_cells.setdefault(e, []).append(cid)
    return edge_cells


def _build_node_cells(unified_cells: List[np.ndarray]) -> Dict[int, List[int]]:
    """Build node → incident unified cell ids: {node_id: [cell_ids, ...]}."""
    node_cells: Dict[int, List[int]] = {}
    for cid, conn in enumerate(unified_cells):
        for n in conn:
            node_cells.setdefault(int(n), []).append(cid)
    return node_cells


def _build_centroids(points: np.ndarray, tris: Optional[np.ndarray], quads: Optional[np.ndarray]) -> Dict[str, np.ndarray]:
    """Compute XY centroids for tris/quads; returns dict with keys 'tri' and/or 'quad'."""
    out: Dict[str, np.ndarray] = {}
    if tris is not None and len(tris):
        out["tri"] = np.stack([_centroid(points[t]) for t in tris], axis=0)
    if quads is not None and len(quads):
        out["quad"] = np.stack([_centroid(points[q]) for q in quads], axis=0)
    return out


def _maybe_boundary_edges(mv: MeshView) -> Optional[set]:
    """
    Try to assemble a set of boundary edges from line elements if available.
    The reader's MeshData currently exposes line_tags (name -> indices of line elements),
    but not the line connectivity explicitly. If connectivity is not available,
    return None and let checks handle the absence.
    """
    # If reader later exposes something like m.lines (K,2) and name->indices,
    # you can reconstruct edges here. For v1, return None.
    return None


def precompute_cache(mv: MeshView, cfg: Dict) -> Dict:
    """
    Build all one-time structures needed by checks.
    """
    cache: Dict[str, Any] = {}

    # Unified cells & derived structures
    unified = _build_unified_cells(mv.tris, mv.quads)
    cache["unified_cells"] = unified
    cell_edges = _build_cell_edges(unified)
    cache["cell_edges"] = cell_edges
    edge_cells = _build_edge_cells(cell_edges)
    cache["edge_cells"] = edge_cells
    node_cells = _build_node_cells(unified)
    cache["node_cells"] = node_cells

    # Centroids (kept split by type for quality/BL checks)
    cache["centroids"] = _build_centroids(mv.points, mv.tris, mv.quads)

    # AABBs for unified cells
    cell_bboxes = _build_cell_bboxes(mv.points, unified)
    cache["cell_bboxes"] = cell_bboxes

    # Spatial grid with neighbor closure that uses bboxes (fast and simple)
    nx = int(cfg.get("overlap_grid_bins", 96))
    _grid = _Grid(cell_bboxes, nx=nx, ny=None)

    # Provide a neighbors() bound method that actually uses the bboxes for cell cid
    # We compute the bin range for that cell and union candidates across those bins.
    # For v1 simplicity, approximate by returning all cells whose bbox overlaps this cell's bbox.
    # (still O(n) per cell worst-case, but fine for moderate sizes; replace later with true bin map if needed)
    def _neighbors(cid: int):
        """Yield j > cid for cells whose AABBs overlap cell `cid` (simple bbox filter)."""
        ax0, ay0, ax1, ay1 = cell_bboxes[cid]
        # Fast reject by bbox overlap
        # NOTE: This is intentionally simple; for large meshes, optimize with true grid binning.
        n = cell_bboxes.shape[0]
        # yield only j>cid to reduce pairs (caller can choose its own convention)
        for j in range(cid + 1, n):
            bx0, by0, bx1, by1 = cell_bboxes[j]
            if not (ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0):
                yield j

    class _NeighborsWrapper:
        __slots__ = ()
        def neighbors(self, cid: int):
            return _neighbors(cid)

    cache["spatial_grid"] = _NeighborsWrapper()

    # Optional: boundary edges from line connectivity (None for v1 if not available)
    cache["boundary_edges"] = _maybe_boundary_edges(mv)

    # Also useful: node->edges map (derived from edge_cells)
    node_edges = cast(Dict[int, List[Tuple[int, int]]], {})
    for (u, v) in edge_cells.keys():
        node_edges.setdefault(u, []).append((u, v))
        node_edges.setdefault(v, []).append((u, v))
    cache["node_edges"] = node_edges

    return cache
