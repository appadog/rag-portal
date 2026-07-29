# NotebookLM-Inspired UI Skill Package

NotebookLM의 UI를 복제하는 자료가 아니라, 해당 제품이 복잡한 AI 작업을 다루는 방식을 재사용 가능한 규칙으로 정리한 실무용 스킬 패키지다.

## 포함 내용

- 실제 UI 구조 분석
- Context / Work / Output 정보 구조
- 멀티패널 워크스페이스 패턴
- Chat·근거 검증·결과물 관리 패턴
- 디자인 토큰과 컴포넌트 API
- React + TypeScript + styled-components 구현
- Zustand와 서버 상태 분리
- WCAG 2.2 AA 접근성
- 테스트·성능·제품 적용 규칙

## 구조

```text
notebooklm-inspired-ui-skill/
├── SKILL.md
├── README.md
├── manifest.json
├── 01-analysis/
├── 02-foundations/
├── 03-patterns/
├── 04-components/
├── 05-implementation/
├── 06-adaptation/
├── examples/
└── references/
```

## 설치 예시

```text
.agents/
└── skills/
    └── notebooklm-inspired-ui/
```

또는 사용하는 AI 코딩 도구의 skill/rules 디렉터리에 전체 폴더를 배치한다.

## 사용 예시

```text
이 프로젝트의 핵심 사용자 흐름을 분석하고
notebooklm-inspired-ui 스킬을 적용해
정보 구조, 패널 역할, 반응형 전략을 설계해줘.
```

```text
현재 프로젝트의 기술 스택과 기존 디자인 시스템을 유지하면서
workspace-shell, components, accessibility 문서를 적용해
워크스페이스 화면을 구현해줘.
```

## 주의

색상과 크기는 공개 UI 관찰을 기반으로 재설계한 권장 토큰이며 공식 Google 디자인 토큰이 아니다. 제품 브랜드와 기존 디자인 시스템을 우선한다.
