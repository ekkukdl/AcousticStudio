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
