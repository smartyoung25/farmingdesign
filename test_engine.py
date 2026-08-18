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


# ── 3-1. 난방부하 max/period U 분리 (2026-07-20 구조개선, 2026-08-16 P1-5로 기본값 분리) ─
def test_heating_load_u_default_uses_u_design_for_max_load():
    # 2026-08-16(P1-5): "필름" 등 U_DESIGN이 있는 cover는 이제 u_design 기본값이
    # U_VALUE가 아니라 U_DESIGN(Diop 등 핫박스 극한조건값)이어야 한다.
    hr_default = e.heating_load(surface_area_m2=5000, cover="필름",
                                t_target=10, t_min=-7.8, fr=0.7)
    hr_explicit = e.heating_load(surface_area_m2=5000, cover="필름",
                                 t_target=10, t_min=-7.8, fr=0.7,
                                 u_design=e.U_DESIGN["필름"], u_period=e.U_VALUE["필름"])
    assert hr_default.max_load_kcal_h == hr_explicit.max_load_kcal_h
    assert hr_default.fuel_consumption == hr_explicit.fuel_consumption
    # U_DESIGN["필름"](8.9) > U_VALUE["필름"](2.66)이므로 기본값도 더 이상 같지 않다
    hr_old_coupled = e.heating_load(surface_area_m2=5000, cover="필름",
                                    t_target=10, t_min=-7.8, fr=0.7,
                                    u_design=e.U_VALUE["필름"], u_period=e.U_VALUE["필름"])
    assert hr_default.max_load_kcal_h > hr_old_coupled.max_load_kcal_h


def test_heating_load_u_default_stays_coupled_when_no_u_design_entry():
    # U_DESIGN에 없는 cover("유리")는 기존처럼 U_VALUE[cover]로 계속 폴백해야 한다
    # (Diop 논문은 PE필름 대상이라 유리는 손대지 않음 — 회귀 영향 없어야 함)
    assert "유리" not in e.U_DESIGN
    hr_default = e.heating_load(surface_area_m2=5000, cover="유리",
                                t_target=10, t_min=-7.8, fr=0.7)
    hr_explicit = e.heating_load(surface_area_m2=5000, cover="유리",
                                 t_target=10, t_min=-7.8, fr=0.7,
                                 u_design=e.U_VALUE["유리"], u_period=e.U_VALUE["유리"])
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


# ── 3-3. P1-9(2026-08-17): fr/curtain 시그니처 수준 강제 ────────────
def test_heating_load_curtain_param_converts_internally():
    base = dict(surface_area_m2=1000, cover="필름", t_target=15, t_min=-10)
    via_curtain = e.heating_load(**base, curtain="다겹보온")
    via_fr = e.heating_load(**base, fr=1 - e.FR_TABLE["다겹보온"])
    assert via_curtain.max_load_kcal_h == via_fr.max_load_kcal_h
    # 방향반전 구조 재발 방지: 보온이 좋을수록 부하가 작아야 한다
    l_po = e.heating_load(**base, curtain="PO단일").max_load_kcal_h
    l_dual = e.heating_load(**base, curtain="이중커튼").max_load_kcal_h
    assert l_dual < l_po


def test_heating_load_rejects_ambiguous_missing_or_invalid_fr():
    import pytest
    base = dict(surface_area_m2=1000, cover="필름", t_target=15, t_min=-10)
    with pytest.raises(ValueError):
        e.heating_load(**base)                              # fr·curtain 둘 다 없음
    with pytest.raises(ValueError):
        e.heating_load(**base, fr=0.7, curtain="다겹보온")   # 둘 다 지정(모호)
    with pytest.raises(ValueError):
        e.heating_load(**base, fr=1.5)                      # 노출비율 범위 밖
    with pytest.raises(ValueError):
        e.heating_load(**base, fr=0)                        # 0은 물리적으로 무의미


# ── 3-3b. B4~B8 확장(2026-08-17): 법정 하자담보·전기 품셈 정액 ──────
def test_warranty_statutory_greenhouse_anchor():
    # 별표4 제19호 "온실설치 2년" — 이 확장의 핵심 법정근거. 값이 바뀌면
    # 법령 개정을 확인하고 원문 PDF(리포 사본)와 함께 갱신해야 한다.
    r = e.warranty_period("온실설치")
    assert r["years"] == 2 and "별표4" in r["근거"]
    assert "세부 공종별" in r["비고"]          # 복합공사 비고(원문) 전달
    # 발췌 항목 대표값 대조(원문 PDF 전사)
    assert e.WARRANTY_STATUTORY["방수"]["years"] == 3
    assert e.WARRANTY_STATUTORY["지붕"]["years"] == 3
    assert e.WARRANTY_STATUTORY["급배수·냉난방·환기·공조·자동제어·가스·배연설비"]["years"] == 2


def test_warranty_period_unknown_returns_none_and_sources_are_primary():
    assert e.warranty_period("존재하지않는공종") is None   # 값 안 지어냄
    # 2026-08-18: 전기·통신 원문 확보로 [확인요망] 해소 — 근거에 조항·확인일이
    # 명시돼야 하고, 확인요망 꼬리표가 되살아나면 회귀다
    elec = e.WARRANTY_STATUTORY["전기(건축물 전기설비)"]["근거"]
    comm = e.WARRANTY_STATUTORY["통신(그 외 정보통신공사)"]["근거"]
    assert "확인요망" not in elec and "확인요망" not in comm
    assert "별표3의2 제7호" in elec and "원문 확인" in elec
    assert "제37조 제3호" in comm and "구내 케이블 제외" in comm


def test_electrical_pumsem_lump_reference():
    # P1-10 라운드4에서 원단위 대사로 검증된 품셈 표준설계 정액(2021)
    assert e.ELECTRICAL_PUMSEM_LUMP_WON_PER_HA == 250_000_000


# ── 3-3c. P3-18(2026-08-17): 금융조달 대출상환표 ────────────────────
def test_loan_amortization_equal_payment_hand_computed():
    import pytest as _pt
    # 1억·10%·3년·무거치 원리금균등: 연납입액 = 1e8×0.1×1.1³/(1.1³−1) = 40,211,480.4
    am = e.loan_amortization(100_000_000, 10.0, 3)
    annuity = 100_000_000 * 0.1 * 1.1**3 / (1.1**3 - 1)
    assert all(row["납입액"] == _pt.approx(annuity, rel=1e-9) for row in am["rows"])
    assert am["rows"][0]["이자"] == _pt.approx(10_000_000)
    assert am["rows"][-1]["잔액"] == 0.0                      # 완제
    assert am["총이자"] == _pt.approx(3 * annuity - 100_000_000, rel=1e-9)


def test_loan_amortization_equal_principal_with_grace():
    import pytest as _pt
    # 3억·6%·전체 3년(거치 1년) 원금균등: 거치 이자 18M → 상환 150M+18M, 150M+9M
    am = e.loan_amortization(300_000_000, 6.0, 3, grace_years=1, method="원금균등")
    assert [row["구분"] for row in am["rows"]] == ["거치", "상환", "상환"]
    assert am["rows"][0]["납입액"] == _pt.approx(18_000_000)   # 거치: 이자만
    assert am["rows"][1]["원금"] == _pt.approx(150_000_000)
    assert am["rows"][2]["이자"] == _pt.approx(9_000_000)      # 잔액 150M×6%
    assert am["총이자"] == _pt.approx(45_000_000)
    assert am["총납입액"] == _pt.approx(345_000_000)


def test_loan_amortization_zero_rate_and_validation():
    import pytest as _pt
    am = e.loan_amortization(90_000_000, 0.0, 3)              # 무이자: 3연 균등
    assert am["총이자"] == 0.0
    assert all(row["납입액"] == _pt.approx(30_000_000) for row in am["rows"])
    for bad in [dict(principal_won=0, annual_rate_pct=3, term_years=5),
                dict(principal_won=1e8, annual_rate_pct=-1, term_years=5),
                dict(principal_won=1e8, annual_rate_pct=3, term_years=5, grace_years=5),
                dict(principal_won=1e8, annual_rate_pct=3, term_years=5, method="이상한방식")]:
        with _pt.raises(ValueError):
            e.loan_amortization(**bad)


# ── 3-3d. LCC 기자재 내용연수(2026-08-18, 데이터 대기 ② 해소) ────────
def test_equipment_service_life_reference_values():
    # 조달청 고시 제2024-30호 [별표1] 원문 전사 대표값 가드(PDF 리포 사본과 대조)
    R = e.EQUIPMENT_SERVICE_LIFE_REFERENCE
    assert R["온풍난방기"]["years"] == 11 and R["온풍난방기"]["code"] == "40101866"
    assert R["전기보일러"]["years"] == 13
    assert R["송풍기(유동·배기팬류)"]["years"] == 10
    assert R["정량펌프(양액공급류)"]["years"] == 11
    assert R["분전반"]["years"] == 8
    assert R["빌딩자동제어장치(복합환경제어 유사분류)"]["years"] == 11
    assert R["컴퓨터서버"]["years"] == 6
    assert R["보안용카메라"]["years"] == 6
    # 전 항목이 8자리 물품분류번호와 양수 연수를 갖는다(추적성)
    assert all(len(v["code"]) == 8 and v["years"] > 0 for v in R.values())


def test_lcc_replacement_schedule_deterministic():
    import pytest as _pt
    items = [
        {"name": "온풍난방기", "unit_cost_won": 20_000_000, "service_life_years": 11},
        {"name": "데스크톱컴퓨터", "unit_cost_won": 1_500_000, "service_life_years": 5},
        {"name": "배전반", "unit_cost_won": 8_000_000, "service_life_years": 12},
    ]
    r = e.lcc_replacement_schedule(items, horizon_years=20)
    by = {row["name"]: row for row in r["rows"]}
    assert by["온풍난방기"]["replacement_years"] == [11]            # 11년 1회
    assert by["데스크톱컴퓨터"]["replacement_years"] == [5, 10, 15]  # 지평 말(20)은 제외
    assert by["배전반"]["replacement_years"] == [12]
    assert r["total_replacement_cost_won"] == _pt.approx(
        20_000_000 * 1 + 1_500_000 * 3 + 8_000_000 * 1)
    # 수명이 지평 이상이면 교체 없음
    r2 = e.lcc_replacement_schedule(
        [{"name": "전기보일러", "unit_cost_won": 30_000_000, "service_life_years": 13}], 10)
    assert r2["rows"][0]["n_replacements"] == 0
    with _pt.raises(ValueError):
        e.lcc_replacement_schedule(items, 0)
    with _pt.raises(ValueError):
        e.lcc_replacement_schedule([{"name": "x", "unit_cost_won": 1, "service_life_years": 0}], 10)


def test_structure_service_life_statutory_values():
    # 법인세법 시행규칙 별표5<개정 2024.11.11.>·별표6<개정 2024.3.22.> 원문 전사
    # 가드(PDF 리포 사본과 대조) — 값이 바뀌면 법령 개정 확인 후 함께 갱신할 것
    R = e.STRUCTURE_SERVICE_LIFE_STATUTORY
    k3 = "별표5_제3호(연와조·블록조·콘크리트조·목조 등 기타 조)"
    k4 = "별표5_제4호(철골·철근콘크리트조 등)"
    assert R[k3]["years"] == 20 and R[k3]["range"] == (15, 25)
    assert R[k4]["years"] == 40 and R[k4]["range"] == (30, 50)
    assert R["별표5_비고3(제3호 단축)"]["years"] == 10
    assert R["별표5_비고3(제3호 단축)"]["range"] == (8, 12)
    assert R["별표5_비고3(제4호 단축)"]["years"] == 20
    assert R["별표5_비고3(제4호 단축)"]["range"] == (15, 25)
    assert R["별표6_제2호(농업 01 업종별 자산)"]["years"] == 5
    assert R["별표6_제2호(농업 01 업종별 자산)"]["range"] == (4, 6)
    # 전 항목: 하한 ≤ 기준내용연수 ≤ 상한 (별표의 내용연수범위 구조)
    for v in R.values():
        lo, hi = v["range"]
        assert lo <= v["years"] <= hi and v["대상"]


def test_structure_service_life_no_greenhouse_type_keys():
    # 판단성 가드: 비고3 가목에 축사는 열거되나 온실은 미열거 — 온실유형→호
    # 자동 매핑 키가 등록되면 유추 적용(원칙 위반)이므로 구조적으로 차단한다.
    # 호 선택은 컨설턴트·세무사 몫(케이스에는 선택 근거와 함께 주입값으로).
    for k in e.STRUCTURE_SERVICE_LIFE_STATUTORY:
        assert k.startswith("별표"), k
        assert not any(w in k for w in ("유리", "비닐", "온실", "하우스")), \
            f"{k}: 온실유형 키 금지 — 호 적용은 판단성"


# ── 3-3e. P1-6 잔여 해소(2026-08-18): 감리비 참고 표시 ────────────────
def test_supervision_fee_rate_table_transcription():
    # 국토교통부고시 제2020-635호 별표5 원문 전사 가드(PDF 리포 사본 대조)
    T = e.SUPERVISION_FEE_RATE_TABLE
    assert len(T) == 17
    assert T[0] == (50_000_000, 2.02, 2.24, 2.46)      # "5천만원 이하" 행
    assert (1_000_000_000, 1.11, 1.23, 1.35) in T      # 07-23 웹 확인값과 일치 확인
    assert (2_000_000_000, 1.02, 1.13, 1.24) in T
    assert T[-1] == (500_000_000_000, 0.84, 0.93, 1.02)
    # 구조 가드: 공사비 오름차순, 요율은 단조 비증가, 각 행 단순<보통<복잡
    for (c1, *r1), (c2, *r2) in zip(T, T[1:]):
        assert c1 < c2 and all(a >= b for a, b in zip(r1, r2))
    for _, g1, g2, g3 in T:
        assert g1 < g2 < g3


def test_design_supervision_fee_reference():
    import pytest as _pt
    # 앵커 정확값(10억): 보간 없이 원문 요율 그대로
    r = e.design_supervision_fee_reference(1_000_000_000)
    assert r["요율_pct"]["제1종(단순)"] == 1.11 and r["요율_pct"]["제3종(복잡)"] == 1.35
    # 원채원 스케일(7.0203억): 5억~10억 직선보간(제16조①) — 손계산 대조
    cost = 702_030_000
    r2 = e.design_supervision_fee_reference(cost)
    t = (cost - 500_000_000) / (1_000_000_000 - 500_000_000)
    raw = 1.29 + t * (1.11 - 1.29)
    assert r2["요율_pct"]["제1종(단순)"] == _pt.approx(raw, abs=1e-4)
    assert r2["감리비_원"]["제1종(단순)"] == round(cost * raw / 100)
    assert "직선보간" in r2["산정구간"] and "불산입" in r2["note"]
    # 제16조②: 5천만원 미만은 5천만원으로 간주하여 산출
    r3 = e.design_supervision_fee_reference(30_000_000)
    assert r3["산정공사비_원"] == 50_000_000
    assert r3["감리비_원"]["제1종(단순)"] == round(50_000_000 * 2.02 / 100)
    # 제16조③: 5천억 초과는 별도 공식(미확보) — 지어내지 않고 None
    assert e.design_supervision_fee_reference(600_000_000_000) is None
    with _pt.raises(ValueError):
        e.design_supervision_fee_reference(0)


# ── 3-4. P1-11(2026-08-17): select_specs 작물특화형 필터 ────────────
def test_select_specs_default_excludes_crop_specific():
    # 왜곡 실측 지점(적설20·풍속26): 종전엔 파프리카 전용이 연동 최소사양으로 나왔음
    sel = e.select_specs(20, 26)
    assert all(not s.crop for s in sel["candidates"])  # 기본은 일반형만
    assert sel["min_by_form"]["연동"].name == "20-연동(등)-04"
    assert sel["min_by_form"]["연동"].crop == ""


def test_select_specs_crop_param_includes_that_crop_only():
    sel = e.select_specs(20, 30, form="단동", crop="수박")
    crops_in = {s.crop for s in sel["candidates"]}
    assert crops_in <= {"", "수박"}          # 일반형 + 수박 특화형만
    assert "수박" in crops_in                # 수박 특화형이 실제 포함됨
    assert sel["min_by_form"]["단동"].name == "21-단동(등)-01"  # 수박 전용이 최소로 경쟁


def test_select_specs_star_reproduces_legacy_and_unknown_crop_is_generic():
    legacy = e.select_specs(20, 26, crop="*")
    assert legacy["min_by_form"]["연동"].crop == "파프리카"     # 구버전 왜곡 동작 재현
    tomato = e.select_specs(20, 26, crop="토마토")              # 특화형 없는 작물
    default = e.select_specs(20, 26)
    assert {s.name for s in tomato["candidates"]} == {s.name for s in default["candidates"]}
    assert "수박" in e.spec_crops() and "참외" in e.spec_crops()


def test_generate_rfq_package_accepts_curtain_path():
    pkg_curtain = e.generate_rfq_package(
        region_snow_cm=40, region_wind_ms=30, area_m2=3000, cover=e.Cover.FILM,
        form="연동", t_target=15, t_min=-10, curtain="다겹보온")
    pkg_fr = e.generate_rfq_package(
        region_snow_cm=40, region_wind_ms=30, area_m2=3000, cover=e.Cover.FILM,
        form="연동", t_target=15, t_min=-10, fr=1 - e.FR_TABLE["다겹보온"])
    assert pkg_curtain.heating.max_load_kcal_h == pkg_fr.heating.max_load_kcal_h


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
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["우민재"])
    assert cb.total == 456_158_140  # 원문 리터럴 앵커 — 단일 출처 상수의 드리프트를 여기서 잡는다(53차 F8)
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["우민재"]
    assert sum(cb.items.values()) + cb.unclassified == 456_158_140


def test_capex_major_breakdown_chj_reconciles_to_source():
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["최혁진"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["최혁진"])
    assert cb.total == 694_575_784
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["최혁진"]
    assert sum(cb.items.values()) + cb.unclassified == 694_575_784


def test_capex_major_breakdown_dh_reconciles_to_source():
    # 2026-07-21 추가 — 이두희 원가계산서 14개 세부공종 합계열 총합(433,606,460)이
    # known_total. unclassified는 '5-3.베드설치'(101,301,410, 9/13카테고리 어디에도
    # 안 맞아 미분류로 남긴 항목)와 정확히 일치해야 한다.
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["이두희"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["이두희"])
    assert cb.total == 433_606_460
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["이두희"]
    assert sum(cb.items.values()) + cb.unclassified == 433_606_460


def test_capex_major_breakdown_ysh_reconciles_to_source():
    # 2026-08-17 추가(P2-17 청킹→엔진 승격 1호) — 윤성호 내역서 공종별집계표(p3)
    # 16개 공종 합 1,162,078,090원(=원가계산서 p2 재료비+직접노무비+산출경비)이
    # known_total. unclassified는 행잉거터(0110)+작물와이어(0111)=39,220,352원.
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["윤성호"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["윤성호"])
    assert cb.total == 1_162_078_090
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["윤성호"]
    assert sum(cb.items.values()) + cb.unclassified == 1_162_078_090
    # 축열조 라인분리 정합: hvac 잔액 + 축열조 = 0109 유동휀·훈증기 + 0114 난방설비 원문값
    assert cb.items["hvac"] + cb.items["thermal_storage_insulation"] == 9_672_200 + 180_052_389
    # 이 표본으로 처음 채워진 두 카테고리(다른 3개 케이스에선 전부 0)
    assert cb.items["auxiliary_facility"] == 40_093_200
    assert cb.items["thermal_storage_insulation"] == 41_958_000


def test_capex_major_breakdown_hanil_reconciles_to_source():
    # 2026-08-18 추가(51차 "다른 견적 세부 분석" 1호) — 한일그린텍 설계예산서(20p)
    # 공사 집계표(p4) 8공종 소계 합=원가계산서(p3) 직접재료비+직접노무비+기계경비
    # =직접공사비 355,597,412원이 known_total. unclassified는 스탠딩 거터(스티,
    # 67.5m 28줄) 46,519,015원(재배시설 성격 — 이두희 베드·윤성호 행잉거터 선례).
    assert 241_374_292 + 97_796_120 + 16_427_000 == 355_597_412  # 원가계산서 p3 원단위 재현
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["한일그린텍"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["한일그린텍"])
    assert cb.total == 355_597_412
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["한일그린텍"] == 46_519_015
    assert sum(cb.items.values()) + cb.unclassified == 355_597_412
    # 공종→카테고리 합성 앵커(집계표 p4 원문 소계): 기초+골조+피복+전면판넬 / 커튼+동력장치
    assert cb.items["greenhouse_structure"] == 14_694_738 + 158_498_030 + 27_231_655 + 16_397_033
    assert cb.items["auto_opening_system"] == 52_411_062 + 21_474_455
    assert cb.items["irrigation_fertigation"] == 18_371_424
    # 본공사 범위에 난방·독립 환경제어·별도 전기 공종 없음(환급금 재투자 블록은 known_total 밖)
    assert cb.items["hvac"] == cb.items["ict_control"] == cb.items["electrical"] == 0
    # 40차 ACTUALS 대조와의 집계 레벨 정합: 총공사비 480,636,000(절사 전 480,636,200)
    # = 도급 공급가액 소계 416,072,106 + 부가세 39,664,769 + 환급금 재투자 24,899,325(=공급 22,635,750+부가세 2,263,575).
    # 절사 전 합에서 원가계산서 p3 소계 455,736,875(=416,072,106+39,664,769)를 원단위 재현.
    assert 416_072_106 + 39_664_769 == 455_736_875
    assert 455_736_875 + 22_635_750 + 2_263_575 == 480_636_200


def test_capex_major_breakdown_ljh_reconciles_to_source():
    # 2026-08-18 추가(52차 "다른 견적 세부 분석" 2호) — 이준희(서산, 표본 최초의
    # 벤로형 유리온실 5,404.32㎡) 공종별집계표 합계행=원가계산서 직재+직노+산출경비
    # =직접공사비 1,010,337,181원이 known_total. unclassified는 행잉거터+유인줄
    # (재배시설 — 윤성호 0110/0111 선례)+기타공사(선홈통·바닥배수 부대).
    assert 758_880_699 + 237_736_474 + 13_720_008 == 1_010_337_181  # 원가계산서 원단위 재현
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["이준희"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["이준희"])
    assert cb.total == 1_010_337_181
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["이준희"] == 93_326_116
    assert sum(cb.items.values()) + cb.unclassified == 1_010_337_181
    # 공종→카테고리 합성 앵커(공종별집계표 원문 소계)
    assert cb.items["greenhouse_structure"] == 6_314_238 + 69_936_701 + 169_114_684 + 174_804_328 + 144_093_767
    assert cb.items["auto_opening_system"] == 47_477_403 + 125_978_303
    assert cb.items["hvac"] == 7_093_767            # 09 유동휀만(난방설비 11은 "본 공사제외")
    assert cb.items["irrigation_fertigation"] == 28_952_319 + 28_859_014 + 3_904_157 + 5_219_421
    assert cb.items["ict_control"] == 83_463_440    # 1209 복합환경제어 — 표본 최대(PRIVA Compact CC 80,000,000이 95.85%, 54차 F1 귀속 정정)
    assert cb.items["electrical"] == 21_799_523     # 13 동력간선공사
    assert 65_624_205 + 19_138_167 + 8_563_744 == 93_326_116  # 미분류 구성 원문 소계
    # 도급·부가세 환급 체인(견적서·원가계산서 시트 원단위 재현 — 환급 명시 표본 최초)
    assert 1_079_731_365 + 11_177_726 == 1_090_909_091          # 원가 계+이윤=공급가액(일반관리비 0%)
    assert 1_090_909_091 + 109_090_909 == 1_200_000_000         # +부가세=도급 합계
    assert 1_200_000_000 - 1_056_000 - 26_179_000 == 1_172_765_000  # 영세율·환급 차감=실부담


def test_capex_major_breakdown_mjy_reconciles_to_source():
    # 2026-08-18 추가(55차 "다른 견적 세부 분석" 3호) — 맹주연(천안, 명칭 '벤로형'
    # 이나 피복은 전량 PO/PE 필름 — 명칭≠재질). 집계표 13공종 열합=원가계산서
    # 직재+직노+기계경비=439,742,227이 known_total(총계행 표기 439,742,226은 원문
    # 1원 갭 — 구성 합 채택). unclassified는 바닥재및행잉거터(재배시설, 윤성호 선례).
    assert 360_447_860 + 72_269_120 + 7_025_247 == 439_742_227  # 원가계산서 3항목 원단위 재현
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["맹주연"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["맹주연"])
    assert cb.total == 439_742_227
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["맹주연"] == 46_977_648
    assert sum(cb.items.values()) + cb.unclassified == 439_742_227
    # 공종→카테고리 합성 앵커(집계표 원문 소계)
    assert cb.items["greenhouse_structure"] == 28_148_966 + 124_024_505 + 14_080_913 + 29_487_743 + 25_521_173 + 17_890_613
    assert cb.items["auto_opening_system"] == 36_129_616 + 50_479_524 + 14_751_446
    # 혼재 공종 010108 '환기 및 개폐'의 명시 라인 분리(최혁진 0113·윤성호 축열조 방식):
    # 유동팬 42대+환풍기 6대+설치노무 → hvac, 잔여(개폐모터·컨트롤박스·전선) → 자동개폐
    assert cb.items["hvac"] == 5_040_000 + 1_123_200 + 2_508_576 == 8_671_776
    assert 8_671_776 + 14_751_446 == 23_423_222                 # 분리 검산 = 공종 소계 재현
    assert cb.items["irrigation_fertigation"] == 33_686_562 + 5_934_127 + 3_957_615
    assert cb.items["ict_control"] == cb.items["electrical"] == 0
    # 도급 체인(원가계산서 원단위): 순공사비 계+관리비 6%+이윤 15%=공급가액, +부가세→합계 절삭
    assert 493_278_737 + 29_596_724 + 24_250_441 == 547_125_902  # 표기 547,125,903은 원문 1원 갭
    assert 547_125_902 + 54_712_590 == 601_838_492               # 절삭 후 표기 601,838,000
    assert 226_473_083 // 10 == 22_647_308                       # 부가세환급금 = 환급품목×10%


def test_capex_major_breakdown_kjg_reconciles_to_source():
    # 2026-08-18 추가(56차 "다른 견적 세부 분석" 4호) — 강정구(군산 딸기 와이드
    # 연동 3,696㎡, 서진비에스 2022-04 — 표본 중 최고(最古), 물가 시점 주의).
    # 부분 범위 시공 견적(골조·천창개폐·피복만): 0인 카테고리는 설비 부재가 아니라
    # 견적 범위 밖. 표본 최초의 unclassified 0.
    assert 223_202_937 + 67_810_080 + 5_908_267 == 296_921_284  # 원가계산서 3항목 원단위 재현
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["강정구"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["강정구"])
    assert cb.total == 296_921_284
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["강정구"] == 0
    assert sum(cb.items.values()) == 296_921_284
    # 공종→카테고리 합성 앵커(집계표 원문 소계 — 명시 개폐 명칭 라인 2건 분리 반영)
    assert cb.items["greenhouse_structure"] == 11_451_200 + (101_638_392 - 347_061) + 81_198_324 + 28_177_124
    # 명시 개폐 명칭 라인 분리(7회차 F5 일관 적용): 비닐 공종의 측면개폐모터·가이드로라
    # + 파이프 공종의 1.2중개폐파이프(측면 개폐 권취 축 계열 추정 — 규칙 일관 적용)
    assert 480_000 + 180_000 == 660_000
    assert 28_177_124 + 660_000 == 28_837_124                    # 비닐 공종 분리 검산
    assert (101_638_392 - 347_061) + 347_061 == 101_638_392      # 파이프 공종 분리 검산
    assert cb.items["auto_opening_system"] == 73_796_244 + 660_000 + 347_061
    for k in ("hvac", "irrigation_fertigation", "ict_control", "electrical"):
        assert cb.items[k] == 0                                  # 부분 범위 견적(범위 밖)
    # 도급 체인 + 환급 차감 전·후 값(p2 원가계산서 머리 — 한글=차감 전 공사금액과 일치,
    # 괄호 숫자=차감 후 총공사금액과 일치. 병기 의도 여부는 [추정] — 7회차 F3)
    assert 323_584_540 + 6_471_690 + 5_295_649 - 10_200_000 == 325_151_879  # 표기 325,151,878은 1원 갭
    assert (325_151_878 + 32_515_188 + 10_200_000) // 1000 * 1000 == 367_867_000  # 공사금액(한글 일치값)
    assert 130_507_454 // 10 == 13_050_745                       # 부가세환급예정액
    assert (367_867_000 - 13_050_745) // 1000 * 1000 == 354_816_000  # 총공사금액(괄호 숫자 일치값)
    # 원문 갭 ③(7회차 F4): 영세율 표시된 측면개폐모터 480,000이 영세율 총액에 미포함
    assert 6_400_000 + 3_800_000 == 10_200_000


def test_capex_major_breakdown_oks_reconciles_to_source():
    # 2026-08-18 추가(57차 "다른 견적 세부 분석" 5호) — 오기수(군산, 서진비에스
    # 2023-08 — 강정구와 동일 업체 시계열). 설비 전용 부분 범위 견적(골조·피복
    # 전무 — 강정구와 상보 쌍): 0 카테고리는 견적 범위 밖.
    assert 164_863_706 + 31_834_400 + 2_876_832 == 199_574_938  # 원가계산서 3항목 원단위 재현
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["오기수"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["오기수"])
    assert cb.total == 199_574_938
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["오기수"] == 39_821_638
    assert sum(cb.items.values()) + cb.unclassified == 199_574_938
    # 공종→카테고리 합성 앵커(집계표 원문 소계)
    assert cb.items["auto_opening_system"] == 5_310_000 + 63_684_894 + 2_817_269
    assert cb.items["irrigation_fertigation"] == 35_567_476 + 12_373_661
    assert cb.items["ict_control"] == 40_000_000   # PRIVA 계열 2번째 관측(프라바 오피스) — 표본 2위
    for k in ("greenhouse_structure", "hvac", "electrical"):
        assert cb.items[k] == 0                    # 설비 전용 부분 범위(범위 밖)
    # 도급 체인(원단위): 순공사원가+관리비 5%+이윤 8%−영세율=공급가액, +부가세+영세율=총액
    assert 164_863_706 + 35_718_196 + 13_358_142 == 213_940_044
    assert 213_940_044 + 10_697_002 + 4_781_867 - 9_170_000 == 220_248_913
    assert 220_248_913 + 22_024_891 + 9_170_000 == 251_443_804  # 한글 원단위 표기와 일치(환급 차감 전)
    # 원문 결함 관찰 고정(57차): p4 환급표 계가 첫 행 값 그대로 — 관리동커텐 합산 누락
    assert 23_974_813 + 1_648_320 == 25_623_133   # 실합(표기 계 23,974,813과 Δ1,648,320)
    assert 23_974_813 // 10 == 2_397_481          # 환급예정은 누락 계 기준(합산 시 2,562,313)


def test_capex_major_known_totals_single_source_sync():
    # 2026-08-18 53차(레드팀 4회차 F8 구조 개선) — known_total은 엔진 상수
    # CAPEX_MAJOR_KNOWN_TOTALS가 단일 출처다(build_site major_totals가 직접 읽음 —
    # 종전 이중 하드코딩은 한쪽만 드리프트해도 테스트가 못 잡았다). 값 자체는 위
    # 케이스별 reconcile 테스트의 원문 리터럴(cb.total == N)이 고정하고, 여기서는
    # 표본 3상수의 키 집합 동기를 고정한다(새 표본을 한쪽에만 추가하면 실패).
    assert (set(e.CAPEX_MAJOR_KNOWN_TOTALS)
            == set(e.CAPEX_MAJOR_CASE_CHUNKS)
            == set(e.CAPEX_MAJOR_UNCLASSIFIED))


def test_capex_major_breakdown_unmapped_categories_default_zero():
    # 근거 없는 7개(부대시설·기자재구매·설계감리비·부지조성비·예비비·부지매입비, 8번 등)는 0
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["우민재"],
                                 known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["우민재"])
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
