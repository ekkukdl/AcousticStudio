"""Visible T6 smoke window. Uses fake serial only; never opens a COM port."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import monotonic

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from acousticstudio.app import AcousticStudioMain
from acousticstudio.geometry import CREO_PRESET_LABEL

root = Path(__file__).parent
app = QApplication([])
window = AcousticStudioMain()
window.setWindowTitle('AcousticStudio — T6 검증 (fake serial)')
window.auto_calc_cb.setChecked(False)
window.array_type_cb.setCurrentText(CREO_PRESET_LABEL)
window.generate_array()
window.select_board_profile('ultraino_simplefpga_256')
window.compute_mode_cb.setCurrentIndex(2)
window.add_control_point(); window.add_control_point()
window.move_scope_cb.setCurrentIndex(1)
window.move_control_points([0., 0., 0.])
window.slice_move_cb.setChecked(True)
window.trap_type_cb.setCurrentText('Kinoforms')
window.hologram_settings['iterations'] = 12
window.control_points[0]['hologram_target'] = dict(trap_type='twin', weight=1., direction=[1., 0., 0.])
window.control_points[1]['hologram_target'] = dict(trap_type='standing_wave', weight=.8, direction=[0., 0., 1.])
window.show_silent_msg = lambda *args, **kwargs: None

class FakeSerial:
    baudrate = 230400
    in_waiting = 0
    def __init__(self): self.frames = []
    def write(self, frame): self.frames.append(frame); return len(frame)
    def close(self): pass

fake = FakeSerial()
window.hw_controller.serial_port = fake
window.chk_realtime_send.setEnabled(True)
window.chk_realtime_send.setChecked(True)
window.show()
window.plotter.view_xz()
window.plotter.reset_camera()
window.auto_calc_cb.setChecked(True)
window.simulate_colors()
QTimer.singleShot(1500, lambda: window.wheel_blocker.scroll_area.ensureWidgetVisible(window.btn_stop_motion))
start = monotonic()
state = dict(rendered=False)
close_marker = root / 't6_close.request'

def tick():
    if not window._field_model_dirty and not state['rendered']:
        window.xz_check.setChecked(True)
        window.show_field_btn.setChecked(True)
        window.update_field_slice()
        state['rendered'] = True
    if (close_marker.exists() or monotonic() - start > 180):
        if close_marker.exists(): close_marker.unlink()
        result = dict(utc=datetime.now(timezone.utc).isoformat(),
                      channels=len(window.transducer_actors),
                      positions_mm=[[p['x'], p['y'], p['z']] for p in window.control_points],
                      backend=window.phase_engine.last_backend, motion_statistics=window.motion_statistics,
                      send_statistics=window.hw_controller.send_statistics,
                      frames_written=len(fake.frames),
                      field_grids=list(getattr(window, '_cached_field_grids', {})))
        (root / 't6_ui_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        window.check_unsaved_changes = lambda: True
        window.close()

timer = QTimer()
timer.timeout.connect(tick); timer.start(100)
app.exec()
