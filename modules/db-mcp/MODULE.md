범위: 프로젝트 전용
구성: 규칙, 훅, MCP 등록·싱글톤

# db-mcp

엔진과 무관한 DB MCP 공통 층. 환경 목록·쓰기 승인 정책·훅·싱글톤·mcp.json url 등록을 담당한다. 실제 JDBC/드라이버 연결은 엔진 어댑터 모듈이 한다.

## 사용자 안내

설명: 프로젝트 설정 파일에서 DB 연결을 찾아 표로 보여 준 뒤, 맞는지 확인만 받습니다. 확인된 환경마다 MCP 서버 `db-<환경>`을 만들고, 데이터를 바꾸는 SQL은 채팅에 승인 키워드를 단독 입력했을 때만 허용합니다.

| 역할 | 설정 | 기본 동작 |
|---|---|---|
| session (`session_envs`) | 예: `dev` | 승인 후 `session_ttl_sec` 동안 쓰기 건수 완화 |
| standard | 두 목록에 없는 환경 | 승인 후 `bundle_ttl_sec`·`bundle_max_writes` |
| prod (`prod_envs`) | 예: `kr` | bundle + INSERT/MERGE/CREATE 영구 차단 |

공통 차단: DROP/TRUNCATE, WHERE 없는 UPDATE/DELETE, 다중 문장. SELECT 행 수 제한은 에이전트 원칙(코드 강제 없음).

물어볼 것

1. `[항상]` 프로젝트 datasource·yml·properties·xml에서 찾은 DB 목록(이름·주소·추정 엔진·추정 역할)을 표로 보여 주고: 맞나요?
   - 정하는 것: MCP로 쓸 환경 목록과 session/prod 구분
   - 선택지: 맞음 / 추가·삭제·역할·이름만 고쳐 줌
   - 추천: 스캔 결과. 역할 불명이면 prod
   - 모름/나중에: 스캔 결과 그대로
   - 스캔이 비었을 때만 수동으로 목록을 받는다
2. `[항상]` 위 역할별 쓰기 정책 표를 보여 주고: 이대로 쓸까요?
   - 선택지: 그대로 / 바꿈(키워드·TTL·건수·막을 SQL)
   - 추천·모름: 그대로
3. 어댑터: 감지된 엔진 모듈이 있으면 그 모듈 질문을 이어서 한다. 어댑터가 없으면 DB MCP 파일을 깔되 **runnable 서버·mcp.json DB 항목은 만들지 않는다**.

## 감지 신호

- JDBC URL, 데이터소스 xml/yml/properties, `application*.yml`
- 어댑터 모듈이 따로 엔진을 확정한다

## 원칙

- 설치는 설정 스캔 → 확인만. 빈손 설문으로 DB 목록을 만들지 않는다
- 환경 이름은 영문 소문자·숫자만(`_``-` 없음). MCP 이름 `db-<env>`, 훅 matcher `mcp__db-[^_]+__execute_sql`. `_`가 있으면 훅 검사가 빠질 수 있다
- 쓰기는 승인 키워드 단독 입력. 훅과 어댑터 서버가 `db_sql_policy`로 이중 검사
- SELECT 결과 행 제한은 에이전트가 SQL에 반영(엔진 방언은 어댑터 문서)

## 규칙 작성 항목

| 항목 | 키 |
|---|---|
| 승인·환경 | `[guard.db] approvals`, `session_envs`, `prod_envs`, TTL·건수 |
| MCP·포트 | `daemon/ports.json`의 `db-<env>`, `.agents/mcp.json` url |
| 어댑터 접속 | 어댑터 모듈의 프로필·드라이버 키 |

## 포함 파일

- 훅 `hooks/db_mcp_guard.py`, `db_dml_approve.py`, `db_sql_policy.py`, `hooks.toml`
- 설정 조각 `harness.fragment.toml`
- MCP 공유 `mcp-servers/daemon/` (db-mcp가 켜져 있으면 이 모듈이 소유. 끄고 원격 로그만이면 log-debug가 소유). ftp는 `ports.json` servers에 `script`만 추가(`kind` 없음)

## 설정 키

`[guard.db]`. 비밀·JDBC는 어댑터 모듈.
