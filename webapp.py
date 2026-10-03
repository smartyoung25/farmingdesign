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
import case_display as cdsp
import glob
import json
import re
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.templating import Jinja2Templates
from fastapi import Request
from markupsafe import Markup
from jinja2 import pass_context

import cases as C
import render_report as rr
import smartfarm_engine as e
import build_site as bs
import consulting_package as cpkg
import audit_work_orders as awo

ROOT = Path(__file__).parent
app = FastAPI(title="스마트팜 컨설팅 콘솔", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(ROOT / "webapp_templates"))


# -------------------------------------------------------------
# 297차(WO-020) — 인라인 마크다운을 **출력 지점에서** 렌더한다.
#   148차가 `build_site.md()`로 정적 사이트의 리터럴 마크다운을 3,833 -> 2로 닫았으나
#   그 작업은 콘솔을 범위에 두지 않았다(근거 문서에 「webapp」·「콘솔」 0회).
#   그래서 콘솔 화면에 별표 552 · 백틱 196이 **글자 그대로** 나가고 있었다.
#
#   템플릿 출력 지점이 **605곳**이라 손으로 필터를 붙이면 하나만 빠뜨려도 조용히
#   남는다. Jinja의 `finalize`는 **모든 출력 지점**에 걸리므로 지점을 고르지 않는다.
#   두 벌을 만들지 않는다 — 정적 사이트와 **같은 `md()`**를 쓴다(1절).
#
#   지켜야 할 것 셋:
#     1. 문자열만 건드린다 — `None`을 빈칸으로 바꾸면 화면이 달라진다
#     2. `__html__`을 가진 값(안전 표시된 결과)은 건너뛴다 — 다시 변환하면 태그가 깨진다
#     3. `md()`가 이미 escape했으므로 `Markup`으로 감싸 자동 이스케이프를 끈다
# -------------------------------------------------------------
def _form_templates() -> frozenset:
    """폼 값을 **되돌려 주는** 템플릿 — 디렉터리에서 도출한다(목록을 손으로 적지 않는다).

    298차 — 297차의 훅이 모든 출력 지점에 걸려 입력칸의 값까지 바꿨다. 전사 근거를
    담은 칸에서는 그 글자가 **그대로 저장된다** — 저장 한 번으로 근거 필드가 오염되고
    md()는 멱등이 아니라 되돌릴 수 없다(1절 「근거 없는 값 금지」).
    목록을 상수로 적으면 새 기입 화면이 조용히 훅을 타므로 **파일에서 도출**한다.
    """
    out = set()
    for q in sorted((ROOT / "webapp_templates").glob("entry_*.html")):
        t = q.read_text(encoding="utf-8")
        if "<form" in t and ('value="{{' in t or "<textarea" in t):
            out.add(q.name)
    return frozenset(out)


FORM_TEMPLATES = _form_templates()


@pass_context
def _render_inline(ctx, value):
    if hasattr(value, "__html__"):
        return value
    if isinstance(value, str) and ctx.name not in FORM_TEMPLATES:
        return Markup(bs.md(value))
    return value


templates.env.finalize = _render_inline


def _nav_functions() -> list:
    """사이드바 기능 메뉴 — 이름·순서는 `consulting_package`가 쥔다(211차)."""
    return [{"fn": f, "name": n, "desc": d}
            for f, n, d in cpkg.BENCHMARK_FUNCTIONS]


templates.env.globals["nav_functions"] = _nav_functions

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
            "case_id": cid, "title": cdsp.alias(case)["title"],
            "meta": f"{inp.get('crop', '—')} · {inp.get('area_m2', '—')}㎡ · {case.get('partial')}",
            "kpi": f"총공사비 {inp.get('total_construction_cost', 0):,}원 · 4축 미산출(부분 케이스)",
            "chip": "참고", "chip_class": "chip-ref",
            "href": f"/case/{cdsp.code(case)}",
        }
    inp = C.case_to_input(case)
    ec = rr.compute(inp)["economics"]
    prov = case.get("provenance", {})
    status = (prov.get("total_construction_cost") or {}).get("status", "추정")
    payback = f"{ec['payback']:.1f}년" if ec["payback"] else "N/A"
    return {
        "case_id": cid, "title": cdsp.alias(case)["title"],
        "meta": f"{case['input'].get('crop')} · {case['input'].get('region')} · {case['input'].get('area_m2'):,}㎡",
        "kpi": f"ROI {ec['roi']*100:.1f}% · Payback {payback}",
        "chip": status, "chip_class": chip_class(status),
        "href": f"/case/{cdsp.code(case)}",
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
    # 245차 — Agritecture 벤치마킹 홈: 숫자 띠 · 일하는 방식 · 서비스 · 케이스 · 근거 현황.
    #   🔴 수치는 전부 **이미 있는 데이터를 세거나 옮긴 것**이다 — 새 수치를 짓지 않는다.
    #   📌256차(레드팀 30회차 B2): 히어로 문구는 245차에 **새로 쓴 소개문**이다(「새 문구를 짓지 않는다」는
    #   틀린 서술이었다). 「모든 수치에 근거가 붙는」은 추정·확인요망이 있는데 과장이라 「근거 상태가 붙는」으로
    #   고쳤다 — 문구 선택은 사용자가 바꿀 수 있다.
    #   📌259차 — ★사용자 결정(2026-09-28): 히어로 제목은 「스마트농업을 디자인하다」. 아래 설명문(엔진이 계산하고
    #   출처 상태를 함께 낸다)은 그대로다.
    #   (Agritecture의 고객 추천사 자리는 지어낼 수 없어 **근거 현황**으로 바꿨다).
    from collections import Counter as _Counter
    ix = cpkg.function_index()
    status = _Counter(v.get("status", "") for v in reg["constants"].values())
    return templates.TemplateResponse(request, "console_home.html", {
        "full_cards": full, "partial_cards": partial,
        "waits": _data_wait(cs),
        "n_constants": len(reg["constants"]),
        "quote_pages": quotes,
        "stats": [("케이스", len(cs), f"4축 {len(full)} · 부분 {len(partial)}"),
                  ("산출물", ix["total"], "D1~D27 — 케이스 1건이 받는 산출물 종류"),
                  ("근거 상수", len(reg["constants"]), "레지스트리에 출처·status가 등재된 엔진 상수"),
                  ("출처 연결", sum(len(v.get("source_refs") or []) for v in reg["constants"].values()),
                   "상수 → 원문 파일 연결 수(source_refs) — 한 파일이 여러 상수에 걸리면 여러 번 센다")],
        "flow": [{"key": k, "name": n, "stages": list(st), "desc": d, "bench": b}
                 for k, n, st, d, b in cpkg.PLATFORM_STAGES],
        "services": ix["rows"],
        "status_rows": [(k, status[k], chip_class(k)) for k in sorted(status, key=lambda x: -status[x])],
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


# ── 248차(WO-003): 작업지시서(WO) 화면 — 읽기 전용 ─────────────────────
#   원본은 `docs/work-orders/*.md` 파일이다. 이 화면은 `audit_work_orders`가 읽은
#   결과를 **보여 주기만** 한다 — 확인 수/전체도 검사기 반환값이고, 화면에서 쓰지 않는다.
#   🔴 경로 값으로 파일을 열지 않는다 — 검사기가 폴더에서 찾은 번호만 받는다(경로 조작 차단).

_WO_ID_RE = re.compile(r"^WO-\d{3}(?:-fix\d+)?$")


@app.get("/workorders")
def work_orders(request: Request):
    r = awo.audit()
    idx = {row[0]: row for row in r["index"]}
    rows = []
    for f in r["files"]:
        p, ix = f["parsed"], idx.get(f["id"])
        #   251차 — 개인 이름은 표시 코드로(R9가 파일을 막지만, 화면도 한 번 더 거른다)
        rows.append({"id": f["id"], "title": cdsp.scrub(p["title"]), "type": p["type"],
                     "round": ix[3] if ix else "—", "prereq": p["prereq"],
                     "state": ix[5] if ix else "색인 없음",
                     "checked": p["n_checked"], "total": p["n_criteria"],
                     "applicable": p["n_applicable"], "na": p["n_na"],
                     "problems": [cdsp.scrub(x) for x in f["problems"]]})
    return templates.TemplateResponse(request, "work_orders.html", {
        "rows": rows, "audit_pass": r["pass"], "problems": [cdsp.scrub(x) for x in r["problems"]]})


@app.get("/workorders/{wo_id}")
def work_order_detail(request: Request, wo_id: str):
    if not _WO_ID_RE.match(wo_id):
        raise HTTPException(404, detail=f"{wo_id}는 WO 번호 형식이 아니다")
    r = awo.audit()
    f = next((x for x in r["files"] if x["id"] == wo_id), None)
    if f is None:
        raise HTTPException(404, detail=f"{wo_id} 없음 — docs/work-orders/에 그 번호의 파일이 없다")
    f = {**f, "problems": [cdsp.scrub(x) for x in f["problems"]]}
    p = dict(f["parsed"])
    p["title"] = cdsp.scrub(p["title"])
    p["criteria"] = [{**c, "text": cdsp.scrub(c["text"])} for c in p["criteria"]]
    return templates.TemplateResponse(request, "work_order_detail.html", {
        "f": f, "p": p,
        "sections": [(n, p["sections"][n]["title"], cdsp.scrub(p["sections"][n]["body"])) for n in p["order"]]})


@app.get("/health")
def health():
    cs = C.load_cases()
    return {"cases": len(cs), "partial": sum(1 for c in cs if c.get("partial")),
            "engine": "smartfarm_engine(단일 계산 출처)", "note": "수치 검증은 pytest가 담당"}


# ── 7단계(211차): 기능 지도 — 벤치마킹 3기능으로 메뉴를 세운다 ──────────
#   사용자 지시(2026-09-24): 벤치마킹 문서의 **주요 기능**으로 IA를 세우고 메뉴·
#   네비게이션을 만들라.
#   🔴 **실측이 축을 정했다**: 리포는 이미 `stage` 6단계를 코드에 쥐고 있는데
#      벤치마킹 3기능과 **1:1이 아니라 교차**한다(F2 시방이 ①·②·⑥에 흩어진다).
#      그래서 기능은 `consulting_package.FUNCTION_OF_CODE`가 **D코드마다 직접**
#      쥐고, 이 계층은 **그것을 그대로 보여 주기만** 한다(제2의 분류 금지).
#   ⚠️ **없는 것을 메뉴에 올리지 않는다** — 벤치마킹이 이름을 대지만 리포에 없는
#      7건은 `FUNCTION_GAPS`로 **「없음」이라고** 낸다(209차 계약).
#   🔴 **밴드·요율은 가져오지 않았다** — 판단성·시세성이다(1절 불변 원칙).

@app.get("/functions")
def function_map(request: Request):
    ix = cpkg.function_index()
    cases = [c for c in C.load_cases() if not c.get("partial")]
    return templates.TemplateResponse(request, "function_map.html", {
        "ix": ix,
        "cards": [{"code": cdsp.code(c), "title": cdsp.alias(c)["title"]}
                  for c in cases],
    })


# ── 281차(N-1): 기본설계 입구 — 주소·품목·면적만 받는다 ────────────────────
#   🔴 읽기 전용이라 GET이다(저장하지 않는다). 셋 중 없는 것이 있으면 그만큼만 낸다.
@app.get("/design")
def basic_design(request: Request, addr: str = "", crop: str = "", area_m2: str = ""):
    try:
        area = float(area_m2) if str(area_m2).strip() else None
    except ValueError:
        raise HTTPException(status_code=400, detail=f"면적은 숫자여야 한다: {area_m2!r}")
    if area is not None and area <= 0:
        raise HTTPException(status_code=400, detail=f"면적은 양수여야 한다: {area}")
    bd = cpkg.basic_design(addr.strip() or None, crop.strip() or None, area)
    return templates.TemplateResponse(request, "basic_design.html", {"bd": bd})


# ── 278차(WO-014): 관점별 입구 — 보는 사람의 질문으로 묶는다(분류뿐) ────────
#   🔴 입구이지 판정이 아니다 — 「당신에겐 이것이 맞다」를 말하지 않는다.
_PERSPECTIVE_NAMES = [n for n, _a, _c in cpkg.PERSPECTIVES]


@app.get("/for")
def perspectives(request: Request):
    return templates.TemplateResponse(request, "perspective.html",
                                      {"ix": cpkg.perspective_index(),
                                       "all_names": _PERSPECTIVE_NAMES})


@app.get("/for/{name}")
def perspective_one(request: Request, name: str):
    ix = cpkg.perspective_index(name)
    if not ix:
        raise HTTPException(status_code=404, detail=f"관점이 없다: {name}")
    return templates.TemplateResponse(request, "perspective.html",
                                      {"ix": ix, "all_names": _PERSPECTIVE_NAMES})


# ── 277차(WO-013): 사용 안내 — 화면별 설명 · FAQ · Q&A ────────────────────
#   🔴 기입 7단계(`ENTRY_STEPS`)는 **상태기계로 그대로 둔다** — 여기가 대신하지 않는다.
@app.get("/guide")
def guide(request: Request):
    return templates.TemplateResponse(request, "guide.html",
                                      {"g": cpkg.guide_index(),
                                       "rm": cpkg.readiness_menu()})


# ── 276차(WO-012): 참조 전수 카탈로그 — 무엇·어디서·어느 상수에 걸리는가 ─────
#   🔴 개인 이름은 **이 계층이 가린다**(183·184차 표시 계층) — 조립은 원본을 낸다.
@app.get("/refs")
def refs_catalog(request: Request):
    cat = cpkg.refs_catalog()
    for g in cat["groups"]:
        g["items"] = [{**x, "name": cdsp.scrub(x["name"]),
                       "desc": cdsp.scrub(x["desc"])} for x in g["items"]]
    return templates.TemplateResponse(request, "refs_catalog.html",
                                      {"cat": cat, "no_desc": cpkg.REFS_NO_DESC})


# ── 275차(WO-011): 축 대응표 — 네 축을 한 줄에 둔다(분류뿐) ──────────────
@app.get("/axes")
def axis_map(request: Request):
    return templates.TemplateResponse(request, "axis_map.html",
                                      {"ix": cpkg.axis_map()})


# ── 288차: 서비스 흐름 — 척추(6단계)에 산출물·대상·기능을 잇는다 ──────────
#   🔴 **축을 새로 만들지 않는다.** 설계서가 정한 3대상 × 6단계를 화면으로 옮길 뿐이고
#      나머지 축은 **렌즈**로 둔다. 분류와 건수만 낸다(1절 258차 단서).
@app.get("/flow")
def service_flow(request: Request):
    return templates.TemplateResponse(request, "service_flow.html",
                                      {"flow": cpkg.service_flow(),
                                       "trades": cpkg.trade_map(),
                                       "ss": cpkg.screen_stage_map(),
                                       "tsd": cpkg.trade_stage_draft()})


# ── 6단계(210차): 케이스 상세 — 산출물이 콘솔에서 닿는다 ────────────────
#   🔴 **실측이 결함을 정했다**: 산출물 **21건 중 9건**이 콘솔 어디에서도 닿지
#      않았다 — 케이스당 **4축 리포트 · 컨설팅 패키지 · 판정 부록**(3종 × 3케이스).
#      카드는 **통합보고서 하나만** 가리켰고, 나머지는 정적 `index.html`로 나가야
#      보였다. *「사이드바 링크가 모자라다」*와 *「케이스 상세가 없다」*는 같은
#      구멍 하나였다.
#   📌 **파일명을 여기서 짓지 않는다** — `build_site.case_output_files()`가 유일한
#      출처다(종전엔 이 파일의 f-string이 **두 번째 출처**였다). 보는 순서와
#      *「왜 보는가」*도 `build_site._MENU_KINDS`에서 그대로 가져온다.
#   ⚠️ 없는 파일을 **있는 척하지 않는다** — 아직 생성 안 된 산출물은 링크 대신
#      *「재생성 필요」*로 낸다(209차 계약: 되돌릴 수 없는 것을 되돌린 척 않기).

_WHY_BY_KIND = {k: why for k, why in bs._MENU_KINDS}


def _case_outputs(case: dict) -> list:
    """케이스 산출물 목록 — 이름·순서·사유 전부 build_site에서 온다."""
    files = bs.case_output_files(case)
    rows = []
    for kind, why in bs._MENU_KINDS:          # 보는 순서는 build_site가 쥔다
        fn = files.get(kind)
        if not fn:
            continue
        rows.append({"kind": kind, "why": why, "file": fn,
                     "href": f"/pages/{fn}", "exists": (ROOT / fn).is_file()})
    return rows


# 223차 — 산출물 상태·규칙 항목 상태 → 칩 색(표시 매핑뿐. 값은 엔진 반환 그대로)
STATUS_CHIP = {"생성": "chip-measured", "부분생성": "chip-statutory",
               "주입대기": "chip-est", "링크": "chip-ref"}
RULE_STATE_CHIP = {"통과": "chip-measured", "미검증": "chip-est", "불합격": "chip-warn"}
STEP_STATE_CHIP = {"완료": "chip-measured", "진행": "chip-statutory",
                   "대기": "chip-ref", "경로 없음": "chip-warn"}


@app.get("/case/{display_code}")
def case_detail(request: Request, display_code: str):
    # 🔴 URL은 **표시 코드**다(C1·C4…) — 실명 `case_id`를 URL에 싣지 않는다
    #    (183·184차 계약. 210차에 실명으로 열 뻔했고 183차 가드가 잡았다).
    case = cdsp.by_code(display_code, C.load_cases())
    if case is None:
        raise HTTPException(404, detail=f"케이스 {display_code} 없음")
    al = cdsp.alias(case)
    prov = case.get("provenance", {})
    # 🔴 출처 문자열에는 **실명이 들어 있다**(농가·기관 이름). 지우면 출처가
    #    사라지므로 183·184차 방식대로 `scrub`으로 **코드로 치환**한다 —
    #    파일명·시트·행·연도 같은 비-실명 부분은 그대로 남아 대조가 가능하다.
    chips = [{"field": f, "status": (prov.get(f) or {}).get("status", ""),
              "cls": chip_class((prov.get(f) or {}).get("status", "")),
              "source": cdsp.scrub((prov.get(f) or {}).get("source", ""))}
             for f in sorted(prov)]
    kpi, assum = None, None
    if not case.get("partial"):
        res = rr.compute(C.case_to_input(case))   # 표시 전용(앱 내 재계산 없음)
        ec = res["economics"]
        kpi = [("ROI", f"{ec['roi']*100:.1f}%"),
               ("Payback", f"{ec['payback']:.1f}년" if ec["payback"] else "산출불가"),
               ("NPV", f"{ec['npv']/100000000:,.2f}억"),
               ("실질ROI", f"{ec['real_roi']*100:.1f}%" if ec["real_roi"] else "—")]
        assum = rr.assumption_html(ec)
    funcs = None
    if not case.get("partial"):
        pkg = cpkg.build_package(case)
        have = {x["code"]: x for x in pkg["items"]}
        ix = cpkg.function_index()
        funcs = [{"fn": r["fn"], "name": r["name"], "desc": r["desc"],
                  "docs": [{"code": i["code"], "title": i["title"],
                            "status": (have.get(i["code"]) or {}).get("status", "")}
                           for i in r["docs"]],
                  "gaps": r["gaps"]} for r in ix["rows"]]
    # 223차 — 벤치마킹 화면 패턴(생애주기 레일·플랫폼 3단계·실사·대조·판정 부록).
    #   🔴 전부 `build_package` 반환의 **표시**다 — 묶음·순서는 `consulting_package`가
    #      쥐고(★사용자 결정 2026-09-27), 이 계층은 옮겨 담기만 한다.
    rail = platform = d23 = d24 = d25 = badge = None
    if not case.get("partial"):
        rail = cpkg.lifecycle_rail(pkg["items"])
        platform = cpkg.platform_index(pkg["items"])
        d23 = (have.get("D23") or {}).get("data")
        d24 = (have.get("D24") or {}).get("data")
        d25 = (have.get("D25") or {}).get("data")
        badge = cpkg.ksfid_badge(pkg)   # 225차 — 추적 식별자(등급 아님)
    return templates.TemplateResponse(request, "case_detail.html", {
        "rail": rail, "platform": platform, "d23": d23, "d24": d24, "d25": d25, "badge": badge,
        "status_cls": STATUS_CHIP, "rule_cls": RULE_STATE_CHIP,
        "case": case, "alias": al, "outputs": _case_outputs(case), "funcs": funcs,
        "chips": chips, "kpi": kpi, "assum": assum,
        "n_sets": len((case.get("scenarios") or {}).get("sets", [])),
        "has_fin": bool(case.get("financing")),
    })


# ── 2단계(33차): 기입 워크플로 — financing·시나리오 웹폼 ─────────────────
# 원칙: 검증·계산은 전부 엔진 계층(loan_amortization·scenario_rows)에 위임하고,
# 앱은 폼 파싱과 저장만 한다. 근거(note) 없는 저장은 거부(시세성·판단성 주입 원칙).
# 저장 대상은 케이스 JSON(git 추적) — 커밋은 사람이 한다(과제 단위 커밋 절차 유지).

def _full_case_or_404(display_code: str) -> dict:
    """표시 코드(C1·C2…)로 4축 케이스를 찾는다.

    🔴210차 — 종전엔 **실명 `case_id`로 받았다**. 그래서 `/entry` 허브와 기입
    화면의 URL에 `wonchaewon`·`chuncheon`·`uminjae`가 그대로 실렸다(33차부터).
    183차 가드는 **홈만** 훑어서 못 봤다 — 210차에 가드를 기입 화면까지 넓히자
    드러났다. 계약은 *「실명을 사용자가 보는 표면에 싣지 않는다」*이고 **URL도
    그 표면**이다.
    """
    c = cdsp.by_code(display_code, C.load_cases())
    if c is None:
        raise HTTPException(404, detail=f"케이스 {display_code} 없음")
    if c.get("partial"):
        raise HTTPException(400, detail="부분 케이스에는 기입할 수 없다(4축 미산출)")
    return c


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
        "code": cdsp.code(c), "title": cdsp.alias(c)["title"],
        "fin": bool(c.get("financing")),
        "n_sets": len((c.get("scenarios") or {}).get("sets", [])),
        "site": bool(c.get(cpkg.SITE_CONDITIONS_KEY)),   # 242차 — ★D-9 입지 조건
        # 224차 — 기입 절차 7단계(SGS JAS 준거). 상태는 `entry_steps`가 분류한다
        "steps": cpkg.entry_steps(c, cpkg.build_package(c)),
    } for c in cs]
    return templates.TemplateResponse(request, "entry_hub.html", {
        "rows": rows, "step_defs": cpkg.ENTRY_STEPS, "step_cls": STEP_STATE_CHIP})


@app.get("/entry/financing/{display_code}")
def financing_form(request: Request, display_code: str):
    case = _full_case_or_404(display_code)
    return templates.TemplateResponse(request, "entry_financing.html", {
        "case": case, "alias": cdsp.alias(case),
        "fin": case.get("financing") or {}, "preview": None, "form_vals": None,
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


@app.post("/entry/financing/{display_code}/preview")
async def financing_preview(request: Request, display_code: str):
    case = _full_case_or_404(display_code)
    form = await request.form()
    fin = _parse_financing(form)
    am = _amortize_or_400(fin)
    return templates.TemplateResponse(request, "entry_financing.html", {
        "case": case, "alias": cdsp.alias(case),
        "fin": fin, "preview": am, "form_vals": fin,
    })


@app.post("/entry/financing/{display_code}/save")
async def financing_save(request: Request, display_code: str):
    case = _full_case_or_404(display_code)
    form = await request.form()
    fin = _parse_financing(form)
    if not fin["note"]:
        raise HTTPException(400, detail="근거(note: 약정서/공고 출처·기준일)가 비어 있다 — 출처 없는 실조건 저장 금지")
    _amortize_or_400(fin)  # 엔진 검증 통과분만 저장
    case["financing"] = fin
    _save_case(case)
    return RedirectResponse(f"/entry/financing/{display_code}?saved=1", status_code=303)


@app.get("/entry/scenario/{display_code}")
def scenario_form(request: Request, display_code: str):
    case = _full_case_or_404(display_code)
    return templates.TemplateResponse(request, "entry_scenario.html", {
        "case": case, "alias": cdsp.alias(case),
        "sets": (case.get("scenarios") or {}).get("sets", []),
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


@app.post("/entry/scenario/{display_code}/preview")
async def scenario_preview(request: Request, display_code: str):
    case = _full_case_or_404(display_code)
    form = await request.form()
    new_set = _parse_scenario_set(form)
    rows, _ = _scenario_rows_or_400(case, new_set)
    return templates.TemplateResponse(request, "entry_scenario.html", {
        "case": case, "alias": cdsp.alias(case),
        "sets": (case.get("scenarios") or {}).get("sets", []),
        "fields": sorted(bs.SCENARIO_ALLOWED_FIELDS), "preview": rows, "form_vals": new_set,
        "error": None,
    })


@app.post("/entry/scenario/{display_code}/save")
async def scenario_save(request: Request, display_code: str):
    case = _full_case_or_404(display_code)
    form = await request.form()
    new_set = _parse_scenario_set(form)
    if not new_set["assumptions"]:
        raise HTTPException(400, detail="변경 필드가 하나도 없다 — 화이트리스트 필드 중 최소 1개 기입")
    _, trial = _scenario_rows_or_400(case, new_set)  # 검증 통과분만 저장
    _save_case(trial)
    return RedirectResponse(f"/entry/scenario/{display_code}?saved=1", status_code=303)


# ── 3단계(35차): 케이스 입력 마법사 ─────────────────────────────────────
# 정책(사용자 지시 "3단계 진행" — 34차 보류 판정의 선행조건을 권고안 채택으로 확정):
#   웹 마법사 신규 케이스의 provenance status는 "추정"/"확인요망"만 허용한다.
#   "실측"은 웹에서 부여 불가 — 실측 승격은 기존 절차(원문 대조→JSON 편집→커밋)로만.
#   예외 1건: 설계하중을 엔진 고시 조회(siting_design_load)로 채택한 경우 그 값의
#   출처는 사용자가 아니라 엔진 레지스트리이므로 "실측(고시 조회)"를 자동 기입한다.

WIZARD_ALLOWED_STATUS = ("추정", "확인요망")
# 87차: 대조가능성 감사 게이트의 필수 provenance 목록(CASE_REQUIRED_PROV)과
#   **짝**으로 확대했다(5→10). ⚠️모듈명을 적지 않는 이유: 감사기는 감사자이지
#   계산 참여자가 아니라 이 계층이 참조하지 않는다는 원칙이 테스트로 고정돼 있다.
#   한쪽만 넓히면 마법사로 만든 새 케이스가 생성 즉시 감사 갭을 낸다.
#   설계하중(snow_cm·wind_ms)은 고시 조회 경로가 provenance를 자동 생성하므로 여기엔 없다.
# 🔴206차 — **값을 두 번 묻지 않는다.** 근거 표가 모든 prov 필드에 값 칸을 내는데
#   그중 다섯(area_m2·surface_area_m2·t_target·fr·fitness_pct)은 **설계·운영 절에도
#   같은 `name`으로 있었다**. 같은 이름이 둘이면 서버는 하나만 읽고(뒤엣것이 이겼다)
#   **앞에 적은 값이 조용히 버려진다** — 206차 관통 시험에서 실제로 그랬다.
#   → 아래 목록의 필드만 근거 표에서 **값**을 받고, 나머지는 **근거만** 받는다.
WIZARD_PROV_VALUE_FIELDS = ("base_yield_kg_m2", "price_won_per_kg", "opex",
                            "total_construction_cost", "subsidy_rate")

WIZARD_PROV_FIELDS = ("base_yield_kg_m2", "price_won_per_kg", "opex",
                      "total_construction_cost", "subsidy_rate",
                      "area_m2", "surface_area_m2", "fr", "t_target", "fitness_pct")
_CASE_ID_RE = re.compile(r"^[a-z][a-z0-9_\-]{1,40}$")


def _parse_newcase_form(form) -> dict:
    cid = (form.get("case_id") or "").strip()
    if not _CASE_ID_RE.match(cid):
        raise HTTPException(400, detail="case_id는 영소문자로 시작, 영소문자·숫자·_·- 2~41자(기존 관례: wonchaewon 등)")
    region = (form.get("region") or "").strip()
    if not region:
        raise HTTPException(400, detail="region이 비어 있다")
    inp = {
        "business_type": (form.get("business_type") or "").strip() or "신규",
        "crop": (form.get("crop") or "").strip(),
        "region": region,
        "area_m2": _form_float(form, "area_m2", required=True),
        "cover": (form.get("cover") or "").strip(),
        "surface_area_m2": _form_float(form, "surface_area_m2", required=True),
        "t_target": _form_float(form, "t_target", required=True),
        "t_min": _form_float(form, "t_min", required=True),
        "fr": _form_float(form, "fr", required=True),
        "base_yield_kg_m2": _form_float(form, "base_yield_kg_m2", required=True),
        "price_won_per_kg": _form_float(form, "price_won_per_kg", required=True),
        "fitness_pct": _form_float(form, "fitness_pct", required=True),
        "opex": _form_float(form, "opex", required=True, as_int=True),
        "total_construction_cost": _form_float(form, "total_construction_cost", required=True, as_int=True),
        "subsidy_rate": _form_float(form, "subsidy_rate", required=True),
    }
    # 🔴199차 — 197차가 연 **재무 가정 주입 자리**를 기입 폼까지 잇는다.
    #   ⚠️ **빈칸은 넣지 않는다** — 넣으면 「주입되지 않았다」가 거짓이 되고,
    #   비우는 것과 기본값을 적어 넣는 것은 **산출물에서 다르게 읽힌다**.
    for _k, _as_int in (("discount_rate", False), ("evaluation_years", True),
                        ("useful_life", True)):
        if (form.get(_k) or "").strip():
            inp[_k] = _form_float(form, _k, required=True, as_int=_as_int)

    prov = {}
    lookup = None
    if form.get("use_lookup") == "1":
        lookup = e.siting_design_load(region)
        if not lookup:
            raise HTTPException(400, detail=f"고시 조회 실패 — REGION_DESIGN_LOAD에 '{region}' 매칭 없음(수동 입력으로 전환하고 근거를 남길 것)")
        inp["snow_cm"], inp["wind_ms"] = lookup["snow_cm"], lookup["wind_ms"]
        auto = {"status": "실측", "source": f"REGION_DESIGN_LOAD 고시 조회('{region}') — 웹 마법사 자동 기입(값 출처는 엔진 레지스트리)"}
        prov["snow_cm"] = dict(auto)
        prov["wind_ms"] = dict(auto)
    else:
        inp["snow_cm"] = _form_float(form, "snow_cm", required=True)
        inp["wind_ms"] = _form_float(form, "wind_ms", required=True)
        st = (form.get("load_status") or "").strip()
        src = (form.get("load_source") or "").strip()
        if st not in WIZARD_ALLOWED_STATUS:
            raise HTTPException(400, detail=f"설계하중 수동 입력의 status는 {WIZARD_ALLOWED_STATUS}만 허용(웹 실측 부여 불가 정책)")
        if not src:
            raise HTTPException(400, detail="설계하중 수동 입력의 근거(source)가 비어 있다")
        prov["snow_cm"] = {"status": st, "source": src}
        prov["wind_ms"] = {"status": st, "source": src}
    for f in WIZARD_PROV_FIELDS:
        st = (form.get(f"prov_{f}_status") or "").strip()
        src = (form.get(f"prov_{f}_source") or "").strip()
        if st not in WIZARD_ALLOWED_STATUS:
            raise HTTPException(400, detail=f"{f}: status는 {WIZARD_ALLOWED_STATUS}만 허용 — 실측 승격은 원문 대조 절차(커밋)로만")
        if not src:
            raise HTTPException(400, detail=f"{f}: 근거(source)가 비어 있다 — 근거 없는 값 금지")
        prov[f] = {"status": st, "source": src}
    case = {
        "case_id": cid,
        "title": (form.get("title") or "").strip() or cid,
        "as_of": (form.get("as_of") or "").strip(),
        "input": inp,
        "provenance": prov,
        "wizard": {"policy": "웹 마법사 신규 케이스(35차) — status는 추정/확인요망만, 실측 승격은 원문 대조 절차로만",
                   "design_load_lookup": bool(lookup)},
    }
    return case


def _newcase_compute_or_400(case: dict):
    try:
        inp = C.case_to_input(case)
        res = rr.compute(inp)
        bench = e.benchmark_check(case["input"]["total_construction_cost"],
                                  case["input"]["area_m2"], inp.cover)
        return res, bench
    except (ValueError, KeyError, TypeError) as ex:
        raise HTTPException(400, detail=f"엔진 검증 실패: {ex}")


# ── 226차: 문서 제출·K-SFID 발급 주입 폼(사용자 지시) ─────────────────────
# 원칙은 financing과 같다: 폼 파싱·저장만 앱이 하고, **검증·미리보기는 엔진**
# (`build_package` → D4 정합 분류·D19 기자재 대조·D25·배지)이 한다 — 이 계층은
# 엔진 함수를 **직접 부르지 않고** 패키지 반환만 옮긴다(80·181차 가드).
# 근거(note) 없는 저장은 거부. 번호는 **발급기관이 준 것을 적을 뿐**이다.

def _lines(form, key) -> list:
    return [x.strip() for x in (form.get(key) or "").splitlines() if x.strip()]


def _parse_docs(form) -> dict:
    rows = []
    for ln in _lines(form, "doc_rows_text"):
        cells = [c.strip() for c in ln.split("|")]
        if len(cells) > len(cpkg.DOC_ROW_FIELDS):
            raise HTTPException(400, detail=f"문서 행 칸이 {len(cells)}개다 — 최대 "
                                f"{len(cpkg.DOC_ROW_FIELDS)}칸(req_id | 요구사항 | 도면 | Rev | "
                                f"시방 | Rev | BoQ | Rev | 규격서 | Rev): {ln!r}")
        row = dict(zip(cpkg.DOC_ROW_FIELDS, cells))
        if not row.get("req_id"):
            raise HTTPException(400, detail=f"문서 행에 req_id가 없다: {ln!r}")
        rows.append({k: row.get(k, "") for k in cpkg.DOC_ROW_FIELDS})
    ks = {}
    for ln in _lines(form, "ks_declared_text"):
        if "=" not in ln:
            raise HTTPException(400, detail=f"규격 선언은 「모델 = 선언」 형식이다: {ln!r}")
        m, d = (x.strip() for x in ln.split("=", 1))
        if not m or not d:
            raise HTTPException(400, detail=f"규격 선언의 모델·선언이 비었다: {ln!r}")
        ks[m] = d
    models = _lines(form, "quoted_models_text")
    att = {}                                   # 227차 — 「모델 = 서류1, 서류2」
    for ln in _lines(form, "attachments_text"):
        if "=" not in ln:
            raise HTTPException(400, detail=f"재료승인 첨부는 「모델 = 서류1, 서류2」 형식이다: {ln!r}")
        m, rest = (x.strip() for x in ln.split("=", 1))
        names = [x.strip() for x in rest.split(",") if x.strip()]
        if m not in models:
            raise HTTPException(400, detail=f"첨부의 모델 「{m}」이 견적 기자재 모델 목록에 없다 — "
                                "대조할 기자재가 아니다")
        if not names:
            raise HTTPException(400, detail=f"「{m}」의 첨부 서류가 비었다: {ln!r}")
        att[m] = names
    block = {"doc_rows": rows, "dd_documents": _lines(form, "dd_documents_text"),
             "quoted_models": models, "ks_declared": ks, "attachments_by_model": att,
             "note": (form.get("note") or "").strip()}
    if not (rows or block["dd_documents"] or block["quoted_models"]):
        raise HTTPException(400, detail="제출 문서가 하나도 없다 — 문서 행·실사 문서·견적 모델 중 하나는 있어야 한다")
    return block


def _docs_text(block: dict) -> dict:
    """저장 블록 → 폼 textarea 값(표시 포맷팅)."""
    return {"doc_rows_text": "\n".join(" | ".join(r.get(k, "") for k in cpkg.DOC_ROW_FIELDS)
                                       for r in block.get("doc_rows") or []),
            "dd_documents_text": "\n".join(block.get("dd_documents") or []),
            "quoted_models_text": "\n".join(block.get("quoted_models") or []),
            "ks_declared_text": "\n".join(f"{m} = {d}" for m, d in
                                          (block.get("ks_declared") or {}).items()),
            "attachments_text": "\n".join(f"{m} = {', '.join(v)}" for m, v in
                                          (block.get("attachments_by_model") or {}).items()),
            "note": block.get("note", "")}


def _preview_with(case: dict, key: str, block: dict) -> dict:
    """블록을 넣은 **사본**으로 패키지를 만든다 — 엔진 검증 실패는 400으로 그대로 낸다."""
    trial = dict(case)
    trial[key] = block
    try:
        pkg = cpkg.build_package(trial)
    except (ValueError, TypeError) as ex:
        raise HTTPException(400, detail=str(ex))
    have = {x["code"]: x for x in pkg["items"]}
    return {"steps": cpkg.entry_steps(trial, pkg), "badge": cpkg.ksfid_badge(pkg),
            "d1": (have.get("D1") or {}).get("data") or {},
            "d4": (have.get("D4") or {}).get("data") or {},
            "d19": (have.get("D19") or {}).get("data"),
            "d25": ((have.get("D25") or {}).get("data") or {}).get("등급") or {}}


def _docs_ctx(case, block, preview=None, form_vals=None):
    rep = ((preview or {}).get("d4") or {}).get("4축 정합")
    return {"case": case, "alias": cdsp.alias(case), "fields": cpkg.DOC_ROW_FIELDS,
            "approval_docs": cpkg.APPROVAL_ATTACHMENTS,
            "approval_aliases": cpkg.APPROVAL_ALIASES,
            "v": form_vals or _docs_text(block), "preview": preview, "rep": rep,
            "step_cls": STEP_STATE_CHIP}


@app.get("/entry/docs/{display_code}")
def docs_form(request: Request, display_code: str):
    case = _full_case_or_404(display_code)
    return templates.TemplateResponse(request, "entry_docs.html",
                                      _docs_ctx(case, case.get(cpkg.DOC_SUBMISSION_KEY) or {}))


@app.post("/entry/docs/{display_code}/preview")
async def docs_preview(request: Request, display_code: str):
    case = _full_case_or_404(display_code)
    form = await request.form()
    block = _parse_docs(form)
    pv = _preview_with(case, cpkg.DOC_SUBMISSION_KEY, block)
    return templates.TemplateResponse(request, "entry_docs.html",
                                      _docs_ctx(case, block, pv, _docs_text(block)))


@app.post("/entry/docs/{display_code}/save")
async def docs_save(request: Request, display_code: str):
    case = _full_case_or_404(display_code)
    form = await request.form()
    block = _parse_docs(form)
    if not block["note"]:
        raise HTTPException(400, detail="근거(note: 문서 출처·수령일)가 비어 있다 — 출처 없는 제출 기록 금지")
    _preview_with(case, cpkg.DOC_SUBMISSION_KEY, block)   # 엔진 검증 통과분만 저장
    case[cpkg.DOC_SUBMISSION_KEY] = block
    _save_case(case)
    return RedirectResponse(f"/entry/docs/{display_code}?saved=1", status_code=303)


def _parse_issue(form) -> dict:
    seq = _form_float(form, "ksfid_seq", required=True, as_int=True)
    issued = (form.get("ksfid_issued") or "").strip()
    if not issued:
        raise HTTPException(400, detail="ksfid_issued(발급일 YYYY-MM-DD)가 비어 있다")
    return {"ksfid_seq": seq, "ksfid_issued": issued, "note": (form.get("note") or "").strip()}


def _issue_ctx(case, block, preview=None):
    return {"case": case, "alias": cdsp.alias(case), "v": block, "preview": preview,
            "step_cls": STEP_STATE_CHIP}


@app.get("/entry/issue/{display_code}")
def issue_form(request: Request, display_code: str):
    case = _full_case_or_404(display_code)
    return templates.TemplateResponse(request, "entry_issue.html",
                                      _issue_ctx(case, case.get(cpkg.KSFID_ISSUE_KEY) or {}))


@app.post("/entry/issue/{display_code}/preview")
async def issue_preview(request: Request, display_code: str):
    case = _full_case_or_404(display_code)
    form = await request.form()
    block = _parse_issue(form)
    pv = _preview_with(case, cpkg.KSFID_ISSUE_KEY, block)
    return templates.TemplateResponse(request, "entry_issue.html", _issue_ctx(case, block, pv))


@app.post("/entry/issue/{display_code}/save")
async def issue_save(request: Request, display_code: str):
    case = _full_case_or_404(display_code)
    form = await request.form()
    block = _parse_issue(form)
    if not block["note"]:
        raise HTTPException(400, detail="근거(note: 발급기관·발급 문서)가 비어 있다 — 출처 없는 발급 기록 금지")
    _preview_with(case, cpkg.KSFID_ISSUE_KEY, block)      # 엔진 검증 통과분만 저장
    case[cpkg.KSFID_ISSUE_KEY] = block
    _save_case(case)
    return RedirectResponse(f"/entry/issue/{display_code}?saved=1", status_code=303)


# ── 242차: 입지 조건(동절기 달 · 보온스크린) 기입 — ★D-9 ──────────────────
# 동절기 달은 **케이스마다 입력**하고 한 달 지정도 유효하다(★사용자 결정 2026-09-28). 엔진은
# 기본값을 두지 않는다. 검증·계산(동절기 평균풍속·보정계수)은 엔진이 하고, 이 계층은 폼만 읽는다.

def _parse_site(form) -> dict:
    months = []
    for raw in form.getlist("winter_m"):
        try:
            m = int(raw)
        except ValueError:
            raise HTTPException(400, detail=f"동절기 달이 숫자가 아니다: {raw!r}")
        if m not in months:
            months.append(m)
    if not months:
        raise HTTPException(400, detail="동절기 달을 한 달 이상 고른다 — 한 달만 골라도 된다(★D-9)")
    scr = (form.get("has_thermal_screen") or "").strip()
    if scr not in ("yes", "no"):
        raise HTTPException(400, detail="보온스크린 유무를 고른다(있음/없음)")
    return {"winter_months": months, "has_thermal_screen": scr == "yes",
            "note": (form.get("note") or "").strip()}


def _site_ctx(case, block, preview=None):
    return {"case": case, "alias": cdsp.alias(case), "v": block, "preview": preview,
            "threshold": e.WIND_STRONG_THRESHOLD_MS}


@app.get("/entry/site/{display_code}")
def site_form(request: Request, display_code: str):
    case = _full_case_or_404(display_code)
    return templates.TemplateResponse(request, "entry_site.html",
                                      _site_ctx(case, case.get(cpkg.SITE_CONDITIONS_KEY) or {}))


@app.post("/entry/site/{display_code}/preview")
async def site_preview(request: Request, display_code: str):
    case = _full_case_or_404(display_code)
    form = await request.form()
    block = _parse_site(form)
    pv = _preview_with(case, cpkg.SITE_CONDITIONS_KEY, block)
    return templates.TemplateResponse(request, "entry_site.html", _site_ctx(case, block, pv))


@app.post("/entry/site/{display_code}/save")
async def site_save(request: Request, display_code: str):
    case = _full_case_or_404(display_code)
    form = await request.form()
    block = _parse_site(form)
    if not block["note"]:
        raise HTTPException(400, detail="근거(note: 동절기 달을 고른 이유·출처)가 비어 있다 — 출처 없는 설계 조건 저장 금지")
    _preview_with(case, cpkg.SITE_CONDITIONS_KEY, block)   # 엔진 검증 통과분만 저장
    case[cpkg.SITE_CONDITIONS_KEY] = block
    _save_case(case)
    return RedirectResponse(f"/entry/site/{display_code}?saved=1", status_code=303)


@app.get("/entry/newcase")
def newcase_form(request: Request):
    return templates.TemplateResponse(request, "entry_newcase.html", {
        "form_vals": {}, "result": None, "statuses": WIZARD_ALLOWED_STATUS,
        "prov_fields": WIZARD_PROV_FIELDS,
        "prov_value_fields": WIZARD_PROV_VALUE_FIELDS,
    })


@app.post("/entry/newcase/preview")
async def newcase_preview(request: Request):
    form = await request.form()
    case = _parse_newcase_form(form)
    res, bench = _newcase_compute_or_400(case)
    return templates.TemplateResponse(request, "entry_newcase.html", {
        "form_vals": dict(form), "result": {"case": case, "res": res, "bench": bench},
        "statuses": WIZARD_ALLOWED_STATUS, "prov_fields": WIZARD_PROV_FIELDS,
        "prov_value_fields": WIZARD_PROV_VALUE_FIELDS,
    })


@app.post("/entry/newcase/save")
async def newcase_save(request: Request):
    form = await request.form()
    case = _parse_newcase_form(form)
    _newcase_compute_or_400(case)  # 엔진 통과분만 저장
    target = Path(C.CASES_DIR) / f"{case['case_id']}.json"
    if target.exists():
        raise HTTPException(409, detail=f"케이스 {case['case_id']} 이미 존재 — 마법사는 신규 전용(수정은 JSON 직접 편집)")
    _save_case(case)
    return RedirectResponse(f"/?created={case['case_id']}", status_code=303)


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


# ── 5단계(209차): 거부가 기입을 버리지 않는다 ───────────────────────────
#   🔴 **실측**: 마법사 폼은 **47칸**인데 브라우저 `required`는 **0개**다 — 검증을
#      한 곳(서버·엔진)에서만 하려고 일부러 그렇게 뒀다(제2 검증기 금지). 그런데
#      그 거부가 `application/json`으로 나가서 **47칸이 통째로 사라졌다**.
#      `HTTPException` 발생 지점은 **26곳**이고 전부 같은 결말이었다.
#   🔴 **폼은 이미 값을 되받을 줄 안다** — 템플릿의 `form_vals`가 그 길이다.
#      **오류 경로만 그 길을 쓰지 않았다**(206차가 찾은 결함과 같은 계열:
#      기능이 없는 게 아니라 **한 경로만 빠져 있었다**).
#   📌 **고치는 것은 표시 계층뿐이다.** 메시지는 검증한 쪽(엔진·저장 규칙)이 낸 말을
#      **그대로** 싣는다 — 앱이 고쳐 말하는 순간 **제2 검증기**가 된다. 상태 코드도
#      그대로 둔다(400/404/409/500). 새 검증도, 새 산술도 넣지 않는다.
#   ⚠️ 폼을 되돌릴 수 없는 거부(케이스가 없다·파싱 자체가 깨졌다)는 **일반 오류
#      화면**으로 간다 — 되돌릴 수 있는 척하지 않는다.

_FIN_FORM_KEYS = ("loan_principal_won", "annual_rate_pct", "term_years",
                  "grace_years", "method", "note")
_ENTRY_PATH_RE = re.compile(r"^/entry/(financing|scenario)/([^/]+)/(preview|save)$")


def _entry_error_page(path: str, form):
    """거부된 POST를 **같은 폼**으로 되돌린다. 되돌릴 수 없으면 None."""
    try:
        if path.startswith("/entry/newcase/"):
            return "entry_newcase.html", {
                "form_vals": dict(form), "result": None,
                "statuses": WIZARD_ALLOWED_STATUS,
                "prov_fields": WIZARD_PROV_FIELDS,
                "prov_value_fields": WIZARD_PROV_VALUE_FIELDS,
            }
        m = _ENTRY_PATH_RE.match(path)
        if m:
            case = _full_case_or_404(m.group(2))
            if m.group(1) == "financing":
                return "entry_financing.html", {
                    "case": case, "alias": cdsp.alias(case),
                    "fin": case.get("financing") or {}, "preview": None,
                    "form_vals": {k: (form.get(k) or "") for k in _FIN_FORM_KEYS},
                }
            return "entry_scenario.html", {
                "case": case, "alias": cdsp.alias(case),
        "sets": (case.get("scenarios") or {}).get("sets", []),
                "fields": sorted(bs.SCENARIO_ALLOWED_FIELDS), "preview": None,
                "form_vals": {
                    "name": form.get("name") or "",
                    "assumptions": {f: form.get(f) for f in bs.SCENARIO_ALLOWED_FIELDS
                                    if (form.get(f) or "").strip()},
                    "note": form.get("note") or "",
                },
            }
        if path.startswith("/entry/quotes/"):
            data = _parse_quotes_form(form)  # 파싱이 깨진 거부는 여기서 다시 깨진다
            return "entry_quotes_edit.html", {
                "data": data, "vendors": [_vendor_to_form(v) for v in data["vendor_quotes"]],
                "n_blocks": len(data["vendor_quotes"]) + 1,
                "src": form.get("src") or "", "category_keys": _category_keys(),
                "result": None,
            }
    except Exception:  # 되돌리기 실패는 조용히 일반 화면으로(2차 예외를 삼킨다)
        return None
    return None


@app.exception_handler(StarletteHTTPException)
async def rejection_keeps_the_form(request: Request, exc: StarletteHTTPException):
    """거부를 **화면**으로 낸다 — 메시지는 그대로, 상태 코드도 그대로."""
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    tpl, ctx = "error.html", {"detail": detail, "status": exc.status_code,
                              "path": request.url.path}
    if request.method == "POST":
        try:
            form = await request.form()
        except Exception:
            form = None
        if form is not None:
            built = _entry_error_page(request.url.path, form)
            if built:
                tpl, ctx = built
                # 🔴 `error`는 **폼을 되돌린 경우에만** 넣는다 — 띠가 *「기입한 값은
                #   아래에 그대로 남아 있다」*고 말하는데, 일반 오류 화면에는 폼이
                #   없다. 되돌리지 못했으면 **되돌린 척하지 않는다**.
                ctx["error"] = detail
    return templates.TemplateResponse(request, tpl, ctx, status_code=exc.status_code)
