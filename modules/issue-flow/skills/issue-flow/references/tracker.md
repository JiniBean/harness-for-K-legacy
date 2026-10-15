# 이슈 관리 도구 설정 (issue-flow)

값 표기 `{…}`·`[tracker.fields] …`는 `.agents/harness.toml`의 같은 키를 Read해서 쓴다.

도구별 호출 방법. 조회 조건(JQL 등)·옵션 ID·상태 이름은 프로젝트 issue-flow 문서(`.agents/docs/issue-flow.md`, set-up-harness가 작성)에 있다.

## 도구 선택

| 도구 | 조회·기입 | 첨부 | 비고 |
|------|-----------|------|------|
| (Jira) | Atlassian MCP | `scripts/download_attachments.py` (REST, 로컬 토큰) | 아래 「Atlassian MCP 호출」 |
| (GitHub) | GitHub MCP (`list_issues`·`issue_read`·`issue_write`) | 본문·댓글의 첨부 URL을 사용자 확인 후 받음 | 아래 「GitHub MCP 호출」 |
| (도구 없음) | 사용자가 요청을 채팅에 붙여넣음 | 사용자가 파일 경로를 줌 | 아래 「요청 붙여넣기」 |

## Atlassian MCP 호출 (Jira)

### 사이트

| 항목 | 값 |
|------|-----|
| Site | `{tracker.site}` |
| cloudId | `{tracker.cloud_id}` (없으면 `{tracker.site}`의 hostname) |
| MCP | Cursor `user-Atlassian-MCP-Server` / Claude Code 플러그인 Atlassian MCP (도구 이름 `mcp__*Atlassian*__*`). 실제 이름은 MCP 목록에서 확인 |

### 키 정규화

| 입력 | 후보 |
|------|------|
| `<KEY>-1234` | 그대로 (대문자) |
| `1234` | 프로젝트 issue-flow 문서 §키 형식의 기본 접두를 붙임. 접두가 여럿이면 묻는다 |
| 조회 404 | 키를 다시 묻는다. 번호 매핑을 추측하지 않는다 |

### JQL

프로젝트 issue-flow 문서 §내 담당 조회의 JQL을 그대로 쓴다. 문서에 없으면 사용자에게 묻는다. 형태 예:

```text
project = <KEY> AND assignee = currentUser() ORDER BY status ASC, updated DESC
```

- `project` + `assignee = currentUser()`로 범위를 묶는다(bounded JQL)
- 상태명에 공백이 있으면 큰따옴표. 상태 ID가 문서에 있으면 ID가 이름보다 안정적

### search/get fields (필수 명시)

MCP `searchJiraIssuesUsingJql` 기본값에 custom field가 빠진다. 항상 `fields`를 넘긴다.

```json
[
  "summary", "status", "reporter", "updated", "duedate",
  "{tracker.fields.<착수 필드 이름>}", "..."
]
```

- 착수 필드 이름 목록은 프로젝트 issue-flow 문서 §착수 필드. 각 ID는 `[tracker.fields] <이름>`
- `reporter.displayName`은 `fields`에 `"reporter"`를 넣어야 응답에 온다

### 필드 값

| 타입 | 읽기 | 기입 |
|------|------|------|
| select | `.value` | `{ "id": "<option id>" }` (옵션 ID는 프로젝트 issue-flow 문서) |
| date | 원문 `YYYY-MM-DD` | `"YYYY-MM-DD"` |
| text | 원문 | 문자열 |

채팅에는 표시명과 번호만 낸다. 옵션 ID는 기입 매핑에만 쓴다.

### 상태 전환

1. `getTransitionsForJiraIssue(issueIdOrKey)` — 현재 상태에서 허용된 transition
2. `name`이 프로젝트 issue-flow 문서 §상태 전환의 transition 이름과 일치하는 항목의 `id` 사용
3. `transitionJiraIssue({ transition: { id } })` — transition id 하드코딩 금지
4. 화면(screen) 필드 없는 전환은 `fields` 없이 id만

### 첨부 다운로드

MCP에 첨부 바이트 도구가 없어 Jira REST `GET /rest/api/3/attachment/content/{id}`를 쓴다.

| 항목 | 값 |
|------|-----|
| 토큰 파일 | `{paths.jira_token_file}` (사용자가 관리) |
| 형식 | 1행 Atlassian 로그인 이메일, 2행 API 토큰. `#` 주석·빈 줄 무시 |
| 저장 위치 | `.agents/tmp/{키}_{원본파일명}` |
| 스크립트 | `python .agents/skills/issue-flow/scripts/download_attachments.py <KEY>-{n}` |
| 발급 | https://id.atlassian.com/manage-profile/security/api-tokens |

- 채팅·문서·git에 토큰을 쓰지 않는다. 에이전트는 토큰 파일을 열지 않고 스크립트만 실행한다
- `{paths.jira_token_file}`이 비어 있으면 실행 전에 SKILL.md 「처음 쓸 때 확인」의 첨부 토큰 파일 단계를 먼저 한다
- exit 2(토큰 파일 없음·형식 오류) → 전환은 계속, §실행결과에 첨부 보류 + 발급 URL 안내
- 받은 `.xlsx`는 `python .agents/skills/issue-flow/scripts/xlsx_attach_dump.py <파일>`로 읽는다. 요청 본문이 셀이 아니라 텍스트 상자·메모에만 있는 경우가 있다

### API 메모

| MCP tool | REST |
|----------|------|
| `searchJiraIssuesUsingJql` | `GET/POST /rest/api/3/search/jql` |
| `getJiraIssue` | `GET /rest/api/3/issue/{key}` |
| `editJiraIssue` | `PUT /rest/api/3/issue/{key}` |
| `getTransitionsForJiraIssue` | `GET /rest/api/3/issue/{key}/transitions` |
| `transitionJiraIssue` | `POST /rest/api/3/issue/{key}/transitions` |

- 검색 페이지네이션: `nextPageToken` (`startAt` 아님). `maxResults` 최대 100. 토큰이 없을 때까지 반복

## GitHub MCP 호출 (GitHub)

| 단계 | 방법 |
|------|------|
| 내 담당 조회 | `list_issues` 또는 `search_issues` (`assignee:@me` + 저장소·라벨 조건은 프로젝트 issue-flow 문서) |
| 키 | `#123` 또는 `owner/repo#123` |
| 상세 | `issue_read` |
| 착수 필드 | 라벨·마일스톤·프로젝트 필드. 대응은 프로젝트 issue-flow 문서 §착수 필드 |
| 상태 전환 | open/closed 또는 라벨 교체. 문서 §상태 전환 |
| 첨부 | 본문·댓글의 `user-attachments` URL. 받기 전 사용자 확인, 저장 위치 `.agents/tmp/` |

집계 스크립트는 쓰지 않는다. MCP 응답을 그대로 §1~§2 표로 옮긴다.

## 요청 붙여넣기 (도구 없음)

- 트리거 직후 목록 단계 대신 「요청 내용(제목·본문·첨부 경로)을 붙여넣어 주세요」를 안내하고 턴 종료
- 키가 없으면 계획 파일 이름은 `YYYYMMDD_{짧은 제목}`
- 착수 필드 기입·상태 전환 단계는 건너뛴다
