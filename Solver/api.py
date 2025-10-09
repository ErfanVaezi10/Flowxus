# -*- coding: utf-8 -*-
# Flowxus/solver/api.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/15/2025 (Updated: 10/09/2025)

Purpose
-------
High-level SU2 case orchestration API. Given a Gmsh mesh and minimal parameters, this 
module prepares a runnable SU2 workspace (mesh + config + manifest), executes solver 
(serial/MPI), tails output for quick diagnostics, and parses history to emit concise 
residual summaries and quick-look plots.

Main Tasks
----------
    1. Prepare: convert `.msh`→`.su2`, resolve marker labels/IDs, compose & write `case.cfg`.
    2. Run: launch SU2 (dry-run or solve) with timeout and stdout/stderr capture.
    3. Post: read `history.*` (csv/dat[.gz]), summarize residuals, save PNG quick-looks.
    4. Sweep: convenience helper to run a list of parameter cases and index results.

Notes
-----
- Marker resolution supports both Physical-ID–based meshes and name-preserving meshes.
- `build.config` is the single source of truth for config assembly/validation.
- History parsing normalizes headers (e.g., RMS_* → RES_*); plotting is best-effort.
"""

import os
import time
import json

from .interface.io import msh_to_su2
from .runner.run import run_su2
from .build.config import build_cfg, render_cfg, write_cfg
from .interface.history import read_history, last_row
from .ops.history import plot_ns_residuals, plot_turb_residuals


def _markers_to_tokens(requested, id_map):
    """
    Map marker names to mesh tokens for SU2 boundary specification.

    Behavior
    --------
    - If a requested name exists in `id_map` (Gmsh Physical group), return its int ID.
    - Otherwise, keep the original string (for name-preserving meshes).

    Args
    ----
    requested : str | Iterable[str] | None
        Single marker name or an iterable of names (or None to pass through).
    id_map : Mapping[str, int]
        Physical-Name → ID mapping extracted during `.msh`→`.su2` conversion.

    Returns
    -------
    None | str | Tuple[int|str, ...]
        None if `requested` is None; otherwise the token(s) suitable for SU2 config.
    """
    if requested is None:
        return None
    if isinstance(requested, (list, tuple)):
        return tuple(id_map.get(name, name) for name in requested)
    return id_map.get(requested, requested)


def _timestamped_dir(base="case_su2"):
    """
    Create a timestamped working directory under `base` (race-safe).

    Returns
    -------
    str
        Absolute or relative path to the newly created directory, e.g.,
        `base/run_YYYYMMDD_HHMMSS`.
    """
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(base, "run_" + ts)
    os.makedirs(path, exist_ok=True)  # race-safe
    return path


def _find_history_file(workdir):
    """
    Locate a SU2 history file in `workdir`.

    Checks common names in order: `history.csv`, `history.dat`, and their `.gz` variants.

    Returns
    -------
    Optional[str]
        Path to the first found candidate; None if absent.
    """
    candidates = ("history.csv", "history.dat", "history.csv.gz", "history.dat.gz")
    for name in candidates:
        p = os.path.join(workdir, name)
        if os.path.exists(p):
            return p
    return None


def prepare_case(msh_path,
                 workdir=None,
                 cfg_params=None,
                 *,
                 # Either specify marker_map, or (legacy) marker_euler/marker_far
                 marker_map=None,
                 marker_euler=("airfoil",),
                 marker_far=("inlet", "outlet", "top", "bottom"),
                 bc_params=None):
    """
    Prepare a runnable SU2 case folder from a Gmsh mesh and parameters.

    Steps
    -----
    1) Convert `<msh_path>` → `mesh.su2` (forced 2D).
    2) Resolve marker labels to tokens (int IDs when available; names otherwise).
    3) Build a config dict via `build_cfg`, render to text, and write `case.cfg`.
    4) Emit a small `manifest.json` for provenance.

    Args
    ----
    msh_path : str
        Path to input Gmsh `.msh`.
    workdir : Optional[str], optional
        Working directory to create/use. If None, a timestamped folder is created.
    cfg_params : Optional[dict], optional
        User overrides to feed into `build_cfg`.
    marker_map : Optional[dict], keyword-only
        Preferred explicit mapping for SU2 markers (overrides legacy arguments).
    marker_euler : Iterable[str] | None, keyword-only
        Legacy convenience for inviscid boundary markers if `marker_map` is None.
    marker_far : Iterable[str] | None, keyword-only
        Legacy convenience for farfield/IO markers if `marker_map` is None.
    bc_params : Optional[dict], keyword-only
        Per-marker BC parameters passed through to `build_cfg`.

    Returns
    -------
    dict
        {
          "workdir": str,
          "mesh_su2": str,
          "cfg_path": str,
          "id_map": Dict[str,int]
        }

    Raises
    ------
    RuntimeError, OSError
        Propagated from mesh conversion or file I/O if failures occur.
    """
    if workdir is None:
        workdir = _timestamped_dir("case_su2")
    else:
        if not os.path.exists(workdir):
            os.makedirs(workdir)

    mesh_su2 = os.path.join(workdir, "mesh.su2")
    mesh_su2, id_map = msh_to_su2(msh_path, mesh_su2)

    # Legacy fallback (used only when no explicit marker_map is supplied)
    m_eul = _markers_to_tokens(marker_euler, id_map)
    m_far = _markers_to_tokens(marker_far, id_map)

    # Build config (config.py resolves names→IDs when marker_map is used)
    cfg = build_cfg(
        cfg_params or {},
        mesh_su2,
        workdir,
        marker_map=marker_map,
        marker_euler=m_eul,   # honored if marker_map is None
        marker_far=m_far,
        bc_params=bc_params,
        id_map=id_map,
    )

    cfg_path = os.path.join(workdir, "case.cfg")
    cfg_text = render_cfg(cfg)
    write_cfg(cfg_text, cfg_path)

    # Save a tiny manifest for provenance
    manifest = {
        "msh_path": os.path.abspath(msh_path),
        "mesh_su2": os.path.abspath(mesh_su2),
        "cfg_path": os.path.abspath(cfg_path),
        "cfg_params": cfg_params or {},
        "marker_map": marker_map or {},
        "resolved_markers": {k: cfg.get(k) for k in cfg.keys() if k.startswith("MARKER_")},
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(workdir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return {"workdir": workdir, "mesh_su2": mesh_su2, "cfg_path": cfg_path, "id_map": id_map}


def run_case(case_info,
             su2_exec="SU2_CFD",
             nprocs=1,
             mpi_exec="mpiexec",
             dry_run=False,
             *,
             timeout_s=None,
             env=None,
             tail_n=200):
    """
    Execute SU2 for a prepared case and summarize its output.

    Builds the command (serial/MPI or dry-run), runs SU2 with an optional timeout,
    captures stdout/stderr, writes a `tail.txt` for quick inspection, and locates
    a history file if produced.

    Args
    ----
    case_info : dict
        Output of `prepare_case` with keys: workdir, mesh_su2, cfg_path, id_map.
    su2_exec : str, optional
        SU2 executable (default: "SU2_CFD").
    nprocs : int, optional
        MPI ranks (default: 1 → serial).
    mpi_exec : str, optional
        MPI launcher (default: "mpiexec").
    dry_run : bool, optional
        If True, invoke SU2 `-d` to validate configuration only.
    timeout_s : Optional[int], keyword-only
        Kill job and return rc=124 if exceeded.
    env : Optional[dict], keyword-only
        Environment variables for the child process.
    tail_n : int, optional
        Number of trailing lines to include in the tail summary (cap: 25 shown).

    Returns
    -------
    dict
        {
          "ok": bool,
          "rc": int,
          "tail": str,
          "workdir": str,
          "history_path": Optional[str]
        }
    """
    # run the solver
    rc, out, err = run_su2(
        case_info["cfg_path"],
        case_info["workdir"],
        su2_exec,
        nprocs,
        mpi_exec,
        dry_run=dry_run,
        timeout_s=timeout_s,
        env=env,
    )
    ok = (rc == 0)

    tail_out = "\n".join((out or "").splitlines()[-min(25, tail_n):])
    tail_err = "\n".join((err or "").splitlines()[-min(25, tail_n):])
    tail = tail_out if ok else (tail_out + ("\n--- STDERR (tail) ---\n" + tail_err if tail_err else ""))

    # write tail.txt for quick inspection
    try:
        with open(os.path.join(case_info["workdir"], "tail.txt"), "w", encoding="utf-8") as f:
            f.write(tail)
    except Exception:
        pass

    # locate the history file (useful for callers)
    history_path = _find_history_file(case_info["workdir"])

    return {
        "ok": ok,
        "rc": rc,
        "tail": tail,
        "workdir": os.path.abspath(case_info["workdir"]),
        "history_path": history_path,
    }


def post_case(case_info):
    """
    Parse history and emit a concise residual summary; save quick-look plots.

    Produces `residuals_ns.png` and `residuals_turb.png` (best-effort; errors ignored).

    Args
    ----
    case_info : dict
        Output of `prepare_case` (must include `workdir`).

    Returns
    -------
    dict
        {
          "n_iters": int,           # number of parsed data rows (0 if none)
          "last": Dict[str, float]  # ITER + residuals only
        }
    """
    workdir = case_info["workdir"]
    history_path = _find_history_file(workdir)
    if history_path is None:
        return {"n_iters": 0, "last": {}}

    headers, rows = read_history(history_path, limit=2000)

    # save quick-look plots (optional)
    try:
        fig, _ = plot_ns_residuals(workdir)
        fig.savefig(os.path.join(workdir, "residuals_ns.png"))
        fig, _ = plot_turb_residuals(workdir)
        fig.savefig(os.path.join(workdir, "residuals_turb.png"))
    except Exception:
        pass

    # last row as dict, then filter to ITER + residuals only
    last = last_row((headers, rows))
    allowed = {"ITER"}
    allowed.update(k for k in last.keys() if k.startswith("RES_"))
    last_filtered = {k: v for k, v in last.items() if k in allowed}

    return {
        "n_iters": len(rows),
        "last": last_filtered,
    }


# -------- Optional convenience: simple sweep --------
def run_sweep(msh_path, cases, base_workdir="case_su2_sweep", su2_exec="SU2_CFD", nprocs=1):
    """
    Run a list of parameter cases and collect summarized results.

    For each `params` in `cases`, prepares a dedicated workdir, runs SU2, posts
    results, and appends a summary entry. Writes `index.json` with all entries.

    Args
    ----
    msh_path : str
        Path to input Gmsh `.msh` used for all cases (shared geometry).
    cases : Iterable[dict]
        Each dict is `cfg_params` for one run.
    base_workdir : str, optional
        Parent directory for all case folders (default: "case_su2_sweep").
    su2_exec : str, optional
        SU2 executable (default: "SU2_CFD").
    nprocs : int, optional
        MPI ranks for each run (default: 1).

    Returns
    -------
    List[dict]
        One summary per case, each augmented with:
        - ok (bool), rc (int), tail_path (str), history_path (str|None), params (dict).
    """
    results = []
    for i, params in enumerate(cases):
        workdir = os.path.join(base_workdir, "case_{:03d}".format(i + 1))
        info = prepare_case(msh_path, workdir=workdir, cfg_params=params)
        res = run_case(info, su2_exec=su2_exec, nprocs=nprocs)
        summary = post_case(info)
        # enrich the summary
        summary.update({
            "ok": bool(res.get("ok")),
            "rc": int(res.get("rc", -1)),
            "tail_path": os.path.join(workdir, "tail.txt"),
            "history_path": res.get("history_path"),
            "params": dict(params),
        })
        results.append(summary)
    # Optionally write an index.json
    if not os.path.exists(base_workdir):
        os.makedirs(base_workdir)
    with open(os.path.join(base_workdir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    return results
