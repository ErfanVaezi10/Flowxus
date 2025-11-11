# -*- coding: utf-8 -*-
# Flowxus/mesh/core/fields/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 11/28/2025

Fields Subpackage:
------------------
Modular field definitions for Gmsh mesh sizing control. Split from the monolithic 
fields.py to enable better organization and future extensibility.

Modules:
--------
- boundary_layer: Boundary layer field generation with quad extrusion

- sizing_fields:  Distance and threshold fields for size tapering

- edge_fields:    Per-edge sizing fields for farfield boundaries

- field_composer: Field combination and background field orchestration

Notes:
------
- This modular approach allows independent development of field types
- Maintains compatibility with existing field emission functions
"""

from .boundary_layer import emit_boundary_layer_field
from .sizing_fields import (
    emit_airfoil_sizing_fields,
    emit_background_field,
    validate_distance_parameters
)
from .edge_fields import emit_edge_sizing_field, emit_all_edge_fields
from .field_composer import compose_fields

# Re-export the main function for backward compatibility
emit_sizing_fields = compose_fields

__all__ = [
    "emit_sizing_fields",
    "emit_boundary_layer_field",
    "emit_airfoil_sizing_fields",
    "emit_background_field",
    "emit_edge_sizing_field",
    "emit_all_edge_fields",
    "compose_fields",
    "validate_distance_parameters"
]
