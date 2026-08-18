"""웹앱 트랙 1단계 — 읽기 전용 콘솔 (2026-08-18, 32차)

화면 설계 근거: Figma "스마트팜 컨설팅 웹앱 UI"(2026-08-18) — 콘솔 홈(케이스 목록)
+ 기존 build_site 산출물 서빙. UI 원칙 4가지를 코드 수준에서 강제한다:
  1. 근거 칩 — 케이스 provenance status를 그대로 칩으로 노출(가공 없음)
  2. 3단 시각 언어 — 판정·추천 표기 금지(케이스 나열만, 정렬도 case_id 순)
  3. 시세성 주입 — 이 단계에는 입력이 없다(읽기 전용)
  4. 프론트/앱 계산 0 — 모든 수치는 엔진(render_report.compute) 호출 결과의
     표시 전용. 이 파일 안에서 새 산술을 하지 않는다(표시 포맷팅만 허용).
보고서 페이지는 Jinja로 재구현하지 않고 build_site 산출물(SmartFarm_*.html)을
그대로 서빙한다 — 제2 렌더러를 만들면 경로 C(정식 산출 경로)와 갈라진다.

실행:  python -m uvicorn webapp:app --port 8600
테스트: pytest test_webapp.py -q
"""
import glob
import json
import re
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request

import cases as C
import render_report as rr

ROOT = Path(__file__).parent
app = FastAPI(title="스마트팜 컨설팅 콘솔", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(ROOT / "webapp_templates"))

# 근거 칩 status → 색 클래스 (레지스트리 status_legend 계열과 1:1, 미지 status는 회색)
CHIP_CLASS = [("실측", "chip-measured"), ("법정", "chip-statutory"), ("공공기준", "chip-statutory"),
              ("참고", "chip-ref"), ("부분실측", "chip-est"), ("추정", "chip-est"),
              ("확인요망", "chip-warn"), ("미검증", "chip-warn")]


def chip_class(status: str) -> str:
    for prefix, cls in CHIP_CLASS:
        if status.startswith(prefix):
            return cls
    return "chip-ref"


def _case_card(case: dict) -> dict:
    """케이스 1건 → 카드 표시 데이터. 수치는 엔진 호출 결과만(파생 산술 금지)."""
    cid = case["case_id"]
    if case.get("partial"):
        inp = case.get("input", {})
        return {
            "case_id": cid, "title": case["title"],
            "meta": f"{inp.get('crop', '—')} · {inp.get('area_m2', '—')}㎡ · {case.get('partial')}",
            "kpi": f"총공사비 {inp.get('total_construction_cost', 0):,}원 · 4축 미산출(부분 케이스)",
            "chip": "참고", "chip_class": "chip-ref",
            "href": f"/pages/SmartFarm_부분케이스_{cid}.html",
        }
    inp = C.case_to_input(case)
    ec = rr.compute(inp)["economics"]
    prov = case.get("provenance", {})
    status = (prov.get("total_construction_cost") or {}).get("status", "추정")
    payback = f"{ec['payback']:.1f}년" if ec["payback"] else "N/A"
    return {
        "case_id": cid, "title": case["title"],
        "meta": f"{case['input'].get('crop')} · {case['input'].get('region')} · {case['input'].get('area_m2'):,}㎡",
        "kpi": f"ROI {ec['roi']*100:.1f}% · Payback {payback}",
        "chip": status, "chip_class": chip_class(status),
        "href": f"/pages/SmartFarm_통합보고서_{cid}.html",
    }


def _data_wait(cases: list) -> list:
    """데이터 대기 알림 — 케이스 데이터에서 도출(하드코딩 금지, 상태가 풀리면 자동 소멸)."""
    items = []
    if all(not c.get("financing") for c in cases if not c.get("partial")):
        items.append("① 대출 약정서 — 기입양식 준비됨(financing_실조건_기입양식.md)")
    items.append("③ 리모델링 진단값 — 수집 명세서 준비됨(리모델링_진단값_수집명세서.md)")
    n_sc = sum(1 for c in cases if c.get("scenarios"))
    if n_sc < sum(1 for c in cases if not c.get("partial")):
        items.append(f"④ 시나리오 가정 선택 — 근거팩 확보됨, 기입 {n_sc}건")
    return items


@app.get("/")
def console_home(request: Request):
    cs = C.load_cases()
    full = [_case_card(c) for c in cs if not c.get("partial")]
    partial = [_case_card(c) for c in cs if c.get("partial")]
    reg = json.loads((ROOT / "엔진데이터_레지스트리.json").read_text(encoding="utf-8"))
    quotes = sorted(Path(p).name for p in glob.glob(str(ROOT / "SmartFarm_견적비교_*.html")))
    return templates.TemplateResponse(request, "console_home.html", {
        "full_cards": full, "partial_cards": partial,
        "waits": _data_wait(cs),
        "n_constants": len(reg["constants"]),
        "quote_pages": quotes,
    })


_PAGE_RE = re.compile(r"^(SmartFarm_[\w가-힣.\-]+|index)\.html$")


@app.get("/pages/{name}")
def serve_page(name: str):
    """build_site 산출물 서빙 — 화이트리스트 패턴만(경로 탈출 차단)."""
    if not _PAGE_RE.match(name):
        raise HTTPException(404)
    f = ROOT / name
    if not f.is_file():
        raise HTTPException(404, detail=f"{name} 없음 — 재생성(POST /rebuild) 필요할 수 있음")
    return FileResponse(f, media_type="text/html")


@app.post("/rebuild")
def rebuild():
    """엔진 재계산 = build_site 재실행(경로 C 그대로). stderr를 삼키지 않는다(16차 교훈)."""
    r = subprocess.run([sys.executable, str(ROOT / "build_site.py")],
                       capture_output=True, text=True, cwd=str(ROOT), timeout=300)
    if r.returncode != 0:
        raise HTTPException(500, detail=(r.stderr or r.stdout)[-2000:])
    return RedirectResponse("/", status_code=303)


@app.get("/health")
def health():
    cs = C.load_cases()
    return {"cases": len(cs), "partial": sum(1 for c in cs if c.get("partial")),
            "engine": "smartfarm_engine(단일 계산 출처)", "note": "수치 검증은 pytest가 담당"}
