"""Offscreen full Qt/VTK smoke test; isolates settings and never opens serial."""
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
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))
from acousticstudio.app import AcousticStudioMain, ResourceMonitorThread
from acousticstudio.geometry import CREO_PRESET_LABEL
from acousticstudio.geometry_scene import transducer_inputs, create_geometry_actors


def main():
    output_dir = Path(__file__).resolve().parent
    qapp = QApplication.instance() or QApplication([])
    font_path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'malgun.ttf'
    if font_path.is_file():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            qapp.setFont(QFont(families[0], 10))
    settings_class = QtCore.QSettings
    with TemporaryDirectory(prefix='acousticstudio-qt-') as temporary:
        settings = settings_class(str(Path(temporary) / 'ui.ini'), settings_class.IniFormat)
        with patch.object(QtCore, 'QSettings', return_value=settings), patch.object(ResourceMonitorThread, 'start'):
            window = AcousticStudioMain()
        try:
            window.plotter.render_window.SetOffScreenRendering(1)
            window.show()
            qapp.processEvents()
            window.array_type_cb.setCurrentText(CREO_PRESET_LABEL)
            assert not window.grid_x_spin.isEnabled()
            assert not window.spacing_spin.isVisible()
            assert window.traj_delay.minimum() == 1
            window._hooked_generate_array()
            qapp.processEvents()
            points, weights = transducer_inputs(window.transducer_actors)
            assert points.shape == (256, 3) and len(window.geometry_support_actors) == 10
            np.testing.assert_allclose(points[0], [105., -29., -70.])
            window.plotter.camera_position = [(390, -460, 350), (0, 0, 0), (0, 0, 1)]
            # Qt's offscreen platform does not supply a current OpenGL context
            # on this machine. Verify the identical scene adapter in standalone
            # VTK rather than claiming the Qt viewport image was captured.
            preview = pv.Plotter(off_screen=True, window_size=(1000, 800))
            try:
                create_geometry_actors(window.geometry_arrays[0], preview.renderer)
                preview.set_background('#f5f7fa')
                preview.add_axes()
                preview.camera_position = [(390, -460, 350), (0, 0, 0), (0, 0, 1)]
                preview.show(screenshot=str(output_dir / 'creo_tunnel_preview.png'), auto_close=False)
            finally:
                preview.close()
            window.grab().save(str(output_dir / 'creo_preset_window.png'))
            saved = window.get_state()
            window.clear_view()
            window.set_state(saved)
            assert window.get_state() == saved
            assert not window.hw_controller.is_connected()
            report = dict(python=sys.executable, preset=CREO_PRESET_LABEL, channels=len(points),
                          pcbs=8, rings=2, emission_face0=points[0].tolist(),
                          qt_startup=True, preset_controls=True, standalone_vtk_render=True,
                          qt_viewport_capture=False,
                          save_restore=True, serial_connected=False)
            (output_dir / 'creo_preset_smoke_result.json').write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(report, ensure_ascii=True))
        finally:
            window._last_saved_state = window.get_state(for_file=True)
            window.plotter.close()
            window.close()
            qapp.processEvents()


if __name__ == '__main__':
    main()
