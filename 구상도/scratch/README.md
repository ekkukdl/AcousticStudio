# 작업 스크립트와 임시 자료

| 폴더 | 용도 |
|---|---|
| [creo_scripts](creo_scripts/) | 형상 추출, Creo 변환·패키지 생성·검증 |
| [pcba_scripts](pcba_scripts/) | 부품 입력 추출 및 업체 요청 패키지 생성·검증 |
| [pcba_inputs](pcba_inputs/) | PCBA 생성용 JSON·CSV 입력 |
| [pcba_artifact](pcba_artifact/) | Node 표 생성 스크립트, 미리보기와 로컬 의존성 |
| [vendor_research](vendor_research/) | 업체 조사 자료와 다운로드한 JS |
| [organization](organization/) | 이번 정리 스크립트와 이동 검증 기록 |
| [organization/history](organization/history/) | 이전 이동·복사·확인 스크립트 보존 |
| `creo_cad_env` | 로컬 Python 환경. 기존 경로 유지, Git 제외 |

실행 시 작업 디렉터리는 **상위 `구상도`**입니다. 예: `python scratch/pcba_scripts/extract_pcba_parts.py`.

생성 스크립트는 결과물을 덮어쓸 수 있고 Creo 자동화는 로컬 Creo와 생성 당시 임시 파일이 필요합니다. 이번 작업은 Python 문법과 경로 확인만 수행했으며 생성 파이프라인 전체를 재실행하지 않았습니다. `organization/history`는 과거 배치 기준의 기록으로 재실행용이 아닙니다. `reorganize_files.py`도 일회성 이동 기록이므로 다시 실행하지 마세요.

업체 제출 파일은 [PCB 안내](../outputs/pcb/README.md)에서 찾으세요. `vendor_research`의 JS는 참고 자료이며 앱 코드가 아닙니다.
