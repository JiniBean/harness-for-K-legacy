# 하네스 설정 가이드 (전역)

지시 파일, 스킬, 에이전트, 훅, MCP를 새로 만들거나 고칠 때 먼저 본다. Claude Code·Cursor·Codex 중 무엇을 쓰든 같다. 프로젝트 전용 절차(훅 생성, 보호 파일, 프로젝트 MCP 서버, 테스트 목록)는 `<프로젝트>/.agents/docs/harness-guide.md`에 있다. 두 문서가 충돌하면 프로젝트 문서를 따른다.

## 1. 원칙

- 정본은 도구 이름이 없는 곳에 둔다. 전역은 `~/.agents/`, 프로젝트는 `<프로젝트>/.agents/`와 `AGENTS.md`다
- `.claude/`, `.cursor/`, `.codex/`와 각 홈 폴더에는 어댑터만 둔다. 어댑터는 정본을 가리키는 링크이거나 생성된 등록 파일이다. 여기에 실파일을 새로 만들지 않는다
- 형식이 같고 위치만 다른 것은 정본 하나에 링크를 건다. 형식이 다른 것(훅 등록, Codex 에이전트·MCP)은 정본 하나에서 생성한다
- 같은 규칙 문장을 여러 지시 파일에 반복하지 않는다. 정본 한 곳에 쓰고 나머지는 위치만 가리킨다
- 전역에는 모든 프로젝트에서 쓸 수 있는 것만 둔다. 프로젝트 경로, 업무 용어, DB, 사내 도구는 프로젝트에 둔다
- 여러 도구가 공유하는 스킬·지시 파일에 한 도구 전용 기능이 있으면 지워서 공통분모로 맞추지 않는다. 원래 경로는 두고 다른 도구의 대체 경로를 한 줄 덧붙인다. 분기는 도구 이름이 아니라 도구 존재로 쓴다("`<도구>`가 있으면 그것을 쓰고, 없으면 …")
- 스크립트 설명(무엇을 하는지·인자)은 스크립트 자신(docstring, 인자 없이 실행 시 usage)과 소유 문서 한 곳에만 둔다. 다른 문서에는 호출 줄만 쓴다
- 지시 파일에 설명용 예시·사례 인용을 넣지 않는다. 명령·설정 형식, 복사할 원본 위치, 금지 대상 문구처럼 그 자체가 내용인 것만 둔다. 예외: 이미 있는 규칙이 들어간 뒤에 같은 교정이 다시 확인되면 그 규칙에만 전후 예시 한 쌍을 둔다(memory-tidy 「예시」 분류)
- 값(사람·조직·경로·서버·필드 ID)은 지시 파일·스크립트에 쓰지 않고 `harness.toml`에 둔다. 비밀값은 비밀 폴더에만 둔다(§2.1)
- 언어: 사용자가 관리하는 지시 파일(AGENTS.md, 스킬, 에이전트 정의, docs)은 한국어, 스크립트 주석·docstring·에이전트 간 기록은 영어

## 2. 무엇이 어디에 있나

| 종류 | 정본 | Claude Code | Cursor | Codex |
|------|------|-------------|--------|-------|
| 전역 지시 | `~/.agents/AGENTS.md` | `~/.claude/CLAUDE.md`가 `@~/.agents/AGENTS.md`로 import | Settings → Rules → User Rules에 붙여넣은 사본(수동) | `~/.codex/AGENTS.md` 링크 |
| 전역 참조 문서 | `~/.agents/docs/` | 지시 파일이 가리키면 Read | 같음 | 같음 |
| 전역 스킬 | `~/.agents/skills/` | `~/.claude/skills/<이름>` 스킬별 링크 | 직접 읽음 | 직접 읽음 |
| 전역 에이전트 | `~/.agents/agents/` | `~/.claude/agents` 링크 | `~/.cursor/agents` 링크 | `~/.codex/agents/*.toml` 생성 |
| 전역 훅 | `~/.agents/hooks/hooks.toml` + `*.py` | `~/.claude/settings.json` hooks에 병합 생성 | `~/.cursor/hooks.json`에 병합 생성 | 생성 안 함(Codex가 `~/.codex/hooks.json`을 읽는지 미확인) |
| 전역 MCP | `~/.agents/mcp.json` | 로컬 플러그인의 `.mcp.json` 링크 | `~/.cursor/mcp.json`에 항목 추가 | `~/.codex/config.toml` `[mcp_servers]` 생성 |
| 프로젝트 지시 | 루트 `AGENTS.md`, 소스 폴더별 `AGENTS.md` | 직접 읽음(`CLAUDE.md`가 없어야 함) | 직접 읽음 | 직접 읽음. git 루트→현재 폴더 경로의 파일을 이어 붙이고 합계 기본 32 KiB를 넘으면 잘림 |
| 프로젝트 참조 문서 | `.agents/docs/` | 지시 파일의 인덱스를 보고 Read | 같음 | 같음 |
| 프로젝트 스킬 | `.agents/skills/` | `.claude/skills` 링크 | 직접 읽음 | 직접 읽음 |
| 프로젝트 에이전트 | `.agents/agents/` | `.claude/agents` 링크 | `.cursor/agents` 링크 | `.codex/agents/*.toml` 생성 |
| 프로젝트 훅 | `.agents/hooks/hooks.toml` | `.claude/settings.json` 생성 | `.cursor/hooks.json` 생성 | `.codex/hooks.json` 생성 |
| 프로젝트 MCP | `.agents/mcp.json` | `.mcp.json` 링크 | `.cursor/mcp.json` 링크 | `.codex/config.toml` `[mcp_servers]` 생성 |
| 일회성 파일·계획 | `.agents/tmp/`, `.agents/plans/` | — | — | — |
| 설정값 | `~/.agents/harness.toml`(고정) → 프로젝트 `.agents/harness.toml`(같은 키는 프로젝트 우선) | 에이전트가 Read | 같음 | 같음 |
| 비밀값 | `<secrets_dir>/<프로젝트 이름>/<이름>.env`(기본 `~/.agents/secrets/`) | 에이전트 읽기 금지(훅이 차단) | 같음 | 같음(읽기 훅이 없어 셸 가드가 경로를 막음) |

- 명령(슬래시 명령)은 쓰지 않는다. 모두 스킬로 만든다. Claude Code는 스킬도 `/이름`으로 부르고, Codex의 사용자 명령(`~/.codex/prompts`)은 폐기 예정이다
- Codex는 사용자가 `/hooks`에서 훅을 신뢰 승인해야 실행한다. 프로젝트 `.codex/` 설정은 신뢰한 프로젝트에서만 읽는다

### 2.1 설정값·비밀값 쓰는 법

- 스크립트·훅·MCP 실행기는 값을 코드에 쓰지 않고 `~/.agents/scripts/harness_config.py`로 읽는다. `load(project_root)`는 설정, `secret(name, project_root=...)`는 비밀(`{KEY: VALUE}`). 환경변수 `HARNESS_SECRET_<NAME>_<KEY>`가 있으면 그 키를 덮어쓴다
- 스킬·에이전트·AGENTS.md에는 값 대신 `harness.toml`의 키 이름을 적는다(`{paths.svn_wc}`, `[tracker.fields] deploy_due`)
- 경로 변경: 비밀 폴더는 전역 `harness.toml`의 `secrets_dir`(사용자만 수정), 프로젝트 설정 위치는 `[projects."<프로젝트 루트>"] harness_dir`
- 비밀 파일의 값은 사용자가 직접 넣는다. 에이전트는 새 빈 파일과 키 이름까지만 만든다
- 프로젝트 `harness.toml`의 `[guard]` 절(훅 정책)은 `gohook` 승인 턴에만 바뀐다
- 경로 확인(값은 출력하지 않음): `python ~/.agents/scripts/harness_config.py <프로젝트 루트>`

## 3. 지시 파일 배치표

교정·규칙을 어디에 넣을지 고를 때 쓴다(memory-tidy 승격 기준).

| 내용 성격 | 넣을 곳 |
|-----------|---------|
| 모든 프로젝트 공통 응답·작업 규칙 | `~/.agents/AGENTS.md`. 고친 뒤 Cursor User Rules에도 다시 붙여 넣는다 |
| 모든 프로젝트 공통이지만 필요할 때만 읽는 지식 | `~/.agents/docs/*.md` + 전역 `AGENTS.md`에 위치 한 줄 |
| 그 프로젝트의 어떤 작업이든 파일을 열기 전부터 필요한 것 | 루트 `AGENTS.md` |
| 특정 소스 폴더 파일을 만들거나 고칠 때만 필요한 것 | 그 폴더의 `AGENTS.md` |
| 파일과 관계없이 질문으로 필요해지는 프로젝트 지식 | `.agents/docs/*.md` + 루트 `AGENTS.md` 인덱스에 한 줄 |
| 여러 단계 절차 | 스킬 |
| 바뀔 수 있는 값 | `harness.toml` |

- 루트에 `CLAUDE.md`나 `.claude/CLAUDE.md`를 만들지 않는다. 만들면 Claude Code가 `AGENTS.md`를 읽지 않는다. Claude 전용 내용이 꼭 필요하면 `CLAUDE.md` 첫 줄에 `@AGENTS.md`를 두고 그 아래에 쓴다
- 새 폴더 `AGENTS.md`를 만들면 루트 `AGENTS.md`의 폴더 지도에 경로를 추가한다
- 폴더 `AGENTS.md`의 자동 로드는 도구와 파일을 연 방식에 따라 다르다. 자동 로드에 기대지 않고, 그 폴더 파일을 다루기 전에 내용이 컨텍스트에 없으면 직접 Read한다
- 서브에이전트는 전역·프로젝트 지시를 받는다. Claude Code는 세션 시작 때 읽은 내용을 넘기므로, 세션 중에 고친 지시는 새 세션부터 서브에이전트에 반영된다

## 4. 기능 (저장소 `modules/`)

하네스 저장소는 기능 단위로 나뉜다. 사용자에게는 「기능」이라고 부르고, `modules/<이름>/`은 기능 하나의 설치 단위다. `set-up-harness`가 프로젝트 스택을 보고 고른다. 기능은 완성된 규칙이 아니라 원칙과 작성 항목을 담고, 설치할 때 프로젝트 내용으로 채운다.

```text
<하네스 저장소>/
├─ core/       공통 런타임·문서: harness_config.py, hook_io.py, gen_hook_configs.py, harness-guide.md, 설정 예시
├─ install/    install.py(전역 기반·도구 링크), set-up-harness(시작 절차 스킬)
└─ modules/<이름>/
   ├─ MODULE.md              맨 위 「범위:」「구성:」 두 줄 · 사용자 안내 · 감지 신호 · 원칙 · 규칙 작성 항목 · 포함 파일 · 설정 키
   ├─ skills/  agents/       → <.agents>/skills, <.agents>/agents
   ├─ hooks/ + hooks.toml    → 훅은 <.agents>/hooks, hooks.toml 조각은 <.agents>/hooks/hooks.toml 끝에 이어 붙임
   ├─ harness.fragment.toml  → <.agents>/harness.toml에 합침. [guard] shell_block_patterns 같은 목록은 기존 목록에 더함
   ├─ verify.md              → .agents/skills/verify/checks/<이름>.md (프로젝트만)
   └─ scripts/  mcp-servers/ → <.agents>/scripts, <.agents>/mcp-servers
```

- `<.agents>`는 전역 설치면 `~/.agents`, 프로젝트 설치면 `<프로젝트>/.agents`
- 범위
  - `범위: 필수(프로젝트)`: guards, verify, reviewbot. 프로젝트에 항상 설치, 끄기 없음
  - `범위: 선택(추천: 전역)`: 사용자가 전역·프로젝트 중 고름
  - `범위: 프로젝트 전용`: 프로젝트에만 설치
- `core/hook_io.py`·`core/gen_hook_configs.py`는 정본 하나다. 전역 기반 설치(`install.py global`)가 `~/.agents/hooks/`에, 프로젝트 설치(guards)가 `.agents/hooks/`에 링크한다. 훅이 있는 기능은 설치한 위치의 `hooks/`에 있는 `hook_io`를 쓴다
- 전역에 이미 같은 훅 스크립트가 있으면 프로젝트 `hooks.toml`에 넣지 않는다
- 기능 훅의 `required = true`는 등록 파일에서 빠지면 생성을 거부하는 가드, `protected = true`·`protects = [...]`는 에이전트가 고치지 못하는 파일이다
- 기능을 끄면 그 기능이 설치한 파일과 조각을 같이 뺀다

## 5. 작업별 절차

### 5.1 스킬 추가

1. 프로젝트 스킬은 `.agents/skills/<이름>/SKILL.md`, 전역 스킬은 `~/.agents/skills/<이름>/SKILL.md`에 만든다. frontmatter에 `name`, `description`(트리거 문구 포함)이 있어야 한다
2. 프로젝트 스킬은 추가 작업이 없다
3. 전역 스킬은 Claude Code용 링크를 하나 건다. `~/.claude/skills`는 다른 동기화 폴더가 들어 있을 수 있는 실폴더라서 폴더째 링크로 바꾸지 않는다
4. 스킬 안의 상대경로는 `.agents/` 기준으로 쓴다

### 5.2 에이전트 추가

- `<위치>/agents/<이름>.md`에 만든다. Claude Code·Cursor는 링크로 읽고, Codex용 TOML은 설치 스크립트가 다시 생성한다
- frontmatter에는 여러 도구 필드를 함께 적어도 된다(Claude `tools`/`disallowedTools`, Cursor `readonly`). 서로 모르는 필드는 무시한다

### 5.3 훅 추가·수정

1. 훅은 `<.agents>/hooks/`(전역 `~/.agents/hooks/`, 프로젝트 `.agents/hooks/`)에 만들고 같은 폴더의 `hook_io.py` 함수를 쓴다(입력 읽기, 허용·거부 출력, 경로·명령 추출). 도구 구분은 `hook_io`가 한다
2. 같은 폴더의 `hooks.toml`에 `[[hook]]`를 추가한 뒤 생성기로 등록 파일을 만든다. 등록 파일을 직접 고치지 않는다(`--check`로 차이만 보기, `--tools`로 도구 고르기)
   - 프로젝트: `python .agents/hooks/gen_hook_configs.py --scope project`. 프로젝트 등록 파일의 `hooks`를 통째로 다시 만든다
   - 전역: `python ~/.agents/hooks/gen_hook_configs.py --scope global`. `~/.claude/settings.json`·`~/.cursor/hooks.json`에서 명령 경로가 `~/.agents/hooks/`인 항목만 바꾸고 사용자가 따로 등록한 항목·다른 키는 그대로 둔다. Codex 전역 등록은 만들지 않는다
3. 도구 판별: Cursor 전용 키(`cursor_version`, `conversation_id`)가 있으면 Cursor, 아니면 Claude Code·Codex(출력 형식이 같음)
4. JSON 출력은 `ensure_ascii=True`로 한다
5. Python은 `harness.toml`의 `[tools] python` 절대경로를 쓴다
6. 테스트를 돌린다

주의
- Cursor 설정의 Third-Party Imports는 꺼 둔다. 켜 두면 Cursor가 `.claude/settings.json`의 훅도 실행해서 훅이 두 번 돈다
- 프로젝트 훅의 Claude 등록에는 `$CLAUDE_PROJECT_DIR`를 쓴다. Codex는 같은 변수가 없어 절대경로로 등록된다. 전역 훅은 Claude·Cursor 모두 `~/.agents/hooks/` 절대경로로 등록된다
- 전역 위치의 `hook_io.guard_config()`는 전역 `harness.toml`만 읽는다(프로젝트 `[guard]`는 프로젝트 훅에만 적용)
- 훅 스크립트를 고칠 때는 고칠 파일 목록을 먼저 적고 사용자의 `gohook` 승인을 받는다

### 5.4 MCP 추가

- 프로젝트 MCP: `.agents/mcp.json`을 편집한다. `.mcp.json`과 `.cursor/mcp.json`은 링크이고, Codex 설정은 설치 스크립트가 다시 만든다
- 전역 MCP: `~/.agents/mcp.json`에 추가한다
  - Claude Code는 로컬 플러그인이 이 파일을 읽어서 도구 이름이 `mcp__plugin_<플러그인>_<서버>__<도구>`가 된다. 훅 matcher는 `mcp__.*<서버>.*`처럼 여러 이름을 함께 잡게 쓴다
  - 환경변수 표기가 도구마다 다르다: Claude `${VAR}`, Cursor `${env:VAR}`, Codex는 치환이 없고 `env_vars`·`bearer_token_env_var`로 넘긴다
  - `~/.claude.json`은 Claude Code가 관리하는 상태 파일이다. 직접 편집하거나 링크하지 않는다
- MCP 서버 스크립트는 `<위치>/mcp-servers/<이름>/`에 둔다. 경로는 `__file__` 기준으로 계산한다
- MCP 서버가 실행 중이면 그 venv·파일이 잠겨 옮길 수 없다. 세션을 재시작한 뒤 옮긴다

#### 프로젝트 MCP 공유 서버 (daemon)

로컬 Python MCP 서버(DB·FTP)는 stdio로 등록하면 세션마다 프로세스가 생긴다. 공유 서버는 서버별 프로세스 1개를 `127.0.0.1` HTTP로 띄우고 모든 세션이 `mcp.json`의 `url`로 붙는다. 상세는 `.agents/mcp-servers/daemon/README.md`.

- 정본: `.agents/mcp-servers/daemon/ports.json`(서버 이름·포트·실행 파일·Python), `.agents/mcp.json`은 같은 포트의 `url`. stdio 항목은 되돌림용으로 `.agents/mcp.stdio.json`
- 서버 이름·포트를 바꾸면 `ports.json`과 `mcp.json`을 같이 고친다
- 기동: `python .agents/mcp-servers/daemon/daemon.py start|status|stop`. `status`의 `running`은 포트가 열려 있다는 뜻이다
- pythonw(로그온 자동 시작)로 돌린 결과는 `state/last_cmd.json`, 서버별 출력은 `state/<이름>.log`
- 데몬이 꺼진 채 세션을 열면 연결 실패로 보인다. 데몬을 띄운 뒤 Claude Code `/mcp`, Cursor MCP 화면 토글로 다시 연결한다
- `state/`는 VCS에서 뺀다

## 6. 링크 만드는 법 (Windows)

- 심볼릭 링크는 개발자 모드가 필요하다. Git Bash에서는 `MSYS=winsymlinks:nativestrict ln -s <대상> <링크>`를 쓴다. 이 설정이 없으면 복사본이 만들어진다
- 새 경로에 링크를 먼저 만들고 `ls -la`로 `->`를 확인한 뒤에 기존 폴더를 지운다
- 하드링크는 쓰지 않는다. 편집 도구가 파일을 교체하면서 링크가 끊긴다
- Codex 스킬은 폴더째 링크보다 스킬별 폴더 링크가 안전하다(폴더째 링크와 Windows 정션 인식은 미확인)
- 구조를 바꾼 뒤에는 옛 경로 참조를 검색해서 0건인지 확인한다

## 7. 도구별로 수동 동기화가 남은 곳

| 구간 | 이유 | 할 일 |
|------|------|-------|
| 전역 지시 → Cursor User Rules | Cursor는 전역 지시 파일을 읽지 않는다 | `~/.agents/AGENTS.md`를 고치면 User Rules에 다시 붙여 넣는다 |
| 전역 MCP → `~/.cursor/mcp.json` | 다른 도구·프로젝트 항목이 같은 파일에 있을 수 있어 링크하지 않는다 | 항목을 같이 추가한다 |
| Codex 훅 신뢰 | 보안 정책 | 훅을 바꾸면 Codex `/hooks`에서 다시 승인한다 |
