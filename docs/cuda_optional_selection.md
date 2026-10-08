# 선택 항목에서 PyTorch/CUDA 적용 — 2026-10-07

2026-10-08 현재 PC 점검에서는 Intel UHD Graphics 620만 조회되고 PyTorch는 CPU 전용이며
별도 CUDA 설치본이 없었다. 따라서 현재 사용 가능한 GPU 경로는 실제 계산을 확인한
Taichi Vulkan이다. 과거 NVIDIA CUDA 검증 기록을 현재 장치 사용 가능 상태로 해석하지 않는다.
설치 창 결과 비교의 `dialog.Accepted` 오류는 `QDialog.DialogCode.Accepted`로 수정했고,
실제 설치 창/QThread의 성공·실패 회귀를 확인했다. 실행 중인 앱은 저장 후 재시작한다.
장치와 계산 증거는 [현재 점검 기록](../scratch/ultraino_migration/current_cuda_result.json)에 있다.

상단 연산 모드의 **`PyTorch/CUDA: 선택 시 준비`**를 선택하면 CUDA 설치본을 준비하고
사용 가능 상태를 확인한 뒤 해당 모드로 계산한다. CPU 전용 PyTorch가 이미 설치되어 있어도
이 경로를 사용할 수 있다. 사용자 선택이 설치 시작이므로 추가 확인 질문은 띄우지 않는다.

`도구 → 라이브러리 관리자`에서도 **`PyTorch/CUDA 사용`**을 체크하고
`선택 항목 설치`를 누르면 같은 준비 과정을 거친 뒤 메인의 연산 모드를 PyTorch/CUDA로 바꾼다.
선택 항목의 초기 체크 상태는 해제다.

- CUDA가 이미 준비되어 있으면 바로 계산 모드를 바꾼다.
- 첫 선택은 공식 CUDA 패키지 다운로드와 설치가 필요하며 수 GB의 공간·인터넷을 사용한다.
- 설치와 CUDA 복소수 커널 확인이 성공해야 모드를 적용한다. 준비 창은 완료 후 자동으로 닫힌다.
- 취소·설치 실패는 이전에 사용하던 계산 모드를 적용하고 사유를 표시한다.
- 이미 CUDA 빌드가 있지만 장치를 사용할 수 없는 경우 장치 오류를 표시한다.
  패키지 재설치로 장치 문제가 해결된 것으로 처리하지 않는다.
- 준비 중에는 진행 중인 Kinoforms 요청과 궤적 재생을 중단하고 새 위상 계산/송신을 보류한다.
  완료 후 새 모드로 다시 계산한다. 재생 재개는 기존 재생 버튼으로 수행한다.

앱을 다시 시작해 수정된 선택 흐름을 사용한다. 준비 완료 후 설계 결과와 음장 계산 상태의
**`복소 합산: PyTorch CUDA`**, CPU 전환 사유 유무로 실제 사용 엔진을 확인한다.

## 설치·계산 구조

Windows에서 실행 중인 CPU PyTorch의 DLL을 교체하거나 같은 프로세스에 다른 빌드를
다시 불러오는 방식으로 즉시 전환하지 않는다. 앱의 Python을 재사용해 CUDA 패키지를
프로젝트의 `runtime/torch_cuda/py313-cu130/install-…` 같은 별도 디렉터리에 설치하고,
그 경로를 먼저 읽는 새 Python 계산 프로세스에서 사용한다. 실행 창과 프로젝트 상태를 이어서 사용한다.
설치 후 확인한 계산 프로세스는 그대로 재사용하므로 GUI 스레드에서 PyTorch를 다시 import하지 않는다.

현재 자동 설치 대상은 Windows/Python 3.10~3.14용 `torch==2.14.0+cu130`이며
[공식 CUDA 13.0 패키지 인덱스](https://download.pytorch.org/whl/cu130/torch/)를 사용한다.
공식 목록에 Python 3.13/Windows x64 wheel을 확인했다.
NVIDIA 장치/드라이버를 먼저 조회하고 CUDA 13의 최소 580 계열 이상을 확인한다.
[NVIDIA 호환성 근거](https://docs.nvidia.com/cuda/archive/13.0.1/cuda-toolkit-release-notes/index.html)
및 [PyTorch 설치 안내](https://pytorch.org/get-started/locally/)를 참고한다.

설치된 상대 경로는 해당 런타임 폴더의 `active.json`에 원자적으로 저장한다.
실패한 새 설치 디렉터리는 그 경로가 런타임 루트 안에 있는지 확인한 뒤 정리한다.
이 런타임은 Git 제외 대상이다. 기존 Anaconda의 PyTorch와 필수 과학/Qt 패키지를 덮어쓰지 않는다.

Qt와 VTK는 기존 GUI 스레드, Kinoforms/방사력 수치 worker는 기존 QThread에서 계속 사용한다.
새 CUDA 프로세스에는 복소 행렬·벡터 같은 수치 배열만 전달한다.
개인 stdin/stdout 파이프에서 직렬화한 메시지를 교환하며 외부 파일이나 네트워크의 pickle은 읽지 않는다.
요청은 한 번에 하나, 메시지는 최대 64 MiB, 응답·잠금 대기는 30초로 제한한다.
프로세스 종료·통신 오류·timeout은 기존 명시적인 CPU 전환 사유로 전달한다.
앱 프로세스가 종료될 때 CUDA 자식 프로세스를 정리한다.

공통 `reduce_field`가 새 런타임을 사용하므로 실제 CAD 위치·법선·고정 보정 이득,
위상-only Kinoforms·방사력·단면 계산의 데이터 계약을 유지한다.
레거시 위상·단면 GPU wrapper도 새 계산 프로세스로 요청을 전달한다.
현재 IBP 제약·투영과 전파 행렬 생성은 CPU이며 GPU 전송 횟수 감소·장치 내 반복 연산은 후속 성능 작업이다.
설치만으로 전체 계산 속도 향상을 보장하지 않는다.

## 검증과 인계

전체 pytest **227 passed, 3 skipped, 6 warnings**를 확인했다. 기존의 실제 PyTorch CUDA
비교 3개는 설치본이 CPU 전용이어서 skip이다. 경고는 기존 Taichi locale 및 Matplotlib API다.
새 테스트는 실제 Qt 선택/설치 창/QThread와 새 Python 프로세스의 파이프를 실행했고,
pip와 CUDA API는 가짜 응답으로 검증했다. 다운로드·실제 PyTorch CUDA 설치/실행은 이번 작업에서 수행하지 않았다.

확인한 동작은 CPU 설치본의 CUDA 옵션 제공, 선택 후 준비와 전환, 준비된 모드의 재선택,
취소 직후 설치가 성공한 경계에서도 이전 모드 유지, 설치 종료 코드 실패/취소,
worker 종료 대기, IPC 복소수·비활성 채널·프로세스 재사용·EOF/timeout/크기 제한,
경로 탈출 거절과 실패 디렉터리 정리, Kinoforms CPU/가짜 CUDA 프로세스의 위상·잔차 일치다.

- [구현: 런타임·설치](../src/acousticstudio/cuda_runtime.py)
- [구현: 새 Python 계산 프로세스](../src/acousticstudio/cuda_worker.py)
- [회귀 테스트](../tests/test_cuda_selection.py)
- [전체 JUnit](../scratch/ultraino_migration/cuda_selection_pytest.xml)
- [정적·환경·코드 해시 기록](../scratch/ultraino_migration/cuda_selection_result.json)
- [정적 검증 재현 도구](../scratch/ultraino_migration/verify_cuda_selection_static.py)

2026-10-08 마무리 점검에서 변경 소스의 구문·문서 링크·인코딩·Git diff를 확인했다.
기존 T4 음장/홀로그램 모델, T5 보정·통신, Creo 256채널 배열·후보 맵과 native DLL의 해시는
그대로 유지했다. 기본 PyTorch는 CPU 빌드이며 CUDA 런타임 폴더는 아직 생성되지 않았다.

T6 조작·이송은 아직 미완료다. [T5 인계](ultraino_t5_result.md)와
[이식 계획](ultraino_migration_plan.md)에 따라 이어서 작업한다.
기존 [CUDA 원인·시간 측정](multitrap_cuda_diagnosis.md)의 해시와 시간은 당시 코드 기준으로 보존했다.
새 CUDA 경로의 실측 속도는 실제 옵션 설치 후 별도로 확인해야 한다.
