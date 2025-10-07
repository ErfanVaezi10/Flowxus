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

from .history import read_history, read_last_n, last_row, tail_follow
from .formats import open_text, sniff_delim
from .io import msh_to_su2

__all__ = ["read_history","read_last_n","last_row","tail_follow",
           "open_text","sniff_delim","msh_to_su2"]


