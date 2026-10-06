# -*- coding: utf-8 -*-
"""Hardware controller module for AcousticStudio.

Manages serial port communication with ultrasonic transducer boards.
Communicates state changes through Qt signals rather than direct UI access.
"""

from dataclasses import dataclass
from math import isfinite, pi
from typing import Iterable

import serial
import serial.tools.list_ports
from PySide6.QtCore import QObject, QTimer, Signal


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


BOARD_PROFILES = {
    "legacy_phase32": BoardProfile(
        "legacy_phase32", "Legacy Phase32 (0xFE … 0xFD)", None, 115200,
        "phase32_frame", "AcousticStudio existing packet format",
    ),
    "ultraino_simplefpga_256": BoardProfile(
        "ultraino_simplefpga_256", "Ultraino SimpleFPGA 256", 256, 230400,
        "phase32_frame", "Ultraino SimpleFPGA.java",
    ),
    "sonicsurface_fpga_256": BoardProfile(
        "sonicsurface_fpga_256", "SonicSurface FPGA 256 (direct)", 256, 230400,
        "phase32_frame", "SonicSurface TestHoloConnection4.ino",
    ),
    "sonicsurface_fpga_two_board": BoardProfile(
        "sonicsurface_fpga_two_board", "SonicSurface FPGA 256 (board tags)", 256, 230400,
        "sonicsurface_two_board", "SonicSurface CommandSenderESP32.ino",
    ),
    "sonicsurface_esp32_command": BoardProfile(
        "sonicsurface_esp32_command", "SonicSurface ESP32 CommandSender", 256, 230400,
        "sonicsurface_ascii", "SonicSurface CommandSenderESP32.ino",
    ),
}


def phases_to_steps(phases_radians: Iterable[float], steps: int = 32) -> list[int]:
    """Quantise radians into firmware phase steps, wrapping at 2π.

    Firmware uses 0–31 while 32 is its *off* value.  Modulo before rounding
    avoids incorrectly turning a phase near 2π into the off code.
    """
    values: list[int] = []
    for phase in phases_radians:
        value = float(phase)
        if not isfinite(value):
            raise ValueError("위상 값에는 NaN 또는 무한대를 사용할 수 없습니다.")
        values.append(int(round(((value % (2.0 * pi)) / (2.0 * pi)) * steps)) % steps)
    return values


def encode_phase_frame(profile: BoardProfile, phases_radians: Iterable[float]) -> bytes:
    """Encode one complete, committed phase frame for *profile*."""
    phase_steps = phases_to_steps(phases_radians)
    if not phase_steps:
        raise ValueError("전송할 트랜스듀서 위상이 없습니다.")
    if profile.channel_count is not None and len(phase_steps) != profile.channel_count:
        raise ValueError(
            f"{profile.label} 프로파일은 정확히 {profile.channel_count}채널을 요구하지만 "
            f"현재 배열은 {len(phase_steps)}채널입니다."
        )

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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.serial_port = None
        self.board_profile = BOARD_PROFILES["legacy_phase32"]
        self.channel_map: list[int] | None = None
        self.phase_offsets: list[float] | None = None

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
        mapping = [int(channel) for channel in channel_map]
        if len(mapping) != count or set(mapping) != set(range(count)):
            raise ValueError(f"채널 맵은 0부터 {count - 1}까지를 한 번씩 포함해야 합니다.")
        self.channel_map = mapping

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

    def prepare_phase_steps(self, phases_radians: Iterable[float]) -> list[int]:
        """Return the same corrected, mapped phase steps used on the wire."""
        return phases_to_steps(self.prepare_phases(phases_radians))

    def build_phase_frame(self, phases_radians: Iterable[float]) -> bytes:
        """Build a profile frame without touching a serial port."""
        return encode_phase_frame(self.board_profile, self.prepare_phases(phases_radians))

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
            self.serial_port = serial.Serial(port, baud, timeout=1)
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
    def send_packet(self, packet_bytes: bytes) -> None:
        """Write raw *packet_bytes* to the serial port.

        If the port is not connected the call is silently ignored.
        On write failure :pyattr:`send_failed` is emitted and the
        connection is torn down via :pymeth:`_handle_disconnect`.
        """
        if self.serial_port is None:
            return

        try:
            written = self.serial_port.write(packet_bytes)
            if written != len(packet_bytes):
                raise serial.SerialTimeoutException(
                    f"부분 전송: {written}/{len(packet_bytes)} bytes"
                )
            self.serial_port.flush()
        except Exception as e:
            print(f"HW Send Error: {e}")
            self.send_failed.emit(f"보드 프레임 전송 실패: {e}")
            self._handle_disconnect()

    def send_phases(self, phases_radians: Iterable[float]) -> bytes:
        """Map, frame and transmit radians using the selected board protocol.

        Returns the transmitted frame to allow deterministic fake-transport
        tests.  It does not claim that a physical board accepted the frame.
        """
        frame = self.build_phase_frame(phases_radians)
        self.send_packet(frame)
        return frame

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
