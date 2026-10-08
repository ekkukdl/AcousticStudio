"""Actual Qt calibration flows without opening a physical serial port."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PySide6 import QtCore
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog

from acousticstudio.app import AcousticStudioMain, ResourceMonitorThread, source_inputs, window_layout
from acousticstudio.calibration import Calibration, utc_now
from acousticstudio.calibration_ui import CalibrationDialog
from acousticstudio.geometry import CREO_PRESET_LABEL
from acousticstudio.hardware import BOARD_PROFILES
from acousticstudio.trajectory_export import save_trajectory_export


@pytest.fixture
def window(tmp_path):
    app = QApplication.instance() or QApplication([])
    settings_class = QtCore.QSettings
    settings = settings_class(str(tmp_path / 'isolated.ini'), settings_class.IniFormat)
    with patch.object(QtCore, 'QSettings', return_value=settings), patch.object(ResourceMonitorThread, 'start'):
        result = AcousticStudioMain()
    result._test_messages = []
    result.show_silent_msg = lambda *args: result._test_messages.append(args)
    result.auto_calc_cb.setChecked(False); result.chk_realtime_send.setChecked(False)
    result.run_btn.setCheckable(False)
    result.compute_mode_cb.setCurrentIndex(1)
    result.select_board_profile('ultraino_simplefpga_256')
    result.array_type_cb.setCurrentText(CREO_PRESET_LABEL); result.generate_array()
    result.add_control_point()
    yield result
    if result.hw_controller.is_connected():
        result.hw_controller.disconnect()
    result.check_unsaved_changes = lambda: True
    result.close(); app.processEvents()


def values_for(window):
    return Calibration('qt-test', window.hw_controller.board_profile.key, window_layout(window),
                       tuple(.02 * index for index in range(256)), (1.,) * 256, (True,) * 256, utc_now())


def test_dialog_candidate_manual_edit_validation_and_offline_files(window, tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / '구상도/outputs/panel_8faces_32ch_R1/physical_to_software_channel_map.json'
    dialog = CalibrationDialog(256, BOARD_PROFILES['ultraino_simplefpga_256'], window_layout(window), candidate_path=path)
    applied = []; dialog.applied.connect(applied.append)
    dialog.load_candidate()
    assert dialog.mapping_status == 'candidate_unverified'
    dialog.table.cellWidget(0, 1).setValue(-.3)
    dialog.table.cellWidget(1, 2).setValue(.7)
    dialog.table.item(2, 3).setCheckState(Qt.Unchecked)
    dialog.apply_values()
    assert applied[-1].phase_offsets_rad[0] == -.3 and not applied[-1].enabled[2]
    assert applied[-1].source_gains[1] == .7 and not applied[-1].pressure_calibrated
    save = tmp_path / 'calibration.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(save), ''))
    dialog.save_json()
    saved = Calibration.load(save)
    assert saved.mapping_status == 'candidate_unverified'
    wire = tmp_path / 'single.bin'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(wire), ''))
    dialog.save_test(0)
    physical = saved.channel_map.index(0)
    assert wire.read_bytes()[1 + physical] != 32 and wire.read_bytes()[1:-1].count(32) == 255
    dialog.save_test(None)
    assert wire.read_bytes() == b'\xfe' + bytes([32] * 256) + b'\xfd'
    dialog.table.cellWidget(0, 4).setValue(dialog.table.cellWidget(1, 4).value())
    dialog.apply_values()
    assert len(applied) == 1 and '불가' in dialog.status.text()
    dialog.identity_map()
    assert dialog.read_values().channel_map is None
    dialog.provenance.setCurrentIndex(1)
    dialog.apply_values(); assert len(applied) == 1
    dialog.firmware.setText('reference'); dialog.wiring.setText('test-wiring')
    dialog.conditions.setPlainText('fake fixture only')
    dialog.apply_values(); assert applied[-1].provenance == 'measured'
    dialog.close()


def test_apply_gains_project_restore_undo_and_bad_binding_before_mutation(window, tmp_path):
    before = window.get_state(); window.push_state()
    gains = [1.] * 256; gains[0] = .7; gains[2] = 0.
    enabled = [True] * 256; enabled[3] = False
    calibration = replace(values_for(window), source_gains=gains, enabled=enabled, channel_map=tuple(reversed(range(256))), mapping_status='manual_unverified')
    window.apply_calibration(calibration)
    assert not window._test_messages
    assert window._field_model_dirty and window.hw_controller.active_channels[2:4] == [False, False]
    np.testing.assert_array_equal(source_inputs(window)[1][:4], [.7, 1., 0., 0.])
    state = window.get_state()
    window.undo(); assert window.get_state() == before
    window.redo(); assert window.get_state() == state
    from acousticstudio import file_io
    path = tmp_path / 'project.json'; file_io.save_project(path, window.get_state(for_file=True))
    window.apply_calibration(None)
    window.set_state(file_io.load_project(path))
    assert window.calibration == calibration and window.get_state() == state
    corrupt = deepcopy(state); corrupt['hardware_settings']['phase_offsets_rad'][0] += 1
    with pytest.raises(ValueError, match='다릅니다'):
        window.set_state(corrupt)
    assert window.get_state() == state
    corrupt = deepcopy(state); corrupt['calibration']['geometry_signature'] = 'b' * 64
    with pytest.raises(ValueError, match='서명'):
        window.set_state(corrupt)
    assert window.get_state() == state
    window.apply_calibration(None)
    legacy = deepcopy(before); legacy.pop('hardware_settings'); legacy.pop('calibration')
    window.set_state(legacy)
    assert window.calibration is None and window.hw_controller.phase_offsets is None
    window.apply_calibration(values_for(window))
    window.check_unsaved_changes = lambda: True
    window.new_project()
    assert window.calibration is None and window.hw_controller.phase_offsets is None and not window.transducer_actors


def test_live_export_force_inputs_share_gains_and_mapped_off_mask(window, tmp_path):
    from acousticstudio.force_analysis import AnalysisSettings, ForceAnalyzer
    class FakeSerial:
        def __init__(self): self.frames = []
        def write(self, frame): self.frames.append(frame); return len(frame)
        def close(self): pass
        def flush(self): raise AssertionError('no blocking flush')
    gains = [1.] * 256; gains[5] = 0.; gains[7] = .4
    calibration = replace(values_for(window), source_gains=gains, channel_map=tuple(reversed(range(256))), mapping_status='manual_unverified')
    window.apply_calibration(calibration)
    window.transducer_actors[9]._enabled = False
    window.simulate_colors()
    app = QApplication.instance()
    deadline = QtCore.QElapsedTimer(); deadline.start()
    while window._field_model_dirty and deadline.elapsed() < 15000:
        app.processEvents(); QtCore.QThread.msleep(5)
    assert not window._field_model_dirty
    snapshot, targets, _, _ = window.hologram_inputs()
    assert snapshot.amplitudes[5] == 0 and snapshot.amplitudes[7] == .4
    assert snapshot.amplitudes[9] == 0
    result = ForceAnalyzer(snapshot, AnalysisSettings(samples=5)).analyze(targets[0].position_mm)
    assert not result['pressure_calibrated'] and result['gravity_equilibrium_status'] == 'unavailable_uncalibrated_pressure'
    fake = FakeSerial(); window.hw_controller.serial_port = fake
    window.send_phase_data()
    assert not window._test_messages and fake.frames
    frame = fake.frames[-1]
    assert frame[1 + calibration.channel_map.index(5)] == 32
    assert frame[1 + calibration.channel_map.index(9)] == 32
    phases = np.array([actor._phase for actor in window.transducer_actors])
    path = tmp_path / 'live.bin'
    save_trajectory_export(path, 'binary', 'live', [targets[0].position_mm], [30.], phases[None, :], window.hw_controller,
                           active=(snapshot.amplitudes > 0).tolist(), calibration_id=calibration.calibration_id)
    assert path.read_bytes() == frame
    window.send_test_frame(7)
    assert fake.frames[-1][1:-1].count(32) == 255
    window.send_all_off()
    assert fake.frames[-1][1:-1] == bytes([32] * 256)
    original = window.get_state()
    with pytest.raises(RuntimeError):
        window.set_state(dict(original, hardware_settings=dict(board_profile='sonicsurface_fpga_256'), calibration=None))
    assert window.get_state() == original
    window.hw_controller.disconnect()
