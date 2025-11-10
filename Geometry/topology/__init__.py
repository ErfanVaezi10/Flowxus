# -*- coding: utf-8 -*-
# Flowxus/geometry/topology/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025 (Updated: 9/5/2025)

Topology Subfolder:
-------------------
Geometric topology operations for closed 2D loops including orientation analysis,
feature detection, and boundary segmentation.

Modules:
--------
- loop:    Closure predicates, signed area, orientation, CCW enforcement.

- indices: Deterministic LE/TE index detection with tie-breaking.

- split:   Partition loop into suction/pressure sides; rotation-stable labeling.
"""

__all__ = ["indices", "loop", "split"]
