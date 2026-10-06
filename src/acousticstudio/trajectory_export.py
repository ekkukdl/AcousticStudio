"""Trajectory files share the live controller's correction and wire encoder."""
import csv
from pathlib import Path

import numpy as np


def save_trajectory_export(filepath, format_key, name, points, delays, phases, controller):
    """Write validated waypoint data; phases enter in software channel order.

    Binary files contain consecutive on-wire frames, without timing information.
    The explicit legacy format is the former 0xFA file container, not a board
    protocol. Header/CSV phase columns are corrected physical channel order.
    """
    if format_key not in ('header', 'csv', 'binary', 'legacy'):
        raise ValueError(f"지원하지 않는 궤적 파일 형식: {format_key}")
    points = np.asarray(points, dtype=np.float64)
    delays = np.asarray(delays, dtype=np.float64)
    phases = np.asarray(phases, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) == 0 or not np.all(np.isfinite(points)):
        raise ValueError("궤적 좌표는 비어 있지 않은 유한한 (steps, 3) 배열이어야 합니다.")
    steps = len(points)
    if delays.shape != (steps,) or not np.all(np.isfinite(delays)) or np.any(delays <= 0):
        raise ValueError("궤적 지연(ms)은 각 좌표에 대응하는 유한한 양수여야 합니다.")
    if phases.ndim != 2 or phases.shape[0] != steps:
        raise ValueError("위상 배열은 (steps, channels) 형상이어야 합니다.")

    path = Path(filepath)
    # Build every frame before opening a file, so invalid channels cannot leave
    # an empty/partially generated export behind.
    if format_key == 'binary':
        frames = [controller.build_phase_frame(row) for row in phases]
        path.write_bytes(b''.join(frames))
        return path

    phase_steps = [controller.prepare_phase_steps(row) for row in phases]
    if format_key == 'legacy':
        path.write_bytes(b''.join(b'\xfa' + bytes(row) + b'\xfd' for row in phase_steps))
        return path

    num_tx = len(phase_steps[0])
    profile = controller.board_profile.key
    if format_key == 'header':
        rounded_delays = np.rint(delays)
        if np.any(rounded_delays < 1) or np.any(rounded_delays > 65535):
            raise ValueError("C 헤더의 지연은 반올림 후 uint16_t 범위(1–65535ms)여야 합니다.")
        safe_name = str(name).replace('\r', ' ').replace('\n', ' ')
        with path.open('w', encoding='utf-8') as output:
            output.write('// AcousticStudio Trajectory Phase Data Header\n')
            output.write(f'// Trajectory: {safe_name}\n// Board profile: {profile}\n')
            output.write('// Phases: corrected physical channel order; offsets/map already applied.\n')
            output.write('#ifndef ACOUSTIC_TRAJECTORY_DATA_H\n#define ACOUSTIC_TRAJECTORY_DATA_H\n\n')
            output.write('#include <stdint.h>\n\n')
            output.write(f'#define TRAJ_TOTAL_STEPS {steps}\n#define TRAJ_NUM_TRANSDUCERS {num_tx}\n\n')
            output.write('const uint16_t traj_step_delays_ms[TRAJ_TOTAL_STEPS] = {\n')
            output.write(',\n'.join(f'    {int(delay)}' for delay in rounded_delays))
            output.write('\n};\n\n// Phase32 values: 0–31\n')
            output.write('const uint8_t traj_phases[TRAJ_TOTAL_STEPS][TRAJ_NUM_TRANSDUCERS] = {\n')
            output.write(',\n'.join('    { ' + ', '.join(map(str, row)) + ' }' for row in phase_steps))
            output.write('\n};\n\n#endif // ACOUSTIC_TRAJECTORY_DATA_H\n')
    else:
        with path.open('w', newline='', encoding='utf-8') as output:
            writer = csv.writer(output)
            writer.writerow(['Step', 'Target_X_mm', 'Target_Y_mm', 'Target_Z_mm', 'Delay_ms',
                             'Board_Profile'] + [f'Physical{index}_Phase32' for index in range(num_tx)])
            for index, row in enumerate(phase_steps):
                writer.writerow([index, *points[index], delays[index], profile, *row])
    return path
