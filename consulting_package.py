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
     "engine": ["siting_lookup", "siting_design_load", "design_outdoor_temp",
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
                "opex_breakdown", "improvement_roi"]},
    {"code": "D22", "title": "컨설팅 대가 산출", "stage": "④타당성검증", "targets": ["시설"],
     "engine": ["consulting_fee_estimate", "design_supervision_fee_reference"]},
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
    "winter_months": "동절기 개월 정의 — ★`D-9` 결정 대기(`mean_wind`가 기본값을 두지 않는다)",
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
     "found": "2차", "where": "KS X 3265~3267·3279 · KS B 7955 · KS B 7956-1~2 (농진원 표준확산사업)",
     "blocked": "★ 표준번호 등재 — 전체 목록·종수를 **확인하지 못했다**(사업 사이트 403)"},
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
                       "밴드·요율은 판단성·시세성이라 가져오지 않았다"),
            "note": ("🔴분류이지 판정이 아니다 — 순위·등급·추천을 만들지 않는다. "
                     "기능과 stage 6단계는 1:1이 아니라 교차한다"
                     "(F2 시방이 ①·②·⑥에 흩어져 있다)")}


JUDGMENT_CODES: tuple = ("D25", "D26", "D27")


def judgment_split(items: list) -> dict:
    """산출물을 **본문 / 판정 부록**으로 가른다(계산하지 않는다 — 분류뿐이다)."""
    return {"body": [x for x in items if x["code"] not in JUDGMENT_CODES],
            "appendix": [x for x in items if x["code"] in JUDGMENT_CODES]}


def build_package(case: dict, injections: dict = None) -> dict:
    """케이스 1건 → D1~D20 패키지(결정론).

    injections: 시세성·고객문서 주입값. 없으면 그 산출물은 `주입대기`로 남는다 —
    🔴 **비어 있는 것을 채우지 않는다.**
    """
    if not isinstance(case, dict) or not case.get("input"):
        raise ValueError("case가 비어 있거나 input이 없다")
    inj = dict(injections or {})
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
                 "난방 설계외기온": e.design_outdoor_temp(region),
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
                d["4축 정합"] = {"집계": rep.counts, "행": len(rep.rows)}
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
                         "온실신축 지침에는 **견적 조항이 없다**(이견 ③ 닫힘)"})
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
                                   e.equipment_reconcile(qm, inj.get("ks_declared")), [],
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
            d = {"감리 대가 참고": e.design_supervision_fee_reference(
                 inp.total_construction_cost)}
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
            items.append(_item(spec, "부분생성", d,
                               _need("dd_documents"),
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
            checks = {
                "design_load": bool(_sel["candidates"]),
                "doc_consistency": (None if not _rows else
                                    e.doc_consistency_check(_rows).counts["OK"]
                                    == len(_rows)),
                "heating_design": _hv["status"] == "정상",
                "cost_band": _bc["status"] == "정상",
                "equipment_ks": (None if not inj.get("quoted_models") else
                                 not e.equipment_reconcile(
                                     inj["quoted_models"],
                                     inj.get("ks_declared"))["needs_ks_declaration"]),
                "permit": not _pm["missing_inputs"],
                "warranty": e.warranty_period("온실설치") is not None,
            }
            gr = e.ksfid_grade(checks, inj.get("ksfid_thresholds"))
            d = {"등급": gr}
            issued = inj.get("ksfid_issued")
            seq = inj.get("ksfid_seq")
            need25 = []
            if seq is None:
                need25 = need25 + _need("ksfid_seq")
            else:
                d["식별번호"] = e.ksfid_number(inp.region, inp.crop, inp.cover.value,
                                           2026, seq)
            if issued:
                d["유효기간"] = e.ksfid_validity(issued, inj.get("ksfid_thresholds"))
            else:
                need25 = need25 + _need("ksfid_issued")
            if not gr["complete"]:
                need25 = need25 + _need("doc_rows", "quoted_models")
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
