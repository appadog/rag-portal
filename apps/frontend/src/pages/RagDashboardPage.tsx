import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import styled from 'styled-components';
import { ragApi } from '../shared/api/client';
import type { RagInstance } from '../shared/api/types';
import {
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  StatusBadge,
  Button,
  Pill,
} from '../shared/ui/primitives';
import { theme } from '../shared/styles/theme';

const Header = styled.header`
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 26px;
  h1 {
    font-size: 28px;
    letter-spacing: -1.2px;
    margin: 0 0 7px;
  }
  p {
    margin: 0;
    color: ${theme.colors.muted};
  }
`;
const Grid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(275px, 1fr));
  gap: 16px;
`;
const RagCard = styled(Link)`
  display: flex;
  flex-direction: column;
  min-height: 190px;
  padding: 20px;
  transition:
    transform 0.18s,
    border-color 0.18s;
  &:hover {
    transform: translateY(-2px);
    border-color: ${theme.colors.brand};
  }
  h2 {
    font-size: 17px;
    margin: 15px 0 10px;
    letter-spacing: -0.3px;
  }
  p {
    font-size: 13px;
    color: ${theme.colors.muted};
    margin: 0;
    line-height: 1.6;
  }
  .bottom {
    margin-top: auto;
    padding-top: 15px;
    display: flex;
    justify-content: space-between;
    align-items: end;
  }
`;

function progressLabel(instance: RagInstance) {
  if (instance.status !== 'PROCESSING' || !instance.progress) return undefined;
  return `${instance.progress.completed}/${instance.progress.total} 후보 준비 중`;
}
export function RagDashboardPage() {
  const [items, setItems] = useState<RagInstance[]>();
  const [error, setError] = useState<string>();
  const load = () => {
    setError(undefined);
    ragApi
      .list()
      .then(setItems)
      .catch((err: Error) => setError(err.message));
  };
  useEffect(load, []);
  if (error) return <ErrorState message={error} retry={load} />;
  if (!items) return <LoadingState label="지식 공간을 정리하고 있어요…" />;
  return (
    <>
      <Header>
        <div>
          <h1>내 지식 공간</h1>
          <p>문서를 올리고, 답변을 비교해 나만의 검색 방식을 찾아보세요.</p>
        </div>
        <Link to="/rag/new">
          <Button>+ 새로 만들기</Button>
        </Link>
      </Header>
      {items.length === 0 ? (
        <EmptyState
          title="아직 지식 공간이 없어요"
          description="문서를 올리고 답변을 비교하면, 내 자료에 맞는 검색을 정할 수 있어요."
          action={
            <Link to="/rag/new">
              <Button>첫 지식 공간 만들기</Button>
            </Link>
          }
        />
      ) : (
        <Grid>
          {items.map((item) => (
            <Card as={RagCard} to={`/rag/${item.id}`} key={item.id}>
              <StatusBadge status={item.status} progress={progressLabel(item)} />
              <h2>{item.name}</h2>
              <p>
                문서 {item.documents.length}개 · {item.embeddingModel}
              </p>
              {item.status === 'PROCESSING' && (
                <p style={{ marginTop: 9 }}>{item.progress?.message}</p>
              )}
              <div className="bottom">
                <Pill $tone={item.graphragEnabled ? 'brand' : 'muted'}>
                  {item.graphragEnabled ? '연결형 질문 켜짐' : '일반 질문 중심'}
                </Pill>
                <span style={{ color: theme.colors.muted, fontSize: 12 }}>열기 →</span>
              </div>
            </Card>
          ))}
        </Grid>
      )}
    </>
  );
}
