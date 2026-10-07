"""Creo 256-channel phase-only backend/constraint comparison and signed T3 checks."""
from dataclasses import replace
from importlib.metadata import version
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))
from acousticstudio.field_model import FieldConfig
from acousticstudio.force_analysis import AnalysisSettings, FieldSnapshot, ForceAnalyzer, json_result
from acousticstudio.geometry import load_creo_tunnel
from acousticstudio.hologram import HologramSettings, HologramSolver, TRAP_TYPES, TrapTarget


def main():
    geometry = load_creo_tunnel()
    sources = np.array([e['position_mm'] for e in geometry['elements']])
    normals = np.array([e['normal'] for e in geometry['elements']])
    gains = np.ones(256)
    rows, diagnoses = [], []
    settings = HologramSettings(iterations=50, phase_tolerance_rad=0.)
    for model in ('point_source', 'ultraino_sinc', 'circular_piston'):
        config = FieldConfig(model=model, aperture_radius_mm=None if model == 'point_source' else 4.5)
        for trap_type in TRAP_TYPES:
            direction = (0., 0., 1.) if trap_type == 'standing_wave' else (1., 0., 0.)
            targets = [TrapTarget((-10., -3., 5.), trap_type, direction=direction),
                       TrapTarget((8., 4., -7.), trap_type, direction=direction)]
            solver = HologramSolver()
            expected = solver.solve(sources, normals, gains, config, targets, settings)
            for mode in range(4):
                actual = solver.solve(sources, normals, gains, config, targets, settings,
                                      mode_idx=mode, has_taichi=True, has_pytorch=True)
                before, after = np.exp(1j * expected['phases_rad']), np.exp(1j * actual['phases_rad'])
                common = np.angle(np.vdot(before, after))
                error = float(np.max(np.abs(after * np.exp(-1j * common) - before)))
                field_reference = expected['field_real'] + 1j * expected['field_imag']
                field_actual = (actual['field_real'] + 1j * actual['field_imag']) * np.exp(-1j * common)
                field_error = float(np.linalg.norm(field_actual - field_reference) / np.linalg.norm(field_reference))
                assert error < 1e-8 and field_error < 1e-8, (model, trap_type, mode, error, field_error)
                rows.append(dict(model=model, trap_type=trap_type, mode=mode, channels=256,
                                 phase_phasor_error_after_common_phase=error, relative_field_error=field_error,
                                 initial_metrics=expected['initial_metrics'], metrics=actual['metrics'],
                                 iterations=actual['iterations_completed'], elapsed_ms=actual['elapsed_seconds'] * 1000,
                                 cache_hit=actual['cache_hit'], backend=actual['backend']))
            frozen = FieldSnapshot(sources, normals, expected['phases_rad'], gains, config)
            for target in targets:
                result = ForceAnalyzer(frozen, AnalysisSettings(samples=5)).analyze(target.position_mm)
                diagnoses.append(dict(model=model, trap_type=trap_type, position_mm=target.position_mm,
                                      restoring=result['restoring'], converged=result['converged'],
                                      centre_force=result['centre_force'], conditional_centre_residual=result['conditional_centre_residual'],
                                      pressure_calibrated=False, particle_provenance='example',
                                      gravity_equilibrium_status=result['gravity_equilibrium_status']))
    hashes = {name: hashlib.sha256((REPO / name).read_bytes()).hexdigest() for name in
              ('src/acousticstudio/hologram.py', 'src/acousticstudio/field_model.py', 'src/acousticstudio/sonic_core.dll',
               '구상도/outputs/panel_8faces_32ch_R1/array_positions_256.json')}
    report = dict(python=sys.executable, python_version=sys.version.split()[0],
                  packages={name: version(name) for name in ('numpy', 'scipy', 'numba', 'levitate', 'taichi', 'torch')},
                  settings=settings.to_dict(), hashes=hashes, pressure_calibrated=False, hardware_used=False,
                  synthetic_directivity_radius_mm=4.5, actual_aperture_radius_mm=None,
                  timing_note='warm matrix cache, one verification run per case, no 1-2 ms claim',
                  comparisons=rows, signed_force_diagnoses=diagnoses)
    Path(__file__).with_name('t4_numerical_result.json').write_text(
        json.dumps(json_result(report), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(backend_cases=len(rows), signed_force_diagnoses=len(diagnoses),
                         max_phasor_error=max(row['phase_phasor_error_after_common_phase'] for row in rows)), indent=2))


if __name__ == '__main__':
    main()
