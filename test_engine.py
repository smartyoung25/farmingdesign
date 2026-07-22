"""
SmartFarm 엔진 회귀 테스트
- 실측 벤치마크(현재 7건)가 각 피복 밴드 안에 들어오는지
- 규격선정·난방 이중검증·재무지표·유형분기 로직 검증
실행: pytest test_engine.py -v   (또는 python test_engine.py)
"""
import smartfarm_engine as e


# ── 1. 실측 벤치마크 밴드 검증 (현재 7건) ───────────────────────────
def test_all_actuals_within_band():
    for name, area, total, cover in e.ACTUALS:
        r = e.benchmark_check(total, area, cover)
        assert r["status"] in ("정상", "경계"), \
            f"{name}: {r['unit_won_m2']}원/㎡ 밴드이탈 {r['band']}"


def test_benchmark_flags_gross_error():
    # 명백한 과소 견적은 경고로 잡혀야 함
    r = e.benchmark_check(50_000_000, 3000, e.Cover.FILM)  # 16,667원/㎡
    assert r["status"] == "경고(밴드이탈)"


# ── 2. 규격 선정 (E2) ────────────────────────────────────────
def test_spec_selection_basic():
    res = e.select_specs(region_snow_cm=30, region_wind_ms=35)
    # 26종 중 충족 규격이 존재하고, 형식별 최소사양이 잡혀야
    assert len(res["candidates"]) >= 10
    assert "단동" in res["min_by_form"]
    assert "연동" in res["min_by_form"]


def test_spec_selection_rejects_understrength():
    # 폭설지역(적설심 60): 충족 규격이 급감해야
    res = e.select_specs(region_snow_cm=60, region_wind_ms=45)
    for s in res["candidates"]:
        assert s.snow_cm >= 60 and s.wind_ms >= 45


# ── 2-1. SPEC_TABLE 전면 확장(32→249종, 2025-108호) 회귀 (2026-07-22) ──────
def test_spec_table_form_counts_match_source_sheets():
    # 농사로 마스터 xlsx 시트별 모델수(인삼·버섯 제외)와 정확히 일치해야
    from collections import Counter
    counts = Counter(s.form for s in e.SPEC_TABLE)
    assert counts == {"연동": 81, "단동": 157, "광폭": 11}
    assert len(e.SPEC_TABLE) == 249


def test_spec_table_old_32_values_are_subset_of_new_249():
    # 2014-78호 기준 옛 32종의 (form, snow_cm, wind_ms) 값이 새 249종 안에
    # 전량 그대로 존재해야 한다 — REGION_DESIGN_LOAD와 달리 이번 확장은
    # "틀린 값을 고치는" 게 아니라 "맞는 32종에 217종을 추가하는" 것이었으므로.
    old_32 = [
        ("연동", 53, 40), ("연동", 57, 36), ("연동", 55, 40), ("연동", 55, 40), ("연동", 55, 40),
        ("단동", 50, 35), ("단동", 50, 35), ("단동", 50, 36), ("단동", 48, 37),
        ("단동", 41, 32), ("단동", 42, 35), ("단동", 37, 33), ("단동", 41, 35),
        ("단동", 30, 32), ("단동", 28, 39), ("단동", 27, 41), ("단동", 25, 33),
        ("단동", 26, 36), ("단동", 30, 28), ("단동", 29, 27), ("단동", 27, 27),
        ("단동", 30, 28), ("단동", 50, 40), ("단동", 55, 42),
        ("광폭", 33, 40), ("광폭", 35, 40), ("광폭", 25, 28), ("광폭", 23, 28),
        ("광폭", 23, 29), ("광폭", 23, 27), ("광폭", 20, 27), ("광폭", 20, 27),
    ]
    new_set = {(s.form, s.snow_cm, s.wind_ms) for s in e.SPEC_TABLE}
    for form, snow, wind in old_32:
        assert (form, snow, wind) in new_set, f"옛 규격 {form}/{snow}/{wind}이 새 SPEC_TABLE에서 사라짐"


# ── 3. 난방부하 이중검증 (E7/C7) ─────────────────────────────
def test_heating_dual_verify_glass():
    # 유리온실 근사 입력 → 면적당 부하가 실측(231)과 같은 자릿수
    hr = e.heating_load(surface_area_m2=5000, cover="유리",
                        t_target=10, t_min=-7.8, fr=0.7,
                        floor_area_m2=3456)
    v = e.verify_heating_vs_actual(hr.load_per_m2, "유리")
    assert v["status"] == "정상", v


# ── 3-1. 난방부하 max/period U 분리 (2026-07-20 구조개선) ─────
def test_heating_load_u_default_stays_coupled():
    # u_design/u_period 미지정 시 기존 동작(둘 다 U_VALUE[cover])과 완전히 동일해야
    hr_default = e.heating_load(surface_area_m2=5000, cover="필름",
                                t_target=10, t_min=-7.8, fr=0.7)
    hr_explicit = e.heating_load(surface_area_m2=5000, cover="필름",
                                 t_target=10, t_min=-7.8, fr=0.7,
                                 u_design=e.U_VALUE["필름"], u_period=e.U_VALUE["필름"])
    assert hr_default.max_load_kcal_h == hr_explicit.max_load_kcal_h
    assert hr_default.fuel_consumption == hr_explicit.fuel_consumption


def test_heating_load_u_design_period_separation():
    # 서로 다른 u_design/u_period를 주면 max_load와 fuel_consumption이 독립적으로 반응해야
    base = e.heating_load(surface_area_m2=5000, cover="필름",
                          t_target=10, t_min=-7.8, fr=0.7,
                          u_design=2.66, u_period=2.66)
    higher_design_only = e.heating_load(surface_area_m2=5000, cover="필름",
                                        t_target=10, t_min=-7.8, fr=0.7,
                                        u_design=5.7, u_period=2.66)
    # u_design만 올리면 max_load(설비용량)는 커지되 fuel_consumption(연료소비)은 불변
    assert higher_design_only.max_load_kcal_h > base.max_load_kcal_h
    assert higher_design_only.fuel_consumption == base.fuel_consumption


# ── 3-2. FR_TABLE 방향성 수정 (2026-07-20) ────────────────────
def test_curtain_exposure_ratio_inverts_savings_rate():
    # 열절감률(클수록 좋음) → 노출비율(작을수록 좋음)로 뒤집혀야
    assert e.curtain_exposure_ratio("PO단일") == 1 - e.FR_TABLE["PO단일"]
    assert e.curtain_exposure_ratio("이중커튼") == 1 - e.FR_TABLE["이중커튼"]
    # 보온이 더 좋은 커튼일수록 노출비율은 더 작아야(방향 반전 확인)
    assert e.curtain_exposure_ratio("이중커튼") < e.curtain_exposure_ratio("다겹보온")
    assert e.curtain_exposure_ratio("다겹보온") < e.curtain_exposure_ratio("PO단일")


def test_curtain_exposure_ratio_unknown_curtain_raises():
    import pytest
    with pytest.raises(ValueError):
        e.curtain_exposure_ratio("존재하지않는커튼")


def test_heating_load_with_curtain_exposure_ratio_direction():
    # 실제 heating_load()에 연결했을 때도 "보온 잘 될수록 부하가 작다"가 성립해야
    def load_for(curtain):
        fr = e.curtain_exposure_ratio(curtain)
        return e.heating_load(surface_area_m2=5000, cover="유리",
                              t_target=10, t_min=-7.8, fr=fr).max_load_kcal_h

    assert load_for("이중커튼") < load_for("다겹보온") < load_for("PO단일")


# ── 4. 골조 단가 정의 구분 (이중계산 방지) ───────────────────
def test_structure_vs_total_price_distinct():
    area_py = 1000
    total = e.greenhouse_total_estimate("07-연동-1", area_py)   # 온실전체
    struct = e.structure_only_estimate(area_py)                 # 골조단독
    # 온실전체가 골조단독보다 훨씬 커야(이중계산이면 같아짐)
    assert total > struct * 2


# ── 5. 재무지표 (F5/F6) ──────────────────────────────────────
def test_finance_positive_case():
    f = e.finance(revenue=332_640_000, opex=186_420_000,
                  capex=702_030_000, subsidy_rate=0.5)
    assert f.operating_profit > 0
    assert f.roi > 0
    assert f.payback_years and f.payback_years > 0
    # 보조금 반영 실질ROI가 명목ROI보다 커야
    assert f.real_roi_after_subsidy > f.roi


def test_npv_irr_consistency():
    cfs = [-1000, 300, 300, 300, 300, 300]
    n = e.npv(0.05, cfs)
    r = e.irr(cfs)
    assert r is not None
    # IRR 할인율에서 NPV≈0
    assert abs(e.npv(r, cfs)) < 1.0


def test_env_fitness_and_yield():
    fit = e.env_fitness(light_r=1.0, temp_r=1.0, humid_r=1.0, co2_r=1.0)
    assert 99 <= fit <= 101              # 완전 최적 ≈ 100%
    assert e.yield_adjustment(fit) == 0.0
    assert e.yield_adjustment(55) == -0.40


# ── 6. 리뉴얼 개선 ROI (F7) ─────────────────────────────────
def test_improvement_roi():
    r = e.improvement_roi(annual_saving=12_000_000, invest=36_000_000)
    assert abs(r["roi"] - 1/3) < 1e-6
    assert abs(r["payback"] - 3.0) < 1e-6


# ── 7. 단지 경제성 (F8) ─────────────────────────────────────
def test_cluster_economics():
    c = e.cluster_economics(n_farms=5, per_farm_capex=600_000_000,
                            shared_capex=750_000_000,
                            per_farm_opex=100_000_000)
    assert c["per_farm_share"] == 150_000_000
    # 보조 70% 반영 후 공동분담 급감 (부동소수 허용)
    assert abs(c["per_farm_share_after_subsidy"] - 45_000_000) < 1
    # 규모의 경제로 OPEX 감소
    assert abs(c["per_farm_opex_after_scale"] - 85_000_000) < 1


# ── 8. CAPEX 카테고리 분해 (2026-07-16, 스마트팜스펙 실측 청킹) ─────
def test_capex_breakdown_umj_reconciles_to_source():
    # 우민재 원본 내역서 순공사비 합계(재+노+경) = 456,158,140원과 원단위 일치해야
    cb = e.capex_breakdown(e.CAPEX_CASE_CHUNKS["우민재"])
    assert cb.total == 456_158_140
    assert abs(sum(cb.shares_pct.values()) - 100.0) < 0.5  # 반올림 오차만 허용


def test_capex_breakdown_chj_reconciles_to_source():
    # 최혁진 원본 내역서 순공사비 합계 = 694,575,784원과 원단위 일치해야
    cb = e.capex_breakdown(e.CAPEX_CASE_CHUNKS["최혁진"])
    assert cb.total == 694_575_784
    assert abs(sum(cb.shares_pct.values()) - 100.0) < 0.5


def test_capex_breakdown_missing_category_defaults_zero():
    cb = e.capex_breakdown({"frame": 100_000_000})
    assert cb.total == 100_000_000
    assert cb.shares_pct["frame"] == 100.0
    assert cb.items["electrical_aux"] == 0.0


def test_capex_observed_range_reference_not_pass_fail():
    # 관측범위는 정상/경고를 가르지 않는다 — 벗어나도 함수는 에러를 내지 않음
    extreme = {"frame": 900_000_000, "scaffold": 1}
    cb = e.capex_breakdown(extreme)
    assert "frame" in cb.out_of_observed_range  # 참고 표시는 되지만
    assert cb.total > 0                          # 계산 자체는 그대로 진행


# ── 9. OPEX 항목 분해 (2026-07-16, 제안값) ─────────────────────
def test_opex_breakdown_total_unchanged():
    # 원채원 케이스 기존 lump-sum(186,420,000원)을 항목 분해해도 총액은 불변
    items = {"종묘비": 40_000_000, "비료비": 15_000_000, "광열동력비": 60_000_000}
    ob = e.opex_breakdown(items, known_total=186_420_000)
    assert ob.total == 186_420_000
    assert ob.unclassified == 186_420_000 - sum(items.values())
    assert ob.unclassified >= 0


def test_opex_breakdown_full_classification_zero_unclassified():
    items = {"종묘비": 100}
    ob = e.opex_breakdown(items, known_total=100)
    assert ob.unclassified == 0


def test_opex_breakdown_rejects_overclassification():
    import pytest
    with pytest.raises(ValueError):
        e.opex_breakdown({"종묘비": 200}, known_total=100)


# ── 9-1. 영업 손익분기 (2026-07-21, Step6 리포트용) ──────────
def test_operating_breakeven_basic():
    r = e.operating_breakeven(opex=186_420_000, price_won_per_kg=2500)
    assert r.breakeven_revenue_won == 186_420_000
    assert r.breakeven_kg == 186_420_000 / 2500


def test_operating_breakeven_rejects_nonpositive_price():
    import pytest
    with pytest.raises(ValueError):
        e.operating_breakeven(opex=100, price_won_per_kg=0)


# ── 10. 입지 지역 매핑 (2026-07-21, 2025-108호 개정 반영으로 전면 갱신) ──
def test_siting_design_load_returns_none_for_unmapped_region():
    # 매핑표에 없는 지명 — 예외 없이 None만 반환해야
    assert e.siting_design_load("충남 임의지역") is None


def test_siting_design_load_matches_existing_case_regions():
    # 케이스 region 필드는 자유서술형("강원(춘천)", "충남 천안(성환읍)") — 부분일치로 조회
    # 2025-108호 개정으로 춘천 wind_ms 32→34(snow_cm은 32로 불변), 천안은 무변경
    assert e.siting_design_load("강원(춘천)") == {"snow_cm": 32, "wind_ms": 34}
    assert e.siting_design_load("충남 천안(성환읍)") == {"snow_cm": 26, "wind_ms": 28}


def test_siting_design_load_exact_match_for_disambiguated_duplicates():
    # 고성·광주는 지명이 두 도에 중복돼 괄호로 구분 — 정확일치만 허용
    # 2025-108호 개정으로 고성(강원)은 종전 "40cm 이상" 뭉뚱그림이 실측 79cm로 구체화,
    # 광주광역시는 36→38cm로 상향. 고성(경남)·광주(경기)는 무변경
    assert e.siting_design_load("고성(강원)") == {"snow_cm": 79, "wind_ms": 43}
    assert e.siting_design_load("고성(경남)") == {"snow_cm": 20, "wind_ms": 38}
    assert e.siting_design_load("광주(경기)") == {"snow_cm": 24, "wind_ms": 26}
    assert e.siting_design_load("광주광역시") == {"snow_cm": 38, "wind_ms": 32}


def test_siting_design_load_ambiguous_duplicate_name_returns_none():
    # 광역 힌트 없는 "고성"만으로는 강원/경남 중 어느 쪽인지 판단 근거가 없다 — 지어내지 않음
    assert e.siting_design_load("고성") is None


def test_region_design_load_count():
    assert len(e.REGION_DESIGN_LOAD) == 172


def test_siting_lookup_returns_none_for_unmapped_region():
    assert e.siting_lookup("충남 임의지역") is None


def test_siting_lookup_matches_manual_select_specs_chain():
    # siting_lookup()은 siting_design_load()+select_specs()를 그대로 이은 것 — 수동 체이닝과 동일해야
    load = e.siting_design_load("강원(춘천)")
    manual = e.select_specs(load["snow_cm"], load["wind_ms"])
    result = e.siting_lookup("강원(춘천)")
    assert result["region_snow_cm"] == load["snow_cm"]
    assert result["region_wind_ms"] == load["wind_ms"]
    assert result["candidates"] == manual["candidates"]
    assert result["min_by_form"] == manual["min_by_form"]


def test_siting_lookup_respects_form_filter():
    result = e.siting_lookup("충남 천안(성환읍)", form="연동")
    assert set(result["min_by_form"].keys()) <= {"연동"}
    assert all(c.form == "연동" for c in result["candidates"])


def test_siting_lookup_without_form_covers_multiple_forms():
    # form 미지정 시 select_specs()처럼 연동/단동/광폭 후보를 형식별로 모두 반환
    result = e.siting_lookup("강원(춘천)")
    assert set(result["min_by_form"].keys()) == set(e.select_specs(32, 34)["min_by_form"].keys())


# ── 11. CAPEX 13개 상위 카테고리 (2026-07-16, 사용자 제안 채택) ─────
def test_capex_major_breakdown_umj_reconciles_to_source():
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["우민재"],
                                  known_total=456_158_140)
    assert cb.total == 456_158_140
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["우민재"]
    assert sum(cb.items.values()) + cb.unclassified == 456_158_140


def test_capex_major_breakdown_chj_reconciles_to_source():
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["최혁진"],
                                  known_total=694_575_784)
    assert cb.total == 694_575_784
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["최혁진"]
    assert sum(cb.items.values()) + cb.unclassified == 694_575_784


def test_capex_major_breakdown_dh_reconciles_to_source():
    # 2026-07-21 추가 — 이두희 원가계산서 14개 세부공종 합계열 총합(433,606,460)이
    # known_total. unclassified는 '5-3.베드설치'(101,301,410, 9/13카테고리 어디에도
    # 안 맞아 미분류로 남긴 항목)와 정확히 일치해야 한다.
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["이두희"],
                                  known_total=433_606_460)
    assert cb.total == 433_606_460
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["이두희"]
    assert sum(cb.items.values()) + cb.unclassified == 433_606_460


def test_capex_major_breakdown_unmapped_categories_default_zero():
    # 근거 없는 7개(부대시설·기자재구매·설계감리비·부지조성비·예비비·부지매입비, 8번 등)는 0
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["우민재"], known_total=456_158_140)
    for k in ("auxiliary_facility", "thermal_storage_insulation", "equipment_procurement",
              "design_supervision_fee", "site_preparation", "contingency", "land_acquisition"):
        assert cb.items[k] == 0.0


def test_capex_major_breakdown_rejects_overclassification():
    import pytest
    with pytest.raises(ValueError):
        e.capex_major_breakdown({"greenhouse_structure": 200}, known_total=100)


def test_capex_major_categories_count_and_keys():
    assert len(e.CAPEX_MAJOR_CATEGORIES) == 13
    keys = [k for k, _, _ in e.CAPEX_MAJOR_CATEGORIES]
    assert keys[-1] == "land_acquisition"  # 13번 부지매입비가 마지막


# ── 12. 부지매입비는 감가상각에서 제외 (2026-07-16) ──────────────
def test_finance_land_cost_excluded_from_depreciation():
    f_no_land = e.finance(revenue=500_000_000, opex=200_000_000, capex=1_000_000_000,
                          useful_life=10, land_cost=0.0)
    f_with_land = e.finance(revenue=500_000_000, opex=200_000_000, capex=1_000_000_000,
                            useful_life=10, land_cost=200_000_000)
    assert abs(f_no_land.depreciation - 100_000_000) < 1e-6      # 1,000,000,000/10
    assert abs(f_with_land.depreciation - 80_000_000) < 1e-6     # (1,000,000,000-200,000,000)/10
    assert f_with_land.depreciation < f_no_land.depreciation
    # 토지비를 감가상각에서 뺀 만큼 영업이익이 늘어나 ROI가 개선되어야
    assert f_with_land.roi > f_no_land.roi


def test_finance_default_land_cost_zero_preserves_regression():
    # land_cost 기본값 0 — 기존 원채원 회귀값(ROI 14.2%)에 영향 없어야
    f = e.finance(revenue=332_640_000, opex=186_420_000, capex=702_030_000, subsidy_rate=0.5)
    assert abs(f.roi - 0.142) < 0.001
    assert abs(f.payback_years - 7.1) < 0.05


# ── 13. RFQ 사양서 생성 + 견적서 정합성 검증 (2026-07-18) ─────────
def _rfq_uminjae():
    return e.generate_rfq_package(
        region_snow_cm=30, region_wind_ms=35, area_m2=2323, cover=e.Cover.FILM,
        form="연동", t_target=10, t_min=-7.8, fr=0.7, surface_area_m2=3362)


def _rfq_choihyeokjin():
    # 최혁진은 cases/*.json이 없어(원가계산서만 확보) 설계입력(적설·풍속·목표온도)이
    # 이 저장소엔 없다 — 원채원 baseline 설계조건([추정])을 그대로 써서 RFQ 생성
    # 메커니즘만 확인한다(면적·피복·CAPEX 실측값만 최혁진 고유값).
    return e.generate_rfq_package(
        region_snow_cm=30, region_wind_ms=35, area_m2=3459, cover=e.Cover.FLUORINE,
        form="연동", t_target=10, t_min=-7.8, fr=0.7)


def test_generate_rfq_package_rejects_understrength_form():
    import pytest
    with pytest.raises(ValueError):
        e.generate_rfq_package(region_snow_cm=60, region_wind_ms=45, area_m2=2323,
                               cover=e.Cover.FILM, form="연동", t_target=10, t_min=-7.8, fr=0.7)


def test_reconcile_quote_uminjae_self_consistency():
    # 우민재의 실측 CAPEX_MAJOR_CASE_CHUNKS를 '견적서'로 대입 — 같은 케이스의
    # 입력으로 만든 RFQ 사양서와 자체정합해야 한다(근거 없는 새 데이터 없음).
    rfq = _rfq_uminjae()
    result = e.reconcile_quote(
        rfq, e.CAPEX_MAJOR_CASE_CHUNKS["우민재"],
        quote_direct_cost_total=456_158_140, quote_total_with_overhead=557_152_000,
        quote_area_m2=2323)
    by_name = {c.name: c for c in result.checks}
    assert by_name["필수 공종 완전성"].status == "일치"
    assert by_name["면적 정합"].status == "일치"
    assert by_name["규격코드 정합"].status == "확인요망"   # 실제 발주 규격코드 근거 없음 — 지어내지 않음
    assert by_name["총액 단가 밴드"].status in ("정상", "경계")
    assert result.overall_status.startswith("부분정합")     # 규격코드 확인요망 1건만 남음
    assert result.match_score_pct >= 85.0


def test_reconcile_quote_choihyeokjin_self_consistency():
    rfq = _rfq_choihyeokjin()
    result = e.reconcile_quote(
        rfq, e.CAPEX_MAJOR_CASE_CHUNKS["최혁진"],
        quote_direct_cost_total=694_575_784, quote_total_with_overhead=930_000_000,
        quote_area_m2=3459)
    by_name = {c.name: c for c in result.checks}
    assert by_name["필수 공종 완전성"].status == "일치"
    assert by_name["면적 정합"].status == "일치"
    assert by_name["총액 단가 밴드"].status in ("정상", "경계")


def test_reconcile_quote_flags_missing_required_category():
    rfq = _rfq_uminjae()
    quote = dict(e.CAPEX_MAJOR_CASE_CHUNKS["우민재"])
    dropped = quote["hvac"]
    quote["hvac"] = 0.0
    result = e.reconcile_quote(
        rfq, quote, quote_direct_cost_total=456_158_140 - dropped,
        quote_total_with_overhead=557_152_000, quote_area_m2=2323)
    by_name = {c.name: c for c in result.checks}
    assert by_name["필수 공종 완전성"].status == "불일치"
    assert "hvac" in by_name["필수 공종 완전성"].detail
    assert result.overall_status.startswith("불일치")


def test_compare_quotes_handles_empty_list():
    rfq = _rfq_uminjae()
    comparison = e.compare_quotes(rfq, [])
    assert comparison.rows == []
    assert comparison.lowest_cost_vendor is None
    assert comparison.highest_match_score_vendor is None


def test_compare_quotes_does_not_let_lowest_cost_win_over_defects():
    # 최저가 업체가 필수 공종을 누락했다면 '최저가'와 '최고점수'가 서로 다른
    # 업체를 가리켜야 한다 — compare_quotes()가 자동으로 승자를 정하지 않는다는 증거
    rfq = _rfq_uminjae()
    vendor_real = e.VendorQuote("업체A(실측)", e.CAPEX_MAJOR_CASE_CHUNKS["우민재"],
                                456_158_140, 557_152_000, area_m2=2323)
    quote_defective = dict(e.CAPEX_MAJOR_CASE_CHUNKS["우민재"])
    dropped = quote_defective["hvac"]
    quote_defective["hvac"] = 0.0
    vendor_cheap = e.VendorQuote("업체B(냉난방누락·저가)", quote_defective,
                                 456_158_140 - dropped, 480_000_000, area_m2=2323)

    comparison = e.compare_quotes(rfq, [vendor_real, vendor_cheap])

    assert len(comparison.rows) == 2
    assert comparison.reconciliations["업체B(냉난방누락·저가)"].overall_status.startswith("불일치")
    assert comparison.lowest_cost_vendor == "업체B(냉난방누락·저가)"
    assert comparison.highest_match_score_vendor == "업체A(실측)"
    assert comparison.lowest_cost_vendor != comparison.highest_match_score_vendor


def test_pumsem_labor_days_known_item():
    r = e.pumsem_labor_days("철골공사", "외부기둥", 10)
    assert r["category"] == "철골공사"
    assert r["labor_days_by_trade"] == {"철골공": 1.8, "특별인부": 0.6}
    assert r["total_labor_days"] == 2.4


def test_pumsem_labor_days_unmapped_item_returns_none():
    # 비닐온실 공종(제3절)은 아직 미확보(Phase G 다음 라운드)
    assert e.pumsem_labor_days("비닐철골공사", "지붕서까래", 5) is None


def test_pumsem_labor_days_wrong_category_for_real_item_returns_none():
    # "외부기둥"은 철골공사에만 있다 — 엉뚱한 공종을 붙이면 이름이 맞아도 None
    assert e.pumsem_labor_days("알루미늄공사", "외부기둥", 5) is None


def test_pumsem_labor_days_disambiguates_same_name_across_categories():
    # "모터설치대"는 천창개폐장치공사·수평스크린공사 두 공종에 같은 이름,
    # 다른 값으로 존재한다 — 공종을 명시해야 올바른 값이 나온다는 걸 증명
    ceiling = e.pumsem_labor_days("천창개폐장치공사", "모터설치대", 1)
    screen = e.pumsem_labor_days("수평스크린공사", "모터설치대", 1)
    assert ceiling["total_labor_days"] != screen["total_labor_days"]
    assert ceiling["labor_days_by_trade"] == {"철골공": 0.31, "조력공": 0.9}
    assert screen["labor_days_by_trade"] == {"철골공": 0.6, "조력공": 0.3}


def test_pumsem_project_labor_summary_aggregates_and_flags_unmatched():
    result = e.pumsem_project_labor_summary({
        ("철골공사", "외부기둥"): 10,
        ("철골공사", "내부기둥"): 5,
        ("비닐철골공사", "지붕서까래"): 3,
    })
    assert result["unmatched"] == [("비닐철골공사", "지붕서까래")]
    assert result["totals_by_trade"] == {"철골공": 2.6, "특별인부": 0.9}
    assert result["total_labor_days"] == 3.5


def test_pumsem_items_cover_glass_and_vinyl_greenhouse():
    # 제7장 품셈 산정 파트 전체(유리 7공종57종 + 비닐 2공종7종) = 64종
    assert len(e.PUMSEM_ITEMS) == 64
    categories = {it.category for it in e.PUMSEM_ITEMS}
    assert "철골공사(비닐·파이프자재)" in categories
    assert "온실피복공사(비닐)" in categories


def test_pumsem_labor_days_vinyl_greenhouse_item():
    r = e.pumsem_labor_days("온실피복공사(비닐)", "농업용PO필름(천창및지붕)", 100)
    assert r["labor_days_by_trade"] == {"철골공": 1.0, "특별인부": 0.4, "보통인부": 0.2}
    assert r["total_labor_days"] == 1.6


# ── 12. 기자재DB (2026-07-19, Phase H) ──────────────────────
def test_equipment_lookup_finds_known_device():
    r = e.equipment_lookup("환경제어기")
    assert len(r) == 85
    assert all(row["표준 장치명"] == "환경제어기" for row in r)


def test_equipment_lookup_unknown_device_returns_empty():
    assert e.equipment_lookup("존재하지않는장치명") == []


def test_equipment_component_prices_parses_won_and_sums():
    r = e.equipment_component_prices("HS-8000")
    assert len(r["필수구성품"]) == 2
    assert r["필수구성품"][0]["표준가격_원"] == 9_500_000
    assert r["필수구성품_합계_원"] == 10_500_000


def test_equipment_component_prices_unknown_model_returns_empty_not_zero_fabricated():
    r = e.equipment_component_prices("존재하지않는모델")
    assert r["필수구성품"] == [] and r["선택구성품"] == []
    assert r["필수구성품_합계_원"] == 0


def test_construction_company_list_filters_by_region():
    r = e.construction_company_list("충청남도")
    assert r == [{"상호": "(주)그린플러스", "소재지": "충청남도 예산군 응봉면 응봉로 50-42",
                  "연락처": "041-332-6421"}]


def test_construction_company_list_no_region_returns_all():
    assert len(e.construction_company_list()) == 84


# ── 13. 보조사업 체크리스트 (2026-07-19, Phase I) ────────────
def test_subsidy_application_checklist_has_five_steps_all_pending():
    checklist = e.subsidy_application_checklist()
    assert len(checklist) == 5
    assert [c["단계"] for c in checklist] == [1, 2, 3, 4, 5]
    assert all(c["상태"] == "확인요망" for c in checklist)


def test_subsidy_application_checklist_no_rates_fabricated():
    # 보조율(%) 수치는 공모 회차마다 바뀌므로 체크리스트 어디에도 없어야 한다
    checklist = e.subsidy_application_checklist()
    for item in checklist:
        assert "%" not in item["설명"]


def test_reconcile_quote_flags_band_deviation():
    rfq = _rfq_uminjae()
    result = e.reconcile_quote(
        rfq, e.CAPEX_MAJOR_CASE_CHUNKS["우민재"],
        quote_direct_cost_total=456_158_140,
        quote_total_with_overhead=100_000_000,   # 명백한 과소견적(43,047원/㎡)
        quote_area_m2=2323)
    by_name = {c.name: c for c in result.checks}
    assert by_name["총액 단가 밴드"].status == "경고(밴드이탈)"
    assert result.overall_status.startswith("불일치")


if __name__ == "__main__":
    import sys, traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception as ex:
            print(f"  FAIL  {fn.__name__}: {ex}")
            traceback.print_exc()
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
