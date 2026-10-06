# T2 공통 복소 음장·방향성 모델 결과

2026-10-07. T2 구현과 소프트웨어 검증을 완료했다. Creo R2 **8면·8기판·기판당 32개, 총 256채널**의 방사면 위치·내향 법선을 실시간 위상, 음압 단면, 궤적 진단, 파일 출력에 전달한다. 다음 작업은 [계획의 T3](ultraino_migration_plan.md): 고정 위상에서의 방사력·복원성 분석이다.

## 사용 방법과 미확정 입력

1. `구성`에서 기존 Creo 터널 프리셋으로 배열을 추가하고 제어점을 만든다.
2. `음장 → 공통 음향 모델`에서 무지향 점음원, Ultraino sinc, 원형 피스톤을 선택한다. 주파수·매질 음속/밀도·상대 음압 스케일을 같은 패널에서 설정한다. `Focus`도 트랩 종류에 추가했다.
3. 방향성 모델에는 **유효 음향 개구 반경(mm)**이 필요하다. 기본값은 미확정이다. CAD 외경 반경 8mm 및 기존 코드의 5mm를 대신 넣지 않는다. 제조사 자료/측정값을 확보하기 전에는 기본 무지향 모델을 사용한다.
4. 설정을 바꾸면 위상을 다시 계산한다. 오래된 단면은 숨기고 재계산 전 수동 송신을 보류한다. 개구 미확정·잘못된 계산 입력은 오류를 표시하며 파일을 생성하지 않는다.

개구 입력은 해당 값이 없는 채널의 공통 대체값이다. 이미 저장된 채널별 유효 개구가 우선한다. 공통 설정은 프로젝트 `acoustic_model` 및 Undo/Redo에 저장한다. 기존 프로젝트에 이 키가 없으면 무지향/40kHz/343m/s/미확정 개구로 읽는다. 음압 및 10/16mm·랑주뱅 진폭 가중치는 **미보정 상대값**이다. 공통 주파수는 시뮬레이션 설정이며 보드 발진 주파수를 변경하는 명령이 아니다.

테스트의 4.5mm·5mm·8mm 반경은 수식을 검증하기 위한 합성 값이다. 실제 16mm 송신기의 확인된 유효 개구로 저장하거나 해석하지 않는다. 이번 작업에서 새 환경·패키지는 설치하지 않았다.

## 재사용할 코드와 데이터 계약

| 파일 | 역할 |
| --- | --- |
| [field_model.py](../src/acousticstudio/field_model.py) | `FieldConfig`, `propagation_matrix`, 법선/반경 검증, Levitate 어댑터. 전파 모델의 기준 구현이다. |
| [field_backends.py](../src/acousticstudio/field_backends.py) | 같은 복소 행렬의 합산을 Numba/C++/Taichi/PyTorch로 수행한다. 실제 사용 엔진 및 CPU 전환 사유를 반환한다. |
| [phase_engine.py](../src/acousticstudio/phase_engine.py) | 기존 진입점에 `field_config`, `normals`, `aperture_radii_mm`을 추가했다. UI는 모든 계산/출력에 이 인자를 전달한다. |
| [geometry_scene.py](../src/acousticstudio/geometry_scene.py) | `transducer_inputs`: CAD 방사면·진폭. `transducer_acoustic_inputs`: CAD 법선·개구, 레거시 actor의 실제 로컬 +Z 방향. ±Z 배열 추정을 사용하지 않는다. |
| [acoustic_model_ui.py](../src/acousticstudio/acoustic_model_ui.py) | 공통 설정 패널, `field_kwargs`, 계산 실패/실제 엔진 표시. 별도 메인 창이나 시리얼 계층을 만들지 않았다. |
| [sonic_core.cpp](../src/acousticstudio/sonic_core.cpp), [sonic_wrapper.py](../src/acousticstudio/sonic_wrapper.py) | 새 `complex_matvec` ABI 및 f64 Taichi 합산. 기존 C++ 위상 ABI도 유지한다. |
| [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) | Ultraino 파생 부분의 원본 저작권과 MIT 라이선스 고지. |

뷰어와 공개 전파 API의 위치/개구 입력은 mm, 법선은 무차원 `(N,3)`, 진폭은 비음수 `(N,)`, 위상은 rad `(N,)`다. 내부 거리·반경은 m, 파수는 rad/m다. 채널 순서를 변경하지 않는다. `G`는 `(수신점 수, 송신기 수)` 복소 행렬이며

```text
k = 2πf/c
x = k × 유효 반경(m) × sin(방사 방향과 수신 방향의 각도)
D_point = 1
D_sinc = sin(x)/x = np.sinc(x/π), x=0일 때 1
D_piston = 2 J1(x)/x, x=0일 때 1
G[p,n] = source_strength × D[p,n] × exp(+i k r[p,n]) / r[p,n]
pressure = G @ (amplitudes × exp(i phases))
```

Ultraino `apperture`는 지름이므로 반으로 변환한다. 음압 단면은 512개 수신점씩 계산한다. 음원 근접점은 분모만 `min_distance_m=1e-6`으로 제한하고 위상에는 실제 거리를 쓴다. 이는 수치 발산 방지이며 물리 근접장 모델이 아니다. 궤적 물리 미분 진단은 이 범위의 점을 거절한다. NaN/Inf·0 법선·음수 진폭·형상/채널 불일치도 거절한다.

세 모델 모두 자유 음장 근사다. sinc와 피스톤 모델은 전/후 방향에 대칭이며 반사·차폐·배플·실측 후면 감쇠를 포함하지 않는다. 음압의 부호가 음수인 방향성 로브는 π 위상 반전을 유지한다. `Focus`는 공통 전파의 켤레 위상을 사용하고 다중 제어점에서는 방향성 및 1/r 가중치를 포함한 켤레장을 합산한다. 기존 Twin/Vortex signature는 세계 좌표 X/XY 기준으로 유지했다. 강체 회전 불변성의 위상 테스트는 Focus에 적용했으며 Twin/Vortex signature의 방향까지 회전시키는 기능은 추가하지 않았다.

Levitate는 동일한 주파수·음속·밀도·음압 스케일·법선·반경을 받는다. 무지향은 PointSource, 방향성은 공통 directivity와 PointSource의 미분 스텐실을 사용한다. 기존 `CircularPiston(0.005)`·±Z 추정·Levitate 기본 p0=6/음속 약343.237 사용을 제거했다. 독립 `SimulationMedium`을 사용하여 전역 `materials.air`를 변경하지 않는다. **방향성 미분은 Levitate의 유한차분이므로 T3에서 간격 수렴을 확인해야 한다.**

외부 레거시 호출의 호환을 위해 `field_config=None` 위상 호출은 종전 알고리즘 경로를 유지한다. 설정 없는 음장 호출도 같은 Green 구현을 쓰되 기존 1/mm 스케일을 유지한다. 신규 기능과 UI는 항상 명시적 `FieldConfig`를 전달해야 한다. 기존 배열의 위치 어댑터는 actor 중심을 유지하며, Creo는 반드시 모델 방사면을 사용한다.

## 환경·가속 검증

Anaconda Python 3.13.9와 기존 SciPy 1.15.3을 재사용했다. 직접 사용하는 SciPy를 requirements/공통 설치 카탈로그/확인 버전에 추가하여 필수 항목 **10개**를 맞췄다. 실제 의존성·엔진·오차는 [T2 환경 및 비교 JSON](../scratch/ultraino_migration/t2_backend_result.json)에 있다.

| 경로 | 이번 실행 결과 |
| --- | --- |
| NumPy 기준/Numba CPU | 세 모델의 복소 음압·위상 비교 통과 |
| C++ | 기존 Visual Studio 18 Community, MSVC 14.50.35717 x64 `/O2 /openmp`로 재빌드. scratch DLL 검증 후 런타임 DLL 반영. 복소 합산과 기존 위상 ABI 확인. 별도 비교의 최대 절대 복소 오차 약8.1e-14 |
| Taichi 1.7.4 | 실제 `cuda` 아키텍처에서 f64 복소 합산·위상 검증. 256채널 기록의 최대 절대 복소 오차 약7.1e-14 |
| PyTorch 2.14.0 | 설치본의 CUDA build가 null이며 CUDA 사용 불가. 새 복소 CUDA 경로는 구현했지만 직접 실행 검증하지 못했다. CPU 전환 및 표시 검증, CUDA 테스트 3개 skip |

전파 행렬 생성은 NumPy/SciPy CPU에서 수행하고 복소 합산만 가속한다. 이번 작업은 전체 계산의 GPU 이식이나 성능 향상 측정이 아니다. DLL 누락/이전 ABI/로드 오류 또는 GPU 실패는 같은 모델의 CPU로 전환하며 사유를 표시한다. 새 DLL은 Windows x64 MSVC/OpenMP 런타임을 사용하므로 다른 머신에서는 DLL 로드 또는 CPU 전환 여부를 확인한다.

## 실행한 검사와 재현

전체 테스트 **116 passed, 3 skipped, 1 warning (8.76s)**. [JUnit 결과](../scratch/ultraino_migration/t2_pytest.xml). skip은 PyTorch CUDA 3개, warning은 기존 Taichi의 Python locale 사용 중단 경고다.

- 단일 음원 SI 거리/위상/진폭, Java sinc π 규약/지름 해석/음의 로브, sinc와 Bessel 차이.
- 동일 단위·주파수·음속·스케일에서 설치된 Levitate 음압 비교. 피스톤은 채널별 CircularPiston 구현과 별도 비교.
- 실제 Creo 256채널의 수평 내향 법선, 8면 대칭, 강체 회전·이동 후 음장 및 Focus 위상 불변성.
- 실시간/궤적/단면 공통 계산, chunk 경계/빈 입력/근접점/NaN/Inf, 개구 미확정과 물리 실패의 진단 불가 처리.
- C++/Taichi 세 모델·Focus/Twin/Vortex 비교, DLL 미지원/GPU 불가 CPU 전환. 파일 프레임과 공통 모델의 실시간 프레임 일치.
- 모델 설정의 저장·복원/Undo/Redo, 이전 프로젝트 기본값, 잘못된 설정에서 장면 보존 및 Qt signal 복원.
- 실제 Qt 창에서 세 모델 계산, 미확정 개구 오류, 14,400점 XY 음압 단면·프로젝트 복원. [Qt 실행 기록](../scratch/ultraino_migration/t2_ui_result.json), [패널 캡처](../scratch/ultraino_migration/t2_model_controls.png), [동일 데이터의 독립 VTK 렌더](../scratch/ultraino_migration/t2_field_xy.png)를 직접 확인했다. Qt offscreen 뷰포트 캡처는 검증 범위에서 제외한다.

```powershell
# AcousticStudio 루트. 기존 환경을 사용하며 설치하지 않는다.
$env:PYTHONPATH = 'src'
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONIOENCODING = 'utf-8'
& 'C:/Users/line0/anaconda3/python.exe' -m pytest tests -q -rs
& 'C:/Users/line0/anaconda3/python.exe' scratch/ultraino_migration/audit_t2_backends.py
& 'C:/Users/line0/anaconda3/python.exe' scratch/ultraino_migration/verify_t2_ui.py

# 이미 설치된 Visual Studio로 재빌드하는 경우. 먼저 scratch 산출물을 검증한다.
$env:STUDIO_VCVARS = 'C:/Program Files/Microsoft Visual Studio/18/Community/VC/Auxiliary/Build/vcvars64.bat'
cmd.exe /c scratch\ultraino_migration\build_t2_native.cmd
& 'C:/Users/line0/anaconda3/python.exe' scratch/ultraino_migration/verify_t2_native.py
```

[native 결과/해시](../scratch/ultraino_migration/t2_native_result.json)를 보존했다. scratch의 컴파일 중간 파일은 정리했으므로 native 재검증은 빌드부터 실행한다. 실제 보드 송신·부양, CAD 재생성, k-Wave 실행은 하지 않았다. backup/commit/push를 갱신하지 않았다.

현재 원본 조사 보고서는 작업공간의 `보고서 및 구체화` 폴더에 있다. 계획의 보고서 링크를 이 위치에 맞췄으며 원본 문서는 수정하지 않았다.

정적 검사: Python 30개 AST, 문서 9개 UTF-8 및 로컬 링크 81개, native 소스/DLL 해시 일치와 `git diff --check` 통과. [검사 기록](../scratch/ultraino_migration/t2_static_result.json).

## 다음 에이전트의 T3 작업

1. AGENTS.md, 작업 계획, 이 기록을 읽고 현재 모델 계약을 유지한다. 배열 좌표·새 전파 엔진·두 번째 시리얼 계층을 만들지 않는다.
2. `force_analysis.py`와 기존 창에 연결할 분석 UI를 추가한다. `FieldConfig`, `propagation_matrix`, `source_parameters`, `levitate_transducer`를 재사용하고 **송신 위상/진폭을 고정한 채 수신점만 이동**한다. 궤적 최적화의 매 지점 재집속을 변위 스캔으로 사용하지 않는다.
3. 입자 반경·밀도·음속/압축률·중력 방향을 입력으로 명시한다. 현재 궤적 진단은 Levitate 기본 1mm styrofoam 입자와 상대 stiffness norm을 사용하므로 사용자 부품의 안정성 결과가 아니다.
4. `F=-∇U`, 복원행렬 `K=-∂F/∂x` 부호, 축별 곡선과 필요한 경우 전체 결합 행렬, 대칭/평형/중력 조건, 미분 간격 수렴을 검증한다. source_strength와 경험적 진폭은 미보정이므로 절대 N 또는 실험 성공률을 주장하지 않는다.
5. 기존 궤적 `metrics`는 `score_kind=relative_stiffness_norm`, `pressure_units=relative_uncalibrated`, `stiffness_units=nominal_N_per_m_uncalibrated`다. norm의 양수만으로 복원성을 판정하지 말고 T3 분석 결과와 구분한다. solver 실패·미확정 입력은 점수 없이 진단 불가를 유지한다.

현재 남은 사용자/실물 입력은 유효 음향 개구와 출처, 구동 조건별 음압·위상 보정, 대상 입자/부품 물성이다. Kinoforms는 T4, 채널 맵 확정·보정·OFF·펌웨어 양자화는 T5, 실제 이송과 부양 검증은 T6/T7에서 이어간다.
