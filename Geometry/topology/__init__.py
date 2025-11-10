# -*- coding: utf-8 -*-
# Flowxus/geometry/topology/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025 (Updated: 11/10/2025)

Topology Subfolder:
-------------------
Geometric topology operations for closed 2D loops including orientation analysis,
feature detection, and boundary segmentation.

Modules:
--------
- loop:        Closure predicates and enforcement, signed area calculation,
               orientation detection (CW/CCW), and CCW canonicalization.

- indices:     Deterministic LE/TE index detection with explicit tie-breaking,
               chord alignment validation, and degenerate geometry handling.

- split:       Partition closed loops into pressure/suction sides with rotation-
               stable labeling, path extraction, and range conversion utilities.

- _validation: Shared validation utilities for geometry quality checking including
               array structure validation, closure verification, and finite values.
"""

__all__ = ["indices", "loop", "split"]
