import { Link } from 'react-router-dom';
import styled from 'styled-components';
import { Button, Card, Pill } from '../shared/ui/primitives';
import { theme } from '../shared/styles/theme';

const Wrap = styled.div`
  max-width: 860px;
  margin: 30px auto;
  h1 {
    font-size: 30px;
    letter-spacing: -1.2px;
    margin: 10px 0;
  }
  p {
    color: ${theme.colors.muted};
    line-height: 1.7;
  }
  .steps {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin: 26px 0;
  }
  .step {
    padding: 20px;
    h2 {
      font-size: 16px;
      margin: 14px 0 6px;
    }
    span {
      display: grid;
      place-items: center;
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: ${theme.colors.brandSoft};
      color: ${theme.colors.brand};
      font-weight: 800;
    }
  }
`;
export function GuidePage() {
  return (
    <Wrap>
      <Pill $tone="brand">처음이신가요?</Pill>
      <h1>
        문서에서 답을 찾는 일을
        <br />더 쉽게 시작해 보세요.
      </h1>
      <p>
        RAG Portal은 답변이 그럴듯해 보이는 것보다, 문서의 어떤 부분을 근거로 했는지 확인하는 데
        집중합니다.
      </p>
      <div className="steps">
        {[
          [
            '1',
            '간단히 알려주세요',
            '문서 언어와 질문 유형을 바탕으로 검색의 기반이 되는 임베딩 모델을 추천해요.',
          ],
          [
            '2',
            '문서를 올리세요',
            '파싱과 후보 준비는 자동으로 진행되고, 기다리는 동안 다른 일을 할 수 있어요.',
          ],
          [
            '3',
            '답변을 비교하세요',
            '같은 질문에 대한 답과 근거를 보고 가장 도움이 되는 방식을 확정하세요.',
          ],
        ].map(([num, title, text]) => (
          <Card className="step" key={num}>
            <span>{num}</span>
            <h2>{title}</h2>
            <p>{text}</p>
          </Card>
        ))}
      </div>
      <Link to="/rag/new">
        <Button>첫 지식 공간 만들기 →</Button>
      </Link>
    </Wrap>
  );
}
