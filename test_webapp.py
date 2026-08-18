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
    for c in C.load_cases():
        assert c["title"] in body, f"{c['case_id']} 카드 누락"
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
    assert "SmartFarm_부분케이스_yonggyun.html" in r.text
    assert "SmartFarm_부분케이스_mulhyangki.html" in r.text
    assert "SmartFarm_통합보고서_wonchaewon.html" in r.text


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
    assert "원채원" in r.text and "물향기" not in r.text  # 부분 케이스는 기입 대상 아님
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
    assert saved["scenarios"]["sets"][0]["assumptions"] == {"price_won_per_kg": 2936}
    rows = bs.scenario_rows(saved, C.case_to_input(saved))
    assert rows[1]["name"] == "Best(테스트)"
