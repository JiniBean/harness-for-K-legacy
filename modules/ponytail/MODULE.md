범위: 선택(추천: 전역)
구성: 스킬 5종

# ponytail

코드 작성·설계·리뷰에서 가장 적게 만드는 해법을 고르게 하는 스킬 묶음. [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail)(MIT)을 고친 것이다. 원본 라이선스는 `skills/ponytail/LICENSE`.

## 사용자 안내

설명: 에이전트가 코드를 짤 때 새로 만들기 전에 이미 있는 코드·표준 라이브러리·기본 기능을 먼저 쓰게 하고, 변경분이나 저장소 전체에서 과하게 만든 부분을 찾아 줍니다.

물어볼 것: 없음(`[묻지 않음]`).

## 포함 파일과 설치 위치

| 스킬 | 하는 일 |
|---|---|
| `ponytail` | 최소 해법 고르기(lite/full/ultra) |
| `ponytail-review` | 현재 diff의 과잉 구현 리뷰 |
| `ponytail-audit` | 저장소 전체 과잉 구현 감사 |
| `ponytail-gain` | 효과 스코어보드 |
| `ponytail-help` | 명령 요약 |

- `skills/<스킬>/` → `<.agents>/skills/<스킬>/`. `<.agents>`는 전역 설치면 `~/.agents`, 프로젝트 설치면 `<프로젝트>/.agents`
- agent-rules `AGENTS.md`의 「코딩 기본값 (YAGNI)」 절은 이 기능과 별개로 agent-rules에 남는다
