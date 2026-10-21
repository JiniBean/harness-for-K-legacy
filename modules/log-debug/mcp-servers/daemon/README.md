# MCP 공유 서버 (daemon)

FTP 로그 MCP 서버(`<프로젝트>-ftp`)를 세션마다 stdio로 띄우지 않고, 내 PC에 프로세스 1개만 띄워 Claude Code·Cursor·Codex가 `url`로 같이 쓴다.

- stdio 방식: 세션 N개만큼 Python 프로세스가 생김
- 공유 방식: 서버당 1개. 세션 수와 무관

## 구성

```text
.agents/mcp-servers/daemon/
├─ daemon.py              start|status|stop|restart [--only <이름>]
├─ ports.json             set-up-harness가 ports.example.json으로 만든다 (프로젝트 값)
├─ ports.example.json     형식 예시
├─ cleanup_stdio_dupes.py stdio 시절 남은 서버 프로세스 정리 (--dry-run 먼저)
├─ smoke_http.py          두 클라이언트가 같은 서버를 공유하는지 확인
└─ state/                 pid, 서버별 로그, last_cmd.json (VCS 제외)
```

이 폴더는 원격 로그(FTP)를 켰을 때만 설치한다. 다른 기능이 같은 `daemon/` 폴더를 설치하면(그 기능 MODULE.md에 적혀 있음) 그쪽 하나만 설치하고 FTP 서버를 그 `ports.json`에 더한다. `daemon.py`·`cleanup_stdio_dupes.py`·`smoke_http.py`는 같은 파일이다.

## ports.json

| 키 | 값 |
|---|---|
| `bind` | `127.0.0.1` 고정. 다른 주소로 열지 않는다 |
| `python` | `ftp/requirements.txt`를 설치한 Python 절대경로 |
| `servers.<이름>` | MCP 서버 이름. `mcp.json` 이름, `[guard.ftp] server_name`과 같게 쓴다 |
| `port` | 서버마다 다른 포트. 예시는 18761부터 |
| `script` | 이 폴더 기준 서버 실행 파일. `../ftp/server.py` |
| `wait_sec` | 기동 대기 초(기본 15) |
| `disabled` | `true`면 `start`가 띄우지 않음(로그온 자동 시작 포함) |

서버는 `HARNESS_MCP_HOST`·`HARNESS_MCP_PORT`·`HARNESS_MCP_TRANSPORT=streamable-http`를 받아 `http://<bind>:<port>/mcp`로 연다. 이 환경변수가 없으면 예전처럼 stdio로 동작한다.

## MCP 등록 (url 방식)

`.agents/mcp.json`(정본)에 `ports.json`의 포트로 적는다. 기존 stdio 항목은 `.agents/mcp.stdio.json`에 옮겨 둔다(되돌릴 때 복사).

```json
{
  "mcpServers": {
    "<프로젝트>-ftp": { "type": "http", "url": "http://127.0.0.1:18761/mcp" }
  }
}
```

- 포트를 바꾸면 `ports.json`과 `mcp.json`을 같이 고친다
- Codex: `install.py project`가 `url` 항목을 `config.toml`로 옮긴다

## 쓰는 법

```text
python .agents/mcp-servers/daemon/daemon.py start     # 꺼진 서버만 띄움
python .agents/mcp-servers/daemon/daemon.py status    # running = 포트가 열려 있음
python .agents/mcp-servers/daemon/daemon.py stop
python .agents/mcp-servers/daemon/smoke_http.py http://127.0.0.1:18761/mcp
```

- `status`의 `stale_pid`: 프로세스는 살아 있지만 포트가 닫힌 서버. `start`가 그 프로세스를 끝내고 다시 띄운다. 실행 명령에 그 서버의 `script` 경로가 있는 프로세스만 끝낸다
- 결과는 콘솔과 `state/last_cmd.json`에 같이 남는다. 서버별 출력은 `state/<이름>.log`
- 서버를 끄려면 `ports.json`에서 `"disabled": true` 후 `stop --only <이름>`. Cursor MCP 토글은 연결만 끊고 서버는 남는다

## 로그온 자동 시작 (선택, 사용자가 직접)

데몬은 재부팅 후 저절로 뜨지 않는다. 꺼진 상태로 세션을 열면 이 MCP가 연결 실패한다. 자동으로 띄우려면 시작프로그램 폴더에 바로가기를 만든다(관리자 권한 불필요).

- 위치: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\<프로젝트>_MCP.lnk`
- 대상: `<venv>\Scripts\pythonw.exe` (콘솔 없음), 인수: `"<프로젝트>\.agents\mcp-servers\daemon\daemon.py" start`, 시작 위치: daemon 폴더
- 작업 스케줄러 로그온 트리거(`schtasks /SC ONLOGON`)는 관리자 권한이 필요하다
- pythonw로 실행한 결과는 `state/last_cmd.json`에서 확인한다
- 데몬보다 먼저 연 세션은 연결 실패로 보이므로 Claude Code `/mcp`, Cursor MCP 화면 토글로 다시 연결한다

## 점검

1. `daemon.py status` → 켠 서버가 모두 `running: true`
2. `smoke_http.py <url>` → `shared_ok: true`, `distinct_sessions: true`
3. 세션을 둘 열어도 서버 Python 프로세스 수가 늘지 않음(리스너 + venv 부모, 서버당 2개)
