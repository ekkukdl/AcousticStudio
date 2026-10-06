# -*- coding: utf-8 -*-
"""위상 연산 및 음압 분포 계산 엔진"""
import numpy as np
from acousticstudio.field_model import FieldConfig, propagation_matrix, source_parameters, levitate_transducer
from acousticstudio.field_backends import reduce_field


def _positions_mm(values, name):
    positions = np.asarray(values, dtype=np.float64)
    if positions.shape == (0,):
        positions = positions.reshape(0, 3)
    if positions.ndim != 2 or positions.shape[1] != 3 or not np.all(np.isfinite(positions)):
        raise ValueError(f"{name} 좌표는 유한한 (N, 3) 배열이어야 합니다.")
    return np.ascontiguousarray(positions)


def _amplitudes(values, count):
    amplitudes = np.asarray(values, dtype=np.float64)
    if amplitudes.shape != (count,) or not np.all(np.isfinite(amplitudes)) or np.any(amplitudes < 0):
        raise ValueError("송신기 진폭은 채널 수와 일치하는 유한한 비음수 배열이어야 합니다.")
    return np.ascontiguousarray(amplitudes)


def trajectory_diagnosis_is_valid(metrics):
    """Reject unavailable/old fallback metrics before displaying percentages."""
    if not isinstance(metrics, dict) or metrics.get('valid') is False:
        return False
    if str(metrics.get('status', '')).startswith(('Fallback', 'Unavailable')):
        return False
    try:
        return all(np.isfinite(float(metrics[key])) for key in ('avg_stability', 'min_stability'))
    except (KeyError, TypeError, ValueError):
        return False


class PhaseEngine:
    """위상 연산 디스패처 — 환경에 맞는 최적 엔진을 자동 선택"""

    DEFAULT_SPEED_OF_SOUND = 343000.0  # mm/s
    DEFAULT_FREQUENCY = 40000.0  # Hz

    def __init__(self):
        self.k = 2.0 * np.pi / (self.DEFAULT_SPEED_OF_SOUND / self.DEFAULT_FREQUENCY)
        self.last_backend = None

    def calculate_phases(self, centers, active_points, amplitudes, algorithm, mode_idx, has_taichi=False, has_pytorch=False,
                         field_config=None, normals=None, aperture_radii_mm=None):
        """
        Calculate phases for all transducers.

        Args:
            centers: np.array shape (N, 3) - transducer center positions
            active_points: list of dicts with 'x', 'y', 'z' keys
            amplitudes: np.array shape (N,) - transducer amplitudes
            algorithm: str - 'Focus', 'Twin Trap' or 'Vortex Trap'
            mode_idx: int - 0=Numba, 1=C++, 2=Taichi, 3=PyTorch
            has_taichi: bool
            has_pytorch: bool

        Returns:
            (total_phases, packet_bytes) - phases array and optional hardware packet
        """
        centers = _positions_mm(centers, "송신기")
        amplitudes = _amplitudes(amplitudes, len(centers))
        if algorithm not in ('Focus', 'Twin Trap', 'Vortex Trap'):
            raise ValueError(f"지원하지 않는 트랩 알고리즘: {algorithm}")
        if mode_idx not in (0, 1, 2, 3):
            raise ValueError(f"지원하지 않는 연산 모드: {mode_idx}")
        try:
            targets = _positions_mm([[point['x'], point['y'], point['z']] for point in active_points], "제어점")
        except (KeyError, TypeError) as exc:
            raise ValueError("제어점에는 x, y, z 좌표가 필요합니다.") from exc
        k = self.k
        if not np.isfinite(k) or k <= 0:
            raise ValueError("파수는 유한한 양수여야 합니다.")

        if field_config is not None:
            source_parameters(len(centers), normals, aperture_radii_mm, field_config)

        if len(centers) == 0 or len(targets) == 0:
            self.last_backend = None
            return np.zeros(len(centers), dtype=np.float64), None

        if field_config is not None:
            green = propagation_matrix(targets, centers, normals, aperture_radii_mm, field_config)
            delta = centers[:, None, :] - targets[None, :, :]
            if algorithm == 'Twin Trap':
                signature = np.where(delta[:, :, 0] > 0, np.pi, 0.)
            elif algorithm == 'Vortex Trap':
                signature = np.arctan2(delta[:, :, 1], delta[:, :, 0])
            else:
                signature = np.zeros(delta.shape[:2])
            # Conjugate propagation, including signed directivity and 1/r gain.
            matrix = green.conj().T * np.exp(1j * signature)
            phasors, self.last_backend = reduce_field(
                matrix, np.ones(len(targets)), mode_idx, has_taichi, has_pytorch)
            phases = np.angle(phasors) % (2 * np.pi)
            phases[amplitudes == 0] = 0.
            return phases, None  # quantization remains exclusively in HardwareController

        cx = centers[:, 0]
        cy = centers[:, 1]
        cz = centers[:, 2]
        tx_arr, ty_arr, tz_arr = targets.T
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
            total_phases = np.asarray(cpp_phases, dtype=np.float64)
            packet = cpp_packet
        else:
            # Fallback to NumPy
            complex_p = np.zeros(len(centers), dtype=np.complex128)
            for tx, ty, tz in targets:
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

        if total_phases.shape != (len(centers),) or not np.all(np.isfinite(total_phases)):
            raise ValueError("위상 계산 결과의 채널 수가 잘못되었거나 유한하지 않습니다.")
        return total_phases % (2.0 * np.pi), packet

    def calculate_trajectory_phases(self, centers, points, amplitudes, algorithm,
                                    mode_idx=0, has_taichi=False, has_pytorch=False,
                                    field_config=None, normals=None, aperture_radii_mm=None):
        """Calculate one moving target per waypoint through the live dispatcher.

        Results retain software channel order; hardware mapping/correction belongs
        exclusively to HardwareController, for both transmission and export.
        """
        centers = _positions_mm(centers, "송신기")
        points = _positions_mm(points, "궤적")
        amplitudes = _amplitudes(amplitudes, len(centers))
        if len(centers) == 0 or len(points) == 0:
            raise ValueError("궤적 위상 계산에는 송신기와 궤적 좌표가 필요합니다.")
        phases = np.empty((len(points), len(centers)), dtype=np.float64)
        for index, point in enumerate(points):
            phases[index], _ = self.calculate_phases(
                centers, [dict(zip(('x', 'y', 'z'), point))], amplitudes, algorithm,
                mode_idx, has_taichi=has_taichi, has_pytorch=has_pytorch,
                field_config=field_config, normals=normals, aperture_radii_mm=aperture_radii_mm,
            )
        return phases

    def calculate_field_slice(self, pts, tx_centers, tx_phases, tx_amplitudes, mode_idx, has_taichi=False, has_pytorch=False,
                              field_config=None, normals=None, aperture_radii_mm=None):
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
        pts = _positions_mm(pts, '수신점')
        if mode_idx not in (0, 1, 2, 3):
            raise ValueError('지원하지 않는 연산 모드입니다.')
        tx_centers = _positions_mm(tx_centers, '방사면')
        amplitudes = _amplitudes(tx_amplitudes, len(tx_centers))
        phases = np.asarray(tx_phases, dtype=np.float64)
        if phases.shape != (len(tx_centers),) or not np.isfinite(phases).all():
            raise ValueError('위상은 채널 수와 일치하는 유한한 rad 배열이어야 합니다.')
        if field_config is None:
            # Preserve 1/mm scale for external legacy callers, with the same Green implementation.
            field_config = FieldConfig(sound_speed_m_s=2 * np.pi * self.DEFAULT_FREQUENCY / (self.k * 1000),
                                       source_strength=.001)
        weights = amplitudes * np.exp(1j * phases)
        output = np.empty(len(pts), dtype=np.complex128)
        source_parameters(len(tx_centers), normals, aperture_radii_mm, field_config)
        for start in range(0, len(pts), 512):
            green = propagation_matrix(pts[start:start + 512], tx_centers, normals, aperture_radii_mm, field_config)
            output[start:start + 512], self.last_backend = reduce_field(
                green, weights, mode_idx, has_taichi, has_pytorch)
        return output.real, output.imag

    def optimize_trajectory_physical(self, tx_centers, points, base_delay, algorithm='Twin Trap', smooth_accel=True,
                                     amplitudes=None, mode_idx=0, has_taichi=False, has_pytorch=False,
                                     field_config=None, normals=None, aperture_radii_mm=None):
        """
        물리 연산(levitate 기반)을 접목한 선형 이송 궤적 최적화.

        - mm -> m 단위 정합화 (SI 단위계 일치)
        - 각 웨이포인트에서의 3차원 음향 방사력(Radiation Force) 및 복원 스티프니스(Stiffness) 연산
        - 음향 트랩 강도(Trap Intensity / Stiffness Margin)에 기반한 적응형 속도 제어 (Adaptive Delay)
        - 급격한 관성 가속도(Inertial Escape) 방지를 위한 S-curve/Cosine 가감속 스무딩

        Args:
            tx_centers: np.array (N, 3) - 트랜스듀서 중심 좌표 (mm)
            points: np.array (steps, 3) - 궤적 좌표 (mm)
            base_delay: float - 기본 스텝 딜레이 (ms, Qt 타이머와 동일)
            algorithm: str - 트랩 알고리즘 ('Twin Trap' 또는 'Vortex Trap')
            smooth_accel: bool - 가감속 스무딩 적용 여부

        Returns:
            delays: np.array (steps,) - 최적화된 각 스텝 지연시간 (ms)
            metrics: dict - 모델 상대 강도 통계, 실패 시 valid=False 및 점수 없음
        """
        steps = len(points)
        if not np.isfinite(base_delay) or base_delay <= 0:
            raise ValueError("궤적 지연은 유한한 양수(ms)여야 합니다.")
        delays = np.ones(steps, dtype=np.float64) * base_delay

        default_metrics = {
            'valid': False,
            'stiffness': None,
            'trap_strengths': None,
            'avg_stability': None,
            'min_stability': None,
            'grade': '진단 불가',
            'grade_en': 'Unavailable',
            'guide_msg': '물리 진단을 수행할 수 없어 기하학적 지연만 적용했습니다.',
            'color': '#666666',
            'status': 'Unavailable (송신기가 없거나 궤적 좌표가 부족합니다.)'
        }

        if len(tx_centers) == 0 or steps < 2:
            return delays, default_metrics

        try:
            import levitate
            tx_centers = _positions_mm(tx_centers, "송신기")
            points = _positions_mm(points, "궤적")
            amplitudes = _amplitudes(np.ones(len(tx_centers)) if amplitudes is None else amplitudes, len(tx_centers))
            config = field_config or FieldConfig(
                sound_speed_m_s=2 * np.pi * self.DEFAULT_FREQUENCY / (self.k * 1000))
            normals, radii_m = source_parameters(len(tx_centers), normals, aperture_radii_mm, config)
            waypoint_phases = self.calculate_trajectory_phases(
                tx_centers, points, amplitudes, algorithm, mode_idx,
                has_taichi=has_taichi, has_pytorch=has_pytorch,
                field_config=field_config, normals=normals, aperture_radii_mm=aperture_radii_mm,
            )

            # Unit conversion: mm -> m
            tx_pos_m = np.ascontiguousarray(tx_centers, dtype=np.float64) * 1e-3
            points_m = np.ascontiguousarray(points, dtype=np.float64) * 1e-3

            if np.any(np.linalg.norm(points_m[:, None, :] - tx_pos_m[None, :, :], axis=-1) <= config.min_distance_m):
                raise ValueError('방사면 근접점에서는 물리 미분 진단을 수행할 수 없습니다.')

            # Initialize Levitate array model
            lev_array = levitate.arrays.TransducerArray(
                positions=tx_pos_m.T,
                normals=normals.T,
                transducer=levitate_transducer(config, radii_m, levitate)
            )
            stiffness_field = levitate.fields.RadiationForceStiffness(lev_array)

            stiff_matrix = np.zeros((steps, 3), dtype=np.float64)
            trap_strengths = np.zeros(steps, dtype=np.float64)

            # Evaluate each trajectory waypoint
            for i in range(steps):
                u = amplitudes * np.exp(1j * waypoint_phases[i])
                stiff_vec = np.asarray((stiffness_field @ points_m[i])(u), dtype=np.float64)
                if stiff_vec.shape != (3,) or not np.all(np.isfinite(stiff_vec)):
                    raise ValueError("물리 계산 결과의 형상이 잘못되었거나 유한하지 않습니다.")
                stiff_matrix[i] = stiff_vec

                # Nominal stiffness scale: input pressure and empirical amplitudes
                # are uncalibrated. This norm cannot establish signed confinement.
                norm_stiff = float(np.linalg.norm(stiff_vec))
                if not np.isfinite(norm_stiff):
                    raise ValueError("트랩 강도의 크기를 유한하게 계산할 수 없습니다.")
                trap_strengths[i] = norm_stiff

            # Adaptive delay based on relative trap strength along trajectory
            max_s = np.max(trap_strengths)
            if max_s > 1e-9:
                rel_strengths = trap_strengths / max_s
            else:
                raise ValueError("트랩 강도가 0이거나 정규화할 수 없습니다.")

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
                guide_msg = '경로 내 상대 트랩 강도가 높은 구간입니다.'
                color = '#2E7D32'
            elif avg_stab >= 60.0:
                grade = '안정'
                grade_en = 'Stable'
                guide_msg = '상대 강도가 낮은 구간에 적응형 감속을 적용했습니다.'
                color = '#1565C0'
            elif avg_stab >= 40.0:
                grade = '주의'
                grade_en = 'Caution'
                guide_msg = '경로 내 상대 트랩 강도에 편차가 있습니다.'
                color = '#E65100'
            else:
                grade = '위험'
                grade_en = 'Critical'
                guide_msg = '경로 내 상대 트랩 강도가 낮은 구간이 많습니다.'
                color = '#C62828'

            metrics = {
                'valid': True,
                'score_kind': 'relative_stiffness_norm',
                'field_config': config.to_dict(),
                'pressure_units': 'relative_uncalibrated',
                'stiffness_units': 'nominal_N_per_m_uncalibrated',
                'stiffness': stiff_matrix,
                'trap_strengths': trap_strengths,
                'avg_stability': avg_stab,
                'min_stability': min_stab,
                'grade': grade,
                'grade_en': grade_en,
                'guide_msg': guide_msg + ' 실제 부양 및 방향별 복원성은 별도 검증이 필요합니다.',
                'color': color,
                'status': 'Optimized (Levitate Radiation Force)'
            }
            return delays, metrics

        except Exception as e:
            # Safe fallback if levitate calculation encounters an error
            print(f"[PhaseEngine] Trajectory optimization fallback: {e}")
            delays[:] = base_delay
            if smooth_accel and steps >= 4:
                ramp_len = max(2, int(steps * 0.15))
                for i in range(ramp_len):
                    factor = 0.5 * (1.0 - np.cos(np.pi * (i + 1) / ramp_len))
                    accel_mult = 1.0 + 1.5 * (1.0 - factor)
                    delays[i] = max(delays[i], base_delay * accel_mult)
                    end_i = steps - 1 - i
                    delays[end_i] = max(delays[end_i], base_delay * accel_mult)
            default_metrics['status'] = f'Unavailable ({e})'
            default_metrics['guide_msg'] += f' 원인: {e}'
            return delays, default_metrics

