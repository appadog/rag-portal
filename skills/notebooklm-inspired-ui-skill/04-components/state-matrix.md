# Component State Matrix

## 기본 상태

| 상태 | 시각 | 행동 | 접근성 |
|---|---|---|---|
| Default | 기본 surface | 실행 가능 | accessible name |
| Hover | subtle background | 동일 | 해당 없음 |
| Focus | 2px ring | keyboard 가능 | focus visible |
| Active | darker surface | press | 해당 없음 |
| Selected | soft brand | 지속 선택 | aria-selected/pressed |
| Disabled | disabled token | 실행 불가 | disabled |
| Loading | geometry 유지 | 중복 방지 | aria-busy |
| Error | error message | retry | aria-describedby |

## List Item

| 상태 | 배경 | Leading | Trailing |
|---|---|---|---|
| Default | surface | type icon | status/menu |
| Hover | surfaceHover | 동일 | menu |
| Selected | surfaceSelected | check | menu |
| Processing | surface | spinner/type | progress |
| Failed | dangerSoft | error | retry |
| Unavailable | surfaceSubtle | muted | request/remove |

## Output Card

| 상태 | 내용 |
|---|---|
| Empty type | 설명 + Create |
| Queued | 제목 + 대기 + Cancel |
| Generating | 제목 + 단계 + Stop |
| Ready | 제목 + 시각 + Open |
| Failed | 제목 + 오류 + Retry |
| Readonly | Open만 |

## Composer

| 상태 | Action | Input | 안내 |
|---|---|---|---|
| Idle empty | disabled | enabled | placeholder |
| Typing | Send | enabled | context |
| Submitting | loading | readonly 선택 | 전송 중 |
| Generating | Stop | 정책 선택 | 생성 중 |
| Error | Retry/Send | enabled | inline error |
| Disabled | disabled | disabled | 이유 |

## Panel

| 상태 | 크기 | 콘텐츠 |
|---|---|---|
| Hidden | 0 | inert |
| Rail | 64px | icon |
| Compact | 약 240px | metadata 축소 |
| Default | 표준 | 전체 |
| Expanded | 확대 | viewer/editor |

## 데이터 상태

- initial
- loading
- refreshing
- empty
- partial
- stale
- offline
- permission denied
- failed
- success
