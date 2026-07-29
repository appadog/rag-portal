# Sprint 01 — Persistent Processing

## Objective

문서를 올리면 실제 준비 작업이 시작되고, 사용자가 화면을 떠났다가 돌아와도 job 진행 상태와 비교 결과가 이어진다.

## Delivered

- SQLite snapshot으로 RAG 인스턴스, 문서 원문, segment, 후보, job, 비교 라운드, 투표, artifact, feedback 저장
- 업로드·재튜닝 요청은 즉시 `202 + QUEUED job`을 반환하고, 백그라운드 worker가 파싱 → 후보 생성 → 검색 준비를 순서대로 처리
- job stage와 완료 수는 실제 단계 완료 시에만 갱신
- 상세 조회가 최신 job 및 마지막 비교 라운드(답변·근거·누적 선택 횟수 포함)를 반환
- 생성 화면이 활성 job을 폴링하고, 완료 후 비교 화면으로 자동 전환

## Acceptance checks

- 서버 상태를 비운 뒤 SQLite snapshot을 다시 읽어도 최신 job과 비교 라운드가 복원된다.
- 처리 중 화면을 떠나도 대시보드와 setup 화면에서 같은 job을 조회한다.
- 후보가 준비되기 전에는 비교 요청을 만들지 않는다.
- 확정 전 라운드와 선택 횟수가 재방문 시 보존된다.

## Follow-up

- SQLite snapshot을 관계형 DB·object storage로 교체
- worker를 queue 기반으로 교체하고 cancel/retry endpoint 제공
- 실제 parser, embedding, vector/BM25/rerank, LLM 비교 SSE 연결
