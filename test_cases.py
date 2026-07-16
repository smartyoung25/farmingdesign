"""
케이스 로더 견고성 + 사이트 렌더 회귀 테스트
- load_cases: 빈 파일/불량 JSON/필수키 결여 파일 스킵, 정상 케이스만 로드.
- comparison_page: IRR None(초고수익 → 이분법 범위 초과) 시 크래시 없이 '>100%' 렌더.
실행: pytest test_cases.py -q
"""
import json, importlib
import cases as C
import build_site as bs


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
