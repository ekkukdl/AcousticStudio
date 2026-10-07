# T5 통신·캘리브레이션 소프트웨어 구현 및 검증 결과

2026-10-07. 사용자 요청에 따라 완료한 T4를 [1d3d83f](https://github.com/ekkukdl/AcousticStudio/commit/1d3d83faa289d0cc9d619fc37097d954442e5052)로 main에 push하고 원격 HEAD 일치를 확인한 뒤 T5를 구현했다. **Creo R2 8면·8기판·기판당 32개·총 256채널**을 유지한다. T5 소프트웨어 및 fake-serial 검증은 완료했으며 실제 컨트롤러/펌웨어/배선·출력 OFF·파형 측정은 남아 있다. 다음 소프트웨어 단계는 [T6 조작·이송](ultraino_migration_plan.md)이다. T5 변경은 현재 로컬 작업 상태다.

## 앱에서 확인하는 순서

1. 기존 Creo 터널 프리셋과 제어점을 추가한다. 상단 `보드` 메뉴에서 사용할 256채널 프로파일을 선택한다. 실제 펌웨어가 미확정이면 COM을 연결하지 않고 프레임/파일 검증부터 한다. **8 PCB 수로 FPGA 주소나 프로파일 분할을 결정하지 않는다.**
2. `보드 → 채널 보정·맵 및 OFF 프레임…`을 연다. 보정 설정 변경은 연결을 해제한 상태에서 한다. 소프트웨어 채널별 명령 위상 오프셋(rad), 고정 상대 음원 이득, 활성 여부를 입력한다. 기본 위상 보정은 0, 이득은 1, 활성은 켜짐이다.
3. `Creo 후보 맵 읽기`로 기존 후보 맵을 불러온다. 마지막 열은 **map[물리 행]=소프트웨어 채널**이며 왼쪽 위상/이득/활성 열은 소프트웨어 행이다. 중복/누락/실수/불리언 맵은 거절한다. 수동 편집하면 맵 출처 상태가 수동 미검증으로 바뀐다. `항등 맵`으로 초기화할 수 있으나 실제 배선의 항등 여부를 확인한 것으로 표시하지 않는다.
4. 보정 ID와 설명을 입력하고 `보정 적용`을 누른다. 실제 측정 자료를 입력할 때만 실측 출처를 선택하고 측정 조건·펌웨어 ID·배선 버전을 기록한다. 이 표시는 입력자의 출처 기록이며 프로그램이 실측을 수행한 증거가 아니다.
5. 공통 음향 모델로 위상을 다시 계산한다. 보정 이득·비활성 상태는 Focus/Twin/Vortex/Kinoforms, 단면, T3 고정 위상 분석, 궤적 계산에 동일하게 반영한다. `보정 JSON 저장/읽기`와 프로젝트 저장·Undo/Redo를 지원한다. 배열·채널 순서·프로파일이 다른 보정은 거절하며, 보정 창에서 새로 작성하거나 `보정 제거`로 초기화한다.
6. COM 없는 검증은 `1채널 프레임 저장` 또는 `전체 OFF 프레임 저장`을 사용한다. 한 채널은 해당 SW 채널의 보정·맵을 반영하고 나머지는 OFF다. Legacy는 OFF 근거가 없어 이 동작을 거절한다. 일반 궤적 내보내기도 비활성 채널이 있는데 OFF를 지원하지 않으면 파일 생성 전에 거절한다.
7. 실제 컨트롤러·펌웨어·배선이 확인된 하드웨어 작업에서는 `보드 → 단일 채널 테스트 전송…` 및 `전체 채널 OFF 전송`을 사용할 수 있다. 비활성 보정 채널의 단독 테스트는 먼저 활성화해야 한다. 이번 검증에서는 fake serial만 연결했으며 실제 COM 송신을 실행하지 않았다.

[보정 창 캡처](../scratch/ultraino_migration/t5_calibration_dialog.png), [검증용 프로젝트](../scratch/ultraino_migration/t5_example_project.json), [예시 보정 JSON](../scratch/ultraino_migration/t5_example_calibration.json), [예시 258-byte 프레임](../scratch/ultraino_migration/t5_example_frame.bin)을 남겼다. 프로젝트는 예시 보정과 동일한 배열 인스턴스 ID를 포함하므로 함께 재현할 수 있다. 보정 JSON만 새로 생성한 다른 배열에 불러오면 배열 서명이 달라 거절한다. 이 예시는 SW0 위상 −0.3rad, SW1 상대 이득 0.7, SW2 비활성의 **미실측 데이터**다. 실제 보드용 보정은 현재 배열에서 별도로 작성한다.

## 공통 데이터 및 송신 계약

| 데이터 | 계약 |
| --- | --- |
| `Calibration` | 불변 schema1, 보정 ID·UTC 시간·SW 순서 오프셋/이득/활성 상태 |
| 위상 보정 | `command_phase = ideal_phase + offset_rad`. 관측 위상 오차가 +이면 상쇄 오프셋은 − |
| 상대 이득 | 기존 nominal 음원 가중치 × `source_gains`; 비활성이면 0. 가변 구동 진폭 명령은 아님 |
| 계산 위상 | 보정 후 이상적인 방사 위상. 시뮬레이션에 명령 오프셋을 다시 더하지 않음 |
| 채널 맵 | `map[physical_frame_channel]=software_channel`; 위상과 활성 상태 모두 같은 방향으로 변환 |
| 활성 마스크 | 호출자의 음원 이득>0 마스크와 보정 활성 상태의 AND; 이득 0도 OFF |
| 출처 | 수동/실측 보정 상태, 맵 상태·출처·SHA256, 조건·펌웨어·배선·수정 이력 |
| 음압 | `gain_units=relative_to_nominal`, `pressure_calibrated=false`. 절대 Pa 보정 표시는 거절 |

실시간과 궤적 파일은 같은 경로를 사용한다.

```text
이상적인 SW 위상
  → SW 명령 위상 오프셋 적용 1회
  → 위상 및 활성 상태를 물리 순서로 매핑
  → 선택 프로파일의 반올림/2π wrapping/OFF
  → 선택 프로파일의 전체 프레임·commit 인코딩
```

`hardware.py`의 `prepare_phase_steps`, `build_phase_frame`, `send_phases`와 `trajectory_export.py`가 이 계약을 공유한다. binary는 송신 프레임 그대로 이어 붙인다. CSV/C 헤더의 위상 열은 이미 보정·맵이 적용된 물리 채널 순서이며 보정 ID도 기록한다. C 헤더는 지원 프로파일의 32=OFF를 명시한다. legacy FA 파일 컨테이너는 종전 형식으로 보존한다. binary에는 시간·보정 메타데이터가 없으므로 프로젝트/보정 JSON과 함께 관리한다. 물리 순서의 내보낸 값을 SW 입력 API에 다시 넣으면 이중 보정·매핑이 되므로 재인코딩하지 않는다.

배열 서명은 순서대로 CAD 인스턴스 ID·채널·기하 ID·원본 입력 해시·기준 방사면 행렬을 포함한다. CAD 전체 강체 이동/회전은 보정을 유지하고 채널 순서·기준 형상·새 배열 인스턴스는 서명을 바꾼다. Legacy는 저장된 송신기 행렬에 묶이므로 배열 좌표를 변경하면 새 보정을 작성한다. 목표점 이동은 서명에 영향을 주지 않는다.

`hardware_settings`와 `calibration`을 프로젝트·Undo/Redo에 저장하며 보정 JSON과 하드웨어의 맵/오프셋/활성 설정이 일치하는지 먼저 검사한다. 손상된 새 필드는 장면 변경 전에 거절한다. 이전 프로젝트의 필드 누락은 무보정 상태와 기존 `board_profile` 또는 Legacy 기본값으로 복원한다. 새 프로젝트는 보정을 초기화하고 연결 상태에서 다른 설정을 복원하려 하면 연결 해제를 요구한다. 원본 CAD 좌표·기판 뱅크 구조를 재생성하지 않는다.

## 프로파일과 반올림·OFF 근거

| 프로파일 | framing | OFF | 활성 위상 반올림 |
| --- | --- | --- | --- |
| Legacy Phase32 | FE + phase bytes + FD, 가변 채널 | 미지원 | 기존 ties-to-even 유지 |
| Ultraino SimpleFPGA 256 | FE + 256 bytes + FD | 32 | nearest, ties toward +∞ |
| SonicSurface direct 256 | FE + 256 bytes + FD | 32 | 클라이언트 정책 nearest, ties toward +∞ |
| SonicSurface board tags | FE C0 + 128 bytes + C1 + 128 bytes + FD | 32 | 같은 클라이언트 정책 |
| SonicSurface ESP32 command | `phases=` + 256 정수와 마지막 쉼표 + LF | 32 | 같은 클라이언트 정책 |

원본 [SimpleFPGA.java](../../simulations/Ultraino/AcousticFieldSim/src/acousticfield3d/protocols/SimpleFPGA.java)는 PHASE_OFF=getDivs()=32이며 [Transducer.java](../../simulations/Ultraino/AcousticFieldSim/src/acousticfield3d/simulation/Transducer.java)의 `calcDiscPhase`는 Java Math.round를 사용한다. Python 기본 반올림과 반 스텝이 달라 Ultraino 프로파일에서 명시적으로 분리했다. Java의 float32 전체 연산과 Python float64의 경계 근처 비트 단위 일치를 주장하지 않으며 수학적 반올림 규칙·정확한 반 스텝·인접값을 테스트했다.

[CommandSenderESP32.ino](<../../simulations/SonicSurface/Firmware/ESP32 controller/CommandSenderESP32/CommandSenderESP32.ino>)와 [TestHoloConnection4.ino](<../../simulations/SonicSurface/Firmware/ESP32 haptic controller/TestHoloConnection4/TestHoloConnection4.ino>)에서 32=OFF, 기존 프레임/commit을 확인했다. ESP32 `phases=`는 정수 값을 받아 전달하므로 반올림은 AcousticStudio의 클라이언트 정책이다. 원본 펌웨어가 위상을 추가로 양자화한다고 가정하지 않는다.

활성 위상은 modulo 2π 후 반올림하고 modulo32로 wrapping한다. 31.5스텝이나 2π 근처가 활성 위상0으로 돌아가며 OFF32가 되지 않는다. OFF는 별도의 활성 마스크에서만 부여한다. 지원되지 않은 OFF·부분 채널 수·NaN/Inf·잘못된 맵은 송신 전에 거절한다.

**8기판≠8 FPGA 주소, 16뱅크≠16 체인 보드**다. 후보 맵은 [channel_map.csv](../구상도/outputs/panel_8faces_32ch_R1/channel_map.csv)의 `fpga_physical_channel`과 전 채널 일치하지만 실제 DATA/header/SHIFT/LATCH/ARM 할당은 확인하지 않았다. 기존 128채널 태그 분할과 원본 Ultraino의 256채널 단위 [ChainedFPGA.java](../../simulations/Ultraino/AcousticFieldSim/src/acousticfield3d/protocols/ChainedFPGA.java)를 32채널 PCB 수만으로 수정하지 않았다. 자동 수신기 기반 채널 할당은 장비가 준비된 후속 하드웨어 작업이다.

## 쓰기 실패와 수명 처리

`serial.Serial`에 `write_timeout=0.1s`를 설정한다. `send_packet`은 전체 프레임의 단일 write가 완료되면 True, 연결 없음·부분 쓰기·timeout·예외면 False다. 부분 프레임의 나머지를 재시도하거나 재연결 시 자동 재생하지 않는다. 실패 신호 후 포트를 닫으며 실제 UI의 실시간 전송 체크도 해제한다.

GUI 스레드에서 무한 대기할 수 있는 `serial.flush()`는 호출하지 않는다. `send_phases` 반환 frame은 결정론적 비교용이며 실패 시에도 생성된 frame을 반환할 수 있다. 실제 전달 성공 여부는 `send_packet`의 반환값/실패 신호로 확인한다. 로컬 write 성공은 보드 ACK·wire 전달 완료·출력 OFF의 증거가 아니다. 연결 해제만으로 실물 출력이 꺼졌다고 표시하지 않는다.

현재 write 호출은 기존 GUI 경로에서 최대 설정 timeout까지 대기할 수 있다. 일반 송신 큐·계산/송신/렌더링 주기 분리·프레임 폐기 정책은 T6에서 확장한다. 실제 드라이버 지연이나 지속 갱신률을 이 fake-serial 검증으로 보장하지 않는다.

## 구현 파일과 실행한 검증

| 파일 | 역할 |
| --- | --- |
| [calibration.py](../src/acousticstudio/calibration.py) | 검증된 불변 보정 데이터·출처·이력·배열 서명·후보 맵 로딩 |
| [calibration_ui.py](../src/acousticstudio/calibration_ui.py) | 기존 창에서 수동 편집·읽기/저장·OFF 프레임 파일 생성 |
| [hardware.py](../src/acousticstudio/hardware.py) | 기존 컨트롤러 확장, 마스크·프로파일 양자화·OFF·bounded write |
| [trajectory_export.py](../src/acousticstudio/trajectory_export.py) | 동일 프레임/Phase32+OFF·보정 ID 내보내기 |
| [app.py](../src/acousticstudio/app.py), [geometry_scene.py](../src/acousticstudio/geometry_scene.py), [geometry.py](../src/acousticstudio/geometry.py) | 보드 메뉴·공통 이득 입력·상태 저장/복원·활성 상태 검증 |
| [test_calibration.py](../tests/test_calibration.py), [test_calibration_ui.py](../tests/test_calibration_ui.py) | 순서/보정/반올림/OFF/실패·실제 Qt 편집·전체 메인 연결 회귀 |

전체 pytest는 **208 passed, 3 skipped, 6 warnings, 20.69s**다. [JUnit](../scratch/ultraino_migration/t5_pytest.xml)에 211개 사례를 기록했다. skip은 기존 CUDA 없는 PyTorch 사례이며 warning은 기존 Taichi locale 1건과 기존 matplotlib get_cmap을 새 GUI 회귀가 호출한 5건이다. 테스트 중 발견한 기존 Legacy export fixture의 이득0은 이제 OFF 미지원으로 거절해야 하므로 일반 export 기준은 양의 이득으로 바꾸고 별도의 Legacy 이득0 거절 회귀를 추가했다.

새 검증은 반 스텝/음수/2π 경계, 위상0≠OFF, 맵 순열과 보정 부호·활성 매핑, 전체 OFF·한 채널, 같은 송신/내보내기 바이트, 프로파일/출처/절대 음압 오기입 거절, 이력/프로젝트/Undo/Redo, 배열 서명과 pose 독립성, 손상된 설정의 원자적 거절, 부분 write/timeout/연결 실패/health 실패·재연결 자동 재생 없음 등을 확인한다. 실제 GUI에서도 후보 맵 읽기·수동 수정·중복 맵 실패 후 초기화·JSON·OFF 파일을 실행했다.

[재현 도구](../scratch/ultraino_migration/verify_t5_pipeline.py)는 채널 CSV와 후보 맵 전 채널 비교 및 독립 코드의 4프로파일 × 일반/1채널/전체 OFF **12건**을 검증했다. 각 frame은 fake 송신·binary와 같고 CSV/C 헤더 값·보정 ID도 확인했다. 실제 메인 창에서 보정 적용 → T4 Kinoforms → 같은 이득의 T3 고정 위상 분석 → fake 송신/내보내기 → 보정 제거/프로젝트 복원까지 확인했다. [검증 JSON](../scratch/ultraino_migration/t5_pipeline_result.json)에 수정 소스·원본 프로토콜/펌웨어·CAD/채널 파일의 SHA256을 남겼다.

T3 예시 Focus 후보는 수렴했으나 전체 K의 음의 고유값으로 `non_restoring`이었다. 상대 이득/위상 보정 데이터를 저장했다고 절대 음압 보정이나 부양 성공으로 바꾸지 않았으며 `unavailable_uncalibrated_pressure`를 유지했다. 창 캡처는 확인했지만 3D 뷰포트 캡처·실제 파형·부양·k-Wave는 검증하지 않았다.

기존 Anaconda Python3.13.9/NumPy/Qt/pyserial/Numba/T2 DLL과 기존 CAD 입력을 재사용했다. 새 환경·패키지 설치·DLL 재빌드·CAD 재생성·backup 갱신은 없다. 관련 없는 Creo `std.out`은 보존했다.

저장소 루트에서 실행한다. 아래 도구는 실제 COM 생성자를 차단하고 fake serial을 사용하며 예시 프로젝트·보정·frame·캡처·검증 기록을 갱신한다.

```powershell
$env:PYTHONPATH='src'
$env:QT_QPA_PLATFORM='offscreen'
$env:PYTHONIOENCODING='utf-8'
& 'C:/Users/line0/anaconda3/python.exe' -m pytest -q --junitxml=scratch/ultraino_migration/t5_pytest.xml
& 'C:/Users/line0/anaconda3/python.exe' scratch/ultraino_migration/verify_t5_pipeline.py
& 'C:/Users/line0/anaconda3/python.exe' scratch/ultraino_migration/verify_t5_static.py
```

[정적 도구](../scratch/ultraino_migration/verify_t5_static.py)와 [기록](../scratch/ultraino_migration/t5_static_result.json)은 Python 51개 AST·문서 15개 UTF-8/로컬 링크 193개, T2 native/T4 공통 음장/T5 수정 입력·원본 프로토콜 해시, 프로젝트/보정/프레임 계약, JUnit과 `git diff --check`를 확인했다.

## 다음 에이전트의 T6 시작 기준

1. AGENTS.md, 계획, T4/T5 결과를 읽고 `git status --short`를 확인한다. 현재 T5 변경은 아직 커밋하지 않았다. T6 소프트웨어 선행 경로는 준비되었고 실제 펌웨어·배선·OFF 검증은 별도로 남아 있다.
2. `source_inputs(window)`의 보정 이득/활성과 T2 `field_kwargs`의 CAD 법선/개구, T4 worker/controller의 최신 요청/취소 구조를 재사용한다. 위상·시리얼·저장 계층을 중복 작성하지 않는다.
3. 기존 이벤트 필터/VTK picking을 확장해 단면 클릭·드래그의 세계 좌표, 선택/전체 제어점 XYZ 이동을 연결한다. 터널 이송 축은 Z다. T4의 phase-only 혼합 목표를 유지하고 매 waypoint 한 목표인 기존 궤적과 동시 다중 목표 이송을 구분한다.
4. GUI/VTK는 메인 스레드에서, 숫자 계산은 불변 스냅샷 worker에서 처리한다. 계산·송신·음장 그래프 주기를 분리하고 오래된 요청/프레임을 버리며 드래그 해제의 최종 위치를 적용한다. T5 write timeout과 실패 신호를 재사용하고 재연결 후 오래된 프레임을 자동 송신하지 않는다.
5. picking 좌표, 이동·정지·취소·창 닫기, 최종 위치/요청 순서, 렌더링·송신 중복과 bounded 큐를 fake-serial/Qt로 검증한다. 기존 궤적의 동기 계산은 worker로 옮길 때 오류·진단 실패 표시와 export 일치를 유지한다. stiffness norm/균일도를 부양 성공률로 사용하지 않는다.
6. 통신선 전송 시간과 실제 계산/드라이버 지연을 분리한다. 230400baud 8N1의 258byte 프레임은 선로만 약11.2ms이며 1ms 송신을 약속하지 않는다. 실제 컨트롤러/펌웨어·DATA 배선·채널 파형/OFF·유효 개구·입자·음압 보정이 확인된 사용자 요청 하드웨어 단계에서 지속 갱신률 및 T7 부양·Z 이송·정지 유지 실험을 기록한다.
