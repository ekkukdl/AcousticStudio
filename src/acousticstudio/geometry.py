"""CAD tunnel data in mm; this module has no CAD, Qt or VTK dependency."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

import numpy as np

CREO_PRESET_LABEL = 'Creo 8면 터널 · 8기판 × 32채널'
GEOMETRY_ID = 'creo_tunnel8_panel32_frame_R2'
SOURCE_DIR = Path(__file__).resolve().parents[2] / '구상도' / 'outputs' / 'panel_8faces_32ch_R1'


def rigid_matrix(values):
    matrix = np.asarray(values, dtype=np.float64)
    if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
        raise ValueError('배열 변환은 유한한 4×4 행렬이어야 합니다.')
    rotation = matrix[:3, :3]
    if (not np.allclose(matrix[3], [0, 0, 0, 1], atol=1e-8)
            or not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-8)
            or not np.isclose(np.linalg.det(rotation), 1., atol=1e-8)):
        raise ValueError('CAD 배열에는 이동과 회전만 적용할 수 있습니다.')
    return matrix


def emitting_matrix(position, normal):
    """Local +Z emits; local origin is the emitting face, not body centre."""
    normal = np.asarray(normal, dtype=np.float64)
    up = np.array([0., 0., 1.]) if abs(normal[2]) < 0.9 else np.array([0., 1., 0.])
    axis_x = np.cross(up, normal)
    axis_x /= np.linalg.norm(axis_x)
    matrix = np.eye(4)
    matrix[:3, :3] = np.column_stack([axis_x, np.cross(normal, axis_x), normal])
    matrix[:3, 3] = position
    return matrix


def load_creo_tunnel(source_dir=None):
    """Read existing array/assembly JSON; never regenerate a Tube or CAD solid."""
    directory = Path(source_dir) if source_dir is not None else SOURCE_DIR
    inputs = [directory / 'array_positions_256.json',
              directory / 'mechanical' / 'creo32_frame_R2' / 'geometry_checks.json']
    raw = [path.read_bytes() for path in inputs]
    array, assembly = [json.loads(content.decode('utf-8-sig')) for content in raw]
    if array.get('units') != 'mm' or assembly.get('units') != 'mm' or not assembly.get('ok'):
        raise ValueError('CAD 배열과 조립체의 mm 좌표 검증 기록이 필요합니다.')
    parameters = array['parameters']
    if (parameters.get('faces'), parameters.get('rows'), parameters.get('columns')) != (8, 8, 4):
        raise ValueError('Creo 프리셋은 8면 × 32송신기 배열이어야 합니다.')
    instance_id = str(uuid4())
    elements = []
    for source in array['elements']:
        element = deepcopy(source)
        element.update(id=f"{instance_id}/face{source['face']}/{source['reference']}",
                       source_position_mm=source['position_mm'], source_normal=source['normal'],
                       amplitude=1., enabled=True, frequency_hz=40000.,
                       effective_aperture_radius_mm=None, model='CAD 16mm TX')
        element['base_matrix'] = emitting_matrix(source['position_mm'], source['normal']).tolist()
        element['matrix'] = deepcopy(element['base_matrix'])
        elements.append(element)
    supports = []
    if len(assembly['face_matrices']) != 8:
        raise ValueError('Creo PCB 배치 행렬 8개가 필요합니다.')
    for face, row_matrix in enumerate(assembly['face_matrices']):
        matrix = rigid_matrix(np.asarray(row_matrix).T).tolist()
        supports.append(dict(kind='pcb', face=face, base_matrix=matrix, matrix=deepcopy(matrix)))
    for component in assembly['top_components']:
        if component['model'] == 'ring8_32_r2':
            matrix = rigid_matrix(np.asarray(component['matrix']).T).tolist()
            supports.append(dict(kind='ring', base_matrix=matrix, matrix=deepcopy(matrix)))
    if len(supports) != 10:
        raise ValueError('Creo 프레임 링 2개와 PCB 8개가 필요합니다.')
    geometry = dict(schema_version=1, geometry_id=GEOMETRY_ID, instance_id=instance_id,
                    units='mm', coordinate_system=array['coordinate_system'],
                    status=array['status'], parameters=deepcopy(parameters),
                    frame=deepcopy(assembly['frame']), elements=elements, supports=supports,
                    world_transform=np.eye(4).tolist(),
                    sources=[dict(path=str(path.relative_to(directory)).replace('\\', '/'),
                                  sha256=sha256(content).hexdigest()) for path, content in zip(inputs, raw)])
    validate_geometry(geometry)
    return geometry


def validate_geometry(geometry):
    """Validate a saved snapshot without requiring the original CAD files."""
    if geometry.get('schema_version') != 1 or geometry.get('geometry_id') != GEOMETRY_ID or geometry.get('units') != 'mm':
        raise ValueError('지원하지 않는 CAD 배열 스키마입니다.')
    pose = rigid_matrix(geometry['world_transform'])
    elements = geometry['elements']
    if len(elements) != 256 or [e['channel'] for e in elements] != list(range(256)):
        raise ValueError('CAD 배열은 소프트웨어 순서의 256개 채널을 유지해야 합니다.')
    if len({e['id'] for e in elements}) != 256:
        raise ValueError('CAD 송신기 ID가 중복되었습니다.')
    for index, element in enumerate(elements):
        if (element['face'], element['local_channel'], element['row'], element['column']) != (index // 32, index % 32, index % 32 // 4, index % 4):
            raise ValueError('CAD 송신기의 면·로컬 채널·행·열 순서가 잘못되었습니다.')
        position = np.asarray(element['position_mm'], dtype=float)
        normal = np.asarray(element['normal'], dtype=float)
        base = rigid_matrix(element['base_matrix'])
        matrix = rigid_matrix(element['matrix'])
        if (position.shape != (3,) or normal.shape != (3,)
                or not np.allclose(matrix, pose @ base, atol=1e-7)
                or not np.allclose(position, matrix[:3, 3], atol=1e-7)
                or not np.allclose(normal, matrix[:3, 2], atol=1e-7)):
            raise ValueError('CAD 방사면 좌표·법선과 배열 변환이 일치하지 않습니다.')
        amplitude = element['amplitude']
        if not np.isfinite(amplitude) or amplitude < 0:
            raise ValueError('CAD 구동 진폭은 유한한 비음수 가중치여야 합니다.')
        if type(element.get('enabled', True)) is not bool:
            raise ValueError('CAD 송신기 활성 상태는 참/거짓이어야 합니다.')
    supports = geometry['supports']
    if [s.get('face') for s in supports if s['kind'] == 'pcb'] != list(range(8)) or sum(s['kind'] == 'ring' for s in supports) != 2:
        raise ValueError('CAD 구조물은 PCB 8개와 프레임 링 2개여야 합니다.')
    for support in supports:
        if not np.allclose(rigid_matrix(support['matrix']), pose @ rigid_matrix(support['base_matrix']), atol=1e-7):
            raise ValueError('CAD 구조물 변환이 송신기 배열과 일치하지 않습니다.')
    return geometry


def transform_geometry(geometry, matrix):
    """Transform the whole immutable layout, including normals and supports."""
    result = deepcopy(geometry)
    delta = rigid_matrix(matrix)
    result['world_transform'] = (delta @ rigid_matrix(geometry['world_transform'])).tolist()
    for element in result['elements']:
        transformed = delta @ np.asarray(element['matrix'])
        element['matrix'] = transformed.tolist()
        element['position_mm'] = transformed[:3, 3].tolist()
        element['normal'] = transformed[:3, 2].tolist()
    for support in result['supports']:
        support['matrix'] = (delta @ np.asarray(support['matrix'])).tolist()
    return validate_geometry(result)
