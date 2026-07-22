"""
케이스 로더 견고성 + 사이트 렌더 회귀 테스트
- load_cases: 빈 파일/불량 JSON/필수키 결여 파일 스킵, 정상 케이스만 로드.
- comparison_page: IRR None(초고수익 → 이분법 범위 초과) 시 크래시 없이 '>100%' 렌더.
- opex_breakdown: 케이스 스키마 v2(Step5) 필드가 엔진 계산과 어긋나지 않는지 드리프트 가드.
- consulting_report_page: Step6 4섹션 통합 리포트가 케이스 3건 전부 크래시 없이
  렌더되고 핵심 KPI·CAPEX 분해 유무 분기가 올바른지 스모크 테스트.
실행: pytest test_cases.py -q
"""
import json, importlib
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
