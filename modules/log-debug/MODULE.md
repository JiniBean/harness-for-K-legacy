범위: 프로젝트 전용
구성: 스킬, 에이전트 logbot, 훅, MCP(FTP), 도구

# log-debug

WAS·애플리케이션 로그로 데이터 변경 타임라인과 오류 원인을 찾는 기능. 운영 로그(원격)와 로컬 로그를 다룬다.

## 사용자 안내

설명: 에이전트가 운영 서버 로그를 읽기 전용으로 필요한 시간 구간만 받아, 언제 누가 어떤 데이터를 바꿨는지(타임라인)와 오류가 난 화면·SQL을 찾아 줍니다. 로그 서버에 올리기·지우기·이름 바꾸기는 훅이 막습니다. 내 PC의 로그도 같은 방식으로 봅니다.

로그 서버 계정과 비밀번호는 에이전트도 볼 수 없게 프로젝트 밖 폴더에 따로 둡니다. 설치 때 빈 파일(`<secrets_dir>/<프로젝트 이름>/ftp.env`)을 만들어 두니 메모장으로 열어 `=` 뒤에 값을 적어 주세요.

물어볼 것

1. `[항상]` 에이전트가 운영 서버 로그를 FTP로 받아 보게 할까요?
   - 정하는 것: 원격 로그 기능(FTP 연결)을 켤지. 켜면 운영 서버에 읽기 전용으로 접속한다
   - 선택지: 켬 / 끔(내 PC 로그만)
   - 추천: 운영 오류·데이터 문의를 직접 확인하는 업무면 켬
   - 모름/나중에: 끔. 나중에 쓰려면 set-up-harness로 이 기능만 다시 켠다
   - 끔이면 FTP MCP 서버(`mcp-servers/ftp/server.py`, `smoke_test.py`, `requirements.txt`, `README.md`), MCP 공유 서버(`mcp-servers/daemon/`. 다른 기능이 설치하면 그쪽 `ports.json`의 FTP 항목만 뺀다), FTP 가드 훅(`hooks/ftp_mcp_guard.py`와 그 테스트 `hooks/tests/test_ftp_mcp_guard.py`, `hooks.toml`의 `part = "ftp"` 항목), `mcp.json`의 FTP 항목, `ftp.env`, `[ftp]`·`[guard.ftp]`·`ftp_hosts`를 설치하지 않는다. 로그 스킬, 로그 서브에이전트, 로그 요약기(`mcp-servers/ftp/log_digest.py`, 같은 경로)만 설치한다
   - 이 기능 전체(로컬 로그 분석 포함)를 쓸지는 3단계 기능 고르기에서 따로 묻는다. 이 질문과 한 질문으로 합치지 않는다
2. `[처음 쓸 때]` (켬일 때) 서버마다 주소(호스트·포트), 오늘 로그가 쌓이는 폴더, 지난 로그 폴더, 채팅에서 그 서버를 부를 짧은 영문 이름(`alias`)
   - 정하는 것: `[[ftp.servers]]`와 셸 차단 목록 `[guard] ftp_hosts`
   - 설치 때: 묻지 않고 비워 둔다. 처음 운영 로그를 볼 때 log-debug 스킬이 묻고 적는다. 설치 때 사용자가 먼저 알려 주면 그 값을 넣는다
   - 추천: 짧은 영문 이름은 지역·용도 약자(영문 소문자)
3. `[처음 쓸 때]` 내 PC 로그 폴더(`[paths] local_log_dir`)
   - 설치 때: 묻지 않고 비워 둔다. 처음 로컬 로그를 볼 때 log-debug 스킬이 로그 설정 파일에서 찾고, 못 찾으면 묻고 적는다

묻지 않고 정하는 것

- 개발·테스트 DB의 회사 ID(`[test] dev_corp`·`test_corp`, 회사·조직별로 데이터를 나누는 키가 코드에 있을 때만): 비워 둔다(`dev_corp`는 mapper 기능이 처음 검사할 때 적는 값을 같이 쓴다). 비어 있으면 로그를 볼 때마다 에이전트가 DB를 조회해 하나로 확정한다
- 요청 시작 줄을 찍는 클래스(`[log] interceptor`): 코드에서 찾은 값

## 감지 신호

- 로컬 로그 폴더(`log/`, `logs/`), 로그 설정(`log4j*.xml`, `logback*.xml`)
- SQL 로그 출력 라이브러리(log4jdbc 등): 로그에 SQL이 찍히는지
- 원격 로그 서버(FTP·SSH)를 쓰는지: 사용자에게 확인

## 원칙

- 질의(회사·업무 키·구간·파일)를 확정하기 전에는 로그를 받거나 검색하지 않는다
- 원격 로그는 읽기만 한다. 업로드·이름 변경·삭제는 훅이 막는다
- 로그 원문을 통째로 읽지 않는다. 구간만 받고 요약기로 줄인 뒤 고른 요청만 원문으로 본다
- 로그에 없는 DML을 있다고 하지 않는다. "왜"는 화면·매퍼를 본 뒤에만 적는다
- 받은 로그는 `.agents/tmp/ftp/`에 두고, 원격·로컬 원본은 고치지 않는다

## 규칙 작성 항목 (set-up-harness가 채움)

| 항목 | 읽을 곳 / 묻기 |
|---|---|
| 로컬 로그 위치 | 설치 때 비워 둠. 처음 쓸 때 log-debug 스킬이 로그 설정·폴더에서 찾거나 묻는다 → `[paths] local_log_dir` |
| 원격 서버 목록·조회 순서 | 설치 때 비워 둠. 처음 쓸 때 log-debug 스킬이 묻는다 → `[[ftp.servers]]`, `[guard] ftp_hosts`(gohook), 프로젝트 로그 문서 |
| 서버별 로그 파일 이름 규칙 | 서버 목록 조회 결과 → `log_name_hint` |
| 로그 줄 형식 | 로그 샘플: 시각·스레드·레벨·클래스, 요청 시작 줄(URI·사용자), SQL 줄 |
| 요청 시작 줄을 찍는 클래스 | 코드의 interceptor·filter 클래스(`HandlerInterceptor`·`Filter` 구현, Spring 설정의 interceptor 등록)를 찾고, 그 클래스 로거가 요청 URI·사용자를 찍는지 확인 → `[log] interceptor`. 쓰는 곳: 요약기 `log_digest.py`(값이 없거나 틀리면 요청 0건) |
| 요청을 가르는 키 | 요청 ID·스레드 |
| 회사·스키마 확인 방법 | 다중 테넌트 여부, 조회 테이블 |
| 개발·테스트 DB 대응 | 다중 테넌트 키(회사 ID 컬럼·세션 키)가 있을 때만. 설치 때는 비워 둔다(사용자 안내 「묻지 않고 정하는 것」) → `[test] dev_corp`·`test_corp`(log-debug 스킬 로컬 모드 DB 고르기, `sqlbot` 로컬 로그 분석), `[test] dev_schema`(mapper 기능 C_SQL 검사·`sqlbot`). 키가 없으면 비운다 |

결과 → 프로젝트 `.agents/docs/`의 로그 문서, `harness.toml` 값

## 포함 파일

- 스킬 `skills/log-debug/SKILL.md` (모드: 운영 로그 / 로컬 로그)
- 훅 `hooks/ftp_mcp_guard.py` (FTP MCP 읽기 전용)
- 원격 로그 MCP 서버 `mcp-servers/ftp/` → `.agents/mcp-servers/ftp/` (`server.py`, 요약기 `log_digest.py`, `smoke_test.py`, `requirements.txt`, 설정·줄 형식은 `README.md`)
- MCP 공유 서버 `mcp-servers/daemon/` → `.agents/mcp-servers/daemon/`. **db-mcp를 켠 경우 daemon은 db-mcp만 설치**하고, 이 모듈은 FTP를 그 `ports.json`에 `script: "../ftp/server.py"`로만 더한다(`kind` 없음). db-mcp가 끄고 원격 로그만 켠 경우에만 이 모듈의 daemon을 설치한다. 로그온 자동 시작은 설치하지 않고 README 「로그온 자동 시작」을 보고에 안내
- 서브에이전트 `agents/logbot.md` → `.agents/agents/logbot.md`
- 비밀 파일 `ftp.env`: set-up-harness가 훅 등록 전에 키 이름만 넣은 빈 파일로 만든다(키는 `mcp-servers/ftp/README.md`). 값은 사용자가 넣는다

## 설정 키

`[paths] local_log_dir`, `[ftp]`·`[[ftp.servers]]`, `[guard] ftp_hosts`, `[guard.ftp] server_name`, `[log] interceptor`(요청 시작 줄을 찍는 클래스), `[test] dev_corp`·`test_corp`·`dev_schema`. 계정: 비밀 `ftp.env`
