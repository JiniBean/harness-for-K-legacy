범위: 선택(추천: 전역)
구성: 스킬

# response

응답 형식 규칙(agent-rules `AGENTS.md` §3 응답 프로토콜)을 어겼다는 지적을 받았을 때 다시 설명하고, 지적을 `learned.md`에 한 줄씩 모았다가 규칙으로 압축하는 기능. 옛 이름 explain-plain.

## 사용자 안내

설명: 에이전트의 설명이 어렵거나 장황하다고 지적하면("이해가 안돼", "장황" 등) 에이전트가 쉬운 형식으로 다시 설명하고, 같은 실수를 줄이도록 그 지적을 기록합니다. 일반 설명 요청에는 쓰지 않습니다.

물어볼 것: 없음(`[묻지 않음]`).

## 포함 파일과 설치 위치

- 스킬 `skills/response/SKILL.md`, 지적 기록 `skills/response/learned.md` → `<.agents>/skills/response/`
- `<.agents>`는 전역 설치면 `~/.agents`, 프로젝트 설치면 `<프로젝트>/.agents`
- 규칙 본문은 agent-rules가 설치한 `AGENTS.md` §3에 있다. agent-rules를 끄면 이 스킬이 압축해 올릴 곳은 프로젝트 루트 `AGENTS.md`의 응답 절이다
