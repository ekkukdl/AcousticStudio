"""Real queued worker lifecycle, latest request, phase-only export and T3 candidate handoff."""
import json
import time

import numpy as np
import pytest
from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import QApplication, QFileDialog

from acousticstudio.field_model import FieldConfig
from acousticstudio.force_analysis import FieldSnapshot
from acousticstudio.force_analysis_ui import ForceAnalysisDialog
from acousticstudio.hologram import HologramSettings, TrapTarget
from acousticstudio.hologram_ui import HologramController, HologramDialog


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def snapshot():
    return FieldSnapshot(np.array([[-20., -20., -40.], [20., -20., -40.], [-20., 20., 40.], [20., 20., 40.]]),
                         np.tile([0., 0., 1.], (4, 1)), [.2, .9, 2.4, 3.2], [1., .7, .3, .9], FieldConfig())


def wait_idle(app, controller):
    deadline = time.monotonic() + 15
    while controller.busy and time.monotonic() < deadline:
        app.processEvents(); time.sleep(.005)
    app.processEvents()
    assert not controller.busy


def test_real_worker_result_export_apply_candidate_force_and_stale_input(app, monkeypatch, tmp_path):
    dialog = HologramDialog(snapshot(), [TrapTarget((-6., 0., 0.)), TrapTarget((6., 1., 2.))])
    emitted = []
    dialog.applied.connect(emitted.append)
    dialog.show(); dialog.start_analysis(); wait_idle(app, dialog.controller)
    assert dialog.result is not None and dialog.apply.isEnabled() and dialog.export.isEnabled()
    assert len(dialog.figure.axes) == 2 and not dialog.result['pressure_calibrated']
    path = tmp_path / 'design.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *_: (str(path), 'Kinoforms JSON (*.json)'))
    dialog.export_result()
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['settings']['iterations'] == 50 and data['snapshot']['amplitudes'] == [1., .7, .3, .9]
    dialog.apply_result(); assert emitted == [dialog.result]
    candidates = []
    def verify_candidate(candidate):
        candidates.append(candidate)
        np.testing.assert_array_equal(candidate.snapshot.phases_rad, dialog.result['phases_rad'])
        np.testing.assert_array_equal([widget.value() for widget in candidate.centre], [-6., 0., 0.])
        candidate.close(); return 0
    monkeypatch.setattr(ForceAnalysisDialog, 'exec', verify_candidate)
    dialog.open_force_analysis(); assert len(candidates) == 1
    dialog.rows[0][1].setValue(2.)
    assert dialog.result is None and not dialog.apply.isEnabled() and not dialog.export.isEnabled()
    dialog.close()


@pytest.mark.parametrize('action', ['cancel', 'close', 'escape'])
def test_cancel_close_and_escape_stop_worker_without_result_or_apply(app, action):
    dialog = HologramDialog(snapshot(), [TrapTarget((0., 0., 0.))],
                            HologramSettings(iterations=2000, phase_tolerance_rad=0.))
    emitted = []; dialog.applied.connect(emitted.append)
    dialog.show(); dialog.start_analysis()
    if action == 'cancel':
        dialog.cancel_analysis()
    elif action == 'close':
        dialog.close()
    else:
        dialog.reject()
    wait_idle(app, dialog.controller)
    assert dialog.result is None and not dialog.apply.isEnabled() and not emitted
    if action != 'cancel':
        assert not dialog.isVisible()
    dialog.close()


def test_invalid_direction_and_duplicate_constraints_do_not_leave_results(app):
    dialog = HologramDialog(snapshot(), [TrapTarget((0., 0., 0.)), TrapTarget((0., 0., 0.))])
    dialog.show()
    for widget in dialog.rows[0][2]:
        widget.setValue(0.)
    dialog.start_analysis()
    assert not dialog.controller.busy and dialog.result is None and '설계 불가' in dialog.summary.text()
    dialog.rows[0][2][0].setValue(1.)
    dialog.start_analysis(); wait_idle(app, dialog.controller)
    assert '중복' in dialog.summary.text() and not dialog.apply.isEnabled()
    dialog.close()


def test_controller_only_delivers_latest_request_on_gui_thread_and_reuses_cache(app):
    controller = HologramController()
    delivered = []
    def record(result):
        assert QThread.currentThread() == app.thread()
        delivered.append(result)
    controller.succeeded.connect(record)
    settings = HologramSettings(iterations=100, phase_tolerance_rad=0.)
    for x in (1., 5., 9.):
        controller.submit(snapshot(), [TrapTarget((x, 2., 3.))], settings)
    wait_idle(app, controller)
    assert len(delivered) == 1 and delivered[0]['targets'][0]['position_mm'] == (9., 2., 3.)
    controller.submit(snapshot(), [TrapTarget((9., 2., 3.))], settings)
    wait_idle(app, controller)
    assert len(delivered) == 2 and delivered[-1]['cache_hit']


def test_taichi_backend_can_run_inside_the_numerical_qthread(app):
    controller = HologramController()
    delivered = []; controller.succeeded.connect(delivered.append)
    controller.submit(snapshot(), [TrapTarget((1., 2., 3.))], HologramSettings(iterations=5), mode=2, taichi=True)
    wait_idle(app, controller)
    assert delivered and delivered[0]['phases_rad'].shape == (4,)
    if delivered[0]['backend']['fallback_reason']:
        pytest.skip(delivered[0]['backend']['fallback_reason'])
    assert delivered[0]['backend']['backend'].startswith('Taichi')
