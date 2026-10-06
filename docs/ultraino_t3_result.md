# T3 고정 위상 방사력·복원성 분석 결과

2026-10-07. T3 구현과 소프트웨어 검증을 완료했다. **Creo R2의 8면·8기판·기판당 32개, 총 256채널**에서 송신 위상·진폭을 고정하고 평가 위치만 이동하여 고르코프 퍼텐셜, 방사력, 전체 3×3 복원행렬을 계산한다. 다음은 [계획의 T4 Kinoforms·다중 트랩](ultraino_migration_plan.md)다.

## 사용하는 방법

1. 기존 Creo 터널 프리셋을 추가하고 제어점을 만든 뒤 현재 공통 음향 설정으로 위상을 계산한다. 방향성 모델에는 확인된 유효 음향 개구가 필요하다.
2. `음장 → 고정 위상 방사력·복원성 분석`을 누른다. 선택한 제어점이 평가 중심이 되며 선택이 없으면 첫 제어점을 사용한다. 아직 계산하지 않았거나 음향 설정이 변경된 경우 재계산 안내를 표시한다.
3. 분석 창에서 중심 XYZ, 축별 범위 ±, 홀수 표본 수, 미분 간격 h, 수렴 허용 오차, 중력 XYZ와 입자 물성을 입력한다. 위치를 변경해도 송신 위상을 재집속하지 않는다.
4. `고정 위상으로 분석`을 누르면 힘·중력 가정 합성, 상대 음압, 퍼텐셜, 축별 복원 스티프니스 곡선을 볼 수 있다. 중심의 전체 복원행렬과 부호를 가진 고유값도 표시한다. 결합 방향의 비복원성을 대각 성분만으로 숨기지 않는다.
5. `분석 JSON 저장`은 고정한 송신기 위치·법선·위상·진폭·개구·공통 음향 설정, 물성 출처, 미분 수렴, 모든 곡선, 실제 엔진과 판정 한계를 함께 저장한다. 입력 변경·실패·취소 시 이전 결과의 저장을 해제한다.

기본 입자 반경 **0.25mm**는 소프트웨어 예시이며 실제 부양 대상의 크기가 아니다. 밀도 **25kg/m³**, 음속 **2350m/s**는 설치된 Levitate의 styrofoam 기본 물성을 참고한 예시다. 물성 구분과 출처를 필수로 보존하며, 반경·밀도·음속 또는 압축률을 직접 입력할 수 있다. 직접 압축률은 음속·밀도로 계산한 값을 대체한다. 실제 대상의 물성과 출처는 아직 미확정이다.

## 계산 계약과 판정 범위

T2의 `FieldConfig`와 `PhaseEngine.calculate_field_slice()`를 재사용한다. Creo 방사면 좌표와 실제 내향 법선, 소프트웨어 채널 순서를 유지하며 새로운 전파 엔진을 만들지 않았다. `FieldSnapshot`은 배열을 복사하고 읽기 전용으로 보존한다. 여기의 위상은 현재 계산된 소프트웨어 위상이며 실측 채널 보정·펌웨어 양자화 후의 실제 음장을 재현한 값이 아니다.

위치·반경 API는 mm, 내부 미분은 m, 위상은 rad다. 복소 음압은 peak phasor 규약이다. 입자 체적 V, 입자/매질 압축률 κp/κ, 밀도 ρp/ρ, 각주파수 ω를 사용한다.

```text
κ = 1 / (ρ c²), κp = 1 / (ρp cp²) 또는 직접 입력
f1 = 1 − κp / κ
f2 = 2(ρp − ρ) / (2ρp + ρ)
M1 = V f1 κ / 4
M2 = V (3/8) f2 / (ρ ω²)
U = M1 |p|² − M2 (|∂xp|² + |∂yp|² + |∂zp|²)
F = −∇U
Kij = −∂Fi/∂xj = ∂²U/(∂xi ∂xj)
conditional_total_force = nominal_acoustic_force + mass × gravity
```

원본 [CalcField.java](../../simulations/Ultraino/AcousticFieldSim/src/acousticfield3d/algorithms/CalcField.java)의 계수와 4차 정확도 1차 미분 스텐실을 옮겼다. 압력 기울기와 힘의 미분 계수는 `[1,−8,8,−1]/(12h)`, 위치는 `[-2h,−h,h,2h]`다. K 대각 성분은 5점 4차 정확도 2차 미분, 비대각 성분은 두 축의 1차 스텐실을 곱한 16점 혼합 미분이다. 혼합 성분은 양쪽에 같은 값을 기록하므로 행렬의 대칭 자체가 독립적인 물리 검증은 아니다. 전체 행렬은 Levitate의 힘을 별도로 미분한 기준과 비교했다.

Ultraino `calcForceGradients()` 및 Levitate `RadiationForceStiffness`는 **+∂F/∂x**를 반환한다. 이 창의 복원행렬은 **−∂F/∂x**다. Levitate의 `GorkovGradient`는 ∇U, `GorkovLaplacian`은 Hessian 대각 성분이다. 같은 입자·매질·음장으로 고르코프 계열을 비교했으며, 진행파 산란 항이 추가된 RadiationForce와 동일한 모델로 취급하지 않는다. 정의와 적용 범위는 [Levitate 공식 필드 문서](https://levitate.readthedocs.io/en/stable/api_docs/fields.html)를 참고한다.

각 분석에서 **h, h/2, h/4**로 모든 축의 힘·대각 스티프니스와 중심 전체 행렬을 계산한다. 최종 곡선은 h/4 값이며 두 번의 상대 변화가 모두 입력 허용 오차 이내일 때 수렴으로 표시한다. 초기 h는 파장의 1/8 이하여야 한다. 중심 행렬 변화의 spectral norm 최대값 두 배를 수치 부호 판정 여유로 사용한다. 이는 경험적 수치 변화 지표이며 엄밀한 오차 상한이나 물리 모델 오차가 아니다.

모든 고유값이 양의 판정 여유보다 크면 `restoring`, 음의 여유보다 작은 고유값이 있으면 `non_restoring`, 중립·수치 불확실성·수렴 실패는 `unresolved`다. **ka≤0.3은 이 소프트웨어의 보수적 진단 기준**이며 보편적인 물리 경계가 아니다. 이를 벗어나면 곡선은 볼 수 있어도 복원 부호 판정은 보류한다. 음원과의 거리가 입자 반경 또는 모델 최소 거리 이하인 스텐실, NaN/Inf와 잘못된 입력은 거절한다. 임의로 작게 잡은 h가 항상 더 정확한 것은 아니므로 세 간격의 결과를 확인한다.

**음압은 여전히 미보정 상대값**이다. `N*`, `J*`, `N*/m`는 상대 음압 1을 1Pa로 간주한 명목 계산 단위다. 중력 mg 자체는 입력한 물성에서 계산한 N이며, 음향 힘과 합성한 값은 같은 명목 음압 스케일을 가정한 결과다. 평형에는 XYZ 잔류력 모두가 0이어야 한다. 이 창은 잔류력과 가정 곡선을 제공하지만 `pressure_calibrated=false`, `gravity_equilibrium_status=unavailable_uncalibrated_pressure`를 유지한다. 실제 평형점을 자동 탐색하거나 부양 성공을 선언하지 않는다. `valid=true`는 수치 계산 성공을 뜻하며 실험 검증을 뜻하지 않는다.

작은 구의 비점성 고르코프 근사와 T2 자유 음장을 사용한다. 진행파 산란력·점성·기구물 반사/차폐를 포함하지 않는다. 국소 복원 부호만으로 동적 안정성이나 실험 성공률을 표시하지 않는다. 기존 궤적의 `relative_stiffness_norm` 및 기본 1mm styrofoam 진단은 별도 경로로 남아 있으며 T3 판정과 같지 않다.

## 구현 파일과 실행 환경

| 파일 | 이번 역할 |
| --- | --- |
| [force_analysis.py](../src/acousticstudio/force_analysis.py) | `ParticleConfig`, `AnalysisSettings`, `FieldSnapshot`, `ForceAnalyzer`. 위상 고정, 계수·미분·전체 K·수렴·명목 중력 잔류력·JSON 변환. |
| [force_analysis_ui.py](../src/acousticstudio/force_analysis_ui.py) | Qt 분석 창, 실제 QThread worker, 입력·곡선·행렬·출력·취소 및 종료 관리. |
| [app.py](../src/acousticstudio/app.py) | 음장 탭 버튼, 위상 계산 여부 확인, GUI 스레드에서 CAD 입력을 고정, 분석 설정 저장·복원 및 Undo/Redo. |
| [test_force_analysis.py](../tests/test_force_analysis.py) | 해석식·결합 부호·Levitate·강체 변환·수렴/실패·취소 검증. |
| [test_force_analysis_ui.py](../tests/test_force_analysis_ui.py) | 실제 worker 계산·결과 저장·입력 변경·취소·창 닫기·Escape·오류 처리. |
| [test_creo_geometry.py](../tests/test_creo_geometry.py) | 분석 설정의 저장·Undo/Redo·이전 파일 기본값·잘못된 설정에서 장면 보존. |
| [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) | Ultraino 파생 계산의 MIT 저작권 고지 보존. |

Qt/VTK actor 접근은 메인 스레드에서 스냅샷을 만들 때 완료한다. worker에는 순수 수치 데이터만 전달하고 결과 신호로 GUI를 갱신한다. 취소 Event를 수신점 chunk마다 확인한다. 계산 중 닫기/Escape는 취소를 요청하고 thread가 끝난 뒤 창을 닫는다. 실패·취소는 부분 결과를 정상 결과로 저장하지 않는다. 분석 설정은 프로젝트 `force_analysis_settings`에 저장하며, 키가 없는 이전 프로젝트는 명시된 예시 기본값을 사용한다.

기존 **Anaconda Python 3.13.9**, NumPy/SciPy/Levitate/PySide6/matplotlib과 T2 가속 계층을 재사용했다. 추가 설치·가상환경 생성·DLL 재빌드는 필요하지 않았다. 필수 의존성 10개와 별도 CAD 환경은 그대로다. 전파 행렬 생성은 CPU, 복소 합산은 선택 엔진이며 전체 계산의 GPU 이식이나 성능 향상 측정은 이번 범위에 포함하지 않는다.

## 실행한 검증과 재현

전체 테스트 **143 passed, 3 skipped, 1 warning (8.98s)**. [JUnit 기록](../scratch/ultraino_migration/t3_pytest.xml). skip 3개는 현재 설치본에서 사용할 수 없는 PyTorch CUDA, warning은 기존 Taichi locale 사용 중단 경고다.

- SI 계수와 압축률 직접 입력, 독립 정상파 해석식의 힘·복원 부호, 4차 미분 수렴을 확인했다.
- 대각 K가 모두 양수여도 결합 방향 고유값이 음수인 saddle을 구별했다. 일정 중력의 행렬 불변성과 XYZ 명목 평형 조건, 실제 음압 미보정 판정 보류를 확인했다.
- 무지향·sinc·피스톤에서 설치된 Levitate의 U/F/대각 K와 전체 힘 미분 기준을 비교했다. 4채널 합성 조건의 벡터/행렬 상대 오차는 각각 아래 표와 같다. 방향성 개구 **4.5mm는 합성 시험값이며 실제 송신기 개구가 아니다**.

| 같은 모델 기준 비교 | U 상대 오차 | F 상대 오차 | 전체 K 상대 오차 |
| --- | --- | --- | --- |
| 무지향 | 3.00e−9 | 2.44e−8 | 2.10e−5 |
| Ultraino sinc | 1.58e−6 | 2.77e−5 | 2.66e−5 |
| 원형 피스톤 | 4.16e−7 | 1.74e−5 | 2.05e−5 |

- 실제 Creo 256채널에 세 모델을 적용하여 고정 위상에서 강체 회전·이동 후 `F'=R F`, `K'=R K Rᵀ`를 검증했다.
- 세 모델 × 네 엔진 요청 **12건**의 전체 분석을 비교했다. C++와 실제 Taichi CUDA는 CPU 기준과 일치했고 최대 상대 오차는 F 약 **1.67e−12**, K 약 **5.34e−11**였다. PyTorch 요청은 CUDA 불가 사유와 함께 CPU로 전환됐다. [수치 비교·입력·환경·해시 JSON](../scratch/ultraino_migration/t3_numerical_result.json)에 기준값과 실행 시간을 보존했다. 시간은 warm-up이 포함된 단발 검증 기록이며 성능 벤치마크가 아니다.
- 실제 Qt 메인 창에서 Creo 프리셋·현재 위상 guard·C++ 분석·JSON 저장·설정 복원을 확인했다. 256개 위상이 분석 전후 같았고 시리얼은 연결하지 않았다. [Qt 실행 JSON](../scratch/ultraino_migration/t3_ui_result.json), [분석 스냅샷](../scratch/ultraino_migration/t3_example_analysis.json), [창 캡처](../scratch/ultraino_migration/t3_force_dialog.png), [곡선 PNG](../scratch/ultraino_migration/t3_force_curves.png)를 보존하고 그림을 직접 확인했다. Qt offscreen 3D 뷰포트 캡처는 제외했다.

Qt 예시의 터널 중심·Twin Trap·무지향·예시 입자는 수렴하고 명목 K 고유값 `[3.72e−5, 8.64e−5, 3.85e−4] N*/m`의 국소 복원 부호를 보였다. 그러나 중심의 가정 잔류력 Z는 약 `−1.60e−8 N*`였으며 중력 평형이 아니다. 이 결과를 실제 대상의 부양 검증으로 사용하지 않는다.

```powershell
# AcousticStudio 루트에서 기존 앱 환경을 재사용한다.
$env:PYTHONPATH = 'src'
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONIOENCODING = 'utf-8'
& 'C:/Users/line0/anaconda3/python.exe' -m pytest tests -q -rs --junitxml=scratch/ultraino_migration/t3_pytest.xml
& 'C:/Users/line0/anaconda3/python.exe' scratch/ultraino_migration/audit_t3_numerics.py
& 'C:/Users/line0/anaconda3/python.exe' scratch/ultraino_migration/verify_t3_ui.py
& 'C:/Users/line0/anaconda3/python.exe' scratch/ultraino_migration/verify_t3_static.py
```

[정적 검사 기록](../scratch/ultraino_migration/t3_static_result.json): Python 37개 AST, 문서 13개 UTF-8·로컬 링크 136개, T2 native 소스/DLL 및 수치 비교 입력 해시 일치, `git diff --check`를 확인했다. 실제 보드 송신·부양, CAD 재생성, k-Wave 실행은 수행하지 않았다. backup/commit/push는 갱신하지 않았다.

## 다음 에이전트의 T4 시작 기준

1. AGENTS.md, 계획, T2/T3 결과를 읽고 `git status --short`를 확인한다. 현재 다음 미완료 단계는 **T4**다. 기존 작업은 아직 커밋하지 않은 상태다.
2. 원본 [Kinoforms.java](../../simulations/Ultraino/AcousticFieldSim/src/acousticfield3d/algorithms/Kinoforms.java)를 읽고 `hologram.py`에 가상점 생성과 IBP를 추가한다. PhaseEngine 진입점과 T2 전파 행렬을 연결한다. 배열 로더·전파 엔진·시리얼 계층을 중복 작성하지 않는다.
3. Focus → 다중 Focus → Twin/Standing Wave 순서로 구현한다. Java 가상점 축/위상을 현재 Z축 터널 좌표계로 명시적으로 변환한다. 원본의 가상점 간격을 현재 mm/m 계약에 맞춘다. 초기 위상·반복 수·목표 진폭/상대 위상 제약을 재현 가능한 입력으로 남긴다.
4. 보드 지원이 확인되지 않은 진폭 제어를 전제로 삼지 않는다. phase-only 제약과 고정 음원 이득을 구분하고 영 복소값/영 진폭을 처리한다. 형상·법선·개구·공통 모델·목표점 변경 시 캐시를 무효화한다.
5. 결과의 균일도·잔차·256채널 실행 시간을 기록한다. 새 위상을 `FieldSnapshot`으로 고정하여 목표점마다 T3의 부호 있는 전체 K·수렴을 평가한다. 여러 음압 초점이나 stiffness norm의 양수만으로 다중 부양을 선언하지 않는다. 실시간 이동 중의 매 지점 재집속과 고정 위상 변위 스캔을 구분한다.
6. 계산은 취소 가능한 수치 worker에서, Qt/VTK 업데이트는 메인 스레드에서 처리한다. T3의 입력/결과 구조와 프로젝트 호환성·실패 처리를 재사용한다. T4 소프트웨어 검증은 COM 연결·실물 송신 없이 진행한다.

실측 유효 개구·대상 입자 물성·구동 조건별 음압/위상 보정, 물리 채널 맵과 펌웨어 확정은 여전히 남아 있다. 보정 데이터와 OFF·양자화는 T5, 조작/이송 및 실험 수용 기준은 T6/T7에서 이어간다.
