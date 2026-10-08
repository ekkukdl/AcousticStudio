# -*- coding: utf-8 -*-
"""Hardware controller module for AcousticStudio.

Manages serial port communication with ultrasonic transducer boards.
Communicates state changes through Qt signals rather than direct UI access.
"""

from dataclasses import dataclass
from math import floor, isfinite, pi
from typing import Iterable
from time import monotonic, perf_counter
from math import ceil

import serial
import serial.tools.list_ports
from PySide6.QtCore import QObject, QTimer, QThread, Signal
from acousticstudio.calibration import validate_active, validate_mapping


@dataclass(frozen=True)
class BoardProfile:
    """A documented on-wire protocol for a supported phased-array board.

    ``channel_count`` is intentionally strict for real board profiles: silently
    sending a partial 256-channel frame can leave a previously driven channel
    active.  The legacy profile is retained for small experimental arrays.
    """

    key: str
    label: str
    channel_count: int | None
    baud_rate: int
    transport: str
    source: str
    off_code: int | None = None
    rounding: str = 'ties_even'


BOARD_PROFILES = {
    "legacy_phase32": BoardProfile(
        "legacy_phase32", "Legacy Phase32 (0xFE … 0xFD)", None, 115200,
        "phase32_frame", "AcousticStudio existing packet format",
    ),
    "ultraino_simplefpga_256": BoardProfile(
        "ultraino_simplefpga_256", "Ultraino SimpleFPGA 256", 256, 230400,
        "phase32_frame", "Ultraino SimpleFPGA.java", 32, 'half_up',
    ),
    "sonicsurface_fpga_256": BoardProfile(
        "sonicsurface_fpga_256", "SonicSurface FPGA 256 (direct)", 256, 230400,
        "phase32_frame", "SonicSurface TestHoloConnection4.ino", 32, 'half_up',
    ),
    "sonicsurface_fpga_two_board": BoardProfile(
        "sonicsurface_fpga_two_board", "SonicSurface FPGA 256 (board tags)", 256, 230400,
        "sonicsurface_two_board", "SonicSurface CommandSenderESP32.ino", 32, 'half_up',
    ),
    "sonicsurface_esp32_command": BoardProfile(
        "sonicsurface_esp32_command", "SonicSurface ESP32 CommandSender", 256, 230400,
        "sonicsurface_ascii", "SonicSurface CommandSenderESP32.ino", 32, 'half_up',
    ),
}


def phases_to_steps(phases_radians: Iterable[float], steps: int = 32, rounding: str = 'ties_even') -> list[int]:
    """Quantise radians using an explicit client rounding policy, wrapping at 2π.

    Firmware uses 0–31 while 32 is its *off* value.  Modulo before rounding
    avoids incorrectly turning a phase near 2π into the off code.
    """
    if type(steps) is not int or not 1 <= steps <= 255 or rounding not in ('ties_even', 'half_up'):
        raise ValueError('위상 분할 수 또는 반올림 방식이 잘못되었습니다.')
    values: list[int] = []
    for phase in phases_radians:
        value = float(phase)
        if not isfinite(value):
            raise ValueError("위상 값에는 NaN 또는 무한대를 사용할 수 없습니다.")
        scaled = ((value % (2.0 * pi)) / (2.0 * pi)) * steps
        values.append((floor(scaled + .5) if rounding == 'half_up' else int(round(scaled))) % steps)
    return values


def encode_phase_frame(profile: BoardProfile, phases_radians: Iterable[float], active=None) -> bytes:
    """Encode one complete, committed phase frame for *profile*."""
    phase_steps = phases_to_steps(phases_radians, rounding=profile.rounding)
    if not phase_steps:
        raise ValueError("전송할 트랜스듀서 위상이 없습니다.")
    if profile.channel_count is not None and len(phase_steps) != profile.channel_count:
        raise ValueError(
            f"{profile.label} 프로파일은 정확히 {profile.channel_count}채널을 요구하지만 "
            f"현재 배열은 {len(phase_steps)}채널입니다."
        )

    if active is not None:
        enabled = validate_active(active, len(phase_steps))
        if not all(enabled) and profile.off_code is None:
            raise ValueError(f'{profile.label} 프로파일은 OFF를 지원하지 않습니다.')
        phase_steps = [step if enabled[index] else profile.off_code for index, step in enumerate(phase_steps)]
    return encode_steps(profile, phase_steps)


def encode_steps(profile, phase_steps):
    """Internal encoder for validated physical-order Phase32/OFF values."""
    payload = bytes(phase_steps)
    if profile.transport == "phase32_frame":
        return bytes((0xFE,)) + payload + bytes((0xFD,))
    if profile.transport == "sonicsurface_two_board":
        # The ESP32 reference firmware forwards each 128-channel half with
        # board-enable tags 0xC0 and 0xC1, then commits with 0xFD.
        return bytes((0xFE, 0xC0)) + payload[:128] + bytes((0xC1,)) + payload[128:] + bytes((0xFD,))
    if profile.transport == "sonicsurface_ascii":
        # CommandSenderESP32 parses values only when it encounters a separator;
        # retain the final comma so the 256th value is committed as well.
        return b"phases=" + b",".join(str(step).encode("ascii") for step in phase_steps) + b",\n"
    raise ValueError(f"지원하지 않는 전송 형식: {profile.transport}")


class FrameWriter(QThread):
    """A single bounded port write; controller state is changed on the GUI thread."""
    def __init__(self, port, frame, parent=None):
        super().__init__(parent)
        self.port, self.frame = port, frame
        self.error = None
        self.elapsed_seconds = 0.

    def run(self):
        started = perf_counter()
        try:
            written = self.port.write(self.frame)
            if written != len(self.frame):
                raise serial.SerialTimeoutException(f'부분 전송: {written}/{len(self.frame)} bytes')
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.elapsed_seconds = perf_counter() - started


class HardwareController(QObject):
    """Manages serial hardware connection and packet transmission.

    Signals:
        connected(str): Emitted when a serial connection is established.
            The argument is the port name (e.g., 'COM3').
        disconnected(str): Emitted when the connection is lost or closed.
            The argument is a reason/message string.
        send_failed(str): Emitted when a packet write fails.
            The argument is the error message.
    """

    connected = Signal(str)       # port name
    disconnected = Signal(str)    # reason message
    send_failed = Signal(str)     # error message
    sender_idle = Signal()
    frame_written = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.serial_port = None
        self.board_profile = BOARD_PROFILES["legacy_phase32"]
        self.channel_map: list[int] | None = None
        self.phase_offsets: list[float] | None = None
        self.active_channels: list[bool] | None = None
        self.write_timeout_s = .1
        self._writer = None
        self._pending_frame = None
        self._next_write = 0.
        self.send_statistics = dict(submitted=0, replaced=0, written=0, failed=0, last_write_ms=0.)
        self._send_timer = QTimer(self)
        self._send_timer.setSingleShot(True)
        self._send_timer.timeout.connect(self._start_queued_write)

        # Timer-based health check (1 s interval)
        self.hw_health_timer = QTimer(self)
        self.hw_health_timer.setInterval(1000)
        self.hw_health_timer.timeout.connect(self.check_health)

    # ------------------------------------------------------------------
    # Port enumeration
    # ------------------------------------------------------------------
    def refresh_ports(self) -> list[str]:
        """Refresh and return the list of available serial port device names.

        Returns:
            A list of port device strings (e.g., ``['COM3', 'COM4']``).
            An empty list when no ports are found.
        """
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    def set_board_profile(self, profile_key: str) -> BoardProfile:
        """Select a protocol before connecting to a board."""
        if self.serial_port is not None:
            raise RuntimeError("보드 연결을 해제한 뒤 프로파일을 변경하세요.")
        try:
            self.board_profile = BOARD_PROFILES[profile_key]
        except KeyError as exc:
            raise ValueError(f"알 수 없는 보드 프로파일: {profile_key}") from exc
        self.channel_map = None
        self.phase_offsets = None
        self.active_channels = None
        return self.board_profile

    def set_channel_map(self, channel_map: Iterable[int]) -> None:
        """Set a validated physical-frame-index → software-channel map.

        For example, ``map[physical_channel] = software_channel``. This is the
        hook used by a future field-mapping calibration workflow.
        It is only meaningful for a fixed-size board profile.
        """
        count = self.board_profile.channel_count
        if count is None:
            raise ValueError("Legacy 프로파일에는 고정 채널 맵을 설정할 수 없습니다.")
        self.channel_map = list(validate_mapping(channel_map, count))

    def set_active_channels(self, enabled):
        values = list(enabled)
        count = self.board_profile.channel_count or len(values)
        self.active_channels = list(validate_active(values, count))

    def settings(self):
        return dict(board_profile=self.board_profile.key, channel_map=self.channel_map,
                    phase_offsets_rad=self.phase_offsets, active_channels=self.active_channels)

    def restore_settings(self, values):
        """Validate a whole configuration before replacing any controller state."""
        if not isinstance(values, dict) or set(values) - {'board_profile', 'channel_map', 'phase_offsets_rad', 'active_channels'}:
            raise ValueError('보드 설정 필드가 잘못되었습니다.')
        candidate = HardwareController()
        candidate.set_board_profile(values.get('board_profile', 'legacy_phase32'))
        if values.get('channel_map') is not None:
            candidate.set_channel_map(values['channel_map'])
        if values.get('phase_offsets_rad') is not None:
            candidate.set_phase_offsets(values['phase_offsets_rad'])
        if values.get('active_channels') is not None:
            candidate.set_active_channels(values['active_channels'])
        if self.is_connected() and candidate.settings() != self.settings():
            raise RuntimeError('보드 연결을 해제한 뒤 보정/맵/프로파일을 변경하세요.')
        self.board_profile = candidate.board_profile
        self.channel_map, self.phase_offsets, self.active_channels = candidate.channel_map, candidate.phase_offsets, candidate.active_channels

    def set_phase_offsets(self, offsets_radians: Iterable[float]) -> None:
        """Set additive calibration offsets in software channel order.

        This in-memory hook does not constitute a measured calibration. Profile
        changes clear it, just like the channel map.
        """
        offsets = [float(value) for value in offsets_radians]
        count = self.board_profile.channel_count
        if not offsets or not all(isfinite(value) for value in offsets):
            raise ValueError("위상 보정값은 비어 있지 않은 유한한 배열이어야 합니다.")
        if count is not None and len(offsets) != count:
            raise ValueError(f"위상 보정값은 {count}채널과 일치해야 합니다.")
        self.phase_offsets = offsets

    def prepare_phases(self, phases_radians: Iterable[float]) -> list[float]:
        """Validate software phases, correct once, then map to physical order."""
        phases = [float(value) for value in phases_radians]
        count = self.board_profile.channel_count
        if not phases or not all(isfinite(value) for value in phases):
            raise ValueError("위상 배열은 비어 있지 않은 유한한 배열이어야 합니다.")
        if count is not None and len(phases) != count:
            raise ValueError(f"{self.board_profile.label} 프로파일은 정확히 {count}채널을 요구합니다.")
        if self.phase_offsets is not None:
            if len(self.phase_offsets) != len(phases):
                raise ValueError("위상 보정값과 송신기 채널 수가 일치하지 않습니다.")
            phases = [phase + offset for phase, offset in zip(phases, self.phase_offsets)]
        if self.channel_map is not None:
            phases = [phases[source] for source in self.channel_map]
        return phases

    def prepare_phase_steps(self, phases_radians: Iterable[float], active=None) -> list[int]:
        """Return the same corrected, mapped phase steps used on the wire."""
        corrected = self.prepare_phases(phases_radians)
        enabled = [True] * len(corrected) if active is None else list(validate_active(active, len(corrected)))
        if self.active_channels is not None:
            mask = validate_active(self.active_channels, len(corrected))
            enabled = [first and second for first, second in zip(enabled, mask)]
        if self.channel_map is not None:
            enabled = [enabled[source] for source in self.channel_map]
        if not all(enabled) and self.board_profile.off_code is None:
            raise ValueError(f'{self.board_profile.label} 프로파일은 OFF를 지원하지 않습니다.')
        steps = phases_to_steps(corrected, rounding=self.board_profile.rounding)
        return [step if enabled[index] else self.board_profile.off_code for index, step in enumerate(steps)]

    def build_phase_frame(self, phases_radians: Iterable[float], active=None) -> bytes:
        """Build a profile frame without touching a serial port."""
        return encode_steps(self.board_profile, self.prepare_phase_steps(phases_radians, active))

    def build_test_frame(self, software_channel=None, phase_rad=0., count=None):
        count = self.board_profile.channel_count or count
        if type(count) is not int or count <= 0:
            raise ValueError('테스트 프레임에는 채널 수가 필요합니다.')
        if software_channel is not None and (type(software_channel) is not int or not 0 <= software_channel < count):
            raise ValueError('테스트할 소프트웨어 채널이 범위를 벗어났습니다.')
        active = [index == software_channel for index in range(count)]
        if software_channel is not None and self.active_channels is not None and not self.active_channels[software_channel]:
            raise ValueError('비활성 보정 채널은 활성화한 뒤 테스트하세요.')
        return self.build_phase_frame([phase_rad] * count, active)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def connect(self, port: str, baud: int) -> bool:
        """Open a serial connection on *port* at *baud* rate.

        If a connection is already open it is left untouched and the
        method returns ``True`` immediately.

        Returns:
            ``True`` on success, ``False`` on failure.
        """
        if self.serial_port is not None:
            return True

        try:
            self.serial_port = serial.Serial(port, baud, timeout=1, write_timeout=self.write_timeout_s)
            self.hw_health_timer.start()
            self.connected.emit(port)
            return True
        except Exception as e:
            error_msg = str(e)
            if "could not open port" in error_msg:
                clean_msg = (
                    f"포트({port})를 열 수 없습니다.\n\n"
                    "장치가 올바르게 연결되어 있는지, "
                    "또는 다른 프로그램에서 사용 중이지 않은지 확인해 주세요."
                )
            else:
                clean_msg = (
                    "하드웨어 연결 중 예기치 않은 오류가 발생했습니다.\n\n"
                    f"상세 내용: {error_msg}"
                )
            self.send_failed.emit(clean_msg)
            return False

    def disconnect(self) -> None:
        """Close the current serial connection (if any)."""
        self.cancel_queued_frames()
        if self.serial_port is not None:
            self.hw_health_timer.stop()
            try:
                self.serial_port.close()
            except:
                pass
            self.serial_port = None
            self.disconnected.emit("사용자에 의해 연결이 해제되었습니다.")

    def is_connected(self) -> bool:
        """Return ``True`` when a serial port is currently open."""
        return self.serial_port is not None

    # ------------------------------------------------------------------
    # Packet transmission
    # ------------------------------------------------------------------
    def send_packet(self, packet_bytes: bytes) -> bool:
        """Write raw *packet_bytes* to the serial port.

        Returns False if disconnected or failed, True for a complete local write.
        On write failure :pyattr:`send_failed` is emitted and the
        connection is torn down via :pymeth:`_handle_disconnect`. No board ACK is implied.
        """
        if self.serial_port is None:
            return False
        self.cancel_queued_frames()
        if self.sender_busy:
            self.send_failed.emit('이전 프레임을 전송 중입니다. 완료 후 다시 전송하세요.')
            return False

        try:
            written = self.serial_port.write(packet_bytes)
            if written != len(packet_bytes):
                raise serial.SerialTimeoutException(
                    f"부분 전송: {written}/{len(packet_bytes)} bytes"
                )
            # Serial.flush() waits for the driver indefinitely on some platforms.
            # write_timeout bounds this write; success only means local acceptance.
            return True
        except Exception as e:
            print(f"HW Send Error: {e}")
            self.send_failed.emit(f"보드 프레임 전송 실패: {e}")
            self._handle_disconnect()
            return False

    def send_phases(self, phases_radians: Iterable[float], active=None) -> bytes:
        """Map, frame and transmit radians using the selected board protocol.

        Returns the transmitted frame to allow deterministic fake-transport
        tests.  It does not claim that a physical board accepted the frame.
        """
        frame = self.build_phase_frame(phases_radians, active)
        self.send_packet(frame)
        return frame

    @property
    def sender_busy(self):
        return self._writer is not None

    def cancel_queued_frames(self):
        self._pending_frame = None
        self._send_timer.stop()

    def queue_phases(self, phases_radians, active=None):
        frame = self.build_phase_frame(phases_radians, active)
        if not self.is_connected():
            return False
        self.send_statistics['submitted'] += 1
        if self._pending_frame is not None:
            self.send_statistics['replaced'] += 1
        self._pending_frame = (self.serial_port, frame)
        self._start_queued_write()
        return True

    def _start_queued_write(self):
        if self.sender_busy or self._pending_frame is None:
            return
        port, frame = self._pending_frame
        if port is not self.serial_port:
            self.cancel_queued_frames()
            return
        remaining = self._next_write - monotonic()
        if remaining > 0:
            self._send_timer.start(max(1, ceil(remaining * 1000)))
            return
        self._pending_frame = None
        baud = getattr(port, 'baudrate', self.board_profile.baud_rate)
        # 8N1 takes ten wire bits per byte. Default update ceiling is 30 Hz.
        self._next_write = monotonic() + max(1 / 30, len(frame) * 10 / baud)
        self._writer = FrameWriter(port, frame, self)
        self._writer.finished.connect(self._queued_write_done)
        self._writer.start()

    def _queued_write_done(self):
        writer, self._writer = self._writer, None
        self.send_statistics['last_write_ms'] = writer.elapsed_seconds * 1000
        if writer.port is self.serial_port:
            if writer.error:
                self.send_statistics['failed'] += 1
                self.cancel_queued_frames()
                self._handle_disconnect()
                self.send_failed.emit(f'보드 프레임 전송 실패: {writer.error}')
            else:
                self.send_statistics['written'] += 1
                self.frame_written.emit(writer.frame)
        writer.deleteLater()
        self._start_queued_write()
        if not self.sender_busy and self._pending_frame is None:
            self.sender_idle.emit()

    # ------------------------------------------------------------------
    # Health monitoring
    # ------------------------------------------------------------------
    def check_health(self) -> None:
        """Check whether the serial connection is still alive.

        Called periodically by :pyattr:`hw_health_timer`.  If the port
        has disappeared or become unresponsive, triggers a disconnect.
        """
        if self.serial_port is not None:
            try:
                _ = self.serial_port.in_waiting
            except Exception:
                self._handle_disconnect()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _handle_disconnect(self) -> None:
        """Tear down the serial connection after an unexpected failure."""
        self.cancel_queued_frames()
        if self.serial_port is not None:
            self.hw_health_timer.stop()
            try:
                self.serial_port.close()
            except:
                pass
            self.serial_port = None
            self.disconnected.emit(
                "보드와의 연결이 끊어졌습니다.\n"
                "장치가 분리되었거나 통신 오류가 발생했습니다."
            )
