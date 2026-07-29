# Visual Language

## Surface

```text
Canvas
└─ Panel
   ├─ Subtle Section
   ├─ Interactive Row
   └─ Elevated Overlay
```

- Canvas와 Panel은 배경 차이로 구분
- Panel 내부는 border와 spacing
- shadow는 Popover·Modal·floating control에 집중

## Border

- 패널: `borderSubtle`
- 입력: `borderDefault`
- focus: `borderFocus`
- 위험: 상태색 + 아이콘 + 문구

## Iconography

- outline icon 기본
- 일반 `18–20px`
- 메타 `16px`
- 주요 기능 `20–24px`
- 동일 역할은 동일 아이콘
- 타입별 색상은 제한적으로 사용

## Illustration

- Empty State 메시지보다 약함
- 핵심 행동을 가리지 않음
- 복잡한 장식 배경 금지

## Cards

다음 경우만 사용한다.

- 독립적으로 선택 가능한 결과물
- 생성 타입 shortcut
- 상태와 행동이 함께 있는 객체
- 반복 가능한 콘텐츠 단위

일반 본문 그룹을 무조건 카드로 만들지 않는다.

## Pills and Chips

- 추천 질문
- 태그
- 상태
- 짧은 필터
- compact action

긴 문장은 pill로 만들지 않는다.

## Focus

```css
outline: 2px solid var(--border-focus);
outline-offset: 2px;
```

selected는 지속 상태, focus는 현재 키보드 위치다.
