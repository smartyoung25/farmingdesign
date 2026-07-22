"""
근거대장 드리프트 가드
- 엔진데이터_레지스트리.json 의 value 가 엔진의 실제 상수와 일치하는지 검증.
- 목적: 레지스트리가 '제2의 출처'로 갈라지지 않게 함. 엔진이 값을 바꾸면 이 테스트가 깨져
  레지스트리(근거·기준시점)를 함께 갱신하도록 강제한다.
실행: pytest test_registry.py -q
"""
import json, os
import smartfarm_engine as e

REG = json.load(open(os.path.join(os.path.dirname(__file__), "엔진데이터_레지스트리.json"),
                    encoding="utf-8"))
C = REG["constants"]


def _norm(v):
    if isinstance(v, tuple): return list(v)
    if isinstance(v, dict): return {k: _norm(x) for k, x in v.items()}
    return v


def test_simple_dict_and_scalar_constants():
    for key in ["U_VALUE", "FR_TABLE", "FUEL_LHV", "TOTAL_PYEONG_PRICE", "STRUCTURE_ONLY_PYEONG"]:
        eng = _norm(getattr(e, C[key]["engine_attr"]))
        assert eng == C[key]["value"], f"{key}: 엔진={eng} vs 레지스트리={C[key]['value']}"


def test_benchmark_bands():
    eng = {c.value: list(v) for c, v in e.BENCHMARK_BANDS.items()}
    assert eng == C["BENCHMARK_BANDS"]["value"]


def test_counts():
    assert len(e.ACTUALS) == C["ACTUALS_COUNT"]["value"]
    assert len(e.SPEC_TABLE) == C["SPEC_COUNT"]["value"]


def test_overhead_rates():
    r = e.OverheadRates()
    want = C["OVERHEAD_RATES"]["value"]
    for field, val in want.items():
        assert getattr(r, field) == val, f"OverheadRates.{field}: {getattr(r,field)} != {val}"


def test_env_weights():
    w = C["ENV_WEIGHTS"]["value"]
    # env_fitness(광,온,습,CO2) 단위입력으로 가중치 복원 (×100 스케일)
    assert e.env_fitness(1, 0, 0, 0) == w["light"] * 100
    assert e.env_fitness(0, 1, 0, 0) == w["temp"] * 100
    assert e.env_fitness(0, 0, 1, 0) == w["humid"] * 100
    assert e.env_fitness(0, 0, 0, 1) == w["co2"] * 100


def test_finance_defaults():
    # finance(revenue, opex, capex, useful_life=15, discount_rate=0.05, years=10,
    #         subsidy_rate=0.0, land_cost=0.0)  # land_cost 2026-07-16 추가
    ul, dr, yr, _sub, land = e.finance.__defaults__
    w = C["FINANCE_DEFAULTS"]["value"]
    assert (ul, dr, yr, land) == (w["useful_life"], w["discount_rate"], w["years"], w["land_cost"])


# ── 2026-07-16 추가: CAPEX 카테고리 분해 / OPEX 제안값 / 입지 매핑 드리프트 가드 ──
def test_capex_category_observed_range():
    eng = _norm(e.CAPEX_CATEGORY_OBSERVED_RANGE)
    assert eng == C["CAPEX_CATEGORY_OBSERVED_RANGE"]["value"]


def test_capex_case_chunks():
    eng = _norm(e.CAPEX_CASE_CHUNKS)
    assert eng == C["CAPEX_CASE_CHUNKS"]["value"]
    # 원본 문서 합계와 원단위 일치(레지스트리 source 주석의 숫자와 대조)
    assert sum(e.CAPEX_CASE_CHUNKS["우민재"].values()) == 456_158_140
    assert sum(e.CAPEX_CASE_CHUNKS["최혁진"].values()) == 694_575_784


def test_opex_item_categories():
    # 2026-07-21: Step3(data.go.kr 15069669) CSV 확보 완료 — 제안값에서 농진청
    # 공식 코드 기반 확정값으로 승격, 시설원예 관련 25항목(직접18+간접7)
    eng = [[it.category, it.name, it.code] for it in e.OPEX_ITEM_CATEGORIES]
    assert eng == C["OPEX_ITEM_CATEGORIES"]["value"]
    assert len(e.OPEX_ITEM_CATEGORIES) == 25


def test_region_design_load_matches_registry():
    # 2026-07-21: 농림축산식품부 고시 제2025-108호(2025.10.31 시행)로 전면 갱신 —
    # 172개 지역 전량 대조(2014-78호 기준 값은 폐기)
    assert e.REGION_DESIGN_LOAD == C["REGION_DESIGN_LOAD"]["value"]
    assert len(e.REGION_DESIGN_LOAD) == 172


# ── 2026-07-16 추가2: 13개 상위 CAPEX 카테고리(총사업비 관점) 드리프트 가드 ──
def test_capex_major_categories():
    eng = [list(t) for t in e.CAPEX_MAJOR_CATEGORIES]
    assert eng == C["CAPEX_MAJOR_CATEGORIES"]["value"]


def test_capex_major_evidence_status():
    assert e.CAPEX_MAJOR_EVIDENCE_STATUS == C["CAPEX_MAJOR_EVIDENCE_STATUS"]["value"]


def test_capex_major_case_chunks():
    eng = _norm(e.CAPEX_MAJOR_CASE_CHUNKS)
    assert eng == C["CAPEX_MAJOR_CASE_CHUNKS"]["value"]


def test_capex_major_unclassified():
    assert e.CAPEX_MAJOR_UNCLASSIFIED == C["CAPEX_MAJOR_UNCLASSIFIED"]["value"]


# ── RFQ 사양서/견적 정합 드리프트 가드 ──
def test_rfq_required_categories_default():
    assert e.RFQ_REQUIRED_CATEGORIES_DEFAULT == C["RFQ_REQUIRED_CATEGORIES_DEFAULT"]["value"]


# ── 공정표(품셈) 드리프트 가드 ──
def test_pumsem_items():
    eng = [[it.category, it.name, it.unit, it.labor_per_unit, it.equipment_hours_per_unit]
           for it in e.PUMSEM_ITEMS]
    assert eng == C["PUMSEM_ITEMS"]["value"]
    assert len(e.PUMSEM_ITEMS) == 64


# ── 기자재DB(CSV) 드리프트 가드 ──
def test_equipment_db_csv_files_match_registered_row_counts():
    expected = C["EQUIPMENT_DB_META"]["value"]["csv_row_counts"]
    for filename, expected_rows in expected.items():
        rows = e._load_csv_rows(filename)
        assert len(rows) == expected_rows, f"{filename}: {len(rows)} != {expected_rows}"


# ── 보조사업 체크리스트 드리프트 가드 ──
def test_subsidy_application_procedure():
    eng = [[s.step_no, s.title, s.description, s.reference] for s in e.SUBSIDY_APPLICATION_PROCEDURE]
    assert eng == C["SUBSIDY_APPLICATION_PROCEDURE"]["value"]


def test_subsidy_program_types_reference():
    assert e.SUBSIDY_PROGRAM_TYPES_REFERENCE == C["SUBSIDY_PROGRAM_TYPES_REFERENCE"]["value"]


# ── 2026-07-22 추가: SPEC_TABLE 전면 확장(32→249종, 2025-108호) 드리프트 가드 ──
def test_spec_table_matches_registry():
    eng = [[s.name, s.form, s.width_m, s.snow_cm, s.wind_ms, s.height_m, s.ridge_height_m,
            s.registered_year, s.developer, s.crop, s.rafter_spec] for s in e.SPEC_TABLE]
    assert eng == C["SPEC_TABLE"]["value"]
    assert len(e.SPEC_TABLE) == 249
