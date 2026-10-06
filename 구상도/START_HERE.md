# 작업 자료 — 여기서 시작

모델을 열거나 제작업체에 보낼 자료를 찾을 때 아래 표를 사용하세요.

| 할 일 | 파일 또는 폴더 |
|---|---|
| 최신 8면 Creo 조립품 열기 | [tunnel_8f_dual.asm](creo_tunnel/v2_dual_panel/native/tunnel_8f_dual.asm) |
| 최신 6면 Creo 조립품 열기 | [tunnel_6f_v2.asm](creo_tunnel/v2_dual_panel/native/tunnel_6f_v2.asm) |
| Creo 버전과 사용법 확인 | [Creo 안내](creo_tunnel/README.md) |
| 최신 8면·16기판 업체 제출 자료 | [PCB 안내](outputs/pcb/README.md) |
| KiCad 원본 수정 — 6면용 | [6면 기판](outputs/pcb/polygon_panels/panel_6faces_16ch/) |
| KiCad 원본 수정 — 8면용 | [8면 기판](outputs/pcb/polygon_panels/panel_8faces_16ch/) |
| 초기 6면·8면 예산 확인 | [제조 및 추가 부품 견적](outputs/pcb/polygon_panels/제작및추가부품견적_센서제외.md) |
| 생성 스크립트 찾기 | [scratch 안내](scratch/README.md) |

## 구성과 수량 구분

- `creo_tunnel/v1_single_panel`: 초기안. 6면 6기판·96송신기, 8면 8기판·128송신기.
- `creo_tunnel/v2_dual_panel`: 최신 모델. **8면은 면당 두 기판, 총 16기판·256송신기**입니다. 6면은 6기판 구조를 유지합니다.
- 기존 `6면_8면` 견적 문서는 초기 6기판·8기판 기준이며 최신 16기판의 총예산으로 그대로 사용하지 마세요.
- `ver1`~`ver4`: 기존 사용자 모델. 이번 정리에서 이동하거나 변경하지 않았습니다.

## 폴더 지도

```text
creo_tunnel/                 열어서 작업할 Creo 모델과 사용 안내
  v2_dual_panel/             최신안
  v1_single_panel/           초기안
outputs/
  pcb/                      KiCad, Gerber, BOM·PnP, 초기 견적 문서
  cad_generation/           Creo 생성 원본·중간 결과·기존 배포 ZIP
  budgets/                  예산표
  vendor_templates/         업체 원본 양식
  reference_analysis/       SonicSurface 참고 설계 분석
  concepts/                 초기 개념도
  docs/                     도구 설치 기록
scratch/                    생성·검증 스크립트와 임시 자료
ver1/ ~ ver4/               기존 사용자 모델
```

Creo는 선택한 버전의 `native` 폴더를 작업 디렉터리로 지정하고 조립품을 여세요. ASM과 참조 PRT를 개별적으로 옮기지 마세요. `creo_tunnel`은 편집용 정리본, `outputs/cad_generation`은 생성 과정과 기존 패키지를 보존한 폴더입니다.

PCB 자료는 견적용 P0입니다. 이번 폴더 정리는 제작 승인이나 부양 성능 검증을 의미하지 않습니다.

## 2026-10-06 정리 기록

기존 파일을 삭제하지 않고 용도별로 이동했습니다. 모델·Gerber·CSV·XLSX·ZIP 내용은 보존하고 스크립트 경로와 일부 안내 문서만 수정했습니다. [이동 및 SHA-256 확인 기록](scratch/organization/organization_verification_20261006.json)을 참고하세요.

기존 ZIP, JSON 생성 기록 및 manifest는 생성 당시 자료이므로 이전 경로나 수정 전 문서 해시가 들어 있을 수 있습니다. 현재 위치는 이 안내와 이동 기록을 기준으로 찾으세요.

`scratch/creo_cad_env`와 `scratch/pcba_artifact`의 실행 환경은 경로 의존성을 고려해 제자리에 보존했습니다. CAD 생성과 업체 업로드는 이번 작업에서 실행하지 않았습니다.
