# -*- coding: utf-8 -*-
# Flowxus/mesh/core/generators/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 11/28/2025

Generators Subpackage:
----------------------
Mesh generator implementations providing concrete implementations of the
MeshGenerator abstract interface.

Modules:
--------
- gmsh_generator:   Gmsh-based mesh generation (current production implementation)

- custom_generator: Placeholder for future custom mesh generation algorithm

Notes:
------
- All generators implement the same MeshGenerator interface
- Enables seamless switching between different mesh generation technologies
- Maintains backward compatibility while enabling future expansion
"""

from .gmsh_generator import GmshGenerator, default_gmsh_generator
from .custom_generator import CustomGenerator

__all__ = [
    "GmshGenerator",
    "default_gmsh_generator",
    "CustomGenerator",
]
