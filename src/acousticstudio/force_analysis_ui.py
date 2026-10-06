"""Qt fixed-drive analysis dialog; numerical work has no access to actors/widgets."""
import json
from pathlib import Path
from threading import Event

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
                              QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                              QProgressBar, QPushButton, QSpinBox, QTableWidget,
                              QTableWidgetItem, QVBoxLayout, QWidget)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from acousticstudio.force_analysis import (AnalysisCancelled, AnalysisSettings,
                                           ForceAnalyzer, ParticleConfig, json_result)


class AnalysisWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    progress = Signal(int)
    finished = Signal()

    def __init__(self, snapshot, centre, settings, mode_idx, has_taichi, has_pytorch, cancellation):
        super().__init__()
        self.arguments = snapshot, centre, settings, mode_idx, has_taichi, has_pytorch, cancellation

    @Slot()
    def run(self):
        snapshot, centre, settings, mode, taichi, torch, cancellation = self.arguments
        try:
            analyzer = ForceAnalyzer(snapshot, settings, mode, taichi, torch, cancellation)
            result = analyzer.analyze(centre, progress=self.progress.emit)
            if cancellation.is_set():
                raise AnalysisCancelled()
            self.succeeded.emit(result)
        except AnalysisCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class ForceAnalysisDialog(QDialog):
    settings_submitted = Signal(dict)

    def __init__(self, snapshot, centre_mm, settings=None, mode_idx=0, has_taichi=False, has_pytorch=False, parent=None):
        super().__init__(parent)
        self.snapshot = snapshot
        self.mode_idx, self.has_taichi, self.has_pytorch = mode_idx, has_taichi, has_pytorch
        self.result = None
        self._thread = self._worker = None
        self._close_after_thread = False
        self._cancellation = Event()
        self.setWindowTitle('고정 위상 방사력 분석')
        self.resize(1180, 890)
        self.setMinimumSize(980, 760)
        layout = QVBoxLayout(self)
        config = snapshot.field_config
        banner = QLabel(f'고정 송신 {len(snapshot.sources_mm)}채널 · {config.model} · {config.frequency_hz:g} Hz · '
                        f'{config.sound_speed_m_s:g} m/s\n'
                        '음압 미보정: N*·J*는 상대 음압 1=1Pa 가정값입니다. 중력 평형과 실제 부양 판정은 보류합니다.\n'
                        '작은 구의 고르코프 근사이며 진행파 산란·점성·기구물 반사는 포함하지 않습니다.')
        banner.setWordWrap(True)
        layout.addWidget(banner)
        self.inputs = QWidget()
        columns = QHBoxLayout(self.inputs)
        scan = QGroupBox('위상 고정 / 평가 위치·미분')
        form = QFormLayout(scan)
        xyz = QHBoxLayout()
        self.centre = [self._spin(-10000., 10000., value, 4, ' mm') for value in centre_mm]
        for name, widget in zip('XYZ', self.centre):
            xyz.addWidget(QLabel(name)); xyz.addWidget(widget)
        form.addRow('평가 중심:', xyz)
        self.span = self._spin(.0001, 1000., 2., 4, ' mm')
        self.samples = QSpinBox(); self.samples.setRange(5, 201); self.samples.setSingleStep(2)
        self.step = self._spin(.000001, 10., .133984, 6, ' mm')
        self.tolerance = self._spin(.0001, 10., 1., 4, ' %')
        form.addRow('축별 범위 ±:', self.span)
        form.addRow('표본 수 (홀수):', self.samples)
        form.addRow('미분 간격 h:', self.step)
        form.addRow('h / h÷2 / h÷4 오차:', self.tolerance)
        gravity = QHBoxLayout()
        self.gravity = [self._spin(-100., 100., value, 5, '') for value in (0., 0., -9.80665)]
        for name, widget in zip('XYZ', self.gravity):
            gravity.addWidget(QLabel(name)); gravity.addWidget(widget)
        form.addRow('중력 XYZ (m/s²):', gravity)
        columns.addWidget(scan, 1)
        particle = QGroupBox('입자 물성')
        form = QFormLayout(particle)
        self.radius = self._spin(.000001, 1000., .25, 6, ' mm')
        self.density = self._spin(.000001, 1e6, 25., 6, ' kg/m³')
        self.speed = self._spin(.000001, 1e6, 2350., 6, ' m/s')
        self.compressibility_mode = QComboBox(); self.compressibility_mode.addItems(['음속·밀도로 계산', '압축률 직접 입력'])
        self.compressibility = QLineEdit(); self.compressibility.setPlaceholderText('1/Pa, 예: 7.24e-9')
        self.provenance = QComboBox(); self.provenance.addItems(['예시·가정 물성', '제공된 제조사·측정 물성'])
        self.source = QLineEdit()
        for label, widget in [('구 반경:', self.radius), ('입자 밀도:', self.density), ('입자 음속:', self.speed),
                              ('압축률 설정:', self.compressibility_mode), ('직접 압축률:', self.compressibility),
                              ('물성 구분:', self.provenance), ('출처:', self.source)]:
            form.addRow(label, widget)
        columns.addWidget(particle, 1)
        layout.addWidget(self.inputs)
        self._restore(settings or AnalysisSettings())
        self.compressibility_mode.currentIndexChanged.connect(self._update_compressibility)
        self._update_compressibility()
        actions = QHBoxLayout()
        self.calculate = QPushButton('고정 위상으로 분석')
        self.cancel = QPushButton('계산 취소'); self.cancel.setEnabled(False)
        self.export = QPushButton('분석 JSON 저장'); self.export.setEnabled(False)
        self.plot_kind = QComboBox(); self.plot_kind.addItems(['힘·중력 가정 합성', '음압', '고르코프 퍼텐셜', '축 복원 스티프니스'])
        self.coupled = QCheckBox('다른 힘 성분 표시')
        for widget in (self.calculate, self.cancel, self.export, self.plot_kind, self.coupled):
            actions.addWidget(widget)
        layout.addLayout(actions)
        self.progress = QProgressBar(); self.progress.setRange(0, 100)
        layout.addWidget(self.progress)
        self.summary = QLabel('예시 물성입니다. 현재 송신 위상·진폭은 분석 동안 변경하지 않습니다.')
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.matrix = QTableWidget(3, 3)
        self.matrix.setHorizontalHeaderLabels(['∂/∂X', '∂/∂Y', '∂/∂Z'])
        self.matrix.setVerticalHeaderLabels(['−∂Fx', '−∂Fy', '−∂Fz'])
        self.matrix.setMaximumHeight(122)
        self.matrix.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.matrix)
        self.figure = Figure(figsize=(10, 2.5), layout='constrained')
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas, 1)
        self.calculate.clicked.connect(self.start_analysis)
        self.cancel.clicked.connect(self.cancel_analysis)
        self.export.clicked.connect(self.export_result)
        self.plot_kind.currentIndexChanged.connect(self.draw_result)
        self.coupled.toggled.connect(self.draw_result)
        for widget in self.inputs.findChildren(QWidget):
            if isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                widget.valueChanged.connect(self._invalidate)
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._invalidate)
            elif isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._invalidate)

    @staticmethod
    def _spin(low, high, value, decimals, suffix):
        widget = QDoubleSpinBox()
        widget.setDecimals(decimals); widget.setRange(low, high); widget.setValue(value); widget.setSuffix(suffix)
        return widget

    def _restore(self, settings):
        particle = settings.particle
        self.span.setValue(settings.span_mm); self.samples.setValue(settings.samples)
        self.step.setValue(settings.derivative_step_mm); self.tolerance.setValue(settings.relative_tolerance * 100)
        self.radius.setValue(particle.radius_mm); self.density.setValue(particle.density_kg_m3)
        self.speed.setValue(particle.sound_speed_m_s)
        self.compressibility_mode.setCurrentIndex(int(particle.compressibility_pa_inv is not None))
        self.compressibility.setText('' if particle.compressibility_pa_inv is None else repr(particle.compressibility_pa_inv))
        self.provenance.setCurrentIndex(int(particle.provenance == 'provided'))
        self.source.setText(particle.source)
        for widget, value in zip(self.gravity, settings.gravity_m_s2):
            widget.setValue(value)

    def _update_compressibility(self):
        direct = self.compressibility_mode.currentIndex() == 1
        self.compressibility.setEnabled(direct); self.speed.setEnabled(not direct)

    def _settings(self):
        compressibility = None
        if self.compressibility_mode.currentIndex() == 1:
            try:
                compressibility = float(self.compressibility.text())
            except ValueError as exc:
                raise ValueError('압축률은 유한한 양수(1/Pa)로 입력하세요.') from exc
        particle = ParticleConfig(self.radius.value(), self.density.value(), self.speed.value(), compressibility,
                                  'provided' if self.provenance.currentIndex() else 'example', self.source.text())
        return AnalysisSettings(particle, self.span.value(), self.samples.value(), self.step.value(),
                                self.tolerance.value() / 100, tuple(widget.value() for widget in self.gravity))

    def _invalidate(self, *_):
        self.result = None
        self.export.setEnabled(False)
        self.summary.setText('입력이 변경되었습니다. 고정 위상 스냅샷으로 다시 분석하세요.')
        self.matrix.clearContents(); self.figure.clear(); self.canvas.draw_idle()

    @Slot()
    def start_analysis(self):
        if self._thread is not None:
            return
        self._invalidate()
        try:
            settings = self._settings()
        except ValueError as exc:
            self.summary.setText(f'진단 불가: {exc}')
            return
        self.settings_submitted.emit(settings.to_dict())
        self._cancellation = Event()
        self._close_after_thread = False
        self._thread = QThread(self)
        self._worker = AnalysisWorker(self.snapshot, [widget.value() for widget in self.centre], settings,
                                      self.mode_idx, self.has_taichi, self.has_pytorch, self._cancellation)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.succeeded.connect(self._on_result)
        self._worker.failed.connect(self._on_failure)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.progress.connect(self.progress.setValue)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread_done)
        self.inputs.setEnabled(False); self.calculate.setEnabled(False); self.cancel.setEnabled(True)
        self.progress.setValue(0); self.summary.setText('h, h/2, h/4에서 고정 위상·전체 복원행렬을 계산하고 있습니다.')
        self._thread.start()

    @Slot()
    def cancel_analysis(self):
        self._cancellation.set()
        self.result = None; self.export.setEnabled(False)
        self.matrix.clearContents(); self.figure.clear(); self.canvas.draw_idle()
        self.cancel.setEnabled(False)
        self.summary.setText('취소 요청 — 현재 수치 연산이 끝나는 대로 종료합니다.')

    @Slot(object)
    def _on_result(self, result):
        if self._cancellation.is_set() or self._close_after_thread:
            return
        self.result = result
        for row in range(3):
            for column in range(3):
                self.matrix.setItem(row, column, QTableWidgetItem(f"{result['centre_stiffness'][row, column]:.5e}"))
        state = {'restoring': '모든 고유방향에 국소 복원 부호',
                 'non_restoring': '비복원 고유방향 존재', 'unresolved': '복원 부호 판정 보류'}[result['restoring']['status']]
        errors = max(max(row['force_relative_change'], row['stiffness_relative_change']) for row in result['convergence'])
        particle_note = '예시·가정 물성' if result['settings']['particle']['provenance'] == 'example' else '제공 물성'
        self.summary.setText(
            f"{state} · {particle_note} · ka={result['ka']:.3g} · 수렴 {'통과' if result['converged'] else '미통과'} "
            f"(최대 변화 {errors * 100:.3g}%)\n"
            f"K=−∂F/∂x [N*/m], 고유값 {np.array2string(result['restoring']['eigenvalues'], precision=3)} · "
            f"질량 {result['mass_kg']:.4g}kg · 중력 {np.array2string(result['gravity_force_N'], precision=3)}N\n"
            f"명목 중심 잔류력 F+mg {np.array2string(result['conditional_centre_residual'], precision=3)} N* · "
            f"중력 평형 판정 보류: 음압 미보정. 복소 합산: {result['backend']['backend']}."
            + (' 작은 입자 진단 범위(ka≤0.3)를 벗어났습니다.' if not result['model_in_range'] else ''))
        if result['backend']['fallback_reason']:
            self.summary.setText(self.summary.text() + f" CPU 전환: {result['backend']['fallback_reason']}")
        self.export.setEnabled(True)
        self.draw_result()

    @Slot(str)
    def _on_failure(self, message):
        self.summary.setText(f'진단 불가: {message}'); self.result = None; self.export.setEnabled(False)

    @Slot()
    def _on_cancelled(self):
        self.summary.setText('계산 취소 — 분석 결과를 생성하지 않았습니다.')
        self.result = None; self.export.setEnabled(False)

    @Slot()
    def _thread_done(self):
        thread = self._thread
        self._thread = self._worker = None
        thread.deleteLater()
        self.inputs.setEnabled(True); self.calculate.setEnabled(True); self.cancel.setEnabled(False)
        if self._close_after_thread:
            self.close()

    def draw_result(self, *_):
        if self.result is None:
            return
        self.figure.clear()
        self.figure.suptitle('Fixed drive, uncalibrated pressure; N* / J* assume 1 relative unit = 1 Pa', fontsize=10)
        result, kind = self.result, self.plot_kind.currentIndex()
        for axis, name in enumerate('XYZ'):
            plot = self.figure.add_subplot(1, 3, axis + 1)
            x = result['offsets_mm']
            if kind == 0:
                plot.plot(x, result['acoustic_force'][axis, :, axis], label=f'Acoustic F{name}')
                if result['gravity_force_N'][axis] != 0:
                    plot.plot(x, result['conditional_total_force'][axis, :, axis], '--', label='With gravity (assumed scale)')
                if self.coupled.isChecked():
                    for component in range(3):
                        if component != axis:
                            plot.plot(x, result['acoustic_force'][axis, :, component], ':', label=f'F{"XYZ"[component]}')
                plot.set_ylabel('Force (N*)'); plot.legend(fontsize=7)
            elif kind == 1:
                plot.plot(x, result['pressure_magnitude'][axis]); plot.set_ylabel('Pressure (relative)')
            elif kind == 2:
                plot.plot(x, result['potential'][axis]); plot.set_ylabel("Gor'kov potential (J*)")
            else:
                plot.plot(x, result['stiffness_diagonal'][axis, :, axis]); plot.set_ylabel('Restoring K (N*/m)')
            plot.axhline(0., color='grey', linewidth=.7); plot.axvline(0., color='grey', linewidth=.7)
            plot.set_title(f'{name} displacement, fixed drive'); plot.set_xlabel('Displacement (mm)'); plot.grid(alpha=.2)
        self.canvas.draw_idle()

    @Slot()
    def export_result(self):
        if self.result is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, '고정 위상 분석 저장', '', 'Analysis JSON (*.json)')
        if path:
            try:
                Path(path).write_text(json.dumps(json_result(self.result), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
            except (OSError, ValueError) as exc:
                self.summary.setText(f'저장 실패: {exc}')

    def reject(self):
        # Escape and the titlebar must both cancel before destroying a running QThread.
        if self._thread is not None:
            self._close_after_thread = True
            self.cancel_analysis()
        else:
            super().reject()

    def closeEvent(self, event):
        if self._thread is not None:
            self._close_after_thread = True
            self.cancel_analysis()
            event.ignore()
        else:
            super().closeEvent(event)
