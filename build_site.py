"""
SmartFarm 리포트 사이트 빌더 (경로 C 마감 + P0 근거대장)
- 계산은 전적으로 smartfarm_engine 에 위임. 이 파일은 렌더/조립만 한다.
- 케이스는 cases/*.json, 엔진 상수 근거는 엔진데이터_레지스트리.json 에서 로드.
- 산출: 케이스별 4축 리포트 · 벤치마크 비교 · 케이스 비교뷰 · 근거대장 · index.html
실행: python build_site.py
"""
from __future__ import annotations
import html, json, os, datetime as _dt
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
    major_totals = {"우민재": 456_158_140, "최혁진": 694_575_784}
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
        unclassified_rows.append(
            f"<li>{esc(case_name)}: {mb.unclassified:,.0f}원 "
            f"({mb.unclassified/mb.total*100:.1f}%) — 품질시험비·안전관리비·재해예방기술지도비 등 13개 어디에도 안 맞아 미분류로 남김</li>")

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
        rows.append(
            f"<tr><td><code>{esc(key)}</code></td><td>{esc(c['axis'])}</td>"
            f"<td>{esc(c['desc'])}</td><td>{esc(vtxt)}</td>"
            f"<td>{esc(c['source'])}</td>"
            f"<td><span class='tag {c['status']}'>{esc(c['status'])}</span></td></tr>")
    n_unver = sum(1 for c in reg["constants"].values() if c["status"] == "미검증")
    body = f"""
  <header class="top"><h1>엔진 상수 근거대장 (P0)</h1>
    <div class="sub">기준시점 {esc(reg['as_of'])} · {len(reg['constants'])}개 상수군 · 값은 엔진과 자동 대조(test_registry)</div></header>
  <section class="card"><span class="axis">provenance registry</span>
    <h2>상수 · 근거 · 상태</h2>
    <table><thead><tr><th>상수</th><th>축</th><th>설명</th><th>값</th><th>근거</th><th>상태</th></tr></thead>
      <tbody>{''.join(rows)}</tbody></table>
    <p class="note">태그: <span class="tag 실측">실측</span> 출처확인 ·
      <span class="tag 부분">부분</span> 대표/일부 수록 ·
      <span class="tag 미검증">미검증</span> 값 사용 중이나 근거문서 미확보({n_unver}건).
      근거문서(<code>SmartFarm_엔진데이터.md</code>·지침) 확보 시 '미검증'을 '실측'으로 승격.
      <b>레지스트리 값은 엔진 상수와 test_registry.py 로 대조되어 드리프트를 막는다.</b></p>
  </section>
  <p><a class="report-link" href="index.html"><span class="t">← 목록으로</span></a></p>"""
    return _page("엔진 상수 근거대장", body)


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
    for c in cases:
        res = rr.compute(case_to_input(c))
        fn = f"SmartFarm_리포트_{c['case_id']}.html"
        with open(fn, "w", encoding="utf-8") as f:
            f.write(rr.render_html(res))
        computed.append({"case": c, "res": res})
        ec = res["economics"]
        rr_ = f" · 실질ROI {ec['real_roi']*100:.1f}%" if ec["real_roi"] else ""
        links.append({"href": fn, "title": c["title"],
                      "desc": f"4축 종합 · ROI {ec['roi']*100:.1f}%{rr_}"})

    with open("SmartFarm_벤치마크비교.html", "w", encoding="utf-8") as f:
        f.write(benchmark_page())
    with open("SmartFarm_케이스비교.html", "w", encoding="utf-8") as f:
        f.write(comparison_page(computed))
    with open("SmartFarm_근거대장.html", "w", encoding="utf-8") as f:
        f.write(registry_page())
    with open("SmartFarm_CAPEX분해.html", "w", encoding="utf-8") as f:
        f.write(capex_breakdown_page())

    links.append({"href": "SmartFarm_케이스비교.html", "title": "▶ 케이스 비교 뷰",
                  "desc": f"{len(cases)}개 케이스 KPI 대조 + 근거"})
    links.append({"href": "SmartFarm_벤치마크비교.html", "title": "▶ 실측 벤치마크 비교",
                  "desc": f"{len(e.ACTUALS)}건 · 시공축 밴드 대조"})
    links.append({"href": "SmartFarm_CAPEX분해.html", "title": "▶ CAPEX 공종 카테고리 분해",
                  "desc": f"{len(e.CAPEX_CASE_CHUNKS)}건 실측 청킹 · 9개 표준 카테고리"})
    links.append({"href": "SmartFarm_근거대장.html", "title": "▶ 엔진 상수 근거대장",
                  "desc": "P0 provenance · 엔진과 자동 대조"})
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(index_page(links))

    print(f"사이트 생성 완료: index + 케이스 {len(cases)}건 + 비교뷰 + 벤치마크 + CAPEX분해 + 근거대장")
    return computed


if __name__ == "__main__":
    main()
