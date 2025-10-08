# -*- coding: utf-8 -*-
# Flowxus/solver/runner/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/18/2025 (Updated: 10/07/2025)

Modules
-------
- run:      Thin SU2 launcher (serial/MPI) with streaming, early-stop, timeout, and env.
            Stages cfg into workdir; builds cmd (dry-run or solver); returns (rc, stdout, stderr).

- mpi:      Build a portable MPI prefix (mpiexec/mpirun) like ['mpiexec', '-n', '4'].
            Short-circuits to [] when nprocs<=1 or no launcher is found; run.py decides behavior.

- monitor:  Stream helpers for solver output: keep a last-N tail and detect failure bursts.
            Case-insensitive substring matching (e.g., 'nan'); lightweight and composable.
"""

from .run import run_su2
from .mpi import build_mpi_cmd
from .monitor import tail_lines, early_stop

__all__ = [
    "run_su2",
    "build_mpi_cmd",
    "tail_lines",
    "early_stop",
]

