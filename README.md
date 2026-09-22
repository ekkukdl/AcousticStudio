# Acoustic Control Studio

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

본 프로그램을 실행하기 위해서는 Python 3.9 이상의 환경이 권장되며, 3D 렌더링 및 UI 구성을 위한 필수 라이브러리들이 필요합니다.

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
- **AI 백업 규정**: 소스 코드를 인공지능(에이전트)을 통해 수정할 때는 반드시 `docs/AI_AGENT_GUIDELINES.md` 에 명시된 덮어쓰기 금지/롤백 규정을 준수하도록 지시해야 안전한 개발이 가능합니다.
