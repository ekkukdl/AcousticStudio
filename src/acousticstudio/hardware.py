# -*- coding: utf-8 -*-
"""Hardware controller module for AcousticStudio.

Manages serial port communication with ultrasonic transducer boards.
Communicates state changes through Qt signals rather than direct UI access.
"""

import serial
import serial.tools.list_ports
from PySide6.QtCore import QObject, QTimer, Signal


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
            self.serial_port.write(packet_bytes)
        except Exception as e:
            print(f"HW Send Error: {e}")
            self._handle_disconnect()

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
