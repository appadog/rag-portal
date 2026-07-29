import { NavLink, Outlet, useLocation } from 'react-router-dom';
import styled, { css } from 'styled-components';
import { theme } from '../styles/theme';

const Shell = styled.div`
  height: 100dvh;
  min-height: 0;
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr);
  overflow: hidden;
  @media (max-width: 720px) {
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(0, 1fr);
  }
`;
const Aside = styled.aside`
  min-height: 0;
  padding: 22px 14px;
  border-right: 1px solid ${theme.colors.line};
  background: var(--rp-canvas);
  display: flex;
  flex-direction: column;
  gap: 24px;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
  @media (max-width: 720px) {
    padding: var(--rp-space-2) var(--rp-space-3);
    border-right: 0;
    border-bottom: 1px solid var(--rp-border);
    flex-direction: row;
    align-items: center;
    gap: var(--rp-space-3);
    & > div:first-child {
      padding: 0;
      small {
        display: none;
      }
    }
  }
`;
const Brand = styled.div`
  padding: 4px 10px;
  font-size: 18px;
  font-weight: 850;
  letter-spacing: -0.7px;
  span {
    color: ${theme.colors.brand};
  }
  small {
    display: block;
    margin-top: 4px;
    color: ${theme.colors.muted};
    font-size: 11px;
    font-weight: 650;
    letter-spacing: 0;
  }
`;
const Nav = styled.nav`
  display: flex;
  flex-direction: column;
  gap: 4px;
  a {
    padding: 10px 11px;
    border-radius: ${theme.radius.sm};
    color: ${theme.colors.muted};
    font-size: 14px;
    font-weight: 680;
  }
  a.active {
    background: ${theme.colors.brandSoft};
    color: ${theme.colors.brand};
  }
  @media (max-width: 720px) {
    flex-direction: row;
    overflow: auto;
    a {
      white-space: nowrap;
    }
  }
`;
const Footer = styled.div`
  margin-top: auto;
  border-top: 1px solid ${theme.colors.line};
  padding: 16px 10px 4px;
  color: ${theme.colors.muted};
  font-size: 12px;
  line-height: 1.5;
  @media (max-width: 720px) {
    display: none;
  }
`;
const Main = styled.main<{ $workspace: boolean }>`
  min-width: 0;
  min-height: 0;
  padding: 30px 40px 48px;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
  ${({ $workspace }) =>
    $workspace &&
    css`
      display: flex;
      flex-direction: column;
      overflow: hidden;
      @media (max-width: 1380px) {
        overflow-y: auto;
      }
    `}
  @media (max-width: 720px) {
    padding: var(--rp-space-4);
  }
`;

export function AppShell() {
  const { pathname } = useLocation();
  const isWorkspace = /^\/rag\/[^/]+$/.test(pathname);

  return (
    <Shell>
      <Aside>
        <Brand>
          <span>◒</span> RAG Portal<small>문서를 믿을 수 있는 답으로</small>
        </Brand>
        <Nav>
          <NavLink to="/rag">내 지식 공간</NavLink>
          <NavLink to="/rag/new">새로 만들기</NavLink>
          <NavLink to="/guide">처음이신가요?</NavLink>
        </Nav>
        <Footer>
          로그인된 계정
          <br />
          <strong style={{ color: theme.colors.ink }}>Hanati Workspace</strong>
        </Footer>
      </Aside>
      <Main $workspace={isWorkspace}>
        <Outlet />
      </Main>
    </Shell>
  );
}
