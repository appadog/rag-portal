# Interaction Model

## 1. 기본 루프

```text
컨텍스트 추가
→ 선택
→ 질문 또는 작업 실행
→ 결과 검토
→ 근거/상세 확인
→ 결과 저장
→ 새로운 결과로 확장
```

## 2. Select와 Open

- checkbox: 작업 범위 포함
- row: 상세 열기
- more: 항목 관리

클릭 이벤트 중복을 방지하고 키보드에서도 두 행동을 구분한다.

## 3. Panel Mode

```ts
type PanelMode = 'hidden' | 'rail' | 'compact' | 'default' | 'expanded';
```

- hidden: 모바일·집중 모드
- rail: 아이콘만, `56–72px`
- compact: 메타데이터 축소
- default: 표준
- expanded: Viewer·Editor 활성

## 4. Scroll Ownership

```text
App Shell: overflow hidden
Panel: overflow hidden
Panel Header: fixed
Panel Body: overflow auto
Composer: sticky
```

body scroll + panel scroll + nested list scroll가 동시에 생기지 않게 한다.

## 5. 자동 스크롤

- 사용자가 하단 80px 이내면 자동 유지
- 위로 이동하면 중단
- 새 내용 발생 시 `새 결과 보기`
- 생성 완료 후 focus 강제 이동 금지

## 6. 저장

- 자동 저장
- 명시적 저장
- 결과물을 새 객체로 저장
- 내보내기

자동 저장 성공마다 Toast를 띄우지 않는다. 실패 시 행동을 요구한다.

## 7. 삭제

복구 가능: 즉시 삭제 + Undo Toast.

복구 불가: 대상 이름과 결과를 명시한 Dialog.

## 8. 키보드

| 행동 | 단축키 |
|---|---|
| 전송 | Enter |
| 줄바꿈 | Shift + Enter |
| 검색 | `/` 또는 Cmd/Ctrl + K |
| 패널 토글 | Cmd/Ctrl + Shift + 숫자 |
| 상세 닫기 | Escape |

IME 조합 중 Enter는 전송하지 않는다.
