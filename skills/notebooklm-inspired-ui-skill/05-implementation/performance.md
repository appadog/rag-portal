# Performance

## Panel Rendering

숨겨진 무거운 Viewer를 항상 렌더링하지 않는다.

- lazy import
- visibility mount 정책
- draft state 분리

## Large Lists

- virtualization
- group rendering
- stable keys
- memoized selector
- search index

## Streaming

- token마다 전체 Markdown 재파싱 최소화
- batching
- section rendering
- 긴 코드 블록 lazy highlight
- auto scroll throttle

## Rich Outputs

- chart/editor/PDF chunk 분리
- intersection observer
- 이미지 크기 지정
- worker 검토

## Resize

pointer move마다 React state를 과도하게 갱신하지 않는다. CSS variable 또는 requestAnimationFrame을 사용하고 drag 종료 시 store에 저장한다.

## Query

- 패널별 query
- detail prefetch
- stale time
- refresh 중 기존 데이터 유지
- polling backoff

## Background Job

- WebSocket/SSE 우선 검토
- polling은 visibility 반영
- job ID 복구
- 중복 구독 방지
