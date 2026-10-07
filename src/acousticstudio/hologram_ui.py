"""Kinoforms editor and queued numerical workers; all actor access stays in app.py."""
import json
from pathlib import Path
from threading import Event

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout,
                              QHBoxLayout, QLabel, QProgressBar, QPushButton, QSpinBox,
                              QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from acousticstudio.force_analysis import AnalysisSettings, FieldSnapshot, json_result
from acousticstudio.hologram import HologramCancelled, HologramSettings, TRAP_TYPES, TrapTarget
from acousticstudio.phase_engine import PhaseEngine

LABELS = ['Focus', 'Twin', 'Standing Wave']


class HologramWorker(QObject):
    succeeded = Signal(int, object)
    failed = Signal(int, str)
    progress = Signal(int, int)
    finished = Signal()

    def __init__(self, engine, request_id, snapshot, targets, settings, mode, taichi, torch, cancellation):
        super().__init__()
        self.arguments = engine, request_id, snapshot, targets, settings, mode, taichi, torch, cancellation

    @Slot()
    def run(self):
        engine, request_id, snapshot, targets, settings, mode, taichi, torch, cancellation = self.arguments
        try:
            result = engine.calculate_hologram(
                snapshot.sources_mm, targets, snapshot.amplitudes, mode, taichi, torch,
                snapshot.field_config, snapshot.normals, snapshot.aperture_radii_mm, settings,
                snapshot.phases_rad, cancellation, lambda value: self.progress.emit(request_id, value))
            if not cancellation.is_set():
                self.succeeded.emit(request_id, result)
        except HologramCancelled:
            pass
        except Exception as exc:
            self.failed.emit(request_id, str(exc))
        finally:
            self.finished.emit()


class HologramController(QObject):
    """Sequential workers with one pending request; superseded results cannot apply."""
    succeeded = Signal(object)
    failed = Signal(str)
    progress = Signal(int)
    idle = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = PhaseEngine()
        self._thread = self._worker = self._pending = None
        self._version = 0
        self._cancellation = Event()

    @property
    def busy(self):
        return self._thread is not None

    def submit(self, snapshot, targets, settings, mode=0, taichi=False, torch=False):
        self._version += 1
        self._pending = (self._version, snapshot, tuple(targets), settings, mode, taichi, torch)
        if self.busy:
            self._cancellation.set()
        else:
            self._start_pending()

    def _start_pending(self):
        arguments, self._pending = self._pending, None
        self._cancellation = Event()
        self._thread = QThread(self)
        self._worker = HologramWorker(self.engine, *arguments, self._cancellation)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.succeeded.connect(self._succeeded)
        self._worker.failed.connect(self._failed)
        self._worker.progress.connect(self._progress)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._done)
        self._thread.start()

    def cancel(self):
        self._version += 1
        self._pending = None
        self._cancellation.set()

    @Slot(int, object)
    def _succeeded(self, version, result):
        if version == self._version and not self._cancellation.is_set():
            self.succeeded.emit(result)

    @Slot(int, str)
    def _failed(self, version, message):
        if version == self._version:
            self.failed.emit(message)

    @Slot(int, int)
    def _progress(self, version, value):
        if version == self._version:
            self.progress.emit(value)

    @Slot()
    def _done(self):
        thread = self._thread
        self._thread = self._worker = None
        thread.deleteLater()
        if self._pending is not None:
            self._start_pending()
        else:
            self.idle.emit()


class HologramDialog(QDialog):
    applied = Signal(object)

    def __init__(self, snapshot, targets, settings=None, mode=0, taichi=False, torch=False,
                 force_settings=None, parent=None):
        super().__init__(parent)
        self.snapshot, self.original_targets = snapshot, tuple(targets)
        self.mode, self.taichi, self.torch = mode, taichi, torch
        self.force_settings = force_settings or AnalysisSettings()
        self.result = None
        self._closing = False
        self.controller = HologramController(self)
        self.setWindowTitle('Kinoforms 다중 트랩 설계')
        self.resize(1100, 820); self.setMinimumSize(940, 720)
        layout = QVBoxLayout(self)
        banner = QLabel(f'{len(snapshot.sources_mm)}채널 · 송신기 이득 고정 / 위상만 조절 · 음압은 미보정 상대값\n'
                        'Focus는 음압 초점입니다. Twin/Standing Wave의 복원성은 고정 위상 분석에서 확인하세요.\n'
                        'Twin 가상점 ±λ/1.5, Standing Wave ±λ/2. 기본 방향은 각각 X, 터널 Z입니다.')
        banner.setWordWrap(True); layout.addWidget(banner)
        self.inputs = QWidget(); controls = QVBoxLayout(self.inputs)
        form = QFormLayout()
        settings = settings or HologramSettings()
        self.iterations = QSpinBox(); self.iterations.setRange(1, 2000); self.iterations.setValue(settings.iterations)
        self.tolerance = self._spin(0., .1, settings.phase_tolerance_rad, 8)
        self.default_type = QComboBox(); self.default_type.addItems(LABELS); self.default_type.setCurrentIndex(TRAP_TYPES.index(settings.default_trap_type))
        self.initialization = QComboBox(); self.initialization.addItems(['0 위상', '현재 위상']); self.initialization.setCurrentIndex(int(settings.initialization == 'current'))
        form.addRow('최대 반복 수:', self.iterations)
        form.addRow('위상 변화 허용값(rad, 0=고정 반복):', self.tolerance)
        form.addRow('새 제어점·단일 궤적 기본 트랩:', self.default_type)
        form.addRow('초기 위상:', self.initialization)
        controls.addLayout(form)
        self.table = QTableWidget(len(targets), 6)
        self.table.setHorizontalHeaderLabels(['중심 XYZ (mm)', '트랩', '목표 가중치', '방향 X', '방향 Y', '방향 Z'])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setColumnWidth(0, 235); self.table.setColumnWidth(1, 160)
        self.table.setMinimumHeight(150)
        self.rows = []
        for row, target in enumerate(targets):
            self.table.setItem(row, 0, QTableWidgetItem(', '.join(f'{v:g}' for v in target.position_mm)))
            trap = QComboBox(); trap.addItems(LABELS); trap.setCurrentIndex(TRAP_TYPES.index(target.trap_type))
            weight = self._spin(.001, 1000., target.weight, 4)
            direction = [self._spin(-1., 1., value, 6) for value in target.direction]
            for column, widget in enumerate([trap, weight, *direction], 1):
                self.table.setCellWidget(row, column, widget)
            trap.currentIndexChanged.connect(lambda index, widgets=direction: self._type_changed(index, widgets))
            self.rows.append((trap, weight, direction))
        controls.addWidget(self.table); layout.addWidget(self.inputs)
        actions = QHBoxLayout()
        self.calculate = QPushButton('Kinoforms 계산')
        self.cancel = QPushButton('계산 취소'); self.cancel.setEnabled(False)
        self.apply = QPushButton('현재 배열에 위상 적용'); self.apply.setEnabled(False)
        self.export = QPushButton('설계 JSON 저장'); self.export.setEnabled(False)
        self.force = QPushButton('선택 트랩의 고정 위상 분석'); self.force.setEnabled(False)
        for widget in (self.calculate, self.cancel, self.apply, self.export, self.force):
            actions.addWidget(widget)
        layout.addLayout(actions)
        self.progress = QProgressBar(); layout.addWidget(self.progress)
        self.summary = QLabel('트랩별 타입·가중치·방향을 설정한 뒤 계산하세요. 가중치는 상대 목표 음압입니다.')
        self.summary.setWordWrap(True); layout.addWidget(self.summary)
        self.figure = Figure(figsize=(9, 2.8), layout='constrained')
        self.canvas = FigureCanvasQTAgg(self.figure); layout.addWidget(self.canvas, 1)
        self.calculate.clicked.connect(self.start_analysis); self.cancel.clicked.connect(self.cancel_analysis)
        self.apply.clicked.connect(self.apply_result); self.export.clicked.connect(self.export_result)
        self.force.clicked.connect(self.open_force_analysis)
        self.controller.succeeded.connect(self._on_result); self.controller.failed.connect(self._on_failure)
        self.controller.progress.connect(self.progress.setValue); self.controller.idle.connect(self._idle)
        for widget in self.inputs.findChildren(QWidget):
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.valueChanged.connect(self._invalidate)
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._invalidate)

    @staticmethod
    def _spin(low, high, value, decimals):
        widget = QDoubleSpinBox(); widget.setDecimals(decimals); widget.setRange(low, high); widget.setValue(value)
        return widget

    def _type_changed(self, index, direction):
        for widget, value in zip(direction, (0., 0., 1.) if index == 2 else (1., 0., 0.)):
            widget.setValue(value)

    def _settings_targets(self):
        settings = HologramSettings(self.iterations.value(), self.tolerance.value(),
                                   TRAP_TYPES[self.default_type.currentIndex()],
                                   'current' if self.initialization.currentIndex() else 'zeros')
        targets = [TrapTarget(old.position_mm, TRAP_TYPES[trap.currentIndex()], weight.value(),
                              tuple(widget.value() for widget in direction))
                   for old, (trap, weight, direction) in zip(self.original_targets, self.rows)]
        return settings, targets

    def _invalidate(self, *_):
        self.result = None
        for button in (self.apply, self.export, self.force):
            button.setEnabled(False)
        self.figure.clear(); self.canvas.draw_idle()

    @Slot()
    def start_analysis(self):
        if self.controller.busy:
            return
        self._invalidate()
        try:
            settings, targets = self._settings_targets()
        except ValueError as exc:
            self.summary.setText(f'설계 불가: {exc}'); return
        self._closing = False
        self.inputs.setEnabled(False); self.calculate.setEnabled(False); self.cancel.setEnabled(True)
        self.progress.setValue(0); self.summary.setText('전방 투영 → 목표장 제약 → 공액 역전파를 반복하고 있습니다.')
        self.controller.submit(self.snapshot, targets, settings, self.mode, self.taichi, self.torch)

    @Slot()
    def cancel_analysis(self):
        self.controller.cancel(); self._invalidate(); self.cancel.setEnabled(False)
        self.summary.setText('취소 요청 — 현재 수치 연산이 끝나는 대로 종료합니다.')

    @Slot(object)
    def _on_result(self, result):
        self.result = result
        metrics = result['metrics']
        self.summary.setText(f"{result['iterations_completed']}회 · 제약 잔차 {metrics['relative_residual']:.5g} · "
                             f"가중 음압 균일도 {metrics['weighted_uniformity']:.4g} · {result['elapsed_seconds'] * 1000:.1f}ms\n"
                             f"복소 합산: {result['backend']['backend']} · 위상 정체 {'도달' if result['stationary'] else '미도달'} · "
                             '음압 초점 균일도이며 부양 성공률이 아닙니다.'
                             + (f" CPU 전환: {result['backend']['fallback_reason']}" if result['backend']['fallback_reason'] else ''))
        self.figure.clear()
        self.figure.suptitle('Phase-only Kinoforms, fixed source gains; uncalibrated relative pressure', fontsize=10)
        plot = self.figure.add_subplot(1, 2, 1)
        plot.plot(np.arange(1, result['iterations_completed'] + 1), result['residual_history'])
        plot.set_xlabel('Iteration'); plot.set_ylabel('Relative constraint residual'); plot.grid(alpha=.2)
        plot = self.figure.add_subplot(1, 2, 2)
        plot.bar(np.arange(len(result['virtual_points_mm'])), result['pressure_magnitude'] / result['target_weights'])
        plot.set_xlabel('Virtual point'); plot.set_ylabel('Pressure / weight\n(relative)')
        self.canvas.draw_idle()

    @Slot(str)
    def _on_failure(self, message):
        self._invalidate(); self.summary.setText(f'설계 불가: {message}')

    @Slot()
    def _idle(self):
        self.inputs.setEnabled(True); self.calculate.setEnabled(True); self.cancel.setEnabled(False)
        for button in (self.apply, self.export, self.force):
            button.setEnabled(self.result is not None)
        if self._closing:
            self.close()

    @Slot()
    def apply_result(self):
        if self.result is not None and not self.controller.busy:
            self.applied.emit(self.result)

    @Slot()
    def export_result(self):
        if self.result is None or self.controller.busy:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Kinoforms 설계 저장', '', 'Kinoforms JSON (*.json)')
        if path:
            try:
                Path(path).write_text(json.dumps(json_result(self.result), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
            except (OSError, ValueError) as exc:
                self.summary.setText(f'저장 실패: {exc}')

    @Slot()
    def open_force_analysis(self):
        if self.result is None or self.controller.busy:
            return
        from acousticstudio.force_analysis_ui import ForceAnalysisDialog
        row = max(0, self.table.currentRow())
        snapshot = FieldSnapshot(self.snapshot.sources_mm, self.snapshot.normals, self.result['phases_rad'],
                                 self.snapshot.amplitudes, self.snapshot.field_config, self.snapshot.aperture_radii_mm)
        dialog = ForceAnalysisDialog(snapshot, self.result['targets'][row]['position_mm'], self.force_settings,
                                     self.mode, self.taichi, self.torch, self)
        dialog.exec()

    def reject(self):
        if self.controller.busy:
            self._closing = True; self.cancel_analysis()
        else:
            super().reject()

    def closeEvent(self, event):
        if self.controller.busy:
            self._closing = True; self.cancel_analysis(); event.ignore()
        else:
            super().closeEvent(event)
