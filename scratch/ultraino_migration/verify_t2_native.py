"""Check the freshly built scratch DLL before replacing the runtime artifact."""
import ctypes
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))
from acousticstudio import field_backends, sonic_wrapper
from acousticstudio.field_model import FieldConfig, propagation_matrix
from acousticstudio.geometry import load_creo_tunnel
from acousticstudio.phase_engine import PhaseEngine


def main():
    dll_path = Path(__file__).with_name('sonic_core_t2.dll')
    library = ctypes.CDLL(str(dll_path))
    pointer = np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS')
    library.complex_matvec.argtypes = [pointer] * 4 + [ctypes.c_int, ctypes.c_int] + [pointer] * 2
    library.complex_matvec.restype = None
    for name in ('calculate_phases_and_packet', 'calculate_field_slice'):
        original = getattr(sonic_wrapper._cpp_lib, name)
        function = getattr(library, name)
        function.argtypes, function.restype = original.argtypes, original.restype
    field_backends._native_checked = True
    field_backends._native = library.complex_matvec
    sonic_wrapper._cpp_lib = library
    geometry = load_creo_tunnel()
    sources = np.array([element['position_mm'] for element in geometry['elements']])
    normals = np.array([element['normal'] for element in geometry['elements']])
    receivers = np.array([[0., 0., 0.], [12., -5., 14.], [-11., 17., -8.]])
    targets = [dict(zip(('x', 'y', 'z'), point)) for point in receivers]
    weights = np.linspace(0., 1., 256) * np.exp(1j * np.linspace(-2., 3., 256))
    errors = {}
    engine = PhaseEngine()
    for model in ('point_source', 'ultraino_sinc', 'circular_piston'):
        config = FieldConfig(model=model, aperture_radius_mm=4.5)
        green = propagation_matrix(receivers, sources, normals, config=config)
        actual, status = field_backends.reduce_field(green, weights, 1)
        assert status['backend'] == 'C++' and status['fallback_reason'] is None
        expected = green @ weights
        np.testing.assert_allclose(actual, expected, atol=1e-10, rtol=1e-12)
        errors[model] = float(np.max(np.abs(actual - expected)))
        for algorithm in ('Focus', 'Twin Trap', 'Vortex Trap'):
            for kwargs in ({}, dict(field_config=config, normals=normals)):
                cpu, _ = engine.calculate_phases(sources, targets, np.ones(256), algorithm, 0, **kwargs)
                native, _ = engine.calculate_phases(sources, targets, np.ones(256), algorithm, 1, **kwargs)
                np.testing.assert_allclose(np.exp(1j * cpu), np.exp(1j * native), atol=1e-12)
    report = dict(python=sys.executable, compiler='MSVC 14.50.35717 x64 /O2 /openmp',
                  models=list(errors), max_abs_pressure_errors=errors,
                  legacy_phase_abi=True, complex_matvec_abi=True,
                  source_sha256=hashlib.sha256((REPO / 'src/acousticstudio/sonic_core.cpp').read_bytes()).hexdigest(),
                  dll_sha256=hashlib.sha256(dll_path.read_bytes()).hexdigest())
    Path(__file__).with_name('t2_native_result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
