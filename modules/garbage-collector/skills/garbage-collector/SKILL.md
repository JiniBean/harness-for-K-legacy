---
name: garbage-collector
description: 에이전트가 남긴 불필요한 파일을 정리한다. 대상은 <프로젝트>/.agents/tmp 일회성 파일, Claude Code 세션 기록·세션 임시 폴더, Cursor agent-tools·대화 기록, 프로젝트 루트의 VCS 미추적 파일, 프로젝트 .agents/gc.toml에 적힌 추가 대상이다. 미리보기 → 사용자 승인 → 영구 삭제. 트리거 — 가비지컬렉터, 가비지 컬렉터, gc 돌려, 임시 파일 정리, tmp 정리, 세션 정리, 세션 기록 정리, 대화 기록 정리, 디스크 정리(에이전트 파일), 쌓인 파일 정리. 메모리 내용 정리·규칙 승격은 memory-tidy가 맡는다. 소스 코드의 죽은 코드 정리나 빌드 산출물 정리에는 쓰지 않는다.
---

# garbage-collector

전역 규칙 `~/.agents/AGENTS.md` §2 「파일 생성 위치」가 정한 위치(`.agents/tmp`)와 하네스가 자동으로 쌓는 세션 파일을 정리한다. 삭제는 되돌릴 수 없으므로 목록을 보여 주고 승인을 받은 뒤에만 지운다.

## 절차

1. 현재 프로젝트 루트에서 스캔한다. 삭제는 하지 않는다.
   ```bash
   python ~/.agents/skills/garbage-collector/scripts/gc_scan.py --project <프로젝트 루트>
   ```
   분류별 건수·용량 요약이 출력되고, 전체 목록은 `<프로젝트>/.agents/tmp/YYYYMMDD_gc_plan.json`에 저장된다.
2. 사용자에게 요약 표를 보여 준다. 분류별로 대표 경로 몇 개와 가장 최근 수정일을 같이 적는다. `note:` 줄은 그대로 전한다.
3. `untracked`(review only)는 자동 삭제 대상이 아니다. 파일마다 무엇인지 한 줄로 설명하고 지울지 묻는다. 사용자가 일부만 지우라고 하면 plan json에서 나머지 항목을 빼고 `--include-review`로 실행한다.
4. 승인을 받으면 실행한다. 승인 범위가 일부 분류뿐이면 `--only`로 좁힌다(요약 표의 분류 이름을 쉼표로). plan json을 고치는 별도 스크립트를 만들지 않는다.
   ```bash
   python ~/.agents/skills/garbage-collector/scripts/gc_scan.py --apply <plan json> [--only tmp,extra:log] [--include-review]
   ```
   사용자가 "바로 지워"처럼 미리 승인했으면 2단계 보고를 건너뛰고 실행한다. 이때도 `untracked`는 파일별 확인이 필요하므로 포함하지 않는다.
5. 결과(삭제 건수, 실패 목록과 사유)를 보고한다. 실패가 있으면 성공으로 말하지 않는다.

## 대상과 기준

| 분류 | 위치 | 기준 |
|---|---|---|
| tmp | `<프로젝트>/.agents/tmp/**` | 수정 후 보존 기간 경과. `keep` 패턴 제외 |
| claude_temp | `%TEMP%\claude\<프로젝트>\<세션>\` | 세션 폴더 안 최신 파일 기준 경과 |
| claude_sessions | `~/.claude/projects/<프로젝트>/<id>.jsonl` + `<id>/` | 경과 + 수확 완료(아래). `memory/`는 건드리지 않음 |
| cursor_tools | `~/.cursor/projects/<프로젝트>/agent-tools/*` | 경과 |
| cursor_transcripts | `~/.cursor/projects/<프로젝트>/agent-transcripts/*` | 경과 + 수확 완료 |
| extra:<경로> | `gc.toml`의 `[[extra]]` | 항목별 `days` |
| untracked | `git status`의 미추적 파일 | 확인 후보만 |

보존 기간 기본값은 30일이다. Claude Code 내장 자동 삭제(`cleanupPeriodDays`)는 60일로 두어 안전망으로만 쓴다. 수확 전에 내장 기능이 먼저 지우지 않게 하기 위해서다.

## 수확 게이트 (memory-tidy 연결)

대화 기록에는 response나 메모리에 아직 옮기지 않은 사용자 교정이 남아 있을 수 있다. 그래서 대화 기록은 memory-tidy가 마지막으로 수확한 날짜(`~/.agents/state/memory-tidy_last_harvest`) 이전 것만 지운다. 파일이 없으면 대화 기록은 하나도 지우지 않고, `note:`로 memory-tidy를 먼저 돌리라고 안내한다. 메모리 파일은 개수만 보고하고 정리는 memory-tidy로 넘긴다.

## 프로젝트 설정 `<프로젝트>/.agents/gc.toml`

없으면 기본값으로 동작한다. 모르는 키가 있으면 스크립트가 멈춘다(오타로 `keep`이 빠진 채 지우는 사고 방지).

```toml
retention_days = 30                 # 기본 보존 기간
keep = ["_keep/**"]                 # .agents/tmp 안에서 보존할 상대경로 패턴
ignore_untracked = ["*.bak"]        # 미추적 후보에서 뺄 파일명 패턴(도구가 만드는 백업 등)

[[extra]]                           # 프로젝트 전용 추가 대상. 프로젝트 루트 안 경로만 허용
path = "log"
glob = "*.log"
days = 7
```

## 안전 장치

- `--apply`는 plan json의 경로를 그대로 믿지 않는다. 각 경로가 자기 분류의 대상 폴더 안에 있는지 다시 확인하고, 밖이면 지우지 않고 실패로 보고한다. 링크는 따라가지 않는다.
- 대상 폴더 자체는 지우지 않는다.
- 빌드 산출물, VCS 추적 파일, 사용자 문서 폴더(Downloads 등)는 대상이 아니다. 필요하면 `[[extra]]`로 명시한다.

## 점검

```bash
python ~/.agents/skills/garbage-collector/scripts/gc_scan.py selftest
```
