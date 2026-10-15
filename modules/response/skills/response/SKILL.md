---
name: response
description: >-
  응답 형식(explain) 규칙 위반을 지적받았을 때 재설명 + learned.md 적재 핸들러.
  규칙 본문은 `AGENTS.md` §3 응답 프로토콜 (explain)에 있다 (이 스킬이 규칙 전체가 아니다).
  일반 설명 요청에는 쓰지 않는다. 아래 지적 트리거에만 쓴다.
  Invoke when the user says 이해가 안돼, 이해가 안, 뭔소리, 뭔소린지,
  이렇게 말해야지, 이렇게 말하면 되잖아, 쉽게 설명해, 다시 설명해,
  장황, or 너만 아는 (about the agent's explanation).
  Also invoke for `learned 반영` / `explain 압축` (compress learned.md into §3).
  Not for CS draft "이렇게 말하면 될까".
---

# response (pushback handler)

이 스킬은 **규칙 위반을 지적받았을 때**와 **learned 압축 요청**에만 돈다. 설명 스타일 규칙 자체는
`AGENTS.md` §3 응답 프로토콜 (explain)에 있고 트리거 없이 항상 적용된다. 전역 설치면 `~/.agents/AGENTS.md`, 프로젝트 설치면 프로젝트 루트 `AGENTS.md`다.

강제 재설명 + (톤 실패 시) `learned.md` 적재. Rule 전문을 여기에 복제하지 않음.

## When

Trigger phrases (developer pushing back on how you explained):

- `이해가 안돼` / `이해가 안`
- `뭔소리` / `뭔소린지`
- `이렇게 말해야지` / `이렇게 말하면 되잖아`
- `쉽게 설명해` / `다시 설명해`
- `장황` / `너만 아는`

Compress triggers:

- `learned 반영` / `explain 압축`

## Procedure

1. Read `AGENTS.md` §3 (it may already be loaded; still re-apply).
2. Discard the prior explanation framing. Re-answer in plain style: lead with ≤3 short sentences (what it means · why you said it · what to do next), then evidence (code/SQL/log) or fact timeline only if needed.
3. Classify the failure:
   - Style/tone (jargon, side plot, contradiction, invented name, over-interpret) → learn
   - Fact-only wrong (`뭔소리` about a wrong claim) → fix the fact, re-explain, **skip** learn
   - Intent correction only (`그게 아니라` without style issue) → restate intent, answer that scope, **skip** learn unless wording also failed
4. If learning: append **one** short DO/DON'T line to `learned.md` in this skill's folder (`<.agents>/skills/response/learned.md`) under `## Entries`. Skip if the same point already exists. Do **not** edit `AGENTS.md` or ask for User Rules re-paste on learn.
5. If you added a line, report in one line: `learned에 추가: …`
6. After append, if `## Entries` bullets exceed ~15 lines, run Compress below in the same turn.

## Compress

When user says `learned 반영` / `explain 압축`, or Entries exceed ~15 lines:

1. Read `learned.md` and §3 DO/DON'T.
2. Fold near-duplicates into 1–3 short DO/DON'T lines; promote those into `AGENTS.md` §3.
3. Remove promoted bullets from `learned.md`. Leave unmerged residuals.
4. Tell the user to re-paste `AGENTS.md` into Cursor User Rules.
5. Report: `explain 압축: 승격 N줄, learned 잔여 M줄`

## Cancel last learn

If the user says `규칙 빼` or `방금 규칙 취소`: remove only the last `learned.md` bullet you added this session, confirm in one line.
