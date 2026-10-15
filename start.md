# 설치 시작 (start.md)

## 사람용

- 필요한 것: Python 3.11+, Git. Windows는 개발자 모드(설정 → 시스템 → 개발자용)를 켜 두면 링크가 만들어집니다
- 하네스를 설치할 프로젝트를 Claude Code·Cursor·Codex로 열고 에이전트에게 「`<저장소 폴더>/start.md` 를 읽고 따라 이 프로젝트에 하네스를 설치해줘」라고 말합니다
- 에이전트가 묻는 것에만 답하면 됩니다. 모르는 질문은 「모름」이라고 답하면 추천값으로 둡니다
- 확인하기 전에는 파일을 쓰지 않습니다

## 에이전트용

이 파일은 요약하지 말고 원문 그대로 읽는다. 명령의 옵션 하나가 빠지면 설치 결과가 달라진다.

`<repo>`는 이 저장소를 받은 폴더, `<project>`는 하네스를 설치할 프로젝트 루트다.

1. 저장소 위치를 정한다
   - 이 파일을 로컬에서 읽고 있으면 그 폴더가 `<repo>`다
   - 아니면 받을 위치를 사용자에게 묻고 `git clone https://github.com/JiniBean/harness-for-K-legacy.git <위치>`
2. 사용자가 쓰는 도구를 묻는다: Claude Code / Cursor / Codex(여러 개 가능). 답을 `--tools claude,cursor,codex` 형식으로 바꾼다
3. 환경을 확인한다
   - `python --version`이 3.11 이상인지. 아니면 멈추고 알린다
   - Windows면 링크 권한. 없으면 폴더 링크는 정션으로 대신 만들어지고 파일 링크는 `error`가 난다. `error`가 나오면 개발자 모드를 켜고 다시 실행하라고 안내한다
4. 전역 기반을 설치한다
   1. `python <repo>/install/install.py global --tools <도구> --dry-run`을 실행하고 무엇이 생기는지 요약해 보여 준 뒤 확인받는다
   2. 확인받으면 `--dry-run` 없이 실행한다
   3. `conflict`가 하나라도 있으면 멈추고 그 항목(기존 파일·다른 곳을 가리키는 링크)을 사용자에게 보여 준다. 덮어쓰지 않는다
5. `<project>`에서 하네스 시작 절차(set-up-harness)를 실행한다
   - Claude Code는 4번에서 만든 스킬 링크를 새 세션부터 읽는다. 지금 세션의 스킬 목록에 set-up-harness가 없으면 `<repo>/install/set-up-harness/SKILL.md`를 Read하고 그 절차를 따른다
   - 이 단계가 프로젝트 파악 → 형상관리 → 쓸 기능 고르기 → 기능별 세부 설정 → 설치 → 점검을 진행하고, 끝에서 `install.py project`와(전역 기능을 골랐으면) `install.py global` 재실행까지 한다
6. set-up-harness의 마지막 보고(만든 파일, 나중에 필요한 것, 사용자가 할 일)를 그대로 사용자에게 전한다

## 참고: install.py

```text
python install/install.py global  --tools claude,cursor,codex [--home DIR] [--dry-run]
python install/install.py project <프로젝트 루트> --tools claude,cursor,codex [--dry-run]
```

- `global`: 전역 기반
  - 링크: `core/harness_config.py` → `~/.agents/scripts/`, `core/harness-guide.md` → `~/.agents/docs/`, `core/hook_io.py`·`core/gen_hook_configs.py` → `~/.agents/hooks/`, `install/set-up-harness` → `~/.agents/skills/`
  - `~/.agents/harness.toml`의 `[harness] repo_dir`에 저장소 위치 기록
  - `--tools claude`: `~/.agents/AGENTS.md`가 있으면 `~/.claude/CLAUDE.md`에 `@~/.agents/AGENTS.md` 줄 추가. `~/.agents/skills/`의 스킬마다 `~/.claude/skills/<이름>` 링크
  - `--tools cursor`: 링크 없음. `~/.agents/AGENTS.md`가 있으면 User Rules에 붙여 넣기 안내
  - `--tools codex`: `~/.agents/AGENTS.md`가 있으면 `~/.codex/AGENTS.md` 링크
  - 전역 훅 등록은 set-up-harness가 `~/.agents/hooks/hooks.toml`을 채운 뒤 `python ~/.agents/hooks/gen_hook_configs.py --scope global`로 한다. 전역 등록 파일에서 `~/.agents/hooks/` 항목만 바꾸고 사용자가 따로 등록한 훅은 남긴다
- `project`: set-up-harness가 채운 프로젝트 `.agents/`를 도구에 연결
  - `--tools claude`: `.claude/skills`, `.claude/agents`, `.mcp.json` 링크
  - `--tools cursor`: `.cursor/agents`, `.cursor/mcp.json` 링크
  - `--tools codex`: `.codex/agents/*.toml` 생성, `.codex/config.toml`의 관리 블록(`[mcp_servers]`)만 교체
- `--dry-run`: 출력만, 파일 변경 없음
- 기존 파일·다른 곳을 가리키는 링크는 덮어쓰지 않고 `conflict` 보고, 종료 코드 1. 다시 실행해도 안전(맞는 항목은 `ok`)
- 링크는 심볼릭 링크. 권한이 없으면 폴더는 정션으로 대체, 파일은 `error`

## 참고: 저장소 구성

```text
core/       공통 런타임·문서 (설정 로더, 훅 입출력 hook_io, 훅 등록 생성기, harness-guide, 설정 예시)
install/    install.py, set-up-harness (시작 절차 스킬)
modules/    기능별 설치 단위. 기능마다 MODULE.md(감지 신호·원칙·규칙 작성 항목·설정 키)
start.md    이 파일
```
