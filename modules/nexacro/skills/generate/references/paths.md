# Generate 경로

값 표기 `{…}`는 `.agents/harness.toml` `[paths]`의 같은 키를 Read해서 쓴다. 상대경로는 프로젝트 루트 기준. 프로젝트 안 경로(`nexacro_adl`, `nexacro_src`)는 set-up-harness가 채우고, PC에 따라 다른 경로(`nexacro_generator`, 결과 폴더, exploded)는 처음 `빌드해` 때 generate 스킬이 묻고 채운다(SKILL.md 「처음 쓸 때 확인」).

## [paths] 키

| 키 | 필수 | 내용 |
|----|------|------|
| `nexacro_generator` | 필수 | `nexacrogenerator.exe` 절대경로. 설치 버전 폴더에 따라 다르므로 하드코딩하지 않는다 |
| `nexacro_adl` | 필수 | Application 정의 `.xadl` |
| `nexacro_src` | 필수 | xfdl·xjs 소스 루트(서비스 폴더의 부모) |
| `nexacro_out_parent` | 필수 | generator `-O` |
| `nexacro_out` | 필수 | 실제 산출 루트. 보통 `{nexacro_out_parent}\{nexacro_project}` |
| `nexacro_project` | 선택 | generator `-P`(앱 이름). 없으면 `{nexacro_out}`의 폴더 이름 |
| `war_exploded` | 선택 | IDE artifact 출력 루트(예: IntelliJ `out/artifacts`, `target/artifacts`) |
| `nexacro_exploded` | 선택 | exploded 안의 앱 폴더. 없으면 `{war_exploded}\<프로젝트 폴더명>_war_exploded\{nexacro_project}` |
| `webapp_app_link` | 선택 | webapp 안의 앱 폴더(정션 위치). 상태 표시에만 쓴다 |

로그: `{project_root}\.agents\tmp\nexacro_gen.log`(고정).

## 명령 형태

```text
{nexacro_generator}
  -A "{nexacro_adl}"
  -O "{nexacro_out_parent}"
  -P {nexacro_project}
  -F "{nexacro_src}\<서비스폴더>\<폼명>.xfdl"
  -L "{project_root}\.agents\tmp\nexacro_gen.log"
```

산출: `{nexacro_out}\<서비스폴더>\<폼명>.xfdl.js`

`-F`와 `-S`·`-AO`·`-T`·`-MO`는 함께 쓸 수 없다(Nexacro 14 generator 기준. 다른 버전은 `nexacrogenerator.exe` 도움말로 확인).

## Generate 산출 / 정션 / exploded 사본

| 대상 | 경로 | 역할 |
|------|------|------|
| Generate 산출 | `{nexacro_out}` | generator 출력 |
| webapp 정션 | `{webapp_app_link}` → `{nexacro_out}` | IDE가 webapp을 읽을 때 Generate 산출을 봄 |
| exploded 앱 폴더 | `{nexacro_exploded}` | 로컬 WAS가 실제로 서빙하는 별도 사본 |

정션만으로는 exploded 사본이 바뀌지 않는다. `run_generate.py`는 기본으로 Generate 산출을 exploded 앱 폴더의 같은 상대경로에 복사한다. 제외할 때만 `--no-sync-exploded`.
