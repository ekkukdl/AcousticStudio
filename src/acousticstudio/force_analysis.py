"""Fixed-drive Gor'kov analysis using T2 propagation, mm API and SI derivatives.

Gor'kov coefficients and fourth-order stencils adapted from Ultraino CalcField,
Copyright (c) 2017 asiermarzo (MIT), see THIRD_PARTY_NOTICES.md.
The pressure scale is uncalibrated: N*, J*, and N*/m assume one relative
pressure unit is one Pa. They do not establish measured gravity equilibrium.
"""
from dataclasses import asdict, dataclass, field
from threading import Event

import numpy as np

from acousticstudio.field_model import FieldConfig, positions, source_parameters
from acousticstudio.phase_engine import PhaseEngine


class AnalysisCancelled(Exception):
    pass


def _positive(value, name):
    if not np.isfinite(value) or value <= 0:
        raise ValueError(f'{name} 값은 유한한 양수여야 합니다.')


@dataclass(frozen=True)
class ParticleConfig:
    radius_mm: float = .25
    density_kg_m3: float = 25.
    sound_speed_m_s: float = 2350.
    compressibility_pa_inv: float | None = None
    provenance: str = 'example'
    source: str = '예시 EPS 물성 / 실제 대상 미확정'

    def __post_init__(self):
        for key in ('radius_mm', 'density_kg_m3', 'sound_speed_m_s'):
            _positive(getattr(self, key), key)
        if self.compressibility_pa_inv is not None:
            _positive(self.compressibility_pa_inv, '입자 압축률')
        if self.provenance not in ('example', 'provided') or not isinstance(self.source, str) or not self.source.strip():
            raise ValueError('입자 물성의 예시/제공 여부 및 출처가 필요합니다.')

    @property
    def compressibility(self):
        return self.compressibility_pa_inv if self.compressibility_pa_inv is not None else (
            1 / (self.density_kg_m3 * self.sound_speed_m_s ** 2))

    @property
    def volume_m3(self):
        return 4 * np.pi / 3 * (self.radius_mm * 1e-3) ** 3

    @property
    def mass_kg(self):
        return self.volume_m3 * self.density_kg_m3


@dataclass(frozen=True)
class AnalysisSettings:
    particle: ParticleConfig = field(default_factory=ParticleConfig)
    span_mm: float = 2.  # half range, both endpoints and zero are included
    samples: int = 41
    derivative_step_mm: float = .133984  # default 343/40000 m wavelength / 64
    relative_tolerance: float = .01
    gravity_m_s2: tuple = (0., 0., -9.80665)

    def __post_init__(self):
        if not isinstance(self.particle, ParticleConfig):
            raise ValueError('입자 설정이 필요합니다.')
        for key in ('span_mm', 'derivative_step_mm', 'relative_tolerance'):
            _positive(getattr(self, key), key)
        if not isinstance(self.samples, int) or isinstance(self.samples, bool) or not 5 <= self.samples <= 201 or self.samples % 2 == 0:
            raise ValueError('스캔 표본은 5~201 사이의 홀수여야 합니다.')
        if self.relative_tolerance > .1:
            raise ValueError('수렴 허용 오차는 10% 이하여야 합니다.')
        gravity = np.asarray(self.gravity_m_s2, dtype=float)
        if gravity.shape != (3,) or not np.isfinite(gravity).all():
            raise ValueError('중력은 유한한 XYZ 가속도 벡터(m/s²)여야 합니다.')
        object.__setattr__(self, 'gravity_m_s2', tuple(float(value) for value in gravity))

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        data = dict(data)
        particle = ParticleConfig(**data.pop('particle', {}))
        return cls(particle=particle, **data)


@dataclass(frozen=True)
class FieldSnapshot:
    sources_mm: np.ndarray
    normals: np.ndarray
    phases_rad: np.ndarray
    amplitudes: np.ndarray
    field_config: FieldConfig
    aperture_radii_mm: tuple | None = None

    def __post_init__(self):
        if not isinstance(self.field_config, FieldConfig):
            raise ValueError('명시적인 공통 음장 설정이 필요합니다.')
        sources = positions(self.sources_mm, '방사면').copy()
        if len(sources) == 0:
            raise ValueError('방사력 분석에는 송신기가 필요합니다.')
        radii = tuple([None] * len(sources) if self.aperture_radii_mm is None else self.aperture_radii_mm)
        normals, _ = source_parameters(len(sources), self.normals, radii, self.field_config)
        phases = np.array(self.phases_rad, dtype=float, copy=True)
        amplitudes = np.array(self.amplitudes, dtype=float, copy=True)
        if phases.shape != (len(sources),) or not np.isfinite(phases).all():
            raise ValueError('고정 위상은 채널 수와 일치하는 유한한 rad 배열이어야 합니다.')
        if amplitudes.shape != phases.shape or not np.isfinite(amplitudes).all() or np.any(amplitudes < 0):
            raise ValueError('고정 진폭은 채널 수와 일치하는 비음수 배열이어야 합니다.')
        for name, array in (('sources_mm', sources), ('normals', normals), ('phases_rad', phases), ('amplitudes', amplitudes)):
            array.setflags(write=False)
            object.__setattr__(self, name, array)
        object.__setattr__(self, 'aperture_radii_mm', radii)

    def to_dict(self):
        return dict(sources_mm=self.sources_mm.tolist(), normals=self.normals.tolist(),
                    phases_rad=self.phases_rad.tolist(), amplitudes=self.amplitudes.tolist(),
                    field_config=self.field_config.to_dict(), aperture_radii_mm=list(self.aperture_radii_mm))


def gorkov_coefficients(particle, medium):
    """U = M1 |p|² - M2 sum(|dp/dq|²); complex p is peak phasor, not RMS."""
    kappa = 1 / (medium.density_kg_m3 * medium.sound_speed_m_s ** 2)
    f1 = 1 - particle.compressibility / kappa
    f2 = 2 * (particle.density_kg_m3 - medium.density_kg_m3) / (2 * particle.density_kg_m3 + medium.density_kg_m3)
    m1 = particle.volume_m3 * f1 * kappa / 4
    m2 = particle.volume_m3 * 3 / 8 * f2 / (medium.density_kg_m3 * (2 * np.pi * medium.frequency_hz) ** 2)
    result = dict(M1=m1, M2=m2, f1=f1, f2=f2)
    if not np.isfinite(list(result.values())).all():
        raise ValueError('고르코프 계수를 유한하게 계산할 수 없습니다.')
    return result


def restoring_diagnosis(matrix, uncertainty=0.):
    matrix = np.asarray(matrix, dtype=float)
    if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
        raise ValueError('복원행렬은 유한한 3×3 배열이어야 합니다.')
    symmetric = .5 * (matrix + matrix.T)
    eigenvalues = np.linalg.eigvalsh(symmetric)
    floor = max(float(uncertainty), np.max(np.abs(eigenvalues)) * 1e-8, np.finfo(float).tiny)
    if eigenvalues[0] > floor:
        status = 'restoring'
    elif eigenvalues[0] < -floor:
        status = 'non_restoring'
    else:
        status = 'unresolved'
    return dict(status=status, eigenvalues=eigenvalues, uncertainty=floor,
                symmetry_relative_error=float(np.linalg.norm(matrix - matrix.T) /
                                              max(np.linalg.norm(matrix), np.finfo(float).tiny)))


class ForceAnalyzer:
    """Immutable drive; evaluation only moves receiver coordinates, never refocuses."""
    def __init__(self, snapshot, settings=None, mode_idx=0, has_taichi=False, has_pytorch=False,
                 cancelled=None):
        self.snapshot = snapshot
        self.settings = settings or AnalysisSettings()
        self.engine = PhaseEngine()
        self.mode_idx, self.has_taichi, self.has_pytorch = mode_idx, has_taichi, has_pytorch
        self.cancelled = cancelled or Event()
        self.coefficients = gorkov_coefficients(self.settings.particle, snapshot.field_config)
        wavelength_mm = snapshot.field_config.sound_speed_m_s / snapshot.field_config.frequency_hz * 1000
        if self.settings.derivative_step_mm > wavelength_mm / 8:
            raise ValueError('미분 간격은 파장의 1/8 이하여야 합니다.')

    def _check_cancel(self):
        if self.cancelled.is_set():
            raise AnalysisCancelled('분석을 취소했습니다.')

    def pressure(self, receivers_mm):
        receivers = positions(receivers_mm, '평가점')
        result = np.empty(len(receivers), dtype=complex)
        for start in range(0, len(receivers), 512):
            self._check_cancel()
            points = receivers[start:start + 512]
            distance = np.linalg.norm(points[:, None, :] - self.snapshot.sources_mm[None, :, :], axis=-1)
            exclusion_mm = max(self.snapshot.field_config.min_distance_m * 1000, self.settings.particle.radius_mm)
            if np.any(distance <= exclusion_mm):
                raise ValueError('미분 스텐실이 방사면 근접점에 닿습니다. 위치·간격·범위를 변경하세요.')
            real, imag = self.engine.calculate_field_slice(
                points, self.snapshot.sources_mm, self.snapshot.phases_rad, self.snapshot.amplitudes,
                self.mode_idx, has_taichi=self.has_taichi, has_pytorch=self.has_pytorch,
                field_config=self.snapshot.field_config, normals=self.snapshot.normals,
                aperture_radii_mm=self.snapshot.aperture_radii_mm)
            result[start:start + 512] = real + 1j * imag
        return result

    def potential(self, receivers_mm, step_mm):
        points = positions(receivers_mm)
        offsets = np.concatenate([np.zeros((1, 3)),
                                  (np.eye(3)[:, None, :] * np.array([-2., -1., 1., 2.])[None, :, None]).reshape(-1, 3)])
        values = self.pressure((points[:, None, :] + offsets[None, :, :] * step_mm).reshape(-1, 3)).reshape(len(points), 13)
        grad = np.einsum('pac,c->pa', values[:, 1:].reshape(-1, 3, 4), [1., -8., 8., -1.]) / (12 * step_mm * 1e-3)
        potential = self.coefficients['M1'] * np.abs(values[:, 0]) ** 2 - self.coefficients['M2'] * np.sum(np.abs(grad) ** 2, axis=1)
        if not np.isfinite(potential).all():
            raise ValueError('퍼텐셜 계산 결과가 유한하지 않습니다.')
        return potential

    def force_and_diagonal(self, receivers_mm, step_mm):
        points = positions(receivers_mm)
        offsets = np.concatenate([np.zeros((1, 3)),
                                  (np.eye(3)[:, None, :] * np.array([-2., -1., 1., 2.])[None, :, None]).reshape(-1, 3)])
        values = self.potential((points[:, None, :] + offsets[None, :, :] * step_mm).reshape(-1, 3), step_mm).reshape(len(points), 13)
        sides = values[:, 1:].reshape(-1, 3, 4)
        h = step_mm * 1e-3
        force = -np.einsum('pac,c->pa', sides, [1., -8., 8., -1.]) / (12 * h)
        diagonal = (np.einsum('pac,c->pa', sides, [-1., 16., 16., -1.]) - 30 * values[:, :1]) / (12 * h ** 2)
        if not np.isfinite(force).all() or not np.isfinite(diagonal).all():
            raise ValueError('힘 또는 복원 미분 결과가 유한하지 않습니다.')
        return force, diagonal, values[:, 0]

    def stiffness_matrix(self, centre_mm, step_mm):
        _, diagonal, _ = self.force_and_diagonal([centre_mm], step_mm)
        matrix = np.diag(diagonal[0])
        first = np.array([1., -8., 8., -1.]) / 12
        offsets = np.array([-2., -1., 1., 2.])
        for a, b in ((0, 1), (0, 2), (1, 2)):
            points = np.tile(centre_mm, (16, 1)).astype(float)
            points[:, a] += np.repeat(offsets, 4) * step_mm
            points[:, b] += np.tile(offsets, 4) * step_mm
            values = self.potential(points, step_mm).reshape(4, 4)
            matrix[a, b] = matrix[b, a] = first @ values @ first / (step_mm * 1e-3) ** 2
        return matrix

    def analyze(self, centre_mm, progress=None):
        self._check_cancel()
        centre = positions([centre_mm], '스캔 중심')[0]
        offsets = np.linspace(-self.settings.span_mm, self.settings.span_mm, self.settings.samples)
        scan_points = centre[None, None, :] + np.eye(3)[:, None, :] * offsets[None, :, None]
        points = np.concatenate([centre[None, :], scan_points.reshape(-1, 3)])
        matrices, forces, diagonals, potentials = [], [], [], []
        steps = [self.settings.derivative_step_mm / scale for scale in (1, 2, 4)]
        for index, step in enumerate(steps):
            f, d, u = self.force_and_diagonal(points, step)
            matrices.append(self.stiffness_matrix(centre, step))
            forces.append(f); diagonals.append(d); potentials.append(u)
            if progress:
                progress(int((index + 1) * 30))
        force_scale = max(np.max(np.linalg.norm(forces[-1], axis=1)),
                          np.linalg.norm(matrices[-1]) / self.snapshot.field_config.k_m,
                          np.finfo(float).tiny)
        stiffness_scale = max(np.max(np.abs(diagonals[-1])), np.linalg.norm(matrices[-1]), np.finfo(float).tiny)
        convergence = []
        matrix_error = 0.
        for index in (0, 1):
            df = float(np.max(np.linalg.norm(forces[index + 1] - forces[index], axis=1)) / force_scale)
            dk = float(max(np.max(np.abs(diagonals[index + 1] - diagonals[index])),
                           np.linalg.norm(matrices[index + 1] - matrices[index])) / stiffness_scale)
            matrix_error = max(matrix_error, np.linalg.norm(matrices[index + 1] - matrices[index], ord=2))
            convergence.append(dict(from_step_mm=steps[index], to_step_mm=steps[index + 1], force_relative_change=df,
                                    stiffness_relative_change=dk))
        converged = all(max(row['force_relative_change'], row['stiffness_relative_change']) <= self.settings.relative_tolerance
                        for row in convergence)
        diagnosis = restoring_diagnosis(matrices[-1], uncertainty=2 * matrix_error)
        ka = self.snapshot.field_config.k_m * self.settings.particle.radius_mm * 1e-3
        # 0.3 is a conservative software diagnostic gate, not a universal physical cutoff.
        model_in_range = ka <= .3
        if not converged or not model_in_range:
            diagnosis['status'] = 'unresolved'
        gravity = self.settings.particle.mass_kg * np.asarray(self.settings.gravity_m_s2)
        pressure = self.pressure(points)
        self._check_cancel()
        result = dict(schema_version=1, model='gorkov_small_sphere_fixed_drive', valid=True,
                      pressure_calibrated=False, force_units='N_star_at_assumed_Pa_scale',
                      stiffness_units='N_star_per_m', potential_units='J_star_at_assumed_Pa_scale',
                      snapshot=self.snapshot.to_dict(), settings=self.settings.to_dict(),
                      centre_mm=centre, offsets_mm=offsets, scan_points_mm=scan_points,
                      pressure_magnitude=np.abs(pressure[1:]).reshape(3, -1),
                      potential=potentials[-1][1:].reshape(3, -1),
                      acoustic_force=forces[-1][1:].reshape(3, -1, 3),
                      stiffness_diagonal=diagonals[-1][1:].reshape(3, -1, 3),
                      centre_force=forces[-1][0], centre_stiffness=matrices[-1],
                      gravity_force_N=gravity, mass_kg=self.settings.particle.mass_kg,
                      conditional_total_force=forces[-1][1:].reshape(3, -1, 3) + gravity,
                      conditional_centre_residual=forces[-1][0] + gravity,
                      gravity_equilibrium_status='unavailable_uncalibrated_pressure',
                      restoring=diagnosis, convergence=convergence, converged=converged,
                      ka=ka, small_particle_gate=.3, model_in_range=model_in_range,
                      coefficients=self.coefficients, backend=self.engine.last_backend)
        if progress:
            progress(100)
        return result


def json_result(result):
    """Convert only supported numerical containers; callers write JSON with allow_nan=False."""
    if isinstance(result, np.ndarray):
        return result.tolist()
    if isinstance(result, np.generic):
        return result.item()
    if isinstance(result, dict):
        return {key: json_result(value) for key, value in result.items()}
    if isinstance(result, (tuple, list)):
        return [json_result(value) for value in result]
    return result
