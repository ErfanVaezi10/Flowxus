# -*- coding: utf-8 -*-
# Flowxus/mesh/api.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/21/2025

Purpose
-------
High-level API for building 2D airfoil-in-box meshes using Gmsh. The module ties together
the geometry writer, field generator, and Gmsh runner, and exposes a single entry point
(`build_mesh`) for generating `.geo` and `.msh` artifacts from a prepared DomainBuilder.

Main Tasks
----------
    1. Validate inflation and mesh size settings, ensure required keys exist.
    2. Compute total BL thickness (if active) via geometric series.
    3. Call the writer (`gmsh_geo_from_domain`) to generate the `.geo` text and
       write it to disk.
    4. Build Gmsh CLI options (algorithm, curvature, optimization).
    5. Call the runner (`mesh_geo`) to invoke Gmsh and produce a `.msh`.
    6. Optionally validate presence of required Physical groups.
"""

from typing import Dict, Optional
import logging
from mesh.tools.utils import bl_thickness
from mesh.core import gmsh_geo_from_domain, write_geo_file, mesh_geo

logger = logging.getLogger(__name__)


def build_mesh(
    domain,
    geo_path: str = "domain.geo",
    msh_path: str = "domain.msh",
    inflation_settings: Dict[str, float] = None,
    mesh_size_settings: Dict[str, float] = None,
    gmsh_algo: Optional[int] = None,
    validate_groups: bool = False,
    *,
    curvature_from_geometry: bool = True,
    gmsh_extra_cli: Optional[Dict[str, float]] = None,
    hybrid_bl: bool = True,
    force_algo_for_bl: bool = True,
    msh_format: str = "msh4",
) -> str:
    """
    Build a 2D mesh with Gmsh for the airfoil far-field domain.

    Parameters
    ----------
    domain : DomainBuilder
        DomainBuilder instance with:
        - `.airfoil.points` (Nx2) and `.airfoil.get_closed_points()`
        - `.bounding_box` dict
        - `.physical_tags` dict.
    geo_path : str, optional
        Path to write the intermediate `.geo` file. Default "domain.geo".
    msh_path : str, optional
        Path to write the output `.msh` file. Default "domain.msh".
    inflation_settings : dict
        {"first_layer": float, "n_layers": int, "growth_rate": float}.
        Set n_layers=0 to disable BL.
    mesh_size_settings : dict
        {"inlet","outlet","top","bottom","interior","airfoil"} mesh sizes.
    gmsh_algo : int, optional
        If provided, forces a specific Gmsh surface algorithm (e.g. 6 or 8).
        Overrides both writer defaults and `force_algo_for_bl`.
    validate_groups : bool, optional
        If True and meshio available, check that required Physical groups exist.
    curvature_from_geometry : bool, optional
        If True, adds `Mesh.CharacteristicLengthFromCurvature=1`.
    gmsh_extra_cli : dict, optional
        Extra CLI options as {"Mesh.Option": value} (wins last).
    hybrid_bl : bool, optional
        If True and n_layers>0, emit a BoundaryLayer field with quads near wall.
    force_algo_for_bl : bool, optional
        Controls global surface algorithm when BL is active:
        - True  (default): prefer quad-friendly algorithm (8 = Frontal-Quad),
                           which may produce quads more broadly.
        - False: let writer steer toward triangular meshing (e.g., Algo=6),
                 so BL quads appear only near the foil and the farfield is tri.
        Ignored if `gmsh_algo` is provided.
    msh_format : {"msh2","msh4"}, optional
        Mesh output format for the runner. Default "msh4".

    Returns
    -------
    str
        The path to the generated mesh file (`msh_path`).

    Raises
    ------
    ValueError
        If required domain attributes or dict keys are missing, or inputs invalid.
    RuntimeError
        If Gmsh fails or produces an empty mesh (caught in runner).
    """
    if domain is None:
        raise ValueError("domain must be a DomainBuilder instance, got None.")
    if not hasattr(domain, "airfoil") or domain.airfoil is None:
        raise ValueError("domain.airfoil is missing.")
    if getattr(domain.airfoil, "points", None) is None:
        raise ValueError("domain.airfoil.points is None. Did you call geo.load()?")

    if inflation_settings is None or mesh_size_settings is None:
        raise ValueError("inflation_settings and mesh_size_settings must be provided.")

    # Required keys
    req_infl = ("first_layer", "n_layers", "growth_rate")
    req_sizes = ("inlet", "outlet", "top", "bottom", "interior", "airfoil")
    for k in req_infl:
        if k not in inflation_settings:
            raise ValueError(f"Missing inflation_settings['{k}'].")
    for k in req_sizes:
        if k not in mesh_size_settings:
            raise ValueError(f"Missing mesh_size_settings['{k}'].")

    first_layer = float(inflation_settings["first_layer"])
    n_layers = int(inflation_settings["n_layers"])
    growth_rate = float(inflation_settings["growth_rate"])

    # Mesh sizes must be > 0
    for k in req_sizes:
        v = float(mesh_size_settings[k])
        if not (v > 0.0):
            raise ValueError(f"mesh_size_settings['{k}'] must be > 0 (got {v}).")

    # Boundary layer activation and validation
    bl_active = (hybrid_bl and n_layers > 0)
    if bl_active:
        if not (first_layer > 0.0):
            raise ValueError("first_layer must be > 0 when n_layers > 0.")
        if not (growth_rate >= 1.0):
            raise ValueError("growth_rate must be >= 1.0 when n_layers > 0.")
        thickness = bl_thickness(first_layer, n_layers, growth_rate)
    else:
        thickness = None  # BL off

    # --- Build .geo text ---
    geo_text = gmsh_geo_from_domain(
        domain=domain,
        inflation_settings=inflation_settings,
        mesh_size_settings=mesh_size_settings,
        thickness=thickness,
        hybrid_bl=bl_active,
    )
    write_geo_file(geo_text, geo_path)
    logger.info("[build_mesh] .geo written to %s", geo_path)

    # --- Build Gmsh CLI options ---
    extra_cli_final: Dict[str, float] = {}
    if curvature_from_geometry:
        extra_cli_final["Mesh.CharacteristicLengthFromCurvature"] = 1.0

    if gmsh_algo is None:
        if bl_active and force_algo_for_bl:
            extra_cli_final["Mesh.Algorithm"] = 8.0  # Frontal-Quad
            extra_cli_final["Mesh.RecombineAll"] = 0.0
            extra_cli_final["Mesh.Optimize"] = 1.0
            extra_cli_final["Mesh.CharacteristicLengthExtendFromBoundary"] = 0.0
        # Else: let writer defaults (e.g. Algo=6) dominate

    if gmsh_extra_cli:
        extra_cli_final.update(gmsh_extra_cli)

    if extra_cli_final:
        logger.info("[build_mesh] Gmsh options: %s", extra_cli_final)

    # --- Run Gmsh ---
    mesh_geo(
        geo_path=geo_path,
        msh_path=msh_path,
        dim=2,
        algo=gmsh_algo,
        extra_cli=extra_cli_final if extra_cli_final else None,
        msh_format=msh_format,
    )
    logger.info("[build_mesh] .msh written to %s", msh_path)

    # --- Optional validation of physical groups ---
    if validate_groups:
        try:
            from mesh.validate import check_physical_groups as _check_pg
        except ImportError:
            def _check_pg(*_args, **_kwargs):
                logger.debug("[build_mesh] meshio not installed; skipping physical-group validation.")
        _check_pg(
            msh_path,
            required=["inlet", "outlet", "top", "bottom", "airfoil", "fluid"],
        )

    return msh_path
