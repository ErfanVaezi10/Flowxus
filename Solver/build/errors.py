# -*- coding: utf-8 -*-
# Flowxus/solver/build/errors.py


"""
Project: Flowxus
Author: Erfan Vaezi
Date: 10/4/2025

Purpose
-------
Provide typed exceptions for the solver/build layer with compact, context-aware messages
to standardize error reporting across schema checks, validation, rendering, and markers
application.

Main Tasks
----------
    1. Define ConfigError(message, context) with a compact context suffix in __str__.
    2. Provide typed subclasses: SchemaError, ValidationError, RenderError, MarkerError.
    3. Supply _format_context helper and expose public names via __all__.

Notes
-----
- Context is optional; long values are truncated for readability.
- Exceptions are scoped to config/schema/markers/render steps in the build layer.
"""

from __future__ import absolute_import

__all__ = [
    "ConfigError",
    "SchemaError",
    "ValidationError",
    "RenderError",
    "MarkerError",
]


def _format_context(ctx):
    """Return a compact ' key1=val1, key2=val2' string or '' if no context."""
    if not ctx:
        return ""
    try:
        parts = []
        for k in sorted(ctx.keys()):
            v = ctx[k]
            # Keep it short; avoid huge dumps
            sv = repr(v)
            if len(sv) > 120:
                sv = sv[:117] + "..."
            parts.append("{}={}".format(k, sv))
        return " | " + ", ".join(parts)
    except Exception:
        # Context should never break error rendering
        return ""


class ConfigError(Exception):
    """
    Base class for all configuration-related errors in the build layer.

    Parameters
    ----------
    message : str
        Human-readable error.
    context : dict, optional
        Extra fields to append in the string form (e.g., {"key": "AOA", "value": 200.0}).

    Notes
    -----
    - Subclasses inherit the same constructor.
    - __str__ appends a compact context suffix for faster debugging.
    """
    def __init__(self, message, context=None):
        self.context = dict(context) if context else None
        super(ConfigError, self).__init__(message)

    def __str__(self):
        base = super(ConfigError, self).__str__()
        return base + _format_context(self.context)


class SchemaError(ConfigError):
    """
    Per-key issues detected by the schema:
      - unknown/invalid enum values
      - non-numeric where numeric is required
      - out-of-range scalar values
      - bad key normalization assumptions
    """


class ValidationError(ConfigError):
    """
    Cross-key contradictions or missing required keys detected AFTER merging defaults+params:
      - logically inconsistent combinations (e.g., RANS with no turbulence model)
      - derived constraints (e.g., RE>0 requires REYNOLDS_LENGTH>0)
    """


class RenderError(ConfigError):
    """
    Errors while rendering/writing the .cfg:
      - non-stringable values
      - encoding/IO problems (use context to include 'path')
    """


class MarkerError(ConfigError):
    """
    Problems applying markers / BC params:
      - malformed marker_map or bc_params
      - unsupported token types or empty groups
    """
