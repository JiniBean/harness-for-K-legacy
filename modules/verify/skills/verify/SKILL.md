---
name: verify
description: 구현 완료 전 정적 검사(파일 내용만, 실행 없음) — 디버그 코드·diff 범위·줄바꿈, 그리고 켠 기능의 검사(주석·화면 구조·리포트·SQL/fixture 등). FAIL>0이면 완료 선언 금지. 빌드·브라우저 실행 검증은 test. 「검증」만 있고 실행/정적 구분이 없으면 먼저 되묻는다.
---

# verify

값 표기 `{…}`는 `.agents/harness.toml`의 같은 키를 Read해서 쓴다.

구현 산출물이 완료 기준을 충족하는지 검사한다. 앱 소스는 수정하지 않는다.

## 공통 규칙

- 검사만 한다. 업무 소스를 고치지 않는다
- 스캔 대상: `git diff --name-only HEAD` 또는 사용자가 `@`로 지정한 파일
- 기존 파일 줄바꿈을 정규화하지 않는다. HEAD의 `crlf`/`lf`/`mixed`를 유지한다
- FAIL>0이면 완료 선언 금지
- DB를 써야 하는 기능 검사는 그 기능 문서의 DB·승인 규칙을 따른다

## 체크 (공통)

| ID | 방법 | FAIL |
| :--- | :--- | :--- |
| C_DEBUG | 변경 hunk에 `[verify] debug_patterns`의 패턴(예: 콘솔 출력·디버그 호출)이 있는지 | 존재 |
| C_SCOPE | 계획 문서의 「구현 상세」 첫 줄 `수정 파일:` 목록(없으면 「허용 파일」 표) ↔ diff. 계획은 `.agents/plans/`(Cursor는 `~/.cursor/plans/`도). 계획 없으면 SKIP | 이탈·누락 |
| C_EOL | `git ls-files --eol -- <path>`로 index(`i/`) vs worktree(`w/`) 종류 비교. 신규·바이너리 SKIP. `mixed`→`mixed` PASS. FAIL이면 `python .agents/scripts/restore_eol.py <path>`로 줄바꿈만 HEAD 기준으로 복원한 뒤 다시 검사 | `i/`≠`w/` |

`C_EOL`은 `git ls-files --eol`의 `i/`·`w/` 종류가 다를 때만 FAIL. `git diff`의 전체 줄 변경만 보고 추정하지 않는다.

## 체크 (기능)

이 스킬 폴더의 `checks/*.md`(켠 기능이 설치한 검사)를 모두 읽고 함께 돈다. 예: comment-gen 기능 → `C_COMMENT`, mapper 기능 → `C_SQL`. 해당 파일 종류의 변경이 없으면 그 검사는 SKIP.

서브에이전트에 맡기는 검사는 각 `checks/*.md`에 적혀 있다. 최종 `[verify]` 합산은 부모가 하고, 서브에이전트는 자기 검사 줄만 돌려준다.

## 출력 (고정)

```text
[verify] PASS n / FAIL n / SKIP n
PASS · C_DEBUG
PASS · C_SCOPE
FAIL · C_EOL · <파일> i/crlf → w/lf
SKIP · C_SQL · 매퍼 변경 없음
결론: FAIL>0 → 완료 선언 금지
```

각 체크는 `PASS ·` / `FAIL ·` / `SKIP ·` 한 줄. FAIL·SKIP은 짧은 사유를 붙인다.
