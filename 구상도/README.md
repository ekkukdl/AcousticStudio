# 부양 터널 구상도와 제작 자료

**현재 파일 위치와 최신 작업 안내는 [시작 안내](START_HERE.md)를 기준으로 찾으세요.** 아래 이동 기록은 2026-10-05 당시의 폴더 구조입니다. 2026-10-06 정리 후 PCB 자료는 `outputs/pcb/polygon_panels`, 모델 생성 기록은 `outputs/cad_generation`에 있습니다. 이전 경로와 실행 안내는 과거 기록으로 보존합니다.

기존 모델 폴더와 함께 설계 산출물 및 작업 스크립트를 이 폴더에서 관리합니다.

## 최신 제작분: 면당 32채널 PCB와 프레임

- [KiCad 10 회로도·PCB·제작 자료](outputs/panel_8faces_32ch_R1/README.md): 한 면에 4×8개, 8면 총 256채널. PCB 84×224×1.6 mm, 발진면 간격 210 mm.
- [진녹색 PCB 및 외부 프레임 Creo R2](outputs/panel_8faces_32ch_R1/mechanical/creo32_frame_R2/사용안내.md): 상하 팔각 링 2개, 외형 265×265×224 mm, 면 사이 촬영용 틈 유지.
- [프레임 포함 모델 ZIP](outputs/panel_8faces_32ch_R1/mechanical/creo32_frame_R2/Creo32_frame_R2_models.zip), [전체 제작 자료 ZIP](outputs/panel_8faces_32ch_R1/Design_R1_complete.zip).
- [기존 회로·제작 방식 분석](outputs/pcb_review_2026-10-06/), [KiCad 스킬 설치 기록](outputs/KiCad10_스킬_설치기록.md).

이전 16장 구성은 아래 폴더에 보존했습니다. 최신 설계의 검사 범위와 미확정 사항은 각 사용안내·검토 문서에 기록했습니다. `scratch/creo32_env` 등 실행 환경, PTC 설치 파일, Creo 실행 로그 및 KiCad 로컬 UI 설정은 Git에 포함하지 않습니다. Creo 세션의 PTC 런타임은 설치된 Creo에서 `prepare_creo32_r1.py`로 복사하며, 새 컴퓨터에서는 경로와 실행 환경을 맞춰야 합니다. 최상위 `제개설/8면_256채널_PCB_프레임_2026-10-06` 폴더는 로컬 정리본이며 이 저장소의 최신 산출물을 복사한 것입니다.

- `creo_tunnel/`: 정리된 Creo 모델. 단일 패널 초기안과 면당 두 패널의 최신안을 구분합니다.
- `outputs/`: KiCad 설계, Gerber 견적 ZIP, BOM·PnP, 개념 모델, 분석 결과, 원본 업체 템플릿.
- `scratch/`: 모델 생성·검증·견적 파일 생성 스크립트 및 중간 결과.
- `outputs/polygon_panels/pcba_8faces_16boards/DOILLABS/`: 최신 DOILLABS 양식의 BOM·PnP XLSX. 8면, 면당 두 기판, 총 16장 구성입니다.

이전 상위 자료조사 폴더의 `outputs/`와 `scratch/`는 2026-10-05에 이 위치로 이동했습니다. 내부 상대 디렉터리 구조와 파일 내용은 유지했습니다. 이동 전후 SHA-256 비교 기록은 `artifact_move_verification.json`에 있습니다.

`scratch/creo_cad_env/` 가상환경과 `scratch/pcba_artifact/node_modules/` 외부 라이브러리 연결은 로컬에 보존하며 Git에는 포함하지 않습니다. 다른 컴퓨터에서는 실행 환경을 별도로 준비해야 합니다. Windows 가상환경은 경로가 이동되면 실행기 내부 경로가 이전 위치를 가리킬 수 있으므로 필요 시 새 위치에서 재구성합니다.

상대 `outputs/`와 `scratch/` 경로를 사용하는 스크립트는 이 `구상도` 폴더를 작업 디렉터리로 사용합니다. 기존 스크립트에 남은 절대 경로, 이전 실행 기록의 경로, 일부 스크립트의 `AcousticStudio/` 참조는 생성 당시 기록입니다. 실행 전 해당 경로를 점검해야 합니다. 이번 작업은 파일 이동과 내용 보존을 검증했으며 Creo 재실행이나 전체 생성 스크립트의 재실행은 수행하지 않았습니다.

PCB 파일은 견적용 P0 설계입니다. 업체의 간격 경고, 부품 품번 및 실장 방향 확인은 아직 제조 승인 전에 필요합니다. 부양 성능은 실물 시험으로 검증해야 합니다.
