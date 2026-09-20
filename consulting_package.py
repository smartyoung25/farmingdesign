"""컨설팅 패키지 조립 계층 (181차 신설)

**무엇인가**: 케이스 하나를 받아 서비스 설계서의 산출물 **D1~D20을 한 번에 세우는** 계층이다.
180차까지 엔진에는 함수가 62개 있었지만 **산출물 계층(build_site·webapp)에서 호출되는 것은
17개뿐**이었다 — D13~D20(173~176차 신설)은 **생성 경로가 아예 없었다**.

🔴 **1절 경계 — 이 파일은 계산하지 않는다.**
- 산술 연산자(`*`·`/`·`-`·`//`·`%`·`**`)를 **한 줄도 쓰지 않는다**. 가드가 AST로 검사한다.
- 4축 수치는 이미 있는 단일 경로(`render_report.compute`)를 **재사용**한다 — 여기서 다시
  계산하면 그것이 곧 **병렬 계산기**다.
- 시세성 값(단가·노임·유가·금리)과 고객 문서(도면·견적·하자 기록)는 **주입**받는다.
  주입이 없으면 **`주입대기`로 드러낼 뿐 채우지 않는다**.
- 판단성(업체·사양·작목 선정, 최종판정)은 **하지 않는다**. 패키지는 자료를 모아 줄 뿐이다.
"""
from __future__ import annotations

from collections import Counter as _Counter

import smartfarm_engine as e
import render_report as rr
from cases import case_to_input

# ─────────────────────────────────────────────────────────────
# 산출물 카탈로그 — 설계서 §4와 같은 20종
#   stage: ①공종설계 ②품질설계 ③감리 ④타당성검증 ⑤운영 ⑥사후관리
# ─────────────────────────────────────────────────────────────
PACKAGE_SPEC = [
    {"code": "D1", "title": "입지 진단 카드", "stage": "①공종설계", "targets": ["부지"],
     "engine": ["siting_lookup", "siting_design_load", "design_outdoor_temp",
                "heating_degree_hours", "monthly_mean_wind", "monthly_sunshine",
                "mean_wind"]},
    {"code": "D2", "title": "RFQ 사양서", "stage": "①공종설계", "targets": ["시설"],
     "engine": ["select_specs", "spec_crops", "cover_assembly_options"]},
    {"code": "D3", "title": "설계 대안 비교표", "stage": "①공종설계", "targets": ["시설"],
     "engine": ["compare_design_options"]},
    {"code": "D4", "title": "문서 4축 정합 리포트", "stage": "②품질설계",
     "targets": ["시설", "기자재"], "engine": ["doc_consistency_check"]},
    {"code": "D5", "title": "견적 정합·업체 비교표", "stage": "④타당성검증",
     "targets": ["시설"], "engine": ["reconcile_quote", "compare_quotes",
                                    "generate_rfq_package", "construction_company_list",
                                    "greenhouse_total_estimate", "structure_only_estimate",
                                    "m2_to_py"]},
    {"code": "D6", "title": "원가 분해표", "stage": "④타당성검증", "targets": ["시설"],
     "engine": ["capex_major_breakdown", "capex_breakdown"]},
    {"code": "D7", "title": "품셈 인력 산출표", "stage": "④타당성검증", "targets": ["시설"],
     "engine": ["pumsem_project_labor_summary", "pumsem_labor_days"]},
    {"code": "D8", "title": "4축 통합 컨설팅 리포트", "stage": "④타당성검증",
     "targets": ["시설"], "engine": ["heating_load", "verify_heating_vs_actual",
                                    "benchmark_check", "production_kg", "finance"]},
    {"code": "D9", "title": "재무 시나리오", "stage": "④타당성검증", "targets": ["시설"],
     "engine": ["operating_breakeven", "max_investable_capex", "loan_amortization",
                "dscr_schedule", "subsidy_application_checklist"]},
    {"code": "D10", "title": "LCC·하자 관리표", "stage": "⑥사후관리",
     "targets": ["시설", "기자재"], "engine": ["warranty_period", "lcc_replacement_schedule"]},
    {"code": "D11", "title": "근거대장", "stage": "②품질설계", "targets": ["시설"],
     "engine": []},
    {"code": "D12", "title": "결정 지원 패키지", "stage": "④타당성검증", "targets": ["시설"],
     "engine": []},
    {"code": "D13", "title": "검측 체크리스트", "stage": "③감리", "targets": ["시설", "기자재"],
     "engine": ["inspection_checklist"]},
    {"code": "D14", "title": "시운전 계획", "stage": "③감리", "targets": ["시설", "기자재"],
     "engine": ["commissioning_plan"]},
    {"code": "D15", "title": "준공 서류철", "stage": "③감리", "targets": ["시설"],
     "engine": ["completion_docset"]},
    {"code": "D16", "title": "점검 일정표", "stage": "⑥사후관리", "targets": ["시설", "기자재"],
     "engine": ["maintenance_schedule"]},
    {"code": "D17", "title": "하자 추적표", "stage": "⑥사후관리", "targets": ["시설"],
     "engine": ["defect_tracking"]},
    {"code": "D18", "title": "인허가 체크리스트", "stage": "①공종설계", "targets": ["부지"],
     "engine": ["site_permit_checklist"]},
    {"code": "D19", "title": "기자재 대조표", "stage": "②품질설계", "targets": ["기자재"],
     "engine": ["equipment_reconcile"]},
    {"code": "D20", "title": "내용연수 대조표", "stage": "⑥사후관리", "targets": ["기자재"],
     "engine": ["service_life_reference"]},
]

# 주입 슬롯 — 이름과 성격을 밝혀 둔다(무엇이 없어서 못 세우는지 고객이 알아야 한다)
INJECTION_SLOTS = {
    "winter_months": "동절기 개월 정의 — ★`D-9` 결정 대기(`mean_wind`가 기본값을 두지 않는다)",
    "curtain": "피복조합(`FR_TABLE` 키) — ★`D-4`·`FR_TABLE` 계열 결정에 걸려 있어 "
               "임의로 고르지 않는다",
    "doc_rows": "도면·시방서·BoQ·규격서 식별자/Rev 행 — 고객 문서",
    "vendor_quotes": "업체 견적(카테고리별 금액) — 시세성",
    "capex_items": "견적 공종별 금액 — 시세성",
    "quantities": "공종별 물량 — 설계 성과품",
    "loan": "대출 조건(금리·기간) — 시세성",
    "lcc_items": "품목별 단가·내용연수 — 단가는 시세성",
    "maintenance_items": "점검 대상 품목",
    "inspection_intervals": "점검 주기(개월) — 🔴리포에 국내 기준표가 없다(174차)",
    "defect_records": "하자 발생·보수 기록 — 고객 운영자료",
    "completion_date": "준공일",
    "quoted_models": "견적에 적힌 기자재 모델명",
    "ks_declared": "규격 선언(KS 적합 여부)",
    "service_life_names": "내용연수를 조회할 기종명",
    "acceptance_criteria": "장비별 시운전 합격 기준 — 🔴시방서 원문에 없다(173차)",
    "land_use_zone": "용도지역 — 지자체 확인 사항",
    "capex_targets": "CAPEX 상한 역산의 목표치(목표 IRR·최대 Payback·최소 DSCR) — "
                     "🔴**협의 항목**이라 기본값을 두지 않는다",
    "pumsem_probe": "품셈 단일 항목 조회(분류·품명·수량) — 설계 성과품",
    "rfq_form": "RFQ 기준 형식(연동·단동 등) — 🔴**판단성**이라 기계가 고르지 않는다",
    "quote_for_reconcile": "정합 검사할 견적 1건(카테고리별 금액·직접비·총액) — 시세성",
}

_LINKED = {
    "D8": "SmartFarm_통합보고서_{case_id}.html",
    "D11": "SmartFarm_근거대장.html",
}
_D12_DOCS = [
    "근거_결정대기대장_20260915.md",
    "서비스설계_컨설팅_3대상x6단계_20260920.md",
    "서비스설계_3x6_비판적검토_20260920.md",
    "검증절차_레드팀.md",
]


def _need(*keys) -> list:
    """주입 슬롯 이름 → 사람이 읽는 설명."""
    out = []
    for k in keys:
        out.append({"slot": k, "why": INJECTION_SLOTS[k]})
    return out


def _item(spec: dict, status: str, data=None, needs=None, note: str = "") -> dict:
    return {"code": spec["code"], "title": spec["title"], "stage": spec["stage"],
            "targets": list(spec["targets"]), "engine": list(spec["engine"]),
            "status": status, "data": data, "needs": list(needs or []), "note": note}


def build_package(case: dict, injections: dict = None) -> dict:
    """케이스 1건 → D1~D20 패키지(결정론).

    injections: 시세성·고객문서 주입값. 없으면 그 산출물은 `주입대기`로 남는다 —
    🔴 **비어 있는 것을 채우지 않는다.**
    """
    if not isinstance(case, dict) or not case.get("input"):
        raise ValueError("case가 비어 있거나 input이 없다")
    inj = dict(injections or {})
    # 🔴 차집합은 `-`가 아니라 `difference()`로 쓴다 — 181차 가드가 조립 계층에서
    #    산술 연산자를 **하나도** 허용하지 않기 때문이다(집합 연산이라도 예외를 두면
    #    그 예외가 곧 산술이 들어오는 문이 된다).
    unknown = sorted(set(inj).difference(INJECTION_SLOTS))
    if unknown:
        raise ValueError("모르는 주입 슬롯: %s" % unknown)

    inp = case_to_input(case)
    res = rr.compute(inp)          # 🔴 4축 수치는 여기서 다시 계산하지 않는다
    region, items = inp.region, []

    for spec in PACKAGE_SPEC:
        code = spec["code"]

        if code == "D1":
            d = {"지역": region,
                 "설계하중": e.siting_design_load(region),
                 "내재해형 조회": e.siting_lookup(region),
                 "난방 설계외기온": e.design_outdoor_temp(region),
                 "월별 평균풍속": e.monthly_mean_wind(region),
                 "월별 일조시간": e.monthly_sunshine(region),
                 "난방도시(설정온도 기준)": e.heating_degree_hours(region, inp.t_target)}
            n = _need("winter_months")
            months = inj.get("winter_months")
            if months:
                d["동절기 평균풍속"] = e.mean_wind(region, months)
                n = []
            miss = [k for k, v in d.items() if v is None]
            items.append(_item(spec, "생성", d, n,
                               "🔴 조회 실패 항목은 `None`으로 남긴다(추정하지 않는다): %s"
                               % (miss or "없음")))

        elif code == "D2":
            sel = e.select_specs(inp.snow_cm, inp.wind_ms, crop=inp.crop)
            d = {"작목": inp.crop,
                 "하중 충족 후보": len(sel["candidates"]),
                 "형식별 최소사양": {f: s.name for f, s in sel["min_by_form"].items()},
                 "작목특화형 목록": e.spec_crops(),
                 "피복조합 후보": len(e.cover_assembly_options())}
            items.append(_item(spec, "생성", d, [],
                               "🔴 사양 확정은 판단성 — 후보와 최소사양까지만 낸다"))

        elif code == "D3":
            # 🔴 대안은 **형식별 최소사양**으로만 세운다 — 어느 것이 낫다고 하지 않는다.
            #    피복조합(curtain)은 FR_TABLE 키라 임의로 고르지 않고 케이스에 있을 때만 쓴다.
            curtain = inj.get("curtain") or case["input"].get("curtain")
            if curtain is None:
                items.append(_item(spec, "주입대기", None, _need("curtain"),
                                   "대안 비교는 피복조합이 정해져야 선다"))
            else:
                opts = []
                for form, s_ in sorted(
                        e.select_specs(inp.snow_cm, inp.wind_ms)["min_by_form"].items()):
                    opts.append(e.DesignOption(
                        label=form, spec_name=s_.name, cover=inp.cover.value,
                        curtain=curtain, area_py=e.m2_to_py(inp.area_m2),
                        surface_area_m2=inp.surface_area_m2, t_target=inp.t_target,
                        t_min=inp.t_min, floor_area_m2=inp.area_m2))
                cmp_ = e.compare_design_options(inp.snow_cm, inp.wind_ms, opts)
                items.append(_item(spec, "생성",
                                   {"대안 수": len(cmp_.rows),
                                    "규격": [r.spec_name for r in cmp_.rows],
                                    "설계강도 충족": [r.spec_ok for r in cmp_.rows],
                                    "비고": cmp_.notes}, [],
                                   "형식별 최소사양을 나란히 놓는다 — 순위·추천 필드가 없다"))

        elif code == "D4":
            rows = inj.get("doc_rows")
            if not rows:
                items.append(_item(spec, "주입대기", None, _need("doc_rows"),
                                   "고객 문서가 와야 4축 정합을 볼 수 있다"))
            else:
                rep = e.doc_consistency_check(rows)
                items.append(_item(spec, "생성",
                                   {"집계": rep.counts, "행": len(rep.rows)}, []))

        elif code == "D5":
            # 🔴 견적 정합은 주입 대기지만, **대조의 기준선**은 지금 세울 수 있다 —
            #    업체 후보(소재지 거르기만)와 개산 2법이다. 어느 것도 추천이 아니다.
            area_py = e.m2_to_py(inp.area_m2)
            est = {}
            for form, s_ in e.select_specs(inp.snow_cm, inp.wind_ms)["min_by_form"].items():
                est[s_.name] = e.greenhouse_total_estimate(s_.name, area_py)
            d = {"업체 후보(소재지 거르기만)": len(e.construction_company_list(region)),
                 "개산 A 온실 전체(평단가×면적)": est,
                 "개산 B 골조 단독": e.structure_only_estimate(area_py)}
            vq = inj.get("vendor_quotes")
            form, curtain = inj.get("rfq_form"), inj.get("curtain")
            if vq and form and curtain:
                rfq = e.generate_rfq_package(
                    inp.snow_cm, inp.wind_ms, inp.area_m2, inp.cover, form,
                    inp.t_target, inp.t_min, fr=inp.fr,
                    surface_area_m2=inp.surface_area_m2, curtain=curtain, crop=inp.crop)
                cmpq = e.compare_quotes(rfq, vq)
                d["RFQ 규격"] = rfq.spec_name
                d["업체 비교"] = {"안 수": len(cmpq.rows),
                              "최저가 표시": cmpq.lowest_cost_vendor,
                              "최고정합 표시": cmpq.highest_match_score_vendor}
                one = inj.get("quote_for_reconcile")
                if one:
                    rec = e.reconcile_quote(rfq, **one)
                    d["견적 정합 4검사"] = rec.checks
                items.append(_item(spec, "생성", d, [] if one else _need("quote_for_reconcile"),
                                   "🔴 최저가·최고정합은 **표시일 뿐 추천이 아니다** — "
                                   "업체 선정은 컨설턴트 몫이다"))
            else:
                items.append(_item(spec, "부분생성", d,
                                   _need("vendor_quotes", "rfq_form", "curtain"),
                                   "🔴 견적 금액은 시세성 — 주입 전용이다. 업체 후보는 "
                                   "**명단일 뿐 추천이 아니다**. 개산이 `None`인 규격은 "
                                   "평단가표 미등재이고 지어내지 않는다. 형식(`rfq_form`) "
                                   "선택은 **판단성**이라 기계가 고르지 않는다"))

        elif code == "D6":
            it = inj.get("capex_items")
            if not it:
                items.append(_item(spec, "주입대기", None, _need("capex_items"),
                                   "공종별 금액이 없으면 분해할 대상이 없다"))
            else:
                br = e.capex_major_breakdown(it, inp.total_construction_cost)
                fine = e.capex_breakdown(it)
                items.append(_item(spec, "생성",
                                   {"미분류": br.unclassified, "상위 카테고리": len(br.rows),
                                    "세부 항목": len(fine.rows)}, [],
                                   "🔴 잔차는 `unclassified`로 **남긴다** — 0으로 만들지 않는다"))

        elif code == "D7":
            q = inj.get("quantities")
            if not q:
                items.append(_item(spec, "주입대기", None, _need("quantities"),
                                   "물량은 설계 성과품에서 온다"))
            else:
                d = {"프로젝트 합계": e.pumsem_project_labor_summary(q)}
                probe = inj.get("pumsem_probe")
                if probe:
                    d["단일 항목 조회"] = e.pumsem_labor_days(**probe)
                items.append(_item(spec, "생성", d,
                                   [] if probe else _need("pumsem_probe")))

        elif code == "D8":
            items.append(_item(spec, "링크",
                               {"파일": _LINKED["D8"].format(case_id=case["case_id"]),
                                "요약": res["economics"]}, [],
                               "🔴 4축 수치는 `render_report.compute` 단일 경로에서 온다 — "
                               "이 계층은 다시 계산하지 않는다"))

        elif code == "D9":
            be = e.operating_breakeven(inp.opex, inp.price_won_per_kg)
            d = {"손익분기": {"필요 매출(원)": be.breakeven_revenue_won,
                           "필요 생산량(kg)": be.breakeven_kg},
                 "ROI": res["economics"]["roi"],
                 "Payback": res["economics"]["payback"],
                 "NPV": res["economics"]["npv"],
                 "IRR": res["economics"]["irr"],
                 "실질ROI": res["economics"]["real_roi"]}
            d["보조사업 절차"] = {"단계": len(e.subsidy_application_checklist()),
                             "주의": "보조율은 공모 회차마다 바뀌어 싣지 않는다"}
            needs = []
            loan = inj.get("loan")
            if loan:
                d["상환표"] = e.loan_amortization(**loan)
                d["DSCR"] = e.dscr_schedule(res["economics"]["revenue"], inp.opex, loan)
            else:
                needs.extend(_need("loan"))
            tg = inj.get("capex_targets")
            if tg:
                d["CAPEX 상한 역산"] = e.max_investable_capex(
                    res["economics"]["revenue"], inp.opex, **tg)
            else:
                needs.extend(_need("capex_targets"))
            items.append(_item(spec, "생성" if not needs else "부분생성", d, needs,
                               "🔴 금리·기간은 시세성, 목표치는 협의 — 주입이 없으면 "
                               "상환표·DSCR·상한 역산을 만들지 않는다. "
                               "NPV·IRR은 `render_report.compute` 결과를 그대로 옮긴다"))

        elif code == "D10":
            # 🔴 공종명은 `WARRANTY_STATUTORY` 등재 키를 **그대로** 쓴다 —
            #    비슷한 이름으로 넘기면 `None`이 돌아오고, 그것을 「담보기간 없음」으로
            #    읽으면 등재값이 있는데 없다고 말하는 것이 된다.
            w = {}
            for wt in ("온실설치", "전기(건축물 전기설비)", "통신(그 외 정보통신공사)",
                       "급배수·냉난방·환기·공조·자동제어·가스·배연설비"):
                w[wt] = e.warranty_period(wt)
            li = inj.get("lcc_items")
            d = {"법정 하자담보기간": w}
            if li:
                d["LCC 교체 일정"] = e.lcc_replacement_schedule(li, 20)
            items.append(_item(spec, "생성" if li else "부분생성", d,
                               [] if li else _need("lcc_items"),
                               "🔴 단가는 시세성 — 없으면 교체 **연도 구조**도 세우지 않는다"))

        elif code in _LINKED:
            items.append(_item(spec, "링크", {"파일": _LINKED[code]}, [],
                               "이미 생성되는 산출물로 연결한다"))

        elif code == "D12":
            items.append(_item(spec, "링크", {"문서": list(_D12_DOCS)}, [],
                               "🔴 ④ 결정 로그는 아직 없다(설계서 §4 기록)"))

        elif code == "D13":
            items.append(_item(spec, "생성", e.inspection_checklist(), [],
                               "공사시방서 9단계 전사 + 엔진 대조 4곳"))

        elif code == "D14":
            names = inj.get("quoted_models") or ["온풍난방기", "보온커튼", "환기팬"]
            plan = e.commissioning_plan(names, inj.get("acceptance_criteria"))
            items.append(_item(spec, "생성", plan,
                               _need("acceptance_criteria") if plan["needs_criteria"] else [],
                               "🔴 합격 기준은 시방서 원문에 없다 — `needs_criteria`로 드러낸다"))

        elif code == "D15":
            items.append(_item(spec, "생성", e.completion_docset(), [],
                               "시방서 열거 5종 + 4축 정합 상태(D4가 서면 함께 붙는다)"))

        elif code == "D16":
            mi = inj.get("maintenance_items") or ["온풍난방기", "보온커튼", "환기팬"]
            sch = e.maintenance_schedule(mi, inj.get("inspection_intervals"))
            items.append(_item(spec, "생성", sch,
                               _need("inspection_intervals") if sch["needs_interval"] else [],
                               "🔴 점검 주기표가 국내에 없다 — 주입 전용이고 미주입을 드러낸다"))

        elif code == "D17":
            rec, done = inj.get("defect_records"), inj.get("completion_date")
            if not rec or not done:
                items.append(_item(spec, "주입대기", None,
                                   _need("defect_records", "completion_date"),
                                   "준공일과 하자 기록이 있어야 담보기간을 대조한다"))
            else:
                items.append(_item(spec, "생성", e.defect_tracking(rec, done), []))

        elif code == "D18":
            chk = e.site_permit_checklist(area_m2=inp.area_m2, cover=inp.cover.value,
                                          land_use_zone=inj.get("land_use_zone"))
            items.append(_item(spec, "생성", chk,
                               _need("land_use_zone") if chk["missing_inputs"] else [],
                               "🔴 비용 이견 2건을 본문에 섞지 않고 `cost_dispute`로 분리한다"))

        elif code == "D19":
            qm = inj.get("quoted_models")
            if not qm:
                items.append(_item(spec, "주입대기", None, _need("quoted_models", "ks_declared"),
                                   "견적 모델명이 없으면 대조할 대상이 없다"))
            else:
                items.append(_item(spec, "생성",
                                   e.equipment_reconcile(qm, inj.get("ks_declared")), [],
                                   "🔴 적합 판정은 하지 않는다 — 3열 대조까지다"))

        elif code == "D20":
            names = inj.get("service_life_names") or ["온풍난방기", "분무기", "컴퓨터서버"]
            rows = []
            for n in names:
                rows.append(e.service_life_reference(n))
            items.append(_item(spec, "생성", {"행": rows}, [],
                               "🔴 조달청·농진청[추정]·세법을 나란히 둘 뿐 고르지 않는다"))

        else:                                       # 카탈로그에 있으나 조립되지 않은 항목
            items.append(_item(spec, "미조립", None, [], "조립기가 없다"))

    by_status = dict(_Counter(it["status"] for it in items))
    needs_all = []
    for it in items:
        for n in it["needs"]:
            if n["slot"] not in [x["slot"] for x in needs_all]:
                needs_all.append(n)
    return {"case_id": case["case_id"], "title": case["title"],
            "items": items, "status_counts": by_status,
            "open_injections": needs_all,
            "note": ("🔴 이 패키지는 **판정하지 않는다**. 주입이 없는 칸은 비어 있는 채로 "
                     "드러나고, 시세성·판단성 값은 고객이 준 것만 쓴다")}


def coverage() -> dict:
    """패키지가 이름을 대고 쓰는 엔진 함수(가드가 실재를 확인한다)."""
    used = set()
    for spec in PACKAGE_SPEC:
        used.update(spec["engine"])
    return {"declared": sorted(used), "items": len(PACKAGE_SPEC)}
