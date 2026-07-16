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


def test_opex_item_categories_proposed():
    assert e.OPEX_ITEM_CATEGORIES_PROPOSED == C["OPEX_ITEM_CATEGORIES_PROPOSED"]["value"]


def test_region_design_load_empty_until_p0b():
    # P0-b(law.go.kr 별표 확보) 완료 전까지는 비어있는 게 정상 상태
    assert e.REGION_DESIGN_LOAD == C["REGION_DESIGN_LOAD"]["value"]


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
