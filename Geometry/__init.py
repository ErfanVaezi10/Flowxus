# -*- coding: utf-8 -*-
# Flowxus/geometry/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 7/18/2025 (Updated: 9/6/2025)

Modules:
--------
- metrics:  Package for computing airfoil metadata for meshing/ML.
              * Global descriptors (LE radius, TE thickness/wedge, max thickness/camber,
                arc length, orientation, ranges),
              * Per-vertex arrays (s, curvature, side masks, distances to LE/TE),
              * Serialization helpers to JSON (for .geo header) and CSV (for scalars).

- loaders:  Package containing format-specific readers for airfoil geometry
            (.dat, .step, .iges). Provides raw point arrays for GeometryLoader.

- geo:      Package with high-level geometry utilities:
              * geometry_loader for unified loading and normalization,
              * geo_writer for emitting geometry-only .geo files.

- domain:   Package for building rectangular far-field domains around airfoils.
            Includes DomainBuilder (setup, metadata/CSV emission) and domain_math helpers.

- ops:      Utility operations on point sets:
              1. Normalization (translation + scaling),
              2. Ensuring geometry is closed,
              3. Dropping duplicate points.

- topology: Connectivity-level operations on closed loops (airfoils and similar):
              * Closure predicates and enforcement,
              * Signed area, orientation, and CCW sorting,
              * Deterministic LE/TE index detection with tie-breaking,
              * Suction/pressure side partitioning (rotation-invariant).
"""

__all__ = ["domain", "geo", "loaders", "metrics", "ops", "topology"]
