"""Independent physics references, sign/coupling, frozen drive, convergence and failures."""
from dataclasses import replace
import json
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest

from acousticstudio.field_model import FieldConfig, levitate_transducer, source_parameters
from acousticstudio.force_analysis import (AnalysisCancelled, AnalysisSettings, FieldSnapshot,
                                           ForceAnalyzer, ParticleConfig, gorkov_coefficients,
                                           json_result, restoring_diagnosis)
from acousticstudio.geometry import load_creo_tunnel
from acousticstudio.phase_engine import PhaseEngine


def snapshot(config=None):
    return FieldSnapshot(np.array([[-20., -20., -40.], [20., -20., -40.],
                                   [-20., 20., 40.], [20., 20., 40.]]),
                         np.array([[0., 0., 1.], [0., 0., 1.], [0., 0., -1.], [0., 0., -1.]]),
                         np.array([.2, .9, 2.4, 3.2]), np.array([1., .7, .3, .9]), config or FieldConfig())


def test_coefficients_match_ultraino_si_peak_phasor_formula_and_particle_compressibility_override():
    particle = ParticleConfig(radius_mm=.2, density_kg_m3=30., compressibility_pa_inv=8e-9)
    medium = FieldConfig(sound_speed_m_s=340., density_kg_m3=1.2)
    coefficients = gorkov_coefficients(particle, medium)
    radius = .2e-3
    volume = 4 / 3 * np.pi * radius ** 3
    kappa = 1 / (1.2 * 340 ** 2)
    f1 = 1 - 8e-9 / kappa
    f2 = 2 * (30 / 1.2 - 1) / (2 * 30 / 1.2 + 1)
    np.testing.assert_allclose(coefficients['M1'], volume * f1 * .5 * kappa * .5)
    np.testing.assert_allclose(coefficients['M2'], volume * f2 * .75 * 1.2 * .5 / (1.2 * 2 * np.pi * 40000) ** 2)
    assert particle.compressibility == 8e-9


def test_snapshot_owns_copies_and_never_refocuses_while_scanning(monkeypatch):
    original = snapshot()
    sources, phases, amplitudes = original.sources_mm.copy(), original.phases_rad.copy(), original.amplitudes.copy()
    frozen = FieldSnapshot(sources, original.normals, phases, amplitudes, original.field_config)
    sources[:] = 0.; phases[:] = 0.; amplitudes[:] = 0.
    np.testing.assert_array_equal(frozen.sources_mm, original.sources_mm)
    np.testing.assert_array_equal(frozen.phases_rad, original.phases_rad)
    with pytest.raises(ValueError):
        frozen.phases_rad[0] = 2.
    monkeypatch.setattr(PhaseEngine, 'calculate_phases', lambda *_args, **_kwargs: pytest.fail('Analysis must not refocus'))
    result = ForceAnalyzer(frozen, AnalysisSettings(samples=5)).analyze([1., 2., 3.])
    assert result['valid'] and result['snapshot']['phases_rad'] == original.phases_rad.tolist()
    assert result['scan_points_mm'].shape == (3, 5, 3)
    np.testing.assert_allclose(result['offsets_mm'], [-2., -1., 0., 1., 2.])
    assert np.ptp(result['acoustic_force'][0, :, 0]) > 0
    assert result['gravity_equilibrium_status'] == 'unavailable_uncalibrated_pressure'
    assert not result['pressure_calibrated']
    json.dumps(json_result(result), allow_nan=False)


class StandingWave(ForceAnalyzer):
    def pressure(self, receivers_mm):
        points = np.asarray(receivers_mm)
        return 200 * np.sin(self.snapshot.field_config.k_m * points[:, 0] * 1e-3).astype(complex)


def test_standing_wave_closed_form_force_stiffness_and_restoring_sign():
    analyzer = StandingWave(snapshot(), AnalysisSettings(samples=5, derivative_step_mm=.1))
    k = analyzer.snapshot.field_config.k_m
    points = np.array([[.3, 0., 0.], [-.3, 0., 0.], [0., 0., 0.], [np.pi / (2 * k) * 1000, 0., 0.]])
    force, stiffness, _ = analyzer.force_and_diagonal(points, .025)
    coefficient = (analyzer.coefficients['M1'] + analyzer.coefficients['M2'] * k ** 2) * 200 ** 2
    expected_force = -coefficient * k * np.sin(2 * k * points[:, 0] * 1e-3)
    expected_k = 2 * coefficient * k ** 2 * np.cos(2 * k * points[:, 0] * 1e-3)
    np.testing.assert_allclose(force[:, 0], expected_force, rtol=2e-7, atol=1e-17)
    np.testing.assert_allclose(stiffness[:, 0], expected_k, rtol=1e-7, atol=1e-15)
    np.testing.assert_allclose(force[:, 1:], 0., atol=1e-17)
    assert stiffness[2, 0] > 0 and stiffness[3, 0] < 0
    result = analyzer.analyze([0., 0., 0.])
    assert result['converged']
    assert result['restoring']['status'] == 'unresolved'  # transverse neutral axes
    assert result['convergence'][1]['stiffness_relative_change'] < result['convergence'][0]['stiffness_relative_change'] / 8


class QuadraticPotential(ForceAnalyzer):
    matrix = np.array([[1., 2., 0.], [2., 1., 0.], [0., 0., 1.]])

    def potential(self, receivers_mm, step_mm):
        points = np.asarray(receivers_mm) * 1e-3
        return .5 * np.einsum('pi,ij,pj->p', points, self.matrix, points)


def test_full_coupling_detects_saddle_despite_positive_axis_diagonals():
    analyzer = QuadraticPotential(snapshot(), AnalysisSettings(samples=5))
    matrix = analyzer.stiffness_matrix([0., 0., 0.], .05)
    np.testing.assert_allclose(matrix, analyzer.matrix, atol=1e-12)
    assert np.all(np.diag(matrix) > 0)
    diagnosis = restoring_diagnosis(matrix)
    assert diagnosis['status'] == 'non_restoring'
    np.testing.assert_allclose(diagnosis['eigenvalues'], [-1., 1., 3.])


def test_constant_gravity_changes_force_residual_not_restoring_matrix():
    settings = AnalysisSettings(samples=5)
    analyzer = QuadraticPotential(snapshot(), settings)
    result = analyzer.analyze([.5, 0., 0.])
    expected_weight = settings.particle.mass_kg * np.array([0., 0., -9.80665])
    np.testing.assert_allclose(result['gravity_force_N'], expected_weight)
    np.testing.assert_allclose(result['conditional_centre_residual'], [-.0005, -.001, expected_weight[2]], atol=1e-16)
    without_gravity = QuadraticPotential(snapshot(), replace(settings, gravity_m_s2=(0., 0., 0.))).analyze([.5, 0., 0.])
    np.testing.assert_array_equal(result['centre_stiffness'], without_gravity['centre_stiffness'])
    assert result['gravity_equilibrium_status'] == 'unavailable_uncalibrated_pressure'


def test_conditional_gravity_balance_requires_all_three_residual_components_and_remains_uncalibrated():
    analyzer = QuadraticPotential(snapshot(), AnalysisSettings(samples=5))
    analyzer.matrix = np.eye(3)
    weight = analyzer.settings.particle.mass_kg * np.asarray(analyzer.settings.gravity_m_s2)
    # For U=|x|²/2, F=-x and the conditional equilibrium is x=mg, in metres.
    equilibrium_mm = weight * 1000
    result = analyzer.analyze(equilibrium_mm)
    np.testing.assert_allclose(result['conditional_centre_residual'], 0., atol=1e-15)
    assert result['restoring']['status'] == 'restoring'
    assert result['gravity_equilibrium_status'] == 'unavailable_uncalibrated_pressure'


@pytest.mark.parametrize('model', ['point_source', 'ultraino_sinc', 'circular_piston'])
def test_same_model_potential_force_and_restoring_sign_match_installed_levitate(model):
    import levitate
    config = FieldConfig(model=model, aperture_radius_mm=4.5, frequency_hz=39500., sound_speed_m_s=340.)
    frozen = snapshot(config)
    particle = ParticleConfig(radius_mm=.2, density_kg_m3=30., sound_speed_m_s=2200.)
    analyzer = ForceAnalyzer(frozen, AnalysisSettings(particle=particle, samples=5, derivative_step_mm=.1))
    normals, radii = source_parameters(4, frozen.normals, frozen.aperture_radii_mm, config)
    array = levitate.arrays.TransducerArray(frozen.sources_mm.T * 1e-3, normals.T,
                                         transducer=levitate_transducer(config, radii, levitate))
    material = SimpleNamespace(rho=particle.density_kg_m3, compressibility=particle.compressibility)
    potential = levitate.fields.GorkovPotential(array, radius=particle.radius_mm * 1e-3, material=material)
    gradient = levitate.fields.GorkovGradient(array, radius=particle.radius_mm * 1e-3, material=material)
    laplacian = levitate.fields.GorkovLaplacian(array, radius=particle.radius_mm * 1e-3, material=material)
    point_mm = np.array([1., 2., 3.]); point_m = point_mm * 1e-3
    u = frozen.amplitudes * np.exp(1j * frozen.phases_rad)
    reference_u = float((potential @ point_m)(u))
    reference_f = -np.asarray((gradient @ point_m)(u))
    reference_k = np.asarray((laplacian @ point_m)(u))
    actual_f, actual_k, actual_u = analyzer.force_and_diagonal([point_mm], .025)
    np.testing.assert_allclose(actual_u[0], reference_u, rtol=2e-5, atol=1e-18)
    np.testing.assert_allclose(actual_f[0], reference_f, rtol=5e-4, atol=1e-15)
    np.testing.assert_allclose(actual_k[0], reference_k, rtol=5e-4, atol=1e-11)
    # Independently differentiate force: K is the negative force Jacobian.
    numerical_jacobian = np.column_stack([
        (-np.asarray((gradient @ (point_m + np.eye(3)[axis] * 1e-5))(u)) +
         np.asarray((gradient @ (point_m - np.eye(3)[axis] * 1e-5))(u))) / 2e-5
        for axis in range(3)])
    matrix = analyzer.stiffness_matrix(point_mm, .025)
    np.testing.assert_allclose(matrix, -numerical_jacobian, rtol=2e-3, atol=1e-11)


@pytest.mark.parametrize('model', ['point_source', 'ultraino_sinc', 'circular_piston'])
def test_creo_fixed_field_rotates_force_and_full_restoring_matrix(model):
    geometry = load_creo_tunnel()
    p = np.array([e['position_mm'] for e in geometry['elements']])
    n = np.array([e['normal'] for e in geometry['elements']])
    config = FieldConfig(model=model, aperture_radius_mm=4.5)
    phases, _ = PhaseEngine().calculate_phases(p, [dict(x=0., y=0., z=0.)], np.ones(256), 'Twin Trap', 0,
                                              field_config=config, normals=n)
    frozen = FieldSnapshot(p, n, phases, np.ones(256), config)
    settings = AnalysisSettings(samples=5)
    rotation = np.array([[0., 0., 1.], [1., 0., 0.], [0., 1., 0.]])
    translation = np.array([13., -17., 29.])
    centre = np.array([.3, .4, .5])
    before = ForceAnalyzer(frozen, settings)
    moved = ForceAnalyzer(FieldSnapshot(p @ rotation.T + translation, n @ rotation.T, phases, np.ones(256), config), settings)
    f = before.force_and_diagonal([centre], .025)[0][0]
    k = before.stiffness_matrix(centre, .025)
    fm = moved.force_and_diagonal([centre @ rotation.T + translation], .025)[0][0]
    km = moved.stiffness_matrix(centre @ rotation.T + translation, .025)
    np.testing.assert_allclose(fm, rotation @ f, rtol=1e-7, atol=1e-14)
    np.testing.assert_allclose(km, rotation @ k @ rotation.T, rtol=1e-5, atol=2e-10)


def test_coarse_step_nonconvergence_and_large_particle_do_not_claim_confinement():
    coarse = StandingWave(snapshot(), AnalysisSettings(samples=5, derivative_step_mm=1., relative_tolerance=.0001)).analyze([0., 0., 0.])
    assert not coarse['converged'] and coarse['restoring']['status'] == 'unresolved'
    large = ForceAnalyzer(snapshot(), AnalysisSettings(samples=5, particle=ParticleConfig(radius_mm=2.))).analyze([0., 0., 0.])
    assert large['ka'] > .3 and not large['model_in_range']
    assert large['restoring']['status'] == 'unresolved'


@pytest.mark.parametrize('bad', [np.nan, np.inf, 0., -1.])
def test_invalid_particle_and_derivative_parameters_fail(bad):
    with pytest.raises(ValueError):
        ParticleConfig(radius_mm=bad)
    with pytest.raises(ValueError):
        AnalysisSettings(derivative_step_mm=bad)
    with pytest.raises(ValueError):
        ParticleConfig(compressibility_pa_inv=bad)


def test_unknown_aperture_near_stencil_empty_inputs_and_cancellation_are_explicit():
    with pytest.raises(ValueError, match='미확정'):
        snapshot(FieldConfig(model='ultraino_sinc'))
    with pytest.raises(ValueError):
        FieldSnapshot([], [], [], [], FieldConfig())
    with pytest.raises(ValueError):
        AnalysisSettings(samples=6)
    cancellation = Event(); cancellation.set()
    with pytest.raises(AnalysisCancelled):
        ForceAnalyzer(snapshot(), cancelled=cancellation).analyze([0., 0., 0.])
    frozen = snapshot()
    with pytest.raises(ValueError, match='근접점'):
        ForceAnalyzer(frozen).potential([frozen.sources_mm[0]], .1)
    with pytest.raises(ValueError):
        ForceAnalyzer(frozen).analyze([np.nan, 0., 0.])
    with pytest.raises(ValueError):
        ForceAnalyzer(frozen, AnalysisSettings(derivative_step_mm=2.))


def test_analysis_settings_json_roundtrip_preserves_particle_source_and_gravity():
    settings = AnalysisSettings(particle=ParticleConfig(compressibility_pa_inv=1e-9, provenance='provided', source='synthetic fixture'),
                                gravity_m_s2=(1., 2., -9.))
    assert AnalysisSettings.from_dict(json.loads(json.dumps(settings.to_dict()))) == settings


def test_cancellation_after_first_step_does_not_finish_or_return_partial_analysis():
    cancellation = Event()
    progress = []
    def cancel_at_first_step(value):
        progress.append(value)
        cancellation.set()
    with pytest.raises(AnalysisCancelled):
        ForceAnalyzer(snapshot(), AnalysisSettings(samples=5), cancelled=cancellation).analyze([0., 0., 0.], cancel_at_first_step)
    assert progress == [30]
