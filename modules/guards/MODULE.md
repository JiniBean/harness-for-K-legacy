범위: 필수(프로젝트)
구성: 훅

# guards

프로젝트에 항상 설치하는 보안 훅. 위험한 셸 명령과 비밀·보호 경로 접근을 막고, 훅·등록 파일·`[guard]` 설정은 사용자가 보호 해제 승인 키워드를 단독 입력한 턴에만 고치게 한다. 끌 수 없다.

## 사용자 안내

설명: 에이전트가 계정·비밀번호 파일을 읽거나, 셸로 위험한 명령을 돌리거나, 안전장치(훅) 자체를 고치는 것을 막습니다. 훅을 고쳐야 할 때는 에이전트가 고칠 파일 목록을 먼저 보여 주고, 채팅에 보호 해제 승인 키워드 한 단어만 입력하면 그 한 번만 풀립니다.

물어볼 것: 보호 해제 승인 키워드는 set-up-harness 2단계(형상관리)에서 `[항상]` 묻는다(`[guard] hook_approval`, 기본 `gohook`).

## 포함 파일과 설치 위치 (프로젝트만)

| 저장소 | 프로젝트 |
|---|---|
| `hooks/shell_guard.py` | `.agents/hooks/` (셸 명령 차단, 필수) |
| `hooks/protected_path_guard.py` | `.agents/hooks/` (비밀·보호 경로 읽기·쓰기 차단, 필수) |
| `hooks/hook_edit_approve.py` | `.agents/hooks/` (보호 해제 승인 키워드 처리) |
| `hooks.toml` | `.agents/hooks/hooks.toml`의 뼈대. 다른 기능의 `hooks.toml` 조각을 이 뒤에 이어 붙인다 |
| `hooks/tests/` | `.agents/hooks/tests/` |
| `harness.example.toml` | `.agents/harness.toml`의 뼈대(프로젝트 설정 예시) |
| `core/hook_io.py`, `core/gen_hook_configs.py` (저장소 공통) | `.agents/hooks/`에 링크 |

- 훅 등록: `python .agents/hooks/gen_hook_configs.py --scope project --tools <쓰는 도구>`
- `shell_guard.py`·`protected_path_guard.py`는 어떤 `hooks.toml`로 생성하든 등록 파일에서 빠지면 생성을 거부한다(`hook_io.CORE_REQUIRED`)

## 설정 키

`[guard] hook_approval`, `block_hosts`, `ftp_hosts`, `shell_block_patterns`(다른 기능의 `harness.fragment.toml`이 더함)
