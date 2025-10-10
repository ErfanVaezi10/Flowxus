# -*- coding: utf-8 -*-
# Flowxus/geometry/ops/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 10/10/2025

Purpose
-------
Lightweight 2D geometry utilities for airfoil-like curves. This package keeps the
**public import path stable** for callers that previously did:

    from geometry.ops import <name>

so switching from a single-module layout (ops.py) to a package (ops/) requires
no changes in downstream code.

Contents
--------
- ops.basic:
    * drop_consecutive_duplicates
    * leading_edge, trailing_edge, chord_length
    * normalize
    * cumulative_arclength

- ops.analysis:
    * curvature_polyline
    * dist_along_curve

- Re-exports from topology (single source of truth):
    * ensure_closed, signed_area, orientation  (geometry.topology.loop)
    * le_te_indices                            (geometry.topology.indices)

Public API
----------
The names exported here are the stable surface used by higher-level modules
(GeometryLoader, DomainBuilder, metrics). Anything not listed in __all__ is
considered internal.
"""

from .basic import (
    drop_consecutive_duplicates,
    leading_edge,
    trailing_edge,
    chord_length,
    normalize,
    cumulative_arclength,
)
from .analysis import (
    curvature_polyline,
    dist_along_curve,
)

# Single-source these from topology to avoid duplication
from ..topology.loop import signed_area, orientation, ensure_closed
from ..topology.indices import le_te_indices

__all__ = [
    # basic
    "drop_consecutive_duplicates", "leading_edge", "trailing_edge",
    "chord_length", "normalize", "cumulative_arclength",
    # topology-sourced
    "signed_area", "orientation", "ensure_closed", "le_te_indices",
    # analysis
    "curvature_polyline", "dist_along_curve",
]
