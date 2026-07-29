# Accessibility

목표: WCAG 2.2 AA

## Landmarks

```tsx
<header />
<main />
<nav aria-label="컨텍스트" />
<aside aria-label="결과물" />
```

## Focus Order

시각 순서와 DOM 순서를 일치시킨다.

```text
Header → Context → Core → Output
```

Drawer가 열리면 focus trap을 적용한다.

## Panel Toggle

```tsx
<button
  aria-label="컨텍스트 패널 접기"
  aria-expanded={open}
  aria-controls="context-panel"
/>
```

## Resize Handle

```tsx
<div
  role="separator"
  tabIndex={0}
  aria-orientation="vertical"
  aria-valuemin={240}
  aria-valuemax={420}
  aria-valuenow={width}
/>
```

Arrow key로 조절한다.

## Dynamic Status

```tsx
<div role="status" aria-live="polite">
  보고서 생성이 완료되었습니다.
</div>
```

스트리밍 전체 본문을 live region으로 읽지 않는다.

## Composer

- label 또는 aria-label
- 설명과 오류 연결
- IME safe
- send/stop 상태 이름
- shortcut 안내

## Citation

- button semantic
- 출처 제목 aria-label
- hover/focus 동등
- Viewer heading focus
- 닫을 때 trigger로 복원

## Contrast

- 일반 텍스트 4.5:1
- 큰 텍스트 3:1
- UI boundary 3:1
- placeholder 의존 금지

## Motion

- reduced motion
- 자동 재생 제어
- flashing 금지
- animation 중 focus 손실 방지

## Touch Target

- Desktop 권장 40px
- Mobile 최소 44px
- citation hit area 확장

## Color

상태는 색상과 icon·text·shape 중 하나를 함께 사용한다.
