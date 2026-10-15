범위: 필수(프로젝트)
구성: 스킬, 도구 restore_eol

# verify

구현을 끝내기 전에 바꾼 코드를 정적으로 검사하는 기능(디버그 코드, 계획 밖 수정, 줄바꿈 + 켠 기능의 검사). 프로젝트에 항상 설치하고 끌 수 없다.

## 사용자 안내

설명: 에이전트가 작업을 끝냈다고 말하기 전에 남은 디버그 출력, 계획에 없던 파일 수정, 줄바꿈이 통째로 바뀐 파일을 찾아 고치게 합니다. 켠 기능(SQL 매퍼, 이력 주석 등)이 있으면 그 검사도 같이 돕니다.

물어볼 것: 없음(`[묻지 않음]`). 디버그 출력 패턴(`[verify] debug_patterns`)은 감지한 스택에 맞춰 정한다.

## 포함 파일과 설치 위치 (프로젝트만)

- 스킬 `skills/verify/SKILL.md` → `.agents/skills/verify/`
- 켠 기능의 `verify.md` → `.agents/skills/verify/checks/<기능>.md`
- 줄바꿈 복원 도구 `scripts/restore_eol.py` → `.agents/scripts/` (C_EOL 실패 시 사용)

## 설정 키

`[verify] debug_patterns`
