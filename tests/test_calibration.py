"""Calibration ordering/provenance and software-only wire failure regressions."""
from copy import deepcopy
import json
from math import pi
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import serial

from acousticstudio.calibration import Calibration, CalibrationRevision, layout_signature, load_candidate_map, utc_now
from acousticstudio.geometry import load_creo_tunnel, transform_geometry
from acousticstudio.hardware import BOARD_PROFILES, HardwareController, encode_phase_frame, phases_to_steps
from acousticstudio.trajectory_export import save_trajectory_export


def record(count=256, **kwargs):
    values = dict(calibration_id='test', board_profile='ultraino_simplefpga_256', geometry_signature='a' * 64,
                  phase_offsets_rad=(0.,) * count, source_gains=(1.,) * count, enabled=(True,) * count, created_utc=utc_now())
    values.update(kwargs)
    return Calibration(**values)


@pytest.mark.parametrize('scaled,expected', [(0.5, 1), (1.5, 2), (2.5, 3), (-0.5, 0), (-1.5, 31), (31.5, 0), (32., 0)])
def test_ultraino_half_step_semantics_and_off_boundary(scaled, expected):
    phase = scaled * 2 * pi / 32
    assert phases_to_steps([phase], rounding='half_up') == [expected]
    assert encode_phase_frame(BOARD_PROFILES['ultraino_simplefpga_256'], [phase] * 256)[1] == expected


def test_legacy_ties_even_is_preserved_and_half_step_neighbors_wrap():
    assert phases_to_steps([.5 * 2 * pi / 32, 2.5 * 2 * pi / 32]) == [0, 2]
    step = 2 * pi / 32
    assert phases_to_steps([.5 * step - 1e-10, .5 * step + 1e-10, 31.5 * step + 1e-10], rounding='half_up') == [0, 1, 0]
    with pytest.raises(ValueError):
        phases_to_steps([0.], rounding='unknown')


@pytest.mark.parametrize('profile', [key for key in BOARD_PROFILES if key != 'legacy_phase32'])
def test_enabled_phase_zero_and_disabled_off_are_distinct_for_all_supported_profiles(profile):
    controller = HardwareController(); controller.set_board_profile(profile)
    steps = controller.prepare_phase_steps([0.] * 256, [True] + [False] * 255)
    assert steps == [0] + [32] * 255
    frame = controller.build_phase_frame([0.] * 256, [True] + [False] * 255)
    assert frame == encode_phase_frame(controller.board_profile, [0.] * 256, [True] + [False] * 255)
    assert len(controller.build_test_frame()) == len(frame) or profile.endswith('command')


def test_map_and_additive_offset_precede_quantization_and_map_active_once(tmp_path):
    controller = HardwareController(); controller.set_board_profile('ultraino_simplefpga_256')
    mapping = list(reversed(range(256))); controller.set_channel_map(mapping)
    offsets = [0.] * 256; offsets[3] = 2 * pi * 2.5 / 32; controller.set_phase_offsets(offsets)
    active = [False] * 256; active[3] = True
    frame = controller.build_phase_frame([0.] * 256, active)
    assert frame[1 + mapping.index(3)] == 3 and frame[1:-1].count(32) == 255
    assert frame == controller.build_test_frame(3)
    path = tmp_path / 'wire.bin'
    save_trajectory_export(path, 'binary', 'test', [[0., 0., 0.]], [20.], np.zeros((1, 256)), controller, active)
    assert path.read_bytes() == frame
    csv_path = tmp_path / 'wire.csv'
    save_trajectory_export(csv_path, 'csv', 'test', [[0., 0., 0.]], [20.], np.zeros((1, 256)), controller, active)
    assert list(map(int, csv_path.read_text(encoding='utf-8').splitlines()[1].split(',')[6:])) == list(frame[1:-1])
    assert controller.build_test_frame()[1:-1] == bytes([32] * 256)


def test_legacy_off_unsupported_and_invalid_map_masks_fail_before_file(tmp_path):
    controller = HardwareController()
    with pytest.raises(ValueError, match='OFF'):
        controller.build_test_frame(0, count=4)
    path = tmp_path / 'invalid.bin'
    with pytest.raises(ValueError, match='OFF'):
        save_trajectory_export(path, 'binary', 'test', [[0., 0., 0.]], [20.], np.zeros((1, 4)), controller, [False] * 4)
    assert not path.exists()
    controller.set_board_profile('ultraino_simplefpga_256')
    for mapping in ([0.] + list(range(1, 256)), [True] + list(range(1, 256)), [0] * 256):
        with pytest.raises(ValueError):
            controller.set_channel_map(mapping)
    with pytest.raises(ValueError):
        controller.build_phase_frame([0.] * 256, [1] * 256)


@pytest.mark.parametrize('changes', [dict(source_gains=(-1.,) * 256), dict(phase_offsets_rad=(float('nan'),) * 256),
                                   dict(enabled=(0,) * 256), dict(gain_units='Pa'), dict(pressure_calibrated=True),
                                   dict(schema_version=True), dict(created_utc='2026-10-07'), dict(geometry_signature='wrong'),
                                   dict(provenance='measured'), dict(channel_map=(0,) * 256), dict(mapping_status='candidate_unverified'),
                                   dict(channel_map=tuple(reversed(range(256))))])
def test_invalid_calibration_cannot_claim_measured_or_absolute_pressure(changes):
    with pytest.raises(ValueError):
        record(**changes)


def test_relative_gain_disabled_state_and_history_json_roundtrip(tmp_path):
    gains = [1.] * 256; gains[2] = 0.; gains[3] = .7
    enabled = [True] * 256; enabled[4] = False
    values = record(source_gains=gains, enabled=enabled, history=(CalibrationRevision('old', utc_now(), 'reference'),))
    assert values.active[2:5] == (False, True, False)
    path = tmp_path / 'calibration.json'; values.save(path)
    assert Calibration.load(path) == values
    assert Calibration.from_dict(json.loads(json.dumps(values.to_dict()))) == values
    with pytest.raises(ValueError):
        values.validate_context(256, values.board_profile, 'b' * 64)
    with pytest.raises(ValueError):
        values.validate_context(255, values.board_profile, values.geometry_signature)


def test_real_creo_candidate_map_and_signature_bind_channel_identity_not_cad_pose():
    geometry = load_creo_tunnel()
    transducers = [dict(geometry_instance=geometry['instance_id'], geometry_channel=index) for index in range(256)]
    signature = layout_signature([geometry], transducers)
    transformed = transform_geometry(geometry, [[0., -1., 0., 10.], [1., 0., 0., 20.], [0., 0., 1., 30.], [0., 0., 0., 1.]])
    assert layout_signature([transformed], transducers) == signature
    assert layout_signature([geometry], list(reversed(transducers))) != signature
    modified = deepcopy(geometry); modified['elements'][0]['base_matrix'][0][3] += 1.
    assert layout_signature([modified], transducers) != signature
    path = Path(__file__).resolve().parents[1] / '구상도/outputs/panel_8faces_32ch_R1/physical_to_software_channel_map.json'
    mapping, source, digest = load_candidate_map(path, 256)
    assert mapping != tuple(range(256)) and len(set(mapping)) == 256
    values = record(geometry_signature=signature, channel_map=mapping, mapping_status='candidate_unverified', mapping_source=source, mapping_sha256=digest)
    assert not values.pressure_calibrated and values.mapping_status != 'measured'


@pytest.mark.parametrize('failure', ['partial', 'timeout', 'unplugged'])
def test_failed_frame_is_not_retried_or_replayed_after_reconnect(failure, monkeypatch):
    class FakeSerial:
        def __init__(self):
            self.frames = []; self.closed = False
        def write(self, frame):
            self.frames.append(frame)
            if failure == 'timeout':
                raise serial.SerialTimeoutException('timeout')
            if failure == 'unplugged':
                raise OSError('unplugged')
            return len(frame) - 1
        def close(self):
            self.closed = True
        def flush(self):
            raise AssertionError('unbounded flush')
    controller = HardwareController(); controller.set_board_profile('ultraino_simplefpga_256')
    failed = FakeSerial(); controller.serial_port = failed
    errors, disconnected = [], []
    controller.send_failed.connect(errors.append); controller.disconnected.connect(disconnected.append)
    assert not controller.send_packet(controller.build_phase_frame([0.] * 256))
    assert len(failed.frames) == 1 and failed.closed and not controller.is_connected()
    assert errors and disconnected
    calls = []
    healthy = SimpleNamespace(write=lambda frame: len(frame), close=lambda: None, in_waiting=0)
    monkeypatch.setattr('acousticstudio.hardware.serial.Serial', lambda *args, **kwargs: calls.append(kwargs) or healthy)
    assert controller.connect('FAKE_ONLY', 230400)
    assert calls[0]['write_timeout'] == .1 and not hasattr(healthy, 'frames')
    controller.disconnect()


def test_disconnected_write_and_atomic_hardware_restore():
    controller = HardwareController()
    assert controller.send_packet(b'frame') is False
    original = controller.settings()
    with pytest.raises(ValueError):
        controller.restore_settings(dict(board_profile='ultraino_simplefpga_256', channel_map=[0] * 256))
    assert controller.settings() == original
    controller.serial_port = SimpleNamespace(close=lambda: None)
    with pytest.raises(RuntimeError):
        controller.restore_settings(dict(board_profile='ultraino_simplefpga_256'))
    assert controller.settings() == original
    controller.disconnect()


def test_connect_failure_and_health_disconnect_leave_no_transport(monkeypatch):
    controller = HardwareController(); errors = []; controller.send_failed.connect(errors.append)
    def fail(*args, **kwargs):
        raise OSError('fake port inaccessible')
    monkeypatch.setattr('acousticstudio.hardware.serial.Serial', fail)
    assert not controller.connect('FAKE_ONLY', 230400)
    assert not controller.is_connected() and errors
    class Lost:
        closed = False
        @property
        def in_waiting(self): raise OSError('lost')
        def close(self): self.closed = True
    lost = Lost(); controller.serial_port = lost
    controller.check_health()
    assert lost.closed and not controller.is_connected()
