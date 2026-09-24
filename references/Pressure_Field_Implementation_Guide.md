# 음압 분포(Acoustic Pressure Field) 시각화 통합 가이드

기존에 성공적으로 구현하신 **위상(Phase) 시각화**에 이어, 실제 공간에 형성되는 **음압(Pressure) 분포**를 AcousticStudio (PyVista + PySide6) 환경에 통합하기 위한 가이드입니다.

## 1. 이론적 배경 (레일리 적분 - 점음원 근사)

초음파 위상 배열(Phased Array)의 음압을 실시간 3D 환경에서 계산하기 위해서는 복잡한 FEM/BEM 연산 대신 **레일리 적분(Rayleigh integral)의 점음원(Point-source) 근사법**을 사용하는 것이 가장 효율적입니다.

특정 공간 좌표 $(x, y, z)$에서의 복소 음압 $P(x,y,z)$는 배열 내 모든 트랜스듀서 $n$의 기여도를 합산하여 구합니다.

$$ P(x, y, z) = \sum_{n=1}^{N} P_0 \frac{e^{j (k r_n + \phi_n)}}{r_n} $$

*   $P_0$: 기준 진폭 (트랜스듀서 1개의 출력 강도)
*   $k$: 파수 (Wave number, $k = 2\pi f / c$)
*   $r_n$: $n$번째 트랜스듀서와 공간 좌표 $(x, y, z)$ 사이의 거리
*   $\phi_n$: $n$번째 트랜스듀서에 인가된 위상(Phase) 지연값

최종적으로 우리가 시각화할 실제 **음압 크기(Amplitude)**는 복소 음압의 절댓값 $|P(x,y,z)|$ 입니다.

## 2. 통합 구현 파일 (파이썬 코드)

동봉된 `pressure_field_example.py` 파일은 위 수식을 `numpy` 행렬 연산으로 최적화하여 구현한 예제 코드입니다. 이를 AcousticStudio 코드에 통합할 때 다음 과정을 거칩니다.

### A. PyVista 볼륨/단면 매쉬 생성
PyVista의 3D 공간을 모두 연산하면 연산량이 너무 많아 실시간(Interactive) 조작이 끊길 수 있습니다. 따라서 다음과 같은 접근을 추천합니다.
1.  **단면 시각화 (Slice Visualization):** 특정 평면(예: xy평면 또는 xz평면)에 대해서만 `StructuredGrid`를 생성하여 음압을 계산합니다.
2.  **등위면 시각화 (Isosurface):** 3D 볼륨(Volume) 격자를 성기게 생성하여 음압을 계산한 뒤, `grid.contour()`를 활용하여 음압이 특정 임계값(예: 초음파 트랩을 형성하는 노드 근처)을 넘는 영역만 3D 덩어리로 시각화합니다.

### B. 실시간 연산 최적화 (GPU 또는 Numba)
마우스 기즈모로 트랜스듀서를 드래그할 때마다 음압을 계산하려면 `numpy` 연산 속도가 중요합니다. 만약 해상도를 높여서 버벅임이 발생한다면:
*   `numba`의 `@jit(nopython=True, parallel=True)` 데코레이터를 사용하여 다중 코어 연산을 활성화하세요.
*   공간 내 트랜스듀서와 그리드 간의 거리를 사전에 계산해두고, 위상(Phase, $\phi_n$)이 바뀔 때만 `exp()` 부분만 다시 계산하도록 최적화할 수 있습니다.

## 3. 참고 문헌 및 기존 논문 활용
현재 폴더에 이미 존재하거나 참고할 만한 논문들입니다:
1.  **"Holographic acoustic elements for manipulation of levitated objects" (기존 폴더 존재)**: 복소 음압장과 위상 변조를 통한 트랩핑(Trapping) 노드 형성의 수학적 모델이 자세히 나와 있습니다.
2.  **"Ultraino: An Open Phased-Array System..." (기존 폴더 존재)**: 오픈소스 기반 위상 배열의 음압 계산(C++ 기반) 및 하드웨어 전송에 대한 아키텍처를 참고할 수 있습니다.
3.  **오픈소스 라이브러리 `levitate` (Python)**: 만약 더 복잡한 초점 제어나 힘(Force) 계산이 필요하다면 GitHub의 `AppliedAcousticsChalmers/levitate` 라이브러리를 추가로 설치(pip install levitate)하여 엔진으로 활용할 수 있습니다.
