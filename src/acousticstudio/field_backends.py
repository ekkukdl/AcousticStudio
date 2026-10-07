"""Accelerate complex reduction only; every backend consumes the same Green matrix."""
import ctypes
from pathlib import Path

import numba
import numpy as np


@numba.njit
def _numba_matvec(matrix, weights):
    output = np.zeros(matrix.shape[0], dtype=np.complex128)
    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            output[row] += matrix[row, col] * weights[col]
    return output


_native = None
_native_checked = False
_native_error = None


def _native_reduce(matrix, weights):
    global _native, _native_checked, _native_error
    if not _native_checked:
        _native_checked = True
        path = Path(__file__).with_name('sonic_core.dll')
        try:
            if path.exists():
                library = ctypes.CDLL(str(path))
                if hasattr(library, 'complex_matvec'):
                    _native = library.complex_matvec
                    pointer = np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS')
                    _native.argtypes = [pointer] * 4 + [ctypes.c_int, ctypes.c_int] + [pointer] * 2
                    _native.restype = None
        except OSError as exc:
            _native_error = f'DLL 로드 실패: {exc}'
    if _native is None:
        raise RuntimeError(_native_error or '현재 DLL에 complex_matvec가 없습니다. 재빌드가 필요합니다.')
    real, imag = np.zeros(matrix.shape[0]), np.zeros(matrix.shape[0])
    _native(*(np.ascontiguousarray(v, dtype=np.float64).ravel() for v in
              (matrix.real, matrix.imag, weights.real, weights.imag)),
            *matrix.shape, real, imag)
    return real + 1j * imag


def reduce_field(matrix, weights, mode_idx=0, has_taichi=False, has_pytorch=False):
    matrix = np.ascontiguousarray(matrix, dtype=np.complex128)
    weights = np.ascontiguousarray(weights, dtype=np.complex128)
    if matrix.ndim != 2 or weights.shape != (matrix.shape[1],):
        raise ValueError('복소 행렬과 채널 가중치의 형상이 일치하지 않습니다.')
    if not np.isfinite(matrix).all() or not np.isfinite(weights).all():
        raise ValueError('복소 입력은 유한해야 합니다.')
    if mode_idx not in (0, 1, 2, 3):
        raise ValueError('지원하지 않는 연산 모드입니다.')
    backend, reason = 'Numba CPU', None
    result = None
    try:
        if mode_idx == 1:
            result = _native_reduce(matrix, weights)
            backend = 'C++'
        elif mode_idx == 2:
            if not has_taichi:
                raise RuntimeError('Taichi 모드를 사용할 수 없습니다.')
            from acousticstudio.sonic_wrapper import calculate_complex_matvec_taichi
            result = calculate_complex_matvec_taichi(matrix, weights)
            if result is None:
                raise RuntimeError('Taichi 복소 연산을 사용할 수 없습니다.')
            from acousticstudio.sonic_wrapper import ti
            backend = f'Taichi {ti.cfg.arch.name}'
        elif mode_idx == 3:
            if not has_pytorch:
                raise RuntimeError('PyTorch CUDA 모드를 사용할 수 없습니다.')
            from acousticstudio.cuda_runtime import run_remote
            try:
                import torch
            except Exception:
                torch = None
            if torch is not None and torch.cuda.is_available():
                result = (torch.as_tensor(matrix, device='cuda') @
                          torch.as_tensor(weights, device='cuda')).cpu().numpy()
            else:
                result = run_remote('matvec', matrix, weights)
            backend = 'PyTorch CUDA'
    except Exception as exc:
        reason = str(exc)
    if result is None:
        result = _numba_matvec(matrix, weights)
    result = np.asarray(result, dtype=np.complex128)
    if result.shape != (matrix.shape[0],) or not np.isfinite(result).all():
        raise ValueError('복소 연산 결과의 형상이 잘못되었거나 유한하지 않습니다.')
    return result, {'requested_mode': mode_idx, 'backend': backend, 'fallback_reason': reason}
