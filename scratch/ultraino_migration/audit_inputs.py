"""Read-only CAD/input and Python environment audit for the migration plan.

Run with the existing AcousticStudio interpreter. No CAD regeneration, package
installation, GUI startup, GPU initialization, or serial connection is performed.
An evidence JSON is written only when --out is supplied.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "구상도/outputs/panel_8faces_32ch_R1"
CAD = DESIGN / "mechanical/creo32_frame_R2"
PACKAGES = [
    "numpy", "numba", "PySide6", "pyvista", "pyvistaqt", "vtk",
    "matplotlib", "levitate", "pyserial", "pytest", "scipy",
    "k-wave-python", "torch", "taichi", "psutil", "GPUtil",
    "cadquery", "cadquery-ocp",
]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row_transform(vector, matrix):
    """The archived Creo matrices use row vectors and last-row translation."""
    return [sum(vector[i] * matrix[i][j] for i in range(4)) for j in range(4)]


def matrix_signature(model, matrix):
    return model.removesuffix(".asm").removesuffix(".prt"), tuple(
        round(float(value), 8) for row in matrix for value in row
    )


def audit_geometry():
    positions = read_json(DESIGN / "array_positions_256.json")
    geometry = read_json(CAD / "geometry_checks.json")
    manifest = read_json(CAD / "manifest.json")
    reopened = read_json(CAD / "validation/native_reopen_report.json")
    mapping = read_json(DESIGN / "physical_to_software_channel_map.json")
    elements = positions["elements"]
    assert positions["units"] == geometry["units"] == "mm"
    assert positions["parameters"] == geometry["parameters"]
    assert len(elements) == 256
    assert {e["channel"] for e in elements} == set(range(256))
    assert Counter(e["face"] for e in elements) == Counter({i: 32 for i in range(8)})
    assert {e["fpga_physical_channel"] for e in elements} == set(range(256))
    assert set(mapping["channel_map"]) == set(range(256))
    assert len(mapping["channel_map"]) == 256
    tx_parts = {p["reference"]: p for p in geometry["panel_components"]
                if p["reference"].startswith("T") and p["reference"][1:].isdigit()}
    assert len(tx_parts) == 32 and len(geometry["face_matrices"]) == 8
    max_position_error = max_normal_error = 0.0
    for element in elements:
        assert element["channel"] == element["face"] * 32 + element["local_channel"]
        assert element["local_channel"] == element["row"] * 4 + element["column"]
        part_matrix = tx_parts[element["reference"]]["matrix"]
        face_matrix = geometry["face_matrices"][element["face"]]
        # tx16_r1 extends from z=-12.5 (emitting face) to z=0 (PCB front).
        position = row_transform(row_transform([0, 0, -12.5, 1], part_matrix), face_matrix)[:3]
        normal = row_transform(row_transform([0, 0, -1, 0], part_matrix), face_matrix)[:3]
        max_position_error = max(max_position_error, math.dist(position, element["position_mm"]))
        max_normal_error = max(max_normal_error, math.dist(normal, element["normal"]))
        assert abs(math.sqrt(sum(v * v for v in element["normal"])) - 1) < 1e-10
        assert abs(element["normal"][2]) < 1e-10
        assert sum(a * b for a, b in zip(element["position_mm"][:2], element["normal"][:2])) < 0
        assert mapping["channel_map"][element["fpga_physical_channel"]] == element["channel"]
    assert max_position_error < 1e-8 and max_normal_error < 1e-8
    expected_panel = Counter(matrix_signature(p["model"], p["matrix"]) for p in geometry["panel_components"])
    actual_panel = Counter(matrix_signature(p["model"], p["matrix"]) for p in reopened["panelComponents"])
    expected_top = Counter(matrix_signature(p["model"], p["matrix"]) for p in geometry["top_components"])
    actual_top = Counter(matrix_signature(p["model"], p["matrix"]) for p in reopened["tunnelComponents"])
    assert expected_panel == actual_panel and expected_top == actual_top
    native_hashes = {}
    for filename, expected_hash in manifest["files"].items():
        relative = Path(filename.replace("\\", "/"))
        if relative.parts[0] == "native" and relative.suffix in {".asm", ".prt"}:
            actual_hash = sha256(CAD / relative)
            assert actual_hash == expected_hash, f"Native model changed: {relative}"
            native_hashes[relative.as_posix()] = actual_hash
    assert len(native_hashes) == 13
    assert sha256(DESIGN / "panel_8faces_32ch_R1.kicad_pcb") == geometry["source_pcb_sha256"]
    face_zero = [e for e in elements if e["face"] == 0]
    source_paths = [
        DESIGN / "parameters.json", DESIGN / "array_positions_256.json",
        DESIGN / "channel_map.csv", DESIGN / "physical_to_software_channel_map.json",
        CAD / "geometry_checks.json", CAD / "validation/native_reopen_report.json",
    ]
    return {
        "ok": True, "pcb_count": 8, "channels_per_pcb": 32, "channels": 256,
        "banks_per_pcb": 2, "channels_per_bank": 16, "tunnel_axis": "Z",
        "parameters": positions["parameters"],
        "face_zero_transverse_mm": sorted({e["position_mm"][1] for e in face_zero}),
        "axial_levels_mm": sorted({e["position_mm"][2] for e in face_zero}),
        "max_position_error_mm": max_position_error, "max_normal_error": max_normal_error,
        "native_reopen_placement_matches_inputs": True,
        "native_files_matching_archived_manifest": len(native_hashes),
        "native_sha256": native_hashes,
        "input_sha256": {p.relative_to(ROOT).as_posix(): sha256(p) for p in source_paths},
        "channel_map_is_candidate_not_measured": True,
        "scope": "Current files compared with archived Creo placement evidence; no live Creo session or acoustic experiment.",
    }


def probe_environment(executable):
    code = (
        "import sys,json,importlib.metadata as m\n"
        f"names={PACKAGES!r}\nversions={{}}\n"
        "for n in names:\n"
        " try: versions[n]=m.version(n).strip()\n"
        " except m.PackageNotFoundError: versions[n]=None\n"
        "print(json.dumps({'executable':sys.executable,'version':sys.version.split()[0],"
        "'prefix':sys.prefix,'base_prefix':sys.base_prefix,'packages':versions}))\n"
    )
    result = subprocess.run([str(executable), "-c", code], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--probe-python", action="append", default=[])
    parser.add_argument("--check-app-imports", action="store_true")
    args = parser.parse_args()
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "workspace_root": str(ROOT), "geometry": audit_geometry(),
        "environments": [probe_environment(p) for p in [sys.executable, *args.probe_python]],
        "tools_on_path": {name: shutil.which(name) for name in ["python", "py", "java", "node", "git", "cl"]},
        "project_environment_paths": {
            name: (ROOT / name).exists() for name in [
                ".venv", "venv", "구상도/scratch/creo_cad_env",
                "구상도/scratch/creo32_env", "구상도/scratch/pcb32_tools",
                "구상도/scratch/pcb32_support",
            ]
        },
        "app_imports": {}, "package_installation_performed": False,
        "app_started": False, "hardware_accessed": False, "tests_run": [],
    }
    if args.check_app_imports:
        for name in ["numpy", "numba", "PySide6.QtCore", "pyvista", "pyvistaqt", "vtk", "matplotlib", "levitate", "serial", "pytest"]:
            try:
                importlib.import_module(name)
                result["app_imports"][name] = {"ok": True}
            except Exception as exc:
                result["app_imports"][name] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        assert all(value["ok"] for value in result["app_imports"].values()), "App dependency import failed"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"geometry": result["geometry"]["ok"], "channels": 256,
                      "max_position_error_mm": result["geometry"]["max_position_error_mm"],
                      "native_files_checked": len(result["geometry"]["native_sha256"]),
                      "environments_checked": len(result["environments"]),
                      "imports_checked": len(result["app_imports"]),
                      "out": str(args.out) if args.out else None}, ensure_ascii=True))


if __name__ == "__main__":
    main()
