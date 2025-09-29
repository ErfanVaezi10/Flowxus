# -*- coding: utf-8 -*-
# Flowxus/mesh/core/runner.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/26/2025

Purpose
-------
Invoke the Gmsh command-line interface to generate a 2D mesh from a previously emitted
`.geo` file. This module does **not** construct geometry or fields; it only runs Gmsh
with robust defaults and clear error messages.

Main Tasks
----------
    1. Locate the Gmsh binary (explicit path, env var `GMSH_BIN`, or PATH).
    2. Build a CLI command with optional overrides (algorithm, extra settings).
    3. Execute Gmsh and validate the resulting `.msh` file (size sanity check).

Notes:
------
   - Designed for 2D meshing with Gmsh (default dim=2);output formats supported are "msh2" and "msh4"
   - Mesh file must exceed ~ 200 bytes; smaller files indicate that no elements were generated.
"""

import os
import subprocess
from typing import Dict, Optional, List, Union
from mesh.tools.utils import ensure_exec_on_path


def mesh_geo(
    *,
    geo_path: str,
    msh_path: str,
    dim: int = 2,
    algo: Optional[int] = None,
    extra_cli: Optional[Dict[str, Union[int, float, str]]] = None,
    gmsh_bin: Optional[str] = None,
    msh_format: str = "msh4",
) -> str:
    """
    Run Gmsh on a `.geo` file and write a `.msh` mesh to disk.

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
        Caller-level overrides passed in `extra_cli` may still win if they
        re-set the same key after this.
    extra_cli : Dict[str, Union[int, float, str]], optional
        Extra Gmsh options to inject as `-setnumber key value` (for numeric
        values) or `-setstring key value` (for non-numerics). Use this to
        toggle options like:
          {"Mesh.Optimize": 1, "Mesh.RecombineAll": 0}
    gmsh_bin : str, optional
        Explicit path to the Gmsh executable. If not provided, the function
        uses the environment variable `GMSH_BIN` and then falls back to
        searching the system PATH.
    msh_format : str, optional
        Output mesh format: "msh2" or "msh4" (default "msh4"). Choose "msh2"
        if your downstream tooling (e.g., some converters) prefers legacy MSH2.

    Returns
    -------
    str
        The output mesh path (`msh_path`), if Gmsh completed successfully.

    Raises
    ------
    FileNotFoundError
        If `geo_path` does not exist.
    ValueError
        If `msh_format` is not "msh2" or "msh4".
    RuntimeError
        If Gmsh returns a non-zero code, or if the resulting file is missing
        or suspiciously small (usually indicates geometry/surface issues).

    Notes
    -----
    - The command is run with `-save -nopopup -v 2` for reproducible
      batch behavior and moderate verbosity.
    - A minimal size check (> ~200 bytes) guards against “No elements in
      surface” failures that still return success in some edge cases.
    """
    if not os.path.exists(geo_path):
        raise FileNotFoundError("Geometry file not found: {}".format(geo_path))

    out_dir = os.path.dirname(os.path.abspath(msh_path))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    gmsh = gmsh_bin or os.environ.get("GMSH_BIN") or ensure_exec_on_path("gmsh")

    # Normalize/guard msh_format
    fmt = (msh_format or "msh4").lower()
    if fmt not in ("msh2", "msh4"):
        raise ValueError("msh_format must be 'msh2' or 'msh4' (got '{}')".format(msh_format))

    cmd: List[str] = [gmsh, "-{}".format(abs(int(dim))), geo_path, "-o", msh_path, "-format", fmt]

    if algo is not None:
        cmd += ["-setnumber", "Mesh.Algorithm", str(int(algo))]

    if extra_cli:
        for k, v in extra_cli.items():
            key = str(k)
            if isinstance(v, (int, float)):
                cmd += ["-setnumber", key, str(v)]
            else:
                # Treat everything else as a string; users can pass JSON-ish literals if needed.
                cmd += ["-setstring", key, str(v)]

    # Save results, no GUI, moderate verbosity
    cmd += ["-save", "-nopopup", "-v", "2"]

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if proc.returncode != 0:
        msg = (
            "Gmsh failed (code {}):\n"
            "CMD: {}\n"
            "STDOUT:\n{}\n"
            "STDERR:\n{}"
        ).format(proc.returncode, " ".join(cmd), proc.stdout, proc.stderr)
        raise RuntimeError(msg)

    try:
        size = os.path.getsize(msh_path)
    except OSError as e:
        raise RuntimeError("Gmsh reported success but mesh file not found: {}".format(msh_path)) from e

    if size < 200:
        raise RuntimeError(
            "Gmsh wrote an unexpectedly small mesh ({} bytes). "
            "This usually means no 2D elements were generated. "
            "Inspect the .geo (surface definition) and Gmsh output."
            .format(size)
        )

    return msh_path
