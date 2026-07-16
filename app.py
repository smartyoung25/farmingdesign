"""
SmartFarm 입력폼 웹앱 (경로 C 확장 + 케이스 저장 연동)
- 폼 입력 → FarmInput → render_report.compute(엔진 실행) → render_html(렌더).
- 계산은 전적으로 smartfarm_engine 이 수행. 서버/HTML 어디에도 계산 로직 없음.
- 시세성 값(단가·노임·유가·총공사비)은 폼으로 '주입'(엔진은 조회 안 함).
- 리포트 화면에서 입력을 cases/*.json 으로 저장 → 사이트 재생성 → /cases 목록/비교뷰 편입.
실행: python app.py  → http://127.0.0.1:5000
"""
from __future__ import annotations
import os, re, json, datetime, html as _html
from flask import Flask, request, send_from_directory, redirect
import smartfarm_engine as e
import render_report as rr
from run_report import FarmInput

app = Flask(__name__)
esc = _html.escape
HERE = os.path.dirname(os.path.abspath(__file__))
CASES_DIR = os.path.join(HERE, "cases")

DEFAULTS = dict(
    business_type="신규", crop="토마토", region="충남",
    area_m2=3456, cover="유리", snow_cm=30, wind_ms=35,
    surface_area_m2=5000, t_target=10, t_min=-7.8, fr=0.7,
    base_yield_kg_m2=38.5, price_won_per_kg=2500, fitness_pct=95,
    opex=186420000, total_construction_cost=702030000, subsidy_rate=50,
)
_BT = [b.value for b in e.BusinessType]
_CV = [c.value for c in e.Cover]
_STATUS = ["실측", "추정", "확인요망"]

FORM_CSS = """
  :root{--bg:#f4f6f8;--card:#fff;--ink:#1a2330;--muted:#6b7787;--line:#e3e8ee;
    --brand:#1f7a4d;--brand-soft:#e8f3ec;}
  *{box-sizing:border-box;}
  body{margin:0;background:var(--bg);color:var(--ink);
    font-family:-apple-system,"Segoe UI","Malgun Gothic",sans-serif;line-height:1.5;}
  .wrap{max-width:860px;margin:0 auto;padding:28px 20px 64px;}
  header.top{background:var(--brand);color:#fff;border-radius:14px;padding:20px 24px;margin-bottom:20px;}
  header.top h1{margin:0 0 4px;font-size:21px;}
  header.top .sub{opacity:.9;font-size:13.5px;}
  form{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px 24px;}
  fieldset{border:1px solid var(--line);border-radius:12px;padding:14px 16px 4px;margin:0 0 16px;}
  legend{font-size:12.5px;font-weight:700;color:var(--brand);padding:0 6px;}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;}
  label{display:block;font-size:12.5px;color:var(--muted);margin-bottom:10px;}
  label .inj{color:#b8860b;font-weight:700;}
  input,select{width:100%;margin-top:4px;padding:8px 10px;border:1px solid var(--line);
    border-radius:8px;font-size:14px;}
  button{background:var(--brand);color:#fff;border:0;border-radius:10px;
    padding:12px 22px;font-size:15px;font-weight:600;cursor:pointer;}
  .note{font-size:12px;color:var(--muted);margin-top:14px;}
  a{color:var(--brand);}
"""

FIELDS = [
    ("기본", [
        ("business_type", "사업유형", "select", _BT),
        ("crop", "작목", "text", None),
        ("region", "지역", "text", None),
        ("area_m2", "재배면적(㎡)", "number", None),
        ("cover", "피복", "select", _CV),
    ]),
    ("설계·난방", [
        ("snow_cm", "지역 적설심(cm)", "number", None),
        ("wind_ms", "지역 풍속(m/s)", "number", None),
        ("surface_area_m2", "외피면적(㎡)", "number", None),
        ("t_target", "목표온도(℃)", "number", None),
        ("t_min", "설계외기온(℃)", "number", None),
        ("fr", "보온비 fr", "number", None),
    ]),
    ("경제성 (★=시세성 주입값)", [
        ("base_yield_kg_m2", "기준수량(kg/㎡)", "number", None),
        ("price_won_per_kg", "단가(원/kg) ★", "number", None),
        ("fitness_pct", "환경적합도(%)", "number", None),
        ("opex", "OPEX(원) ★", "number", None),
        ("total_construction_cost", "총공사비(원) ★", "number", None),
        ("subsidy_rate", "보조금율(%)", "number", None),
    ]),
]


def _field_html(name, labeltxt, kind, choices, val):
    if kind == "select":
        opts = "".join(f"<option value='{c}'{' selected' if str(val)==c else ''}>{c}</option>"
                       for c in choices)
        ctrl = f"<select name='{name}'>{opts}</select>"
    else:
        stepattr = " step='any'" if kind == "number" else ""
        ctrl = f"<input type='{kind}' name='{name}' value='{esc(str(val))}'{stepattr}>"
    inj = " <span class='inj'>★</span>" if "★" in labeltxt else ""
    labeltxt = labeltxt.replace(" ★", "")
    return f"<label>{labeltxt}{inj}{ctrl}</label>"


def form_page(values: dict) -> str:
    sets = []
    for legend, fields in FIELDS:
        cells = "".join(_field_html(n, lt, k, ch, values.get(n, "")) for n, lt, k, ch in fields)
        sets.append(f"<fieldset><legend>{legend}</legend><div class='grid'>{cells}</div></fieldset>")
    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SmartFarm 리포트 생성</title><style>{FORM_CSS}</style></head>
<body><div class="wrap">
  <header class="top"><h1>SmartFarm 4축 리포트 생성기</h1>
    <div class="sub">입력값 주입 → 엔진 계산 → 4축 리포트 · 계산 출처 smartfarm_engine 단일</div></header>
  <p><a href="/cases">▶ 저장된 케이스 목록</a> · <a href="/site/index.html">▶ 생성된 사이트(index)</a></p>
  <form method="post" action="/report">
    {''.join(sets)}
    <button type="submit">리포트 생성 ▶</button>
    <div class="note">★ 표시(단가·OPEX·총공사비)는 조회 시점 실측 <b>주입값</b>. 엔진은 시세를 조회하지 않습니다.</div>
  </form>
</div></body></html>"""


def _to_input(form) -> FarmInput:
    g = lambda k: form.get(k, "").strip()
    return FarmInput(
        business_type=e.BusinessType(g("business_type")),
        crop=g("crop"), region=g("region"),
        area_m2=float(g("area_m2")), cover=e.Cover(g("cover")),
        snow_cm=float(g("snow_cm")), wind_ms=float(g("wind_ms")),
        surface_area_m2=float(g("surface_area_m2")),
        t_target=float(g("t_target")), t_min=float(g("t_min")), fr=float(g("fr")),
        base_yield_kg_m2=float(g("base_yield_kg_m2")),
        price_won_per_kg=float(g("price_won_per_kg")),
        fitness_pct=float(g("fitness_pct")), opex=float(g("opex")),
        total_construction_cost=float(g("total_construction_cost")),
        subsidy_rate=float(g("subsidy_rate")) / 100.0,
    )


def _form_to_case_input(form) -> dict:
    """cases/*.json 의 input 스키마(문자열 enum·비율 보조금)로 변환."""
    g = lambda k: form.get(k, "").strip()
    return {
        "business_type": g("business_type"), "crop": g("crop"), "region": g("region"),
        "area_m2": float(g("area_m2")), "cover": g("cover"),
        "snow_cm": float(g("snow_cm")), "wind_ms": float(g("wind_ms")),
        "surface_area_m2": float(g("surface_area_m2")),
        "t_target": float(g("t_target")), "t_min": float(g("t_min")), "fr": float(g("fr")),
        "base_yield_kg_m2": float(g("base_yield_kg_m2")),
        "price_won_per_kg": float(g("price_won_per_kg")),
        "fitness_pct": float(g("fitness_pct")), "opex": float(g("opex")),
        "total_construction_cost": float(g("total_construction_cost")),
        "subsidy_rate": float(g("subsidy_rate")) / 100.0,
    }


def _safe_id(raw: str) -> str:
    s = re.sub(r"[^0-9A-Za-z가-힣_-]+", "_", (raw or "").strip()).strip("_")
    return s or "case_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _save_panel(form) -> str:
    hidden = "".join(f"<input type='hidden' name='{k}' value=\"{esc(str(form.get(k,'')))}\">"
                     for k in DEFAULTS)
    region, crop = form.get("region", "case"), form.get("crop", "")
    as_of = datetime.datetime.now().strftime("%Y-%m") + " (웹앱 주입)"
    sel = lambda name, default: "<select name='%s'>%s</select>" % (
        name, "".join(f"<option{' selected' if s==default else ''}>{s}</option>" for s in _STATUS))
    return f"""
<form method='post' action='/save' style='max-width:920px;margin:18px auto;padding:16px 20px;
  background:#fff;border:1px solid #e3e8ee;border-radius:12px;
  font-family:-apple-system,"Malgun Gothic",sans-serif;'>
  {hidden}
  <b style='color:#1f7a4d'>이 입력을 케이스로 저장</b>
  <div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:10px 0'>
    <label style='font-size:12px;color:#6b7787'>case_id
      <input name='case_id' value='{esc(_safe_id(region + "_" + crop))}' style='width:100%;padding:7px;border:1px solid #e3e8ee;border-radius:7px'></label>
    <label style='font-size:12px;color:#6b7787'>제목
      <input name='title' value='{esc(f"{region} — {crop}")}' style='width:100%;padding:7px;border:1px solid #e3e8ee;border-radius:7px'></label>
    <label style='font-size:12px;color:#6b7787'>기준시점
      <input name='as_of' value='{esc(as_of)}' style='width:100%;padding:7px;border:1px solid #e3e8ee;border-radius:7px'></label>
    <label style='font-size:12px;color:#6b7787'>단가 상태 {sel('st_price','실측')}</label>
    <label style='font-size:12px;color:#6b7787'>OPEX 상태 {sel('st_opex','추정')}</label>
    <label style='font-size:12px;color:#6b7787'>총공사비 상태 {sel('st_total','실측')}</label>
  </div>
  <button type='submit' style='background:#1f7a4d;color:#fff;border:0;border-radius:9px;padding:10px 18px;font-weight:600;cursor:pointer'>케이스 저장 + 사이트 재생성</button>
</form>"""


@app.route("/")
def index():
    return form_page(DEFAULTS)


@app.route("/report", methods=["POST"])
def report():
    try:
        inp = _to_input(request.form)
    except (ValueError, KeyError) as ex:
        return f"<p>입력 오류: {ex}</p><p><a href='/'>← 돌아가기</a></p>", 400
    res = rr.compute(inp)                      # ← 엔진 계산(단일 출처)
    html = rr.render_html(res)                 # ← 렌더만
    back = ("<a href='/' style='display:block;max-width:920px;margin:14px auto -8px;"
            "padding:0 20px;color:#1f7a4d;text-decoration:none'>← 입력 수정</a>")
    return html.replace("<body>", "<body>" + back + _save_panel(request.form), 1)


@app.route("/save", methods=["POST"])
def save():
    f = request.form
    try:
        _to_input(f)  # 유효성 검증
        input_obj = _form_to_case_input(f)
    except (ValueError, KeyError) as ex:
        return f"<p>저장 오류: {ex}</p><p><a href='/'>← 돌아가기</a></p>", 400
    case_id = _safe_id(f.get("case_id", ""))
    case = {
        "case_id": case_id,
        "title": f.get("title", "").strip() or case_id,
        "as_of": f.get("as_of", "").strip() or datetime.datetime.now().strftime("%Y-%m"),
        "notes": "웹앱에서 저장",
        "input": input_obj,
        "provenance": {
            "price_won_per_kg":        {"status": f.get("st_price", "실측"), "source": "웹앱 주입값"},
            "opex":                    {"status": f.get("st_opex", "추정"), "source": "웹앱 주입값"},
            "total_construction_cost": {"status": f.get("st_total", "실측"), "source": "웹앱 주입값"},
        },
    }
    os.makedirs(CASES_DIR, exist_ok=True)
    with open(os.path.join(CASES_DIR, case_id + ".json"), "w", encoding="utf-8") as fp:
        json.dump(case, fp, ensure_ascii=False, indent=2)
    # 정적 사이트 재생성(엔진 계산 → index/비교뷰에 새 케이스 편입)
    cwd = os.getcwd()
    try:
        os.chdir(HERE)
        import build_site
        build_site.main()
    finally:
        os.chdir(cwd)
    return (f"<div style='font-family:-apple-system,\"Malgun Gothic\";max-width:640px;margin:40px auto'>"
            f"<h2 style='color:#1f7a4d'>케이스 저장 완료</h2>"
            f"<p><code>cases/{esc(case_id)}.json</code> 기록 · 사이트 재생성됨.</p>"
            f"<p><a href='/site/SmartFarm_리포트_{esc(case_id)}.html'>▶ 이 케이스 리포트</a><br>"
            f"<a href='/site/SmartFarm_케이스비교.html'>▶ 케이스 비교뷰</a><br>"
            f"<a href='/cases'>▶ 케이스 목록</a> · <a href='/'>← 새 입력</a></p></div>")


@app.route("/cases")
def cases_list():
    from cases import load_cases
    items = load_cases()
    rows = "".join(
        f"<li style='margin:8px 0'><b>{esc(c['title'])}</b> "
        f"(<code>{esc(c['case_id'])}</code>) · 기준시점 {esc(c.get('as_of','—'))} — "
        f"<a href='/site/SmartFarm_리포트_{esc(c['case_id'])}.html'>리포트</a></li>"
        for c in items)
    return (f"<div style='font-family:-apple-system,\"Malgun Gothic\";max-width:720px;margin:36px auto'>"
            f"<h2 style='color:#1f7a4d'>저장된 케이스 ({len(items)})</h2>"
            f"<ul>{rows}</ul>"
            f"<p><a href='/site/SmartFarm_케이스비교.html'>▶ 비교뷰</a> · "
            f"<a href='/site/index.html'>▶ index</a> · <a href='/'>← 새 입력</a></p></div>")


@app.route("/site/<path:fn>")
def site(fn):
    return send_from_directory(HERE, fn)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
