"""Standard-library-only dependency catalog shared by both installers."""
from importlib.metadata import distributions


PACKAGE_INFO = {
    'PySide6': {'type': '필수', 'size': '~200MB', 'desc': 'GUI 프레임워크'},
    'pyvista': {'type': '필수', 'size': '~40MB', 'desc': '3D 렌더링 엔진'},
    'pyvistaqt': {'type': '필수', 'size': '~1MB', 'desc': 'PyVista와 Qt 뷰어 연결'},
    'vtk': {'type': '필수', 'size': '~100MB', 'desc': '3D 시각화 기반'},
    'numpy': {'type': '필수', 'size': '~15MB', 'desc': '수치 연산 배열 처리'},
    'scipy': {'type': '필수', 'size': '~45MB', 'desc': '원형 피스톤 Bessel 함수와 과학 계산'},
    'numba': {'type': '필수', 'size': '~10MB', 'desc': 'CPU 병렬 최적화'},
    'matplotlib': {'type': '필수', 'size': '~10MB', 'desc': '그래프와 색상 처리'},
    'levitate': {'type': '필수', 'size': '~1MB', 'desc': '음향 방사력 모델'},
    'pyserial': {'type': '필수', 'size': '~2MB', 'desc': '하드웨어 USB 통신'},
    'taichi': {'type': '선택', 'size': '~30MB', 'desc': '다중/GPU 병렬 가속 연산'},
    'torch': {'type': '선택', 'size': '~2.5GB', 'desc': 'NVIDIA 그래픽카드 연산'},
    'psutil': {'type': '선택', 'size': '~1MB', 'desc': 'CPU 리소스 모니터링'},
    'GPUtil': {'type': '선택', 'size': '~1MB', 'desc': 'GPU 리소스 모니터링'},
}


def installed_package_names():
    return {name.lower().replace('_', '-') for dist in distributions()
            if (name := dist.metadata.get('Name'))}
