"""Shared model controls and actor-to-engine adapter for the existing window."""
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QLabel

from acousticstudio.field_model import FieldConfig
from acousticstudio.geometry_scene import transducer_acoustic_inputs


class AcousticModelControls(QGroupBox):
    def __init__(self, changed):
        super().__init__('공통 음향 모델')
        form = QFormLayout(self)
        self.model = QComboBox()
        for label, key in [('무지향 점음원', 'point_source'), ('Ultraino sinc', 'ultraino_sinc'),
                           ('원형 피스톤 (Bessel)', 'circular_piston')]:
            self.model.addItem(label, key)
        form.addRow('방향성:', self.model)
        self.frequency = self._spin(1., 1e6, 40000., 0, ' Hz')
        self.speed = self._spin(10., 2000., 343., 3, ' m/s')
        self.density = self._spin(.01, 10000., 1.204084759, 9, ' kg/m³')
        self.radius = self._spin(0., 1000., 0., 4, ' mm')
        self.radius.setSpecialValueText('미확정')
        self.radius.setToolTip('미확정 채널에 적용할 유효 음향 개구 반경입니다. CAD 외경 반경과 다릅니다.')
        self.strength = self._spin(.000001, 1e6, 1., 6, '')
        for label, widget in [('주파수:', self.frequency), ('매질 음속:', self.speed),
                              ('매질 밀도:', self.density), ('유효 개구 반경:', self.radius),
                              ('상대 음압 스케일:', self.strength)]:
            form.addRow(label, widget)
        self.info = QLabel('음압은 미보정 상대값입니다. 반사·차폐·후면 감쇠는 포함하지 않습니다.')
        self.info.setWordWrap(True)
        form.addRow(self.info)
        self.backend = QLabel('')
        self.backend.setWordWrap(True)
        form.addRow(self.backend)
        self._minimum_distance = FieldConfig().min_distance_m
        self.model.currentIndexChanged.connect(changed)
        for widget in (self.frequency, self.speed, self.density, self.radius, self.strength):
            widget.valueChanged.connect(changed)

    @staticmethod
    def _spin(low, high, value, decimals, suffix):
        widget = QDoubleSpinBox()
        widget.setDecimals(decimals)
        widget.setRange(low, high)
        widget.setValue(value)
        widget.setSuffix(suffix)
        return widget

    def config(self):
        return FieldConfig(model=self.model.currentData(), frequency_hz=self.frequency.value(),
                           sound_speed_m_s=self.speed.value(), density_kg_m3=self.density.value(),
                           source_strength=self.strength.value(),
                           aperture_radius_mm=self.radius.value() or None,
                           min_distance_m=self._minimum_distance)

    def restore(self, config):
        widgets = [self.model, self.frequency, self.speed, self.density, self.radius, self.strength]
        values = [self.model.findData(config.model), config.frequency_hz, config.sound_speed_m_s,
                  config.density_kg_m3, config.aperture_radius_mm or 0., config.source_strength]
        self.validate_config(config)
        blocked = [widget.blockSignals(True) for widget in widgets]
        try:
            self.model.setCurrentIndex(values[0])
            for widget, value in zip(widgets[1:], values[1:]):
                widget.setValue(value)
            self._minimum_distance = config.min_distance_m
        finally:
            for widget, previous in zip(widgets, blocked):
                widget.blockSignals(previous)
        self.backend.clear()

    def validate_config(self, config):
        values = [config.frequency_hz, config.sound_speed_m_s, config.density_kg_m3,
                  config.aperture_radius_mm or 0., config.source_strength]
        for widget, value in zip((self.frequency, self.speed, self.density, self.radius, self.strength), values):
            if not widget.minimum() <= value <= widget.maximum():
                raise ValueError('저장된 음향 설정이 화면 입력 범위를 벗어났습니다.')


def field_kwargs(window):
    controls = getattr(window, 'acoustic_model_controls', None)
    if controls is None:
        return {}
    normals, radii = transducer_acoustic_inputs(window.transducer_actors)
    return dict(field_config=controls.config(), normals=normals, aperture_radii_mm=radii)


def show_backend(window):
    controls = getattr(window, 'acoustic_model_controls', None)
    status = getattr(window.phase_engine, 'last_backend', None)
    if controls is not None and status:
        text = f"복소 합산: {status['backend']} · 전파 모델: CPU"
        if status['fallback_reason']:
            text += f"\nCPU 전환: {status['fallback_reason']}"
        controls.backend.setText(text)


def model_changed(window):
    window._field_model_dirty = True
    window.acoustic_model_controls.backend.setText('음향 설정 변경 — 위상을 다시 계산하세요.')
    for actor in getattr(window, 'field_actors', []):
        actor.SetVisibility(False)
    for grid, actor in getattr(window, '_cached_field_grids', {}).values():
        actor.SetVisibility(False)
    if hasattr(window, 'transducer_actors'):
        window.push_state()
        window.plotter.render()


def model_failed(window, error):
    window._field_model_dirty = True
    controls = getattr(window, 'acoustic_model_controls', None)
    if controls is not None:
        controls.backend.setText(f'계산 불가: {error}')
    for actor in getattr(window, 'field_actors', []):
        actor.SetVisibility(False)
    for grid, actor in getattr(window, '_cached_field_grids', {}).values():
        actor.SetVisibility(False)
    window.statusBar().showMessage(f'음향 계산 불가: {error}', 8000)
    window.plotter.render()
