# T4 Kinoforms·다중 트랩 구현 및 검증 결과

2026-10-07. T4 구현과 소프트웨어 검증을 완료했다. **Creo R2의 8면·8기판·기판당 32개, 총 256채널**을 그대로 사용하며 Focus/Twin/Standing Wave를 함께 설계한다. 송신기 이득을 고정하고 위상만 조절한다. 다음은 [계획의 T5 통신·캘리브레이션](ultraino_migration_plan.md)다. 다중 음압 제약을 구현한 결과이며 실제 다중 입자 부양을 확인한 결과는 아니다.

## 앱에서 확인하는 순서

1. `구성 → 배열 형태 → Creo 8면 터널 · 8기판 × 32채널`을 선택하고 배열을 추가한다. 제어점을 두 개 이상 만들고 목록의 체크를 켠다. 검증 예시는 `(-10,-3,5)`, `(8,4,-7)` mm다. 한 점도 계산할 수 있으며 체크를 끈 점은 설계에서 제외된다.
2. `음장 → 공통 음향 모델`을 확인한다. 실측 유효 개구가 없으면 무지향 모델부터 사용한다. CAD 외경은 유효 음향 개구로 대체하지 않는다. 아래 방향성 비교의 4.5mm 반경은 검증용 가정이다.
3. `음장 → 다중 트랩 설계 (Kinoforms)`를 연다. 활성 제어점별 Focus/Twin/Standing Wave, 상대 목표 음압 가중치, 세계 좌표 방향 XYZ를 입력한다. 타입을 바꾸면 Twin은 X, Standing Wave는 터널 Z가 기본 방향이 된다. 방향은 내부에서 단위 벡터로 정규화되며 영 벡터는 거절한다.
4. 재현 비교는 최대 반복 50회, 위상 변화 허용값 0, 초기 `0 위상`으로 시작한다. 기본 설정은 최대 50회·허용값 1e−6rad이며 정체 시 조기 종료한다. `새 제어점·단일 궤적 기본 트랩`은 기존 표 행의 타입을 바꾸지 않는다.
5. `Kinoforms 계산`을 누르고 실제 엔진, 잔차 곡선과 가중 음압 균일도를 확인한다. 잔차가 단조 감소하거나 작은 값에 도달한다는 보장은 없다. 위상 정체도 최적해·복원성·부양 성공을 뜻하지 않는다.
6. 표에서 검사할 트랩을 선택한 뒤 `선택 트랩의 고정 위상 분석`을 연다. 후보 위상을 배열에 적용하지 않아도 T3에서 XYZ 힘, 전체 K의 부호와 미분 수렴을 확인할 수 있다. 다른 점도 선택해 각각 검사한다. 실제 입자 물성은 별도로 입력해야 한다.
7. `현재 배열에 위상 적용`으로 메인 위상·색상·Kinoforms 모드와 제어점별 설정을 갱신한다. `설계 JSON 저장`은 초기/최종 위상과 입력 스냅샷을 함께 기록한다. 설정 변경·실패·취소 시 이전 결과의 적용/저장은 해제된다.
8. 프로젝트 저장·복원 및 Undo/Redo는 설정·목표·활성 체크를 유지한다. 메인 Kinoforms 모드에서 제어점을 이동한 뒤 계산하면 새 위치를 반영한다. 기존 자동 계산이 꺼져 있다면 위상 계산을 다시 실행한다. 기존 Focus/Twin Trap/Vortex Trap 경로도 유지한다.

계산 중 취소·닫기·Escape는 현재 수치 호출이 끝난 뒤 thread 종료를 기다린다. COM 연결 없이 이 순서를 확인할 수 있다. [설계 창 예시](../scratch/ultraino_migration/t4_design_dialog.png), [잔차·음압 그래프](../scratch/ultraino_migration/t4_constraints.png), [혼합 설계 JSON](../scratch/ultraino_migration/t4_example_design.json)을 남겼다.

## 계산 계약과 원본 대응

원본은 [Kinoforms.java](../../simulations/Ultraino/AcousticFieldSim/src/acousticfield3d/algorithms/Kinoforms.java)다. T2의 공통 Green 행렬과 엔진별 복소 합산을 재사용한다. 별도 전파 모델·시리얼 컨트롤러·CAD 생성기는 추가하지 않았다. [MIT 고지](../THIRD_PARTY_NOTICES.md)를 보존했다.

| 입력/출력 | 계약 |
| --- | --- |
| `TrapTarget` | 세계 좌표 `position_mm`, `trap_type`, 양의 `weight`, 비영 `direction` |
| `HologramSettings` | 반복 1~2000, 위상 허용값 0~0.1rad, 기본 타입, `zeros/current` 초기화 |
| 음원 | CAD 방사면 mm 좌표·실제 법선·소프트웨어 순서의 고정 상대 이득·확인된 개구 |
| 전파 | `FieldConfig`와 T2 모델; 내부 거리는 m, 주파수 Hz, 위상 rad |
| 구동 | 이득 양수 채널은 복소 구동 크기 1, 이득 0은 모델상 0. 조절 가능한 진폭은 구현하지 않음 |
| 결과 | 소프트웨어 순서 위상, 가상점/그룹/부호/가중치, 초기/최종 잔차, 반복 이력, 실제 backend/전환 사유 |
| 단위 | `relative_uncalibrated`, `pressure_calibrated=false`. 목표 가중치는 Pa가 아님 |

Java→AcousticStudio는 `(x,y,z) → (x,−z,y)`인 오른손 변환이다. 원본 Y는 현재 터널 Z가 되고 원본 Z는 −Y가 된다. `JAVA_TO_STUDIO`로 축과 Twin 회전 방향을 검증했다. GUI 방향은 변환된 세계 좌표를 직접 입력하며 트랩 타입을 제어점 색으로 인코딩하지 않는다.

| 타입 | 가상점 | 그룹 내 상대 위상 |
| --- | --- | --- |
| Focus | 중심 한 점 | 자유 앵커 위상 |
| Twin | 중심 ± `(λ/1.5) × direction` | 0, π |
| Standing Wave | 중심 ± `(λ/2) × direction` | 0, π |

원본 `sep`는 중심에서의 **오프셋**이다. 두 점의 전체 간격은 각각 2λ/1.5와 λ이며 다시 반으로 나누지 않는다. λ는 공통 설정의 c/f에서 계산한다. 가상점 중복·음원 근접점은 거절한다. 최대 목표 256개와 행렬 원소 2,000,000개 제한으로 과도한 입력을 막는다.

`H = G × fixed_source_gain`으로 두고 `p=Hq` 전방 투영 → 각 그룹 첫 가상점의 위상을 앵커로 한 상대 음압/π 제약 `d` → `Hᴴd` 공액 역전파 → 활성 채널 크기 1 정규화를 반복한다. 영/근영 목표 음장은 이전 앵커(초기 1+0j)를 유지하고, 영 역전파 채널은 이전 위상을 보존한다. 전체 영 음장이나 비유한 결과는 성공으로 반환하지 않는다.

잔차는 양의 공통 상대 음압 스케일 α를 적합한 `||p−αd||/||p||`다. 균일도는 `min(|p|/weight)/max(|p|/weight)`다. 두 값은 음압 제약의 지표다. 허용값은 공통 위상 회전을 제거한 채널별 위상 변화의 최댓값에 적용하며, 목표 잔차 허용값으로 사용하지 않는다.

단일 전파 행렬 캐시는 음원 좌표·법선·고정 이득·개구·모델 설정 및 목표 위치/타입/가중치/방향을 해시한다. 반복 수·초기화 설정은 행렬 자체를 바꾸지 않지만 결과 적용용 입력 해시에는 포함한다. 새 초기 위상으로 같은 행렬을 재사용할 수 있다. `snapshot.initial_phases_rad`는 실제 계산에 사용한 초기값을 기록한다.

## 연결 파일과 비동기 처리

| 파일 | 역할 |
| --- | --- |
| [hologram.py](../src/acousticstudio/hologram.py) | 불변 설정/목표, 가상점, IBP, 지표, 캐시, 취소 |
| [phase_engine.py](../src/acousticstudio/phase_engine.py) | `calculate_hologram` 및 기존 `calculate_phases`의 Kinoforms 진입점 |
| [hologram_ui.py](../src/acousticstudio/hologram_ui.py) | 수치 worker/controller, 설계 창, 결과 JSON, T3 후보 분석 |
| [app.py](../src/acousticstudio/app.py) | 기존 음장 탭 연결, 메인 계산·색상·저장·Undo/Redo |
| [test_hologram.py](../tests/test_hologram.py), [test_hologram_ui.py](../tests/test_hologram_ui.py) | 독립 반복 기준·경계조건·엔진/궤적 연결·실제 Qt thread 수명 검증 |
| [test_creo_geometry.py](../tests/test_creo_geometry.py) | 기존 저장과 트랩 메타데이터·활성 체크·비원점 복원 회귀 |

수치 worker에는 `FieldSnapshot`, `TrapTarget`, 설정, 취소 Event만 전달한다. Qt/VTK actor와 위젯 읽기·갱신은 GUI 스레드에서 한다. controller는 한 번에 한 worker만 실행하고 마지막 대기 요청만 보존한다. 이전 요청은 취소하고 요청 번호가 일치하는 결과만 전달한다. 메인 창은 현재 입력 해시까지 다시 비교하여 계산 중 위치/모델이 바뀐 결과를 폐기하고 새 결과 전 송신을 보류한다. 입력 변경이 계산 요청을 발생시키지 않은 경우에는 사용자가 다시 계산해야 한다.

프로젝트에는 `hologram_settings`, 제어점 `hologram_target={trap_type,weight,direction}`, `active`를 저장한다. 새 필드를 먼저 검증한 뒤 장면을 변경한다. 이전 파일의 누락 필드는 기본 Focus/50회/0 초기화 및 활성 상태로 복원한다. 비원점 구의 로컬 mesh 중심과 actor 이동을 중복 적용하던 복원 오류도 수정했다.

**프로젝트 복원은 저장된 설정으로 위상을 재계산한다.** `현재 위상` 초기화는 당시 actor의 위상을 사용하며 위상이 없으면 0이다. 프로젝트에는 초기 위상 배열과 최종 해를 고정 저장하지 않으므로 이 옵션의 정확한 반복 재실행은 설계 JSON의 초기 스냅샷으로 수행한다. 기본 0 초기화의 반복성·프로젝트 복원을 확인했다.

정확한 설계 재실행의 API 형태는 다음과 같다. 메인 GUI에 설계 JSON을 불러오는 별도 기능은 추가하지 않았다.

```python
import json
from pathlib import Path
from acousticstudio.field_model import FieldConfig
from acousticstudio.hologram import HologramSettings, TrapTarget
from acousticstudio.phase_engine import PhaseEngine

data = json.loads(Path("design.json").read_text(encoding="utf-8"))
snapshot = data["snapshot"]
result = PhaseEngine().calculate_hologram(
    snapshot["sources_mm"], [TrapTarget(**item) for item in data["targets"]],
    snapshot["amplitudes"], field_config=FieldConfig(**snapshot["field_config"]),
    normals=snapshot["normals"], aperture_radii_mm=snapshot["aperture_radii_mm"],
    settings=HologramSettings(**data["settings"]), initial_phases=snapshot["initial_phases_rad"],
)
```

기존 궤적 위상 생성/최적화/내보내기는 같은 Kinoforms 설정을 전달하지만 **웨이포인트별 한 이동 목표**를 계산한다. 현재 초기 위상 배열은 이 경로에서 전달하지 않아 각 단계가 0에서 시작한다. 동시 다중 입자 궤적 UI·일반 드래그 큐·궤적 작업 전체의 비동기화는 T6 범위다. Vortex/BFGS/DivTrans 이식도 후속 범위다.

## 실행한 검증과 해석 범위

전체 pytest는 **171 passed, 3 skipped, 1 warning, 12.58s**였다. 3개 skip은 기존 PyTorch CUDA 전용 사례이며 CUDA 없는 현재 build에서 제외했다. warning은 기존 Taichi locale 항목이다. [JUnit 기록](../scratch/ultraino_migration/t4_pytest.xml)에 174개 사례를 남겼다. 새 회귀는 독립 스칼라 실수/허수 IBP, 단일 초점 공액 위상, 고정 불균일 이득/영 채널, 혼합 목표, 가중치·중복·근접·잘못된 설정·취소, 강체 변환, 캐시 무효화와 GUI thread 최신 요청 처리 등을 확인한다.

[원본 Java 비교 도구](../scratch/ultraino_migration/verify_t4_java.py)는 **수정하지 않은 원본 Kinoforms.java**를 기존 OpenJDK 25.0.4.1로 컴파일했다. 4음원·2목표·고정 단위 이득·초기 위상 `(0.2,0.9,2.4,3.2)` rad·12회 `iterate(true)` 조건으로 비교했다. 수학/엔티티/공통 점음원 전파 어댑터를 사용했으며 원본 전체 앱·렌더러·물성 모델의 통합 비교는 아니다. 원본 가상점과 반복 알고리즘을 실제 실행한 비교다.

| 타입 | 공통 위상 정렬 후 최대 phasor 오차 |
| --- | --- |
| Focus | 7.12e−8 |
| Twin | 1.06e−7 |
| Standing Wave | 2.05e−7 |

Java float32와 Python float64 차이를 허용했다. 원본 SHA256과 결과는 [Java 비교 기록](../scratch/ultraino_migration/t4_java_result.json)에 있다.

[수치 점검](../scratch/ultraino_migration/audit_t4_numerics.py)은 Creo256채널·두 예시 목표·50회 고정 반복으로 3전파 모델 × 3타입 × 4엔진 요청 **36건**을 비교했다. CPU/C++/실제 Taichi CUDA가 일치했고 Torch 요청은 CPU로 전환했다. 최대 공통 위상 정렬 phasor 오차 **2.89e−14**, 복소 음장 상대 오차 **1.44e−15**다. 모델·엔진·캐시·시간·해시는 [수치 기록](../scratch/ultraino_migration/t4_numerical_result.json)에 있다.

동일 스냅샷의 T3 고정 위상 분석 **18건**에서 h·h/2·h/4 수렴, 전체 K와 힘, 미보정 중력 평형 보류를 기록했다. 예시 반경 0.25mm·밀도 25kg/m³·음속 2350m/s EPS 조건에서 두 목표 모두 Focus/Twin은 `non_restoring`, Z Standing Wave는 `restoring`이었다. 이는 해당 목표·이득·입자·자유 음장 조건의 국소 부호 결과다. 음압 미보정 상태의 N*·J* 가정값이며 실제 XYZ 힘 평형이나 부양을 확인하지 않았다. 모든 사례는 `unavailable_uncalibrated_pressure`를 유지했다. Focus의 높은 균일도도 복원성의 근거로 쓰지 않는다.

캐시 사용 단일 CPU 점음원 사례는 4.4~8.6ms였다. 통제된 벤치마크가 아닌 검증 실행의 시간이며 다른 작업 부하·초기 컴파일·작은 행렬의 GPU 호출 비용이 포함될 수 있다. Taichi 첫 Focus는 kernel 컴파일을 포함했다. 1~2ms 성능을 약속하지 않는다.

[실제 Qt 메인 창 점검 도구](../scratch/ultraino_migration/verify_t4_ui.py)는 Creo256채널/C++에서 세 타입 및 Twin+Standing Wave 혼합 계산·적용, 선택 후보 T3 worker, JSON 저장, 메인 최신 입력 검증·재계산·캐시, 설정/목표/비활성 체크 복원, 계산 중 창 종료를 실행했다. [Qt 기록](../scratch/ultraino_migration/t4_ui_result.json)에 모두 남겼다. 캡처는 설계 창·그래프를 확인했고 offscreen 3D 뷰포트는 시각 검증하지 않았다. serial은 연결하지 않았고 실제 송신 호출이 발생하면 실패하도록 했다.

자유 음장과 작은 구 비점성 고르코프 모델을 사용한다. 기구물 반사·차폐·점성·진행파 산란은 포함하지 않는다. 실측 유효 개구·대상 입자·구동 조건별 음압/위상 보정은 아직 없다. 이득 0은 계산상의 비활성 채널이며 실제 하드웨어 OFF 전송과 구분한다.

## 환경 재사용과 재현 명령

기존 `C:/Users/line0/anaconda3/python.exe`의 Python 3.13.9, NumPy 2.2.6/SciPy 1.15.3/Numba 0.62.1/PySide6 6.9.2/Levitate 3.0/Taichi 1.7.4/Torch 2.14.0을 재사용했다. T2 DLL·CAD JSON·Qt 렌더링 기반도 재사용했다. 원본 비교는 기존 `C:/Program Files/Eclipse Adoptium/jdk-25.0.4.101-hotspot/bin`을 PATH에 추가했으며 JDK는 앱 실행 의존성이 아니다. 추가 환경 생성·설치·CAD 재생성·DLL 재빌드·backup 갱신은 하지 않았다.

저장소 루트에서 다음을 실행한다. UI 검증은 isolated QSettings/offscreen 모드이며 실제 COM을 열지 않는다. Java 도구에는 원본이 있는 상위 `simulations/Ultraino` 경로와 기존 JDK가 필요하다.

```powershell
$env:PYTHONPATH='src'
$env:QT_QPA_PLATFORM='offscreen'
$env:PYTHONIOENCODING='utf-8'
$env:PATH='C:/Program Files/Eclipse Adoptium/jdk-25.0.4.101-hotspot/bin;' + $env:PATH
& 'C:/Users/line0/anaconda3/python.exe' -m pytest -q --junitxml=scratch/ultraino_migration/t4_pytest.xml
& 'C:/Users/line0/anaconda3/python.exe' scratch/ultraino_migration/verify_t4_java.py
& 'C:/Users/line0/anaconda3/python.exe' scratch/ultraino_migration/audit_t4_numerics.py
& 'C:/Users/line0/anaconda3/python.exe' scratch/ultraino_migration/verify_t4_ui.py
& 'C:/Users/line0/anaconda3/python.exe' scratch/ultraino_migration/verify_t4_static.py
```

[정적 점검 도구](../scratch/ultraino_migration/verify_t4_static.py)와 [기록](../scratch/ultraino_migration/t4_static_result.json)은 Python 45개 AST, 문서 14개 UTF-8·로컬 링크 164개, 원본/수치 입력/T2 native 해시, JUnit, Qt 결과, `git diff --check`를 확인했다. T0~T3는 사용자 요청으로 [00de06b](https://github.com/ekkukdl/AcousticStudio/commit/00de06b6607c9a822d11f38f1c8f563095d41ae1)를 main에 push했다. T4도 이후 사용자 요청으로 [1d3d83f](https://github.com/ekkukdl/AcousticStudio/commit/1d3d83faa289d0cc9d619fc37097d954442e5052)를 main에 push했다. 관련 없는 Creo `std.out`은 보존했다.

## T5 구현에 사용한 인계 기준

아래 기준에 따른 T5 소프트웨어 검증도 완료했다. 현재 T6 인계와 남은 실제 하드웨어 검증은 [T5 결과](ultraino_t5_result.md)를 따른다.

1. AGENTS.md, 계획과 이 결과를 읽고 현재 변경을 확인한다. 다음 미완료 단계는 **T5 실제 뱅크 연결에 맞는 통신·캘리브레이션**이다. 기존 `HardwareController`, `BoardProfile`, `set_channel_map`, `phases_to_steps`, `encode_phase_frame` 및 테스트를 확장한다. 별도 시리얼/위상/전파 계층을 만들지 않는다.
2. 소프트웨어 순서의 위상 오프셋·음원 이득과 출처/측정 조건/단위/압력 보정 여부, CAD·배선·보드 버전을 가진 보정 데이터를 추가한다. 이득은 음향 모델 입력이며 보드의 가변 구동 진폭 지원을 가정하지 않는다. 위상 보정의 부호를 명시하고 기준 파형으로 확인한다.
3. [채널 표](../구상도/outputs/panel_8faces_32ch_R1/channel_map.csv)와 [후보 맵](../구상도/outputs/panel_8faces_32ch_R1/physical_to_software_channel_map.json)을 읽는다. 방향은 `map[physical_frame_channel] = software_channel`이다. 계산 위상 → 소프트웨어 보정 → 위상/활성 상태 물리 매핑 → 프로파일별 양자화/OFF → 인코딩을 실시간과 내보내기에서 공통 사용한다. 후보 맵은 실측 배선 검증 완료로 표시하지 않는다.
4. **8 PCB는 8 FPGA 주소가 아니고 16뱅크는 16 체인 보드가 아니다.** 실제 컨트롤러 수·펌웨어·DATA 할당·시프트 비트 방향을 확인한다. 기존 256채널 프로파일/128채널 태그 분할을 PCB당 32채널 기준으로 임의 변경하지 않는다. 실제 송신에는 해당 입력 확정이 필요하지만 보정/프레임의 소프트웨어 개발은 계속할 수 있다.
5. 프로파일별 지원이 확인된 OFF 값과 위상 0을 분리한다. 한 채널/전체 OFF·활성 상태·반 스텝/2π 경계·보정 부호·맵 순열·전체 프레임 커밋·내보내기 일치를 fake serial로 확인한다. 미지원 조합은 명시적으로 실패한다. 연결 해제·부분 쓰기·timeout·재연결 시 이전 상태 문제도 검증한다.
6. 설정/보정의 프로젝트 저장·Undo/Redo·이전 파일 기본값과 Qt 수명 처리를 확인한다. 이번과 같은 COM 없는 검증을 먼저 완료한다. 실물 파형/출력 OFF/지속 갱신률·부상 실험은 사용자 요청 하드웨어 단계에서 기록한다. 조작·다중 입자 이송 및 실험 수용 기준은 T6/T7에서 이어간다.
