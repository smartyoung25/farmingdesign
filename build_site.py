"""
SmartFarm 리포트 사이트 빌더 (경로 C 마감 + P0 근거대장)
- 계산은 전적으로 smartfarm_engine 에 위임. 이 파일은 렌더/조립만 한다.
- 케이스는 cases/*.json, 엔진 상수 근거는 엔진데이터_레지스트리.json 에서 로드.
- 산출: 케이스별 4축 리포트 · 벤치마크 비교 · 케이스 비교뷰 · 근거대장 · index.html
실행: python build_site.py
"""
from __future__ import annotations
import glob
import html, json, os, re, datetime as _dt
import smartfarm_engine as e
import render_report as rr
from cases import load_cases, case_to_input

esc = html.escape
_CSS = """
  :root{--bg:#f4f6f8;--card:#fff;--ink:#1a2330;--muted:#6b7787;--line:#e3e8ee;
    --brand:#1f7a4d;--brand-soft:#e8f3ec;--ok:#1f7a4d;--warn:#b8860b;--bad:#c0392b;}
  *{box-sizing:border-box;}
  body{margin:0;background:var(--bg);color:var(--ink);
    font-family:-apple-system,"Segoe UI","Malgun Gothic",sans-serif;line-height:1.55;}
  .wrap{max-width:960px;margin:0 auto;padding:28px 20px 64px;}
  header.top{background:var(--brand);color:#fff;border-radius:14px;padding:22px 26px;margin-bottom:22px;}
  header.top h1{margin:0 0 6px;font-size:22px;}
  header.top .sub{opacity:.9;font-size:14px;}
  section.card{background:var(--card);border:1px solid var(--line);border-radius:14px;
    padding:20px 24px;margin-bottom:18px;}
  .axis{display:inline-block;font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--brand);
    background:var(--brand-soft);padding:3px 10px;border-radius:20px;margin-bottom:12px;}
  h2{font-size:17px;margin:0 0 14px;}
  table{width:100%;border-collapse:collapse;font-size:13.5px;}
  th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top;}
  th{color:var(--muted);font-weight:600;font-size:12.5px;}
  td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;}
  .badge{font-size:11.5px;font-weight:700;padding:2px 9px;border-radius:20px;}
  .badge.ok{color:var(--ok);background:#e8f3ec;}
  .badge.warn{color:var(--warn);background:#fbf3dc;}
  .badge.bad{color:var(--bad);background:#fbe6e3;}
  .tag{font-size:11px;font-weight:700;padding:1px 7px;border-radius:6px;white-space:nowrap;}
  .tag.실측{color:var(--ok);background:#e8f3ec;}
  .tag.추정{color:var(--warn);background:#fbf3dc;}
  .tag.확인요망{color:var(--bad);background:#fbe6e3;}
  .tag.부분{color:var(--warn);background:#fbf3dc;}
  .tag.부분실측{color:var(--warn);background:#fbf3dc;}
  .tag.법정기준{color:#1b5aa0;background:#e6f0fb;}
  .tag.공공기준{color:#1b5aa0;background:#e6f0fb;}
  .tag.참고기준{color:#555;background:#efefea;}
  .tag.미검증{color:#7a5cff;background:#efeaff;}
  code{font-size:12px;background:#f2f5f8;padding:1px 5px;border-radius:5px;}
  a.report-link{display:flex;justify-content:space-between;align-items:center;
    padding:14px 16px;border:1px solid var(--line);border-radius:12px;margin-bottom:10px;
    text-decoration:none;color:var(--ink);background:#fafbfc;}
  a.report-link:hover{border-color:var(--brand);}
  a.report-link .t{font-weight:600;}
  a.report-link .d{color:var(--muted);font-size:13px;}
  .note{font-size:12.5px;color:var(--muted);margin-top:18px;padding-top:14px;border-top:1px solid var(--line);}
  .prov li{margin-bottom:4px;font-size:12.5px;color:var(--muted);}
  .row{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px dashed var(--line);font-size:14px;}
  .row:last-child{border-bottom:0;}
  .row .lbl{color:var(--muted);}
  .row .val{font-variant-numeric:tabular-nums;font-weight:600;}
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:6px;}
  .kpi{background:#fafbfc;border:1px solid var(--line);border-radius:12px;padding:14px 16px;}
  .kpi.highlight{background:var(--brand-soft);border-color:#cfe6d8;}
  .kpi-label{font-size:12.5px;color:var(--muted);}
  .kpi-value{font-size:22px;font-weight:700;margin-top:4px;font-variant-numeric:tabular-nums;}
"""


def _sc(s: str) -> str:
    return "ok" if "정상" in s else ("warn" if ("경계" in s or "재확인" in s) else "bad")


def _page(title: str, body: str) -> str:
    gen = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{_CSS}</style></head>
<body><div class="wrap">{body}
<div class="note">계산 출처: smartfarm_engine 단일 · 벤치마크는 실측 ACTUALS 기준 · 생성 {gen}</div>
</div></body></html>"""


def benchmark_page() -> str:
    rows = []
    for name, area, total, cover in e.ACTUALS:
        bc = e.benchmark_check(total, area, cover)
        lo, hi = bc["band"]
        rows.append(
            f"<tr><td>{esc(name)}</td><td>{esc(cover.value)}</td>"
            f"<td class='num'>{area:,}</td><td class='num'>{total:,.0f}</td>"
            f"<td class='num'>{bc['unit_won_m2']:,}</td><td class='num'>{lo:,}~{hi:,}</td>"
            f"<td><span class='badge {_sc(bc['status'])}'>{esc(bc['status'])}</span></td></tr>")
    body = f"""
  <header class="top"><h1>실측 벤치마크 비교 (시공축)</h1>
    <div class="sub">엔진 ACTUALS {len(e.ACTUALS)}건 · 총액÷면적 → 피복별 밴드 대조</div></header>
  <section class="card"><span class="axis">시공축</span>
    <h2>단위 공사비 밴드 대조</h2>
    <table><thead><tr><th>농가</th><th>피복</th><th class='num'>면적(㎡)</th>
      <th class='num'>총공사비(원)</th><th class='num'>단위(원/㎡)</th>
      <th class='num'>밴드(원/㎡)</th><th>판정</th></tr></thead>
      <tbody>{''.join(rows)}</tbody></table>
    <p class="note">밴드: {' / '.join(f"{cov.value} {lo:,}~{hi:,}" for cov, (lo, hi) in e.BENCHMARK_BANDS.items())} (원/㎡).</p>
  </section>
  <p><a class="report-link" href="index.html"><span class="t">← 목록으로</span></a></p>"""
    return _page("실측 벤치마크 비교", body)


def capex_breakdown_page() -> str:
    """CAPEX_CASE_CHUNKS(스마트팜스펙 실측 청킹) → 공종 카테고리별 비중 비교 HTML.
    표본 2건 — '밴드'가 아니라 '관측범위'(참고정보)로만 표시. 정상/경고 판정 없음."""
    cat_rows = []
    for key, kor in e.CAPEX_CATEGORIES:
        lo, hi = e.CAPEX_CATEGORY_OBSERVED_RANGE[key]
        per_case = []
        for case_name, chunks in e.CAPEX_CASE_CHUNKS.items():
            cb = e.capex_breakdown(chunks)
            per_case.append(f"{esc(case_name)} {cb.shares_pct[key]:.1f}%")
        cat_rows.append(
            f"<tr><td>{esc(kor)}</td><td><code>{esc(key)}</code></td>"
            f"<td class='num'>{lo:.1f}~{hi:.1f}%</td><td>{' · '.join(per_case)}</td></tr>")
    case_rows = []
    for case_name, chunks in e.CAPEX_CASE_CHUNKS.items():
        cb = e.capex_breakdown(chunks)
        case_rows.append(
            f"<tr><td>{esc(case_name)}</td><td class='num'>{cb.total:,.0f}</td>"
            f"<td>{', '.join(f'{esc(k)} {v:.1f}%' for k, v in cb.shares_pct.items())}</td></tr>")

    # 13개 상위(총사업비) 카테고리 — 2026-07-16 사용자 제안 채택
    # known_total은 엔진 상수 CAPEX_MAJOR_KNOWN_TOTALS가 단일 출처(2026-08-18 53차,
    # 레드팀 4회차 F8: 이중 하드코딩 제거 — 케이스별 근거 주석은 엔진 상수 쪽 참조)
    major_totals = e.CAPEX_MAJOR_KNOWN_TOTALS
    major_rows = []
    for key, kor, desc in e.CAPEX_MAJOR_CATEGORIES:
        ev = e.CAPEX_MAJOR_EVIDENCE_STATUS[key]
        tag = "실측" if ev.startswith("실측") else ("추정" if ev.startswith("부분") else "미검증")
        per_case = []
        for case_name, total in major_totals.items():
            mb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS[case_name], known_total=total)
            per_case.append(f"{esc(case_name)} {mb.shares_pct[key]:.1f}%")
        major_rows.append(
            f"<tr><td>{esc(kor)}</td><td>{esc(desc)}</td>"
            f"<td><span class='tag {tag}'>{esc(ev)}</span></td><td>{' · '.join(per_case)}</td></tr>")
    unclassified_rows = []
    for case_name, total in major_totals.items():
        mb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS[case_name], known_total=total)
        if mb.unclassified == 0:  # 7회차 부수⑵: 0원에 "미분류로 남김" 서술은 오독 — 표시 분기(포맷팅)
            unclassified_rows.append(
                f"<li>{esc(case_name)}: 0원 (0.0%) — 미분류 없음(전 공종이 13분류로 매핑됨)</li>")
        else:
            unclassified_rows.append(
                f"<li>{esc(case_name)}: {mb.unclassified:,.0f}원 "
                f"({mb.unclassified/mb.total*100:.1f}%) — 13개 카테고리 어디에도 안 맞아 미분류로 남김"
                f"(케이스별 구체 항목은 CAPEX_MAJOR_UNCLASSIFIED 레지스트리 source 참고)</li>")

    body = f"""
  <header class="top"><h1>CAPEX 공종 카테고리 분해</h1>
    <div class="sub">스마트팜스펙/ 원본 내역서 실측 청킹 {len(e.CAPEX_CASE_CHUNKS)}건 · 총사업비 13분류(상위) + 공종 9분류(하위) 2계층 · 직접공사비(순공사비) 기준</div></header>
  <section class="card"><span class="axis">총사업비 관점 · 13개 상위 카테고리</span>
    <h2>1~13번 카테고리 (2026-07-16 채택 — 부지매입비는 finance()에서 감가상각 제외 별도 처리)</h2>
    <table><thead><tr><th>카테고리</th><th>설명</th><th>근거 상태</th><th>케이스별 비중</th></tr></thead>
      <tbody>{''.join(major_rows)}</tbody></table>
    <p class="note">근거 없는 7개 항목(7·9·10·11·12·13, 5·6 일부)은 값을 만들지 않고 0으로 둔다 —
      해당 문서(총사업비 산정표·설계감리 계약서·토지매매계약서 등) 확보 시 갱신.</p>
    <p class="note"><b>미분류(unclassified) 잔액</b>(13개 어디에도 안 맞는 원문 항목):</p>
    <ul class="prov">{''.join(unclassified_rows)}</ul>
    <p class="note">⚠️ 0.0%는 "설비 부재"가 아니라 "이 견적의 직접공사비 분모에 해당 공종이 없음"이다 —
      한일그린텍 hvac 0.0%가 대표 사례: 공기유동휀 12대·배출환풍기 6대가 실재하나 부가세 환급분
      재투자 블록(22,635,750원, 직접공사비 밖 별도 계상)에 있어 분모에 안 잡힌다(레드팀 4회차 F6,
      원문 p5·p20 — 상세는 근거대장 CAPEX_MAJOR_CASE_CHUNKS 항목).</p>
    <p class="note">⚠️ 강정구·오기수는 <b>견적 범위 자체가 좁은 부분 범위 견적</b>이라 비중을 풀스펙 표본과
      같은 축으로 읽으면 안 된다 — 강정구는 골조 쪽만(골조·천창개폐·피복+관리동 부속, 온실구조 74.8%),
      오기수는 설비 쪽만(컨트롤박스·커튼·행잉거터·양액·관수·환경제어 — 골조·피복 0%)으로 서로 상보적인 쌍이다.
      둘 다 ㈜서진비에스 견적(2022-04·2023-08)이라 동일 업체 시계열 관찰도 가능하나 물가 시점이
      각각 다르다(레드팀 7회차 F6·57차 — 상세는 근거대장).</p>
    <p class="note">⚠️ 케이스 간 비중 비교 시 분모(known_total) 구성이 문서 구조에 따라 다르다 —
      우민재는 qa_safety(안전관리비 등 2,679,227원)가 공종 라인으로 분모에 포함되지만, 한일그린텍
      (산업안전보건관리비 1,440,000원)·이준희(산업안전 27,047,871원+환경보전 5,051,685원=32,099,556원)·
      맹주연(안전관리비 9,865,947원+환경보전비 2,198,711원=12,064,658원)·강정구(안전관리비
      8,526,681원)·오기수(안전관리비 5,763,255원)·백가은·조윤정(산업안전보건관리비 8,017,698원)은
      같은 성격 비용이 원가계산서 산식 항목이라 분모 밖이다(레드팀 4~8회차·59차 관찰 — 비중의
      한 자리 수준 차이는 이 구조 차이만으로도 생길 수 있다).</p>
  </section>
  <section class="card"><span class="axis">시공사 내역서 관점 · 9개 하위 세부(직접공사비)</span>
    <h2>카테고리별 비중 관측범위 (표본 {len(e.CAPEX_CASE_CHUNKS)}건 — 밴드 아님, 참고정보)</h2>
    <table><thead><tr><th>카테고리</th><th>키</th><th class='num'>관측범위</th><th>케이스별 실측 비중</th></tr></thead>
      <tbody>{''.join(cat_rows)}</tbody></table>
  </section>
  <section class="card"><span class="axis">원본 케이스</span>
    <h2>케이스별 직접공사비 합계 · 전체 비중</h2>
    <table><thead><tr><th>케이스</th><th class='num'>직접공사비(원)</th><th>카테고리 비중</th></tr></thead>
      <tbody>{''.join(case_rows)}</tbody></table>
    <p class="note">직접공사비(재료비+노무비+경비) 기준 — 간접노무비·4대보험·일반관리비·이윤·부가세 등 제경비는
      <code>apply_overheads()</code> 별도 처리. 표본 2건뿐이라 관측범위는 정상/경고 판정에 쓰지 않는다(참고정보).
      원문 근거는 <a href="SmartFarm_근거대장.html">엔진 상수 근거대장</a>의 CAPEX_CATEGORY_OBSERVED_RANGE·CAPEX_CASE_CHUNKS 항목 참고.</p>
  </section>
  <p><a class="report-link" href="index.html"><span class="t">← 목록으로</span></a></p>"""
    return _page("CAPEX 공종 카테고리 분해", body)


def _trunc(s: str, n: int = 160) -> str:
    return s if len(s) <= n else s[:n].rstrip() + "…"


def _prov_flags(case: dict) -> list[tuple[str, str, str]]:
    """provenance 중 status != '실측'인 항목만 (필드명, status, 근거 요약) 튜플로."""
    return [(k, v["status"], _trunc(v.get("source", "")))
            for k, v in case.get("provenance", {}).items() if v.get("status") != "실측"]


# 시나리오 가정값 스키마(2026-08-18, 데이터 대기 ④) — 허용 필드 화이트리스트.
# 판단성·시세성 입력만 바꿀 수 있다. 물리·구조 입력(지역·하중·피복·면적)은
# 시나리오가 아니라 다른 케이스이므로 거부한다. 상세: 시나리오_가정값_기입양식.md
SCENARIO_ALLOWED_FIELDS = {"base_yield_kg_m2", "price_won_per_kg", "opex",
                           "fitness_pct", "subsidy_rate", "total_construction_cost"}


def scenario_rows(case: dict, inp) -> list[dict]:
    """케이스 scenarios 블록 → Base 포함 시나리오별 KPI 행(계산은 전부 엔진 재호출).
    화이트리스트 밖 키·근거(note) 누락은 ValueError — 조용히 넘어가지 않는다."""
    import dataclasses
    sc = case.get("scenarios")
    if not sc:
        return []
    rows = []
    base_res = rr.compute(inp)
    rows.append({"name": "Base(케이스 입력)", "assumptions": {}, "note": "케이스 input 원값",
                 "res": base_res})
    for s in sc.get("sets", []):
        bad = set(s.get("assumptions", {})) - SCENARIO_ALLOWED_FIELDS
        if bad:
            raise ValueError(
                f"시나리오 '{s.get('name')}'에 허용되지 않는 가정 필드 {sorted(bad)} — "
                f"화이트리스트: {sorted(SCENARIO_ALLOWED_FIELDS)}(기입양식.md 1절)")
        if not (s.get("note") or "").strip():
            raise ValueError(f"시나리오 '{s.get('name')}'에 근거(note)가 없다 — 가정값은 근거 필수")
        mod = dataclasses.replace(inp, **s["assumptions"])
        rows.append({"name": s["name"], "assumptions": s["assumptions"],
                     "note": s["note"], "res": rr.compute(mod)})
    return rows


def _sensitivity_snapshot(inp) -> list[dict]:
    """판매단가·수확량 ±10% 스냅샷 — 새 데이터 없이 기존 production_kg()/finance()를
    다른 인자로 다시 호출할 뿐이다(케이스 스키마·엔진 레지스트리 변경 없음)."""
    scenarios = [
        ("기준", inp.price_won_per_kg, inp.base_yield_kg_m2),
        ("판매단가 +10%", inp.price_won_per_kg * 1.1, inp.base_yield_kg_m2),
        ("판매단가 -10%", inp.price_won_per_kg * 0.9, inp.base_yield_kg_m2),
        ("수확량 +10%", inp.price_won_per_kg, inp.base_yield_kg_m2 * 1.1),
        ("수확량 -10%", inp.price_won_per_kg, inp.base_yield_kg_m2 * 0.9),
    ]
    rows = []
    for label, price, base_yield in scenarios:
        prod = e.production_kg(inp.area_m2, base_yield, inp.fitness_pct)
        revenue = prod * price
        fin = e.finance(revenue, inp.opex, inp.total_construction_cost,
                        subsidy_rate=inp.subsidy_rate)
        rows.append({"label": label, "revenue": revenue, "roi": fin.roi,
                     "payback": fin.payback_years})
    return rows


def consulting_report_page(case: dict, res: dict, inp) -> str:
    """4섹션 통합 컨설팅 리포트(Step6, 2026-07-21) — 표지+경영자요약 뒤에
    입지진단서·설계적정성보고서·운영계획서·경제성분석서를 잇는다.
    새 계산은 render_report.compute()가 이미 만든 res를 그대로 재사용하고,
    손익분기·민감도 스냅샷만 기존 엔진 함수를 다시 호출해 더한다 — 케이스
    스키마·엔진 레지스트리는 건드리지 않는다(2026-07-21 사용자 확인 범위)."""
    m, d, h, c, ec = res["meta"], res["design"], res["heating"], res["construction"], res["economics"]
    capex = c["total"]
    subsidy_won = capex * ec["subsidy_rate"]
    self_funded_won = capex - subsidy_won
    cash_flow = ec["operating_profit"] + ec["depreciation"]
    be = e.operating_breakeven(ec["opex"], ec["price"])
    flags = _prov_flags(case)

    # ── 표지 + 경영자 요약 ──
    flags_html = "".join(
        f"<li><code>{esc(k)}</code> <span class='tag {esc(st)}'>{esc(st)}</span> — {esc(src)}</li>"
        for k, st, src in flags[:8])
    more_note = f"<p class='note'>그 외 {len(flags)-8}건 더 — 케이스 JSON provenance 전체 참고</p>" if len(flags) > 8 else ""
    summary = f"""
  <header class="top"><h1>스마트팜 ROI 통합보고서</h1>
    <div class="sub">{esc(case['title'])} · {esc(m['business_type'])} · {esc(m['crop'])} · 기준시점 {esc(case.get('as_of','—'))}</div></header>
  <section class="card"><span class="axis">경영자 요약</span>
    <h2>핵심 결과</h2>
    <div class="kpis">
      <div class="kpi"><div class="kpi-label">총사업비(CAPEX)</div><div class="kpi-value">{capex/1e8:,.2f}억</div></div>
      <div class="kpi"><div class="kpi-label">정부보조금 ({ec['subsidy_rate']*100:.0f}%)</div><div class="kpi-value">{subsidy_won/1e8:,.2f}억</div></div>
      <div class="kpi"><div class="kpi-label">자부담</div><div class="kpi-value">{self_funded_won/1e8:,.2f}억</div></div>
      <div class="kpi"><div class="kpi-label">연매출</div><div class="kpi-value">{ec['revenue']/1e8:,.2f}억</div></div>
      <div class="kpi"><div class="kpi-label">연간 OPEX</div><div class="kpi-value">{ec['opex']/1e8:,.2f}억</div></div>
      <div class="kpi"><div class="kpi-label">영업현금흐름</div><div class="kpi-value">{cash_flow/1e8:,.2f}억</div></div>
      <div class="kpi highlight"><div class="kpi-label">ROI · Payback</div>
        <div class="kpi-value">{ec['roi']*100:.1f}% · {f"{ec['payback']:.1f}년" if ec['payback'] else "N/A"}</div></div>
      <div class="kpi highlight"><div class="kpi-label">NPV(10y·5%) · IRR</div>
        <div class="kpi-value">{ec['npv']/1e8:,.2f}억 · {f"{ec['irr']*100:.1f}%" if ec['irr'] is not None else ">100%"}</div></div>
    </div>
    <p class="note">손익분기 매출 {be.breakeven_revenue_won:,.0f}원(=연간 OPEX) · 손익분기 생산량 {be.breakeven_kg:,.0f}kg —
      CAPEX 회수(Payback)와 별개로 '그 해 매출이 운영비를 커버하는 지점'만 본다.</p>
    <h2 style="margin-top:16px">확인 필요 항목 ({len(flags)}건)</h2>
    <ul class="prov">{flags_html}</ul>{more_note}
    <p class="note">위 목록은 케이스 provenance에서 상태≠'실측'인 항목을 그대로 모은 것이다 — 위험도·우선순위를
      엔진이 판정하지 않는다(판단성 영역, 컨설턴트 검토 필요). 최종 투자 적정성 판정도 이 리포트는 내리지 않는다 —
      아래 4개 섹션과 벤치마크 상태만 중립적으로 제시한다.</p>
  </section>"""

    # ── Ⅰ. 입지진단서 ──
    site = case.get("site", {})
    siting = f"""
  <section class="card"><span class="axis">Ⅰ. 입지진단서</span>
    <h2>부지·설계기준</h2>
    <div class="row"><span class="lbl">부지</span><span class="val">{esc(site.get('region_name', m['region']))}</span></div>
    <div class="row"><span class="lbl">설계기준(적설·풍속)</span><span class="val">{d['snow_cm']}cm · {d['wind_ms']}m/s</span></div>
    <div class="row"><span class="lbl">설계기준 출처</span><span class="val">{esc(_trunc(site.get('design_load_source', '미확인'), 220))}</span></div>
    <div class="row"><span class="lbl">용도지역</span><span class="val">{esc(site.get('landuse_zone', '미확인'))}</span></div>
    <div class="row"><span class="lbl">계통연계</span><span class="val">{esc(site.get('grid_connection_note', '미확인'))}</span></div>
    <p class="note">규제·인프라 상세 체크리스트(도로진입·민원·인허가)는 이 리포트 범위 밖 — 향후 확장 과제(작업지시서 7절 참고).</p>
  </section>"""

    # ── Ⅱ. 설계적정성보고서 ──
    forms_rows = "".join(
        f"<tr><td>{esc(form)}</td><td>{esc(info['name'])}</td>"
        f"<td>설계적설심 {info['snow']}cm · 설계풍속 {info['wind']}m/s</td></tr>"
        for form, info in d["min_by_form"].items())
    design = f"""
  <section class="card"><span class="axis">Ⅱ. 설계적정성보고서</span>
    <h2>규격·난방부하·개산단가</h2>
    <table><thead><tr><th>형식</th><th>최소사양</th><th>설계강도</th></tr></thead>
      <tbody>{forms_rows}</tbody></table>
    <div class="row"><span class="lbl">최대난방부하</span><span class="val">{h['max_load']:,.0f} kcal/h ({h['load_per_m2']:,.0f}/㎡)</span></div>
    <div class="row"><span class="lbl">실측 대조</span>
      <span class="badge {_sc(h['status'])}">{esc(h['status'])}</span></div>
    <div class="row"><span class="lbl">총공사비 단위단가</span><span class="val">{c['unit_won_m2']:,}원/㎡</span></div>
    <div class="row"><span class="lbl">벤치마크({c['band'][0]:,}~{c['band'][1]:,}원/㎡)</span>
      <span class="badge {_sc(c['status'])}">{esc(c['status'])}</span></div>
  </section>"""

    # ── Ⅲ. 운영계획서 ──
    ob = case.get("opex_breakdown", {})
    ob_items = ob.get("items_won", {})
    ob_rows = "".join(f"<tr><td>{esc(k)}</td><td class='num'>{v:,.0f}</td></tr>" for k, v in ob_items.items())
    ob_rows += f"<tr><td>미분류(unclassified)</td><td class='num'>{ob.get('unclassified_won', ec['opex']):,.0f}</td></tr>"
    subsidy_rows = "".join(
        f"<tr><td>{s.step_no}</td><td>{esc(s.title)}</td><td>{esc(s.description)}</td></tr>"
        for s in e.SUBSIDY_APPLICATION_PROCEDURE)
    ops = f"""
  <section class="card"><span class="axis">Ⅲ. 운영계획서</span>
    <h2>생산·운영비 개요</h2>
    <div class="row"><span class="lbl">환경적합도 → 수율조정</span><span class="val">{ec['fitness_pct']:.0f}% → {ec['yield_adj']*100:+.0f}%</span></div>
    <div class="row"><span class="lbl">예상 생산량</span><span class="val">{ec['production_kg']:,.0f} kg</span></div>
    <table><thead><tr><th>OPEX 항목</th><th class='num'>금액(원)</th></tr></thead>
      <tbody>{ob_rows}</tbody></table>
    <p class="note">{esc(ob.get('note', 'OPEX 항목분해 자료 없음'))}</p>
    <h2 style="margin-top:16px">사업 착수 전 행정절차 (보조율 수치 미포함 — 공모 회차마다 상이)</h2>
    <table><thead><tr><th>#</th><th>절차</th><th>내용</th></tr></thead>
      <tbody>{subsidy_rows}</tbody></table>
  </section>"""

    # ── Ⅳ. 경제성분석서 ──
    sens_rows = "".join(
        f"<tr><td>{esc(s['label'])}</td><td class='num'>{s['revenue']:,.0f}</td>"
        f"<td class='num'>{s['roi']*100:.1f}%</td>"
        f"<td class='num'>{f'{s['payback']:.1f}년' if s['payback'] else '—'}</td></tr>"
        for s in _sensitivity_snapshot(inp))
    real_roi_row = ""
    if ec["real_roi"]:
        real_roi_row = (f"<div class='kpi highlight'><div class='kpi-label'>실질ROI(보조금 반영)</div>"
                        f"<div class='kpi-value'>{ec['real_roi']*100:.1f}%</div></div>")
    capex_kor = dict((key, kor) for key, kor, _ in e.CAPEX_MAJOR_CATEGORIES)
    cb = case.get("capex_breakdown", {})
    cb_cats = cb.get("major_categories_won_2026_07_16", {})
    capex_detail = ""
    if cb_cats:
        cb_rows = "".join(
            f"<tr><td>{esc('미분류(unclassified)' if k == 'unclassified' else capex_kor.get(k, k))}</td>"
            f"<td class='num'>{v:,.0f}</td></tr>"
            for k, v in cb_cats.items() if k != "note")
        capex_detail = f"""
    <h2 style="margin-top:16px">CAPEX 항목분해(실측 청킹, {esc(cb.get('as_of','—'))})</h2>
    <table><thead><tr><th>카테고리</th><th class='num'>금액(원)</th></tr></thead>
      <tbody>{cb_rows}</tbody></table>
    <p class="note">{esc(_trunc(cb_cats.get('note', ''), 300))}</p>"""
    else:
        capex_detail = "<p class='note'>이 케이스엔 CAPEX 항목분해 실측 데이터가 없어 총사업비만 표시(CAPEX_CASE_CHUNKS 확보된 케이스는 자동으로 이 표가 채워짐).</p>"
    # 시나리오 가정값(2026-08-18): scenarios 블록이 있는 케이스만 다단 표 렌더
    sc_rows_data = scenario_rows(case, inp)
    if sc_rows_data:
        def _fmt_assum(a):
            return " · ".join(f"{k}={v:,}" if isinstance(v, (int, float)) else f"{k}={v}"
                              for k, v in a.items()) or "—"
        def _sc_tr(r):
            ec = r["res"]["economics"]
            pb = f"{ec['payback']:.1f}년" if ec["payback"] else "—"
            # IRR None은 이분법 수렴 실패 — 흑자면 초고수익(>100%), 적자면 산출불가.
            # 기존 ">100%" 단일 표기는 적자 시나리오에서 정반대 오독을 낳는다(2026-08-18 발견)
            if ec["irr"] is not None:
                irr = f"{ec['irr']*100:.1f}%"
            else:
                irr = ">100%" if ec["npv"] > 0 else "산출불가(적자)"
            return (f"<tr><td>{esc(r['name'])}</td>"
                    f"<td style='font-size:12px'>{esc(_fmt_assum(r['assumptions']))}</td>"
                    f"<td class='num'>{ec['roi']*100:.1f}%</td><td class='num'>{pb}</td>"
                    f"<td class='num'>{ec['npv']/1e8:,.2f}억</td><td class='num'>{irr}</td></tr>")
        sc_tr = "".join(_sc_tr(r) for r in sc_rows_data)
        sc_notes = "".join(f"<li>{esc(r['name'])}: {esc(r['note'])}</li>" for r in sc_rows_data[1:])
        scenario_detail = f"""
    <h2 style="margin-top:16px">시나리오 표 (가정 주입 — {len(sc_rows_data)}단)</h2>
    <table><thead><tr><th>시나리오</th><th>가정(변경 필드만)</th><th class='num'>ROI</th>
      <th class='num'>Payback</th><th class='num'>NPV</th><th class='num'>IRR</th></tr></thead>
      <tbody>{sc_tr}</tbody></table>
    <ul class="prov">{sc_notes}</ul>
    <p class="note">{esc(_trunc(case['scenarios'].get('note', ''), 240))} — 가정값은 컨설턴트 기입(판단성),
      계산은 전 지표 엔진 재호출. 어느 시나리오의 실현을 판정하지 않으며 확률·기대값은 모델링하지 않는다.</p>"""
    else:
        scenario_detail = ("<p class='note'>시나리오 가정값 미제공 — 케이스에 scenarios 블록(가정 세트+근거)을 "
                           "넣으면 Best/Worst 다단 표가 자동 생성된다(시나리오_가정값_기입양식.md, 가정 창작 금지).</p>")
    # P3-18(2026-08-17): 금융조달 — financing 블록이 있는 케이스만 상환표 렌더
    fin = case.get("financing")
    if fin:
        am = e.loan_amortization(fin["loan_principal_won"], fin["annual_rate_pct"],
                                 fin["term_years"], fin.get("grace_years", 0),
                                 fin.get("method", "원리금균등"))
        fin_rows = "".join(
            f"<tr><td class='num'>{row['연차']}</td><td>{esc(row['구분'])}</td>"
            f"<td class='num'>{row['원금']:,.0f}</td><td class='num'>{row['이자']:,.0f}</td>"
            f"<td class='num'>{row['납입액']:,.0f}</td><td class='num'>{row['잔액']:,.0f}</td></tr>"
            for row in am["rows"])
        financing_detail = f"""
    <h2 style="margin-top:16px">금융조달 — 연차별 대출상환표 ({esc(am['방식'])}, 연 {am['연이율_pct']}% · {am['전체기간_년']}년{f" · 거치 {am['거치기간_년']}년" if am['거치기간_년'] else ""})</h2>
    <table><thead><tr><th class='num'>연차</th><th>구분</th><th class='num'>원금(원)</th>
      <th class='num'>이자(원)</th><th class='num'>납입액(원)</th><th class='num'>잔액(원)</th></tr></thead>
      <tbody>{fin_rows}</tbody></table>
    <div class="row"><span class="lbl">총이자 / 총납입액</span>
      <span class="val">{am['총이자']:,.0f}원 / {am['총납입액']:,.0f}원</span></div>
    <p class="note">{esc(_trunc(fin.get('note', '대출조건 출처 미기재'), 240))}</p>"""
    else:
        financing_detail = ("<p class='note'>대출조건 미제공 — 케이스에 financing 블록(대출금액·금리·"
                            "전체/거치기간·상환방식)을 넣으면 연차별 상환표가 자동 생성된다"
                            "(엔진 loan_amortization, 가공 조건은 채우지 않음).</p>")
    # P1-6 잔여 해소(2026-08-18, 사용자 결정: 참고 표시 전용 — CAPEX 불산입)
    sup = e.design_supervision_fee_reference(case["input"]["total_construction_cost"])
    if sup:
        sup_rows = "".join(
            f"<tr><td>{esc(g)}</td><td class='num'>{sup['요율_pct'][g]:.4f}%</td>"
            f"<td class='num'>{sup['감리비_원'][g]:,.0f}</td></tr>"
            for g in e.SUPERVISION_FEE_GRADES)
        supervision_detail = f"""
    <h2 style="margin-top:16px">설계·감리비 참고(법정요율 — CAPEX 불산입)</h2>
    <table><thead><tr><th>종별(별표3 난이도)</th><th class='num'>요율</th>
      <th class='num'>감리비 추정(원)</th></tr></thead>
      <tbody>{sup_rows}</tbody></table>
    <p class="note">「공공발주사업에 대한 건축사의 업무범위와 대가기준」(국토교통부고시 제2020-635호)
      별표5·제16조({esc(sup['산정구간'])}) 적용 참고 추정. 별표5의 '공사비'는 부가가치세·용지비 등을
      제외한 금액 정의 — 케이스 공사비에 부가세가 포함돼 있으면 과대 추정이다. 종별(단순~복잡)
      선택은 난이도 판단(판단성), 실제 감리 계약액은 협의(시세성) — 이 표는 CAPEX 합계·투자지표에
      산입하지 않는다(design_supervision_fee 값 0 유지).</p>"""
    else:
        supervision_detail = ""
    econ = f"""
  <section class="card"><span class="axis">Ⅳ. 경제성분석서</span>
    <h2>투자지표 · 민감도 스냅샷</h2>
    <div class="kpis">
      <div class="kpi"><div class="kpi-label">ROI</div><div class="kpi-value">{ec['roi']*100:.1f}%</div></div>
      <div class="kpi"><div class="kpi-label">Payback</div><div class="kpi-value">{f"{ec['payback']:.1f}년" if ec['payback'] else "N/A"}</div></div>
      <div class="kpi"><div class="kpi-label">NPV</div><div class="kpi-value">{ec['npv']/1e8:,.2f}억</div></div>
      <div class="kpi"><div class="kpi-label">IRR</div><div class="kpi-value">{f"{ec['irr']*100:.1f}%" if ec['irr'] is not None else ">100%"}</div></div>
      {real_roi_row}
    </div>
    <table style="margin-top:14px"><thead><tr><th>시나리오</th><th class='num'>연매출</th>
      <th class='num'>ROI</th><th class='num'>Payback</th></tr></thead>
      <tbody>{sens_rows}</tbody></table>
    <p class="note">판매단가·수확량 ±10% 단순 스냅샷(엔진 재호출, 새 입력 없음). Best/Worst 시나리오 표는
      가정값 주입 시 아래 렌더(2026-08-18 편입), 대출상환표는 P3-18 편입 — 각 섹션 참고.</p>
    {scenario_detail}
    {financing_detail}
    {supervision_detail}
    {capex_detail}
  </section>"""

    body = summary + siting + design + ops + econ + \
        "\n  <p><a class=\"report-link\" href=\"index.html\"><span class=\"t\">← 목록으로</span></a></p>"
    return _page(f"스마트팜 ROI 통합보고서 — {case['title']}", body)


def partial_construction_page(case: dict) -> str:
    """P3-21d(2026-08-17): 시공축 전용 부분 케이스 리포트.
    입지·운영·경제성 데이터가 없는 케이스는 4축 통합보고서를 만들지 않고(가공값
    금지), 확보된 시공축 실측만 렌더한다. 계산은 엔진 benchmark_check만 사용."""
    inp = case["input"]
    con = case["construction"]
    total = inp["total_construction_cost"]
    area = inp["area_m2"]
    bench = e.benchmark_check(total, area, e.Cover(inp["cover"]))
    summary_rows = "".join(
        f"<div class='row'><span class='lbl'>{esc(k)}</span>"
        f"<span class='val'>{v:,.0f}원</span></div>"
        for k, v in con["cost_summary_won"].items())
    trade_rows = "".join(
        f"<tr><td>{esc(k)}</td><td class='num'>{v:,.0f}</td></tr>"
        for k, v in con["trades_material_won"].items())
    body = f"""
  <header class="top"><h1>{esc(case['title'])}</h1>
    <div class="sub">시공축 부분 케이스 · {esc(inp['crop'])} · {area:,.1f}㎡ ({e.m2_to_py(area):,.0f}평) · {esc(inp['cover'])}</div></header>
  <section class="card"><span class="axis">부분 케이스 안내</span>
    <h2>이 리포트의 범위</h2>
    <p style="font-size:13.5px">{esc(case['partial_note'])}</p></section>
  <section class="card"><span class="axis">시공 — 규격</span>
    <h2>실측 규격</h2>
    <p style="font-size:13.5px">{esc(con['spec_note'])}</p></section>
  <section class="card"><span class="axis">시공 — 공사비</span>
    <h2>공사원가 요약 (원문 전사)</h2>
    {summary_rows}
    <div class="row"><span class="lbl">벤치마크(총액 기준)</span>
      <span class="val">{bench['unit_won_m2']:,}원/㎡ — <span class="badge {_sc(bench['status'])}">{esc(bench['status'])}</span> (밴드 {bench['band'][0]:,}~{bench['band'][1]:,})</span></div>
    <h2 style="margin-top:16px">공종·항목 발췌 (원문 전사 — 대사 범위는 노트 참고)</h2>
    <table><thead><tr><th>공종·항목(원문)</th><th class="num">금액(원)</th></tr></thead>
      <tbody>{trade_rows}</tbody></table>
    <p class="note">{esc(con['trades_note'])}</p></section>
  <section class="card"><span class="axis">근거</span>
    <h2>출처·검증</h2>
    {_partial_provenance_html(case)}</section>
  <p><a class="report-link" href="index.html"><span class="t">← 목록으로</span></a></p>"""
    return _page(case["title"], body)


def _partial_provenance_html(case: dict) -> str:
    """43차 provenance 스키마 통일 대응 — dict형(필드별 status·source·source_refs)이면
    표로, 원문 서술은 provenance_note로 병기. 구 문자열형도 하위호환 렌더."""
    prov = case.get("provenance")
    note = case.get("provenance_note")
    parts = []
    if isinstance(prov, dict):
        rows = []
        for field, v in prov.items():
            refs = "".join(f"<div style='font-size:11px'><code>{esc(r['file'])}</code></div>"
                           for r in v.get("source_refs", []))
            rows.append(f"<tr><td><code>{esc(field)}</code></td>"
                        f"<td><span class='tag {esc(v['status'])}'>{esc(v['status'])}</span></td>"
                        f"<td style='font-size:12.5px'>{esc(v['source'])}{refs}</td></tr>")
        parts.append(f"<table><thead><tr><th>항목</th><th>상태</th><th>근거·원문</th></tr></thead>"
                     f"<tbody>{''.join(rows)}</tbody></table>")
    elif isinstance(prov, str):
        parts.append(f"<p style='font-size:13px;color:var(--muted)'>{esc(prov)}</p>")
    if note:
        parts.append(f"<p class='note'>{esc(note)}</p>")
    return "\n    ".join(parts)


def comparison_page(computed: list[dict]) -> str:
    head = ("<tr><th>케이스</th><th class='num'>단위공사비</th><th>벤치마크</th>"
            "<th class='num'>난방/㎡</th><th class='num'>ROI</th><th class='num'>Payback</th>"
            "<th class='num'>NPV(억)</th><th class='num'>IRR</th><th class='num'>실질ROI</th></tr>")
    rows = []
    for item in computed:
        c, res = item["case"], item["res"]
        con, h, ec = res["construction"], res["heating"], res["economics"]
        pb = f"{ec['payback']:.1f}년" if ec["payback"] else "—"
        rr_ = f"{ec['real_roi']*100:.1f}%" if ec["real_roi"] else "—"
        npv_t = f"{ec['npv']/1e8:.2f}" if ec["npv"] is not None else "—"
        irr_t = f"{ec['irr']*100:.1f}%" if ec["irr"] is not None else ">100%"
        rows.append(
            f"<tr><td>{esc(c['title'])}</td>"
            f"<td class='num'>{con['unit_won_m2']:,}</td>"
            f"<td><span class='badge {_sc(con['status'])}'>{esc(con['status'])}</span></td>"
            f"<td class='num'>{h['load_per_m2']:,.0f}</td>"
            f"<td class='num'>{ec['roi']*100:.1f}%</td><td class='num'>{pb}</td>"
            f"<td class='num'>{npv_t}</td><td class='num'>{irr_t}</td>"
            f"<td class='num'>{rr_}</td></tr>")
    prov = []
    for item in computed:
        c = item["case"]
        flags = [f"{k}=<span class='tag {v['status']}'>{v['status']}</span>"
                 for k, v in c.get("provenance", {}).items() if v["status"] != "실측"]
        line = f"<b>{esc(c['title'])}</b> · 기준시점 {esc(c.get('as_of','—'))}"
        if flags:
            line += " · 미검증: " + ", ".join(flags)
        prov.append(f"<li>{line}</li>")
    body = f"""
  <header class="top"><h1>케이스 비교 뷰</h1>
    <div class="sub">{len(computed)}개 케이스 · 4축 핵심 KPI 나란히 비교 · 계산 출처 엔진 단일</div></header>
  <section class="card"><span class="axis">경제성·시공·설계</span>
    <h2>핵심 KPI 대조</h2>
    <table><thead>{head}</thead><tbody>{''.join(rows)}</tbody></table>
  </section>
  <section class="card"><span class="axis">근거 대장 (주입값)</span>
    <h2>케이스 주입값 기준시점 · 상태 태그</h2>
    <ul class="prov">{''.join(prov)}</ul>
    <p class="note">태그: <span class="tag 실측">실측</span> ·
      <span class="tag 추정">추정</span> · <span class="tag 확인요망">확인요망</span>. 실측 외 항목만 표기.</p>
  </section>
  <p><a class="report-link" href="index.html"><span class="t">← 목록으로</span></a></p>"""
    return _page("케이스 비교 뷰", body)


def registry_page() -> str:
    """엔진데이터_레지스트리.json → 엔진 상수 근거대장 HTML. 값은 test_registry 로 엔진과 대조됨."""
    reg = json.load(open("엔진데이터_레지스트리.json", encoding="utf-8"))
    rows = []
    for key, c in reg["constants"].items():
        val = c["value"]
        if isinstance(val, dict):
            vtxt = ", ".join(f"{k}={v}" for k, v in val.items())
        else:
            vtxt = str(val)
        # 42차: source_refs(원문 역참조 — 리포 실재 파일만 등록, 드리프트 가드로 검증)
        refs = c.get("source_refs") or []
        _match_badge = {"near": " <b>[근접]</b>", "partial": " <b>[부분]</b>"}
        refs_html = "".join(
            f"<div style='font-size:11.5px'><code>{esc(r['file'])}</code>"
            f"{_match_badge.get(r.get('match'), '')}"
            f"{(' — ' + esc(r['note'])) if r.get('note') else ''}</div>" for r in refs) or "—"
        rows.append(
            f"<tr><td><code>{esc(key)}</code></td><td>{esc(c['axis'])}</td>"
            f"<td>{esc(c['desc'])}</td><td>{esc(vtxt)}</td>"
            f"<td>{esc(c['source'])}</td>"
            f"<td>{refs_html}</td>"
            f"<td><span class='tag {c['status']}'>{esc(c['status'])}</span>"
            f"{('<div style=' + chr(39) + 'font-size:11px;color:var(--muted);max-width:220px' + chr(39) + '>' + esc(_trunc(c.get('status_note', ''), 160)) + '</div>') if c.get('status_note') else ''}</td></tr>")
    n_unver = sum(1 for c in reg["constants"].values() if c["status"] == "미검증")
    body = f"""
  <header class="top"><h1>엔진 상수 근거대장 (P0)</h1>
    <div class="sub">기준시점 {esc(reg['as_of'])} · {len(reg['constants'])}개 상수군 · 값은 엔진과 자동 대조(test_registry)</div></header>
  <section class="card"><span class="axis">provenance registry</span>
    <h2>상수 · 근거 · 상태</h2>
    <table><thead><tr><th>상수</th><th>축</th><th>설명</th><th>값</th><th>근거</th><th>원문 파일(역참조)</th><th>상태</th></tr></thead>
      <tbody>{''.join(rows)}</tbody></table>
    <p class="note">상태 어휘(45차 정규화 — 8종 enum, 서술은 status_note로 분리):
      <span class="tag 실측">실측</span> 원문 대조·공식 고시 ·
      <span class="tag 부분실측">부분실측</span> 일부 범위·표본만 ·
      <span class="tag 법정기준">법정기준</span> 법령 원문 전사(과세 목적 등) ·
      <span class="tag 공공기준">공공기준</span> 공공 관리 기준 ·
      <span class="tag 참고기준">참고기준</span> 요율·정액·절차 참고 ·
      <span class="tag 추정">추정</span> 산정치 ·
      <span class="tag 확인요망">확인요망</span> 출처 의심·재현 불가 ·
      <span class="tag 미검증">미검증</span> 근거문서 미확보({n_unver}건).
      근거문서 확보 시 원단위 대조 후 승격(원문은 source_refs로 역참조).
      <b>레지스트리 값은 엔진 상수와 test_registry.py 로 대조되어 드리프트를 막는다.</b></p>
  </section>
  <p><a class="report-link" href="index.html"><span class="t">← 목록으로</span></a></p>"""
    return _page("엔진 상수 근거대장", body)


QUOTES_JSON = "견적비교_논산딸기3사.json"
QUOTES_GLOB = "견적비교_*.json"  # 확장(2026-08-17): 데이터 파일 추가만으로 비교 페이지 증설


def quotes_mapping_key(mapping) -> str:
    """매핑 표기에서 카테고리 키 추출 — 실전사 관행 2종을 모두 지원:
    'key(근거…)'(논산 3사)와 'key — 근거…'(군산 규격대안)."""
    return re.split(r"\(|—", str(mapping))[0].strip()


def quotes_derive_categories(raw_rows: list) -> dict:
    """raw_rows(공종 원문 전사+매핑)에서 카테고리 소계 집계 — 전사 보조 부기(34차).
    계산이 아니라 전사 합산이며, 정합 여부는 quotes_vendor_3way_check()·
    compare_quotes()가 검증한다."""
    out = {}
    for _name, amount, mapping in raw_rows:
        key = quotes_mapping_key(mapping)
        out[key] = out.get(key, 0) + amount
    return out


def quotes_vendor_3way_check(v: dict) -> list:
    """전사 무결성 3중 대사(원단위) — test_quotes_json_sums_are_exact와 같은 규칙의
    실행형(웹 기입 미리보기가 이걸 호출, 테스트가 기존 파일로 일치성을 고정)."""
    cat_sum = sum(v["categories"].values())
    raw_sum = sum(r[1] for r in v["raw_rows"])
    total = v["direct_cost_total"]
    return [
        {"name": "raw_rows 합 == 직접공사비(원단위)", "ok": raw_sum == total,
         "detail": f"{raw_sum:,} vs {total:,} (차 {raw_sum - total:+,})"},
        {"name": "카테고리 합 == 직접공사비(원단위)", "ok": cat_sum == total,
         "detail": f"{cat_sum:,} vs {total:,} (차 {cat_sum - total:+,})"},
        {"name": "총액(제경비 포함) ≥ 직접공사비", "ok": v["total_with_overhead"] >= total,
         "detail": f"{v['total_with_overhead']:,} vs {total:,}"},
    ]


def load_quotes_comparison(path: str = QUOTES_JSON):
    """견적비교 데이터(JSON) → 엔진 compare_quotes() 결과. 렌더 밖 계산은 전부 엔진.
    P3-23(2026-08-17 사용자 결정): P3-20 시연을 사이트 파이프라인에 정식 연결.
    rfq_input.required_categories(선택)로 필수 공종을 케이스별 조정(판단성 입력 —
    예: 무가온 하우스 비교는 hvac 제외)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    ri = data["rfq_input"]
    rfq = e.generate_rfq_package(
        region_snow_cm=ri["region_snow_cm"], region_wind_ms=ri["region_wind_ms"],
        area_m2=ri["area_m2"], cover=e.Cover(ri["cover"]), form=ri["form"],
        t_target=ri["t_target"], t_min=ri["t_min"],
        curtain=ri["curtain"], crop=ri["crop"],
        required_categories=ri.get("required_categories"))
    vqs = [e.VendorQuote(v["vendor_name"], v["categories"], v["direct_cost_total"],
                         v["total_with_overhead"], v.get("area_m2"), v.get("spec_name"))
           for v in data["vendor_quotes"]]
    return data, rfq, e.compare_quotes(rfq, vqs)


def quotes_comparison_page(data: dict, rfq, cmp) -> str:
    ri = data["rfq_input"]
    won = lambda v: f"{v:,.0f}"

    # 38차 레드팀 F2: 각 사 총액의 원가 계층이 다를 수 있어(순공사비 vs 부가세 포함)
    # 직접공사비(3사 공통 계층)와 금액 기준 요약을 병기한다. F4: 열 라벨은 종합 점수임을 명시.
    vend_by_name = {v["vendor_name"]: v for v in data["vendor_quotes"]}
    def _basis(v):
        note = v.get("total_note", "")
        head = note.split(".")[0][:30]
        return f"<span title='{esc(note)}'>{esc(head)}{'…' if len(note) > len(head) else ''}</span>"
    comp_rows = "".join(
        f"<tr><td>{esc(r.vendor_name)}</td>"
        f"<td><span class='badge {_sc('정상' if r.overall_status == '일치' else ('경계' if '확인' in r.overall_status else '재확인'))}'>{esc(r.overall_status)}</span></td>"
        f"<td class='num'>{r.match_score_pct:.0f}%</td>"
        f"<td class='num'>{won(r.total_with_overhead_won)}</td>"
        f"<td class='num'>{won(vend_by_name[r.vendor_name]['direct_cost_total'])}</td>"
        f"<td class='num'>{won(r.unit_won_m2)}</td>"
        f"<td style='font-size:12px'>{_basis(vend_by_name[r.vendor_name])}</td></tr>"
        for r in cmp.rows)
    # F5: 사양 부합도 동점이면 특정 업체를 '최고'로 호명하지 않는다(입력 순서 편향 방지)
    _scores = {round(r.match_score_pct, 1) for r in cmp.rows}
    top_txt = "전 업체 동점" if len(_scores) == 1 else esc(cmp.highest_match_score_vendor or "-")

    detail_cards = []
    for v in data["vendor_quotes"]:
        recon = cmp.reconciliations[v["vendor_name"]]
        checks = "".join(
            f"<tr><td>{esc(c.name)}</td>"
            f"<td><span class='badge {_sc('정상' if c.status in ('일치', '정상') else ('경계' if c.status == '확인요망' else '재확인'))}'>{esc(c.status)}</span></td>"
            f"<td>{esc(c.detail)}</td></tr>" for c in recon.checks)
        raws = "".join(
            f"<tr><td>{esc(r[0])}</td><td class='num'>{won(r[1])}</td>"
            f"<td>{esc(r[2])}</td></tr>" for r in v["raw_rows"])
        detail_cards.append(f"""
  <section class="card"><span class="axis">업체 상세</span>
    <h2>{esc(v['vendor_name'])} — {esc(v['area_note'])}</h2>
    <div class="row"><span class="lbl">출처</span><span class="val"><code>{esc(v['source_file'])}</code> · {esc(v['source_sheet'])}</span></div>
    <div class="row"><span class="lbl">금액 기준</span><span class="val">{esc(v['total_note'])}</span></div>
    <table><tr><th>정합 검증</th><th>판정</th><th>상세</th></tr>{checks}</table>
    <p class="note" style="border-top:0">"필수 공종 완전성"은 카테고리 금액의 존재 여부 판정이다(세부 구성의 충분성
      판정 아님 — 47차 명시) · 밴드 판정은 부가세 포함 풀스펙 실측 기준이라 축소 구성 견적은 대조군 범위가 다를 수 있다.</p>
    <h2 style="margin-top:16px">공종 원문 → 카테고리 매핑 (원단위 전사)</h2>
    <table><tr><th>견적서 공종(원문)</th><th class="num">금액(원)</th><th>매핑·근거</th></tr>{raws}</table>
  </section>""")

    body = f"""
  <header class="top"><h1>{esc(data['title'])}</h1>
    <div class="sub">7단계(시공발주관리) compare_quotes · 참고정보 — 업체·대안 선정 판단은 컨설턴트 몫</div></header>
  <section class="card"><span class="axis">RFQ 사양</span>
    <h2>요구 사양서 (엔진 생성)</h2>
    <div class="row"><span class="lbl">입지</span><span class="val">{esc(ri['region'])} — 적설 {ri['region_snow_cm']}cm · 풍속 {ri['region_wind_ms']}m/s</span></div>
    <div class="row"><span class="lbl">채택 규격</span><span class="val">{esc(rfq.spec_name)} (설계 적설 {rfq.snow_cm}·풍속 {rfq.wind_ms})</span></div>
    <div class="row"><span class="lbl">규모·피복</span><span class="val">{ri['area_m2']:,}㎡ · {esc(ri['cover'])} · {esc(ri['form'])} · 작물 {esc(ri['crop'])}</span></div>
    <div class="row"><span class="lbl">난방부하</span><span class="val">{rfq.heating.max_load_kcal_h:,.0f} kcal/h (커튼 {esc(ri['curtain'])} · t_target {ri['t_target']}℃/t_min {ri['t_min']}℃ 기준 — 입력 근거·한계는 하단 note)</span></div>
    <p class="note" style="border-top:0;margin-top:8px">{esc(ri['note'])}</p></section>
  <section class="card"><span class="axis">{len(data['vendor_quotes'])}건 비교</span>
    <h2>비교표 (입력 순서 그대로 — 정렬·순위·추천 없음)</h2>
    <table><tr><th>업체</th><th>종합</th><th class="num">사양 부합도(종합)</th><th class="num">총액(원)</th><th class="num">직접공사비(원)</th><th class="num">원/㎡(총액 기준)</th><th>금액 기준(요약)</th></tr>{comp_rows}</table>
    <p class="note" style="border-top:0">참고: 최저가 {esc(cmp.lowest_cost_vendor or '-')}(총액 기준 — ⚠️ 각 사 총액의 원가 계층이 다르면 직접 비교 불가: '금액 기준' 열과 업체 상세의 계층 서술을 반드시 확인) ·
      최고 사양 부합도 {top_txt} — 어느 쪽이 낫다는 판정이 아니다. 사양 부합도는 필수공종·면적·규격코드·밴드 4개 검증의 종합 점수다.</p></section>
  {''.join(detail_cards)}
  <section class="card"><span class="axis">전사·매핑 원칙</span>
    <h2>데이터 출처와 한계</h2>
    <p style="font-size:13.5px">{esc(data['provenance'])}</p>
    <p style="font-size:13.5px;color:var(--muted)">{esc(data['decision_note'])}</p></section>"""
    return _page(data["title"], body)


def index_page(links: list[dict]) -> str:
    items = "".join(
        f"<a class='report-link' href='{esc(l['href'])}'>"
        f"<span class='t'>{esc(l['title'])}</span>"
        f"<span class='d'>{esc(l['desc'])}</span></a>" for l in links)
    body = f"""
  <header class="top"><h1>SmartFarm 진단·운영 리포트</h1>
    <div class="sub">진단 · 설계 · 시공 · 경제성 4축 · 계산 출처 smartfarm_engine 단일</div></header>
  <section class="card"><span class="axis">리포트 목록</span>
    <h2>바로가기</h2>{items}</section>"""
    return _page("SmartFarm 리포트", body)


def main():
    cases = load_cases()
    computed, links = [], []
    n_partial = 0
    for c in cases:
        # P3-21d: 부분 케이스(시공축 전용)는 4축 계산 없이 전용 페이지만 렌더
        if c.get("partial"):
            fn = f"SmartFarm_부분케이스_{c['case_id']}.html"
            with open(fn, "w", encoding="utf-8") as f:
                f.write(partial_construction_page(c))
            links.append({"href": fn, "title": f"▷ {c['title']}",
                          "desc": "시공축 부분 케이스 — 실측 공사비·규격만(4축 미산출)"})
            n_partial += 1
            continue
        inp = case_to_input(c)
        res = rr.compute(inp)
        fn = f"SmartFarm_리포트_{c['case_id']}.html"
        with open(fn, "w", encoding="utf-8") as f:
            f.write(rr.render_html(res))
        computed.append({"case": c, "res": res})
        ec = res["economics"]
        rr_ = f" · 실질ROI {ec['real_roi']*100:.1f}%" if ec["real_roi"] else ""
        links.append({"href": fn, "title": c["title"],
                      "desc": f"4축 종합 · ROI {ec['roi']*100:.1f}%{rr_}"})

        crn = f"SmartFarm_통합보고서_{c['case_id']}.html"
        with open(crn, "w", encoding="utf-8") as f:
            f.write(consulting_report_page(c, res, inp))
        links.append({"href": crn, "title": f"▶ {c['title']} 통합보고서",
                      "desc": "입지·설계·운영·경제성 4섹션 + 경영자요약"})

    with open("SmartFarm_벤치마크비교.html", "w", encoding="utf-8") as f:
        f.write(benchmark_page())
    with open("SmartFarm_케이스비교.html", "w", encoding="utf-8") as f:
        f.write(comparison_page(computed))
    with open("SmartFarm_근거대장.html", "w", encoding="utf-8") as f:
        f.write(registry_page())
    with open("SmartFarm_CAPEX분해.html", "w", encoding="utf-8") as f:
        f.write(capex_breakdown_page())

    links.append({"href": "SmartFarm_케이스비교.html", "title": "▶ 케이스 비교 뷰",
                  "desc": f"{len(cases) - n_partial}개 케이스 KPI 대조 + 근거"})
    links.append({"href": "SmartFarm_벤치마크비교.html", "title": "▶ 실측 벤치마크 비교",
                  "desc": f"{len(e.ACTUALS)}건 · 시공축 밴드 대조"})
    links.append({"href": "SmartFarm_CAPEX분해.html", "title": "▶ CAPEX 공종 카테고리 분해",
                  "desc": f"{len(e.CAPEX_CASE_CHUNKS)}건 실측 청킹 · 9개 표준 카테고리"})
    links.append({"href": "SmartFarm_근거대장.html", "title": "▶ 엔진 상수 근거대장",
                  "desc": "P0 provenance · 엔진과 자동 대조"})

    # P3-23(2026-08-17): 7단계 compare_quotes 연결 — 견적비교_*.json 전부 순회
    # (확장 2026-08-17: 파일 고정 → glob 일반화. 데이터 파일 추가만으로 페이지 증설)
    n_quote_pages = 0
    for qpath in sorted(glob.glob(QUOTES_GLOB)):
        qdata, qrfq, qcmp = load_quotes_comparison(qpath)
        fn = f"SmartFarm_견적비교_{qdata['comparison_id']}.html"
        with open(fn, "w", encoding="utf-8") as f:
            f.write(quotes_comparison_page(qdata, qrfq, qcmp))
        links.append({"href": fn, "title": f"▶ {qdata['title']}",
                      "desc": f"{len(qdata['vendor_quotes'])}개 안 · RFQ 정합검증 · 참고정보(추천 없음)"})
        n_quote_pages += 1

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(index_page(links))

    print(f"사이트 생성 완료: index + 케이스 {len(cases) - n_partial}건"
          + (f" + 부분케이스 {n_partial}건" if n_partial else "")
          + " + 비교뷰 + 벤치마크 + CAPEX분해 + 근거대장"
          + (f" + 견적비교 {n_quote_pages}건" if n_quote_pages else ""))
    return computed


if __name__ == "__main__":
    main()
