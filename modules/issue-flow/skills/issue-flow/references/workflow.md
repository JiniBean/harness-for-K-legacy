# 티켓 확인 워크플로 (issue-flow)

값 표기 `{…}`·`[tracker.fields] …`는 `.agents/harness.toml`의 같은 키를 Read해서 쓴다.

도구별 호출은 [tracker.md](tracker.md), 조회 조건·옵션 ID·상태 이름은 프로젝트 issue-flow 문서(`.agents/docs/issue-flow.md`)를 쓴다. 제목·표 행·목록 항목의 괄호 속 도구 이름은 SKILL.md 「도구별 표식」.

§1~§2(또는 §4) 채팅 출력 후 그 턴에서 도구를 더 호출하지 않고 종료한다. 선택은 다음 메시지의 키 / 순수숫자 / 칸 토큰 / 「진행」만.

## 흐름 (Jira·GitHub)

단계별 실제 호출은 아래 「단계별 호출」 표.

```text
1. 내 담당 조회 — 프로젝트 문서 §내 담당 조회 조건 (+ 페이지 반복)
2. 집계 → 상태별 건수 + 착수 후보 목록
3. response-format §1~§2 채팅 출력 → 턴 종료
4. 다음 메시지에서 키 또는 순수숫자 수신 (채팅에 키가 이미 있으면 1~3 생략)
5. 선택 티켓 + 착수 필드 조회
   └─ 없는 키 → 키 질문, 종료
6. response-format §4 — 물을 칸만 번호 목록. 물을 칸 0이면 §5만 → 턴 종료
7. 다음 메시지: 물을 칸 개수만큼 토큰, 또는 (물을 칸 0일 때만) 「진행」
   └─ 번호 밖 / 칸이 남았는데 「진행」 → 그 칸만 다시 안내. 기입·전환 없음
8. 토큰이면 착수 필드 기입. 「진행」만이면 기입 생략
9. 첨부 내려받기 → .agents/tmp
   └─ 받을 수 없음 → 전환은 계속, §실행결과 첨부 보류
10. 허용된 전환 조회 → 이름 매칭 → 전환 (id만)
11. 재조회 → response-format §실행결과
12. 계획 단계 진입 → §착수분석 → 계획 산출 → SKILL 파이프 A
```

## 흐름 (도구 없음)

```text
1. 트리거 직후 요청 붙여넣기 안내 (tracker.md 「요청 붙여넣기」) → 턴 종료
2. 붙여넣은 요청(제목·본문·첨부 경로) 수신
3. 계획 단계 진입 → §착수분석 → 계획 산출 → SKILL 파이프 A
```

## 단계별 호출 (Jira)

| 단계 | 호출 |
|------|------|
| 1 | `searchJiraIssuesUsingJql` (아래 「1단계 — 내 담당 조회」) |
| 2 | `python .agents/skills/issue-flow/scripts/aggregate_assigned.py <MCP-JSON 경로> [옵션]` (아래 「2단계 — 집계」) |
| 5 | `getJiraIssue`. 404면 없는 키 |
| 8 | `editJiraIssue` (아래 「기입 payload」) |
| 9 | `python .agents/skills/issue-flow/scripts/download_attachments.py <KEY>-{n}`. exit 2(토큰 없음)면 받을 수 없음 |
| 10 | `getTransitionsForJiraIssue` → `transitionJiraIssue` |
| 11 | `getJiraIssue` |

## 단계별 호출 (GitHub)

[tracker.md](tracker.md) 「GitHub MCP 호출」 표를 따른다. 2단계는 집계 스크립트 없이 MCP 응답을 §1~§2 표로 옮긴다.

## 1단계 — 내 담당 조회 (Jira)

```text
searchJiraIssuesUsingJql({
  cloudId,
  jql: <프로젝트 문서 §내 담당 조회>,
  maxResults: 100,
  fields: [tracker.md § search/get fields]
})
```

- 응답에 `nextPageToken`이 있으면 같은 JQL·fields로 반복
- 큰 응답은 MCP가 파일로 저장한다. 그 경로를 2단계에 넘긴다

## 2단계 — 집계 (Jira)

고정 스크립트만 쓴다.

```text
python .agents/skills/issue-flow/scripts/aggregate_assigned.py <json 경로> \
  --start-status "<착수 상태>" --status-order "<상태1>,<상태2>,..." --sort-field <필드 이름>
```

| 옵션 | 값 출처 | 생략 시 |
|------|---------|---------|
| `--start-status` | 프로젝트 문서 §상태 전환의 착수 전 상태 | 모든 티켓이 후보 |
| `--status-order` | 프로젝트 문서 §상태 이름(워크플로 순) | 상태 이름순 |
| `--sort-field` | `[tracker.fields]`의 이름(예: 예정일 필드) 또는 필드 ID | `duedate` → 키 순 |

- stdout `---STATUS---` → §1 표, `---REVIEW---` → §2 표
- 금지: 셸 `python -c`로 집계·정렬(PowerShell이 `{...}`를 파싱함), 훅 state 폴더에 임시 `.py` 작성

## §2 정렬 (Jira·GitHub)

| 순위 | 기준 | 규칙 |
|------|------|------|
| 1 | 정렬 필드 (프로젝트 문서 §정렬 필드) | 오름차순, 빈 값 맨 뒤 |
| 2 | 기한 | 오름차순, 빈 값 맨 뒤 |
| 3 | 키 | 오름차순 (타이브레이크) |

## 3단계 — 티켓 선택 (Jira·GitHub)

- 다음 메시지의 키 또는 순수숫자를 키로 정규화(tracker.md 「키 정규화」). 후보 목록에 있으면 4단계
- 첫 메시지에 키가 이미 있으면 목록 단계 생략
- 후보 0건 → §1만 출력 후 종료(전환 없음)
- 후보 목록에 없는 키 → 현재 상태를 보여 주고 계속할지 묻는다

## 4단계 — 착수 필드 안내 (Jira·GitHub)

- (Jira) `getJiraIssue({ cloudId, issueIdOrKey, fields: [tracker.md § search/get fields] })`
- 현재 값 한 줄. 값이 있는 칸은 목록을 내지 않는다
- 물을 칸 = 빈 칸 + 프로젝트 문서 §착수 필드의 「재질문 조건」에 걸린 칸
- 옵션 목록 순서·표시명은 프로젝트 문서 §필드 옵션. 채팅에 옵션 ID를 쓰지 않는다
- 날짜 칸 보기가 문서에 정의돼 있으면(예: 진행 중 티켓의 예정일 중 이번 달~다다음 달) 그 방법으로 후보 날짜를 만든다. 정의가 없으면 `MMDD` 입력만 받는다
- 물을 칸 0개 → 목록 없이 §5만

턴 종료.

### 답 파싱 (다음 메시지)

순서는 프로젝트 문서 §착수 필드에 적힌 순서(물을 칸만).

- 물을 칸 0개 + 「진행」 → 기입 없이 5단계
- 물을 칸 N개 → 토큰 N개. 유지하려면 `-`
- 칸 전체 개수만큼 토큰 → 전체 덮어쓰기
- 날짜 토큰: 목록 번호 또는 `MMDD`. `MMDD` → 올해 `YYYY-MM-DD`, 오늘보다 이전이면 다음 해
- 번호가 목록 밖이면 그 칸만 다시 안내. 기입·전환 없음

## 5단계 — 기입·상태 전환 (Jira·GitHub)

승인 후에만.

- `-`인 칸은 payload에서 뺀다. §착수 필드 밖의 필드는 쓰지 않는다
- 이어서 첨부 내려받기(tracker.md 도구별 절), 받은 `.xlsx`는 `xlsx_attach_dump.py`로 읽는다
- 전환: tracker.md 도구별 절의 상태 전환. transition 이름은 프로젝트 문서 §상태 전환
  - 이름이 없으면 §실행결과 보류(transition unavailable) + 사용 가능한 transition 이름 나열
- 재조회 → 상태 이름이 문서의 착수 후 상태이면 §실행결과 완료

### 기입 payload (Jira)

```text
editJiraIssue({
  cloudId,
  issueIdOrKey,
  fields: {
    {tracker.fields.<select 필드>}: { id: "<프로젝트 문서의 option id>" },
    {tracker.fields.<date 필드>}: "YYYY-MM-DD"
  }
})
```

## 계획 산출

계획 단계에 들어가면 Cursor는 `SwitchMode(plan)`. Claude Code는 모드 전환 없이 소스 수정 없이 분석만 한다.

| 하네스 | 방법 |
|--------|------|
| `CreatePlan` 있음 (Cursor) | `CreatePlan(name: "{티켓 키} {짧은 제목}")` → `~/.cursor/plans` |
| `CreatePlan` 없음 (Claude Code) | `.agents/plans/{티켓 키}.plan.md`를 Write |

- 티켓 키가 없으면(요청을 붙여넣은 경우) `YYYYMMDD_{짧은 제목}`을 키 자리에 쓴다
- 쓰기 전 `.agents/plans/`와 `~/.cursor/plans/`에서 `{티켓 키}*.plan.md`를 대소문자 무시로 찾는다. 있으면 그 파일을 갱신한다
- 형식은 [plan-format.md](plan-format.md)
- `## 구현 상세` 첫 줄 `수정 파일: {경로}, {경로}`. `/verify` C_SCOPE가 이 줄을 diff와 대조한다
- 다음 줄 `파급: {같이 영향받는 화면·테이블}`. 없으면 `없음` + 근거 한 줄. 「손대지 않음」은 안 고칠 파일, 「파급」은 안 고쳐도 영향받는 대상
- `## 리뷰`에는 파이프 A 결과
- todo 상태가 바뀌면 프런트매터 `todos[].status`도 갱신(Cursor는 네이티브가 처리)
- 계획 파일을 쓴 직후 경로를 채팅에 출력한다. 소스 패치는 사용자 승인 후

## §착수분석

계획 단계에서만. 산출은 [계획 산출](#계획-산출).

0. 대상 확정: 티켓(또는 붙여넣은 요청)의 화면·메뉴·URL·API 이름으로 수정 대상 파일을 하나로 좁힌다. 프로젝트에 메뉴·화면 대응 문서가 있으면(프로젝트 문서 §대상 확정) 그 절차를 따른다. 확정 못 하면 response-format §대상미확정만 출력하고 심층 분석·계획 본문을 쓰지 않는다
1. 확정된 파일 + 첨부를 읽는다. xlsx 셀이 비면 텍스트 상자·이미지(`--media-out`)를 본다
2. 제목·캡처로 교차검증. 확정 파일과 명백히 다르면 확정을 풀고 §대상미확정
3. 티켓의 메뉴명·화면명은 힌트. 코드·DB의 실제 대응이 우선
4. 화면에서 서버·쿼리까지 호출 경로를 따라간다. 분석 서브에이전트가 있으면 SKILL 「서브에이전트 호출 한도」로 1회씩 맡긴다
5. 스펙 키워드가 있는 컴포넌트·함수만 적는다
6. 구현 계획을 `## 구현 상세`에 넣는다. 같은 성격의 기존 항목 등장 위치(여러 함수·분기·콜백)를 전부 찾아 새 항목이 들어갈 위치를 빠짐없이 적는다. 이 목록은 파이프 A/B의 reviewbot 입력으로 재사용한다. 항목마다 파일, 위치(함수·이벤트·쿼리 id), 변경 내용. 소스 패치·신규 쿼리 본문은 넣지 않는다
7. 파급: 내가 고치지 않는데 영향을 받는 대상. 같은 쿼리·테이블·공통 함수·임베드 화면을 쓰는 다른 화면에서 걸린다. 없으면 `없음` + 무엇을 보고 판단했는지 한 줄

계획 파일을 다 쓰면 SKILL 파이프 A. todo·`/verify`·reviewbot mode=diff·후속 제안은 SKILL 파이프 B.

## 분기 요약

| 조건 | 동작 |
|------|------|
| 담당 0건 (Jira·GitHub) | §1(합계 0) 후 종료 |
| 착수 후보 0건 (Jira·GitHub) | §1 후 「작업 시작 후보 없음」 안내, 종료 |
| §4 번호 밖 / 칸이 남았는데 진행 (Jira·GitHub) | 그 칸만 재안내, 기입·전환 없음 |
| 사용자 취소·미승인 (Jira·GitHub) | §실행결과 보류 (사용자 취소) |
| transition 이름 미발견 (Jira·GitHub) | §실행결과 보류 + 사용 가능한 transition 목록 |
| 없는 키 (Jira·GitHub) | 키 질문, 종료 |
| 프로젝트 issue-flow 문서 없음 | 문서 없음 보고 + set-up-harness 또는 값 입력 요청, 종료 |
