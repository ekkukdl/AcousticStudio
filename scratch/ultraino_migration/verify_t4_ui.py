"""Full Qt Creo multi-trap edit/apply/live/stale/save-restore, with no serial I/O."""
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
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QFileDialog

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))
from acousticstudio.app import AcousticStudioMain, ResourceMonitorThread
from acousticstudio.force_analysis import json_result
from acousticstudio.force_analysis_ui import ForceAnalysisDialog
from acousticstudio.geometry import CREO_PRESET_LABEL
from acousticstudio.hologram import TRAP_TYPES
from acousticstudio.hologram_ui import HologramDialog


def wait_for(app, condition):
    deadline = time.monotonic() + 30
    while not condition() and time.monotonic() < deadline:
        app.processEvents(); time.sleep(.005)
    app.processEvents()
    assert condition()


def main():
    app = QApplication.instance() or QApplication([])
    output = Path(__file__).resolve().parent
    font_id = QFontDatabase.addApplicationFont('C:/Windows/Fonts/malgun.ttf')
    families = QFontDatabase.applicationFontFamilies(font_id)
    if families:
        app.setFont(QFont(families[0], 10))
    settings_class = QtCore.QSettings
    rows, diagnoses, messages = [], [], []
    with TemporaryDirectory(prefix='studio-t4-ui-') as temporary:
        settings = settings_class(str(Path(temporary) / 'ui.ini'), settings_class.IniFormat)
        with patch.object(QtCore, 'QSettings', return_value=settings), patch.object(ResourceMonitorThread, 'start'):
            window = AcousticStudioMain()
        window.show_silent_msg = lambda *args: messages.append(args)
        try:
            window.show(); app.processEvents()
            window.run_btn.setCheckable(False)
            window.auto_calc_cb.setChecked(False); window.chk_realtime_send.setChecked(False)
            window.compute_mode_cb.setCurrentIndex(1)
            window.hw_controller.send_phases = lambda *_: (_ for _ in ()).throw(AssertionError('No serial writes in T4 verification'))
            window.array_type_cb.setCurrentText(CREO_PRESET_LABEL); window.generate_array()
            for position in [(-10., -3., 5.), (8., 4., -7.)]:
                window.add_control_point()
                point = window.control_points[-1]
                offset = np.array(position) - np.asarray(point['actor'].center)
                point['actor'].SetPosition(*offset)
                point.update(dict(zip('xyz', position)))
            window.add_control_point()
            window.points_list.item(2).setCheckState(Qt.Unchecked)

            def verify_force(dialog):
                dialog.samples.setValue(5)
                dialog.show(); dialog.start_analysis()
                wait_for(app, lambda: dialog._thread is None)
                assert dialog.result is not None and not dialog.result['pressure_calibrated']
                diagnoses.append(dict(centre_mm=dialog.result['centre_mm'], restoring=dialog.result['restoring'],
                                      converged=dialog.result['converged'], gravity_equilibrium_status=dialog.result['gravity_equilibrium_status']))
                dialog.close(); return 0

            def verify_design(dialog):
                dialog.show(); app.processEvents()
                assert len(dialog.snapshot.sources_mm) == 256 and len(dialog.rows) == 2
                dialog.iterations.setValue(50); dialog.tolerance.setValue(0.)
                for trap in TRAP_TYPES:
                    for combo, weight, direction in dialog.rows:
                        combo.setCurrentIndex(TRAP_TYPES.index(trap))
                    dialog.default_type.setCurrentIndex(TRAP_TYPES.index(trap))
                    dialog.start_analysis(); wait_for(app, lambda: not dialog.controller.busy)
                    assert dialog.result is not None and dialog.result['iterations_completed'] == 50
                    dialog.apply_result()
                    assert window.trap_type_cb.currentText() == 'Kinoforms' and not window._field_model_dirty
                    np.testing.assert_array_equal([actor._phase for actor in window.transducer_actors], dialog.result['phases_rad'])
                    rows.append(dict(trap_type=trap, metrics=dialog.result['metrics'], backend=dialog.result['backend']))
                    with patch.object(ForceAnalysisDialog, 'exec', verify_force):
                        dialog.open_force_analysis()
                # Mixed target metadata must survive the same pipeline.
                dialog.rows[0][0].setCurrentIndex(1); dialog.rows[1][0].setCurrentIndex(2)
                dialog.rows[1][1].setValue(.7)
                dialog.start_analysis(); wait_for(app, lambda: not dialog.controller.busy)
                assert dialog.result is not None
                dialog.apply_result()
                path = output / 't4_example_design.json'
                with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(path), 'Kinoforms JSON (*.json)')):
                    dialog.export_result()
                data = json.loads(path.read_text(encoding='utf-8'))
                assert data['targets'][0]['trap_type'] == 'twin' and data['targets'][1]['trap_type'] == 'standing_wave'
                dialog.canvas.draw(); app.processEvents()
                dialog.figure.savefig(output / 't4_constraints.png', dpi=140)
                dialog.grab().save(str(output / 't4_design_dialog.png'))
                dialog.close(); app.processEvents(); return 0

            with patch.object(HologramDialog, 'exec', verify_design):
                window.open_hologram()
            assert len(rows) == 3 and len(diagnoses) == 3 and not messages, messages
            window._last_sim_time = 0.; window.simulate_colors()
            assert window._hologram_controller.busy and window._field_model_dirty
            wait_for(app, lambda: not window._hologram_controller.busy)
            assert not window._field_model_dirty
            window._last_sim_time = 0.; window.simulate_colors()
            wait_for(app, lambda: not window._hologram_controller.busy)
            assert window.phase_engine.last_hologram['cache_hit']
            previous = np.array([actor._phase for actor in window.transducer_actors])
            window.start_hologram_live()
            window.control_points[0]['actor'].AddPosition(1., 0., 0.)
            wait_for(app, lambda: not window._hologram_controller.busy)
            assert window._field_model_dirty
            np.testing.assert_array_equal([actor._phase for actor in window.transducer_actors], previous)
            window.start_hologram_live(); wait_for(app, lambda: not window._hologram_controller.busy)
            assert not window._field_model_dirty
            saved = window.get_state(for_file=True)
            window._last_sim_time = 0.; window.set_state(saved)
            wait_for(app, lambda: not window._field_model_dirty and not window._hologram_controller.busy)
            assert window.get_state(for_file=True) == saved
            assert len(saved['control_points']) == 3 and all('hologram_target' in point for point in saved['control_points'][:2])
            assert not saved['control_points'][2]['active'] and window.points_list.item(2).checkState() == Qt.Unchecked
            assert not window.hw_controller.is_connected() and not messages, messages
            window._last_saved_state = saved
            window.start_hologram_live(); assert window._hologram_controller.busy
            window.close()
            wait_for(app, lambda: not window._hologram_controller.busy and not window.isVisible())
            report = dict(python=sys.executable, qt_main_integration=True, channels=256,
                          mixed_target_apply=True, live_worker=True, latest_input_stale_rejected=True,
                          settings_and_target_save_restore=True, inactive_target_save_restore=True,
                          main_close_during_job=True, warm_cache=True, candidate_force_checks=diagnoses,
                          trap_checks=rows, pressure_calibrated=False, serial_connected=False,
                          qt_dialog_capture=True, qt_viewport_capture=False)
            (output / 't4_ui_result.json').write_text(json.dumps(json_result(report), indent=2), encoding='utf-8')
            print(json.dumps(json_result(report), indent=2))
        finally:
            controller = window._hologram_controller
            if controller is not None:
                controller.cancel(); wait_for(app, lambda: not controller.busy)
            window._last_saved_state = window.get_state(for_file=True)
            window.plotter.close(); window.close(); app.processEvents()


if __name__ == '__main__':
    main()
