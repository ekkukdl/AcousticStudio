"""Optional CUDA selection, fake installs and real child IPC; no downloads or board IO."""
from dataclasses import replace
import io
import json
from pathlib import Path
import struct
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
from PySide6 import QtCore
from PySide6.QtWidgets import QApplication, QDialog

from acousticstudio import cuda_runtime, installer_ui
from acousticstudio.compute_devices import ComputeDevices
from acousticstudio.cuda_protocol import MAX_MESSAGE_BYTES, read_message, write_message
from acousticstudio.field_backends import reduce_field
from acousticstudio.field_model import FieldConfig
from acousticstudio.force_analysis import FieldSnapshot
from acousticstudio.hologram import HologramSettings, HologramSolver, TrapTarget
from acousticstudio.hologram_ui import HologramController

# An explicitly fake torch API exercises a REAL fresh interpreter and pipe transport.
# It computes with NumPy; these tests do not claim NVIDIA CUDA execution.
FAKE_TORCH = '''
import numpy as np
__version__ = 'fake+cu130'
complex128 = np.complex128
class version:
    cuda = '13.0'
class cuda:
    @staticmethod
    def is_available(): return True
    @staticmethod
    def get_device_name(*args): return 'fake GPU for IPC tests'
    @staticmethod
    def synchronize(): pass
class Tensor:
    def __init__(self, values): self.values = np.asarray(values, dtype=np.complex128)
    def __matmul__(self, other): return Tensor(self.values @ other.values)
    def cpu(self): return self
    def numpy(self): return self.values
def as_tensor(values, dtype=None, device=None):
    assert device == 'cuda'
    return Tensor(values)
def ones(shape, dtype=None, device=None):
    assert device == 'cuda'
    return Tensor(np.ones(shape, dtype=np.complex128))
'''


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def runtime_dir(monkeypatch, tmp_path):
    cuda_runtime.close_runtime()
    root = tmp_path / 'cuda'
    monkeypatch.setattr(cuda_runtime, 'runtime_root', lambda: root)
    yield root
    cuda_runtime.close_runtime()


def fake_packages(path, code=FAKE_TORCH):
    directory = path / 'torch'
    directory.mkdir(parents=True)
    (directory / '__init__.py').write_text(code, encoding='utf-8')


def activate_fake(root):
    target = root / 'install-fake'
    fake_packages(target)
    (root / 'active.json').write_text(json.dumps(dict(directory=target.name)), encoding='utf-8')
    return target


def test_real_child_is_reused_binary_complex_channels_and_cpu_fallback(runtime_dir, monkeypatch):
    target = activate_fake(runtime_dir)
    client = cuda_runtime.CudaClient(target)
    try:
        assert client.info()['cuda_device'].startswith('fake GPU')
        first_pid = client._process.pid
        matrix = np.array([[1 + 2j, 3 - 4j, 9j], [-1j, 2., 3j]])
        weights = np.array([.3 + .2j, .7j, 0.])
        for _ in range(2):
            np.testing.assert_allclose(client.request('matvec', matrix, weights), matrix @ weights)
            assert client._process.pid == first_pid
        monkeypatch.setattr(cuda_runtime, '_client', client)
        # Force the existing CPU host branch, regardless of the test machine's Torch build.
        import torch
        monkeypatch.setattr(torch.cuda, 'is_available', lambda: False)
        actual, status = reduce_field(matrix, weights, 3, has_pytorch=True)
        np.testing.assert_allclose(actual, matrix @ weights)
        assert status['backend'] == 'PyTorch CUDA' and status['fallback_reason'] is None
        monkeypatch.setattr(cuda_runtime, 'run_remote', lambda *args: (_ for _ in ()).throw(RuntimeError('worker failed')))
        actual, status = reduce_field(matrix, weights, 3, has_pytorch=True)
        assert status['backend'] == 'Numba CPU' and status['fallback_reason'] == 'worker failed'
        np.testing.assert_allclose(actual, matrix @ weights)
    finally:
        client.close()
    assert client._process is None


def test_probe_timeout_and_worker_exit_close_child_without_hanging(runtime_dir):
    target = runtime_dir / 'install-timeout'
    fake_packages(target, "import time; time.sleep(5)\n" + FAKE_TORCH)
    client = cuda_runtime.CudaClient(target, timeout=.1)
    with pytest.raises(TimeoutError):
        client.info()
    assert client._process is None
    target = runtime_dir / 'install-exit'
    fake_packages(target, 'import os; os._exit(9)\n')
    client = cuda_runtime.CudaClient(target, timeout=5)
    with pytest.raises(RuntimeError, match='통신 실패'):
        client.info()
    assert client._process is None


def test_protocol_bounds_and_manifest_cannot_escape_runtime_root(runtime_dir):
    wire = io.BytesIO()
    write_message(wire, dict(values=np.array([1 + 2j])))
    wire.seek(0)
    np.testing.assert_array_equal(read_message(wire)['values'], [1 + 2j])
    with pytest.raises(ValueError):
        read_message(io.BytesIO(struct.pack('!I', MAX_MESSAGE_BYTES + 1)))
    with pytest.raises(EOFError):
        read_message(io.BytesIO(struct.pack('!I', 9) + b'123'))
    runtime_dir.mkdir()
    (runtime_dir / 'active.json').write_text('{"directory":"../install-outside"}', encoding='utf-8')
    with pytest.raises(ValueError):
        cuda_runtime.installed_runtime_path()


@pytest.mark.parametrize('pip_code', [0, 4])
def test_targeted_install_activates_only_after_fresh_probe_and_preserves_host(runtime_dir, monkeypatch, pip_code):
    original_popen = cuda_runtime.subprocess.Popen
    commands = []
    monkeypatch.setattr(cuda_runtime.shutil, 'which', lambda _: 'fake-nvidia-smi')
    monkeypatch.setattr(cuda_runtime.subprocess, 'run', lambda *args, **kwargs:
                        SimpleNamespace(returncode=0, stdout='fake NVIDIA, 617.42\n'))
    def popen(command, **kwargs):
        if '-m' in command and 'pip' in command:
            commands.append(command)
            target = Path(command[command.index('--target') + 1])
            fake_packages(target)
            return SimpleNamespace(stdout=io.StringIO('fake install log\n'), wait=lambda: pip_code)
        return original_popen(command, **kwargs)
    monkeypatch.setattr(cuda_runtime.subprocess, 'Popen', popen)
    logs = []
    if pip_code:
        with pytest.raises(RuntimeError, match='종료 코드 4'):
            cuda_runtime.install_cuda_runtime(logs.append, Event(), lambda _: None)
        assert not (runtime_dir / 'active.json').exists()
        assert not list(runtime_dir.glob('install-*'))
    else:
        cuda_runtime.install_cuda_runtime(logs.append, Event(), lambda _: None)
        info = cuda_runtime.runtime_info()
        assert info['cuda_available'] and info['cuda_device'].startswith('fake GPU')
    assert len(commands) == 1 and '--target' in commands[0]
    assert commands[0][-1] == cuda_runtime.TORCH_CUDA_PACKAGE
    assert commands[0][commands[0].index('--index-url') + 1] == cuda_runtime.CUDA_INDEX_URL
    assert '--force-reinstall' not in commands[0]


def test_installer_checks_exit_status_and_escape_waits_for_worker(app, monkeypatch):
    monkeypatch.setattr(installer_ui.subprocess, 'Popen', lambda *args, **kwargs:
                        SimpleNamespace(stdout=io.StringIO('failure\n'), wait=lambda: 3))
    worker = installer_ui.InstallWorker(['fake'])
    worker.run()
    assert not worker.success and '종료 코드 3' in worker.error
    def waiting(log, cancelled, process_changed):
        while not cancelled.wait(.005):
            pass
        raise RuntimeError('설치를 취소했습니다.')
    monkeypatch.setattr(installer_ui, 'install_cuda_runtime', waiting)
    dialog = installer_ui.LiveInstallerDialog(['torch'], cuda=True)
    QtCore.QTimer.singleShot(30, dialog.reject)
    assert dialog.exec() == QDialog.Rejected
    assert not dialog.worker.isRunning() and not dialog.worker.success
    assert dialog.worker.cancelled.is_set()


def test_mode_selection_installs_then_switches_and_cpu_selection_needs_no_install(app, monkeypatch, tmp_path):
    import acousticstudio.app as app_module
    cpu = ComputeDevices(cpp_available=True, taichi_installed=True, taichi_arch='cuda',
                         torch_installed=True, torch_version='example+cpu', cuda_error='CPU 전용')
    active = [cpu]
    monkeypatch.setattr(app_module, 'probe_compute_devices', lambda: active[0])
    settings_class = QtCore.QSettings
    settings = settings_class(str(tmp_path / 'mode.ini'), settings_class.IniFormat)
    with patch.object(QtCore, 'QSettings', return_value=settings), patch.object(app_module.ResourceMonitorThread, 'start'):
        window = app_module.AcousticStudioMain()
    calls = []
    class Installer:
        Accepted = QDialog.Accepted
        def __init__(self, packages, parent=None, cuda=False):
            assert cuda and packages == ['torch']
            assert parent._compute_installing and parent._field_model_dirty
            self.worker = SimpleNamespace(success=True, error='')
            calls.append('prepare')
        def exec(self):
            active[0] = replace(cpu, cuda_available=True, cuda_device='fake GPU', torch_cuda_build='13.0', cuda_error=None)
            return QDialog.Accepted
    monkeypatch.setattr(installer_ui, 'LiveInstallerDialog', Installer)
    monkeypatch.setattr(window, 'simulate_colors', lambda: calls.append('calculate'))
    monkeypatch.setattr(window, 'update_field_slice', lambda: calls.append('field'))
    try:
        window.compute_mode_cb.setCurrentIndex(3)
        assert window.compute_mode_cb.currentIndex() == 3 and window.has_pytorch
        assert not window._compute_installing and calls.count('prepare') == 1
        window.compute_mode_cb.setCurrentIndex(0)
        assert window.compute_mode_cb.currentIndex() == 0 and calls.count('prepare') == 1
        window.compute_mode_cb.setCurrentIndex(3)
        assert calls.count('prepare') == 1  # Already prepared: no new install.
        window.compute_mode_cb.setCurrentIndex(0)
        active[0] = cpu
        window.refresh_compute_devices(); window.update_compute_mode_styles()
        class CancelledInstaller(Installer):
            def exec(self):
                # Even cancellation just after a successful install preserves the user's prior mode.
                super().exec()
                return QDialog.Rejected
        monkeypatch.setattr(installer_ui, 'LiveInstallerDialog', CancelledInstaller)
        window.compute_mode_cb.setCurrentIndex(3)
        assert window.compute_mode_cb.currentIndex() == 0
        assert '취소' in window.statusBar().currentMessage() and not window._compute_installing
    finally:
        window.check_unsaved_changes = lambda: True
        window.close(); app.processEvents()


@pytest.mark.parametrize('accepted', [True, False])
def test_library_manager_offers_cuda_for_cpu_torch_and_selects_it_after_success(app, monkeypatch, accepted):
    cpu = ComputeDevices(torch_installed=True, torch_version='example+cpu', cuda_error='CPU 전용')
    monkeypatch.setattr(installer_ui, 'probe_compute_devices', lambda: cpu)
    monkeypatch.setattr(installer_ui, 'installed_package_names', lambda: set(name.lower() for name in installer_ui.PACKAGE_INFO))
    calls = []
    class Installer:
        def __init__(self, packages, parent=None, cuda=False):
            calls.append((packages, cuda))
        def exec(self):
            return QDialog.Accepted if accepted else QDialog.Rejected
    monkeypatch.setattr(installer_ui, 'LiveInstallerDialog', Installer)
    manager = installer_ui.LibraryManagerDialog()
    assert 'torch' in manager.checkbox_vars and not manager.checkbox_vars['torch'].isChecked()
    manager.checkbox_vars['torch'].setChecked(True)
    manager.on_install()
    assert manager.requested_compute_mode == (3 if accepted else None) and calls == [(['torch'], True)]
    assert manager.result() == (QDialog.Accepted if accepted else QDialog.Rejected)


def test_kinoforms_qthread_uses_fresh_process_and_matches_fixed_gain_cpu(app, runtime_dir, monkeypatch):
    activate_fake(runtime_dir)
    import torch
    monkeypatch.setattr(torch.cuda, 'is_available', lambda: False)
    sources = np.array([[-20., -20., -40.], [20., -20., -40.], [-20., 20., 40.], [20., 20., 40.]])
    normals = np.tile([0., 0., 1.], (4, 1)); gains = np.array([1., .7, 0., .9])
    snapshot = FieldSnapshot(sources, normals, np.zeros(4), gains, FieldConfig())
    targets = [TrapTarget((-6., 0., 0.)), TrapTarget((6., 1., 2.), 'twin')]
    settings = HologramSettings(iterations=12, phase_tolerance_rad=0.)
    cpu = HologramSolver().solve(sources, normals, gains, snapshot.field_config, targets, settings)
    controller = HologramController(); results = []; errors = []
    controller.succeeded.connect(results.append); controller.failed.connect(errors.append)
    controller.submit(snapshot, targets, settings, mode=3, torch=True)
    timer = QtCore.QElapsedTimer(); timer.start()
    while controller.busy and timer.elapsed() < 15000:
        app.processEvents(); QtCore.QThread.msleep(5)
    assert not controller.busy and not errors and len(results) == 1
    assert results[0]['backend']['backend'] == 'PyTorch CUDA' and not results[0]['backend']['fallback_reason']
    np.testing.assert_allclose(np.exp(1j * results[0]['phases_rad']), np.exp(1j * cpu['phases_rad']), atol=1e-9)
    np.testing.assert_allclose(results[0]['residual_history'], cpu['residual_history'], atol=1e-10)
