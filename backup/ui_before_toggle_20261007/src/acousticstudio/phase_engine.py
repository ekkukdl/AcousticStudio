# -*- coding: utf-8 -*-
"""위상 연산 및 음압 분포 계산 엔진"""
import numpy as np
import numba


@numba.njit(parallel=True)
def calculate_field_slice_numba(pts_x, pts_y, pts_z, tx_x, tx_y, tx_z, tx_phases, tx_amplitudes, k):
    num_pts = len(pts_x)
    num_tx = len(tx_x)
    real_out = np.zeros(num_pts, dtype=np.float64)
    imag_out = np.zeros(num_pts, dtype=np.float64)
    for p in numba.prange(num_pts):
        px, py, pz = pts_x[p], pts_y[p], pts_z[p]
        r_sum, i_sum = 0.0, 0.0
        for t in range(num_tx):
            dx = px - tx_x[t]
            dy = py - tx_y[t]
            dz = pz - tx_z[t]
            dist = np.sqrt(dx*dx + dy*dy + dz*dz)
            if dist < 1e-3: dist = 1e-3
            amp = tx_amplitudes[t] / dist
            phase = k * dist + tx_phases[t]
            r_sum += amp * np.cos(phase)
            i_sum += amp * np.sin(phase)
        real_out[p] = r_sum
        imag_out[p] = i_sum
    return real_out, imag_out


class PhaseEngine:
    """위상 연산 디스패처 — 환경에 맞는 최적 엔진을 자동 선택"""

    DEFAULT_SPEED_OF_SOUND = 343000.0  # mm/s
    DEFAULT_FREQUENCY = 40000.0  # Hz

    def __init__(self):
        self.k = 2.0 * np.pi / (self.DEFAULT_SPEED_OF_SOUND / self.DEFAULT_FREQUENCY)

    def calculate_phases(self, centers, active_points, amplitudes, algorithm, mode_idx, has_taichi=False, has_pytorch=False):
        """
        Calculate phases for all transducers.

        Args:
            centers: np.array shape (N, 3) - transducer center positions
            active_points: list of dicts with 'x', 'y', 'z' keys
            amplitudes: np.array shape (N,) - transducer amplitudes
            algorithm: str - 'Twin Trap' or 'Vortex Trap'
            mode_idx: int - 0=Numba, 1=C++, 2=Taichi, 3=PyTorch
            has_taichi: bool
            has_pytorch: bool

        Returns:
            (total_phases, packet_bytes) - phases array and optional hardware packet
        """
        k = self.k

        if not active_points:
            return np.zeros(len(centers), dtype=np.float64), None

        from acousticstudio.sonic_wrapper import calculate_phases_sonic
        cx = centers[:, 0]
        cy = centers[:, 1]
        cz = centers[:, 2]
        tx_arr = np.array([pt["x"] for pt in active_points])
        ty_arr = np.array([pt["y"] for pt in active_points])
        tz_arr = np.array([pt["z"] for pt in active_points])
        tx_amplitudes = amplitudes

        cpp_phases, cpp_packet = None, None

        if mode_idx == 3 and has_pytorch:
            from acousticstudio.sonic_wrapper import calculate_phases_gpu
            cpp_phases, cpp_packet = calculate_phases_gpu(cx, cy, cz, tx_arr, ty_arr, tz_arr, tx_amplitudes, algorithm, k)
        elif mode_idx == 2 and has_taichi:
            from acousticstudio.sonic_wrapper import calculate_phases_taichi
            cpp_phases, cpp_packet = calculate_phases_taichi(cx, cy, cz, tx_arr, ty_arr, tz_arr, tx_amplitudes, algorithm, k)
        elif mode_idx == 1:
            from acousticstudio.sonic_wrapper import calculate_phases_sonic
            cpp_phases, cpp_packet = calculate_phases_sonic(cx, cy, cz, tx_arr, ty_arr, tz_arr, tx_amplitudes, algorithm, k)

        if cpp_phases is not None:
            total_phases = cpp_phases
            packet = cpp_packet
        else:
            # Fallback to NumPy
            complex_p = np.zeros(len(centers), dtype=np.complex128)
            for pt in active_points:
                tx, ty, tz = pt["x"], pt["y"], pt["z"]
                dx = cx - tx
                dy = cy - ty
                dz = cz - tz

                d = np.sqrt(dx**2 + dy**2 + dz**2)
                phase_focal = -d * k

                if "Twin Trap" in algorithm:
                    signature = np.where(dx > 0, np.pi, 0.0)
                elif "Vortex Trap" in algorithm:
                    signature = np.arctan2(dy, dx)
                else:
                    signature = np.zeros_like(dx)

                pt_phase = phase_focal + signature
                complex_p += tx_amplitudes * np.exp(1j * pt_phase)

            total_phases = np.angle(complex_p) % (2.0 * np.pi)
            total_phases[total_phases < 0] += 2.0 * np.pi
            packet = None

        return total_phases, packet

    def calculate_field_slice(self, pts, tx_centers, tx_phases, tx_amplitudes, mode_idx, has_taichi=False, has_pytorch=False):
        """
        Calculate pressure field on a grid of points.

        Args:
            pts: np.array shape (P, 3) - grid points
            tx_centers: np.array shape (N, 3) - transducer positions
            tx_phases: np.array shape (N,)
            tx_amplitudes: np.array shape (N,)
            mode_idx: int
            has_taichi: bool
            has_pytorch: bool

        Returns:
            (real_part, imag_part) tuple of arrays
        """
        k = self.k

        from acousticstudio.sonic_wrapper import calculate_field_slice_sonic
        pts_x = np.ascontiguousarray(pts[:, 0], dtype=np.float64)
        pts_y = np.ascontiguousarray(pts[:, 1], dtype=np.float64)
        pts_z = np.ascontiguousarray(pts[:, 2], dtype=np.float64)
        tx_x = np.ascontiguousarray(tx_centers[:, 0], dtype=np.float64)
        tx_y = np.ascontiguousarray(tx_centers[:, 1], dtype=np.float64)
        tx_z = np.ascontiguousarray(tx_centers[:, 2], dtype=np.float64)

        calc_res = None
        if mode_idx == 3 and has_pytorch:
            from acousticstudio.sonic_wrapper import calculate_field_slice_gpu
            calc_res = calculate_field_slice_gpu(pts_x, pts_y, pts_z, tx_x, tx_y, tx_z, tx_phases, tx_amplitudes, k)
        elif mode_idx == 2 and has_taichi:
            from acousticstudio.sonic_wrapper import calculate_field_slice_taichi
            calc_res = calculate_field_slice_taichi(pts_x, pts_y, pts_z, tx_x, tx_y, tx_z, tx_phases, tx_amplitudes, k)

        if calc_res is not None:
            real_p, imag_p = calc_res
        else:
            real_p, imag_p = calculate_field_slice_numba(pts_x, pts_y, pts_z, tx_x, tx_y, tx_z, tx_phases, tx_amplitudes, k)

        return real_p, imag_p

    def optimize_trajectory_physical(self, tx_centers, points, base_delay, algorithm='Twin Trap', smooth_accel=True):
        """
        물리 연산(levitate 기반)을 접목한 선형 이송 궤적 최적화.

        - mm -> m 단위 정합화 (SI 단위계 일치)
        - 각 웨이포인트에서의 3차원 음향 방사력(Radiation Force) 및 복원 스티프니스(Stiffness) 연산
        - 음향 트랩 강도(Trap Intensity / Stiffness Margin)에 기반한 적응형 속도 제어 (Adaptive Delay)
        - 급격한 관성 가속도(Inertial Escape) 방지를 위한 S-curve/Cosine 가감속 스무딩

        Args:
            tx_centers: np.array (N, 3) - 트랜스듀서 중심 좌표 (mm)
            points: np.array (steps, 3) - 궤적 좌표 (mm)
            base_delay: float - 기본 스텝 딜레이 (초)
            algorithm: str - 트랩 알고리즘 ('Twin Trap' 또는 'Vortex Trap')
            smooth_accel: bool - 가감속 스무딩 적용 여부

        Returns:
            delays: np.array (steps,) - 최적화된 각 스텝 지연시간 (초)
            metrics: dict - 안정성 점수 및 통계
        """
        steps = len(points)
        delays = np.ones(steps, dtype=np.float64) * base_delay

        default_metrics = {
            'stiffness': np.zeros((steps, 3)),
            'trap_strengths': np.zeros(steps),
            'avg_stability': 75.0,
            'min_stability': 60.0,
            'grade': '안정',
            'grade_en': 'Stable',
            'guide_msg': '안정적인 이송 구간입니다. 기본 가감속 프로파일이 적용되었습니다.',
            'color': '#1565C0',
            'status': 'Fallback (Physics library not loaded)'
        }

        if len(tx_centers) == 0 or steps < 2:
            return delays, default_metrics

        try:
            # NumPy 2.x / 1.2x compatibility patch for levitate
            np.complex = getattr(np, 'complex128', complex)
            np.float = getattr(np, 'float64', float)
            np.int = getattr(np, 'int64', int)
            np.bool = getattr(np, 'bool_', bool)

            import levitate
            from acousticstudio.sonic_wrapper import calculate_phases_sonic

            # Unit conversion: mm -> m
            tx_pos_m = np.ascontiguousarray(tx_centers, dtype=np.float64) * 1e-3
            points_m = np.ascontiguousarray(points, dtype=np.float64) * 1e-3

            # Transducer normal vectors (handle planar and opposed arrays)
            mean_z = np.mean(tx_pos_m[:, 2])
            z_span = np.ptp(tx_pos_m[:, 2])
            normals = np.zeros_like(tx_pos_m)
            if z_span > 0.02:  # Opposed array (multi-plane)
                normals[:, 2] = np.where(tx_pos_m[:, 2] > mean_z, -1.0, 1.0)
            else:
                normals[:, 2] = 1.0

            # Initialize Levitate array model
            lev_array = levitate.arrays.TransducerArray(
                positions=tx_pos_m.T,
                normals=normals.T,
                transducer=levitate.transducers.CircularPiston(effective_radius=0.005)
            )
            stiffness_field = levitate.fields.RadiationForceStiffness(lev_array)

            k_mm = self.k  # rad/mm
            stiff_matrix = np.zeros((steps, 3), dtype=np.float64)
            trap_strengths = np.zeros(steps, dtype=np.float64)

            # Evaluate each trajectory waypoint
            for i in range(steps):
                pt = points[i]
                phases, _ = calculate_phases_sonic(
                    np.array([pt[0]]), np.array([pt[1]]), np.array([pt[2]]),
                    tx_centers[:, 0], tx_centers[:, 1], tx_centers[:, 2],
                    np.ones(len(tx_centers)), algorithm, k_mm
                )
                u = np.exp(1j * phases)
                stiff_vec = (stiffness_field @ points_m[i])(u)
                stiff_matrix[i] = stiff_vec

                # Trap strength: magnitude of stiffness vector (N/m)
                norm_stiff = float(np.linalg.norm(stiff_vec))
                trap_strengths[i] = norm_stiff

            # Adaptive delay based on relative trap strength along trajectory
            max_s = np.max(trap_strengths)
            if max_s > 1e-9:
                rel_strengths = trap_strengths / max_s
            else:
                rel_strengths = np.ones(steps)

            for i in range(steps):
                # Weaker trap regions need slower transit to prevent dropouts
                r = rel_strengths[i]
                if r < 0.3:
                    mult = 3.0
                elif r < 0.7:
                    mult = 1.0 + 2.0 * (0.7 - r) / 0.4
                else:
                    mult = 1.0
                delays[i] = base_delay * mult

            # S-curve (Cosine ramp) smoothing at start and end to suppress inertial escape
            if smooth_accel and steps >= 4:
                ramp_len = max(2, int(steps * 0.15))
                for i in range(ramp_len):
                    factor = 0.5 * (1.0 - np.cos(np.pi * (i + 1) / ramp_len))
                    accel_mult = 1.0 + 1.5 * (1.0 - factor)
                    delays[i] = max(delays[i], base_delay * accel_mult)
                    end_i = steps - 1 - i
                    delays[end_i] = max(delays[end_i], base_delay * accel_mult)

            avg_stab = float(np.clip(np.mean(rel_strengths) * 100.0, 10.0, 99.0))
            min_stab = float(np.clip(np.min(rel_strengths) * 100.0, 5.0, 95.0))

            if avg_stab >= 85.0:
                grade = '최적'
                grade_en = 'Optimal'
                guide_msg = '최적의 부상 환경입니다. 고속 이송이 가능합니다.'
                color = '#2E7D32'
            elif avg_stab >= 60.0:
                grade = '안정'
                grade_en = 'Stable'
                guide_msg = '안정적인 이송 구간입니다. 취약 구간에 적응형 감속이 적용되었습니다.'
                color = '#1565C0'
            elif avg_stab >= 40.0:
                grade = '주의'
                grade_en = 'Caution'
                guide_msg = '배열 외곽에 근접하였습니다. 물체가 흔들릴 경우 딜레이를 늘려주십시오.'
                color = '#E65100'
            else:
                grade = '위험'
                grade_en = 'Critical'
                guide_msg = '트랩 복원력이 매우 낮습니다. 궤적 범위를 배열 중심 쪽으로 재설정하십시오.'
                color = '#C62828'

            metrics = {
                'stiffness': stiff_matrix,
                'trap_strengths': trap_strengths,
                'avg_stability': avg_stab,
                'min_stability': min_stab,
                'grade': grade,
                'grade_en': grade_en,
                'guide_msg': guide_msg,
                'color': color,
                'status': 'Optimized (Levitate Radiation Force)'
            }
            return delays, metrics

        except Exception as e:
            # Safe fallback if levitate calculation encounters an error
            print(f"[PhaseEngine] Trajectory optimization fallback: {e}")
            if smooth_accel and steps >= 4:
                ramp_len = max(2, int(steps * 0.15))
                for i in range(ramp_len):
                    factor = 0.5 * (1.0 - np.cos(np.pi * (i + 1) / ramp_len))
                    accel_mult = 1.0 + 1.5 * (1.0 - factor)
                    delays[i] = max(delays[i], base_delay * accel_mult)
                    end_i = steps - 1 - i
                    delays[end_i] = max(delays[end_i], base_delay * accel_mult)
            default_metrics['status'] = f'Fallback ({e})'
            return delays, default_metrics

