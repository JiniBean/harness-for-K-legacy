# OZ Report 규칙

OZ Report 소스(`.ozr` 리포트, `.odi` 데이터 정의)를 고칠 때 적용한다. set-up-harness는 이 내용과 아래 「프로젝트에서 채울 항목」을 합쳐 프로젝트 리포트 폴더의 `AGENTS.md`를 만든다.

## 1. 작업 원칙

- 리포트 작업을 시작할 때 프로젝트에 대상 `.ozr`가 없고 `.agents/harness.toml` `[paths] oz_src`도 비어 있으면, 리포트 원본 폴더를 사용자에게 묻고 그 값을 `[paths] oz_src`에 적은 뒤 진행한다(드라이브 전체 검색 금지, 사용자가 알려 준 폴더만 확인)
- ozr·odi의 속성·파라미터·데이터셋 바인딩을 추측하지 않는다. 같은 모듈의 비슷한 `.ozr`·`.odi`를 먼저 대조한다
- 출력 값을 추가할 때 새 `ONESHAPE`·`OZTABLELABEL`을 만들지 않는다. 그 값이 이미 표시되는 라벨의 `SCRIPTCODE`에서 `setattr("caption", ...)`으로 문자열을 합친다
- 새 `P_*` 파라미터는 짝 `.odi`의 `<OZXMLSET NAME="OZPARAMS">`에도 `DATAFIELD`로 선언한다. 속성 집합이 파일마다 다르므로 같은 파일의 인접 줄을 복사한다
- 한 화면이 라디오·회사 옵션에 따라 여러 `.ozr`로 분기하면, 그 화면에서 옵션이 보이는 모든 `.ozr`에 넣는다. 요청 캡처에 찍힌 리포트 하나로 범위를 좁히지 않는다

## 2. 파일 구조 (바이너리 취급)

- `.ozr`: 앞 24바이트가 `OZR`로 시작하는 바이너리 헤더이고, 바로 뒤(바이트 24)에 UTF-8 XML(`<?xml`)이 붙는다. 줄바꿈은 CRLF와 LF가 섞인 경우가 많다
- `.odi`: 헤더 없는 XML. 줄바꿈은 CRLF로 일관된다
- 텍스트로 저장하면 헤더 소실·줄바꿈 정규화가 일어나고 Designer가 파일을 거부한다

## 3. 수정 방법 (바이트 패치)

- 편집 도구(Write·Edit·StrReplace)와 셸 텍스트 쓰기(리다이렉트, `Set-Content`·`Out-File`)로 `.ozr`·`.odi`를 저장하지 않는다. oz 기능 훅이 차단한다
- 바이트 단위로 속성만 바꾼다. XML 파싱 후 재직렬화, `newline` 변환, UTF-16, BOM 추가 금지
- 공용 도구 `.agents/scripts/oz_tool.py`를 쓴다. 패치 스크립트에서 헤더 분리·태그 찾기·속성 삽입을 새로 짜지 말고 import한다
  - 함수: `read`, `write`, `find_tag`, `get_attr`, `set_attr`, `delete_element`, `escape_script`, `unescape_script`
  - `set_attr`는 `/>`로 닫힌 태그에도 속성을 올바르게 넣는다. 직접 짠 태그 처리는 `/>` 태그를 깨뜨리기 쉽다
  - `write`는 디스크의 헤더와 다르면 쓰기를 거부하고, 크기 변화량을 출력한다
- 조사: `python .agents/scripts/oz_tool.py dump <ozr> [--name N] [--grep RE]`로 컴포넌트·밴드·`SCRIPTCODE`(풀어 쓴 형태)를 본다. 이전 리비전과 비교할 때는 VCS에서 꺼낸 사본을 `.agents/tmp/`에 두고 둘 다 dump한다
- 패치 스크립트는 `.agents/tmp/*.py`로 만든 뒤 `python <파일>`로 실행한다. `python -c` 금지
- 패치 후: 앞 24바이트 동일, 크기 증가분 = 삽입 바이트 × 횟수. 어긋나면 VCS에서 원본을 되돌린 뒤 다시 패치한다

## 4. SCRIPTCODE

- `SCRIPTCODE`(OZ Script)와 `EVENT`·`EVENTVALUE`(JavaScript)를 섞지 않는다. `setattr(...)`는 `SCRIPTCODE`에만 쓴다
- 속성값 인코딩: 줄바꿈 `~OZ#CRLF`, 탭 `~OZ#TAB`, 따옴표 `&quot;`(XML 이스케이프). `oz_tool.escape_script`·`unescape_script`가 이 변환을 한다
- `SCRIPTCODE`는 같은 모듈의 Designer 저장본에서 복사해 고친다
- 변수 선언(`string`·`double`·`int`·`boolean`·`long`)은 SCRIPTCODE 맨 위(첫 `{` 전)에만 둔다. `if`·`else`·`for` 블록 안에 두면 Viewer가 `Parse Error at "string"[Ln,C1]` 형태로 실패한다. 블록 안에서는 대입만 한다

## 5. 패치 후 필수 자가 점검

바이트 패치 직후, 정적 검증(`/verify`) 전에 `python .agents/scripts/oz_tool.py check <ozr> <odi>`를 실행해 PASS를 확인한다. 기존 리포트 중 일부는 원래 FAIL이므로 패치 전에 `check`를 먼저 돌려 기준 결과를 남기고 패치 후 결과와 비교한다.

`check`가 한 번에 보는 항목:

- `.ozr` 헤더: `OZR` 매직, `<?xml`이 바이트 24
- `.ozr` 본문에 `\r\r\n`(중복 CR) 없음
- `.odi` 줄바꿈이 CRLF로 일관(LF 단독은 텍스트 도구로 저장된 손상 신호)
- 같은 부모 아래 동일한 컴포넌트 사본 없음(페이지마다 같은 이름이 있는 것은 정상). 다른 리포트에서 컴포넌트를 이식·복사했을 때 생긴다
- `TABLEINDEX` 속성을 가진 `OZTABLELABEL`이 `OZTABLESTATIC`의 자식인지. 라벨만 옮기고 부모 `OZTABLESTATIC`을 안 옮기면 밴드 바로 아래 고아로 남는다
- XML 적격성(줄·칸 위치)

위 항목 중 하나라도 걸리면 Designer가 대화상자 없이 종료된다(로딩 중 액세스 위반 `0xc0000005`). XML 파싱은 정상으로 나오므로 XML 파서 성공만으로 안심하지 않는다.

## 6. 완료 검증

- 리포트 변경 후 `/verify`의 C_OZ(oz 기능 `verify.md`). 정적 검사는 서브에이전트 `ozbot`(검사만, 수정 없음)
- Viewer·HTML5 실행 확인은 부모가 한다

## 7. 공식 문서

공식 문서(OZ Report Viewer 개발): https://www.forcs.com/en/documentation-rv_dev/welcome_to.htm — 리포트 속성·`SCRIPTCODE`는 이 문서보다 같은 모듈의 Designer 저장본이 우선이다. set-up-harness가 프로젝트 OZ 버전에 맞는 주소가 따로 있으면 바꾼다.

## 프로젝트에서 채울 항목

set-up-harness가 프로젝트를 열어 확인한 뒤 채운다. 추측으로 채우지 않는다.

| 항목 | 확인할 곳 |
|------|-----------|
| 리포트 소스 폴더와 하위 구조(모듈 그룹별 `.ozr`·`.odi` 짝) | 리포트 루트 디렉터리 트리. 원본이 프로젝트 밖이면 `[paths] oz_src`(설치 때 비워 두고 처음 리포트 작업 때 채움, `ozbot.md` 「처음 쓸 때 확인」) |
| 뷰어 연동 위치(JSP·서블릿)와 외부 OZ 서버 뷰어 스크립트 경로 | webapp의 OZ 관련 JSP |
| 리포트를 여는 화면 쪽 호출 방식과 공통 파라미터(`P_*`) 목록 | UI 공통 스크립트, 기존 화면 |
| 폰트 지정 방식(폰트 파라미터 이름, 폰트 테이블·옵션 위치)과 표준 `SCRIPTCODE` 예시 | 기존 `.ozr`의 `setattr("fontname", ...)`, DB 설정 테이블 |
| 출력 값 합치기 선례(리포트 파일·라벨 이름) | 같은 모듈 `.ozr` |
| 다른 리포트 엔진 병행 여부(예: 서블릿 게이트웨이 방식) | webapp 설정 |
| VCS 원본 복원 명령(Git `git checkout --` / SVN `svn revert`) | 프로젝트 VCS |
