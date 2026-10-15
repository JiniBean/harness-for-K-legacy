---
name: memory-tidy
description: Claude Code 메모리와 대화 기록에 흩어진 사용자 교정을 모아 공유 지시 파일로 승격·정리한다. 메모리 파일 중복 삭제, 낡은 경로 수정, 대화 기록에서 아직 반영 안 된 교정 수확, 응답 방식 지적은 response learned.md로, 절차 교정은 AGENTS.md·스킬·docs로 승격 제안. 트리거 — 메모리 정리, 메모리 점검, 메모리 승격, 메모리 규칙으로 올려, 교정 수확, 대화 기록 수확, 세션에서 교정 뽑아, memory-tidy. garbage-collector가 "memory-tidy 먼저"라고 안내했을 때도 쓴다. 파일 삭제(tmp·세션 정리)는 garbage-collector, 지적 직후의 실시간 재설명은 response가 맡는다.
---

# memory-tidy

Cursor는 Claude Code 메모리를 읽지 않는다. 그래서 교정이 메모리나 대화 기록에만 있으면 다른 하네스·다른 세션에서는 적용되지 않는다. 이 스킬은 그런 교정을 두 하네스가 함께 읽는 지시 파일로 옮기고, 옮긴 것은 메모리에서 지운다.

## 절차

1. 수확: 마지막 수확일 이후 대화 기록에서 교정 후보를 뽑는다.
   ```bash
   python ~/.agents/skills/memory-tidy/scripts/harvest.py --project <프로젝트 루트>
   ```
   결과는 `<프로젝트>/.agents/tmp/YYYYMMDD_harvest.json`(`scanned_at`, `candidates[]`: 날짜·사용자 발화·직전 에이전트 답변 끝부분)과 후보당 한 줄 요약 `YYYYMMDD_harvest.txt`. 수확 기록이 없으면 최근 60일을 본다. 먼저 `.txt`로 훑고, 맥락이 필요한 후보만 json에서 같은 번호의 `prev_assistant`를 본다.
2. 후보 판정: 정규식 1차 필터라 대부분은 업무 내용 논의다. 에이전트의 작업 방식·응답 방식을 바로잡은 발화만 남긴다. 같은 교정이 여러 번 나오면 하나로 합친다(반복은 중요도 근거로 표시).
3. 메모리 읽기: `~/.claude/projects/<프로젝트>/memory/`의 파일을 모두 읽는다(파일이 적으므로 전문).
4. 대조: 남긴 교정과 메모리마다 이미 공유 규칙에 있는지 검색한다. 대상은 전역 `~/.agents/AGENTS.md`, 프로젝트 `AGENTS.md`와 폴더별 `AGENTS.md`, 프로젝트 스킬·에이전트·docs, response `learned.md`. 이름만 보고 판단하지 않고 해당 구간을 열어 문구를 확인한다.
5. 분류해 표로 보고한다.

   | 분류 | 기준 | 제안 |
   |---|---|---|
   | 삭제 | 같은 내용이 이미 공유 규칙에 있음 | 메모리 삭제(수확분은 버림). 근거 파일:줄 |
   | 예시 | 수확분이 이미 공유 규칙에 있는데, 그 규칙이 들어간 날짜 이후에 다시 교정됨 | 그 규칙에 전후 예시 한 쌍 추가. 근거 파일:줄, 재교정 날짜 |
   | 승격 | 작업 절차·방식 교정 | 넣을 파일과 위치, 문구 초안 |
   | learned | 설명·응답 방식 지적 | response 스킬의 `learned.md`(`<.agents>/skills/response/learned.md`) `## Entries`에 한 줄. response가 없는 환경이면 전역 `AGENTS.md`의 응답·서식 절로 승격 |
   | 유지 | 확인 대기, 이 환경에서만 맞는 사실, 공유 파일에 넣을 수 없는 것 | 유지 이유 한 줄 |

   승격 위치는 `~/.agents/docs/harness-guide.md` §3 배치표를 따른다. 프로젝트 `.agents/docs/harness-guide.md`에 다른 배치가 있으면 그쪽이 우선이다. 프로젝트 전용 용어(티켓 번호 체계, 사내 도구명)는 전역에 넣지 않는다.
6. 승인받은 항목만 반영한다. 지시 파일은 사용자가 관리하는 파일이라 문구째 승인을 받는다. 반영 뒤 옮긴 메모리 파일을 지우고 `MEMORY.md` 인덱스에서 그 줄을 뺀다. 남는 메모리의 낡은 경로·빈 설명도 고친다.
7. 수확 기록: 후보 검토가 끝났으면(채택 0건이어도) 1단계 결과의 `scanned_at`으로 기록한다.
   ```bash
   python ~/.agents/skills/memory-tidy/scripts/harvest.py --mark <scanned_at>
   ```
   이 날짜 이전 대화 기록은 garbage-collector가 지울 수 있게 된다. 검토를 중간에 멈췄으면 기록하지 않는다.
8. 전역 `AGENTS.md`를 고쳤으면 Cursor Settings → Rules → User Rules에 다시 붙여 넣으라고 안내한다. `learned.md`가 15줄을 넘으면 response의 `explain 압축`을 제안한다.

## 주의

- 교정 발화는 그 턴의 맥락(`prev_assistant`)과 함께 읽는다. 발화만 떼어 일반 규칙으로 늘리지 않는다. 범위가 한 화면·한 작업에 한정된 교정은 그 작업의 문서에 둔다.
- 사용자가 한 번 배제한 선택지를 규칙으로 되살리지 않는다.
- 이 스킬은 파일을 삭제하지 않는다(메모리 파일 제외). tmp·세션 정리는 garbage-collector.

## 점검

```bash
python ~/.agents/skills/memory-tidy/scripts/harvest.py selftest
```
