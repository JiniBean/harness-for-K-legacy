# MCP 공유 서버 (singleton)

DB MCP(`db-<env>`)와 ftp(`<프로젝트>-ftp`)를 세션마다 stdio로 띄우지 않고, 내 PC에 서버별 프로세스 1개씩만 띄워 Claude Code·Cursor·Codex가 `url`로 같이 쓴다.

## 구성

```text
.agents/mcp-servers/singleton/
├─ daemon.py              start|status|stop|restart [--only <이름>]
├─ ports.json             set-up-harness가 ports.example.json으로 만든다
├─ ports.example.json
├─ cleanup_stdio_dupes.py
├─ smoke_http.py
└─ state/
```

소유: **db-mcp**를 켰으면 이 모듈의 singleton만 설치. db-mcp 없이 원격 로그만이면 log-debug singleton. `kind` 필드 없음 — ftp는 `servers`에 `script`만 추가.

## ports.json

| 키 | 값 |
|---|---|
| `bind` | `127.0.0.1` 고정 |
| `python` | 서버 의존성을 설치한 Python 절대경로 |
| `servers.<이름>` | `mcp.json`과 동일. DB는 `db-<env>`, ftp는 `[guard.ftp] server_name` |
| `port` | 서버마다 다른 포트(예: 18761부터) |
| `script` | 이 폴더 기준. DB 어댑터 `../<adapter>/launch_<env>.py`, ftp `../ftp/server.py` |
| `wait_sec` | 기동 대기(기본 15). JVM 어댑터는 45 |
| `disabled` | `true`면 start 생략 |

서버는 `GSABIS_MCP_HOST`·`GSABIS_MCP_PORT`·`GSABIS_MCP_TRANSPORT=streamable-http`를 받아 HTTP로 연다. 없으면 stdio.

## MCP 등록

```json
{
  "mcpServers": {
    "db-dev": { "type": "http", "url": "http://127.0.0.1:18761/mcp" },
    "<프로젝트>-ftp": { "type": "http", "url": "http://127.0.0.1:18763/mcp" }
  }
}
```

db-mcp 훅은 Cursor url 요청을 `ports.json` 포트로 `db-<env>`에 연결한다.

## 쓰는 법

```text
python .agents/mcp-servers/singleton/daemon.py start
python .agents/mcp-servers/singleton/daemon.py status
python .agents/mcp-servers/singleton/daemon.py stop
python .agents/mcp-servers/singleton/smoke_http.py http://127.0.0.1:18761/mcp
```

로그온 자동 시작은 선택(시작프로그램 `.lnk` → pythonw + `daemon.py start`). JVM 어댑터는 로그온 직후 최대 45초 걸릴 수 있다.
