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
    # 리스트 재귀 추가(2026-08-18): SUPERVISION_FEE_RATE_TABLE이 '튜플의 리스트'라
    # 내부 튜플까지 JSON 리스트와 맞추려면 리스트도 원소 단위로 정규화해야 한다
    if isinstance(v, (tuple, list)): return [_norm(x) for x in v]
    if isinstance(v, dict): return {k: _norm(x) for k, x in v.items()}
    return v


def test_all_entries_have_render_required_fields():
    # P3-18에서 발견: 신규 등록 항목에 axis/desc가 빠지면 build_site 근거대장이
    # KeyError로 죽는데, 당시 파이프라인이 stderr를 삼켜 조용히 실패했다(B4~B8
    # 커밋의 "근거대장 자동 반영" 보고가 사실과 달랐던 원인 — 정정 완료).
    # 등록 시점에 잡히도록 렌더 필수 필드를 가드한다.
    for key, ent in C.items():
        for field in ("axis", "desc", "source", "status", "value"):
            assert field in ent, f"{key}: 레지스트리 항목에 '{field}' 필드 누락 — 근거대장 렌더가 죽는다"


def test_simple_dict_and_scalar_constants():
    for key in ["U_VALUE", "U_DESIGN", "FR_TABLE", "FUEL_LHV", "TOTAL_PYEONG_PRICE", "STRUCTURE_ONLY_PYEONG",
                "WARRANTY_STATUTORY", "ELECTRICAL_PUMSEM_LUMP_WON_PER_HA",  # B4~B8 확장(2026-08-17)
                "EQUIPMENT_SERVICE_LIFE_REFERENCE",  # LCC 내용연수(2026-08-18)
                "STRUCTURE_SERVICE_LIFE_STATUTORY",  # 구조체 법정 내용연수(2026-08-18)
                "SUPERVISION_FEE_RATE_TABLE",  # 감리비 대가요율(2026-08-18, P1-6 잔여)
                "CAPEX_MAJOR_KNOWN_TOTALS"]:  # 표본 known_total 단일 출처(2026-08-18 53차, 레드팀 4회차 F8)
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


def test_source_refs_point_to_existing_files():
    # 42차: 엔진 상수 → 원문 기계가독 역참조(source_refs) 드리프트 가드.
    # 원문 확보 완료 상수만 등록(없는 근거를 만들지 않음 — 미검증 상수는 필드 생략).
    base = os.path.dirname(os.path.abspath(__file__))
    with_refs = {k for k, c in C.items() if c.get("source_refs")}
    # 42차 등록 9개는 유지돼야 한다(줄어들면 역참조 회귀)
    expected = {"WARRANTY_STATUTORY", "SUPERVISION_FEE_RATE_TABLE",
                "STRUCTURE_SERVICE_LIFE_STATUTORY", "EQUIPMENT_SERVICE_LIFE_REFERENCE",
                "ACTUALS_COUNT", "CAPEX_MAJOR_CASE_CHUNKS", "CAPEX_CATEGORY_OBSERVED_RANGE",
                "STRUCTURE_ONLY_PYEONG", "BENCHMARK_BANDS"}
    assert expected <= with_refs, expected - with_refs
    for key in sorted(with_refs):
        for r in C[key]["source_refs"]:
            # match(44차 F5): 파일이 값을 '직접' 담는지(생략=exact) / 근접(near) / 부분(partial)
            assert set(r) <= {"file", "page", "chunk_id", "note", "match"}, (key, r)
            assert r.get("match", "exact") in ("exact", "near", "partial"), (key, r)
            assert r.get("file"), (key, r)
            assert os.path.isfile(os.path.join(base, r["file"])), \
                (key, r["file"], "역참조 원문 소실 — 이동·개명 시 여기서 잡힌다")
    # 44차 F5 고정: 근접·부분 근거는 exact로 위장하지 않는다
    assert any(r.get("match") == "near" for r in C["ACTUALS_COUNT"]["source_refs"])
    assert all(r.get("match") == "partial" for r in C["WARRANTY_STATUTORY"]["source_refs"])


def test_status_vocabulary_is_normalized_enum():
    # 45차(사용자 승인): status는 8종 enum만 — 자유 서술은 status_note로 분리.
    # 기계 게이팅(46차 감사)의 전제. legend와 실사용의 괴리(구 24종)를 재발 방지.
    ENUM = ("실측", "부분실측", "법정기준", "공공기준", "참고기준", "추정", "확인요망", "미검증")
    assert set(REG["status_legend"]) == set(ENUM)
    for key, ent in C.items():
        assert ent["status"] in ENUM, (key, ent["status"])
        if "status_note" in ent:
            assert isinstance(ent["status_note"], str) and ent["status_note"], key
    # 44차 F2 계열 정직성 고정: 원문 미대조가 남은 ACTUALS는 실측을 자칭하지 않는다
    assert C["ACTUALS_COUNT"]["status"] == "부분실측"
    # 69차: TOTAL_PYEONG_PRICE는 원출처(내재해형 고시 예정공사비/한국농업시설협회)를
    # 확보하고 33종 전 행을 검산 재현했으나 **미검증→확인요망**까지만 간다 —
    # 33종 중 실측된 종은 0(전량 단일 2차자료 전사)이라 '부분실측'("일부 표본만
    # 실측")은 과대이고, 포함 공종 범위도 미확정이다(13회차 F3 — 격상 시 감사
    # ④범주에서 행이 사라지는 부작용도 확인돼 되돌림).
    assert C["TOTAL_PYEONG_PRICE"]["status"] == "확인요망"
    assert C["WARRANTY_STATUTORY"]["status"] == "법정기준"


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
