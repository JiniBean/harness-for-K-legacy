범위: 프로젝트 전용
구성: 스킬, 도구

# issue-flow

이슈 관리 도구의 티켓으로 작업을 시작해 계획·구현·검증까지 잇는 기능.

## 사용자 안내

설명: 이슈 관리 도구(Jira·GitHub Issues)에서 내게 배정된 티켓 목록을 보여 주거나, 도구가 없으면 채팅에 붙여넣은 요청 내용(엑셀·메일 내용 포함)에서 작업을 시작합니다. 요청 분석 → 작업 계획 파일 → 구현 → 검사 순서로 진행하고, 티켓에 값을 적거나 상태를 바꾸는 일은 사용자가 확인한 뒤에만 합니다.

물어볼 것

1. `[못 찾을 때]` (커밋 메시지·브랜치 이름의 티켓 번호 형식과 연결된 이슈 관리 MCP로 도구를 하나로 정하지 못할 때만) 작업 요청을 어디서 받나요?
   - 정하는 것: 설치할 파일과 티켓 조회 방법(아래 설치 변형 표)
   - 선택지: Jira / GitHub Issues / 도구 없음 / 쓰지 않음
     - 도구 없음: issue-flow 기능을 설치한다. 이슈 관리 도구 없이 엑셀·메일·메신저의 요청 내용을 채팅에 붙여넣어 작업을 시작한다
     - 쓰지 않음: issue-flow 기능을 설치하지 않는다(이 기능의 파일·설정 키를 만들지 않음)
   - 추천: 찾은 티켓 번호 형식에 맞는 도구
   - 모름/나중에: 도구 없음으로 설치. 나중에 도구를 정하면 다시 설치한다
   - 사용자가 "끔", "안 씀"처럼 답하면 쓰지 않음으로 본다. "없어", "도구 없어"처럼 답하면 도구 없음으로 본다
   - set-up-harness는 답을 받은 뒤 고른 뜻을 한 줄로 되돌려 말한다. 예: "도구 없음 — issue-flow 기능을 설치하고, 요청은 채팅에 붙여넣는 방식으로 씁니다" / "쓰지 않음 — issue-flow 기능을 설치하지 않습니다"
2. `[처음 쓸 때]` (Jira·GitHub Issues) 작업을 시작할 때 티켓에 적을 칸과 바꿀 상태
   - 정하는 것: 착수 때 자동으로 채울 칸(`[tracker.fields]`, issue-flow 문서 §착수 필드·§필드 옵션)과 상태 전환(issue-flow 문서 §상태 전환)
   - 설치 때: 묻지 않고 issue-flow 문서의 그 절을 `미정`으로 둔다. 처음 티켓으로 작업을 시작할 때 issue-flow 스킬이 도구에서 필드·상태 목록을 조회해 보여 주고 고르게 한 뒤 적는다
   - 추천: 팀이 착수 때 늘 채우는 칸만
3. `[처음 쓸 때]` (Jira) 첨부 내려받기용 토큰 파일 위치(`[paths] jira_token_file`)
   - 설치 때: 묻지 않고 비워 둔다. 처음 첨부가 있는 티켓으로 작업을 시작할 때 issue-flow 스킬이 내려받기를 쓸지와 토큰 파일 위치를 묻고 적는다. 토큰은 에이전트에게 보여 주지 않고 사용자가 그 파일(1행 이메일, 2행 토큰)에 직접 적는다

묻지 않고 정하는 것

- (Jira) 티켓 번호 앞의 영문 접두: 커밋 메시지·브랜치 이름에서 찾은 접두. 못 찾으면 Atlassian MCP로 내 담당 티켓의 키에서 확인한다. 그래도 없으면 비워 두고, 사용자가 숫자만 입력할 때 묻는다

## 감지 신호

- 사용자가 쓰는 이슈 관리 도구: Jira / GitHub Issues / 없음(요청을 붙여넣음)
- 커밋 메시지·브랜치 이름의 티켓 키 형식 (`ABC-1234`, `#123` 형태)
- 이슈 관리 MCP 연결 여부 (Atlassian, GitHub)

## 흐름 골격

```text
1. 감지: 내 담당 티켓 목록 → 사용자가 하나 고름 (도구가 없으면 요청 붙여넣기)
2. 요청 분석: 본문, 첨부(xlsx 텍스트 상자 등), 관련 화면·코드
3. 계획 파일 작성 → reviewbot 검토 (분기·범위가 작으면 생략)
4. 구현
5. 검증: verify (정적) → 필요하면 test (실행)
6. 후속 제안: 배포 등 프로젝트 단계 (프로젝트 스킬이 있을 때)
```

## 원칙

- 티켓 키·필드 ID를 지어내지 않는다. 필드 ID는 `[tracker.fields]`에서 읽는다
- 이슈에 쓰기(필드 기입·상태 전환) 전에 사용자 확인을 받는다
- 첨부는 `.agents/tmp/`로 받는다
- 계획 파일은 `.agents/plans/{티켓 키}.plan.md`

## 설치 변형 (사용자 안내 1의 답으로 고름)

쓰지 않음이면 이 기능 전체를 설치하지 않는다. 아래는 Jira / GitHub Issues / 도구 없음일 때.

스킬 본문(`SKILL.md`, `references/`)의 도구 하나에만 맞는 부분에는 표식 `(Jira)`, `(GitHub)`, `(Jira·GitHub)`(이슈 관리 도구가 있을 때), `(도구 없음)`이 붙어 있다. 표식이 없는 부분은 모든 변형에 남긴다. 붙는 자리: 제목 끝(다음 같은·상위 제목 전까지), 표 행의 첫 칸 끝(첫 칸이 표식뿐일 수도 있음), 목록 항목 맨 앞(들여쓴 하위 항목 포함). 코드 블록 안의 `#` 줄은 제목이 아니다.

| 고른 도구 | 지울 표식 |
|---|---|
| Jira | `(GitHub)`, `(도구 없음)` |
| GitHub Issues | `(Jira)`, `(도구 없음)` |
| 도구 없음 | `(Jira)`, `(GitHub)`, `(Jira·GitHub)` |

표식으로 지우는 Jira 전용 부분(도구 없음·GitHub Issues에서 지워지는지 설치 뒤 확인하는 기준):

- `SKILL.md`: 「턴 분리」 표의 `aggregate_assigned.py` 행, 「처음 쓸 때 확인」 「첨부 토큰 파일」, 「승인 게이트」의 Jira 도구 이름, 「범위 외」의 첨부 REST 예외
- `references/tracker.md`: 「도구 선택」 Jira 행, 「Atlassian MCP 호출」 절 전체(JQL의 `<KEY>` 포함)
- `references/workflow.md`: 「단계별 호출 (Jira)」, 「1단계 — 내 담당 조회」, 「2단계 — 집계」, 「기입 payload」, 4단계의 `getJiraIssue` 항목
- `references/response-format.md`: §1 `aggregate_assigned.py` 행 순서 항목, §실행결과 「첨부 토큰 없음」
- `references/examples.md`: 「첨부 — 토큰은 파일만」, 「집계 호출」

| 항목 | Jira | GitHub Issues | 도구 없음 |
|---|---|---|---|
| `SKILL.md`, `references/` 전부 | 설치 | 설치 | 설치 |
| `scripts/xlsx_attach_dump.py` | 설치 | 설치 | 설치 |
| `scripts/aggregate_assigned.py`, `scripts/download_attachments.py` | 설치 | 설치 안 함(Jira 응답 형식 전용) | 설치 안 함 |
| `<KEY>` 바꾸기 (`SKILL.md` 설명·트리거 표, `references/`의 response-format·tracker·workflow·examples 중 표식으로 지우고 남은 곳) | Jira 프로젝트 키 접두(대문자). 접두가 여럿이면 issue-flow 문서 §키 형식의 기본 접두 | `<KEY>-`를 `#`으로(`#{n}`) | `<KEY>-`를 지워 숫자만 남김 |
| 뺄 트리거 (`SKILL.md` 설명) | 없음 | `지라`, `지라 확인` | `지라`, `지라 확인`, `티켓 목록`, `내 티켓`, 「목록 다음 채팅의 … 또는 숫자」 문구 |
| 뺄 트리거 (`SKILL.md` 트리거 표 키워드 행) | 없음 | `지라`, `지라 확인` | `지라`, `지라 확인`, `티켓 목록`, `내 티켓` |
| 설정 키 | `[tracker]`, `[tracker.fields]`, `[paths] jira_token_file` | `[tracker]`, `[tracker.fields]`(라벨·필드 대응이 있을 때). `jira_token_file` 만들지 않음 | 만들지 않음(`[tracker]`·`[tracker.fields]`·`[paths] jira_token_file` 모두) |
| 프로젝트 issue-flow 문서 절 | 전부 | 전부(JQL 대신 GitHub 검색 조건) | 「도구」「대상 확정」「계획 추가 항목」「검증 후 단계」만 |

설치 뒤 `.agents/skills/issue-flow/`에서 Grep으로 확인한다.

- `<KEY>`가 0개
- 지울 표식(위 표)이 0개
- 도구 없음·GitHub Issues: `aggregate_assigned`·`download_attachments`·`jira_token_file`이 0개. Jira 도구 이름(`JiraIssue`)이 0개

## 규칙 작성 항목 (set-up-harness가 묻거나 조회해서 채움)

| 항목 | 키 / 위치 |
|---|---|
| 도구·사이트 | `[tracker] site`, `cloud_id` |
| 티켓 키 형식 | 스킬 본문의 `<KEY>` (위 설치 변형 표) |
| 내 담당 조회 조건 | 프로젝트 issue-flow 문서 (JQL 등) |
| 필드 대응 | `[tracker.fields]` 이름 → ID (처음 착수 때 issue-flow 스킬이 사용자가 고른 칸으로 채움. 사용자 안내 2) |
| 필드 옵션 ID | 프로젝트 issue-flow 문서 |
| 상태 이름과 전환 | 프로젝트 issue-flow 문서 |
| 착수 시 기입할 필드 | 설치 때 `미정`. 처음 착수 때 사용자 (사용자 안내 2) |

## 포함 파일

- 스킬 `skills/issue-flow/SKILL.md`, `references/`(tracker·workflow·plan-format·response-format·examples)
- 스크립트 `skills/issue-flow/scripts/`: `xlsx_attach_dump.py`(xlsx 첨부 전체 출력), `download_attachments.py`(Jira 첨부 내려받기), `aggregate_assigned.py`(내 담당 집계). 도구별 설치 여부는 설치 변형 표
- 프로젝트 issue-flow 문서 템플릿 `project-doc-template.md` (set-up-harness가 `.agents/docs/issue-flow.md` 작성 시 사용)

## 설정 키

`[tracker]`, `[tracker.fields]`, `[paths] jira_token_file`(사용자가 관리하는 토큰 파일). 도구별 사용 여부는 설치 변형 표
