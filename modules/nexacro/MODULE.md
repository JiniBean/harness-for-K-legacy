범위: 프로젝트 전용
구성: 규칙, 스킬 generate, 에이전트 nexabot

# nexacro

Nexacro 화면(.xfdl/.xjs)을 쓰는 프로젝트의 기능. 화면 규칙, HTML5 Generate, 화면 배선 분석·검사를 만든다.

## 사용자 안내

설명: 에이전트가 Nexacro 화면(.xfdl/.xjs)을 고칠 때 기존 화면의 이름 규칙과 공통 함수를 따르게 합니다. 고친 화면을 HTML5로 빌드(Generate)하는 명령과, 완료 전에 화면 이벤트·데이터 연결이 끊기지 않았는지 보는 검사가 함께 설치됩니다.

물어볼 것

1. `[못 찾을 때]` (`.xprj`·`.xadl` 헤더와 Studio 설치 이름에서 버전이 하나로 확실하지 않을 때만) 이 프로젝트의 Nexacro 버전은 무엇인가요? 찾은 후보를 보여 준다
   - 정하는 것: `rules.md`에서 넣을 버전별 규칙
   - 선택지: 후보 중 하나 / 다른 버전 알려 줌
   - 모름/나중에: 버전별 규칙을 넣지 않고 버전 공통 규칙만 넣는다
2. `[처음 쓸 때]` Generate 도구(`nexacrogenerator.exe`) 경로와 빌드 결과 폴더(`[paths] nexacro_generator`, `nexacro_out_parent`, `nexacro_out`, 선택 `war_exploded`·`nexacro_exploded`)
   - 설치 때: 묻지 않고 비워 둔다. 처음 `빌드해`를 쓸 때 generate 스킬이 묻고 적는다

묻지 않고 정하는 것

- 프로젝트 안 경로(`[paths] nexacro_adl`, `nexacro_src`): 프로젝트에서 찾은 경로
- 분석·검사에서 뺄 화면: 없음
- 고객 요청서·캡처의 라벨 문구와 사내 이름 규칙이 다를 때: 고객 문구 우선

## 감지 신호

- `*.xadl`, `*.xprj`, `*.xfdl`, `*.xjs`
- Nexacro Studio·generator 설치 경로, 빌드 산출물 `*.xfdl.js`
- 버전: `.xprj`·`.xadl` 헤더, Studio 실행 파일 이름(`nexacrostudio*.exe`)

## 원칙

- 기술 규칙은 `rules.md`(버전이 다른 사실은 해당 버전 표기)
- 원본은 `.xfdl`/`.xjs`다. Generate 산출물(`*.xfdl.js`)은 직접 고치지 않는다
- 트랜잭션은 프로젝트 공통 래퍼로 부른다
- 화면 분석은 대상 화면 하나를 잠근 뒤에만 한다(`nexabot`)
- 큰 `.xfdl`은 전문을 Read하지 않는다
- `.xfdl`의 Layout·Objects·Dataset XML에는 주석을 넣지 않는다. 주석은 Script CDATA 안에만 둔다. comment-gen 기능을 함께 켜면 `[comment-gen] exclude`에 `"*.xfdl: <Script> CDATA 밖 전체(Layout·Objects·Dataset XML)"`를 넣는다

## 규칙 작성 항목 (set-up-harness가 프로젝트를 읽어 채움)

| 항목 | 읽을 곳 |
|---|---|
| Nexacro 버전 | `.xprj`·`.xadl`, Studio 경로 |
| 소스 폴더 구조·폼 명명 | 원본 폴더 트리 |
| 공통 라이브러리·함수(트랜잭션 래퍼, 폼 초기화 등) | 공통 `.xjs`, 기존 화면의 호출 |
| 접두·명명 규칙(데이터셋, 컴포넌트) | 기존 화면 |
| 단축키 ↔ 공통 함수 표 (키 · 호출 함수 · 동작, 런타임/웹 차이). 필수: 못 찾으면 결과 문서에 `미확인` 줄을 남긴다 | 공통 `.xjs`의 키 처리(`onkeydown` 등 키 이벤트 핸들러), 공통 폼 |
| 다국어 라벨 조회 방법 | 라벨 테이블·공통 함수 |
| 다국어 라벨 ID 만드는 규칙(컴포넌트 이름 → 라벨 ID). 필수: 못 찾으면 결과 문서에 `미확인` 줄을 남긴다 | 공통 `.xjs`의 라벨 ID 함수(떼는 접두, 대소문자 변환) |
| 고객 화면 라벨과 명명 규칙이 충돌할 때 우선순위 | 추천값 고객 문구 우선 (사용자 안내 「묻지 않고 정하는 것」) |
| 메뉴 ↔ 폼 대응 | 메뉴 테이블·메뉴 문서 |
| 분석 제외 화면·버전 사본 | 추천값 없음 (사용자 안내 「묻지 않고 정하는 것」). 사용자가 나중에 알려 주면 더한다 |
| 주석 금지 구간 (comment-gen 기능을 켰을 때) | 위 원칙의 `.xfdl` 구간 → `[comment-gen] exclude`, `file_types`의 `".xfdl" = "//"` |
| Generate 경로 | 설치 때 `[paths] nexacro_adl`, `nexacro_src`(프로젝트 안), (선택) `nexacro_project`, `webapp_app_link`. 처음 `빌드해` 때 generate 스킬이 `nexacro_generator`, `nexacro_out_parent`, `nexacro_out`, (선택) `nexacro_exploded`, `war_exploded` |

결과 → Nexacro 원본 폴더의 `AGENTS.md`

## 포함 파일

- 규칙 `rules.md` → Nexacro 원본 폴더 `AGENTS.md`의 바탕
- 스킬 `skills/generate/` (HTML5 Generate, `--dry`로 명령만)
- `verify.md` → `.agents/skills/verify/checks/nexacro.md` (C_XFDL)
- 서브에이전트 `agents/nexabot.md` → `.agents/agents/nexabot.md` (잠긴 화면 배선 분석)

## 설정 키

`[paths]`의 `nexacro_*` 키 (위 표)
