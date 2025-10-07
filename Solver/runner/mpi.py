# -*- coding: utf-8 -*-
# Flowxus/solver/runner/mpi.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 9/23/2025 (Updated: 10/07/2025)

Purpose
-------
Minimal helper to construct an MPI launcher prefix for SU2 runs. Resolves a usable
MPI executable (user-specified or common fallbacks) and returns a command fragment
(e.g., ["mpiexec", "-n", "4"]) for callers to prepend to solver invocations.

Main Tasks
----------
    1. Validate `nprocs` and short-circuit to serial (empty prefix) when `nprocs<=1`.
    2. Locate an MPI launcher via `shutil.which` (user-provided name, then mpiexec/mpirun).
    3. Emit a portable `-n <N>` prefix supported by major MPI stacks (OpenMPI/MPICH).

Notes
-----
- If no launcher is found, an empty list is returned so the caller can decide whether
  to error (when `nprocs>1`) or fall back to serial execution.
- Both `-n` and `-np` are widely accepted; we standardize on `-n` for brevity.
"""

from __future__ import absolute_import
from typing import List
import shutil


def build_mpi_cmd(mpi_exec: str, nprocs: int) -> List[str]:
    """
    Build a launcher prefix for MPI execution.

    Args
    ----
    mpi_exec : str
        Preferred MPI launcher name or path (e.g., "mpiexec", "mpirun").
    nprocs : int
        Requested number of MPI ranks.

    Returns
    -------
    List[str]
        Command prefix for MPI runs (e.g., ["mpiexec", "-n", "4"]) or `[]` if serial
        or no launcher is available.
    """
    try:
        n = int(nprocs or 0)
    except Exception:
        n = 0

    if n <= 1:
        return []

    # Resolve launcher: user-specified, or common fallbacks.
    launcher = shutil.which(mpi_exec) or shutil.which("mpiexec") or shutil.which("mpirun")
    if not launcher:
        return []

    # Most MPI stacks accept '-n' and '-np'. Prefer '-n'; works on OpenMPI/MPICH.
    return [launcher, "-n", str(n)]
