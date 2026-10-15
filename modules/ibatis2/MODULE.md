범위: 프로젝트 전용
구성: 규칙

# ibatis2

iBatis 2.x 매퍼를 쓰는 프로젝트의 기능. mapper 기능과 함께 켠다. mapper 기능의 공통 원칙에 iBatis 2 고유의 함정과 문법을 더한다.

## 사용자 안내

설명: iBatis 2 SQL 매퍼를 고칠 때 MyBatis 문법이 섞여 실행 오류가 나거나, 이름이 틀린 파라미터가 오류 없이 빈 값으로 바뀌어 엉뚱한 SQL이 도는 실수를 막는 규칙을 매퍼 폴더 `AGENTS.md`에 둡니다.

물어볼 것

- 없음

묻지 않고 정하는 것

- iBatis 버전·세션 파라미터 표·고정 스키마 테이블: 코드에서 찾은 내용 그대로 매퍼 폴더 `AGENTS.md`에 적는다
- 매퍼 반영 방식(서버 재기동 필요 여부): mapper 기능과 같이 정한다. 자동 재로딩 빈이 설정에 보이면 자동 반영, 아니면 재기동 필요

## 감지 신호

- `ibatis-*.jar` (2.x), `sqlMapConfig.xml`·`sql-map-config.xml`
- 매퍼 DTD `-//ibatis.apache.org//DTD SQL Map 2.0//EN`, 루트 `<sqlMap namespace="...">`
- `SqlMapClientFactoryBean`·`RefreshableSqlMapClientFactoryBean` (Spring 설정)

## 원칙

- MyBatis 문법을 섞지 않는다. 바인딩 `#p#`, 치환 `$p$`만 쓴다. `#{p}`·`${p}`와 `<if>`·`<foreach>`·`<choose>`는 iBatis 2에서 동작하지 않는다
- 없는 `$키$`는 에러 없이 빈 문자열로 치환된다. 스키마 접두 같은 치환 파라미터는 프로젝트 세션 키 표에 있는 이름만 쓴다. 오타는 실행 시 "잘못된 테이블 이름" 같은 엉뚱한 오류로만 드러난다
- 동적 태그는 `isNotEmpty`, `isEmpty`, `isEqual`, `isNotEqual`, `isNull`, `isNotNull`, `iterate`, `dynamic`
- 본문은 `<![CDATA[ ]]>`로 감싸는 기존 스타일을 따른다
- `parameterClass`·`resultClass`(`map`/`hashmap` 등)와 `remapResults="true"` 사용 여부는 같은 파일을 따른다
- 매퍼 자동 재로딩(`RefreshableSqlMapClientFactoryBean` 등)이 설정돼 있으면 수정 후 서버 재기동 안내를 하지 않는다

## 규칙 작성 항목 (set-up-harness가 채움)

| 항목 | 읽을 곳 |
|---|---|
| iBatis 버전 | jar 이름 |
| 매퍼 위치·이름 규칙 | 리소스 폴더 구조 (형식 `[모듈]_[업무]_SQL.xml`) |
| 세션 키 표 (키 · 표기 · 용도) | 세션 객체에 값을 넣는 코드, 기존 매퍼의 반복 `$키$`·`#키#` |
| 스키마 고정 규칙 | 공통 스키마 테이블을 쓰는 기존 SQL |
| 자동 재로딩 여부 | Spring의 SqlMapClient 빈 설정 |

결과 → 매퍼 폴더의 `AGENTS.md` (mapper 기능 결과에 이어서)

## 포함 파일

- 없음. 검사는 mapper 기능의 `verify.md`(C_SQL)를 그대로 쓴다

## 설정 키

없음 (mapper 기능의 키를 쓴다)
