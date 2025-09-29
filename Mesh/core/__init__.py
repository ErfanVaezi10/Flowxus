# -*- coding: utf-8 -*-
# Flowxus/mesh/core/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Modules:
--------
- fields: Emit Gmsh field definitions:
            1. Distance & Threshold taper near airfoil,
            2. Optional per-vertex MeshSize pins,
            3. Optional BoundaryLayer extrusion with quads,
            4. Per-edge Thresholds for farfield boundaries.

- runner: Call the Gmsh binary (`gmsh`) on a `.geo` file to produce a `.msh`.
          Handles CLI construction, binary lookup, and result validation.

- writer: Assemble `.geo` scripts for Gmsh by combining geometry (airfoil + farfield)
          and mesh-sizing fields (Thresholds, BoundaryLayer, per-edge).
"""

from .writer import gmsh_geo_from_domain, write_geo_file
from .runner import mesh_geo

__all__ = ["gmsh_geo_from_domain", "write_geo_file", "mesh_geo"]
