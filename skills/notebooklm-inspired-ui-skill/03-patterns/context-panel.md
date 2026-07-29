# Context Panel Pattern

## 역할

Context Panel은 탐색과 현재 작업 범위 제어를 동시에 제공한다.

대상:

- 소스·데이터셋·파일·프로젝트·자산·환경·비교 대상

## 기본 구조

```text
Panel Header
Search / Filter
Primary Add Action
Select All or Scope Summary
Grouped Item List
Processing / Error Items
```

## Item Anatomy

```text
[Select] [Type Icon] Title                  [More]
                     Metadata / Status
```

## 상호작용

- checkbox: 작업 범위 포함
- row: 상세 열기
- more: 관리 메뉴
- type icon: 정보 전달
- status: 오류나 처리 상세

## 그룹

항목이 많을 때만 적용한다.

- 자동 분류
- 사용자 정의 그룹
- 접기/펼치기
- 그룹 선택
- 검색 결과 상태 유지

## 상태

```ts
type ContextItemStatus =
  | 'uploading'
  | 'processing'
  | 'ready'
  | 'syncing'
  | 'failed'
  | 'unavailable';
```

- uploading: 실제 progress, 취소 정책
- processing: indeterminate 가능
- failed: 오류·Retry·Remove
- unavailable: 권한 또는 원본 삭제 설명

## Empty

```text
아직 추가된 데이터가 없습니다.

파일, 링크 또는 텍스트를 추가하면
이 작업 공간에서 분석할 수 있습니다.

[데이터 추가]
```

## Search

검색 중에도 selected 상태를 유지한다.

```text
검색 결과 외 3개 항목이 선택되어 있습니다.
```
