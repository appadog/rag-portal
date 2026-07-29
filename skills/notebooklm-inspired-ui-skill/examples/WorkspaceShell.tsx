import type { CSSProperties, ReactNode } from 'react';
import styled from 'styled-components';

interface WorkspaceShellProps {
  header: ReactNode;
  context: ReactNode;
  main: ReactNode;
  output: ReactNode;
  contextWidth?: number;
  outputWidth?: number;
}

export function WorkspaceShell({
  header,
  context,
  main,
  output,
  contextWidth = 300,
  outputWidth = 340,
}: WorkspaceShellProps) {
  const style = {
    '--context-width': `${contextWidth}px`,
    '--output-width': `${outputWidth}px`,
  } as CSSProperties;

  return (
    <Shell>
      <Header>{header}</Header>
      <Grid style={style}>
        <Panel as="nav" aria-label="컨텍스트">
          {context}
        </Panel>
        <Panel as="main" aria-label="주요 작업">
          {main}
        </Panel>
        <Panel as="aside" aria-label="결과물">
          {output}
        </Panel>
      </Grid>
    </Shell>
  );
}

const Shell = styled.div`
  display: grid;
  grid-template-rows:
    ${({ theme }) => theme.layout.globalHeaderHeight}
    1fr;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: ${({ theme }) => theme.colors.canvas};
`;

const Header = styled.header`
  min-width: 0;
`;

const Grid = styled.div`
  display: grid;
  grid-template-columns:
    minmax(
      ${({ theme }) => theme.layout.contextPanelMin},
      var(--context-width)
    )
    minmax(${({ theme }) => theme.layout.contentMin}, 1fr)
    minmax(
      ${({ theme }) => theme.layout.outputPanelMin},
      var(--output-width)
    );
  gap: ${({ theme }) => theme.layout.panelGap};
  min-width: 0;
  min-height: 0;
  padding:
    0
    ${({ theme }) => theme.layout.appPadding}
    ${({ theme }) => theme.layout.appPadding};

  @media (max-width: 1199px) {
    display: block;
  }
`;

const Panel = styled.section`
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: ${({ theme }) => theme.radius.xl};
  background: ${({ theme }) => theme.colors.surface};
`;
