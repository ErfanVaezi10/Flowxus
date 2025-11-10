# Flowxus Geometry Package

A comprehensive geometry processing framework for airfoil analysis and CFD domain generation. Provides robust tools for loading, analyzing, and exporting 2D airfoil geometries with support for multiple file formats and professional-grade output generation.

## Features

- **Multi-format Support**: Load geometry from `.dat`, `.STEP`, and `.IGES` files
- **Geometric Analysis**: Compute curvature, descriptors, and per-vertex metrics
- **Domain Construction**: Build rectangular far-field domains for CFD simulations
- **Gmsh Integration**: Export geometry-only `.geo` files for meshing
- **Topology Processing**: Advanced loop analysis and boundary segmentation
- **Normalization & Validation**: Automatic coordinate normalization and quality checks

## Package Structure

### Core Subpackages

#### `api/` - High-Level Interface
Simplified facade for common geometry workflows:
- `load_and_normalize()` - Unified geometry loading with normalization
- `build_farfield_domain()` - Domain construction around airfoils
- `write_geo_and_csv()` - Export geometry and metadata

#### `geo/` - Geometry Core
Central geometry handling and file generation:
- `geo_loader.py` - Unified loader for multiple file formats
- `geo_writer.py` - Gmsh `.geo` file generation
- `dispatcher.py` - File format routing and loader dispatch

#### `loaders/` - Format-Specific Readers
Specialized loaders for different geometry formats:
- `dat_loader.py` - Robust parser for airfoil coordinate files
- `step_loader.py` - CAD geometry loader for STEP files
- `iges_loader.py` - CAD geometry loader for IGES files
- `_helpers.py` - Shared CAD processing utilities

#### `domain/` - CFD Domain Construction
Far-field domain building around airfoils:
- `domain_builder.py` - Domain construction with metadata support
- `domain_math.py` - Mathematical utilities for domain calculations

#### `metrics/` - Geometric Analysis
Quantitative analysis and feature extraction:
- `descriptors.py` - Global airfoil descriptors (LE radius, TE thickness, etc.)
- `per_vertex.py` - Per-vertex scalars for meshing/ML applications
- `_num.py` - Numerical utilities for geometric computations

#### `ops/` - Geometric Operations
Fundamental geometric processing utilities:
- `basic.py` - Core operations (normalization, LE/TE detection, arclength)
- `analysis.py` - Advanced analysis (curvature, distance calculations)

#### `topology/` - Connectivity Analysis
Topological operations on closed loops:
- `loop.py` - Closure predicates, orientation, CCW enforcement
- `indices.py` - Deterministic LE/TE index detection
- `split.py` - Pressure/suction side partitioning
- `_validation.py` - Shared validation utilities

## Quick Start

```python
from flowxus.geometry.api import load_and_normalize, build_farfield_domain, write_geo_and_csv

# Load and normalize airfoil geometry
geo = load_and_normalize('airfoil.dat')

# Build far-field domain
domain = build_farfield_domain(geo, {
    'up': 10.0, 'down': 10.0, 'front': 15.0, 'back': 20.0
})

# Export geometry and metadata
write_geo_and_csv(
    domain, 
    export_path='domain.geo',
    emit_metadata=True,
    emit_scalars_csv=True
)
```

## Dependencies

- **Required**: `numpy`
- **Optional**: `gmsh` (for CAD file loading)
- **Development**: `pytest` (for testing)

## Supported File Formats

| Format | Extension | Loader | Notes |
|--------|-----------|--------|-------|
| Airfoil Coordinates | `.dat` | `dat_loader` | Handles headers, comments, mixed delimiters |
| STEP CAD | `.stp`, `.step` | `step_loader` | Requires Gmsh Python API |
| IGES CAD | `.igs`, `.iges` | `iges_loader` | Requires Gmsh Python API |


## Contributing

1. Follow the existing code structure and documentation standards
2. Add tests for new functionality
3. Update documentation for API changes
4. Ensure all validation and error handling is consistent
