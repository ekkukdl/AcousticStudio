"""Numerical jobs reuse Kinoforms' bounded latest-request worker lifecycle."""
from copy import deepcopy
from hashlib import sha256
import pickle
from time import perf_counter

from PySide6.QtCore import QObject, Signal, Slot

from acousticstudio.hologram import HologramCancelled
from acousticstudio.hologram_ui import HologramController


def job_key(parameters):
    # Internal numeric snapshots only. No external pickle is loaded.
    return sha256(pickle.dumps(parameters, protocol=5)).hexdigest()


class NumericalWorker(QObject):
    succeeded = Signal(int, object)
    failed = Signal(int, str)
    progress = Signal(int, int)
    finished = Signal()

    def __init__(self, engine, version, kind, parameters, cancellation):
        super().__init__()
        self.arguments = engine, version, kind, parameters, cancellation

    @Slot()
    def run(self):
        engine, version, kind, parameters, cancelled = self.arguments
        started = perf_counter()
        try:
            kwargs = dict(parameters)
            if kind == 'phase':
                value = engine.calculate_phases(**kwargs, cancelled=cancelled)
            elif kind == 'field':
                planes = kwargs.pop('planes')
                kwargs.pop('view_mode')
                value = []
                for key, points in planes:
                    if cancelled.is_set():
                        return
                    real, imag = engine.calculate_field_slice(points, **kwargs, cancelled=cancelled)
                    value.append((key, points, real, imag))
            elif kind == 'trajectory':
                value = engine.optimize_trajectory_physical(**kwargs, cancelled=cancelled)
            elif kind == 'export':
                value = engine.calculate_trajectory_phases(**kwargs, cancelled=cancelled)
            else:
                raise ValueError('지원하지 않는 수치 작업입니다.')
            if not cancelled.is_set():
                self.succeeded.emit(version, dict(kind=kind, key=job_key(parameters), value=value,
                                                 backend=engine.last_backend, elapsed_seconds=perf_counter() - started))
        except HologramCancelled:
            pass
        except Exception as exc:
            if not cancelled.is_set():
                self.failed.emit(version, str(exc))
        finally:
            self.finished.emit()


class NumericalController(HologramController):
    def submit(self, kind, parameters):
        parameters = deepcopy(parameters)
        self._version += 1
        self._pending = (self._version, kind, parameters)
        if self.busy:
            self._cancellation.set()
        else:
            self._start_pending()
        return job_key(parameters)

    def _make_worker(self, arguments):
        return NumericalWorker(self.engine, *arguments, self._cancellation)
