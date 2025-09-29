# -*- coding: utf-8 -*-
# Flowxus/mesh/tools/utils.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/25/2025

Purpose
-------
Utility helpers for the meshing pipeline:
    1. Boundary-layer thickness computation for a geometric progression.
    2. Executable lookup with clear error messages and env-var override.

Main Tasks
----------
    - bl_thickness: compute total thickness from (first_layer, n_layers, growth_rate).
    - ensure_exec_on_path: find a binary via <NAME>_BIN or system PATH.

Notes:
------
    - bl_thickness handles r≈1 numerically with a tolerance (good) and returns 0.0 when n_layers==0.
    - ensure_exec_on_path correctly prefers <NAME>_BIN over PATH.
    - On Windows, users often put quotes in env vars; os.path.isfile('"C:\\path\\gmsh.exe"') returns False.
"""

import os
import shutil

def bl_thickness(first_layer, n_layers, growth_rate):
    """
    Compute total boundary-layer thickness for a geometric progression.

      thickness = a * (1 - r^N) / (1 - r)    if r != 1
                = a * N                      if r == 1

    Parameters
    ----------
    first_layer : float > 0          (ignored if n_layers == 0)
    n_layers    : int >= 0           (0 disables BL; returns 0.0)
    growth_rate : float >= 1.0       (only validated if n_layers > 0)

    Returns
    -------
    float
    """
    # Coerce to plain Python types (handles numpy scalars / strings cleanly)
    first_layer = float(first_layer)
    n_layers = int(n_layers)
    growth_rate = float(growth_rate)

    # Allow "no BL"
    if n_layers == 0:
        return 0.0

    if first_layer <= 0.0:
        raise ValueError("first_layer must be > 0.")
    if n_layers < 0:
        raise ValueError("n_layers must be >= 0.")
    if growth_rate < 1.0:
        raise ValueError("growth_rate must be >= 1.0.")

    # Guard for near-unity growth rate to avoid cancellation
    if abs(growth_rate - 1.0) < 1e-12:
        return first_layer * n_layers

    return first_layer * (1.0 - (growth_rate ** n_layers)) / (1.0 - growth_rate)


def ensure_exec_on_path(exe_name):
    """
    Find an executable on PATH (or via env var) or raise a clear error.

    Checks the environment variable '<NAME>_BIN' first (uppercased), then PATH.

    Parameters
    ----------
    exe_name : str
        Name of the executable, e.g. 'gmsh'.

    Returns
    -------
    str
        Absolute path to the executable.

    Raises
    ------
    RuntimeError
        If the executable is not found on the system PATH.
    """
    # Allow overrides like GMSH_BIN
    env_key = (exe_name + "_BIN").upper()
    candidate = os.environ.get(env_key)
    if candidate:
        candidate = candidate.strip().strip('"').strip("'")  # <- add this
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):  # <- add exec check
            return os.path.abspath(candidate)

    exe = shutil.which(exe_name) or shutil.which(exe_name + ".exe")
    if exe is None:
        raise RuntimeError(
            "'{}' not found on PATH. "
            "Install it or set the {} environment variable to its full path."
            .format(exe_name, env_key)
        )
    return os.path.abspath(exe)
