# Responsive Behavior

## 1. 전략

```text
Desktop: 3개 역할 동시 표시
Tablet: 핵심 1개 + 임시 보조 1개
Mobile: 단일 작업 전체 화면
```

## 2. Breakpoint

```ts
export const breakpoints = {
  mobile: 768,
  tablet: 1200,
  wide: 1600,
} as const;
```

기존 제품 breakpoint가 있으면 기존 값을 우선한다.

## 3. Desktop

- Context / Work / Output 동시 표시
- 보조 패널 접기
- Viewer와 Editor side-by-side
- Composer는 Main 하단
- 선택적 resize

## 4. Tablet

- Main 기본 표시
- Context와 Output은 Drawer
- 한 번에 보조 하나
- 긴 편집기는 전체 화면 가능

## 5. Mobile

- route 기반 단일 화면
- Context → Work → Output → Detail
- safe-area Composer
- citation은 Bottom Sheet 또는 전체 화면
- hover 제거
- touch target 최소 44px
- Back으로 맥락 복구

## 6. 행렬

| 요소 | Desktop | Tablet | Mobile |
|---|---|---|---|
| Context | 고정/접기 | Drawer | 화면 |
| Work | 중앙 | 기본 | 기본 |
| Output | 고정/접기 | Drawer | 화면 |
| Viewer | 분할 | Drawer/전체 | 전체 |
| Composer | 패널 하단 | 하단 | safe-area |
| Citation | Popover | Popover/Sheet | Sheet |
| Resize | 선택 | 제외 | 제외 |

## 7. 작은 높이

- 추천 질문 접기
- Composer 최대 높이 제한
- Studio 타입 영역 축소
- footer가 입력을 밀어내지 않게 함

## 8. Container Query

resize 가능한 패널 내부 밀도는 container query로 제어한다.

```css
@container panel (max-width: 320px) {
  .metadata {
    display: none;
  }
}
```
