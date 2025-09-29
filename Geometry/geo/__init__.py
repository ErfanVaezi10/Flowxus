# -*- coding: utf-8 -*-
# Flowxus/geometry/geo/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 7/18/2025 (Updated: 8/22/2025)

Modules:
--------
- geo_loader: High-level interface for loading airfoil geometries from supported formats.
              Provides normalization, chord/LE/TE utilities, and plotting.

- geo_writer: Responsible for writing Gmsh .geo files given geometry and domain information.
              Encapsulates .geo file syntax for points, splines, loops, surfaces, and physical groups.
"""

__all__ = ["geo_writer", "geo_loader"]
