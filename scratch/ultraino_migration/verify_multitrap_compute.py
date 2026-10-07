"""Reproduce CPU-only Torch fallback and real CUDA Kinoforms on the Creo array."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from statistics import median
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from acousticstudio.compute_devices import probe_compute_devices
from acousticstudio.force_analysis import json_result
from acousticstudio.geometry import load_creo_tunnel
from acousticstudio.hologram import HologramSettings, HologramSolver, TrapTarget
from acousticstudio.field_model import FieldConfig


def main():
    devices = probe_compute_devices()
    geometry = load_creo_tunnel()
    sources = np.array([element['position_mm'] for element in geometry['elements']])
    normals = np.array([element['normal'] for element in geometry['elements']])
    gains = np.ones(256); gains[5] = 0.; gains[7] = .7
    config = FieldConfig()
    settings = HologramSettings(iterations=50, phase_tolerance_rad=0.)
    cases = {
        'two_focus': [TrapTarget((-12., -8., -15.)), TrapTarget((12., 8., 15.))],
        'eight_mixed': [TrapTarget((-12., -8., -20.)), TrapTarget((12., -8., -15.), 'twin'),
                        TrapTarget((-12., 8., -5.), 'standing_wave', direction=(0., 0., 1.)),
                        TrapTarget((12., 8., 5.)), TrapTarget((-12., -8., 15.), 'twin', direction=(0., 1., 0.)),
                        TrapTarget((12., -8., 25.), 'standing_wave', direction=(0., 0., 1.)),
                        TrapTarget((-12., 8., 30.)), TrapTarget((12., 8., 35.))],
    }
    records = {}
    for name, targets in cases.items():
        modes = {}
        reference = None
        for mode in (0, 1, 2, 3):
            solver = HologramSolver()
            first = solver.solve(sources, normals, gains, config, targets, settings,
                                 mode_idx=mode, has_taichi=devices.taichi_available,
                                 has_pytorch=devices.torch_installed)
            # Mode 3 intentionally probes the requested CUDA branch with CPU Torch installed.
            runs = [solver.solve(sources, normals, gains, config, targets, settings,
                                 mode_idx=mode, has_taichi=devices.taichi_available,
                                 has_pytorch=devices.torch_installed) for _ in range(3)]
            result = runs[-1]
            if reference is None:
                reference = result
            phasor_error = float(np.max(np.abs(np.exp(1j * result['phases_rad']) - np.exp(1j * reference['phases_rad']))))
            field = result['field_real'] + 1j * result['field_imag']
            reference_field = reference['field_real'] + 1j * reference['field_imag']
            np.testing.assert_allclose(np.exp(1j * result['phases_rad']),
                                       np.exp(1j * reference['phases_rad']), atol=1e-8)
            np.testing.assert_allclose(field, reference_field, rtol=1e-9, atol=1e-7)
            if mode == 2 and devices.taichi_available:
                assert result['backend']['backend'] == f'Taichi {devices.taichi_arch}'
                assert result['backend']['fallback_reason'] is None
            if mode == 3 and not devices.cuda_available:
                assert result['backend']['backend'] == 'Numba CPU' and result['backend']['fallback_reason']
            assert result['phases_rad'][5] == 0. and result['iterations_completed'] == 50
            modes[str(mode)] = dict(backend=result['backend'], first_seconds=first['elapsed_seconds'],
                                   warm_seconds=[run['elapsed_seconds'] for run in runs],
                                   warm_median_seconds=median(run['elapsed_seconds'] for run in runs),
                                   max_phasor_error_vs_cpu=phasor_error,
                                   max_field_error_vs_cpu=float(np.max(np.abs(field - reference_field))),
                                   relative_residual=result['metrics']['relative_residual'])
        records[name] = dict(targets=[target.to_dict() for target in targets],
                             virtual_point_count=len(reference['virtual_points_mm']), modes=modes)
    code = ['src/acousticstudio/compute_devices.py', 'src/acousticstudio/app.py',
            'src/acousticstudio/hologram.py', 'src/acousticstudio/hologram_ui.py',
            'src/acousticstudio/field_model.py', 'src/acousticstudio/field_backends.py',
            'src/acousticstudio/sonic_wrapper.py', 'src/acousticstudio/sonic_core.dll']
    source_array = ROOT / '구상도/outputs/panel_8faces_32ch_R1/array_positions_256.json'
    report = dict(schema_version=1, python=sys.executable, devices=asdict(devices),
                  default_mode=devices.preferred_mode(), array='Creo R2 8 faces × 8 PCBs × 32 channels = 256',
                  settings=settings.to_dict(), field_config=config.to_dict(), cases=records,
                  gpu_scope='Complex matvec only. Propagation, constraints, phase projection and diagnostics use CPU.',
                  transfers='Matrices/vectors are copied for every matvec; results return to CPU every iteration.',
                  timing_scope='Solver wall time including CPU work and transfers; first run may include JIT. Warm runs reuse Green cache. No hardware timing.',
                  no_environment_changes=True, no_serial_io=True,
                  code_sha256={path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in code},
                  source_array_sha256=hashlib.sha256(source_array.read_bytes()).hexdigest())
    output = Path(__file__).with_name('multitrap_compute_result.json')
    output.write_text(json.dumps(json_result(report), ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps(dict(report=str(output), devices=asdict(devices), default_mode=report['default_mode'],
                          warm_median_ms={name: {mode: round(data['warm_median_seconds'] * 1000, 3)
                                               for mode, data in record['modes'].items()} for name, record in records.items()}), ensure_ascii=False))


if __name__ == '__main__':
    main()
