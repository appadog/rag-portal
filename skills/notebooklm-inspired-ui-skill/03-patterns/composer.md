# Composer Pattern

## 역할

- 입력
- 현재 컨텍스트
- 첨부
- 모드
- 실행
- 중단
- 추천 행동

## Anatomy

```text
┌───────────────────────────────────────────────┐
│ Context summary / attachments                 │
│ Multiline input                               │
│                                               │
│ [Tools] [Mode]               [Context] [Send] │
└───────────────────────────────────────────────┘
Suggested prompts
```

## 크기

- 최소 `96px`
- 최대 `240px`
- 이후 내부 스크롤
- 모바일 safe-area

## IME Safe

```ts
function handleKeyDown(
  event: React.KeyboardEvent<HTMLTextAreaElement>,
) {
  if (event.nativeEvent.isComposing) return;

  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    submit();
  }
}
```

## 상태

```ts
type ComposerState =
  | 'idle'
  | 'typing'
  | 'submitting'
  | 'generating'
  | 'disabled'
  | 'error';
```

생성 중 Send는 Stop으로 전환할 수 있다.

## Context Summary

```text
7개 데이터 사용
```

```text
선택된 데이터 없음
```

클릭 시 Context Panel을 연다.

## Validation

- 공백
- 최대 길이
- 미지원 첨부
- 권한 부족
- 필수 컨텍스트 없음

disabled 상태만으로 이유를 전달하지 않는다.
