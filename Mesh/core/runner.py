# -*- coding: utf-8 -*-
# Flowxus/mesh/core/runner.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/26/2025 (Updated: 11/11/2025)

Purpose:
--------
Mesh execution orchestration that works with any MeshGenerator implementation.
Provides the high-level API while delegating to specific generators.

Main Tasks:
-----------
    1. Provide backward-compatible API for existing mesh_geo() function
    2. Orchestrate mesh generation using configured MeshGenerator
    3. Handle default generator selection (Gmsh)
    4. Maintain identical error handling and validation

Notes:
------
- This module now serves as an orchestrator rather than Gmsh-specific code
- Can work with GmshGenerator, CustomGenerator, or any MeshGenerator
- All external APIs are preserved for zero breaking changes
"""

from typing import Dict, Optional, Union
from .generators.gmsh_generator import default_gmsh_generator
from .base import MeshGenerator


def mesh_geo(
        *,
        geo_path: str,
        msh_path: str,
        dim: int = 2,
        algo: Optional[int] = None,
        extra_cli: Optional[Dict[str, Union[int, float, str]]] = None,
        gmsh_bin: Optional[str] = None,
        msh_format: str = "msh4",
        mesh_generator: Optional[MeshGenerator] = None,
) -> str:
    """
    Run mesh generation on a `.geo` file and write a `.msh` mesh to disk.

    Parameters
    ----------
    geo_path : str
        Path to the input Gmsh script produced by the writer
        (e.g., "mesh/mesh_ready.geo").
    msh_path : str
        Destination for the generated mesh (e.g., "mesh/domain.msh").
    dim : int, optional
        Mesh dimensionality flag for Gmsh (-1/-2/-3). For 2D surface meshing
        use 2 (default).
    algo : int, optional
        If provided, forces a specific surface meshing algorithm via
        `-setnumber Mesh.Algorithm <algo>`. Examples:
        - 6: Frontal-Delaunay (triangles)
        - 8: Frontal-Delaunay for quads
    extra_cli : Dict[str, Union[int, float, str]], optional
        Extra Gmsh options to inject as `-setnumber key value` (for numeric
        values) or `-setstring key value` (for non-numerics).
    gmsh_bin : str, optional
        Explicit path to the Gmsh executable. If not provided, the function
        uses the environment variable `GMSH_BIN` and then falls back to
        searching the system PATH.
    msh_format : str, optional
        Output mesh format: "msh2" or "msh4" (default "msh4").
    mesh_generator : MeshGenerator, optional
        Mesh generator instance to use. If None, uses default Gmsh generator.

    Returns
    -------
    str
        The output mesh path (`msh_path`), if mesh generation completed successfully.

    Raises
    ------
    FileNotFoundError
        If `geo_path` does not exist.
    ValueError
        If `msh_format` is not "msh2" or "msh4".
    RuntimeError
        If mesh generation returns a non-zero code, or if the resulting file is missing
        or suspiciously small.

    Notes
    -----
    - This function now works with any MeshGenerator implementation
    - By default, uses GmshGenerator for backward compatibility
    - The command is run with `-save -nopopup -v 2` for reproducible
      batch behavior and moderate verbosity when using GmshGenerator.
    """
    # Use default Gmsh generator if none provided (backward compatibility)
    generator = mesh_generator or default_gmsh_generator

    # Prepare settings for the generator
    settings = {
        'dim': dim,
        'algo': algo,
        'extra_cli': extra_cli,
        'gmsh_bin': gmsh_bin,
        'msh_format': msh_format,
    }

    # Remove None values to avoid passing them to the generator
    settings = {k: v for k, v in settings.items() if v is not None}

    # Execute mesh generation using the configured generator
    return generator.generate_mesh(geo_path, msh_path, settings)
