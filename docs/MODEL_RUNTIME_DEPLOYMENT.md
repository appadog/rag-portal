# 모델 런타임 구축 기준서

## 목적과 현재 상태

이 문서는 RAG Portal이 의존하는 모델·OCR·큐 런타임의 단일 기준 문서다. 애플리케이션 코드는 해당 서비스가 이미 구축되어 있다는 계약으로 API를 호출한다. 그러나 **이 저장소를 실행 중인 현재 로컬 환경에는 TEI 모델 서버와 Tesseract가 설치·기동되어 있지 않다.** 따라서 실제 의미 검색·cross-encoder rerank·OCR을 사용하려면 아래 구축 작업을 완료해야 한다.

| 영역 | 코드 상태 | 현재 로컬 런타임 | 실제 구축 완료 기준 |
| --- | --- | --- | --- |
| 임베딩 | 구현됨: TEI `/embed` 호출과 벡터 영속 | 미구축 | 선택한 임베딩 endpoint가 `READY` |
| Reranker | 구현됨: TEI `/rerank` 호출 | 미구축 | `hybrid_rerank` 계획에서 `READY` |
| OCR | 구현됨: Tesseract `kor+eng` 호출 | 미설치 | 스캔 PDF/image OCR 성공 |
| Redis queue | adapter 구현됨 | 미기동 | Redis 연결과 worker dispatch 확인 |
| Object storage | API 교체 지점만 설계됨 | 미구축 | 원본 이진 파일 보관·복구 검증 |

`local-hash-fallback` 및 `local-heuristic-fallback`은 개발용 기준선이다. API 메타데이터에 명시되지만, 실제 임베딩 또는 모델 reranker와 동등하다고 취급하면 안 된다.

## 서비스 계약

| 기능 | 배포 모델/런타임 | 코드의 환경변수 | 기본 endpoint | 사용하는 플로우 |
| --- | --- | --- | --- |
| 기본 다국어 임베딩 | `BAAI/bge-m3` via TEI | `RAG_EMBEDDING_URL_BGE_M3` | `http://127.0.0.1:8081` | 색인, dense, hybrid, hybrid rerank |
| 경량 임베딩 | `Qwen/Qwen3-Embedding-0.6B` via TEI | `RAG_EMBEDDING_URL_QWEN3_EMBEDDING_0_6B` | `http://127.0.0.1:8082` | 선택된 인스턴스의 색인·검색 |
| 소형 임베딩 | `google/embeddinggemma-300m` via TEI | `RAG_EMBEDDING_URL_EMBEDDINGGEMMA_300M` | `http://127.0.0.1:8083` | 선택된 인스턴스의 색인·검색 |
| 정밀 재정렬 | `BAAI/bge-reranker-v2-m3` via TEI | `RAG_RERANKER_URL` | `http://127.0.0.1:8084` | `hybrid_rerank` 후보와 검색 |
| 스캔 OCR | Tesseract `kor` + `eng` language packs | 없음(host binary) | host `tesseract` | scanned PDF, image |
| 비동기 처리 | Redis | `REDIS_URL` | `redis://127.0.0.1:6379/0` | job dispatch, cancel/retry |

임베딩 모델은 RAG 인스턴스마다 하나만 고정한다. 비교를 위해 세 모델을 동시에 기동할 필요는 없다. 다만 모든 신규 인스턴스가 `hybrid_rerank` 후보를 만들므로 선택한 임베딩 모델과 reranker는 함께 준비하는 것을 기본으로 한다.

## 개발 서버 구축 순서

1. `apps/backend/.env.example`을 `apps/backend/.env`로 복사한다.
2. 이번 환경에서 사용할 임베딩 프로필 하나와 reranker를 기동한다. 기본값은 BGE-M3다.

   ```bash
   cd apps/backend
   docker compose -f docker-compose.models.yml --profile bge --profile reranker up -d
   ```

3. 스캔 PDF·이미지를 지원할 환경에는 Tesseract 실행 파일과 `kor`, `eng` language packs를 설치한다.
4. 운영형 job 처리가 필요하면 Redis를 기동하고 `.env`에서 `RAG_QUEUE_BACKEND=redis`로 바꾼다.

   ```bash
   docker compose up -d redis
   ```

5. API는 환경 파일을 명시해 실행한다.

   ```bash
   .venv/bin/uvicorn app.main:app --env-file .env --port 8010
   ```

6. 상태 API로 설치 여부가 아니라 실제 연결 가능 상태를 확인한다.

   ```bash
   curl http://127.0.0.1:8010/api/v1/model-runtime
   ```

TEI의 임베딩 및 rerank HTTP 계약은 [Hugging Face Text Embeddings Inference quick tour](https://huggingface.co/docs/text-embeddings-inference/en/quick_tour)를 기준으로 한다.

## 릴리스 게이트

개발 서버 또는 운영 배포를 모델 준비 완료로 표시하기 전에 아래를 모두 충족해야 한다.

- [ ] `GET /api/v1/model-runtime`에서 사용 대상 모델이 `READY`다.
- [ ] 실제 RAG 인스턴스의 `GET /api/v1/rag-instances/{id}/execution-plan`에서 `required_services`가 모두 `READY`다.
- [ ] PDF, DOCX, XLSX 업로드와 선택한 임베딩 모델의 인덱스 생성이 성공한다.
- [ ] `bm25`, `dense`, `hybrid`, `hybrid_rerank` 비교에서 provider 메타데이터가 fallback이 아니다.
- [ ] 스캔 문서를 지원하는 환경에서는 OCR 업로드와 재시도가 성공한다.
- [ ] Redis 운영 모드에서는 재시작 뒤에도 job 상태와 retry/cancel 동작이 확인된다.
- [ ] 모델 버전, 컨테이너 이미지 digest, GPU/CPU 자원, 관측 지표를 배포 기록에 남긴다.

## 책임 분리와 다음 작업

| 담당 | 다음 산출물 |
| --- | --- |
| 플랫폼/백엔드 | 모델 컨테이너 실행 환경, volume 백업, endpoint health monitoring, Redis worker 운영 |
| ML/검색 | 각 임베딩 후보와 reranker의 실제 문서 벤치마크, 모델·파라미터 선정 기록 |
| 제품/QA | representative PDF/DOCX/XLSX/OCR fixture, 품질 기준 질문 세트, fallback 노출 검수 |
| 보안/운영 | 사내망 접근, 원본 파일 보관 정책, 모델 라이선스·취약점 점검 |

애플리케이션은 모델 서비스가 없을 때 상태를 숨기지 않는다. `NOT_CONFIGURED`, `UNAVAILABLE`, `NOT_INSTALLED`를 반환하므로, 이 문서의 구축 체크리스트를 완료하기 전에는 모델 기반 기능이 준비되었다고 릴리스 노트에 기재하지 않는다.
