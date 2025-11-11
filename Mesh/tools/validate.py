# -*- coding: utf-8 -*-
# Flowxus/mesh/validate.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
-------
Lightweight validation utilities for generated meshes.

Main Tasks:
----------
   - check_physical_groups: verify that required Physical group names exist in
     the mesh file (works when `meshio` is installed; otherwise no-ops cleanly).

Notes:
------
   - Soft-dependency behavior is intentional: no meshio → silent return.
   - Presence check is by physical name (not ID), matching how you write them in .geo.
   - Some meshio versions expose field_data values as NumPy arrays (id, dim)
"""

import os
from typing import List, Dict, Optional


def check_physical_groups(
    msh_path: str,
    required: List[str],
    *,
    kind_expectations: Optional[Dict[str, int]] = None,
    strict_if_no_field_data: bool = False,
) -> None:
    """
    Verify that required physical group names exist in the mesh (via meshio).
    Optionally check their topological dimension: 1 = line, 2 = surface.

    Parameters
    ----------
    msh_path : str
        Path to the .msh file.
    required : List[str]
        Names to look for, e.g. ["inlet", "outlet", "top", "bottom", "airfoil", "fluid"].
    kind_expectations : Dict[str, int], optional
        Mapping of group name -> expected topological dimension (1=line, 2=surface).
        If not provided, defaults to: fluid=2, all others=1 (common for 2D airfoil cases).
    strict_if_no_field_data : bool
        If True and the mesh has no field_data, raise an error; otherwise return silently.

    Notes
    -----
    - Requires 'meshio'. If not installed, this function returns silently.
    - This is a light check; it doesn't validate exact curve IDs or orientations.
    """

    # Soft dependency on meshio
    try:
        import meshio  # type: ignore
    except Exception:
        # meshio not installed — skip silently by design
        return

    if not os.path.exists(msh_path) or os.path.getsize(msh_path) < 200:
        raise RuntimeError("Mesh file '{}' not found or too small.".format(msh_path))

    m = meshio.read(msh_path)

    # meshio field_data maps physical name -> (id, dim) for Gmsh meshes
    field_data = m.field_data if getattr(m, "field_data", None) else {}
    if not field_data:
        if strict_if_no_field_data:
            raise RuntimeError(
                "No field_data found in '{}'. Ensure your .geo defines Physical groups and "
                "that Gmsh wrote them to the mesh.".format(msh_path)
            )
        return  # Nothing more we can check without field_data

    # Build name -> (id, dim) mapping with robust parsing
    groups = {}
    for name, meta in field_data.items():
        dim = None
        try:
            # Common Gmsh+meshio case: meta is (id, dim)
            if isinstance(meta, (list, tuple)) and len(meta) >= 2:
                dim = int(meta[1])
            else:
                # Fallback: try to index like an array
                dim = int(meta[1])  # may raise
        except Exception:
            dim = None
        groups[str(name)] = {"dim": dim}

    # Check presence
    missing = [name for name in required if name not in groups]
    if missing:
        available = ", ".join(sorted(groups.keys())) or "<none>"
        raise RuntimeError(
            "Missing expected physical groups in '{}': {}. Available: [{}]. "
            "Ensure your .geo defines them correctly."
            .format(msh_path, missing, available)
        )

    # Default expectations: 'fluid' is a 2D region, others are 1D boundaries
    if kind_expectations is None:
        kind_expectations = {name: (2 if name == "fluid" else 1) for name in required}

    # Check dimensions where we can
    dim_mismatches = []
    for name, expected_dim in kind_expectations.items():
        got = groups.get(name, {}).get("dim", None)
        if got is None:
            # Some meshio versions may not carry the dim; skip dim check in that case
            continue
        if int(got) != int(expected_dim):
            dim_mismatches.append((name, expected_dim, got))

    if dim_mismatches:
        msg_lines = ["Topological-dimension mismatch for physical groups in '{}' :".format(msh_path)]
        for name, exp_d, got_d in dim_mismatches:
            msg_lines.append("  - {}: expected dim {}, got {}".format(name, exp_d, got_d))
        msg_lines.append("Check that surfaces vs. lines are tagged as intended in the .geo.")
        raise RuntimeError("\n".join(msg_lines))
