# 다중 트랩 CUDA 경로 점검 — 2026-10-07

이 문서는 최초 진단·측정 기준본이다. 이후 선택 항목에서 CUDA 설치·확인·전환을 연결한
현재 흐름은 [PyTorch/CUDA 선택 적용 기록](cuda_optional_selection.md)을 따른다.

현재 개발 환경의 PyTorch는 **2.14.0+cpu**, `torch.version.cuda=None`,
`torch.cuda.is_available()=False`다. 기존 UI는 `torch` 패키지 존재만 확인해
PyTorch/CUDA를 기본 선택했다. 실제 Kinoforms 계산은 `Numba CPU`로 전환되며
결과의 `backend.fallback_reason`에 CUDA 장치 사용 불가를 기록한다.
같은 환경의 Taichi 1.7.4는 실제 `cuda`로 초기화되고 다중 트랩의 복소 행렬 곱을 실행한다.

이 점검은 `C:/Users/line0/anaconda3/python.exe`의 환경을 확인했다.
다른 Python으로 실행한 앱의 상태는 해당 인터프리터에서 다시 확인해야 한다.
GPU는 NVIDIA GeForce RTX 4070 SUPER, 조회한 드라이버는 617.42였다.

## 계산 경로와 가속 범위

메인 화면의 연산 모드는 `HologramController → HologramWorker → PhaseEngine.calculate_hologram
→ HologramSolver.solve → reduce_field`로 전달된다. 설계 창도 같은 worker 경로를 사용한다.

- 전파 행렬 `G` 생성: 공통 NumPy/SciPy CPU 모델. 실제 CAD 방사면·법선과 고정 보정 이득을 사용한다.
- IBP의 전방/공액 역전파 `G @ drive`, `G.conj().T @ desired`: 선택한 Numba/C++/Taichi/PyTorch 엔진.
- 목표장 제약, 위상 투영, 위상 변화·잔차·균일도, 취소 확인: CPU.
- Taichi/PyTorch의 현 구현은 행렬 곱마다 행렬·벡터를 GPU로 복사하고 결과를 CPU로 가져온다.
  50회 고정 반복은 전방 51회와 역전파 50회, 총 101회의 행렬 곱이다.

작은 다중 트랩 문제에서는 복사·커널 호출 비용 때문에 전체 계산 시간이 CPU보다 길어질 수 있다.

## 반영한 수정

[compute_devices.py](../src/acousticstudio/compute_devices.py)는 패키지 설치 상태와
실제 GPU 런타임/장치 상태를 분리한다. [app.py](../src/acousticstudio/app.py)는 이를 사용해
사용 가능한 GPU를 기본 선택한다. 현재 환경의 기본 선택은 `GPU: Taichi (cuda)`다.
이는 장치 사용 가능 여부에 따른 우선순위이며 속도 비교 결과에 따른 자동 튜닝은 아니다.

PyTorch CPU 설치본은 `PyTorch/CUDA: 사용 불가 (CUDA 빌드 없음)`으로 표시하며
도움말에 사유를 보여 준다. 이 항목을 선택하면 사용 가능한 모드로 전환하고
상태바에 사유를 표시한다. 이미 설치된 CPU PyTorch를 자동으로 다시 설치하지 않는다.
Taichi CPU 초기화, GPU 장치 부재, 선택 패키지 로드 실패도 구분한다.
계산 모드를 바꿀 때 이전 Kinoforms 요청을 취소해 이전 모드의 결과가 뒤늦게 적용되지 않도록 했다.
측정으로 보장되지 않은 ‘가장 빠름/매우 빠름’ 표시는 제거했다.

확인 경로: 앱을 재시작하고 상단에서 `GPU: Taichi (cuda)`를 선택한 뒤
`음장 → 다중 트랩 설계 (Kinoforms)`를 실행한다. 설계 결과 및 공통 음향 모델의
계산 상태에서 **`복소 합산: Taichi cuda`**와 CPU 전환 사유 유무를 확인한다.

## 실행 검증

Creo R2 **8면 × 8기판 × 기판당 32송신기 = 256채널**에서 이득 0 채널과
상대 이득 0.7 채널을 포함해 공통 무지향 모델, 50회 고정 반복을 비교했다.
아래 값은 초기 실행 후 Green 캐시를 재사용한 3회 실행의 중앙값이다.
CPU 작업과 GPU 복사 시간을 포함한 solver 벽시계 시간이며 송신·렌더링·실물 측정은 포함하지 않는다.

| 목표 | Numba CPU | C++ CPU | Taichi CUDA | PyTorch/CUDA 선택 시 CPU 전환 |
| --- | ---: | ---: | ---: | ---: |
| Focus 2개, 가상점 2개 | 5.113 ms | 11.816 ms | 81.264 ms | 5.097 ms |
| Focus/Twin/Standing 혼합 8개, 가상점 12개 | 7.378 ms | 15.584 ms | 79.834 ms | 7.433 ms |

Taichi CUDA의 CPU 대비 최대 위상 phasor 오차는 두 경우 각각
`1.07e-14`, `5.33e-15`였다. PyTorch/CUDA 선택은 실제 `Numba CPU` 및 명시적인
전환 사유를 반환했다. 실제 Qt 계산 스레드에서도 Creo 256채널 혼합 트랩의
Taichi CUDA 사용, 비활성 채널, 위상·복소장·잔차 일치를 확인했다.

전체 pytest는 **217 passed, 3 skipped, 6 warnings**다. 3 skip은 현재 환경의
기존 PyTorch CUDA 실행 비교이며, 경고는 기존 Taichi locale 및 Matplotlib API 경고다.
관련 집중 테스트는 36 passed였다.

- [장치·수치·시간·코드/배열 해시 기록](../scratch/ultraino_migration/multitrap_compute_result.json)
- [재현 스크립트](../scratch/ultraino_migration/verify_multitrap_compute.py)
- [전체 JUnit](../scratch/ultraino_migration/multitrap_compute_pytest.xml)
- [회귀 테스트](../tests/test_compute_devices.py)

```powershell
$env:PYTHONPATH='src'
$env:QT_QPA_PLATFORM='offscreen'
$env:PYTHONIOENCODING='utf-8'
& 'C:/Users/line0/anaconda3/python.exe' scratch/ultraino_migration/verify_multitrap_compute.py
& 'C:/Users/line0/anaconda3/python.exe' -m pytest -q tests/test_compute_devices.py tests/test_hologram.py tests/test_hologram_ui.py
```

## T6 작업 인계

이번 수정은 다중 트랩 CUDA 문의에 따른 장치 선택·표시 수정과 계산 경로 검증이다.
T6의 단면 클릭/드래그, 선택/전체 입자 이동, 궤적 worker 및 계산·송신·렌더링 큐는
아직 완료하지 않았다. 기존 [T5의 T6 인계 기준](ultraino_t5_result.md)과
[이식 계획](ultraino_migration_plan.md)을 이어서 따른다.

`window.has_taichi`와 `window.has_pytorch`는 이제 실제 GPU 사용 가능 상태를 뜻한다.
설치 여부는 `window.compute_devices.taichi_installed/torch_installed`에서 확인한다.
환경을 변경하거나 새 패키지를 설치하지 않았고 실제 COM 송신·CAD·backup·commit/push는 수행하지 않았다.
T5 재현 기록의 해시는 당시 기준본이며 이번 app.py 변경으로 달라진 값을 덮어쓰지 않았다.

GPU 반복 연산의 성능을 후속으로 개선할 경우 공통 Green 모델을 유지한 채
전파 행렬과 벡터를 반복 동안 장치에 보존하고 제약·투영을 같은 장치에서 처리해야 한다.
CPU와 위상·잔차·비활성 채널을 비교하고 QThread 취소·마지막 요청 처리·GUI 응답성을 함께 검증한다.
현재의 가속 범위나 위 표의 시간만으로 30~60 Hz 이송을 보장하지 않는다.
