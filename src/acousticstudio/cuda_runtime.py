"""Optional CUDA installation and a persistent fresh-process numerical runtime."""
import atexit
import json
import os
from pathlib import Path
from queue import Empty, Queue
import shutil
import subprocess
import sys
import tempfile
from threading import Lock, Thread

from acousticstudio.cuda_protocol import read_message, write_message

CUDA_INDEX_URL = 'https://download.pytorch.org/whl/cu130'
TORCH_CUDA_PACKAGE = 'torch==2.14.0+cu130'
REQUEST_TIMEOUT_SECONDS = 30.


def runtime_root():
    return Path(__file__).resolve().parents[2] / 'runtime' / 'torch_cuda' / f'py{sys.version_info.major}{sys.version_info.minor}-cu130'


def installed_runtime_path():
    root = runtime_root().resolve()
    marker = root / 'active.json'
    if not marker.exists():
        return None
    data = json.loads(marker.read_text(encoding='utf-8'))
    name = data['directory']
    if not isinstance(name, str) or not name.startswith('install-') or Path(name).name != name:
        raise ValueError('CUDA 런타임 경로 기록이 잘못되었습니다.')
    target = (root / name).resolve()
    if target.parent != root or not (target / 'torch' / '__init__.py').is_file():
        raise ValueError('CUDA 런타임 파일이 없거나 경로가 잘못되었습니다.')
    return target


class CudaClient:
    """One in-flight request; IO and lock waits are bounded even if CUDA hangs."""
    def __init__(self, target, timeout=REQUEST_TIMEOUT_SECONDS):
        self.target, self.timeout = Path(target).resolve(), timeout
        self._lock = Lock()
        self._process = self._io_thread = self._requests = self._info = None

    def _start(self):
        worker = Path(__file__).with_name('cuda_worker.py')
        self._process = subprocess.Popen([sys.executable, '-u', str(worker), str(self.target)],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self._requests = Queue(maxsize=1)
        process, requests = self._process, self._requests
        def io_loop():
            while True:
                job = requests.get()
                if job is None:
                    return
                payload, reply = job
                try:
                    write_message(process.stdin, payload)
                    reply.put(read_message(process.stdout))
                except Exception as exc:
                    reply.put(dict(ok=False, error=f'CUDA 계산 프로세스 통신 실패: {exc}'))
                    return
        self._io_thread = Thread(target=io_loop, daemon=True, name='AcousticStudio CUDA IO')
        self._io_thread.start()

    def request(self, operation, *arguments):
        if not self._lock.acquire(timeout=self.timeout):
            raise TimeoutError('CUDA 계산 프로세스가 이전 요청을 처리 중입니다.')
        try:
            if self._process is not None and self._process.poll() is not None:
                self._stop()
            if self._process is None:
                self._start()
            reply = Queue(maxsize=1)
            self._requests.put(((operation, arguments), reply), timeout=self.timeout)
            try:
                response = reply.get(timeout=self.timeout)
            except Empty as exc:
                raise TimeoutError('CUDA 계산 응답 대기 시간이 초과되었습니다.') from exc
            if not response['ok']:
                raise RuntimeError(response['error'])
            return response['value']
        except Exception:
            self._stop()
            raise
        finally:
            self._lock.release()

    def info(self):
        if self._info is None or self._process is None or self._process.poll() is not None:
            self._info = self.request('probe')
        return dict(self._info, cuda_runtime_path=str(self.target))

    def _stop(self):
        process, thread, requests = self._process, self._io_thread, self._requests
        self._process = self._io_thread = self._requests = self._info = None
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=2)
            if requests is not None:
                try:
                    requests.put_nowait(None)
                except Exception:
                    pass
            if thread is not None:
                thread.join(timeout=1)
            process.stdin.close(); process.stdout.close()

    def close(self):
        if self._lock.acquire(timeout=self.timeout):
            try:
                self._stop()
            finally:
                self._lock.release()


_client = None
_client_lock = Lock()


def _get_client():
    global _client
    with _client_lock:
        if _client is None:
            path = installed_runtime_path()
            if path is not None:
                _client = CudaClient(path)
        return _client


def runtime_info():
    client = _get_client()
    return None if client is None else client.info()


def run_remote(operation, *arguments):
    client = _get_client()
    if client is None:
        raise RuntimeError('PyTorch CUDA 런타임을 먼저 선택 항목에서 설치하세요.')
    return client.request(operation, *arguments)


def close_runtime():
    global _client
    with _client_lock:
        client, _client = _client, None
    if client is not None:
        client.close()


def cuda_install_command(target):
    return [sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', '--progress-bar', 'off',
            '--only-binary=:all:', '--target', str(target), '--index-url', CUDA_INDEX_URL, TORCH_CUDA_PACKAGE]


def install_cuda_runtime(log, cancelled, process_changed):
    """Called only for a user-selected optional CUDA install; activate after verification."""
    global _client
    if sys.platform != 'win32' or not (3, 10) <= sys.version_info[:2] <= (3, 14):
        raise RuntimeError('이 자동 CUDA 설치는 Windows의 Python 3.10~3.14를 지원합니다.')
    executable = shutil.which('nvidia-smi')
    if executable is None:
        raise RuntimeError('NVIDIA 드라이버/장치를 확인할 수 없습니다 (nvidia-smi 없음).')
    device = subprocess.run([executable, '--query-gpu=name,driver_version', '--format=csv,noheader'],
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if device.returncode or not device.stdout.strip():
        raise RuntimeError('NVIDIA CUDA 장치를 확인하지 못했습니다.')
    rows = [row.rsplit(',', 1) for row in device.stdout.strip().splitlines()]
    if any(len(row) != 2 or int(row[1].strip().split('.')[0]) < 580 for row in rows):
        raise RuntimeError('CUDA 13.0에는 NVIDIA 580 계열 이상의 드라이버가 필요합니다.')
    log(f'NVIDIA 장치: {device.stdout.strip()}\n')
    if cancelled.is_set():
        raise RuntimeError('CUDA 설치를 취소했습니다.')
    root = runtime_root().resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix='install-', dir=root)).resolve()
    activated = False
    probe = None
    marker = root / f'{target.name}.active.tmp'
    try:
        process = subprocess.Popen(cuda_install_command(target), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW)
        process_changed(process)
        try:
            for line in iter(process.stdout.readline, ''):
                log(line)
            code = process.wait()
        finally:
            process.stdout.close()
            process_changed(None)
        if cancelled.is_set():
            raise RuntimeError('CUDA 설치를 취소했습니다.')
        if code:
            raise RuntimeError(f'PyTorch CUDA 설치 실패 (pip 종료 코드 {code}). 설치 로그를 확인하세요.')
        log('새 계산 프로세스에서 CUDA와 복소수 커널을 확인합니다.\n')
        probe = CudaClient(target)
        info = probe.info()
        if not info['cuda_available'] or info['torch_cuda_build'] is None:
            raise RuntimeError(info.get('cuda_error') or '설치 후 CUDA를 사용할 수 없습니다.')
        if not Path(info['torch_file']).is_relative_to(target):
            raise RuntimeError('새 CUDA 패키지 대신 기존 PyTorch가 로드되었습니다.')
        if cancelled.is_set():
            raise RuntimeError('CUDA 설치를 취소했습니다.')
        close_runtime()
        marker.write_text(json.dumps(dict(directory=target.name, torch_version=info['torch_version']),
                                     ensure_ascii=False) + '\n', encoding='utf-8')
        os.replace(marker, root / 'active.json')
        activated = True
        with _client_lock:
            _client, probe = probe, None  # Reuse the verified child; no GUI-thread re-import.
        log(f"CUDA 사용 준비 완료: {info['torch_version']} · {info['cuda_device']}\n")
    finally:
        if probe is not None:
            probe.close()
        if not activated:
            # Only our newly created install directory, verified inside the runtime root.
            if target.parent != root or not target.name.startswith('install-'):
                raise RuntimeError('임시 CUDA 설치 경로 검증 실패.')
            if marker.exists():
                marker.unlink()
            shutil.rmtree(target)


atexit.register(close_runtime)
