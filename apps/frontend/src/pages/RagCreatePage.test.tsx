import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { RagCreatePage } from './RagCreatePage';

describe('RagCreatePage', () => {
  it('shows several model candidates and selects the recommendation from the answers', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <RagCreatePage />
      </MemoryRouter>,
    );

    await user.click(screen.getByText('네, 중요해요'));
    await user.click(screen.getByRole('button', { name: '후보 비교하기 →' }));

    expect(
      await screen.findByRole('heading', { name: '문서 전체에 사용할 모델을 선택해 주세요.' }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole('radio', { name: /검색|운영/ })).toHaveLength(3);
    expect(screen.getByRole('radio', { name: /Qwen3-Embedding-0.6B/ })).toBeChecked();

    await user.click(screen.getByRole('radio', { name: /BGE-M3/ }));
    expect(screen.getByRole('radio', { name: /BGE-M3/ })).toBeChecked();
  });
});
