# -*- coding: utf-8 -*-
# Flowxus/mesh/core/base.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 11/28/2025

Purpose:
--------
Abstract interfaces for mesh generation to enable multiple mesh generator implementations
while maintaining consistent APIs across Gmsh and future custom meshing algorithms.

Abstract Classes:
-----------------
- MeshGenerator: Base interface all mesh generators must implement
- GeometryProcessor: Standardized geometry processing interface
- MeshAssembler: Standardized mesh assembly interface

Notes:
------
- These interfaces ensure that Gmsh and custom mesh generators can be used interchangeably
- All concrete implementations must maintain identical input/output signatures
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class MeshGenerator(ABC):
    """
    Abstract base class for all mesh generation implementations.

    This interface allows seamless switching between Gmsh and future custom
    mesh generators without changing external API calls.
    """

    @abstractmethod
    def generate_geometry(self, domain, settings: Dict[str, Any]) -> str:
        """
        Generate geometry definition for mesh generation.

        Parameters
        ----------
        domain : Any
            Domain object containing geometry information
        settings : Dict[str, Any]
            Mesh generation settings and parameters

        Returns
        -------
        str
            Geometry definition in appropriate format
        """
        pass

    @abstractmethod
    def generate_mesh(self, input_path: str, output_path: str,
                      settings: Dict[str, Any]) -> str:
        """
        Execute mesh generation from input to output file.

        Parameters
        ----------
        input_path : str
            Path to input geometry file
        output_path : str
            Path for output mesh file
        settings : Dict[str, Any]
            Mesh generation settings and parameters

        Returns
        -------
        str
            Path to generated mesh file
        """
        pass


class GeometryProcessor(ABC):
    """
    Abstract base class for geometry processing and validation.
    """

    @abstractmethod
    def process_domain(self, domain, settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process and validate domain geometry for mesh generation.

        Parameters
        ----------
        domain : Any
            Domain object containing geometry information
        settings : Dict[str, Any]
            Processing settings and parameters

        Returns
        -------
        Dict[str, Any]
            Processed geometry data ready for assembly
        """
        pass


class MeshAssembler(ABC):
    """
    Abstract base class for mesh assembly operations.
    """

    @abstractmethod
    def assemble_mesh_definition(self, processed_data: Dict[str, Any]) -> str:
        """
        Assemble complete mesh definition from processed geometry data.

        Parameters
        ----------
        processed_data : Dict[str, Any]
            Processed geometry data from GeometryProcessor

        Returns
        -------
        str
            Complete mesh definition ready for generation
        """
        pass
