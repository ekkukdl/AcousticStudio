"""30 Hz request stream on actual CPU/Vulkan workers, using fake serial only."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import monotonic, sleep

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from acousticstudio.compute_devices import probe_compute_devices
from acousticstudio.force_analysis import FieldSnapshot
from acousticstudio.field_model import FieldConfig
from acousticstudio.geometry import load_creo_tunnel
from acousticstudio.hardware import HardwareController
from acousticstudio.hologram import HologramSettings, HologramSolver, TrapTarget
from acousticstudio.hologram_ui import HologramController

app = QApplication([])
devices = probe_compute_devices()
geometry = load_creo_tunnel()
sources = np.array([e['position_mm'] for e in geometry['elements']])
normals = np.array([e['normal'] for e in geometry['elements']])
gains = np.ones(256); gains[5] = 0.; gains[7] = .7
snapshot = FieldSnapshot(sources, normals, np.zeros(256), gains, FieldConfig())
settings = HologramSettings(iterations=12, phase_tolerance_rad=0.)

def targets(step):
    z = step * .1
    return [TrapTarget((-6., 0., z), 'twin'),
            TrapTarget((6., 0., z + 3.), 'standing_wave', weight=.8, direction=(0., 0., 1.))]

class FakeSerial:
    baudrate = 230400
    def __init__(self): self.frames = []
    def write(self, frame): self.frames.append(frame); return len(frame)
    def close(self): pass

records = []
for mode in (1, 2):
    if mode == 2 and not devices.taichi_available:
        continue
    solver = HologramController()
    hardware = HardwareController(); hardware.set_board_profile('ultraino_simplefpga_256')
    fake = FakeSerial(); hardware.serial_port = fake
    results, errors = [], []
    issued = [0]; last_request_time = [0.]; end_latency = [None]
    def completed(result):
        results.append(result)
        hardware.queue_phases(result['phases_rad'], active=(gains > 0).tolist())
        if issued[0] == 30:
            end_latency[0] = (monotonic() - last_request_time[0]) * 1000
    solver.succeeded.connect(completed); solver.failed.connect(errors.append)
    # Warm the actual engine before measuring the update stream.
    solver.submit(snapshot, targets(0), settings, mode, devices.taichi_available, False)
    deadline = monotonic() + 20
    while (solver.busy or hardware.sender_busy) and monotonic() < deadline:
        app.processEvents(); sleep(.001)
    assert not solver.busy and results and not errors
    results.clear(); fake.frames.clear()
    hardware.send_statistics.update(submitted=0, replaced=0, written=0, failed=0)
    started = monotonic()
    def tick():
        issued[0] += 1; last_request_time[0] = monotonic()
        solver.submit(snapshot, targets(issued[0]), settings, mode, devices.taichi_available, False)
        if issued[0] == 30:
            timer.stop()
    timer = QTimer(); timer.setInterval(33); timer.timeout.connect(tick); timer.start()
    deadline = monotonic() + 20
    while (timer.isActive() or solver.busy or hardware.sender_busy or hardware._pending_frame is not None) and monotonic() < deadline:
        app.processEvents(); sleep(.001)
    assert issued[0] == 30 and not errors and not solver.busy and results
    stream_elapsed = monotonic() - started
    final = results[-1]
    np.testing.assert_allclose(final['targets'][0]['position_mm'], targets(30)[0].position_mm)
    cpu = HologramSolver().solve(sources, normals, gains, snapshot.field_config, targets(30), settings)
    phase_error = float(np.max(np.abs(np.exp(1j * final['phases_rad']) - np.exp(1j * cpu['phases_rad']))))
    assert phase_error < 1e-9
    assert fake.frames[-1] == hardware.build_phase_frame(final['phases_rad'], active=(gains > 0).tolist())
    records.append(dict(mode=mode, backend=final['backend'], requested=issued[0], accepted=len(results),
                        superseded_or_merged=issued[0] - len(results), frames_written=len(fake.frames),
                        elapsed_seconds=stream_elapsed, final_response_ms=end_latency[0],
                        worker_ms=[result['elapsed_seconds'] * 1000 for result in results],
                        phase_error=phase_error, send_statistics=dict(hardware.send_statistics)))
    hardware.disconnect()
result = dict(utc=datetime.now(timezone.utc).isoformat(), nominal_request_interval_ms=33,
              serial_transport='fake serial, no physical wire or controller ACK', results=records)
Path(__file__).with_name('t6_updates_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
