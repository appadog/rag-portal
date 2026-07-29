# RAGAS 참고 가이드

## 1. 문서 목적

이 문서는 Enterprise RAG의 검색 및 답변 품질을 평가할 때 참고할 수 있도록 RAGAS의 핵심 개념, 주요 지표, 평가 데이터 구성과 적용 방식을 정리한다.

RAGAS는 RAG 및 LLM Application의 품질을 평가하기 위한 외부 평가 Framework이다. 검색 결과, 생성 답변과 기준 답변을 조합하여 검색 품질과 답변 품질을 수치화할 수 있다.

이 문서는 제품 또는 Framework 도입을 확정하는 구현 명세가 아니다. 프로젝트의 [Quality Evaluation 상세 설계](./03_Components/03_Quality_Evaluation.md)는 특정 평가 Framework에 종속되지 않으며, RAGAS는 `Evaluator Interface`를 통해 교체 가능하게 연계할 수 있는 외부 평가 수단 중 하나이다.

### 1.1 포함 범위

- RAGAS의 역할과 특징
- 평가 입력 데이터
- 대표적인 RAG 평가 지표
- 지표 선택 기준
- 평가 실행 예시
- 결과 해석과 운영 시 주의사항
- Enterprise RAG 설계와의 대응 관계

### 1.2 제외 범위

- RAGAS 도입 확정
- 특정 RAGAS 버전과 평가 모델 선정
- API, DB Schema와 배포 구조
- 평가 점수에 따른 운영 설정 자동 변경
- 평가용 LLM과 Embedding Model의 비용 산정

---

## 2. RAGAS 개요

RAGAS는 RAG Pipeline을 하나의 종합 점수로만 평가하기보다 검색과 답변 생성 단계를 서로 다른 관점의 지표로 평가한다.

일반적인 RAG 평가 질문은 다음과 같이 나눌 수 있다.

| 평가 대상 | 평가 질문 | 대표 지표 |
|---|---|---|
| 검색 결과 | 필요한 근거를 빠뜨리지 않았는가? | Context Recall |
| 검색 결과 | 관련성이 높은 근거를 상위에 배치했는가? | Context Precision |
| 생성 답변 | 검색된 근거에 충실한가? | Faithfulness |
| 생성 답변 | 사용자 질문에 직접 답했는가? | Response Relevancy |
| 생성 답변 | 기준 답변과 사실적으로 일치하는가? | Factual Correctness |

RAGAS 지표에는 LLM, Embedding Model 또는 문자열·ID 비교를 사용하는 방식이 있다. LLM 기반 지표는 사람이 모든 Case를 직접 채점하는 비용을 줄일 수 있지만, 평가 모델과 Prompt에 따라 결과가 달라질 수 있으므로 절대적인 정답으로 취급하지 않는다.

---

## 3. 평가 데이터

### 3.1 핵심 입력

RAG 평가에는 다음 정보가 주로 사용된다.

| RAGAS 개념 | 프로젝트 내 대응 정보 | 의미 |
|---|---|---|
| `user_input` | Evaluation Case의 질문 | 사용자가 RAG에 입력한 질문 |
| `response` | Answer | RAG가 생성한 최종 답변 |
| `retrieved_contexts` | Retrieval Result와 Evidence | 답변 생성에 사용된 검색 Context 목록 |
| `reference` | 기대 답변 | 업무 검토를 거친 기준 답변 |
| `reference_contexts` | 기대 근거·출처 | 질문에 답하기 위해 검색되어야 하는 기준 Context |
| `retrieved_context_ids` | 검색 결과의 Knowledge Unit 식별자 | 검색된 Context를 식별하는 값 |
| `reference_context_ids` | 기대 근거의 Knowledge Unit 식별자 | 기준 Context를 식별하는 값 |

지표마다 필요한 입력이 다르다. 모든 Dataset에 모든 필드를 강제로 채우기보다 평가 목적과 확보 가능한 기준 데이터에 따라 지표를 선택한다.

### 3.2 Reference가 있는 Dataset

업무 전문가가 기대 답변이나 기대 근거를 검수한 Dataset이다.

장점은 다음과 같다.

- 검색 누락과 답변 정확성을 직접 평가할 수 있다.
- 동일 Dataset으로 변경 전후 결과를 반복 비교할 수 있다.
- ID 기반 검색 평가를 구성하면 LLM Judge 의존도를 줄일 수 있다.

다음 정보의 관리 비용이 발생한다.

- 기준 답변과 근거의 작성 및 검수
- 원본 문서 변경에 따른 기준 데이터 갱신
- Dataset Version과 평가 실행 당시 지식 Version의 호환성 유지

### 3.3 Reference가 없는 Dataset

운영 질문과 실제 답변을 활용하여 기준 답변 없이 평가할 수 있다. Faithfulness, Response Relevancy와 Context Utilization 같은 지표를 활용할 수 있다.

이 방식은 초기 평가와 운영 결과 점검에 유용하지만 다음 한계가 있다.

- 검색되지 않은 필수 근거를 직접 측정하기 어렵다.
- 답변이 검색 Context에는 충실하지만 실제 업무 정답과 다를 수 있다.
- 생성 답변을 기준으로 검색 결과를 판단하면 답변의 오류가 평가에 영향을 줄 수 있다.

---

## 4. 주요 평가 지표

### 4.1 Context Precision

Context Precision은 검색된 Context 중 관련 Context가 상위 순위에 배치되었는지를 평가한다.

점수가 낮을 때 검토할 후보는 다음과 같다.

- 검색 Query 구성
- Chunk 크기와 경계
- Metadata Filter
- Hybrid Search 가중치
- Re-ranking 방식과 후보 수

Reference 답변이 있으면 검색 Context를 Reference와 비교할 수 있다. Reference가 없으면 생성 답변을 이용하는 Context Utilization 계열 평가를 고려할 수 있다.

Context Precision은 상위 검색 결과의 순서를 반영한다. 관련 Context가 검색되었더라도 낮은 순위에 있으면 점수가 낮아질 수 있다.

### 4.2 Context Recall

Context Recall은 기준 답변이나 기준 Context에 필요한 정보를 검색 결과가 얼마나 빠짐없이 포함하는지 평가한다.

개념적인 계산은 다음과 같다.

```text
Context Recall
  = 검색 Context가 뒷받침하는 Reference Claim 수
    / 전체 Reference Claim 수
```

Context Recall은 비교할 Reference가 필요하다. 기준 Context 식별자를 안정적으로 관리할 수 있다면 ID 기반 Context Recall을 사용하여 빠르고 결정적인 평가를 수행할 수 있다.

점수가 낮을 때 검토할 후보는 다음과 같다.

- 검색 후보 수
- Query Expansion
- 문서 Parsing과 Chunking
- Embedding Model과 검색 Index
- Metadata Filter로 인한 과도한 범위 제한

### 4.3 Faithfulness

Faithfulness는 생성 답변의 Claim이 검색된 Context로부터 뒷받침되는지를 평가한다.

개념적인 계산은 다음과 같다.

```text
Faithfulness
  = 검색 Context가 뒷받침하는 답변 Claim 수
    / 전체 답변 Claim 수
```

점수가 낮으면 검색 Context에 없는 내용을 답변에 포함했을 가능성이 있다. 다만 Faithfulness가 높다고 답변이 업무적으로 정확하거나 완전하다는 의미는 아니다. 잘못된 Context만 사용해 일관된 답변을 생성해도 Faithfulness는 높을 수 있다.

점수가 낮을 때 검토할 후보는 다음과 같다.

- Grounding Prompt
- 검색 Context와 답변 생성 Prompt의 연결 방식
- Context 길이와 잘림
- 답변 거부 또는 불충분 근거 처리
- Model의 지시 준수 성능

### 4.4 Response Relevancy

Response Relevancy는 생성 답변이 사용자 질문의 의도에 얼마나 직접적으로 대응하는지 평가한다. 일반적으로 답변에서 역으로 생성한 질문과 원래 질문 사이의 의미적 유사도를 사용한다.

점수가 낮을 때 검토할 후보는 다음과 같다.

- 질문 의도 분석
- 불필요하게 긴 답변
- 질문 일부에 대한 누락
- 검색 결과와 무관한 일반 설명
- 답변 형식 Prompt

Response Relevancy는 사실 정확성을 보장하지 않는다. 질문과 관련된 잘못된 답변도 높은 관련성 점수를 받을 수 있으므로 Faithfulness 또는 Factual Correctness와 함께 본다.

### 4.5 Factual Correctness

Factual Correctness는 생성 답변과 Reference 답변의 Claim을 비교하여 사실적 일치 정도를 평가한다. Precision, Recall 또는 F1 관점으로 결과를 구성할 수 있다.

- Precision: 생성한 Claim 중 Reference가 뒷받침하는 비율
- Recall: Reference Claim 중 생성 답변이 포함한 비율
- F1: Precision과 Recall의 조화 평균

업무 기준 답변이 있어야 하며, 평가 목적에 따라 Claim 분해 수준과 Precision·Recall의 중요도를 결정해야 한다.

### 4.6 ID 기반 Context Precision과 Recall

검색 결과와 기준 근거에 동일한 Knowledge Unit 식별 체계를 적용할 수 있다면 Context 내용을 LLM으로 판정하지 않고 ID 집합을 직접 비교할 수 있다.

장점은 다음과 같다.

- 실행 결과가 결정적이다.
- LLM 평가 비용과 지연이 없다.
- 평가 모델 변경의 영향을 받지 않는다.

주의할 점은 다음과 같다.

- 동일 의미의 근거가 여러 Chunk에 중복될 수 있다.
- Chunking 또는 게시 Version 변경 시 ID 호환성이 깨질 수 있다.
- 기준 Context ID를 업무적으로 검수해야 한다.

---

## 5. 지표 선택 기준

### 5.1 목적별 권장 조합

| 평가 목적 | 최소 입력 | 권장 지표 |
|---|---|---|
| 검색 순위 품질 | 질문, 검색 Context, Reference | Context Precision |
| 검색 누락 확인 | 질문, 검색 Context, Reference 또는 기준 Context | Context Recall |
| 검색 ID 회귀 테스트 | 검색 Context ID, 기준 Context ID | ID 기반 Context Precision·Recall |
| 근거 기반 답변 확인 | 답변, 검색 Context | Faithfulness |
| 질문 대응성 확인 | 질문, 답변 | Response Relevancy |
| 기준 답변 정확성 확인 | 답변, Reference | Factual Correctness |
| Reference 없는 운영 결과 점검 | 질문, 답변, 검색 Context | Faithfulness, Response Relevancy, Context Utilization |
| 검수 Dataset 기반 종합 평가 | 질문, 답변, 검색 Context, Reference | Context Precision, Context Recall, Faithfulness, Response Relevancy, Factual Correctness |

### 5.2 초기 적용 권장안

초기에는 지표 수를 늘리기보다 품질 문제의 원인을 구분할 수 있는 최소 조합으로 시작한다.

```text
검색 품질
  → Context Precision
  → Context Recall

답변 품질
  → Faithfulness
  → Response Relevancy

검수 Reference가 있는 경우
  → Factual Correctness 추가
```

각 지표의 통과 기준은 RAGAS의 일반적인 점수 구간만으로 결정하지 않는다. 실제 업무 Dataset에서 사람 평가와의 상관관계를 확인한 뒤 프로젝트 기준선을 정한다.

---

## 6. 평가 실행 흐름

프로젝트 설계에 적용할 때의 개념적인 흐름은 다음과 같다.

```text
Evaluation Dataset Version 확정
  → Evaluation Run 계획
  → 지식·Runtime·외부 자원 구성정보 확정
  → Case별 RAG Runtime 실행
  → 질문·검색 결과·답변·Reference 조립
  → Evaluator Interface를 통해 RAGAS 호출
  → Case별 지표 결과와 실패 사유 저장
  → Run 단위 집계
  → 사람 검토와 개선 후보 분류
```

평가 당시 다음 조건을 함께 기록해야 재현성과 비교 가능성을 확보할 수 있다.

- Dataset과 Case Version
- 지식 게시 Version
- 검색·답변 Runtime 조건
- 적용된 외부 자원 구성정보
- RAGAS Package Version
- 지표 이름과 설정
- 평가 LLM과 Embedding Model
- 평가 Prompt 또는 Metric Version
- 재시도, Timeout과 실패 처리 기준

---

## 7. Python 참고 예제

> 아래 코드는 RAGAS의 권장 Collections API 형태를 설명하기 위한 참고 예제이다. 실제 도입 시 설치한 RAGAS Version의 공식 문서와 API를 다시 확인하고 Dependency Version을 고정해야 한다.

### 7.1 설치

```bash
pip install ragas openai
```

### 7.2 단일 Case 평가

```python
import asyncio
import os

from openai import AsyncOpenAI
from ragas.embeddings.base import embedding_factory
from ragas.llms import llm_factory
from ragas.metrics.collections import (
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
    Faithfulness,
    FactualCorrectness,
)


async def main() -> None:
    # 실제 구현에서는 Secret 관리 체계를 통해 API Key를 주입합니다.
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    evaluator_llm = llm_factory(
        "gpt-4o-mini",
        provider="openai",
        client=client,
    )
    evaluator_embeddings = embedding_factory(
        "openai",
        model="text-embedding-3-small",
        client=client,
    )

    user_input = "연차 휴가는 언제부터 사용할 수 있나요?"
    response = "연차 휴가는 입사 후 정해진 발생 기준에 따라 사용할 수 있습니다."
    retrieved_contexts = [
        "연차 휴가는 근속 기간과 출근율에 따른 발생 기준을 적용한다.",
        "휴가 신청은 사내 시스템에서 승인 절차를 거친다.",
    ]
    reference = "연차 휴가는 근속 기간과 출근율에 따른 발생 기준에 따라 사용할 수 있다."

    metrics = {
        "context_precision": ContextPrecision(llm=evaluator_llm),
        "context_recall": ContextRecall(llm=evaluator_llm),
        "faithfulness": Faithfulness(llm=evaluator_llm),
        "response_relevancy": AnswerRelevancy(
            llm=evaluator_llm,
            embeddings=evaluator_embeddings,
        ),
        "factual_correctness": FactualCorrectness(llm=evaluator_llm),
    }

    results = {
        "context_precision": await metrics["context_precision"].ascore(
            user_input=user_input,
            reference=reference,
            retrieved_contexts=retrieved_contexts,
        ),
        "context_recall": await metrics["context_recall"].ascore(
            reference=reference,
            retrieved_contexts=retrieved_contexts,
        ),
        "faithfulness": await metrics["faithfulness"].ascore(
            response=response,
            retrieved_contexts=retrieved_contexts,
        ),
        "response_relevancy": await metrics["response_relevancy"].ascore(
            user_input=user_input,
            response=response,
        ),
        "factual_correctness": await metrics["factual_correctness"].ascore(
            response=response,
            reference=reference,
        ),
    }

    for metric_name, result in results.items():
        print(metric_name, result.value)


if __name__ == "__main__":
    asyncio.run(main())
```

### 7.3 코드 적용 시 주의사항

- Application 응답 생성 Model과 평가 Model을 반드시 같게 사용할 필요는 없다.
- 비교 평가에서는 평가 Model과 지표 설정을 고정한다.
- LLM 기반 평가 호출은 Timeout, Rate Limit과 일시 오류를 고려한다.
- 평가 실패를 점수 `0`으로 변환하지 않고 실패 상태로 구분한다.
- 재시도한 평가 결과는 동일한 Case Result를 덮어쓰기보다 Attempt 관계를 남긴다.
- 질문, 답변과 검색 Context 원문을 Log에 직접 기록하지 않는다.

---

## 8. 결과 해석

### 8.1 지표를 함께 해석하는 예

| 관찰 결과 | 가능한 해석 | 우선 검토 영역 |
|---|---|---|
| Context Recall 낮음 | 필요한 근거를 검색하지 못함 | Parsing, Chunking, Retrieval |
| Context Precision 낮음 | 관련 없는 Context가 상위에 많음 | Retrieval, Re-ranking |
| Recall 높고 Precision 낮음 | 필요한 근거는 있으나 Noise가 많음 | 후보 수, Re-ranking |
| Precision 높고 Recall 낮음 | 일부 정확한 근거만 검색하고 필수 근거를 누락함 | Query Expansion, 후보 수 |
| Faithfulness 낮음 | 답변이 검색 근거 밖의 Claim을 포함함 | Grounding, Prompt, Model |
| Faithfulness 높고 Correctness 낮음 | 검색 Context 자체가 부정확하거나 기준 답변과 다름 | 지식 품질, Retrieval |
| Relevancy 낮고 Faithfulness 높음 | 근거에는 충실하지만 질문에 직접 답하지 않음 | 답변 Prompt, 의도 분석 |
| 모든 자동 지표가 높고 사람 평가가 낮음 | Dataset 또는 평가 Judge가 업무 품질을 충분히 반영하지 못함 | 평가 기준, Human Calibration |

### 8.2 평균값만 사용하지 않는다

Run 전체 평균만 보면 특정 업무 영역이나 심각한 실패가 숨을 수 있다. 다음 기준으로 함께 분류한다.

- Tenant와 업무 Domain
- 질문 유형과 난이도
- 문서 유형
- 검색 결과 수
- 답변 성공·거부·부분 답변
- 지식 및 외부 자원 구성정보
- 지표별 분포, 하위 분위와 실패 Case

### 8.3 통과 기준

통과 기준은 다음 순서로 수립하는 것을 권장한다.

1. 업무 대표 Dataset을 구성한다.
2. 업무 전문가가 Case별 품질을 평가한다.
3. 자동 지표와 사람 평가의 일치도를 확인한다.
4. 심각한 오류 유형에 별도 필수 기준을 둔다.
5. Baseline을 확정하고 변경 전후 차이를 비교한다.
6. Dataset과 평가 Model 변경 시 기준선을 재검증한다.

단일 지표의 평균 Threshold만으로 운영 배포 여부를 자동 결정하지 않는다.

---

## 9. 운영 적용 시 고려사항

### 9.1 재현성

- Dataset, 지식, Runtime과 지표 Version을 고정한다.
- 평가 Model의 Provider, Model명과 주요 설정을 기록한다.
- 동일 조건의 반복 실행에서 점수 변동 범위를 확인한다.
- Prompt 또는 Judge가 변경되면 기존 결과와 직접 비교하지 않는다.

### 9.2 비용과 성능

- LLM 기반 지표는 Case와 지표 수에 비례하여 호출 비용이 증가한다.
- 개발 단계에서는 작은 대표 Dataset으로 빠르게 회귀 평가한다.
- 정기 평가는 전체 검수 Dataset으로 분리할 수 있다.
- ID·규칙 기반 지표를 병행하여 불필요한 LLM 호출을 줄인다.

### 9.3 평가 편향

- 특정 평가 Model의 문체, 언어와 Domain 선호가 점수에 영향을 줄 수 있다.
- 한국어 및 사내 전문용어 Case로 사람 평가와의 일치도를 확인한다.
- 평가 Model이 생성 Model의 오류를 그대로 선호하는지 점검한다.
- 업무상 중요한 안전성·금지 표현은 별도의 결정적 규칙으로 검사한다.

### 9.4 보안과 개인정보

- 외부 평가 Model 호출 전에 질문, 답변과 Context의 전송 허용 범위를 확인한다.
- 민감정보 Masking이 평가 의미를 훼손하지 않는지 검토한다.
- 원문을 일반 Application Log와 Trace Attribute에 기록하지 않는다.
- Dataset과 결과에 Tenant 격리 및 접근통제를 적용한다.

---

## 10. Enterprise RAG 설계와의 대응

RAGAS를 적용하더라도 프로젝트 내 책임은 다음과 같이 유지한다.

| 프로젝트 책임 | RAGAS 적용 시 역할 |
|---|---|
| Quality Evaluation | Dataset, Run, Case, 평가 조건과 결과의 생명주기 관리 |
| Evaluation Target Assembly | RAGAS 지표가 요구하는 입력 구성 |
| Evaluator Interface | RAGAS API와 내부 평가 모델 사이의 차이 격리 |
| Result Aggregation | Case 결과 검증, 누락·실패 처리와 Run 집계 |
| Quality Result Management | 결과와 실행 당시 조건의 추적 관계 유지 |
| RAG Runtime | Evaluation Context에서 검색과 답변 실행 |
| Resource Manager | 외부 평가 수단의 구성정보 관리 |
| 외부 평가 수단 | RAGAS 지표 실행과 평가 결과 반환 |

RAGAS는 다음 책임을 소유하지 않는다.

- 프로젝트의 Dataset 및 평가 승인 절차
- 평가 실행 상태와 재시도 정책
- Tenant 격리
- 지식·Runtime·외부 자원 구성정보의 추적
- 평가 결과에 따른 운영 설정 변경
- 품질 개선안의 최종 판단

이 경계를 유지하면 RAGAS의 API 또는 Version이 변경되거나 다른 평가 Framework를 도입하더라도 Quality Evaluation의 핵심 책임과 정보 모델을 유지할 수 있다.

---

## 11. 도입 전 확인사항

- [ ] 평가하려는 업무 품질 질문이 정의되어 있는가?
- [ ] 각 지표에 필요한 입력을 안정적으로 수집할 수 있는가?
- [ ] Reference와 기준 Context의 검수 책임자가 정해져 있는가?
- [ ] Dataset과 지식 Version의 호환성을 추적할 수 있는가?
- [ ] 평가 Model과 지표 설정을 Version으로 관리하는가?
- [ ] LLM 평가 결과를 사람 평가로 Calibration했는가?
- [ ] 평가 실패와 낮은 점수를 구분하는가?
- [ ] 민감정보의 외부 전송과 저장 정책을 확인했는가?
- [ ] 평가 비용, Rate Limit과 실행 시간을 수용할 수 있는가?
- [ ] 결과가 운영 설정을 자동 변경하지 않도록 분리했는가?

---

## 12. 참고 자료

다음 링크는 2026-07-29에 확인한 RAGAS 공식 문서이다. RAGAS API와 권장 방식은 Version에 따라 변경될 수 있으므로 실제 구현 시 설치 Version에 해당하는 문서를 다시 확인한다.

- [RAGAS 공식 문서](https://docs.ragas.io/en/stable/)
- [Quick Start](https://docs.ragas.io/en/stable/getstarted/quickstart/)
- [Core Concepts](https://docs.ragas.io/en/stable/concepts/)
- [사용 가능한 지표 목록](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/)
- [Context Precision](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/)
- [Context Recall](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/)
- [Faithfulness](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/faithfulness/)
- [Response Relevancy](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/answer_relevance/)
- [Factual Correctness](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/factual_correctness/)
- [RAGAS GitHub Repository](https://github.com/explodinggradients/ragas)
