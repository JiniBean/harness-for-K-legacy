범위: 선택(추천: 전역)
구성: 스킬

# memory-tidy

Claude Code 메모리와 대화 기록에 흩어진 사용자 교정을 모아 공유 지시 파일(AGENTS.md·스킬·docs)로 올리고 메모리를 정리하는 기능.

## 사용자 안내

설명: 대화 중에 에이전트에게 고쳐 달라고 한 내용이 메모리나 대화 기록에만 남아 있으면 다른 도구(Cursor 등)나 다음 대화에서 빠집니다. 이 기능이 그런 교정을 찾아 규칙 파일로 옮기자고 제안합니다.

물어볼 것: 없음(`[묻지 않음]`).

## 포함 파일과 설치 위치

- 스킬 `skills/memory-tidy/SKILL.md`, 대화 기록 수확 스크립트 `skills/memory-tidy/scripts/harvest.py` → `<.agents>/skills/memory-tidy/`
- `<.agents>`는 전역 설치면 `~/.agents`, 프로젝트 설치면 `<프로젝트>/.agents`
- 응답 방식 지적은 response 기능의 `learned.md`로 보낸다. response를 켜지 않았으면 `AGENTS.md`의 응답·서식 절로 올린다
