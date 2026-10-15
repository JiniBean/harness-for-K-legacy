# harness-for-K-legacy

> 한국형 SI 레거시용 에이전트 하네스 키트

에이전트가 알기 힘든 국내 SI 레거시 스택에 맞춰 하네스 환경을 구축합니다.

`#Java6-8` `#eGovFrame` `#Tibero` `#Nexacro` `#iBatis2` `#OZ` `#WindowsCP949`

일반 웹프로젝트는 [harness-kit](https://github.com/JiniBean/harness-kit)를 쓰세요.

## 장점

1. **프로젝트를 읽어 루트·폴더 `AGENTS.md`를 맞춰 씁니다**  
   jar·설정·소스로 스택을 알아서 잡고, 계층별 규칙을 폴더마다 둡니다.

2. **위험한 실수는 훅이 막습니다**  
   운영 DB 쓰기, 리포트 바이너리 텍스트 저장, 비밀·보호 경로 접근을 실행 전에 차단합니다.

3. **쓸수록 규칙이 남고, 쓰레기는 치웁니다**  
   대화 교정은 memory-tidy로 공유 규칙에 올리고, 임시·세션 파일은 garbage-collector로 미리보기 후 지웁니다.

## 주요 기능

- **프로젝트 맞춤 설치** — 스택을 감지하고 쓸 기능만 고른 뒤, 원칙을 프로젝트 사실로 채움
- **루트·폴더 AGENTS.md** — 폴더 지도와 계층별 규칙을 구조에 맞게 생성
- **위험 동작 차단** — 비밀·보호 경로·위험 셸을 실행 전에 막고, 보호 해제만 승인 키워드
- **검증·검토** — 변경 정적 검사(verify), 계획·diff 별도 검토(reviewbot)
- **교정 승격** — 대화·메모리 교정을 공유 지시 파일로 올림 (memory-tidy)
- **임시 파일 정리** — `.agents/tmp`·세션 기록을 미리보기 후 삭제 (garbage-collector)
- **레거시 스택** — java-legacy, egov-spring, ibatis2, tibero, nexacro, oz, windows-cp949
- **이슈·로그·매퍼·DB** — issue-flow, log-debug, mapper, db-mcp (상세는 아래 표)

## 구현 포인트

- **원칙 → 프로젝트 채움** — 모듈은 작성 항목. 설치 때 jar·설정·폴더에서 채움. 못 찾은 값은 `미확인`으로 남기고 물음
- **폴더별 지시** — 화면·매퍼·리포트 규칙을 해당 폴더 `AGENTS.md`로 나눔
- **기존 규칙 이전** — `CLAUDE.md`·`.cursor/rules` 등을 옮기고 빠진 규칙 점검
- **정본 하나** — `.agents/`만 키우고 도구별은 링크·생성. 값은 `harness.toml`, 비밀은 저장소 밖
- **레거시 고정** — DB 쓰기 승인은 db-mcp, Tibero는 JDBC 어댑터. OZ 바이너리 텍스트 저장은 막음
- **오래 쓰기** — memory-tidy·garbage-collector

## 설치하면 생기는 것

예시 프로젝트(eGovFrame + iBatis 2 + Nexacro + OZ + Tibero)에 설치한 결과입니다. 폴더 `AGENTS.md`는 켠 기능과 실제 폴더 구조에 따라 정해집니다.

```text
my-egov-project/
├─ AGENTS.md                       ← 스택·폴더 지도·DB 확인 절차·형상관리
├─ src/main/java/AGENTS.md         ← Controller → Service → DAO, JDK 문법 제한
├─ src/main/resources/AGENTS.md    ← iBatis 2 문법, 기존 매퍼 먼저 읽기
├─ src/main/ui/AGENTS.md           ← Nexacro 스크립트 순서, transaction 래퍼
├─ src/main/report/AGENTS.md       ← OZ 바이트 패치 절차
└─ .agents/
   ├─ harness.toml                 ← 경로·서버·이름 (규칙 본문에는 값 없음)
   ├─ skills/  agents/  hooks/  mcp-servers/  docs/
   └─ tmp/                         ← 일회성 파일 (garbage-collector가 정리)
```

매퍼 폴더 `AGENTS.md` 발췌입니다. 아래 값은 설치 때 프로젝트 매퍼를 읽어 채운 모습입니다.

```markdown
# SQL 매퍼 (src/main/resources)

- iBatis 2.3.4 (`sql-map-2.dtd`). 바인딩 `#p#`, 치환 `$p$`. MyBatis 문법 `#{p}` 금지
  ← sql-map-2.dtd · 매퍼 XML DOCTYPE에서
- statement id는 `<업무>.<동작><대상>` (예: `order.selectOrderList`). DAO 호출 문자열과 같게
  ← 기존 매퍼 id 형식에서
- SQL을 처음부터 새로 쓰지 않는다. 같은 모듈의 기존 `*_SQL.xml`을 먼저 읽고 구조를 따른다
- 세션 파라미터는 아래 표에 있는 이름만 쓴다
  ← 공통 매퍼·세션 키 사용처에서

| 파라미터 | 뜻 |
|---|---|
| `#SES_COMP_CD#` | 로그인 회사 |
| `#SES_USER_ID#` | 로그인 사용자 |
```

## 시작하기

1. 저장소를 받습니다: `git clone https://github.com/JiniBean/harness-for-K-legacy.git`
2. 하네스를 설치할 프로젝트에서 에이전트에게 말합니다: `<받은 폴더>/start.md 를 읽고 따라 이 프로젝트에 하네스를 설치해줘`
3. 끝나면 「하네스 점검해줘」로 확인합니다

필요한 것: Python 3.11+(표준 라이브러리만), Windows는 개발자 모드. 자세한 절차는 [start.md](start.md).

시작 전에

- 확인받기 전에는 프로젝트 파일을 쓰지 않습니다
- 코드에서 찾은 값은 묻지 않고 「이렇게 정했습니다」로 보여 줍니다. 모르면 「모름」이라고 해도 됩니다
- 계정·비밀번호 값은 묻지도 받지도 않습니다. 빈 파일만 만들어 둡니다

## 기능 목록

`modules/<이름>/`이 기능 하나의 설치 단위입니다.

### 전역 또는 프로젝트

어디에 둘지 고릅니다. 여러 프로젝트에서 같이 쓰면 전역, 그 저장소만이면 프로젝트입니다.

| 이름 | 하는 일 | 구성 |
|---|---|---|
| agent-rules | 에이전트 응답·작업 태도 규칙 | 규칙 |
| response | 응답 형식 지적을 받으면 다시 설명하고 지적을 쌓아 둠 | 스킬 |
| ponytail | 필요한 만큼만 코드를 쓰게 함 | 스킬 5종 |
| memory-tidy | 대화에서 고쳐 준 것을 모아 규칙 파일로 올림 | 스킬 |
| garbage-collector | 에이전트 임시 파일·세션 기록을 미리보기 후 삭제 | 스킬 |
| transcript-grep | 지난 대화 기록 검색 | 도구 |
| jetbrains | IntelliJ로 코드 검색, IDE 쪽 수정·터미널 호출 차단 | 훅, 규칙 |
| windows-cp949 | 한국어 Windows 셸에서 한글 깨짐 방지 | 훅, 규칙 |

### 프로젝트 전용

이 저장소에만 붙습니다. 스택과 무관한 뼈대·업무 기능입니다.

| 이름 | 하는 일 | 구성 |
|---|---|---|
| guards | 비밀 파일 읽기·훅 수정·위험 셸을 실행 전에 차단. 보호 파일은 승인 키워드로 한 번만 풀림 | 훅 |
| verify | 바꾼 파일만 정적 검사. FAIL이 있으면 완료 선언 금지 | 스킬, 도구 restore_eol |
| reviewbot | 계획·diff를 별도 맥락에서 검토 | 에이전트 |
| db-mcp | DB 환경·쓰기 승인 정책·훅·싱글톤. JDBC는 tibero 등 어댑터가 담당 | 규칙, 훅, MCP 등록·싱글톤 |
| log-debug | WAS 로그로 오류·변경 추적 (운영 로그 / 로컬 로그) | 스킬, 에이전트 logbot, 훅, MCP(FTP), 도구 |
| issue-flow | 이슈 착수→분석→계획→검증을 한 흐름으로 | 스킬, 도구 |
| comment-gen | 바꾼 코드에 변경 이력 주석 | 스킬 |

### 레거시 모듈

프로젝트 스택을 감지하고 쓰는 것만 켭니다. 폴더 `AGENTS.md`를 채우는 규칙이 여기에 많습니다.

| 이름 | 하는 일 | 구성 |
|---|---|---|
| java-legacy | 옛 JDK에서 못 쓰는 문법 금지 | 규칙 |
| egov-spring | Controller→Service→DAO 계층·명명 규칙 | 규칙 |
| mapper | 기존 매퍼 구조를 따라 SQL 작성, 바꾼 SQL은 개발 DB에서 확인 | 규칙, 에이전트 sqlbot |
| ibatis2 | iBatis 2 문법 (mapper와 함께) | 규칙 |
| tibero | Tibero JDBC·런처·방언. 승인·훅·싱글톤은 db-mcp | 규칙, MCP 어댑터 |
| nexacro | Nexacro 화면 규칙, 화면 빌드(Generate) | 규칙, 스킬 generate, 에이전트 nexabot |
| oz | OZ 리포트를 바이트 패치로만 수정·점검 | 규칙, 훅, 에이전트 ozbot, 도구 oz_tool |

## 지원 도구

| 구성 | Claude Code | Cursor | Codex |
|---|---|---|---|
| 전역 지시 | `~/.claude/CLAUDE.md` import | User Rules 붙여넣기 | `~/.codex/AGENTS.md` 링크 |
| 스킬 | 링크 | 직접 읽음 | 직접 읽음 |
| 에이전트 | 링크 | 링크 | TOML 생성 |
| 프로젝트 훅 | 생성 | 생성 | 생성 (`/hooks`에서 신뢰 승인 필요) |
| 전역 훅 | 병합 생성 | 병합 생성 | 생성 안 함 |
| MCP | 링크 | 링크 | `config.toml` 생성 |

## 라이선스

MIT.

`modules/ponytail/skills/ponytail*`은 [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail)(MIT)을 고친 것입니다.

`modules/tibero/mcp-servers/tibero/tibero-mcp-server/`는 [YeomYuJun/tibero-mcp-server](https://github.com/YeomYuJun/tibero-mcp-server)(MIT)에 서버측 쓰기 정책 검사와 감사 로그를 더한 수정판입니다. 원본 LICENSE를 그 폴더에 함께 둡니다.
