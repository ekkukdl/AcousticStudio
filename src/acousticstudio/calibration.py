"""Software-order relative gain/phase calibration with explicit provenance.

Command correction is additive: command = ideal_phase + phase_offset_rad.
An observed positive emitter phase error needs a negative command offset.
These records never establish an absolute pressure calibration.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from math import isfinite
from numbers import Integral
from pathlib import Path


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def validate_mapping(values, count):
    values = tuple(values)
    if (len(values) != count or any(not isinstance(value, Integral) or isinstance(value, bool) for value in values)
            or set(values) != set(range(count))):
        raise ValueError(f'채널 맵은 정수 0~{count - 1}을 한 번씩 포함해야 합니다.')
    return tuple(int(value) for value in values)


def validate_active(values, count):
    values = tuple(values)
    if count <= 0 or len(values) != count or any(type(value) is not bool for value in values):
        raise ValueError('활성 상태는 채널 수와 일치하는 참/거짓 배열이어야 합니다.')
    return values


def layout_signature(geometries, transducers):
    """Bind ordered CAD channels and source hashes; CAD pose is independent.

    Legacy arrays bind their saved matrices; moving that array requires a new
    calibration. Control-point motion never affects this signature.
    """
    by_id = {geometry['instance_id']: geometry for geometry in geometries}
    records = []
    for index, tx in enumerate(transducers):
        if 'geometry_instance' in tx:
            geometry = by_id[tx['geometry_instance']]
            records.append(dict(instance=geometry['instance_id'], channel=tx['geometry_channel'],
                                geometry_id=geometry['geometry_id'], sources=geometry['sources'],
                                base_matrix=geometry['elements'][tx['geometry_channel']]['base_matrix']))
        else:
            records.append(dict(legacy_index=index, matrix=tx.get('matrix', [])))
    payload = json.dumps(records, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class CalibrationRevision:
    calibration_id: str
    timestamp_utc: str
    note: str

    def __post_init__(self):
        if any(not isinstance(value, str) or not value.strip() for value in asdict(self).values()):
            raise ValueError('보정 이력에는 ID·시간·설명이 필요합니다.')
        validate_timestamp(self.timestamp_utc)


def validate_timestamp(value):
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
            raise ValueError()
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError('보정 시간은 시간대가 포함된 UTC ISO 날짜여야 합니다.') from exc


@dataclass(frozen=True)
class Calibration:
    calibration_id: str
    board_profile: str
    geometry_signature: str
    phase_offsets_rad: tuple
    source_gains: tuple
    enabled: tuple
    created_utc: str
    channel_map: tuple | None = None
    mapping_status: str = 'identity_unverified'
    mapping_source: str = ''
    mapping_sha256: str = ''
    provenance: str = 'manual_unverified'
    measurement_conditions: str = ''
    firmware_id: str = ''
    wiring_revision: str = ''
    gain_units: str = 'relative_to_nominal'
    pressure_calibrated: bool = False
    schema_version: int = 1
    history: tuple = ()

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError('지원하지 않는 보정 파일 버전입니다.')
        for name in ('calibration_id', 'board_profile', 'geometry_signature', 'created_utc'):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError('보정 ID·보드·형상·시간을 기록해야 합니다.')
        if not re_hash(self.geometry_signature):
            raise ValueError('형상 서명은 SHA256이어야 합니다.')
        validate_timestamp(self.created_utc)
        for name in ('measurement_conditions', 'firmware_id', 'wiring_revision', 'mapping_source', 'mapping_sha256'):
            if not isinstance(getattr(self, name), str):
                raise ValueError('보정 출처와 측정 조건은 문자열이어야 합니다.')
        phases, gains = tuple(float(value) for value in self.phase_offsets_rad), tuple(float(value) for value in self.source_gains)
        count = len(phases)
        if not 1 <= count <= 4096 or len(gains) != count or not all(isfinite(value) for value in (*phases, *gains)) or any(value < 0 for value in gains):
            raise ValueError('보정 위상/이득은 같은 채널 수의 유한한 배열이고 이득은 비음수여야 합니다.')
        object.__setattr__(self, 'phase_offsets_rad', phases)
        object.__setattr__(self, 'source_gains', gains)
        object.__setattr__(self, 'enabled', validate_active(self.enabled, count))
        if self.channel_map is not None:
            object.__setattr__(self, 'channel_map', validate_mapping(self.channel_map, count))
        if self.mapping_status not in ('identity_unverified', 'manual_unverified', 'candidate_unverified', 'measured'):
            raise ValueError('알 수 없는 채널 맵 출처 상태입니다.')
        if self.mapping_status == 'identity_unverified' and self.channel_map is not None and self.channel_map != tuple(range(count)):
            raise ValueError('항등 맵 상태로 비항등 맵을 저장할 수 없습니다.')
        if self.mapping_status == 'candidate_unverified' and (self.channel_map is None or not self.mapping_source or not re_hash(self.mapping_sha256)):
            raise ValueError('후보 맵에는 맵·파일 출처·SHA256이 필요합니다.')
        if self.mapping_sha256 and not re_hash(self.mapping_sha256):
            raise ValueError('채널 맵 SHA256이 잘못되었습니다.')
        if self.provenance not in ('manual_unverified', 'measured'):
            raise ValueError('보정 출처는 수동 미검증 또는 실측이어야 합니다.')
        if (self.provenance == 'measured' or self.mapping_status == 'measured') and not all(
                value.strip() for value in (self.measurement_conditions, self.firmware_id, self.wiring_revision)):
            raise ValueError('실측 표시는 측정 조건·펌웨어·배선 버전이 필요합니다.')
        if self.gain_units != 'relative_to_nominal' or self.pressure_calibrated is not False:
            raise ValueError('T5 보정은 상대 이득만 지원하며 절대 음압 보정으로 표시할 수 없습니다.')
        if not all(isinstance(item, CalibrationRevision) for item in self.history):
            raise ValueError('보정 이력 형식이 잘못되었습니다.')
        object.__setattr__(self, 'history', tuple(self.history))

    @property
    def count(self):
        return len(self.phase_offsets_rad)

    @property
    def active(self):
        return tuple(enabled and gain > 0 for enabled, gain in zip(self.enabled, self.source_gains))

    def validate_context(self, count, profile, signature):
        if (self.count != count or self.board_profile != profile or self.geometry_signature != signature):
            raise ValueError('보정의 채널 수·보드 프로파일·배열 서명이 현재 배열과 다릅니다.')

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError('보정 데이터는 객체여야 합니다.')
        values = dict(data)
        try:
            values['history'] = tuple(CalibrationRevision(**item) for item in values.get('history', []))
            return cls(**values)
        except (TypeError, KeyError) as exc:
            raise ValueError('보정 데이터 필드가 잘못되었습니다.') from exc

    @classmethod
    def load(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text(encoding='utf-8')))

    def save(self, path):
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def re_hash(value):
    return isinstance(value, str) and len(value) == 64 and all(char in '0123456789abcdef' for char in value)


def load_candidate_map(path, count):
    path = Path(path)
    raw = path.read_bytes()
    data = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(data, dict) or not data.get('definition', '').startswith('map[physical_frame_channel] = software_channel;'):
        raise ValueError('후보 맵은 physical_frame_channel → software_channel 방향이어야 합니다.')
    return validate_mapping(data['channel_map'], count), str(path), hashlib.sha256(raw).hexdigest()
