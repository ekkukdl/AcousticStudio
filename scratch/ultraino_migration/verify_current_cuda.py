"""Read-only device probe and real backend comparison; no install or board IO."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import torch

from acousticstudio.compute_devices import probe_compute_devices
from acousticstudio.cuda_runtime import installed_runtime_path, runtime_root
from acousticstudio.field_backends import reduce_field


def command(arguments):
    result = subprocess.run(arguments, capture_output=True, text=True, encoding='utf-8',
                            errors='replace', timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    return dict(returncode=result.returncode, stdout=result.stdout.strip(), stderr=result.stderr.strip())


devices = probe_compute_devices()
rng = np.random.default_rng(20261008)
matrix = rng.normal(size=(16, 256)) + 1j * rng.normal(size=(16, 256))
weights = rng.normal(size=256) + 1j * rng.normal(size=256)
weights[5] = 0.
expected = matrix @ weights
checks = []
for mode in (2, 3):
    actual, status = reduce_field(matrix, weights, mode,
                                  has_taichi=devices.taichi_available, has_pytorch=devices.cuda_available)
    np.testing.assert_allclose(actual, expected, atol=1e-10, rtol=1e-10)
    checks.append(dict(status=status, max_absolute_error=float(np.max(np.abs(actual - expected)))))
installed = installed_runtime_path()
result = dict(utc=datetime.now(timezone.utc).isoformat(), python=sys.executable,
              windows_gpu=command(['powershell', '-NoProfile', '-Command',
                                   'Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,Status | ConvertTo-Json']),
              nvidia_smi=command(['nvidia-smi', '--query-gpu=name,driver_version', '--format=csv,noheader']),
              host_torch=dict(version=torch.__version__, cuda_build=torch.version.cuda,
                              cuda_available=torch.cuda.is_available(), device_count=torch.cuda.device_count()),
              runtime_root=str(runtime_root()), installed_runtime=None if installed is None else str(installed),
              compute_devices=asdict(devices), backend_checks=checks)
output = Path(__file__).with_name('current_cuda_result.json')
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
