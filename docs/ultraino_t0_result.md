# T0 구현 및 검증 기록

2026-10-07. 기준: Creo R2의 8면·8기판·32 TX/기판, 총 256채널. 이 단계는 기존 계산·송신 경로를 바로잡는다. CAD 프리셋은 T1에서 연결한다.

## 다음 에이전트가 재사용할 진입점

- [PhaseEngine](../src/acousticstudio/phase_engine.py): `calculate_phases(centers, active_points, amplitudes, algorithm, mode_idx, ...)`는 mm 좌표와 소프트웨어 채널 순서의 rad 위상 `(N,)`을 사용한다. `calculate_trajectory_phases`는 각 경유점을 단일 목표점으로 계산해 `(steps,N)`을 반환한다. 정지 목표점과 이동 목표점의 동시 재생은 T6 범위다.
- `optimize_trajectory_physical`은 같은 위상 진입점 및 실제 설정 진폭을 사용한다. 지연 단위는 ms다. 실패 시 점수·강도·스티프니스는 None, `valid=False`다. `trajectory_diagnosis_is_valid`는 이전 저장 파일의 Fallback 점수도 거른다.
- [HardwareController](../src/acousticstudio/hardware.py): `set_phase_offsets`는 소프트웨어 채널 순서의 **가산 rad 보정**을 설정한다. `set_channel_map`은 `map[physical]=software`를 설정한다. `prepare_phases`에서 입력 채널 수 검증 → 보정 → 맵을 한 번씩 적용한다. `prepare_phase_steps`와 `build_phase_frame`은 파일/실시간 공통 경로다. 보드 프로파일 변경은 맵과 보정을 초기화한다. 보정 API는 메모리에서만 동작하며 측정·UI·저장 기능이 아니다.
- [파일 출력](../src/acousticstudio/trajectory_export.py): `save_trajectory_export`는 원래 소프트웨어 순서의 위상을 받는다. 헤더/CSV에는 보정 완료 물리 채널 순서를 명시한다. 일반 `.bin`은 선택 프로파일 프레임 연결이며 타이밍/메타데이터가 포함되지 않는다. `legacy` 선택과 `.legacy.bin`은 이전 `0xFA + Phase32 + 0xFD` 파일 컨테이너다. CSV에는 `Board_Profile`과 `PhysicalN_Phase32` 열이 추가되었다. 기존 외부 CSV 소비자는 이 변경에 맞춰야 한다.
- [의존성 카탈로그](../src/acousticstudio/dependencies.py): `main.py`, `installer_ui.py`가 같은 `PACKAGE_INFO`를 사용한다. 필수 9개는 requirements.txt와 일치한다. [확인한 버전](../requirements-tested.txt)은 기존 환경의 핵심 패키지 스냅샷이며 신규 환경 설치를 검증한 잠금 파일은 아니다.

## 실제 실행한 검증

사용 인터프리터: `C:/Users/line0/anaconda3/python.exe`, Python 3.13.9. pytest 8.4.2. 새 설치 없음.

AcousticStudio 루트에서:

```powershell
& 'C:/Users/line0/anaconda3/python.exe' -c "import sys; sys.path.insert(0,'src'); import pytest; raise SystemExit(pytest.main(['tests','-q']))"
```

결과: **58 passed, 1 warning, 4.00s**. 기존 7개 테스트가 포함된다. [계산/송신/파일 회귀 테스트](../tests/test_trajectory_pipeline.py)와 [Qt 핸들러 회귀 테스트](../tests/test_trajectory_ui.py)를 추가했다.

- 5개 송신기/2개 목표점: Focus/Twin/Vortex의 NumPy 기준 계산 및 실제 C++ DLL 위상이 일치했다. DLL 부재 시 다중 목표점과 궤적 경유점 계산이 지원되었다.
- 역순 C++ 인자, 잘못된 채널 수/진폭, 비정상 계산 결과를 검출했다. 물리 라이브러리 부재/예외/영 강도/NaN/크기 오버플로/잘못된 벡터/빈 입력에는 성공 점수가 생성되지 않았다.
- 비순차 채널 맵과 서로 다른 보정을 적용한 5개 프로파일에서 fake-serial 송신과 `.bin` 바이트가 일치했다. 헤더/CSV/legacy의 위상 값도 같은 순서였다. 실제 포트를 열지 않았다.
- 실제 설치된 Levitate로 두 경유점의 유한 스티프니스가 계산되었다. 물리 안정성의 정확성을 확인하는 시험은 아니다.
- offscreen Qt 레이블, 궤적 생성/내보내기 핸들러, 라이브러리 관리자의 누락 필수 항목을 확인했다. 전체 VTK 앱 창·3D 렌더링은 실행하지 않았다.
- 필수 설치 검사 실행, 두 UI의 동일 카탈로그 사용, requirements.txt 집합 일치, Python 파일 18개 AST 문법 검사 통과. `git diff --check` 통과.

Taichi의 기존 import 경로가 GPU 런타임을 초기화하고 `locale.getdefaultlocale` 사용 중단 경고를 한 번 출력했다. GPU 계산 커널, k-Wave solver, 실제 보드 송신·부양 및 CAD 재생성은 수행하지 않았다. `backup/`과 commit/push도 갱신하지 않았다.

## 남은 경계 및 이어서 할 작업

현재 물리 진단은 기존 ±Z 법선 추정과 5mm 유효 개구, 스티프니스 크기 기반 상대 점수를 사용한다. 이 모델은 내향 8면 터널의 물리 검증을 대신하지 않는다. T2에서 CAD 법선·음향 개구를 연결하고 T3에서 힘 부호·복원 방향·입자 물성으로 검증한다. T5에는 측정 보정/영구 저장/OFF/펌웨어별 반 스텝 경계가 남아 있다.

다음은 [계획의 T1](ultraino_migration_plan.md): 기존 `array_positions_256.json` 로더와 프리셋을 추가하고 위치·법선·ID·채널 순서를 렌더링/저장·복원/Undo에서 유지한다. 일반 Tube 계산식으로 좌표를 다시 생성하지 않는다.
