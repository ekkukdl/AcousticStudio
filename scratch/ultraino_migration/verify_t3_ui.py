"""Full main-window integration and fixed-drive dialog, with no serial writes."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

import numpy as np
from PySide6 import QtCore
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QFileDialog

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))
from acousticstudio.app import AcousticStudioMain, ResourceMonitorThread
from acousticstudio.geometry import CREO_PRESET_LABEL
from acousticstudio.force_analysis_ui import ForceAnalysisDialog


def main():
    output = Path(__file__).resolve().parent
    app = QApplication.instance() or QApplication([])
    font_id = QFontDatabase.addApplicationFont('C:/Windows/Fonts/malgun.ttf')
    families = QFontDatabase.applicationFontFamilies(font_id)
    if families:
        app.setFont(QFont(families[0], 10))
    settings_class = QtCore.QSettings
    with TemporaryDirectory(prefix='acousticstudio-t3-') as temporary:
        settings = settings_class(str(Path(temporary) / 'ui.ini'), settings_class.IniFormat)
        with patch.object(QtCore, 'QSettings', return_value=settings), patch.object(ResourceMonitorThread, 'start'):
            window = AcousticStudioMain()
        messages = []
        window.show_silent_msg = lambda *args: messages.append(args)
        try:
            window.show(); app.processEvents()
            window.compute_mode_cb.setCurrentIndex(1)
            window.trap_type_cb.setCurrentText('Twin Trap')
            window.array_type_cb.setCurrentText(CREO_PRESET_LABEL)
            window.generate_array(); window.add_control_point()
            point = window.control_points[0]
            point['z'] = 0.; point['actor'].SetPosition(0., 0., -50.)
            window.open_force_analysis()
            assert messages and '먼저' in messages[-1][1]
            window.chk_realtime_send.setChecked(False)
            window.hw_controller.send_phases = lambda *_: (_ for _ in ()).throw(AssertionError('Serial writes are forbidden here'))
            window.run_btn.setCheckable(False); window._last_sim_time = 0.; window.simulate_colors()
            original_phases = np.array([actor._phase for actor in window.transducer_actors])
            reports = []

            def verify_dialog(dialog):
                dialog.show(); app.processEvents()
                assert len(dialog.snapshot.sources_mm) == 256
                assert dialog.snapshot.field_config.aperture_radius_mm is None
                dialog.start_analysis()
                deadline = time.monotonic() + 30
                while dialog._thread is not None and time.monotonic() < deadline:
                    app.processEvents(); time.sleep(.01)
                assert dialog._thread is None and dialog.result is not None
                assert dialog.result['converged'] and dialog.result['restoring']['status'] == 'restoring'
                assert dialog.result['gravity_equilibrium_status'] == 'unavailable_uncalibrated_pressure'
                assert '예시' in dialog.summary.text()
                np.testing.assert_array_equal(dialog.snapshot.phases_rad, original_phases)
                path = output / 't3_example_analysis.json'
                with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(path), 'Analysis JSON (*.json)')):
                    dialog.export_result()
                data = json.loads(path.read_text(encoding='utf-8'))
                assert data['snapshot']['phases_rad'] == original_phases.tolist()
                dialog.coupled.setChecked(True)
                app.processEvents()
                dialog.canvas.draw()
                dialog.figure.savefig(output / 't3_force_curves.png', dpi=140)
                dialog.grab().save(str(output / 't3_force_dialog.png'))
                reports.append(dict(channels=256, frozen_phases=True, source_model=data['snapshot']['field_config']['model'],
                                    particle_provenance=data['settings']['particle']['provenance'],
                                    pressure_calibrated=False, axis_samples=data['settings']['samples'],
                                    converged=data['converged'], restoring=data['restoring'],
                                    conditional_centre_residual=data['conditional_centre_residual'],
                                    gravity_equilibrium_status=data['gravity_equilibrium_status'],
                                    backend=data['backend']))
                dialog.close(); app.processEvents()
                return 0

            with patch.object(ForceAnalysisDialog, 'exec', verify_dialog):
                window.open_force_analysis()
            assert reports and len(messages) == 1, messages
            np.testing.assert_array_equal([actor._phase for actor in window.transducer_actors], original_phases)
            saved = window.get_state(for_file=True)
            window.clear_view(); window.set_state(saved); app.processEvents()
            assert window.get_state(for_file=True) == saved
            assert not window.hw_controller.is_connected()
            report = dict(python=sys.executable, qt_main_integration=True, phase_guard=True,
                          snapshot_unchanged=True, force_settings_save_restore=True,
                          qt_dialog_capture=True, qt_viewport_capture=False, serial_connected=False,
                          analyses=reports)
            (output / 't3_ui_result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report, indent=2))
        finally:
            window._last_saved_state = window.get_state(for_file=True)
            window.plotter.close(); window.close(); app.processEvents()


if __name__ == '__main__':
    main()
