# Claude 프롬프트 라이브러리
### Chat · Cowork · Code 통합 — 단위 프롬프트와 전체흐름 프롬프트 141선

작성일 2026-08-16 · 출처는 각 카드에 개별 표기 · 수집 범위: Anthropic 공식 문서/엔지니어링 블로그, 영문 개발 블로그(Medium·dev.to·builder.io·developertoolkit), 한국어 블로그(브런치·velog·gpters·potato-ai 외), GitHub 커맨드 저장소 12곳, 유튜브·SNS 내용을 정리한 2차 기사

---

## 이 문서를 읽는 법

프롬프트를 **모아서 늘어놓는 것**은 별 쓸모가 없습니다. 같은 프롬프트라도 언제 쓰느냐에 따라 결과가 갈리기 때문입니다. 그래서 이 문서는 세 층으로 되어 있습니다.

**제1부**는 2026년 현재 Claude가 어떻게 작동하는지에 대한 다섯 가지 사실입니다. 이걸 모르면 아래 프롬프트를 잘못된 자리에 씁니다. 특히 "예전에 좋았던 프롬프트가 지금은 해롭다"는 부분은 꼭 읽어 주세요.

**제2부**는 분류 체계입니다. 141개를 2축(환경 × 유형)으로 갈랐습니다.

**제3부**는 프롬프트 카드입니다. 그대로 복사해서 쓰면 됩니다.

**제4부**는 활용 방안입니다. 개인 → 팀 → 조직으로 넘어가는 4단계 성숙도 모델과, 이암허브 실무(제안서·컨설팅 보고서·교육영상·스마트팜 데이터)에 붙이는 구체적 경로, 그리고 30·60·90일 도입 로드맵입니다.

---

# 제1부. 먼저 알아야 할 다섯 가지

## 1. 유일한 진짜 제약은 컨텍스트다

Claude Code 공식 문서의 첫 문장이 이렇습니다.

> "Most best practices are based on one constraint: **Claude's context window fills up fast, and performance degrades as it fills.**"

거의 모든 요령이 여기서 파생됩니다. 컨텍스트가 차오를수록 회상 정확도가 떨어지는 현상을 Anthropic은 **context rot**이라고 부릅니다. 트랜스포머가 토큰 쌍마다 관계를 계산하기 때문에 생기는 구조적 한계이고, 모델이 좋아진다고 사라지지 않습니다. 그래서 목표는 "많이 넣기"가 아니라 **"원하는 결과의 확률을 최대화하는 가장 작은 고신호 토큰 집합"**입니다.

실무 번역:

| 원칙 | 구체적 수치 |
|---|---|
| CLAUDE.md / 폴더 지침 | 200줄 이하 (60~80줄이면 더 좋다) |
| SKILL.md 본문 | 500줄 이하 |
| 무관한 작업 사이 | `/clear` (Chat이면 새 대화) |
| 넓은 조사 | 서브에이전트로 격리하고 결론만 회수 |

> **"Bloated CLAUDE.md files cause Claude to ignore your actual instructions!"**
> 규칙을 넣었는데도 계속 어긴다면, 십중팔구 파일이 너무 길어서 그 규칙이 묻힌 것입니다.

## 2. 두 번째 축은 '검증 수단'이다

공식 문서가 가장 임팩트 큰 실천으로 꼽는 것은 프롬프트 문장 기교가 아니라 **Claude가 스스로 돌려볼 수 있는 검사**를 주는 것입니다.

> "Give Claude a check it can run: tests, a build, a screenshot to compare. It's the difference between a session you watch and one you walk away from."
> "Claude stops when the work looks done. Without a check it can run, 'looks done' is the only signal available, and **you become the verification loop.**"

Claude Code 제작자 Boris Cherny는 이렇게 표현했습니다 — *"검증 수단을 주면 최종 결과 품질이 2~3배가 된다."*

문서 작업에도 그대로 적용됩니다. "숫자는 CSV 기준으로 쓰고, 추정이 필요한 내용은 '확인 필요'로 표시" 같은 한 줄이 검증 수단 역할을 합니다. 카드 `D-06`, `F-08`, `C-22`가 이 원칙의 구현체입니다.

## 3. 쪼개는 기준이 바뀌었다 — 추론이 아니라 '검증 게이트'

과거에는 "1단계 프롬프트 → 2단계 프롬프트 → 3단계 프롬프트"로 사람이 잘게 쪼개는 것이 미덕이었습니다. 지금은 아닙니다.

> "With adaptive thinking and subagent orchestration, Claude handles most multistep reasoning internally. Explicit prompt chaining is still useful when you need to **inspect intermediate outputs** or **enforce a specific pipeline structure**."

즉 **쪼개는 이유가 '추론을 돕기 위해서'에서 '검증 게이트를 끼우거나 컨텍스트를 격리하기 위해서'로 이동**했습니다.

| 쪼개라 | 합쳐라 |
|---|---|
| 중간 산출물을 사람이 검사해야 함 | 단순한 다단계 추론 (모델이 알아서 함) |
| 파이프라인 구조를 강제해야 함 | 한 문장으로 결과를 설명할 수 있는 작업 |
| 리뷰·승인 게이트가 필요함 | 단계 간 맥락 공유가 많은 작업 |

Claude Code에도 같은 기준이 있습니다. **"diff를 한 문장으로 설명할 수 있으면 계획 단계를 건너뛰라."**

## 4. 2026년에는 '더 시키기'가 아니라 '덜 시키기'다

가장 반직관적이지만 가장 중요한 변화입니다. Claude 3 세대용으로 튜닝했던 프롬프트 상당수가 지금은 **역효과**를 냅니다.

| 옛날 프롬프트 | 지금의 공식 지침 |
|---|---|
| "double-check your answer" / "re-verify before responding" | Opus 5는 시키지 않아도 자기 검증을 한다. **재작성이 아니라 삭제**하라. 비용만 늘고 결과는 나빠진다 |
| "CRITICAL: You MUST use this tool when..." | 최신 모델은 시스템 프롬프트에 더 민감해져 **과트리거**한다. "Use this tool when..." 수준으로 낮춰라 |
| assistant 응답 prefill | Claude 4.6 이상에서 **400 에러** — 기능 자체가 폐기 |
| `thinking.budget_tokens` 지정 | Claude 4.7 이상에서 **400 에러** — `thinking:{type:"adaptive"}` + `effort`로 전환 |
| 수동 `<thinking>` 태그 강제 | adaptive thinking이 대체. 수동 CoT는 thinking이 꺼져 있을 때만 fallback |
| 코드 리뷰에 "only report high-severity issues" | 문자 그대로 따라서 **덜 보고한다**. 전부 보고시키고 별도 패스에서 필터링하라 |

**기존 프롬프트를 최신 모델로 옮길 때 첫 작업은 추가가 아니라 제거입니다.** 카드 `F-11`이 삭제 대상 체크리스트입니다.

## 5. 세 환경은 같은 엔진, 다른 손잡이다

| | Claude Chat | Claude Cowork | Claude Code |
|---|---|---|---|
| 인터페이스 | 웹·앱 대화 | 데스크톱 GUI (터미널 불필요) | 터미널 CLI |
| 파일 접근 | 업로드한 것만 | 연결한 로컬 폴더 직접 읽고 씀 | 저장소 전체 |
| 대표 산출물 | 답변·아티팩트 | xlsx·pptx·docx·pdf 파일 | 커밋·PR |
| 상시 지침 | Projects 지침 / 스타일 | 폴더 지침(CLAUDE.md) | CLAUDE.md + hooks |
| 자동화 | — | 예약 작업(클라우드 실행) | 헤드리스 모드·스크립트 |
| 자산 단위 | 스타일·프로젝트 | 스킬·플러그인·커넥터 | 스킬·서브에이전트·훅 |

Anthropic 지원문서의 표현: **"Claude Cowork uses the same agentic architecture that powers Claude Code, with no terminal required."**

그래서 **프롬프트의 문법은 세 환경에서 동일합니다.** 카드 A그룹(기반문법)은 셋 다에 적용됩니다. 달라지는 것은 "무엇을 검증 수단으로 줄 수 있는가"뿐입니다 — Code는 테스트, Cowork는 원본 파일 대조, Chat은 인용 그라운딩.

> ⚠️ **오래된 한국어 글 주의** — 2026년 초에 쓰인 다수 한국어 블로그는 "예약 작업은 PC가 켜져 있어야 실행된다"고 씁니다. 현재 공식 문서는 **"Scheduled tasks run in the cloud, so they don't need your computer to be awake"**라고 명시합니다. 제품이 로컬 실행에서 클라우드 세션으로 바뀌었습니다. 오래된 글의 기능 설명은 반드시 공식 문서로 재확인하세요.

---

# 제2부. 분류 체계

## 2축 분류

**축 1 — 어디서 쓰는가 (환경)**

| 환경 | 개수 | 성격 |
|---|---:|---|
| 공통 | 48 | 세 환경 어디서나 통하는 문법·흐름·운영 |
| Chat | 14 | 글·요약·학습·의사결정, Projects/Artifacts |
| Cowork | 26 | 파일·문서·엑셀·PPT·예약 자동화 |
| Code | 53 | 코드 파악·구현·테스트·리뷰·Git |

**축 2 — 어떤 층위인가 (유형)**

| 유형 | 개수 | 정의 | 판별법 |
|---|---:|---|---|
| **단위** | 98 | 한 번의 지시로 결과가 나오는 것 | 결과물을 한 문장으로 말할 수 있다 |
| **흐름** | 20 | 여러 단계를 잇는 것. 단계 사이에 **검증 게이트**가 있다 | 중간에 사람이 확인하거나 방향을 틀 지점이 있다 |
| **운영** | 11 | 세션·컨텍스트를 관리하는 것 | 산출물이 아니라 '작업 환경'을 다룬다 |
| **자산** | 12 | 한 번 만들어 계속 쓰는 것 (CLAUDE.md·스킬·커맨드·훅) | 파일로 저장된다 |

## 7개 분류 그룹

```
A. 기반문법  (26)  ─ 모든 환경 공통. 프롬프트를 '문장'이 아니라 '구조'로 만드는 법
   · 명확한 지시 / 이유 제공 / 예시 / XML 구조화 / 역할 부여
   · 긴 문서 처리 / 사고 제어 / 출력 포맷 / 실행 강도 / 속도
   · 분량 제어 / 범위 고정 / 안전 / 환각 방지 / 리서치 / 위임 제어 / 메타

B. Chat     (14)  ─ 글쓰기 · 요약 · 의사결정 · 학습 · 번역 · Projects · Artifacts · 스타일

C. Cowork   (22)  ─ 파일정리 · 엑셀 · 보고서 · 발표자료 · 회의/메일
                    · 리서치 · 문서변환 · 예약작업 · 스킬 만들기 · 가드레일

D. Code     (36)  ─ 코드파악 · 구현 · 디버깅 · 테스트 · 리뷰 · 보안
                    · 성능 · 리팩터링 · 문서화 · Git · 궤도수정 · 메타

E. 흐름     (20)  ─ ★ 이 문서의 핵심. 단위 프롬프트를 잇는 20가지 구조
   요구사항 확정 / 개발 4단계 / TDD / 자기교정 / 평가-개선 루프
   분기 / 병렬(Sectioning·Voting) / 오케스트레이션 / 적대적 검증
   지식노동 파이프라인 / 데이터 파이프라인 / 대규모 마이그레이션
   멀티에이전트 / 병렬 브랜치 / 원샷 / 업무 자동화 성숙도 / 교차검증

F. 운영     (11)  ─ 컨텍스트 관리 · 핸드오프 · 외부 메모리 · 실패 복구
                    · 자기검증 · Cowork 세팅 · 안티패턴

G. 자산화   (12)  ─ CLAUDE.md · 폴더 지침 · 슬래시 커맨드 · 스킬 · 서브에이전트 · 훅
```

## 흐름 프롬프트를 고르는 판단표

전체흐름 프롬프트는 20개나 되지만, 실제로 고르는 기준은 세 가지 질문뿐입니다.

```
Q1. 무엇을 만들지 나도 아직 모른다
    → E-01 인터뷰 → SPEC.md → 새 세션          (모든 큰 작업의 출발점)

Q2. 만들 것은 안다. 그럼 무엇이 불확실한가?
    ├ 코드가 어디를 건드릴지 모른다     → E-02 Explore→Plan→Code→Commit
    ├ 정답이 테스트로 검증된다          → E-03 TDD 3단 루프
    ├ 품질 기준이 명확하다              → E-05 Evaluator–Optimizer
    ├ 조사 범위가 넓다                  → E-09 Orchestrator–Workers
    ├ 자료가 컨텍스트를 넘는다          → E-11 리서치 파이프라인 / E-12 데이터 파이프라인
    └ 같은 변환을 대량 반복한다         → E-13 Fan-out / E-14 마이그레이션 킷

Q3. 어떻게 틀렸는지 확인할 것인가?  (건너뛰지 말 것)
    ├ 가장 값싼 방법                    → E-16 Writer/Reviewer 두 세션
    ├ 놓치면 안 되는 검토               → E-08 Voting (3관점 다수결)
    ├ 완료 직전 마지막 관문             → E-10 Fresh context 레드팀
    └ 모델 편향까지 걷어내고 싶다       → E-20 교차검증
```

---
# 제3부. 프롬프트 카드 (복사해서 바로 쓰는 것)
각 카드는 **ID · 제목 · 언제 쓰는가 · 프롬프트 원문 · 출처** 다섯 칸으로 되어 있습니다. `{ }` 와 `[ ]` 는 채워 넣는 슬롯입니다. ★ 표시는 투자 대비 효과가 가장 큰 항목입니다.

### 카드 목차

- **A. 기반문법 · 명확한 지시** — `A-01`
- **A. 기반문법 · 이유 제공** — `A-02`
- **A. 기반문법 · 예시(few-shot)** — `A-03`
- **A. 기반문법 · XML 구조화** — `A-04`, `A-05`
- **A. 기반문법 · 역할 부여** — `A-06`
- **A. 기반문법 · 긴 문서 처리** — `A-07`, `A-08`
- **A. 기반문법 · 사고 제어** — `A-09`, `A-10`, `A-11`
- **A. 기반문법 · 출력 포맷** — `A-12`, `A-13`, `A-14`
- **A. 기반문법 · 실행 강도** — `A-15`, `A-16`
- **A. 기반문법 · 속도** — `A-17`
- **A. 기반문법 · 분량 제어** — `A-18`, `A-19`
- **A. 기반문법 · 범위 고정** — `A-20`
- **A. 기반문법 · 안전** — `A-21`
- **A. 기반문법 · 환각 방지** — `A-22`
- **A. 기반문법 · 장시간 작업** — `A-23`
- **A. 기반문법 · 리서치** — `A-24`
- **A. 기반문법 · 위임 제어** — `A-25`
- **A. 기반문법 · 메타** — `A-26`
- **B. Chat · 글쓰기** — `B-01`, `B-02`
- **B. Chat · 요약** — `B-03`, `B-04`, `B-05`
- **B. Chat · 의사결정** — `B-06`
- **B. Chat · 학습** — `B-07`, `B-08`
- **B. Chat · 번역** — `B-09`
- **B. Chat · Projects** — `B-10`, `B-11`
- **B. Chat · Artifacts** — `B-12`, `B-13`
- **B. Chat · 스타일** — `B-14`
- **C. Cowork · 파일·폴더 정리** — `C-01`, `C-02`
- **C. Cowork · 엑셀·데이터** — `C-03`, `C-04`, `C-05`
- **C. Cowork · 보고서** — `C-06`, `C-07`, `C-08`
- **C. Cowork · 발표자료** — `C-09`, `C-10`
- **C. Cowork · 회의·메일** — `C-11`, `C-12`, `C-13`
- **C. Cowork · 리서치** — `C-14`, `C-15`
- **C. Cowork · 문서 변환** — `C-16`
- **C. Cowork · 예약 작업** — `C-17`, `C-18`
- **C. Cowork · 스킬 만들기** — `C-19`, `C-20`
- **C. Cowork · 가드레일** — `C-21`, `C-22`
- **D. Code · 코드 파악** — `D-01`, `D-02`, `D-03`, `D-04`
- **D. Code · 구현** — `D-05`, `D-06`, `D-07`
- **D. Code · 디버깅** — `D-08`, `D-09`, `D-10`
- **D. Code · 테스트** — `D-11`, `D-12`, `D-13`
- **D. Code · 리뷰** — `D-14`, `D-15`, `D-16`
- **D. Code · 보안** — `D-17`, `D-18`, `D-19`
- **D. Code · 성능** — `D-20`, `D-21`, `D-22`
- **D. Code · 리팩터링** — `D-23`, `D-24`, `D-25`
- **D. Code · 문서화** — `D-26`, `D-27`
- **D. Code · Git** — `D-28`, `D-29`, `D-30`
- **D. Code · 궤도 수정** — `D-31`, `D-32`, `D-33`
- **D. Code · 메타** — `D-34`, `D-35`, `D-36`
- **E. 흐름 · 요구사항 확정** — `E-01`
- **E. 흐름 · 개발 4단계** — `E-02`
- **E. 흐름 · TDD** — `E-03`
- **E. 흐름 · 자기교정** — `E-04`
- **E. 흐름 · 평가-개선 루프** — `E-05`
- **E. 흐름 · 분기** — `E-06`
- **E. 흐름 · 병렬** — `E-07`, `E-08`
- **E. 흐름 · 오케스트레이션** — `E-09`
- **E. 흐름 · 적대적 검증** — `E-10`
- **E. 흐름 · 지식노동 파이프라인** — `E-11`
- **E. 흐름 · 데이터 파이프라인** — `E-12`
- **E. 흐름 · 대규모 마이그레이션** — `E-13`, `E-14`
- **E. 흐름 · 멀티에이전트** — `E-15`, `E-16`
- **E. 흐름 · 병렬 브랜치** — `E-17`
- **E. 흐름 · 원샷** — `E-18`
- **E. 흐름 · 업무 자동화 성숙도** — `E-19`
- **E. 흐름 · 교차검증** — `E-20`
- **F. 운영 · 컨텍스트 관리** — `F-01`, `F-02`
- **F. 운영 · 핸드오프** — `F-03`, `F-04`
- **F. 운영 · 외부 메모리** — `F-05`
- **F. 운영 · 실패 복구** — `F-06`, `F-07`
- **F. 운영 · 자기검증** — `F-08`
- **F. 운영 · Cowork 세팅** — `F-09`
- **F. 운영 · 안티패턴** — `F-10`, `F-11`
- **G. 자산화 · CLAUDE.md** — `G-01`, `G-02`, `G-03`
- **G. 자산화 · 폴더 지침** — `G-04`
- **G. 자산화 · 슬래시 커맨드** — `G-05`, `G-06`
- **G. 자산화 · 스킬** — `G-07`, `G-08`, `G-09`
- **G. 자산화 · 서브에이전트** — `G-10`, `G-11`
- **G. 자산화 · 훅** — `G-12`


## A. 기반문법 · 명확한 지시

### `A-01` '평범한 결과'를 '풀옵션 결과'로 끌어올리는 수식어

**환경** 공통 · **유형** 단위

> **언제 쓰나** 결과물이 밋밋하게 나올 때. Claude는 모호한 지시에서 '더 잘해달라'는 뜻을 추론하지 않는다.

```text
Create an analytics dashboard. Include as many relevant features and interactions as possible. Go beyond the basics to create a fully-featured implementation.

(한국어) [산출물]을 만들어줘. 관련 기능과 인터랙션을 가능한 한 많이 포함해줘. 기본 수준을 넘어서 완전한 구현으로 만들어줘.
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices


## A. 기반문법 · 이유 제공

### `A-02` 금지어만 던지지 말고 '왜'를 붙이기

**환경** 공통 · **유형** 단위

> **언제 쓰나** 규칙을 줬는데 엉뚱한 상황까지 일반화하거나, 반대로 지키지 않을 때.

```text
Your response will be read aloud by a text-to-speech engine, so never use ellipses since the text-to-speech engine will not know how to pronounce them.

(패턴) [제약]. 왜냐하면 [이유]. 그러니 [행동]해줘.
※ 나쁜 예: "NEVER use ellipses" — 이유가 없으면 Claude가 일반화하지 못한다.
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices


## A. 기반문법 · 예시(few-shot)

### `A-03` 출력 포맷·톤을 고정하는 예시 3~5개

**환경** 공통 · **유형** 단위

> **언제 쓰나** 포맷/톤/구조를 반복 재현해야 할 때. 공식 문서가 '가장 신뢰할 수 있는 조종 수단'으로 꼽음.

```text
<examples>
<example>
[예시 1 — 실제 use case 그대로]
</example>
<example>
[예시 2 — 다른 각도]
</example>
<example>
[예시 3 — 엣지 케이스]
</example>
</examples>

위 예시와 동일한 형식·톤·구조로 다음을 처리해줘: {{INPUT}}

※ 개수는 3~5개. 관련성(Relevant) · 다양성(Diverse, 엣지케이스 포함) · 태그 구조화(Structured) 3원칙.
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices


## A. 기반문법 · XML 구조화

### `A-04` 지시 + 맥락 + 입력을 태그로 분리하는 기본 골격

**환경** 공통 · **유형** 단위

> **언제 쓰나** 프롬프트가 길어져 '지시'와 '자료'가 섞이기 시작할 때. 한국어에서도 그대로 작동한다.

```text
<instructions>
[무엇을 할지 — 동사로 시작하는 명령문]
</instructions>

<context>
[배경 · 제약 · 독자 · 목적]
</context>

<input>
{{자료 또는 사용자 입력}}
</input>

<output_format>
[결과물 형식 — 항목, 길이, 표/산문 여부]
</output_format>
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices

### `A-05` 한국어권에서 검증된 6블록 구조 (역할→목표→배경→입력→출력형식→검수기준)

**환경** 공통 · **유형** 단위

> **언제 쓰나** 사내 표준 프롬프트를 만들 때. 같은 골격으로 회의록·블로그·고객응대 3종이 모두 작동한 사례.

```text
<역할>
너는 [직무/전문성]이다.
</역할>

<목표>
[이 작업이 달성해야 할 단 하나의 결과]
</목표>

<배경>
[독자, 사용 맥락, 회사 톤, 하지 말아야 할 것]
</배경>

<입력>
{{자료}}
</입력>

<출력형식>
1. [항목]
2. [항목]
3. [항목]
</출력형식>

<검수기준>
- 자료에 없는 사실은 쓰지 말 것. 필요하면 '확인 필요'로 표시.
- [기준2]
</검수기준>
```

출처: https://potato-ai.xyz/claude-prompt-structure-xml-examples-workflow/


## A. 기반문법 · 역할 부여

### `A-06` 한 문장짜리 역할 지정

**환경** 공통 · **유형** 단위

> **언제 쓰나** 도메인 톤·판단 기준을 고정하고 싶을 때. 공식 문서: '한 문장만으로도 차이가 난다.'

```text
You are a helpful coding assistant specializing in Python.

(한국어 확장형)
당신은 10년 경력의 [직무]입니다.
[기본 원칙]
- [원칙 1 — 무엇을 우선하는가]
- [원칙 2 — 어떤 표현을 피하는가]
- [원칙 3 — 답변 전에 무엇을 확인하는가]
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices


## A. 기반문법 · 긴 문서 처리

### `A-07` 20k 토큰 이상 자료는 '위'에, 질문은 '아래'에

**환경** 공통 · **유형** 단위

> **언제 쓰나** 장문 문서·다중 파일을 넣을 때. 공식 테스트 기준 최대 30% 품질 차이.

```text
<documents>
  <document index="1">
    <source>annual_report_2023.pdf</source>
    <document_content>
      {{ANNUAL_REPORT}}
    </document_content>
  </document>
  <document index="2">
    <source>competitor_analysis_q2.xlsx</source>
    <document_content>
      {{COMPETITOR_ANALYSIS}}
    </document_content>
  </document>
</documents>

Analyze the annual report and competitor analysis. Identify strategic advantages and recommend Q3 focus areas.
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices

### `A-08` 인용 먼저 → 판단 나중 (환각 차단용 그라운딩)

**환경** 공통 · **유형** 단위

> **언제 쓰나** 사실관계가 중요한 문서 분석. 근거 문장을 먼저 뽑게 하면 지어내기가 급감한다.

```text
Find quotes from the documents that are relevant to {{질문}}. Place these in <quotes> tags. Then, based on these quotes only, write your analysis. Place it in <analysis> tags.

If the documents do not contain enough information to answer, say so explicitly instead of inferring.

(한국어) 먼저 {{질문}}과 관련된 문장을 원문 그대로 <quotes> 태그 안에 인용해. 그다음 그 인용문에만 근거해서 분석을 <analysis> 태그 안에 써. 자료가 부족하면 추론하지 말고 부족하다고 명시해.
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices


## A. 기반문법 · 사고 제어

### `A-09` 도구 호출 후 반성하며 진행하게 하기

**환경** 공통 · **유형** 단위

> **언제 쓰나** 에이전트가 검색/파일 읽기 결과를 그냥 흘려보내고 다음 행동으로 넘어갈 때.

```text
After receiving tool results, carefully reflect on their quality and determine optimal next steps before proceeding. Use your thinking to plan and iterate based on this new information, and then take the best next action.
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices

### `A-10` 과사고(overthinking) 억제

**환경** 공통 · **유형** 단위

> **언제 쓰나** 간단한 질문에도 장황하게 생각하며 느려질 때.

```text
Thinking adds latency and should only be used when it will meaningfully improve answer quality - typically for problems that require multistep reasoning. When in doubt, respond directly.
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices

### `A-11` 결정 번복 방지 — 하나 골라서 끝까지

**환경** 공통 · **유형** 단위

> **언제 쓰나** 접근법을 계속 바꾸며 제자리걸음할 때.

```text
When you're deciding how to approach a problem, choose an approach and commit to it. Avoid revisiting decisions unless you encounter new information that directly contradicts your reasoning. If you're weighing two approaches, pick one and see it through. You can always course-correct later if the chosen approach fails.
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices


## A. 기반문법 · 출력 포맷

### `A-12` 불릿 남발 끄고 산문으로 쓰게 하기

**환경** 공통 · **유형** 단위

> **언제 쓰나** 보고서·기고문처럼 '읽히는 글'이 필요한데 개조식 불릿만 나올 때.

```text
<avoid_excessive_markdown_and_bullet_points>
When writing reports, documents, technical explanations, analyses, or any long-form content, write in clear, flowing prose using complete paragraphs and sentences. Use standard paragraph breaks for organization and reserve markdown primarily for `inline code`, code blocks, and simple headings (## and ###). Avoid using **bold** and *italics*.

DO NOT use ordered lists (1. ...) or unordered lists (*) unless: a) you're presenting truly discrete items where a list format is the best option, or b) the user explicitly requests a list or ranking.

Instead of listing items with bullets or numbers, incorporate them naturally into sentences. NEVER output a series of overly short bullet points.
</avoid_excessive_markdown_and_bullet_points>
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices

### `A-13` 서두(preamble) 제거 — prefill 폐기 이후의 대체법

**환경** 공통 · **유형** 단위

> **언제 쓰나** '다음은 ...입니다' 같은 군더더기 도입부를 없애고 싶을 때.

```text
Respond directly without preamble. Do not start with phrases like 'Here is...', 'Based on...', etc.
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices

### `A-14` 수식을 LaTeX 없이 평문으로

**환경** 공통 · **유형** 단위

> **언제 쓰나** 한글 문서·메일에 붙여넣을 때 \frac{}{} 같은 마크업이 깨져 보일 때.

```text
Format your response in plain text only. Do not use LaTeX, MathJax, or any markup notation such as \( \), $, or \frac{}{}. Write all math expressions using standard text characters (e.g., "/" for division, "*" for multiplication, and "^" for exponents).
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices


## A. 기반문법 · 실행 강도

### `A-15` 제안이 아니라 실제로 고치게 하기

**환경** 공통 · **유형** 단위

> **언제 쓰나** '개선안을 제안해줘'라고 했더니 말만 하고 파일을 안 고칠 때.

```text
<default_to_action>
By default, implement changes rather than only suggesting them. If the user's intent is unclear, infer the most useful likely action and proceed, using tools to discover any missing details instead of guessing. Try to infer the user's intent about whether a tool call (e.g., file edit or read) is intended or not, and act accordingly.
</default_to_action>

※ 반대로 함부로 고치지 못하게 하려면 <do_not_act_before_instructions> 버전을 쓴다.
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices

### `A-16` 함부로 실행하지 못하게 막기 (보수 모드)

**환경** 공통 · **유형** 단위

> **언제 쓰나** 탐색·조사 단계인데 Claude가 성급하게 파일을 수정할 때.

```text
<do_not_act_before_instructions>
Do not jump into implementation or change files unless clearly instructed to make changes. When the user's intent is ambiguous, default to providing information, doing research, and providing recommendations rather than taking action. Only proceed with edits, modifications, or implementations when the user explicitly requests them.
</do_not_act_before_instructions>
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices


## A. 기반문법 · 속도

### `A-17` 병렬 도구 호출 강제 (체감 속도 최대 90% 개선)

**환경** 공통 · **유형** 단위

> **언제 쓰나** 파일 여러 개 읽기·검색 여러 건처럼 서로 독립적인 작업이 순차 실행될 때.

```text
<use_parallel_tool_calls>
If you intend to call multiple tools and there are no dependencies between the tool calls, make all of the independent tool calls in parallel. Prioritize calling tools simultaneously whenever the actions can be done in parallel rather than sequentially. For example, when reading 3 files, run 3 tool calls in parallel to read all 3 files into context at the same time. Maximize use of parallel tool calls where possible to increase speed and efficiency. However, if some tool calls depend on previous calls to inform dependent values like the parameters, do NOT call these tools in parallel and instead call them sequentially. Never use placeholders or guess missing parameters in tool calls.
</use_parallel_tool_calls>
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices


## A. 기반문법 · 분량 제어

### `A-18` 간결성 지시 (Opus 5는 기본 응답이 길다)

**환경** 공통 · **유형** 단위

> **언제 쓰나** 답이 너무 길 때. effort를 낮춰도 가시 응답 길이는 안 줄어들므로 명시해야 한다.

```text
Keep responses focused, brief, and concise. Keep disclaimers and caveats short, and spend most of the response on the main answer. When asked to explain something, give a high-level summary unless an in-depth explanation is specifically requested.

※ 긴 시스템 프롬프트라면 맨 끝에 리마인더를 한 번 더:
<tone_preference>
Keep outputs reasonably concise.
</tone_preference>
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5

### `A-19` 문서 산출물의 분량을 과제에 맞추기

**환경** 공통 · **유형** 단위

> **언제 쓰나** 보고서에 채우기용 요약·상투 문구가 붙을 때.

```text
Match the length of written documents to what the task needs: cover the substance, but do not pad with filler sections, redundant summaries, or boilerplate.
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5


## A. 기반문법 · 범위 고정

### `A-20` 시킨 만큼만, 그러나 끝까지

**환경** 공통 · **유형** 단위

> **언제 쓰나** 범위를 조용히 줄이거나 반대로 부풀릴 때.

```text
Deliver what was asked, at the scope intended. Make routine judgment calls yourself, and check in only when different readings of the request would lead to materially different work. If the request seems mistaken or a better approach exists, say so in a sentence and continue with the task as asked rather than quietly narrowing, widening, or transforming it. Finish the whole task, and stop short of actions that are clearly beyond what was asked.
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5


## A. 기반문법 · 안전

### `A-21` 되돌릴 수 없는 행동은 물어보게 하기

**환경** 공통 · **유형** 단위

> **언제 쓰나** 파일 삭제·강제 푸시·공유 시스템 변경이 섞인 자율 작업을 맡길 때. 무인 실행의 필수 가드레일.

```text
Consider the reversibility and potential impact of your actions. You are encouraged to take local, reversible actions like editing files or running tests, but for actions that are hard to reverse, affect shared systems, or could be destructive, ask the user before proceeding.

Examples of actions that warrant confirmation:
- Destructive operations: deleting files or branches, dropping database tables, rm -rf
- Hard to reverse operations: git push --force, git reset --hard, amending published commits
- Operations visible to others: pushing code, commenting on PRs/issues, sending messages, modifying shared infrastructure

When encountering obstacles, do not use destructive actions as a shortcut.
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices


## A. 기반문법 · 환각 방지

### `A-22` 열어보지 않은 것에 대해 말하지 않기

**환경** 공통 · **유형** 단위

> **언제 쓰나** 파일·문서를 읽지 않고 그럴듯하게 답할 때.

```text
<investigate_before_answering>
Never speculate about code you have not opened. If the user references a specific file, you MUST read the file before answering. Make sure to investigate and read relevant files BEFORE answering questions about the codebase. Never make any claims about code before investigating unless you are certain of the correct answer - give grounded and hallucination-free answers.
</investigate_before_answering>
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices


## A. 기반문법 · 장시간 작업

### `A-23` 토큰 걱정으로 조기 종료하지 않게 하기

**환경** 공통 · **유형** 단위

> **언제 쓰나** 긴 작업 중간에 '컨텍스트가 부족해서 여기서 마칩니다'로 끝나버릴 때.

```text
Your context window will be automatically compacted as it approaches its limit, allowing you to continue working indefinitely from where you left off. Therefore, do not stop tasks early due to token budget concerns. As you approach your token budget limit, save your current progress and state to memory before the context window refreshes. Always be as persistent and autonomous as possible and complete tasks fully, even if the end of your budget is approaching. Never artificially stop any task early regardless of the context remaining.
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices


## A. 기반문법 · 리서치

### `A-24` 복잡한 리서치를 체계화하는 한 문단

**환경** 공통 · **유형** 단위

> **언제 쓰나** 조사 범위가 넓고 근거의 신뢰도가 중요한 작업 앞에 붙인다.

```text
Search for this information in a structured way. As you gather data, develop several competing hypotheses. Track your confidence levels in your progress notes to improve calibration. Regularly self-critique your approach and plan. Update a hypothesis tree or research notes file to persist information and provide transparency. Break down this complex research task systematically.
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices


## A. 기반문법 · 위임 제어

### `A-25` 서브에이전트 남발 억제 (Opus 5는 위임을 너무 쉽게 한다)

**환경** 공통 · **유형** 단위

> **언제 쓰나** 간단한 일까지 에이전트를 띄워 비용이 튈 때. 멀티에이전트는 일반 대화의 약 15배 토큰을 쓴다.

```text
Delegate to a subagent only for large tasks that are genuinely independent and parallelizable, such as a wide multi-file investigation. Do not delegate work you can finish yourself in a handful of tool calls, and do not use subagents to verify or double-check your own work. If one subagent can complete the task, use one rather than several, and keep spawn counts low.
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5


## A. 기반문법 · 메타

### `A-26` 프롬프트를 개선하게 하는 프롬프트 (공식 개선기 5단계)

**환경** 공통 · **유형** 단위

> **언제 쓰나** 반복 사용할 프롬프트를 자산으로 다듬을 때. 분류 정확도 30% 향상이 보고된 절차.

```text
아래 프롬프트를 개선해줘. 다음 5가지를 순서대로 적용해.

<original_prompt>
{{기존 프롬프트}}
</original_prompt>

1. 답변 전에 단계적으로 생각할 전용 섹션을 추가해라.
2. 예시가 있으면 XML 태그로 표준화해라. 없으면 3~5개를 새로 만들어라. 예시는 관련성 있고, 다양하고(엣지케이스 포함), 태그로 감싸야 한다.
3. 각 예시에 "왜 그 답이 나오는지" 추론 과정을 덧붙여라.
4. 모호한 표현, 문법 오류, 구조 문제를 고쳐라. "하지 마라"는 금지형 대신 "무엇을 하라"는 지시형으로 바꿔라.
5. 출력 형식을 강제할 방법을 제안해라.

개선본을 내놓기 전에, 무엇을 왜 바꿨는지 항목별로 먼저 설명해줘.
```

출처: https://claude.com/blog/prompt-improver


## B. Chat · 글쓰기

### `B-01` 퇴고 3조건 (문장길이·수동태·용어)

**환경** Chat · **유형** 단위

> **언제 쓰나** 초안은 있는데 문장이 늘어지고 번역투일 때.

```text
아래 글을 퇴고해줘. 조건: 한 문장 40자 이내, 수동태 제거, 전문 용어는 괄호로 뜻 풀이.

{{원문}}
```

출처: https://community.linkareer.com/employment_data/6142510

### `B-02` 2단계 첨삭 (논리 → 표현)

**환경** Chat · **유형** 단위

> **언제 쓰나** 한 번에 다 고치라고 하면 논리 손질이 표현 손질에 묻힐 때.

```text
아래 글을 2단계로 첨삭해줘.
1단계: 논리 흐름·핵심 메시지 점검 — 무엇이 빠졌고 무엇이 순서가 틀렸는지만 지적. 아직 고치지 마.
2단계: 내가 1단계에 동의하면, 번역투·클리셰를 교정한 최종본을 써줘.

{{원문}}
```

출처: https://community.linkareer.com/employment_data/6142510


## B. Chat · 요약

### `B-03` 회의록 → 실행 체크리스트 (추측 금지 조항 포함)

**환경** Chat · **유형** 단위

> **언제 쓰나** 회의록에서 '이번 주에 바로 할 일'만 뽑아야 할 때. 담당자·일정 환각을 막는 마지막 줄이 핵심.

```text
아래 회의록을 읽고 실행 체크리스트로 정리해줘.
목적: 이번 주에 바로 처리할 일을 찾는 것.
출력 형식:
1. 한 문장 결론
2. 결정된 사항
3. 바로 할 일
4. 담당자나 일정이 확인되지 않은 항목
5. 다음 회의에서 물어볼 질문

자료에 없는 담당자, 일정, 숫자는 추측하지 말고 '확인 필요'로 표시해줘.

{{회의록}}
```

출처: https://potato-ai.xyz/claude-action-checklist-long-doc-workflow/

### `B-04` 고객 피드백 → 제품 개선 항목

**환경** Chat · **유형** 단위

> **언제 쓰나** 흩어진 VOC를 개선 과제로 압축할 때.

```text
아래 고객 피드백을 제품 페이지 개선에 쓸 수 있게 정리해줘. 먼저 반복해서 나오는 불만을 5개 이하로 묶어줘. 그다음 각 불만마다 1. 사용자가 헷갈린 지점, 2. 페이지에서 고칠 문장, 3. 추가 확인이 필요한 근거를 나눠줘. 과장된 표현은 피하고, 원문에 없는 기능은 만들지 마.

{{피드백 모음}}
```

출처: https://potato-ai.xyz/claude-action-checklist-long-doc-workflow/

### `B-05` 자료 → 초보자용 글 구조

**환경** Chat · **유형** 단위

> **언제 쓰나** 전문 자료를 대중용 콘텐츠로 옮길 때.

```text
아래 자료를 초보자용 블로그 글 흐름으로 바꿔줘. 결과는 1. 제목 후보 5개, 2. TL;DR, 3. 핵심 3줄 요약, 4. 본문 H2 구성, 5. 자주 묻는 질문, 6. 출처 확인이 필요한 문장 순서로 정리해줘. 표는 쓰지 말고 짧은 문단과 목록으로 풀어줘.

{{자료}}
```

출처: https://potato-ai.xyz/claude-action-checklist-long-doc-workflow/


## B. Chat · 의사결정

### `B-06` 가상 전문가 4인 패널로 다관점 검토

**환경** Chat · **유형** 단위

> **언제 쓰나** 혼자 판단하기 어려운 기획·투자·조직 결정. 관점이 섞이지 않게 역할을 분리하는 게 핵심.

```text
질문에 답할 때, 당신은 4명의 가상 전문가로 구성된 팀을 만들어주세요:
- 데이터 분석가 (객관적 데이터와 수치)
- 창의적 전략가 (혁신적 관점)
- 비판적 평가자 (문제점과 리스크 지적)
- 실무 전문가 (현실적 적용 가능성)

각자 독립적으로 의견을 낸 뒤, 마지막에 네 의견이 충돌하는 지점을 먼저 정리하고 그다음 종합 결론을 내려줘.

질문: {{질문}}
```

출처: https://www.gotai.co.kr/%ED%81%B4%EB%A1%9C%EB%93%9C-%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8/


## B. Chat · 학습

### `B-07` 소크라테스식 튜터

**환경** Chat · **유형** 단위

> **언제 쓰나** 개념을 '아는 것 같은' 상태에서 실제로 아는 상태로 넘어갈 때.

```text
{{주제}}에 대한 소크라테스식 튜터가 되어줘. 규칙:
1) 내가 먼저 설명하면 논리적 빈틈을 찾아 질문한다
2) 내 답변에 반례나 엣지 케이스를 제시한다
3) 최종적으로 개선된 이해도를 요약한다

정답을 먼저 알려주지 마. 내가 스스로 도달하게 해줘.
```

출처: https://gongbuhow.com/genai/prompts/study-prompts/

### `B-08` 자료 → 문제 세트 생성

**환경** Chat · **유형** 단위

> **언제 쓰나** 교육자료·매뉴얼의 이해도를 점검할 문항이 필요할 때.

```text
{{주제}}에 대해 다음 형식의 문제를 생성해줘:
- 기초 이해 확인 문제 5개
- 응용/분석 문제 5개
- 실제 시나리오 기반 문제 3개
- 오답 함정이 있는 객관식 5개

각 문제마다 정답과 '왜 다른 선택지가 틀렸는지'를 함께 달아줘.
```

출처: https://gongbuhow.com/genai/prompts/study-prompts/


## B. Chat · 번역

### `B-09` 비즈니스 번역 지침 (프로젝트 지침용)

**환경** Chat · **유형** 단위

> **언제 쓰나** 같은 톤으로 반복 번역해야 할 때. Projects 지침에 넣어두면 매번 지정할 필요가 없다.

```text
한국어를 영어로 번역하세요. 비즈니스 이메일에 적합한 격식체를 사용하세요. 한국어 고유 표현은 의역하되 괄호 안에 원문을 병기하세요. 문장당 20단어를 넘기지 마세요.
```

출처: https://aijeong.com/%ED%81%B4%EB%A1%9C%EB%93%9C-%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8-%EA%B8%B0%EB%8A%A5-%EC%82%AC%EC%9A%A9%EB%B2%95%EC%A7%80%EC%B9%A8%EC%84%A4%EC%A0%95-%EB%B0%8F-%EC%B6%94%EC%B2%9C/


## B. Chat · Projects

### `B-10` Projects 지침 4요소 (말투·독자·형식·금지)

**환경** Chat · **유형** 단위

> **언제 쓰나** 프로젝트 지침을 처음 쓸 때. 길게 쓰면 오히려 무시되므로 이 4가지만 짧게.

```text
당신은 [분야] 전문 에디터입니다.
- 모든 글은 [말투: 해요체/합쇼체]로 작성하세요.
- 독자는 [독자]입니다.
- 한 문단은 3~5문장으로 구성하세요. 소제목에는 ### 을 사용하세요.
- 과장 표현(혁신적, 극대화, 완벽한 등)은 사용하지 마세요.
- 글 마지막에 3줄 요약을 추가하세요.

※ 운영 원칙: 지침은 길게 쓰지 말고 말투·독자·출력 형식·금지 사항 정도만 짧게 유지해야 관리가 쉽다.
```

출처: https://potato-ai.xyz/claude-projects-long-document-workflow/

### `B-11` 프로젝트 지식 정합성 점검

**환경** Chat · **유형** 단위

> **언제 쓰나** 프로젝트에 문서가 쌓여 서로 모순되기 시작할 때. 주기적으로 돌리는 위생 프롬프트.

```text
지금 이 프로젝트의 지식 파일들만 근거로 답해줘.
1. 서로 충돌하는 서술이 있는 문서 쌍과 그 문장을 짚어줘.
2. 날짜·수치가 오래돼 보이는 항목을 표시해줘.
3. 어느 문서에도 답이 없는 '빈칸' 주제를 알려줘.
추측하지 말고, 근거 문서명을 각 항목에 달아줘.
```

출처: https://potato-ai.xyz/claude-projects-long-document-workflow/


## B. Chat · Artifacts

### `B-12` Artifact 외부 공개 전 검수표

**환경** Chat · **유형** 단위

> **언제 쓰나** 만든 아티팩트를 링크로 공유하기 직전. 실무에서 사고를 막아주는 프롬프트.

```text
지금 만든 artifact를 외부 공개 링크로 공유하려고 합니다. 아래 기준으로 공개 전 검수표를 만들어 주세요.
1. 외부인이 봐도 되는 정보
2. 삭제해야 할 개인정보 또는 내부 정보
3. 오래된 숫자, 날짜, 가격
4. 오해를 줄 수 있는 문장
5. 링크 공유 전에 직접 눌러 봐야 할 요소

결과는 "공개 가능", "수정 필요", "공개 금지" 세 단계로 나눠 주세요.
```

출처: https://potato-ai.xyz/claude-artifacts-share-publish-workflow/

### `B-13` 내부용 아티팩트 → 공개용 사본 변환

**환경** Chat · **유형** 단위

> **언제 쓰나** 실데이터가 든 산출물을 데모용으로 바꿔야 할 때.

```text
현재 artifact를 공개용 사본으로 바꾸고 싶습니다. 아래 기준으로 수정해 주세요.
- 고객명, 회사명, 이메일, 전화번호 제거
- 내부 가격과 계약 조건 제거
- 예시는 가상의 데이터로 변경
- 첫 화면에 "예시용 데모"라고 표시
- 외부인이 기능을 이해할 수 있도록 설명 보강
```

출처: https://potato-ai.xyz/claude-artifacts-share-publish-workflow/


## B. Chat · 스타일

### `B-14` 내 글로 커스텀 스타일 학습시키기

**환경** Chat · **유형** 단위

> **언제 쓰나** Claude 답변이 '내 말투'가 아닐 때. 설정에서 Create & Edit Styles로 만든다.

```text
아래는 내가 직접 쓴 글 3편이야. 이 글들에서 반복되는 특징을 추출해줘:
- 문장 길이와 리듬
- 자주 쓰는 접속 표현과 어미
- 단락을 여는 방식과 닫는 방식
- 절대 쓰지 않는 표현

추출한 특징을 '스타일 지시문' 형태로 정리해줘. 그 지시문만 보고도 내 말투를 재현할 수 있어야 해.

{{내 글 3편}}
```

출처: https://news.aikoreacommunity.com/claude-3-conversation-styles-custom-update/


## C. Cowork · 파일·폴더 정리

### `C-01` 폴더 정리 (계획 먼저 → 승인 후 실행)

**환경** Cowork · **유형** 단위

> **언제 쓰나** 다운로드·자료 폴더가 뒤엉켰을 때. '계획 먼저·삭제 확인' 두 조항이 사고를 막는다.

```text
[폴더 경로]에 있는 파일을 주제별로 분류해줘. 중복은 해시로 찾고, 이미지는 1080px로 리사이즈, PDF는 압축. 작업 전에 계획을 먼저 보여주고, 삭제 전에는 목록 확인 받아. 삭제는 절대 자동 실행하지 마.
```

출처: https://www.gpters.org/nocode/post/how-use-claude-cowork-0CdQIT9LWrd3Zbl

### `C-02` 파일 정리 3단 콤보 (관찰 → 제안 → 실행)

**환경** Cowork · **유형** 단위

> **언제 쓰나** 어떻게 정리할지 나도 모를 때. 한 번에 시키지 말고 세 번에 나눠 시키면 실패가 없다.

```text
① 이 폴더 설명해 줘
② 카테고리 추천해 줘
③ 제안대로 파일 옮겨 줘

※ ①에서 Claude가 파악한 내용이 틀렸으면 ②로 넘어가기 전에 바로잡는다. 이 지점이 전체 품질을 결정한다.
```

출처: https://myip.co.kr/board/read.php?id=2090&table=tip


## C. Cowork · 엑셀·데이터

### `C-03` 수식이 살아있는 엑셀 만들기

**환경** Cowork · **유형** 단위

> **언제 쓰나** 값만 박힌 표가 아니라 '고치면 자동으로 갱신되는' 시트가 필요할 때.

```text
첨부한 데이터로 엑셀(.xlsx) 파일을 만들어줘.
- 시트1: 원본 데이터 정리(불필요한 공백·중복 제거)
- 시트2: [월별/카테고리별] 합계와 비중(%) 요약표
- 합계·평균은 수식으로 넣어서 값이 바뀌면 자동 갱신되게 해줘
- 요약표 옆에 막대 차트 하나 추가
완성 파일을 주고, 어떤 수식을 어디에 썼는지 한 줄로 설명해줘.
```

출처: https://aimatters.co.kr/ai-tool/43911/

### `C-04` CSV 분석 → 3시트 구조 (원본·요약·개선안)

**환경** Cowork · **유형** 단위

> **언제 쓰나** 데이터를 넘기면서 '사람이 검증할 수 있게' 만들어야 할 때.

```text
첨부한 CSV를 분석해 엑셀 파일로 정리해주세요. 첫 번째 시트에는 원본 데이터를 유지하고, 두 번째 시트에는 [분류]별 성과 요약 표를 만들어주세요. 세 번째 시트에는 개선이 필요한 항목과 이유를 적어주세요. 계산식이 들어간 셀은 사람이 확인할 수 있도록 설명 열을 추가해주세요.
```

출처: https://potato-ai.xyz/claude-file-creation-report-workflow/

### `C-05` 영수증 이미지 → 경비정산 엑셀 (OCR + 환율)

**환경** Cowork · **유형** 단위

> **언제 쓰나** 영수증·명세 이미지가 폴더에 쌓여 있을 때.

```text
[폴더 경로]의 영수증 이미지/PDF를 OCR로 읽어서 [회사 양식.xlsx] 형식으로 정리. 카테고리는 식비/교통비/숙박/기타로 분류. 외화는 [기준일] 환율로 원화 환산. 합계 수식 포함.

읽지 못한 항목은 임의로 채우지 말고 '판독 불가' 행으로 따로 모아줘.
```

출처: https://www.gpters.org/nocode/post/how-use-claude-cowork-0CdQIT9LWrd3Zbl


## C. Cowork · 보고서

### `C-06` 산재된 노트 → 보고서 초안 (모순 표시 포함)

**환경** Cowork · **유형** 단위

> **언제 쓰나** 회의록·메일·메모가 폴더에 흩어져 있을 때. '모순 표시' 조항이 이 프롬프트의 값어치다.

```text
[폴더]에 회의록·노트·이메일 발췌가 들어있어. [주제]에 대한 보고서 초안 만들어줘. 시간 순으로 정리하고, 자료 간 모순이 있으면 따로 표시해줘. [회사 톤] 유지하고 [목표 분량]자.
```

출처: https://www.gpters.org/nocode/post/how-use-claude-cowork-0CdQIT9LWrd3Zbl

### `C-07` 복수 파일 → 주간 보고서 (숫자 근거 고정)

**환경** Cowork · **유형** 단위

> **언제 쓰나** PDF·CSV를 함께 넘겨 보고서를 만들 때. 마지막 문장이 숫자 환각을 막는다.

```text
첨부한 PDF는 [자료 A]이고, CSV는 [자료 B] 데이터입니다. [팀명] 주간 보고서 초안을 워드 문서 형태로 만들어주세요. 핵심 결론 3개, 주요 수치 표, 반복된 이슈, 다음 주 실행 항목 순서로 구성해주세요. 숫자는 CSV 기준으로 쓰고, 추정이 필요한 내용은 '확인 필요'로 표시해주세요.
```

출처: https://potato-ai.xyz/claude-file-creation-report-workflow/

### `C-08` 장기 데이터 → 시각화 PDF 보고서

**환경** Cowork · **유형** 단위

> **언제 쓰나** 1년치 이상 거래·실적 데이터를 한 장짜리 그림으로 요약해야 할 때.

```text
[파일 경로]의 [기간] 거래/이벤트 데이터를 분석해서 PDF 보고서 만들어줘. 카테고리별 합계 차트, 월간 추이, 상위 N개 항목, 이상치 자동 감지 포함. 한국어로.
```

출처: https://www.gpters.org/nocode/post/how-use-claude-cowork-0CdQIT9LWrd3Zbl


## C. Cowork · 발표자료

### `C-09` 보고서 → 7장 발표자료 (장별 역할 지정)

**환경** Cowork · **유형** 단위

> **언제 쓰나** 문서를 슬라이드로 옮길 때. 장별 역할을 못 박아야 '문서 복붙 슬라이드'가 안 나온다.

```text
첨부한 보고서와 표를 바탕으로 7장짜리 발표자료 초안을 만들어주세요. 대상은 [청중]입니다. 1장은 결론, 2장은 배경, 3장은 핵심 수치, 4장은 문제점, 5장은 [현장 목소리], 6장은 제안, 7장은 다음 액션으로 구성해주세요. 각 슬라이드에는 제목, 핵심 문장, 발표자 메모를 넣어주세요.
```

출처: https://potato-ai.xyz/claude-file-creation-report-workflow/

### `C-10` PPT 실패 회피 — 한 장 테스트 먼저

**환경** Cowork · **유형** 단위

> **언제 쓰나** 10장 넘는 덱을 한 번에 시키면 생성 도중 실패하는 문제를 우회할 때.

```text
① 임의의 주제로 딱 한 장의 테스트 PPT만 먼저 만들어줘. 폰트·로고·비율·여백을 확인할게.
② (승인 후) 같은 디자인 규칙으로 1~5장을 만들어줘.
③ (승인 후) 같은 규칙으로 6~10장을 만들고 하나로 합쳐줘.

디자인 규칙: 폰트는 [폰트명]만 사용 / 로고는 [파일] / 슬라이드 비율은 16:9만.
```

출처: https://brunch.co.kr/@sonteady/103


## C. Cowork · 회의·메일

### `C-11` 회의록 → 액션 아이템 + 발송 메일

**환경** Cowork · **유형** 단위

> **언제 쓰나** 회의 직후 5분 안에 후속 조치를 돌릴 때.

```text
이 회의록에서 액션 아이템 추출해줘. 담당자·기한·산출물 3열 표로. 참석자에게 보낼 이메일 초안도 써줘. 회의록에 없는 담당자·기한은 비워두고 '미정'으로 표시해.
```

출처: https://digit2sight.com/%ED%81%B4%EB%A1%9C%EB%93%9C-%EC%BD%94%EC%9B%8C%ED%81%ACclaude-cowork-%EC%99%84%EB%B2%BD-%EA%B0%80%EC%9D%B4%EB%93%9C-%EA%B0%80%EA%B2%A9%C2%B7%EC%82%AC%EC%9A%A9%EB%B2%95%C2%B7%EC%8B%A4%EC%A0%84/

### `C-12` 받은편지함 5단 분류 (자동 삭제 금지)

**환경** Cowork · **유형** 단위

> **언제 쓰나** 메일이 쌓여 우선순위가 안 보일 때.

```text
받은편지함을 분류해줘. (1) 즉시 답장 필요, (2) 24시간 내 답장, (3) 읽기만, (4) 보관, (5) 삭제 후보. 분류 기준은 [내 룰 5개]. 삭제는 절대 자동 실행하지 마. 분류 결과만 표로 보여줘.
```

출처: https://www.gpters.org/nocode/post/how-use-claude-cowork-0CdQIT9LWrd3Zbl

### `C-13` 내 과거 메일 톤으로 새 메일 쓰기

**환경** Cowork · **유형** 단위

> **언제 쓰나** 거래처 대응 메일의 톤을 유지해야 할 때.

```text
지난주에 보낸 이메일과 비슷한 톤으로 [상대]에게 [용건] 안내 메일 초안을 써 줘. 과거 메일에서 내가 실제로 쓴 인사말·맺음말 형식을 그대로 따라줘.
```

출처: https://www.digitalmarketer.co.kr/insights/claude-cowork-5-ai-tasks-for-beginners


## C. Cowork · 리서치

### `C-14` 경쟁사·제품 비교 보고서 자동 생성

**환경** Cowork · **유형** 단위

> **언제 쓰나** 여러 사이트를 돌며 표를 만들어야 할 때.

```text
[대상 1·2·3] 공식 사이트를 탐색해서 가격·기능 비교 보고서 만들어줘. 각 항목마다 출처 URL과 확인 일자를 달아줘. 사이트에서 확인되지 않은 항목은 빈칸으로 두고 추정하지 마.
```

출처: https://digit2sight.com/%ED%81%B4%EB%A1%9C%EB%93%9C-%EC%BD%94%EC%9B%8C%ED%81%ACclaude-cowork-%EC%99%84%EB%B2%BD-%EA%B0%80%EC%9D%B4%EB%93%9C-%EA%B0%80%EA%B2%A9%C2%B7%EC%82%AC%EC%9A%A9%EB%B2%95%C2%B7%EC%8B%A4%EC%A0%84/

### `C-15` 링크 하나 → 3종 콘텐츠 동시 생산

**환경** Cowork · **유형** 단위

> **언제 쓰나** 같은 소스로 블로그·SNS·요약을 한 번에 뽑을 때.

```text
이 링크 → 한국어 요약 + 블로그 글(3,000자) + 스레드 포스트(250자) 동시에 만들어줘. 세 결과물의 사실관계는 반드시 원문과 일치해야 하고, 원문에 없는 수치는 쓰지 마.
```

출처: https://digit2sight.com/%ED%81%B4%EB%A1%9C%EB%93%9C-%EC%BD%94%EC%9B%8C%ED%81%ACclaude-cowork-%EC%99%84%EB%B2%BD-%EA%B0%80%EC%9D%B4%EB%93%9C-%EA%B0%80%EA%B2%A9%C2%B7%EC%82%AC%EC%9A%A9%EB%B2%95%C2%B7%EC%8B%A4%EC%A0%84/


## C. Cowork · 문서 변환

### `C-16` 폴더 안 PDF 전체 → 한 장 요약

**환경** Cowork · **유형** 단위

> **언제 쓰나** 논문·보고서 뭉치의 공통점을 뽑을 때.

```text
이 폴더의 모든 PDF를 읽고 핵심 결론과 공통점을 한 페이지 요약으로 정리해 줘. 문서마다 결론이 갈리는 지점은 '이견'으로 따로 모아줘.
```

출처: https://www.digitalmarketer.co.kr/insights/claude-cowork-5-ai-tasks-for-beginners


## C. Cowork · 예약 작업

### `C-17` 매일 아침 브리핑 (토큰 절약형 — 영어 지시 + 한국어 출력)

**환경** Cowork · **유형** 단위

> **언제 쓰나** 반복 리서치를 자동화할 때. 지시는 영어로, 출력만 한국어로 하면 토큰이 절약된다.

```text
You are a global tech researcher and news curator.

Every day at 9am: find the TOP 5 most important news in [분야] and save to [저장 위치].

Cover: [키워드 1, 2, 3]
Select news that covers: [선정 기준]

Output format:
[뉴스 TOP 5 - YYYY.MM.DD]
1️⃣ Title / Source / Summary (3-4 lines) / Why it matters / Insight
— repeat for all 5 —
📊 Today's trend summary (3 lines)
🚀 Company to watch (1-2)

Respond in Korean.
```

출처: https://maily.so/makersnote/posts/8mo542j7z9p

### `C-18` 아침 업무 브리핑 (일정·메일·메시지 통합)

**환경** Cowork · **유형** 단위

> **언제 쓰나** 출근 전 30분에 하루 그림을 받고 싶을 때. /schedule 로 등록한다.

```text
매일 오전 8시 30분에 다음을 정리해서 브리핑 문서로 만들어줘.
1. 오늘 일정 — 시간 순, 준비물이 필요한 것 표시
2. 어제 이후 온 중요 메일 — 답장 필요한 것만
3. 미해결 액션 아이템 — 기한 임박 순

문서는 [폴더]에 날짜_브리핑.md 로 저장해줘.
```

출처: https://www.gpters.org/nocode/post/summary-how-use-claude-1s9HnCamgNA8tFZ


## C. Cowork · 스킬 만들기

### `C-19` 방금 한 작업을 스킬로 역설계하기

**환경** Cowork · **유형** 단위

> **언제 쓰나** 같은 작업을 또 할 것 같을 때. 스킬을 만드는 가장 쉽고 확실한 방법.

```text
지금까지의 과정을 스킬로 만들어줘.

포함할 것:
1. 이 스킬이 하는 일 (한 문장)
2. 언제 발동해야 하는지 (사용자가 쓸 법한 표현 5개)
3. 반드시 지켜야 할 규칙
4. 톤앤매너
5. 결과물 형태와 저장 위치

방금 작업에서 내가 중간에 수정 요청한 부분은 '흔한 실수' 항목으로 따로 넣어줘.
```

출처: https://www.aiground.co.kr/claude-cowork-beginners-guide/

### `C-20` 업무 스킬 요청 5요소 템플릿

**환경** Cowork · **유형** 단위

> **언제 쓰나** 처음부터 스킬을 설계할 때. 5요소를 다 채우면 실패율이 급감한다.

```text
[스킬 이름] 스킬을 만들어줘.

① 작업 정의: 우리는 [업종/맥락]이고, 이 스킬은 [무엇]을 한다.
② 트리거 상황: [언제 이 스킬이 쓰여야 하는가 — 사용자 표현 예시 포함]
③ 규칙·가이드: [반드시 지킬 것 / 절대 하지 말 것]
④ 톤앤매너: [문체, 어휘 수준, 금지 표현]
⑤ 결과물 형태: [파일 형식, 구조, 저장 위치]
```

출처: https://blog.highoutputclub.com/claude-skills-for-non-developers/


## C. Cowork · 가드레일

### `C-21` 파일 변경 전 확인 받기 (모든 Cowork 세션의 기본값)

**환경** Cowork · **유형** 단위

> **언제 쓰나** 로컬 폴더를 연결한 모든 작업. 폴더 지침(CLAUDE.md)에 넣어두면 매번 안 써도 된다.

```text
파일 삭제/덮어쓰기 전에 변경 내용을 보여주고 확인 기다려줘.
작업 전에 계획을 먼저 보여주고, 삭제 전에는 목록 확인 받아.
삭제는 절대 자동 실행하지 마.
```

출처: https://www.aiground.co.kr/claude-cowork-beginners-guide/

### `C-22` 추측 금지 조항 (모든 문서 작업에 덧붙이는 한 줄)

**환경** Cowork · **유형** 단위

> **언제 쓰나** 담당자·일정·숫자를 지어내는 것을 막을 때. 실무에서 가장 효용이 큰 한 줄.

```text
자료에 없는 담당자, 일정, 숫자는 추측하지 말고 '확인 필요'로 표시해줘.
과장된 표현은 피하고, 원문에 없는 내용은 만들지 마.
```

출처: https://potato-ai.xyz/claude-action-checklist-long-doc-workflow/


## D. Code · 코드 파악

### `D-01` 코드베이스 전체 개요

**환경** Code · **유형** 단위

> **언제 쓰나** 처음 보는 저장소에 들어갈 때 첫 질문.

```text
give me an overview of this codebase: architecture, key directories, and how the pieces connect

(한국어) 이 코드베이스 개요를 줘: 아키텍처, 주요 디렉터리, 각 조각이 어떻게 연결되는지.
```

출처: https://code.claude.com/docs/en/prompt-library

### `D-02` 특정 경로의 데이터 흐름 설명 + 산출물 지정

**환경** Code · **유형** 단위

> **언제 쓰나** 한 모듈을 이해해야 할 때. format 슬롯에 'HTML 다이어그램'을 넣으면 그림까지 나온다.

```text
explain what {path} does and how data flows through it. write it up as {format}

(예) explain what src/scheduler/queue.ts does and how data flows through it. write it up as an HTML page with a diagram, then open it in the browser.
```

출처: https://code.claude.com/docs/en/prompt-library

### `D-03` 이 코드를 지우면 뭐가 깨지나

**환경** Code · **유형** 단위

> **언제 쓰나** 삭제·리팩터링 전 영향 범위 파악.

```text
what would break if I deleted {target}?

(한국어) {target}을 지우면 뭐가 깨질까? 호출 지점을 전부 찾아서 보여줘.
```

출처: https://code.claude.com/docs/en/prompt-library

### `D-04` 이상한 API의 유래를 git 히스토리로 추적

**환경** Code · **유형** 단위

> **언제 쓰나** '왜 이렇게 짜여 있지?'가 궁금할 때. 코드가 아니라 히스토리에 답이 있는 경우.

```text
look through {target}'s git history and summarize how its api came to be

(한국어) {target}의 git 히스토리를 훑어서 이 API가 어떻게 지금 모습이 됐는지 요약해줘.
```

출처: https://code.claude.com/docs/en/best-practices


## D. Code · 구현

### `D-05` 기존 패턴을 지목해서 따라 만들게 하기

**환경** Code · **유형** 단위

> **언제 쓰나** 신규 기능이 기존 코드와 따로 놀지 않게 하려 할 때. 공식 문서의 대표 Before/After.

```text
look at how existing widgets are implemented on the home page to understand the patterns. HotDogWidget.php is a good example. follow the pattern to implement a new calendar widget that lets the user select a month and paginate forwards/backwards to pick a year. build from scratch without libraries other than the ones already used in the codebase.

(패턴) {기존 예시}가 어떻게 구현됐는지 보고 패턴을 이해한 다음, 같은 방식으로 {신규}를 만들어줘. 코드베이스에 이미 쓰는 라이브러리 외에는 쓰지 마.
```

출처: https://code.claude.com/docs/en/best-practices

### `D-06` 검증 기준을 프롬프트에 심기 (가장 효과 큰 한 가지)

**환경** Code · **유형** 단위

> **언제 쓰나** 항상. 검증 수단이 없으면 '다 된 것 같다'가 유일한 완료 신호가 되고 사람이 검증 루프가 된다.

```text
write a validateEmail function. example test cases: user@example.com is true, invalid is false, user@.com is false. run the tests after implementing

(패턴) {기능}을 구현해줘. 예시 테스트 케이스: {입력1}→{기대1}, {입력2}→{기대2}. 구현한 뒤에 테스트를 실행해줘.
```

출처: https://code.claude.com/docs/en/best-practices

### `D-07` UI는 스크린샷으로 자기검증시키기

**환경** Code · **유형** 단위

> **언제 쓰나** '더 예쁘게'처럼 주관적 지시를 객관적 루프로 바꿀 때.

```text
[paste screenshot] implement this design. take a screenshot of the result and compare it to the original. list differences and fix them

(한국어) [스크린샷 첨부] 이 디자인대로 구현해줘. 결과물 스크린샷을 찍어 원본과 비교하고, 차이점을 나열한 다음 고쳐줘.
```

출처: https://code.claude.com/docs/en/best-practices


## D. Code · 디버깅

### `D-08` 증상이 아니라 근본 원인 (에러 원문 붙여넣기)

**환경** Code · **유형** 단위

> **언제 쓰나** 빌드·테스트 실패. 말로 설명하지 말고 로그 원문을 붙여넣는 것이 핵심.

```text
the build fails with this error: [paste error]. fix it and verify the build succeeds. address the root cause, don't suppress the error
```

출처: https://code.claude.com/docs/en/best-practices

### `D-09` 버그 리포트 3요소 (증상 + 위치 힌트 + 완료 정의)

**환경** Code · **유형** 단위

> **언제 쓰나** 재현 가능한 버그를 맡길 때.

```text
users report that login fails after session timeout. check the auth flow in src/auth/, especially token refresh. write a failing test that reproduces the issue, then fix it

(패턴) {증상}이라는 제보가 있어. {경로}의 {영역}, 특히 {의심 지점}을 확인해줘. 이슈를 재현하는 실패 테스트를 먼저 작성한 다음 고쳐.
```

출처: https://code.claude.com/docs/en/best-practices

### `D-10` 운영 장애 1차 진단

**환경** Code · **유형** 단위

> **언제 쓰나** 원인을 모르는 상태에서 조사 범위를 지정할 때.

```text
{symptom}. check the logs, recent deploys, and config changes, then tell me the most likely cause

(한국어) {증상}. 로그, 최근 배포, 설정 변경을 확인하고 가장 유력한 원인을 알려줘. 아직 고치지는 마.
```

출처: https://code.claude.com/docs/en/prompt-library


## D. Code · 테스트

### `D-11` 기존 테스트 패턴을 학습시킨 뒤 생성 (실무 효과 최대)

**환경** Code · **유형** 단위

> **언제 쓰나** 테스트 스타일이 제각각이 되는 걸 막을 때.

```text
Read these existing test files to learn our testing patterns:
- tests/services/user.service.test.ts
- tests/services/project.service.test.ts

Now generate tests for src/services/organization.service.ts.
Match the existing patterns exactly:
- Same describe/it nesting structure
- Same mock setup approach
- Same assertion style
- Same test naming convention
- Same beforeEach/afterEach patterns

Cover: all public methods, error cases, edge cases, and any async behavior.
Do not skip the unhappy paths.
```

출처: https://developertoolkit.ai/en/claude-code/lessons/testing/

### `D-12` 커버리지 구멍만 골라 메우기

**환경** Code · **유형** 단위

> **언제 쓰나** 테스트를 무작정 늘리지 않고 미커버 경로만 칠 때.

```text
Read {path} and the coverage report for it. Show me which lines and branches are not covered. Then write tests that cover the uncovered paths. Focus on: error handling branches, conditional logic tested for only one case, and async paths where the promise rejects.
```

출처: https://developertoolkit.ai/en/claude-code/lessons/testing/

### `D-13` 테스트 통과용 하드코딩 방지

**환경** Code · **유형** 단위

> **언제 쓰나** 테스트만 통과하는 가짜 구현이 나올 때. 마지막 문단이 특히 중요하다.

```text
Please write a high-quality, general-purpose solution using the standard tools available. Do not create helper scripts or workarounds to accomplish the task more efficiently. Implement a solution that works correctly for all valid inputs, not just the test cases. Do not hard-code values or create solutions that only work for specific test inputs.

Tests are there to verify correctness, not to define the solution.

If the task is unreasonable or infeasible, or if any of the tests are incorrect, please inform me rather than working around them.
```

출처: https://code.claude.com/docs/en/best-practices


## D. Code · 리뷰

### `D-14` 커밋 전 위험 신호 점검

**환경** Code · **유형** 단위

> **언제 쓰나** 매일 쓰는 가장 짧은 리뷰 프롬프트.

```text
review my uncommitted changes and flag anything that looks risky before I commit

(한국어) 커밋 전에 내 uncommitted 변경사항을 리뷰하고 위험해 보이는 걸 지적해줘.
```

출처: https://code.claude.com/docs/en/prompt-library

### `D-15` PR diff 시니어 관점 리뷰

**환경** Code · **유형** 단위

> **언제 쓰나** 브랜치를 올리기 전 자체 리뷰.

```text
Review the diff between the current branch and main, and evaluate it from the perspective of a senior engineer. Output: numbered list, each item including [file:line], severity, and a concrete fix.
```

출처: https://help.apiyi.com/en/claude-code-code-review-prompts-collection-guide-en.html

### `D-16` 하위 호환성 파괴 점검

**환경** Code · **유형** 단위

> **언제 쓰나** 공개 API·라이브러리를 수정한 PR.

```text
Review all changes in the current PR and check for backward-incompatible modifications: Have public API signatures or return values changed? Have required fields been added? Have default behaviors changed? List each with a migration note.
```

출처: https://help.apiyi.com/en/claude-code-code-review-prompts-collection-guide-en.html


## D. Code · 보안

### `D-17` 전체 보안 감사 7항목

**환경** Code · **유형** 단위

> **언제 쓰나** 배포 전 또는 인수인계 받은 코드의 1차 스크리닝.

```text
Perform a security audit of this codebase. Check for: 1) SQL injection or NoSQL injection (string concatenation in queries), 2) XSS vulnerabilities (unsanitized user input rendered in HTML), 3) hardcoded secrets (API keys, passwords, JWT secrets in source files), 4) authentication bypasses (routes missing auth middleware), 5) insecure cryptography (MD5, SHA1 for passwords, weak random number generation), 6) missing security headers (CSP, HSTS, X-Frame-Options), 7) overly permissive CORS configuration. For each finding, show the file path, line number, severity (critical/high/medium/low), and a concrete fix.
```

출처: https://developertoolkit.ai/en/claude-code/lessons/security-audit/

### `D-18` git 히스토리에 커밋된 시크릿 추적 + 재발 방지 훅

**환경** Code · **유형** 단위

> **언제 쓰나** 자격증명이 저장소에 들어갔을지 모를 때.

```text
Search the entire git history for committed secrets: API keys, database connection strings, JWT secrets, private keys, AWS credentials. Check .env files that may have been committed, config files with hardcoded values, and test fixtures with real credentials. For each finding, tell me which commit introduced it and whether the secret is still valid. Then generate a .gitignore update and a pre-commit hook that blocks secret commits.
```

출처: https://developertoolkit.ai/en/claude-code/lessons/security-audit/

### `D-19` 발견 → 조치 계획 (작업량 기준 3분류)

**환경** Code · **유형** 단위

> **언제 쓰나** 감사 결과가 쏟아진 뒤 무엇부터 할지 정할 때.

```text
From the security findings you just identified, create a prioritized remediation plan. Group fixes by effort (quick wins under 30 minutes, medium fixes under 2 hours, architectural changes). Start implementing the quick wins now.
```

출처: https://developertoolkit.ai/en/claude-code/lessons/security-audit/


## D. Code · 성능

### `D-20` N+1·인덱스·SELECT * 일괄 점검

**환경** Code · **유형** 단위

> **언제 쓰나** 응답이 느린데 원인을 모를 때 가장 먼저 돌리는 프롬프트.

```text
Analyze all database queries in our codebase. For each query: 1) identify if it is an N+1 pattern (query inside a loop or called once per item in a list), 2) check if the WHERE clause columns have indexes by looking at our migration files or schema, 3) flag any SELECT * that could be narrowed to specific columns, 4) find queries that fetch more rows than needed (missing LIMIT or pagination). For each problem, show the file location and provide the optimized version.
```

출처: https://developertoolkit.ai/en/claude-code/lessons/performance/

### `D-21` 느린 엔드포인트 실행 경로 프로파일링

**환경** Code · **유형** 단위

> **언제 쓰나** 특정 API 하나가 느릴 때.

```text
Profile our {endpoint} endpoint. It currently takes {N} seconds. Trace the execution path from the route handler through every function it calls. For each function, estimate the time complexity based on the data structures used. Identify any: 1) nested loops over large arrays, 2) synchronous operations that should be async, 3) repeated computation that could be cached, 4) unnecessary data fetching.
```

출처: https://developertoolkit.ai/en/claude-code/lessons/performance/

### `D-22` 목표 수치를 명시한 최적화 지시

**환경** Code · **유형** 단위

> **언제 쓰나** '빠르게 해줘'가 아니라 검증 가능한 목표를 줄 때.

```text
optimize {target} to bring {metric} from {current} down to under {goal}. measure before and after, and show me the numbers.

(한국어) {대상}을 최적화해서 {지표}를 {현재}에서 {목표} 미만으로 낮춰줘. 전후를 측정해서 숫자로 보여줘.
```

출처: https://code.claude.com/docs/en/prompt-library


## D. Code · 리팩터링

### `D-23` 행동 고정 테스트(characterization test) 먼저

**환경** Code · **유형** 단위

> **언제 쓰나** 레거시를 손대기 직전. 이걸 건너뛴 리팩터링은 사고가 난다.

```text
Read {file} in full, then read its test file. Write characterization tests that lock in the CURRENT behavior of {function}, including the branches I am likely to break: {분기1}, {분기2}, {분기3}. Do not change the implementation yet.
```

출처: https://developertoolkit.ai/en/claude-code/productivity-patterns/refactoring-patterns/

### `D-24` 비대한 서비스 분리 (파사드 유지로 PR 안전하게)

**환경** Code · **유형** 단위

> **언제 쓰나** 900줄짜리 God 클래스를 쪼갤 때. 파사드 조항이 PR을 작게 유지한다.

```text
{file} has grown to ~{N} lines and mixes {관심사1}, {관심사2}, and {관심사3}. Plan a split into {ServiceA}, {ServiceB}, and {ServiceC}. Keep one thin facade that delegates, so external imports do not break in this PR. Plan first, then implement.
```

출처: https://developertoolkit.ai/en/claude-code/productivity-patterns/refactoring-patterns/

### `D-25` 과잉 엔지니어링 억제 (Opus 4.5 이후 필수)

**환경** Code · **유형** 단위

> **언제 쓰나** 시킨 것보다 훨씬 많이 고쳐올 때. 구현 지시 앞에 붙인다.

```text
Avoid over-engineering. Only make changes that are directly requested or clearly necessary. Keep solutions simple and focused:

- Scope: Don't add features, refactor code, or make "improvements" beyond what was asked. A bug fix doesn't need surrounding code cleaned up.
- Documentation: Don't add docstrings, comments, or type annotations to code you didn't change. Only add comments where the logic isn't self-evident.
- Defensive coding: Don't add error handling, fallbacks, or validation for scenarios that can't happen. Only validate at system boundaries.
- Abstractions: Don't create helpers, utilities, or abstractions for one-time operations. The right amount of complexity is the minimum needed for the current task.
```

출처: https://code.claude.com/docs/en/best-practices


## D. Code · 문서화

### `D-26` 신규 개발자 첫날용 README 생성

**환경** Code · **유형** 단위

> **언제 쓰나** 인수인계·온보딩 문서가 없을 때.

```text
Read the codebase and generate a README.md that a new developer needs on day one: what the project does, how to run it locally, how to run tests, the directory map, and the three things that most surprise newcomers.
```

출처: https://developertoolkit.ai/en/claude-code/lessons/documentation/

### `D-27` 운영팀용 런북 생성

**환경** Code · **유형** 단위

> **언제 쓰나** 배포·장애 대응을 다른 사람이 할 수 있게 만들 때.

```text
Generate a runbook for the operations team. They need to know: how to deploy and roll back, what to check when the service is down, which alerts mean what, how to rotate credentials, and who to escalate to. Write it so someone who has never touched this codebase can follow it at 3am.
```

출처: https://developertoolkit.ai/en/claude-code/lessons/documentation/


## D. Code · Git

### `D-28` 커밋 메시지 후보 3개 → 선택 → 커밋

**환경** Code · **유형** 단위

> **언제 쓰나** 커밋 메시지 품질을 일정하게 유지할 때. 슬래시 커맨드로 저장해 두면 좋다.

```text
Analyze the staged diff and:
1. Understand the nature and purpose of the changes
2. Generate 3 commit message candidates (Conventional Commits format: feat:, fix:, docs:, refactor:)
3. Select the most appropriate one and explain why
4. Execute the commit with the selected message

Do not add a co-authorship footer.
```

출처: https://en.bioerrorlog.work/entry/git-commit-with-claude-code-custom-slash-command

### `D-29` 릴리스 노트 초안

**환경** Code · **유형** 단위

> **언제 쓰나** 태그 사이 변경을 사용자 언어로 옮길 때.

```text
compare {from} to {to} and draft release notes grouped by feature, fix, and breaking change. Write each line for a user, not for a developer.
```

출처: https://code.claude.com/docs/en/prompt-library

### `D-30` 머지 컨플릭트 해결 + 판단 근거 설명

**환경** Code · **유형** 단위

> **언제 쓰나** 양쪽 의도를 모두 살려야 할 때.

```text
두 변경의 의도를 모두 살려서 자연스럽게 하나로 합쳐줘. 합치는 과정에서 판단이 필요한 부분이 있으면, 어떻게 합쳤는지를 코드 읽을 줄 모르는 사람도 알 수 있게 쉬운 말로 설명해주세요. 다 합친 뒤에는 양쪽 기능이 모두 정상 동작하는지 직접 테스트하고 깨진 게 있으면 수정해주세요.
```

출처: https://brunch.co.kr/@yongjinjinipln/257


## D. Code · 궤도 수정

### `D-31` 방향이 틀렸을 때 한 줄

**환경** Code · **유형** 단위

> **언제 쓰나** 결과가 어긋났을 때. 길게 설명하지 말고 이 형태로 끊는다.

```text
that is not right: {feedback}. try a different approach

(한국어) 그거 아니야: {무엇이 왜 틀렸는지}. 다른 접근을 시도해봐.
```

출처: https://code.claude.com/docs/en/prompt-library

### `D-32` 너무 많이 고쳤을 때 되감기

**환경** Code · **유형** 단위

> **언제 쓰나** 범위를 벗어난 변경이 섞여 들어왔을 때.

```text
that is too much. keep only the changes to {scope} and undo your other edits

(한국어) 너무 많이 했어. {범위}에 대한 변경만 남기고 나머지 수정은 되돌려.
```

출처: https://code.claude.com/docs/en/prompt-library

### `D-33` 같은 실수를 규칙으로 환류시키기

**환경** Code · **유형** 단위

> **언제 쓰나** 같은 지적을 두 번 했을 때. 세 번째는 하지 않게 만드는 프롬프트.

```text
you keep {mistake}. add a rule to CLAUDE.md so this stops happening

(한국어) 너 계속 {실수} 하잖아. 다시는 안 그러도록 CLAUDE.md에 규칙을 추가해.
```

출처: https://code.claude.com/docs/en/prompt-library


## D. Code · 메타

### `D-34` 세션 학습을 프로젝트 규칙으로 축적

**환경** Code · **유형** 단위

> **언제 쓰나** 세션 종료 직전. 이 한 줄이 다음 세션의 품질을 올린다.

```text
summarize what we did this session and suggest what to add to CLAUDE.md

(한국어) 이번 세션에서 한 일을 요약하고 CLAUDE.md에 추가할 것을 제안해줘. 이미 있는 규칙과 중복되면 제안하지 마.
```

출처: https://code.claude.com/docs/en/prompt-library

### `D-35` 모르는 CLI 도구를 스스로 익히게 하기

**환경** Code · **유형** 단위

> **언제 쓰나** MCP를 붙이기 전에 먼저 시도할 것. CLI가 MCP보다 컨텍스트 효율이 좋다.

```text
Use '{foo-cli-tool} --help' to learn about the tool, then use it to solve A, B, C.

(한국어) '{도구} --help'로 이 도구를 익힌 다음, 그걸로 A, B, C를 해결해줘.
```

출처: https://code.claude.com/docs/en/best-practices

### `D-36` 훅을 작성하게 하기

**환경** Code · **유형** 단위

> **언제 쓰나** '매번 반드시' 일어나야 하는 일이 있을 때. CLAUDE.md는 권고, 훅은 강제다.

```text
Write a hook that runs eslint after every file edit.
Write a hook that blocks writes to the migrations folder.

(한국어) 파일 편집마다 eslint를 실행하는 훅을 작성해줘. / migrations 폴더에 대한 쓰기를 막는 훅을 작성해줘.
```

출처: https://code.claude.com/docs/en/hooks-guide


## E. 흐름 · 요구사항 확정

### `E-01` ★ 인터뷰 → SPEC.md → 새 세션에서 실행

**환경** 공통 · **유형** 흐름

> **언제 쓰나** 큰 작업의 시작점. 공식 문서가 템플릿까지 제공하는데 가장 덜 알려진 패턴. '명세에 쓴 시간이 구현을 지켜보는 시간보다 더 큰 보상을 준다.'

```text
[1단계 — 인터뷰]
I want to build [brief description]. Interview me in detail using the AskUserQuestion tool.

Ask about technical implementation, UI/UX, edge cases, concerns, and tradeoffs. Don't ask obvious questions, dig into the hard parts I might not have considered.

Keep interviewing until we've covered everything, then write a complete spec to SPEC.md.

(한국어) 나는 [한 줄 설명]을 만들려고 해. 나를 자세히 인터뷰해줘. 기술 구현, UI/UX, 엣지케이스, 우려사항, 트레이드오프를 물어봐. 뻔한 질문은 하지 마. 내가 미처 생각 못 했을 어려운 지점을 파고들어. 전부 다룰 때까지 계속 인터뷰하고, 끝나면 완성된 명세를 SPEC.md에 써줘.

[2단계 — 반드시 새 세션에서]
SPEC.md 를 읽고 구현해줘. 이 대화 이전의 맥락은 없다고 가정해.

※ 좋은 명세의 조건(공식): ① 관련 파일과 인터페이스를 이름으로 지목 ② 무엇이 범위 밖인지 명시 ③ 기능이 실제 동작함을 증명하는 end-to-end 검증 단계로 끝날 것.
※ 개수를 고정("질문 5개만 해줘")하면 뻔한 질문으로 채우게 된다. "다 다룰 때까지"가 공식 권장.
```

출처: https://code.claude.com/docs/en/best-practices


## E. 흐름 · 개발 4단계

### `E-02` ★ Explore → Plan → Code → Commit (공식 4단계)

**환경** Code · **유형** 흐름

> **언제 쓰나** 범위가 불확실한 기능 개발. 반대로 'diff를 한 문장으로 설명할 수 있으면 계획 단계를 건너뛰라'가 공식 지침.

```text
[1 Explore]  ※ Shift+Tab 으로 plan mode 진입
read /src/auth and understand how we handle sessions and login.
also look at how we manage environment variables for secrets.

[2 Plan]  ※ Ctrl+G 로 계획을 에디터에서 직접 수정 가능
I want to add Google OAuth. What files need to change?
What's the session flow? Create a plan.

[3 Implement]  ※ plan mode 해제
implement the OAuth flow from your plan. write tests for the
callback handler, run the test suite and fix any failures.

[4 Commit]
commit with a descriptive message and open a PR
```

출처: https://code.claude.com/docs/en/best-practices


## E. 흐름 · TDD

### `E-03` TDD 3단 루프 (RED → GREEN → REFACTOR)

**환경** Code · **유형** 흐름

> **언제 쓰나** 요구사항이 명확하고 정답이 검증 가능한 로직. 각 단계를 반드시 끊어서 시켜야 한다.

```text
[RED — 테스트만]
Write a test for {함수}.
Requirements:
- {입출력 계약}
- {예외 조건 1}
- {예외 조건 2}
- Do NOT test the database directly (use mocks)

Don't write the implementation yet.

[GREEN]
The test is now written. Write the implementation that makes all tests pass. Do not modify the tests.

[REFACTOR]
The tests are passing. Refactor the implementation for readability without changing behavior. Run the tests again to confirm.

※ 강화판: 한 세션이 테스트를 쓰고, 다른 세션이 통과시키는 코드를 쓴다(공식 Writer/Reviewer 변형).
※ 필수 안전장치: "It is unacceptable to remove or edit tests." — 테스트를 지워서 통과시키는 것을 막는다.
```

출처: https://dev.to/myougatheaxo/test-driven-development-with-claude-code-write-tests-first-then-make-them-pass-2a6m


## E. 흐름 · 자기교정

### `E-04` ★ 생성 → 리뷰 → 수정 (self-correction chain)

**환경** 공통 · **유형** 흐름

> **언제 쓰나** 공식 문서가 '가장 흔한 체이닝 패턴'으로 지목. 각 단계를 별개 호출로 끊어야 효과가 난다.

```text
[1 생성]
{작업}에 대한 초안을 작성해줘. 완성도보다 커버리지를 우선해. 빠진 영역이 없게 하고, 확신이 없는 부분은 <uncertain> 태그로 표시해줘.

[2 리뷰 — 별개 호출]
아래 초안을 다음 기준으로만 평가해줘. 다시 쓰지 말고 평가만 해.
<criteria>
1. {기준1 — 예: 사실관계가 인용 출처와 일치하는가}
2. {기준2 — 예: 요청한 범위를 벗어난 내용이 있는가}
3. {기준3 — 예: 결론이 근거로부터 실제로 도출되는가}
</criteria>
각 항목마다 PASS / FAIL 과 근거를 한 줄씩. FAIL만 수정 지시를 붙여줘. 스타일 취향은 지적하지 마.
<draft>{1단계 출력}</draft>

[3 수정 — 별개 호출]
아래 리뷰의 FAIL 항목만 반영해서 초안을 수정해줘. PASS 항목은 건드리지 마. 무엇을 바꿨는지 마지막에 3줄로 요약해줘.
<draft>{1단계 출력}</draft>
<review>{2단계 출력}</review>
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/chain-prompts


## E. 흐름 · 평가-개선 루프

### `E-05` Evaluator–Optimizer (루브릭 기반 반복 개선)

**환경** 공통 · **유형** 흐름

> **언제 쓰나** 평가 기준이 명확하고 반복 개선이 값어치를 하는 작업(번역, 카피, 제안서 문구).

```text
{작업}을 생성-평가 루프로 진행할 거야. 두 역할을 번갈아 수행해.

<rubric>
R1. {기준1} — 통과 조건: {구체적으로}
R2. {기준2} — 통과 조건: {구체적으로}
R3. {기준3} — 통과 조건: {구체적으로}
</rubric>

루프:
  [Generator] 산출물 생성 또는 수정
  [Evaluator] rubric 각 항목에 PASS/FAIL + FAIL이면 "무엇을 어떻게" 지시
             ※ Evaluator는 절대 직접 고치지 마. 지시만 해.
  [Generator] FAIL 항목만 반영

종료 조건:
  - 전 항목 PASS → 종료
  - 3회 반복해도 같은 항목이 FAIL → 멈추고 나에게 물어봐. 루브릭 자체가 틀렸거나 모순됐을 가능성이 크니 그 가설도 같이 말해줘.

매 라운드마다 "이번에 바뀐 것"을 3줄로 남겨줘.
```

출처: https://www.anthropic.com/engineering/building-effective-agents


## E. 흐름 · 분기

### `E-06` Routing (입력을 분류해 다른 처리로 보내기)

**환경** 공통 · **유형** 흐름

> **언제 쓰나** 문의 유형·문서 종류가 뚜렷이 갈리고 각각 다르게 다뤄야 할 때.

```text
아래 입력을 분류만 해. 답변은 하지 마.

<categories>
A: {범주A 정의} → {후속 처리}
B: {범주B 정의} → {후속 처리}
C: {범주C 정의} → {후속 처리}
D: 위 어디에도 해당 없음 → 사람 에스컬레이션
</categories>

<input>{입력}</input>

출력 형식:
category: <A|B|C|D>
confidence: <0-1>
reason: <한 줄>

confidence가 0.7 미만이면 무조건 D로 보내.
```

출처: https://www.anthropic.com/engineering/building-effective-agents


## E. 흐름 · 병렬

### `E-07` Parallelization — Sectioning (독립 축으로 쪼개 동시 평가)

**환경** 공통 · **유형** 흐름

> **언제 쓰나** 한 산출물을 여러 축에서 봐야 할 때. 축이 섞이면 평가가 뭉개진다.

```text
{대상}을 4개 축으로 병렬 평가할 거야. 각 축은 독립된 서브에이전트로 돌려줘. 서로의 결과를 참조하지 말고, 각자 자기 축만 판단해.

축1 — 사실 정확성: 주장과 근거가 일치하는가
축2 — 논리 정합성: 결론이 전제로부터 도출되는가
축3 — 완결성: 요청 범위 중 누락된 부분
축4 — 리스크: 실행 시 되돌리기 어려운 지점

각 축은 {0-5점 + 근거 3줄 + 가장 큰 문제 1개}만 반환해.
전부 모이면 축별 점수표를 만들고, 2점 이하 축만 개선안을 제시해줘.
```

출처: https://www.anthropic.com/engineering/building-effective-agents

### `E-08` Parallelization — Voting (같은 일을 관점만 바꿔 여러 번)

**환경** 공통 · **유형** 흐름

> **언제 쓰나** 놓치면 안 되는 검토(보안·법무·안전). 다수결로 노이즈를 거른다.

```text
같은 작업을 서로 다른 관점 3개로 독립 수행해줘. 서로 참조 금지.

관점1: {예 — 보안 엔지니어}
관점2: {예 — 성능 엔지니어}
관점3: {예 — 신규 입사자(가독성)}

각각 발견사항 목록을 낸 뒤, 마지막에 합산해줘.
- 3명 전원 지적: 즉시 수정
- 2명 지적: 검토 대상
- 1명만 지적: 참고 (근거가 특별히 강하지 않으면 무시)
```

출처: https://www.anthropic.com/engineering/building-effective-agents


## E. 흐름 · 오케스트레이션

### `E-09` Orchestrator–Workers (하위 작업을 미리 알 수 없을 때)

**환경** 공통 · **유형** 흐름

> **언제 쓰나** 넓은 조사·다파일 변경. 위임 시 objective/format/sources/boundaries 4가지를 다 줘야 중복이 안 생긴다.

```text
{목표}를 조사할 거야. 너는 오케스트레이터야. 직접 조사하지 마.

1단계 — 분해:
   목표를 3~5개의 독립적 조사 축으로 쪼개줘. 축끼리 겹치면 안 돼. 겹침이 보이면 경계를 다시 그어. 쪼개기 전에 "왜 이렇게 나눴는지"를 먼저 설명해줘.

2단계 — 각 서브에이전트에게 아래를 전부 명시해서 위임:
   - objective: 이 축에서 답해야 할 질문 (한 문장)
   - output format: 반환 형식 (예: 발견 5개 + 각각 출처 URL)
   - sources: 어디를 봐야 하고 어디는 보지 말아야 하는가
   - boundaries: 이 축에서 다루지 "않을" 것 — 다른 축 침범 금지

3단계 — 종합:
   결과가 모이면 축 간 모순부터 찾아줘. 모순이 있으면 추가 조사가 필요한지 판단하고, 필요하면 그 축만 다시 돌려. 최종 산출 전에 "어느 축이 근거가 약한지" 먼저 말해줘.

※ 비용 경고: 멀티에이전트는 일반 대화의 약 15배 토큰을 쓴다. 고가치 작업에만.
※ 안 맞는 경우: 에이전트 간 공유 컨텍스트가 많이 필요한 도메인(대부분의 코딩 작업 포함).
```

출처: https://www.anthropic.com/engineering/multi-agent-research-system


## E. 흐름 · 적대적 검증

### `E-10` ★ Fresh context 레드팀 리뷰 (과잉 지적 방지 조항 포함)

**환경** 공통 · **유형** 흐름

> **언제 쓰나** 완료로 치기 전 마지막 관문. 마지막 줄이 없으면 과잉 엔지니어링을 유발한다.

```text
서브에이전트를 써서 {산출물}을 {기준 문서}에 대조해 리뷰해줘.
- 모든 요구사항이 실제로 구현/반영됐는가
- 명시된 엣지케이스에 대응이 있는가
- 작업 범위 밖이 건드려지지 않았는가

스타일 취향이 아니라 "빠진 것"을 보고해. 정확성이나 명시된 요구사항에 영향을 주는 갭만 flag 해.

※ 공식 경고: "갭을 찾으라고 지시받은 리뷰어는 작업이 멀쩡해도 대개 뭔가를 보고한다. 그게 시키는 일이니까. 모든 지적을 쫓아가면 과잉 엔지니어링으로 이어진다."
※ fresh context가 핵심 — 자기가 방금 쓴 것에 편향되지 않는다.
```

출처: https://code.claude.com/docs/en/best-practices


## E. 흐름 · 지식노동 파이프라인

### `E-11` 리서치 → 분석 → 문서 → 발표자료 (5단계)

**환경** 공통 · **유형** 흐름

> **언제 쓰나** 조사량이 한 컨텍스트를 넘고 중간에 방향 확인이 필요한 작업. 이암허브의 사업계획·기술동향 보고서에 그대로 적용된다.

```text
[0 스코핑]
{주제}를 조사하려고 해. 조사 시작 전에 나를 인터뷰해줘. 조사 범위, 독자, 의사결정 목적, 제외할 영역, 신뢰할 출처 기준을 물어봐. 뻔한 질문은 하지 마. 끝나면 RESEARCH_BRIEF.md 로 저장해줘.

[1 리서치]
RESEARCH_BRIEF.md 기준으로 조사해줘. 조사 축을 3~5개로 나누고 각각 서브에이전트에 위임해. 각 서브에이전트에는 objective / output format / sources / boundaries 를 명시해.
원자료는 findings.md 에 출처 URL과 함께 누적해. 본문에 다 넣지 마.

[2 분석]
findings.md 를 읽고 분석해줘. 원문을 통째로 컨텍스트에 올리지 말고 필요한 부분만 참조해.
- 축 간 모순 지점 먼저
- 근거가 약한 주장(출처 1개뿐이거나 2차 출처만) 표시
- "확실히 아는 것 / 추정하는 것 / 모르는 것" 3분류
analysis.md 로 저장. 아직 문서 쓰지 마.

[3 문서]
analysis.md 기반으로 먼저 목차와 각 절의 핵심 주장만 써줘. 내가 승인하기 전에 본문은 쓰지 마.
(승인 후) 승인된 목차대로 본문을 작성해. 모든 사실 주장에 findings.md 의 출처를 달아. 출처 없는 주장은 쓰지 말고, 꼭 필요하면 [추정]으로 표시해.

[4 발표자료]
문서를 슬라이드로 옮기지 마. 다시 설계해.
- 청중이 기억해야 할 메시지 3개를 먼저 정하고 나에게 확인받아
- 확정 후 슬라이드당 메시지 1개, 슬라이드 제목은 주장문으로(명사구 금지)
- 근거는 본문 문서 참조로 남기고 슬라이드에는 요약만

[5 레드팀]
서브에이전트로 발표자료를 RESEARCH_BRIEF.md 에 대조 검토해줘.
- 원래 의사결정 목적에 답하고 있는가
- analysis.md 에서 "근거 약함"으로 표시된 게 슬라이드에서 단정문이 됐는가
- 반대 입장이 제기할 가장 강한 반론은
스타일이 아니라 갭만 보고해.
```

출처: https://code.claude.com/docs/en/best-practices


## E. 흐름 · 데이터 파이프라인

### `E-12` 수집 → 정제 → 시각화 → 보고 (4단계, 승인 게이트 포함)

**환경** Cowork · **유형** 흐름

> **언제 쓰나** 대용량 데이터가 컨텍스트를 압도하는 작업. 스마트팜 소득조사·환경데이터 분석에 그대로 쓴다.

```text
[1 수집]
{소스}에서 데이터를 수집해 raw/ 에 저장해줘. 수집한 데이터를 컨텍스트에 출력하지 마. 다음만 보고해:
- 행/열 수, 파일 크기
- 컬럼명과 각 컬럼의 샘플 3개
- 결측·이상 의심 지점

[2 정제]
raw/ 를 정제해 clean/ 으로 만들어줘. 전체를 읽지 말고 head/tail/샘플링으로 파악한 뒤 스크립트를 작성해.
정제 규칙을 코드로 남기고(cleaning.py), 각 규칙마다 "몇 행이 영향받았는지" 로그를 남겨줘.
데이터를 조용히 버리지 마 — 버린 건 dropped.csv 로 따로 저장.
정제 전후 행 수 대조표를 먼저 보여주고, 내 승인 후 다음 단계로.

[3 시각화]
차트를 그리기 전에 "이 데이터에서 답할 질문 3개"를 먼저 제안해줘. 내가 고르면 그것만 시각화해.
각 차트마다: 무엇을 보여주는가 / 무엇을 보여주지 "않는가" / 이 차트로 내리면 안 되는 결론

[4 보고]
보고서를 쓰기 전에 자기검증부터:
- 본문의 모든 수치가 clean/ 에서 재현되는지 실제로 다시 계산해 대조해줘
- 불일치가 있으면 보고서를 쓰지 말고 먼저 알려줘
- 상관관계를 인과로 서술한 문장이 있는지 스스로 점검
검증 통과 후 보고서 작성. 각 수치 옆에 산출 근거(파일·컬럼·집계방식)를 달아.
```

출처: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents


## E. 흐름 · 대규모 마이그레이션

### `E-13` Fan-out 마이그레이션 (수천 파일)

**환경** Code · **유형** 흐름

> **언제 쓰나** 같은 변환을 대량 반복할 때. 2~3개로 먼저 검증하고 전체에 돌리는 것이 핵심.

```text
[1 작업 목록 파일 만들기]
list all 2,000 files that need migrating and save the list to files.txt

[2 루프 스크립트 — 헤드리스 모드]
for file in $(cat files.txt); do
  claude -p "Migrate $file from React to Vue. Return OK or FAIL." \
    --allowedTools "Edit,Bash(git commit *)"
done

[3 검증 후 전체 실행]
처음 2~3개 파일에서 잘못된 점을 보고 프롬프트를 다듬은 뒤 전체에 돌린다.
```

출처: https://code.claude.com/docs/en/best-practices

### `E-14` Anthropic 공식 마이그레이션 킷 6단계 게이트

**환경** Code · **유형** 흐름

> **언제 쓰나** 언어·프레임워크 전면 이전. 철학: '코드를 고치는 게 아니라 그 코드를 만들어낸 프로세스를 고친다.'

```text
Step 0. 00-feasibility.md → 읽기 전용 타당성 판정. "Don't migrate"도 정당한 결론.
Step 1. 3개 산출물 동시 생성
        - RULEBOOK.md : 번역자가 두 가지로 해석할 수 있는 모든 결정에 단 하나의 정답 부여
        - Dependency Map : 파일/패키지 단위 순환 탐지 → 작업 순서 결정
        - inventory.tsv : 소유권/nullability/타입 등 언어별 갭 목록
Step 2. bakeoff + 파일럿으로 룰북 스트레스 테스트 → 룰 수정안 큐잉
Step 3. 기계적 큐로 병렬 번역
Step 4. 컴파일 → 에러를 기계 큐로 뽑아 병렬 수정 → 클린 빌드
Step 5. hello-world 검증 → 최소 E2E → 실행 가능 바이너리
Step 6. parity judge로 동작 일치 검증 → 테스트 스위트 통과
```

출처: https://github.com/anthropics/code-migration-kit-with-claude-code


## E. 흐름 · 멀티에이전트

### `E-15` 에이전트 팀 3~5명 병렬 운용

**환경** Code · **유형** 흐름

> **언제 쓰나** 독립적인 관점·모듈이 3개 이상일 때. '집중된 3명이 산만한 5명보다 낫다'가 공식 가이드.

```text
[다관점 설계]
I'm designing {대상}. Spawn three teammates to explore this from different angles: one on UX, one on technical architecture, one playing devil's advocate.

[병렬 리뷰]
Spawn three teammates to review PR #142: one focused on security implications, one checking performance impact, one validating test coverage. Have them each review and report findings.

[경쟁 가설 디버깅 — 서로 반증하게 하기]
Users report {증상}. Spawn 5 agent teammates to investigate different hypotheses. Have them talk to each other to try to disprove each other's theories, like a scientific debate. Update the findings doc with whatever consensus emerges.

[게이트 걸기]
Spawn an architect teammate to refactor {모듈}. Require plan approval before they make any changes. Only approve plans that include test coverage.

[리드가 먼저 코딩 시작하는 것 막기]
Wait for your teammates to complete their tasks before proceeding.

※ 팀메이트는 리드의 대화 이력을 상속하지 않는다. 위임 프롬프트에 맥락을 충분히 실어야 한다.
```

출처: https://code.claude.com/docs/en/agent-teams

### `E-16` Writer / Reviewer 2세션 분리

**환경** Code · **유형** 흐름

> **언제 쓰나** 에이전트 팀 없이도 되는 가장 값싼 품질 장치. 세션을 두 개 띄우기만 하면 된다.

```text
[Session A — Writer]
Implement a rate limiter for our API endpoints.

[Session B — Reviewer, 새 세션]
Review the rate limiter implementation in @src/middleware/rateLimiter.ts. Look for edge cases, race conditions, and consistency with our existing middleware patterns.

[Session A — Writer]
Here's the review feedback: [Session B output]. Address these issues.

※ 이유(공식): "새 컨텍스트는 코드 리뷰를 개선한다. Claude가 방금 자기가 쓴 코드에 편향되지 않기 때문이다."
※ 테스트에도 같은 구조를 쓸 수 있다 — 한 세션이 테스트를 쓰고, 다른 세션이 통과 코드를 쓴다.
```

출처: https://code.claude.com/docs/en/best-practices


## E. 흐름 · 병렬 브랜치

### `E-17` 1 세션 = 1 워크트리 = 1 브랜치 = 1 PR

**환경** Code · **유형** 흐름

> **언제 쓰나** 여러 기능을 동시에 진행할 때. 한국어 실전 운용 규칙 그대로.

```text
[세션 A]
워크트리를 만들어서 작업할게요. 이름은 {render-fix}로 하고요. {렌더링 속도가 느린 원인}을 찾아서 개선해주세요.

[세션 B]
워크트리 {stock-lib} 만들어서 시작해주세요. {에피소드 간 스톡 이미지를 재활용하는 구조}를 잡아주세요.

[병합]
두 변경의 의도를 모두 살려서 자연스럽게 하나로 합쳐줘. 판단이 필요한 부분은 코드 읽을 줄 모르는 사람도 알 수 있게 설명해주세요. 합친 뒤 양쪽 기능이 정상 동작하는지 직접 테스트하고 깨진 게 있으면 수정해주세요.

[정리]
PR 머지됐어요. 이 워크트리랑 브랜치 정리해주세요.

※ 주의: worktree를 과하게 쓰면 잦은 컨텍스트 스위칭이 오히려 품질을 떨어뜨린다.
```

출처: https://brunch.co.kr/@yongjinjinipln/257


## E. 흐름 · 원샷

### `E-18` PMU 원샷 (Plan Mode + Ultrathink + Auto-Accept)

**환경** Code · **유형** 흐름

> **언제 쓰나** 5~10분간 자리를 비워도 되는 큰 덩어리 작업. 막히면 디버깅 말고 더 좋은 프롬프트로 재시작.

```text
1. 터미널이 아니라 마크다운 에디터에서 긴 프롬프트를 완성한다
2. Shift+Tab 으로 Plan Mode 진입
3. 프롬프트에 "ultrathink" 키워드를 넣는다 (think < think hard < think harder < ultrathink)
4. 계획 승인 후 auto-accept 로 5~10분 무중단 실행
5. 막히면 디버깅하지 말고 → 더 나은 프롬프트로 처음부터 재시작

"Starting from scratch, especially if you elaborate a better, higher quality prompt, is the easiest way to unstuck the agent."
```

출처: https://dev.to/luaroncrew/how-to-one-shot-tasks-with-claude-code-338o


## E. 흐름 · 업무 자동화 성숙도

### `E-19` 수동 실행 → 스킬 저장 → 스케줄 자동화 (3단계 승격)

**환경** Cowork · **유형** 흐름

> **언제 쓰나** 반복 업무를 자산으로 바꾸는 표준 경로. Cowork 활용의 핵심 뼈대.

```text
[1단계 — 수동으로 한 번 제대로 한다]
{업무}를 해줘. (중간에 수정 요청을 하며 결과를 원하는 수준까지 끌어올린다)

[2단계 — 스킬로 굳힌다]
지금까지의 과정을 스킬로 만들어줘. 내가 중간에 수정 요청한 부분은 '흔한 실수' 항목으로 따로 넣어줘.

[3단계 — 스케줄로 돌린다]
매주 {요일} {시간}에 이 스킬로 {업무}를 실행하고 결과를 {위치}에 저장해줘. 실패하면 어디서 멈췄는지 로그를 남겨줘.

※ 1단계를 건너뛰고 바로 스킬을 만들면 거의 실패한다. 한 번 손으로 해봐야 규칙이 나온다.
```

출처: https://digit2sight.com/%ED%81%B4%EB%A1%9C%EB%93%9C-%EC%BD%94%EC%9B%8C%ED%81%ACclaude-cowork-%EC%99%84%EB%B2%BD-%EA%B0%80%EC%9D%B4%EB%93%9C-%EA%B0%80%EA%B2%A9%C2%B7%EC%82%AC%EC%9A%A9%EB%B2%95%C2%B7%EC%8B%A4%EC%A0%84/


## E. 흐름 · 교차검증

### `E-20` 다른 모델과 갑론을박시키기

**환경** 공통 · **유형** 흐름

> **언제 쓰나** 한 모델의 편향을 걷어낼 때. 한국어 커뮤니티에서 반복 추천되는 실전 루틴.

```text
[1] Cowork/Claude로 초안 생성
[2] 다른 모델에 초안을 넣고: "이 문서의 사실 오류, 논리 비약, 근거 없는 단정을 찾아줘. 칭찬은 하지 말고 문제만."
[3] Claude에 되돌려: "다음은 외부 검토 의견이야. 각 지적에 대해 ① 수용 ② 부분 수용 ③ 반박 중 하나로 답하고, 반박이면 근거를 대. 그다음 수용한 것만 반영해 수정본을 써줘."
[4] 2~3회 반복 후 최종본은 Claude에서 정리
```

출처: https://www.clien.net/service/board/use/19165111


## F. 운영 · 컨텍스트 관리

### `F-01` ★ 2회 교정 규칙 — 세 번째는 고치지 말고 리셋하라

**환경** 공통 · **유형** 운영

> **언제 쓰나** 같은 문제를 두 번 넘게 지적했을 때. 직관에 반하지만 공식 문서가 단정하는 원칙.

```text
공식 원문:
"If you've corrected Claude more than twice on the same issue in one session, the context is cluttered with failed approaches. Run /clear and start fresh with a more specific prompt that incorporates what you learned. A clean session with a better prompt almost always outperforms a long session with accumulated corrections."

실행:
1. /clear (또는 새 대화 시작)
2. 아래 형식으로 새 프롬프트를 쓴다

이전 시도에서 확인된 사실만 전제로 깔고 다시 시작할게.
<확인된_사실>
- {실제로 검증된 것}
</확인된_사실>
<막다른_길>
- {접근 A} — {실패한 정확한 이유}
- {접근 B} — {실패한 정확한 이유}
※ 이 둘은 다시 시도하지 마.
</막다른_길>
<이번_제약>
- {새로 확정한 제약}
</이번_제약>
이 전제 위에서 접근법부터 제안해줘. 구현은 내가 승인한 뒤에.
```

출처: https://code.claude.com/docs/en/best-practices

### `F-02` /compact 에 보존 대상 명시하기

**환경** 공통 · **유형** 운영

> **언제 쓰나** 압축하면서 중요한 게 날아가는 걸 막을 때.

```text
/compact 다음을 반드시 보존해줘: 수정한 파일 전체 목록, 확정된 아키텍처 결정, 아직 못 고친 버그, 테스트 실행 명령어. 탐색 과정에서 읽었던 파일 내용과 폐기된 접근법은 버려도 돼.

※ CLAUDE.md / 폴더 지침에 박아두는 상시 버전:
When compacting, always preserve the full list of modified files and any test commands
```

출처: https://code.claude.com/docs/en/best-practices


## F. 운영 · 핸드오프

### `F-03` ★ 세션 종료 핸드오프 5섹션

**환경** 공통 · **유형** 운영

> **언제 쓰나** 오늘 작업을 내일 이어갈 때. 마지막 두 줄('이 대화를 못 봤다고 가정')이 문서 품질을 좌우한다.

```text
지금 세션을 중단할 거야. HANDOFF.md 를 작성해줘. 다음 5개 섹션을 정확히 지켜:

## 1. What happened
이번 세션에서 실제로 완료한 것과 내린 결정. "시도했다"가 아니라 "됐다"만. 결정에는 왜 그렇게 정했는지 이유도 한 줄씩.

## 2. Where things live
변경된 파일의 절대 경로 목록. 각 파일에 무엇을 했는지 한 줄.

## 3. Verification done
무엇을 테스트했고 무엇이 통과했는가. 그리고 ★무엇을 테스트하지 "않았는가"★ — 이걸 빠뜨리지 마.

## 4. State
현재 상태 (브랜치/커밋, 또는 문서 버전과 미반영 피드백).

## 5. Open follow-ups
번호를 붙인 구체적 재개 지점. "리팩토링 필요" 같은 모호한 항목 금지. "파일 X의 함수 Y를 Z 때문에 수정해야 함" 수준으로.

내가 이 문서만 읽고 내일 다른 세션에서 이어갈 수 있어야 해. 이 대화를 못 봤다고 가정하고 써.
```

출처: https://www.nathanonn.com/claude-code-handoff-doc-skill/

### `F-04` 재개 프롬프트 (상태 검증 먼저)

**환경** 공통 · **유형** 운영

> **언제 쓰나** 핸드오프 문서로 다음 날 시작할 때. 바로 작업시키면 낡은 전제 위에서 출발한다.

```text
HANDOFF.md 를 읽고 이어서 작업할 거야. 바로 시작하지 마.

먼저:
1. HANDOFF.md 의 "State"가 현재 실제 상태와 일치하는지 확인해줘
2. 불일치가 있으면 그것부터 보고해
3. "Open follow-ups" 중 첫 항목이 여전히 유효한지(이미 됐거나, 전제가 바뀌지 않았는지) 확인해줘

확인이 끝나면 무엇부터 할지 제안하고 내 승인을 기다려.
```

출처: https://code.claude.com/docs/en/common-workflows


## F. 운영 · 외부 메모리

### `F-05` 다중 세션 메모리 구조 세우기

**환경** 공통 · **유형** 운영

> **언제 쓰나** 여러 날에 걸친 프로젝트 시작 시 1회. '완료 표시는 검증됐을 때만'이 핵심 규칙.

```text
[프로젝트 시작 시 1회]
본격 작업 전에 메모리 구조부터 세우자. 다음 파일을 만들어줘:
1. progress.md — 완료된 것 / 다음 할 것
2. checklist.md — 전체 항목 목록과 범위 정의
3. setup.md — 프로젝트 시작 방법과 환경 정보

★규칙★: 항목을 "완료"로 표시하는 건 작업했을 때가 아니라 end-to-end 검증이 끝났을 때만이야. 이걸 checklist.md 맨 위에 적어둬.

[이후 매 세션]
시작: 위 파일들을 먼저 읽고 프로젝트 상태를 복원해줘.
종료: progress.md 를 갱신해줘 — 완료한 것과 남은 것.
```

출처: https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool


## F. 운영 · 실패 복구

### `F-06` 막혔을 때 — 재시도 금지, 진단부터

**환경** 공통 · **유형** 운영

> **언제 쓰나** 같은 시도를 반복하며 제자리걸음할 때.

```text
멈춰. 같은 걸 반복하고 있어. 다시 시도하지 말고 진단부터 해줘.

1. 지금까지 시도한 접근을 나열하고, 각각 정확히 어디서 실패했는지 (증상 말고 실패 지점)
2. 그 접근들이 공유하는 "암묵적 전제"가 뭐야?
3. 그 전제 중 틀렸을 가능성이 가장 높은 건?
4. 전제가 틀렸다면 대안 접근 2개는?

아직 실행하지 마. 위 4개에만 답해.

If the task is unreasonable or infeasible, or if any of the tests are incorrect, please inform me rather than working around them. When encountering obstacles, do not use destructive actions as a shortcut.
```

출처: https://code.claude.com/docs/en/best-practices

### `F-07` 무한 탐색 방지 (읽기 예산 걸기)

**환경** 공통 · **유형** 운영

> **언제 쓰나** '조사해줘' 한마디에 수백 파일을 읽어 컨텍스트가 폭발할 때.

```text
{주제}를 조사해줘. 단, 다음 예산 안에서:
- 최대 {N}개 파일까지만 읽어
- 그 안에 답을 못 찾으면 멈추고, 어디를 더 봐야 할지 나에게 물어봐
- 탐색은 서브에이전트로 격리하고, 나에게는 결론만 보고해

읽기 시작하기 전에 "어떤 파일을 왜 읽을 건지" 목록을 먼저 보여줘.
```

출처: https://code.claude.com/docs/en/best-practices


## F. 운영 · 자기검증

### `F-08` 주장이 아니라 증거를 요구하기

**환경** 공통 · **유형** 운영

> **언제 쓰나** '완료했습니다'만 오고 실제로는 안 됐을 때.

```text
작업이 끝나면 "완료했습니다"라고 쓰지 마. 대신 다음 증거를 그대로 붙여줘.
- 실행한 명령어와 그 출력 전문
- 통과한 항목과 실패한 항목의 개수
- 검증하지 못한 부분과 그 이유

검증하지 못한 게 있으면 숨기지 말고 명시해.
```

출처: https://code.claude.com/docs/en/best-practices


## F. 운영 · Cowork 세팅

### `F-09` Cowork 폴더 위생 규칙

**환경** Cowork · **유형** 운영

> **언제 쓰나** Cowork를 처음 세팅할 때. 사고를 미리 막는 4가지.

```text
① 전용 작업 폴더를 만든다 (예: Documents\Cowork-Playground) — 루트 드라이브 선택 금지
② 폴더명은 영문으로 (한글 경로 버그 회피)
③ 폴더에 CLAUDE.md(폴더 지침)를 두고 상시 규칙을 적는다:
   - 파일 삭제/덮어쓰기 전에 변경 내용을 보여주고 확인을 기다릴 것
   - 자료에 없는 수치·담당자·일정은 '확인 필요'로 표시할 것
   - 산출물은 output/ 아래에 날짜_제목 형식으로 저장할 것
④ 커넥터는 필요한 것만 연결한다 (Gmail → Drive → Calendar → Notion 순 권장)
```

출처: https://www.aiground.co.kr/claude-cowork-beginners-guide/


## F. 운영 · 안티패턴

### `F-10` 공식이 지목한 5대 실패 패턴과 처방

**환경** 공통 · **유형** 운영

> **언제 쓰나** 세션이 자꾸 산으로 갈 때 자가진단표로 쓴다.

```text
① The kitchen sink session — 한 작업 하다 딴 걸 묻고 돌아옴
   → 무관한 작업 사이에는 /clear (Chat이면 새 대화)

② Correcting over and over — 고쳐도 계속 틀림
   → 2회 실패하면 /clear + 배운 걸 반영한 더 나은 초기 프롬프트

③ The over-specified CLAUDE.md — 규칙이 있는데 무시함
   → 가차없이 가지치기. 지시 없이도 잘하면 삭제하거나 훅으로 전환
   → "Bloated CLAUDE.md files cause Claude to ignore your actual instructions!"

④ The trust-then-verify gap — 그럴듯한데 엣지케이스가 깨짐
   → 항상 검증 수단 제공. "If you can't verify it, don't ship it."

⑤ The infinite exploration — 범위 없는 조사로 컨텍스트 폭발
   → 범위를 좁히거나 서브에이전트로 격리
```

출처: https://code.claude.com/docs/en/best-practices

### `F-11` 2026년에 '지우라'고 명시된 옛날 프롬프트들

**환경** 공통 · **유형** 운영

> **언제 쓰나** 예전에 만든 프롬프트를 최신 모델로 옮길 때. 마이그레이션의 첫 작업은 추가가 아니라 제거다.

```text
삭제 대상 (Opus 5 기준 공식 지침):
- "double-check your answer" / "re-verify before responding"
  → Opus 5는 시키지 않아도 자기 검증을 한다. 비용만 늘고 결과는 나빠진다. 재작성이 아니라 삭제.
- "CRITICAL: You MUST use this tool when..."
  → 최신 모델은 시스템 프롬프트에 더 민감해져 오히려 과트리거한다. "Use this tool when..." 수준으로 낮춘다.
- "include a final verification step" 류의 상시 검증 지시
- 수동 chain-of-thought(<thinking> 태그 강제) — thinking 기능으로 대체
- prefill(assistant 메시지 미리 채우기) — Claude 4.6 이상에서 400 에러
- thinking budget_tokens 지정 — Claude 4.7 이상에서 400 에러

- 코드 리뷰에서 "only report high-severity issues" / "be conservative"
  → 문자 그대로 따라서 덜 보고한다. 전부 보고시키고 별도 패스에서 필터링하라.
```

출처: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5


## G. 자산화 · CLAUDE.md

### `G-01` 공식 최소 CLAUDE.md (이게 정답 크기다)

**환경** Code · **유형** 자산

> **언제 쓰나** 처음 만들 때. /init 으로 초안을 만든 뒤 이 수준으로 깎는다. 목표 200줄 이하.

```text
# Code style
- Use ES modules (import/export) syntax, not CommonJS (require)
- Destructure imports when possible (eg. import { foo } from 'bar')

# Workflow
- Be sure to typecheck when you're done making a series of code changes
- Prefer running single tests, and not the whole test suite, for performance

★ 판별 질문: 한 줄마다 "이걸 지우면 Claude가 실수할까?" 아니면 지운다.
```

출처: https://code.claude.com/docs/en/memory

### `G-02` CLAUDE.md 포함/제외 기준표

**환경** Code · **유형** 자산

> **언제 쓰나** 무엇을 넣을지 판단할 때.

```text
[넣을 것]
- Claude가 추측할 수 없는 bash 명령어
- 기본값과 다른 코드 스타일 규칙
- 테스트 방법·선호 테스트 러너
- 저장소 에티켓 (브랜치 명명, PR 관례)
- 프로젝트 고유 아키텍처 결정
- 개발 환경 특이사항 (필수 환경변수)
- 흔한 함정, 비자명한 동작

[빼야 할 것]
- 코드를 읽으면 알 수 있는 것
- Claude가 이미 아는 표준 관례
- 상세 API 문서 (링크로 대체)
- 자주 바뀌는 정보
- 긴 설명이나 튜토리얼
- 파일별 코드베이스 설명
- "clean code를 작성하라" 같은 자명한 관행

※ 스타일 가이드는 CLAUDE.md가 아니라 린터에 맡겨라.
```

출처: https://code.claude.com/docs/en/best-practices

### `G-03` Karpathy 계열 4원칙 (드롭인 전문)

**환경** Code · **유형** 자산

> **언제 쓰나** 프로젝트 무관하게 LLM 코딩 실수를 줄이는 범용 규칙. 그대로 복사해 병합한다.

```text
## 1. Think Before Coding
**Don't assume. Don't hide confusion. Surface tradeoffs.**
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First
**Minimum code that solves the problem. Nothing speculative.**
- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

## 3. Surgical Changes
**Touch only what you must. Clean up only your own mess.**
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- Remove imports/variables that YOUR changes made unused; don't remove pre-existing dead code.
The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution
**Define success criteria. Loop until verified.**
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
For multi-step tasks, state a brief plan: [Step] → verify: [check]
```

출처: https://github.com/multica-ai/andrej-karpathy-skills/blob/main/CLAUDE.md


## G. 자산화 · 폴더 지침

### `G-04` Cowork 폴더 지침 템플릿 (업무용 CLAUDE.md)

**환경** Cowork · **유형** 자산

> **언제 쓰나** Cowork에 폴더를 연결할 때 그 안에 두는 상시 규칙 파일.

```text
# 이 폴더 작업 규칙

## 산출물
- 결과물은 `output/` 아래 `YYYYMMDD_제목.확장자` 로 저장
- 원본 파일은 절대 덮어쓰지 말 것. 수정본은 `_v2` 접미사로

## 안전
- 파일 삭제/이동/덮어쓰기 전에 목록을 보여주고 확인을 기다릴 것
- 삭제는 절대 자동 실행하지 말 것

## 사실성
- 자료에 없는 수치·담당자·일정은 만들지 말고 '확인 필요'로 표시
- 모든 수치에는 출처(파일명·시트·행)를 병기

## 문체
- [해요체/합쇼체], 과장 표현 금지, 한 문단 3~5문장

## 자주 쓰는 양식
- 보고서 양식: `templates/report.docx`
- 제안서 양식: `templates/proposal.hwp`
```

출처: https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork


## G. 자산화 · 슬래시 커맨드

### `G-05` 배포 전 점검 커맨드 (/deploy)

**환경** Code · **유형** 자산

> **언제 쓰나** 반복 체크리스트를 명령 하나로 굳힐 때. .claude/commands/deploy.md 에 저장.

```text
Pre-deployment checklist for $ARGUMENTS (or main branch if not specified):

1. Run the test suite and confirm all tests pass
2. Check for any console.log statements that shouldn't go to production
3. Verify environment variables are documented in .env.example
4. Check that package.json version was bumped if needed
5. Look for any TODO comments that should be resolved before shipping
6. Summarize what changed and whether it's safe to deploy

If anything fails, stop and explain what needs to be fixed first.
```

출처: https://dev.to/subprime2010/claude-code-custom-slash-commands-build-your-own-deploy-review-test-1ifc

### `G-06` 컨텍스트 자동 주입 커맨드 문법

**환경** Code · **유형** 자산

> **언제 쓰나** 명령 실행 시점의 git 상태 등을 프롬프트에 자동으로 넣을 때.

```text
---
description: Create a git commit with a conventional message
allowed-tools: Bash(git add:*), Bash(git commit:*)
argument-hint: [message]
model: haiku
---

# Commit Changes

<git_diff>
!`git diff --cached`
</git_diff>

Create a commit message following Conventional Commits.
If $ARGUMENTS is provided, use it as the commit message.

※ 문법 포인트
!`명령`     → 실행 결과를 프롬프트에 주입
$ARGUMENTS  → 인자 치환 ($1, $2 로 개별 접근)
model:      → 간단한 커맨드는 저비용 모델로
```

출처: https://alexop.dev/posts/claude-code-slash-commands-guide/


## G. 자산화 · 스킬

### `G-07` 워크플로 스킬 = 슬래시 커맨드 (수동 전용)

**환경** Code · **유형** 자산

> **언제 쓰나** 부작용이 있는 워크플로를 자동 발동 없이 수동으로만 쓰게 할 때.

```text
---
name: fix-issue
description: Fix a GitHub issue
disable-model-invocation: true
---
Analyze and fix the GitHub issue: $ARGUMENTS.

1. Use `gh issue view` to get the issue details
2. Understand the problem described in the issue
3. Search the codebase for relevant files
4. Implement the necessary changes to fix the issue
5. Write and run tests to verify the fix
6. Ensure code passes linting and type checking
7. Create a descriptive commit message
8. Push and create a PR

※ 커스텀 커맨드는 스킬로 통합됐다. .claude/commands/x.md 와 .claude/skills/x/SKILL.md 는 둘 다 /x 를 만든다.
```

출처: https://code.claude.com/docs/en/skills

### `G-08` SKILL.md 작성 규격 (description이 전부다)

**환경** 공통 · **유형** 자산

> **언제 쓰나** 스킬을 만들 때. description은 Claude가 100개 넘는 스킬 중에서 고르는 유일한 단서다.

```text
---
name: processing-pdfs          # 소문자·숫자·하이픈, 64자 이내, 동명사형 권장
description: Extracts text and tables from PDF files, fills forms, and merges documents. Use when working with PDF files or when the user mentions PDFs, forms, or document extraction.
---

# PDF Processing

## Quick start
[가장 흔한 사용법을 코드/절차로 바로]

## Advanced
**Form filling**: See [FORMS.md](FORMS.md)
**API reference**: See [REFERENCE.md](REFERENCE.md)

★ description 공식 = [동사구: 무엇을 하는가] + "Use when ~" [구체적 트리거: 파일 유형·사용자 표현·상황]
★ 반드시 3인칭으로. "I can help you..." / "You can use this to..." 금지.
★ 나쁜 예: "Helps with documents" / "Processes data"
★ 본문 500줄 이하. 참조는 1단계 깊이까지만 (중첩 참조 금지).
★ 3계층 로딩: 메타데이터(항상, ~100토큰) → 본문(트리거 시) → 참조파일(필요할 때만, 미사용 시 0토큰)
```

출처: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices

### `G-09` 자유도 설계 — 좁은 다리인가 열린 들판인가

**환경** 공통 · **유형** 자산

> **언제 쓰나** 스킬을 얼마나 구체적으로 쓸지 정할 때.

```text
[낮은 자유도 — "양쪽이 절벽인 좁은 다리"]
취약하고 순서가 중요한 작업. 정확한 명령을 박아둔다.
  Run exactly this script:
  python scripts/migrate.py --verify --backup
  Do not modify the command or add additional flags.

[중간 자유도]
선호 패턴은 있으나 변형 허용. 파라미터가 있는 의사코드/스크립트.
  def generate_report(data, format="markdown", include_charts=True):

[높은 자유도 — "위험 없는 열린 들판"]
맥락이 최선을 결정하는 작업(코드 리뷰, 글 다듬기). 방향만 준다.
  1. Analyze the code structure and organization
  2. ...
```

출처: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices


## G. 자산화 · 서브에이전트

### `G-10` 코드 리뷰어 서브에이전트 (공식 전문)

**환경** Code · **유형** 자산

> **언제 쓰나** .claude/agents/code-reviewer.md 에 저장. 우선순위 3단 분류가 실무 효용의 핵심.

```text
---
name: code-reviewer
description: Expert code review specialist. Proactively reviews code for quality, security, and maintainability. Use immediately after writing or modifying code.
tools: Read, Grep, Glob, Bash
model: inherit
---

You are a senior code reviewer ensuring high standards of code quality and security.

When invoked:
1. Run git diff to see recent changes
2. Focus on modified files
3. Begin review immediately

Review checklist:
- Code is clear and readable
- Functions and variables are well-named
- No duplicated code
- Proper error handling
- No exposed secrets or API keys
- Input validation implemented
- Good test coverage
- Performance considerations addressed

Provide feedback organized by priority:
- Critical issues (must fix)
- Warnings (should fix)
- Suggestions (consider improving)

Include specific examples of how to fix issues.
```

출처: https://code.claude.com/docs/en/sub-agents

### `G-11` 디버거 서브에이전트 (근본원인 전문)

**환경** Code · **유형** 자산

> **언제 쓰나** 에러·테스트 실패 전담. '최소 수정'과 '재발 방지'가 포인트.

```text
---
name: debugger
description: Debugging specialist for errors, test failures, and unexpected behavior. Use proactively when encountering any issues.
tools: Read, Edit, Bash, Grep, Glob
---

You are an expert debugger specializing in root cause analysis.

When invoked:
1. Capture error message and stack trace
2. Identify reproduction steps
3. Isolate the failure location
4. Implement minimal fix
5. Verify solution works

For each issue, provide:
- Root cause explanation
- Evidence supporting the diagnosis
- Specific code fix
- Testing approach
- Prevention recommendations

Focus on fixing the underlying issue, not the symptoms.
```

출처: https://code.claude.com/docs/en/sub-agents


## G. 자산화 · 훅

### `G-12` 편집 후 자동 포맷 훅 (권고가 아니라 강제)

**환경** Code · **유형** 자산

> **언제 쓰나** '매번 반드시' 일어나야 하는 일. CLAUDE.md 지시는 권고, 훅은 결정론적이다.

```text
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path' | xargs npx prettier --write"
          }
        ]
      }
    ]
  }
}

※ 훅 자체를 Claude에게 쓰게 해도 된다: "Write a hook that runs eslint after every file edit."
※ 컴팩션으로 중요 정보가 날아가는 걸 막으려면 SessionStart 훅에 compact matcher를 걸어 핵심 컨텍스트를 재주입한다.
```

출처: https://code.claude.com/docs/en/hooks-guide

---

# 제4부. 활용 방안

## 4-1. 성숙도 4단계 — 프롬프트를 '치는 것'에서 '자산'으로

프롬프트를 잘 모으는 것보다 중요한 것은 **모은 것을 어디에 두느냐**입니다. 같은 문장이라도 매번 손으로 치면 소모품이고, 파일에 두면 자산입니다.

| 단계 | 무엇을 한다 | 프롬프트가 사는 곳 | 이 단계의 신호 |
|---|---|---|---|
| **L1 즉석** | 카드를 복사해 붙여 쓴다 | 이 문서 / HTML 대시보드 | "매번 찾아서 붙여넣는다" |
| **L2 상시화** | 반복 규칙을 지침 파일로 내린다 | CLAUDE.md · 폴더 지침 · Projects 지침 · 스타일 | "같은 지시를 세 번 이상 썼다" |
| **L3 스킬화** | 절차 전체를 스킬로 굳힌다 | `.skill` / SKILL.md / 슬래시 커맨드 | "절차가 3단계 이상이고 순서가 중요하다" |
| **L4 자동화** | 사람 없이 돌린다 | 예약 작업 · 훅 · 헤드리스 스크립트 | "주기가 정해져 있고 판단이 필요 없다" |

**승격 규칙 세 가지**

1. **L1 → L2 : 3회 규칙.** 같은 지시를 세 번 썼으면 지침 파일로 내립니다. 단, 내리기 전에 "이 줄을 지우면 Claude가 실수할까?"를 물어보세요. 아니면 넣지 않습니다.
2. **L2 → L3 : 손으로 한 번 완주한 뒤에만.** 카드 `C-19`("지금까지의 과정을 스킬로 만들어줘")를 쓰는 것이 가장 확실합니다. 한 번도 해보지 않은 작업을 스킬로 먼저 만들면 거의 실패합니다 — 규칙이 어디서 튀어나오는지 모르기 때문입니다.
3. **L3 → L4 : 실패해도 되는 것부터.** 되돌리기 어려운 작업(발송·삭제·결제)은 자동화 대상에서 제외하거나 반드시 `A-21`(되돌릴 수 없는 행동은 물어보기)을 걸어 둡니다.

## 4-2. 세 환경을 하나의 흐름으로 잇는 법

사용자가 요청한 "전체 흐름을 잇는 프롬프트"의 실체는 **한 세션 안의 긴 프롬프트가 아니라, 산출물 파일을 매개로 세션과 환경을 잇는 것**입니다. 컨텍스트가 유일한 제약이기 때문에, 흐름은 대화가 아니라 **파일로 이어야** 합니다.

```
[Chat]                  [Cowork]                        [Code]
발상·구조 잡기      →   자료 수집·문서 산출        →   구현·검증
   │                        │                              │
   └─ SPEC.md ──────────────┴─ findings.md / analysis.md ──┘
      RESEARCH_BRIEF.md        output/*.xlsx *.pptx *.docx
                               HANDOFF.md  (모든 경계에서)
```

**연결 규칙 네 가지**

1. **경계마다 파일을 남긴다.** 세션이 바뀌거나 환경이 바뀌면 `E-01`의 SPEC.md, `E-11`의 RESEARCH_BRIEF.md·findings.md·analysis.md, `F-03`의 HANDOFF.md 중 하나를 반드시 만듭니다.
2. **다음 세션은 그 파일만 읽는다.** "이 대화를 못 봤다고 가정하고 써"라는 `F-03`의 마지막 줄이 이 규칙을 지탱합니다.
3. **재개할 때는 상태부터 검증한다.** `F-04`. 낡은 전제 위에서 출발하는 것이 실무에서 가장 흔한 사고입니다.
4. **완료 표시는 검증됐을 때만.** `F-05`의 핵심 규칙. 작업했을 때가 아니라 end-to-end로 확인됐을 때만 체크합니다. 이게 무너지면 다음 세션이 거짓 진척도를 물려받습니다.

## 4-3. 이암허브 실무에 붙이는 다섯 갈래

이미 보유하신 스킬(제안서 변환, 스마트팜 컨설팅 보고서, 교육영상 품질게이트, 영상→PPT, 스킬 빌더)에 이 라이브러리를 얹는 구체적 경로입니다.

### ① 정성제안서 (PPT → 한글 변환)

기존 `ppt-to-hwp-proposal` 스킬은 L3에 있습니다. 여기에 흐름 프롬프트를 붙이면 품질이 올라갑니다.

```
E-01 인터뷰      →  RFP 유형·평가배점·제출형식을 먼저 확정 (SPEC 대신 RFP_BRIEF.md)
   ↓
스킬 실행        →  ppt-to-hwp-proposal 로 목차 도출 + 본문 변환
   ↓
E-10 레드팀      →  "제안요청서 각 요구항목이 실제로 답변됐는가. 스타일 말고 빠진 것만."
   ↓
C-22 추측 금지   →  실적·인력·일정 수치에 근거 없는 것이 없는지 최종 점검
```

가장 값어치 있는 추가는 **E-10 레드팀**입니다. 제안서는 "잘 썼는가"보다 "요구항목을 빠뜨리지 않았는가"에서 떨어지는데, 새 컨텍스트의 리뷰어가 RFP와 제안서를 대조하는 것이 사람이 하는 것보다 빠릅니다. 반드시 마지막 줄("정확성이나 명시된 요구사항에 영향 주는 갭만")을 붙이세요 — 없으면 없는 문제를 만들어 옵니다.

### ② 스마트팜 경영성과 컨설팅 보고서

`smartfarm-consulting-report` 스킬 + **E-12 데이터 파이프라인**의 조합이 정확히 들어맞습니다.

```
E-12 [1 수집]  농진청 소득조사표·환경데이터·출하데이터를 raw/ 에.
               "수집한 데이터를 컨텍스트에 출력하지 마" ← 이 한 줄이 대용량 처리를 가능하게 함
E-12 [2 정제]  정제 규칙을 cleaning.py 로 남기고, 버린 행은 dropped.csv 로 별도 보관
               → 전후 행 수 대조표를 승인한 뒤 진행
E-12 [3 시각화] 차트 전에 "이 데이터로 답할 질문 3개"를 먼저 제안받고 고른다
E-12 [4 보고]  ★ "본문의 모든 수치가 clean/ 에서 재현되는지 실제로 다시 계산해 대조"
               → 불일치가 있으면 보고서를 쓰지 말고 먼저 알리게 한다
```

컨설팅 보고서에서 가장 치명적인 사고는 **수치 불일치**입니다. `E-12`의 4단계 자기검증과 `F-08`(주장이 아니라 증거)가 이 문제를 구조적으로 막습니다.

### ③ 교육영상 (딸기 교육영상 시리즈)

`edu-video-production-quality-gate`는 이미 "측정하되 계산하지 말라"는 검증 게이트를 갖고 있습니다. 이는 제1부 2번 원칙의 모범 사례입니다. 여기에 붙일 것은 **E-05 Evaluator–Optimizer**입니다.

```
루브릭(기존 스킬의 평가 기준)을 그대로 <rubric>에 넣고
Generator(영상 수정) ⇄ Evaluator(루브릭 대조) 루프를 돌린다.
3회 반복해도 같은 항목이 FAIL이면 → 멈추고 "루브릭 자체가 틀렸을 가능성"을 보고하게 한다.
```

마지막 종료 조건이 중요합니다. 루브릭이 잘못됐는데 계속 고치면 영상이 이상해집니다.

### ④ 발표자료 / 영상 → PPT

`video-to-ppt` 스킬 앞뒤에 두 개를 붙입니다.

- **앞**: `C-10`(한 장 테스트 먼저) — 폰트·로고·비율을 한 장으로 확정한 뒤 본 제작. 10장 넘어가면 생성이 실패하는 문제를 우회합니다.
- **뒤**: `E-11 [4단계]` — "문서를 슬라이드로 옮기지 마. 다시 설계해. 청중이 기억해야 할 메시지 3개를 먼저 정하고 확인받아." 이 지시가 없으면 대본을 그대로 옮긴 글자 덩어리 슬라이드가 나옵니다.

### ⑤ 사내 표준 프롬프트 만들기

`skill-builder` 스킬과 카드 `G-08`(SKILL.md 규격) · `G-09`(자유도 설계) · `A-26`(프롬프트 개선기)의 조합입니다.

특히 `G-09`의 판단이 실무에서 자주 틀립니다. **순서가 중요하고 실수하면 되돌리기 어려운 작업(제안서 제출 형식, 데이터 정제)은 낮은 자유도**로, **맥락이 최선을 결정하는 작업(글 다듬기, 리뷰)은 높은 자유도**로 써야 합니다. 반대로 하면 각각 "융통성 없음"과 "제멋대로"가 됩니다.

## 4-4. 폴더 지침 한 장으로 시작하기 (오늘 바로)

가장 적은 노력으로 가장 큰 효과를 내는 것은 **연결한 폴더마다 지침 파일 한 장**입니다. `G-04`를 그대로 쓰되, 이암허브용으로는 이 정도면 충분합니다.

```markdown
# 이 폴더 작업 규칙

## 안전
- 파일 삭제·이동·덮어쓰기 전에 목록을 보여주고 확인을 기다릴 것
- 삭제는 절대 자동 실행하지 말 것
- 원본은 덮어쓰지 말고 수정본에 _v2 접미사

## 사실성
- 자료에 없는 수치·담당자·일정은 만들지 말고 '확인 필요'로 표시
- 모든 수치에 출처(파일명·시트·행)를 병기

## 산출물
- output/ 아래 YYYYMMDD_제목.확장자 로 저장
- 압축할 때는 수정한 파일 전체 목록과 확정된 결정사항을 보존할 것

## 문체
- 합쇼체, 과장 표현 금지, 한 문단 3~5문장
```

**200줄을 넘기지 마세요.** 넘기는 순간 규칙이 무시되기 시작합니다.

## 4-5. 30 · 60 · 90일 로드맵

### 첫 30일 — 개인 숙련 (L1 → L2)

| 주 | 할 일 | 성공 판정 |
|---|---|---|
| 1주 | HTML 대시보드를 열어두고 하루 3개씩 카드를 실제로 써 본다. `A-04`(XML 골격)·`C-22`(추측 금지)·`D-06`(검증 기준)부터 | 세 카드를 안 보고 쓸 수 있다 |
| 2주 | 자주 쓰는 폴더 2곳에 폴더 지침(`G-04`) 배치. Chat Projects에 지침(`B-10`) 설정 | 같은 지시를 반복해 치지 않는다 |
| 3주 | `E-01`(인터뷰→SPEC)을 실제 업무 하나에 적용. 반드시 **새 세션에서 실행** | 결과물 재작업 횟수가 줄었다 |
| 4주 | `F-03` 핸드오프 문서로 이틀짜리 작업을 이어본다 | 이튿날 "어디까지 했더라"가 사라졌다 |

**이 달의 금기**: 스킬을 만들지 마세요. 아직 이릅니다.

### 31~60일 — 자산화 (L2 → L3)

| 주 | 할 일 |
|---|---|
| 5~6주 | 손으로 완주한 반복 업무 2~3개를 `C-19`로 스킬화. `G-08` 규격 준수 — 특히 description의 "Use when ~" 부분 |
| 7주 | `E-16`(Writer/Reviewer 두 세션)을 팀 표준으로. 가장 값싼 품질 장치 |
| 8주 | 안티패턴 자가진단 (`F-10`, `F-11`). 지난 두 달의 프롬프트에서 **삭제할 것**을 찾는다 |

**이 달의 핵심 질문**: "내가 매주 반복하는 일이 뭐지?" — Cowork 활용 사례를 모은 글들이 공통으로 지목하는, 가장 중요한 질문입니다.

### 61~90일 — 조직화 (L3 → L4)

| 주 | 할 일 |
|---|---|
| 9~10주 | 검증된 스킬을 팀에 배포. 폴더 지침을 공유 저장소에 두고 버전 관리 |
| 11주 | 예약 작업 도입 — 되돌릴 수 있는 것부터 (브리핑 생성, 자료 수집). 발송·삭제는 제외하거나 `A-21` 필수 |
| 12주 | `E-11`/`E-12` 파이프라인을 정식 업무 절차로 문서화. 각 단계의 승인 게이트를 누가 볼지 정한다 |

**이 달의 경고**: 멀티에이전트(`E-09`, `E-15`)는 일반 대화의 **약 15배 토큰**을 씁니다. 고가치·병렬 가능 작업에만 쓰고, 대부분의 코딩 작업처럼 맥락 공유가 많은 일에는 오히려 나쁩니다.

## 4-6. 자주 하는 실수 다섯 가지 (요약)

| 실수 | 증상 | 처방 카드 |
|---|---|---|
| 지침 파일을 계속 늘린다 | 규칙을 넣었는데 안 지킨다 | `G-02` 포함/제외 기준, 200줄 상한 |
| 같은 문제를 세 번 넘게 교정한다 | 고칠수록 나빠진다 | `F-01` 2회 교정 규칙 — 고치지 말고 리셋 |
| 검증 수단 없이 맡긴다 | "완료했습니다"인데 안 됨 | `D-06`, `F-08` |
| 범위 없이 "조사해줘" | 컨텍스트 폭발, 응답 저하 | `F-07` 읽기 예산 |
| 옛날 프롬프트를 그대로 쓴다 | 과검증·과트리거·400 에러 | `F-11` 삭제 목록 |

---

# 부록. 조사 한계와 검증 안내

정직하게 밝힙니다.

- **접근 차단으로 원문을 확보하지 못한 소스**: Reddit r/ClaudeAI(프록시 403), YouTube 영상 설명·자막(429), Threads·dcinside 일부 게시물(robots.txt). 이들 내용은 **2차 정리 기사**를 통해서만 반영했고, 카드에는 그 2차 출처를 표기했습니다.
- **일부 한국어 "프롬프트 모음" 글**은 페이지는 열렸으나 저작권 사유로 코드블록 전문을 재현할 수 없었습니다. 해당 글은 제목·구조만 참고했고, 카드에는 다른 확인 가능한 출처의 프롬프트를 실었습니다.
- **대괄호 변수형 프롬프트**(`[폴더 경로]`, `[기간]` 등)는 원저자가 템플릿화한 버전일 가능성이 높습니다. 원문 그대로가 아닐 수 있습니다.
- **가장 신뢰도 높은 출처는 Anthropic 공식 문서**입니다. 기능 설명이 한국어 블로그와 충돌할 경우 공식 문서를 따랐습니다(예: 예약 작업의 클라우드 실행 여부).
- 문서 구조가 자주 바뀝니다. 2026-08 기준으로 기법별 개별 페이지들이 하나의 "living reference"로 통합되었습니다. 링크가 리다이렉트되면 아래 두 곳을 먼저 확인하세요.

**1차 출처 (분기마다 재확인 권장)**

- 프롬프트 베스트 프랙티스 통합본 — https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- Opus 5 전용 프롬프트 가이드 — https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5
- Claude Code 베스트 프랙티스 — https://code.claude.com/docs/en/best-practices
- Claude Code 프롬프트 라이브러리 — https://code.claude.com/docs/en/prompt-library
- Agent Skills 작성법 — https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- Building effective agents — https://www.anthropic.com/engineering/building-effective-agents
- Effective context engineering — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Multi-agent research system — https://www.anthropic.com/engineering/multi-agent-research-system
- Cowork 시작하기 — https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork
