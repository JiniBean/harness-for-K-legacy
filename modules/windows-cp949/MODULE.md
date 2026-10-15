범위: 선택(추천: 전역)
구성: 훅, 규칙

# windows-cp949

한국어 Windows(CP949 + PowerShell 5.1)에서 셸 출력·스크립트 인코딩 문제를 막는 기능.

## 사용자 안내

설명: 한국어 Windows에서 에이전트가 실행한 명령의 한글 출력이 깨지거나 스크립트 파일 인코딩이 틀어지는 것을 막습니다. PowerShell 명령 앞에 UTF-8 설정을 훅이 자동으로 붙입니다.

물어볼 것

- 없음. 코드페이지와 PowerShell 버전은 명령으로 확인해 보여 준다

## 감지 신호와 포함 파일

- 감지 신호: Windows + 시스템 코드페이지 949 (`chcp` 결과), PowerShell 5.1
- 포함 파일: `hooks/shell_encoding_before.py`(한글 here-string 쓰기 차단), `hooks/shell_encoding_pretool.py`(PowerShell 명령 앞에 UTF-8 프리앰블 자동 추가) → `<.agents>/hooks/`, 그 등록 항목 `hooks.toml` → `<.agents>/hooks/hooks.toml`에 덧붙임. `<.agents>`는 전역 설치면 `~/.agents`, 프로젝트 설치면 `<프로젝트>/.agents`
- 등록: Cursor는 `beforeShellExecution`(before)·`preToolUse` `Shell`(pretool), Claude Code는 `PreToolUse` `PowerShell`. Codex에는 등록하지 않는다. 설치한 위치의 생성기(`gen_hook_configs.py --scope global` 또는 `--scope project`)로 등록하고, 전역에 이미 같은 훅이 있으면 프로젝트 `hooks.toml`에 넣지 않는다


## 설치되는 규칙

아래 절이 켠 프로젝트·전역 지시에 들어간다.

### Windows 셸 (CP949 + PowerShell 5.1 머신)

- 도구 파라미터의 한글·비ASCII는 리터럴 UTF-8로 쓴다. `\uXXXX` 이스케이프를 쓰지 않는다.
- 한글이 나올 수 있는 PowerShell 명령 앞에는 UTF-8 프리앰블이 필요하다. 훅이 자동으로 넣는다. 수동으로 넣을 때는 다음 줄을 쓴다.
  `chcp 65001 > $null; [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); $OutputEncoding = [Console]::OutputEncoding; $env:PYTHONIOENCODING = 'utf-8'`
- 한글이 들어간 여러 줄 스크립트는 편집 도구(Write)로 UTF-8 파일을 만든 뒤 실행한다. 셸의 `Set-Content`/`Out-File` here-string으로 만들지 않는다(훅이 차단).
- 셸 안에 `python -c`를 넣지 않는다. `.py` 파일을 만든 뒤 `python path\to\file.py`로 실행한다. PowerShell ParserError는 인코딩 문제가 아니므로 프리앰블을 다시 붙이지 말고 스크립트 파일로 나눈다.
- 코드 검색은 셸 `rg` 대신 Grep 도구나 IDE 검색을 쓴다.
- 출력이 `�ѱ�`처럼 깨져 보이면 인코딩 실패다. 깨진 stdout만 보고 파일·데이터 내용이 틀렸다고 단정하지 않는다.

