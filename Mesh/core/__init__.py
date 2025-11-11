# -*- coding: utf-8 -*-
# Flowxus/mesh/core/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025 (Updated: 11/11/2025)

Core Subpackage:
----------------
Central mesh generation engine with modular architecture. Handles domain processing,
Gmsh-specific assembly, and mesh generation orchestration.

Modules:
--------
- base: Abstract interfaces for mesh generators and processors
- processor: Domain processing, validation, and data preparation
- assembler: Gmsh-specific GEO script assembly from processed data
- writer: High-level orchestrator maintaining backward-compatible API
- fields: Modular field definitions for mesh sizing control
- generators: Mesh generator implementations (Gmsh and future custom)
- runner: Mesh execution orchestration

Notes:
------
- Maintains full backward compatibility with existing APIs
- New modular architecture enables future custom mesh generators
- All external function signatures remain unchanged
"""

from .writer import gmsh_geo_from_domain, write_geo_file
from .runner import mesh_geo
from .processor import process_domain
from .assembler import assemble_geo_script
from .base import MeshGenerator, GeometryProcessor, MeshAssembler
from .generators import GmshGenerator, default_gmsh_generator, CustomGenerator

__all__ = [
    # Core API
    "gmsh_geo_from_domain",
    "write_geo_file",
    "mesh_geo",
    # Modular components
    "process_domain",
    "assemble_geo_script",
    # Abstract interfaces
    "MeshGenerator",
    "GeometryProcessor",
    "MeshAssembler",
    # Generator implementations
    "GmshGenerator",
    "default_gmsh_generator",
    "CustomGenerator",
]
