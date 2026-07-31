import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import { ragApi } from '../shared/api/client';
import type { EmbeddingBenchmark, EmbeddingModelRecommendation } from '../shared/api/types';
import { Button, Card, Input, Pill } from '../shared/ui/primitives';
import { theme } from '../shared/styles/theme';

const Wrap = styled.div`
  max-width: 850px;
  margin: 0 auto;
`;
const Header = styled.header`
  margin: 14px 0 26px;
  h1 {
    font-size: 30px;
    letter-spacing: -1.3px;
    margin: 0 0 8px;
  }
  p {
    margin: 0;
    color: ${theme.colors.muted};
  }
`;
const Step = styled.div`
  display: flex;
  gap: 9px;
  align-items: center;
  margin-bottom: 22px;
  color: ${theme.colors.muted};
  font-size: 13px;
  font-weight: 700;
  .on {
    color: ${theme.colors.brand};
  }
  .dot {
    width: 22px;
    height: 22px;
    display: grid;
    place-items: center;
    border-radius: 50%;
    background: ${theme.colors.surfaceMuted};
  }
  .on .dot {
    background: ${theme.colors.brand};
    color: white;
  }
`;
const Choices = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin: 20px 0;
`;
const Choice = styled.label<{ $selected: boolean }>`
  display: block;
  cursor: pointer;
  border: 1px solid ${({ $selected }) => ($selected ? theme.colors.brand : theme.colors.line)};
  background: ${({ $selected }) => ($selected ? theme.colors.brandSoft : 'white')};
  padding: 16px;
  border-radius: ${theme.radius.md};
  input {
    position: absolute;
    opacity: 0;
  }
  strong {
    display: block;
    font-size: 15px;
    margin-bottom: 5px;
  }
  span {
    font-size: 13px;
    color: ${theme.colors.muted};
    line-height: 1.5;
  }
`;
const Field = styled.label`
  display: block;
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 8px;
  span {
    display: block;
    color: ${theme.colors.muted};
    font-weight: 500;
    font-size: 12px;
    margin: 6px 0 8px;
  }
`;
const ModelChoices = styled.div`
  display: grid;
  gap: 10px;
  margin: 20px 0;
`;
const ModelChoice = styled.label<{ $selected: boolean }>`
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  cursor: pointer;
  border: 1px solid ${({ $selected }) => ($selected ? theme.colors.brand : theme.colors.line)};
  background: ${({ $selected }) => ($selected ? theme.colors.brandSoft : theme.colors.surface)};
  padding: 16px;
  border-radius: ${theme.radius.md};
  input {
    margin: 3px 0 0;
  }
  strong,
  span {
    display: block;
  }
  strong {
    font-size: 15px;
  }
  .model-name {
    margin-top: 3px;
    color: ${theme.colors.muted};
    font-size: 12px;
    font-weight: 700;
  }
  .model-copy,
  .model-tradeoff {
    margin-top: 7px;
    color: ${theme.colors.muted};
    font-size: 13px;
    line-height: 1.5;
  }
  .model-tradeoff {
    color: ${theme.colors.ink};
  }
`;
const BenchmarkPanel = styled.section`
  margin: var(--rp-space-5) 0;
  padding: var(--rp-space-4);
  border: 1px solid var(--rp-border);
  border-radius: var(--rp-radius-md);
  background: var(--rp-surface-subtle);
  h3 {
    margin: 0;
    font-size: var(--rp-font-size-16);
  }
  .meta,
  .empty {
    margin: var(--rp-space-2) 0 0;
    color: var(--rp-ink-muted);
    font-size: var(--rp-font-size-12);
    line-height: var(--rp-line-normal);
  }
  .results {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
    gap: var(--rp-space-3);
    margin-top: var(--rp-space-3);
  }
  .result {
    padding: var(--rp-space-3);
    border: 1px solid var(--rp-border);
    border-radius: var(--rp-radius-sm);
    background: var(--rp-surface);
  }
  .result strong,
  .result span {
    display: block;
  }
  .result strong {
    overflow-wrap: anywhere;
    font-size: var(--rp-font-size-13);
  }
  .result span {
    margin-top: var(--rp-space-1);
    color: var(--rp-ink-muted);
    font-size: var(--rp-font-size-12);
  }
`;

function percent(value: number | null) {
  if (value === null) return '측정 안 됨';
  return `${(value <= 1 ? value * 100 : value).toFixed(1)}%`;
}

function BenchmarkSummary({
  benchmark,
  loading,
}: {
  benchmark?: EmbeddingBenchmark;
  loading: boolean;
}) {
  return (
    <BenchmarkPanel aria-live="polite" aria-busy={loading}>
      <h3>우리 문서 실측 결과</h3>
      {loading ? (
        <p className="empty">실측 결과를 확인하고 있어요.</p>
      ) : !benchmark ? (
        <p className="empty">
          아직 우리 문서 실측 결과를 실행하지 않았어요. 점수 없이 문서 특성 기반 추천만 보여드려요.
        </p>
      ) : (
        <>
          <p className="meta">
            {benchmark.run.corpusLabel} · 질문 {benchmark.run.queryCount}개 ·{' '}
            {benchmark.run.createdAt}
          </p>
          <div className="results" aria-label="임베딩 모델 실측 결과">
            {benchmark.results.map((result) => (
              <div className="result" key={result.modelId}>
                <strong>{result.modelId}</strong>
                <span>
                  Recall@1 {percent(result.recallAt1)} · Recall@5 {percent(result.recallAt5)}
                </span>
                <span>
                  MRR {percent(result.mrr)} · 평균 {result.averageLatencyMs ?? '측정 안 됨'}ms
                </span>
                <span>
                  {result.provider} · {result.dimension ?? '차원 미측정'}차원 · {result.status}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </BenchmarkPanel>
  );
}

export function RagCreatePage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [language, setLanguage] = useState('ko');
  const [privateData, setPrivateData] = useState('no');
  const [multiHop, setMultiHop] = useState('no');
  const [name, setName] = useState('새 지식 공간');
  const [saving, setSaving] = useState(false);
  const [recommendations, setRecommendations] = useState<EmbeddingModelRecommendation[]>([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [loadingRecommendations, setLoadingRecommendations] = useState(false);
  const [benchmark, setBenchmark] = useState<EmbeddingBenchmark>();
  const [loadingBenchmark, setLoadingBenchmark] = useState(false);
  const questionnaire = {
    primaryLanguage: language,
    requiresOnPremise: privateData === 'yes',
    budget: 'standard',
    multiHopQuestions: multiHop === 'yes',
  };
  const showRecommendations = async () => {
    setLoadingRecommendations(true);
    setLoadingBenchmark(true);
    try {
      const [items, latestBenchmark] = await Promise.all([
        ragApi.recommendEmbeddingModels(questionnaire),
        ragApi.latestEmbeddingBenchmark(),
      ]);
      setRecommendations(items);
      setBenchmark(latestBenchmark);
      setSelectedModel(items.find((item) => item.recommended)?.id ?? items[0]?.id ?? '');
      setStep(2);
    } finally {
      setLoadingRecommendations(false);
      setLoadingBenchmark(false);
    }
  };
  const create = async () => {
    if (!selectedModel) return;
    setSaving(true);
    try {
      const item = await ragApi.create({
        name,
        embeddingModel: selectedModel,
        questionnaire,
      });
      navigate(`/rag/${item.id}/setup`);
    } finally {
      setSaving(false);
    }
  };
  return (
    <Wrap>
      <Header>
        <Pill $tone="brand">새 지식 공간</Pill>
        <h1>문서에 맞는 검색을 함께 찾아볼게요.</h1>
        <p>어려운 설정은 몇 가지 질문으로 추천하고, 나머지는 실제 답변을 보며 고를 수 있어요.</p>
      </Header>
      <Step>
        <span className={step >= 1 ? 'on' : ''}>
          <i className="dot">1</i> 간단한 질문
        </span>
        <span>—</span>
        <span className={step >= 2 ? 'on' : ''}>
          <i className="dot">2</i> 모델 선택
        </span>
        <span>—</span>
        <span>
          <i className="dot">3</i> 문서 올리기
        </span>
      </Step>
      {step === 1 ? (
        <Card style={{ padding: 28 }}>
          <h2 style={{ marginTop: 0 }}>어떤 문서를 다루나요?</h2>
          <Field>
            주로 어떤 언어로 작성되어 있나요?
            <span>언어에 맞는 임베딩 모델을 추천하는 데 사용합니다.</span>
          </Field>
          <Choices>
            {[
              ['ko', '한국어 중심', '한국어와 영어가 섞인 문서도 잘 찾습니다.'],
              ['multi', '여러 언어', '여러 언어를 비슷한 비중으로 사용합니다.'],
            ].map(([value, title, desc]) => (
              <Choice key={value} $selected={language === value}>
                <input
                  type="radio"
                  checked={language === value}
                  onChange={() => setLanguage(value)}
                />
                <strong>{title}</strong>
                <span>{desc}</span>
              </Choice>
            ))}
          </Choices>
          <Field>
            문서를 외부 서비스로 보낼 수 없나요?
            <span>예를 선택하면 자체 운영에 적합한 모델을 우선합니다.</span>
          </Field>
          <Choices>
            {[
              ['no', '아니요', '일반적인 클라우드 환경에서 사용할게요.'],
              ['yes', '네, 중요해요', '사내 또는 폐쇄망에서만 처리해야 해요.'],
            ].map(([value, title, desc]) => (
              <Choice key={value} $selected={privateData === value}>
                <input
                  type="radio"
                  checked={privateData === value}
                  onChange={() => setPrivateData(value)}
                />
                <strong>{title}</strong>
                <span>{desc}</span>
              </Choice>
            ))}
          </Choices>
          <Field>여러 인물·조직·사건의 관계를 함께 묻는 일이 많나요?</Field>
          <Choices>
            {[
              ['no', '아니요', '규정, 매뉴얼처럼 사실을 빠르게 찾는 일이 주로 있어요.'],
              ['yes', '네, 자주 있어요', '연결된 정보를 따라가며 답해야 하는 질문이 많아요.'],
            ].map(([value, title, desc]) => (
              <Choice key={value} $selected={multiHop === value}>
                <input
                  type="radio"
                  checked={multiHop === value}
                  onChange={() => setMultiHop(value)}
                />
                <strong>{title}</strong>
                <span>{desc}</span>
              </Choice>
            ))}
          </Choices>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 24 }}>
            <Button onClick={() => void showRecommendations()} disabled={loadingRecommendations}>
              {loadingRecommendations ? '추천을 준비하는 중…' : '후보 비교하기 →'}
            </Button>
          </div>
        </Card>
      ) : (
        <Card style={{ padding: 28 }}>
          <Pill $tone="brand">임베딩 모델 후보</Pill>
          <h2>문서 전체에 사용할 모델을 선택해 주세요.</h2>
          <p style={{ color: theme.colors.muted, lineHeight: 1.6 }}>
            추천은 출발점일 뿐이에요. 선택은 이 지식 공간의 설정으로 저장되고, 실제 임베딩 연결
            뒤에는 모든 문서가 같은 임베딩 공간을 사용합니다. 현재 로컬 미리보기 검색은 비교
            기준선인 lexical 방식으로 동작합니다.
          </p>
          <BenchmarkSummary benchmark={benchmark} loading={loadingBenchmark} />
          <ModelChoices role="radiogroup" aria-label="임베딩 모델 후보">
            {recommendations.map((item) => (
              <ModelChoice key={item.id} $selected={selectedModel === item.id}>
                <input
                  type="radio"
                  name="embedding-model"
                  checked={selectedModel === item.id}
                  onChange={() => setSelectedModel(item.id)}
                />
                <span>
                  {item.recommended && <Pill $tone="brand">추천</Pill>}
                  <strong>{item.label}</strong>
                  <span className="model-name">{item.id}</span>
                  <span className="model-copy">{item.reason}</span>
                  <span className="model-tradeoff">확인할 점: {item.tradeoff}</span>
                </span>
              </ModelChoice>
            ))}
          </ModelChoices>
          <div style={{ marginTop: 22 }}>
            <Field>
              지식 공간 이름
              <Input
                value={name}
                onChange={(event) => setName(event.target.value)}
                aria-label="지식 공간 이름"
              />
            </Field>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 26 }}>
            <Button $variant="secondary" onClick={() => setStep(1)}>
              이전
            </Button>
            <Button onClick={create} disabled={saving || !selectedModel || !name.trim()}>
              {saving ? '만드는 중…' : '문서 올리기 →'}
            </Button>
          </div>
        </Card>
      )}
    </Wrap>
  );
}
