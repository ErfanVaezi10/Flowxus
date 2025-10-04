# -*- coding: utf-8 -*-
# Flowxus/solver/build/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 10/3/2025

Modules:
--------
- config:   Sectioned defaults and public API to assemble, render, and write SU2 configs.
            Order of ops: normalize -> per-key validate -> merge -> markers/BC -> cross-validate.

- markers:  SU2 marker tuple formatting and marker/BC injection into the config dict.
            Groups labels per SU2 key, resolves ids via id_map, appends bc_params verbatim.

- schema:   Canonical key normalization (aliases → SU2 keys) and per-key validation.
            Enforces enums & numeric ranges; raises SchemaError with clear, actionable messages.

- validate: Cross-key consistency checks after merge (final config sanity).
            Ensures solver↔turbulence coherence, Reynolds logic, and non-empty boundary markers.

- errors:   Unified exceptions for the build layer (consistent error surface).
            Provides ConfigError base plus SchemaError, ValidationError, RenderError, MarkerError.
"""

from .config import build_cfg, render_cfg, write_cfg
from .schema import normalize_keys, validate as validate_schema
from .validate import cross_validate
from .markers import fmt_tuple, apply_marker_map, apply_bc_params
from .errors import (ConfigError, SchemaError, ValidationError, RenderError, MarkerError)

__all__ = [
    # Public build API
    "build_cfg", "render_cfg", "write_cfg",
    # Validation helpers
    "normalize_keys", "validate_schema", "cross_validate",
    # Marker utilities
    "fmt_tuple", "apply_marker_map", "apply_bc_params",
    # Error types
    "ConfigError", "SchemaError", "ValidationError", "RenderError", "MarkerError",
]
