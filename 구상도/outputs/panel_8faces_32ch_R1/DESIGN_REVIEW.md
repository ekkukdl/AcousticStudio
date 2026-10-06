# R1 설계 검토 — KiCad 10.0.6 / 2026-10-06

## Overview / 판정

**새 네이티브 회로도·배선된 PCB·제작 출력의 시제품 설계가 완료되었습니다. 성능 및 생산 승인까지 검증한 설계는 아닙니다.** 원본 16채널 셀을 두 개 합쳐 32채널 한 장으로 만들었습니다. 외부 전원·FPGA·카메라·프레임은 별도 구성입니다.

## Critical Findings / 우선 확인

| 항목 | 판단·신뢰도 | 근거 및 영향 |
|---|---|---|
| FPGA 시프트 순서·헤더 분배 | 미확인 | 기존 펌웨어를 수정하지 않음. 맵은 QA…QH와 문서상 DATA 순서만 보장 |
| 트랜스듀서 정확한 제조사·연속 전압·정전용량 | 미확인 | D16/P10 기존 풋프린트만 유지. 전압과 열·전류 예산 확정 불가 |
| 물체 전체 촬영 | 미확인 | 물체 크기·카메라 위치 미정. 12.325 mm 기판 모서리 거리는 촬영 성립 증명이 아님 |
| 출력 귀환 경로·외부 케이블 EMC | heuristic / 중간 이하 | 자동 EMC가 92개 항목을 보고. 제조 연결 오류와 분리하여 파형·방사 실측 필요 |
| 전원 공급/커넥터 전류 용량 | inference-only | 동시 256채널 전류 미정. 보호·외부 분배·전압강하를 시스템에서 확인 |

## Previous Review Delta

기존 면당 16채널 PCB 2장/총16장에서 면당32채널 PCB1장/총8장으로 변경했습니다. 중앙 기판 슬롯을 제거하고 인접 면 틈은 유지했습니다. 기존 열18/행20 mm 간격을 유지하면서 두 셀 사이 열만22 mm로 조정했습니다. 발진면 거리300→210 mm, PCB84×224 mm, 고정 여백22 mm, GND 비아92개 추가. IC 구매 후보 표기를 Nexperia 74HCT595D,118로 통일했습니다. `delta_from_16ch.json`은 초기 분석 대비 자료이며 이후 GND 보강은 `stitching.json`에 별도 기록됩니다. 이전 업체의 0.002 mm 간격 지적은 원래 오류 좌표가 없어 해결을 단정하지 않습니다.

## Component Summary

74HCT595 4개, TC4427A16개, MMBT3904 2개, 저항50개, MLCC38개, 전해2개, 헤더4개, TX32개 = 전기부품148개/장. 고정홀4개 별도. SMT110/THT38. MPN은 BOM 후보이며 확정 구매 지시가 아닙니다. 제조사 미정 TX/헤더와 일부 배급사 번호가 없는 부품은 구매 확인이 필요합니다.

## Power Tree / Power Analysis

외부 +5V_A/B → 각 74HCT595 2개, OE/ARM 회로, 100 nF 2개 +10 µF 1개/뱅크.
외부 DRV_VDD_A/B → 각 TC4427A8개, 100 nF8개 +1 µF8개 +220 µF1개/뱅크.
GND는 두 뱅크 공통. 레귤레이터·전원 역접 보호·입력 퓨즈·전압감지 회로는 없음.
74HCT595은5 V 로직, TC4427A4.5–18 V 전원 범위(제조사 PDF p1), TTL 입력. TC4427A는 트랜스듀서 한쪽을 구동하는 비반전 듀얼 출력이며 브리지 구동이 아님. 1.5 A 표기는 드라이버의 피크 능력이며 연속 PCB 전류 정격으로 해석하지 않습니다. 용량성 전류/동적 소비는 주파수·부하 정전용량·전압·파형과 손실에 따라 달라 실측 예산이 필요합니다. 동박1oz는 제안값이며 실측 전류/허용 온도상승으로 재평가해야 합니다.

## Analyzer Verification / 핀 근거

별도 `verification.json` 검사는 원시 PCB 패드468개와 새 XML 네트리스트의 모든 핀을 대조하여 일치 확인(raw-file verified / 높음). 명시 NC36개와 기계NPTH4개는 구분했습니다. QA…QH→IN→TC4427A→OUT→TX32개 전부 검증했습니다.

| 부품 | 제조사 PDF / 페이지 | 검증 상태 |
|---|---|---|
| U1–U4 / 74HCT595D | Nexperia 74HC_HCT595, p5 핀 설명, p2 SO16 | datasheet-verified / 높음: 16VCC,8GND,14DATA,11SHIFT,12LATCH,13/OE,10/MR; 출력15,1…7 |
| U5–U20 / TC4427A | Microchip DS20001423, p8 핀 기능 | datasheet-verified / 높음: 2INA,3GND,4INB,5OUTB,6VDD,7OUTA,1/8NC |
| Q1–Q2 / MMBT3904 | Nexperia MMBT3904, p1 핀 표 | datasheet-verified / 높음: 1B,2E,3C |
| R1–R50,C1–C40 | 원시 패드/넷 대조; 후보 구매품 PDF 전수 검증 미실시 | raw-file verified / 높음; 제조사 공차·전압·패키지 전수는 미확인 |
| J1–J4 | 원시 번호/네트 대조 | raw-file verified / 높음; 구매 커넥터 방향·길이 미확인 |
| T1–T32 | 기존 D16/P10 모델 및 원시 패드 대조 | raw-file verified / 높음; 실제 송신기 데이터시트 미확인 |
| H1–H4 | PCB NPTH 지름3.2 mm | raw-file verified / 높음; 고정 하드웨어는 범위 밖 |

공식 PDF는 `datasheets/`에 보관했습니다. 구조화된 데이터시트 extraction 검증은 수행하지 않았으며 제조사 표를 직접 대조했습니다. 전체 부품의 제조사 데이터시트 검증이 완료되었다고 주장하지 않습니다.

## Signal Analysis Review

각 뱅크별 33 Ω 클록/래치 직렬 저항과 입력100 kΩ 풀다운을 유지했습니다. DATA0/1 각각8비트, SHIFT/LATCH/OE 공유인 두595 구성입니다. QA와 마지막에 시프트한 비트의 관계는 FPGA 구현에서 확인해야 합니다. ARM=LOW에서 Q OFF, OE HIGH,595출력고임피던스; 드라이버입력 풀다운으로 출력LOW가 의도됩니다(raw topology verified; 기동 과도파형 미측정). 출력 핀 접속만으로 FPGA 타이밍이나 음향 위상 보정까지 검증되지는 않습니다.

## PCB Layout Analysis

2층,84×224×1.6 mm. 트랙1408개, 비아206개(기존셀114+GND보강92). TX는 F면, 구동부 B면. 고정구간 y0–22 및202–224 mm는 전기 패드/배선 없는 것 확인. GND 두 면 채움, 뱅크 전원은 분리. 통합PCB 전체 시야·후면 하드웨어 간섭은 미검증.

## Thermal Analysis

`analyze_thermal.py`를 실행했으나 지원되는 발열부품/손실 데이터가 없어 분석이 SKIPPED되었습니다. TC4427A와 TX의 실제 손실·온도, 256채널 동시 동작 조건을 계산/측정하지 않았습니다. 열 안전 판정 없음.

## EMC / Cross-Domain Analysis

`analyze_emc.py` 재실행 92개: {'error': 26, 'warning': 53, 'info': 13}. 점수34/100은 해당 도구의 휴리스틱이며 인증 점수나 제조 합격 기준이 아닙니다. 출력 OUT의 참조면 공백과 층전환 귀환 경로, 드라이버 디커플링 거리, 외부커넥터 보호/필터를 주로 지적합니다. GND 비아를 추가한 후 cross_analysis의 접지 비아 밀도 경고는0개가 되었습니다. 다른 EMC 경고를 해결한 것으로 표시하지 않습니다. 짧은 드라이버-출력선도 빠른 에지가 있으므로 근거 없이 오탐 처리하지 않았습니다. 외부 케이블 길이, 스코프 입력/출력 파형, 링잉/그라운드바운스와 동시 스위칭을 확인하여 재배선 필요성을 판단합니다.

## Component Lifecycle

`lifecycle_audit.py --onlylcsc` 실행10개 후보 모두unknown. 이 모드는 수명상태를 확인할 수 없다는 도구 설명이 있어 공급/단종 상태로 해석하지 않습니다. 공식 제조사 생산 상태 및 실제 재고는 확인되지 않았습니다.

## Manufacturing / DFM / Testability

KiCad ERC0/DRC0/미연결0/패리티0. 9개 Gerber 및 독립 PTH/NPTH 드릴을 새 보드에서 출력했습니다. 정렬 경고는 동박영역 높이180 mm와 외곽224 mm의 의도된44 mm 차이이며 동일 좌표 원점을 유지합니다. 위·아래는 동박을 의도적으로 비웠으므로 레이어의 occupied bounding box가 같을 필요는 없습니다. Drill/outline/패드의 좌표 기준을 실제PCB 출력과 대조했습니다. SMT좌표110개를 manifest와 대조했으며 임의 bottom미러 변환 없음.

기존 커스텀 풋프린트에는 일부 courtyard가 없습니다. 업체 DFM과 조립방향·TX 극성·기구 높이 확인이 필요합니다. 전용 테스트 포인트/공장검사 지그는 추가하지 않았습니다. 헤더에서 전원·ARM·클록·데이터 확인, ARM off에서 전류 확인, 채널별 순차 활성화, 전체 동시 구동을 단계적으로 검증하는 것이 적절합니다(inference-only).

## False Positives / Reviewer Overrides

- KO-001 고정홀 keepout 오류4개: NPTH이며 KiCad rule-area가 패드/기계홀을 허용하고 트랙·비아·동박 채움만 금지합니다. 실제DRC0과 전기패드 부재 확인으로 오탐 판정(raw-file verified). 구멍을 전기적 접지 패드로 변경하지 않았습니다.
- GR-002 레이어 높이44 mm 차이: 고정용 무동박 영역 때문. 레이어 자동 bounding-box 비교에 따른 정렬 오탐이며 Gerber 원점이 다른 증거가 아님.
- 자동 lifecycle unknown 및 디커플링 거리 경고를 생산/전기 실패로 단정하지 않음. EMC 출력 참조면 경고는 남은 검토사항으로 보존.

## Not Performed / Review Limits

실행: KiCad ERC/DRC/패리티, XML netlist전수대조, analyze_schematic.py, analyze_pcb.py --full, analyze_gerbers.py, cross_analysis.py, analyze_emc.py, analyze_thermal.py(실행 후SKIPPED), lifecycle_audit.py(unknown), diff_analysis.py(16ch 초기분석 대비). 분석 결과는 `analysis/`에 보관.

미실행: SPICE(ngspice/상용엔진 설치없음, TX모델없음), 발주업체 DFM/패널화, FPGA 빌드·비트순서/배선 통합시험, 전체 제조사 부품 PDF확인, 열손실 계산/온도측정, 전류·EMI실측, 음향장/부상 실험, 카메라 광학 검증, 외부 프레임과 케이블 3D간섭 검사.

프로젝트 DRC ignore 유지: footprint_filters_mismatch, footprint_type_mismatch, missing_courtyard, track_not_centered_on_via, tuning_profile_track_geometries. ERC ignored_checks는 `ERC.json` 원문에 기록. 제외된 검사를 포함한 무조건 오류0 또는 양산 승인으로 해석하지 않습니다. 실제 위반을 항목별로 숨기는 DRC exclusions는 비어 있습니다.

## Final Verdict / trust_summary

원시파일·제조사 핵심IC 핀 연결: 신뢰 높음. 후보부품 완전성·열·EMC·FPGA 통합·음향/광학: 미확인 또는 휴리스틱. **KiCad 10에서 편집·검토할 수 있는 새 시제품 제작자료를 제공하며, 실물 성능·제조업체 승인 완료는 주장하지 않습니다.**
