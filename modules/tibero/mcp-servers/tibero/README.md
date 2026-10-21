# Tibero MCP 실행기

에이전트가 Tibero DB에 SQL을 실행하는 로컬 MCP 어댑터. 환경마다 프로세스 하나. MCP 서버 이름은 공통 층 기준 `db-<env>`(스크립트만 이 폴더의 `launch_<env>.py`).

## 구성

```text
.agents/mcp-servers/tibero/
├─ launch_common.py       공통 실행기 (설정·비밀 읽기, JDK 선택, JVM 시작, 서버 실행)
├─ launch_<env>.py        환경마다 1개 (아래 2줄. set-up-harness가 만든다)
├─ tibero-mcp-server/     MCP 서버 본체 (수정판, 아래 「서버 본체」)
│  ├─ LICENSE             원본 MIT 라이선스
│  └─ src/tibero_mcp_server/{__init__.py, server.py}
├─ requirements.txt       mcp 1.x, jpype1, jaydebeapi
└─ tibero.env.example     비밀 파일 키 목록
```

## 서버 본체

- 출처: GitHub `YeomYuJun/tibero-mcp-server` 커밋 `696e65a`, MIT (Copyright (c) 2025 YeomYuJun). 원본 LICENSE를 `tibero-mcp-server/LICENSE`에 그대로 둠
- 수정판이다. 원본은 받은 SQL을 정책 없이 실행한다

| 항목 | 원본 | 수정판 |
|---|---|---|
| 쓰기 정책 | 없음 | 훅과 같은 정책 파일(`.agents/hooks/db_sql_policy.py`)로 서버에서 2차 검사 |
| 환경 구분 | 없음 | `TIBERO_MCP_PROFILE`(실행기가 `launch_<env>`의 env로 설정) |
| 승인 | 없음 | 승인 상태 확인, 묶음 모드 건수 차감 |
| 감사 로그 | 없음 | `.agents/hooks/state/dml_audit.log`에 실행·거부 기록 |
| 트랜잭션 | 실행 후 커밋 | 실행 후 커밋, 마지막에 항상 rollback·close |
| `get_table_info` | 컬럼·제약조건·인덱스 | 컬럼만 (토큰 절감) |

- 정책 파일 위치: `server.py` 기준 `parents[5]/hooks`. 설치 경로(`.agents/mcp-servers/tibero/tibero-mcp-server/src/tibero_mcp_server/`)를 바꾸지 않는다
- 제약조건·인덱스가 필요하면 `execute_sql`로 `USER_CONSTRAINTS`·`USER_CONS_COLUMNS`·`USER_INDEXES`·`USER_IND_COLUMNS`를 SELECT한다

| 항목 | 내용 |
|---|---|
| 진입점 | `tibero_mcp_server.server.main` (async) |
| 접속 정보 | 환경변수 `TIBERO_HOST`·`TIBERO_PORT`·`TIBERO_SID`·`TIBERO_USER`·`TIBERO_PASSWORD`, JDBC jar는 `CLASSPATH` |
| 도구 | `execute_sql`, `get_table_info` (훅 matcher `mcp__tibero-[^_]+__execute_sql`) |

## 설정

설정 파일: 프로젝트 `.agents/harness.toml`(로더 `~/.agents/scripts/harness_config.py`)

```toml
[tibero]
jdbc_jar = "<프로젝트 기준 상대경로 또는 절대경로>/tibero*-jdbc.jar"

[tibero.profiles.dev]
host = "<호스트>"
port = 8629
sid = "<SID>"

[tibero.profiles.test]
host = "<호스트>"
port = 8629
sid = "<SID>"

[java]
tool_jdk_home = "<64-bit JDK 9+ 경로, 17 권장>"
tool_jdk_fallbacks = []
```

- 환경 키(`dev`, `test` …)는 `[guard.db] approvals`의 키와 같게 쓴다
- 앱 서버용 JDK 1.x(32-bit가 흔함)는 JPype와 맞지 않는다. MCP 전용 64-bit JDK를 `tool_jdk_home`에 둔다. `JAVA_HOME`이 `jdk1.`을 포함하면 `tool_jdk_home`을 우선한다
- 모든 Tibero 호스트를 `[guard] block_hosts`에 넣는다(셸 직접 접속 차단, tibero 기능 `harness.fragment.toml`)

비밀

- 비밀 `tibero` → `<secrets_dir>/<프로젝트 이름>/tibero.env`(기본 `~/.agents/secrets/<프로젝트 이름>/tibero.env`)
- 키는 `tibero.env.example`. 환경별 `TIBERO_USER_<ENV>`·`TIBERO_PASSWORD_<ENV>`가 공통 `TIBERO_USER`·`TIBERO_PASSWORD`보다 우선
- 사용자가 직접 만들고 값을 채운다. 에이전트는 읽거나 쓰지 않는다(훅이 차단)

## 환경별 실행 파일

환경·승인 훅은 **db-mcp**의 `db_mcp_guard.py`가 담당한다(서버 이름 `db-<env>`). Claude/Codex는 `tool_name` `mcp__db-<env>__…`, Cursor는 `mcp_server_name`(`db-<env>` 또는 `project-<n>-<워크스페이스>-db-<env>`), 그다음 url 포트를 `daemon/ports.json`의 `db-*`와 맞춘다. SQL 본문(`tool_input`)은 보지 않는다. 이 어댑터는 환경마다 `launch_<env>.py`를 두어 프로필을 고정한다(인자로 환경만 넘기는 단일 실행기 금지).

`launch_<env>.py` 내용(모든 환경이 같다. 환경은 파일 이름에서 읽는다)

```python
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from launch_common import main; main()
```

set-up-harness는 `[guard.db] approvals`의 키마다 이 파일을 만든다.

## MCP 등록

기본은 url 방식(공유 서버). 절차·`ports.json`은 db-mcp의 `mcp-servers/daemon/README.md`(설치 후 `.agents/mcp-servers/daemon/`).

1. `daemon/ports.json`에 환경마다 `"db-<env>": { "port": <포트>, "script": "../tibero/launch_<env>.py", "wait_sec": 45 }`
2. 프로젝트 `.agents/mcp.json`(정본)에 환경마다 하나

```json
{
  "mcpServers": {
    "db-dev": { "type": "http", "url": "http://127.0.0.1:18761/mcp" }
  }
}
```

3. 같은 서버를 stdio로 적은 항목을 `.agents/mcp.stdio.json`에 남긴다(되돌림용)

```json
{
  "mcpServers": {
    "db-dev": {
      "command": "<venv Python 절대경로>",
      "args": [".agents/mcp-servers/tibero/launch_dev.py"]
    }
  }
}
```

의존성: `<venv Python> -m pip install -r .agents/mcp-servers/tibero/requirements.txt`. `mcp`는 1.x만 쓴다. url 방식에 필요한 `uvicorn`·`starlette`는 `mcp`가 함께 설치한다.

서버 본체는 `HARNESS_MCP_TRANSPORT`가 `streamable-http`(또는 `http`)면 `HARNESS_MCP_HOST`·`HARNESS_MCP_PORT`로 HTTP를 열고, 없으면 stdio로 동작한다. 데몬이 이 값을 넣는다.

## 쓰기 정책

훅·정책은 db-mcp(`db_mcp_guard.py`·`db_dml_approve.py`·`db_sql_policy.py`, `[guard.db]`). 이 서버는 같은 `db_sql_policy`로 2차 강제한다.

- 승인과 무관하게 막힘: DROP/TRUNCATE, 다중문, WHERE 없는 UPDATE/DELETE, WITH로 감싼 DML
- 훅이 없어도 서버 2차 검사는 남는다. 승인어 기록은 `db_dml_approve.py`가 담당

## 활성화

1. 비밀 파일 확인(사용자)
2. `python .agents/mcp-servers/daemon/daemon.py start` → `status`에서 `running: true`
3. MCP Reload(Cursor) 또는 `/mcp`(Claude Code)
4. `db-<env>`에서 `SELECT 1 FROM DUAL`
5. 훅 검사: db-mcp `test_db_mcp_guard.py`, `test_db_dml_policy.py`, `test_dml_prompt.py`
