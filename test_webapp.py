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
    # 🔴210차 — 카드는 이제 **케이스 상세**로 간다. 계약(실명을 URL에 싣지 않는다)은
    #    그대로이고 **경로만 옮겼다**: 홈 → `/case/C4` → 부분케이스 산출물.
    assert '"/case/C4"' in r.text, "🔴 홈 카드가 표시 코드로 상세를 열지 않는다"
    assert "SmartFarm_부분케이스_C4.html" in client.get("/case/C4").text
    assert '"/case/C5"' in r.text and '"/case/C2"' in r.text
    assert "SmartFarm_부분케이스_C5.html" in client.get("/case/C5").text
    assert "SmartFarm_통합보고서_C2.html" in client.get("/case/C2").text
    # 🔴 실명은 **홈에도 상세에도** 없어야 한다 — 210차가 라우트를 열면서 하마터면
    #    `/case/wonchaewon`으로 실명을 URL에 실을 뻔했고, 183차 가드가 잡았다.
    for page in [r.text] + [client.get("/case/" + k).text
                            for k in ("C1", "C2", "C3", "C4", "C5")]:
        for old in ("yonggyun", "mulhyangki", "wonchaewon", "chuncheon", "uminjae"):
            assert old not in page, f"🔴 내부 식별자 {old}가 화면에 남았다"


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
    r = client.post("/entry/financing/C2/preview", data=form)
    assert r.status_code == 200
    am = e.loan_amortization(300_000_000, 1.5, 25, 5, "원리금균등")
    assert f"{am['총이자']:,.0f}" in r.text  # 상환표 수치 = 엔진 반환값 그대로
    assert "거치 5년" in r.text


def test_financing_engine_validation_surfaces():
    # 거치 ≥ 전체기간은 엔진 ValueError → 400으로 그대로 노출(제2 검증기 없음)
    form = {"loan_principal_won": "1000000", "annual_rate_pct": "2",
            "term_years": "5", "grace_years": "5", "method": "원리금균등", "note": "x"}
    r = client.post("/entry/financing/C2/preview", data=form)
    assert r.status_code == 400


def test_financing_save_requires_note_and_writes_case(tmp_cases):
    form = {"loan_principal_won": "100000000", "annual_rate_pct": "0",
            "term_years": "5", "grace_years": "", "method": "원리금균등", "note": ""}
    assert client.post("/entry/financing/C2/save", data=form).status_code == 400  # 출처 없음
    form["note"] = "테스트 약정서(합성) — 출처 형식 예시"
    r = client.post("/entry/financing/C2/save", data=form, follow_redirects=False)
    assert r.status_code == 303
    saved = json.loads((tmp_cases / "wonchaewon.json").read_text(encoding="utf-8"))
    assert saved["financing"]["loan_principal_won"] == 100_000_000
    assert saved["financing"]["note"].startswith("테스트 약정서")
    # 저장되면 홈 배너의 대기 ①이 사라진다(데이터 도출 배너의 증거)
    assert "약정서" not in client.get("/").text.split("데이터 대기")[1][:300]


def test_scenario_whitelist_rejected_via_engine():
    form = {"name": "불량", "note": "x", "area_m2": "9999"}  # 물리 입력은 화이트리스트 밖
    r = client.post("/entry/scenario/C2/preview", data=form)
    assert r.status_code == 400 or "허용되지 않는" not in r.text  # 폼에 없는 필드는 무시됨
    # 화이트리스트 필드가 하나도 없으면 저장 거부
    r2 = client.post("/entry/scenario/C2/save", data={"name": "빈세트", "note": "x"})
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
    r = client.post("/entry/scenario/C2/preview", data=form)
    assert r.status_code == 200
    # 미리보기 ROI = 엔진 재계산값
    case = {c["case_id"]: c for c in C.load_cases()}["wonchaewon"]
    import dataclasses
    inp = C.case_to_input(case)
    ec = rr.compute(dataclasses.replace(inp, price_won_per_kg=2936))["economics"]
    assert f"{ec['roi']*100:.1f}%" in r.text
    # 저장 → 세트가 케이스에 추가되고 scenario_rows가 그대로 소비 가능
    rs = client.post("/entry/scenario/C2/save", data=form, follow_redirects=False)
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
    r = client.post("/entry/financing/C2/preview", data={
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
    r = client.post("/entry/scenario/C2/save",
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
                 "/entry/financing/C2", "/entry/scenario/C2"):
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


def test_210cha_every_output_is_reachable_from_the_console():
    """210차 — **산출물이 콘솔에서 닿는가**(하나도 빠짐없이).

    🔴 **실측이 결함을 정했다**: 산출물 **21건 중 9건**이 콘솔 어디에서도 닿지
    않았다 — 케이스당 **4축 리포트 · 컨설팅 패키지 · 판정 부록**(3종 × 4축 3건).
    카드는 **통합보고서 하나만** 가리켰다. *「사이드바 링크가 모자라다」*와
    *「케이스 상세가 없다」*는 **같은 구멍 하나**였다.

    🔴 **왜 그랬나**: 파일명을 짓는 곳이 **둘**이었다 — `build_site.build()`의
    지역 변수와 `webapp.py`의 f-string. 둘이면 갈라지고, 실제로 갈라져 있었다.
    → `build_site.case_output_files()`를 **유일한 출처**로 두고 양쪽이 부른다.

    📌 이 가드는 **수를 고정하지 않는다**(21을 박으면 산출물이 늘 때 거짓 실패한다).
    대신 **사각이 0인가**를 잰다 — 새 산출물이 생기면 자동으로 발화한다.
    """
    import re as _re, os as _o, glob as _g
    import build_site as _bs
    from cases import load_cases as _lc

    repo = _o.path.dirname(_o.path.abspath(webapp.__file__))
    outputs = sorted([_o.path.basename(p)
                      for p in _g.glob(_o.path.join(repo, "SmartFarm_*.html"))]
                     + ["index.html"])
    assert len(outputs) >= 21, (
        f"🔴 산출물이 {len(outputs)}건이다 — 210차 실측은 21건이고 **하한**이다. "
        "줄었다면 build_site가 덜 돈 것이다(게이트 순서: build_site → pytest)")

    cs = _lc()
    pages = ["/", "/entry", "/entry/newcase", "/entry/quotes"]
    import case_display as _cd
    pages += ["/case/" + _cd.code(x) for x in cs]   # URL도 표시 코드다
    seen = set()
    for p in pages:
        r = client.get(p)
        assert r.status_code == 200, f"🔴 {p}가 {r.status_code}다"
        seen |= set(_re.findall(r'href="/pages/([^"]+)"', r.text))

    gap = [n for n in outputs if n not in seen]
    assert not gap, (
        f"🔴 콘솔에서 **닿지 않는 산출물** {len(gap)}건: {gap} — 만들어 놓고 "
        "**보여 주지 않는 산출물**은 없는 것과 같다(210차 전에 9건이 그랬다)")
    broken = sorted(n for n in seen if n not in outputs)
    assert not broken, (
        f"🔴 콘솔이 **없는 파일**을 가리킨다: {broken} — 링크는 있는데 파일이 없다")

    # ── 🔴 이름을 **두 곳에서 짓지 않는가** ────────────────────────
    src = _io_read("webapp.py")
    assert 'f"SmartFarm_' not in src, (
        "🔴 `webapp.py`가 산출물 파일명을 **직접 짓는다** — 이름의 출처는 "
        "`build_site.case_output_files()` 하나여야 한다. 둘이면 갈라지고, "
        "210차 전에 실제로 갈라져 케이스당 3종이 사각이 됐다")
    for case in cs:
        files = _bs.case_output_files(case)
        kinds = [k for k, _w in _bs._MENU_KINDS if k in files]
        assert len(kinds) == len(files), (
            f"🔴 `{case['case_id']}`의 산출물 갈래가 `_MENU_KINDS`에 없다: "
            f"{sorted(set(files) - set(kinds))} — 보는 순서를 잃는다")
        html = client.get("/case/" + _cd.code(case)).text
        for kind, fn in files.items():
            assert fn in html, (
                f"🔴 상세 화면이 `{case['case_id']}`의 「{kind}」({fn})를 내지 않는다")

    # ── ⚠️ 없는 파일을 **있는 척하지 않는가** ──────────────────────
    import smartfarm_engine as _e  # noqa: F401  (경로 확인용 import 아님)
    case0 = [x for x in cs if not x.get("partial")][0]
    fn = _bs.case_output_files(case0)["판정 부록"]
    p = _o.path.join(repo, fn)
    body = _io_read(fn)
    _o.rename(p, p + ".210bak")
    try:
        html = client.get("/case/" + _cd.code(case0)).text
        assert "아직 없다" in html and "엔진 재계산" in html, (
            "🔴 생성되지 않은 산출물을 **링크로 내놨다** — 눌러도 404다. "
            "없는 것은 **없다고** 말해야 한다(209차 계약)")
        assert ('href="/pages/%s"' % fn) not in html, (
            f"🔴 없는 파일 {fn}을 아직 링크한다")
    finally:
        _o.rename(p + ".210bak", p)
    assert _io_read(fn) == body, "🔴 가드가 산출물을 바꿔 놓았다"

    # ── 🔴 실명이 **콘솔 어디에도** 남지 않는가(183·184차 계약을 전 화면으로) ─
    #   210차에 케이스 상세를 열면서 하마터면 `/case/wonchaewon`으로 **URL에 실명을
    #   실을 뻔했다** — 183차 가드가 잡았다. 가드를 기입 화면까지 넓히자 `/entry`
    #   허브·기입 폼이 **33차부터 실명을 URL에 싣고 있었다**는 것이 드러났다
    #   (183차 가드는 **홈만** 훑었다). 그래서 이제 **전 화면**을 훑는다.
    EXC = {"/entry/quotes/edit":
           "전사 편집기는 **전사 대상 자체**를 보여 준다 — 업체명은 편집할 데이터이지 "
           "산출물이 아니다(`test_quotes_edit_prefills_real_data`가 그것을 요구한다)"}
    sweep = ["/", "/entry", "/entry/newcase", "/entry/quotes", "/entry/quotes/edit"]
    sweep += ["/case/" + _cd.code(x) for x in cs]
    sweep += ["/entry/%s/%s" % (k, _cd.code(x))
              for k in ("financing", "scenario")
              for x in cs if not x.get("partial")]
    used_exc = set()
    for p in sweep:
        r = client.get(p)
        assert r.status_code == 200, f"🔴 {p}가 {r.status_code}다"
        left = _cd.audit(r.text)
        if p in EXC:
            used_exc.add(p)
            continue
        assert not left, (
            f"🔴 {p}에 실명·내부 식별자가 남았다: {left} — **URL도 화면도** 사용자가 "
            "보고 복사해 나르는 표면이다(183·184차 계약)")
    assert used_exc == set(EXC), (
        f"🔴 쓰이지 않은 예외가 있다: {sorted(set(EXC) - used_exc)} — 예외는 "
        "**실제로 걸릴 때만** 둔다(192차 교훈: 안 쓰인 예외는 사유가 검사되지 않는다)")

    # ── 판정·추천 어휘가 상세 화면에 들어오지 않았는가 ─────────────
    #   📌 **또 무딘 토큰이었다(아홉 번째)**: `"추천"`만 세니 화면 맨 아래의
    #      선언문 *「판정·추천 없음」* 자체에 걸렸다(182·185·190·192·193·198·
    #      200·207차와 같은 유형). 선언문은 **있어야 하는 것**이므로 지우지 않고,
    #      **그 문장만 들어낸 뒤** 나머지를 잰다.
    html = client.get("/case/" + _cd.code(case0)).text
    DECL = "판정·추천 없음"
    assert DECL in html, (
        f"🔴 케이스 상세에서 「{DECL}」 선언이 사라졌다 — 콘솔이 나열만 한다는 "
        "약속은 **화면에 적혀 있어야** 읽는 사람이 안다")
    body = html.replace(DECL, "")
    for w in ("추천", "권장", "최적", "1순위", "우선순위"):
        assert w not in body, (
            f"🔴 케이스 상세에 판정·추천 어휘 「{w}」가 들어왔다 — 콘솔은 "
            "나열만 한다(1절 불변 원칙)")


def test_211cha_ia_menu_matches_the_code():
    """211차 — **IA·메뉴가 코드와 같은 것을 말하는가**(사용자 지시: 벤치마킹 IA).

    🔴 **실측이 축을 정했다**: 리포는 이미 `PACKAGE_SPEC.stage` **6단계**를 코드에
    쥐고 있는데 벤치마킹 3기능과 **1:1이 아니라 교차**한다 — F2 시방이
    D2(①공종설계)·D19(②품질설계)·D20(⑥사후관리)에 **흩어져 있다**. 그래서 기능은
    `FUNCTION_OF_CODE`가 **D코드마다 직접** 쥔다(단계에서 유도하면 틀린다).

    🔴 **가져오지 않은 것을 잰다**: 밴드(Basic/Standard/Premium)와 요율은
    **판단성·시세성**이라 두고 왔다 — 화면·문서에 스며들면 1절 위반이다.

    ⚠️ **없는 것을 있는 척하지 않는다**: 벤치마킹이 이름을 대지만 리포에 없는 7건은
    「없다」로 낸다(209차 계약).
    """
    import re as _re
    import consulting_package as _cp

    ix = _cp.function_index()

    # ── ① 27건이 **하나도 빠짐없이** 배정됐는가 ─────────────────────
    spec_codes = sorted(x["code"] for x in _cp.PACKAGE_SPEC)
    mapped = sorted(_cp.FUNCTION_OF_CODE)
    assert mapped == spec_codes, (
        f"🔴 배정과 산출물 목록이 다르다 — 빠짐 {sorted(set(spec_codes) - set(mapped))} · "
        f"군더더기 {sorted(set(mapped) - set(spec_codes))}. D코드가 늘면 **배정도 늘려야** "
        "한다(늘지 않으면 새 산출물이 메뉴에서 사라진다)")
    assert ix["total"] == len(spec_codes)
    fns = {f for f, _n, _d in _cp.BENCHMARK_FUNCTIONS}
    for code, (fn, why) in _cp.FUNCTION_OF_CODE.items():
        assert fn in fns, f"🔴 {code}가 없는 기능 {fn!r}에 배정됐다"
        assert why.strip(), (
            f"🔴 {code}에 **왜 이 기능인가**가 비었다 — 분류도 근거를 단다")

    # ── ② 🔴 **판정이 아니라 분류인가**(순위·등급·추천 금지) ─────────
    for r in ix["rows"]:
        assert "rank" not in r and "score" not in r and "grade" not in r, (
            f"🔴 기능 축이 {r['fn']}에 순위·점수를 달았다 — 분류는 **줄 세우지 않는다**")
    html = client.get("/functions").text
    #   📌 **무딘 토큰, 열 번째다.** `"추천"`만 세면 화면의 **선언문 세 줄**에 걸린다
    #      (210차와 같은 유형). 선언문은 **있어야 하는 것**이므로 하나하나 확인한 뒤
    #      **그 줄만 들어내고** 나머지를 잰다 — 하나라도 없으면 실패한다.
    DECLS = ("순위·등급·추천 없음",
             "순위·등급·추천을 만들지 않는다",
             "판정·추천 없음")
    body = html
    for d in DECLS:
        assert d in body, (
            f"🔴 기능 지도에서 선언 「{d}」이 사라졌다 — 이 축이 **분류이지 판정이 "
            "아니라는 것**은 화면에 적혀 있어야 읽는 사람이 안다")
        body = body.replace(d, "")
    for w in ("추천", "권장", "최적", "1순위", "우선순위", "등급이 높"):
        assert w not in body, f"🔴 기능 지도에 판정·추천 어휘 「{w}」가 들어왔다"

    # ── ③ 🔴 **밴드·요율이 스며들지 않았는가**(판단성·시세성) ────────
    #   📌 벤치마킹 문서의 밴드 이름과 요율은 **가져오지 않기로** 한 것이다.
    #      코드·화면·IA 문서 어디에도 값으로 들어오면 안 된다. 다만 *「두고 왔다」*고
    #      적은 문장은 **있어야 하므로** 그 줄만 들어내고 잰다(210차 교훈: 선언문이
    #      제 가드에 걸린다 — 무딘 토큰 아홉 번째였다).
    ia = _io_read("IA_20260924.md")
    KEPT = "| 두고 온 것 |"
    kept_line = [ln for ln in ia.split(chr(10)) if ln.startswith(KEPT)]
    assert len(kept_line) == 1, (
        "🔴 IA 문서에서 **무엇을 두고 왔는지** 적은 줄이 사라졌다")
    scan = {"IA 문서": ia.replace(kept_line[0], ""),
            "기능 지도": body,
            "조립 계층": _io_read("consulting_package.py")}
    src_cp = scan["조립 계층"]
    keep = [ln for ln in src_cp.split(chr(10))
            if "Basic/Standard/Premium" in ln or "1.5~3%" in ln]
    for ln in keep:
        scan["조립 계층"] = scan["조립 계층"].replace(ln, "")
    for where, text in scan.items():
        for token in ("Basic", "Standard·", "Premium", "1.5~3", "3~5%",
                      "$29", "€490", "€1,980"):
            assert token not in text, (
                f"🔴 {where}에 벤치마킹 **밴드·요율** 「{token}」이 들어왔다 — "
                "밴드는 판단성이고 요율은 시세성이다(1절: 조회하지 않는다 · "
                "판정·추천 자동화 금지). 기능 축만 가져오기로 한 것이다")

    # ── ④ ⚠️ **없는 것을 없다고 내는가** ───────────────────────────
    assert ix["gap_count"] == len(_cp.FUNCTION_GAPS) >= 1
    for g in _cp.FUNCTION_GAPS:        # 🔴212차에 dict로 바뀌었다(출처·막는 것이 붙었다)
        fn, name, why = g["fn"], g["name"], g["why"]
        assert fn in fns, f"🔴 미구축 {name!r}이 없는 기능 {fn!r}에 달렸다"
        assert name in html, (
            f"🔴 기능 지도가 미구축 「{name}」을 감췄다 — 벤치마킹이 이름을 대는데 "
            "우리에게 없다는 사실은 **메뉴에 보여야** 한다")
        assert why.strip(), f"🔴 미구축 「{name}」에 사유가 없다"
    assert html.count("— 없다") == len(_cp.FUNCTION_GAPS), (
        f"🔴 「없다」 표시가 {html.count('— 없다')}개다 — {len(_cp.FUNCTION_GAPS)}개여야 한다")

    #   🔴 **가드가 목록을 되읽기만 하면 하나 지워도 통과한다**(211차 뮤테이션 M2가
    #      그랬다 — 자기 점검 3위 「가드의 실측 추종」과 같은 유형). 그래서 기준을
    #      **밖**에 둔다: 아래는 벤치마킹 문서 **정의문에서 그대로 따온** 낱말이고,
    #      각각은 ①엔진이 구현했거나 ②미구축으로 **이름이 걸려 있어야** 한다.
    #      둘 다 아니면 **조용히 사라진 것**이다.
    eng0 = _io_read("smartfarm_engine.py")
    ACCOUNTED = {          # 엔진 원문 낱말 → 미구축 목록에 걸릴 이름
        "KCS": "KCS 형식 시방",
        "수의계약": "수의계약 한도 판정",
        "나라장터": "나라장터 등록 지원",
        "하자이행보증": "하자이행보증 2%·1년",
        "공급사": "적격 공급사 풀",
    }
    gap_names = {g["name"] for g in _cp.FUNCTION_GAPS}
    for token, gap_name in ACCOUNTED.items():
        n = eng0.count(token)
        if n == 0:
            assert gap_name in gap_names, (
                f"🔴 엔진에 「{token}」이 **0회**인데 미구축 목록에서 「{gap_name}」이 "
                "사라졌다 — 벤치마킹이 이름 대는 기능을 **조용히 감춘 것**이다")
            assert gap_name in html, f"🔴 화면이 「{gap_name}」을 내지 않는다"
        else:
            assert gap_name not in gap_names, (
                f"🔴 엔진에 「{token}」이 {n}회 있는데 아직 「{gap_name}」이 "
                "미구축이라고 적혀 있다 — 구현됐으면 목록에서 내려야 한다")

    # ── ⑤ 🔴 **문서가 코드와 같은 것을 말하는가**(썩으면 실패) ───────
    for r in ix["rows"]:
        head = "### %s %s" % (r["fn"], r["name"])
        assert head in ia, f"🔴 IA 문서에 {head!r} 절이 없다 — `python gen_ia.py`로 다시 낼 것"
        for d in r["docs"]:
            row = "| %s | %s |" % (d["code"], d["title"])
            assert row in ia, (
                f"🔴 IA 문서의 {r['fn']} 표에 {d['code']} {d['title']} 행이 없다 — "
                "문서가 **썩었다**. 손으로 고치지 말고 `python gen_ia.py`")
    # 엔진 원문 실측이 문서에 그대로 실렸는가
    eng = _io_read("smartfarm_engine.py")
    for tok in ("수의계약", "나라장터", "내재해"):
        assert ("| `%s` | **%d**회 |" % (tok, eng.count(tok))) in ia, (
            f"🔴 IA 문서의 「{tok}」 실측이 지금 엔진과 다르다 — 다시 낼 것")

    # ── ⑥ 메뉴가 **전 화면**에 서 있는가(네비게이션) ────────────────
    import case_display as _cd2
    from cases import load_cases as _lc2
    for p in (["/", "/functions", "/entry", "/entry/newcase", "/entry/quotes"]
              + ["/case/" + _cd2.code(x) for x in _lc2()]):
        h = client.get(p).text
        assert 'href="/functions"' in h, f"🔴 {p}에 기능 지도 메뉴가 없다"
        for f, name, _d in _cp.BENCHMARK_FUNCTIONS:
            if f == "F0":
                continue
            assert ('href="/functions#%s"' % f) in h, (
                f"🔴 {p}의 사이드바에 기능 {f}({name}) 항목이 없다 — 네비게이션은 "
                "**전 화면 공통**이어야 한다")

def test_212cha_collected_sources_did_not_become_engine_values():
    """212차 — **외부 수집이 값 등재로 새지 않았는가**(사용자 지시: 외부 수집·매핑).

    🔴 **수집은 1절이 지시한 경로다**: 7건 중 **시세성(단가·노임·유가·금리)은
    하나도 없었다** — 전부 **법정·표준·절차** 정보이고, 법정값은 *「원문 확보·대조를
    거쳐서만」* 등재하라고 되어 있다. 그러나 **확보와 등재는 다른 칸**이다.

    🔴 **이 가드가 지키는 선**: 확보한 수치(2% · 1년 · 2억 · 8천만원 …)가
    **엔진·레지스트리·케이스로 새어 들어가지 않았는지**. 새면 ★결정을 건너뛴 것이다.

    ⚠️ 원문 대조에서 **벤치마킹 문서와 어긋나는 세 곳**이 나왔다 — 본문에 섞지 않고
    근거 문서 「이견」 절로 뺐다(1절 사실성 규칙). 그 절이 사라져도 실패한다.
    """
    import re as _re
    import consulting_package as _cp

    DOC = _cp.GAP_EVIDENCE_DOC
    doc = _io_read(DOC)
    ix = _cp.function_index()

    # ── ① 공백마다 **어디를 보면 있나**가 달렸는가 ──────────────────
    for g in _cp.FUNCTION_GAPS:
        for k in ("fn", "name", "why", "found", "where", "blocked"):
            assert g.get(k), f"🔴 미구축 「{g.get('name')}」에 `{k}`가 비었다"
        assert g["found"] in ("1차", "2차", "미확인"), (
            f"🔴 「{g['name']}」의 등급이 {g['found']!r}다 — 1차/2차/미확인만 쓴다")
        assert g["name"] in doc, (
            f"🔴 근거 문서에 「{g['name']}」이 없다 — 수집 결과는 **문서에 남아야** "
            "다음 사람이 대조할 수 있다")
    # ── ② 🔴 **등재된 값에 근거가 붙어 있는가**(213차에 계약이 뒤집혔다) ──
    #   212차의 계약은 *「확보했어도 엔진에 넣지 마라」*였다. 213차에 **★사용자
    #   결정**(「보조사업자 계약 기준으로 확정하고 등재 진행하라」)이 내려져
    #   등재가 열렸다 — 그래서 이 검사는 **「없어야 한다」가 아니라 「근거가 있어야
    #   한다」**로 바뀐다. 지우지 않고 **방향을 바꾼다**: 근거 없이 들어온 값은
    #   여전히 잡힌다.
    COLLECTED = ("계약금액의 2% 이상", "최소 1년 이상", "8천만원을 초과",
                 "1억6천만원", "제57조 제2항", "서로 다른 광역자치단체")
    for tok in COLLECTED:
        assert tok in doc, (
            f"🔴 근거 문서에서 확보한 원문 「{tok}」이 사라졌다 — 등재값의 근거는 "
            "**문서에 남아야** 한다")
    import json as _j
    reg = _j.loads(_io_read("엔진데이터_레지스트리.json"))["constants"]
    import smartfarm_engine as _e2
    REGISTERED = {
        "PROCUREMENT_CONTRACT_BASIS": "결정",
        "SUBSIDY_PROCUREMENT_THRESHOLDS": "법정기준",
        "WARRANTY_BOND_RULE": "법정기준",
        "QUOTE_COUNT_RULE": "법정기준",
    }
    for name, want_status in REGISTERED.items():
        assert name in reg, (
            f"🔴 엔진이 쓰는 `{name}`이 **레지스트리에 없다** — 근거 없는 값이다(1절)")
        assert reg[name]["status"] == want_status, (
            f"🔴 `{name}`의 status가 {reg[name]['status']!r}다 — {want_status!r}여야 한다")
        assert hasattr(_e2, name), f"🔴 레지스트리에만 있고 엔진에 없다: {name}"
        # 🔴**드리프트 가드**: 레지스트리 값과 엔진 값이 갈라지면 잡는다.
        #    (213차에 여기 `or True`를 썼다가 201차 「항상 통과하는 단언」 가드가
        #     잡았다 — 고정 수는 그대로인데 아무것도 재지 않는 문장이었다.)
        live = getattr(_e2, name)
        for _k, _v in reg[name]["value"].items():
            assert _k in live and live[_k] == _v, (
                f"🔴 `{name}`의 `{_k}`가 레지스트리 {_v!r} ↔ 엔진 "
                f"{live.get(_k)!r}로 **갈라졌다** — 값의 출처는 한 곳이어야 한다")
    assert "★사용자 결정 2026-09-24" in reg["PROCUREMENT_CONTRACT_BASIS"]["source"], (
        "🔴 적용 규정의 **★결정 기록**이 레지스트리에서 사라졌다 — 이 값은 실측이 "
        "아니라 **결정**이고, 누가 언제 정했는지가 곧 근거다")
    assert "★" in _io_read("smartfarm_engine.py"), "🔴 엔진에서 ★ 표기가 사라졌다"

    # ── ②-b 🔴 **적용하지 않기로 한 값이 들어오지 않았는가** ────────────
    #   ★결정은 *「보조사업자 계약 기준」*이었다. 지방계약법 시행령의 수의계약
    #   한도(4억/2억/1.6억)는 **적용하지 않기로** 한 것이므로 값으로 들어오면
    #   결정을 어긴 것이다.
    for bad in (400_000_000, 160_000_000):
        assert bad not in set(_e2.SUBSIDY_PROCUREMENT_THRESHOLDS.values()), (
            f"🔴 지방계약법 한도 {bad:,}이 임계값으로 들어왔다 — ★결정은 "
            "**보조사업자 계약 기준**이고 그 한도는 적용하지 않는다")
    assert _e2.PROCUREMENT_CONTRACT_BASIS["basis"] == "보조사업자 계약"
    assert "지방자치단체" in _e2.PROCUREMENT_CONTRACT_BASIS["not_applies"], (
        "🔴 **무엇을 적용하지 않기로 했는지**가 사라졌다 — 그것이 결정의 절반이다")
    cp_src = _io_read("consulting_package.py")
    for tok in ("20_000_000", "200_000_000", "0.02", "min_rate"):
        assert tok not in cp_src, (
            f"🔴 조립 계층이 임계값 「{tok}」을 직접 들고 있다 — 값은 엔진 상수 "
            "한 곳에서만 온다(제2의 계산 출처 금지)")


    # ── ③ 🔴 **막는 것을 적었는가**(원문이 있어도 ★면 막힌 것이다) ───
    #   🔴 **하한으로 재면 또 추종이 된다**(212차 뮤테이션 M3가 그랬다 — 6건에서
    #      하나를 ★에서 빼도 `>= 5`를 통과했다. 211차 M2와 같은 유형). 기준을
    #      **이름으로 못 박는다**: ★ 없이 열려도 되는 것은 **값이 아닌 것** 하나뿐이다.
    UNBLOCKED_OK = {
        "KCS 형식 시방": "코드 **체계**이지 값이 아니다 — 등재할 수가 없으므로 ★도 없다",
    }
    for g in _cp.FUNCTION_GAPS:
        if g["blocked"].startswith("★"):
            assert g["name"] not in UNBLOCKED_OK, (
                f"🔴 「{g['name']}」은 값이 아닌데 ★로 막아 뒀다")
            continue
        assert g["name"] in UNBLOCKED_OK, (
            f"🔴 「{g['name']}」의 **막는 것**에서 ★가 사라졌다 — 이건 **값**이고, "
            "값의 등재는 원문을 확보했더라도 **★사용자 결정**이다(1절: 원문 확보·"
            "대조를 거쳐서만). ★를 지우면 결정을 건너뛴 것이 된다")
    assert len(UNBLOCKED_OK) == 1, (
        "🔴 ★ 없이 열어 두는 예외가 늘었다 — 예외는 **값이 아닌 것**에만 준다")

    # ── ④ ⚠️ **이견을 본문에 섞지 않았는가** ────────────────────────
    assert "## 4. 🔴 이견" in doc, (
        "🔴 근거 문서에서 **「이견」 절**이 사라졌다 — 원문 대조에서 벤치마킹과 "
        "어긋난 세 곳은 본문에 섞지 않고 따로 세워야 한다(1절 사실성 규칙)")
    for frag in ("이견 ①", "이견 ②", "이견 ③"):
        assert frag in doc, f"🔴 근거 문서에서 「{frag}」이 사라졌다"
    assert "고르지 않는다" in doc, (
        "🔴 반대로 읽히는 두 요건 중 **어느 쪽도 고르지 않는다**는 문장이 사라졌다 — "
        "고르면 그것은 판단이다(1절)")

    # ── ⑤ 화면이 **수집 결과와 막는 것**을 내는가 ───────────────────
    html = client.get("/functions").text
    assert DOC in html, "🔴 기능 지도가 근거 문서를 가리키지 않는다"
    for g in _cp.FUNCTION_GAPS:
        assert g["where"][:24] in html, (
            f"🔴 화면이 「{g['name']}」의 **어디를 보면 있나**를 감췄다")
    assert html.count("막는 것:") == len(_cp.FUNCTION_GAPS)

    # ── ⑥ 🔴 **시세성을 끌어오지 않았는가**(1절이 금한 것) ───────────
    #   수집 대상에 단가·노임·유가·금리가 없었다는 것이 이 차수의 전제다.
    assert "시세성 값(단가·노임·유가·금리)은 하나도 없다" in doc, (
        "🔴 **수집 대상에 시세성이 없다**는 전제가 문서에서 사라졌다 — 이 전제가 "
        "무너지면 수집 자체가 1절 위반이 된다")
    #   ⚠️ **또 무딘 토큰이었다(열한 번째)**: `"원/㎡"`·`"천원/kW"`로 재니 엔진에
    #      원래 있던 **정당한 단위 문자열**(준분 111,055원/㎡ 등)에 걸렸다. 막으려던
    #      것은 **벤치마킹 문서에서 끌어온 값**이지 단위가 아니다 → 문서 고유 수치로 조인다.
    for tok in ("요율 1.5", "$29", "€490", "€1,980", "C$6M", "$1,999",
                "공사비 1.5~3", "공사비 3~5"):
        assert tok not in cp_src and tok not in _io_read("smartfarm_engine.py"), (
            f"🔴 벤치마킹 문서의 **요금·요율** 「{tok}」이 코드에 들어왔다 — "
            "시세성이라 1절이 조회를 금한다")


def test_214cha_originals_replaced_the_quoted_copies():
    """214차 — **인용본을 원문으로 바꿨는가**(213차가 남긴 한계).

    🔴 213차의 `status_note`는 *「규정 원문이 아니라 지침서의 인용본에서 전사했다」*
    였다. 214차에 **훈령 제532호 제57조 원문**과 **온실신축 사업시행지침 원문**을
    직접 열어 대조했다 — 인용본의 금액은 **한 자리도 틀리지 않았고**, 발췌본이
    **빠뜨린 단서**가 드러났다(제3항의 전문·전기·정보통신·소방 **3억원**).

    🔴 **부등호가 다르다**: 제2항은 「초과」, 제3항은 **「이상」**이다. 섞으면
    경계값에서 틀린다 — 그래서 경계값을 직접 잰다.

    ⚠️ 이견 ②가 닫혔다(온실신축에서 내재해형은 **요건**), ③은 좁혀졌다(그 지침에
    견적 조항이 **없다**), 그리고 **새 이견 둘**이 나왔다 — 어느 쪽도 고르지 않는다.
    """
    import smartfarm_engine as _e
    import json as _j
    doc = _io_read("근거_외부수집_기능공백_20260924.md")
    reg = _j.loads(_io_read("엔진데이터_레지스트리.json"))["constants"]

    # ── ① 🔴 **제2항은 「초과」 · 제3항은 「이상」** — 경계값으로 잰다 ──
    th = _e.SUBSIDY_PROCUREMENT_THRESHOLDS["건설공사"]
    assert _e.procurement_route("건설공사", th)["required"] is False, (
        "🔴 제2항이 **경계값에서 발화했다** — 원문은 「2억 원을 **초과**하는」이다. "
        "딱 2억이면 해당하지 않는다")
    assert _e.procurement_route("건설공사", th + 1)["required"] is True

    dr = _e.PROCUREMENT_DESIGN_REVIEW_RULE["일반 공사"]
    assert _e.procurement_route("건설공사", dr)["design_review_required"] is True, (
        "🔴 제3항이 **경계값에서 발화하지 않았다** — 원문은 「30억 원 **이상**」이다. "
        "제2항과 부등호가 다르다(섞으면 30억 정각에서 틀린다)")
    assert _e.procurement_route("건설공사", dr - 1)["design_review_required"] is False

    # ── ② 🔴 발췌본이 빠뜨린 **3억원 단서**가 들어왔는가 ────────────
    for kind in ("전문공사", "전기공사", "정보통신공사", "소방공사"):
        assert _e.PROCUREMENT_DESIGN_REVIEW_RULE[kind] == 300_000_000, (
            f"🔴 `{kind}`의 설계검토 문턱이 3억원이 아니다 — 212차 발췌본은 "
            "「총사업비 30억원 이상」이라고만 적어 **이 단서를 빠뜨렸다**. "
            "원문을 봐야 했던 이유다")
    assert _e.PROCUREMENT_DESIGN_REVIEW_RULE["일반 공사"] == 3_000_000_000
    assert _e.procurement_route("전문공사", 350_000_000)["design_review_required"] is True

    #   🔴 **무엇을 요청해야 하는지까지 내야 한다** — 「해야 한다」만 말하고 항목을
    #      감추면 읽는 사람이 다음 걸음을 뗄 수 없다(214차 뮤테이션 M10이 잡았다).
    hit = _e.procurement_route("전문공사", 350_000_000)
    assert len(hit["design_review_items"]) == 3, (
        f"🔴 설계검토 요청 항목이 {len(hit['design_review_items'])}개다 — 제3항 각 호는 "
        "**3개**다(설계적정성 검토 · 공사계약 체결 · 10% 이상 증가 설계변경 타당성 검토)")
    joined = " ".join(hit["design_review_items"])
    for frag in ("실시설계", "공사계약 체결", "10% 이상"):
        assert frag in joined, f"🔴 제3항 각 호에서 「{frag}」가 사라졌다"
    assert "민간보조사업자가 추진하는 계약에 한한다" in joined, (
        "🔴 제3항 제2호의 **단서**가 사라졌다 — 공사계약 체결은 민간보조사업자 "
        "계약에만 적용된다")
    assert _e.procurement_route("전문공사", 250_000_000)["design_review_items"] == [], (
        "🔴 문턱 미만인데 요청 항목을 냈다")

    # ── ③ 등재가 **원문 근거**로 올라섰는가 ────────────────────────
    for name in ("SUBSIDY_PROCUREMENT_THRESHOLDS", "PROCUREMENT_DESIGN_REVIEW_RULE"):
        src = reg[name]["source"]
        assert "농림축산식품부훈령 제532호" in src and "2025. 2. 21." in src, (
            f"🔴 `{name}`의 근거에서 **훈령 번호·시행일**이 사라졌다 — 원문 확보의 "
            "증거는 그 표기다")
    note = reg["SUBSIDY_PROCUREMENT_THRESHOLDS"]["status_note"]
    assert "훈령 원문으로 대조 완료" in note, (
        "🔴 213차의 「인용본만」 한계가 **해소됐다는 기록**이 사라졌다")
    assert "인용본" not in reg["PROCUREMENT_DESIGN_REVIEW_RULE"]["status_note"]

    # ── ④ ⚠️ 이견 ②가 **닫힌 대로** 적혀 있는가 ────────────────────
    assert "## 5-b. 🔴 214차 — 원문을 둘 다 확보했다" in doc
    assert "내재해형 시설규격 설계도를 적용" in doc, (
        "🔴 온실신축 지침의 **원문 문장**이 사라졌다 — 이견 ②는 이 문장으로 닫혔다")
    assert "「가점」은 0회" in doc, (
        "🔴 *「이 지침에 가점은 0회」*가 사라졌다 — 212차의 「가점」이 **다른 사업**의 "
        "것이었다는 근거다")
    assert "온실신축에서는 요건" in doc

    # ── ⑤ ⚠️ **새 이견 둘**이 본문에 섞이지 않고 서 있는가 ──────────
    for frag in ("### ④ 🔴 새 이견", "### ⑤ 🔴 새 이견",
                 "설계는 자부담으로 직접", "고시 제2022-104호"):
        assert frag in doc, f"🔴 근거 문서에서 「{frag}」가 사라졌다"
    assert "단정하지 않는다" in doc, (
        "🔴 새 이견에서 **단정하지 않는다**는 문장이 사라졌다 — 다른 사업·연도는 "
        "확인하지 않았다(1절 사실성)")
    assert "고르지 않는다" in doc

    # ── ⑥ 🔴 등재하지 **않기로** 한 것이 들어오지 않았는가 ───────────
    eng = _io_read("smartfarm_engine.py")
    for tok in ("15일 이내", "2년간", "제4항의 예외"):
        assert tok not in eng or "등재하지 않" in eng, (
            f"🔴 「{tok}」이 엔진에 값으로 들어왔다 — 절차 의무·판단 예외는 "
            "**임계값이 아니다**")
    assert "예외" not in str(_e.PROCUREMENT_DESIGN_REVIEW_RULE)

def _io_read(rel):
    import io as _i, os as _o
    return _i.open(_o.path.join(_o.path.dirname(_o.path.abspath(webapp.__file__)), rel),
                   encoding="utf-8").read()
