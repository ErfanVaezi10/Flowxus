# -*- coding: utf-8 -*-
# Flowxus/solver/interface/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/18/2025 (Updated: 10/07/2025)

Modules:
--------
- formats: Provides minimal I/O helpers to read plain or gzip-compressed text files
           and detect CSV-like delimiters for SU2/Gmsh logs and histories.

- history: Parses SU2 history files into normalized, numeric arrays with canonical
           headers and supports efficient tail reading and live file following.

- io:      Converts Gmsh meshes (.msh v2/v4) to SU2 format, enforcing 2D geometry,
           preserving boundary tags, and validating output integrity.
"""

__all__ = ["history", "formats", "io"]


