# Core Workspace Pattern

## 역할

제품 핵심 가치가 발생하는 영역이다.

- AI Chat
- 문서 편집기
- Flow Canvas
- 데이터 분석
- 코드 실행
- 비교 화면
- 미디어 편집

## 초기 상태

```text
Identity
Summary or Orientation
Primary Next Actions
Suggested Tasks
Composer or Main Control
```

기능 목록보다 현재 컨텍스트를 먼저 설명한다.

## 읽기 폭

```css
max-width: 720px;
margin-inline: auto;
```

표·차트·캔버스는 전체 폭 사용 가능.

## Message Layout

- User: 연한 배경 블록
- Assistant: 문서형 본문
- Actions: 답변 하단
- Citations: 인라인
- Status: 생성 indicator

업무 도구에서는 과도한 메신저형 말풍선을 피한다.

## Quick Actions

초기 행동은 2–4개.

- 노트
- 요약
- 보고서
- 분석

기능이 많으면 Output Panel이나 Command Menu로 이동한다.

## Suggested Prompts

- 현재 컨텍스트와 관련
- 한 문장
- 선택 즉시 입력 또는 실행
- 가로 스크롤 가능
- 입력 시작 시 축소

## Response Actions

- 저장
- 복사
- 다시 생성
- 피드백
- 더보기

아이콘에는 Tooltip과 aria-label이 필요하다.
