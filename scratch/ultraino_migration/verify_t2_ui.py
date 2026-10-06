"""Exercise the real Qt model controls, phase handlers, slice and persistence."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import pyvista as pv
from PySide6 import QtCore
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QTabWidget

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))
from acousticstudio.app import AcousticStudioMain, ResourceMonitorThread
from acousticstudio.geometry import CREO_PRESET_LABEL
from acousticstudio.geometry_scene import transducer_inputs, create_geometry_actors
from acousticstudio.acoustic_model_ui import field_kwargs


def main():
    qapp = QApplication.instance() or QApplication([])
    font_id = QFontDatabase.addApplicationFont('C:/Windows/Fonts/malgun.ttf')
    families = QFontDatabase.applicationFontFamilies(font_id)
    if families:
        qapp.setFont(QFont(families[0], 10))
    settings_class = QtCore.QSettings
    with TemporaryDirectory(prefix='acousticstudio-t2-') as temporary:
        settings = settings_class(str(Path(temporary) / 'ui.ini'), settings_class.IniFormat)
        with patch.object(QtCore, 'QSettings', return_value=settings), patch.object(ResourceMonitorThread, 'start'):
            window = AcousticStudioMain()
        try:
            window.show()
            qapp.processEvents()
            window.compute_mode_cb.setCurrentIndex(1)
            window.trap_type_cb.setCurrentText('Focus')
            window.array_type_cb.setCurrentText(CREO_PRESET_LABEL)
            window.generate_array()
            window.add_control_point()
            window.chk_realtime_send.setChecked(False)
            window.hw_controller.send_phases = lambda *_: (_ for _ in ()).throw(AssertionError('No serial I/O in verification'))
            window.run_btn.setCheckable(False)
            controls = window.acoustic_model_controls
            assert controls.config().aperture_radius_mm is None
            controls.model.setCurrentIndex(1)
            window._last_sim_time = 0.
            window.simulate_colors()
            assert window._field_model_dirty and '미확정' in controls.backend.text()
            controls.radius.setValue(4.5)  # synthetic test value, not measured hardware data
            outputs = {}
            for index in range(3):
                controls.model.setCurrentIndex(index)
                window._last_sim_time = 0.
                window.simulate_colors()
                assert not window._field_model_dirty
                assert window.phase_engine.last_backend['backend'] == 'C++'
                phases = np.array([a._phase for a in window.transducer_actors])
                centres, amplitudes = transducer_inputs(window.transducer_actors)
                target = np.array([[0., 0., 50.]])
                real, imag = window.phase_engine.calculate_field_slice(
                    target, centres, phases, amplitudes, 1, **field_kwargs(window))
                assert np.isfinite(real).all() and np.isfinite(imag).all()
                outputs[controls.config().model] = dict(target_real=float(real[0]), target_imag=float(imag[0]))
            window.xy_check.setChecked(True)
            window.xy_spin.setValue(50)
            window.show_field_btn.setChecked(True)
            window.update_field_slice()
            grid, actor = window._cached_field_grids['2']
            assert grid.n_points == 14400 and actor.GetVisibility()
            assert np.isfinite(grid.active_scalars).all()
            saved = window.get_state(for_file=True)
            window.clear_view()
            window.set_state(saved)
            qapp.processEvents()
            assert window.get_state(for_file=True) == saved
            for tab in window.findChildren(QTabWidget):
                if tab.count() == 3 and tab.tabText(1) == '\uC74C\uC7A5':
                    tab.setCurrentIndex(1)
            qapp.processEvents()
            controls.grab().save(str(Path(__file__).with_name('t2_model_controls.png')))
            preview = pv.Plotter(off_screen=True, window_size=(1000, 800))
            try:
                create_geometry_actors(window.geometry_arrays[0], preview.renderer)
                preview.add_mesh(grid.copy(), scalars=grid.active_scalars_name, cmap='jet',
                                 clim=[0., float(np.percentile(grid.active_scalars, 99.5))],
                                 show_scalar_bar=True, scalar_bar_args={
                                     'title': 'Relative pressure (uncalibrated)', 'position_x': .18,
                                     'position_y': .03, 'width': .64, 'height': .09,
                                     'title_font_size': 16, 'label_font_size': 14, 'n_labels': 4, 'fmt': '%.2g'})
                preview.set_background('#f5f7fa')
                preview.camera_position = [(390, -460, 350), (0, 0, 0), (0, 0, 1)]
                preview.show(screenshot=str(Path(__file__).with_name('t2_field_xy.png')), auto_close=False)
            finally:
                preview.close()
            report = dict(python=sys.executable, channels=256, aperture_unknown_guard=True,
                          synthetic_test_radius_mm=4.5, models=outputs, native_backend=True,
                          pressure_slice_points=14400, save_restore=True,
                          qt_controls_capture=True, qt_viewport_capture=False,
                          standalone_vtk_slice_render=True, serial_connected=False)
            Path(__file__).with_name('t2_ui_result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report, indent=2))
        finally:
            window._last_saved_state = window.get_state(for_file=True)
            window.plotter.close()
            window.close()
            qapp.processEvents()


if __name__ == '__main__':
    main()
