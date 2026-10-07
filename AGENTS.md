# AcousticStudio — GPT/Codex 작업 지침

## 프로젝트와 작업 시작

초음파 부상·음장 제어용 Python/PySide6/PyVista 데스크톱 프로그램이다.
한국어로 소통하고, 요청에 필요한 변경을 구현·검증한 뒤 결과와 남은 한계를 보고한다.

- Ultraino 이식·터널 배열 작업은 먼저 `docs/ultraino_migration_plan.md`를 읽는다.
  T0·T1·T2·T3·T4는 구현·소프트웨어 검증 완료이며 상세 기록은 `docs/ultraino_t0_result.md`,
  `docs/ultraino_t1_result.md`, `docs/ultraino_t2_result.md`, `docs/ultraino_t3_result.md`,
  `docs/ultraino_t4_result.md`다. 다음은 T5 통신·캘리브레이션이며 T4 기록 끝의 인계 기준을 따른다.
  현재 기준은 Creo R2의 **8면·8기판·기판당 32송신기, 총 256채널**이다.
  `구상도/outputs/panel_8faces_32ch_R1/array_positions_256.json`의 방사면 좌표와
  법선을 재사용한다. 터널 축은 Z이며 과거 16기판 구성이나 일반 Tube 생성식으로 대체하지 않는다.
- 개발 환경 재사용 근거는 `docs/ultraino_migration_audit.json`에 있다.
  현재 앱은 Anaconda Python 3.13.9 환경을 기준으로 확인했으며, 기본 `py`와
  CAD 가상환경은 다른 환경이다. 실제 인터프리터를 확인한 뒤 실행한다.
- 먼저 `docs/project_status.txt`, 관련 소스, `git status --short`를 확인한다.
  문서의 완료 표시는 구현 기록이며 실제 작동·물리 정확성의 검증 증거와 구분한다.
- `main.py`는 시작 시 의존성 설치 UI를 띄울 수 있다. 읽기·문서 작업을 위해
  앱을 실행하거나 패키지를 일괄 설치하지 않는다.
- 실행 검증 시 Python 인터프리터와 관련 패키지 버전을 확인한다. 필요한 설치는
  프로젝트 가상환경을 우선하고 GPU 패키지를 무조건 설치하지 않는다.
- `app.py`는 UI 통합, `phase_engine.py`는 물리/위상 계산,
  `sonic_wrapper.py`·`sonic_core.cpp`는 가속 연산, `hardware.py`는 시리얼,
  `kwave_engine.py`는 2D 기구물 해석을 담당한다.
  `geometry.py`는 Creo JSON 모델, `geometry_scene.py`는 VTK 어댑터다.
  CAD 배열의 계산 좌표는 모델의 방사면 위치이며 actor.center(몸체 중심)로 대체하지 않는다.
  `field_model.py`의 FieldConfig/Green 모델을 재사용하고 `acoustic_model_ui.field_kwargs()`로
  실제 법선·개구를 전달한다. 개구 미확정은 CAD 외경으로 대체하지 않는다.
  전파는 CPU, 복소 합산은 선택 엔진이며 실제 사용/전환은 last_backend로 확인한다.
- `force_analysis.py`는 T2 음장을 재사용한 고정 위상·진폭의 작은 구 고르코프 분석이다.
  `FieldSnapshot`을 고정한 뒤 수신점만 이동한다. F=−∇U, K=−∂F/∂x이며 전체 3×3 행렬의
  고유값과 h·h/2·h/4 수렴을 확인한다. 기존 궤적 relative_stiffness_norm과 혼동하지 않는다.
  N*·J*는 상대 음압 1=1Pa 가정값이다. 예시 물성·미보정 음압으로 실물 평형/부양을 선언하지 않는다.
  `force_analysis_ui.py` worker에는 Qt/VTK 객체를 전달하지 않고 계산 중 닫기는 취소·thread 종료를 기다린다.
- `hologram.py`는 T2 Green 행렬과 고정 음원 이득으로 위상만 조절하는 Kinoforms IBP다.
  Focus/Twin/Standing Wave를 혼합하며 Java Y→현재 터널 Z의 오른손 좌표 변환을 유지한다.
  목표 가중치는 상대 음압 제약이며 조절 가능한 송신 진폭이나 부양 성공률이 아니다.
  위상 정체와 잔차/복원 부호를 구분하고 후보 위상은 T3 FieldSnapshot으로 고정해 평가한다.
  이득 0은 음향 모델의 비활성 상태다. 실제 OFF·보정·맵·양자화 계약은 T5에서 구현한다.
  `hologram_ui.py` controller는 한 번에 한 worker만 실행하고 마지막 대기 요청만 보존한다.
  요청 번호·현재 입력 해시가 일치할 때만 GUI 스레드에서 결과를 적용하며 닫기는 thread 종료를 기다린다.
  프로젝트는 설정·목표·활성 체크 상태를 저장하고 위상을 재계산한다. 현재 위상 초기값의 정확한
  재실행에는 설계 JSON의 initial_phases_rad를 사용한다. 기존 단일 궤적의 동기 계산은 T6 후속 범위다.

## 변경과 사용자 의도

- 요청된 수정·검증은 간단히 방향을 알린 뒤 진행한다. 이미 허용된 작업에 대해
  매번 승인을 다시 요청하지 않는다. 결과를 크게 바꾸는 불명확한 요구만 질문한다.
- 관련 없는 리팩터링, 기존 사용자 변경 덮어쓰기, 사용자 파일 삭제를 피한다.
- 새 메서드는 기존 구조와 가독성에 맞춰 배치한다. 클래스 끝에 강제 배치하거나
  무분별한 문자열 치환으로 UI 초기화 흐름을 손상시키지 않는다.

## 백업과 Git

- `backup/`은 직전 검증 완료 상태를 보존한다. 개발·디버깅 중 덮어쓰거나 동기화하지 않는다.
- 백업 갱신은 사용자가 현 단계 결과를 최종 검증·승인한 뒤 다음 과제로 넘어가기 직전에만 한다.
- ZIP, `_backup.py`, `_old.py` 등 임의 백업을 누적하지 않는다.
- `git commit`과 `git push`는 사용자 최종 검증과 명시적 요청이 있을 때 수행한다.
  AI 테스트 통과를 사용자 승인으로 간주하지 않는다.

## 파일과 인코딩

- 수정은 `apply_patch` 또는 UTF-8을 명시한 Python 입출력을 사용한다.
  PowerShell 읽기는 `Get-Content -Encoding UTF8`처럼 인코딩을 명시한다.
  기본 인코딩에 의존하는 읽기-쓰기 파이프라인은 사용하지 않는다.
- 검색은 `rg`를 우선하고 기존 줄바꿈·한글·파일 구조를 보존한다.
- 프로젝트 산출물은 이 폴더 안에 둔다. 임시 자료는 `scratch/` 등 하위 폴더를 사용한다.
  사용자 요청에 따른 개인 스킬 설치·수정은 해당 스킬 폴더를 사용할 수 있다.
- 이번 작업에서 만든 불필요한 임시 파일만 정리한다. 기존 테스트와 유용한 회귀 테스트는 보존한다.

## 검증과 진행 기록

- 문서 수정은 링크·인코딩·diff를 확인한다. 물리/통신 변경은 단위, 경계조건,
  실패 경로를 검증하고 GUI 변경은 해당 사용자 흐름을 확인한다.
- 현재 `tests/test_hardware_profiles.py`와 `tests/test_ui_appearance.py`가 있다.
  새 테스트는 실제 회귀 위험이 있는 계산·프로토콜 동작을 검증할 때만 추가하고,
  GUI 실험 스크립트를 테스트로 가장하지 않는다. 테스트 통과와 실물 검증을 구분한다.
- 음향 계산에서는 mm/m, rad/위상 바이트, 좌표축, 배열 형상과 채널 순서를 명확히 한다.
- 상대 안정도 점수를 실험 성공률로 표현하지 않는다. fallback이나 계산 실패를
  정상 결과처럼 표시하지 않으며, 2D 모델 결과를 3D 실험 검증으로 간주하지 않는다.
- 실제 보드 송신·부상 실험은 사용자가 요청한 하드웨어 작업 범위에서 수행한다.
  소프트웨어 검증과 실물 검증을 구분해서 보고한다.
- 구현·수정 완료 시 `docs/project_status.txt`에 변경, 검증 범위, 남은 작업을 기록한다.
  실행하지 않은 테스트를 통과했다고 기록하지 않는다.

## 스킬 선택

- 세션의 스킬 목록에서 실제 작업에 필요한 것만 선택하고 해당 `SKILL.md`를 읽는다.
  `karpathy-guidelines` 등 특정 외부 스킬 설치를 작업 선행조건으로 삼지 않는다.
- `acousticstudio-development`가 제공되면 물리 계산·Qt UI·시리얼 구현 및 검증에 사용한다.
  미설치 환경에서는 본 지침과 소스로 작업을 이어간다.
- 데스크톱 UI 확인은 `computer-use`, Orca 조작은 `orca-cli`, 스킬 수정은
  `skill-creator`, 스킬 설치는 `skill-installer`, 발표자료는 `pptx`를 해당 작업에 사용한다.
- 관련 없는 스킬을 일괄 로드하거나 설치하지 않는다. 공식 시스템 스킬과 플러그인 캐시는
  프로젝트별 취향에 맞춰 직접 수정하지 않는다.
- 스킬 점검 결과는 `docs/skill_audit.md`를 참고한다.
