범위: 선택(추천: 전역)
구성: 스킬

# garbage-collector

에이전트가 남긴 일회성 파일(`.agents/tmp/`, 세션 기록·임시 폴더, Cursor 대화 기록, VCS 미추적 파일)을 미리보기 → 사용자 승인 → 삭제 순서로 정리하는 기능.

## 사용자 안내

설명: 에이전트가 작업 중에 만든 임시 파일과 오래된 대화 기록을 찾아 목록으로 보여 주고, 승인하면 지웁니다. 아직 규칙으로 옮기지 않은 교정이 있을 수 있는 대화 기록은 memory-tidy를 먼저 돌린 뒤에만 지웁니다.

물어볼 것: 없음(`[묻지 않음]`).

## 포함 파일과 설치 위치

- 스킬 `skills/garbage-collector/SKILL.md`, 스캔 스크립트 `skills/garbage-collector/scripts/gc_scan.py` → `<.agents>/skills/garbage-collector/`
- `<.agents>`는 전역 설치면 `~/.agents`, 프로젝트 설치면 `<프로젝트>/.agents`
- 프로젝트마다 더 지울 대상은 프로젝트 `.agents/gc.toml`(스킬 본문 참고)
