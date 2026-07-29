# UI Analysis

## 1. 분석 대상

- Global Header
- Sources 패널
- Chat 패널
- Studio 패널
- Source Viewer
- Note 또는 Artifact Editor
- Composer
- Citation
- 패널 확장·축소
- 생성 결과물 목록

목표는 시각 복제가 아니라 복잡성을 다루는 방식을 추출하는 것이다.

## 2. 전체 인상

UI는 세 특성을 결합한다.

1. 문서 도구의 안정감
2. 대화형 AI의 즉시성
3. 작업 공간의 병렬성

화면은 화려한 효과보다 읽기와 조작에 집중한다. 넓은 화면에서 세 영역을 동시에 보여주지만 각 패널을 흰색 surface와 넓은 여백으로 분리하여 복잡한 대시보드처럼 보이지 않게 한다.

## 3. 공간 구성

### Canvas

아주 연한 유색 중립 배경은 흰 패널 사이의 gutter를 드러낸다. 강한 테두리 없이도 화면 구조를 이해하게 한다.

### Panel

- 독립된 흰색 surface
- 큰 radius
- 일정한 gutter
- 고정 Panel Header
- 내부 독립 스크롤
- 축소·확장 가능
- 강한 shadow 사용 안 함

### 비율

1440px에서 관찰되는 구조를 일반화하면 다음 범위가 적절하다.

- Context: `240–360px`
- Main: `minmax(520px, 1fr)`
- Output: `300–420px`
- Gutter: `12–16px`
- Outer padding: `16px`

이는 공식 값이 아닌 권장 범위다.

## 4. 시각 계층

색상보다 크기·간격·굵기·surface 경계·선택 배경으로 계층을 표현한다.

- 본문: 거의 검정
- 메타데이터: 중간 회색
- 선택: 연한 브랜드 배경
- 주요 실행: 단일 강조색
- 위험: 상태색 + 아이콘 + 설명

## 5. Sources 패널

Sources는 파일 목록이 아니라 AI 작업의 **컨텍스트 범위 제어기**다.

구성:

- 검색·정렬·필터
- Add source
- Select all
- 개별 checkbox
- 파일 유형 아이콘
- 제목·메타데이터
- 처리·접근 상태
- Source Viewer 전환

핵심 UX:

- 행 클릭: 상세 열기
- checkbox: 작업 컨텍스트 포함
- more: 관리 행동

이 패턴은 데이터셋 열기/분석 대상 포함, 파일 미리보기/배치 선택 같은 다른 도메인에도 적용할 수 있다.

## 6. Chat 패널

화면 중심의 Core Workspace다.

초기 상태:

- 아이콘 또는 이모지
- 제목
- 소스 수·수정 시각
- 요약
- 저장·평가 행동
- 빠른 생성 행동
- 추천 질문
- Composer

작업 시작 후:

```text
Summary
→ User Message
→ Assistant Response
→ Message Actions
→ Composer
```

사용자 메시지는 연한 블록으로, AI 답변은 문서형 본문으로 표시한다. 메신저형 말풍선보다 읽기 중심이다.

## 7. Studio 패널

Studio는 결과 타입 선택기이자 결과물 라이브러리다.

```text
Output Type Tiles
→ Create / Customize
→ Generated Output List
```

특징:

- 결과 타입을 tile로 빠르게 인지
- 같은 타입의 결과물을 여러 개 생성
- 결과물을 객체로 저장
- 생성 중 다른 작업 수행
- 상세 편집 시 패널 폭 확장

다른 제품에서는 보고서·테스트 결과·배포 기록·생성 이미지·실행 로그·내보내기 파일로 치환할 수 있다.

## 8. 레이아웃 전환

```text
기본: Sources | Chat | Studio
원문 검토: Source Viewer | Chat | Studio
결과 편집: Sources | Chat | Artifact Editor
집중: Rail | Expanded Work | Editor
```

새 페이지로 이동하기보다 작업 맥락을 유지하면서 공간 비율을 바꾸는 것이 핵심이다.

## 9. Composer

Composer는 다음을 한 표면에 결합한다.

- 사용자 입력
- 현재 컨텍스트 수
- 전송 또는 중단
- 추천 질문
- 추가 도구

사용자는 무엇을 입력하고 어떤 컨텍스트가 사용되며 지금 실행 가능한지 이해할 수 있어야 한다.

## 10. 근거 검증

1. 본문 인라인 citation
2. hover/focus 원문 preview
3. click 후 정확한 원문 위치 열기

신뢰를 문구로 주장하지 않고 검증 가능한 상호작용으로 제공한다.

## 11. 강점

- 컨텍스트와 핵심 작업을 동시에 확인
- 입력에서 결과물 생성까지 한 화면에서 연결
- 결과가 객체로 축적
- 패널 전환 시 작업 맥락 유지
- 선택과 검증 흐름이 명확
- 읽기 UI와 생성 기능의 균형

## 12. 위험

- 좁은 화면에서 3패널 압박
- 다중 독립 스크롤의 위치 상실
- Studio 타입 증가 시 복잡도
- 추천 질문이 Composer를 과도하게 확대
- checkbox와 행 click 오작동
- 작은 회색 텍스트의 대비 저하

## 13. 결론

핵심은 3패널 자체가 아니라 다음 관계다.

```text
현재 작업 조건
→ 핵심 작업
→ 저장되는 결과
→ 필요 시 원문 또는 상세 확인
```
