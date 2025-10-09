# -*- coding: utf-8 -*-
# Flowxus/main.py

"""
End-to-end driver:
  1) Load & normalize airfoil geometry
  2) Build rectangular farfield domain (+ preview)
  3) Emit geometry-only .geo (+ CSV metadata)
  4) Generate mesh via Gmsh
  5) Quick mesh plots (nodes/elements)
  6) Mesh QA summary + a few stats plots
"""

import os
import logging
import json
import sys

from pathlib import Path
from geometry.geo.geo_loader import GeometryLoader
from geometry.domain.domain_builder import DomainBuilder
from post.plot_geo import plot_domain
from post.plot_mesh import plot_msh_2d_nodes, plot_msh_2d_elements
from mesh.stats.export import write_summary_csv, write_summary_json, write_summary_excel
from mesh.api import build_mesh
from mesh.stats.report import summarize
from mesh.checks import run_checks
from solver.api import prepare_case, run_case, post_case
from post.plot_stats import (
    plot_element_type_distribution,
    plot_node_valence_hist,
    plot_tri_min_angle_hist,
    plot_tri_aspect_hist,
    plot_quad_skew_hist,
    plot_h_vs_distance,
)


if __name__ == "__main__":
    # ------------------------------------------------------------------
    # 0) Logging
    # ------------------------------------------------------------------
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    log = logging.getLogger("Flowxus")

    # Ensure output folders exist
    os.makedirs("mesh", exist_ok=True)
    os.makedirs("plots", exist_ok=True)

    # ------------------------------------------------------------------
    # 1) Load & normalize geometry
    # ------------------------------------------------------------------
    geo = GeometryLoader("naca0010.dat")
    geo.load()
    geo.normalize(translate_to_le=True, scale_to_chord1=True)
    geo.plot(show=True, save_path="airfoil.png")

    # ------------------------------------------------------------------
    # 2) Build rectangular farfield domain (+ preview)
    #    box_dims: distances from the leading edge-based ref box
    # ------------------------------------------------------------------
    box_dims = {"up": 5.0, "down": 5.0, "front": 5.0, "back": 10.0}
    domain = DomainBuilder(geo, box_dims)

    plot_domain(
        airfoil_pts=geo.get_closed_points(),
        bbox=domain.bounding_box,
        physical_tags=domain.physical_tags,
        show=True,
        save_path="domain.png",
    )

    # ------------------------------------------------------------------
    # 3) Emit geometry-only .geo and airfoil CSV metadata
    #    (useful for provenance and third-party tools)
    # ------------------------------------------------------------------
    out_geo = "domain.geo"
    out_csv = "airfoil_scalars.csv"
    domain.generate_geo_file(
        export_path=out_geo,
        emit_metadata=True,
        emit_scalars_csv=True,
        scalars_path=out_csv,
        provenance={"version": "0.4.0"},
    )
    log.info("Artifacts written: %s, %s (and airfoil.png/domain.png if plotting enabled)", out_geo, out_csv)

    # ------------------------------------------------------------------
    # 4) Mesh with Gmsh via Flowxus mesh API
    #    - Set n_layers > 0 to activate BL layers around the airfoil.
    #    - 'airfoil' size controls near-wall size via the distance threshold field.
    # ------------------------------------------------------------------
    inflation = {
        "first_layer": 1.0e-3,   # used only if n_layers > 0
        "n_layers": 15,          # 0 => BL off; >0 => BL on
        "growth_rate": 1.1,      # used only if n_layers > 0
    }


    sizes = {
        "inlet": 0.3,
        "outlet": 0.3,
        "top": 0.3,
        "bottom": 0.3,
        "interior": 0.1,
        "airfoil": 0.05,         # near-wall target size
    }

    msh_path = "mesh/domain.msh"
    geo_for_meshing = "mesh/mesh_ready.geo"   # writer writes here
    msh_format = "msh2"                       # "msh4" or "msh2" (often friendlier for downstream tools)

    msh_out = build_mesh(
        domain=domain,
        geo_path=geo_for_meshing,
        msh_path=msh_path,
        inflation_settings=inflation,
        mesh_size_settings=sizes,
        gmsh_algo=None,                # or an int (e.g., 6 or 8) to force an algorithm
        validate_groups=True,          # requires meshio; checks Physical names
        curvature_from_geometry=True,  # let Gmsh adapt size from curvature
        hybrid_bl=True,                # BL quads near wall when n_layers > 0
        force_algo_for_bl=False,       # let writer favor tris outside BL
        msh_format=msh_format,
    )
    log.info("Mesh written to: %s", msh_out)

    # ------------------------------------------------------------------
    # 5) Quick mesh plots (optional)
    # ------------------------------------------------------------------
    try:
        plot_msh_2d_nodes(msh_out, show=True, save_path="mesh_nodes.png")
        plot_msh_2d_elements(msh_out, show=True, save_path="mesh_elements.png")
    except Exception as e:
        log.warning("Skipping quick mesh plots: %s", e)

    # ------------------------------------------------------------------
    # 6) Mesh QA summary + selected plots from stats package
    # ------------------------------------------------------------------
    summary = summarize(msh_out, wall_name="airfoil", include_bl=True)
    log.info("Mesh summary:\n%s", summary)

    try:
        plot_element_type_distribution(msh_out, show=False, save_path="elements.png")
        plot_node_valence_hist(msh_out, show=False, save_path="valence.png")
        plot_tri_min_angle_hist(msh_out, show=False, save_path="tri_min_angle.png")
        plot_tri_aspect_hist(msh_out, show=False, save_path="tri_aspect.png")
        plot_quad_skew_hist(msh_out, show=False, save_path="quad_skew.png")
        plot_h_vs_distance(msh_out, wall_name="airfoil", show=False, save_path="h_vs_d.png")
    except Exception as e:
        log.warning("Skipping stats plots: %s", e)

    out_dir = ""
    csv_path = write_summary_csv(summary,  os.path.join(out_dir, "summary.csv"))
    json_path = write_summary_json(summary, os.path.join(out_dir, "summary.json"))
    xlsx_path = write_summary_excel(summary, os.path.join(out_dir, "summary.xlsx"))

    print("Stats written:")
    print(" - CSV :", csv_path)
    print(" - JSON:", json_path)
    print(" - XLSX:", xlsx_path if xlsx_path else "(pandas not installed)")

    # --- Post-mesh validation (hard stop on errors) ---
    CHECKS_CONFIG = None  # or e.g. {"thresholds": {"min_angle_deg": 25.0}}

    findings = run_checks(msh_path, CHECKS_CONFIG)

    # Persist a report next to the mesh (handy for debugging/CI)
    report_path = Path(msh_out).with_suffix(".checks.json")
    report_path.write_text(json.dumps(findings, indent=2))

    if not findings["ok"]:
        # Collect only the failing ERROR rules (warnings are allowed)
        failures = []
        for rid, f in findings["rules"].items():
            if f.get("severity") == "error" and not f.get("ok", True):
                failures.append((rid, int(f.get("count", 0)), f.get("examples", [])[:3]))

        # Human-friendly message
        lines = [
            "❌ Mesh validation failed. The following error checks did not pass:",
            *(f"  - {rid}: count={cnt}"
              + (f", examples={examples}" if examples else "")
              for rid, cnt, examples in failures),
            f"➡ See full report: {report_path}",
        ]
        print("\n".join(lines), file=sys.stderr)
        # Hard stop: do not proceed to next steps
        sys.exit(1)

    print(f"✅ Mesh checks passed. Report: {report_path}")

    # ------------------------------------------------------------------
    # 7) SU2: prepare, run, post-process
    # ------------------------------------------------------------------
    su2_params = {
        "MACH_NUMBER": 0.2,
        "AOA": 0.0,  # degrees
        "REYNOLDS_NUMBER": 1.0e6,
        "REYNOLDS_LENGTH": 1.0,  # chord = 1 after normalization
        "ITER": 500,
        "CFL_NUMBER": 5.0,
        # Optional v7+ tweaks, enable as needed:
        # "OUTPUT_FILES": "(RESTART, SURFACE_PARAVIEW)",
        # "OUTPUT_WRT_FREQ": 200,
        # "HISTORY_WRT_FREQ_INNER": 1,
        # "SCREEN_WRT_FREQ_INNER": 1,
    }

    case = prepare_case(
        msh_out,
        workdir="case_su2",
        cfg_params=su2_params,
        marker_euler=("airfoil",),
        marker_far=("inlet", "outlet", "top", "bottom"),
    )

    # Optional environment control (threading, etc.)
    # env_run = dict(os.environ, OMP_NUM_THREADS="2")

    res = run_case(
        case,
        su2_exec="SU2_CFD",
        nprocs=2,  # set >1 to enable MPI
        mpi_exec="mpiexec",  # or "mpirun" if that’s your launcher
        timeout_s=3600,  # return rc=124 on timeout
    )

    if not res["ok"]:
        log.error("SU2 run failed.\n%s", res["tail"])
        if res.get("history_path"):
            log.error("History file: %s", res["history_path"])
    else:
        log.info("SU2 run finished.\n%s", res["tail"])
        if res.get("history_path"):
            log.info("History file: %s", res["history_path"])

    summary_su2 = post_case(case)
    log.info("SU2 summary: %s", summary_su2)
