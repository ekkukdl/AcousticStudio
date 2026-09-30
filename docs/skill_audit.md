# Codex 스킬 점검 — 2026-09-30

## 범위

개인 스킬(`~/.agents/skills`), 현재 Codex 계정의 `skills/.system`, 플러그인 캐시의
SKILL.md 존재·UTF-8 읽기·frontmatter 및 Markdown 상대 링크를 점검했다.
설치 구조 점검이며 모든 스킬의 외부 도구·계정·GUI 실행을 검증한 것은 아니다.
캐시 파일 존재와 현재 세션에서 사용할 수 있는 스킬은 구분한다.

| 대상 | 판단 및 조치 |
| --- | --- |
| computer-use, orca-cli, orchestration | Orca 버전에 맞는 안내를 CLI로 로드하는 구조. 유지. 사용 때 CLI와 권한 확인 |
| find-skills | 외부 스킬 탐색용으로 유지. 일반 코딩의 필수 단계로 사용하지 않음 |
| pptx | 연구 발표자료 제작용으로 유지. 실행 의존성은 사용 시 확인 |
| portfolio-case-study-writer | 포트폴리오 작성용으로 유지. 프로젝트 개발에는 로드하지 않음 |
| imagegen, openai-docs, plugin-creator, skill-creator, skill-installer | Codex 시스템 제공 스킬. 중복 설치·직접 수정 없이 유지 |
| work-pets 및 plugin-management | 제품별 플러그인. 초음파 개발 시 로드하지 않음 |
| 캐시의 review-agent·openai-templates | 파일 존재 확인. 현재 세션 활성화나 도구 사용 가능 여부를 추정하지 않음 |
| karpathy-guidelines | 점검한 개인/계정 스킬 경로에서 발견되지 않음. 강제 설치 요구 제거 |
| acousticstudio-development | 현재 계정의 `$CODEX_HOME/skills/acousticstudio-development/SKILL.md`에 신규 작성 |

링크 검사에서 skill-creator의 redlining.md/ooxml.md가 잡혔지만 실제 의존성이 아닌
코드 블록 속 문서 구조 예시이므로 수정하지 않았다. 기존 스킬 삭제·플러그인 해제는 하지 않았다.

## 변경 내용

- AGENTS.md를 기준 지침으로 신설하고 GEMINI.md는 이를 안내하도록 변경.
- 반복 승인, 불필요한 패키지/스킬 설치, 메서드 끝 배치 강제를 제거.
- 백업 보존 및 사용자 검증 후 명시적인 commit/push 원칙 유지.
- 전용 스킬은 물리 단위·상대 안정도·2D 음장·Qt 스레드·시리얼 경계조건에 집중.
- 신규 스킬은 새 세션의 목록에서 발견 여부를 확인해야 한다. 현재 목록이 즉시 갱신된다고 가정하지 않는다.

## 참고

- [공식 AGENTS.md 안내](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [공식 스킬 안내](https://learn.chatgpt.com/docs/build-skills)
