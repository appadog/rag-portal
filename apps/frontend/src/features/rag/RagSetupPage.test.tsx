import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, vi } from 'vitest';
import { RagSetupPage } from './RagWorkspace';

function renderSetup() {
  return render(
    <MemoryRouter initialEntries={['/rag/travel/setup']}>
      <Routes>
        <Route path="/rag/:id/setup" element={<RagSetupPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('RagSetupPage comparison workspace', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockImplementation((query: string) => ({
        matches: query === '(max-width: 47.9375rem)',
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    );
  });
  afterEach(() => vi.unstubAllGlobals());

  it('shows one mobile candidate at a time while retaining a clear candidate switcher', async () => {
    const user = userEvent.setup();
    renderSetup();

    await screen.findByRole('heading', { name: '답변과 근거를 비교해 주세요.' });
    expect(screen.getAllByRole('checkbox')).toHaveLength(1);
    const candidateSwitcher = screen.getByLabelText('비교 후보 전환');
    expect(within(candidateSwitcher).getByText('후보 1: 일반 검색')).toHaveAttribute(
      'aria-pressed',
      'true',
    );

    await user.click(within(candidateSwitcher).getByText('후보 4: 키워드 검색'));
    expect(screen.getAllByRole('checkbox')).toHaveLength(1);
    expect(screen.getByText('원본 조각 없음')).toBeInTheDocument();
  });
});
