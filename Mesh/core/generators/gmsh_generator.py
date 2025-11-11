# -*- coding: utf-8 -*-
# Flowxus/mesh/core/generators/gmsh_generator.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 11/28/2025

Purpose:
--------
Concrete implementation of MeshGenerator for Gmsh-based mesh generation.
Contains the Gmsh-specific execution logic extracted from runner.py.

Main Tasks:
-----------
    1. Execute Gmsh binary with proper CLI construction
    2. Handle Gmsh binary location (explicit path, env var, or PATH)
    3. Validate resulting .msh file integrity
    4. Provide clear error messaging for Gmsh failures

Notes:
------
- Maintains identical functionality to original runner.py
- Implements the MeshGenerator abstract interface
- Can be used interchangeably with future custom generators
"""

import os
import subprocess
from typing import Dict, List, Any
from mesh.tools.utils import ensure_exec_on_path
from ..base import MeshGenerator


class GmshGenerator(MeshGenerator):
    """
    Gmsh-specific mesh generator implementation.

    This class contains the Gmsh execution logic previously located in runner.py,
    now implementing the abstract MeshGenerator interface.
    """

    def generate_geometry(self, domain, settings: Dict[str, Any]) -> str:
        """
        Generate Gmsh .geo geometry definition.

        Parameters
        ----------
        domain : Any
            Domain object containing geometry information
        settings : Dict[str, Any]
            Gmsh-specific geometry generation settings

        Returns
        -------
        str
            Gmsh .geo geometry definition text

        Notes
        -----
        This method delegates to the existing writer functionality
        to maintain compatibility with the current workflow.
        """
        # For now, delegate to the existing writer to maintain compatibility
        # This could be refactored further in the future
        from ..writer import gmsh_geo_from_domain

        # Extract relevant settings for gmsh_geo_from_domain
        geo_settings = {
            'inflation_settings': settings.get('inflation_settings', {}),
            'mesh_size_settings': settings.get('mesh_size_settings', {}),
            'thickness': settings.get('thickness'),
            'distance_points_per_curve': settings.get('distance_points_per_curve', 200),
            'dist_min': settings.get('dist_min', 0.05),
            'dist_max': settings.get('dist_max', 5.0),
            'edge_dist_min': settings.get('edge_dist_min', 0.0),
            'edge_dist_max': settings.get('edge_dist_max', 0.02),
            'hybrid_bl': settings.get('hybrid_bl', True),
            'airfoil_point_sizes': settings.get('airfoil_point_sizes'),
            'scalars_csv_path': settings.get('scalars_csv_path'),
            'size_map': settings.get('size_map'),
        }

        return gmsh_geo_from_domain(domain, **geo_settings)

    def generate_mesh(self, input_path: str, output_path: str,
                      settings: Dict[str, Any]) -> str:
        """
        Execute Gmsh to generate mesh from .geo file.

        Parameters
        ----------
        input_path : str
            Path to input .geo file
        output_path : str
            Path for output .msh file
        settings : Dict[str, Any]
            Gmsh execution settings including:
            - dim: Mesh dimensionality (default: 2)
            - algo: Surface meshing algorithm
            - extra_cli: Additional Gmsh options
            - gmsh_bin: Explicit Gmsh binary path
            - msh_format: Output format ("msh2" or "msh4")

        Returns
        -------
        str
            Path to generated .msh file

        Raises
        ------
        FileNotFoundError
            If input_path does not exist
        ValueError
            If msh_format is not "msh2" or "msh4"
        RuntimeError
            If Gmsh returns non-zero code or output file is invalid
        """
        # Extract settings with defaults
        dim = settings.get('dim', 2)
        algo = settings.get('algo')
        extra_cli = settings.get('extra_cli')
        gmsh_bin = settings.get('gmsh_bin')
        msh_format = settings.get('msh_format', 'msh4')

        # Validate input file exists
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Geometry file not found: {input_path}")

        # Create output directory if needed
        out_dir = os.path.dirname(os.path.abspath(output_path))
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        # Locate Gmsh binary
        gmsh = gmsh_bin or os.environ.get("GMSH_BIN") or ensure_exec_on_path("gmsh")

        # Validate mesh format
        fmt = (msh_format or "msh4").lower()
        if fmt not in ("msh2", "msh4"):
            raise ValueError(f"msh_format must be 'msh2' or 'msh4' (got '{msh_format}')")

        # Build Gmsh command
        cmd: List[str] = [gmsh, f"-{abs(int(dim))}", input_path, "-o", output_path, "-format", fmt]

        # Add algorithm if specified
        if algo is not None:
            cmd += ["-setnumber", "Mesh.Algorithm", str(int(algo))]

        # Add extra CLI options
        if extra_cli:
            for k, v in extra_cli.items():
                key = str(k)
                if isinstance(v, (int, float)):
                    cmd += ["-setnumber", key, str(v)]
                else:
                    cmd += ["-setstring", key, str(v)]

        # Add standard options: save results, no GUI, moderate verbosity
        cmd += ["-save", "-nopopup", "-v", "2"]

        # Execute Gmsh
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if proc.returncode != 0:
            msg = (
                "Gmsh failed (code {}):\n"
                "CMD: {}\n"
                "STDOUT:\n{}\n"
                "STDERR:\n{}"
            ).format(proc.returncode, " ".join(cmd), proc.stdout, proc.stderr)
            raise RuntimeError(msg)

        # Validate output file
        try:
            size = os.path.getsize(output_path)
        except OSError as e:
            raise RuntimeError(f"Gmsh reported success but mesh file not found: {output_path}") from e

        if size < 200:
            raise RuntimeError(
                f"Gmsh wrote an unexpectedly small mesh ({size} bytes). "
                "This usually means no 2D elements were generated. "
                "Inspect the .geo (surface definition) and Gmsh output."
            )

        return output_path


# Create default instance for convenience
default_gmsh_generator = GmshGenerator()
