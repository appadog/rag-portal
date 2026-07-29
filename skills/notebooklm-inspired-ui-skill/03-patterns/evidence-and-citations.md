# Evidence and Citation Pattern

근거 추적이 필요한 제품에만 적용한다.

## 데이터

```ts
interface Citation {
  id: string;
  index: number;
  contextId: string;
  title: string;
  excerpt: string;
  location?: {
    page?: number;
    timestamp?: number;
    section?: string;
    range?: [number, number];
  };
}
```

## 3단계 검증

1. Inline trigger
2. Hover/focus preview
3. Full Context Viewer

## Trigger

- keyboard focus
- 최소 24px hit area
- 색상 외 형태
- aria-label

```tsx
<button
  type="button"
  aria-label={`${index}번 근거: ${title}`}
  aria-expanded={open}
  aria-controls={`citation-${id}`}
>
  {index}
</button>
```

## Viewer 유형

- PDF: page + highlight
- Web: section + text
- Audio/Video: timestamp
- Table: sheet + cell range
- Image: region

## Navigation

- 이전·다음 citation
- 현재 위치
- 원문 링크
- 닫기
- Core Workspace 위치 유지

## 근거 부족

```text
현재 선택된 데이터에서 이 결과를 뒷받침하는 근거를 찾지 못했습니다.

다른 데이터를 선택하거나 질문 범위를 조정해 주세요.
```
