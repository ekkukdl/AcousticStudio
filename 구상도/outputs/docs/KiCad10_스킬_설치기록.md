# KiCad 10 설계 지원 스킬 설치 기록

## 2026-10-06 현재 계정 설치

사용자가 KiCad 10.0 회로도 설계 스킬 다운로드를 요청하여 현재 계정에 아래 두 스킬을 설치했다. 아래의 2026-10-04 기록은 다른 계정의 설치 이력이며 현재 설치 위치와 구분한다.

- 설치 루트: `C:\Users\line0\AppData\Roaming\orca\codex-accounts\a053bc42-2712-4a29-83e3-7bca6d3b0d3f\home\skills`.
- `kicad-schematic`: American-Embedded/kistack의 `skills/schematic`, 커밋 `8494dbde095669df081950cbb6b24d08a21e25b0`. 회로도 작성·수정, 이미지 검토와 넷리스트 검증 지침. 특정 KiCad 버전 전용 코드는 아니며 현재 KiCad 10.0.6 CLI로 적용한다.
- `kicad`: aklofas/kicad-happy의 `skills/kicad`, 커밋 `78b8f02e70af5a29aef99ebd66b0d3538fb6010c`. 스킬 설명에 KiCad 5~10 지원 명시. 회로도·PCB·넷리스트 분석 및 교차 검토 도구 포함.
- Skills CLI 검색 설치 수: 회로도 스킬 312, kicad 893. GitHub 조회 stars: 각각 395, 1,336. 조회 시점 값이며 품질이나 전체 호환성 보증은 아니다.
- 공식 skill-installer의 GitHub 설치 스크립트로 커밋을 고정하여 다운로드. 설치된 SKILL.md 및 분석 스크립트 존재 확인.
- 실제 KiCad CLI: `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`, 버전 10.0.6.
- 검증: `analyze_schematic.py --help` 정상 종료, 기존 KiCad 10.0.6 회로도 `panel_8faces_16ch.kicad_sch`를 분석기에 입력해 JSON 출력 정상 완료. 결과는 `pcb_review_2026-10-06/skill_install_schematic_smoke.json`에 저장.
- 이 실행은 설치 및 파일 파싱 확인이며 새 회로 설계·전체 설계 리뷰·전기적 타당성 검증이 아니다. 기존 회로도/PCB는 변경하지 않았다.
- 두 스킬은 KiCad 내부 플러그인이 아니라 Codex가 사용하는 설계 지원 스킬이다. 다음 대화 턴부터 사용 가능하다.

출처: [회로도 작성 스킬](https://github.com/American-Embedded/kistack/blob/8494dbde095669df081950cbb6b24d08a21e25b0/skills/schematic/SKILL.md), [KiCad 5~10 분석 스킬](https://github.com/aklofas/kicad-happy/blob/78b8f02e70af5a29aef99ebd66b0d3538fb6010c/skills/kicad/SKILL.md).

---

확인일: 2026-10-04

## 현재 환경

- Windows / PowerShell.
- 실제 확인한 KiCad CLI 버전: 10.0.6.
- 실행 파일: `C:\Users\line0\AppData\Local\Programs\KiCad\bin\kicad-cli.exe`.
- 설치 위치: `C:\Users\line0\AppData\Roaming\orca\codex-accounts\3085b31c-8e42-4e8c-be20-346bf798bd11\home\skills`.
- 기존 스킬 목록에는 KiCad 전용 스킬이 없었다.

## 설치한 스킬

| 설치 이름 | 출처 | 용도 | 설치 기준 커밋 |
|---|---|---|---|
| kicad-schematic | american-embedded/kistack, skills/schematic | 회로도 작성·수정, 데이터시트와 넷리스트 대조, 도면 시각 검토 | 8494dbde095669df081950cbb6b24d08a21e25b0 |
| kicad-pcb | american-embedded/kistack, skills/pcb | 부품 배치, DRC, 레이어 및 3D 간섭 검토 | 8494dbde095669df081950cbb6b24d08a21e25b0 |
| kicad | aklofas/kicad-happy, skills/kicad | 회로도·PCB·Gerber 분석 및 회로도와 PCB 비교 | a6bba1add1e18b89e3aa0824b9769ed1d9d79174 |

KiStack은 KiCad 10 전용 구현이나 GUI 조작 플러그인이 아니라 설계 작업 지침이다. 현재 설치된 KiCad 10.0.6의 CLI와 라이브러리를 사용해 적용한다. kicad-happy는 스킬 설명에서 KiCad 5~10 지원을 명시한다. 모두 커뮤니티 제작 스킬이며 KiCad 공식 제공 스킬은 아니다.

## 선택 근거

skills.sh 및 GitHub에서 공개 후보를 검색하고 스킬 원문과 저장소 정보를 비교했다. 조회 당시 KiStack 저장소는 395 stars, kicad-happy는 1,330 stars였다. Skills CLI 조회 설치 수는 KiStack 회로도 309, PCB 307, kicad-happy의 kicad 888이었다. 수치는 조회 시점의 값이며 품질 보증이 아니다.

- KiStack: 별도 MCP 서버나 WSL 없이 기존 도구를 사용해 설계할 수 있는 지침. 회로도와 PCB 작업을 분리해 필요한 지침을 선택할 수 있다.
- kicad-happy: 원본 파일과 분석 결과의 교차 검증, 근거 및 확신 수준 구분을 강조하며 분석 스크립트를 제공한다.
- Potapovrg/kicad-skill: KiCad 10을 명시하지만 WSL과 작성자의 경로를 전제로 하므로 이번 Windows 환경의 기본 선택에서 제외.
- bretbouchard/kicad-agent: 별도 volta 백엔드와 Beads 작업 추적 도구 의존성이 있어 제외.
- fl4p/kicad-design: 상세 검증 지침이 있으나 추가 외부 도구와 작성자의 로컬 환경을 참조하는 부분이 있어 기본 선택에서 제외.
- Seahan1/kicad-agent: 회로도 절차는 관련성이 있으나 확인 당시 사용 근거가 상대적으로 적어 기본 선택에서 제외.

## 설치 및 확인 범위

- skill-installer의 GitHub 설치 스크립트로 커밋을 고정해 세 스킬 설치 완료.
- `analyze_schematic.py --help`, `analyze_pcb.py --help`가 Python 3.13.9에서 오류 없이 종료됨을 확인.
- 이는 도구 시작과 기본 의존성 확인이다. 실제 설계 전체 분석, 모든 기능의 KiCad 10 호환성, 회로의 전기적 타당성 또는 부상 성능을 검증한 것은 아니다.
- 전체 설계 검토를 시작할 때 해당 스킬의 전체 지침을 다시 읽고, EMC·SPICE·데이터시트 분석 등 관련 보조 스킬이 필요한지 확인한다. 이번 설치에는 해당 보조 스킬을 포함하지 않았다.
- KiCad 애플리케이션 내부 메뉴에 설치되는 플러그인이 아니라 AI 에이전트가 읽는 스킬이다. 다음 대화 턴부터 사용 가능하다.
- 기존 회로도와 PCB 파일은 수정하지 않았다.

## 다음 설계 단계

사용자는 기존 6면·8면 초안의 구조가 원하는 방향과 다르다고 밝혔다. 해당 초안의 패널 치수, 열·행 수, 부품 위치를 확정 조건으로 취급하지 않는다. 기판 수정 전에 사용자와 전체 형상, 트랜스듀서 배열, 구동 회로의 위치, 패널별 인터페이스를 토론해 구체화한다.

## 출처

- [KiStack](https://github.com/american-embedded/kistack)
- [KiStack 회로도 스킬](https://github.com/american-embedded/kistack/blob/8494dbde095669df081950cbb6b24d08a21e25b0/skills/schematic/SKILL.md)
- [KiStack PCB 스킬](https://github.com/american-embedded/kistack/blob/8494dbde095669df081950cbb6b24d08a21e25b0/skills/pcb/SKILL.md)
- [kicad-happy](https://github.com/aklofas/kicad-happy)
- [kicad-happy 분석 스킬](https://github.com/aklofas/kicad-happy/blob/a6bba1add1e18b89e3aa0824b9769ed1d9d79174/skills/kicad/SKILL.md)
- [KiCad 10 CLI 공식 문서](https://docs.kicad.org/10.0/en/cli/cli.html)
