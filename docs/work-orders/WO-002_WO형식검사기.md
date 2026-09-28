# 작업지시서 WO-002: WO 형식 검사기 · 가드

- 작성일: 2026-09-28
- 작업 유형: 테스트 보강
- 선행 지시서: WO-001

## 1. 목적
- `docs/work-orders/`의 WO가 스킬 Verification Checklist 중 **기계로 판정할 수 있는 항목**을 지키는지 명령 하나로 판정한다. 지금은 사람이 눈으로만 볼 수 있다.

## 2. 배경·사용자
- 사용자: WO를 쓰는 세션(작성 직후 자가점검), 커밋 전 게이트를 돌리는 세션.
- 이 리포는 규칙마다 기계 가드를 둔다(`audit_traceability.py` 46차 등). 스킬 규칙만 가드가 없으면 「양식을 빼거나 기준을 흐리는」 일을 막을 수 없다(스킬 Foundational Principle).

## 3. 범위
- 포함:
  - 루트에 `audit_work_orders.py`(read-only 검사기 + CLI)
  - 가드 테스트 1건(실제 폴더 PASS + 규칙별 변형 입력을 하나씩 잡는지)
  - `CLAUDE.md` 명령어 절에 검사 명령 한 줄
- 제외 (이번에 하지 않음):
  - 수용기준이 목적을 실제로 덮는지 같은 **의미 판정**(사람·레드팀 몫)
  - WO 자동 생성·자동 수정(검사기는 고치지 않고 보고만 한다)
  - 콘솔 화면(→ WO-003)
  - 착수 프롬프트의 「계획 먼저」 여부 검사(프롬프트는 WO 파일 밖 산출물이다)

## 4. 입력·출력
- 입력: `docs/work-orders/WO-NNN_*.md`, `docs/work-orders/WO-NNN-fixK_*.md`, `docs/work-orders/README.md`(색인 표). UTF-8. 폴더가 없거나 WO가 0건이면 FAIL로 보고한다.
- 출력: 표준출력 리포트. 마지막 줄은 `WO 형식 검사: PASS (N건)` 또는 `WO 형식 검사: FAIL (문제 M건)`. 종료 코드 PASS=0, FAIL=1. 파일을 쓰지 않는다.
- 파이썬 인터페이스(예시 형태만): `parse_wo(text) -> dict`(헤더·절·작업 단위·수용기준), `check_wo(text, name, known_ids) -> list[str]`(문제 목록, 빈 목록이면 통과), `audit(folder) -> dict`(`files`·`problems`·`index_missing`·`index_extra`).

## 5. 기술 조건
- 언어: Python 3, 표준 라이브러리만(`re`·`os`·`sys`·`io`)
- 실행 환경: Windows 11, `C:\FarmingDesign`, 리포 루트에서 실행
- 새 의존성 추가: 금지
- 수정 금지 파일·폴더: `CLAUDE.md` 「손대지 말 것」 전체 · 엔진·케이스·레지스트리 · 스킬 원문 본문 · 엔진 계층(`smartfarm_engine.py`·`build_site.py`)은 이 검사기를 import하지 않는다

## 6. 작업 단위 (순서대로)
- T1: 파서 — 완료 조건: WO-001을 넣으면 9절·작업 단위 4개·수용기준 6개가 나온다
- T2: 규칙 검사 — 완료 조건: 아래 규칙마다 위반 변형 1개가 문제 1건 이상을 낸다
  - R1 템플릿 9절이 순서대로 있고 비어 있지 않다(「해당 없음」은 뒤에 이유가 있어야 한다)
  - R2 수용기준마다 「(확인:」이 있고 금지 표현(잘 · 적절히 · 원활하게 · 빠르게 · 깔끔하게 · 사용자 친화적 · 정상 동작 · 문제없이)이 없다 — 「잘못」처럼 낱말 안의 글자는 금지 표현이 아니다
  - R3 3절 「제외」에 항목이 1개 이상이다
  - R4 작업 단위가 1~7개이고 각각 「완료 조건:」을 가진다
  - R5 코드 블록 안에 함수·클래스 정의나 import 줄이 없다
  - R6 헤더(제목 번호 = 파일명 번호 · 작성일 YYYY-MM-DD · 작업 유형 6종 중 하나 · 선행 지시서 「없음」 또는 실재하는 WO)
  - R7 수정 지시서(`-fixK`)는 원 지시서가 실재한다
  - R8 README 색인과 폴더의 WO 파일이 서로 빠짐없이 대응한다
- T3: CLI · 가드 테스트 · `CLAUDE.md` 한 줄 · 차수 기록 — 완료 조건: 7절 전부 통과

## 7. 수용기준
- [x] 현재 폴더(WO-001~003)에서 마지막 줄이 `WO 형식 검사: PASS (3건)`이고 종료 코드가 0이다 (확인: `python audit_work_orders.py`)
- [x] R1~R8 위반 변형 입력마다 문제가 1건 이상 나오고, 원본 WO-001은 문제 0건이다 (확인: `python -m pytest test_engine.py -q -k 247cha`)
- [x] 「잘못」이 들어간 수용기준은 R2 문제를 내지 않는다 (확인: 같은 명령)
- [x] 엔진 계층 `smartfarm_engine.py`·`build_site.py`에 `audit_work_orders` import가 없다 — 표시 계층 `webapp.py`는 WO-003에서 읽기 전용으로 쓴다 (확인: 같은 명령)
- [x] 회귀 3파일 383 passed, C2 ROI 14.2% · Payback 7.1년 · 실질ROI 28.3% 유지 (확인: `python -m pytest test_engine.py test_registry.py test_cases.py -q`)
- [x] 5파일 462 passed, skip 0 (확인: `python -m pytest test_engine.py test_registry.py test_cases.py test_chunking_v2.py test_webapp.py -q`)

## 8. 제약·주의사항
- `CLAUDE.md` 1절 전체 적용. 검사기는 **감사자이지 계산 참여자가 아니다** — 엔진 값을 읽지도 만들지도 않는다.
- 검사기가 「통과」라고 해도 WO가 옳다는 뜻이 아니다 — 리포트 첫 줄에 그 한계를 적는다.
- 비밀키·개인정보: 해당 없음 — 리포 안의 마크다운만 읽고 외부 호출이 없다.

## 9. 보고 형식
- 수용기준별 통과/실패 표(실행한 명령과 결과 포함)
- 변경 파일 목록
- 남은 이슈·리스크
- 인계: `차수로그.md` 247차 항목 + `작업지시서.md` 헤더 「최종 갱신」 교체 + 2절 스냅샷 · README 색인 상태 「완료」
