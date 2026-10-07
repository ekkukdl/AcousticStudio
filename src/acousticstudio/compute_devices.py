"""Inspect usable compute runtimes without installing or changing the environment."""
from dataclasses import dataclass
from importlib import import_module
from importlib.util import find_spec


@dataclass(frozen=True)
class ComputeDevices:
    cpp_available: bool = False
    taichi_installed: bool = False
    taichi_arch: str | None = None
    taichi_error: str | None = None
    torch_installed: bool = False
    torch_version: str | None = None
    torch_cuda_build: str | None = None
    cuda_available: bool = False
    cuda_device: str | None = None
    cuda_error: str | None = None
    cuda_runtime_path: str | None = None

    @property
    def taichi_available(self):
        return self.taichi_arch is not None and self.taichi_error is None

    def preferred_mode(self):
        if self.cuda_available:
            return 3
        if self.taichi_available:
            return 2
        return 1 if self.cpp_available else 0


def probe_compute_devices():
    """Package presence is distinct from a GPU runtime/device being available."""
    values = dict(taichi_installed=find_spec('taichi') is not None,
                  torch_installed=find_spec('torch') is not None)
    if values['torch_installed']:
        try:
            torch = import_module('torch')
            values.update(torch_version=str(torch.__version__), torch_cuda_build=torch.version.cuda,
                          cuda_available=bool(torch.cuda.is_available()))
            if values['cuda_available']:
                values['cuda_device'] = torch.cuda.get_device_name()
            elif torch.version.cuda is None:
                values['cuda_error'] = '설치된 PyTorch에 CUDA 빌드가 없습니다 (CPU 전용).'
            else:
                values['cuda_error'] = 'PyTorch가 CUDA 장치를 사용할 수 없습니다. 장치/드라이버를 확인하세요.'
        except Exception as exc:
            values.update(cuda_available=False, cuda_error=f'PyTorch 로드/장치 확인 실패: {exc}')
    else:
        values['cuda_error'] = 'PyTorch가 설치되지 않았습니다.'
    if not values.get('cuda_available', False):
        try:
            from acousticstudio.cuda_runtime import runtime_info
            remote = runtime_info()
            if remote is not None:
                values.update({name: remote[name] for name in
                               ('torch_version', 'torch_cuda_build', 'cuda_available', 'cuda_device', 'cuda_error', 'cuda_runtime_path')})
                values['torch_installed'] = True
        except Exception as exc:
            values['cuda_error'] = f'별도 CUDA 런타임 확인 실패: {exc}'
    try:
        wrapper = import_module('acousticstudio.sonic_wrapper')
        values['cpp_available'] = wrapper._cpp_lib is not None
        if values['taichi_installed']:
            if not wrapper._has_taichi:
                raise RuntimeError('Taichi 런타임을 사용할 수 없습니다.')
            values['taichi_arch'] = wrapper.ti.cfg.arch.name
            if wrapper.ti.cfg.arch == wrapper.ti.cpu:
                values['taichi_error'] = 'Taichi가 CPU로 초기화되었습니다. GPU 가속을 사용할 수 없습니다.'
    except Exception as exc:
        if values['taichi_installed']:
            values['taichi_error'] = f'Taichi 런타임 확인 실패: {exc}'
    if not values['taichi_installed']:
        values['taichi_error'] = 'Taichi가 설치되지 않았습니다.'
    return ComputeDevices(**values)
