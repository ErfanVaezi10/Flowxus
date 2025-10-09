# -*- coding: utf-8 -*-
# Flowxus/solver/ops/__init__.py
"""
Project: Flowxus
Author: Erfan Vaezi
Date: 10/8/2025

Modules
-------
- style:    Centralized Matplotlib style and figure() context for consistent plots.
            One place to control DPI, fonts, grids, and spacing across all figures.

- utils:    Residual header utilities (NS vs turbulence), smoothing, and helpers.
            Keep pure and dependency-light for easy testing and reuse.

- history:  Static and live residual plots reading SU2 history files (.csv/.gz/whitespace).
            Provides separate NS and turbulence residual views, plus live updating.
"""

from .style import apply_base_style, figure
from .utils import split_residual_headers, moving_average, ema
from .history import (
    plot_ns_residuals,
    plot_turb_residuals,
    plot_all_residuals,
)

__all__ = [
    "apply_base_style", "figure",
    "split_residual_headers", "moving_average", "ema",
    "plot_ns_residuals", "plot_turb_residuals", "plot_all_residuals",
]

