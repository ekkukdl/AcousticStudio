"""Device availability, CPU-only Torch selection and actual Kinoforms CUDA routing."""
from dataclasses import replace
import time
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
from PySide6 import QtCore
from PySide6.QtWidgets import QApplication

import acousticstudio.compute_devices as devices_module
from acousticstudio.compute_devices import ComputeDevices, probe_compute_devices
from acousticstudio.field_model import FieldConfig
from acousticstudio.force_analysis import FieldSnapshot
from acousticstudio.hologram import HologramSettings, HologramSolver, TrapTarget
from acousticstudio.hologram_ui import HologramController


def fake_runtime(monkeypatch, *, cuda_build=None, cuda_ready=False, arch='cuda', installed=('torch', 'taichi'), error=None):
    torch = SimpleNamespace(__version__='example', version=SimpleNamespace(cuda=cuda_build),
                            cuda=SimpleNamespace(is_available=lambda: cuda_ready, get_device_name=lambda: 'example GPU'))
    wrapper = SimpleNamespace(_cpp_lib=object(), _has_taichi=True,
                              ti=SimpleNamespace(cfg=SimpleNamespace(arch=SimpleNamespace(name=arch)), cpu=SimpleNamespace(name='x64')))
    def load(name):
        if name == 'torch':
            if error:
                raise error
            return torch
        return wrapper
    monkeypatch.setattr(devices_module, 'find_spec', lambda name: object() if name in installed else None)
    monkeypatch.setattr(devices_module, 'import_module', load)


def test_cpu_only_torch_does_not_override_working_taichi_cuda(monkeypatch):
    fake_runtime(monkeypatch)
    devices = probe_compute_devices()
    assert devices.torch_installed and not devices.cuda_available
    assert 'CPU' in devices.cuda_error and devices.taichi_arch == 'cuda'
    assert devices.taichi_available and devices.preferred_mode() == 2


@pytest.mark.parametrize('kwargs, expected_mode', [
    (dict(cuda_build='12.x', cuda_ready=True), 3),
    (dict(cuda_build='12.x', cuda_ready=False), 2),
    (dict(arch='x64'), 1),
    (dict(installed=()), 1),
    (dict(error=OSError('broken optional runtime')), 2),
])
def test_missing_device_cpu_runtime_and_import_failure_keep_a_usable_mode(monkeypatch, kwargs, expected_mode):
    fake_runtime(monkeypatch, **kwargs)
    devices = probe_compute_devices()
    assert devices.preferred_mode() == expected_mode
    if not devices.cuda_available:
        assert devices.cuda_error
    if not devices.taichi_available:
        assert devices.taichi_error
    if kwargs.get('cuda_ready'):
        assert devices.cuda_device == 'example GPU' and devices.torch_cuda_build == '12.x'
    assert ComputeDevices().preferred_mode() == 0


def test_actual_main_window_selects_available_gpu_and_handles_cancelled_cuda_setup(monkeypatch, tmp_path):
    import acousticstudio.app as app_module
    app = QApplication.instance() or QApplication([])
    available = ComputeDevices(cpp_available=True, taichi_installed=True, taichi_arch='cuda',
                               torch_installed=True, torch_version='example+cpu',
                               cuda_error='CPU 전용 설치본')
    monkeypatch.setattr(app_module, 'probe_compute_devices', lambda: available)
    settings_class = QtCore.QSettings
    settings = settings_class(str(tmp_path / 'compute.ini'), settings_class.IniFormat)
    with patch.object(QtCore, 'QSettings', return_value=settings), patch.object(app_module.ResourceMonitorThread, 'start'):
        window = app_module.AcousticStudioMain()
    try:
        assert window.compute_mode_cb.currentIndex() == 2
        assert 'cuda' in window.compute_mode_cb.itemText(2)
        assert 'CUDA 빌드 없음' in window.compute_mode_cb.itemText(3)
        assert window.has_taichi and not window.has_pytorch
        assert 'CPU 전용' in window.compute_mode_cb.itemData(3, QtCore.Qt.ToolTipRole)
        calls = []
        monkeypatch.setattr(window, '_prompt_install_from_cb', lambda pkg: calls.append(('install', pkg)))
        monkeypatch.setattr(window, 'configure_pytorch_cuda', lambda: calls.append(('configure', 3)))
        monkeypatch.setattr(window, 'simulate_colors', lambda: calls.append(('simulate', window.compute_mode_cb.currentIndex())))
        monkeypatch.setattr(window, 'update_field_slice', lambda: calls.append(('field', window.compute_mode_cb.currentIndex())))
        window.compute_mode_cb.setCurrentIndex(3)
        assert window.compute_mode_cb.currentIndex() == 2
        assert calls == [('configure', 3), ('field', 2)] and 'CPU 전용' in window.statusBar().currentMessage()
        # A library-manager refresh must also recover from losing the device.
        unavailable = replace(available, taichi_error='GPU 장치 없음')
        monkeypatch.setattr(app_module, 'probe_compute_devices', lambda: unavailable)
        window.refresh_compute_devices(); window.update_compute_mode_styles()
        window.on_compute_mode_changed(2)
        assert window.compute_mode_cb.currentIndex() == 1
        assert not window.has_taichi and not window.has_pytorch
    finally:
        window.check_unsaved_changes = lambda: True
        window.close(); app.processEvents()


def test_kinoforms_requested_cuda_fallback_is_visible_and_matches_cpu():
    sources = np.array([[-20., -20., -40.], [20., -20., -40.], [-20., 20., 40.], [20., 20., 40.]])
    normals = np.tile([0., 0., 1.], (4, 1))
    targets = [TrapTarget((-6., 0., 0.)), TrapTarget((6., 1., 2.), 'twin')]
    settings = HologramSettings(iterations=12, phase_tolerance_rad=0.)
    solver = HologramSolver()
    cpu = solver.solve(sources, normals, [.9, .7, 0., 1.], FieldConfig(), targets, settings)
    fallback = solver.solve(sources, normals, [.9, .7, 0., 1.], FieldConfig(), targets, settings,
                            mode_idx=3, has_pytorch=False)
    assert fallback['backend']['requested_mode'] == 3
    assert fallback['backend']['backend'] == 'Numba CPU' and fallback['backend']['fallback_reason']
    np.testing.assert_array_equal(cpu['phases_rad'], fallback['phases_rad'])
    np.testing.assert_array_equal(cpu['residual_history'], fallback['residual_history'])


def test_actual_creo_mixed_multitrap_taichi_cuda_in_qthread_matches_cpu():
    from acousticstudio.geometry import load_creo_tunnel
    devices = probe_compute_devices()
    if not devices.taichi_available or devices.taichi_arch != 'cuda':
        pytest.skip(devices.taichi_error or 'CUDA Taichi runtime not available')
    geometry = load_creo_tunnel()
    sources = np.array([e['position_mm'] for e in geometry['elements']])
    normals = np.array([e['normal'] for e in geometry['elements']])
    gains = np.ones(256); gains[5] = 0.; gains[7] = .7
    targets = [TrapTarget((-10., -3., -12.)), TrapTarget((10., 3., 0.), 'twin'),
               TrapTarget((0., 0., 15.), 'standing_wave', direction=(0., 0., 1.))]
    settings = HologramSettings(iterations=20, phase_tolerance_rad=0.)
    snapshot = FieldSnapshot(sources, normals, np.zeros(256), gains, FieldConfig())
    cpu = HologramSolver().solve(sources, normals, gains, snapshot.field_config, targets, settings)
    app = QApplication.instance() or QApplication([])
    controller = HologramController()
    delivered = []; failed = []
    controller.succeeded.connect(delivered.append); controller.failed.connect(failed.append)
    controller.submit(snapshot, targets, settings, mode=2, taichi=True)
    deadline = time.monotonic() + 20
    while controller.busy and time.monotonic() < deadline:
        app.processEvents(); time.sleep(.005)
    if controller.busy:
        controller.cancel()
        while controller.busy:
            app.processEvents(); time.sleep(.005)
        pytest.fail('Kinoforms worker did not complete within 20 seconds')
    assert not failed and len(delivered) == 1
    gpu = delivered[0]
    assert gpu['backend']['backend'] == 'Taichi cuda' and not gpu['backend']['fallback_reason']
    assert gpu['iterations_completed'] == 20 and gpu['phases_rad'][5] == 0.
    np.testing.assert_allclose(np.exp(1j * gpu['phases_rad']), np.exp(1j * cpu['phases_rad']), atol=1e-9)
    np.testing.assert_allclose(gpu['residual_history'], cpu['residual_history'], atol=1e-10)
    np.testing.assert_allclose(gpu['field_real'] + 1j * gpu['field_imag'],
                               cpu['field_real'] + 1j * cpu['field_imag'], rtol=1e-10, atol=1e-8)
