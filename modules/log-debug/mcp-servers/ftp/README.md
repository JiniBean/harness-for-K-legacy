# FTP 로그 MCP (읽기 전용)

에이전트가 원격 WAS 로그를 FTP로 조회하는 로컬 MCP 서버와 로그 요약기. log-debug 스킬 운영 로그 모드와 서브에이전트 `logbot`이 쓴다.

## 구성

```text
.agents/mcp-servers/ftp/
├─ server.py         MCP 서버 (FastMCP, ftplib)
├─ log_digest.py     로그 요약기 (표준 라이브러리만)
├─ smoke_test.py     서버 직접 호출 스모크
└─ requirements.txt  mcp 1.x
```

설치 위치는 프로젝트 `.agents/mcp-servers/ftp/`. 두 스크립트 모두 자기 위치에서 위로 올라가 `.agents` 폴더를 찾아 프로젝트 루트를 정한다.

## 설정

설정 파일: 프로젝트 `.agents/harness.toml`(로더 `~/.agents/scripts/harness_config.py`)

```toml
[guard]
ftp_hosts = ["<호스트>"]          # 셸에서 직접 접속 차단 (shell_guard)

[guard.ftp]
server_name = "<프로젝트>-ftp"    # MCP 서버 이름. ftp_mcp_guard 훅도 이 이름을 본다

[ftp]
port_default = 21

[[ftp.servers]]
alias = "<별칭>"                  # 도구 인자 server 값
host = "<호스트>"
port = 21                         # 생략 시 port_default
region = "<지역·용도 메모>"
log_cwd_current = "/<당일 로그 폴더>"
log_cwd_backup = "/<회전·백업 폴더>"
log_name_hint = "<파일 이름 규칙 메모>"

[log]
interceptor = "<요청 시작 줄을 찍는 로거 클래스>"
```

- 계정: 비밀 `ftp` → `<secrets_dir>/<프로젝트 이름>/ftp.env`. 사용자만 편집한다. 에이전트는 읽지 않는다
- 키: `FTP_USER`, `FTP_PASSWORD`(공통), `FTP_USER_<ALIAS>`, `FTP_PASSWORD_<ALIAS>`(서버별, ALIAS는 대문자). 서버별 키가 공통 키보다 우선
- 서버 조회 순서·회전 규칙 같은 운영 지식은 프로젝트 `.agents/docs/`의 로그 문서에 적는다

## MCP 등록

기본은 url 방식(공유 서버). 서버 프로세스 1개를 띄워 두고 모든 세션이 같이 쓴다. 절차·`ports.json` 형식은 `../daemon/README.md`. 이름은 `[guard.ftp] server_name`과 같게 쓴다.

1. `daemon/ports.json`에 `"<프로젝트>-ftp": { "port": <포트>, "script": "../ftp/server.py" }`
2. 프로젝트 `.agents/mcp.json`(정본. `.mcp.json`·`.cursor/mcp.json`은 링크)에 추가

```json
{
  "mcpServers": {
    "<프로젝트>-ftp": { "type": "http", "url": "http://127.0.0.1:<포트>/mcp" }
  }
}
```

3. 같은 서버를 stdio로 적은 항목을 `.agents/mcp.stdio.json`에 남긴다(데몬을 못 쓸 때 되돌리는 용도)

```json
{
  "mcpServers": {
    "<프로젝트>-ftp": {
      "command": "<mcp가 설치된 Python 절대경로>",
      "args": [".agents/mcp-servers/ftp/server.py"]
    }
  }
}
```

의존성: `python -m pip install -r .agents/mcp-servers/ftp/requirements.txt`. `mcp`는 1.x만 쓴다(`mcp>=2`는 API 비호환 가능성, 미확인).

`server.py`는 `HARNESS_MCP_TRANSPORT`가 `streamable-http`(또는 `http`)면 `HARNESS_MCP_HOST`·`HARNESS_MCP_PORT`로 HTTP를 열고, 없으면 stdio로 동작한다. 데몬이 이 값을 넣는다.

## 도구 (읽기만)

| 도구 | 설명 |
|------|------|
| `ftp_servers` | 별칭·경로 힌트 목록 (설정만 읽음) |
| `ftp_list` | 원격 디렉터리 LIST |
| `ftp_get` | RETR 미리보기 (기본 최대 2MB, 상한 8MB, `tail_lines`). 본문을 응답에 넣음 |
| `ftp_download` | RETR → `.agents/tmp/ftp/{alias}/`. 경로·크기만 반환. 기본 512MB, 상한 2GB. 상한 초과 시 받은 일부를 지움 |
| `ftp_slice` | 텍스트 로그의 시각 구간만 받음(`from_ts` 이상 `to_ts` 미만, 로그에 찍힌 `YYYY-MM-DD HH:mm[:ss]`). 타임스탬프 이진 탐색 + REST. 저장명 `{원본}.{HHmm}-{HHmm}.log`. zip/gz 불가 |

put / rename / delete 도구 없음. 훅 `ftp_mcp_guard.py`가 허용 목록 밖 도구를 막는다. zip/gz는 풀지 않고 요약기가 직접 읽는다(원본 유지).

`ftp_slice`는 줄 맨 앞의 `YYYY-MM-DD HH:mm:ss`로 위치를 찾는다. 줄이 다른 시각 형식으로 시작하는 로그는 `ftp_download`를 쓴다.

## 로그 요약기 (`log_digest.py`)

- 요약: `log_digest.py --group <스키마> --corp <회사 ID> [--from ..] [--to ..] [--key 값] FILE...` → 대상 회사 요청 1건당 1줄(INS/UPD/DEL/MRG/ETC/예외/키 hit)
- 원문: `log_digest.py --puuid <요청 ID> FILE...` → 그 요청의 SQL(SELECT 제외)·예외, 최대 200줄
- 자체검사: `log_digest.py --selftest` (설정 없이 동작. 고정 샘플 줄 사용)

프로젝트 값은 `[log] interceptor` 하나다. 나머지 줄 형식은 코드에 고정돼 있어 아래와 다르면 요청 0건이 나온다. 이때는 `HEAD`·`REQ`·`MEMBER_FIELD` 정규식을 프로젝트 로그에 맞게 고친다.

기대하는 줄 형식

```text
레코드 머리:  YYYY-MM-DD HH:mm:ss[,mmm] <스레드 | (괄호로 감싼 스레드)> LEVEL [로거] 본문
              LEVEL = TRACE|DEBUG|INFO|WARN|ERROR. 머리 없는 줄은 앞 레코드에 붙음
요청 시작:    로거 = [log] interceptor, LEVEL = DEBUG, 본문이 "=============" 로 시작
              ... Request URI : [<URI>] / PUUID : [<요청 ID>] / ... / IP : [<IP>]
              / Member : [... Group_ID=<스키마>, Corp_ID=<회사 ID>, User_ID=<사용자> ...]   (로그인 전 요청은 Member 없음)
SQL:          로거 = jdbc.sqltiming (log4jdbc), 본문 앞 /* Dao.method */ 주석은 선택
```

판정 규칙

- 요청은 스레드로 가른다. 같은 스레드의 다음 요청 시작 줄까지가 한 요청
- 대상 회사: 요청 시작 줄의 `Corp_ID`·`Group_ID`. Member가 없는 요청은 SQL에 `<스키마>.`와 `CORP_ID = <회사 ID>`가 같이 있을 때만 대상
- 요청 시작 줄 전에 나온 대상 회사 DML은 `outside_request_dml`로 건수만 센다

## 스모크

```text
python .agents/mcp-servers/ftp/smoke_test.py
```

- `[[ftp.servers]]`의 서버마다 `log_cwd_current` LIST → 첫 일반 파일 tail → `ftp_download` 상한 거부 → 첫 시각부터 1시간 `ftp_slice`
- 서버가 없으면 원격 검사를 SKIP하고 종료 코드 0. `log_cwd_current`가 빈 서버도 SKIP
- 훅 정책은 `.agents/hooks/tests/test_ftp_mcp_guard.py`가 따로 검사

## 활성화

1. `python .agents/mcp-servers/daemon/daemon.py start` → `status`에서 `running: true`
2. MCP 등록 후 Cursor MCP Reload 또는 Claude Code `/mcp`
3. 서버 이름이 Running인지 확인
4. 스모크 실행
