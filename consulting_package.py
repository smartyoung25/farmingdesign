"""컨설팅 패키지 조립 계층 (181차 신설)

**무엇인가**: 케이스 하나를 받아 서비스 설계서의 산출물 **D1~D20을 한 번에 세우는** 계층이다.
180차까지 엔진에는 함수가 62개 있었지만 **산출물 계층(build_site·webapp)에서 호출되는 것은
17개뿐**이었다 — D13~D20(173~176차 신설)은 **생성 경로가 아예 없었다**.

🔴 **1절 경계 — 이 파일은 계산하지 않는다.**
- 산술 연산자(`*`·`/`·`-`·`//`·`%`·`**`)를 **한 줄도 쓰지 않는다**. 가드가 AST로 검사한다.
- 4축 수치는 이미 있는 단일 경로(`render_report.compute`)를 **재사용**한다 — 여기서 다시
  계산하면 그것이 곧 **병렬 계산기**다.
- 시세성 값(단가·노임·유가·금리)과 고객 문서(도면·견적·하자 기록)는 **주입**받는다.
  주입이 없으면 **`주입대기`로 드러낼 뿐 채우지 않는다**.
- 판단성(업체·사양·작목 선정, 최종판정)은 **하지 않는다**. 패키지는 자료를 모아 줄 뿐이다.
"""
from __future__ import annotations

from collections import Counter as _Counter

import smartfarm_engine as e
import render_report as rr
from cases import case_to_input

# ─────────────────────────────────────────────────────────────
# 산출물 카탈로그 — 설계서 §4와 같은 20종
#   stage: ①공종설계 ②품질설계 ③감리 ④타당성검증 ⑤운영 ⑥사후관리
# ─────────────────────────────────────────────────────────────
PACKAGE_SPEC = [
    {"code": "D1", "title": "입지 진단 카드", "stage": "①공종설계", "targets": ["부지"],
     "engine": ["siting_lookup", "siting_design_load", "weather_station", "design_outdoor_temp",
                "heating_degree_hours", "monthly_mean_wind", "monthly_sunshine",
                "mean_wind", "wind_correction_factor", "period_load_adjust_k"]},
    {"code": "D2", "title": "RFQ 사양서", "stage": "①공종설계", "targets": ["시설"],
     "engine": ["select_specs", "spec_crops", "cover_assembly_options",
                "cover_assembly_lookup", "curtain_exposure_ratio",
                "m2_to_py", "py_to_m2", "equipment_lookup",
                "equipment_component_prices"]},
    {"code": "D3", "title": "설계 대안 비교표", "stage": "①공종설계", "targets": ["시설"],
     "engine": ["compare_design_options"]},
    {"code": "D4", "title": "문서 4축 정합 리포트", "stage": "②품질설계",
     "targets": ["시설", "기자재"],
     "engine": ["doc_consistency_check", "transmission_share_pct",
                "heating_load_components"]},
    {"code": "D5", "title": "견적 정합·업체 비교표", "stage": "④타당성검증",
     "targets": ["시설"], "engine": ["reconcile_quote", "compare_quotes",
                                    "generate_rfq_package", "construction_company_list",
                                    "greenhouse_total_estimate", "structure_only_estimate",
                                    "m2_to_py", "procurement_route",
                                    "quote_count_requirement"]},
    {"code": "D6", "title": "원가 분해표", "stage": "④타당성검증", "targets": ["시설"],
     "engine": ["capex_major_breakdown", "capex_breakdown"]},
    {"code": "D7", "title": "품셈 인력 산출표", "stage": "④타당성검증", "targets": ["시설"],
     "engine": ["pumsem_project_labor_summary", "pumsem_labor_days"]},
    {"code": "D8", "title": "4축 통합 컨설팅 리포트", "stage": "④타당성검증",
     "targets": ["시설"], "engine": ["heating_load", "verify_heating_vs_actual",
                                    "benchmark_check", "production_kg", "finance"]},
    {"code": "D9", "title": "재무 시나리오", "stage": "④타당성검증", "targets": ["시설"],
     "engine": ["operating_breakeven", "max_investable_capex", "loan_amortization",
                "dscr_schedule", "subsidy_application_checklist",
                "npv", "irr", "cluster_economics"]},
    {"code": "D10", "title": "LCC·하자 관리표", "stage": "⑥사후관리",
     "targets": ["시설", "기자재"], "engine": ["warranty_period", "lcc_replacement_schedule",
                                              "warranty_bond_requirement"]},
    {"code": "D11", "title": "근거대장", "stage": "②품질설계", "targets": ["시설"],
     "engine": []},
    {"code": "D12", "title": "결정 지원 패키지", "stage": "④타당성검증", "targets": ["시설"],
     "engine": []},
    {"code": "D13", "title": "검측 체크리스트", "stage": "③감리", "targets": ["시설", "기자재"],
     "engine": ["inspection_checklist"]},
    {"code": "D14", "title": "시운전 계획", "stage": "③감리", "targets": ["시설", "기자재"],
     "engine": ["commissioning_plan"]},
    {"code": "D15", "title": "준공 서류철", "stage": "③감리", "targets": ["시설"],
     "engine": ["completion_docset"]},
    {"code": "D16", "title": "점검 일정표", "stage": "⑥사후관리", "targets": ["시설", "기자재"],
     "engine": ["maintenance_schedule"]},
    {"code": "D17", "title": "하자 추적표", "stage": "⑥사후관리", "targets": ["시설"],
     "engine": ["defect_tracking"]},
    {"code": "D18", "title": "인허가 체크리스트", "stage": "①공종설계", "targets": ["부지"],
     "engine": ["site_permit_checklist"]},
    {"code": "D19", "title": "기자재 대조표", "stage": "②품질설계", "targets": ["기자재"],
     "engine": ["equipment_reconcile"]},
    {"code": "D20", "title": "내용연수 대조표", "stage": "⑥사후관리", "targets": ["기자재"],
     "engine": ["service_life_reference", "service_life_index"]},
    # 🔴182차 — ⑤운영에는 산출물이 **D8 링크뿐**이었고, 172차에 만든 과금 함수는
    #   어느 산출물에도 붙어 있지 않았다. 두 칸을 채운다.
    {"code": "D21", "title": "운영 진단표", "stage": "⑤운영", "targets": ["시설", "기자재"],
     "engine": ["env_fitness", "yield_adjustment", "production_kg",
                "opex_breakdown", "improvement_roi",
                "facility_yield", "facility_yield_crops"]},
    {"code": "D22", "title": "컨설팅 대가 산출", "stage": "④타당성검증", "targets": ["시설"],
     "engine": ["consulting_fee_estimate", "design_supervision_fee_reference",
                "guideline_fee_reference"]},
    # 🔴185차 — 사업기획서(투자검증·설계보증 플랫폼)의 1·3단계를 3×6에 얹는다.
    #   2단계(설계 적정성 검증)는 이미 D4·D13·D14·D15가 덮는다(대응표는 설계서 §0-c).
    {"code": "D23", "title": "투자 실사 카드(6영역)", "stage": "④타당성검증",
     "targets": ["부지", "시설", "기자재"],
     "engine": ["select_specs", "verify_heating_vs_actual", "equipment_reconcile",
                "operating_breakeven", "benchmark_check", "dscr_schedule",
                "site_permit_checklist", "service_life_reference"]},
    {"code": "D24", "title": "설계값–실측 대조표", "stage": "⑤운영",
     "targets": ["시설", "기자재"],
     "engine": ["verify_heating_vs_actual", "benchmark_check", "production_kg"]},
    # 🔴187차 — ★사용자 결정으로 **등급 부여**가 들어왔다.
    #   등급은 **검증 항목 통과 수 + 실격 사유**이지 사업 평가가 아니다.
    {"code": "D25", "title": "K-SFID 검증 등급·인증서", "stage": "②품질설계",
     "targets": ["부지", "시설", "기자재"],
     "engine": ["ksfid_grade", "ksfid_number", "ksfid_validity",
                "select_specs", "verify_heating_vs_actual", "benchmark_check",
                "site_permit_checklist", "warranty_period"]},
    # 🔴188차 — 185차 `D24`가 *"편차 함수가 없다"*로 세어 둔 3항목에 함수를 붙였다.
    {"code": "D26", "title": "성능보증 판정서", "stage": "⑥사후관리",
     "targets": ["시설", "기자재"],
     "engine": ["performance_shortfall", "guarantee_assessment", "guarantee_fee",
                "production_kg"]},
    {"code": "D27", "title": "기성 확인서", "stage": "③감리", "targets": ["시설"],
     "engine": ["progress_certification"]},
]

# 주입 슬롯 — 이름과 성격을 밝혀 둔다(무엇이 없어서 못 세우는지 고객이 알아야 한다)
INJECTION_SLOTS = {
    "winter_months": "동절기 개월 — ★D-9 결정(2026-09-28): **케이스마다 입력**, 한 달 지정도 유효. "
                     "엔진은 기본값을 두지 않는다(원문이 동절기를 정의하지 않는다)",
    "curtain": "피복조합(`FR_TABLE` 키) — ★`D-4`·`FR_TABLE` 계열 결정에 걸려 있어 "
               "임의로 고르지 않는다",
    "doc_rows": "도면·시방서·BoQ·규격서 식별자/Rev 행 — 고객 문서",
    "vendor_quotes": "업체 견적(카테고리별 금액) — 시세성",
    "capex_items": "견적 공종별 금액 — 시세성",
    "quantities": "공종별 물량 — 설계 성과품",
    "loan": "대출 조건(금리·기간) — 시세성",
    "lcc_items": "품목별 단가·내용연수 — 단가는 시세성",
    "maintenance_items": "점검 대상 품목",
    "inspection_intervals": "점검 주기(개월) — 🔴리포에 국내 기준표가 없다(174차)",
    "defect_records": "하자 발생·보수 기록 — 고객 운영자료",
    "completion_date": "준공일",
    "quoted_models": "견적에 적힌 기자재 모델명",
    "ks_declared": "규격 선언(KS 적합 여부)",
    "attachments_by_model": "재료승인 첨부(모델별 서류명) — 고객 문서. 시방서 6종과 대조한다",
    "service_life_names": "내용연수를 조회할 기종명",
    "acceptance_criteria": "장비별 시운전 합격 기준 — 🔴시방서 원문에 없다(173차)",
    "land_use_zone": "용도지역 — 지자체 확인 사항",
    "capex_targets": "CAPEX 상한 역산의 목표치(목표 IRR·최대 Payback·최소 DSCR) — "
                     "🔴**협의 항목**이라 기본값을 두지 않는다",
    "pumsem_probe": "품셈 단일 항목 조회(분류·품명·수량) — 설계 성과품",
    "rfq_form": "RFQ 기준 형식(연동·단동 등) — 🔴**판단성**이라 기계가 고르지 않는다",
    "quote_for_reconcile": "정합 검사할 견적 1건(카테고리별 금액·직접비·총액) — 시세성",
    "has_thermal_screen": "보온커튼 유무(True/False) — 설계 조건",
    "period_sunshine_h": "기간 일조시간(h) — 설계 조건. 🔴월별 표를 기계가 합치면 "
                         "기간 정의를 임의로 정하는 것이 된다",
    "cover_layers": "피복 층 구성(층 이름 tuple) — `COVER_ASSEMBLIES` 키",
    "equipment_model": "구성품·표준가격을 조회할 장비 모델명",
    "transmission_kcal_h": "관류열부하(kcal/h) — 설계 성과품. 🔴이 계층이 역산하면 "
                           "그것이 병렬 계산이다",
    "cashflows": "연차별 현금흐름 — NPV·IRR 재계산용(시나리오)",
    "cluster": "단지화 조건(농가 수·공동 CAPEX·절감률 등) — 사업 설계 전제",
    "env_ratios": "환경 적합도 4비율(광·온·습·CO₂) — 운영 실측",
    "opex_items": "OPEX 항목별 금액 — 운영 실측",
    "improvement": "개선 투자(연간 절감액·투자비) — 운영 실측",
    "fee_inputs": "컨설팅 대가 산출 입력(등급별 인·일 · 노임단가 · 제경비율 · 기술료율) "
                  "— 🔴노임은 **시세성**, 인·일은 **우리 원가(판단성)**다",
    "actual_load_per_m2": "준공 후 실측 난방부하(kcal/h·㎡) — 운영 실측",
    "actual_yield_kg": "준공 후 실측 수확량(kg) — 운영 실측",
    "actual_energy": "준공 후 실측 에너지 사용량 — 운영 실측",
    "actual_uptime_pct": "준공 후 실측 가동률(%) — 운영 실측",
    "dd_documents": "실사 제출 문서 목록(사업계획서·설계도서·견적·판로계약 등) — 고객 문서",
    "ksfid_seq": "K-SFID 일련번호(0~9999) — 발급 기관이 관리한다",
    "ksfid_issued": "인증 발급일(YYYY-MM-DD) — 유효기간의 기산점",
    "ksfid_thresholds": "등급 경계를 바꿀 규칙 — 🔴바꾸면 등급이 바뀐다",
    "perf_losses": "성능 미달이 만든 **손실액**(항목별 원) — 🔴단가는 시세성이라 주입 전용",
    "insured_value_won": "보험가액(원) — 보상 합계의 상한. 보증 계약이 정한다",
    "guarantee_rule": "면책·보상비율을 바꿀 규칙 — 🔴바꾸면 지급 대상이 바뀐다",
    "guarantee_fee_inputs": "보증수수료 입력(보증금액·기본요율·운용요율·일수) — "
                            "🔴**요율은 시세성**이라 기본값을 두지 않는다",
    "progress_plan": "공종별 계획(금액 또는 물량) — 설계 성과품",
    "progress_done": "공종별 실적(같은 단위) — 현장 기성 자료",
}

# 🔴 `장비정보.csv`에는 `농장명/업체명`·`농장주`·`계약 금액` 열이 있다 —
#    조회 결과를 그대로 내보내면 **실명과 계약가가 산출물에 실린다**.
#    패키지는 아래 열만 옮긴다(182차).
_DEVICE_FIELDS = ("표준 장치명", "세부 장치명", "모델명", "제조국", "KC 인증여부")
_DEVICE_DROP = ("농장명/업체명", "농장주", "계약 금액")

# ─────────────────────────────────────────────────────────────
# 투자 실사 6영역 (185차) — 사업기획서 §5.1의 평가영역을 엔진에 얹는다.
#   🔴 **덮지 못하는 영역을 덮은 척하지 않는다**: 경영진 역량·시장위치는
#      사람·시장 자료라 엔진 밖이다. 그 둘을 「없음」으로 드러내는 것이
#      이 카드의 값어치다(기획서도 *「문서검토 → 기술평가 → 보고서」*의
#      문서검토 단계를 사람이 한다고 적는다).
#   ⚠️ **등급을 매기지 않는다.** 기획서는 K-SFID 등급(PVEL Top Performer 방식)을
#      두지만, 1절은 판정·추천 자동화를 금한다 — 엔진은 **항목과 결손**까지다.
# ─────────────────────────────────────────────────────────────
DD_AREAS = [
    {"area": "기술시스템", "engine": ["select_specs", "verify_heating_vs_actual",
                                 "equipment_reconcile"],
     "covers": "규격 적합·난방 설계 자릿수 검증·기자재 3열 대조"},
    {"area": "단위경제성", "engine": ["operating_breakeven", "benchmark_check"],
     "covers": "손익분기·단위 공사비 밴드 대조(ROI·NPV·IRR은 D8·D9)"},
    {"area": "운영프로세스", "engine": ["service_life_reference"],
     "covers": "내용연수 3출처 대조(점검 일정·검측은 D16·D13)"},
    {"area": "경영진 역량", "engine": [],
     "covers": "", "gap": "영농경력·기술이해도·재무역량은 **사람 자료**다 — 엔진 밖"},
    {"area": "시장위치", "engine": [],
     "covers": "", "gap": "판로·경쟁강도는 **시세성·시장자료**다 — 1절이 조회를 금한다"},
    {"area": "리스크 평가", "engine": ["dscr_schedule", "site_permit_checklist"],
     "covers": "상환능력·인허가 결손(하자·기후는 D17·D1)"},
]

# 설계값 ↔ 실측 대조 항목 (185차) — 기획서 §5.3 성능보증의 **기술적 전제**
#   🔴 편차를 재는 **엔진 함수가 있는 항목만** 잰다. 없는 항목은 **없다고 적는다**.
PERF_ITEMS = [
    {"item": "난방부하", "fn": "verify_heating_vs_actual", "slot": "actual_load_per_m2"},
    {"item": "공사비", "fn": "benchmark_check", "slot": None},
    {"item": "수확량", "fn": None, "slot": "actual_yield_kg"},
    {"item": "에너지효율", "fn": None, "slot": "actual_energy"},
    {"item": "가동률", "fn": None, "slot": "actual_uptime_pct"},
]

_LINKED = {
    "D8": "SmartFarm_통합보고서_{case_id}.html",
    "D11": "SmartFarm_근거대장.html",
}
_D12_DOCS = [
    "근거_결정대기대장_20260915.md",
    "서비스설계_컨설팅_3대상x6단계_20260920.md",
    "서비스설계_3x6_비판적검토_20260920.md",
    "검증절차_레드팀.md",
]


def _need(*keys) -> list:
    """주입 슬롯 이름 → 사람이 읽는 설명."""
    out = []
    for k in keys:
        out.append({"slot": k, "why": INJECTION_SLOTS[k]})
    return out


def _item(spec: dict, status: str, data=None, needs=None, note: str = "") -> dict:
    return {"code": spec["code"], "title": spec["title"], "stage": spec["stage"],
            "targets": list(spec["targets"]), "engine": list(spec["engine"]),
            "status": status, "data": data, "needs": list(needs or []), "note": note}


# ★사용자 결정 2026-09-22(194차) — **판정은 본문에서 뺀다.**
#   189차 점검 4위: 등급·보상액이 **공유 산출물 본문**에 실리면 분쟁 시 증거로
#   읽힐 수 있다. 190차가 *「해도 되는가」*를, 191차가 *「엔진 안에 둔다」*를
#   정했고, 남은 *「어디까지 내보내는가」*를 이 결정이 정한다 —
#   **대조 자료(본문)와 규칙 적용 결과(부록)를 물리적으로 가른다.**
#   🔴 지우는 것이 아니다. 부록은 그대로 나오고, 떼어 보내거나 빼고 보낼 수 있다.
# ─────────────────────────────────────────────────────────────
# 211차 — **기능 축**(벤치마킹 3기능). 사용자 지시로 신설했다.
#   출처: `Farmingdesign 벤치마킹`(2026-09-02) 머리말의 Function 1~3 정의 —
#     F1 기본디자인 「부지·작목·예산 → 배치·단면·내재해형 규격 매핑」
#     F2 시방서 작성 「내재해형 시방 + KCS 형식 + ICT 기자재 표준 사양」
#     F3 수의계약 발주 「2인 이상 견적 → 한도 판정 → 계약·하자보증·나라장터」
#   🔴 **이것은 판정이 아니라 분류다** — 산출물을 「고객이 무엇을 사는가」로 묶어
#      메뉴를 만든다. 값·등급·순위를 만들지 않고, 어떤 산출물도 더 낫다고 하지
#      않는다. 밴드(Basic/Standard/Premium)와 요율(1.5~3% 등)은 **판단성·시세성**
#      이라 **가져오지 않았다**(1절 불변 원칙).
#   🔴 **기능과 단계는 1:1이 아니다(211차 실측)**: 리포가 이미 쥔 축은 `stage`
#      6단계인데 F2 시방은 D2(①공종설계)·D19(②품질설계)·D20(⑥사후관리)에
#      **흩어져 있다**. 그래서 기능은 **D코드마다 직접** 적는다 — 단계에서
#      유도하면 틀린다.
#   ⚠️ 이 배정은 **★사용자 확인 대상**이다(분류는 판단이다). 바꾸려면 아래 표만
#      고치면 되고, 가드가 **27건 전부 배정됐는지**와 **코드 집합이 같은지**를 잰다.
# ─────────────────────────────────────────────────────────────
BENCHMARK_FUNCTIONS = (
    ("F1", "기본디자인", "부지·작목·예산 → 배치·단면·내재해형 규격 매핑"),
    ("F2", "시방·사양", "내재해형 시방 + 기자재 표준 사양"),
    ("F3", "발주·계약", "견적 → 계약 → 준공 → 하자"),
    ("F0", "공통·근거", "4축 계산·재무·근거대장·판정 부록 — 세 기능에 걸친다"),
)

FUNCTION_OF_CODE = {
    "D1": ("F1", "부지 자료를 읽어 설계하중·외기온을 낸다 — 기본디자인의 입력"),
    "D3": ("F1", "배치·규격 대안을 나란히 둔다 — 「배치·단면」에 해당"),
    "D6": ("F1", "개략 내역(원가 분해) — 벤치마킹 Band 1의 「개략 내역」"),
    "D18": ("F1", "인허가 체크리스트 — 기본디자인 단계에서 걸리는 것"),
    "D21": ("F1", "작목 적합·수량 — 「작목」 입력의 판독"),
    "D2": ("F2", "RFQ 사양서 — 「시방서 작성」의 본체"),
    "D4": ("F2", "도면·시방·내역이 서로 맞는지 — 시방 정합"),
    "D7": ("F2", "품셈 인력 산출 — 물량내역(BoQ)의 노무 쪽"),
    "D19": ("F2", "기자재 대조표 — 「ICT 기자재 표준 사양」에 해당"),
    "D20": ("F2", "내용연수 대조 — 기자재 사양의 수명 근거"),
    "D5": ("F3", "견적 정합·업체 비교 — 「2인 이상 견적」의 비교 쪽"),
    "D10": ("F3", "LCC·하자 관리표 — 「하자보증」의 기간 근거"),
    "D13": ("F3", "검측 체크리스트 — 계약 이행 확인"),
    "D14": ("F3", "시운전 계획 — 인수 조건"),
    "D15": ("F3", "준공 서류철 — 계약 종결 서류"),
    "D16": ("F3", "점검 일정표 — 하자 기간 중 관리"),
    "D17": ("F3", "하자 추적표 — 「하자보증」의 실행"),
    "D27": ("F3", "기성 확인서 — 청구 승인(벤치마킹 Larssen 「청구승인 독립」)"),
    "D8": ("F0", "4축 통합 리포트 — 세 기능의 계산 결과가 모인다"),
    "D9": ("F0", "재무 시나리오 — 기능이 아니라 의사결정 축"),
    "D11": ("F0", "근거대장 — 모든 기능의 출처"),
    "D12": ("F0", "결정 지원 — ★결정 지점 모음"),
    "D22": ("F0", "컨설팅 대가 산출 — 서비스 자체의 값(기능 산출물이 아니다)"),
    "D23": ("F0", "투자 실사 카드 — 6영역 횡단"),
    "D24": ("F0", "설계값–실측 대조 — 세 기능의 사후 검증"),
    "D25": ("F0", "K-SFID 등급 — 판정 부록(본문과 분리, ★194차)"),
    "D26": ("F0", "성능보증 판정 — 판정 부록"),
}

# 🔴 벤치마킹이 **이름을 대지만 리포에 없는 것**. 세어서 남긴다 —
#    없는 것을 메뉴에 있는 척 올리지 않는다(209차 계약). 엔진 원문 실측(211차):
#    「수의계약」0 · 「나라장터」0 · 「지방계약」0 · 「하자이행보증」0 · 「KCS」0 ·
#    「적격」0 · 「공급사」0회.
# 🔴 212차 — 사용자 지시로 **외부 자료를 수집**해 각 공백에 「어디를 보면 있나」를
#    달았다. 수집 결과·원문 인용·이견 3건은 `근거_외부수집_기능공백_20260924.md`.
#    📌 **여기에 값을 적지 않는다** — 수치는 근거 문서에만 있고, 엔진·레지스트리
#       등재는 **★사용자 결정**이다(1절: 원문 확보·대조를 거쳐서만).
#    📌 수집 대상에 **시세성(단가·노임·유가·금리)은 하나도 없었다** — 전부 법정·
#       표준·절차 정보다.
#    ⚠️ `blocked`는 **무엇이 막고 있나**다. 원문이 손에 있어도 ★가 남으면 막힌 것이다.
GAP_EVIDENCE_DOC = "근거_외부수집_기능공백_20260924.md"

FUNCTION_GAPS = (
    {"fn": "F2", "name": "KCS 형식 시방",
     "why": "엔진 원문에 「KCS」 0회 — 형식 변환이 없다",
     "found": "1차", "where": "국가건설기준센터(kcsc.re.kr) — 설계 KDS·시방 KCS 6자리 코드체계",
     "blocked": "없음 — 형식 체계라 값 등재가 아니다(만들기로 하면 만들 수 있다)"},
    {"fn": "F2", "name": "ICT 기자재 KS/SPS/TTAS 사양",
     "why": "표준 번호 체계를 엔진이 모른다(D19는 대조만 한다)",
     # 🔴270차 — 목록을 열었다. 막힌 이유가 바뀐다: 「목록을 못 구했다」가 아니라
     #    「목록은 구했고 **등재만 남았다**」. 사업 사이트는 **여전히 403**이고,
     #    우회로는 농진원(KOAT) 「스마트농업 정보」 게시판 7쪽 전수였다.
     #    ⚠️ 여기 수를 적지 않는다 — 건수·목록은 근거 문서에만 둔다(212차 계약).
     "found": "1차", "where": ("농진원(KOAT) 스마트농업 정보 게시판 전수 — 근거 문서 §7에 표준 전수표. "
                              "1차 조문은 농식품부 보도자료(2021-03-03): 시설원예 KS X 3265∼3269 · 축산 KS X 3279"),
     "blocked": ("★ 표준번호 등재 — 목록은 확보했다. 🔴285차에 본문 6건을 열어 보니 **엔진에 넣을 「값」이 없다**. "
                 "이 표준들은 기자재의 기계·전기 연결과 통신 데이터 규격이고, 엔진의 네 축(입지·설계·"
                 "운영·경제성) 낱말이 6건 전문에서 **0회**다. 넣을 수 있는 것은 번호·제목·제개정일 같은 "
                 "**참조 메타데이터**뿐이라 남은 ★는 「어떤 값을 넣을까」가 아니라 "
                 "**「참조 카탈로그에 어떻게 올릴까」**다. "
                 "⚠️KS X 3268·3269는 283차에 **실재를 확인했다**(국립전파연구원 방송통신표준자료실 — "
                 "구동기·센서 메타데이터, 제개정일 2022-01-11, 상태 「유지」). KOAT 게시판에 없던 것은 "
                 "게시판 사정이었다. 다만 **e나라 표준인증에는 이 계열 여섯 번호가 전부 0건**이라 "
                 "그 까닭은 **이견으로 남긴다** — 어느 쪽도 등재 근거로 쓰지 않는다")},
    {"fn": "F3", "name": "나라장터 등록 **대행**",
     "why": ("🔴213차에 **의무 여부 판정은 열렸다**(`procurement_route`) — 금액이 "
             "임계를 넘으면 나라장터·조달청 위탁·지자체 위탁 중 하나를 거쳐야 한다고 "
             "낸다. 남은 것은 **실제 등록을 대신해 주는 일**이고, 그것은 계정·서식·"
             "제출이라 엔진 밖이다"),
     "found": "1차", "where": "재정사업관리 기본규정 제57조제2항 — 등재 완료(`SUBSIDY_PROCUREMENT_THRESHOLDS`)",
     "blocked": "★ 대행을 서비스 범위에 넣을 것인가 · 규정 **원문 자체**는 아직 인용본만 확보"},
    {"fn": "F3", "name": "적격 공급사 풀",
     "why": "업체 **선정**은 1절이 금한 판단성이다 — 풀 자체가 없다",
     "found": "2차", "where": "농진원 표준적합 검정·성능시험(ICT 검인증 센터) 제도가 있다",
     "blocked": "★ **경계가 먼저다** — 업체 목록은 수집하지 않았다(선정에 닿는다)"},
    {"fn": "F3", "name": "견적 **자동 수집**",
     "why": ("🔴213차에 **개수·지역 요건 판정은 열렸다**(`quote_count_requirement`). "
             "남은 것은 업체에 **실제로 요청해 받아 오는 일**이고, 그것은 업체 접촉이라 "
             "**선정에 닿는다** — 1절이 금한 판단성이다"),
     "found": "1차", "where": "시행지침서 p176 — 등재 완료(`QUOTE_COUNT_RULE`)",
     "blocked": "★ 업체 접촉을 서비스 범위에 넣을 것인가(넣으면 선정 경계를 먼저 정해야 한다)"},
)


def function_index() -> dict:
    """기능 축으로 본 산출물 지도(결정론 · 판정 없음 · 순위 없음)."""
    by = {f: [] for f, _n, _d in BENCHMARK_FUNCTIONS}
    for spec in PACKAGE_SPEC:
        fn, why = FUNCTION_OF_CODE[spec["code"]]
        by[fn].append({"code": spec["code"], "title": spec.get("title", ""),
                       "stage": spec.get("stage", ""), "why": why,
                       "engine": list(spec.get("engine") or [])})
    gaps = {f: [] for f, _n, _d in BENCHMARK_FUNCTIONS}
    for g in FUNCTION_GAPS:
        gaps[g["fn"]].append(dict(g))
    # ⚠️ 키를 `items`로 두면 Jinja가 **dict 메서드 `items()`**를 먼저 잡는다
    #    (211차에 실제로 `TypeError`가 났다) → `docs`로 둔다.
    rows = [{"fn": f, "name": n, "desc": d, "docs": by[f], "gaps": gaps[f]}
            for f, n, d in BENCHMARK_FUNCTIONS]
    return {"rows": rows,
            "counts": {r["fn"]: len(r["docs"]) for r in rows},
            "total": sum(len(r["docs"]) for r in rows),
            "gap_count": len(FUNCTION_GAPS),
            "gap_doc": GAP_EVIDENCE_DOC,
            "source": ("Farmingdesign 벤치마킹(2026-09-02) 머리말 Function 1~3 — "
                       "밴드·요율은 판단성·시세성이라 가져오지 않았다. ⚠️원본은 237차 탐색"
                       "(리포 grep · Drive 제목 검색 · Notion 검색 · 로컬 파일명 검색)에서 "
                       "회수되지 않았다 — 이 정의는 211차 전사만 남아 있다(238차 병기)"),
            "note": ("🔴분류이지 판정이 아니다 — 순위·등급·추천을 만들지 않는다. "
                     "기능과 stage 6단계는 1:1이 아니라 교차한다"
                     "(F2 시방이 ①·②·⑥에 흩어져 있다)")}


# ─────────────────────────────────────────────────────────────
# 275차 — **축 대응표**(WO-011). 273차 점검이 센 것: 축이 넷인데 이어 주는 화면이 없다.
#   🔴 **새 축을 만들지 않는다.** 네 축 상수를 읽어 **펴기만** 한다 —
#      단계(`STAGE_ORDER`) · 플랫폼(`PLATFORM_STAGES`) · 기능(`FUNCTION_OF_CODE`) ·
#      기입(`ENTRY_STEPS`). 값·순위·추천을 만들지 않는다(211·223차와 같은 경계).
#   🔴 **기입 축만 산출물 대응이 없었다.** `entry_steps()`가 코드 이름을 대는 것은
#      **D25 하나**뿐이고(가드가 그 함수 원문에서 다시 센다), 나머지는 케이스 파일·주입
#      슬롯·provenance를 본다 — 그래서 세 단계는 **산출물 대응이 없다**고 적는다.
#      없는 대응을 만들어 채우면 그 순간 **다섯 번째 축**이 된다.
# ─────────────────────────────────────────────────────────────
ENTRY_STEP_OF_CODE: dict = {"D25": ("rules", "issue", "renew")}
ENTRY_STEP_ALL_CODES: tuple = ("engine",)        # 산출물 전체가 함께 걸리는 단계
ENTRY_STEP_NO_CODE: tuple = ("case", "docs", "evidence")   # 산출물 대응이 없는 단계
AXIS_NONE: str = "대응 없음"


def axis_map() -> dict:
    """산출물 코드 ↔ 네 축(단계·플랫폼·기능·기입). 분류뿐 — 계산·판정 없음.

    반환의 모든 이름은 **상수에서 온 그대로**다. 이 함수는 이름을 짓지 않는다.
    """
    fn_name = {f: n for f, n, _d in BENCHMARK_FUNCTIONS}
    entry_name = {k: n for k, n, _w, _j in ENTRY_STEPS}
    platform_of_stage = {}
    for key, name, stages, _desc, _bench in PLATFORM_STAGES:
        for st in stages:
            platform_of_stage[st] = (key, name)

    rows = []
    for spec in PACKAGE_SPEC:
        code = spec["code"]
        stage = spec.get("stage", "")
        fn, why = FUNCTION_OF_CODE[code]
        pk, pn = platform_of_stage.get(stage, (None, None))
        steps = tuple(ENTRY_STEP_ALL_CODES) + tuple(ENTRY_STEP_OF_CODE.get(code, ()))
        rows.append({
            "code": code,
            "title": spec.get("title", ""),
            "stage": stage or AXIS_NONE,
            "platform": AXIS_NONE if pk is None else f"{pk} {pn}",
            "function": f"{fn} {fn_name[fn]}",
            "why": why,
            "entry": [entry_name[k] for k in steps] or [AXIS_NONE],
            "appendix": code in JUDGMENT_CODES,
        })

    # 역방향 — 기입 단계에서 본 산출물(대응이 없는 칸을 숨기지 않는다)
    by_step = []
    for k, n, who, jas in ENTRY_STEPS:
        if k in ENTRY_STEP_ALL_CODES:
            codes, note = [r["code"] for r in rows], "산출물 전체"
        elif k in ENTRY_STEP_NO_CODE:
            codes, note = [], AXIS_NONE
        else:
            codes = sorted(c for c, ks in ENTRY_STEP_OF_CODE.items() if k in ks)
            note = "" if codes else AXIS_NONE
        by_step.append({"key": k, "name": n, "who": who, "jas": jas,
                        "codes": codes, "note": note})

    return {"rows": rows, "by_step": by_step,
            "axes": [("단계", "STAGE_ORDER", len(STAGE_ORDER)),
                     ("플랫폼", "PLATFORM_STAGES", len(PLATFORM_STAGES)),
                     ("기능", "BENCHMARK_FUNCTIONS", len(BENCHMARK_FUNCTIONS)),
                     ("기입", "ENTRY_STEPS", len(ENTRY_STEPS))],
            "total": len(rows),
            "note": ("🔴분류이지 판정이 아니다 — 어떤 축도 더 낫다고 하지 않는다. "
                     "네 축은 각 상수에서 읽어 펴기만 했고 이 표가 이름을 짓지 않는다. "
                     "기입 축의 세 단계(케이스 생성·문서 제출·근거 대조)는 **산출물 대응이 "
                     "없다** — 없는 대응을 만들지 않는다")}

# ─────────────────────────────────────────────────────────────
# 276차 — **참조 전수 카탈로그**(WO-012). 273차 점검 3절: 참조 메뉴 링크 7개 중
#   설명이 2개고, 리포가 쥔 자료(근거 문서·법령·고시·생성 산출물)가 콘솔에서 안 닿았다.
#   🔴 **세어서 낸다.** 건수는 파일 목록에서 만들고, 문서에 적힌 수를 믿지 않는다.
#   🔴 **설명을 지어내지 않는다.** 근거 문서의 한 줄은 `근거지도_20260923.md`가 적은 것,
#      원문 파일의 한 줄은 레지스트리 `source_refs`의 `note`를 옮긴 것이다.
#      어느 쪽에도 없으면 **「설명 없음(등재 필요)」**이라 적는다.
#   🔴 **status를 새로 매기지 않는다** — 레지스트리 값을 옮긴다.
#   ⚠️ 개인 이름은 이 계층이 가리지 않는다 — **표시 계층(webapp)이 scrub**한다(183·184차).
# ─────────────────────────────────────────────────────────────
REFS_NO_DESC: str = "설명 없음(등재 필요)"
REFS_NOT_IN_REPO: str = "리포에 없음"
REFS_NOT_IN_MAP: str = "지도 미등재"
_REFS_MAP_DOC: str = "근거지도_20260923.md"


def _refs_read(path) -> str:
    import io as _io
    return _io.open(path, encoding="utf-8").read()


def _refs_map_rows(root) -> dict:
    """`근거지도`의 표를 {파일명: (한 줄, 묶인 상수)}로 읽는다(지도가 원본이다)."""
    import os as _os
    import re as _re
    try:
        txt = _refs_read(_os.path.join(root, _REFS_MAP_DOC))
    except OSError:
        return {}
    out = {}
    for ln in txt.splitlines():
        m = _re.match(r"^\|\s*`([^`]+\.md)`\s*\|([^|]*)\|([^|]*)\|", ln)
        if m:
            consts = [c.strip(" `") for c in m.group(3).split("·") if c.strip(" `—")]
            out[m.group(1)] = (m.group(2).strip(), consts)
    return out


def refs_catalog() -> dict:
    """참조 자료 전수 — 갈래별 목록·건수. 세기만 한다(판정·계산 없음)."""
    import glob as _glob
    import json as _json
    import os as _os
    root = _os.path.dirname(_os.path.abspath(__file__))
    j = lambda *a: _os.path.join(root, *a)
    names = lambda pat: sorted(_os.path.basename(p) for p in _glob.glob(j(pat)))

    reg = _json.loads(_refs_read(j("엔진데이터_레지스트리.json")))["constants"]
    #   status는 **레지스트리 값을 옮긴다** — 새로 매기지 않는다
    status_of = {k: (v.get("status") or "") for k, v in reg.items()}
    ref_note, ref_by = {}, {}
    for cname, v in reg.items():
        for r in (v.get("source_refs") or []):
            f = r.get("file")
            if not f:
                continue
            ref_by.setdefault(f, []).append(cname)
            if f not in ref_note and r.get("note"):
                ref_note[f] = r["note"]

    # ① 근거 문서 — 지도가 한 줄과 상수를 쥔다
    mapped = _refs_map_rows(root)
    docs = []
    for n in names("근거_*.md"):
        desc, consts = mapped.get(n, (None, []))
        docs.append({"name": n, "desc": desc or REFS_NO_DESC,
                     "extra": "" if n in mapped else REFS_NOT_IN_MAP,
                     "consts": consts, "in_repo": True, "href": None,
                     "statuses": sorted({status_of[c] for c in consts
                                         if c in status_of and status_of[c]})})

    # ② 원문 파일 — 레지스트리가 지목한 것 + 법령·고시. 없으면 없다고 적는다
    cited = {f for f in ref_by if not f.endswith(".md")}
    for pat in ("법령_*.pdf", "고시_*.pdf"):
        cited |= set(names(pat))
    originals = []
    for f in sorted(cited):
        exists = _os.path.exists(j(f))
        cs_ = sorted(set(ref_by.get(f) or []))
        originals.append({"name": f, "desc": ref_note.get(f) or REFS_NO_DESC,
                          "extra": "" if exists else REFS_NOT_IN_REPO,
                          "consts": cs_, "in_repo": exists, "href": None,
                          "statuses": sorted({status_of[c] for c in cs_
                                              if c in status_of and status_of[c]})})

    # ③ 생성 산출물 — 콘솔이 /pages 로 연다
    outputs = [{"name": n, "desc": "build_site.py가 만든 산출물", "extra": "",
                "consts": [], "in_repo": True, "href": "/pages/" + n, "statuses": []}
               for n in names("SmartFarm_*.html") + names("index.html")]

    # ④ 작업지시서
    wos = [{"name": n, "desc": "작업지시서(WO) — 과제 1건의 지시·수용기준", "extra": "",
            "consts": [], "in_repo": True, "href": "/workorders", "statuses": []}
           for n in sorted(_os.path.basename(p)
                           for p in _glob.glob(j("docs", "work-orders", "WO-*.md")))]

    groups = [
        {"key": "docs", "name": "근거 문서", "why": "개별 수치·결정이 어디서 왔는지 적은 조사 기록",
         "source": _REFS_MAP_DOC, "items": docs},
        {"key": "originals", "name": "원문 파일", "why": "레지스트리가 지목한 원문 + 법령·고시",
         "source": "엔진데이터_레지스트리.json (source_refs)", "items": originals},
        {"key": "outputs", "name": "생성 산출물", "why": "엔진이 낸 보고서·비교표",
         "source": "build_site.py", "items": outputs},
        {"key": "wos", "name": "작업지시서", "why": "과제별 지시서와 수용기준",
         "source": "docs/work-orders/", "items": wos},
    ]
    for g in groups:
        g["count"] = len(g["items"])
        g["missing"] = sum(1 for x in g["items"] if not x["in_repo"])
        g["no_desc"] = sum(1 for x in g["items"] if x["desc"] == REFS_NO_DESC)
    return {"groups": groups,
            "total": sum(g["count"] for g in groups),
            "missing": sum(g["missing"] for g in groups),
            "not_in_map": sum(1 for x in docs if x["extra"] == REFS_NOT_IN_MAP),
            "note": ("🔴건수는 **파일 목록에서 세었다** — 문서에 적힌 수를 옮기지 않았다. "
                     "설명은 `근거지도`와 레지스트리 `source_refs`가 적은 것을 그대로 옮기고, "
                     "어느 쪽에도 없으면 **「설명 없음(등재 필요)」**이라 적는다 — 지어내지 않는다. "
                     "열 수 없는 원문은 **「리포에 없음」**으로 드러낸다")}

# ─────────────────────────────────────────────────────────────
# 277차 — **사용자 매뉴얼 · FAQ · Q&A**(WO-013). 273차 점검 4절: 화면별 설명이
#   드롭다운 툴팁 한 줄뿐이고 FAQ·Q&A가 없었다.
#   🔴 **기입 7단계(`ENTRY_STEPS`)는 그대로 둔다** — 그것은 매뉴얼이 아니라 JAS 준거
#      **상태기계**다. 매뉴얼로 바꾸면 「어디까지 했는가」를 잃는다. 매뉴얼은 **옆에** 둔다.
#   🔴 **답은 리포 안 출처가 있는 것만** 적는다. 없으면 **「확인 필요」**가 정답이다.
#   🔴 **수치를 새로 적지 않는다** — 화면이 내는 값을 가리키기만 한다.
#   ⚠️ 라우트가 늘면 가드가 **빠진 화면**을 드러낸다(아래 두 목록의 합 = GET 라우트).
# ─────────────────────────────────────────────────────────────
GUIDE_SCREENS: tuple = (
    ("/", "홈", "케이스 목록과 일하는 방식·서비스·근거 현황을 한 화면에",
     "넣는 것 없음(읽기)", "케이스 카드 · 숫자 띠 · 플랫폼 3단계 · 기능 4갈래 · status 분포",
     "케이스가 없으면 카드가 비어 있다 — `cases/*.json`이 원본이다"),
    ("/flow", "서비스 흐름", "척추인 6단계에 산출물·대상·기능을 잇는다(설계서 3대상 × 6단계)",
     "넣는 것 없음(읽기)", "단계 레일 6 · 3대상 × 6단계 매트릭스 · 렌즈 4 · 아직 못 이은 것",
     "칸의 수는 **산출물 건수**다 — 한 산출물이 여러 대상에 걸리면 여러 번 센다. 화면이 어느 단계인지는 **정의돼 있지 않다**"),
    ("/functions", "기능 지도", "산출물 27종을 벤치마킹 기능 축으로 묶어 본다",
     "넣는 것 없음(읽기)", "F1·F2·F3·F0별 산출물과 **아직 없는 것**",
     "「없는 것」은 자료가 없는 게 아니라 **★등재가 안 된 것**일 수 있다 — 각 항목의 `blocked`를 보라"),
    ("/axes", "축 대응표", "같은 산출물을 부르는 네 이름(단계·플랫폼·기능·기입)을 한 줄에",
     "넣는 것 없음(읽기)", "산출물 27행 × 네 축 · 기입 절차에서 본 역방향",
     "기입 칸이 「대응 없음」이면 그 단계는 **산출물이 아니라 사람이 하는 일**이다"),
    ("/refs", "참조 카탈로그", "리포가 쥔 참조 자료 전수를 갈래별로",
     "넣는 것 없음(읽기)", "근거 문서·원문 파일·생성 산출물·작업지시서와 각각의 출처·status",
     "「설명 없음(등재 필요)」은 그 자료를 **아무 상수도 가리키지 않는다**는 뜻이다"),
    ("/case/{display_code}", "케이스 상세", "케이스 1건의 산출물과 기입 경로를 모아 본다",
     "케이스 코드(C1~C5)", "통합보고서 · 컨설팅 패키지 · 판정 부록 · 4축 리포트 링크와 기입 상태",
     "부분 케이스는 4축이 없어 **부분 케이스 페이지 하나**만 나온다"),
    ("/entry", "기입 허브", "케이스별 기입 절차 7단계가 어디까지 왔는지",
     "넣는 것 없음(읽기)", "케이스별 7단계 상태(완료·진행·대기·경로 없음)와 폼 링크",
     "「경로 없음」은 **콘솔 밖 절차**라는 뜻이다(예: 근거 대조는 원문을 사람이 본다)"),
    ("/entry/newcase", "새 케이스", "케이스 파일을 새로 만든다",
     "케이스 기본 입력(작목·지역·면적·피복 등)", "미리보기 후 `cases/*.json` 저장",
     "값이 규칙에 어긋나면 **거부되고 기입한 값은 화면에 그대로 남는다**(209차)"),
    ("/entry/site/{display_code}", "입지 조건 기입", "동절기 개월 등 입지 조건을 케이스에 넣는다",
     "케이스 코드 + 입지 조건", "미리보기 후 케이스에 저장",
     "기상 지점이 안 잡히면 값이 비는데, 그건 **지역명이 관측지점과 안 맞는 것**이다"),
    ("/entry/financing/{display_code}", "financing 기입", "대출 원금·금리 등 실조건을 넣는다",
     "케이스 코드 + 융자 조건", "미리보기 후 케이스에 저장",
     "금리는 **시세성**이라 엔진이 만들지 않는다 — 넣지 않으면 기본값 표기가 나간다"),
    ("/entry/scenario/{display_code}", "시나리오 기입", "가정값 세트(Best/Worst 등)를 넣는다",
     "케이스 코드 + 가정값 세트", "미리보기 후 케이스에 저장",
     "세트가 0개면 시나리오 표가 안 나온다 — 가정값 채택은 **컨설턴트 판단**이다"),
    ("/entry/docs/{display_code}", "문서 제출", "설계도서·기자재 목록 등 문서 슬롯을 채운다",
     "케이스 코드 + 문서 행", "미리보기 후 케이스에 저장",
     "미제출 슬롯이 남으면 기입 허브의 「문서 제출」이 **대기**로 남는다"),
    ("/entry/issue/{display_code}", "발급 기입", "식별번호 일련번호·발급일을 넣는다",
     "케이스 코드 + 일련번호·발급일", "미리보기 후 케이스에 저장",
     "둘 중 하나만 있으면 번호가 서지 않는다 — **형식은 엔진이 쥔다**"),
    ("/entry/quotes", "견적 허브", "견적비교 파일 목록을 본다",
     "넣는 것 없음(읽기)", "견적비교 JSON 목록과 편집 링크",
     "파일이 없으면 비어 있다 — 견적 금액은 **시세성이라 주입 전용**이다"),
    ("/entry/quotes/edit", "견적 편집", "견적비교 항목을 고친다",
     "견적 파일 + 항목", "미리보기 후 견적비교 JSON 저장",
     "합계가 안 맞으면 거부된다 — 앱이 값을 고쳐 주지 않는다"),
    ("/workorders", "작업지시서", "과제별 지시서와 수용기준 진행을 본다",
     "넣는 것 없음(읽기)", "WO 색인(번호·작업명·차수·선행·상태)과 형식 검사 결과",
     "수용기준 체크는 **파일이 원본**이다 — 화면에서 바꾸지 않는다"),
    ("/workorders/{wo_id}", "작업지시서 상세", "WO 1건의 9절을 절별로 읽는다",
     "WO 번호", "9절 본문과 수용기준 체크 상태",
     "없는 번호는 404다 — 색인에 있는 번호만 연다"),
    ("/design", "기본설계", "주소·품목·면적만 받아 구조 기본설계까지 낸다",
     "주소(시·군·구 포함) · 품목 · 면적(㎡) — **케이스 파일이 필요 없다**",
     "재해 조건 · 조건을 통과하는 규격과 형식별 최소사양 · 개산 · 인허가 · **낼 수 없는 것**",
     "기상값이 비면 그 지역이 관측지점에 안 닿는 것이고, 개산이 비면 평단가 미등재다 — 둘 다 화면이 말한다"),
    ("/for", "관점별 입구", "같은 산출물을 보는 사람의 질문으로 묶어 본다",
     "넣는 것 없음(읽기)", "농업인·투자자·공공기관별 묶음과 이유 · 어느 관점에도 없는 산출물",
     "관점은 **입구이지 판정이 아니다** — 무엇을 고르라고 말하지 않는다"),
    ("/for/{name}", "관점 하나", "관점 하나만 펼쳐 본다",
     "관점 이름(농업인·투자자·공공기관)", "그 관점의 산출물 묶음 · 공공기관은 지침 가·감점 대조표",
     "없는 이름은 404다 — 관점은 `PERSPECTIVES` 한 곳에 있다"),
    ("/guide", "사용 안내", "이 문서 — 화면별 설명과 FAQ·Q&A",
     "넣는 것 없음(읽기)", "화면 목록 · 자주 막히는 자리 · 답할 수 있는 것과 확인 필요한 것",
     "여기에 없는 화면이 있으면 **가드가 실패한다**(라우트와 대조한다)"),
)

GUIDE_NOT_SCREENS: tuple = (
    ("/health", "화면이 아니다 — 서버가 살아 있는지 보는 점검 경로"),
    ("/openapi.json", "화면이 아니다 — FastAPI가 자동으로 내는 스키마"),
    ("/pages/{name}", "화면이 아니다 — 생성 산출물 파일을 그대로 낸다. 설명은 참조 카탈로그가 쥔다"),
)

# FAQ — 자주 막히는 자리. 답마다 **리포 안 출처**를 단다.
GUIDE_FAQ: tuple = (
    ("산출물에 「미주입」이라고 나온다 — 내가 채워야 하나?",
     "사업에 따라 다르다. 견적 개수 요건의 `기준사업비`는 **온실신축 사업에 아예 없다** — "
     "그래서 「미주입」이 **정확한 상태**다. 다른 사업(인삼 등)을 케이스로 받으면 그때 주입한다.",
     "consulting_package.py D5 · 근거_외부수집_기능공백_20260924.md 6-b"),
    ("「주입 대기」는 무엇인가?",
     "엔진이 **만들지 않기로 한 값**을 기다리는 자리다. 단가·노임·금리 같은 **시세성**과 "
     "규격·업체 선택 같은 **판단성**은 엔진이 고르지 않는다 — 사람이 넣는다.",
     "작업지시서.md 1절 · consulting_package.INJECTION_SLOTS"),
    ("status 칩(실측·추정·확인요망·미검증·결정·법정기준·공공기준)은 무슨 뜻인가?",
     "**근거의 상태**다. 값이 맞다/틀리다가 아니라 *「어디까지 확인됐나」*를 적는다. "
     "`추정`·`확인요망`이 `실측`으로 올라가는 길은 **원문 대조 하나**뿐이다.",
     "엔진데이터_레지스트리.json status · 참조 카탈로그(/refs)"),
    ("케이스가 C1·C2로 나온다 — 실명은 어디에 있나?",
     "표시 계층이 **코드로 바꾼다**. 실명은 `case_display.py`에만 있고 화면·문서·커밋에는 "
     "나가지 않는다. 지우는 게 아니라 **바꾸는 것**이라 문장이 깨지지 않는다.",
     "case_display.py · 183·184차"),
    ("기입 7단계는 어디서 온 것인가? 매뉴얼인가?",
     "**매뉴얼이 아니라 진행 상태**다. JAS 인증 절차를 준거로 만든 상태기계이고, "
     "각 단계에 완료·진행·대기·**경로 없음**이 붙는다. 이 안내 문서가 그것을 대신하지 않는다.",
     "consulting_package.ENTRY_STEPS · 근거_콘솔점검_20260929.md 4절"),
    ("어떤 화면도 「이게 좋다」고 말하지 않는다 — 왜인가?",
     "작목·부지·업체 **선정과 최종판정은 사람 몫**이라고 1절이 못 박았다. 엔진은 대조 자료와 "
     "규칙 적용 결과를 내고, 고르는 일은 하지 않는다.",
     "작업지시서.md 1절"),
    ("입지 진단에서 기상값이 비어 있다.",
     "설계하중은 **행정구역 172개**, 기상 4표는 **관측지점 69개**로 체계가 다르다. "
     "닿지 않는 지역은 **잇지 않고 주입**받기로 정했고, 괄호 안이 광역이면 "
     "**애매해서 일부러 주지 않는다**.",
     "근거_지역정규화_기상지점_20260929.md · smartfarm_engine.WEATHER_MATCH_RULE"),
    ("값을 넣었는데 거부됐다 — 입력이 날아갔나?",
     "아니다. **기입한 값은 화면에 그대로 남는다.** 거부 문구도 검증한 쪽이 낸 말 그대로이고 "
     "앱이 고쳐 말하지 않는다.",
     "webapp.py 오류 처리 · 209차"),
)

# Q&A — **답할 수 있는 것**과 **확인 필요한 것**을 가른다.
GUIDE_QA: tuple = (
    ("온실신축 사업의 지원 비율은?",
     "2026년 사업시행지침이 **국비 보조 20% · 지방비 보조 30% · 융자 30% 이내 · 자부담 20%**라 적는다.",
     "근거_외부수집_기능공백_20260924.md 6-b (2026년 사업시행지침 원문)", True),
    ("비닐온실 설계는 어느 고시를 따르나?",
     "**농식품부 고시 제2022-104호**의 내재해형 시설규격 설계도를 적용한다 — "
     "2025·2026년 지침 본문이 같은 고시를 가리킨다.",
     "근거_지역정규화_기상지점_20260929.md · 근거_외부수집_기능공백_20260924.md 6-c", True),
    ("우리 산출물을 내면 공모에서 가점을 받나?",
     "**확인 필요.** 2026년 지침 가점 항목에 *「설계도서(도면·내역서·시방서·구조계산서·부하계산서)가 "
     "준비된 경우」*가 있고 그것이 우리 산출물과 이름이 겹치지만, **가점을 주는 것은 심사 주체**다 — "
     "리포는 대응 이름까지만 적고 판정하지 않는다.",
     "근거_외부수집_기능공백_20260924.md 6-d", False),
    ("컨설팅 대가는 얼마인가?",
     "**확인 필요.** 대가는 **시세성**이라 엔진이 만들지 않는다. 산출 틀(`consulting_fee_estimate`)은 "
     "있으나 노임·요율은 **주입**받는다.",
     "작업지시서.md 1절 · smartfarm_engine.consulting_fee_estimate", False),
    ("견적을 몇 곳에서 받아야 하나?",
     "**확인 필요 — 사업에 따라 다르다.** 「기준사업비 초과 시 서로 다른 광역자치단체의 2개 업체」는 "
     "**인삼생산시설현대화 사업** 조항이고, **온실신축 지침에는 견적 조항이 없다**.",
     "smartfarm_engine.QUOTE_COUNT_RULE · 근거_외부수집_기능공백_20260924.md", False),
    ("설계·감리비 요율은 어느 기준을 쓰나?",
     "**확인 필요 — 결정 대기(D-17)다.** 엔진은 **건축사대가기준**을 참고로 내는데, 온실신축 지침은 "
     "**엔지니어링산업진흥법·농어촌정비법**을 준용하라 하고 자체 요율표를 싣는다. 어느 쪽을 "
     "조회처로 삼을지는 **정해지지 않았다**.",
     "근거_외부수집_기능공백_20260924.md 6-e · 근거_결정대기대장_20260915.md D-17", False),
)


def guide_index() -> dict:
    """사용 안내 — 화면 목록·FAQ·Q&A. 수치를 만들지 않고 **가리키기만** 한다."""
    screens = [{"path": p, "name": n, "what": w, "input": i, "output": o, "why_empty": e}
               for p, n, w, i, o, e in GUIDE_SCREENS]
    faq = [{"q": q, "a": a, "src": s} for q, a, s in GUIDE_FAQ]
    qa = [{"q": q, "a": a, "src": s, "answered": ok} for q, a, s, ok in GUIDE_QA]
    return {"screens": screens, "not_screens": [{"path": p, "why": w} for p, w in GUIDE_NOT_SCREENS],
            "faq": faq, "qa": qa,
            "counts": {"screens": len(screens), "not_screens": len(GUIDE_NOT_SCREENS),
                       "faq": len(faq), "qa": len(qa),
                       "need_check": sum(1 for x in qa if not x["answered"])},
            "note": ("🔴답은 **리포 안 출처가 있는 것만** 적는다 — 없으면 **「확인 필요」**가 정답이다. "
                     "이 문서는 **수치를 새로 적지 않는다**(화면이 내는 값을 가리키기만 한다). "
                     "⚠️기입 7단계는 매뉴얼이 아니라 **진행 상태**라 그대로 둔다 — 여기가 대신하지 않는다")}

# ─────────────────────────────────────────────────────────────
# 278차 — **관점별 입구**(WO-014). 273차 점검 6절: 메뉴가 만든 쪽의 언어
#   (기능 지도·산출물 코드)로 되어 있어 농업인·투자자·공공기관이 자기 질문으로
#   들어올 입구가 없었다.
#   🔴 **입구이지 판정이 아니다.** 관점은 산출물을 **묶어 보는 창**일 뿐이고
#      *「당신에겐 이것이 맞다」*를 말하지 않는다. 순위·등급·추천을 만들지 않는다.
#   🔴 **배정은 분류다**(211·223·275차와 같은 경계). 바꾸려면 아래 표만 고치면 되고,
#      가드가 **27종이 적어도 한 관점에 들어가는지**와 **어디에도 없는 코드**를 잰다.
#   ⚠️ 이 배정은 **★사용자 확인 대상**이다 — 분류는 판단이기 때문이다.
#   🔴 가점 대조표는 **지침 원문 인용**이다. *「우리 산출물이 가점을 받는다」*고
#      **단정하지 않는다** — 대응 이름까지만 적고 판단은 심사 주체의 몫이다.
# ─────────────────────────────────────────────────────────────
PERSPECTIVES: tuple = (
    ("농업인", "내 땅에 지을 수 있나 · 얼마나 드나 · 지은 뒤 무엇이 드나",
     ("D1", "D2", "D3", "D6", "D10", "D16", "D18", "D20", "D21")),
    ("투자자", "회수되나 · 무엇이 리스크인가 · 설계값과 실측이 맞나",
     ("D6", "D8", "D9", "D22", "D23", "D24", "D26")),
    ("공공기관", "지침에 맞나 · 서류가 갖춰졌나 · 무엇으로 확인하나",
     ("D2", "D4", "D5", "D7", "D11", "D12", "D13", "D14", "D15", "D17", "D18", "D19",
      "D25", "D27")),
)

# 2026년 스마트팜ICT융복합확산(온실신축) 사업시행지침의 가·감점 항목 원문(269차 확보)과
#   우리 산출물의 **이름 대응**. 대응이 없으면 **없다고 적는다**.
GUIDELINE_SCORE_ITEMS: tuple = (
    ("우선지원(가점)", "침수피해 방지를 위한 조치(주변보다 높게 성토, 배수로·배수시설)가 된 부지", ()),
    ("우선지원(가점)", "침수 우려가 있는 저지대 온실을 침수 가능성이 낮은 지대로 옮기는 경우", ()),
    ("우선지원(가점)",
     "설계도서(도면, 내역서, 시방서, 구조계산서, 부하계산서 등)가 준비된 경우",
     ("D2", "D4", "D6", "D7")),
    ("후순위(감점)", "침수, 산사태 우려 지역", ()),
    ("후순위(감점)", "신용조사서에 표시된 융자예상액과 자부담 가능액 불충분(사업비의 50%미만)", ()),
)
GUIDELINE_SCORE_SOURCE: str = "근거_외부수집_기능공백_20260924.md 6-d (2026년 사업시행지침 원문)"
PERSPECTIVE_NONE: str = "대응 산출물 없음"


def perspective_index(name: str = None) -> dict:
    """관점별 입구 — 묶음과 이유만 낸다(순위·등급·추천 없음).

    name이 없으면 전체, 있으면 그 관점 하나. 배정은 `PERSPECTIVES` 한 곳에 있고
    이 함수는 **읽기만** 한다.
    """
    spec_by = {s["code"]: s for s in PACKAGE_SPEC}
    fn_name = {f: n for f, n, _d in BENCHMARK_FUNCTIONS}
    rows = []
    for pname, ask, codes in PERSPECTIVES:
        docs = []
        for c in codes:
            s = spec_by[c]
            fn, why = FUNCTION_OF_CODE[c]
            docs.append({"code": c, "title": s.get("title", ""), "stage": s.get("stage", ""),
                         "function": "%s %s" % (fn, fn_name[fn]), "why": why})
        rows.append({"name": pname, "ask": ask, "docs": docs, "count": len(docs)})

    assigned = {c for _n, _a, cs in PERSPECTIVES for c in cs}
    orphan = [{"code": s["code"], "title": s.get("title", "")}
              for s in PACKAGE_SPEC if s["code"] not in assigned]

    score = [{"kind": k, "text": t,
              "codes": list(cs),
              "note": "" if cs else PERSPECTIVE_NONE}
             for k, t, cs in GUIDELINE_SCORE_ITEMS]

    out = {"rows": rows, "orphan": orphan, "score": score,
           "score_source": GUIDELINE_SCORE_SOURCE,
           "total": len(PACKAGE_SPEC), "assigned": len(assigned),
           "note": ("🔴관점은 **입구이지 판정이 아니다** — 어떤 산출물도 더 낫다고 하지 않고 "
                    "*「당신에겐 이것이 맞다」*를 말하지 않는다. 배정은 **분류**이고 "
                    "`PERSPECTIVES` 한 곳에 있다(★사용자 확인 대상). "
                    "가점 대조표는 **지침 원문 인용**이다 — 가점을 주는 것은 **심사 주체**이고 "
                    "리포는 **이름 대응까지만** 적는다")}
    if name is not None:
        one = [r for r in rows if r["name"] == name]
        if not one:
            return {}
        out["rows"] = one
        out["one"] = one[0]
    return out
# ─────────────────────────────────────────────────────────────
# 281차 — **기본설계 입구**(N-1). 작업지시서 11-B ⓒ: 엔진은 이미 내는데 **화면이 없었다**.
#   주소·품목·면적 셋만 받아 F1 계열이 낼 수 있는 것을 낸다. **케이스 파일이 필요 없다** —
#   `siting_lookup`·`select_specs`·`site_permit_checklist`는 순수 함수다(280차 확인).
#   🔴 **고르지 않는다.** 규격은 *「지역 조건을 통과하는 것」*을 세고 형식별 최소사양을
#      **참고로** 낼 뿐이다 — 어느 규격이 낫다고 하지 않는다(`select_specs` docstring:
#      *「최종 선택은 사용자 몫」*).
#   🔴 **못 내는 것을 함께 낸다.** 11-B ⓓ의 한계가 여기서 그대로 드러난다 —
#      기상 도달 68/172 · 평단가 18/249. 빈칸으로 두면 «없는 것»이 «0»으로 읽힌다.
#   ⚠️ 이 입구는 **「구조 기본설계」까지**다. 난방부하·경제면적·작기는 N-2·N-3과
#      주입이 들어와야 선다(11-B ⓓ).
# ─────────────────────────────────────────────────────────────
BASIC_DESIGN_FORMS: tuple = ("연동", "단동", "광폭")
BASIC_DESIGN_NONE: str = "낼 수 없다"


def basic_design(addr: str = None, crop: str = None, area_m2: float = None) -> dict:
    """주소·품목·면적 → 구조 기본설계 묶음. 분류·조회뿐 — 판정·추천 없음.

    셋 중 없는 것이 있으면 그만큼만 낸다(빈칸을 지어내지 않는다).
    """
    out = {"input": {"주소": addr or "", "품목": crop or "", "면적_m2": area_m2},
           "site": None, "specs": None, "estimate": None, "permit": None,
           "cannot": [], "note": (
               "🔴**고르지 않는다** — 규격은 지역 조건을 통과하는 것을 세고 형식별 "
               "최소사양을 **참고로** 낼 뿐이다(최종 선택은 사용자 몫). "
               "⚠️이 입구는 **「구조 기본설계」까지**다 — 난방부하·경제면적·작기는 "
               "자료·주입이 들어와야 선다")}
    cannot = out["cannot"]

    # ── ① 입지 ────────────────────────────────────────────────────────
    site = e.siting_lookup(addr) if addr else None
    if addr and site is None:
        cannot.append({"무엇": "입지 진단", "왜": (
            "설계하중 표에서 지역을 찾지 못했다 — 시군구 이름을 포함해 적으면 잡힌다"
            "(표는 행정구역 %d개)" % len(e.REGION_DESIGN_LOAD))})
    if site:
        st = e.weather_station(addr)
        w = None
        if st:
            hdh = e.heating_degree_hours(addr, 12)
            w = {"지점": st,
                 "설계외기온_C": e.design_outdoor_temp(addr),
                 "난방도일_12C": hdh.get("value"),
                 "월별풍속": e.monthly_mean_wind(addr),
                 "월별일조": e.monthly_sunshine(addr)}
        else:
            cannot.append({"무엇": "기상값(설계외기온·난방도일·풍속·일조)", "왜": (
                "이 지역은 기상 4표의 관측지점에 닿지 않는다 — 설계하중은 **행정구역 %d개**, "
                "기상 4표는 **관측지점 %d개**로 체계가 다르다. 공식 대응표가 없어 "
                "**잇지 않고 주입**받기로 했다(사용자 결정 2026-09-29)"
                % (len(e.REGION_DESIGN_LOAD), len(e.DESIGN_OUTDOOR_TEMP_TAC)))})
        out["site"] = {"지역명": site["region_name"],
                       "적설심_cm": site["region_snow_cm"],
                       "풍속_ms": site["region_wind_ms"],
                       "기상": w,
                       "출처": "내재해형 시설규격 고시 제2022-104호 별표(★준거 221차)"}

    # ── ② 적합 규격 ───────────────────────────────────────────────────
    if site:
        snow, wind = site["region_snow_cm"], site["region_wind_ms"]
        base = e.select_specs(snow, wind)
        withc = e.select_specs(snow, wind, crop=crop) if crop else base
        crops = e.spec_crops()
        if crop and crop not in crops:
            crop_note = ("이 작목의 **특화형 규격이 등록돼 있지 않다** — 일반형만 본다"
                         "(등록된 작목: %s)" % " · ".join(crops))
        elif crop and len(withc["candidates"]) == len(base["candidates"]):
            crop_note = ("이 작목의 특화형이 **이 지역 조건을 통과하지 못했다** — "
                         "일반형만 남았다(오류가 아니다)")
        elif crop:
            #   ⚠️ 두 수를 **빼지 않는다** — 조립 계층의 산술은 1절이 금한다
            #      (258차 단서는 **건수 집계**까지다). 둘을 나란히 적는다.
            crop_note = ("일반형 %d · 이 작목 포함 %d"
                         % (len(base["candidates"]), len(withc["candidates"])))
        else:
            crop_note = "품목 미지정 — 작물특화형은 제외하고 일반형만 본다(P1-11 결정)"
        out["specs"] = {
            "조건": "설계적설심 ≥ %scm AND 설계풍속 ≥ %sm/s" % (snow, wind),
            "통과_규격수": len(withc["candidates"]),
            "전체_규격수": len(e.SPEC_TABLE),
            "작목_주": crop_note,
            "형식별_최소사양": {f: {"이름": s.name, "폭_m": s.width_m,
                             "설계적설심_cm": s.snow_cm, "설계풍속_ms": s.wind_ms,
                             "서까래": s.rafter_spec, "등록연도": s.registered_year}
                        for f, s in sorted(withc["min_by_form"].items())},
            "주의": "최소사양은 **참고**다 — 어느 규격이 낫다고 하지 않는다",
        }

    # ── ③ 개산 ────────────────────────────────────────────────────────
    if site and area_m2:
        py = e.m2_to_py(area_m2)
        per = {}
        missing = []
        for f, s in sorted(out["specs"]["형식별_최소사양"].items()) if out["specs"] else []:
            v = e.greenhouse_total_estimate(s["이름"], py)
            per[f] = v
            if v is None:
                missing.append("%s(%s)" % (f, s["이름"]))
        out["estimate"] = {
            "면적_평": round(py, 2),
            "온실_전체_개산_원": per,
            "골조_단독_개산_원": round(e.structure_only_estimate(py)),
            "주의": ("개산은 **평단가표에 등재된 규격**만 낸다 — `None`은 미등재이고 "
                   "**지어내지 않는다**. 금액은 시세성이라 실제 견적은 주입받는다"),
        }
        if missing:
            cannot.append({"무엇": "온실 전체 개산 — " + " · ".join(missing), "왜": (
                "그 규격은 평단가표에 없다(등재 %d / 전체 %d)"
                % (sum(1 for s_ in e.SPEC_TABLE
                       if e.greenhouse_total_estimate(s_.name, 1000) is not None),
                   len(e.SPEC_TABLE)))})

    # ── ④ 인허가 ──────────────────────────────────────────────────────
    if area_m2:
        out["permit"] = e.site_permit_checklist(area_m2)

    # ── ⑤ 이 입구가 낼 수 없는 것(자료·주입이 먼저) ─────────────────────
    cannot.append({"무엇": "난방부하·연료량", "왜": (
        "기상값과 피복·목표온도가 있어야 선다 — 피복·온도는 **판단성**이라 "
        "엔진이 고르지 않는다(주입)")})
    #   🔴282차(N-2) — 수량은 등재됐다. **남은 것은 단가**이고 그것은 시세성이다.
    #      작목 이름을 **고르지 않는다** — 낱말이 들어가는 후보를 나열만 한다
    #      (토경/수경 중 무엇인지는 케이스가 정한다).
    if crop:
        hits = [n for n in e.facility_yield_crops() if crop in n]
        out["yield_ref"] = {
            "찾은_이름": hits,
            "수량_kg_m2": {n: e.facility_yield(n)["수량_kg_m2"] for n in hits},
            "원문_기준": e.FACILITY_YIELD_BASIS["unit"] + " — 위 값은 ㎡당으로 환산한 것",
            "출처": e.FACILITY_YIELD_BASIS["source"],
            "주의": ("**전국 평균**이고 **고르지 않는다** — 토경·수경 중 무엇을 쓸지는 "
                   "케이스가 정한다. 이름이 없으면 그 작목은 표에 없는 것이다"),
        }
    cannot.append({"무엇": "경제성(ROI·회수기간)·경제면적", "왜": (
        "수량은 282차에 등재됐다(전국 평균 · 시설 계열 %d종) — 그런데 **단가가 시세성**이라 "
        "주입 전용이고, 그것 없이는 총수입이 서지 않는다"
        % len(e.FACILITY_YIELD_KG_10A))})
    #   🔴286차 — 자료는 **있다**(농사로 「농작업일정」 작형별 출하시기). 막는 것이
    #      「자료 부재」에서 **라이선스**로 바뀌었다 — 고쳐 적는다
    cannot.append({"무엇": "적정작기·작형", "왜": (
        "자료는 있다 — 농사로 「농작업일정」이 작목마다 **작형별 출하시기**를 싣고 "
        "엔진이 아는 시설 작목에 닿는 것이 18건이다(286차에 소재 확정). 막는 것은 "
        "**라이선스**다 — 그 자료는 **공공누리 제2유형(출처표시+상업적 이용금지)**이고 "
        "이 산출물은 컨설팅용이라 등재 가부가 **법적·사업적 판단**이다. 작목 이름과 표의 "
        "열도 엔진과 1:1이 아니라 대응 규칙이 따로 필요하다(11-B N-3)")})
    cannot.append({"무엇": "작목 적합 판정", "왜": (
        "작목 선정은 **판단성**이라 1절이 금한다 — 규격이 그 작목을 지원하는지까지만 낸다")})
    return out


JUDGMENT_CODES: tuple = ("D25", "D26", "D27")


# ─────────────────────────────────────────────────────────────
# 288차 — **서비스 흐름(척추 1 · 렌즈 4)**. 사용자 지시 — *「화면스토리보드를
#   최적화하고 흐름을 세부적으로 연계하고 기능을 구체적으로 매칭하라」*.
#   🔴 **축을 새로 만들지 않는다.** 전부 기존 구조를 **잇기만** 한다 —
#      `STAGE_ORDER`(척추) · `PACKAGE_SPEC`(산출물·대상·엔진함수) ·
#      `PLATFORM_STAGES` · `FUNCTION_OF_CODE` · `ENTRY_STEP_*` · `GUIDE_SCREENS`.
#   🔴 **계산하지 않는다** — 분류와 **건수**뿐이다(1절 258차 단서: 항목 건수 집계 허용).
#   🔴 **척추를 내가 고르지 않았다** — 서비스 설계서가 3대상 × 6단계로 설계했고
#      `STAGE_ORDER`가 그 순서다. 이 함수는 그 설계를 화면으로 옮길 뿐이다.
#   ⚠️ **화면 ↔ 단계 대응은 리포에 없다.** 지어내지 않고 `gaps`로 드러낸다.
# ─────────────────────────────────────────────────────────────
FLOW_TARGETS: tuple = ("부지", "시설", "기자재")      # 설계서 §1의 3대상(순서 그대로)
FLOW_NO_LINK: str = "대응 정의 없음"


def service_flow() -> dict:
    """6단계 척추에 산출물·대상·기능·플랫폼·기입을 **잇는다**(결정론 · 판정 없음)."""
    plat_of = {}
    for key, name, stages, desc, bench in PLATFORM_STAGES:
        for st in stages:
            plat_of[st] = {"key": key, "name": name, "desc": desc, "bench": bench}

    spine = []
    for st in STAGE_ORDER:
        docs = []
        for sp in PACKAGE_SPEC:
            if sp["stage"] != st:
                continue
            fn = FUNCTION_OF_CODE.get(sp["code"])
            steps = list(ENTRY_STEP_ALL_CODES) + list(
                ENTRY_STEP_OF_CODE.get(sp["code"], ()))
            docs.append({
                "code": sp["code"], "title": sp["title"],
                "targets": list(sp.get("targets") or []),
                "fn": (fn or [FLOW_NO_LINK, ""])[0],
                "fn_why": (fn or ["", FLOW_NO_LINK])[1],
                "engine_n": len(sp.get("engine") or []),
                "entry_steps": steps,
                "appendix": sp["code"] in JUDGMENT_CODES,
            })
        spine.append({
            "stage": st, "platform": plat_of.get(st),
            "docs": docs, "n": len(docs),
            "targets": [(t, sum(1 for d in docs if t in d["targets"])) for t in FLOW_TARGETS],
            "engine_n": sum(d["engine_n"] for d in docs),
        })

    # 3대상 × 6단계 — 설계서 §2 커버리지 매트릭스를 **카탈로그에서 다시 센다**
    matrix = {"targets": list(FLOW_TARGETS),
              "rows": [{"stage": r["stage"],
                        "cells": [n for _t, n in r["targets"]],
                        "total": r["n"]} for r in spine],
              "col_total": [sum(1 for sp in PACKAGE_SPEC if t in (sp.get("targets") or []))
                            for t in FLOW_TARGETS]}

    # 렌즈 — 척추를 **다르게 보는 축**들. 각자 제 화면이 있다
    by_path = {s[0]: s[1] for s in GUIDE_SCREENS}
    lenses = [
        ("4축", "/axes", "입지·설계·운영·경제성 — 엔진이 계산하는 축"),
        ("기능", "/functions", "F0~F3 — 고객이 무엇을 받는가로 묶은 것"),
        ("관점", "/for", "농업인·투자자·공공기관 — 누가 읽는가"),
        ("참조", "/refs", "리포가 쥔 자료 — 수치가 어디서 왔는가"),
    ]
    lenses = [{"name": n, "path": p, "label": by_path.get(p, FLOW_NO_LINK), "why": w}
              for n, p, w in lenses]

    gaps = [
        {"무엇": "화면 ↔ 단계 대응", "왜": (
            "어느 화면이 어느 단계에 속하는지는 **리포 어디에도 정의돼 있지 않다**. "
            "배정하는 것은 판단이라 이 함수가 만들지 않는다 — 지금은 **산출물까지만** 잇는다")},
        {"무엇": "대상별 진입", "왜": (
            "3대상(부지·시설·기자재)으로 들어가는 화면이 없다. 매트릭스는 **건수**를 보일 뿐 "
            "대상 하나를 골라 따라가는 길은 아직 없다")},
        {"무엇": "단계 게이트", "왜": (
            "설계서 §8의 단계 게이트(무엇이 통과·대기인가)는 **문서에만** 있다 — "
            "케이스마다 달라서 이 화면은 케이스 없이 선다")},
    ]
    return {
        "spine": spine, "matrix": matrix, "lenses": lenses, "gaps": gaps,
        "doc_total": len(PACKAGE_SPEC), "stage_total": len(STAGE_ORDER),
        "source": "서비스설계_컨설팅_3대상x6단계_20260920.md §1·§2·§4",
        "note": ("🔴**척추는 6단계다** — 서비스 설계서가 3대상 × 6단계로 설계했고 이 화면은 "
                 "그 순서(`STAGE_ORDER`)를 그대로 옮긴다. 나머지 축은 **렌즈**이고 각자 제 화면이 있다. "
                 "🔴**이 화면은 분류와 건수만 낸다** — 값·등급·순위를 만들지 않고 "
                 "어떤 단계도 더 중요하다고 하지 않는다"),
    }



def judgment_split(items: list) -> dict:
    """산출물을 **본문 / 판정 부록**으로 가른다(계산하지 않는다 — 분류뿐이다)."""
    return {"body": [x for x in items if x["code"] not in JUDGMENT_CODES],
            "appendix": [x for x in items if x["code"] in JUDGMENT_CODES]}


# ─────────────────────────────────────────────────────────────
# 223차 — **플랫폼 3단계 축 + 표시 순서**(★사용자 결정 2026-09-27).
#   출처: `근거_사업기획서_투자검증설계보증플랫폼_20260921.docx` §5의 3단계
#     (투자실사 → 설계검증 → 성능보증)와 185차 대응표(`근거_사업기획서_컨셉적용_20260921.md` §1).
#   ★ 묶음: 설계검증 = ①②③ · 성능보증 = ⑤⑥ · 투자실사 = ④
#   ★ 표시 순서: ①②③⑤⑥④ — 레일과 탭이 **같은 순서**를 쓴다(웹 콘솔만. 정적
#     보고서의 순서는 바꾸지 않는다 — 같은 날 사용자 결정).
#   🔴 **분류이지 판정이 아니다** — 기능 축(211차)과 같은 산출물 27종을 다른 축으로
#      묶을 뿐 값·순위를 만들지 않는다. 기능 축은 D코드마다, 이 축은 **stage마다**
#      배정한다(185차 대응이 단계 단위였다).
#   준거(186차 원문 대조): 레일 = DNV Owner's Engineer 전주기 개입 ·
#     투자실사 = Agritecture Due Diligence 6영역 · 성능보증 = kWh Analytics
#     Solar Revenue Put(설계 대 실측) + PVEL 합격선 명시형.
# ─────────────────────────────────────────────────────────────
STAGE_ORDER: tuple = ("①공종설계", "②품질설계", "③감리",
                      "⑤운영", "⑥사후관리", "④타당성검증")

PLATFORM_STAGES: tuple = (
    ("P1", "설계검증", ("①공종설계", "②품질설계", "③감리"),
     "설계문서 검토 → 시공 감리 → 준공 커미셔닝",
     "DNV Owner's Engineer(전주기 개념 참고)"),   # 238차 — TÜV는 186차 403·미확인이라 뺐다
    ("P2", "성능보증", ("⑤운영", "⑥사후관리"),
     "준공 후 설계값 대 실측 — 보상 판정은 보험·금융의 일",
     "kWh Analytics Solar Revenue Put · PVEL Scorecard"),
    ("P3", "투자실사", ("④타당성검증",),
     "6영역을 문서검토 → 기술평가 → 보고서로",
     "Agritecture Due Diligence"),
)


def lifecycle_rail(items: list) -> list:
    """산출물 → `STAGE_ORDER` 순서의 단계 레일(분류와 개수뿐 — 계산하지 않는다)."""
    kinds = ("생성", "부분생성", "주입대기", "링크")
    rail = []
    for st in STAGE_ORDER:
        docs = [{"code": x["code"], "title": x["title"], "status": x["status"],
                 "appendix": x["code"] in JUDGMENT_CODES,
                 "needs": [n["slot"] for n in (x.get("needs") or [])]}
                for x in items if x["stage"] == st]
        rail.append({"stage": st, "docs": docs,
                     "tally": [(k, sum(1 for d in docs if d["status"] == k))
                               for k in kinds]})
    return rail


def platform_index(items: list) -> list:
    """산출물 → 플랫폼 3단계 묶음. 「엔진 밖」은 D23·D24 반환을 **그대로 옮긴다**."""
    by = {x["code"]: x for x in items}
    outside = {"P2": list((by.get("D24", {}).get("data") or {}).get("편차 함수 없는 항목") or []),
               "P3": list((by.get("D23", {}).get("data") or {}).get("공백 영역") or [])}
    rows = []
    for key, name, stages, desc, bench in PLATFORM_STAGES:
        docs = [{"code": x["code"], "title": x["title"], "status": x["status"],
                 "appendix": x["code"] in JUDGMENT_CODES}
                for st in stages for x in items if x["stage"] == st]
        rows.append({"key": key, "name": name, "stages": list(stages), "desc": desc,
                     "bench": bench, "docs": docs, "outside": outside.get(key, [])})
    return rows


# ─────────────────────────────────────────────────────────────
# 224차 — **기입 절차 스테퍼**(사용자 지시 · 223차 목업 승인분).
#   준거(186차 원문 대조): SGS Japan JAS 인증 절차 — 見積り依頼 / 見積書受領·申請 /
#     書類審査 / 実地検査 / 判定 / 認定証発行 / 年次審査(연 1회).
#   🔴 **진행 상태이지 판정이 아니다** — 각 단계 상태는 케이스·패키지 반환을 **분류**할
#      뿐 값·등급을 새로 만들지 않는다. ⑤의 등급은 D25가 낸 것을 그대로 옮긴다.
#   ⚠️ 224차엔 ②문서 제출·⑥발급에 **기입 양식도 저장 필드도 없어** 「경로 없음」이었다.
#      226차(사용자 지시)에 두 양식과 케이스 저장 블록을 만들어 이제 「대기」로 바뀌고
#      양식으로 이어진다. ⑦은 여전히 발급일이 있어야 기산된다.
# ─────────────────────────────────────────────────────────────
ENTRY_STEPS: tuple = (
    # 238차 정정(레드팀 29회차 B2): 종전 「書類提出」은 JAS 원문에 없는 단계명이었다. 원문 7단계
    #   (見積り依頼 / 見積書受領·申請 / 書類審査 / 実地検査 / 判定 / 認定証発行 / 年次審査)와
    #   **대응하는 것만** 적고, 대응이 없으면 없다고 적는다.
    ("case", "케이스 생성", "사람", "見積り依頼·見積書受領·申請(견적·신청)"),
    ("docs", "문서 제출", "사람", "JAS 대응 없음(콘솔 단계)"),
    ("engine", "엔진 검증", "엔진", "書類審査(서류심사)"),
    ("evidence", "근거 대조", "사람", "JAS 대응 없음(実地検査는 현장검사라 다르다)"),
    ("rules", "규칙 적용", "엔진", "判定(판정)"),
    ("issue", "발급", "사람", "認定証発行(인증서 발행)"),
    ("renew", "연차 재검", "사람", "年次審査(연차심사)"),
)
ENTRY_DOC_SLOTS: tuple = ("doc_rows", "dd_documents", "quoted_models")
# 원문 대조 전 status — 이것이 남아 있으면 ④는 끝나지 않았다(35차 정책: 실측 승격은 대조로만)
ENTRY_OPEN_PROVENANCE: tuple = ("추정", "확인요망", "미검증")


def entry_steps(case: dict, pkg: dict) -> list:
    """케이스 1건의 기입 절차 7단계 상태(분류뿐 — 계산하지 않는다).

    상태: 완료 · 진행 · 대기 · 경로 없음. `detail`은 **반환을 옮긴 문구**다.
    """
    by = {x["code"]: x for x in pkg["items"]}
    open_slots = [n["slot"] for n in pkg.get("open_injections") or []]
    d25 = (by.get("D25") or {}).get("data") or {}
    g = d25.get("등급") or {}
    prov = case.get("provenance") or {}
    unresolved = sorted(f for f, v in prov.items()
                        if (v or {}).get("status") in ENTRY_OPEN_PROVENANCE)
    sc = pkg.get("status_counts") or {}
    docs_open = [s for s in ENTRY_DOC_SLOTS if s in open_slots]
    state = {
        "case": ("완료", "케이스 파일이 있다"),
        "docs": (("대기", "미제출 " + " · ".join(docs_open))
                 if docs_open else ("완료", "문서 주입 슬롯이 채워졌다")),
        "engine": (("완료" if not sc.get("주입대기") and not sc.get("부분생성") else "진행"),
                   " · ".join(f"{k} {sc[k]}" for k in ("생성", "부분생성", "주입대기", "링크")
                              if sc.get(k))),
        # 238차 — ④는 **콘솔에 입력 경로가 없다**(원문 대조 → 레지스트리·케이스 status 갱신은
        #   문서 절차다). 224차 설계 의도(경로 없는 칸이 진행처럼 보이지 않게)대로 「경로 없음」.
        "evidence": (("경로 없음", f"원문 대조 전 {len(unresolved)} / {len(prov)}필드 — "
                      + " · ".join(unresolved) + " — 콘솔 밖 절차(원문 대조 후 status 갱신)")
                     if unresolved else ("완료", f"{len(prov)}필드 전부 대조됨")),
        "rules": ((("완료" if g.get("complete") else "진행"),
                   f"등급 {g.get('grade')} · 통과 {g.get('n_passed')} / {g.get('n_total')}"
                   + ("" if g.get("complete") else f" · 미검증 {len(g.get('unchecked') or [])}"))
                  if g else ("대기", "D25가 아직 없다")),
        # 🔴225차 정정 — `식별번호`·`유효기간`은 **dict**다(`ksfid_number`·`ksfid_validity`
        #    반환). 224차는 통째로 문자열에 넣어 주입되는 순간 dict가 화면에 샜다
        #    (가드가 가짜 문자열을 넣어 못 봤다).
        "issue": (("완료", f"식별번호 {d25['식별번호']['ksfid']}") if d25.get("식별번호")
                  else ("대기", "{} 미주입 — 번호는 일련번호와 발급일(연도)이 모두 있어야 선다".format(
                      " · ".join(n["slot"] for n in (by.get("D25") or {}).get("needs") or []
                                 if n["slot"] in ("ksfid_seq", "ksfid_issued"))))),
        "renew": (("진행", f"유효기간 {d25['유효기간']['issued']} ~ {d25['유효기간']['expires']}")
                  if d25.get("유효기간")
                  else ("대기", "발급일(ksfid_issued)이 없어 기산할 수 없다")),
    }
    return [{"key": k, "name": n, "who": w, "jas": j,
             "state": state[k][0], "detail": state[k][1]}
            for k, n, w, j in ENTRY_STEPS]


# ─────────────────────────────────────────────────────────────
# 225차 — **추적 식별자 배지**(사용자 지시 · 223차 목업 승인분).
#   준거(186차 원문 대조): GLOBALG.A.P. 13자리 GGN — **번호는 추적 식별자이지 등급이
#   아니다**. 번호·만료일은 엔진(`ksfid_number`·`ksfid_validity`)이 D25에 실어 낸 것을
#   **그대로** 옮긴다. 미발급이면 번호 형식과 빠진 주입 슬롯을 드러낸다.
#   📌 형식 문자열은 `ksfid_number` docstring과 **같아야 한다**(가드가 대조한다).
# ─────────────────────────────────────────────────────────────
KSFID_FORMAT = e.KSFID_NUMBER_SPEC["format"]   # 230차 — 엔진 상수 하나에서(따로 적지 않는다)


def ksfid_badge(pkg: dict) -> dict:
    """D25 반환 → 추적 식별자 배지(분류·옮김뿐. 번호를 만들지 않는다)."""
    d25 = next((x for x in pkg["items"] if x["code"] == "D25"), None) or {}
    data = d25.get("data") or {}
    num, val = data.get("식별번호"), data.get("유효기간")
    missing = [n["slot"] for n in (d25.get("needs") or [])
               if n["slot"] in ("ksfid_seq", "ksfid_issued")]
    return {"issued": bool(num),
            "ksfid": num["ksfid"] if num else None,
            "expires": val["expires"] if val else None,
            "format": KSFID_FORMAT, "missing": missing}


# ─────────────────────────────────────────────────────────────
# 226차 — **케이스에 저장하는 주입 블록**(사용자 지시: 발급·문서 제출 주입 폼).
#   financing과 같은 모양이다 — 블록마다 **근거(note)가 필수**이고 저장은 케이스 JSON,
#   커밋은 사람이 한다. 값의 검증은 엔진(`doc_consistency_check`·`equipment_reconcile`·
#   `ksfid_number`·`ksfid_validity`)이 한다 — 이 계층은 모양만 바꾼다.
#   🔴 번호는 **발급기관이 준 것을 적을 뿐**이다 — 엔진·콘솔이 번호를 고르지 않는다.
# ─────────────────────────────────────────────────────────────
DOC_SUBMISSION_KEY = "doc_submission"
KSFID_ISSUE_KEY = "ksfid_issue"
# 242차 — ★D-9(2026-09-28): 동절기 달은 **케이스마다 입력**(한 달도 유효) — 입지 조건 블록
SITE_CONDITIONS_KEY = "site_conditions"
# 227차 — 재료승인 첨부 6종(공사시방서 재료 절 전사, 레지스트리 `실측`). 양식 안내용으로
#   **엔진 상수를 그대로** 내보낸다 — 표시 계층이 목록을 따로 적지 않는다.
APPROVAL_ATTACHMENTS: tuple = tuple(e.MATERIAL_APPROVAL_ATTACHMENTS)
APPROVAL_ALIASES: dict = dict(e.MATERIAL_APPROVAL_ALIASES)   # 231차 — 양식 안내용(엔진 상수 그대로)
DOC_ROW_FIELDS: tuple = ("req_id", "requirement", "drawing_no", "drawing_rev",
                         "spec_no", "spec_rev", "boq_id", "boq_rev", "std_id", "std_rev")


def case_injections(case: dict) -> dict:
    """케이스 JSON의 저장 주입 블록 → `build_package` 슬롯(모양 변환뿐)."""
    out = {}
    ds = case.get(DOC_SUBMISSION_KEY) or {}
    if ds.get("doc_rows"):
        out["doc_rows"] = [e.DocRefRow(**{k: str(r.get(k) or "") for k in DOC_ROW_FIELDS})
                           for r in ds["doc_rows"]]
    for k in ("dd_documents", "quoted_models"):
        if ds.get(k):
            out[k] = list(ds[k])
    if ds.get("ks_declared"):
        out["ks_declared"] = dict(ds["ks_declared"])
    if ds.get("attachments_by_model"):                      # 227차
        out["attachments_by_model"] = {m: list(v) for m, v in ds["attachments_by_model"].items()}
    sc = case.get(SITE_CONDITIONS_KEY) or {}
    if sc.get("winter_months"):
        out["winter_months"] = [int(m) for m in sc["winter_months"]]
    if sc.get("has_thermal_screen") is not None:
        out["has_thermal_screen"] = bool(sc["has_thermal_screen"])
    ki = case.get(KSFID_ISSUE_KEY) or {}
    if ki.get("ksfid_seq") is not None:
        out["ksfid_seq"] = int(ki["ksfid_seq"])
    if ki.get("ksfid_issued"):
        out["ksfid_issued"] = str(ki["ksfid_issued"])
    return out


def build_package(case: dict, injections: dict = None) -> dict:
    """케이스 1건 → D1~D20 패키지(결정론).

    injections: 시세성·고객문서 주입값. 없으면 그 산출물은 `주입대기`로 남는다 —
    🔴 **비어 있는 것을 채우지 않는다.**
    """
    if not isinstance(case, dict) or not case.get("input"):
        raise ValueError("case가 비어 있거나 input이 없다")
    # 226차 — 케이스에 **저장된** 주입(문서 제출·K-SFID 발급)을 먼저 깔고, 인자로 받은
    #   주입이 그 위를 덮는다. 저장 주입을 여기서 읽어야 콘솔과 정적 보고서가 **같은
    #   값**을 본다(한쪽만 읽으면 둘이 갈라진다 — 210차 교훈).
    inj = case_injections(case)
    inj.update(injections or {})
    # 🔴 차집합은 `-`가 아니라 `difference()`로 쓴다 — 181차 가드가 조립 계층에서
    #    산술 연산자를 **하나도** 허용하지 않기 때문이다(집합 연산이라도 예외를 두면
    #    그 예외가 곧 산술이 들어오는 문이 된다).
    unknown = sorted(set(inj).difference(INJECTION_SLOTS))
    if unknown:
        raise ValueError("모르는 주입 슬롯: %s" % unknown)

    inp = case_to_input(case)
    res = rr.compute(inp)          # 🔴 4축 수치는 여기서 다시 계산하지 않는다
    region, items = inp.region, []

    for spec in PACKAGE_SPEC:
        code = spec["code"]

        if code == "D1":
            d = {"지역": region,
                 "설계하중": e.siting_design_load(region),
                 "내재해형 조회": e.siting_lookup(region),
                 # 241차 — ★D-5·D-6: 기상 4표는 별칭·부분 일치로 찾는다. **어느 관측지점을
                 #   썼는지**를 함께 낸다(부분 일치는 글자 포함이라 사람이 확인할 수 있어야 한다)
                 "기상 지점": e.weather_station(region),
                 "난방 설계외기온": e.design_outdoor_temp(region),
                 # 241차 — D-5 원래 뜻(89차 ⓑ 「t_min 옆 TAC 참고 열 병기」): 케이스 입력을
                 #   **옮겨 적기만** 한다(비교·판정하지 않는다)
                 "케이스 최저온도 t_min(입력)": inp.t_min,
                 "월별 평균풍속": e.monthly_mean_wind(region),
                 "월별 일조시간": e.monthly_sunshine(region),
                 "난방도시(설정온도 기준)": e.heating_degree_hours(region, inp.t_target)}
            n = _need("winter_months")
            months = inj.get("winter_months")
            if months:
                mw = e.mean_wind(region, months)
                d["동절기 평균풍속"] = mw
                n = []
                screen = inj.get("has_thermal_screen")
                if mw is not None and screen is not None:
                    d["풍속 보정계수"] = e.wind_correction_factor(mw, screen)
                else:
                    n = _need("has_thermal_screen")
            sun = inj.get("period_sunshine_h")
            if sun is not None:
                d["기간부하 일조 보정 k"] = e.period_load_adjust_k(sun)
            else:
                n = n + _need("period_sunshine_h")
            miss = [k for k, v in d.items() if v is None]
            items.append(_item(spec, "생성", d, n,
                               "🔴 조회 실패 항목은 `None`으로 남긴다(추정하지 않는다): %s"
                               % (miss or "없음")))

        elif code == "D2":
            sel = e.select_specs(inp.snow_cm, inp.wind_ms, crop=inp.crop)
            d = {"작목": inp.crop,
                 "하중 충족 후보": len(sel["candidates"]),
                 "형식별 최소사양": {f: s.name for f, s in sel["min_by_form"].items()},
                 "작목특화형 목록": e.spec_crops(),
                 "피복조합 후보": len(e.cover_assembly_options()),
                 "면적(㎡→평→㎡ 왕복)": {"평": e.m2_to_py(inp.area_m2),
                                  "㎡": e.py_to_m2(e.m2_to_py(inp.area_m2))},
                 "표준 장치명별 등재 수": {}}
            # 🔴 `장비정보.csv`는 `농장명/업체명`·`농장주`·`계약 금액`을 함께 담는다 —
            #    **수만 센다**(행을 그대로 옮기면 실명과 계약가가 산출물에 실린다).
            for dev in ("환경제어기", "양액기", "냉방기", "환풍기"):
                d["표준 장치명별 등재 수"][dev] = len(e.equipment_lookup(dev))
            n2 = []
            layers = inj.get("cover_layers")
            if layers:
                asm = e.cover_assembly_lookup(tuple(layers))
                d["피복조합 조회"] = (None if asm is None else
                                {"층": list(asm.layers), "U": asm.u_w_m2k,
                                 "열절감률(%)": asm.savings_pct, "표": asm.table})
            else:
                n2 = n2 + _need("cover_layers")
            cur = inj.get("curtain") or case["input"].get("curtain")
            if cur:
                d["커튼 노출비율(fr)"] = e.curtain_exposure_ratio(cur)
            else:
                n2 = n2 + _need("curtain")
            model = inj.get("equipment_model")
            if model:
                d["장비 구성품·표준가격"] = e.equipment_component_prices(model)
            else:
                n2 = n2 + _need("equipment_model")
            items.append(_item(spec, "생성", d, n2,
                               "🔴 사양 확정은 판단성 — 후보와 최소사양까지만 낸다. "
                               "장비 조회는 **수만 센다** — 원문 CSV에 농장명·농장주·"
                               "계약 금액이 함께 있어 행을 그대로 옮기지 않는다"))

        elif code == "D3":
            # 🔴 대안은 **형식별 최소사양**으로만 세운다 — 어느 것이 낫다고 하지 않는다.
            #    피복조합(curtain)은 FR_TABLE 키라 임의로 고르지 않고 케이스에 있을 때만 쓴다.
            curtain = inj.get("curtain") or case["input"].get("curtain")
            if curtain is None:
                items.append(_item(spec, "주입대기", None, _need("curtain"),
                                   "대안 비교는 피복조합이 정해져야 선다"))
            else:
                opts = []
                for form, s_ in sorted(
                        e.select_specs(inp.snow_cm, inp.wind_ms)["min_by_form"].items()):
                    opts.append(e.DesignOption(
                        label=form, spec_name=s_.name, cover=inp.cover.value,
                        curtain=curtain, area_py=e.m2_to_py(inp.area_m2),
                        surface_area_m2=inp.surface_area_m2, t_target=inp.t_target,
                        t_min=inp.t_min, floor_area_m2=inp.area_m2))
                cmp_ = e.compare_design_options(inp.snow_cm, inp.wind_ms, opts)
                items.append(_item(spec, "생성",
                                   {"대안 수": len(cmp_.rows),
                                    "규격": [r.spec_name for r in cmp_.rows],
                                    "설계강도 충족": [r.spec_ok for r in cmp_.rows],
                                    "비고": cmp_.notes}, [],
                                   "형식별 최소사양을 나란히 놓는다 — 순위·추천 필드가 없다"))

        elif code == "D4":
            d = {"원문 관류열부하 비율(%)": e.transmission_share_pct()}
            n4 = []
            tr = inj.get("transmission_kcal_h")
            if tr is not None:
                comp = e.heating_load_components(tr, inp.t_target, inp.t_min)
                d["부하 3성분"] = {"관류": comp.transmission_kcal_h,
                              "환기": comp.infiltration_kcal_h,
                              "지중": comp.ground_kcal_h,
                              "결손": comp.missing,
                              "부분합": comp.partial_total_kcal_h}
            else:
                n4 = n4 + _need("transmission_kcal_h")
            rows = inj.get("doc_rows")
            if rows:
                rep = e.doc_consistency_check(rows)
                # 226차 — 행별 분류도 싣는다(기입 양식이 **패키지를 거쳐** 보여 주도록 —
                #   표시 계층이 엔진 함수를 직접 부르지 않는다, 80·181차 가드)
                d["4축 정합"] = {"집계": rep.counts, "행": len(rep.rows),
                               "행별": [{"req_id": r.req_id, "requirement": r.requirement,
                                        "status": r.status,
                                        "missing_docs": list(r.missing_docs),
                                        "missing_revs": list(r.missing_revs),
                                        "mismatch_detail": r.mismatch_detail}
                                       for r in rep.rows]}
            else:
                n4 = n4 + _need("doc_rows")
            items.append(_item(spec, "생성" if not n4 else "부분생성", d, n4,
                               "🔴 3성분 분해는 관류열부하를 **주입받는다** — 이 계층이 "
                               "역산하면 그것이 병렬 계산이다. `missing`은 채우지 않는다"))

        elif code == "D5":
            # 🔴 견적 정합은 주입 대기지만, **대조의 기준선**은 지금 세울 수 있다 —
            #    업체 후보(소재지 거르기만)와 개산 2법이다. 어느 것도 추천이 아니다.
            area_py = e.m2_to_py(inp.area_m2)
            est = {}
            for form, s_ in e.select_specs(inp.snow_cm, inp.wind_ms)["min_by_form"].items():
                est[s_.name] = e.greenhouse_total_estimate(s_.name, area_py)
            d = {"업체 후보(소재지 거르기만)": len(e.construction_company_list(region)),
                 "개산 A 온실 전체(평단가×면적)": est,
                 "개산 B 골조 단독": e.structure_only_estimate(area_py)}
            # 🔴213차 — ★보조사업자 계약 기준(사용자 결정 2026-09-24)의 **요건 판정**.
            #    계산값(총공사비)을 판정에 **넣는 것은 조립 계층의 일**이다 —
            #    판정 함수는 계산 함수를 부르지 않는다(191차 결정).
            d["조달 경로 요건(보조사업자 계약)"] = e.procurement_route(
                "건설공사", case["input"]["total_construction_cost"])
            std = inj.get("standard_cost_won")
            d["견적 개수 요건"] = (
                e.quote_count_requirement(
                    case["input"]["total_construction_cost"], std)
                if std is not None else
                {"미주입": "기준사업비(standard_cost_won) — 사업·연도마다 달라 "
                           "**주입**받는다(엔진이 고르지 않는다)",
                 "적용 사업": e.QUOTE_COUNT_RULE["applies_to"],
                 "주의": "🔴222차 — 이 요건은 **인삼생산시설현대화 사업** 조항이다. "
                         "온실신축 지침에는 **견적 조항이 없다**(이견 ③ 닫힘)",
                 "미주입의 뜻": "🔴269차 — **채울 구멍이 아니다**. 2026년 온실신축 "
                            "사업시행지침 원문에도 「기준사업비」는 0회다(2025년판·"
                            "'27 공모 추진계획도 0회). 이 사업은 기준 단가를 주지 "
                            "않고 신청자가 「㎡ × 천원」으로 산출하며 농어촌공사가 "
                            "**적정성 검토**로 받는다. 주입 경로는 다른 사업을 "
                            "케이스로 받을 때를 위해 남겨 둔다"})
            vq = inj.get("vendor_quotes")
            form, curtain = inj.get("rfq_form"), inj.get("curtain")
            if vq and form and curtain:
                rfq = e.generate_rfq_package(
                    inp.snow_cm, inp.wind_ms, inp.area_m2, inp.cover, form,
                    inp.t_target, inp.t_min, fr=inp.fr,
                    surface_area_m2=inp.surface_area_m2, curtain=curtain, crop=inp.crop)
                cmpq = e.compare_quotes(rfq, vq)
                d["RFQ 규격"] = rfq.spec_name
                d["업체 비교"] = {"안 수": len(cmpq.rows),
                              "최저가 표시": cmpq.lowest_cost_vendor,
                              "최고정합 표시": cmpq.highest_match_score_vendor}
                one = inj.get("quote_for_reconcile")
                if one:
                    rec = e.reconcile_quote(rfq, **one)
                    d["견적 정합 4검사"] = rec.checks
                items.append(_item(spec, "생성", d, [] if one else _need("quote_for_reconcile"),
                                   "🔴 최저가·최고정합은 **표시일 뿐 추천이 아니다** — "
                                   "업체 선정은 컨설턴트 몫이다"))
            else:
                items.append(_item(spec, "부분생성", d,
                                   _need("vendor_quotes", "rfq_form", "curtain"),
                                   "🔴 견적 금액은 시세성 — 주입 전용이다. 업체 후보는 "
                                   "**명단일 뿐 추천이 아니다**. 개산이 `None`인 규격은 "
                                   "평단가표 미등재이고 지어내지 않는다. 형식(`rfq_form`) "
                                   "선택은 **판단성**이라 기계가 고르지 않는다"))

        elif code == "D6":
            it = inj.get("capex_items")
            if not it:
                items.append(_item(spec, "주입대기", None, _need("capex_items"),
                                   "공종별 금액이 없으면 분해할 대상이 없다"))
            else:
                br = e.capex_major_breakdown(it, inp.total_construction_cost)
                fine = e.capex_breakdown(it)
                items.append(_item(spec, "생성",
                                   {"미분류": br.unclassified, "상위 카테고리": len(br.rows),
                                    "세부 항목": len(fine.rows)}, [],
                                   "🔴 잔차는 `unclassified`로 **남긴다** — 0으로 만들지 않는다"))

        elif code == "D7":
            q = inj.get("quantities")
            if not q:
                items.append(_item(spec, "주입대기", None, _need("quantities"),
                                   "물량은 설계 성과품에서 온다"))
            else:
                d = {"프로젝트 합계": e.pumsem_project_labor_summary(q)}
                probe = inj.get("pumsem_probe")
                if probe:
                    d["단일 항목 조회"] = e.pumsem_labor_days(**probe)
                items.append(_item(spec, "생성", d,
                                   [] if probe else _need("pumsem_probe")))

        elif code == "D8":
            items.append(_item(spec, "링크",
                               {"파일": _LINKED["D8"].format(case_id=case["case_id"]),
                                "요약": res["economics"]}, [],
                               "🔴 4축 수치는 `render_report.compute` 단일 경로에서 온다 — "
                               "이 계층은 다시 계산하지 않는다"))

        elif code == "D9":
            be = e.operating_breakeven(inp.opex, inp.price_won_per_kg)
            d = {"손익분기": {"필요 매출(원)": be.breakeven_revenue_won,
                           "필요 생산량(kg)": be.breakeven_kg},
                 "ROI": res["economics"]["roi"],
                 "Payback": res["economics"]["payback"],
                 "NPV": res["economics"]["npv"],
                 "IRR": res["economics"]["irr"],
                 "실질ROI": res["economics"]["real_roi"]}
            d["보조사업 절차"] = {"단계": len(e.subsidy_application_checklist()),
                             "주의": "보조율은 공모 회차마다 바뀌어 싣지 않는다"}
            needs = []
            loan = inj.get("loan")
            if loan:
                d["상환표"] = e.loan_amortization(**loan)
                d["DSCR"] = e.dscr_schedule(res["economics"]["revenue"], inp.opex, loan)
            else:
                needs.extend(_need("loan"))
            # 🔴202차 — 재무 가정은 **케이스가 정한 것**을 쓴다. 종전엔 이 둘이
            #   엔진 기본값·리터럴로 갔고, 케이스가 할인율을 주입해도 **D9만 따로
            #   0.05로** 계산돼 **같은 리포트 안에 두 할인율이 공존**할 수 있었다.
            _asm = res["economics"]["assumptions"]
            _av = _asm["values"]
            d["가정"] = {"값": dict(_av), "주입": dict(_asm["injected"]),
                       "note": ("D9의 NPV·상한 역산은 **4축 리포트와 같은 가정**을 "
                                "쓴다. `주입`이 거짓인 항목은 **엔진 기본값**이다")}
            tg = inj.get("capex_targets")
            if tg:
                d["CAPEX 상한 역산"] = e.max_investable_capex(
                    res["economics"]["revenue"], inp.opex,
                    useful_life=_av["useful_life"],
                    discount_rate=_av["discount_rate"],
                    years=_av["years"], **tg)
            else:
                needs.extend(_need("capex_targets"))
            cf = inj.get("cashflows")
            if cf:
                d["시나리오 NPV"] = e.npv(_av["discount_rate"], cf)
                d["시나리오 IRR"] = e.irr(cf)
            else:
                needs.extend(_need("cashflows"))
            cl = inj.get("cluster")
            if cl:
                d["단지화 경제성"] = e.cluster_economics(**cl)
            else:
                needs.extend(_need("cluster"))
            items.append(_item(spec, "생성" if not needs else "부분생성", d, needs,
                               "🔴 금리·기간은 시세성, 목표치는 협의 — 주입이 없으면 "
                               "상환표·DSCR·상한 역산을 만들지 않는다. "
                               "NPV·IRR은 `render_report.compute` 결과를 그대로 옮긴다"))

        elif code == "D10":
            # 🔴 공종명은 `WARRANTY_STATUTORY` 등재 키를 **그대로** 쓴다 —
            #    비슷한 이름으로 넘기면 `None`이 돌아오고, 그것을 「담보기간 없음」으로
            #    읽으면 등재값이 있는데 없다고 말하는 것이 된다.
            w = {}
            for wt in ("온실설치", "전기(건축물 전기설비)", "통신(그 외 정보통신공사)",
                       "급배수·냉난방·환기·공조·자동제어·가스·배연설비"):
                w[wt] = e.warranty_period(wt)
            li = inj.get("lcc_items")
            d = {"법정 하자담보기간": w}
            # 🔴213차 — 하자이행보증보험의 **법정 최소 요건**(보험 판정이 아니다)
            d["하자이행보증 최소 요건"] = e.warranty_bond_requirement(
                case["input"]["total_construction_cost"])
            if li:
                d["LCC 교체 일정"] = e.lcc_replacement_schedule(li, 20)
            items.append(_item(spec, "생성" if li else "부분생성", d,
                               [] if li else _need("lcc_items"),
                               "🔴 단가는 시세성 — 없으면 교체 **연도 구조**도 세우지 않는다"))

        elif code in _LINKED:
            items.append(_item(spec, "링크", {"파일": _LINKED[code]}, [],
                               "이미 생성되는 산출물로 연결한다"))

        elif code == "D12":
            items.append(_item(spec, "링크", {"문서": list(_D12_DOCS)}, [],
                               "🔴 ④ 결정 로그는 아직 없다(설계서 §4 기록)"))

        elif code == "D13":
            items.append(_item(spec, "생성", e.inspection_checklist(), [],
                               "공사시방서 9단계 전사 + 엔진 대조 4곳"))

        elif code == "D14":
            names = inj.get("quoted_models") or ["온풍난방기", "보온커튼", "환기팬"]
            plan = e.commissioning_plan(names, inj.get("acceptance_criteria"))
            items.append(_item(spec, "생성", plan,
                               _need("acceptance_criteria") if plan["needs_criteria"] else [],
                               "🔴 합격 기준은 시방서 원문에 없다 — `needs_criteria`로 드러낸다"))

        elif code == "D15":
            items.append(_item(spec, "생성", e.completion_docset(), [],
                               "시방서 열거 5종 + 4축 정합 상태(D4가 서면 함께 붙는다)"))

        elif code == "D16":
            mi = inj.get("maintenance_items") or ["온풍난방기", "보온커튼", "환기팬"]
            sch = e.maintenance_schedule(mi, inj.get("inspection_intervals"))
            items.append(_item(spec, "생성", sch,
                               _need("inspection_intervals") if sch["needs_interval"] else [],
                               "🔴 점검 주기표가 국내에 없다 — 주입 전용이고 미주입을 드러낸다"))

        elif code == "D17":
            rec, done = inj.get("defect_records"), inj.get("completion_date")
            if not rec or not done:
                items.append(_item(spec, "주입대기", None,
                                   _need("defect_records", "completion_date"),
                                   "준공일과 하자 기록이 있어야 담보기간을 대조한다"))
            else:
                items.append(_item(spec, "생성", e.defect_tracking(rec, done), []))

        elif code == "D18":
            chk = e.site_permit_checklist(area_m2=inp.area_m2, cover=inp.cover.value,
                                          land_use_zone=inj.get("land_use_zone"))
            items.append(_item(spec, "생성", chk,
                               _need("land_use_zone") if chk["missing_inputs"] else [],
                               "🔴 비용 이견 2건을 본문에 섞지 않고 `cost_dispute`로 분리한다"))

        elif code == "D19":
            qm = inj.get("quoted_models")
            if not qm:
                items.append(_item(spec, "주입대기", None, _need("quoted_models", "ks_declared"),
                                   "견적 모델명이 없으면 대조할 대상이 없다"))
            else:
                items.append(_item(spec, "생성",
                                   e.equipment_reconcile(qm, inj.get("ks_declared"),
                                                         inj.get("attachments_by_model")), [],
                                   "🔴 적합 판정은 하지 않는다 — 3열 대조까지다"))

        elif code == "D20":
            names = inj.get("service_life_names") or ["온풍난방기", "분무기", "컴퓨터서버"]
            rows = []
            for n in names:
                rows.append(e.service_life_reference(n))
            # 🔴208차(★②) — 품목 셋만 보면 **두 표가 어떻게 갈라져 있는지**를
            #   알 수 없다. 합집합 요약을 함께 낸다 — **값이 아니라 조회 경로**를
            #   합친 결과다. `이름이 스치는 쌍`은 **잇지 않은 것**을 드러낸다.
            ix = e.service_life_index()
            items.append(_item(spec, "생성",
                               {"행": rows, "두 표 합집합": ix["counts"],
                                "이름이 스치는 쌍(잇지 않음)": ix["near_pairs"],
                                "통합 주석": ix["note"]}, [],
                               "🔴 조달청·농진청[추정]·세법을 나란히 둘 뿐 고르지 않는다"))

        elif code == "D21":
            d = {"수율 조정(현 적합도)": e.yield_adjustment(inp.fitness_pct),
                 "생산량(kg)": e.production_kg(inp.area_m2, inp.base_yield_kg_m2,
                                            inp.fitness_pct),
                 "OPEX 비목 체계(항목 수)": len(e.OPEX_ITEM_CATEGORIES)}
            n21 = []
            er = inj.get("env_ratios")
            if er:
                d["환경 적합도(%)"] = e.env_fitness(**er)
            else:
                n21 = n21 + _need("env_ratios")
            oi = inj.get("opex_items")
            if oi:
                ob = e.opex_breakdown(oi, inp.opex)
                d["OPEX 분해"] = {"항목": len(ob.items), "미분류": ob.unclassified,
                               "합계": ob.total}
            else:
                n21 = n21 + _need("opex_items")
            im = inj.get("improvement")
            if im:
                d["개선 투자 ROI"] = e.improvement_roi(**im)
            else:
                n21 = n21 + _need("improvement")
            items.append(_item(spec, "생성" if not n21 else "부분생성", d, n21,
                               "🔴 `env_fitness` 가중치는 `[추정]`이다(광 0.5·온 0.2·습 0.2·"
                               "CO₂ 0.1) — 작목·생육단계 의존이라 외부 일반값으로 덮지 않았다. "
                               "OPEX 잔차는 `unclassified`로 **남긴다**"))

        elif code == "D22":
            # 🔴279차(D-17 닫힘) — 온실신축은 **지침 요율표**가 조회처다.
            #    건축사대가기준은 **다른 사업용**이라 지우지 않고 함께 낸다.
            d = {"지침 요율(온실신축)": e.guideline_fee_reference(
                     inp.total_construction_cost),
                 "감리 대가 참고(건축사대가기준 — 다른 사업용)":
                     e.design_supervision_fee_reference(inp.total_construction_cost)}
            fi = inj.get("fee_inputs")
            if fi:
                d["실비정액가산 산출"] = e.consulting_fee_estimate(**fi)
                items.append(_item(spec, "생성", d, [],
                                   "🔴 `in_notice_range`는 **고시 범위와의 대조 결과**이지 "
                                   "판정이 아니다"))
            else:
                items.append(_item(spec, "부분생성", d, _need("fee_inputs"),
                                   "🔴 노임단가·요율에 **기본값을 두지 않는다** — 고시는 "
                                   "범위만 정하고 그 안의 선택은 협의(시세성)다. "
                                   "인·일은 우리 원가라 `[제안]`이다"))

        elif code == "D23":
            rows, gaps = [], []
            for a in DD_AREAS:
                row = {"영역": a["area"], "엔진 함수": list(a["engine"]),
                       "무엇을 덮는가": a["covers"] or None}
                if not a["engine"]:
                    row["공백"] = a["gap"]
                    gaps.append(a["area"])
                rows.append(row)
            # 🔴 `len(DD_AREAS) - len(gaps)`는 **산술**이다(가드가 잡았다) — 센다.
            d = {"영역": rows,
                 "엔진이 덮는 영역": sum(1 for a in DD_AREAS if a["engine"]),
                 "공백 영역": gaps,
                 "규격 적합(하중 충족 후보)": len(
                     e.select_specs(inp.snow_cm, inp.wind_ms)["candidates"]),
                 "단위 공사비 대조": e.benchmark_check(
                     inp.total_construction_cost, inp.area_m2, inp.cover),
                 "인허가 결손": e.site_permit_checklist(
                     area_m2=inp.area_m2, cover=inp.cover.value)["missing_inputs"]}
            # 226차 — 제출 문서 목록을 **옮겨 적기만** 한다(내용을 심사하지 않는다)
            if inj.get("dd_documents"):
                d["제출 문서"] = list(inj["dd_documents"])
            items.append(_item(spec, "부분생성", d,
                               [] if inj.get("dd_documents") else _need("dd_documents"),
                               "🔴 **등급을 매기지 않는다** — 기획서가 둔 인증 등급은 "
                               "**판정**이고 1절이 금한다. "
                               f"6영역 중 **{len(gaps)}개는 엔진 밖**이다(경영진 역량·시장위치) "
                               "— 덮은 척하지 않는다"))

        elif code == "D24":
            rows, no_fn = [], []
            for p in PERF_ITEMS:
                r = {"항목": p["item"], "편차 함수": p["fn"], "실측 주입": p["slot"]}
                if p["fn"] is None:
                    r["상태"] = "엔진에 편차 함수가 없다"
                    no_fn.append(p["item"])
                rows.append(r)
            al = inj.get("actual_load_per_m2")
            if al is not None:
                rows[0]["대조"] = e.verify_heating_vs_actual(al, inp.cover.value)
            d = {"행": rows,
                 "설계 수확량(kg)": e.production_kg(inp.area_m2, inp.base_yield_kg_m2,
                                              inp.fitness_pct),
                 "공사비 밴드 대조": e.benchmark_check(inp.total_construction_cost,
                                                inp.area_m2, inp.cover),
                 "편차 함수 없는 항목": no_fn}
            need = _need("actual_load_per_m2", "actual_yield_kg",
                         "actual_energy", "actual_uptime_pct")
            items.append(_item(spec, "부분생성", d, need,
                               "🔴 **보증 지급을 판정하지 않는다** — 기획서 §5.3의 보상은 "
                               "보험·금융 판단이고 1절 밖이다. 이 표는 그 **기술적 전제**"
                               "(설계값 대 실측)까지다. "
                               f"⚠️**{len(no_fn)}개 항목은 엔진에 편차 함수가 없다** — "
                               "만들지 않고 없다고 적는다"))

        elif code == "D25":
            # 🔴 검증 항목은 **엔진이 이미 내는 결과**에서 채운다 — 사람이 손으로
            #    체크박스를 켜는 것이 아니라, 결손이 있으면 그대로 불합격이 된다.
            #    자료가 없어 못 본 항목은 **None(미검증)**이다 — 통과로 세지 않는다.
            _sel = e.select_specs(inp.snow_cm, inp.wind_ms)
            _bc = e.benchmark_check(inp.total_construction_cost, inp.area_m2, inp.cover)
            _pm = e.site_permit_checklist(area_m2=inp.area_m2, cover=inp.cover.value,
                                          land_use_zone=inj.get("land_use_zone"))
            _hv = e.verify_heating_vs_actual(res["heating"]["load_per_m2"],
                                             inp.cover.value)
            _rows = inj.get("doc_rows")
            # 228차 — ★사용자 결정(2026-09-27, B10 ⓑ): `equipment_ks`는 근거 문구
            #   *「KS 적합 선언·재료승인 첨부가 갖춰졌는가」* 그대로 **선언과 첨부 6종
            #   완비를 함께** 본다. 227차까지는 선언만 봐서 문구와 검사가 어긋났다.
            #   판정 기준은 엔진 `equipment_reconcile` 반환(`needs_ks_declaration`·
            #   `attachments_missing`)이다 — 이 계층은 그 둘을 **읽기만** 한다.
            _eq = (None if not inj.get("quoted_models") else
                   e.equipment_reconcile(inj["quoted_models"], inj.get("ks_declared"),
                                         inj.get("attachments_by_model")))
            # 🔴238차 정정(레드팀 29회차 A2): 228차는 *「첨부 미제출 = 불합격」*을 정했는데 그것은
            #   **사용자 결정이 아니라 내 선택**이었다. 이 블록의 원칙 *「자료가 없어 못 본 항목은
            #   None(미검증)」*에 맞춰, **첨부 정보가 아예 없으면 미검증**이다. 첨부를 냈는데 6종이
            #   모자라면 불합격(B10 ⓑ 그대로). 📌239차 — ★B11 **ⓐ 미검증으로 확정**(사용자 결정 2026-09-28).
            _att_given = bool(inj.get("attachments_by_model"))
            _att_short = bool(_eq) and any(r["attachments_missing"] for r in _eq["rows"])
            checks = {
                "design_load": bool(_sel["candidates"]),
                "doc_consistency": (None if not _rows else
                                    e.doc_consistency_check(_rows).counts["OK"]
                                    == len(_rows)),
                "heating_design": _hv["status"] == "정상",
                "cost_band": _bc["status"] == "정상",
                "equipment_ks": (None if _eq is None else
                                 False if _eq["needs_ks_declaration"] else
                                 None if not _att_given else not _att_short),
                "permit": not _pm["missing_inputs"],
                "warranty": e.warranty_period("온실설치") is not None,
            }
            gr = e.ksfid_grade(checks, inj.get("ksfid_thresholds"))
            d = {"등급": gr}
            issued = inj.get("ksfid_issued")
            seq = inj.get("ksfid_seq")
            need25 = []
            # 229차 — ★사용자 결정(2026-09-27): 번호의 연도는 **발급일의 연도**다.
            #   **228차까지**는 `2026`이 박혀 있어 2027년 발급분도 `KSF-2026-…`이 됐다
            #   (238차 정정 — 종전 「226차까지」는 틀렸다).
            #   발급일은 엔진 `ksfid_validity`가 검증·정규화한 ISO 날짜(`issued`)의 **앞 네 자리를
            #   읽는다** — 날짜 계산을 다시 하지 않는다(238차: 「해석하지 않는다」는 과장이었다). 발급일이 없으면 **연도를 모르므로
            #   번호를 만들지 않는다**(지어내지 않는다).
            if issued:
                d["유효기간"] = e.ksfid_validity(issued, inj.get("ksfid_thresholds"))
            if seq is None:
                need25 = need25 + _need("ksfid_seq")
            elif issued:
                d["식별번호"] = e.ksfid_number(inp.region, inp.crop, inp.cover.value,
                                           int(d["유효기간"]["issued"][:4]), seq)
            if not issued:
                need25 = need25 + _need("ksfid_issued")
            # 238차 정정 — 종전엔 미완결이면 `doc_rows`·`quoted_models`를 **이미 냈어도** 달았다
            #   (187차 단순화). 첨부 미제출이 미검증이 되자 「낸 것을 안 냈다」고 보였다 →
            #   **실제로 빠진 입력만** 단다.
            if checks["doc_consistency"] is None:
                need25 = need25 + _need("doc_rows")
            if _eq is None:
                need25 = need25 + _need("quoted_models")
            if _eq is not None and (not _att_given or _att_short):   # 228·238차
                need25 = need25 + _need("attachments_by_model")
            items.append(_item(spec, "생성" if not need25 else "부분생성", d, need25,
                               "🔴 등급은 **검증 항목 통과 수 + 실격 사유**이지 "
                               "**사업 평가가 아니다**. 임계값은 ★사용자 결정이고 "
                               "`ksfid_thresholds`로 덮어쓰면 **등급이 바뀐다** — "
                               "반환의 `rule`이 그것을 드러낸다. 미검증 항목은 "
                               "**통과로 세지 않는다**"))

        elif code == "D26":
            # 🔴 설계값은 엔진이 낸다. **실측은 주입**이고, 없으면 편차를 만들지 않는다.
            # 🔴 `rr.compute`의 heating 요약에는 연료소비량이 없다 — **엔진 함수에서
            #    직접** 받는다(같은 단일 계산 출처다. 이 계층이 다시 계산하는 것이 아니다).
            _hr = e.heating_load(inp.surface_area_m2, inp.cover.value, inp.t_target,
                                 inp.t_min, inp.fr, floor_area_m2=inp.area_m2)
            design = {"yield": e.production_kg(inp.area_m2, inp.base_yield_kg_m2,
                                               inp.fitness_pct),
                      "energy": _hr.fuel_consumption,
                      "uptime": None}
            actual = {"yield": inj.get("actual_yield_kg"),
                      "energy": inj.get("actual_energy"),
                      "uptime": inj.get("actual_uptime_pct")}
            losses = inj.get("perf_losses") or {}
            ready = [k for k in design
                     if design[k] is not None and actual[k] is not None]
            # 🔴 **보험가액이 없어도 편차는 낸다** — 지급 판정과 편차는 다른 일이다.
            _rule = dict(e.PERF_GUARANTEE_RULE)
            _rule.update(inj.get("guarantee_rule") or {})
            _dirs = {c["key"]: c["direction"] for c in e.PERF_GUARANTEE_SPEC}
            gaps = {}
            for k in ready:
                gaps[k] = e.performance_shortfall(design[k], actual[k], _dirs[k],
                                                  _rule["tolerance_pct"])
            d = {"설계값": design, "실측 주입": actual,
                 "판정 가능한 항목": ready, "항목별 편차": gaps}
            n26 = []
            for _sl in ("actual_yield_kg", "actual_energy", "actual_uptime_pct"):
                if inj.get(_sl) is None:
                    n26 = n26 + _need(_sl)
            iv = inj.get("insured_value_won")
            if ready and iv is not None:
                d["판정"] = e.guarantee_assessment(
                    [{"key": k, "design": design[k], "actual": actual[k],
                      "loss_won": losses.get(k)} for k in ready],
                    iv, inj.get("guarantee_rule"))
            elif iv is None:
                n26 = n26 + _need("insured_value_won")
            fi = inj.get("guarantee_fee_inputs")
            if fi:
                d["보증수수료"] = e.guarantee_fee(**fi)
            else:
                n26 = n26 + _need("guarantee_fee_inputs")
            items.append(_item(spec, "생성" if not n26 else "부분생성", d, n26,
                               "🔴 **손실액과 요율은 주입**이다 — 단가·시세를 엔진이 "
                               "만들지 않는다. 🔴**가동률의 설계값은 엔진이 내지 않는다**"
                               "(설계 전제라 주입). 면책·보상비율은 ★사용자 결정이고 "
                               "`guarantee_rule`로 덮어쓰면 **지급 대상이 바뀐다**. "
                               "최종 지급은 보증 계약과 보험사 심사가 정한다"))

        elif code == "D27":
            plan, done = inj.get("progress_plan"), inj.get("progress_done")
            if not plan:
                items.append(_item(spec, "주입대기", None,
                                   _need("progress_plan", "progress_done"),
                                   "계획이 없으면 기성률을 낼 수 없다"))
            else:
                items.append(_item(spec, "생성" if done else "부분생성",
                                   e.progress_certification(plan, done or {}),
                                   [] if done else _need("progress_done"),
                                   "🔴 **기성률을 낼 뿐 지급을 승인하지 않는다** — "
                                   "기성 인정과 대출 인출은 발주처·대출기관의 판단이다"))

        else:                                       # 카탈로그에 있으나 조립되지 않은 항목
            items.append(_item(spec, "미조립", None, [], "조립기가 없다"))

    by_status = dict(_Counter(it["status"] for it in items))
    needs_all = []
    for it in items:
        for n in it["needs"]:
            if n["slot"] not in [x["slot"] for x in needs_all]:
                needs_all.append(n)
    return {"case_id": case["case_id"], "title": case["title"],
            "items": items, "status_counts": by_status,
            "open_injections": needs_all,
            "note": ("🔴 **189차 정정** — 181차의 *「이 패키지는 판정하지 않는다」*는 "
                     "187·188차에 **등급·지급 판정이 들어와 더 이상 참이 아니다**. "
                     "지금 참인 것: **주입이 없는 칸은 비어 있는 채로 드러나고**, "
                     "**시세성·판단성 값은 고객이 준 것만 쓰며**, 판정하는 칸"
                     "(`D25`·`D26`)은 **명시된 규칙을 그대로 적용한 결과**와 "
                     "**항목별 근거 행**을 함께 낸다. 투자·보험·시공 판정은 하지 않는다")}


def coverage() -> dict:
    """패키지가 이름을 대고 쓰는 엔진 함수(가드가 실재를 확인한다)."""
    used = set()
    for spec in PACKAGE_SPEC:
        used.update(spec["engine"])
    return {"declared": sorted(used), "items": len(PACKAGE_SPEC)}
