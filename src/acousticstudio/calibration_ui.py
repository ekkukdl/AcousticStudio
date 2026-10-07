"""Manual calibration editor and offline channel-test frame exporter."""
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout,
                              QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
                              QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout)

from acousticstudio.calibration import Calibration, CalibrationRevision, load_candidate_map, utc_now
from acousticstudio.hardware import HardwareController


class CalibrationDialog(QDialog):
    applied = Signal(object)

    def __init__(self, count, profile, signature, current=None, candidate_path=None, parent=None):
        super().__init__(parent)
        self.count, self.profile, self.signature = count, profile, signature
        self.current, self.candidate_path = current, candidate_path
        self.setWindowTitle('채널 보정·맵 및 OFF 프레임')
        self.resize(1020, 820)
        layout = QVBoxLayout(self)
        info = QLabel(f'{count}채널 · {profile.label}\n'
                      '위상 보정은 명령에 더합니다. 측정 위상 오차가 +이면 보정은 −입니다.\n'
                      '이득은 고정 상대 음원 이득입니다. 절대 음압·가변 구동 진폭 보정은 아닙니다.\n'
                      '후보 채널 맵은 배선 실측 완료가 아닙니다. 파일 저장은 보드로 송신하지 않습니다.')
        info.setWordWrap(True); layout.addWidget(info)
        form = QFormLayout()
        self.identifier = QLineEdit()
        self.provenance = QComboBox(); self.provenance.addItems(['수동 미검증', '실측 조건 기록'])
        self.firmware = QLineEdit(); self.wiring = QLineEdit()
        self.conditions = QPlainTextEdit(); self.conditions.setMaximumHeight(70)
        for label, widget in [('보정 ID:', self.identifier), ('출처:', self.provenance),
                              ('펌웨어 ID:', self.firmware), ('배선 버전:', self.wiring),
                              ('측정 조건·설명:', self.conditions)]:
            form.addRow(label, widget)
        layout.addLayout(form)
        self.map_info = QLabel(); self.map_info.setWordWrap(True); layout.addWidget(self.map_info)
        buttons = QHBoxLayout()
        self.load = QPushButton('보정 JSON 읽기'); self.save = QPushButton('보정 JSON 저장')
        self.candidate = QPushButton('Creo 후보 맵 읽기'); self.identity = QPushButton('항등 맵')
        for button in (self.load, self.save, self.candidate, self.identity):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.table = QTableWidget(count, 5)
        self.table.setHorizontalHeaderLabels(['소프트웨어 채널', '명령 보정(rad)', '상대 이득', '활성', 'map[물리 행]=SW'])
        self.table.setColumnWidth(0, 150); self.table.setColumnWidth(1, 175)
        self.table.setColumnWidth(2, 145); self.table.setColumnWidth(3, 70); self.table.setColumnWidth(4, 165)
        for index in range(count):
            item = QTableWidgetItem(str(index)); item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(index, 0, item)
            offset = QDoubleSpinBox(); offset.setDecimals(10); offset.setRange(-1e6, 1e6)
            gain = QDoubleSpinBox(); gain.setDecimals(8); gain.setRange(0., 1e6)
            enabled = QTableWidgetItem(); enabled.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            self.table.setItem(index, 3, enabled)
            mapping = QSpinBox(); mapping.setRange(0, count - 1)
            self.table.setCellWidget(index, 1, offset); self.table.setCellWidget(index, 2, gain)
            self.table.setCellWidget(index, 4, mapping)
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        self.apply = QPushButton('보정 적용'); self.clear = QPushButton('보정 제거')
        actions.addWidget(self.apply); actions.addWidget(self.clear)
        self.channel = QSpinBox(); self.channel.setRange(0, count - 1)
        actions.addWidget(QLabel('테스트 SW 채널:')); actions.addWidget(self.channel)
        self.single_file = QPushButton('1채널 프레임 저장'); self.off_file = QPushButton('전체 OFF 프레임 저장')
        actions.addWidget(self.single_file); actions.addWidget(self.off_file)
        layout.addLayout(actions)
        self.status = QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.restore(current or Calibration(str(uuid4()), profile.key, signature,
                                           (0.,) * count, (1.,) * count, (True,) * count, utc_now()))
        for index in range(count):
            self.table.cellWidget(index, 4).valueChanged.connect(self.manual_map)
        self.load.clicked.connect(self.load_json); self.save.clicked.connect(self.save_json)
        self.candidate.clicked.connect(self.load_candidate); self.identity.clicked.connect(self.identity_map)
        self.apply.clicked.connect(self.apply_values); self.clear.clicked.connect(lambda: self.applied.emit(None))
        self.single_file.clicked.connect(lambda: self.save_test(self.channel.value()))
        self.off_file.clicked.connect(lambda: self.save_test(None))

    def restore(self, calibration):
        calibration.validate_context(self.count, self.profile.key, self.signature)
        for offset, gain in zip(calibration.phase_offsets_rad, calibration.source_gains):
            if abs(offset) > 1e6 or gain > 1e6:
                raise ValueError('보정 값이 화면 입력 범위를 벗어났습니다.')
        self.identifier.setText(calibration.calibration_id)
        self.provenance.setCurrentIndex(int(calibration.provenance == 'measured'))
        self.firmware.setText(calibration.firmware_id); self.wiring.setText(calibration.wiring_revision)
        self.conditions.setPlainText(calibration.measurement_conditions)
        mapping = calibration.channel_map or tuple(range(self.count))
        for index in range(self.count):
            self.table.cellWidget(index, 1).setValue(calibration.phase_offsets_rad[index])
            self.table.cellWidget(index, 2).setValue(calibration.source_gains[index])
            self.table.item(index, 3).setCheckState(Qt.Checked if calibration.enabled[index] else Qt.Unchecked)
            widget = self.table.cellWidget(index, 4)
            blocked = widget.blockSignals(True); widget.setValue(mapping[index]); widget.blockSignals(blocked)
        self.base = calibration
        self.mapping_status, self.mapping_source, self.mapping_sha256 = (
            calibration.mapping_status, calibration.mapping_source, calibration.mapping_sha256)
        self.update_map_info()

    def update_map_info(self):
        self.map_info.setText(f'맵 상태: {self.mapping_status} · physical_frame_channel → software_channel\n{self.mapping_source}')

    def manual_map(self, *_):
        self.mapping_status, self.mapping_source, self.mapping_sha256 = 'manual_unverified', 'manual table', ''
        self.update_map_info()

    def read_values(self, mapping_override=None):
        mapping = tuple(self.table.cellWidget(index, 4).value() for index in range(self.count)) if mapping_override is None else tuple(mapping_override)
        history = self.base.history
        if self.current is not None:
            history += (CalibrationRevision(self.current.calibration_id, utc_now(), 'manual editor revision'),)
        return Calibration(
            self.identifier.text().strip(), self.profile.key, self.signature,
            tuple(self.table.cellWidget(index, 1).value() for index in range(self.count)),
            tuple(self.table.cellWidget(index, 2).value() for index in range(self.count)),
            tuple(self.table.item(index, 3).checkState() == Qt.Checked for index in range(self.count)), utc_now(),
            channel_map=None if mapping == tuple(range(self.count)) and self.mapping_status == 'identity_unverified' else mapping,
            mapping_status=self.mapping_status, mapping_source=self.mapping_source, mapping_sha256=self.mapping_sha256,
            provenance='measured' if self.provenance.currentIndex() else 'manual_unverified',
            measurement_conditions=self.conditions.toPlainText(), firmware_id=self.firmware.text(),
            wiring_revision=self.wiring.text(), history=history)

    def run_action(self, action):
        try:
            action()
        except (ValueError, TypeError, KeyError, OSError) as exc:
            self.status.setText(f'보정 처리 불가: {exc}')

    def apply_values(self):
        self.run_action(lambda: self.applied.emit(self.read_values()))

    def save_json(self):
        path, _ = QFileDialog.getSaveFileName(self, '보정 저장', '', 'Calibration JSON (*.json)')
        if path:
            self.run_action(lambda: self.read_values().save(path))

    def load_json(self):
        path, _ = QFileDialog.getOpenFileName(self, '보정 읽기', '', 'Calibration JSON (*.json)')
        if path:
            self.run_action(lambda: self.restore(Calibration.load(path)))

    def identity_map(self):
        def restore():
            values = replace(self.read_values(range(self.count)), channel_map=None, mapping_status='identity_unverified',
                             mapping_source='', mapping_sha256='')
            self.restore(values)
        self.run_action(restore)

    def load_candidate(self):
        def load():
            if self.profile.channel_count is None:
                raise ValueError('후보 맵은 고정 채널 수 프로파일을 선택한 뒤 사용하세요.')
            path = self.candidate_path
            if path is None or not Path(path).is_file():
                path, _ = QFileDialog.getOpenFileName(self, '후보 채널 맵', '', 'Channel map JSON (*.json)')
            if not path:
                return
            mapping, source, digest = load_candidate_map(path, self.count)
            self.restore(replace(self.read_values(range(self.count)), channel_map=mapping, mapping_status='candidate_unverified',
                                 mapping_source=source, mapping_sha256=digest))
        self.run_action(load)

    def save_test(self, channel):
        def save():
            values = self.read_values()
            if self.profile.channel_count is None and values.channel_map is not None:
                raise ValueError('Legacy 프로파일은 채널 맵을 지원하지 않습니다.')
            controller = HardwareController()
            controller.restore_settings(dict(board_profile=self.profile.key, channel_map=values.channel_map,
                                             phase_offsets_rad=list(values.phase_offsets_rad), active_channels=list(values.active)))
            frame = controller.build_test_frame(channel, count=self.count)
            path, _ = QFileDialog.getSaveFileName(self, '테스트 프레임 저장', '', 'Wire frame (*.bin)')
            if path:
                Path(path).write_bytes(frame)
                self.status.setText(f'{len(frame)} bytes 저장 · 실제 송신 없음')
        self.run_action(save)
