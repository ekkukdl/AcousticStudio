"""Record independent Gor'kov references and derivative/backend parity; no hardware."""
from dataclasses import replace
from importlib.metadata import version
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter
from types import SimpleNamespace

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))
from acousticstudio.field_model import FieldConfig, levitate_transducer, source_parameters
from acousticstudio.force_analysis import AnalysisSettings, FieldSnapshot, ForceAnalyzer, ParticleConfig, json_result
from acousticstudio.geometry import load_creo_tunnel
from acousticstudio.phase_engine import PhaseEngine


def relative_error(actual, reference):
    return float(np.linalg.norm(np.asarray(actual) - reference) /
                 max(np.linalg.norm(reference), np.finfo(float).tiny))


def reference_comparison(config):
    import levitate
    sources = np.array([[-20., -20., -40.], [20., -20., -40.],
                        [-20., 20., 40.], [20., 20., 40.]])
    normals = np.array([[0., 0., 1.], [0., 0., 1.], [0., 0., -1.], [0., 0., -1.]])
    frozen = FieldSnapshot(sources, normals, [.2, .9, 2.4, 3.2], [1., .7, .3, .9], config)
    particle = ParticleConfig(radius_mm=.2, density_kg_m3=30., sound_speed_m_s=2200.,
                              source='synthetic numerical reference')
    settings = AnalysisSettings(particle=particle, samples=5, derivative_step_mm=.1)
    analyzer = ForceAnalyzer(frozen, settings)
    normals, radii = source_parameters(4, frozen.normals, frozen.aperture_radii_mm, config)
    array = levitate.arrays.TransducerArray(sources.T * 1e-3, normals.T,
                                          transducer=levitate_transducer(config, radii, levitate))
    material = SimpleNamespace(rho=particle.density_kg_m3, compressibility=particle.compressibility)
    options = dict(radius=particle.radius_mm * 1e-3, material=material)
    potential = levitate.fields.GorkovPotential(array, **options)
    gradient = levitate.fields.GorkovGradient(array, **options)
    diagonal = levitate.fields.GorkovLaplacian(array, **options)
    point = np.array([1., 2., 3.])
    point_m, weights = point * 1e-3, frozen.amplitudes * np.exp(1j * frozen.phases_rad)
    expected_u = float((potential @ point_m)(weights))
    expected_f = -np.asarray((gradient @ point_m)(weights))
    expected_d = np.asarray((diagonal @ point_m)(weights))
    delta_m = 1e-5
    expected_k = np.column_stack([
        (np.asarray((gradient @ (point_m + np.eye(3)[axis] * delta_m))(weights)) -
         np.asarray((gradient @ (point_m - np.eye(3)[axis] * delta_m))(weights))) / (2 * delta_m)
        for axis in range(3)])
    actual_f, actual_d, actual_u = analyzer.force_and_diagonal([point], .025)
    actual_k = analyzer.stiffness_matrix(point, .025)
    np.testing.assert_allclose(actual_u[0], expected_u, rtol=2e-5, atol=1e-18)
    np.testing.assert_allclose(actual_f[0], expected_f, rtol=5e-4, atol=1e-15)
    np.testing.assert_allclose(actual_d[0], expected_d, rtol=5e-4, atol=1e-11)
    np.testing.assert_allclose(actual_k, expected_k, rtol=2e-3, atol=1e-11)
    return dict(model=config.model, snapshot=frozen.to_dict(), settings=settings.to_dict(),
                reference='installed levitate Gor\'kov potential/gradient/laplacian; full K from gradient differences',
                derivative_step_mm=.025, reference_jacobian_step_m=delta_m,
                potential_relative_error=relative_error(actual_u[0], expected_u),
                force_relative_error=relative_error(actual_f[0], expected_f),
                diagonal_relative_error=relative_error(actual_d[0], expected_d),
                full_matrix_relative_error=relative_error(actual_k, expected_k))


def main():
    geometry = load_creo_tunnel()
    sources = np.array([e['position_mm'] for e in geometry['elements']])
    normals = np.array([e['normal'] for e in geometry['elements']])
    references, comparisons = [], []
    for model in ('point_source', 'ultraino_sinc', 'circular_piston'):
        config = FieldConfig(model=model, aperture_radius_mm=None if model == 'point_source' else 4.5)
        references.append(reference_comparison(replace(config, frequency_hz=39500., sound_speed_m_s=340.)))
        phases, _ = PhaseEngine().calculate_phases(
            sources, [dict(x=0., y=0., z=0.)], np.ones(256), 'Twin Trap', 0,
            field_config=config, normals=normals)
        frozen = FieldSnapshot(sources, normals, phases, np.ones(256), config)
        settings = AnalysisSettings(samples=5)
        centre = [.3, .4, .5]
        expected = ForceAnalyzer(frozen, settings).analyze(centre)
        for mode in (0, 1, 2, 3):
            started = perf_counter()
            actual = ForceAnalyzer(frozen, settings, mode, has_taichi=True, has_pytorch=True).analyze(centre)
            elapsed = perf_counter() - started
            force_error = relative_error(actual['acoustic_force'], expected['acoustic_force'])
            matrix_error = relative_error(actual['centre_stiffness'], expected['centre_stiffness'])
            np.testing.assert_allclose(actual['acoustic_force'], expected['acoustic_force'], rtol=1e-7, atol=1e-13)
            np.testing.assert_allclose(actual['centre_stiffness'], expected['centre_stiffness'], rtol=1e-5, atol=1e-10)
            assert actual['converged'] == expected['converged']
            assert actual['restoring']['status'] == expected['restoring']['status']
            assert actual['snapshot']['phases_rad'] == phases.tolist()
            comparisons.append(dict(model=model, channels=256, mode_idx=mode, centre_mm=centre,
                                    backend=actual['backend'], elapsed_seconds=elapsed,
                                    force_relative_error=force_error, matrix_relative_error=matrix_error,
                                    converged=actual['converged'], restoring=actual['restoring'],
                                    convergence=actual['convergence'],
                                    gravity_equilibrium_status=actual['gravity_equilibrium_status']))
    paths = ['src/acousticstudio/force_analysis.py', 'src/acousticstudio/field_model.py',
             'src/acousticstudio/sonic_core.dll',
             '구상도/outputs/panel_8faces_32ch_R1/array_positions_256.json']
    report = dict(python=sys.executable, python_version=sys.version.split()[0],
                  packages={name: version(name) for name in ('numpy', 'scipy', 'levitate', 'numba', 'taichi', 'torch')},
                  hashes={path: hashlib.sha256((REPO / path).read_bytes()).hexdigest() for path in paths},
                  actual_aperture_radius_mm=None, synthetic_directivity_test_radius_mm=4.5,
                  pressure_calibrated=False, particle_provenance='example',
                  hardware_used=False, timing_note='single verification run, includes warm-up; not a benchmark',
                  references=references, backend_comparisons=comparisons)
    Path(__file__).with_name('t3_numerical_result.json').write_text(
        json.dumps(json_result(report), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(reference_models=len(references), backend_cases=len(comparisons),
                          max_force_backend_relative_error=max(r['force_relative_error'] for r in comparisons),
                          max_matrix_backend_relative_error=max(r['matrix_relative_error'] for r in comparisons)), indent=2))


if __name__ == '__main__':
    main()
