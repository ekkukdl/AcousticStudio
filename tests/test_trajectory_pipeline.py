"""Numerical and file/transport regressions; no real serial port is opened."""
import csv
import re
import sys
from math import pi
from types import SimpleNamespace

import numpy as np
import pytest

from acousticstudio.hardware import BOARD_PROFILES, HardwareController
from acousticstudio.phase_engine import PhaseEngine, trajectory_diagnosis_is_valid
from acousticstudio.trajectory_export import save_trajectory_export


CENTERS = np.array([[-20., -15., -40.], [20., -15., -40.],
                    [-20., 15., 40.], [20., 15., 40.], [5., 9., -40.]])
POINTS = np.array([[1., 2., 3.], [3., -1., 2.]])
AMPLITUDES = np.array([1., 0.7, 0.5, 0.9, 0.])


def active_points(points):
    return [dict(zip(('x', 'y', 'z'), point)) for point in points]


@pytest.mark.parametrize('algorithm', ['Focus', 'Twin Trap', 'Vortex Trap'])
def test_different_transducer_and_target_counts_match_phasor_reference(algorithm):
    engine = PhaseEngine()
    phases, _ = engine.calculate_phases(CENTERS, active_points(POINTS), AMPLITUDES, algorithm, 0)
    # An independent N×M propagation matrix catches a transposed coordinate contract.
    displacement = CENTERS[:, None, :] - POINTS[None, :, :]
    reference = -engine.k * np.linalg.norm(displacement, axis=2)
    if algorithm == 'Twin Trap':
        reference += np.where(displacement[:, :, 0] > 0, pi, 0.)
    elif algorithm == 'Vortex Trap':
        reference += np.arctan2(displacement[:, :, 1], displacement[:, :, 0])
    expected = np.angle(AMPLITUDES * np.exp(1j * reference).sum(axis=1)) % (2 * pi)
    # Zero-amplitude channels have no meaningful phase; the engine uses zero.
    expected[AMPLITUDES == 0] = 0.
    assert phases.shape == (5,)
    np.testing.assert_allclose(phases, expected, atol=1e-12)


@pytest.mark.parametrize('algorithm', ['Focus', 'Twin Trap', 'Vortex Trap'])
def test_missing_dll_preserves_live_and_trajectory_calculation(monkeypatch, algorithm):
    from acousticstudio import sonic_wrapper
    monkeypatch.setattr(sonic_wrapper, '_cpp_lib', None)
    engine = PhaseEngine()
    expected, _ = engine.calculate_phases(CENTERS, active_points(POINTS), AMPLITUDES, algorithm, 0)
    actual, packet = engine.calculate_phases(CENTERS, active_points(POINTS), AMPLITUDES, algorithm, 1)
    np.testing.assert_allclose(actual, expected)
    assert packet is None
    rows = engine.calculate_trajectory_phases(CENTERS, POINTS, AMPLITUDES, algorithm, 1)
    assert rows.shape == (2, 5)
    for index, point in enumerate(POINTS):
        live, _ = engine.calculate_phases(CENTERS, active_points([point]), AMPLITUDES, algorithm, 0)
        np.testing.assert_allclose(rows[index], live)


@pytest.mark.parametrize('algorithm', ['Focus', 'Twin Trap', 'Vortex Trap'])
def test_available_cpp_matches_cpu_for_unequal_counts(algorithm):
    from acousticstudio import sonic_wrapper
    if sonic_wrapper._cpp_lib is None:
        pytest.skip('Native DLL is not installed; fallback is covered separately.')
    engine = PhaseEngine()
    cpu, _ = engine.calculate_phases(CENTERS, active_points(POINTS), AMPLITUDES, algorithm, 0)
    native, _ = engine.calculate_phases(CENTERS, active_points(POINTS), AMPLITUDES, algorithm, 1)
    np.testing.assert_allclose(np.exp(1j * native), np.exp(1j * cpu), atol=1e-12)


def test_native_wrapper_rejects_old_reversed_coordinate_call():
    from acousticstudio.sonic_wrapper import calculate_phases_sonic
    with pytest.raises(ValueError, match='진폭'):
        calculate_phases_sonic(*POINTS.T, *CENTERS.T, AMPLITUDES, 'Twin Trap', PhaseEngine().k)


@pytest.mark.parametrize('bad_result', [np.zeros(2), np.full(5, np.nan), np.zeros((5, 1))])
def test_bad_backend_output_is_rejected(monkeypatch, bad_result):
    from acousticstudio import sonic_wrapper
    monkeypatch.setattr(sonic_wrapper, 'calculate_phases_sonic', lambda *args: (bad_result, None))
    with pytest.raises(ValueError, match='계산 결과'):
        PhaseEngine().calculate_phases(CENTERS, active_points(POINTS), AMPLITUDES, 'Twin Trap', 1)


@pytest.mark.parametrize('amplitudes', [np.ones(2), [1., 1., 1., 1., np.nan], [1., 1., 1., 1., -1.]])
def test_invalid_amplitude_inputs_are_rejected(amplitudes):
    with pytest.raises(ValueError, match='진폭'):
        PhaseEngine().calculate_phases(CENTERS, active_points(POINTS), amplitudes, 'Twin Trap', 0)


def test_empty_live_inputs_have_correct_shape_but_cannot_export_a_trajectory():
    engine = PhaseEngine()
    assert engine.calculate_phases([], active_points(POINTS), [], 'Twin Trap', 0)[0].shape == (0,)
    np.testing.assert_array_equal(engine.calculate_phases(CENTERS, [], AMPLITUDES, 'Twin Trap', 0)[0], np.zeros(5))
    with pytest.raises(ValueError, match='좌표가 필요'):
        engine.calculate_trajectory_phases([], POINTS, [], 'Twin Trap')


def fake_levitate(monkeypatch, vectors):
    captured = {'u': [], 'points': []}

    def array(**kwargs):
        captured['positions'] = kwargs['positions']
        captured['normals'] = kwargs['normals']
        return object()

    def transducer(**kwargs):
        captured['transducer_config'] = kwargs
        return object()

    class Field:
        def __matmul__(self, point):
            captured['points'].append(point)

            def evaluate(u):
                captured['u'].append(u)
                result = vectors[len(captured['u']) - 1]
                if isinstance(result, Exception):
                    raise result
                return result
            return evaluate

    module = SimpleNamespace(
        arrays=SimpleNamespace(TransducerArray=array),
        transducers=SimpleNamespace(PointSource=transducer),
        fields=SimpleNamespace(RadiationForceStiffness=lambda array: Field()),
    )
    monkeypatch.setitem(sys.modules, 'levitate', module)
    return captured


def test_diagnosis_uses_live_phase_dispatcher_amplitudes_and_si_units(monkeypatch):
    captured = fake_levitate(monkeypatch, [[1., 0., 0.], [0.2, 0., 0.]])
    engine = PhaseEngine()
    delays, metrics = engine.optimize_trajectory_physical(
        CENTERS, POINTS, 50., amplitudes=AMPLITUDES, smooth_accel=False,
    )
    assert trajectory_diagnosis_is_valid(metrics)
    assert metrics['score_kind'] == 'relative_stiffness_norm'
    np.testing.assert_allclose(delays, [50., 150.])
    np.testing.assert_allclose(captured['positions'], CENTERS.T * 1e-3)
    np.testing.assert_allclose(captured['points'], POINTS * 1e-3)
    for index, point in enumerate(POINTS):
        live, _ = engine.calculate_phases(CENTERS, active_points([point]), AMPLITUDES, 'Twin Trap', 0)
        np.testing.assert_allclose(captured['u'][index], AMPLITUDES * np.exp(1j * live))


def test_diagnosis_uses_supplied_normals_frequency_speed_and_pressure_scale(monkeypatch):
    from acousticstudio.field_model import FieldConfig
    captured = fake_levitate(monkeypatch, [[1., 0., 0.], [.2, 0., 0.]])
    engine = PhaseEngine()
    normals = np.tile([-1., 0., 0.], (5, 1))
    config = FieldConfig(frequency_hz=39000., sound_speed_m_s=340., source_strength=2.3)
    _, metrics = engine.optimize_trajectory_physical(
        CENTERS, POINTS, 50., amplitudes=AMPLITUDES, field_config=config, normals=normals)
    assert metrics['valid'], metrics['status']
    np.testing.assert_array_equal(captured['normals'], normals.T)
    assert captured['transducer_config']['freq'] == 39000.
    assert captured['transducer_config']['p0'] == 2.3
    assert captured['transducer_config']['medium'].c == 340.
    for index, point in enumerate(POINTS):
        phases, _ = engine.calculate_phases(CENTERS, active_points([point]), AMPLITUDES, 'Twin Trap', 0,
                                           field_config=config, normals=normals)
        np.testing.assert_allclose(captured['u'][index], AMPLITUDES * np.exp(1j * phases))


@pytest.mark.parametrize('vectors', [
    [[0., 0., 0.], [0., 0., 0.]],
    [[1., 0., 0.], [np.nan, 0., 0.]],
    [[1., 0., 0.], [1e308, 0., 0.]],
    [[1., 0., 0.], [1., 2.]],
    [[1., 0., 0.], RuntimeError('solver failed')],
])
def test_physics_failure_has_no_success_score_and_resets_delays(monkeypatch, vectors):
    fake_levitate(monkeypatch, vectors)
    delays, metrics = PhaseEngine().optimize_trajectory_physical(CENTERS, POINTS, 50.)
    assert not trajectory_diagnosis_is_valid(metrics)
    assert metrics['valid'] is False and metrics['grade'] == '진단 불가'
    assert metrics['avg_stability'] is None and metrics['min_stability'] is None
    np.testing.assert_array_equal(delays, [50., 50.])


def test_missing_levitate_uses_only_geometric_ramp(monkeypatch):
    monkeypatch.setitem(sys.modules, 'levitate', None)
    points = np.vstack([POINTS, POINTS])
    delays, metrics = PhaseEngine().optimize_trajectory_physical(CENTERS, points, 40.)
    assert not trajectory_diagnosis_is_valid(metrics)
    np.testing.assert_allclose(delays, [70., 40., 40., 70.])


@pytest.mark.parametrize('centers,points', [([], POINTS), (CENTERS, []), (CENTERS, POINTS[:1])])
def test_insufficient_geometry_cannot_produce_a_diagnosis(centers, points):
    delays, metrics = PhaseEngine().optimize_trajectory_physical(centers, points, 50.)
    assert delays.shape == (len(points),)
    assert metrics['avg_stability'] is None and not trajectory_diagnosis_is_valid(metrics)


def test_installed_levitate_evaluates_finite_waypoint_stiffness():
    # A software smoke test, without assuming physically stable levitation.
    centers = np.array([[-20., -20., -40.], [20., -20., -40.],
                        [-20., 20., 40.], [20., 20., 40.]])
    points = np.array([[0., 0., 0.], [1., 0., 0.]])
    delays, metrics = PhaseEngine().optimize_trajectory_physical(centers, points, 50.)
    assert trajectory_diagnosis_is_valid(metrics), metrics['status']
    assert metrics['stiffness'].shape == (2, 3)
    assert np.isfinite(delays).all() and np.isfinite(metrics['stiffness']).all()


class FakeSerial:
    def __init__(self):
        self.frames = []

    def write(self, frame):
        self.frames.append(frame)
        return len(frame)

    def flush(self):
        pass


@pytest.mark.parametrize('profile_key', BOARD_PROFILES)
def test_all_exports_share_send_mapping_correction_and_phase_steps(tmp_path, profile_key):
    controller = HardwareController()
    controller.set_board_profile(profile_key)
    count = controller.board_profile.channel_count or 5
    mapping = list(reversed(range(count))) if controller.board_profile.channel_count else list(range(count))
    if controller.board_profile.channel_count:
        controller.set_channel_map(mapping)
    phases = np.arange(count) * 2 * pi / 32
    offsets = (np.arange(count) % 3) * 2 * pi / 32
    controller.set_phase_offsets(offsets)
    rows = np.vstack([phases, phases + 2 * pi / 32])
    expected = [[int(index + index % 3 + step) % 32 for index in mapping] for step in range(2)]
    fake_serial = FakeSerial()
    controller.serial_port = fake_serial
    frames = [controller.send_phases(row) for row in rows]
    for step, row in enumerate(rows):
        assert controller.prepare_phase_steps(row) == expected[step]

    binary = tmp_path / 'wire.bin'
    save_trajectory_export(binary, 'binary', 'test', POINTS, [50., 75.], rows, controller)
    assert binary.read_bytes() == b''.join(fake_serial.frames) == b''.join(frames)
    csv_path = tmp_path / 'trajectory.csv'
    save_trajectory_export(csv_path, 'csv', 'test', POINTS, [50., 75.], rows, controller)
    with csv_path.open(encoding='utf-8', newline='') as stream:
        csv_rows = list(csv.reader(stream))
    assert csv_rows[0][6] == 'Physical0_Phase32'
    assert [list(map(int, row[6:])) for row in csv_rows[1:]] == expected
    assert all(row[5] == profile_key for row in csv_rows[1:])
    header = tmp_path / 'trajectory.h'
    save_trajectory_export(header, 'header', 'test', POINTS, [50., 75.], rows, controller)
    text = header.read_text(encoding='utf-8')
    assert 'corrected physical channel order' in text and profile_key in text
    assert [list(map(int, row.split(','))) for row in re.findall(r'\{ ([0-9, ]+) \}', text)] == expected
    legacy = tmp_path / 'trajectory.legacy.bin'
    save_trajectory_export(legacy, 'legacy', 'test', POINTS, [50., 75.], rows, controller)
    assert legacy.read_bytes() == b''.join(b'\xfa' + bytes(row) + b'\xfd' for row in expected)
    assert legacy.read_bytes() != binary.read_bytes()


@pytest.mark.parametrize('bad_phases', [np.zeros(255), np.zeros(257), np.full(256, np.nan)])
def test_bad_channels_are_rejected_before_mapping_sending_or_creating_file(tmp_path, bad_phases):
    controller = HardwareController()
    controller.set_board_profile('ultraino_simplefpga_256')
    controller.set_channel_map(reversed(range(256)))
    fake_serial = FakeSerial()
    controller.serial_port = fake_serial
    with pytest.raises(ValueError):
        controller.send_phases(bad_phases)
    path = tmp_path / 'invalid.bin'
    with pytest.raises(ValueError):
        save_trajectory_export(path, 'binary', 'test', POINTS, [50., 50.],
                               np.vstack([bad_phases, bad_phases]), controller)
    assert not path.exists() and fake_serial.frames == []


def test_profile_change_clears_mapping_and_correction():
    controller = HardwareController()
    controller.set_board_profile('ultraino_simplefpga_256')
    controller.set_channel_map(reversed(range(256)))
    controller.set_phase_offsets(np.ones(256))
    controller.set_board_profile('sonicsurface_fpga_256')
    assert controller.channel_map is None and controller.phase_offsets is None


def test_header_rejects_delay_overflow_without_creating_file(tmp_path):
    controller = HardwareController()
    path = tmp_path / 'overflow.h'
    with pytest.raises(ValueError, match='uint16_t'):
        save_trajectory_export(path, 'header', 'test', POINTS, [50., 65536.], np.zeros((2, 5)), controller)
    assert not path.exists()
