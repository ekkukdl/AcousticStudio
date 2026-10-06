"""Propagation, CAD normals, SI alignment, and backend parity (no serial I/O)."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
import vtk
import pyvista as pv
from PySide6.QtWidgets import QApplication

from acousticstudio.acoustic_model_ui import AcousticModelControls, field_kwargs
from acousticstudio.field_model import (FieldConfig, SimulationMedium, levitate_transducer,
                                       propagation_matrix, source_parameters)
from acousticstudio.field_backends import reduce_field
from acousticstudio.geometry import load_creo_tunnel, transform_geometry
from acousticstudio.geometry_scene import create_geometry_actors, transducer_inputs, transducer_acoustic_inputs
from acousticstudio.phase_engine import PhaseEngine


@pytest.mark.parametrize('model', ['point_source', 'ultraino_sinc', 'circular_piston'])
def test_single_source_on_axis_si_amplitude_phase_and_inverse_distance(model):
    config = FieldConfig(model=model, aperture_radius_mm=4.5, source_strength=2.)
    receivers = np.array([[0., 0., 100.], [0., 0., 200.]])
    green = propagation_matrix(receivers, [[0., 0., 0.]], [[0., 0., 1.]], config=config)[:, 0]
    distances_m = np.array([.1, .2])
    expected = 2 / distances_m * np.exp(1j * 2 * np.pi * 40000 / 343 * distances_m)
    np.testing.assert_allclose(green, expected, rtol=1e-13)


def test_ultraino_off_axis_sinc_sign_and_pi_convention_from_java_formula():
    # 9 mm Java aperture is a DIAMETER, so Python effective radius is 4.5 mm.
    config = FieldConfig(model='ultraino_sinc', aperture_radius_mm=4.5)
    receivers = np.array([[100., 0., 0.], [60., 0., 80.], [0., 0., -100.]])
    distance = np.linalg.norm(receivers, axis=1) * 1e-3
    angle = np.arccos(receivers[:, 2] * 1e-3 / distance)
    x = .009 * .5 * (2 * np.pi * 40000 / 343) * np.sin(angle)
    sinc = np.array([np.sin(value) / value if abs(value) > 1e-14 else 1. for value in x])
    actual = propagation_matrix(receivers, [[0., 0., 0.]], config=config)[:, 0]
    expected = sinc / distance * np.exp(1j * config.k_m * distance)
    np.testing.assert_allclose(actual, expected, atol=2e-13)
    assert sinc[0] < 0  # negative sidelobes retain their pi phase inversion


def test_sinc_and_piston_are_explicitly_different_models():
    config = FieldConfig(model='ultraino_sinc', aperture_radius_mm=5.)
    sinc = propagation_matrix([[80., 0., 60.]], [[0., 0., 0.]], config=config)
    piston = propagation_matrix([[80., 0., 60.]], [[0., 0., 0.]],
                                config=replace(config, model='circular_piston'))
    assert not np.isclose(sinc, piston).all()


@pytest.mark.parametrize('model', ['point_source', 'ultraino_sinc', 'circular_piston'])
def test_shared_pressure_matches_installed_levitate_with_same_units_medium_and_scale(model):
    import levitate
    sources = np.array([[-25., 4., 0.], [30., -5., 10.]])
    normals = np.array([[1., 0., 1.], [-1., 0., 1.]])
    receivers = np.array([[0., 10., 100.], [40., 20., 150.]])
    config = FieldConfig(model=model, frequency_hz=39000., sound_speed_m_s=340., source_strength=2.3)
    radii = [4., 5.5]  # intentionally heterogeneous channels
    normal, radius_m = source_parameters(2, normals, radii, config)
    transducer = levitate_transducer(config, radius_m, levitate)
    actual = propagation_matrix(receivers, sources, normals, radii, config)
    from_levitate = transducer.pressure_derivs(sources.T * 1e-3, normal.T, receivers.T * 1e-3, orders=0)[0].T
    np.testing.assert_allclose(actual, from_levitate, rtol=2e-12, atol=1e-12)
    if model == 'circular_piston':
        # Also compare each channel to the library's independent Bessel implementation.
        for index in range(2):
            reference = levitate.transducers.CircularPiston(
                effective_radius=radius_m[index], freq=39000., p0=2.3,
                medium=SimulationMedium(340., config.density_kg_m3))
            field = reference.pressure_derivs(sources[index] * 1e-3, normal[index], receivers.T * 1e-3, orders=0)[0]
            np.testing.assert_allclose(actual[:, index], field, rtol=2e-12, atol=1e-12)


@pytest.mark.parametrize('model', ['point_source', 'ultraino_sinc', 'circular_piston'])
def test_creo_normals_and_global_rigid_transform_preserve_field_and_focus(model):
    geometry = load_creo_tunnel()
    config = FieldConfig(model=model, aperture_radius_mm=4.5)
    receivers = np.array([[0., 0., 0.], [7., -8., 9.]])
    sources = np.array([e['position_mm'] for e in geometry['elements']])
    normals = np.array([e['normal'] for e in geometry['elements']])
    assert np.all(normals[:, 2] == 0.)  # tunnel normals are horizontal
    green = propagation_matrix(receivers, sources, normals, config=config)
    pose = np.array([[0., 0., 1., 13.], [1., 0., 0., -17.], [0., 1., 0., 29.], [0., 0., 0., 1.]])
    moved = transform_geometry(geometry, pose)
    moved_sources = np.array([e['position_mm'] for e in moved['elements']])
    moved_normals = np.array([e['normal'] for e in moved['elements']])
    moved_receivers = receivers @ pose[:3, :3].T + pose[:3, 3]
    transformed = propagation_matrix(moved_receivers, moved_sources, moved_normals, config=config)
    np.testing.assert_allclose(green, transformed, rtol=1e-12, atol=1e-12)
    engine = PhaseEngine()
    phases = engine.calculate_trajectory_phases(sources, receivers, np.ones(256), 'Focus',
                                               field_config=config, normals=normals)
    moved_phases = engine.calculate_trajectory_phases(moved_sources, moved_receivers, np.ones(256), 'Focus',
                                                     field_config=config, normals=moved_normals)
    np.testing.assert_allclose(np.exp(1j * phases), np.exp(1j * moved_phases), atol=1e-12)
    symmetry = green[0].reshape(8, 32)
    np.testing.assert_allclose(symmetry, np.broadcast_to(symmetry[0], (8, 32)), atol=1e-10)


@pytest.mark.parametrize('algorithm', ['Focus', 'Twin Trap', 'Vortex Trap'])
def test_live_trajectory_and_slice_use_common_propagation(algorithm):
    sources = np.array([[-20., 0., 0.], [20., 0., 0.], [0., 0., -30.]])
    receivers = np.array([[3., 4., 55.], [2., 1., 60.]])
    normal = np.tile([0., 0., 1.], (3, 1))
    amps = np.array([1., .3, 0.])
    config = FieldConfig(model='ultraino_sinc', aperture_radius_mm=8.)
    engine = PhaseEngine()
    trajectory = engine.calculate_trajectory_phases(sources, receivers, amps, algorithm,
                                                  field_config=config, normals=normal)
    for index, receiver in enumerate(receivers):
        live, _ = engine.calculate_phases(sources, [dict(zip(('x', 'y', 'z'), receiver))], amps,
                                         algorithm, 0, field_config=config, normals=normal)
        np.testing.assert_array_equal(live, trajectory[index])
        real, imag = engine.calculate_field_slice(receivers, sources, live, amps, 0,
                                                 field_config=config, normals=normal)
        expected = propagation_matrix(receivers, sources, normal, config=config) @ (amps * np.exp(1j * live))
        np.testing.assert_allclose(real + 1j * imag, expected, atol=1e-12)
        assert live[-1] == 0.


@pytest.mark.parametrize('bad', [np.nan, np.inf, 0., -1.])
def test_invalid_config_and_unknown_directed_aperture_fail_explicitly(bad):
    with pytest.raises(ValueError):
        FieldConfig(sound_speed_m_s=bad)
    with pytest.raises(ValueError):
        propagation_matrix([[0., 0., 10.]], [[0., 0., 0.]], aperture_radii_mm=[bad])
    with pytest.raises(ValueError, match='미확정'):
        propagation_matrix([[0., 0., 10.]], [[0., 0., 0.]], config=FieldConfig(model='circular_piston'))


def test_near_singularity_is_finite_but_invalid_normals_coordinates_and_phases_fail():
    config = FieldConfig(model='ultraino_sinc', aperture_radius_mm=4.5)
    near = propagation_matrix([[0., 0., 0.], [0., 0., 1e-9]], [[0., 0., 0.]], config=config)
    assert np.isfinite(near).all()
    np.testing.assert_allclose(np.abs(near), 1 / config.min_distance_m)
    for coords, normal in [([[np.nan, 0., 0.]], [[0., 0., 1.]]),
                           ([[0., 0., 10.]], [[0., 0., 0.]])]:
        with pytest.raises(ValueError):
            propagation_matrix(coords, [[0., 0., 0.]], normal)
    with pytest.raises(ValueError):
        PhaseEngine().calculate_field_slice([[0., 0., 10.]], [[0., 0., 0.]], [np.inf], [1.], 0)


def test_slice_chunk_boundaries_empty_inputs_and_legacy_scale():
    sources = [[0., 0., 0.], [10., 0., 0.]]
    receivers = np.column_stack([np.linspace(-20., 20., 1027), np.ones(1027), np.full(1027, 100.)])
    engine = PhaseEngine()
    real, imag = engine.calculate_field_slice(receivers, sources, [.3, .7], [1., .5], 0)
    expected = propagation_matrix(receivers, sources, config=FieldConfig(source_strength=.001)) @ (
        np.array([1., .5]) * np.exp(1j * np.array([.3, .7])))
    np.testing.assert_allclose(real + 1j * imag, expected, atol=1e-14)
    assert engine.calculate_field_slice([], sources, [.3, .7], [1., .5], 0)[0].shape == (0,)
    np.testing.assert_array_equal(engine.calculate_field_slice(receivers[:2], [], [], [], 0)[0], [0., 0.])


def test_native_capability_and_disabled_gpu_fallback_are_reported(monkeypatch):
    import acousticstudio.field_backends as backends
    monkeypatch.setattr(backends, '_native_checked', True)
    monkeypatch.setattr(backends, '_native', None)
    matrix = np.array([[1 + 2j, 3 - 4j], [-1j, 2.]])
    weights = np.array([.3 + .2j, .7j])
    for mode in (0, 1, 2, 3):
        result, status = reduce_field(matrix, weights, mode)
        np.testing.assert_allclose(result, matrix @ weights, atol=1e-14)
        assert status['backend'] == 'Numba CPU'
        assert bool(status['fallback_reason']) == (mode != 0)


@pytest.mark.parametrize('mode', [1, 2, 3])
@pytest.mark.parametrize('model', ['point_source', 'ultraino_sinc', 'circular_piston'])
def test_available_accelerators_match_reference_complex_fields_and_phases(mode, model):
    config = FieldConfig(model=model, aperture_radius_mm=4.5)
    geometry = load_creo_tunnel()
    sources = np.array([e['position_mm'] for e in geometry['elements']])
    normals = np.array([e['normal'] for e in geometry['elements']])
    green = propagation_matrix([[0., 0., 0.], [12., -5., 14.]], sources, normals, config=config)
    weights = np.linspace(0., 1., 256) * np.exp(1j * np.linspace(-2., 3., 256))
    result, status = reduce_field(green, weights, mode, has_taichi=True, has_pytorch=True)
    if status['fallback_reason']:
        pytest.skip(status['fallback_reason'])
    np.testing.assert_allclose(result, green @ weights, atol=1e-10, rtol=1e-12)
    engine = PhaseEngine()
    targets = [dict(x=12., y=-5., z=14.), dict(x=0., y=0., z=0.)]
    for algorithm in ('Focus', 'Twin Trap', 'Vortex Trap'):
        cpu, _ = engine.calculate_phases(sources, targets, np.ones(256), algorithm, 0,
                                        field_config=config, normals=normals)
        actual, _ = engine.calculate_phases(sources, targets, np.ones(256), algorithm, mode,
                                           has_taichi=True, has_pytorch=True, field_config=config, normals=normals)
        assert not engine.last_backend['fallback_reason']
        np.testing.assert_allclose(np.exp(1j * actual), np.exp(1j * cpu), atol=1e-10)


def test_cad_actor_adapter_keeps_unknown_aperture_and_legacy_actual_rotation():
    renderer = vtk.vtkRenderer()
    actors, _ = create_geometry_actors(load_creo_tunnel(), renderer)
    normals, radii = transducer_acoustic_inputs(actors)
    np.testing.assert_allclose(normals[0], [-1., 0., 0.])
    assert radii == [None] * 256
    actor = pv.Actor(mapper=pv.DataSetMapper(pv.Cylinder()))
    actor.RotateY(90.)
    normal, radius = transducer_acoustic_inputs([actor])
    np.testing.assert_allclose(normal[0], [1., 0., 0.], atol=1e-12)
    assert radius == [None]


def test_model_controls_roundtrip_and_cad_input_contract():
    app = QApplication.instance() or QApplication([])
    changes = []
    controls = AcousticModelControls(lambda *_: changes.append(True))
    assert controls.config().model == 'point_source'
    assert controls.config().aperture_radius_mm is None
    controls.model.setCurrentIndex(1)
    controls.radius.setValue(4.5)
    controls.speed.setValue(340.)
    original = controls.config()
    controls.restore(original)
    assert controls.config() == original and len(changes) == 3
    actors, _ = create_geometry_actors(load_creo_tunnel(), vtk.vtkRenderer())
    window = SimpleNamespace(acoustic_model_controls=controls, transducer_actors=actors)
    kwargs = field_kwargs(window)
    np.testing.assert_allclose(kwargs['normals'][0], [-1., 0., 0.])
    assert kwargs['aperture_radii_mm'] == [None] * 256
    assert kwargs['field_config'].aperture_radius_mm == 4.5
    controls.close()
    app.processEvents()


@pytest.mark.parametrize('model', ['point_source', 'ultraino_sinc', 'circular_piston'])
def test_installed_solver_uses_directed_cad_model_without_mutating_global_air(model):
    import levitate
    from acousticstudio.phase_engine import trajectory_diagnosis_is_valid
    geometry = load_creo_tunnel()
    sources = np.array([element['position_mm'] for element in geometry['elements']])
    normals = np.array([element['normal'] for element in geometry['elements']])
    old_c = levitate.materials.air.c
    config = FieldConfig(model=model, aperture_radius_mm=4.5, frequency_hz=39500., sound_speed_m_s=340.)
    delays, metrics = PhaseEngine().optimize_trajectory_physical(
        sources, [[0., 0., 0.], [1., 0., 0.]], 50., field_config=config, normals=normals)
    assert trajectory_diagnosis_is_valid(metrics), metrics['status']
    assert metrics['field_config'] == config.to_dict()
    assert metrics['pressure_units'] == 'relative_uncalibrated'
    assert np.isfinite(delays).all()
    assert levitate.materials.air.c == old_c


def test_unknown_aperture_and_near_source_cannot_generate_success_diagnosis():
    engine = PhaseEngine()
    for config, points in [(FieldConfig(model='ultraino_sinc'), [[0., 0., 10.], [1., 0., 10.]]),
                           (FieldConfig(), [[0., 0., 0.], [1., 0., 0.]])]:
        _, metrics = engine.optimize_trajectory_physical([[0., 0., 0.]], points, 50., field_config=config)
        assert metrics['valid'] is False
        assert metrics['avg_stability'] is None
