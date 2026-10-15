# C_SQL + L3 (매퍼 SQL)

| ID | 방법 | FAIL |
| :--- | :--- | :--- |
| C_SQL | 변경 매퍼 statement를 읽고(서브에이전트 `sqlbot`), 개발 DB에서 SELECT 스모크·필요 시 fixture INSERT(부모) | SQL·fixture 실패, 화면·SQL이 가정한 조건과 결과가 명확히 어긋남(L3) |

## 처음 쓸 때 확인

검사를 시작할 때, 매퍼 폴더 `AGENTS.md`의 세션 파라미터 표에 회사·스키마 키가 있는데 `[test] dev_schema`·`dev_corp`가 비어 있으면 먼저 채운다. 회사·스키마 키가 없는 프로젝트는 비어 있는 것이 정상이므로 묻지 않는다.

1. 한 문장으로 설명한다: "바꾼 SQL을 개발 DB에서 실제로 조회해 보려면 어느 스키마·회사 데이터로 볼지 정해야 하는데 아직 정해지지 않아, 검사에 쓸 스키마와 회사 ID를 알려 주셔야 합니다"
2. 개발 DB에서 SELECT로 후보(스키마·회사 ID 목록, 결과 행 수 제한)를 보여 주고 고르게 한다. 조회가 안 되면 값을 직접 받는다
3. 고른 값을 `.agents/harness.toml` `[test] dev_schema`·`dev_corp`에 편집 도구로 적는다(UTF-8, BOM 없음. 절이 없으면 파일 끝에 추가). 이어서 아래 흐름을 진행한다

## 컨텍스트

- 스키마 `{test.dev_schema}`, 회사 ID `{test.dev_corp}`
- 테이블·컬럼: 프로젝트 DB 스키마 기준 문서 또는 DB 조회 도구. 추측 금지
- DB는 개발 DB만. fixture INSERT는 허용, fixture DELETE 금지. 쓰기는 프로젝트 DB 승인 절차를 따른다

## fixture 키

- 조회 키 접두: `{person.alias}` + `YYMMDD` (당일 사용분을 LIKE로 확인하고 있으면 `…1`, `…2` 접미)
- 내부 키: 같은 회사 최근 행 패턴에 맞춰 생성. UNIQUE 충돌 시 숫자만 바꿈
- 테이블별 필수 컬럼·값 규칙: 매퍼 폴더 `AGENTS.md` 「verify fixture」 절. 없으면 fixture INSERT 검사(흐름 3)는 SKIP(사유: fixture 표 없음)

## 흐름

1. 변경 statement 또는 화면이 가정하는 조회 조건을 파악한다
2. SELECT만으로 충분하면 fixture 없이 실데이터 키로 스모크(결과 행 수 제한). 0건은 FAIL이 아니다
3. DML이거나 건 단위 검증이면 최소 컬럼 fixture를 INSERT한다. DELETE 안 함. 결과에 키를 기록한다
4. L3: 화면·SQL이 가정한 조건으로 SELECT → 문법·컬럼 오류는 FAIL. fixture 키가 있는데 조건에 안 걸리면 FAIL 후보
5. UPDATE/DELETE 스모크는 fixture 키 WHERE만. 실데이터 행 금지
6. 동적 태그 때문에 치환이 불가능하면 SKIP + 사유
