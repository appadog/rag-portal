# Decision Trees

## 3패널

```text
입력 목록과 결과를 핵심 작업과 동시에 봐야 하는가?
├─ 아니오 → 단일 또는 2패널
└─ 예
   ├─ 화면 폭이 충분한가?
   │  ├─ 아니오 → Drawer
   │  └─ 예
   └─ 보조 패널이 지속적으로 필요한가?
      ├─ 아니오 → 필요 시 Drawer
      └─ 예 → 3패널
```

## Citation

```text
결과를 원문으로 검증해야 하는가?
├─ 아니오 → 제외
└─ 예
   ├─ 원문 위치를 제공할 수 있는가?
   │  ├─ 아니오 → Source link
   │  └─ 예 → Inline + Preview + Viewer
```

## Output Panel

```text
결과가 저장·재사용·내보내기 되는가?
├─ 아니오 → Core 내부
└─ 예
   ├─ 결과 유형이 여러 개인가?
   │  ├─ 아니오 → 결과 목록
   │  └─ 예 → Type Tiles + Artifact List
```

## Resize

```text
콘텐츠 유형별 필요한 폭이 크게 다른가?
├─ 아니오 → 고정 폭 + 접기
└─ 예
   ├─ Desktop 중심인가?
   │  ├─ 아니오 → 제외
   │  └─ 예 → 접근 가능한 resize
```

## Sticky Composer

```text
긴 콘텐츠를 읽으며 반복 입력하는가?
├─ 아니오 → 일반 폼
└─ 예 → 패널 하단 sticky
```

## Card

```text
독립 객체이며 자체 행동을 가지는가?
├─ 아니오 → section/list
└─ 예 → card
```
