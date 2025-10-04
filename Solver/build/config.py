# -*- coding: utf-8 -*-
# Flowxus/solver/build/config.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/21/2025

Purpose
-------
Assemble a robust SU2 (v7+) configuration from sectioned defaults and user overrides, resolve
boundary markers (name→ID when provided), enforce schema validation and cross-key consistency,
and emit a deterministic, sectioned .cfg text with an atomic writer.

Main Tasks
----------
    1. Flatten curated defaults and merge normalized, schema-checked user params.
    2. Inject mesh I/O: MESH_FILENAME, MESH_FORMAT="SU2", RESTART_FILENAME.
    3. Resolve markers via marker_map/id_map or legacy tuples; normalize tuples
    4. Apply per-marker bc_params and run cross-key validation.
    5. Render a sectioned `.cfg` (extras under 'MISC') and write atomically.

Notes
-----
- Targets SU2 v7+ keys; legacy/removed keys are not set.
- Ensures VOLUME_OUTPUT unless explicitly provided.
- Keyword overrides: marker_map, marker_euler, marker_far, bc_params, id_map.
"""

from __future__ import absolute_import
import os
import tempfile
import io
from pathlib import Path
from typing import Dict, Mapping, Any, Optional
from .markers import fmt_tuple, apply_marker_map, apply_bc_params
from .schema import normalize_keys, validate
from .validate import cross_validate


# -----------------------------
_DEFAULTS_SECTIONS = [
    ("PROBLEM", {
        "SOLVER": "RANS",
        "MATH_PROBLEM": "DIRECT",
        "RESTART_SOL": "NO",
        "ITER": 200,
    }),
    ("FREESTREAM", {
        "GAS_MODEL": "IDEAL_GAS",
        "GAMMA_VALUE": 1.4,
        "MACH_NUMBER": 0.2,
        "AOA": 0.0,
        "FREESTREAM_TEMPERATURE": 300.0,
        "FREESTREAM_PRESSURE": 101325.0,
        # If you pass density/velocity/viscosity later, you can override here via params.
    }),
    ("TURBULENCE", {
        "KIND_TURB_MODEL": "SST",
        "REYNOLDS_NUMBER": 1.0e6,
        "REYNOLDS_LENGTH": 1.0,
    }),
    ("DISCRETIZATION", {
        "NUM_METHOD_GRAD": "GREEN_GAUSS",
        "CFL_NUMBER": 5.0,
        "CFL_ADAPT": "NO",
        "CONV_NUM_METHOD_FLOW": "ROE",
        "MUSCL_FLOW": "YES",
        "SLOPE_LIMITER_FLOW": "VENKATAKRISHNAN",
        "CONV_NUM_METHOD_TURB": "SCALAR_UPWIND",
    }),
    ("LINEAR_SOLVER", {
        "LINEAR_SOLVER": "FGMRES",
        "LINEAR_SOLVER_PREC": "ILU",
        "LINEAR_SOLVER_ITER": 50,
        "LINEAR_SOLVER_ERROR": 1e-6,
    }),
    ("OUTPUT", {
        "OUTPUT_FILES": "(RESTART, SURFACE_PARAVIEW)",
        "OUTPUT_WRT_FREQ": 200,
        "VOLUME_OUTPUT": "SOLUTION, PRIMITIVE",
        "SCREEN_OUTPUT": "INNER_ITER, RMS_DENSITY, RMS_MOMENTUM-X, RMS_MOMENTUM-Y, RMS_ENERGY",
        "HISTORY_OUTPUT": "INNER_ITER, RMS_DENSITY, RMS_MOMENTUM-X, RMS_MOMENTUM-Y, RMS_ENERGY, DRAG, LIFT",
        "HISTORY_WRT_FREQ_INNER": 1,
        "SCREEN_WRT_FREQ_INNER": 1,
    }),
]


def _flatten_defaults(sections):
    """
    Turn sectioned defaults into a single flat dict (stable order preserved).
    """
    flat = {}  # type: Dict[str, Any]
    for _name, block in sections:
        flat.update(block)
    return flat


_DEFAULTS = _flatten_defaults(_DEFAULTS_SECTIONS)


# ---------- Public API ----------
def build_cfg(params,  # type: Optional[Mapping[str, Any]]
              mesh_su2,  # type: str
              out_dir,   # type: str
              **kwargs   # type: Any
              ):
    """
    Merge user params over sectioned defaults, inject mesh + markers, return a flat SU2 dict.

    Keyword-only overrides (all optional):
      marker_map: Mapping[str, str]
      marker_euler: tuple/list of str
      marker_far:   tuple/list of str
      bc_params: Mapping[str, Mapping[str, Any]]
      id_map:    Mapping[str, int]
    """
    marker_map   = kwargs.get("marker_map")       # type: Optional[Mapping[str, str]]
    marker_euler = kwargs.get("marker_euler", ("airfoil",))
    marker_far   = kwargs.get("marker_far", ("inlet", "outlet", "top", "bottom"))
    bc_params    = kwargs.get("bc_params")        # type: Optional[Mapping[str, Mapping[str, Any]]]
    id_map       = kwargs.get("id_map")           # type: Optional[Mapping[str, int]]

    cfg = dict(_DEFAULTS)  # start from defaults
    if params:
        # Canonicalize and validate *before* merging
        params = normalize_keys(params)
        validate(params)  # may raise SchemaError
        cfg.update(params)

    # Mesh & restart I/O
    cfg["MESH_FILENAME"] = os.path.basename(mesh_su2)
    cfg["MESH_FORMAT"] = "SU2"
    cfg["RESTART_FILENAME"] = "restart.dat"

    # Markers
    if marker_map:
        apply_marker_map(cfg, marker_map, id_map)
    else:
        if marker_euler:
            cfg["MARKER_EULER"] = fmt_tuple(marker_euler)
        if marker_far:
            cfg["MARKER_FAR"] = fmt_tuple(marker_far)

    # Ensure volume output default unless user provided
    cfg["VOLUME_OUTPUT"] = cfg.get("VOLUME_OUTPUT", "SOLUTION, PRIMITIVE")

    # Expert BC overrides
    apply_bc_params(cfg, bc_params)

    # Final cross-key validation (logical consistency)
    cross_validate(cfg)
    return cfg  # flat dict with SU2 keys


def render_cfg(cfg_dict):
    # type: (Mapping[str, Any]) -> str
    """
    Deterministic SU2 syntax with section comment headers.
    Keys not belonging to known sections are placed under 'MISC'.
    """
    # Partition keys by section using the original blocks
    sections = []  # list of (title, list of lines)
    seen = set()   # type: set
    for title, block in _DEFAULTS_SECTIONS:
        keys = sorted(k for k in block.keys() if k in cfg_dict)
        if not keys:
            continue
        lines = ["% --- {} ---".format(title)]
        lines.extend(["{}= {}".format(k, cfg_dict[k]) for k in keys])
        sections.append(lines)
        seen.update(keys)

    # Any remaining keys (set by user or helpers)
    misc_keys = sorted(k for k in cfg_dict.keys() if k not in seen)
    if misc_keys:
        lines = ["% --- MISC ---"]
        lines.extend(["{}= {}".format(k, cfg_dict[k]) for k in misc_keys])
        sections.append(lines)

    # Join with newlines + trailing newline
    buf = io.StringIO()
    for i, block_lines in enumerate(sections):
        if i > 0:
            buf.write("\n")
        buf.write("\n".join(block_lines))
    buf.write("\n")
    return buf.getvalue()


def write_cfg(text, path):
    # type: (str, str) -> str
    """
    Atomic UTF-8 write (Python 3.6 compatible).
    """
    p = Path(path)
    if not p.parent.exists():
        p.parent.mkdir(parents=True)
    tf = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(p.parent), delete=False)
    try:
        tf.write(text)
        tmp_name = tf.name
    finally:
        tf.close()
    os.replace(tmp_name, str(p))
    return str(p)
