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

- ops:      Package of lightweight geometry utilities (backward-compatible import path).
              * Submodules:
                  - ops.basic:    LE/TE/chord queries, normalization, cumulative arclength,
                                   drop_consecutive_duplicates.
                  - ops.analysis: curvature_polyline, dist_along_curve.
              * Re-exports (from topology) for a single source of truth:
                  ensure_closed, signed_area, orientation, le_te_indices.

- topology: Connectivity-level operations on closed loops (airfoils and similar):
              * Closure predicates and enforcement,
              * Signed area, orientation, and CCW sorting,
              * Deterministic LE/TE index detection with tie-breaking,
              * Suction/pressure side partitioning (rotation-invariant).

- api:       Minimal public facade for common tasks used in main scripts.
              * load_and_normalize(filename, translate_to_le=True, scale_to_chord1=True)
                    → returns a GeometryLoader (closed + CCW + optionally normalized)
              * build_farfield_domain(geo, box_dims)
                    → returns a DomainBuilder configured with up/down/front/back distances
              * write_geo_and_csv(domain, export_path="domain.geo", emit_metadata=True,
                                  emit_scalars_csv=True, scalars_path="airfoil_scalars.csv",
                                  provenance=None)
                    → writes the geometry-only .geo (and optional CSV) and returns the .geo path

            Usage:
                from geometry.api import load_and_normalize, build_farfield_domain, write_geo_and_csv

"""

__all__ = ["domain", "geo", "loaders", "metrics", "ops", "topology", "api"]
