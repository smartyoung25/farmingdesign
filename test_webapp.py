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
              for k in ("financing", "scenario", "docs", "issue", "site")   # 226차 양식 2종 · 242차 입지 조건
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

def test_215cha_notice_edition_is_named_not_assumed():
    """215차 — **이견 ⑤가 닫혔는가**(사용자 지시: 고시 제2025-108호 확인).

    🔴 답은 **부칙 목록**에 있었다. 같은 규정이 네 번 개정됐고
    (2016-180 · 2019-44 · **2022-104** · **2025-108**), `2025년 온실신축 지침`이
    2022-104호를 참조한 것은 **그 시점의 최신 판**이었기 때문이다 —
    **모순이 아니라 시점 차이**다. 벤치마킹 문서도 지침도 틀리지 않았다.

    🔴 **대신 리포가 한 판을 몰랐다**: 엔진 주석은 `2014-78 → 2019-44 → 2025-108`로
    적어 2019-44를 *「한 세대 전」*이라 했는데 그 사이에 2022-104호가 있었다.

    ⚠️ **준거가 갈릴 수 있다**: 엔진은 2025-108호, 지침은 2022-104호다. 어느 판을
    쓸지는 **★사용자 결정**(대장 D-16)이고 엔진은 **고르지 않는다** — 드러낼 뿐이다.
    """
    import smartfarm_engine as _e
    doc = _io_read("근거_외부수집_기능공백_20260924.md")
    ledger = _io_read("근거_결정대기대장_20260915.md")

    # ── ① 🔴 네 판이 **부칙 그대로** 적혀 있는가 ───────────────────
    ed = _e.REGION_DESIGN_LOAD_EDITION
    assert len(ed["history"]) == 4, (
        f"🔴 판본 계보가 {len(ed['history'])}판이다 — 고시 원문 부칙은 **4판**이다"
        "(2016-180 · 2019-44 · 2022-104 · 2025-108)")
    for frag in ("제2016-180호", "제2019-44호", "제2022-104호", "제2025-108호"):
        assert any(frag in h for h in ed["history"]), (
            f"🔴 계보에서 「{frag}」가 사라졌다 — 이 판이 빠져 있어서 215차 전까지 "
            "2019-44를 *「한 세대 전」*이라 잘못 적고 있었다")
    assert "제2025-108호" in ed["current"], "🔴 현행 판 표기가 최신이 아니다"

    # ── ② 🔴 **값은 바뀌지 않았는가**(계보만 고쳤다) ────────────────
    assert len(_e.REGION_DESIGN_LOAD) == 172, (
        f"🔴 설계하중이 {len(_e.REGION_DESIGN_LOAD)}지역이다 — 215차는 **계보 기록만** "
        "고쳤고 값은 172지역 그대로다(2025-108호 전면 교체본)")

    # ── ③ ⚠️ **준거가 갈릴 수 있다는 사실**이 드러나 있는가 ──────────
    assert "제2022-104호" in ed["note"] and "★사용자 결정" in ed["note"], (
        "🔴 *「지침은 2022-104호, 엔진은 2025-108호」*라는 사실이 상수에서 사라졌다 — "
        "드러내지 않으면 **모르고 쓰게 된다**")
    assert "**D-16**" in ledger, (
        "🔴 새 ★가 **대기**인데 결정대기대장에 없다 — 146차 가드가 요구하는 절차다")
    assert "REGION_DESIGN_LOAD_EDITION" in ledger, (
        "🔴 대장이 **어디를 보면 되는지**를 적지 않는다")

    # ── ④ 🔴 **고르지 않았는가** ────────────────────────────────
    #   📌 **또 무딘 토큰이었다(열두 번째)**: `"고르지 않는다"`만 세니 문서의 **다른
    #      절**(이견 ③ 등)에도 있어서 ⑤-b의 문장을 지워도 통과했다(215차 뮤테이션 M8).
    #      → **그 절의 문장 전체**로 조인다.
    SENT = ("🔴 **엔진은 고르지 않는다** — 어느 판을 쓸지는 사업·연도와 심사 주체가 "
            "정한다.")
    assert SENT in doc, (
        "🔴 ⑤-b에서 *「엔진은 고르지 않는다 — 어느 판을 쓸지는 사업·연도와 심사 "
        "주체가 정한다」*가 사라졌다. 판을 고르는 순간 그것은 **판정**이다(1절)")
    assert "★결정이다" in doc
    for bad in ("권장", "추천", "이 판을 쓰라", "더 낫다"):
        assert bad not in str(ed), f"🔴 판본 상수가 「{bad}」로 **고르고 있다**"

    # ── ⑤ ⚠️ **하지 않은 것**이 적혀 있는가 ────────────────────────
    #   🔴216차에 **대조를 실제로 했다** — 215차가 *「안 한 일」*로 적었던 것이
    #      이제 **한 일**이다. 지우지 않고 **무엇이 남았는지**로 바꾼다.
    assert "216차에 전수 대조했다" in doc, (
        "🔴 *「216차에 전수 대조했다」*가 사라졌다 — 한 일을 안 한 것처럼 적으면 "
        "다음 사람이 같은 일을 또 한다")
    #   🔴217차에 그 2건도 닫혔다 — 이제 남은 한계는 **사이 판을 열지 않은 것**이다.
    assert "217차에 2건도 닫았다" in doc, (
        "🔴 *「217차에 2건도 닫았다」*가 사라졌다")
    #   🔴218차에 2019-44호도 열었다 — 남은 구멍은 **2016-180호 및 그 이전**이다.
    assert "제2016-180호 및 그 이전 6판은" in doc, (
        "🔴 *「219차에 10판을 전부 열었다」*가 사라졌다 — 218차가 남긴 구멍이 "
        "닫혔다는 기록이다")
    assert "시점 차이" in doc and "모순이 아니라" in doc, (
        "🔴 이견 ⑤의 **답**(모순이 아니라 시점 차이)이 사라졌다")

def test_216cha_edition_diff_is_recounted_not_asserted():
    """216차 — **두 판 차이를 기계가 다시 세는가**(사용자 지시: 별표 확보·대조).

    🔴 **내가 적은 수를 믿지 않는다.** 근거 문서·엔진 주석의 「22지역」은 내가 손으로
    옮긴 수다 — 이 가드는 **엔진 표에서 다시 세어** 대조한다. 차이 목록을 코드에
    박아 두고 세므로, 설계하중 표가 움직이면 **여기서 먼저 터진다**.

    🔴 **「N 이상」을 확정값으로 읽지 않았다는 것**이 이 대조의 핵심이다. 2022판
    최상단 행은 「40 이상」이라 **하한만** 말한다 — 확정값으로 읽으면 차이가 50건으로
    부풀고 그중 36건은 **내가 만든 수**가 된다(159차 교훈).

    ⚠️ 이름이 쪼개진 `고성`·`광주` 2건은 **대조하지 못했다** — 전수라 적고 구멍을
    감추지 않는다.
    """
    import smartfarm_engine as _e
    doc = _io_read("근거_외부수집_기능공백_20260924.md")
    ledger = _io_read("근거_결정대기대장_20260915.md")

    # 제2022-104호 [별표]에서 읽은 값 — 원문 전사(「N 이상」 행은 제외했다)
    SNOW_2022 = {"과천": 24, "광명": 24, "군포": 24, "성남": 24, "수원": 24,
                 "시흥": 24, "안산": 24, "안양": 24, "오산": 24, "용인": 24,
                 "의왕": 24, "화성": 24, "성산": 22, "진도": 22}
    WIND_2022 = {"구례": 26, "김제": 30, "봉화": 24, "부안": 28, "산청": 28,
                 "순천": 24, "연천": 28, "창원": 34}

    cur = _e.REGION_DESIGN_LOAD
    moved_s = [(n, v, cur[n]["snow_cm"]) for n, v in SNOW_2022.items()
               if cur[n]["snow_cm"] != v]
    moved_w = [(n, v, cur[n]["wind_ms"]) for n, v in WIND_2022.items()
               if cur[n]["wind_ms"] != v]
    #   🔴221차 — ★2022-104호 준거 확정(D-16 닫힘)으로 **22건을 되돌렸다**.
    #      216~220차는 *「차이가 22건이다」*를 지켰고, 221차부터는
    #      *「확정값은 2022판과 같아야 한다」*를 지킨다 — 다시 갈라지면 실패한다.
    assert len(moved_s) == 0 and len(moved_w) == 0, (
        f"🔴 엔진이 2022판 확정값과 다시 갈라졌다: 적설 {moved_s} · 풍속 {moved_w}. "
        "★사용자 결정 2026-09-24는 **준거를 제2022-104호로 확정**했다 — 확정값 칸은 "
        "2022판과 같아야 한다(「40 이상」 칸만 2025 실측을 쓴다)")

    # 🔴 되돌린 뒤에도 **2022판보다 작아진 칸은 없어야** 한다
    for n, old, new in moved_s + moved_w:
        assert new > old, (
            f"🔴 `{n}`이 2022 {old} → 2025 {new}로 **작아졌다**. 216차 실측은 "
            "**22건 전부 2025판이 더 크다**였다 — 방향이 뒤집히면 「더 보수적」이라는 "
            "서술이 거짓이 된다")

    # ── ⚠️ 「N 이상」을 확정값으로 읽지 않았는가 ────────────────────
    #   40 이상 행의 대표 지역들은 2025판에서 40을 크게 넘는다 — 그것은 **어긋남이
    #   아니다**. 이 사실이 문서에서 사라지면 다음 사람이 50건으로 잘못 센다.
    for n, lo in (("강릉", 40), ("대관령", 40), ("울릉", 40)):
        assert cur[n]["snow_cm"] >= lo
    import smartfarm_engine as _e2
    _b = _e2.REGION_DESIGN_LOAD_BASIS
    assert "제2022-104호" in _b["basis"] and _b["reverted"]["count"] == 22, (
        "🔴 ★2022-104호 준거 확정 기록이 사라졌다")
    assert _b["open_upper_bound"]["count"] == 36 and cur["강릉"]["snow_cm"] == 93, (
        "🔴 「40 이상」 36건이 2025 실측을 잃었다 — 2022판은 그 칸에 **수치를 주지 "
        "않는다**. 40으로 낮추면 강릉 93→40(2.3배)·대관령 167→40(4.2배)이 된다")
    assert "「N 이상」을 확정값으로 읽지 않았다" in doc, (
        "🔴 *「N 이상은 하한이다」*가 사라졌다 — 확정값으로 읽으면 차이가 **50건으로 "
        "부풀고** 36건은 **자가 만든 수**가 된다(159차 교훈)")

    # ── ⚠️ 대조 못 한 것을 적었는가 ────────────────────────────────
    #   🔴221차 — **두 수가 갈라졌다.** `diff_2022_vs_2025`는 **두 판 사이의
    #      차이**(14·8 — 이 사실은 그대로다)이고, `moved_s/w`는 **엔진 ↔ 2022판**
    #      차이(★결정으로 0이 됐다)다. 엔진이 2025판일 때는 우연히 같았다.
    #      같은 것으로 재면 ★결정이 주석을 썩힌 것처럼 보인다 — 나눠서 잰다.
    d = _e.REGION_DESIGN_LOAD_EDITION["diff_2022_vs_2025"]
    assert (d["snow_regions"], d["wind_regions"]) == (14, 8), (
        f"🔴 **두 판 사이의 차이**가 {d['snow_regions']}·{d['wind_regions']}로 바뀌었다 — "
        "216~220차 실측은 **14·8**이고 이것은 ★결정과 무관한 **사실**이다")
    assert (len(moved_s), len(moved_w)) == (0, 0), (
        "🔴 **엔진 ↔ 2022판** 차이가 0이 아니다 — ★결정은 2022 준거다")
    #   🔴217차 — 사각이 **0**이 됐다. 216차는 *「2건 남았다」*를 지켰고,
    #      217차부터는 *「0이어야 한다」*를 지킨다. 다시 늘면 실패한다.
    assert d["uncompared"] == (), (
        f"🔴 대조 사각이 {d['uncompared']}로 **다시 생겼다** — 217차에 0이 됐다")
    assert d["compared_regions"] == 170, (
        f"🔴 대조한 지역이 {d.get('compared_regions')}다 — 217차 실측은 170이다")
    for nm in ("고성(강원)", "고성(경남)", "광주(경기)", "광주광역시"):
        assert nm in cur, (
            f"🔴 2025판이 쪼갠 이름 `{nm}`이 표에 없다 — 2022판의 `고성`·`광주`가 "
            "어느 쪽인지 갈리지 않아 대조하지 못한 이유다")

    # ── ⚠️ 현재 케이스가 영향권 밖이라는 사실이 서 있는가 ────────────
    from cases import load_cases as _lc
    names = {n for n, _o, _x in moved_s + moved_w}
    for c in _lc():
        rg = str((c.get("input") or {}).get("region") or "")
        assert not [n for n in names if n in rg], (
            f"🔴 케이스 `{c['case_id']}`(지역 {rg!r})가 **두 판이 갈리는 지역**에 "
            "들어왔다 — 이제 어느 판을 쓰느냐가 **산출물 수치를 바꾼다**. "
            "D-16가 실제 영향을 갖게 됐으니 ★결정을 먼저 받아야 한다")

    # ── ⚠️ D-16가 **닫힌 척하지 않는가** ───────────────────────────
    #   🔴221차 — ★사용자 결정으로 **D-16이 닫혔다**. 216~220차는 *「닫히지 않고
    #      좁혀졌다」*를 지켰고, 221차부터는 **닫힌 기록과 그 근거**를 지킨다.
    assert "~~**D-16**~~ ✅**닫힘**" in ledger, (
        "🔴 D-16 닫힘 표기가 사라졌다 — ★사용자 결정 2026-09-24로 닫혔다")
    assert "★사용자 결정 2026-09-24: 준거는 제2022-104호" in ledger, (
        "🔴 **무엇으로 닫혔는지**가 사라졌다 — 닫혔다는 표시만 남으면 근거가 없다")
    assert "216차에 전수 대조했다" in ledger
    #   ⚠️ 215차에 이 항목을 **D-15로 넣어 기존 D-15와 번호가 겹쳤다**. 221차에
    #      D-16으로 양보했고, 그 사실을 남긴다 — 겹침을 조용히 지우지 않는다.
    assert "번호가 겹쳤다" in ledger and "D-16으로 양보" in ledger, (
        "🔴 **215차의 번호 겹침**과 그 정정 기록이 사라졌다")
    import re as _re2
    nums = _re2.findall(r"\|\s*~?~?\*\*(D-\d+)\*\*", ledger)
    dup = sorted({x for x in nums if nums.count(x) > 1})
    assert dup == ["D-3", "D-7"], (
        f"🔴 대장의 D 번호가 겹친다: {dup} — D-3·D-7은 §3 표의 **재언급**이라 "
        "정상이고, 그 밖의 겹침은 215차와 같은 사고다")

def test_217cha_split_names_are_resolved_by_neighbours():
    """217차 — **대조 사각 2건이 닫혔는가**(사용자 지시: 고성·광주 원문 확인).

    🔴 **그것은 대조 사각이 아니라 파서가 만든 사각이었다.** 2022판 표는 **열이
    도(道)를 말하는데** 216차 파서가 열을 뭉개고 `setdefault`로 모아 같은 이름의
    **두 번째 출현을 버렸다**. `고성`·`광주`는 실제로 **각각 두 번** 나온다.

    ⚠️ **열 인덱스도 믿지 않았다** — 빈 칸과 줄바꿈 때문에 **셀이 6개가 아닌 행이
    4개** 나왔다(엔진 주석이 이미 「컬럼 밀림 오독」을 경고하고 있었다).
    → **같은 셀의 이웃 지역**으로 갈랐다.

    ⚠️ 한 건(`고성` 풍속 38)만 **단독 셀**이라 이웃이 없어 **소거법**으로 보았고,
    2025판 값이 그 추론과 **독립적으로 일치**했다. 소거법은 소거법이라고 적는다.
    """
    import smartfarm_engine as _e
    doc = _io_read("근거_외부수집_기능공백_20260924.md")
    R = _e.REGION_DESIGN_LOAD

    # 2022판 [별표]에서 **같은 셀의 이웃으로 갈라** 읽은 값
    #   (값, 「N 이상」인가, 어떻게 갈랐는가)
    RESOLVED = {
        ("고성(경남)", "snow_cm"): (20, False, "거제·김해·남해·진주·통영 셀"),
        ("고성(강원)", "snow_cm"): (40, True, "속초·대관령·강릉·정선·양양 셀"),
        ("광주(경기)", "snow_cm"): (24, False, "가평·고양·구리·군포·남양주 셀"),
        ("광주광역시", "snow_cm"): (38, False, "순창·장수 셀"),
        ("광주(경기)", "wind_ms"): (26, False, "안성·용인 셀"),
        ("광주광역시", "wind_ms"): (32, False, "영암·장성·화순·장흥 셀"),
        ("고성(강원)", "wind_ms"): (40, True, "양양·대관령·속초·강릉 셀"),
        ("고성(경남)", "wind_ms"): (38, False, "단독 셀 — 소거법"),
    }
    assert len(RESOLVED) == 8, "🔴 갈라낸 항목이 8건이 아니다"

    # ── ① 🔴 8건 전부 어긋나지 않는가 ──────────────────────────────
    bad = []
    for (key, field), (v, atleast, why) in RESOLVED.items():
        assert key in R, f"🔴 2025판에 `{key}`가 없다 — 쪼갠 이름이 사라졌다"
        cur = R[key][field]
        if atleast:
            if cur < v:
                bad.append((key, field, v, cur, "하한 미달"))
        elif cur != v:
            bad.append((key, field, v, cur, "확정값이 다르다"))
    assert not bad, (
        f"🔴 갈라낸 2건에서 **새 차이가 나왔다**: {bad} — 216차가 「대조 못 함」으로 "
        "남긴 것이 실제 차이였다는 뜻이고, 그러면 차이는 22지역이 아니다")

    # ── ② 🔴 같은 이름이 **두 번** 나온다는 사실이 남아 있는가 ───────
    assert "각각 두 번" in doc, (
        "🔴 *「`고성`·`광주`는 각각 두 번 나온다」*가 사라졌다 — 216차 파서가 두 번째를 "
        "버렸다는 것이 이 사각의 **원인**이다")
    assert "파서가\n만든 사각" in doc or "파서가 만든 사각" in doc, (
        "🔴 *「대조 사각이 아니라 파서가 만든 사각」*이 사라졌다 — 원인을 원인으로 "
        "적지 않으면 다음에 또 같은 파서를 쓴다")

    # ── ③ ⚠️ **열 인덱스를 믿지 않았다**는 것이 적혀 있는가 ──────────
    assert "셀이 6개가 아닌 행이 4개" in doc, (
        "🔴 *「셀이 6개가 아닌 행이 4개」*가 사라졌다 — 열 번호로 판정했으면 "
        "**밀린 채로 답을 냈을 것**이다")
    assert "같은 셀의 이웃" in doc

    # ── ④ ⚠️ **소거법을 소거법이라고** 적었는가 ─────────────────────
    assert "소거법" in doc and "독립적으로 들어맞았다" in doc, (
        "🔴 단독 셀 한 건을 **소거법으로 보았다**는 것과 그 추론이 2025판 값과 "
        "**독립적으로 들어맞았다**는 것이 사라졌다 — 추론을 관측처럼 적으면 안 된다")

    # ── ⑤ 🔴 사각이 **0**이고 차이는 그대로인가 ────────────────────
    d = _e.REGION_DESIGN_LOAD_EDITION["diff_2022_vs_2025"]
    assert d["uncompared"] == () and d["compared_regions"] == 170
    assert d["snow_regions"] == 14 and d["wind_regions"] == 8, (
        "🔴 2건을 닫았는데 차이 수가 움직였다 — 217차 실측은 **새 차이 없음**이다")
    assert "새로 드러난 차이는 없다" in doc

def test_218cha_middle_edition_is_opened_too():
    """218차 — **사이 판(2019-44호)까지 열었는가**(사용자 지시).

    🔴 **다른 길로 같은 수가 나왔다**: 216·217차는 평면 파서 + 손보정, 218차는
    열·이웃 기반 파서인데 **2022↔2025 차이가 22건으로 같다**. 독립 재현이다.

    🔴 **함평 서사가 정확해졌다**: 36(2014) → **36(2019)** → **40 이상(2022)** →
    40(2025). 2025년 구조계산서의 40은 **2022판을 따른 것**이고, 2026-07 발견 시점에
    우리 출처는 **한 세대가 아니라 두 세대** 뒤처져 있었다.

    ⚠️ 제2016-180호 및 그 이전 6판은 **여전히 열지 않았다** — 전수라 적고 구멍을
    감추지 않는다.
    """
    import smartfarm_engine as _e
    doc = _io_read("근거_외부수집_기능공백_20260924.md")
    R = _e.REGION_DESIGN_LOAD

    # 2019-44호 [별표 1]에서 읽은 값(엔진과 **다른** 것만 · 이웃으로 갈랐다)
    SNOW_2019_DIFF = {
        "강진": 22, "강화": 22, "과천": 24, "광명": 24, "광주광역시": 36,
        "군포": 24, "나주": 34, "대전": 30, "목포": 32, "문경": 34, "보은": 32,
        "상주": 30, "성남": 24, "성산": 22, "수원": 24, "순창": 36, "시흥": 24,
        "안산": 24, "안양": 24, "영덕": 34, "영암": 28, "영양": 24, "영월": 30,
        "예천": 26, "오산": 24, "옥천": 30, "용인": 24, "울진": 38, "의왕": 24,
        "인제": 30, "진도": 22, "함평": 36, "홍천": 30, "화성": 24,
    }
    assert len(SNOW_2019_DIFF) == 34, "🔴 2019판 적설 차이가 34건이 아니다"
    for nm, v in SNOW_2019_DIFF.items():
        assert nm in R, f"🔴 `{nm}`이 설계하중 표에 없다"
        assert R[nm]["snow_cm"] >= v, (
            f"🔴 `{nm}` 적설이 2019 {v} → 엔진 {R[nm]['snow_cm']}로 **작아졌다**. "
            "🔴221차에 ★2022 준거로 되돌려 일부가 2019판과 **같아졌지만**, "
            "2019판보다 작아지면 어느 판 기준으로도 설명되지 않는다")

    # ── 🔴 함평 — 두 세대 뒤처져 있었다는 사실 ─────────────────────
    assert SNOW_2019_DIFF["함평"] == 36 and R["함평"]["snow_cm"] == 40, (
        "🔴 함평 36→40이 깨졌다 — 이 한 지역이 2026-07 「출처가 낡았다」 발견의 "
        "계기였고, 218차에 **2022판에서 이미 올랐다**는 것이 드러났다")
    eng = _io_read("smartfarm_engine.py")
    assert "「한 세대」가 아니라 「두 세대」였다" in eng, (
        "🔴 엔진 주석의 **218차 정정**이 사라졌다 — 2019판도 36이었고 2022판에서 "
        "40이 됐다는 것이 함평 서사의 빠진 칸이다")
    for frag in ("제2019-44호 36", "제2022-104호 「40 이상」"):
        assert frag in eng, f"🔴 엔진 주석에서 「{frag}」가 사라졌다"

    # ── 🔴 22건이 **독립 재현**됐다는 것이 적혀 있는가 ───────────────
    d = _e.REGION_DESIGN_LOAD_EDITION["diff_2022_vs_2025"]
    assert d["snow_regions"] == 14 and d["wind_regions"] == 8
    assert "독립 재현" in doc and "다른 길로 같은 수가 나왔다" in doc, (
        "🔴 *「다른 파서로 같은 수가 나왔다」*가 사라졌다 — 216·217차 수를 "
        "**믿을 수 있는 이유**가 그것이다")
    #   📌 **또 무딘 토큰이었다(열세 번째)**: `"72"`·`"50"`만 세니 문서 다른 곳의
    #      숫자에 걸려 **표를 통째로 바꿔도 통과**했다(218차 뮤테이션 M8).
    #      → **표 행 전체**로 조인다.
    for row in ("| **2019-44 ↔ 2025-108(엔진)** | 343 | **72** (적설 34 · 풍속 38) | 32 | 239 |",
                "| **2022-104 ↔ 2025-108(엔진)** | 343 | **22** (적설 14 · 풍속 8) | 38 | 283 |",
                "| **2019-44 ↔ 2022-104** | 343 | **50** | — | 293 |"):
        assert row in doc, (
            f"🔴 3판 대조 표에서 행이 사라지거나 바뀌었다: {row}")

    # ── ⚠️ 아직 열지 않은 판을 적었는가 ────────────────────────────
    #   🔴219차에 10판을 전부 열었다 — 남은 한계는 *「열지 않았다」*가 아니라
    #      *「2007판은 구조가 달라 대조가 불가능하다」*로 **성격이 바뀌었다**.
    assert "219차에 10판을 전부 열었다" in doc, (
        "🔴 **아직 열지 않은 판**이 사라졌다 — 「전수」는 2019·2022·2025 세 판 "
        "사이에서만 참이다")
    assert "단독 셀" in doc and "소거법으로 경남" in doc, (
        "🔴 못 가른 1건(`고성` 풍속 38 단독 셀)을 **소거법으로 보았다**는 표기가 "
        "사라졌다 — 추론을 관측처럼 적지 않는다")

def test_219cha_all_ten_editions_were_opened():
    """219차 — **10판을 전부 열었는가**(사용자 지시: 2016-180호 이전도 전부).

    🔴 **2016-180호와 2019-44호의 별표가 완전히 같다**(343항목 차이 0). 즉
    2019-44호 개정은 **지역별 설계기준을 건드리지 않았다** — 값이 실제로 움직인
    지점은 **2022·2025 둘뿐**이다.

    ⚠️ **2007판 2건은 원단위 대조가 불가능하다**: 값이 **구간**(「20～25미만」)이고
    이름 체계가 다르다(154~159개 중 **그대로 일치 4개**). 접미사를 떼고 구간
    중앙값을 잡으면 대조되는 것처럼 보이지만 **그 수는 원문에 없는 수**다
    (159차 교훈) → **대조 불가로 남겼다**.

    ⚠️ 나머지 4판(2014-78 · 2013-146 · 2010-128 · 2008-76)은 법령정보센터에
    **별표가 없다**. 2014-78호는 표를 고쳤다고 **스스로 적는데** 그 표가 없다.
    """
    import smartfarm_engine as _e
    doc = _io_read("근거_외부수집_기능공백_20260924.md")
    eng = _io_read("smartfarm_engine.py")

    # ── ① 🔴 2016-180 = 2019-44 라는 사실이 서 있는가 ────────────────
    #   🔴220차에 진술이 **더 강해졌다**: 2016=2019 → **2014=2016=2019**.
    #      약한 진술을 지우지 않고 **강한 진술로 옮긴다**(약해지면 실패한다).
    assert "제2014-78호 = 제2016-180호 = 제2019-44호" in eng, (
        "🔴 엔진 주석에서 *「2014 = 2016 = 2019」*가 사라졌다 — 이것이 "
        "**값이 움직인 지점은 2022·2025 둘뿐**이라는 결론의 근거다")
    assert "343항목 차이 0" in eng
    assert "2016-180 = 2019-44" in doc and "2022-104" in doc

    # ── ② 🔴 2016-180 ↔ 엔진 차이가 2019-44와 **같은가** ─────────────
    #   두 판이 같으므로 엔진 대비 차이도 같아야 한다. 218차가 박아 둔 2019판
    #   적설 34건을 그대로 쓰되, **2016판에도 그대로 성립**하는지로 잰다.
    SNOW_2016_2019 = {
        "강진": 22, "강화": 22, "과천": 24, "광명": 24, "광주광역시": 36,
        "군포": 24, "나주": 34, "대전": 30, "목포": 32, "문경": 34, "보은": 32,
        "상주": 30, "성남": 24, "성산": 22, "수원": 24, "순창": 36, "시흥": 24,
        "안산": 24, "안양": 24, "영덕": 34, "영암": 28, "영양": 24, "영월": 30,
        "예천": 26, "오산": 24, "옥천": 30, "용인": 24, "울진": 38, "의왕": 24,
        "인제": 30, "진도": 22, "함평": 36, "홍천": 30, "화성": 24,
    }
    R = _e.REGION_DESIGN_LOAD
    assert len(SNOW_2016_2019) == 34
    for nm, v in SNOW_2016_2019.items():
        assert R[nm]["snow_cm"] >= v, (
            f"🔴 `{nm}`이 2016/2019판 {v}보다 **작다** — 🔴221차에 ★2022 준거로 "
            "되돌려 같아진 칸이 있지만, 그보다 작아지면 설명되지 않는다")

    # ── ③ ⚠️ **대조 불가를 대조한 척하지 않는가** ───────────────────
    assert "원단위 대조가 불가능하다" in doc, (
        "🔴 2007판을 *「대조 불가」*로 남긴 기록이 사라졌다 — 접미사를 떼고 구간 "
        "중앙값을 잡으면 **원문에 없는 수**가 만들어진다(159차 교훈)")
    for frag in ("20～25미만", "그대로 일치 4개", "문산시", "흑산도"):
        assert frag in doc, f"🔴 대조 불가의 **근거**「{frag}」가 사라졌다"

    # ── ④ ⚠️ 별표가 **없는 판**을 없다고 적었는가 ───────────────────
    assert "별표가 있는 판 **6** · 없는 판 **4**" in doc, (
        "🔴 판마다 별표 유무를 **세어서** 적은 줄이 사라졌다")
    assert "원단위 대조가 된 판 **4**" in doc, (
        "🔴 *「원단위 대조가 된 판은 4」*가 사라졌다 — 10판을 **열었다**는 것과 "
        "**대조했다**는 것은 다르다")

    # ── ⑤ 📌 2014-78호의 자기 진술이 남아 있는가 ────────────────────
    assert "급간 세분화" in doc and "농촌진흥청 홈페이지에 게재" in doc, (
        "🔴 2014-78호가 **표를 고쳤다고 스스로 적는데 그 표가 법령정보센터에 없다**는 "
        "사실이 사라졌다 — 리포가 농사로에서 받아 대조한 이유다")

    # ── ⑥ ⚠️ 설계하중 값은 그대로인가 ──────────────────────────────
    assert len(R) == 172, "🔴 219차는 **읽기만** 했다 — 값이 움직이면 안 된다"

def test_220cha_nongsaro_original_closed_the_2014_edition():
    """220차 — **농사로에서 2014-78호를 찾아 대조했는가**(사용자 지시).

    🔴 **2014-78 = 2016-180 = 2019-44**(343항목 차이 0). 8년(2014~2022) 동안
    지역별 설계기준이 **한 자리도 움직이지 않았고**, 실제로 바뀐 것은
    **2022·2025 두 번**뿐이다.

    🔴 **셀 경계로 읽었다**: 619쪽 PDF의 p7·p8을 `extract_tables()`로 **7열 구조
    그대로** 뽑았다. raw text로 파싱하면 병합 셀 때문에 **컬럼이 밀린다** —
    엔진 주석이 이미 그 경고를 적어 두었다.

    ⚠️ **농사로에 고시는 2건뿐**이라 나머지 3판(2013-146·2010-128·2008-76)은
    **거기에도 없다**. 4판 중 1판만 닫혔다 — 전부 닫았다고 적지 않는다.
    """
    import smartfarm_engine as _e
    doc = _io_read("근거_외부수집_기능공백_20260924.md")
    eng = _io_read("smartfarm_engine.py")
    R = _e.REGION_DESIGN_LOAD

    # ── ① 🔴 2014 = 2016 = 2019 라는 결론이 서 있는가 ───────────────
    assert "제2014-78호 = 제2016-180호 = 제2019-44호" in eng, (
        "🔴 엔진 주석에서 *「2014 = 2016 = 2019」*가 사라졌다 — 이것이 "
        "**표가 8년간 그대로였다**는 결론의 근거다")
    assert "2022·2025 두 번뿐" in eng
    assert "2014-78 = 2016-180 = 2019-44" in doc

    # ── ② 🔴 2014판 값으로 재어도 **같은 72건**인가 ─────────────────
    #   218·219차가 박아 둔 적설 34건을 2014판에도 그대로 적용한다 —
    #   세 판이 같다면 성립해야 하고, 하나라도 어긋나면 결론이 깨진다.
    SNOW_2014 = {
        "강진": 22, "강화": 22, "과천": 24, "광명": 24, "광주광역시": 36,
        "군포": 24, "나주": 34, "대전": 30, "목포": 32, "문경": 34, "보은": 32,
        "상주": 30, "성남": 24, "성산": 22, "수원": 24, "순창": 36, "시흥": 24,
        "안산": 24, "안양": 24, "영덕": 34, "영암": 28, "영양": 24, "영월": 30,
        "예천": 26, "오산": 24, "옥천": 30, "용인": 24, "울진": 38, "의왕": 24,
        "인제": 30, "진도": 22, "함평": 36, "홍천": 30, "화성": 24,
    }
    assert len(SNOW_2014) == 34
    for nm, v in SNOW_2014.items():
        assert R[nm]["snow_cm"] >= v, (
            f"🔴 `{nm}`이 2014판 {v}보다 **작다** — 🔴221차에 ★2022 준거로 되돌려 "
            "같아진 칸이 있지만, 그보다 작아지면 설명되지 않는다")

    # ── ③ 📌 함평 36이 **원본에서 재확인**됐다는 기록 ───────────────
    assert SNOW_2014["함평"] == 36 and R["함평"]["snow_cm"] == 40
    assert "함평 36이 맞았다" in eng and "과거 전사는 정확했다" in eng, (
        "🔴 *「원본에서 함평 36을 재확인했다」*가 엔진 주석에서 사라졌다 — "
        "2026-07 발견의 **전사 정확성**을 독립적으로 뒷받침한 사실이다")

    # ── ④ ⚠️ **농사로에도 없는 3판**을 없다고 적었는가 ──────────────
    assert "농사로에 고시는 **2건뿐**" in doc, (
        "🔴 *「농사로 고시 검색 결과는 전체 2건」*이 사라졌다 — 나머지 3판이 "
        "**거기에도 없다**는 근거다")
    #   📌 **또 무딘 토큰이었다(열네 번째)**: 판 이름만 세니 219차가 쓴 §5-f 표에도
    #      있어서 *「아직 못 구했다」* 줄을 지워도 통과했다(220차 뮤테이션 M5).
    #      → **그 문장 전체**로 조인다.
    assert ("⚠️ **아직 표를 못 구한 판 3**: 제2013-146호 · 제2010-128호 · "
            "제2008-76호.") in doc, (
        "🔴 *「아직 표를 못 구한 판 3」*이 사라졌다 — 법령정보센터에도 농사로에도 "
        "없는 판이 셋 남았다는 것이 220차의 **남은 구멍**이다")
    assert "별표 없는 4판 중 **1판만** 표를 얻었다" in doc, (
        "🔴 *「4판 중 1판만」*이 사라졌다 — 넷을 다 닫은 것처럼 읽히면 안 된다")

    # ── ⑤ 🔴 **셀 경계로 읽었다**는 방법 기록 ───────────────────────
    assert "셀 경계로" in doc and "컬럼이 밀린다" in doc, (
        "🔴 *「raw text가 아니라 셀 경계로 읽었다」*가 사라졌다 — 병합 셀 표에서 "
        "raw text 파싱은 **밀린 수**를 만든다")
    assert "619쪽" in doc and "32,020,837" in doc, (
        "🔴 확보한 원본의 **크기·쪽수**가 사라졌다 — 같은 파일인지 확인할 표지다")

    # ── ⑥ ⚠️ 값은 그대로인가 ──────────────────────────────────────
    assert len(R) == 172, "🔴 220차는 **읽기만** 했다 — 값이 움직이면 안 된다"

def test_222cha_quote_rule_names_its_programme():
    """222차 — **이견 ③이 닫혔는가**(사용자 지시: 이견 ②·③ 닫기).

    🔴 세 요건이 *「반대로 읽힌」* 것은 **다른 사업을 겹쳐 읽었기 때문**이었다.
    「서로 다른 광역자치단체」는 **인삼생산시설현대화**, 「관내 업체 우선」은
    **군산시 공고**, 우리 ★준거인 **온실신축에는 그 요건이 없다**.

    🔴 그 과정에서 **213차의 과일반화**가 드러났다: `QUOTE_COUNT_RULE`을
    *「보조사업자 계약 기준」*으로 등재했는데 실제로는 **인삼 사업 한 절**의
    조항이었다. 어느 사업의 규칙인지 모르면 **없는 요건을 만들어 낸다**.

    ⚠️ ②는 **214차에 이미 닫혀 있었는데** 213차의 낡은 문장이 남아 215~221차
    보고가 *「닫히지 않았다」*를 되풀이했다 — 그 줄을 정정했다.
    """
    import smartfarm_engine as _e
    import json as _j
    doc = _io_read("근거_외부수집_기능공백_20260924.md")
    reg = _j.loads(_io_read("엔진데이터_레지스트리.json"))["constants"]

    # ── ① 🔴 규칙이 **어느 사업의 것인지 이름으로** 말하는가 ────────
    R = _e.QUOTE_COUNT_RULE
    assert R["applies_to"] == "특용작물(인삼)생산시설현대화 사업", (
        f"🔴 `QUOTE_COUNT_RULE`의 적용 사업이 {R.get('applies_to')!r}다 — 222차 "
        "확정은 **특용작물(인삼)생산시설현대화 사업**이다(발췌본 p176, 사업 머리 p172)")
    assert any("온실신축" in x for x in R["not_in"]), (
        "🔴 **온실신축에는 이 요건이 없다**는 사실이 상수에서 사라졌다 — 그것이 "
        "이견 ③의 답이고, 없으면 **없는 요건을 케이스에 들이대게 된다**")
    out = _e.quote_count_requirement(900_000_000, 700_000_000)
    assert out["applies_to"] == R["applies_to"]
    assert "온실신축 지침에는 **이 요건이 없다**" in out["note"], (
        "🔴 반환이 **적용 범위**를 말하지 않는다 — 판정만 내고 어디에 쓰는지 "
        "감추면 오용된다")

    # ── ② 🔴 값은 바꾸지 않았는가(바뀐 것은 적용 범위뿐) ────────────
    assert (R["base_count"], R["over_count"], R["distinct_region"]) == (1, 2, True), (
        "🔴 조항 값이 움직였다 — 222차가 고친 것은 **어디에 적용되는가**이지 "
        "**무엇을 요구하는가**가 아니다")
    assert reg["QUOTE_COUNT_RULE"]["value"]["applies_to"] == R["applies_to"], (
        "🔴 레지스트리와 엔진의 적용 사업이 갈라졌다")
    assert "222차 정정" in reg["QUOTE_COUNT_RULE"]["source"], (
        "🔴 레지스트리에서 **과일반화를 정정했다는 기록**이 사라졌다")

    # ── ③ 🔴 이견 ③이 **닫힌 근거**가 서 있는가 ────────────────────
    assert "### ⑤-i 🔴 222차 — 이견 ②·③을 닫았다" in doc
    for frag in ("특용작물(인삼)생산시설현대화", "군산시 청년 스마트팜 공고",
                 "p176 하나", "모순이 아니다"):
        assert frag in doc, f"🔴 이견 ③을 닫은 근거 「{frag}」가 사라졌다"

    # ── ④ ⚠️ ②가 **닫혀 있었다는 사실**과 내 잘못이 적혔는가 ────────
    assert "214차에 이미 닫혀 있었다" in doc, (
        "🔴 *「②는 214차에 이미 닫혀 있었다」*가 사라졌다")
    assert "여섯 차수 동안 보고했다" in doc, (
        "🔴 **닫힌 것을 열린 것처럼 되풀이 보고했다**는 기록이 사라졌다 — "
        "문서를 고칠 때 앞 절을 함께 고치지 않은 결과다")
    assert "~~⚠️ **이견 ②·③은 닫히지 않았다.**~~" in doc, (
        "🔴 213차의 낡은 문장이 **취소선 없이** 돌아왔거나 통째로 지워졌다 — "
        "지우지 말고 **정정 흔적을 남긴다**")

    # ── ⑤ 🔴 과일반화를 **과일반화라고** 적었는가 ───────────────────
    #   📌 **또 무딘 토큰이었다(열다섯 번째)**: `"내 과일반화"`가 **절 제목에도**
    #      있어서 소제목을 통째로 지워도 통과했다(222차 뮤테이션 M10).
    #      → **소제목 문장 전체**로 조인다.
    assert "#### 🔴 그 과정에서 **내 과일반화**가 드러났다" in doc, (
        "🔴 *「그 과정에서 내 과일반화가 드러났다」* 절이 사라졌다 — 원인을 적지 "
        "않으면 다음에 또 **어느 사업의 규칙인지 확인하지 않고** 등재한다")
    assert "**「보조사업자 계약 기준」으로 일반화**했다" in doc, (
        "🔴 **무엇을 과일반화했는지**가 사라졌다")

def test_223cha_benchmark_screen_follows_the_decided_order(monkeypatch):
    """223차 — **벤치마킹 화면 패턴**을 케이스 상세에 얹었다(사용자 지시 + 목업 승인).

    준거(186차 원문 대조): 생애주기 레일 = DNV Owner's Engineer · 실사 6영역 =
    Agritecture · 설계 대 실측 = kWh Analytics · 합격선 명시형 = PVEL.

    ★사용자 결정 2026-09-27: 플랫폼 3단계 묶음은 **설계검증 = ①②③ · 성능보증 =
    ⑤⑥ · 투자실사 = ④**, 표시 순서는 **①②③⑤⑥④**(레일과 탭이 같은 순서),
    바꾸는 곳은 **웹 콘솔만**(정적 보고서 순서는 그대로).

    🔴 묶음·순서는 `consulting_package`가 쥐고 화면은 옮겨 담기만 한다 —
       화면이 순서를 따로 쥐면 둘이 갈라진다(210차 교훈: 이름을 두 곳에서 짓지 않는다).
    """
    import re as _re
    import consulting_package as _cp
    import case_display as _cd
    from cases import load_cases as _lc

    # ── ① ★결정이 코드에 **그대로** 있는가 ─────────────────────────
    assert _cp.STAGE_ORDER == ("①공종설계", "②품질설계", "③감리",
                               "⑤운영", "⑥사후관리", "④타당성검증"), (
        f"🔴 표시 순서가 {_cp.STAGE_ORDER}로 바뀌었다 — ★사용자 결정(2026-09-27)은 ①②③⑤⑥④다")
    assert [(k, n, s) for k, n, s, _d, _b in _cp.PLATFORM_STAGES] == [
        ("P1", "설계검증", ("①공종설계", "②품질설계", "③감리")),
        ("P2", "성능보증", ("⑤운영", "⑥사후관리")),
        ("P3", "투자실사", ("④타당성검증",))], (
        "🔴 플랫폼 3단계 묶음이 ★사용자 결정(설계검증 ①②③ · 성능보증 ⑤⑥ · 투자실사 ④)과 다르다")
    assert set(_cp.STAGE_ORDER) == {s["stage"] for s in _cp.PACKAGE_SPEC}, (
        "🔴 `STAGE_ORDER`가 `PACKAGE_SPEC`의 단계 집합과 다르다 — 레일에서 산출물이 사라진다")
    flat = [st for _k, _n, sts, _d, _b in _cp.PLATFORM_STAGES for st in sts]
    assert tuple(flat) == _cp.STAGE_ORDER, (
        "🔴 3단계 묶음을 이어 붙인 순서가 레일 순서와 다르다 — 레일과 탭이 같은 순서여야 한다")

    # ── ② 정적 보고서는 **건드리지 않았는가**(같은 날 사용자 결정) ────
    assert "STAGE_ORDER" not in _io_read("build_site.py") and \
        "PLATFORM_STAGES" not in _io_read("build_site.py"), (
        "🔴 정적 보고서가 새 순서를 쓰기 시작했다 — 이번 결정은 **웹 콘솔만**이다")

    cs = _lc()
    full = [x for x in cs if not x.get("partial")]
    assert full, "케이스가 없다"
    for case in full:
        code = _cd.code(case)
        html = client.get("/case/" + code).text
        pkg = _cp.build_package(case)
        have = {x["code"]: x for x in pkg["items"]}

        # ── ③ 레일이 그 순서로 나오고, 27종이 **한 번씩** 올라가는가 ──
        got = _re.findall(r'<div class="sn">([^<]+)</div>', html)
        assert tuple(got) == _cp.STAGE_ORDER, (
            f"🔴 {code} 레일 순서가 {got}다 — `STAGE_ORDER`를 따르지 않는다")
        rail_codes = _re.findall(r'<details class="doc[^"]*">\s*<summary><code>(D\d+)</code>', html)
        assert sorted(rail_codes) == sorted(have), (
            f"🔴 {code} 레일의 산출물이 패키지와 다르다: 빠짐 "
            f"{sorted(set(have) - set(rail_codes))} · 중복/잉여 {sorted(rail_codes)}")
        appx = _re.findall(r'<details class="doc appx">\s*<summary><code>(D\d+)</code>', html)
        assert tuple(appx) == tuple(c for st in _cp.STAGE_ORDER for c in _cp.JUDGMENT_CODES
                                    if have[c]["stage"] == st), (
            f"🔴 {code} 레일의 판정 부록 표시가 {appx}다 — `JUDGMENT_CODES`(★194차)와 다르다")

        # ── ④ 탭 순서가 레일과 같은가 ─────────────────────────────
        pos = [html.find(f"<code>{k}</code> {n}") for k, n, *_r in _cp.PLATFORM_STAGES]
        assert all(p > 0 for p in pos) and pos == sorted(pos), (
            f"🔴 {code} 플랫폼 3단계 탭이 설계검증 → 성능보증 → 투자실사 순서가 아니다: {pos}")

        # ── ⑤ 「엔진 밖」과 등급이 **엔진 반환에서** 오는가 ────────────
        for k, key, field in (("P3", "D23", "공백 영역"), ("P2", "D24", "편차 함수 없는 항목")):
            gaps = have[key]["data"][field]
            assert gaps, f"🔴 {code} {key}의 「{field}」가 비었다 — 가드의 전제가 무너졌다"
            assert ("엔진 밖 — " + " · ".join(gaps)) in html, (
                f"🔴 {code} {k}의 「엔진 밖」이 {key} 반환({gaps})과 다르다")
        g = have["D25"]["data"]["등급"]
        assert f'<div class="gg">{g["grade"]}</div>' in html and \
            f'통과 {g["n_passed"]} / {g["n_total"]}' in html, (
            f"🔴 {code} 판정 부록의 등급·통과 수가 엔진 반환({g['grade']}, "
            f"{g['n_passed']}/{g['n_total']})과 다르다")
        uc = have["D23"]["data"]["단위 공사비 대조"]
        assert "{:,.0f}원/㎡".format(uc["unit_won_m2"]) in html, (
            f"🔴 {code} 단위 공사비가 엔진 반환({uc['unit_won_m2']})과 다르다")

    # ── ⑥ 🔴 화면이 **값을 짓지 않는가** ───────────────────────────
    tpl = _io_read("webapp_templates/case_detail.html")
    for w in ("경영진 역량", "시장위치", "에너지효율", "가동률"):
        assert w not in tpl, (
            f"🔴 템플릿에 「{w}」가 박혀 있다 — 「엔진 밖」 목록은 D23·D24 반환에서 와야 한다")
    exprs = _re.findall(r"\{\{(.*?)\}\}|\{%(.*?)%\}", tpl, _re.S)
    arith = [a or b for a, b in exprs if _re.search(r"\w\s*[-+*/%]\s*\w", (a or b)
                                                     .replace('"{:,.0f}"', "")
                                                     .replace("'chip-ref'", ""))]
    assert not arith, (
        f"🔴 템플릿 식에 산술이 있다: {arith} — 앱 계층은 표시 포맷팅만 한다(1절)")

    # ── ⑥-b 📌 등급을 **바꿔 넣어도 화면이 따라오는가** ─────────────────
    #   뮤테이션 M8이 잡혔다: 현재 케이스 셋이 **전부 C**라 템플릿에 「C」를 박아도
    #   ⑤가 통과했다(**고정값이 실측과 우연히 같으면 가드가 못 본다**). 엔진 반환을
    #   다른 값으로 바꿔 화면이 그것을 옮기는지 잰다.
    _orig = _cp.build_package

    def _swapped(case, injections=None):
        out = _orig(case, injections)
        for x in out["items"]:
            if x["code"] == "D25":
                x["data"]["등급"] = dict(x["data"]["등급"], grade="보류", n_passed=1)
        return out
    monkeypatch.setattr(webapp.cpkg, "build_package", _swapped)
    html = client.get("/case/" + _cd.code(full[0])).text
    assert '<div class="gg">보류</div>' in html and "통과 1 / " in html, (
        "🔴 판정 부록의 등급·통과 수가 엔진 반환을 따르지 않는다 — 화면에 값이 박혀 있다")
    monkeypatch.undo()

    # ── ⑦ 부분 케이스는 레일 없이 열리는가(4축 미산출이라 패키지가 없다) ──
    for case in [x for x in cs if x.get("partial")]:
        r = client.get("/case/" + _cd.code(case))
        assert r.status_code == 200 and 'class="rail"' not in r.text, (
            f"🔴 부분 케이스 {_cd.code(case)}가 레일을 냈거나 열리지 않는다")


def test_224cha_entry_stepper_shows_real_state():
    """224차 — **기입 절차 스테퍼**(SGS JAS 준거, 223차 목업 승인분).

    ★사용자 결정 2026-09-27: *「스테퍼만 — 실제 상태 표시」* — 주입 폼은 만들지
    않는다. 그래서 ②문서 제출·⑥발급은 **「경로 없음」**으로 드러나야 한다.
    📌226차(사용자 지시)에 두 양식이 생겨 미기입은 **「대기」**가 됐다 — 완료로
    보이지 않아야 한다는 요구는 그대로다.

    🔴 상태는 `consulting_package.entry_steps`가 **분류**하고 화면은 옮긴다 —
       등급·개수를 화면이 짓지 않는다.
    """
    import re as _re
    import copy as _copy
    import consulting_package as _cp
    import case_display as _cd
    from cases import load_cases as _lc

    # ── ① 7단계와 준거가 그대로인가 ────────────────────────────
    assert [k for k, *_r in _cp.ENTRY_STEPS] == [
        "case", "docs", "engine", "evidence", "rules", "issue", "renew"], (
        "🔴 기입 절차 단계가 바뀌었다 — 223차 목업 승인분은 7단계다")
    assert {w for _k, _n, w, _j in _cp.ENTRY_STEPS} == {"사람", "엔진"}
    assert [k for k, _n, w, _j in _cp.ENTRY_STEPS if w == "엔진"] == ["engine", "rules"], (
        "🔴 엔진이 하는 단계는 검증·규칙 적용 둘뿐이다 — 나머지는 사람 몫이다")

    html = client.get("/entry").text
    cells = _re.findall(r'data-step="(\w+)">\s*<span class="chip [^"]+">([^<]+)</span><br>\s*([^<\n]+?)\s*(?:<br>|</div>)',
                        html)
    full = [x for x in _lc() if not x.get("partial")]
    assert len(cells) == 7 * len(full), (
        f"🔴 스테퍼 칸이 {len(cells)}개다 — 케이스 {len(full)}건 × 7이어야 한다")

    for i, case in enumerate(full):
        pkg = _cp.build_package(case)
        want = _cp.entry_steps(case, pkg)
        got = cells[7 * i: 7 * i + 7]
        assert [(s["key"], s["state"], s["detail"]) for s in want] == \
            [(k, st, d.strip()) for k, st, d in got], (
            f"🔴 {_cd.code(case)} 스테퍼가 `entry_steps` 반환과 다르다: {got}")
        st = {s["key"]: s for s in want}

        # ── ② 🔴 경로가 없는 칸을 **완료처럼 보이지 않는가** ────────
        slots = [n["slot"] for n in pkg["open_injections"]]
        if any(s in slots for s in _cp.ENTRY_DOC_SLOTS):
            assert st["docs"]["state"] == "대기", (
                f"🔴 {_cd.code(case)} 문서가 없는데 ②가 「{st['docs']['state']}」다")
        if not (pkg["items"] and [x for x in pkg["items"] if x["code"] == "D25"][0]
                ["data"].get("식별번호")):
            assert st["issue"]["state"] == "대기" and st["renew"]["state"] == "대기"

        # ── ③ 근거 대조 수를 **독립으로** 다시 세어 대조 ─────────────
        prov = case.get("provenance") or {}
        n_open = sum(1 for v in prov.values()
                     if (v or {}).get("status") in ("추정", "확인요망", "미검증"))
        assert f"원문 대조 전 {n_open} / {len(prov)}필드" in st["evidence"]["detail"] or \
            (n_open == 0 and st["evidence"]["state"] == "완료"), (
            f"🔴 {_cd.code(case)} ④ 근거 대조 수가 케이스 provenance와 다르다")

        # ── ④ 등급은 D25 반환 그대로인가 ─────────────────────────
        g = [x for x in pkg["items"] if x["code"] == "D25"][0]["data"]["등급"]
        assert st["rules"]["detail"].startswith(
            f"등급 {g['grade']} · 통과 {g['n_passed']} / {g['n_total']}"), (
            f"🔴 {_cd.code(case)} ⑤가 D25 반환과 다르다: {st['rules']['detail']}")

    # ── ⑤ 📌 주입이 **생기면 상태가 따라 바뀌는가**(값이 박혀 있지 않은가) ──
    #   🔴225차 정정: 여기서 **가짜 문자열**("TEST-0001")을 넣었더니, 엔진이 실제로
    #      내는 `식별번호`·`유효기간`이 **dict**라는 것을 못 봤다 — 주입되는 순간 화면에
    #      dict가 샜다. → 발급은 **엔진에 실제로 주입**해 받은 반환으로 잰다.
    case = full[0]
    pkg = _copy.deepcopy(_cp.build_package(case, {"ksfid_seq": 7,
                                                  "ksfid_issued": "2026-09-27"}))
    pkg["open_injections"] = [n for n in pkg["open_injections"]
                              if n["slot"] not in _cp.ENTRY_DOC_SLOTS]
    d25 = [x for x in pkg["items"] if x["code"] == "D25"][0]["data"]
    real = d25["식별번호"]["ksfid"]
    d25["등급"] = dict(d25["등급"], complete=True, grade="보류")
    st = {s["key"]: s for s in _cp.entry_steps(case, pkg)}
    assert st["docs"]["state"] == "완료" and st["issue"]["state"] == "완료" and         st["renew"]["state"] == "진행" and st["rules"]["state"] == "완료" and         "등급 보류" in st["rules"]["detail"], (
        f"🔴 주입이 채워져도 스테퍼가 따라오지 않는다: {st}")
    assert st["issue"]["detail"] == "식별번호 " + real and         st["renew"]["detail"] == "유효기간 2026-09-27 ~ " + d25["유효기간"]["expires"], (
        f"🔴 발급·연차 칸이 엔진 반환을 옮기지 않는다: {st['issue']['detail']} / {st['renew']['detail']}")
    assert not any("{'" in s["detail"] for s in st.values()), (
        "🔴 스테퍼 문구에 dict가 샜다 — 엔진 반환의 필드를 골라 옮겨야 한다")

    # ── ⑥ 🔴 템플릿이 값을 짓지 않는가 ────────────────────────────
    tpl = _io_read("webapp_templates/entry_hub.html")
    #   📌226차: `"대기</span>"`를 템플릿 전체에서 찾으니 **기존 financing 표의 「대기」
    #      칩**에 걸렸다(무딘 토큰, 열여섯 번째) → **스테퍼 구간만** 잘라서 잰다.
    seg = tpl[tpl.index('class="steprow"'):tpl.index('<p class="note">')]
    for w in ("경로 없음", "대기", "완료", "진행"):
        assert f">{w}<" not in seg, f"🔴 스테퍼 구간에 상태 「{w}」가 박혀 있다"
    for w in ("등급 C", "통과 4"):
        assert w not in tpl, f"🔴 기입 허브 템플릿에 값 「{w}」가 박혀 있다"
    exprs = _re.findall(r"\{\{(.*?)\}\}|\{%(.*?)%\}", tpl, _re.S)
    arith = [a or b for a, b in exprs if _re.search(r"\w\s*[-+*/%]\s*\w", (a or b)
                                                     .replace("'chip-ref'", ""))]
    assert not arith, f"🔴 기입 허브 템플릿 식에 산술이 있다: {arith}"
    for w in ("추천", "권장", "최적", "1순위", "우선순위"):
        assert w not in html, f"🔴 기입 허브에 판정·추천 어휘 「{w}」가 들어왔다"


def test_225cha_tracking_id_badge_is_an_identifier_not_a_grade(monkeypatch):
    """225차 — **추적 식별자 배지**(GLOBALG.A.P. GGN 준거, 223차 목업 승인분).

    🔴 번호는 **식별자이지 등급이 아니다** — 배지에 등급 글자를 싣지 않는다.
    🔴 번호·만료일은 엔진(`ksfid_number`·`ksfid_validity`)이 D25에 실은 것을
       **그대로** 옮긴다. 미발급이면 형식과 빠진 주입 슬롯을 드러낸다.
    """
    import re as _re
    import consulting_package as _cp
    import smartfarm_engine as _e
    import case_display as _cd
    from cases import load_cases as _lc

    # ── ① 형식 문자열이 엔진 docstring과 같은가(두 곳에서 짓지 않는다) ──
    assert ("형식: `%s`" % _cp.KSFID_FORMAT) in (_e.ksfid_number.__doc__ or ""), (
        "🔴 배지의 번호 형식이 `ksfid_number` docstring과 다르다 — 형식을 바꿨다면 "
        "양쪽을 같이 고쳐라")

    full = [x for x in _lc() if not x.get("partial")]

    def _badge(html):
        m = _re.search(r'<div class="idbadge"[^>]*>(.*?)</div>', html, _re.S)
        assert m, "🔴 케이스 상세에 추적 식별자 배지가 없다"
        return m.group(1)

    # ── ② 미발급: 형식과 **실제로 빠진** 슬롯을 드러내는가 ──────────
    for case in full:
        b = _badge(client.get("/case/" + _cd.code(case)).text)
        pkg = _cp.build_package(case)
        need = [n["slot"] for n in [x for x in pkg["items"] if x["code"] == "D25"][0]["needs"]
                if n["slot"] in ("ksfid_seq", "ksfid_issued")]
        assert "미발급" in b and _cp.KSFID_FORMAT.replace("<", "&lt;").replace(">", "&gt;") in b, (
            f"🔴 {_cd.code(case)} 미발급 배지가 형식을 내지 않는다")
        assert _re.findall(r"<code>(ksfid_\w+)</code>", b) == need, (
            f"🔴 {_cd.code(case)} 배지의 대기 슬롯이 D25 needs({need})와 다르다")
        g = [x for x in pkg["items"] if x["code"] == "D25"][0]["data"]["등급"]["grade"]
        assert "등급 아님" in b and ("등급 " + g) not in b and ">%s<" % g not in b, (
            f"🔴 {_cd.code(case)} 배지에 등급이 섞였다 — 번호는 식별자이지 등급이 아니다")

    # ── ③ 발급: 엔진이 낸 번호·만료일이 **그대로** 나오는가 ──────────
    case = full[0]
    inj = {"ksfid_seq": 7, "ksfid_issued": "2026-09-27"}
    _orig = _cp.build_package
    monkeypatch.setattr(webapp.cpkg, "build_package",
                        lambda c, injections=None: _orig(c, inj))
    html = client.get("/case/" + _cd.code(case)).text
    b = _badge(html)
    inp = C.case_to_input(case)
    want = _e.ksfid_number(inp.region, inp.crop, inp.cover.value, 2026, 7)["ksfid"]
    exp = _e.ksfid_validity("2026-09-27")["expires"]
    assert f'<code class="iv">{want}</code>' in b and f"만료 {exp}" in b and "미발급" not in b, (
        f"🔴 발급 배지가 엔진 반환({want}, {exp})을 옮기지 않는다")
    assert "{'" not in html and "{&#39;" not in html, (
        "🔴 케이스 상세에 dict가 샜다 — `식별번호`는 dict다(225차 정정)")
    monkeypatch.undo()

    # ── ④ 🔴 템플릿이 번호를 짓지 않는가 ──────────────────────────
    tpl = _io_read("webapp_templates/case_detail.html")
    assert "KSF-" not in tpl, "🔴 템플릿에 번호 조각이 박혀 있다 — 형식은 `KSFID_FORMAT`에서 온다"


def test_226cha_docs_and_issue_forms_write_the_case_and_move_the_steps(tmp_cases):
    """226차 — **문서 제출·K-SFID 발급 주입 폼**(사용자 지시).

    🔴 저장 주입은 `build_package`가 **케이스에서 직접** 읽는다 — 콘솔과 정적 보고서가
       같은 값을 본다(한쪽만 읽으면 갈라진다, 210차 교훈).
    🔴 검증은 엔진이 한다: 범위 밖 번호·잘못된 날짜는 엔진 예외가 400으로 나온다.
    🔴 번호는 **발급기관이 준 것을 적을 뿐** — 콘솔이 번호를 고르지 않는다.
    """
    import re as _re
    import consulting_package as _cp
    import smartfarm_engine as _e
    path = tmp_cases / "wonchaewon.json"
    before = json.loads(path.read_text(encoding="utf-8"))
    assert _cp.DOC_SUBMISSION_KEY not in before and _cp.KSFID_ISSUE_KEY not in before, (
        "전제: 실케이스에는 아직 주입 블록이 없다")

    # ── ① 근거 없는 저장·엔진이 거부하는 값은 **저장되지 않는다** ────────
    docs = {"doc_rows_text": "R-01 | 측창 개폐 | A-101 | Rev2 | S-07 | Rev2 | B-12 | Rev1 | KS-01 | 2021",
            "dd_documents_text": "사업계획서(합성)\n설계도서 일식(합성)",
            "quoted_models_text": "온풍난방기", "ks_declared_text": "온풍난방기 = KS 적합 선언(합성)",
            "note": ""}
    assert client.post("/entry/docs/C2/save", data=docs).status_code == 400
    bad = dict(docs, doc_rows_text="R-01 | a | b | c | d | e | f | g | h | i | 넘침", note="x")
    assert client.post("/entry/docs/C2/save", data=bad).status_code == 400
    issue = {"ksfid_seq": "7", "ksfid_issued": "2026-09-27", "note": ""}
    assert client.post("/entry/issue/C2/save", data=issue).status_code == 400
    for k, v in (("ksfid_seq", "12000"), ("ksfid_issued", "2026-13-40")):
        r = client.post("/entry/issue/C2/save", data=dict(issue, note="x", **{k: v}))
        assert r.status_code == 400, f"🔴 엔진이 거부할 {k}={v}가 저장까지 갔다"
    assert json.loads(path.read_text(encoding="utf-8")) == before, (
        "🔴 거부된 요청이 케이스를 바꿨다")

    # ── ② 미리보기는 엔진 반환을 옮기고, 저장하지 않는다 ─────────────
    r = client.post("/entry/issue/C2/preview", data=issue)
    inp = C.case_to_input(before)
    want = _e.ksfid_number(inp.region, inp.crop, inp.cover.value, 2026, 7)["ksfid"]
    assert r.status_code == 200 and _re.findall(r'id="pv-ksfid">([^<]+)', r.text) == [want], (
        "🔴 발급 미리보기가 엔진이 조립한 번호를 내지 않는다")
    r = client.post("/entry/docs/C2/preview", data=docs)
    assert r.status_code == 200 and "R-01" in r.text and "온풍난방기" in r.text
    assert json.loads(path.read_text(encoding="utf-8")) == before, "🔴 미리보기가 저장했다"

    # ── ③ 저장하면 케이스에 **근거와 함께** 기록되고 절차가 움직인다 ──────
    docs["note"] = "고객 제출 문서(합성) — 출처 형식 예시"
    issue["note"] = "발급기관 인증서(합성) — 출처 형식 예시"
    assert client.post("/entry/docs/C2/save", data=docs, follow_redirects=False).status_code == 303
    assert client.post("/entry/issue/C2/save", data=issue, follow_redirects=False).status_code == 303
    saved = json.loads(path.read_text(encoding="utf-8"))
    ds, ki = saved[_cp.DOC_SUBMISSION_KEY], saved[_cp.KSFID_ISSUE_KEY]
    assert ds["doc_rows"][0]["req_id"] == "R-01" and ds["doc_rows"][0]["std_rev"] == "2021"
    assert ds["dd_documents"] == ["사업계획서(합성)", "설계도서 일식(합성)"]
    assert ds["ks_declared"] == {"온풍난방기": "KS 적합 선언(합성)"} and ds["note"]
    assert ki == {"ksfid_seq": 7, "ksfid_issued": "2026-09-27", "note": issue["note"]}
    for k in ("input", "provenance", "title"):
        assert saved[k] == before[k], f"🔴 주입 저장이 케이스의 `{k}`를 건드렸다"

    pkg = _cp.build_package(saved)            # 🔴 인자 없이 — 저장분을 **스스로** 읽는가
    have = {x["code"]: x for x in pkg["items"]}
    slots = [n["slot"] for n in pkg["open_injections"]]
    for s in ("doc_rows", "dd_documents", "quoted_models", "ksfid_seq", "ksfid_issued"):
        assert s not in slots, f"🔴 저장했는데 `{s}`가 아직 주입 대기다 — 패키지가 저장분을 안 읽는다"
    assert have["D23"]["data"]["제출 문서"] == ds["dd_documents"]
    assert have["D25"]["data"]["식별번호"]["ksfid"] == want
    assert have["D19"]["status"] == "생성"

    st = {s["key"]: s for s in _cp.entry_steps(saved, pkg)}
    assert st["docs"]["state"] == "완료" and st["issue"]["state"] == "완료" and \
        st["renew"]["state"] == "진행", f"🔴 저장 후 절차가 움직이지 않았다: {st}"
    html = client.get("/case/C2").text
    assert f'<code class="iv">{want}</code>' in html, "🔴 케이스 상세 배지가 저장분을 내지 않는다"
    hub = client.get("/entry").text
    assert "식별번호 " + want in hub, "🔴 기입 허브 스테퍼가 저장분을 내지 않는다"

    # ── ④ 폼을 다시 열면 저장값이 채워져 있는가(왕복) ────────────────
    f = client.get("/entry/docs/C2").text
    assert "R-01 | 측창 개폐 | A-101" in f and "온풍난방기 = KS 적합 선언(합성)" in f
    assert 'value="7"' in client.get("/entry/issue/C2").text

    # ── ⑤ 🔴 새 양식에 산술·추천 어휘가 없는가 ──────────────────────
    for t in ("entry_docs.html", "entry_issue.html"):
        tpl = _io_read("webapp_templates/" + t)
        exprs = _re.findall(r"\{\{(.*?)\}\}|\{%(.*?)%\}", tpl, _re.S)
        arith = [a or b for a, b in exprs if _re.search(
            r"\w\s*[-+*/%]\s*\w", (a or b).replace("'chip-ref'", ""))]
        assert not arith, f"🔴 {t} 식에 산술이 있다: {arith}"
    for u in ("/entry/docs/C2", "/entry/issue/C2"):
        body = client.get(u).text
        for w in ("추천", "권장", "최적", "1순위", "우선순위"):
            assert w not in body, f"🔴 {u}에 판정·추천 어휘 「{w}」가 들어왔다"


def test_227cha_approval_attachments_reach_the_equipment_reconcile(tmp_cases):
    """227차 — **재료승인 첨부 입력**(사용자 지시). 문서 제출 양식에 `attachments_by_model`.

    🔴 첨부 누락은 **엔진**(`equipment_reconcile`)이 시방서 6종과 대조해 낸다 —
       양식 안내의 6종 목록도 엔진 상수를 그대로 쓴다(두 곳에서 적지 않는다).
    ⚠️ 이견(227차 발견): D25 `equipment_ks`의 근거 문구는 *「KS 적합 선언·재료승인
       첨부가 갖춰졌는가」*인데 검사는 **선언만** 봤다. → 📌228차 ★사용자 결정(B10 ⓑ)으로
       검사에 **첨부 6종 완비**를 더했다(⑤가 그것을 잰다).
    """
    import consulting_package as _cp
    import smartfarm_engine as _e
    path = tmp_cases / "wonchaewon.json"
    before = json.loads(path.read_text(encoding="utf-8"))

    # ── ① 안내 목록 = 엔진 상수 ─────────────────────────────────
    assert _cp.APPROVAL_ATTACHMENTS == tuple(_e.MATERIAL_APPROVAL_ATTACHMENTS)
    page = client.get("/entry/docs/C2").text
    assert " · ".join(_e.MATERIAL_APPROVAL_ATTACHMENTS) in page, (
        "🔴 양식 안내가 시방서 6종(엔진 상수)을 그대로 내지 않는다")

    base = {"quoted_models_text": "온풍난방기\n보온커튼",
            "ks_declared_text": "온풍난방기 = KS 적합 선언(합성)",
            "note": "고객 제출 첨부(합성) — 출처 형식 예시"}

    # ── ② 형식이 틀리거나 견적에 없는 모델이면 **저장되지 않는다** ────────
    for bad in ("온풍난방기 시험성적표", "환기팬 = 시험성적표", "온풍난방기 = "):
        r = client.post("/entry/docs/C2/save", data=dict(base, attachments_text=bad))
        assert r.status_code == 400, f"🔴 잘못된 첨부 입력 {bad!r}이 저장까지 갔다"
    assert json.loads(path.read_text(encoding="utf-8")) == before

    # ── ③ 저장 → 케이스 → 패키지 D19가 **엔진과 같은** 첨부 누락을 낸다 ──
    att = "온풍난방기 = 시험성적표, 카탈로그\n보온커튼 = 제조업자 시방서"
    r = client.post("/entry/docs/C2/save", data=dict(base, attachments_text=att),
                    follow_redirects=False)
    assert r.status_code == 303
    saved = json.loads(path.read_text(encoding="utf-8"))
    want_att = {"온풍난방기": ["시험성적표", "카탈로그"], "보온커튼": ["제조업자 시방서"]}
    assert saved[_cp.DOC_SUBMISSION_KEY]["attachments_by_model"] == want_att
    pkg = _cp.build_package(saved)
    d19 = [x for x in pkg["items"] if x["code"] == "D19"][0]["data"]
    ref = _e.equipment_reconcile(["온풍난방기", "보온커튼"],
                                 {"온풍난방기": "KS 적합 선언(합성)"}, want_att)
    assert [(x["model"], x["attachments_given"], x["attachments_missing"]) for x in d19["rows"]] == \
        [(x["model"], x["attachments_given"], x["attachments_missing"]) for x in ref["rows"]], (
        "🔴 패키지 D19의 첨부 대조가 엔진 반환과 다르다 — 저장 첨부가 전달되지 않는다")
    assert d19["rows"][0]["attachments_missing"] == [
        a for a in _e.MATERIAL_APPROVAL_ATTACHMENTS if a not in ("시험성적표", "카탈로그")]

    # ── ④ 미리보기 표와 재열기 왕복 ─────────────────────────────
    pv = client.post("/entry/docs/C2/preview", data=dict(base, attachments_text=att)).text
    assert ", ".join(d19["rows"][1]["attachments_missing"]) in pv, (
        "🔴 미리보기 표가 엔진의 첨부 누락을 내지 않는다")
    #   📌 무딘 토큰(열일곱 번째, 뮤테이션 M7): 입력칸 **placeholder**가 같은 예문
    #      「온풍난방기 = 시험성적표, 카탈로그」라 재열기 값이 비어도 통과했다 →
    #      textarea **본문**만 잘라 잰다.
    import re as _re
    body = _re.search(r'<textarea id="attachments_text"[^>]*>([^<]*)</textarea>',
                      client.get("/entry/docs/C2").text).group(1)
    assert body.splitlines() == att.splitlines(), (
        f"🔴 문서 양식을 다시 열면 저장된 첨부가 채워지지 않는다: {body!r}")

    # ── ⑤ 🔴228차 ★사용자 결정(B10 ⓑ): `equipment_ks` = 선언 + 첨부 6종 **완비** ──
    #   227차엔 여기서 *「첨부는 등급을 바꾸지 않는다」*를 고정했다(이견 고정). 사용자가
    #   ⓑ를 골라 **규칙이 바뀌었고** 이 절도 함께 바꿨다. 두 모델 모두 **선언이 있어야**
    #   첨부만의 효과를 잰다(선언이 빠지면 첨부와 무관하게 불합격이라 가드가 못 본다).
    full6 = list(_e.MATERIAL_APPROVAL_ATTACHMENTS)

    both = {"온풍난방기": "KS 선언(합성)", "보온커튼": "KS 선언(합성)"}

    def _eqks(att_map, ks=both):
        c = dict(saved)
        c[_cp.DOC_SUBMISSION_KEY] = dict(
            saved[_cp.DOC_SUBMISSION_KEY], ks_declared=ks, attachments_by_model=att_map)
        it = [x for x in _cp.build_package(c)["items"] if x["code"] == "D25"][0]
        row = [r for r in it["data"]["등급"]["rows"] if r["key"] == "equipment_ks"][0]
        return row["state"], [n["slot"] for n in it["needs"]]

    st_full, need_full = _eqks({"온풍난방기": full6, "보온커튼": full6})
    st_part, need_part = _eqks({"온풍난방기": full6, "보온커튼": full6[:-1]})
    st_none, need_none = _eqks({})
    #   📌 뮤테이션 M5: 선언 검사를 빼도 위 셋은 통과했다 → **첨부 완비 + 선언 누락**을 잰다
    st_nodecl, _n = _eqks({"온풍난방기": full6, "보온커튼": full6}, {"온풍난방기": "KS 선언(합성)"})
    assert st_nodecl == "불합격", (
        f"🔴 첨부가 다 있어도 선언이 빠졌는데 「{st_nodecl}」다 — 선언과 첨부는 **둘 다** 필요하다")
    assert st_full == "통과" and "attachments_by_model" not in need_full, (
        f"🔴 선언과 첨부 6종이 모두 있는데 `equipment_ks`가 「{st_full}」다")
    assert st_part == "불합격" and "attachments_by_model" in need_part, (
        f"🔴 첨부 1종이 빠졌는데 「{st_part}」다 — ★B10 ⓑ는 **6종 완비**다")
    #   📌238차(레드팀 29회차 A2): 「첨부 미제출 = 불합격」은 사용자 결정이 아니라 228차 내 선택이었다 →
    #      **못 본 것은 미검증**(같은 블록의 원칙)으로 되돌렸다. 통과가 아닌 것은 그대로다. 📌239차 ★B11 ⓐ 확정.
    assert st_none == "미검증" and "attachments_by_model" in need_none, (
        f"🔴 첨부가 하나도 없는데 「{st_none}」다 — 못 본 것은 미검증이다(통과로 세면 227차 이견으로 돌아간다)")
    reg = json.loads(_io_read("엔진데이터_레지스트리.json"))["constants"]["KSFID_CHECK_SPEC"]
    #   📌265차: 「228차」 글자는 239차 서술에도 나온다 — 228차 기록 문구 자체를 본다(뮤테이션 재현에서 놓침)
    assert "📌228차 — ★**사용자 결정(2026-09-27, B10 ⓑ)**" in reg["source"] and reg["status"] == "결정", (
        "🔴 규칙을 바꿨는데 레지스트리 `KSFID_CHECK_SPEC` 출처에 ★결정 기록이 없다")


def test_229cha_ksfid_year_follows_the_issue_date():
    """229차 — ★사용자 결정(2026-09-27): K-SFID 번호의 연도는 **발급일의 연도**다.

    226차까지 `2026`이 박혀 있어 2027년 발급분도 `KSF-2026-…`이 됐다.
    🔴 발급일이 없으면 **연도를 모르므로 번호를 만들지 않는다** — 지어내지 않는다.
    """
    import re as _re
    import consulting_package as _cp
    import smartfarm_engine as _e
    import case_display as _cd
    from cases import load_cases as _lc
    case = [x for x in _lc() if not x.get("partial")][0]
    inp = C.case_to_input(case)

    def _d25(inj):
        pkg = _cp.build_package(case, inj)
        it = [x for x in pkg["items"] if x["code"] == "D25"][0]
        st = {s["key"]: s for s in _cp.entry_steps(case, pkg)}
        return it["data"], [n["slot"] for n in it["needs"]], st["issue"]

    # ── ① 연도가 발급일에서 온다(두 해를 대조 — 한 해만 재면 박힌 값과 구별이 안 된다) ──
    for day in ("2026-09-27", "2027-03-01", "2031-12-31"):
        data, _n, st = _d25({"ksfid_seq": 7, "ksfid_issued": day})
        want = _e.ksfid_number(inp.region, inp.crop, inp.cover.value, int(day[:4]), 7)["ksfid"]
        assert data["식별번호"]["ksfid"] == want and want.startswith("KSF-%s-" % day[:4]), (
            f"🔴 발급일 {day}인데 번호가 {data['식별번호']['ksfid']}다 — 연도는 발급일에서 와야 한다")
        assert st["detail"] == "식별번호 " + want

    # ── ② 발급일이 없으면 번호가 **없다** — 그리고 무엇이 없는지 말한다 ──────
    data, needs, st = _d25({"ksfid_seq": 7})
    assert "식별번호" not in data and "ksfid_issued" in needs and "ksfid_seq" not in needs, (
        "🔴 발급일 없이 번호를 만들었다 — 연도를 지어낸 것이다")
    assert st["state"] == "대기" and st["detail"].startswith("ksfid_issued 미주입"), (
        f"🔴 스테퍼가 빠진 것을 잘못 말한다: {st['detail']}")
    data, needs, st = _d25({"ksfid_issued": "2027-03-01"})
    assert "식별번호" not in data and needs.count("ksfid_seq") == 1 and \
        st["detail"].startswith("ksfid_seq 미주입"), f"🔴 일련번호 없음이 드러나지 않는다: {st['detail']}"

    # ── ③ 발급 양식 미리보기도 같은 길을 탄다 ─────────────────────
    r = client.post("/entry/issue/%s/preview" % _cd.code(case),
                    data={"ksfid_seq": "7", "ksfid_issued": "2027-03-01", "note": ""})
    got = _re.findall(r'id="pv-ksfid">([^<]+)', r.text)
    assert got == [_e.ksfid_number(inp.region, inp.crop, inp.cover.value, 2027, 7)["ksfid"]], (
        f"🔴 발급 미리보기 번호가 발급일 연도를 따르지 않는다: {got}")

    # ── ④ 🔴 연도 리터럴이 번호 조립에 남지 않았는가 ──────────────────
    src = _io_read("consulting_package.py")
    call = src[src.index('d["식별번호"] = e.ksfid_number('):]
    call = call[:call.index(")") + 1]
    assert not _re.search(r"\b20\d\d\b", call), f"🔴 번호 조립에 연도 리터럴이 있다: {call}"


def test_231cha_docs_form_shows_normalization_and_unrecognized(tmp_cases):
    """231차 — 문서 양식 미리보기가 **표기 정리와 인식 안 됨**을 엔진 반환 그대로 낸다.

    🔴 저장값은 **적힌 그대로**다(원문 보존) — 정규화는 대조할 때 엔진이 한다.
    """
    import consulting_package as _cp
    import smartfarm_engine as _e
    path = tmp_cases / "wonchaewon.json"
    form = {"quoted_models_text": "온풍난방기",
            "ks_declared_text": "온풍난방기 = KS 선언(합성)",
            "attachments_text": "온풍난방기 = 시험성적서, 표준색상철, 세금계산서",
            "note": "고객 제출 첨부(합성) — 출처 형식 예시"}
    pv = client.post("/entry/docs/C2/preview", data=form).text
    assert "시험성적서→시험성적표" in pv and "표준색상철→표준 색상철" in pv, (
        "🔴 미리보기가 표기 정리를 보여 주지 않는다")
    assert "인식 안 됨</span> 세금계산서" in pv, "🔴 인식 안 된 이름이 드러나지 않는다"
    #   📌232차: 영문 별칭 「Manufacturer's …」의 `'`를 Jinja가 `&#39;`로 이스케이프한다 —
    #      화면은 맞고 **비교가 날것**이었다 → Jinja와 같은 `markupsafe.escape`로 잰다.
    from markupsafe import escape as _esc
    for a, c in _e.MATERIAL_APPROVAL_ALIASES.items():
        assert f"{_esc(a)}→{_esc(c)}" in pv, f"🔴 양식 안내에 등재 별칭 {a}→{c}가 없다"

    assert client.post("/entry/docs/C2/save", data=form, follow_redirects=False).status_code == 303
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved[_cp.DOC_SUBMISSION_KEY]["attachments_by_model"] == {
        "온풍난방기": ["시험성적서", "표준색상철", "세금계산서"]}, (
        "🔴 저장값을 정본으로 고쳐 썼다 — 적힌 그대로 보존해야 출처와 대조할 수 있다")
    d19 = [x for x in _cp.build_package(saved)["items"] if x["code"] == "D19"][0]["data"]["rows"][0]
    assert d19["attachments_unrecognized"] == ["세금계산서"] and \
        "시험성적표" not in d19["attachments_missing"], "🔴 패키지 D19가 정규화를 거치지 않는다"


def test_242cha_d9_winter_months_are_entered_per_case(tmp_cases):
    """242차 — ★사용자 결정(2026-09-28): **D-9 동절기 달은 케이스마다 입력, 한 달 지정도 유효**.

    원문 주는 「동절기 평균풍속 3.0m/s 이상 = 강풍지역」이라고만 하고 달을 정하지 않는다 —
    엔진은 기본값을 두지 않고(`mean_wind(months)`), 입지 조건 양식이 근거와 함께 받는다.
    🔴 150차 「단일 월 12종 → 11곳」은 **정의 후보를 넣어 본 수**였다 — 어느 달을 쓸지는 정하지 않는다.
    """
    import inspect as _in
    import consulting_package as _cp
    import smartfarm_engine as _e
    path = tmp_cases / "wonchaewon.json"
    before = json.loads(path.read_text(encoding="utf-8"))

    # ── ① 엔진은 여전히 기본값을 두지 않는다 ─────────────────────────
    assert _in.signature(_e.mean_wind).parameters["months"].default is _in.Parameter.empty

    # ── ② 거부 — 달 없음 · 13월 · 스크린 미선택 · 근거 없음 ─────────────────
    ok = {"winter_m": ["1"], "has_thermal_screen": "no", "note": "설계 조건서(합성) — 출처 형식 예시"}
    for bad in ({**ok, "winter_m": []}, {**ok, "winter_m": ["13"]},
                {**ok, "has_thermal_screen": ""}, {**ok, "note": ""}):
        assert client.post("/entry/site/C2/save", data=bad).status_code == 400, bad
    assert json.loads(path.read_text(encoding="utf-8")) == before, "🔴 거부된 요청이 케이스를 바꿨다"

    # ── ③ 한 달 지정 저장 → 케이스 블록 → 패키지가 스스로 읽는다 ──────────
    assert client.post("/entry/site/C2/save", data=ok, follow_redirects=False).status_code == 303
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved[_cp.SITE_CONDITIONS_KEY] == {"winter_months": [1], "has_thermal_screen": False,
                                              "note": ok["note"]}
    inj = _cp.case_injections(saved)
    assert inj["winter_months"] == [1] and inj["has_thermal_screen"] is False

    # ── ④ D1은 지점이 있으면 엔진 값을 낸다 — 가상의 춘천 케이스로 잰다 ─────────
    trial = dict(saved)
    trial["input"] = dict(saved["input"], region="강원(춘천)")
    d1 = [x for x in _cp.build_package(trial)["items"] if x["code"] == "D1"][0]
    want = _e.mean_wind("춘천", [1])
    assert d1["data"]["동절기 평균풍속"] == want
    assert d1["data"]["풍속 보정계수"] == _e.wind_correction_factor(want, False)
    assert "winter_months" not in [n["slot"] for n in d1["needs"]], "🔴 입력했는데 동절기가 아직 대기다"
    # 원채원(「충남」)은 지점이 없어 평균풍속도 None이다 — 달을 넣어도 지어내지 않는다
    d1w = [x for x in _cp.build_package(saved)["items"] if x["code"] == "D1"][0]["data"]
    assert d1w["동절기 평균풍속"] is None and "풍속 보정계수" not in d1w

    # ── ⑤ 기록 ─────────────────────────────────────────────────────
    reg = json.loads(_io_read("엔진데이터_레지스트리.json"))["constants"]["WIND_CORRECTION_FACTOR"]["source"]
    assert "D-9 동절기 개월은 케이스마다 입력, 한 달 지정도 유효" in reg
    led = _io_read("근거_결정대기대장_20260915.md")
    assert "| ~~**D-9**~~ ✅**닫힘(242차)** |" in led
    assert "★D-9 결정" in _cp.INJECTION_SLOTS["winter_months"]


def test_245cha_agritecture_layout_uses_only_existing_data():
    """245차 — Agritecture 홈 구성을 벤치마킹했다(사용자 지시: 세부 내용은 두고 구성만).

    상단 메뉴 + 행동 버튼 · 히어로 → 숫자 띠 → 일하는 방식 → 서비스 → 케이스 → 근거 현황 · 푸터.
    🔴 **내용은 이미 있는 데이터만** 쓴다 — 숫자 띠는 실측, 일하는 방식은 ★결정된 3단계, 서비스는 기능 축,
       Agritecture의 **고객 추천사 자리는 지어낼 수 없어 근거 현황**으로 바꿨다.
    """
    import re as _re
    import consulting_package as _cp
    from cases import load_cases as _lc
    html = client.get("/").text

    # ── ① 섹션 순서 ────────────────────────────────────────────────
    marks = ['class="hero"', 'class="stats"', 'id="how"', 'id="svc"', 'id="cs"', 'id="ev"']
    pos = [html.find(m) for m in marks]
    assert all(p > 0 for p in pos) and pos == sorted(pos), f"🔴 홈 섹션 순서가 다르다: {pos}"

    # ── ② 숫자 띠 = 실측 ────────────────────────────────────────────
    reg = json.loads(_io_read("엔진데이터_레지스트리.json"))["constants"]
    cs = _lc()
    want = {"케이스": len(cs), "산출물": len(_cp.PACKAGE_SPEC), "근거 상수": len(reg),
            "출처 연결": sum(len(v.get("source_refs") or []) for v in reg.values())}
    got = dict((l, int(n)) for n, l in _re.findall(
        r'<div class="n">(\d+)</div><div class="l">([^<]+)</div>', html))
    assert got == want, f"🔴 숫자 띠 {got}가 실측 {want}와 다르다 — 숫자를 짓지 않는다"

    # ── ③ 일하는 방식 = ★결정된 3단계 순서 · 서비스 = 기능 축 ──────────────
    flow = _re.findall(r'<div class="step">\s*<div class="no">\d</div>\s*<h3>([^<]+)</h3>', html)
    assert flow == [n for _k, n, *_r in _cp.PLATFORM_STAGES], f"🔴 일하는 방식 순서가 {flow}다"
    svc = _re.findall(r'<span class="code">(F\d) ·', html)
    assert svc == [f for f, _n, _d in _cp.BENCHMARK_FUNCTIONS], f"🔴 서비스 카드가 {svc}다"

    # ── ④ 지어낸 추천사·실적 과장이 없다 ─────────────────────────────
    for w in ("추천사", "고객 후기", "What Our Clients Say", "+ Projects", "억 원 자문"):
        assert w not in html, f"🔴 홈에 근거 없는 홍보 문구 「{w}」가 들어왔다"
    assert "근거 현황" in html and "/pages/SmartFarm_근거대장.html" in html

    # ── ⑤ 모든 화면이 같은 상단 메뉴·행동 버튼·푸터를 쓴다(사이드바 없음) ────────
    for u in ("/", "/functions", "/entry", "/case/C1", "/entry/docs/C1", "/entry/site/C1"):
        h = client.get(u).text
        assert '<header class="topbar">' in h and 'class="cta" href="/entry/newcase"' in h, u
        assert '<footer class="foot">' in h and "<aside>" not in h, u


def test_248cha_work_order_screens_show_the_audit_as_is(monkeypatch):
    """248차 — WO-003: 콘솔 작업지시서 화면(읽기 전용)이 검사기 반환값을 **그대로** 보여 주는가.

    🔴 확인 수/전체는 `parse_wo()`가 센 수다 — 화면이 따로 세지 않는다(앱 계층 산술 0).
    🔴 경로 값으로 파일을 열지 않는다 — 폴더에 있는 번호만 열리고, 나머지는 404다.
    """
    import re as _re, os as _o
    import audit_work_orders as A
    r = A.audit()
    d = _o.path.join(_o.path.dirname(_o.path.abspath(webapp.__file__)), "docs", "work-orders")

    # ── ① 색인 행 = 파일 · 확인 수 = 파서 ────────────────────────────
    html = client.get("/workorders").text
    got = _re.findall(r'<tr data-wo="([^"]+)">', html)
    assert got == [f["id"] for f in r["files"]], got
    assert len(got) == len([f for f in _o.listdir(d) if A.FILE_RE.match(f)])
    cnt = dict(zip(got, _re.findall(r'data-checked="(\d+)" data-total="(\d+)"', html)))
    for f in r["files"]:
        p = f["parsed"]
        assert cnt[f["id"]] == (str(p["n_checked"]), str(p["n_criteria"])), f["id"]
    assert ("PASS" if r["pass"] else "FAIL") in html

    # ── ② 상세 — 9절이 순서대로 · 수용기준 체크 상태 그대로 ──────────────
    h1 = client.get("/workorders/WO-001").text
    pos = [h1.find(f'id="s{n}"') for n in range(1, 10)]
    assert all(x > 0 for x in pos) and pos == sorted(pos), pos
    for n, t in enumerate(A.SECTION_TITLES, 1):
        assert t in h1, t
    p1 = next(f["parsed"] for f in r["files"] if f["id"] == "WO-001")
    assert h1.count('<span class="chip chip-measured">확인</span>') == p1["n_checked"]
    #   🔴 완료된 WO는 전부 「확인」이라 **체크를 무시하는 화면도 통과한다** — 임시 폴더에서
    #      WO-001 수용기준 절반을 풀어 **미확인이 미확인으로** 나오는지 본다.
    import tempfile as _tf, shutil as _sh, io as _io
    tmp = _tf.mkdtemp()
    try:
        for fn in _o.listdir(d):
            _sh.copy(_o.path.join(d, fn), tmp)
        fp = next(_o.path.join(tmp, fn) for fn in _o.listdir(tmp) if fn.startswith("WO-001_"))
        t = _io.open(fp, encoding="utf-8").read()
        _io.open(fp, "w", encoding="utf-8").write(t.replace("- [x] ", "- [ ] ", 3))
        _orig = A.audit
        monkeypatch.setattr(webapp.awo, "audit", lambda folder=tmp: _orig(folder))
        h2 = client.get("/workorders/WO-001").text
        p2 = A.parse_wo(_io.open(fp, encoding="utf-8").read())
        assert p2["n_checked"] == p1["n_checked"] - 3
        assert h2.count('<span class="chip chip-est">미확인</span>') == 3
        assert h2.count('<span class="chip chip-measured">확인</span>') == p2["n_checked"]
        h3 = client.get("/workorders").text
        assert f'data-checked="{p2["n_checked"]}" data-total="{p2["n_criteria"]}"' in h3
    finally:
        monkeypatch.undo()
        _sh.rmtree(tmp, ignore_errors=True)

    # ── ③ 경로 조작·없는 번호 ───────────────────────────────────────
    for u in ("/workorders/WO-999", "/workorders/..%2FCLAUDE", "/workorders/README",
              "/workorders/WO-001_스킬설치_리포적용.md"):
        assert client.get(u).status_code == 404, u
    #   📌 폴더 조회만으로도 404가 나서 **번호 형식 검사를 지워도 통과했다**(등가 변이) —
    #      형식이 틀린 값은 **폴더를 보기 전에** 형식 사유로 거부되는지 본다.
    for u in ("/workorders/README", "/workorders/WO-001_스킬설치_리포적용.md", "/workorders/wo-001"):
        assert "WO 번호 형식이 아니다" in client.get(u).text, u
    assert "WO 번호 형식이 아니다" not in client.get("/workorders/WO-999").text

    # ── ④ 모든 화면의 참조 메뉴에 링크 ───────────────────────────────
    #   📌 푸터에도 같은 링크가 있어 href만 보면 **메뉴에서 빠져도 통과한다** — 메뉴 항목 그대로 본다.
    for u in ("/", "/functions", "/entry", "/case/C1", "/workorders"):
        h = client.get(u).text
        assert '<a href="/workorders">작업지시서(WO)<small>' in h, u
        assert '<a href="/workorders">작업지시서(WO)</a></div>' in h, u


def test_251cha_work_orders_carry_no_personal_names(monkeypatch):
    """251차 — 사용자 지시 「개인 이름은 무기명으로 처리」: WO 문서·색인·콘솔 WO 화면에 실명이 없는가.

    🔴 판정은 `case_display.audit` **그대로** 쓴다 — 명단을 따로 두면 제2의 명단이 된다(183·184차 표시 계층).
    🔴 파일(R9)과 화면(scrub) **두 겹**이다 — 검사가 FAIL인 WO가 들어와도 화면에는 코드로 나간다.
    ⚠️ 경계: 엔진·케이스·레지스트리·옛 차수 기록은 **내부 데이터**라 그대로다(추적성 — 183차).
    """
    import os as _o, io as _io, re as _re, tempfile as _tf, shutil as _sh
    import audit_work_orders as A
    import case_display as cd
    d = _o.path.join(_o.path.dirname(_o.path.abspath(webapp.__file__)), "docs", "work-orders")

    # ── ① 파일·파일명·색인 ─────────────────────────────────────────
    r = A.audit()
    assert r["pass"], r["problems"]
    for fn in _o.listdir(d):
        assert cd.audit(fn) == {}, fn
        assert cd.audit(_io.open(_o.path.join(d, fn), encoding="utf-8").read()) == {}, fn

    # ── ② R9가 잡는가(본문 · 파일명) ─────────────────────────────────
    name = next(f for f in _o.listdir(d) if f.startswith("WO-001_"))
    base = _io.open(_o.path.join(d, name), encoding="utf-8").read()
    known = {f["id"] for f in r["files"]}
    leak = base.replace("## 2. 배경·사용자\n", "## 2. 배경·사용자\n- 우민재 농가 표본\n", 1)
    assert leak != base
    msgs = A.check_wo(leak, name, known)
    assert any(x.startswith("R9") for x in msgs)
    #   📌 메시지가 찾은 이름을 되풀이하면 **CLI 출력이 누출 경로**가 된다(화면은 scrub이 가려 준다)
    assert cd.audit(" ".join(msgs)) == {}, msgs
    assert any(x.startswith("R9") for x in A.check_wo(base, "WO-001_최선동.md", known))
    assert not any(x.startswith("R9") for x in A.check_wo(base, name, known))

    # ── ③ 화면 — 실명이 든 WO가 들어와도 코드로 나간다 ─────────────────
    tmp = _tf.mkdtemp()
    try:
        for fn in _o.listdir(d):
            _sh.copy(_o.path.join(d, fn), tmp)
        _io.open(_o.path.join(tmp, name), "w", encoding="utf-8").write(
            leak.replace("# 작업지시서 WO-001: ", "# 작업지시서 WO-001: 임미라 ", 1))
        _orig = A.audit
        monkeypatch.setattr(webapp.awo, "audit", lambda folder=tmp: _orig(folder))
        assert not webapp.awo.audit()["pass"]
        for u in ("/workorders", "/workorders/WO-001"):
            h = client.get(u).text
            assert cd.audit(h) == {}, (u, cd.audit(h))
        assert "C3 농가 표본" in client.get("/workorders/WO-001").text
    finally:
        monkeypatch.undo()
        _sh.rmtree(tmp, ignore_errors=True)

    # ── ④ 이 지시 뒤의 새 차수 기록(249~251)에도 실명이 없다 ─────────────
    lg = _io_read("차수로그.md")
    #   📌256차(레드팀 30회차 B6③·B9): 249~251로 고정하면 뒤 차수를 보지 않는다 — 이 세션이 쓴 245차부터
    #   최신까지 **전부** 본다(245~248은 256차에 코드로 바꿨다).
    top = int(_re.search(r"- \*\*2026-\d\d-\d\d (\d+)차\*\*", lg).group(1))
    for n in range(245, top + 1):
        #   📌263차 — 날짜가 바뀌었다(2026-09-29). 차수 번호로 찾는다
        i = _re.search(r"(?m)^- \*\*2026-\d\d-\d\d %d차\*\*" % n, lg).start()
        j = lg.index("\n- **2026-", i + 5)
        assert cd.audit(lg[i:j]) == {}, (n, cd.audit(lg[i:j]))


def test_259cha_home_hero_is_the_user_copy():
    """259차 — ★사용자 결정(2026-09-28): 홈 히어로 제목은 「스마트농업을 디자인하다」.

    🔴 제목만 바꿨다 — 설명문(엔진이 계산하고 출처 상태를 함께 낸다)과 섹션 구성은 그대로여야 한다.
    결정은 코드 주석과 현행 릴리스 §4에 기록돼 있어야 하고, 과장 문구(256차 B2)는 돌아오지 않는다.
    """
    import re as _re
    html = client.get("/").text
    h1 = _re.search(r'<div class="hero">\s*<h1>(.*?)</h1>', html, _re.S)
    assert h1 and _re.sub(r"<[^>]+>", "", h1.group(1)) == "스마트농업을 디자인하다", h1 and h1.group(1)
    assert "실측인지, 추정인지, 확인이 필요한지" in html, "🔴 설명문까지 바뀌었다 — 결정은 제목만이다"
    assert "모든 수치에 근거가 붙는" not in html
    assert "★사용자 결정(2026-09-28): 히어로 제목은 「스마트농업을 디자인하다」" in _io_read("webapp.py")
    #   📌261차(31회차 A10): 릴리스 표현을 「홈 제목(`<h1>`)」으로 좁혔다 — 사용자 발언은 제목 문구 하나였다
    assert "홈 **제목(`<h1>`)**은 259차에 ★「스마트농업을 디자인하다」로 확정" in _io_read("릴리스_v1.2_20260928.md")


def test_261cha_redteam31_corrections_hold():
    """261차 — 레드팀 31회차(256~260차 대상) 반영이 되돌아가지 않는가.

    B1 WO 화면이 **대상 수·「해당 없음」 칩**을 파서 값대로 보여 준다(256차 표시를 지키는 가드가 없었다).
    B2 「해당 없음」은 **분기 표기**만이고, 체크된 해당 없음 기준은 문제다.  B3 「잘」 · B4 자리표시자.
    A1 C3 면적 2,323은 총표지에만 — 「단가대비표 2,323」은 자재 단가 오독.  A2 결정 기록 위치.
    A3 확인요망 U2의 철회된 산식 표시.  B6 D-15 인용은 리포 전사본(「공정등이」)과 같다.
    """
    import re as _re, os as _o, io as _io
    import audit_work_orders as A
    r = A.audit()
    assert r["pass"], r["problems"]

    # ── B1 화면 = 파서 ───────────────────────────────────────────
    html = client.get("/workorders").text
    #   📌264차(32회차 B9): 행 단위로 잘라 읽는다(비탐욕 정규식이 다음 행 값을 가져갈 수 있었다) · NA 없는 WO도 표시 대조
    segs = {m.group(1): m.group(0) for m in _re.finditer(r'<tr data-wo="([^"]+)">.*?</tr>', html, _re.S)}
    for f in r["files"]:
        p = f["parsed"]
        seg = segs[f["id"]]
        assert f'data-applicable="{p["n_applicable"]}"' in seg, (f["id"], seg[-200:])
        shown = f'{p["n_checked"]} / {p["n_applicable"]}' + (f' <small>(해당 없음 {p["n_na"]})</small>' if p["n_na"] else "")
        assert shown + "</td>" in seg, (f["id"], shown)
        h = client.get(f"/workorders/{f['id']}").text
        assert h.count('<span class="chip chip-ref">해당 없음</span>') == p["n_na"], f["id"]
        assert h.count('<span class="chip chip-est">미확인</span>') == p["n_applicable"] - p["n_checked"], f["id"]
        assert f'수용기준 확인 {p["n_checked"]} / {p["n_applicable"]}' in h, f["id"]
        assert "당시 값" in h

    # ── B2·B3·B4 검사기 ────────────────────────────────────────────
    d = _o.path.join(_o.path.dirname(_o.path.abspath(webapp.__file__)), "docs", "work-orders")
    name = next(fn for fn in _o.listdir(d) if fn.startswith("WO-001_"))
    base = _io.open(_o.path.join(d, name), encoding="utf-8").read()
    crit = next(ln for ln in base.splitlines() if ln.startswith("- [x] `docs/HANDOFF.md`"))
    known = {f["id"] for f in r["files"]}
    def chk(line):
        s = base.replace(crit, line)
        p = A.parse_wo(s)
        return A.check_wo(s, name, known), (p["n_checked"], p["n_applicable"], p["n_na"])
    probs, cnt = chk("- [ ] (C2 해당 없음 — 온실 없음) 실제 기준 (확인: 같은 명령)")
    assert cnt[2] == 0, "🔴 분기 표기가 아닌 괄호를 해당 없음으로 셌다"
    probs, cnt = chk("- [x] (ⓐ 해당 없음 — ⓑ 선택) 기준 (확인: 같은 명령)")
    assert cnt[2] == 1 and any("해당 없음인데 체크" in x for x in probs) and cnt[0] <= cnt[1]
    assert chk("- [ ] (ⓐ·ⓑ 해당 없음 - ⓒ 선택) 기준 (확인: 같은 명령)")[1][2] == 1
    for bad in ("잘된다", "매우잘 된다", "제대로잘동작"):
        assert any(x.startswith("R2") for x in chk(f"- [x] {bad} (확인: 같은 명령)")[0]), bad
    for ok in ("잘리지 않는다", "잘립니다", "잘릴 수 있다", "잘림 없이", "잘못된 값", "잘라 낸 줄", "잘게 나눈다"):
        assert chk(f"- [x] {ok} (확인: 같은 명령)")[0] == [], ok
    for ph in ("…", "-", "`명령`", "명령", "`…`", "—", "TBD", "테스트 명령"):
        assert any(x.startswith("R2") for x in chk(f"- [x] 끝난다 (확인: {ph})")[0]), ph

    # ── A1·A2·A3·B6 문서 ────────────────────────────────────────────
    led = _io_read("근거_결정대기대장_20260915.md")
    d7 = next(ln for ln in led.splitlines() if ln.startswith("| ~~**D-7**~~"))
    assert "면적 **2,323**은 `총표지 (2)`에만" in d7 and "물가정보 단가 2,323원/EA" in d7
    cl = _io_read("근거_확인요망대장_20260915.md")
    assert "표지·단가대비표 2,323과도" not in cl and "149차에 철회된 산식" in cl
    rel = _io_read("릴리스_v1.2_20260928.md")
    assert "레지스트리·대장·WO 세 곳" not in rel.replace("「레지스트리·대장·WO 세 곳」", "")
    assert "**239~244차는 레지스트리에도**" in rel and "**250~255차는 WO에도**" in rel
    assert "유리닦기 등의 공정이 없는 것으로" not in led and "유리닦기 등의 공정등이 없는 것으로 조사" in led
    assert "유리닦기 등의 공정등이 없는 것으로 조사" in _io_read("엔진데이터_레지스트리.json")


def _io_read(rel):
    import io as _i, os as _o
    return _i.open(_o.path.join(_o.path.dirname(_o.path.abspath(webapp.__file__)), rel),
                   encoding="utf-8").read()


def test_275cha_axes_map_flattens_existing_axes_without_making_one():
    """275차(WO-011) — 축 대응표가 **있는 매핑을 펴기만** 하는가.

    🔴 축 값은 전부 상수에서 온 그대로다 — 화면·조립 함수가 축 이름을 새로 짓지 않는다.
    🔴 기입 축의 대응은 `entry_steps()` **원문에서 다시 센다** — 그 함수가 이름을 대는
       산출물 코드가 늘면 `ENTRY_STEP_OF_CODE`도 늘어야 한다(갈리면 실패).
    🔴 대응이 없는 칸은 **「대응 없음」**으로 나온다. 없는 대응을 채우면 다섯 번째 축이다.
    """
    import re as _re, inspect as _inspect
    import consulting_package as _cp

    ix = _cp.axis_map()

    # ── ① 27행 · 코드 집합이 기능 배정과 같다 ─────────────────────────────
    codes = [r["code"] for r in ix["rows"]]
    assert len(codes) == 27 and len(set(codes)) == 27, len(codes)
    assert set(codes) == set(_cp.FUNCTION_OF_CODE), (
        set(codes) ^ set(_cp.FUNCTION_OF_CODE))
    assert ix["total"] == 27

    # ── ② 축 값이 상수에서 온 그대로다(새 이름 0) ──────────────────────────
    stages = set(_cp.STAGE_ORDER)
    fns = {"%s %s" % (f, n) for f, n, _d in _cp.BENCHMARK_FUNCTIONS}
    plats = {"%s %s" % (k, n) for k, n, _s, _d, _b in _cp.PLATFORM_STAGES}
    steps = {n for _k, n, _w, _j in _cp.ENTRY_STEPS}
    #   ⚠️ 「목록 안에 있나」로만 재면 **전부 같은 값을 넣어도** 통과한다 —
    #      플랫폼은 **그 행의 단계에서 유도된 것**인지 본다
    plat_of_stage = {st: "%s %s" % (k, n)
                     for k, n, sts, _d, _b in _cp.PLATFORM_STAGES for st in sts}
    for r in ix["rows"]:
        assert r["stage"] in stages, r
        assert r["platform"] == plat_of_stage[r["stage"]], (
            "🔴 %s의 플랫폼이 단계에서 유도되지 않았다: %r" % (r["code"], r))
        assert r["function"] in fns, r
        for e in r["entry"]:
            assert e in steps, r
    #   축 목록도 상수 길이를 그대로 낸다
    assert ix["axes"] == [("단계", "STAGE_ORDER", 6), ("플랫폼", "PLATFORM_STAGES", 3),
                          ("기능", "BENCHMARK_FUNCTIONS", 4), ("기입", "ENTRY_STEPS", 7)], ix["axes"]

    # ── ③ 🔴 기입 대응을 `entry_steps()` 원문에서 다시 센다 ─────────────────
    named = sorted(set(_re.findall(r"D\d+", _inspect.getsource(_cp.entry_steps))))
    assert named == sorted(_cp.ENTRY_STEP_OF_CODE), (
        "🔴 `entry_steps()`가 이름을 대는 코드 %r와 ENTRY_STEP_OF_CODE %r가 갈라졌다"
        % (named, sorted(_cp.ENTRY_STEP_OF_CODE)))
    assert named == ["D25"], named
    #   D25만 세 단계를 더 받는다
    for r in ix["rows"]:
        extra = [e for e in r["entry"] if e != "엔진 검증"]
        assert (extra != []) == (r["code"] == "D25"), (r["code"], r["entry"])

    # ── ④ 대응 없는 단계는 숨지 않는다 ────────────────────────────────────
    empty = [s["key"] for s in ix["by_step"] if not s["codes"]]
    assert empty == list(_cp.ENTRY_STEP_NO_CODE), (empty, _cp.ENTRY_STEP_NO_CODE)
    for s in ix["by_step"]:
        if not s["codes"]:
            assert s["note"] == _cp.AXIS_NONE, s
    assert len(ix["by_step"]) == 7
    #   「엔진 검증」은 산출물 전체를 받는다
    eng = next(s for s in ix["by_step"] if s["key"] == "engine")
    assert set(eng["codes"]) == set(codes)

    # ── ⑤ 화면 — 200 · 27행 · 판정 어휘 0 · 메뉴 링크 ──────────────────────
    r = client.get("/axes")
    assert r.status_code == 200
    html = r.text
    assert html.count('<td class="c">') == 27, html.count('<td class="c">')
    assert html.count("대응 없음") >= 3
    for bad in ("추천", "권장", "최적", "우선순위", "순위", "등급이 높"):
        assert bad not in html, f"🔴 축 대응표에 판정 어휘 「{bad}」"
    assert "분류이지 판정이 아니다" in html
    #   ⚠️ 머리 메뉴와 푸터 **두 곳**이다 — 한 곳만 지워도 통과하면 안 된다
    for page in ("/", "/functions", "/entry"):
        n_link = client.get(page).text.count('href="/axes"')
        assert n_link == 2, f"🔴 {page}의 축 대응표 링크가 {n_link}곳이다(머리·푸터 2곳)"

    # ── ⑥ 🔴 새 축을 만들지 않았다 ────────────────────────────────────────
    import os as _o, io as _io
    src = _io.open(_o.path.join(_o.path.dirname(_o.path.abspath(webapp.__file__)),
                                "consulting_package.py"), encoding="utf-8").read()
    for made_up in ("SITE_FACILITY_EQUIPMENT", "OBJECT_AXIS", "부지_시설_장비"):
        assert made_up not in src, f"🔴 새 축 `{made_up}`이 생겼다 — 축을 세우는 것은 ★사용자다"
    assert "새 축을 만들지 않는다" in src
    assert "없는 대응을 만들어 채우면" in src


def test_276cha_refs_catalog_is_recounted_from_the_files(monkeypatch):
    """276차(WO-012) — 참조 카탈로그가 **파일에서 다시 센 것**인가.

    🔴 건수를 문서에서 옮기지 않는다 — 이 가드가 glob으로 다시 세어 화면과 맞춘다.
    🔴 설명을 지어내지 않는다 — `근거지도`·`source_refs`에서 온 것이고, 없으면
       「설명 없음(등재 필요)」으로 **드러난다**(빈칸으로 숨지 않는다).
    🔴 status를 새로 매기지 않는다 — 레지스트리 값과 한 글자도 다르지 않다.
    """
    import os as _o, io as _io, glob as _g, json as _json
    import consulting_package as _cp
    import case_display as _cd
    root = _o.path.dirname(_o.path.abspath(webapp.__file__))
    cat = _cp.refs_catalog()

    # ── ① 갈래별 건수를 glob으로 다시 센다 ────────────────────────────────
    by = {g["key"]: g for g in cat["groups"]}
    assert list(by) == ["docs", "originals", "outputs", "wos"], list(by)
    n = lambda pat: len(_g.glob(_o.path.join(root, pat)))
    assert by["docs"]["count"] == n("근거_*.md"), by["docs"]["count"]
    assert by["outputs"]["count"] == n("SmartFarm_*.html") + n("index.html")
    assert by["wos"]["count"] == n(_o.path.join("docs", "work-orders", "WO-*.md"))
    assert cat["total"] == sum(g["count"] for g in cat["groups"])
    #   원문 갈래 = 레지스트리가 지목한 비-md 파일 ∪ 법령·고시
    reg = _json.loads(_io.open(_o.path.join(root, "엔진데이터_레지스트리.json"),
                               encoding="utf-8").read())["constants"]
    cited = {r["file"] for v in reg.values() for r in (v.get("source_refs") or [])
             if r.get("file") and not r["file"].endswith(".md")}
    cited |= {_o.path.basename(p) for p in _g.glob(_o.path.join(root, "법령_*.pdf"))}
    cited |= {_o.path.basename(p) for p in _g.glob(_o.path.join(root, "고시_*.pdf"))}
    assert by["originals"]["count"] == len(cited), (by["originals"]["count"], len(cited))

    # ── ② 설명은 옮긴 것이다 — 지도 행과 글자가 같다 ───────────────────────
    mp = _cp._refs_map_rows(root)
    for x in by["docs"]["items"]:
        if x["name"] in mp:
            assert x["desc"] == mp[x["name"]][0], x["name"]
            assert x["extra"] == ""
        else:
            assert x["desc"] == _cp.REFS_NO_DESC and x["extra"] == _cp.REFS_NOT_IN_MAP, x
    assert cat["not_in_map"] == sum(1 for x in by["docs"]["items"]
                                    if x["extra"] == _cp.REFS_NOT_IN_MAP)

    # ── ③ 없는 것을 숨기지 않는다 ─────────────────────────────────────────
    real_missing = [x["name"] for x in by["originals"]["items"]
                    if not _o.path.exists(_o.path.join(root, x["name"]))]
    flagged = [x["name"] for x in by["originals"]["items"]
               if x["extra"] == _cp.REFS_NOT_IN_REPO]
    assert sorted(real_missing) == sorted(flagged), (real_missing, flagged)
    assert cat["missing"] == len(flagged)
    #   🔴 설명은 **옮긴 것**이다 — note가 있으면 그 note, 없으면 「설명 없음」.
    #      기본값을 지어내면(예: 「원문 자료」) 여기서 걸린다.
    note_of = {}
    for _v in reg.values():
        for _r in (_v.get("source_refs") or []):
            f_ = _r.get("file")
            if f_ and f_ not in note_of and _r.get("note"):
                note_of[f_] = _r["note"]
    for x in by["originals"]["items"]:
        assert x["desc"] == note_of.get(x["name"], _cp.REFS_NO_DESC), (
            "🔴 %s의 설명이 옮긴 것이 아니다: %r" % (x["name"], x["desc"][:40]))
    #   설명 없는 항목은 **정말로 아무 상수도 가리키지 않는 것**이어야 한다
    for g in cat["groups"]:
        for x in g["items"]:
            if x["desc"] == _cp.REFS_NO_DESC and g["key"] == "originals":
                assert not x["consts"], (x["name"], x["consts"])

    # ── ④ status는 레지스트리 값이다(새로 매기지 않는다) ────────────────────
    st_of = {k: (v.get("status") or "") for k, v in reg.items()}
    for g in cat["groups"]:
        for x in g["items"]:
            want = sorted({st_of[c] for c in x["consts"] if c in st_of and st_of[c]})
            assert x["statuses"] == want, (x["name"], x["statuses"], want)

    # ── ⑤ 화면 — 200 · 전수 · 실명 0 · 죽은 링크 0 · 메뉴 2곳 ───────────────
    r = client.get("/refs")
    assert r.status_code == 200
    html = r.text
    assert html.count('class="it"') == cat["total"], (html.count('class="it"'), cat["total"])
    assert _cd.audit(html) == {}, _cd.audit(html)
    for x in by["outputs"]["items"]:
        assert client.get(x["href"]).status_code == 200, x["href"]
    for page in ("/", "/functions", "/entry"):
        c_ = client.get(page).text.count('href="/refs"')
        assert c_ == 2, f"🔴 {page}의 참조 카탈로그 링크가 {c_}곳이다(머리·푸터 2곳)"

    # ── ⑥ 269·270차 자료가 이름으로 찾힌다 ────────────────────────────────
    docnames = {x["name"] for x in by["docs"]["items"]}
    for want in ("근거_외부수집_기능공백_20260924.md",
                 "근거_지역정규화_기상지점_20260929.md",
                 "근거_콘솔점검_20260929.md"):
        assert want in docnames, f"🔴 {want}가 카탈로그에 없다"

    # ── ⑦ 경계 문구를 지우지 않았다 ───────────────────────────────────────
    src = _io.open(_o.path.join(root, "consulting_package.py"), encoding="utf-8").read()
    assert "설명을 지어내지 않는다" in src and "status를 새로 매기지 않는다" in src
    assert "세어서 낸다" in src
    assert "지어내지 않는다" in cat["note"] and "리포에 없음" in cat["note"]

    # ── ⑧ 🔴 표시 문구를 **글자로 못 박는다** — 상수와 함께 바뀌면 가드가 데이터를
    #      따라간다(211·212차 교훈). 빈 문자열로 바꿔 숨기는 것을 여기서 잡는다.
    assert _cp.REFS_NO_DESC == "설명 없음(등재 필요)", _cp.REFS_NO_DESC
    assert _cp.REFS_NOT_IN_REPO == "리포에 없음", _cp.REFS_NOT_IN_REPO
    assert _cp.REFS_NOT_IN_MAP == "지도 미등재", _cp.REFS_NOT_IN_MAP

    # ── ⑨ 🔴 지금 0건인 가지를 **일부러 만들어** 작동하는지 본다 ────────────
    #      (지도 미등재 0 · 리포에 없음 0이라 위 단언만으로는 비어 있다)
    monkeypatch.setattr(_cp, "_refs_map_rows", lambda root: {})
    blind = _cp.refs_catalog()
    bd = next(g for g in blind["groups"] if g["key"] == "docs")
    assert blind["not_in_map"] == bd["count"] > 0
    assert all(x["extra"] == "지도 미등재" and x["desc"] == "설명 없음(등재 필요)"
               for x in bd["items"]), "🔴 지도에 없는 문서가 드러나지 않는다"
    monkeypatch.undo()

    #   없는 원문을 레지스트리에 심어 「리포에 없음」이 뜨는지 본다
    real = _cp._refs_read
    ghost = "없는원문_가드시험_20260929.pdf"
    def fake(path):
        t = real(path)
        if path.endswith("엔진데이터_레지스트리.json"):
            d = _json.loads(t)
            d["constants"]["_GUARD_PROBE"] = {
                "status": "추정",
                "source_refs": [{"file": ghost, "note": "가드가 심은 것"}]}
            return _json.dumps(d, ensure_ascii=False)
        return t
    monkeypatch.setattr(_cp, "_refs_read", fake)
    probed = _cp.refs_catalog()
    po = next(g for g in probed["groups"] if g["key"] == "originals")
    hit = [x for x in po["items"] if x["name"] == ghost]
    assert len(hit) == 1 and hit[0]["extra"] == "리포에 없음", hit
    assert hit[0]["desc"] == "가드가 심은 것", hit
    assert probed["missing"] == 1, probed["missing"]
    monkeypatch.undo()


def test_277cha_guide_covers_every_console_screen():
    """277차(WO-013) — 사용 안내가 **콘솔 화면 전부**를 덮는가.

    🔴 라우트를 앱에서 읽어 목록과 대조한다 — 새 화면이 생기면 **빠진 채로 통과하지 않는다**.
    🔴 답에는 **리포 안 출처**가 붙고, 출처가 가리키는 파일·속성이 **실재**한다.
    🔴 확인 안 된 질문은 **「확인 필요」**로 남는다 — 지어낸 답이 0이다.
    🔴 기입 7단계는 **상태기계로 남는다** — 안내가 그것을 대신하지 않는다.
    """
    import os as _o, io as _io
    import consulting_package as _cp
    import case_display as _cd
    root = _o.path.dirname(_o.path.abspath(webapp.__file__))
    rd = lambda p_: _io.open(_o.path.join(root, p_), encoding="utf-8").read()
    g = _cp.guide_index()

    # ── ① 앱의 GET 라우트 = 화면 목록 + 화면 아닌 경로 ────────────────────
    got = {r.path for r in webapp.app.routes
           if "GET" in (getattr(r, "methods", None) or set())}
    listed = {s["path"] for s in g["screens"]} | {x["path"] for x in g["not_screens"]}
    assert got == listed, (
        "🔴 안내에 빠진 화면 %r · 안내에만 있는 경로 %r" % (sorted(got - listed), sorted(listed - got)))
    #   📌278차(WO-014)에 관점별 화면 2개가 늘어 17 → 19가 됐다
    #   📌281차(N-1)에 기본설계 화면이 늘어 19 → 20이 됐다
    assert len(g["screens"]) == 20 and len(g["not_screens"]) == 3, g["counts"]
    #   화면마다 네 칸이 다 있다(빈칸으로 넘어가지 않는다)
    for s in g["screens"]:
        for k in ("name", "what", "input", "output", "why_empty"):
            assert s[k] and s[k].strip(), (s["path"], k)

    # ── ② 화면 링크가 실제로 열린다 ───────────────────────────────────────
    codes = [c["code"] for c in [{"code": "C1"}, {"code": "C2"}]]
    for s in g["screens"]:
        p_ = (s["path"].replace("{display_code}", codes[0])
              .replace("{wo_id}", "WO-001").replace("{name}", "농업인"))
        assert client.get(p_).status_code == 200, (s["path"], p_)

    # ── ③ 답에 출처가 붙고, 출처가 실재한다 ───────────────────────────────
    import re as _re
    for item in g["faq"] + g["qa"]:
        assert item["src"].strip(), item["q"]
        for tok in _re.findall(r"[\w가-힣_.]+\.(?:md|py|json)", item["src"]):
            assert _o.path.exists(_o.path.join(root, tok)), (
                "🔴 출처 파일이 없다: %s (%s)" % (tok, item["q"]))
        #   ⚠️ `consulting_package.py`처럼 **파일 확장자**가 붙은 것은 이름이 아니다
        import smartfarm_engine as _e
        for attr in _re.findall(r"(?:smartfarm_engine|consulting_package)\.(\w+)", item["src"]):
            if attr in ("py", "md", "json"):
                continue
            assert hasattr(_cp, attr) or hasattr(_e, attr), (
                "🔴 출처가 가리키는 이름이 없다: %s" % attr)

    # ── ④ 확인 필요를 지우지 않았다 ───────────────────────────────────────
    need = [x for x in g["qa"] if not x["answered"]]
    assert len(need) == g["counts"]["need_check"] >= 1
    for x in need:
        assert "확인 필요" in x["a"], (
            "🔴 「확인 필요」로 표시했는데 답이 그렇게 말하지 않는다: %s" % x["q"])
    #   답이 있다고 표시한 것은 **확인 필요라고 말하지 않는다**
    for x in g["qa"]:
        if x["answered"]:
            assert "확인 필요" not in x["a"], x["q"]

    # ── ⑤ 기입 7단계는 상태기계로 남는다 ──────────────────────────────────
    assert len(_cp.ENTRY_STEPS) == 7
    assert [k for k, *_ in _cp.ENTRY_STEPS][0] == "case"
    src = rd("consulting_package.py")
    assert "기입 7단계(`ENTRY_STEPS`)는 그대로 둔다" in src
    assert "매뉴얼로 바꾸면 「어디까지 했는가」를 잃는다" in src

    # ── ⑥ 화면 — 실명 0 · 판정 어휘 0 · 메뉴 2곳 ──────────────────────────
    r = client.get("/guide")
    assert r.status_code == 200
    html = r.text
    assert _cd.audit(html) == {}, _cd.audit(html)
    assert html.count('class="scr"') == 20
    assert html.count("확인 필요") >= len(need)
    for bad in ("추천", "권장합니다", "최적", "이것이 맞다"):
        assert bad not in html, f"🔴 안내에 판정 어휘 「{bad}」"
    for page in ("/", "/functions", "/entry"):
        c_ = client.get(page).text.count('href="/guide"')
        assert c_ == 2, f"🔴 {page}의 사용 안내 링크가 {c_}곳이다(머리·푸터 2곳)"

    # ── ⑦ 수치를 새로 적지 않았다 — 경계 문구 존속 ────────────────────────
    #   ⚠️ 같은 문구가 주석과 note 두 곳에 있다 — **따로** 본다(한 곳만 지워도 잡히게)
    head = src[:src.index("GUIDE_SCREENS: tuple")]
    assert "수치를 새로 적지 않는다" in head, "🔴 주석의 수치 금지 경계가 사라졌다"
    assert "수치를 새로 적지 않는다" in g["note"], "🔴 note의 수치 금지 경계가 사라졌다"
    assert "**「확인 필요」**가 정답이다" in src
    assert "리포 안 출처가 있는 것만" in g["note"]


def test_278cha_perspective_entries_are_a_view_not_a_verdict(monkeypatch):
    """278차(WO-014) — 관점별 입구가 **입구이지 판정이 아닌가**.

    🔴 배정은 상수 한 곳에 있고 화면은 읽기만 한다 — 화면이 코드를 새로 고르지 않는다.
    🔴 27종이 적어도 한 관점에 들어가고, 어디에도 없으면 **화면에 드러난다**.
    🔴 가점 대조표는 **지침 원문 인용**이고 대응이 없으면 **없다고 적는다** —
       「가점을 받는다」고 단정하면 실패.
    🔴 공통·근거 9종이 메뉴에 **이름으로 나온다**(273차 §2가 연 것).
    """
    import os as _o, io as _io
    import consulting_package as _cp
    import case_display as _cd
    root = _o.path.dirname(_o.path.abspath(webapp.__file__))
    rd_ = lambda p_: _io.open(_o.path.join(root, p_), encoding="utf-8").read()
    ix = _cp.perspective_index()

    # ── ① 배정 — 27종 전부, 고아 0, 상수와 한 글자도 다르지 않다 ────────────
    assert ix["total"] == 27 and len(_cp.PACKAGE_SPEC) == 27
    names = [n for n, _a, _c in _cp.PERSPECTIVES]
    assert names == ["농업인", "투자자", "공공기관"], names
    assert [r["name"] for r in ix["rows"]] == names
    for r, (n, ask, codes) in zip(ix["rows"], _cp.PERSPECTIVES):
        assert r["name"] == n and r["ask"] == ask
        assert [d["code"] for d in r["docs"]] == list(codes), (n, codes)
    assigned = {c for _n, _a, cs in _cp.PERSPECTIVES for c in cs}
    assert assigned == {s["code"] for s in _cp.PACKAGE_SPEC}, (
        "🔴 배정 밖 코드 %r" % sorted({s["code"] for s in _cp.PACKAGE_SPEC} - assigned))
    assert ix["orphan"] == [] and ix["assigned"] == 27
    #   🔴 지금 고아가 0건이라 위 단언은 비어 있다 — **하나를 빼서** 드러나는지 본다
    cut = tuple((n, a, tuple(c for c in cs if c != "D21")) for n, a, cs in _cp.PERSPECTIVES)
    monkeypatch.setattr(_cp, "PERSPECTIVES", cut)
    holed = _cp.perspective_index()
    assert [o["code"] for o in holed["orphan"]] == ["D21"], holed["orphan"]
    assert "D21" in client.get("/for").text
    monkeypatch.undo()
    #   제목·이유는 기존 상수에서 온 것이다(화면이 짓지 않는다)
    spec_by = {s["code"]: s for s in _cp.PACKAGE_SPEC}
    for r in ix["rows"]:
        for d in r["docs"]:
            assert d["title"] == spec_by[d["code"]].get("title", "")
            assert d["why"] == _cp.FUNCTION_OF_CODE[d["code"]][1]

    # ── ② 가점 대조 — 원문 인용 · 대응 없으면 없다고 적는다 ─────────────────
    assert len(ix["score"]) == 5, len(ix["score"])
    kinds = {x["kind"] for x in ix["score"]}
    assert kinds == {"우선지원(가점)", "후순위(감점)"}, kinds
    withdocs = [x for x in ix["score"] if x["codes"]]
    assert len(withdocs) == 1, [x["text"][:20] for x in withdocs]
    assert withdocs[0]["codes"] == ["D2", "D4", "D6", "D7"], withdocs[0]
    assert "설계도서(도면, 내역서, 시방서, 구조계산서, 부하계산서 등)가 준비된 경우" in withdocs[0]["text"]
    #   ⚠️ 상수로만 비교하면 **빈 문자열로 바꿔 숨겨도** 통과한다 — 글자로 못 박는다
    assert _cp.PERSPECTIVE_NONE == "대응 산출물 없음", _cp.PERSPECTIVE_NONE
    for x in ix["score"]:
        if not x["codes"]:
            assert x["note"] == "대응 산출물 없음", x
    #   원문이 근거 문서에 실재한다
    #   ⚠️ 근거 문서는 인용을 **줄바꿈해 적는다** — 공백을 눌러 비교한다
    #      인용문이 **블록인용(`>`)**이라 줄머리 기호도 벗긴다
    doc = " ".join(w for ln in rd_("근거_외부수집_기능공백_20260924.md").splitlines()
                   for w in ln.lstrip("> ").split())
    for x in ix["score"]:
        assert " ".join(x["text"].split()) in doc, (
            "🔴 가점 항목이 근거 문서 원문에 없다: %s" % x["text"][:24])
    assert _cp.GUIDELINE_SCORE_SOURCE.split()[0] == "근거_외부수집_기능공백_20260924.md"

    # ── ③ 🔴 단정하지 않는다 ──────────────────────────────────────────────
    src = rd_("consulting_package.py")
    assert "단정하지 않는다" in src and "심사 주체의 몫" in src
    assert "입구이지 판정이 아니다" in ix["note"]
    #   ⚠️ 소스에는 *「…고 단정하지 않는다」*처럼 **부정문 속 인용**이 있다 —
    #      낱개 낱말로 소스를 재면 그 인용이 걸린다. **화면**에서 잰다.
    pub = client.get("/for/공공기관").text
    for bad in ("가점을 받는다", "가점을 준다", "가점 대상이다"):
        assert bad not in pub, f"🔴 화면이 단정한다: 「{bad}」"
    #   ⚠️ 배너(note)와 대조표 머리말 **두 곳**이다 — 한 곳만 지워도 통과하면 안 된다
    assert pub.count("심사 주체") == 2, (
        "🔴 「심사 주체」가 %d곳이다 — 배너·대조표 머리말 2곳이다" % pub.count("심사 주체"))

    # ── ④ 화면 — 전체·관점 3개 200 · 없는 관점 404 ─────────────────────────
    all_ = client.get("/for")
    assert all_.status_code == 200
    #   🔴 질문(ask)이 **화면에 그대로** 나온다 — 화면이 새로 짓지 않는다
    for _n, ask_, _c in _cp.PERSPECTIVES:
        assert ask_ in all_.text, f"🔴 「{_n}」의 질문이 화면에 없다"
    for n in names:
        r = client.get("/for/" + n)
        assert r.status_code == 200, n
        html = r.text
        assert _cd.audit(html) == {}, _cd.audit(html)
        for bad in ("추천", "권장", "최적", "우선순위"):
            assert bad not in html, f"🔴 {n} 화면에 판정 어휘 「{bad}」"
    assert client.get("/for/없는관점").status_code == 404
    #   공공기관 화면에만 가점 대조표가 붙는다
    assert "가·감점 항목" in client.get("/for/공공기관").text
    assert "가·감점 항목" not in client.get("/for/농업인").text

    # ── ⑤ 🔴 공통·근거 9종이 메뉴에 이름으로 나온다 ────────────────────────
    base = rd_("webapp_templates/_base.html")
    assert "f.fn != 'F0'" not in base, "🔴 F0 제외가 되살아났다"
    home = client.get("/").text
    f0 = next(r for r in _cp.function_index()["rows"] if r["fn"] == "F0")
    assert len(f0["docs"]) == 9, len(f0["docs"])
    assert f0["name"] in home, "🔴 공통·근거 기능 이름이 메뉴에 없다"
    for page in ("/", "/functions", "/entry"):
        c_ = client.get(page).text.count('href="/for"')
        assert c_ == 2, f"🔴 {page}의 관점별 링크가 {c_}곳이다(머리·푸터 2곳)"


def test_281cha_basic_design_entry_answers_only_what_it_can():
    """281차(N-1) — 기본설계 입구가 **낼 수 있는 것만** 내는가.

    🔴 케이스 파일이 필요 없다 — 순수 함수 셋으로만 선다.
    🔴 **고르지 않는다** — 최소사양은 참고이고 판정·추천 어휘가 0이다.
    🔴 **못 내는 것을 숨기지 않는다** — 기상 미도달·평단가 미등재·난방/경제/작기는
       화면이 이유와 함께 말한다. 빈칸으로 두면 실패.
    """
    import os as _o, io as _io
    import consulting_package as _cp
    import smartfarm_engine as _e
    import case_display as _cd
    root = _o.path.dirname(_o.path.abspath(webapp.__file__))
    rd = lambda p_: _io.open(_o.path.join(root, p_), encoding="utf-8").read()

    # ── ① 기상에 닿는 지역 / 닿지 않는 지역 — 둘 다 잰다 ──────────────────
    hit = _cp.basic_design("전북 군산시", "수박", 5000)
    assert hit["site"]["적설심_cm"] == _e.REGION_DESIGN_LOAD["군산"]["snow_cm"]
    assert hit["site"]["기상"]["지점"] == "군산"
    assert hit["site"]["기상"]["설계외기온_C"] == _e.design_outdoor_temp("군산")
    miss = _cp.basic_design("충청남도 논산시 연무읍", "딸기", 3300)
    assert miss["site"] is not None, "🔴 설계하중은 닿아야 한다(부분 매칭)"
    assert miss["site"]["기상"] is None
    why = [c["왜"] for c in miss["cannot"] if "기상값" in c["무엇"]]
    assert len(why) == 1 and "잇지 않고 주입" in why[0], why

    # ── ② 규격 — 엔진을 직접 불러 같은 수가 나오는가 ───────────────────────
    s = hit["site"]
    want = _e.select_specs(s["적설심_cm"], s["풍속_ms"], crop="수박")
    assert hit["specs"]["통과_규격수"] == len(want["candidates"])
    #   🔴 품목이 후보를 **늘리는** 자리에서도 재야 한다 — 늘지 않는 지역만 보면
    #      crop 인자를 빼도 통과한다(군산 34/38은 수박 특화형이 전부 탈락한다)
    warm = _cp.basic_design("충청남도 논산시 연무읍", "수박", 3300)
    base_n = len(_e.select_specs(28, 28)["candidates"])
    crop_n = len(_e.select_specs(28, 28, crop="수박")["candidates"])
    assert crop_n > base_n, (base_n, crop_n)
    assert warm["specs"]["통과_규격수"] == crop_n, (
        "🔴 품목 특화형이 후보에 더해지지 않았다: %s vs %s"
        % (warm["specs"]["통과_규격수"], crop_n))
    #   🔴 조립 계층은 두 수를 **빼지 않는다**(1절) — 나란히 적었는지 본다
    assert "일반형 %d · 이 작목 포함 %d" % (base_n, crop_n) in warm["specs"]["작목_주"]
    assert "빼지 않는다" in rd("consulting_package.py")
    assert hit["specs"]["전체_규격수"] == len(_e.SPEC_TABLE) == 249
    assert set(hit["specs"]["형식별_최소사양"]) == set(want["min_by_form"])
    for f, row in hit["specs"]["형식별_최소사양"].items():
        assert row["이름"] == want["min_by_form"][f].name
    #   🔴 고르지 않는다
    assert "어느 규격이 낫다고 하지 않는다" in hit["specs"]["주의"]

    # ── ③ 품목 — 특화형이 없을 때 **없다고 적는다** ────────────────────────
    none_crop = _cp.basic_design("전북 군산시", "배추", 5000)
    assert "특화형 규격이 등록돼 있지 않다" in none_crop["specs"]["작목_주"], (
        none_crop["specs"]["작목_주"])
    assert "수박" in _e.spec_crops() and "배추" not in _e.spec_crops()

    # ── ④ 개산 — None은 None으로 두고 이유를 낸다 ─────────────────────────
    est = miss["estimate"]
    assert est["면적_평"] == round(_e.m2_to_py(3300), 2)
    assert est["골조_단독_개산_원"] == round(_e.structure_only_estimate(_e.m2_to_py(3300)))
    assert any(v is None for v in est["온실_전체_개산_원"].values())
    assert "지어내지 않는다" in est["주의"]
    assert any("평단가표에 없다" in c["왜"] for c in miss["cannot"]), miss["cannot"]

    # ── ⑤ 낼 수 없는 것 — 네 가지가 늘 붙는다 ─────────────────────────────
    always = {"난방부하·연료량", "경제성(ROI·회수기간)·경제면적", "적정작기·작형", "작목 적합 판정"}
    for b in (hit, miss, _cp.basic_design()):
        got = {c["무엇"] for c in b["cannot"]}
        assert always <= got, (sorted(always - got))

    # ── ⑥ 셋이 없어도 선다(케이스 파일 없이) ──────────────────────────────
    empty = _cp.basic_design()
    assert empty["site"] is None and empty["specs"] is None and empty["estimate"] is None
    assert empty["cannot"], "🔴 빈 조회에서도 한계는 말해야 한다"

    # ── ⑦ 화면 — 200 · 잘못된 면적은 400 · 실명 0 · 판정 어휘 0 ────────────
    r = client.get("/design", params={"addr": "전북 군산시", "crop": "수박", "area_m2": "5000"})
    assert r.status_code == 200
    html = r.text
    assert _cd.audit(html) == {}, _cd.audit(html)
    assert client.get("/design").status_code == 200
    assert client.get("/design", params={"area_m2": "abc"}).status_code == 400
    assert client.get("/design", params={"area_m2": "-3"}).status_code == 400
    for bad in ("추천", "권장", "최적", "이 규격을 쓰"):
        assert bad not in html, f"🔴 기본설계 화면에 판정 어휘 「{bad}」"
    assert "낼 수 없는 것" in html and html.count('class="can"') >= 4
    for page in ("/", "/functions", "/entry"):
        c_ = client.get(page).text.count('href="/design"')
        assert c_ == 2, f"🔴 {page}의 기본설계 링크가 {c_}곳이다(머리·푸터 2곳)"

    # ── ⑧ 경계 문구를 지우지 않았다 ───────────────────────────────────────
    src = rd("consulting_package.py")
    #   ⚠️ 같은 문구가 **주석과 note 두 곳**에 있다 — 한 곳만 지워도 잡히게 수를 센다
    assert "**고르지 않는다.**" in src
    assert src.count("「구조 기본설계」까지") == 2, (
        "🔴 「구조 기본설계」까지가 %d곳이다 — 주석·note 2곳이다"
        % src.count("「구조 기본설계」까지"))
    assert "빈칸으로 두면 «없는 것»이 «0»으로 읽힌다" in src
    #   사용 안내에도 이 화면이 올라 있다(277차 가드와 겹쳐 지킨다)
    assert any(x["path"] == "/design" for x in _cp.guide_index()["screens"])



def test_282cha_facility_yield_is_reread_from_the_income_book():
    """282차(N-2) — 시설 작목 수량이 **원문에서 다시 읽어도** 같은가.

    🔴 등재값을 문서와 대조하지 않는다 — 소득자료집 PDF를 **열어서** 수량 열을 다시 뽑아
       엔진 상수와 맞춘다(279차 패턴).
    🔴 **금액을 등재하지 않았다** — 같은 표의 총수입·경영비·소득이 엔진 코드에 들어오면
       실패한다(1절: 시세성은 주입 전용).
    🔴 **시설장미는 뺐다**(원문 단위가 「본」) · **케이스 값을 바꾸지 않았다**.
    """
    import os as _o, io as _io, re as _re, importlib.util as _iu
    import pytest as _pt
    import smartfarm_engine as _e
    repo = _o.path.dirname(_o.path.abspath(webapp.__file__))
    rd = lambda p_: _io.open(_o.path.join(repo, p_), encoding="utf-8").read()

    # ── ① 원문에서 표를 다시 뽑는다(이름이 두·세 줄로 끊긴 행 포함) ──────────
    if _iu.find_spec("pdfplumber") is None:
        _pt.skip("pdfplumber 없음 — 원문 재판독 불가")
    import pdfplumber as _pdf
    path = _o.path.join(repo, "근거_농진청_소득자료집2024_전국.pdf")
    assert _o.path.exists(path), "🔴 소득자료집 원문이 리포에서 사라졌다"
    with _pdf.open(path) as pdf:
        t12 = pdf.pages[17].extract_text() or ""
        t13 = pdf.pages[18].extract_text() or ""
    assert "(기준 : 년 1기작/10a)" in t12 and "수량 총수입 경영비 소 득 소득률" in t12, (
        "🔴 원문 표머리가 바뀌었다 — 아래 재추출이 다른 표를 읽고 있다")

    #   표 한 행 = 수량 + 금액 3열 + 소득률. 이름은 앞줄, 괄호 한정자는 뒷줄에 온다
    _lead = _re.compile(r"^[가-힣]\s+")          # 「채 」「소 」 같은 세로쓰기 분류 글자
    _tail = r"([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+[\d.]+$"
    NAMED = _re.compile(r"^(\S[^\d]*?)\s+([\d,]+)(?:\(본\))?\s+" + _tail)
    BARE = _re.compile(r"^([\d,]+)(?:\(본\))?\s+" + _tail)
    num = lambda s: int(s.replace(",", ""))

    def table(txt):
        out, lines = {}, [l.strip() for l in txt.splitlines()]
        for k, l in enumerate(lines):
            m = NAMED.match(l)
            if m and "평균" not in m.group(1):
                out[_lead.sub("", m.group(1)).strip()] = tuple(num(x) for x in m.groups()[1:])
                continue
            m = BARE.match(l)
            if not m:
                continue
            name = _lead.sub("", lines[k - 1]).strip() if k else ""
            nxt = _lead.sub("", lines[k + 1]).strip() if k + 1 < len(lines) else ""
            out[name + (nxt if nxt.startswith("(") else "")] = tuple(num(x) for x in m.groups())
        return out
    src = table(t12)
    src.update(table(t13))
    assert len(src) >= 30, "🔴 원문에서 %d행밖에 못 뽑았다 — 파서가 표를 놓쳤다" % len(src)

    # ── ② 엔진 상수가 원문과 같은가(18종 전부, 한 종씩) ────────────────────
    tbl = _e.FACILITY_YIELD_KG_10A
    assert len(tbl) == 18, len(tbl)
    for name, v in tbl.items():
        assert name in src, "🔴 등재 이름 「%s」가 원문에서 안 잡힌다" % name
        assert src[name][0] == v, "🔴 %s: 등재 %s ≠ 원문 %s" % (name, v, src[name][0])
    assert sum(tbl.values()) == 107_956, sum(tbl.values())
    assert min(tbl.values()) == 1_528 and max(tbl.values()) == 14_310
    assert _e.facility_yield("시설토마토(수경)")["수량_kg_m2"] == 14.31

    # ── ③ 🔴 시설장미는 뺐다 — 원문 단위가 「본」이다 ──────────────────────
    assert not [n for n in tbl if "장미" in n], "🔴 시설장미가 들어왔다 — 단위가 ㎏이 아니다"
    assert "65,840(본)" in t13, "🔴 원문의 「본」 표기가 사라졌다 — 제외 이유의 근거다"
    assert "단위가 ㎏이 아니다" in rd("근거_시설작목수량_등재_20260929.md")
    #   노지도 아니다 — 같은 원문의 노지 작목이 하나라도 들어오면 실패
    for noji in ("사과", "배", "복숭아", "노지포도", "노지감귤", "단감", "블루베리", "자두"):
        assert noji not in tbl, "🔴 노지 작목 「%s」가 등재됐다 — 시설 계열만 결정이다" % noji

    # ── ④ 🔴 금액을 등재하지 않았다(원문 금액을 엔진 코드에서 찾는다) ───────
    esrc = rd("smartfarm_engine.py")
    #   주석은 빼고 **코드만** 본다. 숫자 구분자만 지운다(칸을 지우면 서로 다른 수가 붙는다)
    code = chr(10).join(l for l in esrc.splitlines() if not l.lstrip().startswith("#"))
    code = code.replace("_", "")
    money = sorted({m for row in src.values() for m in row[1:]})
    assert len(money) >= 60, "🔴 금액을 %d개밖에 못 모았다 — 대조가 헐겁다" % len(money)
    for m in money:
        for form in (str(m), "{:,}".format(m)):
            assert form not in code, (
                "🔴 소득자료집 금액 %s 이 엔진 코드에 들어왔다 — 시세성은 주입 전용이다" % m)
    assert "금액은 등재하지 않는다" in esrc
    #   🔴 이름으로도 막는다 — 같은 표의 다른 열이 **두 번째 상수**로 들어오면 실패
    fac = sorted(a for a in dir(_e) if a.isupper() and "FACILITY" in a)
    assert fac == ["FACILITY_YIELD_BASIS", "FACILITY_YIELD_KG_10A"], fac
    crops = set(_e.FACILITY_YIELD_KG_10A)
    for a in dir(_e):
        v = getattr(_e, a)
        if a.isupper() and isinstance(v, dict) and set(map(str, v)) & crops:
            assert a == "FACILITY_YIELD_KG_10A", (
                "🔴 시설 작목을 키로 쓰는 두 번째 표 「%s」가 엔진에 있다" % a)
    #   조회 반환도 금액을 내지 않는다
    assert set(_e.facility_yield("시설딸기")) == {
        "작목", "수량_kg_10a", "수량_kg_m2", "기준", "출처", "주의"}

    # ── ⑤ 없는 이름은 None — 비슷한 이름을 골라 주지 않는다 ────────────────
    for miss in ("딸기", "토마토", "배추", "시설장미", "", None):
        assert _e.facility_yield(miss) is None, miss
    assert _e.facility_yield_crops() == sorted(tbl) and len(_e.facility_yield_crops()) == 18

    # ── ⑥ 🔴 케이스 값을 바꾸지 않았다 ────────────────────────────────────
    import cases as _C
    c2 = next(c for c in _C.load_cases() if c["case_id"] == "wonchaewon")
    assert c2["input"]["base_yield_kg_m2"] == 38.5, "🔴 케이스 수량이 바뀌었다 — 회귀가 움직인다"
    doc = rd("근거_시설작목수량_등재_20260929.md")
    for phrase in ("케이스 값을 바꾸지 않았다", "2.7배 차이다", "판정하지 않는다"):
        assert phrase in doc, phrase

    # ── ⑦ 기본설계 화면이 **고르지 않는다** ───────────────────────────────
    import consulting_package as _cp
    bd = _cp.basic_design("전북 군산시", "딸기", 3300)
    assert bd["yield_ref"]["찾은_이름"] == ["시설딸기", "시설딸기(수경)"], bd["yield_ref"]
    assert "고르지 않는다" in bd["yield_ref"]["주의"]
    assert _cp.basic_design("전북 군산시", "배추", 3300)["yield_ref"]["찾은_이름"] == []
    assert "yield_ref" not in _cp.basic_design()
    r = client.get("/design", params={"addr": "전북 군산시", "crop": "딸기", "area_m2": "3300"})
    assert r.status_code == 200 and "2.893" in r.text and "3.292" in r.text
    #   화면이 둘 중 하나를 고르지 않는다
    for bad in ("추천", "권장", "최적"):
        assert bad not in r.text, "🔴 수량 참고에 판정 어휘 「%s」" % bad
    #   경제성을 못 내는 이유가 **바뀌었다** — 수량이 아니라 단가다
    eco = next(c for c in bd["cannot"] if "경제성" in c["무엇"])
    assert "단가가 시세성" in eco["왜"] and "수량은 282차에 등재됐다" in eco["왜"], eco

    # ── ⑧ 레지스트리에 status와 함께 올라 있다 ────────────────────────────
    import json as _j
    ent = _j.loads(rd("엔진데이터_레지스트리.json"))["constants"]
    for k in ("FACILITY_YIELD_KG_10A", "FACILITY_YIELD_BASIS"):
        assert k in ent, "🔴 %s 미등재" % k
        assert ent[k]["source_refs"], k
        assert any(r_["file"] == "근거_시설작목수량_등재_20260929.md"
                   for r_ in ent[k]["source_refs"]), k
    assert ent["FACILITY_YIELD_KG_10A"]["status"] == "공공기준"
    assert any(r_["file"] == "근거_농진청_소득자료집2024_전국.pdf" and r_["match"] == "exact"
               for r_ in ent["FACILITY_YIELD_KG_10A"]["source_refs"]), "🔴 원문 exact 참조가 없다"
    assert ent["FACILITY_YIELD_BASIS"]["status"] == "결정"
    #   레지스트리 사본과 엔진이 같은가 — 한쪽만 고치면 잡힌다
    assert ent["FACILITY_YIELD_KG_10A"]["value"] == tbl, "🔴 레지스트리 사본이 엔진과 다르다"
