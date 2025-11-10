# -*- coding: utf-8 -*-
# Flowxus/geometry/geo/dispatcher.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 11/10/2025

Purpose:
--------
Centralized file format routing system that decouples format detection from geometry
loading logic, enabling clean separation of concerns and easy extension.

Main Tasks:
-----------------------
    1. Map file extensions to appropriate loader functions from the loaders subpackage
    2. Provide consistent error handling for unsupported file formats
    3. Maintain a single source of truth for supported format-to-loader mappings
"""

from typing import Callable
from ..loaders.dat_loader import load_dat
from ..loaders.step_loader import load_step
from ..loaders.iges_loader import load_iges


def get_loader_function(file_extension: str) -> Callable:
    """
    Route file extension to appropriate loader function.

    Parameters
    ----------
    file_extension : str
        File extension including dot (e.g., '.dat', '.stp')

    Returns
    -------
    Callable
        Loader function for the specified file format

    Raises
    ------
    ValueError
        If file extension is not supported
    """
    extension_map = {
        ".dat": load_dat,
        ".stp": load_step,
        ".step": load_step,
        ".igs": load_iges,
        ".iges": load_iges,
    }

    loader = extension_map.get(file_extension.lower())
    if loader is None:
        raise ValueError(f"Unsupported file type: {file_extension}")

    return loader
