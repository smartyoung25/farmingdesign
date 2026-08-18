"""웹앱 트랙 1~2단계 — 콘솔 + 기입 워크플로 (2026-08-18, 32~33차)

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
import smartfarm_engine as e
import build_site as bs

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


# ── 2단계(33차): 기입 워크플로 — financing·시나리오 웹폼 ─────────────────
# 원칙: 검증·계산은 전부 엔진 계층(loan_amortization·scenario_rows)에 위임하고,
# 앱은 폼 파싱과 저장만 한다. 근거(note) 없는 저장은 거부(시세성·판단성 주입 원칙).
# 저장 대상은 케이스 JSON(git 추적) — 커밋은 사람이 한다(과제 단위 커밋 절차 유지).

def _full_case_or_404(case_id: str) -> dict:
    for c in C.load_cases():
        if c["case_id"] == case_id:
            if c.get("partial"):
                raise HTTPException(400, detail="부분 케이스에는 기입할 수 없다(4축 미산출)")
            return c
    raise HTTPException(404, detail=f"케이스 {case_id} 없음")


def _save_case(case: dict) -> None:
    """케이스 JSON 원자적 저장 — 기존 EOL 보존, ensure_ascii=False·indent 2."""
    path = Path(C.CASES_DIR) / f"{case['case_id']}.json"
    old = path.read_bytes().decode("utf-8") if path.exists() else "\n"
    eol = "\r\n" if "\r\n" in old else "\n"
    text = json.dumps(case, ensure_ascii=False, indent=2)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_bytes((text.replace("\n", eol) + eol).encode("utf-8"))
    tmp.replace(path)


def _form_float(form, key, *, required=False, as_int=False):
    raw = (form.get(key) or "").strip().replace(",", "")
    if not raw:
        if required:
            raise HTTPException(400, detail=f"{key} 값이 비어 있다")
        return None
    try:
        if as_int:
            return int(raw)
        v = float(raw)
        return int(v) if v.is_integer() else v  # 2936.0 → 2936 (저장 JSON 오염 방지)
    except ValueError:
        raise HTTPException(400, detail=f"{key}: 숫자가 아니다 — {raw!r}")


@app.get("/entry")
def entry_hub(request: Request):
    cs = [c for c in C.load_cases() if not c.get("partial")]
    rows = [{
        "case_id": c["case_id"], "title": c["title"],
        "fin": bool(c.get("financing")),
        "n_sets": len((c.get("scenarios") or {}).get("sets", [])),
    } for c in cs]
    return templates.TemplateResponse(request, "entry_hub.html", {"rows": rows})


@app.get("/entry/financing/{case_id}")
def financing_form(request: Request, case_id: str):
    case = _full_case_or_404(case_id)
    return templates.TemplateResponse(request, "entry_financing.html", {
        "case": case, "fin": case.get("financing") or {}, "preview": None, "form_vals": None,
    })


def _parse_financing(form) -> dict:
    fin = {
        "loan_principal_won": _form_float(form, "loan_principal_won", required=True, as_int=True),
        "annual_rate_pct": _form_float(form, "annual_rate_pct", required=True),
        "term_years": _form_float(form, "term_years", required=True, as_int=True),
        "grace_years": _form_float(form, "grace_years", as_int=True) or 0,
        "method": (form.get("method") or "").strip(),
        "note": (form.get("note") or "").strip(),
    }
    if fin["method"] not in ("원리금균등", "원금균등"):
        raise HTTPException(400, detail="상환방식은 원리금균등/원금균등 중 하나")
    return fin


def _amortize_or_400(fin: dict):
    try:
        return e.loan_amortization(fin["loan_principal_won"], fin["annual_rate_pct"],
                                   fin["term_years"], fin["grace_years"], fin["method"])
    except ValueError as ex:  # 엔진 검증 메시지를 그대로 노출(제2 검증기 금지)
        raise HTTPException(400, detail=str(ex))


@app.post("/entry/financing/{case_id}/preview")
async def financing_preview(request: Request, case_id: str):
    case = _full_case_or_404(case_id)
    form = await request.form()
    fin = _parse_financing(form)
    am = _amortize_or_400(fin)
    return templates.TemplateResponse(request, "entry_financing.html", {
        "case": case, "fin": fin, "preview": am, "form_vals": fin,
    })


@app.post("/entry/financing/{case_id}/save")
async def financing_save(request: Request, case_id: str):
    case = _full_case_or_404(case_id)
    form = await request.form()
    fin = _parse_financing(form)
    if not fin["note"]:
        raise HTTPException(400, detail="근거(note: 약정서/공고 출처·기준일)가 비어 있다 — 출처 없는 실조건 저장 금지")
    _amortize_or_400(fin)  # 엔진 검증 통과분만 저장
    case["financing"] = fin
    _save_case(case)
    return RedirectResponse(f"/entry/financing/{case_id}?saved=1", status_code=303)


@app.get("/entry/scenario/{case_id}")
def scenario_form(request: Request, case_id: str):
    case = _full_case_or_404(case_id)
    return templates.TemplateResponse(request, "entry_scenario.html", {
        "case": case, "sets": (case.get("scenarios") or {}).get("sets", []),
        "fields": sorted(bs.SCENARIO_ALLOWED_FIELDS), "preview": None, "form_vals": None,
        "error": None,
    })


def _parse_scenario_set(form) -> dict:
    assumptions = {}
    for f in bs.SCENARIO_ALLOWED_FIELDS:
        v = _form_float(form, f)
        if v is not None:
            assumptions[f] = v
    return {"name": (form.get("name") or "").strip() or "이름없음",
            "assumptions": assumptions,
            "note": (form.get("note") or "").strip()}


def _scenario_rows_or_400(case: dict, new_set: dict) -> list:
    trial = dict(case)
    sc = dict(case.get("scenarios") or {})
    sc["sets"] = list(sc.get("sets", [])) + [new_set]
    sc.setdefault("note", "웹폼 기입(33차) — 가정값은 컨설턴트 판단, 근거는 세트별 note")
    trial["scenarios"] = sc
    try:  # 화이트리스트·근거 필수 검증은 scenario_rows가 한다(단일 검증 경로)
        rows = bs.scenario_rows(trial, C.case_to_input(case))
    except ValueError as ex:
        raise HTTPException(400, detail=str(ex))
    return rows, trial


@app.post("/entry/scenario/{case_id}/preview")
async def scenario_preview(request: Request, case_id: str):
    case = _full_case_or_404(case_id)
    form = await request.form()
    new_set = _parse_scenario_set(form)
    rows, _ = _scenario_rows_or_400(case, new_set)
    return templates.TemplateResponse(request, "entry_scenario.html", {
        "case": case, "sets": (case.get("scenarios") or {}).get("sets", []),
        "fields": sorted(bs.SCENARIO_ALLOWED_FIELDS), "preview": rows, "form_vals": new_set,
        "error": None,
    })


@app.post("/entry/scenario/{case_id}/save")
async def scenario_save(request: Request, case_id: str):
    case = _full_case_or_404(case_id)
    form = await request.form()
    new_set = _parse_scenario_set(form)
    if not new_set["assumptions"]:
        raise HTTPException(400, detail="변경 필드가 하나도 없다 — 화이트리스트 필드 중 최소 1개 기입")
    _, trial = _scenario_rows_or_400(case, new_set)  # 검증 통과분만 저장
    _save_case(trial)
    return RedirectResponse(f"/entry/scenario/{case_id}?saved=1", status_code=303)


# ── 4단계(34차): 견적비교 전사 입력 UI ──────────────────────────────────
# 기준 데이터: 견적비교_논산딸기3사.json(원단위 대사 완료 실측 전사) — 편집기는 이
# 스키마를 그대로 읽고 쓴다. 전사 무결성(3중 대사)은 build_site.quotes_vendor_3way_check,
# 정합 신호는 엔진 compare_quotes — 앱은 파싱·표시·저장만 한다.

QUOTES_DIR = ROOT  # 견적비교_*.json 위치(테스트에서 임시 디렉터리로 대체 가능)
_QUOTES_RE = re.compile(r"^견적비교_[\w가-힣.\-]+\.json$")
VALID_CATEGORY_KEYS = None  # 지연 초기화(엔진 상수에서)


def _category_keys() -> list:
    global VALID_CATEGORY_KEYS
    if VALID_CATEGORY_KEYS is None:
        VALID_CATEGORY_KEYS = [k for k, _kor, _d in e.CAPEX_MAJOR_CATEGORIES]
    return VALID_CATEGORY_KEYS


def _quotes_files() -> list:
    return sorted(p.name for p in Path(QUOTES_DIR).glob("견적비교_*.json"))


def _load_quotes_json(name: str) -> dict:
    if not _QUOTES_RE.match(name):
        raise HTTPException(404)
    p = Path(QUOTES_DIR) / name
    if not p.is_file():
        raise HTTPException(404, detail=f"{name} 없음")
    return json.loads(p.read_text(encoding="utf-8"))


def _parse_quote_rows(text: str) -> list:
    """textarea 전사 파싱 — 한 줄 = '공종 원문 | 금액 | 카테고리키(근거)'. 금액은
    콤마 허용·음수 허용(작업부산물 공제). 파싱만 하고 합산·판정은 하지 않는다."""
    rows = []
    for i, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3:
            raise HTTPException(400, detail=f"{i}행: '공종 | 금액 | 매핑' 3열이 아니다 — {line!r}")
        name, amount_s, mapping = parts
        try:
            amount = int(amount_s.replace(",", ""))
        except ValueError:
            raise HTTPException(400, detail=f"{i}행 금액이 정수가 아니다(원단위 전사) — {amount_s!r}")
        key = bs.quotes_mapping_key(mapping)
        if key not in _category_keys():
            raise HTTPException(400, detail=f"{i}행 매핑 키 {key!r} 미등록 — 허용: {', '.join(_category_keys())}")
        if not name:
            raise HTTPException(400, detail=f"{i}행 공종 원문이 비어 있다")
        rows.append([name, amount, mapping])
    return rows


def _parse_quotes_form(form) -> dict:
    """폼 → 견적비교 JSON 스키마 dict. 카테고리 소계는 raw_rows에서 집계(전사 부기),
    정합 검증은 미리보기/저장 단계에서 3중 대사+엔진이 수행."""
    cid = (form.get("comparison_id") or "").strip()
    if not re.match(r"^[\w가-힣\-]+$", cid or ""):
        raise HTTPException(400, detail="comparison_id는 한글·영숫자·언더스코어·하이픈만")
    rfq = {
        "region": (form.get("region") or "").strip(),
        "region_snow_cm": _form_float(form, "region_snow_cm", required=True),
        "region_wind_ms": _form_float(form, "region_wind_ms", required=True),
        "area_m2": _form_float(form, "area_m2", required=True),
        "cover": (form.get("cover") or "").strip(),
        "form": (form.get("form") or "").strip(),
        "t_target": _form_float(form, "t_target", required=True),
        "t_min": _form_float(form, "t_min", required=True),
        "crop": (form.get("crop") or "").strip() or None,
        "note": (form.get("rfq_note") or "").strip(),
    }
    curtain = (form.get("curtain") or "").strip()
    fr = _form_float(form, "fr")
    if curtain:
        rfq["curtain"] = curtain
    if fr is not None:
        rfq["fr"] = fr
    req_cats = [c.strip() for c in (form.get("required_categories") or "").split(",") if c.strip()]
    if req_cats:
        bad = [c for c in req_cats if c not in _category_keys()]
        if bad:
            raise HTTPException(400, detail=f"required_categories 미등록 키: {bad}")
        rfq["required_categories"] = req_cats
    vendors = []
    for i in range(int(form.get("n_vendors") or 0)):
        name = (form.get(f"vendor{i}_name") or "").strip()
        rows_text = form.get(f"vendor{i}_rows") or ""
        if not name and not rows_text.strip():
            continue  # 빈 블록
        if not name:
            raise HTTPException(400, detail=f"업체 블록 {i+1}: 업체명이 비어 있다")
        raw_rows = _parse_quote_rows(rows_text)
        if not raw_rows:
            raise HTTPException(400, detail=f"{name}: 전사 행이 없다")
        v = {
            "vendor_name": name,
            "source_file": (form.get(f"vendor{i}_source_file") or "").strip(),
            "source_sheet": (form.get(f"vendor{i}_source_sheet") or "").strip(),
            "area_m2": _form_float(form, f"vendor{i}_area_m2"),
            "area_note": (form.get(f"vendor{i}_area_note") or "").strip(),
            "direct_cost_total": _form_float(form, f"vendor{i}_direct_cost_total", required=True, as_int=True),
            "total_with_overhead": _form_float(form, f"vendor{i}_total_with_overhead", required=True, as_int=True),
            "total_note": (form.get(f"vendor{i}_total_note") or "").strip(),
            "categories": bs.quotes_derive_categories(raw_rows),
            "raw_rows": raw_rows,
        }
        if not v["source_file"]:
            raise HTTPException(400, detail=f"{name}: 출처 파일(source_file)이 비어 있다 — 원문 없는 전사 금지")
        vendors.append(v)
    if not vendors:
        raise HTTPException(400, detail="업체가 하나도 없다")
    return {
        "comparison_id": cid,
        "title": (form.get("title") or "").strip() or cid,
        "created": (form.get("created") or "").strip(),
        "decision_note": (form.get("decision_note") or "").strip(),
        "provenance": (form.get("provenance") or "").strip(),
        "rfq_input": rfq,
        "vendor_quotes": vendors,
    }


def _quotes_engine_or_400(data: dict):
    try:
        ri = data["rfq_input"]
        rfq = e.generate_rfq_package(
            region_snow_cm=ri["region_snow_cm"], region_wind_ms=ri["region_wind_ms"],
            area_m2=ri["area_m2"], cover=e.Cover(ri["cover"]), form=ri["form"],
            t_target=ri["t_target"], t_min=ri["t_min"],
            fr=ri.get("fr"), curtain=ri.get("curtain"), crop=ri.get("crop"),
            required_categories=ri.get("required_categories"))
        vqs = [e.VendorQuote(v["vendor_name"], v["categories"], v["direct_cost_total"],
                             v["total_with_overhead"], v.get("area_m2"), v.get("spec_name"))
               for v in data["vendor_quotes"]]
        return rfq, e.compare_quotes(rfq, vqs)
    except (ValueError, KeyError) as ex:  # 엔진 검증 메시지 그대로 노출
        raise HTTPException(400, detail=f"엔진 검증 실패: {ex}")


def _quotes_validation(data: dict):
    """3중 대사 먼저 — 통과한 경우에만 엔진 신호 호출(대사 실패 데이터는 엔진이
    ValueError로 거부하므로, 전사자에게는 대사 결과부터 보여주는 것이 올바른 순서)."""
    checks = {v["vendor_name"]: bs.quotes_vendor_3way_check(v) for v in data["vendor_quotes"]}
    all_ok = all(c["ok"] for cs in checks.values() for c in cs)
    rfq = cmp = None
    if all_ok:
        rfq, cmp = _quotes_engine_or_400(data)
    return checks, all_ok, rfq, cmp


@app.get("/entry/quotes")
def quotes_hub(request: Request):
    items = []
    for name in _quotes_files():
        d = _load_quotes_json(name)
        ok = all(c["ok"] for v in d["vendor_quotes"] for c in bs.quotes_vendor_3way_check(v))
        items.append({"file": name, "id": d["comparison_id"], "title": d["title"],
                      "n_vendors": len(d["vendor_quotes"]), "ok": ok})
    return templates.TemplateResponse(request, "entry_quotes_hub.html", {"items": items})


def _vendor_to_form(v: dict) -> dict:
    out = dict(v)
    out["rows_text"] = "\n".join(f"{r[0]} | {r[1]} | {r[2]}" for r in v["raw_rows"])
    return out


@app.get("/entry/quotes/edit")
def quotes_edit(request: Request, src: str = "", vendors: int = 0):
    data, vend_forms = None, []
    if src:
        data = _load_quotes_json(src)
        vend_forms = [_vendor_to_form(v) for v in data["vendor_quotes"]]
    n_blocks = max(len(vend_forms) + (1 if not src else 0), vendors, 1)
    return templates.TemplateResponse(request, "entry_quotes_edit.html", {
        "data": data, "vendors": vend_forms, "n_blocks": n_blocks, "src": src,
        "category_keys": _category_keys(), "result": None,
    })


@app.post("/entry/quotes/preview")
async def quotes_preview(request: Request):
    form = await request.form()
    data = _parse_quotes_form(form)
    checks, all_ok, _rfq, cmp = _quotes_validation(data)
    vend_forms = [_vendor_to_form(v) for v in data["vendor_quotes"]]
    return templates.TemplateResponse(request, "entry_quotes_edit.html", {
        "data": data, "vendors": vend_forms, "n_blocks": len(vend_forms) + 1,
        "src": form.get("src") or "", "category_keys": _category_keys(),
        "result": {"checks": checks, "cmp": cmp, "all_ok": all_ok},
    })


@app.post("/entry/quotes/save")
async def quotes_save(request: Request):
    form = await request.form()
    data = _parse_quotes_form(form)
    if not data["provenance"]:
        raise HTTPException(400, detail="provenance(전사 출처·방법)가 비어 있다 — 근거 없는 전사 저장 금지")
    checks, all_ok, _rfq, _cmp = _quotes_validation(data)
    if not all_ok:
        bad = [(vn, c) for vn, cs in checks.items() for c in cs if not c["ok"]]
        raise HTTPException(400, detail="3중 대사 불일치 — 저장 거부: " +
                            "; ".join(f"{vn}: {c['name']} ({c['detail']})" for vn, c in bad))
    target = Path(QUOTES_DIR) / f"견적비교_{data['comparison_id']}.json"
    if target.exists() and form.get("overwrite") != "1":
        raise HTTPException(409, detail=f"{target.name} 이미 존재 — 덮어쓰기 확인란 체크 필요")
    old = target.read_bytes().decode("utf-8") if target.exists() else "\n"
    eol = "\r\n" if "\r\n" in old else "\n"
    text = json.dumps(data, ensure_ascii=False, indent=2)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_bytes((text.replace("\n", eol) + eol).encode("utf-8"))
    tmp.replace(target)
    return RedirectResponse(f"/entry/quotes?saved={data['comparison_id']}", status_code=303)
