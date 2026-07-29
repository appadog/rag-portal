# Design Principles

## Quiet Intelligence

AI를 시각적으로 과장하지 않는다.

- 네온·과도한 그라데이션·광택 금지
- 생성 상태는 작은 움직임과 명확한 문구
- 신뢰성은 인용과 검증 흐름으로 표현
- 브랜드 색상은 주요 행동에 제한

## Reading Before Decoration

- 본문 최대 폭 제한
- 충분한 line-height
- 일관된 제목 계층
- 카드 중첩 금지
- 텍스트 주변 여백 확보

## Parallel but Not Crowded

- 패널 gutter 유지
- Panel Header 높이 통일
- 패널별 직접 행동 수 제한
- 중앙 작업 영역 우선

## One Primary Action per Context

화면 또는 카드마다 primary action은 하나를 원칙으로 한다. 나머지는 secondary·ghost·text로 낮춘다.

## Visible System Status

사용자는 업로드·처리·생성·저장·동기화·실패·권한 상태를 이해할 수 있어야 한다.

## Reversible Exploration

Viewer 닫기, 패널 복원, 선택 해제, Undo, 스크롤 복원을 지원한다.

## Contextual Tools

- 메시지 행동: 메시지 하단
- 항목 행동: 행 우측
- 패널 행동: Panel Header
- 전역 행동: Global Header

## No Invisible Prerequisites

실행 조건을 명시한다.

```text
3개 데이터가 선택됨
```

```text
먼저 데이터를 추가해 주세요.
```

```text
편집 권한이 필요합니다.
```

disabled 버튼만 보여주고 이유를 숨기지 않는다.
