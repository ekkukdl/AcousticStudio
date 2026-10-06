import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['PYVISTA_OFF_SCREEN'] = 'true'
import sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'src'))
from PySide6 import QtCore
from PySide6.QtWidgets import QApplication
out=root/'구상도/scratch/ui_toggle_validation'
out.mkdir(parents=True,exist_ok=True)
settings_class=QtCore.QSettings
# Do not overwrite the user's persistent settings during this verification.
QtCore.QSettings=lambda *args:settings_class(str(out/'test_ui.ini'),settings_class.IniFormat)
from acousticstudio.app import AcousticStudioMain
app=QApplication([])
window=AcousticStudioMain()
try:
    window.show();app.processEvents()
    window.add_control_point()
    window._last_saved_state=window.get_state(for_file=True)
    before=window.get_state(for_file=True)
    viewer_id=id(window.plotter); hardware_id=id(window.hw_controller)
    camera=window.plotter.camera_position
    calls=[]
    window.hw_controller.send_phases=lambda *args:calls.append('send')
    window.ui_appearance.apply(False)
    app.processEvents();window.grab().save(str(out/'ver2.png'))
    for _ in range(3):
        window.classic_ui_action.trigger();app.processEvents()
        assert window.classic_ui_action.isChecked() and not window.modern_ui_action.isChecked()
        assert window.get_state(for_file=True)==before
        window.modern_ui_action.trigger();app.processEvents()
        assert window.modern_ui_action.isChecked() and not window.classic_ui_action.isChecked()
        assert window.get_state(for_file=True)==before
    window.classic_ui_action.trigger();app.processEvents()
    assert window.ui_menu.title() == 'UI'
    assert [action.text() for action in window.ui_menu.actions()] == ['클래식', '모던']
    window.grab().save(str(out/'legacy.png'))
    assert window.plotter.camera_position==camera
    assert id(window.plotter)==viewer_id and id(window.hw_controller)==hardware_id
    assert not calls
    assert window.board_menu.title()=='보드'
    assert window.settings.value('ui/ver2/use_legacy_ui',type=bool)
    print('PASS: actual application toggle, control point/state/camera preserved, board menu retained, no phase send')
finally:
    window.resource_monitor.stop()
    window.check_unsaved_changes=lambda:True
    window.close();window.plotter.close();app.processEvents()
