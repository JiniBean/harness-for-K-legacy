범위: 프로젝트 전용
구성: 규칙

# egov-spring

전자정부 표준프레임워크(eGovFrame)·Spring MVC 계층 구조 프로젝트의 기능. 컨트롤러 → 서비스 → DAO → 매퍼 흐름을 규칙으로 만든다.

## 사용자 안내

설명: 에이전트가 화면 요청 주소에서 컨트롤러 → 서비스 → DAO → SQL 매퍼까지 호출을 끝까지 따라가 읽고, 새 코드를 같은 패키지의 기존 코드와 같은 이름·구조로 쓰게 합니다. Spring·프레임워크 설정 파일은 지시 없이 고치지 않습니다.

물어볼 것

- 없음

묻지 않고 정하는 것

- 기본 패키지(`[org] base_package`)·클래스 이름 규칙·수정 금지 설정 파일: 코드에서 찾은 내용 그대로 Java 소스 폴더 `AGENTS.md`에 적는다

## 감지 신호

- jar·의존성: `egovframework.rte.*`, `org.egovframe.rte.*`, `spring-webmvc-*`, `spring-context-*`
- 설정: `context-*.xml`, `dispatcher-servlet.xml`, `egovframework` 패키지
- 클래스 패턴: `*Controller`/`*Ctrl`, `*Service` + `*ServiceImpl`, `*DAO`/`*Dao`, `EgovAbstractDAO`·`EgovAbstractMapper` 상속

## 원칙

- 새 클래스는 같은 패키지의 인접 파일을 따른다(명명, 상속 대상, 주입 방식)
- 호출 체인을 끝까지 따라간다: 화면 요청 URL → 컨트롤러 → 서비스 인터페이스 → 구현 → DAO → 매퍼 statement
- 화면 모듈과 서비스 모듈이 같다고 가정하지 않는다. 다른 모듈의 서비스를 주입해 쓰는 경우가 있다
- statement id 문자열은 매퍼 XML `id`와 정확히 같아야 한다
- 세션·회사 파라미터를 넣는 방식이 여럿이면 같은 모듈의 기존 방식을 따르고 섞지 않는다
- Spring·프레임워크 설정 파일은 사용자 지시 없이 바꾸지 않는다

## 규칙 작성 항목 (set-up-harness가 프로젝트를 읽어 채움)

| 항목 | 읽을 곳 |
|---|---|
| eGovFrame·Spring 버전 | jar 이름, 의존성 |
| 기본 패키지와 계층 폴더 구조 | 소스 트리 → `[org] base_package` |
| 클래스 명명 (Ctrl/Controller, Impl 대소문자, Dao/DAO) | 기존 클래스 |
| URL 매핑 형식 | `@RequestMapping` 사용 위치 |
| 컨트롤러 메서드 시그니처·반환 타입 | 기존 컨트롤러 |
| 주입 방식 (`@Resource(name=…)`, `@Autowired`) | 기존 서비스·DAO |
| DAO 기반 클래스와 호출 패턴 | DAO 상속 대상, `list`/`insert` 호출 |
| 세션 값 꺼내는 방법 | 컨트롤러·서비스 코드 |
| 모듈 간 서비스 재사용 사례 | 다른 모듈 서비스를 주입하는 컨트롤러 |
| 수정 금지 설정 파일 | `context-*.xml` 등 |

결과 → Java 소스 폴더의 `AGENTS.md` 「계층 구조와 명명」「호출 체인」「DAO 호출 패턴」「세션 파라미터」 절

## 포함 파일

- 없음. 매퍼 쪽 규칙은 mapper·ibatis2 기능, 읽기 추적은 mapper 기능의 `sqlbot`

## 설정 키

`[org] base_package`
