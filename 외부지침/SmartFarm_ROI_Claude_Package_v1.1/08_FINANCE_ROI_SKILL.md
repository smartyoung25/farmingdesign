# 08. FINANCE & ROI SKILL
## 목적
CAPEX, OPEX, 매출, 금융조건을 연결해 사업 자체와 자기자본 관점의 경제성을 분석한다.

## 입력
- CAPEX
- OPEX/LCC
- Revenue
- 자기자본
- 보조금
- 대출
- 금리
- 거치
- 상환기간/방식
- 할인율
- 분석기간
- 세금/감가상각 가정

## 두 개의 경제성
### Project Economics
보조금/금융 구조와 분리하여 시설사업 자체의 현금창출력 평가

### Equity Economics
보조금과 차입을 반영한 사업주 자기자본 수익성

## 지표
- Simple ROI
- Operating Margin
- Payback
- NPV
- IRR
- BEP Revenue
- BEP Yield
- BEP Price
- DSCR
- Cumulative Cash Flow

## 보조금
- 확정/예정/미확정 구분
- 대상 공종 확인
- 지급시점 반영
- 지연 시 브릿지 금융비용 반영
- 무보조 Case 병행

## Maximum Investable CAPEX
사용자 목표 예:
- IRR ≥ 8%
- Payback ≤ 8년
- DSCR ≥ 1.3

절차:
1. Base/Reality Cash Flow 생성
2. CAPEX를 변수로 둔다
3. 모든 제약을 만족하는 최대 CAPEX 탐색
4. 현재 견적과 비교
5. 초과액을 설계 Value Engineering 목표로 제시

## 출력
| 지표 | Project | Equity | Reality | Stress |
|---|---:|---:|---:|---:|

추가:
- 최대 감당 투자비
- 현재 CAPEX와의 차이
- 연차별 부채상환
- 최저 현금잔고
- 현금고갈 연도
- 금융 리스크

## Handoff
→ `09_SCENARIO_STRESS_SKILL.md`, `12_REPORT_GENERATOR_SKILL.md`
