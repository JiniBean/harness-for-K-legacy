---
name: generate
description: >-
  Nexacro HTML5 Generate(nexacrogenerator CLI). 트리거: 빌드해.
  폼: 빌드해 <폼명> / 여러 폼. 서비스 폴더: 빌드해 <서비스폴더>. 전체: 빌드해 all.
  공통 스크립트(.xjs)도 같다(빌드해 <xjs명>).
  기본: Generate 후 war exploded에 자동 복사. 제외: 톰캣 빼 / 싱크하지마 / --no-sync-exploded.
  --dry는 명령만 출력. 정션 셋업은 junction ok 승인 후.
---

# Nexacro Generate (빌드해)

값 표기 `{…}`는 `.agents/harness.toml` `[paths]`의 같은 키를 Read해서 쓴다. 키 목록은 [references/paths.md](references/paths.md).

흐름: `.xfdl`·`.xjs` → nexacrogenerator CLI → `{nexacro_out}` 아래 `*.xfdl.js`·`*.xjs.js` → (기본) war exploded 사본에 같은 상대경로로 복사.

사용자가 `빌드해 …`로 부른다. 다른 스킬(테스트·티켓 구현 후 검증 등)이 변경된 `*.xfdl`·`*.xjs`에 대해 같은 스크립트를 부를 수 있다. 공통 `.xjs`는 그것을 include한 폼을 다시 빌드해도 갱신되지 않으므로 xjs 자체를 빌드한다.

## 처음 쓸 때 확인

실행 전에 `.agents/harness.toml` `[paths]`의 필수 키(`nexacro_generator`, `nexacro_adl`, `nexacro_src`, `nexacro_out_parent`, `nexacro_out`)를 Read한다. 빈 키가 있으면 실행하지 않고 먼저 채운다. 설치 때는 프로젝트 안 경로(`nexacro_adl`, `nexacro_src`)만 채워 두므로 처음에는 보통 generator와 결과 폴더가 비어 있다.

1. 한 문장으로 설명한다: "화면을 HTML5로 빌드하려면 PC에 설치된 Nexacro Generate 도구와 빌드 결과를 둘 폴더를 알아야 하는데 아직 정해지지 않아, 경로를 알려 주셔야 합니다"
2. 빈 키마다 묻는다. 사용자가 경로를 모르면 찾아볼 폴더(예: Nexacro 설치 폴더)를 말해 달라고 하고, 그 폴더 아래에서만 `nexacrogenerator.exe`·기존 `*.xfdl.js` 산출 폴더를 찾아 보여 준다. 드라이브 전체를 뒤지지 않는다
3. 로컬 WAS가 exploded 사본을 서빙하면 그 경로(`war_exploded` 또는 `nexacro_exploded`)도 함께 묻는다. 모르면 비워 둔다(복사는 `n/a`로 보고)
4. 확인받은 값을 `.agents/harness.toml` `[paths]`에 편집 도구로 적는다(UTF-8, BOM 없음. 절이 없으면 파일 끝에 추가). `[guard]` 절은 건드리지 않는다
5. 요청받은 `빌드해`를 이어서 실행한다

## 금지

- Studio·런타임 실행 파일(`nexacro.exe`, `nexacrostudio*.exe`) 실행
- `.xprj`·`.xadl`·`.xfdl`를 셸 `start`·`Invoke-Item`으로 열기
- `nexacrogenerator.exe` 인자를 직접 조합해 실행. 항상 `run_generate.py`를 거친다
- webapp으로 대량 파일 복사. webapp 연결은 정션([references/junction.md](references/junction.md))

## Read 순서

1. 이 SKILL.md
2. [references/paths.md](references/paths.md)
3. 정션 요청 시 [references/junction.md](references/junction.md)

## 트리거

| 입력 | 동작 |
|------|------|
| `빌드해 <폼명>` | `-F` 해당 xfdl 1건 + exploded 복사 |
| `빌드해 <폼명1> <폼명2>` | `-F` 여러 건(`,` 연결) + exploded 복사 |
| `빌드해 <xjs명>` | `-F` 해당 xjs 1건 + exploded 복사 |
| `빌드해 <서비스폴더>` | `-S <서비스폴더>` + exploded 복사 |
| `빌드해 all` | Application 전체 + exploded 복사 |
| `빌드해 톰캣 빼 …` / `빌드해 싱크하지마 …` | Generate만(`--no-sync-exploded`) |
| `빌드해 --dry …` | 명령만 출력, 실행 안 함 |
| `junction ok` | [junction.md](references/junction.md) 1회 셋업만 |

토큰 판정: `{nexacro_src}/{토큰}/` 디렉터리가 있으면 서비스(`-S`). 없으면 `**/{토큰}.xfdl`, 그다음 `**/{토큰}.xjs`를 찾아 `-F`.

## exploded 복사 (기본 ON)

| 규칙 | 동작 |
|------|------|
| 기본 | Generate 성공 후 산출 `.xfdl.js`·`.xjs.js` → exploded 앱 폴더(paths.md 「exploded 앱 폴더」)에 복사 |
| 제외 문구 | `톰캣 빼`, `싱크하지마`, `exploded 빼`, `sync 하지마` 등 → `--no-sync-exploded` |
| dry | 복사 안 함 |

`빌드해`만 받으면 플래그 없이 호출한다(= 복사 기본). 제외 문구가 있을 때만 `--no-sync-exploded`. `--sync-exploded`는 호환용(붙여도 동작 같음).

## 실행

프로젝트 루트에서 실행한다(다른 위치면 `--project-root <루트>`).

```text
python .agents/skills/generate/scripts/run_generate.py <폼명>
python .agents/skills/generate/scripts/run_generate.py --no-sync-exploded <폼명>
python .agents/skills/generate/scripts/run_generate.py --dry <폼명>
python .agents/skills/generate/scripts/run_generate.py <서비스폴더>
python .agents/skills/generate/scripts/run_generate.py all
```

## 성공 판정

- 스크립트 exit 0
- stdout의 산출 `.xfdl.js`·`.xjs.js` 경로·크기·mtime 보고
- `-F`면 대상 js마다 존재·갱신 확인(`WARN: mtime not newer`가 나오면 그 파일을 보고에 적음)
- 복사가 켜져 있으면 exploded 경로에도 같은 파일 존재(`synced:`, `sync_count:`)
- exit 2 또는 `harness.toml [paths] … missing`: generator·ADL 등 경로 없음 → 「처음 쓸 때 확인」으로 값을 채운 뒤 다시 실행

## 보고 형식

```markdown
## 빌드해 — {모드}

| 항목 | 값 |
|------|-----|
| 모드 | file / service / all / dry |
| 대상 | … |
| exit | 0 |
| 산출 | `{nexacro_out}\…` |
| exploded 복사 | done / skipped (--no-sync) / n/a |
| 정션 | linked / missing / real_dir / n/a |
```

기본 복사 덕분에 IDE의 Update(재배포) 없이 로컬 WAS가 새 js를 서빙한다. 정션은 webapp 읽기 연결용([junction.md](references/junction.md)).
