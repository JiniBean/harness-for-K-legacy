범위: 선택(추천: 전역)
구성: 훅, 규칙

# jetbrains

IntelliJ 내장 MCP(`jetbrains`)를 코드 검색 도구로 쓰는 기능.

## 사용자 안내

설명: IntelliJ가 켜져 있으면 에이전트가 IntelliJ의 검색 기능(MCP 연결)으로 코드를 찾아 검색이 빠르고 정확해집니다. 에이전트가 IntelliJ를 통해 파일을 고치거나 터미널·실행 설정을 돌리는 것은 훅이 막습니다.

물어볼 것

1. `[못 찾을 때]` (프로젝트에 `.idea/` 폴더가 없을 때만) 이 프로젝트 작업 중에 IntelliJ를 켜 두나요?
   - 정하는 것: 이 기능 설치 여부. `.idea/` 폴더가 있으면 묻지 않고 설치한다
   - 선택지: 예 / 아니오
   - 추천: 예
   - 모름/나중에: 예. IntelliJ가 꺼져 있으면 에이전트가 일반 검색을 쓰므로 손해가 없다

## 감지 신호와 포함 파일

- 감지 신호: `.idea/` 폴더, 사용자가 IntelliJ 사용을 선택
- 포함 파일: `hooks/jetbrains_mcp_guard.py`(파일 수정·터미널·런 설정 도구 차단) → `<.agents>/hooks/`, 그 등록 항목 `hooks.toml` → `<.agents>/hooks/hooks.toml`에 덧붙임, 테스트 `hooks/tests/test_jetbrains_mcp_guard.py` → `<.agents>/hooks/tests/`, `mcp.example.json`. `<.agents>`는 전역 설치면 `~/.agents`, 프로젝트 설치면 `<프로젝트>/.agents`
- 훅은 설치한 위치의 `hooks/`에 링크된 `hook_io.py`를 쓰고, 그 위치의 생성기(`gen_hook_configs.py --scope global` 또는 `--scope project`)로 등록한다. 전역에 이미 같은 훅이 있으면 프로젝트 `hooks.toml`에 넣지 않는다

## 설치되는 규칙

아래 절이 설치한 위치의 지시(전역 `~/.agents/AGENTS.md` 또는 프로젝트 `AGENTS.md`)에 들어간다.

### 코드 탐색 (IntelliJ 내장 MCP `jetbrains`)

- IntelliJ가 켜져 있으면 기본 검색 도구는 `jetbrains` MCP다. 꺼져 있으면 Grep으로 대체한다.
- `search_in_files_by_text`·`search_in_files_by_regex`에는 `maxUsageCount`를 항상 붙인다(기본 30). 제한 없이 흔한 이름을 검색하면 한 번에 수만 토큰이 들어온다. `fileMask`로 범위를 좁힌다.
- IntelliJ에 프로젝트가 둘 이상 열려 있으면 "No exact project is specified"로 실패한다. `projectPath`에 현재 프로젝트 루트를 넣어 다시 호출한다.
- 파일 일부를 읽을 때는 편집 도구 Read의 offset·limit을 쓴다. 폴더별 `AGENTS.md`는 Read로 파일을 열 때만 로드되기 때문이다. jetbrains는 검색 전용으로 쓴다.
- 큰 파일은 전문을 Read하지 않는다. 검색으로 줄을 잡고 그 구간만 읽는다.
- `execute_terminal_command`, `execute_run_configuration`, `create_new_file`, `replace_text_in_file`, `rename_refactoring`, `reformat_file`은 훅(`jetbrains_mcp_guard.py`)이 차단한다. 파일 수정은 편집 도구로, 셸은 셸 도구로 한다.

