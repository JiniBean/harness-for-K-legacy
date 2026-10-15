범위: 프로젝트 전용
구성: 규칙, MCP 어댑터

# tibero

Tmax Tibero 연결 어댑터. 공통 환경 목록·승인 정책·훅·싱글톤은 **db-mcp** 모듈이 담당한다. 이 모듈은 JDBC·런처·방언·Tibero 전용 셸 차단만 둔다.

## 사용자 안내

설명: db-mcp가 확정한 환경에 Tibero JDBC로 붙는 MCP 서버를 만듭니다. 계정은 프로젝트 밖 `tibero.env`에 둡니다.

물어볼 것 (db-mcp 질문 다음에)

1. `[항상]` 스캔으로 찾은 `tibero*-jdbc.jar` 경로와 프로필(host·port·sid)이 맞나요?
   - 선택지: 맞음 / 경로·프로필 수정
   - 추천·모름: 스캔 후보
2. 비밀 파일 안내: `<secrets_dir>/<프로젝트>/tibero.env`에 `TIBERO_USER_<ENV>` / `TIBERO_PASSWORD_<ENV>`

## 감지 신호

- `tibero*-jdbc.jar`, `jdbc:tibero:thin:@`, `com.tmax.tibero.jdbc.TbDriver`

## 원칙

- SELECT 행 제한 예: `ROWNUM`(방언). 공통 승인·차단은 db-mcp
- 서버는 `.agents/hooks/db_sql_policy.py`를 import해 2차 검사
- `launch_<env>.py`는 환경마다 하나. 환경 이름은 db-mcp와 동일(`[a-z0-9]+`)
- MCP 등록 이름은 `db-<env>`(공통). 스크립트만 `../tibero/launch_<env>.py`

## 규칙 작성 항목

| 항목 | 키 |
|---|---|
| JDBC jar | `[tibero] jdbc_jar` |
| 접속 | `[tibero.profiles.<env>]` host, port, sid |
| JDK | `[java] tool_jdk_home` |
| 셸 차단 호스트 | `[guard] block_hosts` (Tibero 호스트) |
| 비밀 | `tibero.env` |

## 포함 파일

- `harness.fragment.toml` (jaydebeapi·TbDriver·tibero:thin·TIBERO_PASSWORD·tibero-mcp-server)
- `mcp-servers/tibero/` (`launch_common.py`, `launch_<env>.py` 생성, `tibero-mcp-server/`, `requirements.txt`, `tibero.env.example`, `README.md`)

## 설정 키

`[tibero]`, `[tibero.profiles.<env>]`, `[java] tool_jdk_home`, `[guard] block_hosts`
