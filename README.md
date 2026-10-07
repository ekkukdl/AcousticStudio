# Acoustic Control Studio

현재 개발 저장소는 **[ekkukdl/AcousticStudio](https://github.com/ekkukdl/AcousticStudio)** 하나로 통합했습니다. 2026-10-07 기준 `AcousticStudio_ver2`의 코드, 구상도·PCB·Creo 자료 및 로컬 수정 내용을 반영했으며 두 저장소의 커밋 이력을 보존했습니다.

화면은 **보기 → UI → 클래식 / 모던**에서 선택합니다. 두 화면 모두 상단 **보드** 메뉴를 사용합니다. 설계 자료는 [구상도 시작 안내](구상도/START_HERE.md), 최신 32채널 PCB는 [제작 자료 안내](구상도/outputs/panel_8faces_32ch_R1/README.md)를 참고하세요. 통합 범위와 검증 기록은 [저장소 통합 기록](docs/repository_consolidation.md)에 있습니다.

Ultraino 기능 이식은 [작업 계획](docs/ultraino_migration_plan.md)을 기준으로 진행합니다. 현재 대상은 **Creo R2의 8면·8기판·기판당 32송신기, 총 256채널**이며 터널 축은 Z입니다. 기존 배열 좌표와 개발 환경을 재사용하는 범위 및 단계별 완료 조건을 정리했습니다. [입력·환경 점검 결과](docs/ultraino_migration_audit.json)는 현재 로컬 설치 상태의 기록입니다.

Acoustic Control Studio는 초음파 부상(Ultrasonic Levitation) 및 역장 제어(Acoustic Field Control) 연구를 위한 **통합 3D 시뮬레이션 및 하드웨어 제어 소프트웨어**입니다.
이 프로그램은 사용자가 직관적인 3D UI를 통해 센서 배열을 설계하고, 타겟의 위치를 조작하며, 실시간으로 위상(Phase)을 계산하여 하드웨어 보드(아두이노, FPGA 등)로 직접 전송할 수 있는 All-in-One 플랫폼을 제공합니다.

---

## 주요 기능 (Features)
- **3D 대화형 인터페이스 (Interactive 3D UI)**: PyVista 및 PySide6를 기반으로 한 3D 뷰어 제공.
- **다양한 배열 생성**: 터널형, 평면형, 반구형 등 복잡한 센서 배열(Array) 자동 생성 지원.
- **이기종 센서 하이브리드 지원**: 일반 10mm/16mm 초음파 센서와 고출력 랑주뱅(Langevin) 진동자의 혼합 시뮬레이션 지원.
- **실시간 위상 연산 (Real-time Phase Calculation)**: Twin Trap, Vortex Trap 등의 알고리즘을 적용하여 타겟 이동 시 위상을 즉각 재계산하고 색상으로 시각화.
- **하드웨어 연동 (USB Serial)**: 계산된 위상 데이터를 Byte 형식으로 변환하여 실시간으로 외부 제어 보드로 전송.

---

## 사전 설정 및 설치 가이드 (Prerequisites & Installation)

Creo 배열은 `구성 → 배열 형태 → Creo 8면 터널 · 8기판 × 32채널`을 선택하고 `배열 3D 렌더링 생성`으로 추가합니다. 기존 CAD 좌표를 읽으므로 일반 Grid/Spacing 값은 적용되지 않습니다. 위치·회전은 배열 전체에 적용되며, PCB 8개와 프레임 링 2개는 간략 형상으로 표시합니다. [구현 및 검증 기록](docs/ultraino_t1_result.md)을 참고하세요.

`음장 → 공통 음향 모델`에서 무지향, Ultraino sinc, 원형 피스톤을 선택합니다. 기본 개구는 미확정이며 CAD 외경에서 추정하지 않습니다. 방향성 모델에는 유효 음향 개구 반경이 필요하고, 음압은 미보정 상대값입니다. 설정을 바꾼 뒤 위상을 다시 계산하세요. [T2 결과 및 다음 작업](docs/ultraino_t2_result.md)에 데이터 계약과 검증 범위를 정리했습니다.

위상을 계산한 뒤 `음장 → 고정 위상 방사력·복원성 분석`에서 입자 물성, 중력, 평가 범위와 미분 간격을 입력합니다. 현재 송신을 고정한 XYZ 힘·퍼텐셜·복원 곡선과 전체 3×3 복원행렬을 확인하고 분석 JSON을 저장할 수 있습니다. 기본 물성은 예시이며 음압 미보정 상태의 힘은 N* 가정값입니다. 실제 중력 평형·부양 판정은 보류합니다. [T3 결과](docs/ultraino_t3_result.md)를 참고하세요.

다중 제어점을 활성화하고 `음장 → 다중 트랩 설계 (Kinoforms)`를 엽니다. 각 점에 Focus/Twin/Standing Wave, 상대 목표 음압 가중치와 세계 좌표 방향을 지정해 함께 계산합니다. 송신기 이득은 고정하고 위상만 조절하며, 반복 잔차·가중 음압 균일도를 확인한 뒤 `선택 트랩의 고정 위상 분석`으로 T3 복원 부호를 검사할 수 있습니다. `현재 배열에 위상 적용`과 `설계 JSON 저장`을 지원합니다. 음압 균일도는 부양 성공률이 아닙니다. [T4 사용·검증 및 T5 인계](docs/ultraino_t4_result.md)에 재현 방법을 정리했습니다.

`보드 → 채널 보정·맵 및 OFF 프레임…`에서 SW 채널별 위상 오프셋·고정 상대 이득·활성 상태와 후보 채널 맵을 편집하고 JSON/프로젝트로 저장합니다. 보정·맵·양자화·OFF는 실시간 송신과 궤적 내보내기에서 공통 사용합니다. 지원 프로파일의 OFF32와 위상0을 구분하며 Legacy OFF는 거절합니다. 실제 COM 없이 1채널/전체 OFF 프레임을 파일로 확인할 수 있습니다. [T5 사용·검증·T6 인계](docs/ultraino_t5_result.md)를 참고하세요. 실제 펌웨어·배선·파형 검증과 절대 음압 보정은 남아 있습니다.

상단 연산 모드에서 `PyTorch/CUDA: 선택 시 준비`를 선택하면 필요한 CUDA 패키지를 다운로드·확인한 뒤 그 모드를 적용합니다. `도구 → 라이브러리 관리자`의 `PyTorch/CUDA 사용` 체크도 같은 흐름입니다. 첫 준비는 수 GB 다운로드가 필요하며 이후 선택은 바로 전환합니다. 취소·실패는 이전 모드를 유지합니다. [선택 항목 적용 안내](docs/cuda_optional_selection.md)를 참고하세요. 다중 트랩은 복소 행렬 곱만 선택 엔진을 사용하며 작은 문제의 GPU 계산은 복사 비용 때문에 CPU보다 느릴 수 있습니다. [기존 원인·측정 기록](docs/multitrap_cuda_diagnosis.md)을 함께 확인할 수 있습니다.

현재 로컬 개발 환경은 Python 3.13.9이며, 확인한 인터프리터와 의존성은 [이식 계획의 환경 안내](docs/ultraino_migration_plan.md)에 있습니다. 기존 환경을 먼저 확인하고 재사용하세요. 기본 `py`가 선택하는 Python과 앱용 환경은 다를 수 있습니다. 필수 의존성 10개는 `requirements.txt`와 공통 설치 카탈로그에 일치하며, 확인한 버전은 [requirements-tested.txt](requirements-tested.txt)에 기록했습니다. T2는 이미 설치된 SciPy를 재사용했습니다. 아래 신규 설치 예시는 새 머신에 필요한 경우에 사용합니다.

### 1. Python 가상 환경 설정 (선택 사항이나 권장)
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
```

### 2. 필수 라이브러리 설치
프로젝트 루트 폴더에 포함된 `requirements.txt`를 사용하여 의존성 패키지를 한 번에 설치합니다.
```bash
pip install -r requirements.txt
```
**[설치되는 주요 패키지]**
- `PySide6`: GUI 프레임워크
- `pyvista`, `pyvistaqt`, `vtk`: 3D 렌더링 및 기하학 연산 엔진
- `numpy`: 고속 배열 및 위상 수학 연산
- `pyserial`: 하드웨어(USB) 시리얼 통신 모듈

### 3. 프로그램 실행
모든 설치가 완료되었다면, 최상단 경로에서 아래 명령어를 통해 메인 창을 띄울 수 있습니다.
```bash
python main.py
```

---

## 디렉터리 구조 (Directory Structure)
- `src/acousticstudio/`: 애플리케이션의 핵심 소스 코드 (`app.py`, `app_backup.py` 등)
- `main.py`: 프로그램 실행 진입점 (Entry point)
- `docs/`: AI 에이전트 가이드라인 및 프로젝트 진행 상태(`project_status.txt`)가 기록된 문서 폴더
- `archive/temp_scripts/`: 개발 과정에서 생성된 임시 수정 스크립트(수동 코드 인젝션 파일) 모음 보관소
- `requirements.txt`: 의존성 패키지 목록

---

## 주의 사항 (Notes)
- **그래픽 드라이버**: 3D 렌더링 엔진인 VTK/PyVista를 사용하므로, 그래픽 드라이버(OpenGL 호환)가 정상적으로 설치된 환경에서 실행해야 튕김 현상이 발생하지 않습니다.
- **AI 작업 지침**: GPT/Codex를 포함한 코딩 에이전트는 [AGENTS.md](AGENTS.md)의 작업·백업·검증 규칙을 따릅니다. 기존 `GEMINI.md`도 이 공통 지침을 안내합니다. 스킬 점검 내역은 [docs/skill_audit.md](docs/skill_audit.md)에 있습니다.
