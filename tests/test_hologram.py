"""Adjoint/sign/constraints, fixed gain, cache, dispatcher and failure regressions."""
from dataclasses import replace
import json
from threading import Event

import numpy as np
import pytest

from acousticstudio.field_model import FieldConfig, propagation_matrix
from acousticstudio.force_analysis import json_result
from acousticstudio.geometry import load_creo_tunnel
from acousticstudio.hologram import (HologramCancelled, HologramSettings, HologramSolver, JAVA_TO_STUDIO,
                                     TrapTarget, constrain_field, virtual_targets)
from acousticstudio.phase_engine import PhaseEngine


def fixture():
    sources = np.array([[-20., -20., -40.], [20., -20., -40.], [-20., 20., 40.], [20., 20., 40.]])
    normals = np.array([[0., 0., 1.], [0., 0., 1.], [0., 0., -1.], [0., 0., -1.]])
    return sources, normals, np.ones(4), FieldConfig()


def aligned_error(actual, expected):
    offset = np.angle(np.vdot(expected, actual))
    return np.max(np.abs(actual * np.exp(-1j * offset) - expected))


def test_java_axes_are_right_handed_and_virtual_offsets_are_not_half_the_original_separation():
    np.testing.assert_array_equal(JAVA_TO_STUDIO @ [0., 1., 0.], [0., 0., 1.])
    np.testing.assert_allclose(np.linalg.det(JAVA_TO_STUDIO), 1.)
    targets = [TrapTarget((2., 3., 4.)), TrapTarget((10., 20., 30.), 'twin', 2.),
               TrapTarget.from_point(dict(x=-10., y=0., z=0.), 'standing_wave')]
    config = FieldConfig()
    points, signs, weights, groups = virtual_targets(targets, config)
    wavelength = 343 / 40000 * 1000
    np.testing.assert_allclose(points[1:3], [[10 + wavelength / 1.5, 20, 30], [10 - wavelength / 1.5, 20, 30]])
    np.testing.assert_allclose(points[3:5], [[-10, 0, wavelength / 2], [-10, 0, -wavelength / 2]])
    np.testing.assert_array_equal(signs, [1., 1., -1., 1., -1.])
    np.testing.assert_array_equal(weights, [1., 2., 2., 1., 1.])
    assert groups == [(0, 1), (1, 3), (3, 5)]


def test_group_phase_and_weight_constraints_retain_zero_field_anchor():
    field = np.array([3j, -4., 0., 0.])
    result, anchors = constrain_field(field, np.array([1, -1, 1, -1]), np.array([2, 2, 1, 1]),
                                     [(0, 2), (2, 4)], np.array([1j, -1j]))
    np.testing.assert_allclose(result, [2j, -2j, -1j, 1j])
    np.testing.assert_allclose(anchors, [1j, -1j])


@pytest.mark.parametrize('model', ['point_source', 'ultraino_sinc', 'circular_piston'])
def test_single_focus_matches_conjugate_green_phase_with_fixed_unequal_gains_and_disabled_channel(model):
    sources, normals, _, config = fixture()
    config = replace(config, model=model, aperture_radius_mm=4.5)
    gains = np.array([1., .7, 0., .4])
    target = TrapTarget((3., 4., 5.))
    result = HologramSolver().solve(sources, normals, gains, config, [target])
    expected = propagation_matrix([target.position_mm], sources, normals, config=config)[0].conj()
    active = gains > 0
    expected = expected[active] / np.abs(expected[active])
    assert aligned_error(np.exp(1j * result['phases_rad'][active]), expected) < 1e-12
    assert result['phases_rad'][2] == 0. and result['drive_amplitudes'][2] == 0.
    np.testing.assert_array_equal(result['snapshot']['amplitudes'], gains)
    actual_field = propagation_matrix(result['virtual_points_mm'], sources, normals, config=config) @ (gains * np.exp(1j * result['phases_rad']))
    np.testing.assert_allclose(result['field_real'] + 1j * result['field_imag'], actual_field)
    assert not result['pressure_calibrated'] and result['constraint'] == 'phase_only_fixed_source_gains'
    json.dumps(json_result(result), allow_nan=False)


@pytest.mark.parametrize('trap_type', ['focus', 'twin', 'standing_wave'])
def test_fixed_iterations_match_independent_scalar_real_imaginary_ultraino_loop(trap_type):
    sources, normals, gains, config = fixture()
    direction = (0., 0., 1.) if trap_type == 'standing_wave' else (1., 0., 0.)
    targets = [TrapTarget((-6., 0., 0.), trap_type, direction=direction), TrapTarget((6., 1., 2.), trap_type, direction=direction)]
    initial = np.array([.2, .9, 2.4, 3.2])
    settings = HologramSettings(iterations=12, phase_tolerance_rad=0., initialization='current')
    result = HologramSolver().solve(sources, normals, gains, config, targets, settings, initial_phases=initial)
    green = propagation_matrix(result['virtual_points_mm'], sources, normals, config=config)
    ta, tb = np.cos(initial), np.sin(initial)
    for _ in range(12):
        pa, pb = np.zeros(len(green)), np.zeros(len(green))
        for j in range(len(green)):
            for i in range(len(sources)):
                pa[j] += ta[i] * green[j, i].real - tb[i] * green[j, i].imag
                pb[j] += ta[i] * green[j, i].imag + tb[i] * green[j, i].real
        for start, end in result['groups']:
            magnitude = np.hypot(pa[start], pb[start])
            ar, br = pa[start] / magnitude, pb[start] / magnitude
            pa[start], pb[start] = ar, br
            if end - start == 2:
                pa[start + 1], pb[start + 1] = -ar, -br
        for i in range(len(sources)):
            ar, br = 0., 0.
            for j in range(len(green)):
                ar += pa[j] * green[j, i].real + pb[j] * green[j, i].imag
                br += -pa[j] * green[j, i].imag + pb[j] * green[j, i].real
            magnitude = np.hypot(ar, br)
            ta[i], tb[i] = ar / magnitude, br / magnitude
    assert aligned_error(np.exp(1j * result['phases_rad']), ta + 1j * tb) < 1e-12
    assert result['iterations_completed'] == 12 and not result['stationary']
    np.testing.assert_array_equal(result['snapshot']['initial_phases_rad'], initial)


def test_zero_backprojection_keeps_previous_phase_and_zero_field_cannot_claim_success(monkeypatch):
    import acousticstudio.hologram as hologram
    sources, normals, gains, config = fixture()
    monkeypatch.setattr(hologram, 'propagation_matrix', lambda *_: np.array([[1., 0., 0., 0.]], dtype=complex))
    initial = np.array([.2, .9, 2.4, 3.2])
    settings = HologramSettings(iterations=3, initialization='current')
    result = HologramSolver().solve(sources, normals, gains, config, [TrapTarget((0., 0., 0.))], settings, initial_phases=initial)
    np.testing.assert_allclose(result['phases_rad'], initial)
    monkeypatch.setattr(hologram, 'propagation_matrix', lambda *_: np.zeros((1, 4), dtype=complex))
    with pytest.raises(ValueError, match='음장이 0'):
        HologramSolver().solve(sources, normals, gains, config, [TrapTarget((0., 0., 0.))], settings)


def test_creo_multiple_focus_improves_relative_constraints_and_is_repeatable():
    geometry = load_creo_tunnel()
    sources = np.array([e['position_mm'] for e in geometry['elements']])
    normals = np.array([e['normal'] for e in geometry['elements']])
    targets = [TrapTarget((-10., -3., 5.)), TrapTarget((8., 4., -7.), weight=.7)]
    engine = HologramSolver()
    first = engine.solve(sources, normals, np.ones(256), FieldConfig(), targets)
    second = engine.solve(sources, normals, np.ones(256), FieldConfig(), targets)
    assert first['metrics']['relative_residual'] < first['initial_metrics']['relative_residual']
    assert first['metrics']['weighted_uniformity'] > first['initial_metrics']['weighted_uniformity']
    assert not first['cache_hit'] and second['cache_hit']
    np.testing.assert_array_equal(first['phases_rad'], second['phases_rad'])


def test_cache_invalidates_all_propagation_and_target_inputs():
    sources, normals, gains, config = fixture()
    solver = HologramSolver()
    targets = [TrapTarget((1., 2., 3.))]
    args = dict(sources_mm=sources, normals=normals, gains=gains, config=config, targets=targets,
                settings=HologramSettings(iterations=2, phase_tolerance_rad=0.), aperture_radii_mm=[4.] * 4)
    assert not solver.solve(**args)['cache_hit']
    assert solver.solve(**args)['cache_hit']
    changed = [dict(sources_mm=sources + [1., 0., 0.]), dict(normals=-normals), dict(gains=gains * .9),
               dict(aperture_radii_mm=[4.5] * 4), dict(config=replace(config, model='ultraino_sinc')),
               dict(config=replace(config, frequency_hz=39000.)), dict(targets=[TrapTarget((2., 2., 3.))]),
               dict(targets=[TrapTarget((1., 2., 3.), weight=2.)]), dict(targets=[TrapTarget((1., 2., 3.), 'twin')])]
    for change in changed:
        solver.solve(**args)
        assert not solver.solve(**(args | change))['cache_hit']


def test_rigid_rotation_rotates_virtual_directions_and_preserves_solution():
    sources, normals, gains, config = fixture()
    target = TrapTarget((1., 2., 3.), 'twin', direction=(1., 2., 3.))
    rotation = JAVA_TO_STUDIO
    translation = np.array([13., -17., 29.])
    moved = TrapTarget(tuple(rotation @ target.position_mm + translation), 'twin', direction=tuple(rotation @ target.direction))
    solver = HologramSolver()
    settings = HologramSettings(iterations=15, phase_tolerance_rad=0.)
    a = solver.solve(sources, normals, gains, config, [target], settings)
    b = solver.solve(sources @ rotation.T + translation, normals @ rotation.T, gains, config, [moved], settings)
    assert aligned_error(np.exp(1j * a['phases_rad']), np.exp(1j * b['phases_rad'])) < 1e-11


def test_dispatch_and_single_target_trajectory_share_settings_and_output():
    sources, normals, gains, config = fixture()
    settings = HologramSettings(default_trap_type='standing_wave', iterations=12)
    engine = PhaseEngine()
    points = np.array([[1., 2., 3.], [2., 3., 4.]])
    trajectory = engine.calculate_trajectory_phases(sources, points, gains, 'Kinoforms', field_config=config,
                                                   normals=normals, hologram_settings=settings)
    for row, point in enumerate(points):
        live, packet = engine.calculate_phases(sources, [dict(zip('xyz', point))], gains, 'Kinoforms', 0,
                                                field_config=config, normals=normals, hologram_settings=settings)
        assert packet is None
        np.testing.assert_array_equal(trajectory[row], live)
    assert engine.last_hologram['targets'][0]['trap_type'] == 'standing_wave'


@pytest.mark.parametrize('bad', [0., -1., np.nan, np.inf])
def test_invalid_weights_and_gains_are_rejected(bad):
    sources, normals, _, config = fixture()
    with pytest.raises(ValueError):
        TrapTarget((0., 0., 0.), weight=bad)
    with pytest.raises(ValueError):
        HologramSolver().solve(sources, normals, np.full(4, bad), config, [TrapTarget((0., 0., 0.))])


def test_duplicate_near_empty_unknown_aperture_bad_settings_and_cancellation():
    sources, normals, gains, config = fixture()
    target = TrapTarget((0., 0., 0.))
    solver = HologramSolver()
    for targets in ([], [target, target], [TrapTarget(tuple(sources[0]))]):
        with pytest.raises(ValueError):
            solver.solve(sources, normals, gains, config, targets)
    with pytest.raises(ValueError):
        solver.solve(sources, normals, gains, replace(config, model='ultraino_sinc'), [target])
    for settings in (dict(iterations=0), dict(iterations=True), dict(phase_tolerance_rad=np.nan), dict(default_trap_type='vortex')):
        with pytest.raises(ValueError):
            HologramSettings(**settings)
    with pytest.raises(ValueError):
        TrapTarget((0., 0., 0.), direction=(0., 0., 0.))
    cancellation = Event(); cancellation.set()
    with pytest.raises(HologramCancelled):
        solver.solve(sources, normals, gains, config, [target], cancelled=cancellation)
    cancellation.clear()
    progress = []
    def cancel(value):
        progress.append(value); cancellation.set()
    with pytest.raises(HologramCancelled):
        solver.solve(sources, normals, gains, config, [target], HologramSettings(iterations=20, phase_tolerance_rad=0.),
                     cancelled=cancellation, progress=cancel)
    assert progress == [5]


@pytest.mark.parametrize('weight', [1e308, 1e-310])
def test_unrepresentable_target_normalization_fails_instead_of_exporting_nonfinite_metrics(weight):
    sources, normals, gains, config = fixture()
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        with pytest.raises(ValueError, match='가중치의 수치 범위'):
            HologramSolver().solve(sources, normals, gains, config, [TrapTarget((0., 0., 0.), weight=weight)])
