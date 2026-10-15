# C_OZ (OZ 리포트)

| ID | 방법 | FAIL |
| :--- | :--- | :--- |
| C_OZ | 부모가 먼저 `python .agents/scripts/oz_tool.py check <변경 ozr/odi>`로 구조 검사(헤더·중복 CR·odi CRLF·동일 사본·고아 라벨·XML). 이어서 서브에이전트 `ozbot`이 아래 정적 검사. `.ozr`/`.odi` 변경 없으면 SKIP | `oz_tool check` FAIL(수정 전부터 FAIL이던 항목 제외), 짝 파일·폰트 스크립트·OZPARAMS·스크립트 휴리스틱 |

변경 `.ozr` / `.odi`만 정적으로 검사한다. Viewer·서버 실행·PDF 렌더·시각 비교 없음. DB의 리포트 설정값·화면의 리포트 호출 대조는 범위 밖.

## 파싱

- `.ozr`: 앞쪽 `OZR` 바이너리 헤더 뒤 `<?xml`부터 UTF-8 XML
- `.odi`: `<?xml`부터 UTF-8 XML
- `SCRIPTCODE` / `EVENTVALUE`: `~OZ#CRLF`→개행, `~OZ#TAB`→탭, HTML 엔티티 언이스케이프 후 검사

## 짝 파일

- 각 `.ozr`의 짝 `.odi`: 같은 폴더의 같은 basename, 또는 `.ozr` 안 `ODINAME`(확장자 유무 모두 허용). 없으면 FAIL
- `.odi`만 바뀌고 같은 basename `.ozr`가 없으면 FAIL. 있으면 그 `.ozr` 기준으로 아래를 검사

## 폰트 스크립트 누락

- 폰트 파라미터 이름은 리포트 폴더 `AGENTS.md` 「폰트 동적 적용」 절. 없으면 이 검사(폰트 스크립트 누락)는 SKIP(사유: 폰트 파라미터 정의 없음)
- `.ozr`에 그 폰트 파라미터 참조가 있으면 폰트 동적 적용 리포트로 본다
- 후보 도형: `ONESHAPE`/`OZTABLELABEL` 중 `FONTNAME`이 있고 이미지가 아니며(`IMGSTYLE`, `PAINTTYPE="2"` 제외) 텍스트 성격(`COLNAME`, 본문 caption, `SCRIPTCODE`/`EVENT` 중 하나)인 것. 빈 스페이서 제외
- 후보의 `SCRIPTCODE`·`EVENTVALUE`에 `setattr("fontname", …)` 또는 `SetFontName(`가 없으면 FAIL. 사유에 도형 `NAME` 나열

## OZPARAMS 설정 누락

- `.ozr`의 `#OZPARAMS.P_…#` / `GetDataSetValue("OZPARAMS.P_…")` 참조를 모은다
- 짝 `.odi`의 `OZPARAMS` 데이터셋 필드에 없으면 FAIL. 사유에 누락 파라미터명

## 스크립트 정적 휴리스틱

각 `SCRIPTCODE` / `EVENTVALUE`에 대해:
1. 줄마다 `//`부터 줄 끝까지 제거
2. `/* … */` 블록 제거
3. `{`·`}` 개수 불일치 → FAIL
4. `"` 개수 홀수 → FAIL
5. 블록 안 변수 선언 금지: 중첩 깊이 1 이상인 줄에 `string|double|int|boolean|long` + 식별자 + `;` 선언이 있으면 FAIL(Viewer가 `Parse Error at "string"`으로 실패함). 선언은 첫 `{` 전에만 허용

문자열 리터럴 안의 `//`는 구분하지 않는다. 의미·런타임·OZ 엔진 문법 전체는 검사하지 않는다.

## 판정

- 변경 없음 → `SKIP · C_OZ · .ozr/.odi 변경 없음`
- FAIL이 있으면 파일별로 `FAIL · C_OZ · <파일> <사유>`
- 모두 통과하면 `PASS · C_OZ · <대표 .ozr>`
