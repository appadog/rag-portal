# Sprint 04 — 실제 파일 처리와 검색 실행 경로

## Delivered

- 이진 업로드를 `content_base64`로 받아 PDF, DOCX, XLSX, 텍스트를 실제 추출기로 처리한다.
- 스캔 PDF·이미지는 PyMuPDF/Pillow/Tesseract OCR 경로로 분기한다. OCR 실행 파일 또는 언어팩이 없으면 job을 실패시키고 재시도 가능한 이유를 남긴다.
- 후보별 청크를 대상으로 벡터를 생성·영속한다. 개발 서버의 local TEI endpoint가 선택된 무료 모델을 실행하는 기본 경로이며, Hugging Face Inference Providers는 선택적 fallback이다. 둘 다 없거나 실패하면 명시적인 `local-hash-fallback` 메타데이터를 저장한다.
- 검색은 실제 BM25, dense cosine, 정규화된 hybrid fusion, local rerank fallback을 사용한다.
- 작업 상태는 SQLite로 복원되고 cancel/retry API를 제공한다. Redis가 provision된 경우 Redis dispatch adapter를 사용하며, 로컬에서는 thread backend로 안전하게 fallback한다.

## Verified

- DOCX, XLSX, 텍스트 PDF의 실제 이진 추출과 후보 벡터 준비
- BM25/dense/hybrid/hybrid-rerank 실행 경로
- 처리 중단 뒤 같은 job의 재시도
- 기존 재방문·비교·인용 회귀

## Development-server model registry

| Role | Model | Service |
| --- | --- | --- |
| Multilingual embedding | `BAAI/bge-m3` | TEI `/embed` |
| Lightweight embedding | `Qwen/Qwen3-Embedding-0.6B` | TEI `/embed` |
| Small-footprint embedding | `google/embeddinggemma-300m` | TEI `/embed` |
| Cross-encoder reranking | `BAAI/bge-reranker-v2-m3` | TEI `/rerank` |
| OCR | Tesseract `kor`, `eng` traineddata | host runtime |

`docker-compose.models.yml` profiles download and serve these model weights. A RAG instance continues to fix exactly one embedding model, while the reranker is shared.

The backend exposes `GET /api/v1/model-runtime` for server-wide readiness and `GET /api/v1/rag-instances/{id}/execution-plan` for the exact model services needed by one RAG flow. This keeps model requirements visible before processing begins.

## Deployment prerequisites

- local TEI model services: primary semantic embedding and cross-encoder reranking
- `HF_TOKEN`: optional provider fallback
- Tesseract + `kor`/`eng` language packs: scanned PDF/image OCR
- Redis 또는 SQS credentials/worker runtime: multi-process queue operation
- object storage: production-scale original-file retention
- model-backed reranker endpoint: cross-encoder quality reranking

이 값이 없는 환경에서도 제품은 멈추지 않지만, 화면과 API 메타데이터는 fallback 상태를 명시해야 하며 이를 실제 의미 검색 또는 cross-encoder rerank로 표현해서는 안 된다.
