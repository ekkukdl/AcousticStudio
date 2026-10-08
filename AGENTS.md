# AcousticStudio — GPT/Codex 작업 지침

## 프로젝트와 작업 시작

초음파 부상·음장 제어용 Python/PySide6/PyVista 데스크톱 프로그램이다.
한국어로 소통하고, 요청에 필요한 변경을 구현·검증한 뒤 결과와 남은 한계를 보고한다.

- Ultraino 이식·터널 배열 작업은 먼저 `docs/ultraino_migration_plan.md`를 읽는다.
  T0·T1·T2·T3·T4·T5·T6는 구현·소프트웨어 검증 완료이며 상세 기록은 `docs/ultraino_t0_result.md`,
  `docs/ultraino_t1_result.md`, `docs/ultraino_t2_result.md`, `docs/ultraino_t3_result.md`,
  `docs/ultraino_t4_result.md`, `docs/ultraino_t5_result.md`, `docs/ultraino_t6_result.md`다.
  다음 실물 단계는 T7이며 사용자 요청 하드웨어 범위에서 수행한다.
  실제 펌웨어·배선·파형/OFF·지속 갱신률 측정은 아직 남아 있다.
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
  이득 0은 음향 모델의 비활성 상태이며 T5에서 지원 프로파일의 OFF 마스크로 연결한다.
  `hologram_ui.py` controller는 한 번에 한 worker만 실행하고 마지막 대기 요청만 보존한다.
  요청 번호·현재 입력 해시가 일치할 때만 GUI 스레드에서 결과를 적용하며 닫기는 thread 종료를 기다린다.
  프로젝트는 설정·목표·활성 체크 상태를 저장하고 위상을 재계산한다. 현재 위상 초기값의 정확한
  재실행에는 설계 JSON의 initial_phases_rad를 사용한다. T6는 같은 controller 종료/취소 구조를
  motion_ui.NumericalController로 재사용한다. 단일 목표 궤적 export와 혼합 목표 그룹 재생을 구분한다.
- `calibration.py`는 SW 순서의 상대 이득·명령 위상 보정·활성 상태·물리 맵 및 출처/이력을 저장한다.
  `source_inputs(window)`를 모든 계산 경로에서 재사용한다. 보정 이득은 nominal 이득에 곱하고,
  명령 위상 오프셋은 hardware.py에서 한 번 더하며 시뮬레이션 위상에 중복 적용하지 않는다.
  맵은 map[physical_frame_channel]=software_channel이며 활성 상태도 같은 방향으로 매핑한다.
  절대 음압 보정은 아직 없고 pressure_calibrated=false를 유지한다. measured 표시는 입력자의 출처 기록이다.
  CAD 보정은 인스턴스·채널 순서·원본 해시·기준 방사면에 묶이며 전체 CAD pose 변경은 허용한다.
  `calibration_ui.py`는 기존 보드 메뉴에 연결하고 새 배열과 맞지 않는 보정의 새 작성/제거 경로를 보존한다.
  supported OFF=32와 활성 위상0을 구별한다. Legacy OFF는 거절하며 기존 ties-even 반올림을 유지한다.
  송신/내보내기는 공통 encoder를 사용한다. 부분 write·timeout은 재시도 없이 연결을 종료한다.
  write_timeout=0.1s이며 serial.flush()를 GUI에서 호출하지 않는다. 로컬 write 성공은 보드 ACK가 아니다.
  T6의 queue_phases는 별도 write 작업1개/대기 최신 프레임1개다. 수동 송신과 동시 write는 거절한다.
  다른 보정/맵/프로파일의 connected 복원을 거절한다.
- `compute_devices.py`는 설치 여부와 실제 GPU 런타임 사용 가능 상태를 구분한다.
  app의 has_taichi/has_pytorch는 실제 GPU 사용 가능 상태이며 설치 여부는 compute_devices에 있다.
  현재 CPU 전용 PyTorch를 CUDA 가속으로 표시하지 않는다. 현재 PC에서 확인한 Taichi GPU 경로는 Vulkan이다.
  Kinoforms는 복소 행렬 곱만 GPU이며 작은 문제에서 매 연산의 복사 비용 때문에 CPU보다 느릴 수 있다.
  장치 기본 선택은 성능 자동 튜닝이 아니다. 근거·재현·T6 후속은 docs/multitrap_cuda_diagnosis.md를 읽는다.
  사용자 선택으로 CUDA를 준비하는 현재 흐름은 docs/cuda_optional_selection.md를 따른다.
  cuda_runtime/worker/protocol은 별도 --target 패키지와 새 Python 프로세스를 사용한다.
  기본 환경에서 로드된 CPU Torch를 hot reload/강제 덮어쓰기하지 않는다. 사용 가능한 기존 CUDA는 직접 계산한다.
  선택 후 설치는 기존 Qt 창, 성공 확인 후 모드 적용이며 실패/취소는 이전 모드를 유지한다.
  공통 reduce_field와 레거시 GPU wrapper를 함께 유지하고 숫자 배열만 전달한다.
  실제 새 CUDA 패키지 설치/커널 실행은 아직 미검증이다. fake IPC를 실제 GPU 검증으로 기록하지 않는다.
- T6의 단면 좌표는 VTK 역투영과 motion.py의 mm 평면 교차를 사용한다. Qt/VTK 객체는 GUI에서만 읽는다.
  일반 위상/음장/궤적 진단/내보내기는 복사 스냅샷 worker이며 요청 번호와 현재 입력 해시로 결과를 거른다.
  단면 시각화는 제어점 연속 이동 중 마지막 완성 단면을 유지한다. 실행 중 단면 작업은 이동만으로 취소하지
  않고 음원·보정·평면·표시 설정이 같으면 완성 스냅샷을 표시한 뒤 최신 위상으로 재계산한다.
  이 표시 계약을 위상 적용이나 하드웨어 송신의 최신 입력 검증에 확대하지 않는다.
  드래그는 최신 위치로 병합하고 궤적 재생은 이전 위상/실시간 write 완료를 기다려 waypoint를 유지한다.
  현재 PC는 Intel UHD Graphics620/Taichi Vulkan, CPU 전용 Torch이며 과거 NVIDIA 기록과 구분한다.
  nominal33ms 요청은 실제 지속30Hz 보장이 아니다. 현재 작은 혼합 문제는 C++이 Vulkan보다 빠르다.
  근거와 T7 인계는 docs/ultraino_t6_result.md 및 scratch/ultraino_migration/t6_*를 확인한다.

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
