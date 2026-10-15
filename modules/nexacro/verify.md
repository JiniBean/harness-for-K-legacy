# C_XFDL (Nexacro 화면)

| ID | 방법 | FAIL |
| :--- | :--- | :--- |
| C_XFDL | 서브에이전트 `nexabot`. L0: 이벤트↔함수, bind↔Column, CODE↔case, 서비스 URL↔컨트롤러, in/outData 이름, 화면 키↔SQL, 계획 「참조 화면」 패턴. L1: 확실한 구조 결함만. `.xfdl` 변경 없으면 SKIP | 연결 깨짐 |

- 엔진 실행 없음. L0(+확실한 L1)과 DB 조회 결과 대조(L3)로만 검증한다
