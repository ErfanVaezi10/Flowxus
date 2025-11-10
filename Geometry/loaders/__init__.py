# -*- coding: utf-8 -*-
# Flowxus/geometry/loaders/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 6/14/2025 (Updated: 11/10/2025)

Loaders Subpackage:
-------------------
File format-specific loaders for importing airfoil geometry data.

Modules:
--------
- dat_loader:  Robust parser for `.dat` airfoil files (handles headers, comments, and commas/whitespace).

- iges_loader: Loader for IGES geometry via Gmsh OCC interface.

- step_loader: Loader for STEP geometry via Gmsh OCC interface.

- _helpers: Shared utility functions for CAD loaders (entity deduplication and curve evaluation).

Assumptions & Notes:
--------------------
- IGES and STEP loaders sample curves into (x, y) point arrays
- Primary interface: `GeometryLoader` provides unified API across all formats
- Units: Native file units preserved; no automatic rescaling
- Planarity: IGES/STEP loaders assume planar geometry (z-coordinate dropped)
- Data extraction: Only first two numeric columns used as (x, y) coordinates
- Topology: No automatic curve reordering or stitching performed

"""

__all__ = ["dat_loader", "iges_loader", "step_loader"]
