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


# ── 3. 난방부하 이중검증 (E7/C7) ─────────────────────────────
def test_heating_dual_verify_glass():
    # 유리온실 근사 입력 → 면적당 부하가 실측(231)과 같은 자릿수
    hr = e.heating_load(surface_area_m2=5000, cover="유리",
                        t_target=10, t_min=-7.8, fr=0.7,
                        floor_area_m2=3456)
    v = e.verify_heating_vs_actual(hr.load_per_m2, "유리")
    assert v["status"] == "정상", v


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


# ── 10. 입지 지역 매핑 스텁 (2026-07-16) ────────────────────────
def test_siting_design_load_returns_none_gracefully():
    # 매핑표가 비어있는 상태(P0-b 진행중) — 예외 없이 None만 반환해야
    assert e.siting_design_load("충남 임의지역") is None


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
