import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { RagDashboardPage } from './RagDashboardPage';

describe('RagDashboardPage', () => {
  it('shows instances from the mock fallback', async () => {
    render(
      <MemoryRouter>
        <RagDashboardPage />
      </MemoryRouter>,
    );
    expect(await screen.findByRole('heading', { name: '출장비 규정 RAG' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /새로 만들기/ })).toBeInTheDocument();
  });
});
