# webapp ↔ Generate 정션

값 표기 `{…}`는 `.agents/harness.toml` `[paths]`의 같은 키를 Read해서 쓴다.

목적: 로컬 WAS의 `/{nexacro_project}/…` 요청이 webapp 폴더 대신 `{nexacro_out}`(Generate 산출)을 보게 한다.

| 링크 | 대상 |
|------|------|
| `{project_root}\{webapp_app_link}` | `{nexacro_out}` |

종류: 디렉터리 정션(`mklink /J`). 심볼릭 링크(`/D`) 아님(관리자 권한 불필요).

## 승인

채팅에 단독 입력: `junction ok`

승인 없이 rename·mklink 금지.

## 절차 (승인 후)

1. `{webapp_app_link}`가 이미 정션이면(`run_generate.py --dry …`의 `junction: linked`) 경로만 보고하고 끝낸다.
2. 실제 폴더면 `<폴더명>_bak_YYYYMMDD`로 rename한다(삭제 금지).
3. 정션 생성:

```text
cmd /c mklink /J "{project_root}\{webapp_app_link}" "{nexacro_out}"
```

4. `dir`에 `<JUNCTION>`이 보이는지 확인한다.
5. 이후 `빌드해`는 기본으로 exploded 사본에도 복사한다(제외 시 `--no-sync-exploded`).

## 정션 vs exploded 복사

- 정션: webapp 이름 → Generate 산출(읽기 연결)
- exploded 복사(기본): Generate 파일을 `{nexacro_exploded}`에 복사. IDE Update 없이 로컬 WAS가 새 js를 서빙

## 되돌리기

정션만 삭제한다(`rmdir "{project_root}\{webapp_app_link}"`). 대상 Generate 폴더 내용은 삭제하지 않는다. 백업 폴더를 원래 이름으로 되돌린다.
