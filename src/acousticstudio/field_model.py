"""Shared free-field propagation in SI units (viewer boundary: mm).

Ultraino sinc propagation is adapted from CalcField.java, Copyright (c) 2017
asiermarzo, MIT license. See THIRD_PARTY_NOTICES.md. The piston model is distinct.
Neither model includes a baffle, reflections, or measured rear attenuation.
"""
from dataclasses import asdict, dataclass

import numpy as np
from scipy.special import j1


MODELS = ('point_source', 'ultraino_sinc', 'circular_piston')


@dataclass(frozen=True)
class FieldConfig:
    model: str = 'point_source'
    frequency_hz: float = 40000.
    sound_speed_m_s: float = 343.
    density_kg_m3: float = 1.2040847588826422
    source_strength: float = 1.  # relative pressure at 1 m, NOT a measured Pa value
    aperture_radius_mm: float | None = None  # explicit fallback, never CAD body radius
    min_distance_m: float = 1e-6  # numerical regularization, not a near-field model

    def __post_init__(self):
        if self.model not in MODELS:
            raise ValueError(f'지원하지 않는 방향성 모델: {self.model}')
        for name in ('frequency_hz', 'sound_speed_m_s', 'density_kg_m3',
                     'source_strength', 'min_distance_m'):
            value = getattr(self, name)
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f'{name} 값은 유한한 양수여야 합니다.')
        if self.aperture_radius_mm is not None:
            if not np.isfinite(self.aperture_radius_mm) or self.aperture_radius_mm <= 0:
                raise ValueError('유효 개구 반경은 유한한 양수(mm)여야 합니다.')

    @property
    def k_m(self):
        return 2 * np.pi * self.frequency_hz / self.sound_speed_m_s

    def to_dict(self):
        return asdict(self)


def positions(values, name='좌표'):
    values = np.asarray(values, dtype=np.float64)
    if values.shape == (0,):
        values = values.reshape(0, 3)
    if values.ndim != 2 or values.shape[1] != 3 or not np.isfinite(values).all():
        raise ValueError(f'{name}는 유한한 (N, 3) 배열이어야 합니다.')
    return np.ascontiguousarray(values)


def source_parameters(count, normals, aperture_radii_mm, config):
    # Legacy API defaults to its local +Z convention. CAD callers supply real normals.
    normals = np.tile([0., 0., 1.], (count, 1)) if normals is None else positions(normals, '법선')
    if len(normals) != count:
        raise ValueError('법선의 채널 수가 일치하지 않습니다.')
    lengths = np.linalg.norm(normals, axis=1)
    if not np.isfinite(lengths).all() or np.any(lengths <= 0):
        raise ValueError('법선은 0이 아닌 유한한 벡터여야 합니다.')
    normals = normals / lengths[:, None]
    supplied = [None] * count if aperture_radii_mm is None else list(aperture_radii_mm)
    if len(supplied) != count:
        raise ValueError('유효 개구의 채널 수가 일치하지 않습니다.')
    radii = np.zeros(count)
    for index, radius in enumerate(supplied):
        radius = config.aperture_radius_mm if radius is None else radius
        if radius is None:
            if config.model != 'point_source':
                raise ValueError('유효 음향 개구 반경이 미확정입니다. 반경을 입력하거나 무지향 모델을 선택하세요.')
        elif not np.isfinite(radius) or radius <= 0:
            raise ValueError('유효 개구 반경은 유한한 양수(mm)여야 합니다.')
        else:
            radii[index] = radius * 1e-3
    return normals, radii


def directivity(displacement_m, normals, radii_m, config):
    """displacement (P,N,3), output (P,N), signed and front/back symmetric."""
    if config.model == 'point_source':
        return np.ones(displacement_m.shape[:2])
    distances = np.linalg.norm(displacement_m, axis=-1)
    cosine = np.divide(np.einsum('pnc,nc->pn', displacement_m, normals), distances,
                       out=np.ones_like(distances), where=distances > 0)
    sin_angle = np.sqrt(np.maximum(0., 1. - np.clip(cosine, -1., 1.) ** 2))
    argument = config.k_m * radii_m[None, :] * sin_angle
    if config.model == 'ultraino_sinc':
        # Java M.sinc(x) = sin(x)/x; NumPy's sinc includes pi.
        return np.sinc(argument / np.pi)
    return np.divide(2 * j1(argument), argument, out=np.ones_like(argument), where=argument != 0)


def propagation_matrix(receivers_mm, sources_mm, normals=None, aperture_radii_mm=None, config=None):
    """Complex Green matrix G[P,N]; channel amplitudes and phases remain separate."""
    config = FieldConfig() if config is None else config
    receivers = positions(receivers_mm, '수신점') * 1e-3
    sources = positions(sources_mm, '방사면') * 1e-3
    normals, radii = source_parameters(len(sources), normals, aperture_radii_mm, config)
    diff = receivers[:, None, :] - sources[None, :, :]
    distance = np.linalg.norm(diff, axis=-1)
    if not np.isfinite(distance).all():
        raise ValueError('전파 거리를 유한하게 계산할 수 없습니다.')
    gain = config.source_strength * directivity(diff, normals, radii, config)
    gain /= np.maximum(distance, config.min_distance_m)
    result = gain * np.exp(1j * config.k_m * distance)
    if not np.isfinite(result).all():
        raise ValueError('전파 행렬이 유한하지 않습니다.')
    return np.ascontiguousarray(result)


@dataclass(frozen=True)
class SimulationMedium:
    """Per-calculation medium; does not mutate Levitate's shared materials.air."""
    c: float
    rho: float

    @property
    def compressibility(self):
        return 1 / (self.rho * self.c ** 2)

    @property
    def impedance(self):
        return self.rho * self.c


def levitate_transducer(config, radii_m, levitate):
    kwargs = dict(freq=config.frequency_hz, p0=config.source_strength,
                  medium=SimulationMedium(config.sound_speed_m_s, config.density_kg_m3))
    if config.model == 'point_source':
        return levitate.transducers.PointSource(**kwargs)

    class SharedDirectivity(levitate.transducers.PointSource):
        # PointSource supplies finite-difference directivity derivatives. These
        # inherit Levitate's stencil/step limitations; T3 must assess convergence.
        def directivity(self, source_positions, source_normals, receiver_positions):
            source_shape = source_positions.shape[1:]
            receiver_shape = receiver_positions.shape[1:]
            src = np.asarray(source_positions).reshape(3, -1).T
            nrm = np.asarray(source_normals).reshape(3, -1).T
            recv = np.asarray(receiver_positions).reshape(3, -1).T
            if len(src) != len(radii_m):
                raise ValueError('Levitate 개구와 송신기 채널 수가 일치하지 않습니다.')
            result = directivity(recv[:, None, :] - src[None, :, :], nrm, radii_m, config)
            return result.T.reshape(source_shape + receiver_shape)

    return SharedDirectivity(**kwargs)
