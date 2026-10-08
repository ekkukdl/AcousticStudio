"""World-space slice manipulation, in millimetres; no Qt or actor state."""
import numpy as np

PLANE_AXES = {'xy': 2, 'xz': 1, 'yz': 0}


def ray_plane_intersection(origin, direction, plane, offset):
    origin, direction = np.asarray(origin, dtype=float), np.asarray(direction, dtype=float)
    if origin.shape != (3,) or direction.shape != (3,) or not np.isfinite([origin, direction]).all():
        raise ValueError('픽킹 광선은 유한한 XYZ 좌표여야 합니다.')
    if plane not in PLANE_AXES or not np.isfinite(offset):
        raise ValueError('단면과 위치가 잘못되었습니다.')
    axis = PLANE_AXES[plane]
    length = np.linalg.norm(direction)
    if length == 0 or abs(direction[axis]) <= 1e-10 * length:
        return None
    distance = (offset - origin[axis]) / direction[axis]
    if distance < 0:
        return None
    result = origin + distance * direction
    result[axis] = offset
    return result


def translated_points(points, destination):
    points, destination = np.asarray(points, dtype=float), np.asarray(destination, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or not len(points) or destination.shape != (3,):
        raise ValueError('이동할 제어점과 XYZ 목적지가 필요합니다.')
    if not np.isfinite(points).all() or not np.isfinite(destination).all():
        raise ValueError('이동 좌표는 유한해야 합니다.')
    return points + destination - points.mean(axis=0)
