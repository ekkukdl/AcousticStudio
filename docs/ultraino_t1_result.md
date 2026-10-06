# T1 Creo 터널 배열 연결 및 검증 기록

2026-10-07. T0에 이어 **8면·8기판·32송신기/기판, 총 256채널**의 Creo R2 프리셋을 구현했다. 다음 작업은 [계획의 T2](ultraino_migration_plan.md)다.

## 사용 방법과 표시 범위

`구성 → 배열 형태 → Creo 8면 터널 · 8기판 × 32채널 → 배열 3D 렌더링 생성`을 사용한다. 위치와 회전 입력으로 전체 조립체를 배치한다. 일반 모델/Grid/Spacing 입력을 숨기고 CAD 고정 치수를 안내한다. 기존 일반 Tube와 분리된 추가 프리셋이며 이미 있는 배열에 더해 생성한다. 보드 프로파일은 실제 펌웨어에 맞게 별도로 선택한다.

송신기는 CAD 외형 16mm, 높이 12.5mm의 원통이다. PCB 8개는 원본 84×224×1.6mm 치수·행렬, 프레임 링 2개는 R2의 내외측 아포템·높이·행렬로 표시한다. 구조물은 반투명 간략 표시이며 슬롯·나사홀·전자부품을 구현한 제조용 솔리드는 아니다. 새 CAD 생성기나 STEP 변환 의존성을 추가하지 않았다.

[독립 VTK로 확인한 3D 미리보기](../scratch/ultraino_migration/creo_tunnel_preview.png).

## 다른 에이전트가 이어서 사용할 구조

| 위치 | 책임과 계약 |
| --- | --- |
| [geometry.py](../src/acousticstudio/geometry.py) | `load_creo_tunnel()`은 패키지/저장소 위치 기준으로 기존 두 JSON을 읽는다. 작업 CWD와 사용자 이름을 하드코딩하지 않는다. `validate_geometry()`는 저장 스냅샷의 좌표·법선·회전·채널 순서·구조물 관계를 확인한다. `transform_geometry()`는 전체 방사면과 법선·구조물을 함께 변환한다. |
| [geometry_scene.py](../src/acousticstudio/geometry_scene.py) | GUI 스레드의 VTK 어댑터다. `create_geometry_actors`는 256개 송신기 및 10개 구조물 actor를 만든다. 원점은 방사면, 로컬 +Z가 방사 방향, 몸체는 로컬 -Z에 있다. `transducer_inputs()`는 CAD 모델 방사면 좌표·진폭을 읽고 레거시에는 기존 actor 좌표 어댑터를 사용한다. |
| [app.py](../src/acousticstudio/app.py) | `geometry_arrays`를 모델 원본으로 보존한다. CAD actor의 `_geometry_element`는 해당 모델의 채널 레코드를 참조한다. CAD 선택은 전체 배열로 확장하고 모델/방향을 바꾸는 개별 속성 편집은 막는다. UI 변환 후 `_sync_cad_geometry()`가 모델 및 구조물의 전체 pose를 갱신한다. |
| `get_state` / `set_state` | JSON과 Undo 스냅샷 양쪽에 `geometry_arrays`를 깊은 복사로 저장한다. 송신기 목록은 `geometry_instance`와 `geometry_channel`로 모델을 참조한다. CAD 구조물은 별도 음향 채널로 넣지 않는다. 저장된 스냅샷은 원본 CAD 파일 없이 복원할 수 있다. 누락·중복·재배열된 CAD 채널과 불일치 행렬은 장면을 지우기 전에 거절한다. |

스키마 버전 1은 `geometry_id`, 고유 `instance_id`, 단위 mm, 원본 좌표계/상태, 두 입력 JSON의 SHA-256, 치수, `world_transform`, `elements`, `supports`를 담는다. 송신기의 ID·channel·face/local_channel/row/column·bank·원본/세계 방사면 좌표·법선·진폭 가중치·활성 상태·주파수와 유효 음향 개구 미확정 값을 보존한다. 주파수 40kHz와 진폭 1은 초기 설정이며 실측 보정값이 아니다. 물리 맵의 후보 값은 원본 그대로 보존하며 송신 맵으로 자동 적용하지 않는다.

CAD의 방사면 위치와 `actor.center`는 **6.25mm** 차이 난다. 현재 PhaseEngine 호출, 음압 단면, 궤적 진단과 파일 출력은 모델 좌표를 사용한다. T2에서는 같은 모델의 법선 및 확정된 음향 개구를 공통 전파 모델에 연결한다. CAD 외경의 반경 8mm를 유효 음향 개구로 자동 가정하지 않는다.

## 검증과 재현

Anaconda Python 3.13.9를 그대로 사용했다. 새 환경·패키지를 생성/설치하지 않았다.

```powershell
# AcousticStudio 루트
& 'C:/Users/line0/anaconda3/python.exe' -c "import sys; sys.path.insert(0,'src'); import pytest; raise SystemExit(pytest.main(['tests','-q']))"
& 'C:/Users/line0/anaconda3/python.exe' 'scratch/ultraino_migration/verify_creo_preset.py'
```

최종 전체 테스트: **76 passed, 1 warning, 6.27s**. T0의 58개와 [T1 회귀 테스트](../tests/test_creo_geometry.py) 18개를 포함한다. 안내 레이아웃 조정 중 CAD/기존 UI의 집중 검사 19개도 통과했다.

- 256개 방사면·법선을 Creo R2의 송신기 및 면 행렬과 직접 비교했다. 원본 JSON 일치, face별 32개, 열 좌표 -29/-11/11/29mm, Z 좌표 -70..70mm/20mm 간격, 해시를 확인했다.
- face0/face2/대향 face4에서 VTK 로컬 방사면과 몸체 중심을 확인했다. PCB bounds와 두 링의 Z 위치를 확인하여 행렬 전치가 한 번 적용되는지 검증했다.
- 이동/회전과 법선·구조물 변환, ID·순서 보존, 저장/불러오기, Undo/Redo, 전체 삭제, 원본 파일 없는 스냅샷 복원, 잘못된 채널 순서 거부를 확인했다. 일반 Tube와 이전 test1.json도 읽었다.
- 실제 `AcousticStudioMain`을 Qt offscreen으로 초기화하고 프리셋 선택·입력 제어·생성·저장/복원을 확인했다. 설정은 임시 파일로 격리했고 리소스 모니터 스레드 시작과 실제 보드 연결을 하지 않았다. [실행 결과 JSON](../scratch/ultraino_migration/creo_preset_smoke_result.json)과 [재현 스크립트](../scratch/ultraino_migration/verify_creo_preset.py)를 남겼다.
- 같은 VTK 어댑터를 독립 offscreen Plotter에서 렌더링하고 PNG를 직접 확인했다. Qt offscreen의 뷰포트 캡처는 `Render window is not current`로 실패했으므로 성공으로 보고하지 않는다. Qt 위젯 캡처는 제어부 검사용이며 왼쪽 뷰포트의 빈 표시를 실제 데스크톱의 정상 3D 렌더링으로 해석하지 않는다.
- 최종 정적 검사: Python 파일 23개 AST, 문서 9개 UTF-8, 로컬 링크 97개와 `git diff --check` 통과.

실제 보드 송신·부양, 정상 데스크톱 Qt에서 마우스 픽킹·3D 조작, CAD 재생성, GPU 계산 커널 및 k-Wave solver는 실행하지 않았다. 기존 import의 Taichi 런타임 초기화/locale 사용 중단 경고는 T0와 같다. `backup/`, commit/push는 갱신하지 않았다.

UI 지연 입력은 T0의 양수 계약에 맞춰 1ms 이상으로 정리했다. 이전 저장 파일의 0 이하 지연은 기존 재생 fallback인 10ms로 읽는다. 이 설정은 실제 보드의 1ms 갱신 가능성을 보장하지 않는다.

## T2 전달 내용

현재 법선은 모델에 올바르게 저장되지만 물리 엔진은 아직 기존 ±Z 법선 추정·5mm 유효 개구와 상대 스티프니스 크기 모델을 사용한다. T2에서 모델 법선을 PhaseEngine의 공통 복소 음장에 전달하고, T3에서 방향별 힘·복원성과 실제 입자 조건을 검증해야 한다. 현재 장면 및 상대 점수를 실제 터널의 부양 검증으로 취급하지 않는다.

다음 에이전트는 AGENTS.md, 이 문서, ultraino_migration_plan.md의 T2를 읽고 `geometry_arrays[*].elements`를 재사용한다. 모델과 송신기 순서를 다시 생성하거나 일반 Tube 계산식·두 번째 시리얼 계층을 추가하지 않는다. 측정 보정·OFF·맵 저장·펌웨어별 양자화 경계는 T5, 다중 정지/이동 목표점 동시 재생은 T6에 남아 있다.
