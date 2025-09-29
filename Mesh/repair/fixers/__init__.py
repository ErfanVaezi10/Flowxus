# -*- coding: utf-8 -*-
# Flowxus/mesh/repair/fixers/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 7/18/2025 (Updated: 9/6/2025)


Modules
-------
- duplicates:  Remove exact duplicate elements (keep first).

- multi_edges: Dedupe oversubscribed edges (>2 incident cells).

- orientation: Reorient cells to counter-clockwise (CCW).
"""

__all__ = ["duplicates", "multi_edges", "orientation"]
