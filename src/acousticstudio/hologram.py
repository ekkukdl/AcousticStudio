"""Phase-only IBP adapted from Ultraino Kinoforms.java (MIT, asiermarzo 2017).

See THIRD_PARTY_NOTICES.md. Viewer positions are mm, phases rad; pressure is
relative/uncalibrated. Source gains remain fixed and are not drive amplitudes.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
from threading import Event
from time import perf_counter

import numpy as np

from acousticstudio.field_backends import reduce_field
from acousticstudio.field_model import FieldConfig, positions, propagation_matrix, source_parameters

TRAP_TYPES = ('focus', 'twin', 'standing_wave')
# Right-handed conversion: Java X -> X, Java Y -> Z, Java Z -> -Y.
JAVA_TO_STUDIO = np.array([[1., 0., 0.], [0., 0., -1.], [0., 1., 0.]])


class HologramCancelled(Exception):
    pass


@dataclass(frozen=True)
class HologramSettings:
    iterations: int = 50
    phase_tolerance_rad: float = 1e-6
    default_trap_type: str = 'focus'
    initialization: str = 'zeros'

    def __post_init__(self):
        if not isinstance(self.iterations, int) or isinstance(self.iterations, bool) or not 1 <= self.iterations <= 2000:
            raise ValueError('Kinoforms 반복 수는 1~2000의 정수여야 합니다.')
        if not np.isfinite(self.phase_tolerance_rad) or not 0 <= self.phase_tolerance_rad <= .1:
            raise ValueError('위상 변화 허용값은 0~0.1rad의 유한한 값이어야 합니다. 0은 고정 반복입니다.')
        if self.default_trap_type not in TRAP_TYPES or self.initialization not in ('zeros', 'current'):
            raise ValueError('Kinoforms 기본 트랩/초기 위상 설정이 잘못되었습니다.')

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class TrapTarget:
    position_mm: tuple
    trap_type: str = 'focus'
    weight: float = 1.
    direction: tuple = (1., 0., 0.)

    def __post_init__(self):
        point = positions([self.position_mm], '트랩 중심')[0]
        direction = positions([self.direction], '트랩 방향')[0]
        length = np.linalg.norm(direction)
        if self.trap_type not in TRAP_TYPES:
            raise ValueError('지원하는 Kinoforms 트랩은 Focus/Twin/Standing Wave입니다.')
        if not np.isfinite(self.weight) or self.weight <= 0 or not np.isfinite(length) or length == 0:
            raise ValueError('목표 가중치는 양수이고 방향은 유한한 비영 벡터여야 합니다.')
        object.__setattr__(self, 'position_mm', tuple(float(x) for x in point))
        object.__setattr__(self, 'direction', tuple(float(x) for x in direction / length))

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_point(cls, point, default_type='focus'):
        metadata = point.get('hologram_target', {})
        if not isinstance(metadata, dict):
            raise ValueError('트랩 메타데이터는 객체여야 합니다.')
        trap_type = metadata.get('trap_type', default_type)
        direction = metadata.get('direction', (0., 0., 1.) if trap_type == 'standing_wave' else (1., 0., 0.))
        return cls(tuple(point[key] for key in ('x', 'y', 'z')), trap_type, metadata.get('weight', 1.), direction)


def virtual_targets(targets, config):
    """Original separations are offsets: Twin ±λ/1.5; Standing ±λ/2."""
    if not targets or len(targets) > 256 or not all(isinstance(t, TrapTarget) for t in targets):
        raise ValueError('Kinoforms에는 1~256개의 명시적인 트랩 목표가 필요합니다.')
    wavelength_mm = config.sound_speed_m_s / config.frequency_hz * 1000
    points, signs, weights, groups = [], [], [], []
    for target in targets:
        start = len(points)
        centre = np.asarray(target.position_mm)
        if target.trap_type == 'focus':
            points.append(centre); signs.append(1.); weights.append(target.weight)
        else:
            offset = wavelength_mm / (1.5 if target.trap_type == 'twin' else 2.)
            displacement = np.asarray(target.direction) * offset
            points.extend((centre + displacement, centre - displacement))
            signs.extend((1., -1.)); weights.extend((target.weight, target.weight))
        groups.append((start, len(points)))
    points = np.asarray(points)
    if not np.isfinite(points).all():
        raise ValueError('가상점 위치를 유한하게 계산할 수 없습니다.')
    # Duplicate constraints make target weights/relative phases ambiguous.
    if len(points) > 1:
        distance = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=-1)
        distance[np.diag_indices(len(points))] = np.inf
        if np.any(distance <= config.min_distance_m * 1000):
            raise ValueError('가상점이 중복되거나 최소 거리 이내입니다. 트랩 위치·방향을 변경하세요.')
    return points, np.asarray(signs), np.asarray(weights), groups


def input_signature(sources, normals, gains, radii, config, targets, settings=None):
    """Content key; GUI/worker objects never enter the cache."""
    digest = hashlib.sha256()
    for array in (sources, normals, gains):
        array = np.ascontiguousarray(array, dtype=np.float64)
        digest.update(str(array.shape).encode('ascii')); digest.update(array.tobytes())
    payload = dict(config=config.to_dict(), radii=None if radii is None else list(radii),
                   targets=[t.to_dict() for t in targets])
    if settings is not None:
        payload['settings'] = settings.to_dict()
    digest.update(json.dumps(payload, sort_keys=True, allow_nan=False).encode('utf-8'))
    return digest.hexdigest()


def constrain_field(field, signs, weights, groups, anchors):
    anchors = anchors.copy()
    result = np.empty_like(field)
    floor = max(float(np.max(np.abs(field))) * 1e-14, np.finfo(float).tiny)
    for index, (start, end) in enumerate(groups):
        if abs(field[start]) > floor:
            anchors[index] = field[start] / abs(field[start])
        # At zero pressure keep the previous anchor, initialized to phase zero.
        result[start:end] = anchors[index] * signs[start:end] * weights[start:end]
    if not np.isfinite(result).all():
        raise ValueError('목표장 제약 결과가 유한하지 않습니다.')
    return result, anchors


def field_metrics(field, constrained, weights):
    norm = np.linalg.norm(field)
    if not np.isfinite(norm) or norm <= np.finfo(float).tiny:
        raise ValueError('가상점 음장이 0이어서 잔차/균일도를 진단할 수 없습니다.')
    target_norm = np.linalg.norm(constrained)
    if not np.isfinite(target_norm) or target_norm <= np.finfo(float).tiny:
        raise ValueError('목표장 가중치의 수치 범위가 너무 크거나 작습니다.')
    scale = max(0., float(np.vdot(constrained / target_norm, field).real / target_norm))
    normalized = np.abs(field) / weights
    metrics = dict(relative_residual=float(np.linalg.norm(field - scale * constrained) / norm),
                   weighted_uniformity=float(np.min(normalized) / np.max(normalized)), fitted_pressure_scale=scale)
    if not np.isfinite(list(metrics.values())).all():
        raise ValueError('제약 잔차/균일도를 유한하게 계산할 수 없습니다.')
    return metrics


class HologramSolver:
    """Single-entry Green cache, fixed gains, adjoint IBP and explicit cancellation."""
    def __init__(self):
        self._cache_key = self._green = None

    def solve(self, sources_mm, normals, gains, config, targets, settings=None, aperture_radii_mm=None,
              initial_phases=None, mode_idx=0, has_taichi=False, has_pytorch=False, cancelled=None, progress=None):
        started = perf_counter()
        settings = settings or HologramSettings()
        if not isinstance(config, FieldConfig) or not isinstance(settings, HologramSettings):
            raise ValueError('명시적인 공통 음장/Kinoforms 설정이 필요합니다.')
        cancellation = cancelled if cancelled is not None else Event()
        def check_cancel():
            if cancellation.is_set():
                raise HologramCancelled('Kinoforms 계산을 취소했습니다.')
        check_cancel()
        sources = positions(sources_mm, '방사면').copy()
        normals, _ = source_parameters(len(sources), normals, aperture_radii_mm, config)
        gains = np.array(gains, dtype=float, copy=True)
        if not len(sources) or gains.shape != (len(sources),) or not np.isfinite(gains).all() or np.any(gains < 0) or not np.any(gains > 0):
            raise ValueError('Kinoforms에는 비영 이득을 가진 송신기와 채널 수에 맞는 비음수 이득이 필요합니다.')
        phases = np.zeros(len(sources)) if initial_phases is None else np.array(initial_phases, dtype=float, copy=True)
        if phases.shape != gains.shape or not np.isfinite(phases).all():
            raise ValueError('초기 위상은 채널 수와 일치하는 유한한 rad 배열이어야 합니다.')
        if settings.initialization == 'zeros':
            phases[:] = 0.
        initial = phases.copy()
        targets = tuple(targets)
        virtual, signs, weights, groups = virtual_targets(targets, config)
        if len(virtual) * len(sources) > 2_000_000:
            raise ValueError('전파 행렬이 너무 큽니다. 목표점/송신기 수를 줄이세요.')
        if np.any(np.linalg.norm(virtual[:, None, :] - sources[None, :, :], axis=-1) <= config.min_distance_m * 1000):
            raise ValueError('가상점이 방사면 근접점에 닿습니다.')
        cache_key = input_signature(sources, normals, gains, aperture_radii_mm, config, targets)
        cache_hit = self._cache_key == cache_key
        if not cache_hit:
            green = propagation_matrix(virtual, sources, normals, aperture_radii_mm, config) * gains[None, :]
            check_cancel()
            self._cache_key, self._green = cache_key, green
        green = self._green
        adjoint = np.ascontiguousarray(green.conj().T)
        active = gains > 0
        drive = np.where(active, np.exp(1j * phases), 0j)
        anchors = np.ones(len(targets), dtype=complex)
        backends = []
        def reduce(matrix, values):
            check_cancel()
            output, backend = reduce_field(matrix, values, mode_idx, has_taichi, has_pytorch)
            if backend not in backends:
                backends.append(backend)
            return output
        field = reduce(green, drive)
        desired, anchors = constrain_field(field, signs, weights, groups, anchors)
        initial_metrics = field_metrics(field, desired, weights) if np.linalg.norm(field) > np.finfo(float).tiny else None
        history, phase_changes = [], []
        for index in range(settings.iterations):
            desired, anchors = constrain_field(field, signs, weights, groups, anchors)
            projected = reduce(adjoint, desired)
            magnitudes = np.abs(projected)
            supported = active & (magnitudes > max(np.max(magnitudes) * 1e-14, np.finfo(float).tiny))
            updated = drive.copy()
            # Zero backprojection preserves the previous phase; disabled channels remain zero.
            updated[supported] = projected[supported] / magnitudes[supported]
            overlap = np.vdot(drive[active], updated[active])
            common = np.angle(overlap) if abs(overlap) else 0.
            change = float(np.max(np.abs(np.angle(updated[active] * drive[active].conj() * np.exp(-1j * common)))))
            drive = updated
            field = reduce(green, drive)
            desired, anchors = constrain_field(field, signs, weights, groups, anchors)
            metrics = field_metrics(field, desired, weights)
            history.append(metrics['relative_residual']); phase_changes.append(change)
            if progress:
                progress(int((index + 1) / settings.iterations * 100))
            if settings.phase_tolerance_rad > 0 and change <= settings.phase_tolerance_rad:
                break
        check_cancel()
        phases = np.angle(drive) % (2 * np.pi); phases[~active] = 0.
        result = dict(schema_version=1, algorithm='Kinoforms', constraint='phase_only_fixed_source_gains',
                      pressure_calibrated=False, pressure_units='relative_uncalibrated',
                      settings=settings.to_dict(), targets=[t.to_dict() for t in targets],
                      snapshot=dict(sources_mm=sources, normals=normals, amplitudes=gains,
                                    aperture_radii_mm=None if aperture_radii_mm is None else list(aperture_radii_mm),
                                    field_config=config.to_dict(), initial_phases_rad=initial),
                      phases_rad=phases, drive_amplitudes=active.astype(float),
                      virtual_points_mm=virtual, target_signs=signs, target_weights=weights, groups=groups,
                      field_real=field.real, field_imag=field.imag, pressure_magnitude=np.abs(field),
                      initial_metrics=initial_metrics, metrics=metrics, residual_history=np.asarray(history),
                      phase_change_history_rad=np.asarray(phase_changes), iterations_completed=len(history),
                      stationary=settings.phase_tolerance_rad > 0 and phase_changes[-1] <= settings.phase_tolerance_rad,
                      cache_hit=cache_hit, input_key=input_signature(sources, normals, gains, aperture_radii_mm, config, targets, settings),
                      backend=backends[-1], backends=backends, elapsed_seconds=perf_counter() - started)
        if progress:
            progress(100)
        return result
