"""
케이스 로더 견고성 + 사이트 렌더 회귀 테스트
- load_cases: 빈 파일/불량 JSON/필수키 결여 파일 스킵, 정상 케이스만 로드.
- comparison_page: IRR None(초고수익 → 이분법 범위 초과) 시 크래시 없이 '>100%' 렌더.
- opex_breakdown: 케이스 스키마 v2(Step5) 필드가 엔진 계산과 어긋나지 않는지 드리프트 가드.
- consulting_report_page: Step6 4섹션 통합 리포트가 케이스 3건 전부 크래시 없이
  렌더되고 핵심 KPI·CAPEX 분해 유무 분기가 올바른지 스모크 테스트.
실행: pytest test_cases.py -q
"""
import json, importlib, os
import cases as C
import build_site as bs
import render_report as rr
import smartfarm_engine as e


def test_load_cases_skips_empty_and_invalid(tmp_path, monkeypatch):
    d = tmp_path / "cases"
    d.mkdir()
    (d / "empty.json").write_text("", encoding="utf-8")            # 빈 파일(tombstone)
    (d / "broken.json").write_text("{not json", encoding="utf-8")  # 불량 JSON
    (d / "nokey.json").write_text('{"foo":1}', encoding="utf-8")   # 필수키 없음
    good = {"case_id": "good", "title": "정상", "as_of": "2026-07",
            "input": {"business_type": "신규", "crop": "토마토", "region": "충남",
                      "area_m2": 3456, "cover": "유리", "snow_cm": 30, "wind_ms": 35,
                      "surface_area_m2": 5000, "t_target": 10, "t_min": -7.8, "fr": 0.7,
                      "base_yield_kg_m2": 38.5, "price_won_per_kg": 2500, "fitness_pct": 95,
                      "opex": 186420000, "total_construction_cost": 702030000,
                      "subsidy_rate": 0.5}}
    (d / "good.json").write_text(json.dumps(good, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(C, "CASES_DIR", str(d))
    loaded = C.load_cases()
    assert [c["case_id"] for c in loaded] == ["good"]
    # 변환도 정상
    inp = C.case_to_input(loaded[0])
    assert inp.cover.value == "유리" and inp.subsidy_rate == 0.5


def test_comparison_page_handles_none_irr():
    synth = {"case": {"title": "초고수익(합성)", "as_of": "t", "provenance": {}},
             "res": {"construction": {"unit_won_m2": 200000, "status": "정상"},
                     "heating": {"load_per_m2": 96},
                     "economics": {"roi": 2.5, "payback": 0.4, "npv": 5e8,
                                   "irr": None, "real_roi": 5.0}}}
    html = bs.comparison_page([synth])   # 크래시 없어야 함
    assert ">100%" in html


def test_case_opex_breakdown_matches_engine_and_input():
    # 케이스 JSON의 opex_breakdown 필드(Step5, 2026-07-21)가 실제
    # smartfarm_engine.opex_breakdown() 재계산과 항상 일치해야 한다 — 수기로
    # 적어둔 unclassified_won이 코드와 어긋나면(항목 추가 후 갱신 누락 등)
    # 이 테스트가 잡아낸다. known_total_won은 input.opex와도 같아야 한다.
    checked = 0
    for case in C.load_cases():
        ob = case.get("opex_breakdown")
        if ob is None:
            continue
        result = e.opex_breakdown(ob["items_won"], ob["known_total_won"])
        assert result.unclassified == ob["unclassified_won"], case["case_id"]
        assert ob["known_total_won"] == case["input"]["opex"], case["case_id"]
        checked += 1
    assert checked == 3  # 원채원·춘천·우민재


def test_consulting_report_page_renders_all_cases_without_crashing():
    checked = 0
    for case in C.load_cases():
        if case.get("partial"):   # P3-21d: 부분 케이스는 4축 통합보고서 비대상
            continue
        inp = C.case_to_input(case)
        res = rr.compute(inp)
        html = bs.consulting_report_page(case, res, inp)
        assert "경영자 요약" in html and "Ⅰ. 입지진단서" in html
        assert "Ⅱ. 설계적정성보고서" in html and "Ⅲ. 운영계획서" in html
        assert "Ⅳ. 경제성분석서" in html
        checked += 1
    assert checked == 3


def test_consulting_report_page_shows_capex_breakdown_only_when_present():
    # 우민재는 capex_breakdown.major_categories_won_2026_07_16이 있어 항목분해
    # 표가 나와야 하고, 원채원은 없어 "없음" 안내문이 나와야 한다.
    cases_by_id = {c["case_id"]: c for c in C.load_cases()}
    uminjae, wonchaewon = cases_by_id["uminjae"], cases_by_id["wonchaewon"]
    html_with = bs.consulting_report_page(uminjae, rr.compute(C.case_to_input(uminjae)),
                                          C.case_to_input(uminjae))
    html_without = bs.consulting_report_page(wonchaewon, rr.compute(C.case_to_input(wonchaewon)),
                                             C.case_to_input(wonchaewon))
    assert "CAPEX 항목분해" in html_with
    assert "CAPEX 항목분해 실측 데이터가 없어" in html_without


# ── P3-23(2026-08-17): compare_quotes 파이프라인 연결 회귀 ──────────────

def test_quotes_json_sums_are_exact():
    # 공종별 전사의 무결성(확장 2026-08-17: 전 견적비교 파일 glob):
    # 카테고리 합 == raw_rows 합 == 직접공사비 총액(원단위) — 전사·매핑 어느
    # 쪽이 어긋나도 잡힌다. 파일이 늘어나면 자동으로 검사 대상에 포함된다.
    import glob as _g
    files = sorted(_g.glob("견적비교_*.json"))
    assert len(files) >= 2                      # 논산딸기3사 + 군산무화과 규격대안
    for path in files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["comparison_id"] and len(data["vendor_quotes"]) >= 2, path
        for v in data["vendor_quotes"]:
            cat_sum = sum(v["categories"].values())
            raw_sum = sum(r[1] for r in v["raw_rows"])
            assert cat_sum == v["direct_cost_total"], (path, v["vendor_name"])
            assert raw_sum == v["direct_cost_total"], (path, v["vendor_name"])
            assert v["total_with_overhead"] >= v["direct_cost_total"]


def test_quotes_comparison_gunsan_fig_variant_pair():
    # 규격 대안 비교(동일 사업량 125×75 vs 75×75): 필수 공종은 축소 3종
    # (무가온이라 hvac 제외 — 판단성 입력)이며 두 안 모두 완전해야 한다.
    data, rfq, cmp = bs.load_quotes_comparison("견적비교_군산무화과_규격대안.json")
    assert rfq.required_categories == ["greenhouse_structure", "auto_opening_system",
                                       "irrigation_fertigation"]
    for name, recon in cmp.reconciliations.items():
        c = next(x for x in recon.checks if x.name == "필수 공종 완전성")
        assert c.status == "일치", name
    # 규격 차이의 실측 가격차: A안(125×75)이 B안보다 비싸다(합계 3,984,219원 차)
    a, b = cmp.rows[0], cmp.rows[1]
    assert a.total_with_overhead_won - b.total_with_overhead_won == 3_984_219


def test_quotes_comparison_pipeline_flags_expected_signals():
    data, rfq, cmp = bs.load_quotes_comparison()
    # RFQ가 P1-11 crop 필터·P1-9 curtain 경로로 생성됨
    assert rfq.spec_name and rfq.heating.max_load_kcal_h > 0
    # 임미라: hvac 누락(혼재 표기 검출)이 플래그돼야 한다 — 핵심 컨설팅 신호
    recon = cmp.reconciliations["임미라(수현건설)"]
    comp_check = next(c for c in recon.checks if c.name == "필수 공종 완전성")
    assert comp_check.status == "불일치" and "hvac" in comp_check.detail
    # 최선동·한수진: 필수 공종은 완전
    for name in ("최선동(렉창)", "한수진"):
        c = next(c for c in cmp.reconciliations[name].checks if c.name == "필수 공종 완전성")
        assert c.status == "일치", name
    # 3사 모두 벤치마크 밴드 내(참고정보), 추천 필드는 존재하되 판정 아님
    assert all(115000 <= r.unit_won_m2 <= 240000 for r in cmp.rows)
    assert cmp.lowest_cost_vendor == "임미라(수현건설)"


def test_quotes_comparison_page_renders():
    data, rfq, cmp = bs.load_quotes_comparison()
    html_out = bs.quotes_comparison_page(data, rfq, cmp)
    assert "추천" in html_out and "참고정보" in html_out   # 판단성 존중 문구
    assert "hvac" in html_out                              # 누락 신호 노출
    assert "원단위 전사" in html_out                        # 출처 표기
    for v in data["vendor_quotes"]:
        assert v["vendor_name"] in html_out


# ── P3-18(2026-08-17): 금융조달 상환표 렌더 분기 ────────────────────────

def test_consulting_report_financing_section_conditional():
    # financing 블록이 없으면 안내문, 있으면 상환표가 렌더돼야 한다.
    # 케이스 원본엔 실제 대출조건이 없으므로(가공값 금지) 사본에만 합성 블록을 넣어 검증.
    cases_by_id = {c["case_id"]: c for c in C.load_cases()}
    base = cases_by_id["uminjae"]
    res = rr.compute(C.case_to_input(base))
    html_without = bs.consulting_report_page(base, res, C.case_to_input(base))
    assert "대출조건 미제공" in html_without
    assert "연차별 대출상환표" not in html_without

    with_fin = dict(base)
    with_fin["financing"] = {"loan_principal_won": 100_000_000, "annual_rate_pct": 2.0,
                             "term_years": 5, "grace_years": 2, "method": "원리금균등",
                             "note": "테스트 합성 조건(케이스 실데이터 아님)"}
    html_with = bs.consulting_report_page(with_fin, res, C.case_to_input(base))
    assert "연차별 대출상환표" in html_with and "거치 2년" in html_with
    assert "테스트 합성 조건" in html_with


# ── P3-21d(2026-08-17): 이용균 부분 케이스(시공축 전용) ─────────────────

def test_partial_case_yonggyun_loads_and_is_arithmetically_consistent():
    cases_by_id = {c["case_id"]: c for c in C.load_cases()}
    y = cases_by_id["yonggyun"]
    assert y.get("partial") == "construction_only"
    cs = y["construction"]["cost_summary_won"]
    # 원문 3중 검증 구조가 JSON에서도 유지되는지 산술 가드
    assert cs["직접재료비"] + cs["직접노무비"] + cs["경비"] == cs["직접공사비"]
    assert cs["공급가액"] + cs["부가가치세"] == cs["합계"]
    assert cs["도급비(만단위 절사)"] == 506_000_000
    trades = y["construction"]["trades_material_won"]
    assert sum(trades.values()) == cs["직접재료비"]      # 집계표 ↔ 원가계산서 대사
    assert y["input"]["total_construction_cost"] == 506_000_000


def test_partial_case_renders_construction_page_and_skips_4axis():
    cases_by_id = {c["case_id"]: c for c in C.load_cases()}
    y = cases_by_id["yonggyun"]
    html_out = bs.partial_construction_page(y)
    assert "시공축 부분 케이스" in html_out or "부분 케이스" in html_out
    assert "506,000,000" in html_out                  # 도급비
    assert "골조(MS신형 125-75)" in html_out           # 공종 표
    assert "벤치마크" in html_out                      # benchmark_check 연동
    assert "ROI" not in html_out                       # 4축 경제성 미산출(가공값 금지)
    # 로더가 partial을 정상 케이스로 오인해 FarmInput 변환을 시도하면 안 된다
    import pytest as _pt
    with _pt.raises(TypeError):
        C.case_to_input(y)   # 필수 필드 없음 — 부분 케이스는 이 경로로 못 감(main이 분기)


# ── financing 기입양식(2026-08-18): 예시 파일 무결성 ─────────────────────

def test_financing_example_file_is_valid_and_clearly_synthetic():
    # 예시 파일은 (a) 스키마대로 엔진 계산이 돌아가야 하고, (b) 합성 예시임이
    # 명시돼 있어야 하며(실케이스 오염 방지), (c) cases/ 밖에 있어야 한다.
    with open("financing_예시.json", encoding="utf-8") as f:
        data = json.load(f)
    fin = data["financing"]
    assert "예시" in fin["note"] or "합성" in fin["note"]
    am = e.loan_amortization(fin["loan_principal_won"], fin["annual_rate_pct"],
                             fin["term_years"], fin.get("grace_years", 0), fin["method"])
    assert len(am["rows"]) == fin["term_years"]
    assert am["rows"][-1]["잔액"] == 0.0
    assert not os.path.exists(os.path.join("cases", "financing_예시.json"))


# ── 시나리오 가정값 스키마(2026-08-18, 데이터 대기 ④) ───────────────────

def _uminjae_with_example_scenarios():
    cases_by_id = {c["case_id"]: c for c in C.load_cases()}
    base = cases_by_id["uminjae"]
    with open("시나리오_예시.json", encoding="utf-8") as f:
        sc = json.load(f)["scenarios"]
    return dict(base, scenarios=sc), C.case_to_input(base)


def test_scenario_rows_engine_recompute_and_direction():
    case, inp = _uminjae_with_example_scenarios()
    rows = bs.scenario_rows(case, inp)
    assert rows[0]["name"].startswith("Base") and len(rows) == 4   # Base + 3세트
    by = {r["name"]: r["res"]["economics"] for r in rows}
    # 방향성: 수확·단가 상향(Best)은 Base보다 ROI 상승, Worst는 하락(엔진 재계산 일관성)
    assert by["Best"]["roi"] > by["Base(케이스 입력)"]["roi"] > by["Worst"]["roi"]
    # 예시 무결성: 합성 명시·cases/ 밖
    with open("시나리오_예시.json", encoding="utf-8") as f:
        note = json.load(f)["scenarios"]["note"]
    assert "예시" in note or "합성" in note
    assert not os.path.exists(os.path.join("cases", "시나리오_예시.json"))


def test_scenario_rows_rejects_bad_fields_and_missing_note():
    import pytest as _pt
    case, inp = _uminjae_with_example_scenarios()
    bad = dict(case, scenarios={"note": "t", "sets": [
        {"name": "X", "assumptions": {"snow_cm": 100}, "note": "물리 입력 변경 시도"}]})
    with _pt.raises(ValueError):
        bs.scenario_rows(bad, inp)          # 화이트리스트 밖 필드 거부
    noname = dict(case, scenarios={"note": "t", "sets": [
        {"name": "Y", "assumptions": {"opex": 1_000_000}, "note": ""}]})
    with _pt.raises(ValueError):
        bs.scenario_rows(noname, inp)       # 근거(note) 필수


def test_scenario_section_renders_conditionally_and_irr_label():
    case, inp = _uminjae_with_example_scenarios()
    res = rr.compute(inp)
    html_with = bs.consulting_report_page(case, res, inp)
    assert "시나리오 표 (가정 주입" in html_with and "Worst" in html_with
    assert "산출불가(적자)" in html_with     # 적자 시나리오 IRR 오독 방지 분기
    cases_by_id = {c["case_id"]: c for c in C.load_cases()}
    plain = cases_by_id["uminjae"]
    html_without = bs.consulting_report_page(plain, res, inp)
    assert "시나리오 가정값 미제공" in html_without
    assert "시나리오 표 (가정 주입" not in html_without


# ── 리모델링 실측 사례(2026-08-18, 데이터 대기 ③ 표본 1호) ──────────────

def test_partial_case_mulhyangki_remodeling_structure():
    cases_by_id = {c["case_id"]: c for c in C.load_cases()}
    mh = cases_by_id["mulhyangki"]
    assert mh.get("partial") == "construction_only"
    assert "재축" in mh["input"]["business_type"]
    cs = mh["construction"]["cost_summary_won"]
    # 총액 3중 대사 구조: 절사 전 89,610,883 → 천단위 절사 89,610,000(한글 대사)
    assert cs["원가계산 합계(절사 전)"] == 89_610_883
    assert cs["총공사비(도급, 천단위 절사)"] == 89_610_000
    assert mh["input"]["total_construction_cost"] == 89_610_000
    # 리모델링 특유 구조: 철거비·부산물 공제(음수)·폐기물처리 실존
    trades = mh["construction"]["trades_material_won"]
    assert any("철거" in k for k in trades)
    assert any(v < 0 for v in trades.values())          # 고철 매각 공제
    assert any("폐기물" in k for k in trades)
    # 부분 발췌임이 명시돼야 한다(전액 대사로 오독 방지)
    assert "부분 발췌" in mh["construction"]["trades_note"]


def test_partial_case_mulhyangki_renders():
    cases_by_id = {c["case_id"]: c for c in C.load_cases()}
    mh = cases_by_id["mulhyangki"]
    html_out = bs.partial_construction_page(mh)
    assert "재축" in html_out and "폭설피해복구" in html_out
    assert "89,610,000" in html_out
    assert "-432,000" in html_out or "−432,000" in html_out   # 공제 항목 노출
    assert "ROI" not in html_out                              # 4축 미산출 유지
