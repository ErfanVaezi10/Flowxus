# -*- coding: utf-8 -*-
# Flowxus/geometry/loaders/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 6/14/2025 (Updated: 7/22/2025)

Modules:
--------
- dat_loader:  Robust parser for `.dat` airfoil files (handles headers, comments, and commas/whitespace).

- iges_loader: Loader for IGES geometry via Gmsh OCC interface.

- step_loader: Loader for STEP geometry via Gmsh OCC interface.

Assumptions & Notes:
--------------------
- IGES and STEP loaders sample curves into (x, y) point arrays.
- Users should go through `GeometryLoader`, which provides a unified API and integrates these loaders.
- Units: whatever the file provides; no rescaling is applied.
- Planarity: IGES/STEP samplers drop z; non-planar inputs are unsupported.
- Columns: Only the first two numeric tokens per line are used as (x, y).
- No reordering/stitching of multiple curves is performed here (see upstream).

"""

__all__ = ["dat_loader", "iges_loader", "step_loader"]
