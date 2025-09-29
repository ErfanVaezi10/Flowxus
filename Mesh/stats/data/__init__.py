# -*- coding: utf-8 -*-
# Flowxus/mesh/stats/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Modules:
--------
- reader:    mesh IO → MeshData (points, cells, tags, bbox).
- topology:  inventory & connectivity (counts, valence, area).
- quality:   element quality for tris/quads; summaries.
- bl:        boundary-layer conformance (presence, heights, growth).
- sizefield: grading & h(d) profiles relative to wall distance.
"""

__all__ = ["reader", "topology", "quality", "bl", "sizefield"]
