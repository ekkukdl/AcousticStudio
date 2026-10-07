# Creo 8면 32채널 터널 기준 Ultraino 이식 작업 계획

2026-10-07 사용자 지시에 따라 현재 개발 기준을 **8면, 면당 PCB 1장, PCB당 트랜스듀서 32개, 총 8기판·256채널**로 확정한다. 현재 Creo R2의 배치와 일치하는 배열을 AcousticStudio에 추가하고, 그 배열을 공통 입력으로 Ultraino의 다중 트랩·방사력 분석·조작·캘리브레이션 기능을 이식한다.

이 문서는 이후 에이전트의 구현 기준이다. 입력 형상·개발 환경 점검에 이어 T0 계산 경로 수정, T1 CAD 배열 로더·프리셋 연결, T2 공통 복소 음장·방향성, T3 고정 위상 방사력 분석, T4 Kinoforms·다중 트랩, T5 통신·캘리브레이션의 소프트웨어 구현과 검증을 완료했다. [T0 기록](ultraino_t0_result.md), [T1 기록](ultraino_t1_result.md), [T2 기록](ultraino_t2_result.md), [T3 기록](ultraino_t3_result.md), [T4 기록](ultraino_t4_result.md), [T5 기록](ultraino_t5_result.md)을 확인하고 다음 소프트웨어 단계 T6부터 진행한다. 실제 펌웨어·배선·OFF/파형 측정은 미완료다. 사용자의 최신 지시가 과거 보고서·안내의 8면 16기판 구성을 대체한다.

## 작업 시작 순서

1. [AGENTS.md](../AGENTS.md), 이 문서, [진행 기록](project_status.txt)을 읽는다.
2. `git status --short`와 관련 소스를 확인하고 기존 사용자 변경을 보존한다.
3. [점검 결과 JSON](ultraino_migration_audit.json)에서 형상 및 인터프리터 근거를 확인한다. 날짜·해시가 달라졌다면 입력을 다시 확인한다.
4. 완료된 작업의 검증 기록을 확인하고 첫 미완료 단계부터 작업한다. 현재 T0·T1·T2·T3·T4·T5 소프트웨어 완료, 다음은 T6다. T5 실제 하드웨어 검증은 사용자 요청 실물 단계에서 수행한다. 각 작업의 산출물과 완료 기준을 만족한 후 의존하는 작업으로 넘어간다.
5. 구현 후 진행 기록에 변경·실행한 검증·남은 한계를 기록한다. 다른 에이전트에게 맡길 때 작업 ID, 파일 범위, 완료 기준, 실제 검증 결과를 전달한다.

사용자 승인 전 `backup/`을 갱신하지 않으며, 명시적 요청 없이 commit/push하지 않는다. 이 계획 자체가 실제 보드 송신이나 CAD 재생성의 실행 요청은 아니다.

## 현재 형상과 입력의 우선순위

| 용도 | 현재 기준 파일 |
| --- | --- |
| Creo 전체 조립체 | [tunnel8_32_r2.asm](../구상도/outputs/panel_8faces_32ch_R1/mechanical/creo32_frame_R2/native/tunnel8_32_r2.asm) |
| Creo 기판 조립체 | [panel32_r2.asm](../구상도/outputs/panel_8faces_32ch_R1/mechanical/creo32_frame_R2/native/panel32_r2.asm) |
| 256개 방사면 중심과 법선 | [array_positions_256.json](../구상도/outputs/panel_8faces_32ch_R1/array_positions_256.json) |
| PCB 치수와 배열 설정 | [parameters.json](../구상도/outputs/panel_8faces_32ch_R1/parameters.json) |
| Creo 부품 및 면 배치 행렬 | [geometry_checks.json](../구상도/outputs/panel_8faces_32ch_R1/mechanical/creo32_frame_R2/geometry_checks.json) |
| Creo 저장 후 재조회 배치 근거 | [native_reopen_report.json](../구상도/outputs/panel_8faces_32ch_R1/mechanical/creo32_frame_R2/validation/native_reopen_report.json) |
| 전체 채널의 행·열·뱅크 연결 | [channel_map.csv](../구상도/outputs/panel_8faces_32ch_R1/channel_map.csv) |
| 물리 채널에서 소프트웨어 채널로의 후보 맵 | [physical_to_software_channel_map.json](../구상도/outputs/panel_8faces_32ch_R1/physical_to_software_channel_map.json) |
| R2 형상 사용 안내 | [Creo R2 사용안내](../구상도/outputs/panel_8faces_32ch_R1/mechanical/creo32_frame_R2/사용안내.md) |
| 원래 조사 보고서 | [초음파부상 및 Ultraino 기능통합 분석보고서](<../../보고서 및 구체화/초음파부상_역장제어_및_Ultraino_기능통합_분석보고서.docx>) |

CAD 입력은 새로 생성하지 않고 기존 파일을 읽는다. 실행 시에는 배포 가능한 배열 JSON을 사용하며 Creo, KiCad, CadQuery 또는 STEP 변환기를 앱 필수 의존성으로 만들지 않는다. STEP 표시가 필요하면 별도 선택 기능으로 추가한다.

`구상도/creo_tunnel/v1_single_panel`의 8기판·128개와 `v2_dual_panel`의 16기판·256개는 이전 설계다. 이 폴더와 과거 검증 기록은 보존하되 현재 배열 입력으로 사용하지 않는다. `parameters.json`의 revision R1은 PCB 개정이며, Creo 프레임 R2와 충돌하지 않는다.

## 반드시 재현할 배치

| 항목 | 현재 값 |
| --- | --- |
| 면 및 채널 | 8면 × 1기판 × 32채널 = 256채널 |
| 한 기판의 배열 | 4열 × 8행, 지름 16 mm 트랜스듀서 |
| PCB 크기 | 84 × 224 × 1.6 mm |
| 터널 축 및 수직 방향 | Z축, 원점은 터널 중심 및 기판 높이 중앙 |
| 면 방향 | 면 0은 +X측, 이후 +Z에서 내려다본 XY 평면 기준 45°씩 회전 |
| 발진면 아포템 | 105 mm, 마주 보는 발진면 거리 210 mm |
| PCB 앞면 아포템 | 117.5 mm, 트랜스듀서 높이 12.5 mm |
| 기판 접선 방향 좌표 | −29, −11, 11, 29 mm, 간격 18/22/18 mm |
| 축 방향 좌표 | −70, −50, −30, −10, 10, 30, 50, 70 mm |
| 법선 | 각 면에서 터널 중심을 향하는 수평 단위 벡터 |
| 외부 프레임 | 링 2개, Z −105..−97 및 97..105 mm, 전체 외형 265 × 265 × 224 mm |
| 전기적 뱅크 | PCB당 A/B 16채널씩, 전체 16뱅크 |

면 f의 각도를 θ=fπ/4, 외향 벡터를 n=(cosθ,sinθ,0), 접선 벡터를 t=(−sinθ,cosθ,0)로 두면 기존 좌표는 `position_mm = 105*n + u*t + (0,0,z)`이고, 발진 법선은 `normal = -n`이다. u와 z는 위 표의 값이다. 면 0의 T1은 `(105,−29,−70)`, 법선은 `(−1,0,0)`이다. 실제 로더는 JSON을 읽고 이 식은 검증에 사용한다.

소프트웨어 채널은 `channel=32*face+local_channel`, `local_channel=4*row+column`, T1..T32는 각 기판에서 반복한다. 영구 식별자는 face와 local_channel의 조합을 사용한다. 소프트웨어 행 우선 순서와 물리 전송 순서는 다르므로 후보 맵을 항등 맵으로 대체하지 않는다.

Creo JSON의 행렬은 **행 벡터와 마지막 행의 평행이동** 규약이다. `[x,y,z,1] @ T`를 사용한다. VTK의 열 벡터 규약에 적용할 때는 전치/변환 어댑터를 거쳐 검증한다. 트랜스듀서 단품 로컬 발진면은 z=−12.5이고 법선은 −Z다. mesh의 외접 상자 중심이나 PCB 위치를 방사면 중심으로 사용하지 않는다.

이번 점검에서 256개 위치·법선을 R2 배치 행렬로 재계산하고 Creo 재조회 기록과 비교했다. 위치 최대 오차는 약 5.61e−14 mm이며, 네이티브 ASM/PRT 13개의 현재 해시가 기존 manifest와 일치했다. 이는 저장된 모델과 입력 파일의 일치 확인이며, 현재 열린 Creo의 저장하지 않은 변경이나 실제 부양 성능을 확인한 것은 아니다.

## 기존 기능과 작업 환경의 재사용

| 기존 자산 | 재사용할 부분 | 추가하거나 수정할 부분 |
| --- | --- | --- |
| `app.py::generate_array()` | 일반 Matrix, Tube, 대향형, 반구형 생성 및 렌더링 | 고정 CAD 프리셋 로더 추가. 기존 Tube의 X축 링 배치·균일 간격으로 현재 형상을 생성하지 않는다 |
| `PhaseEngine` | 계산 진입점, 연산 모드 선택, 기존 Twin/Vortex | 좌표·법선·개구 전달, 공통 복소 음장 및 Kinoforms 경로 |
| `sonic_wrapper.py`, `sonic_core.cpp`, DLL | 기존 CPU/native/GPU 가속 경로 | T0 호출 수정 후 동일 모델의 수치 비교. 신규 기능의 지원 여부를 명시 |
| `hardware.py` | BoardProfile, 양자화, 프레임 인코더, `set_channel_map()` | 후보 맵 검토, 보정 및 OFF, 실제 펌웨어 프로파일 |
| `MouseEventFilter`, 자동 계산, 실시간 전송 | 선택·기즈모·자동 계산 연결 | 단면 피킹, XYZ 스텝 이동, 요청 취소 및 송신 속도 제한 |
| `file_io.py`, `get_state()/set_state()`, `StateManager` | JSON 입출력, Undo/Redo | 배열 메타데이터·법선·개별 모델·캘리브레이션 저장과 이전 파일 호환 |
| `kwave_engine.py` | 기존 2D 해석 창 | 필요할 때 같은 CAD 입력을 전달. Kinoforms 이식의 선행조건으로 삼지 않는다 |
| `ui_appearance.py` | 클래식/모던 UI와 공통 보드 메뉴 | 두 UI에 동일한 기능 연결. 별도 메인 창·렌더러를 만들지 않는다 |
| 기존 배열 JSON 및 Creo 생성 스크립트 | 확인된 좌표와 형상 근거 | 새 CAD 생성기와 좌표 파일을 중복 작성하지 않는다 |
| 기존 테스트 | `test_hardware_profiles.py`, `test_ui_appearance.py` | 형상·계산·보정·프로토콜의 실제 회귀 위험을 검증하는 테스트 추가 |

초기 점검에서는 단면 방향성 누락, ±Z 법선 추정, 계산 실패의 기본 '안정' 반환을 확인했다. T0/T2에서 실패 표시와 CAD 법선·선택 방향성 연결을 수정했다. 현재 상대 stiffness norm은 복원 부호·중력 평형·실측 음압을 검증하지 않으므로 T3 방사력 분석과 구분한다.

### 확인한 인터프리터

| 환경 | 확인 결과 | 작업 방침 |
| --- | --- | --- |
| `C:/Users/line0/anaconda3/python.exe` | Python 3.13.9. NumPy 2.2.6, Numba 0.62.1, PySide6 6.9.2, PyVista 0.49.0, PyVistaQt 0.13.1, VTK 9.7.0, matplotlib 3.10.9, levitate 3.0.0, pyserial 3.5, pytest 8.4.2 등 설치. 핵심 모듈 10개 import 성공 | 현재 기계의 개발·검증 기준. 경로를 명시하여 사용하며 일괄 재설치하지 않는다 |
| `py`의 기본 Python | Python 3.14.6, 점검한 앱 패키지 미설치 | `py main.py` 또는 경로 없는 기본 `py -m pytest`로 환경을 판단하지 않는다 |
| `구상도/scratch/creo_cad_env/Scripts/python.exe` | Python 3.13.9. CadQuery 2.8.0, cadquery-ocp 7.9.3.1.1, NumPy 2.5.3, VTK 9.6.2. 앱용 Qt·levitate 등은 미설치 | CAD 변환용으로 보존. 앱 패키지를 여기 설치하거나 이 환경을 앱 환경으로 사용하지 않는다 |
| Anaconda의 `sixsense` | Python 3.9.25, 점검한 앱 패키지 대부분 미설치 | 다른 용도의 기존 환경으로 보존 |
| 저장소의 `.venv` 및 `venv` | 현재 없음 | 기존 앱 환경으로 작업 가능. 격리가 실제 필요할 때 검증한 의존성으로 별도 환경을 구성한다 |

`creo32_env`라는 경로가 R2 안내와 `.gitignore`에 남아 있지만 현재 존재하지 않는다. CAD 환경의 현존 경로는 위 표의 `creo_cad_env`다. 복사된 `pyvenv.cfg`의 과거 생성 경로만 보고 환경을 이동·재생성하지 않는다.

앱과 CAD 환경에는 NumPy/VTK 등이 각각 다른 버전으로 설치되어 있다. 용도가 분리된 환경이므로 합치지 않는다. 앱 기능 이식에는 이미 설치된 NumPy/Numba/Qt/matplotlib/pyserial을 사용한다. 초기 점검은 Torch/Taichi 설치 메타데이터만 확인했으며, T2/T3/T4에서 Taichi 1.7.4의 실제 CUDA 복소 합산을 검증했다. 설치된 PyTorch 2.14.0은 CUDA build가 없어 CPU 전환만 검증했다. SciPy 1.15.3은 T2부터 공통 모델에 사용한다. k-wave-python 0.6.3rc1은 설치되어 있지만 solver 실행 검증은 포함하지 않는다. T4 원본 비교는 기존 OpenJDK 25.0.4.1을 사용했으며 Java/NetBeans는 Python 앱 실행의 필수 환경이 아니다. T2는 기존 MSVC로 DLL을 재빌드했고 T3/T4는 같은 DLL을 재사용했다. 추가 환경·패키지를 설치하지 않았다.

초기 점검에서 `requirements.txt`의 `numba` 누락과 `main.py` 점검 목록의 불일치를 확인했고 T0에서 필수 의존성 10개를 공통 카탈로그와 일치시켰다. 확인한 앱 패키지 버전은 `requirements-tested.txt`에 기록했다. 사용자 Anaconda 전체 환경을 freeze하여 프로젝트 요구사항으로 복사하지 않는다. 새 머신에서는 표의 설치 상태를 보장할 수 없으므로 선택한 인터프리터로 다시 점검한다.

점검 명령은 저장소 루트에서 실행한다. 아래 스크립트는 입력 파일을 읽고, `--out`으로 지정한 점검 JSON만 갱신한다.

```powershell
$studioPython = 'C:/Users/line0/anaconda3/python.exe'
& $studioPython scratch/ultraino_migration/audit_inputs.py --check-app-imports --out docs/ultraino_migration_audit.json
```

다른 환경을 함께 기록하려면 `--probe-python <python.exe>`를 반복 지정한다. 현재 점검 JSON에는 앱, 기본 py, CAD, sixsense 4개 환경이 기록되어 있다. 위 기본 명령으로 갱신하면 실행 인터프리터만 기록되므로 기존 비교를 유지하려면 같은 3개 보조 인터프리터를 다시 지정한다. 문서 작업을 위해 `main.py`를 실행하지 않는다. 시작 시 설치 UI가 뜰 수 있다.

## 공통 데이터와 모듈 계약

UI의 actor를 계산 데이터의 원본으로 사용하지 않는다. 로더가 만든 배열 데이터가 계산·시각화·저장·송신의 공통 원본이며, actor는 표현과 선택을 담당한다.

- 배열: `geometry_id`, `schema_version`, 원본 경로/해시, 좌표계/단위, 256개 송신기. 송신기는 ID, face, local_channel, row, column, position_mm, normal, aperture, frequency, 모델, 구동 진폭, 활성 상태를 가진다.
- 물리 조건: 매질 음속/밀도, 입자 반경·밀도·음속, 음압 스케일 및 출처. CAD 외경 16 mm만으로 유효 음향 개구 반경을 확정하지 않는다.
- 위상 결과: shape `(N,)`, rad, 유한값, 소프트웨어 채널 순서. 빈 배열·영 진폭·미지원 알고리즘·계산 실패를 명시한다.
- 제어점: ID, position_mm, trap_type, orientation, target_weight. 원본 Java의 색상 기반 트랩 유형을 명시적 필드로 바꾼다.
- 보정: 소프트웨어 채널 순서의 위상 오프셋(rad), 보정 ID, 측정 조건, 기하/보드/배선 버전. 물리 맵은 `map[physical_channel]=software_channel`이다.
- 송신: 계산 위상 → 소프트웨어 채널별 보정 → 위상 및 활성 상태의 물리 채널 매핑 → 프로파일별 양자화/OFF → 인코딩. 실시간과 파일 내보내기가 같은 경로를 사용한다.
- 저장: 배열과 보정 메타데이터, 송신 프로파일을 기록하고 이전 `test1.json`을 읽는 이행 경로를 제공한다. Undo/Redo에서도 배열 메타데이터가 소실되지 않아야 한다.

새 파일은 필요 범위에만 추가한다. `geometry.py`의 CAD 배열 로딩·검증과 `geometry_scene.py`의 VTK 어댑터는 T1, `field_model.py`와 `field_backends.py`의 공통 복소 전파·합산은 T2, `force_analysis.py`와 `force_analysis_ui.py`의 고정 위상 힘/퍼텐셜 분석은 T3에서 구현했다. T4는 `hologram.py`의 가상점/IBP와 `hologram_ui.py`의 취소·최신 요청 관리 및 설계 UI를 추가했다. T5는 `calibration.py`의 상대 보정/출처/배열 서명과 `calibration_ui.py`의 수동 편집·OFF 파일을 추가하고 기존 hardware.py/trajectory_export.py를 확장했다. PhaseEngine은 계산 진입점, hardware.py는 전송 책임, app.py/widgets.py는 UI 연결을 유지한다. 외부 라이브러리나 별도 위상 엔진·시리얼 컨트롤러를 중복 도입하지 않는다.

## 작업 단위와 완료 기준

### T0 기존 계산 경로와 의존성 선언 수정

상태: **구현 및 소프트웨어 검증 완료**. [상세 결과와 재현 명령](ultraino_t0_result.md). 전체 테스트 58개 통과. CAD 배열 연결과 물리 모델의 정확성은 이후 단계의 범위다.

관련 파일: [phase_engine.py](../src/acousticstudio/phase_engine.py), [sonic_wrapper.py](../src/acousticstudio/sonic_wrapper.py), [app.py](../src/acousticstudio/app.py), [hardware.py](../src/acousticstudio/hardware.py), [requirements.txt](../requirements.txt), [main.py](../main.py), [installer_ui.py](../src/acousticstudio/installer_ui.py).

`calculate_phases_sonic(cx,cy,cz,tx,ty,tz,...)`의 cx/cy/cz는 송신기, tx/ty/tz는 목표점이다. T0에서 궤적 최적화·내보내기의 뒤집힌 호출을 공통 PhaseEngine 진입점으로 교체했고 DLL 부재 시 NumPy 경로를 사용한다. 물리 계산 실패·빈 입력은 진단 불가로 표시하며 75/60% 기본 안정 판정을 제거했다. 일반 `.bin`은 선택 프로파일 프레임을 사용하고 이전 0xFA 파일은 `.legacy.bin`으로 구분한다. HardwareController의 보정·채널 매핑 경로를 송신과 내보내기에서 한 번씩 사용한다. 의존성 9개 선언과 두 설치 화면의 공통 카탈로그를 맞췄으며 일괄 재설치는 수행하지 않았다. 보정 측정·UI·영구 저장 및 OFF 처리는 T5에 남아 있다.

완료 기준: 서로 다른 송신기/목표점 개수로 출력이 `(N,)`인지 검증, DLL 없음·계산 오류·빈 입력 처리, 송신/내보내기 일치, 기존 보드 프로파일 테스트 유지. 아직 물리 정확성이나 CAD 배열 UI 완료로 기록하지 않는다.

### T1 Creo 배열 로더와 프리셋 연결

상태: **구현 및 소프트웨어 검증 완료**. [상세 결과와 재현 명령](ultraino_t1_result.md). 전체 테스트 76개 통과, 실제 Qt 프리셋 선택·저장/복원 확인, 독립 VTK 장면 렌더링 확인. Qt offscreen의 OpenGL 캡처 제약은 기록에 구분했다.

의존: T0. 구현 파일은 `geometry.py`, VTK 어댑터 `geometry_scene.py`, app.py의 구성/렌더링 및 get_state/set_state다. CAD JSON을 읽고 원본 해시와 256개 방사면 좌표·법선·ID, 구조물 행렬을 모델에 보존한다. 계산에는 CAD 모델 좌표를 사용하고 actor는 표시와 선택·변환의 어댑터로 사용한다. 이전 프로젝트는 기존 좌표 어댑터로 읽는다.

기존 `array_positions_256.json`에서 배열을 읽고 UI에 **Creo 8면 터널 8기판 32채널** 프리셋을 추가한다. 입력 경로는 실행 CWD와 Windows 사용자 이름에 의존하지 않도록 저장소/패키지 기준으로 해석한다. 배포용 배열 데이터가 필요하면 원본 해시를 함께 기록하며 CAD 전체를 복제하지 않는다. 단일 Spacing 입력으로 열 간격을 재생성하지 않는다. 고정 프리셋을 일반 Tube와 구분하며 현재 CAD를 바꾸는 치수 편집은 별도 기능으로 남긴다. 8개의 PCB와 필요한 프레임 표시는 재사용한 행렬·치수로 구성하고 256개 트랜스듀서는 방사면 위치와 법선에 맞춘다. 전체 위치·회전 변환을 적용하면 좌표와 법선도 함께 변환한다. 복잡한 STEP 솔리드 전체의 import를 초기 기능의 필수 조건으로 삼지 않는다.

완료 기준: 8면/32개/256개 수량, 비균일 열 간격, Z축, 내향 법선, CAD 입력 좌표 일치. VTK 어댑터에서 한 개와 대향 면의 방사면을 확인한다. 전체 회전/이동 및 저장·복원/Undo 후 동일한 ID·좌표·법선·채널 순서를 유지한다. 후보 물리 맵의 적용은 T5에서 다룬다.

### T2 공통 복소 음장과 방향성 모델

상태: **구현 및 소프트웨어 검증 완료**. [상세 결과·데이터 계약·T3 인계](ultraino_t2_result.md). 전체 116개 통과, PyTorch CUDA 3개 skip. NumPy/Numba/C++/실제 Taichi CUDA와 Levitate 음압을 비교했다. SciPy를 포함한 필수 선언 10개는 기존 설치 환경과 일치한다.

의존: T1. PhaseEngine과 신규 field_model.py가 위치·법선·개구·진폭을 공통으로 받도록 한다.

Ultraino의 [CalcField.java](../../simulations/Ultraino/AcousticFieldSim/src/acousticfield3d/algorithms/CalcField.java)의 전파 계산을 NumPy 기준 구현으로 옮긴다. Ultraino의 sinc 모델과 levitate CircularPiston 모델은 다르므로 모드를 명시하고 같은 모델·단위·음압 스케일끼리 비교한다. NumPy `sinc`의 π 정규화와 Java `sin(x)/x` 규약을 맞춘다. 계산 내부의 SI 경계와 위상 rad를 명확히 한다. levitate의 ±Z 법선 추정 및 모든 소자 유효 반경 0.005 m 고정을 CAD/음향 모델 입력으로 교체한다.

완료 기준: 단일 송신기 위상·거리·방향성 기준값, 대칭 배열과 전체 좌표 변환에서 일관성, NaN/무한대·근접 특이점 처리. 기존 10/16 mm·랑주뱅 표현은 유지하되 경험적 진폭을 측정 음압으로 표시하지 않는다. CPU 기준 검증 후 지원하는 native/GPU 경로를 같은 모델로 맞춘다.

### T3 고정 위상에서의 방사력 분석

상태: **구현 및 소프트웨어 검증 완료**. [상세 결과·계산 계약·T4 인계](ultraino_t3_result.md). 전체 143개 통과, PyTorch CUDA 3개 skip. 독립 정상파 해석식·Levitate 고르코프·전체 결합 행렬·미분 수렴·명목 중력 조건 및 실제 Qt worker의 계산·취소·닫기·출력을 확인했다. 실제 음압 미보정으로 물리 중력 평형/부양 판정은 보류한다.

의존: T2. 구현 파일은 force_analysis.py, force_analysis_ui.py와 app.py의 버튼·프로젝트 설정 연결이다. T2 전파·현재 위상/진폭을 고정한 FieldSnapshot을 재사용한다.

[CalcField.java](../../simulations/Ultraino/AcousticFieldSim/src/acousticfield3d/algorithms/CalcField.java)와 [ForcePlotsFrame.java](../../simulations/Ultraino/AcousticFieldSim/src/acousticfield3d/gui/misc/ForcePlotsFrame.java)의 고르코프 상수·수치 미분·변위 스캔을 옮긴다. 위상은 고정하고 입자 위치만 이동한다. F=−∇U, 복원 스티프니스 K=−∂F/∂x의 부호를 명시한다. levitate와 원본의 force-gradient 값은 K와 부호가 다를 수 있으므로 정합화한다. 강도 norm만으로 안정성을 판정하지 않는다. 축별 곡선부터 구현하고 결합 방향 안정성을 주장할 때는 전체 행렬을 확인한다.

완료 기준: 대칭 기준에서 힘의 대칭·복원 부호, 입자 물성 입력, 미분 간격 변경 수렴, 중력을 포함한 평형 조건, 같은 음장/모델의 기준값 비교. 절대 음압 보정 전 힘의 단위를 실측 성능으로 해석하지 않는다. 2D k-Wave 결과를 3D 부양 검증으로 사용하지 않는다.

### T4 Kinoforms와 다중 트랩

상태: **구현 및 소프트웨어 검증 완료**. [상세 결과·사용법·T5 인계](ultraino_t4_result.md). 전체 테스트 171개 통과·3개 skip. 원본 Java 반복 계산의 최대 공통 위상 정렬 오차 2.05e−7, Creo256채널 36건의 CPU/C++/실제 Taichi CUDA 및 Torch CPU 전환 비교를 확인했다. 음압 균일도와 실물 부양을 구분한다.

의존: T2, T3 진단. hologram.py와 PhaseEngine을 연결하고 hologram_ui.py를 기존 메인 창에서 사용한다.

[Kinoforms.java](../../simulations/Ultraino/AcousticFieldSim/src/acousticfield3d/algorithms/Kinoforms.java)의 가상점 생성, 전방 투영, 목표 진폭·상대 위상 제약, 공액 역전파, 송신기 진폭 제약을 옮긴다. Focus → 다중 Focus → Twin/Standing Wave 순서로 구현한다. 원본 가상점 간격·트랩 방향은 Ultraino 좌표계 변환 후 적용한다. 가상점의 영 복소값과 송신기 영 진폭 정규화를 처리한다. 측정 송신기 이득과 조절 가능한 구동 진폭을 구분하고 보드 능력에 맞는 phase-only 모드를 사용한다. 배열/목표점 변경 시 전파 행렬 캐시를 무효화한다.

완료 기준: 고정된 작은 입력과 초기 위상으로 원본/CPU 기준을 비교, 공통 위상 차이를 제거한 복소 음장 오차 확인, 목표점 균일도 및 물리 진단 비교, 반복 수·잔차·256채널 실행 시간 기록. 다중 음압 초점만으로 다중 부양 성공을 선언하지 않는다. 1~2 ms 목표는 측정 전 완료 기준으로 확정하지 않는다. Vortex/BFGS/DivTrans는 후속 과제이며 초기 부양·이송·고정 흐름의 선행조건으로 만들지 않는다.

### T5 실제 뱅크 연결에 맞는 통신과 캘리브레이션

상태: **소프트웨어 구현 및 fake-serial/Qt 검증 완료**. [상세 결과·사용법·T6 인계](ultraino_t5_result.md). 전체 테스트 208개 통과·3개 skip. 4프로파일×일반/1채널/전체 OFF 12건의 송신/내보내기 일치, 맵·보정·활성·반올림·부분 쓰기/timeout 및 상태 복원을 확인했다. 실제 펌웨어 식별·배선·파형/OFF·지속 갱신률의 측정은 미완료다.

의존: T0, T1. 보정 데이터와 프로토콜의 소프트웨어 준비는 T2~T4 진행 중 별도 작업 단위로 가능하다. 실제 송신은 사용자 요청 하드웨어 작업에서 수행한다.

기존 BoardProfile·set_channel_map·프레임 테스트를 확장한다. 입력 [channel_map.csv](../구상도/outputs/panel_8faces_32ch_R1/channel_map.csv)와 후보 맵을 읽되 실물에서 검증된 것으로 표시하지 않는다. PCB당 A/B 뱅크가 있고 DATA 4선, SHIFT/LATCH/ARM은 뱅크별 외부 연결이 필요하다. **8기판은 8개 FPGA 주소를 뜻하지 않으며, 16뱅크도 16개 체인 보드를 뜻하지 않는다.** 실제 컨트롤러 개수·펌웨어·DATA 할당·시프트 비트 방향을 확인한 뒤 프로파일을 선택한다.

Ultraino [ChainedFPGA.java](../../simulations/Ultraino/AcousticFieldSim/src/acousticfield3d/protocols/ChainedFPGA.java)는 상위 SimpleFPGA의 기본 256채널 단위로 분할하며 커밋은 호출 컨트롤러가 수행한다. 기존 AcousticStudio 태그형은 128채널씩 분할한다. 이를 PCB당 32채널만 보고 수정하지 않는다. 먼저 실제 펌웨어의 프레임 규약을 확정한다.

1채널 구동/나머지 OFF, 전체 OFF, 위상 오프셋 저장·적용, 보정 이력, 연결 해제/부분 쓰기/쓰기 timeout을 구현한다. 위상 0과 OFF를 구분한다. Python round, NumPy round, C++/Java round의 반 스텝 경계 차이를 펌웨어 기준으로 정합화한다. 초기에는 수동 위상 보정 UI를 제공하고 [AssignTransducers.java](../../simulations/Ultraino/AcousticFieldSim/src/acousticfield3d/gui/AssignTransducers.java)의 수신기 자동 채널 식별은 측정 장치가 준비되면 연결한다.

완료 기준: 맵 순열/활성 상태/보정 부호/위상 경계/커밋 바이트/부분 쓰기/연결 실패의 fake-serial 검증. 선택 프로파일 기준으로 내보낸 프레임과 송신 프레임의 바이트 일치. 실제 보드 단계에는 펌웨어 식별·배선표·채널별 파형·출력 OFF·지속 갱신률의 측정 기록이 필요하다.

### T6 단면 조작과 궤적 이송

의존: T1, T4 및 T5 소프트웨어 경로. 기존 자동 계산·실시간 전송과 widgets.py의 이벤트 필터를 확장한다.

[TrapsPanel.java](../../simulations/Ultraino/AcousticFieldSim/src/acousticfield3d/gui/panels/TrapsPanel.java)와 [MovePanel.java](../../simulations/Ultraino/AcousticFieldSim/src/acousticfield3d/gui/panels/MovePanel.java)의 단면 클릭/드래그, 선택 입자/전체 입자 XYZ 이동을 Qt로 연결한다. 현재 CAD의 Z축을 터널 이송 축으로 사용한다. 작업 큐에 요청 번호를 부여하여 오래된 계산 결과를 버리고 GUI/VTK는 GUI 스레드에서 갱신한다. 프레임 계산/송신과 음장 그래프 갱신 속도를 분리하며 드래그 해제 시 최종 위치를 반영한다.

완료 기준: 픽킹 평면과 세계 좌표 일치, 단일/전체 이동, 취소·창 닫기·연결 실패, 렌더링과 송신의 중복 호출 방지. 230400 baud 8N1에서 258 bytes는 선로 전송만 약 11.2 ms이므로 1 ms 송신을 약속하지 않는다. 초기 30~60 Hz 범위에서 계산·송신 지연과 누락을 측정한 뒤 실제 가능한 속도를 정한다.

### T7 실제 터널의 부양 이송 고정 검증

의존: T3~T6. 사용자가 요청한 하드웨어 실험 단계에서 수행한다.

단일 입자 부양 → Z축 이송 → 검사 위치 정지·유지 → 다중 입자 순서로 검증한다. 대상의 크기·질량·물성, 배열 및 보정 해시, 구동 조건, 위치 오차, 유지 시간, 반복 횟수, 탈락 횟수, 송신 지연을 기록한다. 실패 시 실패 조건과 마지막 명령을 기록한다. 랑주뱅과의 위상/주파수 동기 및 음압 모델은 별도 검증하며 UI의 진폭 20.0 가중치를 실측 부양력으로 취급하지 않는다.

이식 초기 목표는 부양·축 방향 이송·고정이다. 회전 스캔과 영상 검사 시스템은 기존 [검사 소프트웨어 요구사항](software_requirements.md)의 별도 장기 범위로 유지한다. 작은 입자 모델을 실제 비구형 검사 부품에 그대로 적용하지 않는다.

## 다른 에이전트에게 전달할 작업 형식

한 번에 맡기는 기본 단위는 T0, T1 등이다. 동시에 작업하는 경우 공통 데이터 계약을 먼저 확정하고 app.py/phase_engine.py/hardware.py의 최종 통합 담당을 정한다. 같은 파일을 여러 에이전트가 독립 수정하는 방식은 피한다. 이 문서는 작업 분배 지침이며 이번 정리에서 별도 에이전트를 실행하지 않았다.

```text
작업 ID: T0 또는 해당 단계
기준: AGENTS.md와 docs/ultraino_migration_plan.md
하드웨어: Creo R2 8면 × 8 PCB × PCB당 32 TX = 256채널
형상: 기존 array_positions_256.json, Z축 터널, 내향 법선
수정 파일: 담당 단계에 명시된 파일만 우선 수정
재사용: 기존 계산 진입점, BoardProfile, 이벤트 필터, 저장 및 테스트
선행 결과: 완료된 단계와 검증 결과 파일/명령
완료 조건: 해당 단계의 완료 기준과 실제 실행 증거
보고: 변경 내용, 통과/실패한 검사, 미실행 항목, 남은 입력
```

현재 미확정 입력은 실제 컨트롤러/펌웨어/헤더 배선, 소자의 유효 음향 개구와 음압 보정, 실제 입자 물성이다. 이 입력을 가정한 실물 완료 판정은 금지하지만 완료한 T0~T5 소프트웨어 및 fake-serial 경로를 재사용해 T6 개발은 계속할 수 있다.

## 이번 정리의 검증 범위

- 8면 × 32개 좌표·법선·ID·후보 채널 맵, Creo 행렬 및 저장 후 재조회 기록을 비교했다.
- 현재 네이티브 모델 13개와 원본 PCB의 해시를 기존 기록과 비교했다. CAD를 재생성하지 않았다.
- 기존 Python 환경 4개를 설치 메타데이터로 비교하고 앱 의존성 10개를 import했다. 추가 설치·환경 생성·GPU/solver 실행은 하지 않았다.
- 문서 8개의 UTF-8, 상대 링크 75개와 git diff --check를 확인했다. 깨진 링크는 0개이며 점검 스크립트 AST 문법도 통과했다. 앱 실행, 기존 기능 테스트, 실제 보드 송신과 부양 실험은 이번 정리 범위에 포함하지 않는다.
- 이식 시 [Ultraino LICENSE](../../simulations/Ultraino/LICENSE)의 저작권 및 MIT 고지를 보존한다.
