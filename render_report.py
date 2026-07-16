"""
SmartFarm 4축 웹 리포트 생성기 (경로 C)
- 계산은 전적으로 smartfarm_engine 에 위임한다. 이 파일은 '렌더'만 한다.
- HTML 안에는 계산 로직(JS)이 없다. 값은 모두 파이썬 엔진이 산출한 결과다.
- 시세성 값(단가·노임·유가·총공사비)은 FarmInput 으로 '주입'한다(엔진은 조회 안 함).
- 입력을 바꾸려면 FarmInput 을 수정해 재생성한다(= 계산은 항상 엔진만 참조).

실행: python render_report.py            → 원채원 데모 리포트 HTML 생성
      compute(inp) / render_html(res)   → 다른 케이스에 재사용
"""
from __future__ import annotations
import html
import datetime as _dt
from dataclasses import asdict

import smartfarm_engine as e
from run_report import FarmInput  # 입력 스키마는 단일 정의 재사용


# ─────────────────────────────────────────────────────────────
# 1) 계산: 엔진만 호출해 구조화된 결과 dict 를 만든다 (렌더와 분리)
# ─────────────────────────────────────────────────────────────
def compute(inp: FarmInput) -> dict:
    # ── 설계: 규격 선정
    sel = e.select_specs(inp.snow_cm, inp.wind_ms)
    min_by_form = {
        form: {"name": s.name, "snow": s.snow_cm, "wind": s.wind_ms}
        for form, s in sel["min_by_form"].items()
    }

    # ── 설계/시공: 난방부하 + 실측 이중검증
    hr = e.heating_load(inp.surface_area_m2, inp.cover.value,
                        inp.t_target, inp.t_min, inp.fr,
                        floor_area_m2=inp.area_m2)
    v = e.verify_heating_vs_actual(hr.load_per_m2, inp.cover.value)

    # ── 시공: 총공사비 벤치마크 대조
    bc = e.benchmark_check(inp.total_construction_cost, inp.area_m2, inp.cover)

    # ── 경제성: 생산·매출·손익·투자지표
    prod = e.production_kg(inp.area_m2, inp.base_yield_kg_m2, inp.fitness_pct)
    revenue = prod * inp.price_won_per_kg
    fin = e.finance(revenue, inp.opex, inp.total_construction_cost,
                    subsidy_rate=inp.subsidy_rate)

    return {
        "meta": {
            "crop": inp.crop,
            "business_type": inp.business_type.value,
            "region": inp.region,
            "area_m2": inp.area_m2,
            "area_py": e.m2_to_py(inp.area_m2),
            "cover": inp.cover.value,
            "generated": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
        "design": {
            "snow_cm": inp.snow_cm,
            "wind_ms": inp.wind_ms,
            "n_candidates": len(sel["candidates"]),
            "min_by_form": min_by_form,
        },
        "heating": {
            "max_load": hr.max_load_kcal_h,
            "load_per_m2": hr.load_per_m2,
            "heater_capacity": hr.heater_capacity_kcal_h,
            "ref": v["ref_kcal_h_m2"],
            "ratio": v["ratio"],
            "status": v["status"],
        },
        "construction": {
            "total": inp.total_construction_cost,
            "unit_won_m2": bc["unit_won_m2"],
            "band": bc["band"],
            "status": bc["status"],
        },
        "economics": {
            "fitness_pct": inp.fitness_pct,
            "yield_adj": e.yield_adjustment(inp.fitness_pct),
            "production_kg": prod,
            "price": inp.price_won_per_kg,
            "revenue": revenue,
            "opex": inp.opex,
            "depreciation": fin.depreciation,
            "operating_profit": fin.operating_profit,
            "roi": fin.roi,
            "payback": fin.payback_years,
            "npv": fin.npv,
            "irr": fin.irr,
            "subsidy_rate": inp.subsidy_rate,
            "real_roi": fin.real_roi_after_subsidy,
        },
        "input_echo": {k: (val.value if hasattr(val, "value") else val)
                       for k, val in asdict(inp).items()},
    }


# ─────────────────────────────────────────────────────────────
# 2) 렌더: 결과 dict → 자체완결형 HTML (계산 로직 없음)
# ─────────────────────────────────────────────────────────────
def _won(x) -> str:
    return f"{x:,.0f}원" if x is not None else "N/A"


def _pct(x, digits=1) -> str:
    return f"{x*100:.{digits}f}%" if x is not None else "N/A"


def _status_class(status: str) -> str:
    if "정상" in status:
        return "ok"
    if "경계" in status or "재확인" in status:
        return "warn"
    return "bad"


def render_html(res: dict) -> str:
    m = res["meta"]
    d = res["design"]
    h = res["heating"]
    c = res["construction"]
    ec = res["economics"]
    esc = html.escape

    forms_rows = "".join(
        f"<tr><td>{esc(form)}</td><td>{esc(info['name'])}</td>"
        f"<td>설계적설심 {info['snow']}cm · 설계풍속 {info['wind']}m/s</td></tr>"
        for form, info in d["min_by_form"].items()
    )

    payback = f"{ec['payback']:.1f}년" if ec["payback"] else "초기적자·J커브"
    yield_adj = f"{ec['yield_adj']*100:+.0f}%"

    real_roi_block = ""
    if ec["real_roi"]:
        real_roi_block = f"""
        <div class="kpi highlight">
          <div class="kpi-label">실질 ROI <span class="sub">(보조금 {ec['subsidy_rate']*100:.0f}% 반영)</span></div>
          <div class="kpi-value">{_pct(ec['real_roi'])}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SmartFarm 4축 리포트 — {esc(m['crop'])} / {esc(m['region'])}</title>
<style>
  :root {{
    --bg:#f4f6f8; --card:#fff; --ink:#1a2330; --muted:#6b7787;
    --line:#e3e8ee; --brand:#1f7a4d; --brand-soft:#e8f3ec;
    --ok:#1f7a4d; --warn:#b8860b; --bad:#c0392b;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font-family:-apple-system,"Segoe UI","Malgun Gothic",sans-serif; line-height:1.55; }}
  .wrap {{ max-width:920px; margin:0 auto; padding:28px 20px 64px; }}
  header.top {{ background:var(--brand); color:#fff; border-radius:14px;
    padding:22px 26px; margin-bottom:22px; }}
  header.top h1 {{ margin:0 0 6px; font-size:22px; }}
  header.top .sub {{ opacity:.9; font-size:14px; }}
  header.top .gen {{ opacity:.7; font-size:12px; margin-top:10px; }}
  section.card {{ background:var(--card); border:1px solid var(--line);
    border-radius:14px; padding:20px 24px; margin-bottom:18px; }}
  .axis {{ display:inline-block; font-size:12px; font-weight:700; letter-spacing:.04em;
    color:var(--brand); background:var(--brand-soft); padding:3px 10px;
    border-radius:20px; margin-bottom:12px; }}
  h2 {{ font-size:17px; margin:0 0 14px; }}
  table {{ width:100%; border-collapse:collapse; font-size:14px; }}
  th,td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); }}
  th {{ color:var(--muted); font-weight:600; font-size:12.5px; }}
  .row {{ display:flex; justify-content:space-between; padding:7px 0;
    border-bottom:1px dashed var(--line); font-size:14px; }}
  .row:last-child {{ border-bottom:0; }}
  .row .lbl {{ color:var(--muted); }}
  .row .val {{ font-variant-numeric:tabular-nums; font-weight:600; }}
  .badge {{ font-size:12px; font-weight:700; padding:3px 10px; border-radius:20px; }}
  .badge.ok {{ color:var(--ok); background:#e8f3ec; }}
  .badge.warn {{ color:var(--warn); background:#fbf3dc; }}
  .badge.bad {{ color:var(--bad); background:#fbe6e3; }}
  .kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
    gap:12px; margin-top:6px; }}
  .kpi {{ background:#fafbfc; border:1px solid var(--line); border-radius:12px;
    padding:14px 16px; }}
  .kpi.highlight {{ background:var(--brand-soft); border-color:#cfe6d8; }}
  .kpi-label {{ font-size:12.5px; color:var(--muted); }}
  .kpi-label .sub {{ font-size:11px; }}
  .kpi-value {{ font-size:22px; font-weight:700; margin-top:4px;
    font-variant-numeric:tabular-nums; }}
  .note {{ font-size:12.5px; color:var(--muted); margin-top:18px;
    padding-top:14px; border-top:1px solid var(--line); }}
  details {{ margin-top:10px; font-size:13px; }}
  details summary {{ cursor:pointer; color:var(--muted); }}
  details pre {{ background:#f7f9fb; border:1px solid var(--line); border-radius:8px;
    padding:12px; overflow:auto; font-size:12px; }}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <h1>SmartFarm 4축 리포트 — {esc(m['crop'])} / {esc(m['business_type'])}</h1>
    <div class="sub">{esc(m['region'])} · {m['area_m2']:,.0f}㎡ ({m['area_py']:,.0f}평) · {esc(m['cover'])}</div>
    <div class="gen">생성 {esc(m['generated'])} · 계산 출처: smartfarm_engine (단일)</div>
  </header>

  <section class="card">
    <span class="axis">설계축</span>
    <h2>내재해형 규격 선정 (지역 설계강도 충족)</h2>
    <div class="row"><span class="lbl">지역 설계강도</span>
      <span class="val">적설심 {d['snow_cm']}cm · 풍속 {d['wind_ms']}m/s</span></div>
    <div class="row"><span class="lbl">충족 규격 수</span>
      <span class="val">{d['n_candidates']}종</span></div>
    <table>
      <thead><tr><th>형식</th><th>최소사양</th><th>설계강도</th></tr></thead>
      <tbody>{forms_rows}</tbody>
    </table>
  </section>

  <section class="card">
    <span class="axis">설계 · 시공축</span>
    <h2>난방부하 (실측 이중검증)</h2>
    <div class="row"><span class="lbl">최대난방부하</span>
      <span class="val">{h['max_load']:,.0f} kcal/h ({h['load_per_m2']:,.0f} kcal/h·㎡)</span></div>
    <div class="row"><span class="lbl">난방기 용량</span>
      <span class="val">{h['heater_capacity']:,.0f} kcal/h</span></div>
    <div class="row"><span class="lbl">실측 대조 (기준 {h['ref']} × {h['ratio']})</span>
      <span class="badge {_status_class(h['status'])}">{esc(h['status'])}</span></div>
  </section>

  <section class="card">
    <span class="axis">시공축</span>
    <h2>총공사비 벤치마크 대조</h2>
    <div class="row"><span class="lbl">총공사비</span>
      <span class="val">{_won(c['total'])}</span></div>
    <div class="row"><span class="lbl">단위 공사비</span>
      <span class="val">{c['unit_won_m2']:,}원/㎡</span></div>
    <div class="row"><span class="lbl">{esc(m['cover'])} 밴드 {c['band'][0]:,}~{c['band'][1]:,}</span>
      <span class="badge {_status_class(c['status'])}">{esc(c['status'])}</span></div>
  </section>

  <section class="card">
    <span class="axis">경제성축</span>
    <h2>생산 · 수익 · 투자지표</h2>
    <div class="row"><span class="lbl">환경적합도 → 수율조정</span>
      <span class="val">{ec['fitness_pct']:.0f}% → {yield_adj}</span></div>
    <div class="row"><span class="lbl">생산량 × 단가</span>
      <span class="val">{ec['production_kg']:,.0f} kg × {ec['price']:,.0f}원</span></div>
    <div class="row"><span class="lbl">매출</span>
      <span class="val">{_won(ec['revenue'])}</span></div>
    <div class="row"><span class="lbl">OPEX · 감가상각</span>
      <span class="val">{_won(ec['opex'])} · {_won(ec['depreciation'])}</span></div>
    <div class="row"><span class="lbl">영업이익</span>
      <span class="val">{_won(ec['operating_profit'])}</span></div>
    <div class="kpis">
      <div class="kpi"><div class="kpi-label">ROI</div>
        <div class="kpi-value">{_pct(ec['roi'])}</div></div>
      <div class="kpi"><div class="kpi-label">투자회수기간</div>
        <div class="kpi-value">{payback}</div></div>
      <div class="kpi"><div class="kpi-label">NPV (10y·5%)</div>
        <div class="kpi-value">{ec['npv']/1e8:,.2f}억</div></div>
      <div class="kpi"><div class="kpi-label">IRR</div>
        <div class="kpi-value">{_pct(ec['irr'])}</div></div>
      {real_roi_block}
    </div>
  </section>

  <div class="note">
    ※ 단가·노임·유가·총공사비는 조회 시점 실측 <b>주입값</b> 기준(엔진은 시세를 조회하지 않음).
    ROI·NPV·IRR은 <b>추정치</b>이며 투자 확정조언이 아님. 모든 수치의 계산 출처는 smartfarm_engine 단일.
    <details>
      <summary>입력값 원문 보기</summary>
      <pre>{esc(_fmt_echo(res['input_echo']))}</pre>
    </details>
  </div>
</div>
</body>
</html>"""


def _fmt_echo(echo: dict) -> str:
    return "\n".join(f"{k} = {v}" for k, v in echo.items())


# ─────────────────────────────────────────────────────────────
# 3) 데모: 원채원 케이스 (run_report.demo 와 동일 파라미터)
# ─────────────────────────────────────────────────────────────
def demo_input() -> FarmInput:
    return FarmInput(
        business_type=e.BusinessType.NEW,
        crop="토마토", region="충남", area_m2=3456, cover=e.Cover.GLASS,
        snow_cm=30, wind_ms=35,
        surface_area_m2=5000, t_target=10, t_min=-7.8, fr=0.7,
        base_yield_kg_m2=38.5, price_won_per_kg=2500, fitness_pct=95,
        opex=186_420_000, total_construction_cost=702_030_000,
        subsidy_rate=0.5,
    )


def main(out_path: str = "SmartFarm_리포트_원채원.html") -> dict:
    inp = demo_input()
    res = compute(inp)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(render_html(res))
    return res


if __name__ == "__main__":
    r = main()
    ec = r["economics"]
    print(f"HTML 생성 완료 · ROI {ec['roi']:.1%} · "
          f"Payback {ec['payback']:.1f}년 · 실질ROI {ec['real_roi']:.1%}")
