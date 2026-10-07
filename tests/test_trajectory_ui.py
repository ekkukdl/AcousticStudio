"""Exercise actual UI handlers with offscreen labels and no 3D scene/board."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel

from acousticstudio.app import AcousticStudioMain
from acousticstudio.dependencies import PACKAGE_INFO
from acousticstudio.hardware import HardwareController
from acousticstudio.phase_engine import PhaseEngine


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


def value_widget(value):
    return SimpleNamespace(value=lambda: value)


@pytest.mark.parametrize('metrics', [
    {'valid': False, 'avg_stability': None, 'min_stability': None, 'guide_msg': '계산 실패'},
    {'status': 'Fallback (old solver error)', 'avg_stability': 75., 'min_stability': 60.},
    {'status': 'Unavailable', 'avg_stability': 75., 'min_stability': 60.},
    {'avg_stability': float('nan'), 'min_stability': 60.},
    {},
])
def test_unavailable_or_saved_legacy_fallback_has_no_percentage(qt_app, metrics):
    window = SimpleNamespace(lbl_diag_title=QLabel(), lbl_diag_desc=QLabel(), trajectories_list=[{}])
    AcousticStudioMain.update_trajectory_diagnosis_ui(window, metrics)
    assert '진단 불가' in window.lbl_diag_title.text()
    assert '%' not in window.lbl_diag_title.text()


def test_success_diagnosis_is_explicitly_relative(qt_app):
    window = SimpleNamespace(lbl_diag_title=QLabel(), lbl_diag_desc=QLabel(), trajectories_list=[{}])
    AcousticStudioMain.update_trajectory_diagnosis_ui(
        window, {'valid': True, 'avg_stability': 80., 'min_stability': 50.},
    )
    assert window.lbl_diag_title.text() == '상대 트랩 강도: 평균 80.0% / 최저 50.0%'
    assert '별도 검증' in window.lbl_diag_desc.text()


def test_failed_generation_stores_unavailable_name_and_status(qt_app, monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, 'levitate', None)
    messages = []
    loaded = []
    window = SimpleNamespace(
        traj_type_cb=SimpleNamespace(currentIndex=lambda: 0, currentText=lambda: '선형'),
        traj_param_spin=value_widget(10.), traj_steps=value_widget(4), traj_delay=value_widget(50.),
        chk_optim_traj=SimpleNamespace(isChecked=lambda: True),
        transducer_actors=[SimpleNamespace(center=[-20., 0., -40.], _amplitude=0.5),
                           SimpleNamespace(center=[20., 0., 40.], _amplitude=1.)],
        trap_type_cb=SimpleNamespace(currentText=lambda: 'Twin Trap'),
        compute_mode_cb=SimpleNamespace(currentIndex=lambda: 0), phase_engine=PhaseEngine(),
        statusBar=lambda: SimpleNamespace(showMessage=lambda text, duration: messages.append(text)),
        traj_list=SimpleNamespace(addItem=lambda text: None, setCurrentRow=lambda row: None),
        load_selected_trajectory=loaded.append,
    )
    for prefix in ('start', 'end'):
        for axis in ('x', 'y', 'z'):
            setattr(window, f'traj_{prefix}_{axis}', value_widget(1. if prefix == 'end' else 0.))
    AcousticStudioMain.generate_trajectory(window)
    trajectory = window.trajectories_list[0]
    assert trajectory['name'].endswith('[진단 불가]') and '%' not in trajectory['name']
    assert trajectory['metrics']['avg_stability'] is None
    assert messages and '진단 불가' in messages[-1]
    assert loaded == [0]


def export_window():
    points = np.array([[1., 2., 3.], [3., -1., 2.]])
    actors = [SimpleNamespace(center=[-20., 0., -40.], _amplitude=0.2),
              SimpleNamespace(center=[20., 0., 40.], _amplitude=0.7),
              SimpleNamespace(center=[0., 20., -40.], _amplitude=1.)]
    messages = []
    window = SimpleNamespace(
        trajectories_list=[{'name': 'test', 'points': points, 'delays': [50., 60.]}],
        traj_list=SimpleNamespace(currentRow=lambda: 0),
        transducer_actors=actors, phase_engine=PhaseEngine(), hw_controller=HardwareController(),
        traj_delay=value_widget(50.), trap_type_cb=SimpleNamespace(currentText=lambda: 'Twin Trap'),
        compute_mode_cb=SimpleNamespace(currentIndex=lambda: 1),
        show_silent_msg=lambda title, message: messages.append((title, message)),
    )
    return window, messages


@pytest.mark.parametrize('file_filter,suffix', [
    ('C/C++ Header (*.h)', '.h'), ('CSV Data (*.csv)', '.csv'),
    ('Board Wire Frames (*.bin)', '.bin'), ('Legacy FA File (*.legacy.bin)', '.legacy.bin'),
])
def test_export_handler_uses_selected_mode_weights_and_handles_no_dll(qt_app, monkeypatch, tmp_path, file_filter, suffix):
    from acousticstudio import sonic_wrapper
    monkeypatch.setattr(sonic_wrapper, '_cpp_lib', None)
    window, messages = export_window()
    path = tmp_path / 'export'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), file_filter))
    original = window.phase_engine.calculate_trajectory_phases
    calls = []

    def record(centers, points, amplitudes, algorithm, **kwargs):
        calls.append((centers.shape, amplitudes.copy(), kwargs['mode_idx']))
        return original(centers, points, amplitudes, algorithm, **kwargs)
    monkeypatch.setattr(window.phase_engine, 'calculate_trajectory_phases', record)
    AcousticStudioMain.export_selected_trajectory(window)
    saved = Path(str(path) + suffix)
    assert saved.is_file() and saved.stat().st_size > 0
    assert calls[0][0] == (3, 3) and calls[0][2] == 1
    np.testing.assert_array_equal(calls[0][1], [0.2, 0.7, 1.])
    assert messages[-1][0] == '내보내기 완료'
    if suffix == '.bin':
        trajectory = window.trajectories_list[0]
        phases = original(np.array([a.center for a in window.transducer_actors]),
                          trajectory['points'], np.array([0.2, 0.7, 1.]), 'Twin Trap', 0)
        assert saved.read_bytes() == b''.join(window.hw_controller.build_phase_frame(row) for row in phases)


def test_export_handler_reports_calculation_failure_without_file(qt_app, monkeypatch, tmp_path):
    window, messages = export_window()
    window.transducer_actors = []
    path = tmp_path / 'invalid.bin'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), 'Board Wire Frames (*.bin)'))
    AcousticStudioMain.export_selected_trajectory(window)
    assert messages[-1][0] == '내보내기 오류'
    assert not path.exists()


def test_legacy_export_rejects_zero_gain_instead_of_emitting_an_active_phase(qt_app, monkeypatch, tmp_path):
    window, messages = export_window()
    window.transducer_actors[0]._amplitude = 0.
    path = tmp_path / 'unsupported.bin'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), 'Board Wire Frames (*.bin)'))
    AcousticStudioMain.export_selected_trajectory(window)
    assert messages[-1][0] == '내보내기 오류' and 'OFF' in messages[-1][1]
    assert not path.exists()


@pytest.mark.parametrize('model_index', [0, 1, 2])
def test_export_frames_use_current_shared_model_and_match_live_phases(qt_app, monkeypatch, tmp_path, model_index):
    from acousticstudio.acoustic_model_ui import AcousticModelControls, field_kwargs
    window, messages = export_window()
    window.acoustic_model_controls = AcousticModelControls(lambda *_: None)
    window.acoustic_model_controls.model.setCurrentIndex(model_index)
    window.acoustic_model_controls.radius.setValue(4.5)
    path = tmp_path / 'shared.bin'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), 'Board Wire Frames (*.bin)'))
    AcousticStudioMain.export_selected_trajectory(window)
    assert messages[-1][0] == '내보내기 완료'
    centres = np.array([actor.center for actor in window.transducer_actors])
    amplitudes = np.array([actor._amplitude for actor in window.transducer_actors])
    frames = []
    for point in window.trajectories_list[0]['points']:
        phases, _ = window.phase_engine.calculate_phases(
            centres, [dict(zip(('x', 'y', 'z'), point))], amplitudes, 'Twin Trap', 1, **field_kwargs(window))
        frames.append(window.hw_controller.build_phase_frame(phases))
    assert path.read_bytes() == b''.join(frames)


def test_unknown_directed_aperture_prevents_export_file(qt_app, monkeypatch, tmp_path):
    from acousticstudio.acoustic_model_ui import AcousticModelControls
    window, messages = export_window()
    window.acoustic_model_controls = AcousticModelControls(lambda *_: None)
    window.acoustic_model_controls.model.setCurrentIndex(1)
    path = tmp_path / 'unknown.bin'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), 'Board Wire Frames (*.bin)'))
    AcousticStudioMain.export_selected_trajectory(window)
    assert not path.exists()
    assert messages[-1][0] == '내보내기 오류'
    assert '미확정' in messages[-1][1]


def test_library_manager_can_repair_newly_declared_required_dependencies(qt_app, monkeypatch):
    from acousticstudio import installer_ui
    missing = {'pyvistaqt', 'levitate', 'numba'}
    monkeypatch.setattr(installer_ui, 'installed_package_names',
                        lambda: {name.lower() for name in PACKAGE_INFO if name not in missing})
    manager = installer_ui.LibraryManagerDialog()
    assert set(manager.missing_selected) == missing
    assert all(manager.checkbox_vars[name].isChecked() for name in missing)
    manager.close()
