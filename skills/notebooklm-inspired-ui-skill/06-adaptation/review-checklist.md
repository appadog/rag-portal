# Review Checklist

## Information Architecture

- [ ] Context, Work, Output 역할이 구분되어 있다.
- [ ] 필요하지 않은 패널이 제거되어 있다.
- [ ] 현재 컨텍스트를 확인할 수 있다.
- [ ] 결과물의 객체 관리 여부가 결정되었다.
- [ ] 상세 route와 패널 상태 관계가 정의되었다.

## Layout

- [ ] 중앙 영역 최소 너비가 보장된다.
- [ ] Panel Header 높이가 일관된다.
- [ ] gutter가 유지된다.
- [ ] 스크롤 소유권이 명확하다.
- [ ] 작은 화면에서 Drawer/route로 전환된다.
- [ ] 긴 콘텐츠 읽기 폭이 제한된다.

## Visual

- [ ] Canvas와 Surface가 구분된다.
- [ ] Shadow는 overlay에 집중된다.
- [ ] Primary color는 주요 행동에 제한된다.
- [ ] 모든 섹션이 카드가 아니다.
- [ ] 계층이 크기와 간격으로 표현된다.

## Components

- [ ] Button variant가 명시적이다.
- [ ] IconButton에 aria-label이 있다.
- [ ] List item의 Select와 Open이 구분된다.
- [ ] 상태 행렬이 있다.
- [ ] loading 중 geometry가 유지된다.
- [ ] disabled 이유가 설명된다.

## AI

- [ ] 준비/처리/생성 상태가 구분된다.
- [ ] 가짜 진행률이 없다.
- [ ] Stop/Cancel 정책이 있다.
- [ ] job ID로 상태를 복구한다.
- [ ] 근거 부족이 일반 결과와 구분된다.
- [ ] Citation 필요성이 검토되었다.

## Responsive

- [ ] Desktop 동시 작업 수가 정의되었다.
- [ ] Tablet은 핵심 + 보조 하나다.
- [ ] Mobile은 단일 작업이다.
- [ ] safe-area가 반영된다.
- [ ] hover 전용 기능이 없다.

## Accessibility

- [ ] keyboard-only 흐름이 가능하다.
- [ ] focus ring이 보인다.
- [ ] Dialog focus trap/restore가 있다.
- [ ] live region이 과도하지 않다.
- [ ] contrast 기준을 충족한다.
- [ ] resize handle이 keyboard를 지원한다.
- [ ] citation preview가 focus에서도 동작한다.

## Implementation

- [ ] token 외 값이 하드코딩되지 않았다.
- [ ] server state와 UI state가 분리되었다.
- [ ] shared UI가 domain store를 참조하지 않는다.
- [ ] 무거운 Viewer는 lazy loading된다.
- [ ] panel별 Error Boundary를 검토했다.
- [ ] visual regression 시나리오가 있다.
