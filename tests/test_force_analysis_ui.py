"""Real Qt worker lifecycle, malformed inputs, export and snapshot immutability."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import time

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog

from acousticstudio.field_model import FieldConfig
from acousticstudio.force_analysis import AnalysisSettings, FieldSnapshot
from acousticstudio.force_analysis_ui import ForceAnalysisDialog


@pytest.fixture
def dialog():
    app = QApplication.instance() or QApplication([])
    frozen = FieldSnapshot(np.array([[-20., -20., -40.], [20., -20., -40.],
                                     [-20., 20., 40.], [20., 20., 40.]]),
                           np.array([[0., 0., 1.], [0., 0., 1.], [0., 0., -1.], [0., 0., -1.]]),
                           np.array([.2, .9, 2.4, 3.2]), np.array([1., .7, .3, .9]), FieldConfig())
    instance = ForceAnalysisDialog(frozen, [0., 0., 0.], AnalysisSettings(samples=5))
    instance._test_app = app
    yield instance
    if instance._thread is not None:
        instance.cancel_analysis()
        wait_for_completion(instance)
    instance.close()
    app.processEvents()


def wait_for_completion(dialog, timeout=10.):
    deadline = time.monotonic() + timeout
    while dialog._thread is not None and time.monotonic() < deadline:
        dialog._test_app.processEvents()
        time.sleep(.005)
    assert dialog._thread is None, 'Numerical worker did not stop.'
    dialog._test_app.processEvents()


def test_worker_finishes_on_gui_thread_preserves_drive_and_exports_metadata(dialog, monkeypatch, tmp_path):
    submitted = []
    dialog.settings_submitted.connect(submitted.append)
    phases = dialog.snapshot.phases_rad.copy()
    dialog.start_analysis()
    assert not dialog.calculate.isEnabled() and dialog.cancel.isEnabled()
    wait_for_completion(dialog)
    assert dialog.result and dialog.progress.value() == 100
    assert dialog.calculate.isEnabled() and not dialog.cancel.isEnabled()
    assert dialog.matrix.item(0, 0) is not None
    assert '평형 판정 보류' in dialog.summary.text() and '예시' in dialog.summary.text()
    assert submitted[0]['particle']['provenance'] == 'example'
    np.testing.assert_array_equal(dialog.snapshot.phases_rad, phases)
    path = tmp_path / 'analysis.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), 'Analysis JSON (*.json)'))
    dialog.export_result()
    saved = json.loads(path.read_text(encoding='utf-8'))
    assert saved['pressure_calibrated'] is False
    assert saved['force_units'].startswith('N_star')
    assert saved['snapshot']['phases_rad'] == phases.tolist()
    for kind in range(4):
        dialog.plot_kind.setCurrentIndex(kind)
        assert len(dialog.figure.axes) == 3
    dialog.radius.setValue(.3)
    assert dialog.result is None and not dialog.export.isEnabled()
    assert not dialog.figure.axes and dialog.matrix.item(0, 0) is None


@pytest.mark.parametrize('close_mode', ['cancel', 'titlebar', 'escape'])
def test_cancel_and_close_discard_in_flight_results_without_destroying_running_qthread(dialog, close_mode):
    dialog.show()
    dialog.samples.setValue(201)
    dialog.start_analysis()
    if close_mode == 'cancel':
        dialog.cancel_analysis()
    elif close_mode == 'titlebar':
        dialog.close()
    else:
        dialog.reject()
    wait_for_completion(dialog)
    assert dialog.result is None
    assert not dialog.export.isEnabled()
    if close_mode != 'cancel':
        assert not dialog.isVisible()


def test_bad_compressibility_has_no_worker_and_numerical_failure_has_no_stale_result(dialog):
    dialog.compressibility_mode.setCurrentIndex(1)
    dialog.compressibility.setText('NaN')
    dialog.start_analysis()
    assert dialog._thread is None and dialog.result is None
    assert '진단 불가' in dialog.summary.text()
    dialog.compressibility_mode.setCurrentIndex(0)
    # Evaluation at a source intersects the derivative exclusion region.
    for widget, value in zip(dialog.centre, dialog.snapshot.sources_mm[0]):
        widget.setValue(value)
    dialog.start_analysis()
    wait_for_completion(dialog)
    assert dialog.result is None and not dialog.export.isEnabled()
    assert '근접점' in dialog.summary.text()
    assert dialog.calculate.isEnabled()


def test_direct_compressibility_and_confirmed_source_are_explicit_in_saved_settings(dialog):
    dialog.compressibility_mode.setCurrentIndex(1)
    dialog.compressibility.setText('8.0e-9')
    dialog.provenance.setCurrentIndex(1)
    dialog.source.setText('Synthetic measurement fixture')
    settings = dialog._settings()
    assert settings.particle.compressibility == 8e-9
    assert settings.particle.provenance == 'provided'
    assert settings.particle.source == 'Synthetic measurement fixture'
    assert not dialog.speed.isEnabled()
