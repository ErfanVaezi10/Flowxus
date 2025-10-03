# -*- coding: utf-8 -*-
# Flowxus/post/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 7/18/2025 (Updated: 10/3/2025)

Modules:
--------
- plot_geo:    Common plotting routines for geometry and domain visualization.
               Wraps matplotlib for airfoil, bounding box, and tag visualization.

- plot_mesh:   Quick 2D mesh visualization (nodes & elements) for .msh (MSH2/MSH4)
               Uses meshio + matplotlib; headless-safe backend, optional down sampling for huge meshes

- plot_stats:  Mesh-quality statistics and diagnostic plots.
               Histograms/bars for valence, angles, aspect, skewness; ⟨h⟩ vs. wall distance.

- post_solver: Solver history parsing and summary for SU2-style logs.
               Auto-reads CSV/whitespace (incl. .gz), normalizes headers, extracts residuals.

- plot_post:   Under development!
               Under development!
"""

__all__ = ["plot_geo", "plot_mesh", "plot_stats", "post_solver", "plot_post"]
