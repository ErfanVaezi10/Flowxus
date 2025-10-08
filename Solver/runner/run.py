# -*- coding: utf-8 -*-
# Flowxus/solver/runner/run.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 9/23/2025 (Updated: 10/08/2025)

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
import threading
import time
from typing import Optional, Tuple, List
from collections import deque

from .mpi import build_mpi_cmd
from .monitor import tail_lines  # use monitor utility for tails


def _reader_thread(stream, sink_full: List[str], sink_tail: deque,
                   stop_evt: threading.Event,
                   early_patterns: List[str], max_bad: int,
                   bad_counter: List[int]) -> None:
    """
    Stream a text handle line-by-line, mirroring output into buffers and
    triggering an early-stop signal when repeated failure patterns appear.

    Behavior
    --------
    - Appends every raw line to `sink_full` (unbounded) and to `sink_tail`
      (caller should configure `deque(maxlen=...)`).
    - Performs a case-insensitive substring check against `early_patterns`;
      increments `bad_counter[0]` on each hit and sets `stop_evt` once the
      count reaches `max_bad`.
    - Exits promptly if `stop_evt` is set externally.

    Args
    ----
    stream : TextIO
        Open, readable text stream (e.g., process.stdout) supporting `.readline()`.
        Must yield '' on EOF (standard text-mode contract).
    sink_full : List[str]
        Unbounded log sink for all lines (consider memory implications).
    sink_tail : Deque[str]
        Fixed-size tail buffer (e.g., `deque(maxlen=200)`) for quick summaries.
    stop_evt : threading.Event
        Cooperative stop signal shared with the controller thread(s).
    early_patterns : List[str]
        Substrings to match case-insensitively (assumed already lowercased or
        will be lowercased here).
    max_bad : int
        Number of pattern matches required to trigger early stop.
    bad_counter : List[int]
        Single-item list used to mutate an integer across threads
        (e.g., `[0]`). Updated in-place.

    Returns
    -------
    None

    Notes
    -----
    - Uses `iter(stream.readline, "")` for efficient line iteration without
      buffering the entire stream.
    - Leaves newline characters intact in sinks; consumers can `.rstrip()` if needed.
    - On exit (normal or early), attempts to close `stream` safely.
    """
    try:
        for line in iter(stream.readline, ""):
            if not line:
                break
            sink_full.append(line)
            sink_tail.append(line)
            s = line.lower()
            if any(p in s for p in early_patterns):
                bad_counter[0] += 1
                if bad_counter[0] >= max_bad:
                    stop_evt.set()
                    break
            if stop_evt.is_set():
                break
    finally:
        try:
            stream.close()
        except Exception:
            pass


def run_su2(cfg_path: str,
            workdir: str,
            su2_exec: str = "SU2_CFD",
            nprocs: int = 1,
            mpi_exec: str = "mpiexec",
            dry_run: bool = False,
            timeout_s: Optional[int] = None,
            env: Optional[dict] = None,
            *,
            tail_n: int = 200,
            early_stop_patterns: Tuple[str, ...] = ("nan", "floating point exception"),
            early_stop_max: int = 3) -> Tuple[int, str, str]:
    """
    Launch SU2 in serial or MPI, stream stdout/stderr, and return (rc, stdout, stderr).

    Options
    -------
    dry_run=True      → runs 'SU2_CFD -d case.cfg' (key validation only)
    timeout_s         → wall-clock timeout; on expiry, kill and return rc=124
    env               → dict of environment vars to pass to SU2
    tail_n            → lines kept for tail (used internally; full text still returned)
    early_stop_*      → pattern-based early termination once patterns appear repeatedly
    """
    if not shutil.which(su2_exec):
        return (127, "", "Executable not found: {}".format(su2_exec))

    # Ensure workdir exists and stage config there (SU2 reads basename in CWD)
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

    # Build command
    if dry_run:
        cmd = [su2_exec, "-d", cfg_base]
    else:
        mpi_prefix = build_mpi_cmd(mpi_exec, nprocs)
        if mpi_prefix:
            cmd = mpi_prefix + [su2_exec, cfg_base]
        else:
            if int(nprocs or 0) > 1:
                return (127, "", "MPI launcher not found (tried: {}, mpiexec, mpirun)".format(mpi_exec))
            cmd = [su2_exec, cfg_base]

    # Prepare streaming capture
    early_pats = [p.lower() for p in early_stop_patterns]
    early_max = int(early_stop_max)
    stop_evt = threading.Event()

    out_full: List[str] = []
    err_full: List[str] = []
    out_tail = deque(maxlen=int(tail_n))
    err_tail = deque(maxlen=int(tail_n))
    out_bad = [0]  # shared mutable counter
    err_bad = [0]

    # Start process (text mode, line-buffered)
    try:
        # On POSIX, start a new process group so we can terminate MPI children on timeout/early-stop
        preexec = os.setsid if sys.platform != "win32" else None
        proc = subprocess.Popen(
            cmd,
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
            env=env,
            preexec_fn=preexec,
        )
    except Exception as e:
        return (2, "", "Failed to start process: {}".format(e))

    # Reader threads for stdout/stderr
    t_out = threading.Thread(
        target=_reader_thread,
        args=(proc.stdout, out_full, out_tail, stop_evt, early_pats, early_max, out_bad),
        daemon=True,
    )
    t_err = threading.Thread(
        target=_reader_thread,
        args=(proc.stderr, err_full, err_tail, stop_evt, early_pats, early_max, err_bad),
        daemon=True,
    )
    t_out.start()
    t_err.start()

    # Wait with optional timeout, but also react to early-stop
    rc = None
    start = time.time()
    try:
        while True:
            if stop_evt.is_set():
                # Early termination requested (patterns detected repeatedly)
                break
            if timeout_s is not None and (time.time() - start) > float(timeout_s):
                # Timeout
                break
            rc = proc.poll()
            if rc is not None:
                break
            # light sleep to avoid busy-wait
            time.sleep(0.05)
    except KeyboardInterrupt:
        stop_evt.set()
    finally:
        # Termination logic if still running
        if proc.poll() is None and (stop_evt.is_set() or (timeout_s is not None and (time.time() - start) > float(timeout_s))):
            try:
                if sys.platform != "win32":
                    # terminate whole group
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                else:
                    proc.kill()
            except Exception:
                pass

        # Ensure threads exit
        try:
            t_out.join(timeout=1.0)
            t_err.join(timeout=1.0)
        except Exception:
            pass

        # If process still alive, wait a bit more for cleanup
        try:
            if proc.poll() is None:
                proc.wait(timeout=1.0)
        except Exception:
            pass

    # Determine final return code
    if rc is None:
        rc = proc.poll()

    # Compose full strings
    stdout = "".join(out_full)
    stderr = "".join(err_full)

    # Early-stop/timeout messages in stderr for clarity
    if stop_evt.is_set() and rc is None:
        rc = 125  # conventional "stopped by tester" code
        stderr = (stderr + ("\n[runner] Early-stop triggered after {} pattern hits.\n"
                            .format(max(out_bad[0], err_bad[0]))))
    if timeout_s is not None and (time.time() - start) > float(timeout_s) and (rc is None or rc == 0):
        rc = 124
        stderr = stderr + "\n[runner] Timed out after {} s.\n".format(timeout_s)

    # For diagnostics you might want tails (api.py can write them to tail.txt)
    _ = tail_lines(out_tail, n_tail=len(out_tail))  # example usage; tails are available if needed
    _ = tail_lines(err_tail, n_tail=len(err_tail))

    return (int(rc if rc is not None else 0), stdout, stderr)

