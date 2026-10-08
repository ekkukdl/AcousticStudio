"""World picking, bounded numerical/serial queues and actual Qt motion flows."""
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
import serial
from PySide6 import QtCore
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QFileDialog

from acousticstudio.app import AcousticStudioMain, ResourceMonitorThread, source_inputs
from acousticstudio.field_model import FieldConfig
from acousticstudio.geometry import CREO_PRESET_LABEL
from acousticstudio.hardware import HardwareController
from acousticstudio.motion import ray_plane_intersection, translated_points
from acousticstudio.motion_ui import NumericalController


def wait_for(predicate, timeout=15):
    app = QApplication.instance()
    deadline = monotonic() + timeout
    while not predicate() and monotonic() < deadline:
        app.processEvents(); sleep(.005)
    app.processEvents()
    assert predicate()


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path):
    settings_type = QtCore.QSettings
    settings = settings_type(str(tmp_path / 'ui.ini'), settings_type.IniFormat)
    with patch.object(QtCore, 'QSettings', return_value=settings), patch.object(ResourceMonitorThread, 'start'):
        value = AcousticStudioMain()
    value.show_silent_msg = lambda *args, **kwargs: None
    value.auto_calc_cb.setChecked(False)
    value.compute_mode_cb.setCurrentIndex(1)
    value.array_type_cb.setCurrentText(CREO_PRESET_LABEL)
    value.generate_array()
    value.select_board_profile('ultraino_simplefpga_256')
    value.add_control_point(); value.add_control_point()
    yield value
    value.check_unsaved_changes = lambda: True
    value.close()
    wait_for(lambda: not any(c.busy for c in value.motion_controllers()) and not value.hw_controller.sender_busy)
    app.processEvents()


@pytest.mark.parametrize('plane,axis', [('xy', 2), ('xz', 1), ('yz', 0)])
def test_world_plane_intersection_and_degenerate_camera(plane, axis):
    origin = np.array([3., 4., 5.]); origin[axis] = -10.
    direction = np.array([.2, .3, .4]); direction[axis] = 2.
    actual = ray_plane_intersection(origin, direction, plane, 6.)
    np.testing.assert_allclose(actual, origin + 8 * direction)
    assert actual[axis] == 6.
    direction[axis] = 0.
    assert ray_plane_intersection(origin, direction, plane, 6.) is None
    direction[axis] = -1.
    assert ray_plane_intersection(origin, direction, plane, 6.) is None
    with pytest.raises(ValueError):
        ray_plane_intersection([np.nan, 0, 0], direction, plane, 0.)


def test_group_translation_preserves_separation():
    points = np.array([[1., 2., 3.], [5., 8., 13.]])
    shifted = translated_points(points, [30., -20., 40.])
    np.testing.assert_allclose(shifted.mean(axis=0), [30., -20., 40.])
    np.testing.assert_allclose(shifted[1] - shifted[0], points[1] - points[0])


def test_numerical_latest_request_copies_input_and_discards_cancelled_result(app):
    started, release = Event(), Event()
    calls, output = [], []
    class Engine:
        last_backend = None
        def calculate_phases(self, active_points, **kwargs):
            value = active_points[0]['x']; calls.append(value)
            if value == 1:
                started.set(); release.wait(5)
            return np.array([value]), None
    controller = NumericalController(); controller.engine = Engine()
    controller.succeeded.connect(output.append)
    controller.submit('phase', dict(active_points=[dict(x=1)]))
    assert started.wait(5)
    controller.submit('phase', dict(active_points=[dict(x=2)]))
    pending = dict(active_points=[dict(x=3)])
    controller.submit('phase', pending)
    pending['active_points'][0]['x'] = 99
    release.set()
    wait_for(lambda: not controller.busy)
    assert calls == [1, 3] and len(output) == 1
    np.testing.assert_array_equal(output[0]['value'][0], [3])
    controller.submit('phase', dict(active_points=[dict(x=4)])); controller.cancel()
    wait_for(lambda: not controller.busy)
    assert len(output) == 1


class FakePort:
    baudrate = 230400
    def __init__(self, block=False, error=None):
        self.started, self.release = Event(), Event()
        if not block: self.release.set()
        self.frames = []; self.error = error; self.closed = False
    def write(self, frame):
        self.started.set(); self.release.wait(5)
        if self.error == 'timeout': raise serial.SerialTimeoutException('timeout')
        self.frames.append(frame)
        return len(frame) - 1 if self.error == 'partial' else len(frame)
    def close(self):
        self.closed = True; self.release.set()


def test_sender_one_inflight_and_latest_pending_and_frame_export_match(app):
    controller = HardwareController(); controller.set_board_profile('ultraino_simplefpga_256')
    port = FakePort(block=True); controller.serial_port = port
    controller.queue_phases(np.zeros(256))
    assert port.started.wait(5)
    controller.queue_phases(np.ones(256))
    controller.queue_phases(np.full(256, 2.))
    assert controller.send_statistics['replaced'] == 1
    assert controller.sender_busy
    port.release.set()
    wait_for(lambda: len(port.frames) == 2 and not controller.sender_busy)
    assert port.frames == [controller.build_phase_frame(np.zeros(256)), controller.build_phase_frame(np.full(256, 2.))]
    controller.disconnect()


@pytest.mark.parametrize('error', ['partial', 'timeout'])
def test_sender_failure_closes_without_retry_or_pending_replay(app, error):
    controller = HardwareController(); controller.set_board_profile('ultraino_simplefpga_256')
    port = FakePort(block=True, error=error); controller.serial_port = port
    failed = []; controller.send_failed.connect(failed.append)
    controller.queue_phases(np.zeros(256)); assert port.started.wait(5)
    controller.queue_phases(np.ones(256)); port.release.set()
    wait_for(lambda: not controller.sender_busy)
    assert not controller.is_connected() and port.closed and len(failed) == 1
    assert controller._pending_frame is None and controller.send_statistics['failed'] == 1
    other = FakePort(); controller.serial_port = other
    QApplication.instance().processEvents()
    assert not other.frames
    controller.disconnect()


def test_sender_disconnect_drops_old_session_completion(app):
    controller = HardwareController(); controller.set_board_profile('ultraino_simplefpga_256')
    first = FakePort(block=True); controller.serial_port = first
    controller.queue_phases(np.zeros(256)); assert first.started.wait(5)
    controller.queue_phases(np.ones(256)); controller.disconnect()
    second = FakePort(); controller.serial_port = second
    wait_for(lambda: not controller.sender_busy)
    assert not second.frames and controller.is_connected()
    controller.disconnect()


def test_selected_and_all_move_updates_model_actors_and_keeps_metadata(window):
    before = np.array([[p['x'], p['y'], p['z']] for p in window.control_points])
    window.control_points[0]['hologram_target'] = dict(trap_type='twin', weight=.7, direction=[1., 0., 0.])
    window.move_scope_cb.setCurrentIndex(0)
    window.selected_actors = [window.control_points[0]['actor']]
    window.move_control_points([10., 20., 30.], final=True)
    np.testing.assert_allclose(window.control_points[0]['actor'].center, [10., 20., 30.], atol=1e-5)
    np.testing.assert_allclose(window.control_points[1]['actor'].center, before[1], atol=1e-5)
    window.move_scope_cb.setCurrentIndex(1)
    delta_before = np.array(window.control_points[1]['actor'].center) - window.control_points[0]['actor'].center
    window.move_control_points([0., 0., 50.], final=True)
    np.testing.assert_allclose(np.mean([p['actor'].center for p in window.control_points], axis=0), [0., 0., 50.], atol=1e-5)
    np.testing.assert_allclose(np.array(window.control_points[1]['actor'].center) - window.control_points[0]['actor'].center, delta_before, atol=1e-5)
    assert window.control_points[0]['hologram_target']['weight'] == .7


def test_slice_mouse_release_applies_final_position(window, monkeypatch):
    window.slice_move_cb.setChecked(True)
    window.selected_actors = [window.control_points[0]['actor']]
    monkeypatch.setattr(window, 'slice_world_point', lambda x, y: np.array([float(x), 0., 20.]))
    filter = window.mouse_filter
    widget = window.plotter.interactor
    for kind, x in ((QEvent.MouseButtonPress, 10), (QEvent.MouseMove, 20), (QEvent.MouseButtonRelease, 30)):
        event = QMouseEvent(kind, QPointF(x, 20), QPointF(x, 20), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        assert filter.eventFilter(widget, event)
    assert not filter.slice_dragging
    np.testing.assert_allclose(window.control_points[0]['actor'].center, [30 * widget.devicePixelRatioF(), 0., 20.], atol=1e-5)


def test_world_display_round_trip_for_rotated_camera(window):
    window.slice_move_plane_cb.setCurrentText('XY'); window.xy_spin.setValue(0.)
    renderer = window.plotter.renderer
    renderer.GetRenderWindow().SetSize(640, 480)
    camera = renderer.GetActiveCamera()
    camera.SetPosition(180., -120., 160.); camera.SetFocalPoint(0., 0., 0.); camera.SetViewUp(0., 0., 1.)
    renderer.ResetCameraClippingRange()
    expected = [7., -4., 0.]
    renderer.SetWorldPoint(*expected, 1.); renderer.WorldToDisplay()
    x, y, _ = renderer.GetDisplayPoint()
    actual = window.slice_world_point(x, y)
    np.testing.assert_allclose(actual, expected, atol=1e-5)


def test_playback_keeps_trajectory_selection_and_final_phase(window):
    window.trap_type_cb.setCurrentText('Kinoforms')
    window.hologram_settings['iterations'] = 8
    window.move_scope_cb.setCurrentIndex(1)
    window.traj_steps.setValue(3); window.chk_optim_traj.setChecked(False)
    window.traj_end_z.setValue(30.); window.generate_trajectory()
    assert window.traj_list.currentRow() == 0
    window.start_traj_playback(1)
    window.traj_timer.stop()
    for _ in range(3):
        window._on_traj_timer_step()
        wait_for(lambda: not window._field_model_dirty)
    wait_for(lambda: not window._field_model_dirty)
    assert window.traj_current_step == 2 and window.traj_list.currentRow() == 0
    assert not window._trajectory_moving
    np.testing.assert_allclose(np.mean([p['actor'].center for p in window.control_points], axis=0), window.traj_points_data[-1], atol=1e-5)
    assert window.phase_engine.last_hologram is not None
    window.start_traj_playback(-1); window.traj_timer.stop()
    window.traj_current_step = 3
    for _ in range(3):
        window._on_traj_timer_step()
        wait_for(lambda: not window._field_model_dirty)
    wait_for(lambda: not window._field_model_dirty)
    assert window.traj_current_step == 0


def test_stop_cancels_worker_and_unapplied_frame_then_close_waits(window, monkeypatch):
    started, release = Event(), Event()
    def delayed(**kwargs):
        started.set(); release.wait(5)
        return np.zeros(256), None
    monkeypatch.setattr(window._phase_controller.engine, 'calculate_phases', delayed)
    window.simulate_colors(); assert started.wait(5)
    window.stop_motion(); release.set()
    wait_for(lambda: not window._phase_controller.busy)
    assert window._field_model_dirty and window.motion_statistics['phase_results'] == 0
    assert window.hw_controller._pending_frame is None


def test_async_trajectory_and_export_match_live_encoder(window, monkeypatch, tmp_path):
    window.traj_steps.setValue(3); window.chk_optim_traj.setChecked(True)
    window.generate_trajectory()
    wait_for(lambda: not window._trajectory_controller.busy)
    assert len(window.trajectories_list) == 1
    path = tmp_path / 'trajectory.bin'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *_: (str(path), 'Board Wire Frames (*.bin)'))
    window.export_selected_trajectory()
    wait_for(lambda: not window._export_controller.busy)
    assert path.exists()
    sources, gains = source_inputs(window)
    from acousticstudio.acoustic_model_ui import field_kwargs
    from acousticstudio.phase_engine import PhaseEngine
    points = window.trajectories_list[0]['points']
    phases = PhaseEngine().calculate_trajectory_phases(sources, points, gains, window.trap_type_cb.currentText(), 1,
                                                      **field_kwargs(window))
    assert path.read_bytes() == b''.join(window.hw_controller.build_phase_frame(p, active=(gains > 0).tolist()) for p in phases)


def test_async_field_draws_on_gui_thread_and_uses_current_plane(window, monkeypatch):
    gui_thread = QtCore.QThread.currentThread()
    original = window.plotter.add_mesh
    field_calls = []
    def draw(*args, **kwargs):
        if str(kwargs.get('name', '')).startswith('field_'):
            assert QtCore.QThread.currentThread() == gui_thread
            field_calls.append(kwargs['name'])
        return original(*args, **kwargs)
    monkeypatch.setattr(window.plotter, 'add_mesh', draw)
    window.xy_check.setChecked(True); window.show_field_btn.setChecked(True)
    window.simulate_colors()
    wait_for(lambda: window.motion_statistics['field_results'] > 0)
    window.xy_spin.setValue(17.)
    wait_for(lambda: '2' in window._cached_field_grids and np.all(window._cached_field_grids['2'][0].points[:, 2] == 17.))
    assert field_calls and not window._field_model_dirty
    window.show_field_btn.setChecked(False); window.update_field_slice()
    assert not window._cached_field_grids['2'][1].GetVisibility()


@pytest.mark.parametrize('move_kind', ['slice', 'coordinates'])
def test_continuous_target_motion_keeps_field_and_finishes_latest_snapshot(window, monkeypatch, move_kind):
    window.xz_check.setChecked(False)
    window.yz_check.setChecked(False)
    window.xy_check.setChecked(True)
    window.show_field_btn.setChecked(True)
    window.simulate_colors()
    wait_for(lambda: window.motion_statistics['field_results'] > 0 and not window._field_controller.busy)
    actor = window._cached_field_grids['2'][1]
    started, release = Event(), Event()
    original = window._field_controller.engine.calculate_field_slice
    snapshots = []
    cancellations = []

    def delayed(points, **kwargs):
        snapshots.append(kwargs['tx_phases'].copy())
        cancellations.append(kwargs['cancelled'])
        if len(snapshots) == 1:
            started.set()
            release.wait(5)
        return original(points, **kwargs)

    monkeypatch.setattr(window._field_controller.engine, 'calculate_field_slice', delayed)
    window.selected_actors = [window.control_points[0]['actor']]
    window.update_ui_from_selection()
    window.auto_calc_cb.setChecked(True)
    window.update_field_slice()
    wait_for(started.is_set)
    count = window.motion_statistics['field_results']
    try:
        for x in (5., 10., 15.):
            if move_kind == 'slice':
                window.move_control_points([x, 0., 20.])
            else:
                window.sel_x.setValue(x)
            assert actor.GetVisibility()
            wait_for(lambda: not window._field_model_dirty)
            assert not cancellations[0].is_set()
        latest = np.array([a._phase for a in window.transducer_actors])
        assert not np.allclose(snapshots[0], latest)
    finally:
        release.set()
    wait_for(lambda: window.motion_statistics['field_results'] >= count + 2 and not window._field_controller.busy)
    np.testing.assert_allclose(snapshots[-1], latest)
    grid, actor = window._cached_field_grids['2']
    parameters = window.motion_field_parameters()
    parameters.pop('planes'); parameters.pop('view_mode')
    real, imag = original(grid.points, **parameters)
    np.testing.assert_allclose(grid.point_data['Pressure'], np.hypot(real, imag))
    assert actor.GetVisibility()


def test_close_waits_for_numeric_and_serial_workers(window, monkeypatch):
    started, release = Event(), Event()
    def delayed(**kwargs):
        started.set(); release.wait(5)
        return np.zeros(256), None
    monkeypatch.setattr(window._phase_controller.engine, 'calculate_phases', delayed)
    port = FakePort(block=True); window.hw_controller.serial_port = port
    window.hw_controller.queue_phases(np.zeros(256)); assert port.started.wait(5)
    window.simulate_colors(); assert started.wait(5)
    checks = []
    window.check_unsaved_changes = lambda: checks.append(True) or True
    window.close()
    assert not checks and window._closing_motion
    release.set(); port.release.set()
    wait_for(lambda: bool(checks))
    assert not any(c.busy for c in window.motion_controllers())
    assert not window.hw_controller.sender_busy and port.closed


def test_export_rejects_changed_profile_before_file_write(window, monkeypatch, tmp_path):
    window.traj_steps.setValue(3); window.chk_optim_traj.setChecked(False); window.generate_trajectory()
    started, release = Event(), Event()
    def delayed(**kwargs):
        started.set(); release.wait(5)
        return np.zeros((3, 256))
    monkeypatch.setattr(window._export_controller.engine, 'calculate_trajectory_phases', delayed)
    path = tmp_path / 'stale.bin'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *_: (str(path), 'Board Wire Frames (*.bin)'))
    window.export_selected_trajectory(); assert started.wait(5)
    window.hw_controller.set_board_profile('sonicsurface_fpga_two_board')
    release.set(); wait_for(lambda: not window._export_controller.busy)
    assert not path.exists() and '취소' in window.statusBar().currentMessage()


def test_motion_settings_restore_and_invalid_state_is_atomic(window):
    window.move_scope_cb.setCurrentIndex(1); window.move_step_spin.setValue(2.5)
    window.slice_move_cb.setChecked(True); window.slice_move_plane_cb.setCurrentText('XY')
    saved = window.get_state()
    window.move_step_spin.setValue(1.); window.set_state(saved)
    assert window.get_state()['motion_settings'] == saved['motion_settings']
    corrupt = dict(saved, motion_settings=dict(saved['motion_settings'], step_mm=float('nan')))
    with pytest.raises(ValueError, match='이동 설정'):
        window.set_state(corrupt)
    assert window.get_state()['motion_settings'] == saved['motion_settings']


def test_field_interval_persists_defaults_old_projects_and_rejects_invalid_state(window):
    window.field_update_interval_spin.setValue(35)
    saved = window.get_state()
    assert saved['field_update_interval_ms'] == 35
    window.field_update_interval_spin.setValue(250)
    window.set_state(saved)
    assert window.field_update_interval_spin.value() == 35
    for invalid in (0, 5001, True, 10.5, '50'):
        with pytest.raises(ValueError, match='갱신 간격'):
            window.set_state(dict(saved, field_update_interval_ms=invalid))
        assert window.field_update_interval_spin.value() == 35
    saved.pop('field_update_interval_ms')
    window.set_state(saved)
    assert window.field_update_interval_spin.value() == 100


def test_field_interval_changes_reschedule_wait_without_duplicate_work(window, monkeypatch):
    import acousticstudio.app as app_module
    clock = [10.]
    submitted = []
    monkeypatch.setattr(app_module.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(window, 'motion_field_parameters', lambda: {})
    monkeypatch.setattr(window._field_controller, 'submit', lambda *args: submitted.append(args))
    window._field_model_dirty = False
    window.show_field_btn.setChecked(True)
    window.update_field_slice()
    assert len(submitted) == 1
    window.field_update_interval_spin.setValue(500)
    assert window._field_due == pytest.approx(10.5)
    clock[0] = 10.05
    window.update_field_slice()
    assert len(submitted) == 1 and window._field_timer.isActive()
    window.field_update_interval_spin.setValue(20)
    assert len(submitted) == 2 and window._field_due == pytest.approx(10.07)
    # Changing the interval while a real worker is active must preserve it.
    monkeypatch.setattr(window._field_controller, '_thread', object())
    try:
        window.field_update_interval_spin.setValue(1)
        assert len(submitted) == 2 and window._field_refresh_pending
    finally:
        monkeypatch.setattr(window._field_controller, '_thread', None)


def test_slow_playback_waits_for_phase_and_write_instead_of_skipping_waypoint(window, monkeypatch):
    window.traj_steps.setValue(3); window.chk_optim_traj.setChecked(False); window.generate_trajectory()
    window.move_scope_cb.setCurrentIndex(1)
    started, release = Event(), Event()
    def delayed(**kwargs):
        started.set(); release.wait(5)
        return np.zeros(256), None
    monkeypatch.setattr(window._phase_controller.engine, 'calculate_phases', delayed)
    port = FakePort(block=True); window.hw_controller.serial_port = port
    window.chk_realtime_send.setEnabled(True); window.chk_realtime_send.setChecked(True)
    window.start_traj_playback(1); window.traj_timer.stop(); window.traj_current_step = -1
    window._last_sim_time = 0.
    window._on_traj_timer_step(); assert started.wait(5)
    assert window.traj_current_step == 0
    window._on_traj_timer_step(); assert window.traj_current_step == 0
    release.set(); wait_for(lambda: not window._field_model_dirty)
    assert port.started.wait(5)
    window._on_traj_timer_step(); assert window.traj_current_step == 0
    port.release.set(); wait_for(lambda: not window.hw_controller.sender_busy)
    window._on_traj_timer_step(); assert window.traj_current_step == 1
    window.stop_motion()
