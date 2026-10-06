"""Record actual backend capabilities, numerical errors and reused dependencies."""
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sys

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))
from acousticstudio.dependencies import PACKAGE_INFO
from acousticstudio.field_backends import reduce_field
from acousticstudio.field_model import FieldConfig, propagation_matrix
from acousticstudio.geometry import load_creo_tunnel


def main():
    required = {name for name, info in PACKAGE_INFO.items() if info['type'] == '\uD544\uC218'}
    declared = {line.strip() for line in (REPO / 'requirements.txt').read_text(encoding='utf-8').splitlines()
                if line.strip() and not line.startswith('#')}
    assert required == declared
    geometry = load_creo_tunnel()
    sources = np.array([e['position_mm'] for e in geometry['elements']])
    normals = np.array([e['normal'] for e in geometry['elements']])
    weights = np.linspace(0., 1., 256) * np.exp(1j * np.linspace(-2., 3., 256))
    rows = []
    for model in ('point_source', 'ultraino_sinc', 'circular_piston'):
        config = FieldConfig(model=model, aperture_radius_mm=4.5)
        green = propagation_matrix([[0., 0., 0.], [12., -5., 14.]], sources, normals, config=config)
        expected = green @ weights
        for mode in range(4):
            result, status = reduce_field(green, weights, mode, has_taichi=True, has_pytorch=True)
            error = float(np.max(np.abs(result - expected)))
            np.testing.assert_allclose(result, expected, atol=1e-10, rtol=1e-12)
            rows.append(dict(model=model, max_abs_complex_error=error, **status))
    import torch
    report = dict(python=sys.executable, python_version=sys.version.split()[0],
                  packages={name: version(name) for name in sorted(required | {'torch', 'taichi', 'pytest'})},
                  required_catalog_matches_requirements=True, required_count=len(required),
                  torch_cuda_available=torch.cuda.is_available(), torch_cuda_build=torch.version.cuda,
                  synthetic_test_radius_mm=4.5, actual_aperture_radius_mm=None,
                  runtime_dll_sha256=hashlib.sha256((REPO / 'src/acousticstudio/sonic_core.dll').read_bytes()).hexdigest(),
                  comparisons=rows)
    Path(__file__).with_name('t2_backend_result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
