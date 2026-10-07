"""Independent candidate-map/codec audit and full Qt calibration smoke, offline."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import csv
import hashlib
import json
from math import floor, pi
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

import numpy as np
from PySide6 import QtCore
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QFileDialog

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))
from acousticstudio.app import AcousticStudioMain, ResourceMonitorThread, source_inputs
from acousticstudio.calibration import load_candidate_map
from acousticstudio.calibration_ui import CalibrationDialog
from acousticstudio.force_analysis import AnalysisSettings, ForceAnalyzer, json_result
from acousticstudio.geometry import CREO_PRESET_LABEL
from acousticstudio.hardware import BOARD_PROFILES, HardwareController
from acousticstudio.trajectory_export import save_trajectory_export
from acousticstudio import file_io

OUTPUT = Path(__file__).resolve().parent
CANDIDATE = REPO / '구상도/outputs/panel_8faces_32ch_R1/physical_to_software_channel_map.json'
CHANNEL_CSV = CANDIDATE.with_name('channel_map.csv')


class FakeSerial:
    def __init__(self): self.frames = []
    def write(self, frame): self.frames.append(frame); return len(frame)
    def close(self): pass
    def flush(self): raise AssertionError('No unbounded flush')


def expected_frame(profile, steps):
    if profile.transport == 'phase32_frame':
        return b'\xfe' + bytes(steps) + b'\xfd'
    if profile.transport == 'sonicsurface_two_board':
        return b'\xfe\xc0' + bytes(steps[:128]) + b'\xc1' + bytes(steps[128:]) + b'\xfd'
    return ('phases=' + ''.join(f'{step},' for step in steps) + '\n').encode('ascii')


def wait_for(app, condition):
    deadline = time.monotonic() + 30
    while not condition() and time.monotonic() < deadline:
        app.processEvents(); time.sleep(.005)
    app.processEvents(); assert condition()


def main():
    app = QApplication.instance() or QApplication([])
    mapping, source, digest = load_candidate_map(CANDIDATE, 256)
    with CHANNEL_CSV.open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            assert mapping[int(row['fpga_physical_channel'])] == int(row['channel'])
    phases = np.linspace(-12 * pi, 12 * pi, 256)
    offsets = np.arange(256) * 2 * pi / 32 * .5
    cases = []
    with TemporaryDirectory(prefix='t5_exports_', dir=OUTPUT) as temporary:
        assert Path(temporary).resolve().parent == OUTPUT
        for key, profile in BOARD_PROFILES.items():
            if profile.off_code is None:
                controller = HardwareController()
                try:
                    controller.build_test_frame(0, count=256)
                except ValueError:
                    continue
                raise AssertionError('Legacy must reject OFF')
            controller = HardwareController(); controller.set_board_profile(key)
            controller.set_channel_map(mapping); controller.set_phase_offsets(offsets)
            fake = FakeSerial(); controller.serial_port = fake
            for kind in ('pattern', 'single', 'all_off'):
                enabled = [index % 17 != 0 for index in range(256)] if kind == 'pattern' else [index == 7 and kind == 'single' for index in range(256)]
                inputs = phases if kind == 'pattern' else np.zeros(256)
                expected = [floor(((float(inputs[index]) + float(offsets[index])) % (2 * pi)) / (2 * pi) * 32 + .5) % 32
                            if enabled[index] else 32 for index in mapping]
                reference = expected_frame(profile, expected)
                assert controller.send_phases(inputs, enabled) == reference == fake.frames[-1]
                path = Path(temporary) / 'wire.bin'
                save_trajectory_export(path, 'binary', 'audit', [[0., 0., 0.]], [30.], inputs[None, :], controller, enabled)
                assert path.read_bytes() == reference
                for format_key in ('csv', 'header'):
                    path = Path(temporary) / ('wire.' + format_key)
                    save_trajectory_export(path, format_key, 'audit', [[0., 0., 0.]], [30.], inputs[None, :], controller, enabled, 'audit-calibration')
                    text = path.read_text(encoding='utf-8')
                    assert 'audit-calibration' in text
                    if format_key == 'csv':
                        rows = list(csv.reader(text.splitlines()))
                        assert list(map(int, rows[1][6:-1])) == expected
                cases.append(dict(profile=key, kind=kind, bytes=len(reference), inactive_channels=expected.count(32),
                                  frame_sha256=hashlib.sha256(reference).hexdigest(), send_export_equal=True))
            controller.disconnect()

    font_id = QFontDatabase.addApplicationFont('C:/Windows/Fonts/malgun.ttf')
    families = QFontDatabase.applicationFontFamilies(font_id)
    if families: app.setFont(QFont(families[0], 10))
    settings_class = QtCore.QSettings
    with TemporaryDirectory(prefix='t5_ui_', dir=OUTPUT) as temporary:
        settings = settings_class(str(Path(temporary) / 'ui.ini'), settings_class.IniFormat)
        with patch.object(QtCore, 'QSettings', return_value=settings), patch.object(ResourceMonitorThread, 'start'), patch('acousticstudio.hardware.serial.Serial', side_effect=AssertionError('Physical serial forbidden')):
            window = AcousticStudioMain()
            messages = []; window.show_silent_msg = lambda *args: messages.append(args)
            window.check_unsaved_changes = lambda: True
            try:
                window.show(); app.processEvents()
                window.auto_calc_cb.setChecked(False); window.chk_realtime_send.setChecked(False)
                window.run_btn.setCheckable(False); window.compute_mode_cb.setCurrentIndex(1)
                window.select_board_profile('ultraino_simplefpga_256')
                window.array_type_cb.setCurrentText(CREO_PRESET_LABEL); window.generate_array()
                window.add_control_point()
                window.control_points[0]['actor'].SetPosition(-10., -3., -45.)

                def probe(dialog):
                    dialog.show(); dialog.load_candidate()
                    dialog.identifier.setText('T5 software example; unmeasured')
                    dialog.conditions.setPlainText('소프트웨어 검증용 예시. 실제 보드·음압·위상 측정 없음.')
                    dialog.table.cellWidget(0, 1).setValue(-.3)
                    dialog.table.cellWidget(1, 2).setValue(.7)
                    dialog.table.item(2, 3).setCheckState(Qt.Unchecked)
                    dialog.apply_values()
                    assert window.calibration is not None and not window.calibration.pressure_calibrated
                    window.calibration.save(OUTPUT / 't5_example_calibration.json')
                    app.processEvents()
                    dialog.grab().save(str(OUTPUT / 't5_calibration_dialog.png'))
                    dialog.close(); return 0

                with patch.object(CalibrationDialog, 'exec', probe): window.open_calibration()
                assert source_inputs(window)[1][1] == .7 and source_inputs(window)[1][2] == 0.
                window.trap_type_cb.setCurrentText('Kinoforms')
                window.start_hologram_live()
                wait_for(app, lambda: window._hologram_controller is not None and not window._hologram_controller.busy)
                assert not window._field_model_dirty
                snapshot, targets, _, _ = window.hologram_inputs()
                force = ForceAnalyzer(snapshot, AnalysisSettings(samples=5)).analyze(targets[0].position_mm)
                fake = FakeSerial(); window.hw_controller.serial_port = fake
                window.send_phase_data(); live = fake.frames[-1]
                assert live[1 + mapping.index(2)] == 32
                path = OUTPUT / 't5_example_frame.bin'
                save_trajectory_export(path, 'binary', 'T5 example', [targets[0].position_mm], [30.],
                                       snapshot.phases_rad[None, :], window.hw_controller,
                                       active=(snapshot.amplitudes > 0).tolist(), calibration_id=window.calibration.calibration_id)
                assert path.read_bytes() == live
                window.send_test_frame(1); assert fake.frames[-1][1:-1].count(32) == 255
                window.send_all_off(); assert fake.frames[-1][1:-1] == bytes([32] * 256)
                window.hw_controller.disconnect()
                saved = window.get_state(for_file=True)
                file_io.save_project(OUTPUT / 't5_example_project.json', saved)
                window.apply_calibration(None); window.set_state(saved)
                wait_for(app, lambda: not window._hologram_controller.busy and not window._field_model_dirty)
                assert window.get_state(for_file=True) == saved
                assert messages == [('하드웨어 연결 끊김', '사용자에 의해 연결이 해제되었습니다.')], messages
                assert not window.chk_realtime_send.isChecked()
                force_summary = dict(restoring=force['restoring'], converged=force['converged'],
                                     gravity_equilibrium_status=force['gravity_equilibrium_status'])
            finally:
                if window._hologram_controller is not None:
                    window._hologram_controller.cancel(); wait_for(app, lambda: not window._hologram_controller.busy)
                window.hw_controller.disconnect(); window.close(); app.processEvents()
    source_names = ('src/acousticstudio/calibration.py', 'src/acousticstudio/calibration_ui.py',
                    'src/acousticstudio/hardware.py', 'src/acousticstudio/trajectory_export.py',
                    'src/acousticstudio/app.py', 'src/acousticstudio/geometry_scene.py', 'src/acousticstudio/geometry.py',
                    'src/acousticstudio/sonic_core.dll', '구상도/outputs/panel_8faces_32ch_R1/array_positions_256.json',
                    '구상도/outputs/panel_8faces_32ch_R1/channel_map.csv',
                    '구상도/outputs/panel_8faces_32ch_R1/physical_to_software_channel_map.json')
    hashes = {name: hashlib.sha256((REPO / name).read_bytes()).hexdigest() for name in source_names}
    originals = ['simulations/Ultraino/AcousticFieldSim/src/acousticfield3d/protocols/SimpleFPGA.java',
                 'simulations/Ultraino/AcousticFieldSim/src/acousticfield3d/simulation/Transducer.java',
                 'simulations/SonicSurface/Firmware/ESP32 controller/CommandSenderESP32/CommandSenderESP32.ino',
                 'simulations/SonicSurface/Firmware/ESP32 haptic controller/TestHoloConnection4/TestHoloConnection4.ino']
    report = dict(python=sys.executable, hashes=hashes, source_hashes={name: hashlib.sha256((REPO.parent / name).read_bytes()).hexdigest() for name in originals},
                  candidate_mapping_csv_matches=True, candidate_sha256=digest, mapping_status='candidate_unverified',
                  protocol_cases=cases, qt_main_integration=True, calibrated_gain_inputs=True,
                  project_restore=True, legacy_off_rejected=True, force_guard=force_summary,
                  physical_serial_opened=False, pressure_calibrated=False, hardware_measured=False,
                  qt_dialog_capture=True, qt_viewport_capture=False)
    (OUTPUT / 't5_pipeline_result.json').write_text(json.dumps(json_result(report), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(protocol_cases=len(cases), qt_main_integration=True, source_hashes_checked=len(originals),
                         physical_serial_opened=False, pressure_calibrated=False), indent=2))


if __name__ == '__main__': main()
