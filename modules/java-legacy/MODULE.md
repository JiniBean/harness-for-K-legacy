범위: 프로젝트 전용
구성: 규칙

# java-legacy

오래된 JDK(1.6·1.7·1.8)로 고정된 Java 프로젝트의 기능. 그 버전에서 쓸 수 없는 문법·API를 막는다.

## 사용자 안내

설명: 프로젝트가 쓰는 Java 버전에서 컴파일되지 않는 문법·API를 에이전트가 쓰지 않게 막고, 이미 있는 라이브러리와 프로젝트 로거만 쓰게 합니다.

물어볼 것

1. `[못 찾을 때]` (빌드·IDE 설정과 jar에서 버전 하나로 확실히 정해지지 않을 때만) 이 프로젝트의 Java 버전은 무엇인가요? 찾은 후보를 보여 준다
   - 정하는 것: 금지할 문법·API 범위
   - 선택지: 후보 중 하나 / 다른 버전 알려 줌
   - 추천: 후보 중 가장 낮은 버전
   - 모름/나중에: 찾은 후보 중 가장 낮은 버전(더 많이 막는 쪽)

묻지 않고 정하는 것

- 앱 JDK 경로(`[java] app_jdk_home`)·라이브러리 목록·로깅 API·명명 규칙: 설정과 기존 코드에서 찾은 값
- 디버그 출력 패턴(`[verify] debug_patterns`): `System.out.print`, `printStackTrace(`

## 감지 신호

- 빌드 설정의 소스·타깃 버전: `pom.xml`(`maven.compiler.source`, `<source>`), `build.gradle`(`sourceCompatibility`), Eclipse `.settings/org.eclipse.jdt.core.prefs`, IntelliJ `.idea/misc.xml`(`languageLevel`)
- 빌드 도구가 없는 프로젝트: `WEB-INF/lib` jar의 대상 버전, 서버(Tomcat·JEUS 등) 버전, 사용자 확인
- 사용 중인 JDK 경로 (`JAVA_HOME`, IDE 설정)

## 원칙

- 프로젝트의 Java 수준을 넘는 문법·API를 쓰지 않는다. 버전은 추측하지 않는다. 감지 결과가 하나로 확실하지 않을 때만 사용자에게 묻는다
- 라이브러리는 이미 있는 것만 쓴다. 새 jar 추가는 사용자 지시가 있을 때만
- 로깅은 프로젝트 로거로. 콘솔 출력은 쓰지 않는다
- 에이전트 도구(DB MCP, 스크립트)가 쓰는 JDK와 앱 JDK를 구분한다. 도구가 더 높은 버전을 요구하면 `[java] tool_jdk_home`을 따로 둔다

## 버전별 금지 (감지한 버전에 해당하는 줄을 프로젝트 규칙에 넣음)

| 수준 | 쓸 수 없는 것 (그보다 높은 버전 기능) |
|---|---|
| 1.6 | try-with-resources, diamond `<>`, switch 문자열, 멀티 catch, 숫자 밑줄, `java.nio.file`, `Objects` |
| 1.7 | Lambda, 메서드 참조, Stream, Optional, `java.time`, 인터페이스 default 메서드, `String.join` |
| 1.8 | `var`, `List.of`·`Map.of`, `Optional.isEmpty`, 모듈, `String` 신규 메서드(`isBlank`, `strip`, `repeat`) |

## 규칙 작성 항목 (set-up-harness가 채움)

| 항목 | 읽을 곳 |
|---|---|
| Java 수준 | 빌드·IDE 설정. 확실하지 않으면 사용자 (사용자 안내 1) |
| 앱 JDK 경로 | `[java] app_jdk_home` |
| 사용 가능한 라이브러리 | 의존성 목록, `WEB-INF/lib` |
| 로깅 API | 기존 코드의 로거 선언. 로거는 기본 패키지(업무 코드) 전체에서 호출 수를 세어 가장 많은 것 하나만 규칙에 쓴다. 프레임워크 패키지 표본으로 정하지 않는다 |
| 명명·문서 규칙 | 기존 코드 (클래스·메서드 명명, Javadoc 관례) |

결과 → Java 소스 폴더의 `AGENTS.md` 「코딩 규칙」 절

## 포함 파일

- verify 디버그 패턴 기본값 제안: `System.out.print`, `printStackTrace(` → `[verify] debug_patterns`

## 설정 키

`[java] app_jdk_home`, `tool_jdk_home`, `tool_jdk_fallbacks`, `[verify] debug_patterns`
