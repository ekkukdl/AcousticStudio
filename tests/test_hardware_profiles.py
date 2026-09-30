"""Regression tests for supported board wire formats.

They exercise only byte encoding.  They do not represent a physical board or
an acoustic-levitation measurement.
"""

from math import pi

import pytest

from acousticstudio.hardware import BOARD_PROFILES, HardwareController, encode_phase_frame, phases_to_steps


def test_phase_quantisation_wraps_two_pi_without_using_off_code():
    assert phases_to_steps([0.0, 2.0 * pi, -2.0 * pi, 2.0 * pi - 1e-12]) == [0, 0, 0, 0]


def test_ultraino_simplefpga_frame_is_complete_256_channel_transaction():
    frame = encode_phase_frame(BOARD_PROFILES["ultraino_simplefpga_256"], [0.0] * 256)
    assert len(frame) == 258
    assert frame[0] == 0xFE
    assert frame[-1] == 0xFD
    assert set(frame[1:-1]) == {0}


def test_sonicsurface_two_board_frame_includes_reference_board_tags():
    phases = [2.0 * pi * index / 32 for index in range(256)]
    frame = encode_phase_frame(BOARD_PROFILES["sonicsurface_fpga_two_board"], phases)
    assert len(frame) == 260
    assert frame[:2] == bytes((0xFE, 0xC0))
    assert frame[130] == 0xC1
    assert frame[-1] == 0xFD
    assert frame[2] == 0
    assert frame[33] == 31


def test_sonicsurface_esp32_command_has_a_final_separator_for_last_phase():
    frame = encode_phase_frame(BOARD_PROFILES["sonicsurface_esp32_command"], [0.0] * 256)
    assert frame.startswith(b"phases=")
    assert frame.endswith(b",\n")
    assert frame.count(b",") == 256


def test_fixed_profile_rejects_partial_frame():
    with pytest.raises(ValueError, match="256채널"):
        encode_phase_frame(BOARD_PROFILES["sonicsurface_fpga_256"], [0.0] * 255)


def test_controller_writes_a_complete_profile_frame_to_fake_serial():
    class FakeSerial:
        def __init__(self):
            self.frames = []
            self.flushed = False

        def write(self, frame):
            self.frames.append(frame)
            return len(frame)

        def flush(self):
            self.flushed = True

    controller = HardwareController()
    controller.set_board_profile("ultraino_simplefpga_256")
    fake_serial = FakeSerial()
    controller.serial_port = fake_serial

    frame = controller.send_phases([0.0] * 256)

    assert fake_serial.frames == [frame]
    assert fake_serial.flushed
    assert frame == bytes((0xFE,)) + bytes(256) + bytes((0xFD,))
