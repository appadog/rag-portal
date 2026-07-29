# Testing

## Unit

- keyboard handler
- width clamp
- selection logic
- output status mapping
- token helper

## Component

- default
- focus
- disabled
- loading
- error
- keyboard
- accessible name
- visual states

## Integration

1. Context 추가
2. 항목 선택
3. 작업 제출
4. 생성 중 중단
5. 결과 완료
6. 결과 열기
7. Evidence Viewer
8. 패널 복원

## Responsive Viewports

- 1440×1024
- 1280×800
- 1024×768
- 768×1024
- 390×844

## Accessibility

- axe
- keyboard-only
- focus trap/restore
- screen reader smoke test
- 200% zoom
- reduced motion
- high contrast

## Visual Regression

- Empty
- Ready
- Active
- Viewer
- Editor
- Rail
- Generating
- Error
- Dark mode

## E2E

```text
새 Workspace
→ 데이터 추가
→ 선택
→ 질문
→ citation 열기
→ 결과 저장
→ 결과 패널 열기
```

모바일에서는 Back과 draft 복원을 추가한다.
