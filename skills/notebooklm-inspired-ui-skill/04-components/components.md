# Component Guidelines

## Button

```ts
type ButtonVariant =
  | 'primary'
  | 'secondary'
  | 'ghost'
  | 'text'
  | 'danger';

type ButtonSize = 'small' | 'medium' | 'large';
```

규칙:

- 화면 내 primary는 하나를 원칙으로 한다.
- loading 중 너비를 유지한다.
- icon과 label 간격은 `8px`.
- destructive action은 별도 의미를 갖는다.
- disabled 이유를 주변 설명으로 제공한다.

## IconButton

- 아이콘 `18–20px`
- hit area Desktop `40px`, Mobile `44px`
- aria-label 필수
- hover/focus Tooltip
- selected는 배경과 아이콘으로 표현

## TextField

```text
Label
Field
Helper or Error
```

- placeholder는 label 대체 불가
- error는 field 바로 아래
- readonly와 disabled 구분
- 검색 field에는 clear
- prefix/suffix가 입력 폭을 과도하게 줄이지 않게 함

## Checkbox

- label 전체 클릭 가능
- checked·unchecked·indeterminate
- row click과 이벤트 분리
- 색상 외 check mark

## SearchField

- 검색 아이콘
- clear
- 결과 수
- keyboard shortcut 선택
- debounce는 필요할 때만

## ListItem

```text
Leading
Primary text
Secondary text
Trailing
```

- title 최대 2줄
- metadata 1줄
- hover·selected·focus
- trailing action은 keyboard focus에서도 노출

## Panel

- 동일 radius와 header 높이
- body scroll
- 선택적 sticky footer
- nested panel shadow 금지

## PanelHeader

- title
- count/status
- 최대 3개 직접 행동
- overflow menu
- 긴 제목 말줄임

## Card

```ts
type CardVariant = 'plain' | 'outlined' | 'interactive' | 'selected';
```

- border와 shadow 동시 과용 금지
- interactive card는 button/link semantic
- 내부에 button이 있으면 card 전체 button 금지

## Chip

- filter
- suggestion
- status
- tag
- compact action

긴 설명을 chip 안에 넣지 않는다.

## Badge

- 짧은 상태
- icon/text 병행
- 색상만으로 의미 전달 금지

## Tooltip

- 한두 문장 이하
- interactive content 금지
- hover와 focus
- 모바일 핵심 정보 금지

## Popover

적합:

- citation preview
- filter
- quick menu
- contextual settings

복잡한 입력은 Dialog 또는 Drawer로 전환한다.

## Dialog

- 제목
- 설명
- body
- secondary
- primary

위험 행동은 대상을 명시한다.

## Drawer

- 보조 탐색
- 긴 설정
- tablet panel
- mobile detail

focus trap, background inert, focus restore를 적용한다.

## Tabs

동일 계층 콘텐츠 전환에만 사용한다. Panel toggle 대체로 사용하지 않는다.

## Segmented Control

짧은 mode 전환에 사용한다. 3–4개 이하 권장.

## Progress

- determinate/indeterminate 구분
- label
- screen reader value
- 짧은 작업은 button loading

## Skeleton

- 실제 구조와 유사
- 과도한 shimmer 금지
- reduced motion

## Toast

- 메시지 하나 + 선택적 행동
- 성공·Undo·백그라운드 완료
- 해결이 필요한 오류는 inline

## ResizeHandle

- 넓은 hit area
- hover
- keyboard arrow
- double click reset
- aria values

## Composer

- multiline
- context indicator
- send/stop
- attachments
- suggestions
- IME safe
- max height
- error message

## Citation

- inline trigger
- preview
- full viewer
- keyboard
- source location
