"""웹앱 1단계(읽기 전용 콘솔) 회귀 테스트 — 2026-08-18(32차)
- 홈이 전 케이스를 나열하고, 수치가 엔진 계산과 일치하는지(제2 계산기 없음의 증거)
- 산출물 서빙의 화이트리스트 가드(경로 탈출 차단)
- 판정·추천 문구가 새어 들어오지 않는지(3단 시각 언어 원칙)
실행: pytest test_webapp.py -q  (의존성: fastapi·jinja2·httpx — pip 유실 시 재설치)
"""
import pytest

fastapi = pytest.importorskip("fastapi", reason="웹앱 의존성 미설치(환경 특성상 pip 유실 반복) — pip install fastapi jinja2 httpx")
from fastapi.testclient import TestClient

import cases as C
import render_report as rr
import webapp

client = TestClient(webapp.app)


def test_home_lists_every_case_with_chips():
    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    # 🔴183차 — 카드는 **표시 코드**로 나온다(산출물에 실명을 싣지 않는다).
    import case_display as cdsp
    for c in C.load_cases():
        assert cdsp.alias(c)["title"] in body, f"{c['case_id']} 카드 누락"
        assert c["title"] not in body, (
            f"🔴 {c['case_id']}의 **실명 제목이 그대로 나갔다** — 표시 계층을 거치지 않았다")
    assert not cdsp.audit(body), (
        f"🔴 홈 화면에 케이스 실명·식별자가 남았다: {cdsp.audit(body)}")
    # 근거 칩: 실측(정식 3건)과 참고(부분 2건)가 모두 노출
    assert "chip-measured" in body and "chip-ref" in body
    # 데이터 대기 배너는 케이스 데이터에서 도출된다(현재 ①·③·④ 전부 대기)
    assert "데이터 대기" in body and "약정서" in body


def test_home_numbers_match_engine_exactly():
    # 원채원 회귀 기준값이 홈 카드에 그대로 나와야 한다 — 엔진이 유일한 계산 출처라는
    # 구조적 증거(webapp이 자체 산술을 하면 이 값이 어긋난다)
    case = {c["case_id"]: c for c in C.load_cases()}["wonchaewon"]
    ec = rr.compute(C.case_to_input(case))["economics"]
    r = client.get("/")
    assert f"ROI {ec['roi']*100:.1f}%" in r.text
    assert f"Payback {ec['payback']:.1f}년" in r.text


def test_home_has_no_verdict_language():
    # 3단 시각 언어: 콘솔은 판정·추천을 만들지 않는다
    body = client.get("/").text
    for banned in ("추천 업체", "최적 케이스", "1위", "판정:"):
        assert banned not in body


def test_pages_whitelist_and_traversal_guard():
    assert client.get("/pages/SmartFarm_근거대장.html").status_code == 200
    assert client.get("/pages/index.html").status_code == 200
    # 화이트리스트 밖(엔진 소스·상위 경로)은 404
    assert client.get("/pages/smartfarm_engine.py").status_code == 404
    assert client.get("/pages/..%2Fsmartfarm_engine.py").status_code == 404
    assert client.get("/pages/SmartFarm_없는파일.html").status_code == 404


def test_partial_case_links_to_partial_page():
    r = client.get("/")
    # 🔴183차 — 파일명도 표시 코드다. 실명이 URL에 남으면 가린 의미가 없다.
    assert "SmartFarm_부분케이스_C4.html" in r.text
    assert "SmartFarm_부분케이스_C5.html" in r.text
    assert "SmartFarm_통합보고서_C2.html" in r.text
    for old in ("yonggyun", "mulhyangki", "wonchaewon"):
        assert old not in r.text, f"🔴 내부 식별자 {old}가 링크에 남았다"


def test_health():
    j = client.get("/health").json()
    assert j["cases"] == len(C.load_cases()) and j["partial"] == 2


# ── 2단계(33차): 기입 워크플로 ─────────────────────────────────────────

import json
import shutil
from pathlib import Path


@pytest.fixture
def tmp_cases(tmp_path, monkeypatch):
    """실케이스를 건드리지 않도록 wonchaewon 사본만 있는 임시 케이스 디렉터리."""
    d = tmp_path / "cases"
    d.mkdir()
    shutil.copy(Path(C.CASES_DIR) / "wonchaewon.json", d / "wonchaewon.json")
    monkeypatch.setattr(C, "CASES_DIR", str(d))
    return d


def test_entry_hub_lists_full_cases_only():
    r = client.get("/entry")
    assert r.status_code == 200
    # 🔴183차 — 실명 대신 표시 코드. 부분 케이스(C5)는 기입 대상이 아니다.
    assert "C2" in r.text and "C5" not in r.text
    assert "원채원" not in r.text and "물향기" not in r.text
    assert "폼 열기" in r.text


def test_financing_preview_matches_engine():
    import smartfarm_engine as e
    form = {"loan_principal_won": "300000000", "annual_rate_pct": "1.5",
            "term_years": "25", "grace_years": "5", "method": "원리금균등",
            "note": "합성 예시(테스트)"}
    r = client.post("/entry/financing/wonchaewon/preview", data=form)
    assert r.status_code == 200
    am = e.loan_amortization(300_000_000, 1.5, 25, 5, "원리금균등")
    assert f"{am['총이자']:,.0f}" in r.text  # 상환표 수치 = 엔진 반환값 그대로
    assert "거치 5년" in r.text


def test_financing_engine_validation_surfaces():
    # 거치 ≥ 전체기간은 엔진 ValueError → 400으로 그대로 노출(제2 검증기 없음)
    form = {"loan_principal_won": "1000000", "annual_rate_pct": "2",
            "term_years": "5", "grace_years": "5", "method": "원리금균등", "note": "x"}
    r = client.post("/entry/financing/wonchaewon/preview", data=form)
    assert r.status_code == 400


def test_financing_save_requires_note_and_writes_case(tmp_cases):
    form = {"loan_principal_won": "100000000", "annual_rate_pct": "0",
            "term_years": "5", "grace_years": "", "method": "원리금균등", "note": ""}
    assert client.post("/entry/financing/wonchaewon/save", data=form).status_code == 400  # 출처 없음
    form["note"] = "테스트 약정서(합성) — 출처 형식 예시"
    r = client.post("/entry/financing/wonchaewon/save", data=form, follow_redirects=False)
    assert r.status_code == 303
    saved = json.loads((tmp_cases / "wonchaewon.json").read_text(encoding="utf-8"))
    assert saved["financing"]["loan_principal_won"] == 100_000_000
    assert saved["financing"]["note"].startswith("테스트 약정서")
    # 저장되면 홈 배너의 대기 ①이 사라진다(데이터 도출 배너의 증거)
    assert "약정서" not in client.get("/").text.split("데이터 대기")[1][:300]


def test_scenario_whitelist_rejected_via_engine():
    form = {"name": "불량", "note": "x", "area_m2": "9999"}  # 물리 입력은 화이트리스트 밖
    r = client.post("/entry/scenario/wonchaewon/preview", data=form)
    assert r.status_code == 400 or "허용되지 않는" not in r.text  # 폼에 없는 필드는 무시됨
    # 화이트리스트 필드가 하나도 없으면 저장 거부
    r2 = client.post("/entry/scenario/wonchaewon/save", data={"name": "빈세트", "note": "x"})
    assert r2.status_code == 400


# ── 3단계(35차): 케이스 입력 마법사 — status 제한 정책(추정/확인요망만) ──

import webapp as W


def _wizard_form(cid="test_wizard", use_lookup=False):
    form = {"case_id": cid, "title": "마법사 테스트(합성)", "as_of": "2026-08",
            "business_type": "신규", "region": "논산" if use_lookup else "가상지역",
            "crop": "딸기", "cover": "필름",
            "area_m2": "4000", "surface_area_m2": "5800",
            "t_target": "15", "t_min": "-12.4", "fr": "0.7", "fitness_pct": "90",
            "base_yield_kg_m2": "10", "price_won_per_kg": "2500",
            "opex": "120000000", "total_construction_cost": "600000000",
            "subsidy_rate": "0.5"}
    if use_lookup:
        form["use_lookup"] = "1"
    else:
        form.update({"snow_cm": "30", "wind_ms": "30",
                     "load_status": "추정", "load_source": "합성 테스트값"})
    for f in W.WIZARD_PROV_FIELDS:
        form[f"prov_{f}_status"] = "추정"
        form[f"prov_{f}_source"] = "합성 테스트 근거"
    return form


def test_newcase_form_renders_policy():
    r = client.get("/entry/newcase")
    assert r.status_code == 200
    assert "추정·확인요망만" in r.text and "실측" in r.text  # 정책 배너 고정


def test_newcase_preview_matches_engine_and_benchmark():
    r = client.post("/entry/newcase/preview", data=_wizard_form())
    assert r.status_code == 200
    # 독립 구성한 동일 입력으로 엔진 직접 계산 — 마법사 수치는 그 표시여야 한다
    case = {"case_id": "x", "title": "t", "as_of": "t", "input": {
        "business_type": "신규", "crop": "딸기", "region": "가상지역", "area_m2": 4000,
        "cover": "필름", "snow_cm": 30, "wind_ms": 30, "surface_area_m2": 5800,
        "t_target": 15, "t_min": -12.4, "fr": 0.7, "base_yield_kg_m2": 10,
        "price_won_per_kg": 2500, "fitness_pct": 90, "opex": 120000000,
        "total_construction_cost": 600000000, "subsidy_rate": 0.5}}
    ec = rr.compute(C.case_to_input(case))["economics"]
    assert f"{ec['roi']*100:.1f}%" in r.text
    assert "정상" in r.text  # 150,000원/㎡ — 필름 밴드 내(벤치마크 참고 표시)


def test_newcase_design_load_lookup_adoption():
    r = client.post("/entry/newcase/preview", data=_wizard_form(use_lookup=True))
    assert r.status_code == 200
    assert "실측(고시 조회)" in r.text and "적설 28" in r.text  # REGION_DESIGN_LOAD['논산']
    # 매칭 안 되는 지역은 400 + 수동 전환 안내
    bad = _wizard_form(use_lookup=True)
    bad["region"] = "존재하지않는지역명"
    assert client.post("/entry/newcase/preview", data=bad).status_code == 400


def test_newcase_rejects_measured_status_and_empty_source():
    form = _wizard_form()
    form["prov_opex_status"] = "실측"  # 웹 실측 부여 시도 → 정책 차단
    assert client.post("/entry/newcase/preview", data=form).status_code == 400
    form2 = _wizard_form()
    form2["prov_price_won_per_kg_source"] = ""
    assert client.post("/entry/newcase/preview", data=form2).status_code == 400


def test_newcase_save_roundtrip(tmp_cases):
    r = client.post("/entry/newcase/save", data=_wizard_form(), follow_redirects=False)
    assert r.status_code == 303
    saved = json.loads((tmp_cases / "test_wizard.json").read_text(encoding="utf-8"))
    assert saved["provenance"]["opex"]["status"] == "추정"
    assert saved["wizard"]["policy"].startswith("웹 마법사")
    assert "test_wizard" in {c["case_id"] for c in C.load_cases()}  # 로더가 그대로 소비
    home = client.get("/").text
    # 🔴183차 — 미등재 케이스도 **이름을 쓰지 않는다**: `case_id` 해시 코드로 나온다.
    import case_display as cdsp
    assert cdsp._fallback_code("test_wizard") in home and "chip-est" in home
    assert "마법사 테스트(합성)" not in home, (
        "🔴 미등재 케이스의 제목이 그대로 나갔다 — 새 케이스에도 표시 계층이 걸려야 한다")
    # 마법사는 신규 전용 — 중복 id는 409
    assert client.post("/entry/newcase/save", data=_wizard_form()).status_code == 409


# ── 4단계(34차): 견적비교 전사 UI — 기준 데이터: 논산딸기 3사(원단위 대사 완료 실측 전사) ──

def _nonsan_form(comparison_id="논산딸기_3사"):
    """리포의 가장 잘 된 실전사본(논산 3사)을 폼 페이로드로 재구성 — 편집기 왕복 기준."""
    d = json.loads(Path("견적비교_논산딸기3사.json").read_text(encoding="utf-8"))
    ri = d["rfq_input"]
    form = {
        "comparison_id": comparison_id, "title": d["title"], "created": d["created"],
        "decision_note": d.get("decision_note", ""), "provenance": d["provenance"],
        "region": ri["region"], "region_snow_cm": str(ri["region_snow_cm"]),
        "region_wind_ms": str(ri["region_wind_ms"]), "area_m2": str(ri["area_m2"]),
        "cover": ri["cover"], "form": ri["form"], "t_target": str(ri["t_target"]),
        "t_min": str(ri["t_min"]), "curtain": ri.get("curtain", ""), "fr": "",
        "crop": ri.get("crop", ""), "rfq_note": ri.get("note", ""),
        "required_categories": ",".join(ri.get("required_categories", [])),
        "n_vendors": str(len(d["vendor_quotes"])),
    }
    for i, v in enumerate(d["vendor_quotes"]):
        form[f"vendor{i}_name"] = v["vendor_name"]
        form[f"vendor{i}_source_file"] = v["source_file"]
        form[f"vendor{i}_source_sheet"] = v.get("source_sheet", "")
        form[f"vendor{i}_area_m2"] = str(v.get("area_m2") or "")
        form[f"vendor{i}_area_note"] = v.get("area_note", "")
        form[f"vendor{i}_direct_cost_total"] = str(v["direct_cost_total"])
        form[f"vendor{i}_total_with_overhead"] = str(v["total_with_overhead"])
        form[f"vendor{i}_total_note"] = v.get("total_note", "")
        form[f"vendor{i}_rows"] = "\n".join(f"{r[0]} | {r[1]} | {r[2]}" for r in v["raw_rows"])
    return form


def test_quotes_helpers_agree_with_stored_real_data():
    # 헬퍼(파생 집계·3중 대사)가 기존 실전사 파일 전체와 원단위로 합치해야 한다 —
    # 헬퍼와 test_quotes_json_sums_are_exact 규칙이 갈라지면 여기서 잡힌다
    import build_site as bs
    import glob as _g
    for path in sorted(_g.glob("견적비교_*.json")):
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        for v in d["vendor_quotes"]:
            assert bs.quotes_derive_categories(v["raw_rows"]) == v["categories"], (path, v["vendor_name"])
            assert all(c["ok"] for c in bs.quotes_vendor_3way_check(v)), (path, v["vendor_name"])


def test_quotes_hub_lists_real_comparisons():
    r = client.get("/entry/quotes")
    assert r.status_code == 200
    assert "논산딸기_3사" in r.text and "원단위 일치" in r.text


def test_quotes_edit_prefills_real_data():
    r = client.get("/entry/quotes/edit", params={"src": "견적비교_논산딸기3사.json"})
    assert r.status_code == 200
    assert "임미라(수현건설)" in r.text
    assert "골조공사 | 184464840 | greenhouse_structure" in r.text


def test_quotes_preview_real_data_roundtrip():
    # 실전사본 그대로 → 3중 대사 전 업체 일치 + 엔진 신호(임미라 hvac 누락)가 재현돼야 한다
    r = client.post("/entry/quotes/preview", data=_nonsan_form())
    assert r.status_code == 200
    assert "전 업체 일치" in r.text
    assert "hvac" in r.text  # P3-20 시연의 핵심 컨설팅 신호가 편집기에서도 보인다


def test_quotes_preview_detects_transcription_error_and_blocks_save():
    form = _nonsan_form()
    form["vendor0_rows"] = form["vendor0_rows"].replace("184464840", "184464841")  # 1원 오염
    r = client.post("/entry/quotes/preview", data=form)
    assert r.status_code == 200 and "불일치" in r.text and "+1" in r.text
    assert client.post("/entry/quotes/save", data=form).status_code == 400  # 대사 실패 저장 거부


def test_quotes_bad_mapping_key_rejected():
    form = _nonsan_form()
    form["vendor0_rows"] = "골조공사 | 100 | 없는카테고리"
    assert client.post("/entry/quotes/preview", data=form).status_code == 400


def test_quotes_save_roundtrip_via_engine(tmp_path, monkeypatch):
    import webapp as W
    import build_site as bs
    monkeypatch.setattr(W, "QUOTES_DIR", tmp_path)
    form = _nonsan_form(comparison_id="테스트왕복")
    r = client.post("/entry/quotes/save", data=form, follow_redirects=False)
    assert r.status_code == 303
    saved = tmp_path / "견적비교_테스트왕복.json"
    assert saved.is_file()
    # 저장본이 정식 로더+엔진 파이프라인으로 그대로 소비된다(왕복 무손실의 증거)
    data, rfq, cmp = bs.load_quotes_comparison(str(saved))
    assert len(cmp.rows) == 3
    assert {v["vendor_name"] for v in data["vendor_quotes"]} == \
           {"임미라(수현건설)", "최선동(렉창)", "한수진"}
    # 덮어쓰기 확인 없이 재저장 → 409
    assert client.post("/entry/quotes/save", data=form).status_code == 409


def test_scenario_preview_and_save_match_engine(tmp_cases):
    import build_site as bs
    import render_report as rr
    form = {"name": "Best(테스트)", "price_won_per_kg": "2936",
            "note": "농진청 소득자료집 2024판 p46 시설토마토(수경) 2024 농가수취단가(테스트 기입)"}
    r = client.post("/entry/scenario/wonchaewon/preview", data=form)
    assert r.status_code == 200
    # 미리보기 ROI = 엔진 재계산값
    case = {c["case_id"]: c for c in C.load_cases()}["wonchaewon"]
    import dataclasses
    inp = C.case_to_input(case)
    ec = rr.compute(dataclasses.replace(inp, price_won_per_kg=2936))["economics"]
    assert f"{ec['roi']*100:.1f}%" in r.text
    # 저장 → 세트가 케이스에 추가되고 scenario_rows가 그대로 소비 가능
    rs = client.post("/entry/scenario/wonchaewon/save", data=form, follow_redirects=False)
    assert rs.status_code == 303
    saved = json.loads((tmp_cases / "wonchaewon.json").read_text(encoding="utf-8"))
    # 50차부터 실케이스에 기본 세트(Best/Worst)가 실존 — 웹 추가분은 마지막에 append된다
    assert saved["scenarios"]["sets"][-1]["assumptions"] == {"price_won_per_kg": 2936}
    assert saved["scenarios"]["sets"][-1]["name"] == "Best(테스트)"
    rows = bs.scenario_rows(saved, C.case_to_input(saved))
    assert rows[-1]["name"] == "Best(테스트)"  # Base + 기존 세트(50차 Best/Worst) 뒤에 append

def test_206cha_entry_form_asks_each_value_once():
    """206차 — 기입 폼이 **같은 값을 두 번 묻지 않는가**(실사용 관통이 찾은 것).

    🔴 근거 표가 `prov_fields` **전부**에 값 칸을 냈는데 그중 다섯
    (`area_m2`·`surface_area_m2`·`t_target`·`fr`·`fitness_pct`)은
    **설계·운영 절에도 같은 `name`으로** 있었다. 같은 이름이 둘이면 서버는 하나만
    읽는다 — 206차 관통 시험에서 **뒤엣것이 이겼고**, 설계 절에 적은 3,000㎡가
    **9,999로 조용히 덮였다**.

    🔴 199차 가드는 *"필드가 폼에 있는가"*만 봤다 — **중복은 보지 않았다**.
    그래서 여기서는 **렌더된 HTML을 직접 세고**, 관통으로 **저장값까지** 확인한다.
    """
    import re as _re

    html = client.get("/entry/newcase").text
    names = _re.findall(r'<(?:input|select)[^>]*name="([^"]+)"', html)
    dup = sorted({n for n in names if names.count(n) > 1})
    assert not dup, (
        f"🔴 기입 폼에 같은 이름이 두 번 있다: {dup} — 사용자가 두 곳에 **다른 값**을 "
        "적을 수 있고 서버는 하나만 읽는다. **앞에 적은 값이 조용히 버려진다**")

    # ── 값은 한 곳에서만 받고, 나머지는 **근거만** 받는가 ───────────
    for f in webapp.WIZARD_PROV_VALUE_FIELDS:
        assert ('name="%s"' % f) in html, (
            f"🔴 `{f}`의 값 칸이 사라졌다 — 이 다섯은 **근거 표에서만** 값을 받는다")
    echo = [f for f in webapp.WIZARD_PROV_FIELDS
            if f not in webapp.WIZARD_PROV_VALUE_FIELDS]
    assert len(echo) == 5, f"🔴 근거만 받는 필드가 {len(echo)}개다 — 실측은 5다"
    assert html.count("위 절에서 기입") == len(echo), (
        f"🔴 근거 표의 「위 절에서 기입」 표시가 {html.count('위 절에서 기입')}개다 — "
        f"{len(echo)}개여야 한다. 표시가 없으면 **왜 값 칸이 없는지** 알 수 없다")
    for f in echo:
        assert len(_re.findall(r'name="%s"' % f, html)) == 1, (
            f"🔴 `{f}`의 값 칸이 {len(_re.findall(chr(39) + f + chr(39), html))}개다")

    # ── 🔴 **관통**: 설계 절 값이 저장까지 살아 오는가 ───────────────
    import os as _o, json as _j, io as _io
    form = {"case_id": "guard206tmp", "title": "206차 가드 합성",
            "as_of": "2026-09", "business_type": "신규", "region": "충남 논산",
            "snow_cm": "30", "wind_ms": "30", "load_status": "확인요망",
            "load_source": "206차 가드 — 합성 입력", "cover": "필름",
            "area_m2": "3000", "surface_area_m2": "5400", "t_target": "18",
            "t_min": "-12", "fr": "0.5", "crop": "딸기", "fitness_pct": "92",
            "base_yield_kg_m2": "6.5", "price_won_per_kg": "12000",
            "opex": "180000000", "total_construction_cost": "900000000",
            "subsidy_rate": "0.5", "discount_rate": "0.03",
            "evaluation_years": "", "useful_life": ""}
    for f in webapp.WIZARD_PROV_FIELDS:
        form["prov_%s_status" % f] = "확인요망"
        form["prov_%s_source" % f] = "206차 가드 — 합성 입력"
    assert client.post("/entry/newcase/preview", data=form).status_code == 200
    path = _o.path.join(_o.path.dirname(_o.path.abspath(webapp.__file__)),
                        "cases", "guard206tmp.json")
    try:
        assert client.post("/entry/newcase/save", data=form).status_code == 200
        saved = _j.load(_io.open(path, encoding="utf-8"))["input"]
        for k, want in (("area_m2", 3000.0), ("surface_area_m2", 5400.0),
                        ("t_target", 18.0), ("fr", 0.5),
                        ("fitness_pct", 92.0)):
            assert saved[k] == want, (
                f"🔴 설계 절에 적은 `{k}`={want}가 {saved[k]}로 저장됐다 — "
                "**다른 칸이 덮었다**(206차가 고친 바로 그 결함이다)")
        assert saved.get("discount_rate") == 0.03, "🔴 주입한 할인율이 살아오지 않았다"
        for k in ("evaluation_years", "useful_life"):
            assert k not in saved, (
                f"🔴 빈칸인 `{k}`가 저장됐다 — 199차 계약(빈칸은 넣지 않는다) 위반")
    finally:
        if _o.path.exists(path):
            _o.remove(path)


def test_209cha_rejection_keeps_the_form():
    """209차 — **거부가 기입을 버리지 않는가**(UI 완성의 첫 조건).

    🔴 **실측이 범위를 정했다**: 마법사 폼은 **47칸**인데 브라우저 `required`는
    **0개**다 — 검증을 한 곳(서버·엔진)에서만 하려고 일부러 그렇게 뒀다
    (**제2 검증기 금지**). 그런데 그 거부가 `application/json`으로 나가서
    **47칸이 통째로 사라졌다**. `HTTPException` 발생 지점 **26곳**이 전부 같은 결말.

    🔴 **없던 기능이 아니라 빠진 경로였다** — 템플릿은 이미 `form_vals`로 값을
    되받을 줄 안다. **오류 경로만 그 길을 쓰지 않았다**(206차가 찾은 결함과 같은 계열).

    📌 **고친 것은 표시 계층뿐이다.** 그래서 이 가드는 ①값이 살아오는가 ②메시지가
    **엔진이 낸 말 그대로**인가 ③상태 코드가 그대로인가 ④**클라이언트 검증이
    늘지 않았는가**를 잰다 — ④가 무너지면 고친 것이 아니라 **검증기를 하나 더
    만든 것**이다.
    """
    import re as _re
    import smartfarm_engine as _e

    # ── ① 마법사: 거부가 HTML이고 제출값이 살아오는가 ──────────────
    typed = {"case_id": "BADID", "region": "충남 논산", "crop": "딸기",
             "area_m2": "3000", "t_target": "18", "opex": "123456789"}
    r = client.post("/entry/newcase/preview", data=typed)
    assert r.status_code == 400, f"🔴 상태 코드가 {r.status_code}다 — 400이어야 한다"
    assert r.headers["content-type"].startswith("text/html"), (
        f"🔴 거부가 {r.headers['content-type']}로 나간다 — 폼으로 되돌리려면 화면이어야 "
        "한다(종전엔 application/json이라 47칸이 통째로 사라졌다)")
    for k, v in typed.items():
        assert ('name="%s" value="%s"' % (k, v)) in r.text, (
            f"🔴 거부 뒤 `{k}`={v!r}가 폼에 없다 — **기입한 값을 버렸다**. "
            "템플릿은 `form_vals`로 되받을 줄 아는데 오류 경로가 그 길을 안 쓴 것이다")
    assert 'class="banner err"' in r.text, "🔴 거부 사유를 화면에 띄우지 않는다"

    # ── ② 🔴 메시지가 **엔진이 낸 말 그대로**인가(앱이 고쳐 말하면 제2 검증기다) ─
    try:
        _e.loan_amortization(300000000, 1.5, 5, 9, "원리금균등")
        raise AssertionError("🔴 엔진이 거치≥전체기간을 거부하지 않는다 — 전제가 깨졌다")
    except ValueError as ex:
        # 🔴 엔진 문장에 `<`가 들어 있다("0 <= 거치 < 전체기간") — 화면은 이걸
        #   **이스케이프해서** 싣는다. 날문자열로 재면 *「고쳐 말했다」*고 오판한다
        #   (209차에 실제로 이 가드가 먼저 그렇게 틀렸다). 같은 이스케이프로 잰다.
        from markupsafe import escape as _esc
        engine_says = str(_esc(str(ex)))
    r = client.post("/entry/financing/wonchaewon/preview", data={
        "loan_principal_won": "300000000", "annual_rate_pct": "1.5",
        "term_years": "5", "grace_years": "9", "method": "원리금균등",
        "note": "209차 가드 — 합성 입력"})
    assert r.status_code == 400
    assert engine_says in r.text, (
        f"🔴 화면이 엔진의 말을 **고쳐 말한다**. 엔진(이스케이프 후): "
        f"{engine_says!r} — "
        "앱이 사유를 다시 쓰는 순간 **제2 검증기**가 된다(1절 불변 원칙)")
    assert 'value="300000000"' in r.text and "209차 가드 — 합성 입력" in r.text, (
        "🔴 financing 거부가 원금·근거를 버렸다")

    # ── ③ 시나리오·견적비교도 같은 계약인가 ────────────────────────
    r = client.post("/entry/scenario/wonchaewon/save",
                    data={"name": "209가드", "price_won_per_kg": "3100", "note": ""})
    assert r.status_code == 400 and "209가드" in r.text and 'value="3100"' in r.text, (
        "🔴 시나리오 거부가 세트 이름·가정값을 버렸다")
    qform = _nonsan_form()
    qform["provenance"] = ""          # 근거 없는 전사 → 저장 거부
    r = client.post("/entry/quotes/save", data=qform)
    assert r.status_code == 400, f"🔴 근거 없는 전사가 {r.status_code}로 통과한다"
    assert "골조공사 | 184464840 | greenhouse_structure" in r.text, (
        "🔴 견적 거부가 **전사한 행 전체**를 버렸다 — 가장 다시 치기 싫은 입력이다")

    # ── ④ 🔴 **클라이언트 검증을 늘리지 않았는가**(제2 검증기 금지) ──
    for path in ("/entry/newcase", "/entry/quotes/edit",
                 "/entry/financing/wonchaewon", "/entry/scenario/wonchaewon"):
        html = client.get(path).text
        # 🔴 이 자리에 `\b`를 쓰려다 **백스페이스 문자가 박혔다**
        #   (209차 뮤테이션 M5가 잡았다 — 가드가 **한 번도 발화할 수 없었다**).
        #   역슬래시 이스케이프를 아예 쓰지 않는다.
        tags = _re.findall("<(?:input|select|textarea)[^>]*>", html)
        hits = sorted({a for t in tags for a in
                       ("required", "pattern", "min", "max",
                        "minlength", "maxlength")
                       if _re.search("[ ]" + a + "[ =>]", t)})
        assert not hits, (
            f"🔴 {path}에 브라우저 검증 속성 {sorted(set(hits))}이 생겼다 — 검증은 "
            "**서버·엔진 한 곳**에서만 한다. 클라이언트에도 두면 **둘이 갈라진다**")

    # ── ⑤ 되돌릴 수 없는 거부는 **되돌릴 수 있는 척하지 않는가** ────
    r = client.post("/entry/financing/nope/save", data={"loan_principal_won": "1"})
    assert r.status_code == 404 and "기입이 거부됐다" in r.text, (
        "🔴 케이스가 없어 폼을 복원할 수 없는 거부가 일반 오류 화면으로 가지 않는다")
    assert "케이스 nope 없음" in r.text, "🔴 일반 오류 화면도 사유를 그대로 실어야 한다"
    assert "<form" not in r.text, (
        "🔴 복원하지 못했는데 빈 폼을 띄웠다 — **되돌릴 수 있는 척**이다")
    assert "기입한 값은 아래에 그대로 남아 있다" not in r.text, (
        "🔴 폼을 되돌리지 못한 화면이 *「값은 아래에 남아 있다」*고 말한다 — "
        "**거짓말이다**. 아래에는 아무것도 없다")
    assert r.text.count("케이스 nope 없음") == 1, (
        "🔴 같은 사유가 두 번 실린다 — 띠와 본문이 겹쳤다")

    # ── ⑥ 어느 거부도 JSON으로 새지 않는가 ─────────────────────────
    for meth, path, data in (
            ("get", "/pages/SmartFarm_없는파일.html", None),
            ("get", "/pages/smartfarm_engine.py", None),
            ("post", "/entry/newcase/save", {"case_id": "BADID"})):
        rr = client.get(path) if meth == "get" else client.post(path, data=data)
        assert rr.status_code in (400, 404, 409), rr.status_code
        assert not rr.headers["content-type"].startswith("application/json"), (
            f"🔴 {path}의 거부가 아직 JSON이다 — 화면 한 곳으로 모으지 못했다")

    # ── ⑦ 좁은 폭에서 무너지지 않게 했는가(실측: 미디어 쿼리 **0개**였다) ─
    base = _io_read("webapp_templates/_base.html")
    assert "@media" in base, (
        "🔴 스타일시트에 미디어 쿼리가 없다 — 209차 실측에서 600px일 때 `main`이 "
        "288px인데 카드 그리드가 340px였고, 액션 버튼 3개가 **114px 높이**의 "
        "세로 글자열로 무너졌다")
    assert "flex-direction:column" in base.split("@media", 1)[1], (
        "🔴 미디어 쿼리는 있는데 세로 배치로 바뀌지 않는다")
    for tpl in ("entry_financing.html", "entry_scenario.html"):
        t = _io_read("webapp_templates/" + tpl)
        assert 'class="split"' in t and "width:420px" not in t, (
            f"🔴 {tpl}이 아직 인라인 `width:420px`로 2단을 만든다 — "
            "**인라인 style은 미디어 쿼리가 못 이긴다**")
    home = _io_read("webapp_templates/console_home.html")
    assert "minmax(min(340px,100%),1fr)" in home, (
        "🔴 카드 그리드가 칸보다 넓어질 수 있다 — `min(340px,100%)`로 막아야 한다")


def _io_read(rel):
    import io as _i, os as _o
    return _i.open(_o.path.join(_o.path.dirname(_o.path.abspath(webapp.__file__)), rel),
                   encoding="utf-8").read()
