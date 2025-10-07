# -*- coding: utf-8 -*-
# Flowxus/solver/runner/run.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 9/23/2025 (Updated: 10/07/2025)

Purpose
-------
Thin, robust launcher for SU2 runs (serial or MPI). Stages the case configuration into a
working directory, builds the command-line (including dry-run mode for key validation),
executes SU2, and returns returncode/stdout/stderr with optional timeout control.

Main Tasks
----------
    1. Verify SU2 executable availability and stage the `.cfg` into `workdir`.
    2. Compose the command for serial or MPI execution (`mpiexec -n N ...`).
    3. Run the process, capture stdout/stderr, and enforce an optional timeout,
       returning (rc, out, err). Uses rc=124 on timeout by convention.

Notes
-----
- Dry-run (`-d`) invokes SU2’s configuration validation without advancing the solver.
- MPI launching is delegated to `runner.mpi.build_mpi_cmd`. If `nprocs>1` and no
  launcher is found, a clear error (rc=127) is returned.
- The `.cfg` is copied to `workdir` and referenced by basename because SU2 reads
  the config from the current working directory.
"""

from __future__ import absolute_import
import os
import sys
import shutil
import subprocess
import signal
from typing import Optional, Tuple
from .mpi import build_mpi_cmd


def run_su2(cfg_path: str,
            workdir: str,
            su2_exec: str = "SU2_CFD",
            nprocs: int = 1,
            mpi_exec: str = "mpiexec",
            dry_run: bool = False,
            timeout_s: Optional[int] = None,
            env: Optional[dict] = None) -> Tuple[int, str, str]:
    """
    Launch SU2 (serial or MPI) and return (returncode, stdout, stderr).

    Args
    ----
    cfg_path : str
        Path to the SU2 configuration file to run.
    workdir : str
        Working directory where SU2 is executed; the `.cfg` is staged here and
        referenced by basename, as SU2 reads from CWD.
    su2_exec : str, optional
        SU2 solver executable name or path (default: "SU2_CFD").
    nprocs : int, optional
        Number of MPI ranks (default: 1 → serial).
    mpi_exec : str, optional
        MPI launcher to try first (default: "mpiexec"). If missing, `build_mpi_cmd`
        may fall back to alternatives (e.g., mpirun).
    dry_run : bool, optional
        If True, perform SU2 configuration validation (`-d`) without solving.
    timeout_s : Optional[int], optional
        If provided, kill the job after this many seconds and return rc=124.
    env : Optional[dict], optional
        Environment variables to pass to the child process (merges with OS defaults).

    Returns
    -------
    Tuple[int, str, str]
        (returncode, stdout, stderr). Notable return codes:
          - 0   : success (solver-dependent).
          - 124 : timeout (process terminated by the launcher).
          - 127 : required executable/launcher not found.
          - 2   : staging or process start failure.

    Notes
    -----
    - Captures *complete* stdout/stderr (text mode).
    - On POSIX, attempts to terminate the process group on timeout. On Windows,
      falls back to `proc.kill()`.
    - Does not mutate the provided `cfg_path`; a copy is placed in `workdir`.
    """
    # Check SU2 executable availability up front for a clear error.
    if not shutil.which(su2_exec):
        return (127, "", "Executable not found: {}".format(su2_exec))

    # Ensure workdir exists and stage config there (SU2 reads basename in CWD).
    cfg_base = os.path.basename(cfg_path)
    cfg_in_cwd = os.path.join(workdir, cfg_base)
    try:
        if not os.path.exists(workdir):
            os.makedirs(workdir)
        if not os.path.exists(cfg_in_cwd):
            if os.path.isfile(cfg_path):
                with open(cfg_path, "rb") as src, open(cfg_in_cwd, "wb") as dst:
                    dst.write(src.read())
            else:
                return (2, "", "Config file not found: {}".format(cfg_path))
    except Exception as e:
        return (2, "", "Failed to stage config in workdir: {}".format(e))

    # Build command: dry-run vs. serial/MPI solve.
    if dry_run:
        cmd = [su2_exec, "-d", cfg_base]
    else:
        mpi_prefix = build_mpi_cmd(mpi_exec, nprocs)
        if mpi_prefix:
            cmd = mpi_prefix + [su2_exec, cfg_base]
        else:
            # No MPI launcher (or nprocs<=1) → serial. If user asked for >1 procs and
            # no launcher exists, mimic previous behavior and error out explicitly.
            if int(nprocs or 0) > 1:
                return (127, "", "MPI launcher not found (tried: {}, mpiexec, mpirun)".format(mpi_exec))
            cmd = [su2_exec, cfg_base]

    # Run and capture full stdout/stderr; enforce optional timeout.
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            env=env
        )
    except Exception as e:
        return (2, "", "Failed to start process: {}".format(e))

    try:
        out, err = proc.communicate(timeout=timeout_s)
        return (proc.returncode, out, err)
    except subprocess.TimeoutExpired:
        # Kill process (and children for POSIX).
        try:
            if sys.platform != "win32":
                # Terminate the whole process group if possible.
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            else:
                proc.kill()
        except Exception:
            pass
        return (124, "", "Timed out after {} s".format(timeout_s))
