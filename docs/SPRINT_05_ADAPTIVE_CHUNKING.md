# Sprint 05 — 문서 적응형 청킹 후보

## Goal

문서를 업로드할 때 동일한 청킹 템플릿을 기계적으로 적용하지 않는다. 파싱한 원문 구조를 측정하고, 비교 가능한 범위 안에서 문서에 맞는 후보와 파라미터를 만든다.

## Input signals

- 원문 길이, 줄 수, 문단 수, 평균 문단 길이
- 제목/조/장 개수
- 표 형태 줄 수와 비율
- OCR 사용 여부

분석 결과는 문서 상세 응답의 `chunking_analysis`로 저장·복원된다.

## Candidate policy

후보 폭증을 막기 위해 문서마다 청킹 전략 3개와 검색 방식 3개만 조합한다. 따라서 비교 화면의 후보 수는 최대 9개로 안정적이지만, 전략과 파라미터는 아래처럼 달라진다.

| Document profile | Chunking candidates | Calculated parameters |
| --- | --- | --- |
| short | document, semantic, fixed | semantic target chars, fixed width/overlap |
| structured | hierarchical, semantic, fixed | heading preservation, max section chars, target chars, overlap |
| long | semantic, fixed, hierarchical | paragraph-based target chars, width/overlap, relaxed section cap |
| table | table, hierarchical, fixed | rows per chunk, repeated header, section cap, overlap |
| scanned | OCR hierarchical, OCR semantic, fixed | shorter OCR target/section limit and overlap |

`hierarchical`은 계산된 절 최대 길이를 넘는 절만 다시 겹침 고정 길이로 나눈다. `table`은 각 청크마다 헤더를 포함해 열 의미를 잃지 않는다. `reuse` 모드는 확정된 파이프라인의 동일 파라미터를 적용해 재현성을 보장한다.

## API transparency

문서 상세와 비교 결과의 candidate payload는 다음 값을 반환한다.

- `chunking_parameters`: 실제로 청커에 전달한 값
- `selection_reason`: 문서 신호를 사람이 읽을 수 있게 설명한 문장
- `chunk_count`: 그 설정으로 생성된 근거 조각 수

이 값들은 SQLite snapshot에 후보와 함께 저장되어 재방문 후에도 유지된다.
