# Nexacro UI 규칙

Nexacro 소스(`.xfdl`·`.xjs`·`.xadl`)를 만들거나 고칠 때 적용한다. set-up-harness는 이 내용과 아래 「프로젝트에서 채울 항목」을 합쳐 프로젝트 Nexacro 소스 폴더의 `AGENTS.md`를 만든다. 버전에 따라 다른 사실은 해당 버전을 함께 적었다.

## 1. 파일 종류

- `.xfdl`: XML 기반 Form Definition Language(UI 레이아웃 + 스크립트)
- `.xjs`: 여러 폼이 include하는 재사용 스크립트
- `.xadl`: Application 정의(서비스 폴더·프레임·전역 설정)
- 브라우저가 읽는 것은 Generate 산출(`*.xfdl.js`·`*.xjs.js`)이다. 산출 폴더는 직접 고치지 않고, 소스를 고친 뒤 generate 스킬(`빌드해 <폼>`)로 다시 만든다
- 공통 `.xjs`를 고치면 그 xjs 자체를 빌드한다. include한 폼만 다시 빌드해서는 갱신되지 않는다
- Studio·런타임 실행 파일을 에이전트가 띄우지 않는다. 소스 파일을 셸로 열지 않는다

## 2. 스크립트 구조 (표준 순서)

한 폼 스크립트 안에서 아래 순서를 지킨다. 새 함수는 같은 성격의 기존 함수 옆에 둔다.

1. 폼 변수 선언
2. onload 이벤트(프로젝트 공통 초기화 함수 호출)
3. 사용자 함수
4. Transaction 함수(조회·저장 등)
5. 인터페이스 함수(버튼·단축키에 매핑되는 공통 이름)
6. 콜백 함수
7. 컴포넌트 이벤트 핸들러

## 3. Transaction

- 서버 호출은 프로젝트 공통 스크립트의 transaction 래퍼를 쓴다. 플랫폼 transaction API(Nexacro 14 기준 `application.transaction`)를 폼에서 직접 부르지 않는다. 세션 체크·오류 처리·메뉴 ID 주입 같은 공통 처리가 래퍼에 있다
- 인자 구성은 플랫폼 transaction과 같다

```javascript
var strSvcId    = "searchList";             // service id, callback branch key
var strSvcUrl   = "<module>/selectList.do"; // controller URL
var inData      = "ds_search=ds_search";    // server <- client (server name = client dataset)
var outData     = "ds_list=ds_list";        // client <- server (client dataset = server name)
var strArg      = "param1=value1";          // space-separated key=value
var callBackFnc = "fn_callBack";
var isAsync     = true;
```

- 콜백에서 오류 코드를 반드시 처리한다. 0 미만이면 오류이며, 오류일 때 후속 처리(재조회·화면 갱신)를 하지 않는다
- 서비스 ID로 콜백 분기를 나눈다. 새 transaction을 추가하면 콜백 분기도 같이 추가한다

## 4. Grid와 Dataset

- Grid 셀은 `text="bind:<컬럼명>"`으로 Dataset 컬럼과 연결한다. 컬럼을 추가하면 Dataset `ColumnInfo`, Grid `Columns`·`Rows`(head/body), `Cell` 바인딩을 함께 맞춘다
- Dataset 행 상태(`rowtype`: insert/update/delete/normal)가 서버의 INSERT/UPDATE/DELETE 분기를 결정한다. 화면 표시용으로 값을 넣을 때 의도치 않은 행 상태 변경이 서버 저장으로 이어지지 않는지 본다

## 5. 항목 추가·이식

- 레거시 화면은 옵션·컬럼 하나가 여러 함수·분기·콜백에 흩어져 있다. 같은 성격의 기존 항목이 등장하는 위치를 전부 찾아 새 항목을 빠짐없이 넣는다(초기화, 조회 조건, 저장 인자, 콜백, 활성/비활성 제어, 출력 파라미터)
- 다른 화면의 옵션을 이식할 때는 선례의 조건문·연동 동작을 엣지 케이스까지 그대로 옮긴다. 선례에 없는 강제·보정 로직은 넣지 않는다. 새 화면에만 다르게 할 이유가 있으면 다르다는 점을 밝혀 제안한다
- 컴포넌트 id·리포트 파라미터명은 같은 계열 화면 선례의 대칭형으로 정한다
- 고객 요구사항·캡처에 라벨 문구가 있으면 사내 명명 관례보다 그 문구가 우선이다

## 6. 공식 문서

공식 문서(Nexacro 14): https://docs.tobesoft.com/developer_guide_nexacro_14_en_kr/ — 검색하면 다른 버전(N·17) 문서가 먼저 나오므로 이 버전 문서를 기준으로 한다. set-up-harness가 프로젝트 버전에 맞는 주소로 바꾼다(같은 사이트에서 주소의 버전 번호만 다름).

## 프로젝트에서 채울 항목

set-up-harness가 프로젝트 소스를 열어 확인한 뒤 채운다. 추측으로 채우지 않는다.

| 항목 | 확인할 곳 |
|------|-----------|
| Nexacro 버전 | `.xadl`·`.xprj`의 버전 표기, generator 설치 경로 |
| 소스 폴더 구조(서비스 폴더, 공통 JS·공통 폼·프레임 폼·이미지 폴더) | `{nexacro_src}` 디렉터리 트리, `.xadl`의 서비스 정의 |
| 폼 파일 명명 규칙(모듈 코드·업무명·유형 접미) | 서비스 폴더의 기존 `.xfdl` 이름 |
| 접두 규칙(Dataset·폼 변수·파라미터·컴포넌트 종류별) | 기존 폼에서 많이 쓰는 접두 |
| 공통 스크립트 파일과 transaction 래퍼 이름·시그니처·추가 기능 | 공통 `.xjs`에서 플랫폼 transaction을 감싼 함수 |
| onload 공통 초기화 함수, 다국어 변환 함수 | 기존 폼 onload |
| 인터페이스 함수 이름과 단축키 매핑(런타임/웹 동작 차이 포함) | 공통 `.xjs`의 키 처리 |
| 다국어 단어 ID 규칙과 단어 테이블 역검색 방법 | 공통 `.xjs`의 단어 ID 함수, DB 단어 테이블 |
| 메뉴 ID·폼 ID 기준 문서 | 프로젝트 메뉴 SSOT |
| Generate 산출·webapp·exploded 경로 | `harness.toml` `[paths]`(generate 스킬 `references/paths.md`) |
| 화면 배선 분석 담당 에이전트 | nexacro 기능 `agents/` |
