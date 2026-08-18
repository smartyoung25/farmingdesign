"""
케이스 로더 견고성 + 사이트 렌더 회귀 테스트
- load_cases: 빈 파일/불량 JSON/필수키 결여 파일 스킵, 정상 케이스만 로드.
- comparison_page: IRR None(초고수익 → 이분법 범위 초과) 시 크래시 없이 '>100%' 렌더.
- opex_breakdown: 케이스 스키마 v2(Step5) 필드가 엔진 계산과 어긋나지 않는지 드리프트 가드.
- consulting_report_page: Step6 4섹션 통합 리포트가 케이스 3건 전부 크래시 없이
  렌더되고 핵심 KPI·CAPEX 분해 유무 분기가 올바른지 스모크 테스트.
실행: pytest test_cases.py -q
"""
import json, importlib, os
import cases as C
import build_site as bs
import render_report as rr
import smartfarm_engine as e


def test_load_cases_skips_empty_and_invalid(tmp_path, monkeypatch):
    d = tmp_path / "cases"
    d.mkdir()
    (d / "empty.json").write_text("", encoding="utf-8")            # 빈 파일(tombstone)
    (d / "broken.json").write_text("{not json", encoding="utf-8")  # 불량 JSON
    (d / "nokey.json").write_text('{"foo":1}', encoding="utf-8")   # 필수키 없음
    good = {"case_id": "good", "title": "정상", "as_of": "2026-07",
            "input": {"business_type": "신규", "crop": "토마토", "region": "충남",
                      "area_m2": 3456, "cover": "유리", "snow_cm": 30, "wind_ms": 35,
                      "surface_area_m2": 5000, "t_target": 10, "t_min": -7.8, "fr": 0.7,
                      "base_yield_kg_m2": 38.5, "price_won_per_kg": 2500, "fitness_pct": 95,
                      "opex": 186420000, "total_construction_cost": 702030000,
                      "subsidy_rate": 0.5}}
    (d / "good.json").write_text(json.dumps(good, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(C, "CASES_DIR", str(d))
    loaded = C.load_cases()
    assert [c["case_id"] for c in loaded] == ["good"]
    # 변환도 정상
    inp = C.case_to_input(loaded[0])
    assert inp.cover.value == "유리" and inp.subsidy_rate == 0.5


def test_comparison_page_handles_none_irr():
    synth = {"case": {"title": "초고수익(합성)", "as_of": "t", "provenance": {}},
             "res": {"construction": {"unit_won_m2": 200000, "status": "정상"},
                     "heating": {"load_per_m2": 96},
                     "economics": {"roi": 2.5, "payback": 0.4, "npv": 5e8,
                                   "irr": None, "real_roi": 5.0}}}
    html = bs.comparison_page([synth])   # 크래시 없어야 함
    assert ">100%" in html


def test_case_opex_breakdown_matches_engine_and_input():
    # 케이스 JSON의 opex_breakdown 필드(Step5, 2026-07-21)가 실제
    # smartfarm_engine.opex_breakdown() 재계산과 항상 일치해야 한다 — 수기로
    # 적어둔 unclassified_won이 코드와 어긋나면(항목 추가 후 갱신 누락 등)
    # 이 테스트가 잡아낸다. known_total_won은 input.opex와도 같아야 한다.
    checked = 0
    for case in C.load_cases():
        ob = case.get("opex_breakdown")
        if ob is None:
            continue
        result = e.opex_breakdown(ob["items_won"], ob["known_total_won"])
        assert result.unclassified == ob["unclassified_won"], case["case_id"]
        assert ob["known_total_won"] == case["input"]["opex"], case["case_id"]
        checked += 1
    assert checked == 3  # 원채원·춘천·우민재


def test_consulting_report_page_renders_all_cases_without_crashing():
    checked = 0
    for case in C.load_cases():
        if case.get("partial"):   # P3-21d: 부분 케이스는 4축 통합보고서 비대상
            continue
        inp = C.case_to_input(case)
        res = rr.compute(inp)
        html = bs.consulting_report_page(case, res, inp)
        assert "경영자 요약" in html and "Ⅰ. 입지진단서" in html
        assert "Ⅱ. 설계적정성보고서" in html and "Ⅲ. 운영계획서" in html
        assert "Ⅳ. 경제성분석서" in html
        checked += 1
    assert checked == 3


def test_consulting_report_page_shows_capex_breakdown_only_when_present():
    # 우민재는 capex_breakdown.major_categories_won_2026_07_16이 있어 항목분해
    # 표가 나와야 하고, 원채원은 없어 "없음" 안내문이 나와야 한다.
    cases_by_id = {c["case_id"]: c for c in C.load_cases()}
    uminjae, wonchaewon = cases_by_id["uminjae"], cases_by_id["wonchaewon"]
    html_with = bs.consulting_report_page(uminjae, rr.compute(C.case_to_input(uminjae)),
                                          C.case_to_input(uminjae))
    html_without = bs.consulting_report_page(wonchaewon, rr.compute(C.case_to_input(wonchaewon)),
                                             C.case_to_input(wonchaewon))
    assert "CAPEX 항목분해" in html_with
    assert "CAPEX 항목분해 실측 데이터가 없어" in html_without


# ── P3-23(2026-08-17): compare_quotes 파이프라인 연결 회귀 ──────────────

def test_quotes_json_sums_are_exact():
    # 공종별 전사의 무결성(확장 2026-08-17: 전 견적비교 파일 glob):
    # 카테고리 합 == raw_rows 합 == 직접공사비 총액(원단위) — 전사·매핑 어느
    # 쪽이 어긋나도 잡힌다. 파일이 늘어나면 자동으로 검사 대상에 포함된다.
    import glob as _g
    files = sorted(_g.glob("견적비교_*.json"))
    assert len(files) >= 2                      # 논산딸기3사 + 군산무화과 규격대안
    for path in files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["comparison_id"] and len(data["vendor_quotes"]) >= 2, path
        for v in data["vendor_quotes"]:
            cat_sum = sum(v["categories"].values())
            raw_sum = sum(r[1] for r in v["raw_rows"])
            assert cat_sum == v["direct_cost_total"], (path, v["vendor_name"])
            assert raw_sum == v["direct_cost_total"], (path, v["vendor_name"])
            assert v["total_with_overhead"] >= v["direct_cost_total"]


def test_quotes_comparison_gunsan_fig_variant_pair():
    # 규격 대안 비교(동일 사업량 125×75 vs 75×75): 필수 공종은 축소 3종
    # (무가온이라 hvac 제외 — 판단성 입력)이며 두 안 모두 완전해야 한다.
    data, rfq, cmp = bs.load_quotes_comparison("견적비교_군산무화과_규격대안.json")
    assert rfq.required_categories == ["greenhouse_structure", "auto_opening_system",
                                       "irrigation_fertigation"]
    for name, recon in cmp.reconciliations.items():
        c = next(x for x in recon.checks if x.name == "필수 공종 완전성")
        assert c.status == "일치", name
    # 규격 차이의 실측 가격차: A안(125×75)이 B안보다 비싸다(합계 3,984,219원 차)
    a, b = cmp.rows[0], cmp.rows[1]
    assert a.total_with_overhead_won - b.total_with_overhead_won == 3_984_219


def test_quotes_comparison_pipeline_flags_expected_signals():
    data, rfq, cmp = bs.load_quotes_comparison()
    # RFQ가 P1-11 crop 필터·P1-9 curtain 경로로 생성됨
    assert rfq.spec_name and rfq.heating.max_load_kcal_h > 0
    # 38차 레드팀 F1(39차 반영): 종전 "임미라 hvac 누락" 신호는 오검출이었다 —
    # 원문 세부시트가 히트펌프 44,920,000을 블록 소계로 분리 계상(4블록 합이 집계표
    # 행 178,420,700과 원단위 일치). 재전사 후 3사 전부 필수 공종 완전.
    for name in ("임미라(수현건설)", "최선동(렉창)", "한수진"):
        c = next(c for c in cmp.reconciliations[name].checks if c.name == "필수 공종 완전성")
        assert c.status == "일치", name
    # 임미라 hvac 분해값이 카테고리에 실려 있다(재발 방지 고정)
    imr = {v["vendor_name"]: v for v in data["vendor_quotes"]}["임미라(수현건설)"]
    assert imr["categories"]["hvac"] == 44_920_000
    assert imr["categories"]["irrigation_fertigation"] == 133_500_700
    # 종합: 임미라 87.5%(규격코드 확인요망만), 최선동·한수진 62.5%(면적 불일치)
    scores = {r.vendor_name: r.match_score_pct for r in cmp.rows}
    assert scores["임미라(수현건설)"] == 87.5
    assert scores["최선동(렉창)"] == scores["한수진"] == 62.5
    # 3사 모두 벤치마크 밴드 내(참고정보 — 단 임미라 총액은 순공사비 계층이라
    # 밴드 기준[부가세 포함]과 계층이 다름을 데이터가 명시: F2)
    assert all(115000 <= r.unit_won_m2 <= 240000 for r in cmp.rows)
    assert "계층" in imr["total_note"]
    assert cmp.lowest_cost_vendor == "임미라(수현건설)"  # 총액 기준 참고 필드(계층 경고 병기 전제)


def test_quotes_comparison_page_renders():
    data, rfq, cmp = bs.load_quotes_comparison()
    html_out = bs.quotes_comparison_page(data, rfq, cmp)
    assert "추천" in html_out and "참고정보" in html_out   # 판단성 존중 문구
    assert "hvac" in html_out                              # 매핑 노출(분해 재전사)
    assert "원단위 전사" in html_out                        # 출처 표기
    for v in data["vendor_quotes"]:
        assert v["vendor_name"] in html_out
    # 38차 레드팀 F2·F4·F5 렌더 고정
    assert "사양 부합도(종합)" in html_out                  # F4: 오표기 라벨 제거
    assert "필수공종 일치도" not in html_out
    assert "직접공사비(원)" in html_out                     # F2: 공통 계층 병기
    assert "계층이 다르면 직접 비교 불가" in html_out
    assert "이중계상" in html_out                           # F6: 원본 결함 기록 노출(provenance)
    assert "t_target" in html_out                           # F7: 난방부하 조건 표시


# ── P3-18(2026-08-17): 금융조달 상환표 렌더 분기 ────────────────────────

def test_consulting_report_financing_section_conditional():
    # financing 블록이 없으면 안내문, 있으면 상환표가 렌더돼야 한다.
    # 케이스 원본엔 실제 대출조건이 없으므로(가공값 금지) 사본에만 합성 블록을 넣어 검증.
    cases_by_id = {c["case_id"]: c for c in C.load_cases()}
    base = cases_by_id["uminjae"]
    res = rr.compute(C.case_to_input(base))
    html_without = bs.consulting_report_page(base, res, C.case_to_input(base))
    assert "대출조건 미제공" in html_without
    assert "연차별 대출상환표" not in html_without

    with_fin = dict(base)
    with_fin["financing"] = {"loan_principal_won": 100_000_000, "annual_rate_pct": 2.0,
                             "term_years": 5, "grace_years": 2, "method": "원리금균등",
                             "note": "테스트 합성 조건(케이스 실데이터 아님)"}
    html_with = bs.consulting_report_page(with_fin, res, C.case_to_input(base))
    assert "연차별 대출상환표" in html_with and "거치 2년" in html_with
    assert "테스트 합성 조건" in html_with


# ── 37차(2026-08-18): 원천자료 실재·전사 가드 ─────────────────────────────
# 패턴 원본: test_chunking_v2.py test_manual_override_files_all_exist —
# "산출물이 가리키는 원본 파일이 실제로 있는가"를 기계 가드로. 원본이 이동·개명되면
# 조용히 끊기는 대신 여기서 잡힌다(가이드 기둥 C: 원천자료 기반 최종 검증의 1층).

import re as _re

_REPO = os.path.dirname(os.path.abspath(__file__))
_SRC_PATH_RE = _re.compile(r"스마트팜스펙/.+?\.(?:pdf|xlsx|xls|hwp|png|jpg|jpeg|docx|doc)")


def test_quotes_source_files_exist():
    # 견적비교 전 파일의 업체별 source_file 실재 — 신규 비교 파일은 glob으로 자동 편입
    import glob as _g
    checked = 0
    for path in sorted(_g.glob(os.path.join(_REPO, "견적비교_*.json"))):
        data = json.load(open(path, encoding="utf-8"))
        for v in data["vendor_quotes"]:
            src = v["source_file"]
            assert src, (path, v["vendor_name"], "source_file 비어 있음")
            assert os.path.isfile(os.path.join(_REPO, src)), \
                (path, v["vendor_name"], f"원본 없음: {src} — 파일 이동·개명 시 전사 추적성이 끊긴다")
            checked += 1
    assert checked >= 5  # 논산 3사 + 군산 2안


def test_case_provenance_path_sources_exist():
    # 케이스 provenance 안의 경로형 출처("스마트팜스펙/…확장자")가 실재하는지.
    # 서술형 출처(예: "원채원 견적(A-11)")는 통과 — 스키마 통일은 42차 몫.
    found = 0
    for c in C.load_cases():
        prov = c.get("provenance")
        texts = []
        if isinstance(prov, dict):
            texts = [str(v.get("source", "")) for v in prov.values() if isinstance(v, dict)]
        elif isinstance(prov, str):
            texts = [prov]
        for t in texts:
            for m in _SRC_PATH_RE.finditer(t):
                rel = m.group(0)
                assert os.path.isfile(os.path.join(_REPO, rel)), \
                    (c["case_id"], f"provenance가 가리키는 원본 없음: {rel}")
                found += 1
    assert found >= 2  # 최소 uminjae(xlsx)·mulhyangki(pdf)


# 한글 금액 파서 — 테스트 전용(전사 검증기이지 계산기가 아님 — 엔진에 넣지 않는다).
# OCR 유래 수치의 유일한 독립 검산(3중 대사의 '한글 대사')을 산문 기록에서 코드로.
_KDIG = {"영": 0, "일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
_KSMALL = {"십": 10, "백": 100, "천": 1000}
_KBIG = {"만": 10**4, "억": 10**8, "조": 10**12}


def _parse_korean_amount(text: str) -> int:
    s = _re.sub(r"[\s,]", "", text)
    s = _re.sub(r"^(일금|금)", "", s)
    s = _re.sub(r"(원정|원|정)$", "", s)
    total = section = num = 0
    for ch in s:
        if ch in _KDIG:
            num = _KDIG[ch]
        elif ch in _KSMALL:
            section += (num or 1) * _KSMALL[ch]
            num = 0
        elif ch in _KBIG:
            total += ((section + num) or 1) * _KBIG[ch]
            section = num = 0
        else:
            raise ValueError(f"한글 금액이 아닌 문자: {ch!r} in {text!r}")
    return total + section + num


def test_korean_amount_parser_selfcheck():
    # 파서 자체 검산(합성 표기 — 규칙 고정)
    assert _parse_korean_amount("일금오억육백만원정") == 506_000_000
    assert _parse_korean_amount("금 사억오천구백이십일만이천팔백칠십구원") == 459_212_879
    assert _parse_korean_amount("팔천구백육십일만원") == 89_610_000
    assert _parse_korean_amount("십만원") == 100_000          # 선행 일 생략형
    assert _parse_korean_amount("일조이억삼천원") == 1_000_200_003_000


def test_hangul_amount_reconciliation_in_partial_cases():
    # 케이스 파일에 실제 기록된 한글 표기 ↔ 숫자 필드의 기계 대사(OCR 3원 대조의 코드화).
    # 파일에 없는 표기는 검증하지 않는다(근거 없는 검증 금지).
    y_raw = open(os.path.join(_REPO, "cases", "yonggyun.json"), encoding="utf-8").read()
    y = json.loads(y_raw)
    assert "사억오천구백이십일만이천팔백칠십구" in y_raw
    assert _parse_korean_amount("사억오천구백이십일만이천팔백칠십구원") \
        == y["construction"]["cost_summary_won"]["공급가액"] == 459_212_879

    m_raw = open(os.path.join(_REPO, "cases", "mulhyangki.json"), encoding="utf-8").read()
    m = json.loads(m_raw)
    assert "팔천구백육십일만원정" in m_raw
    assert _parse_korean_amount("일금 팔천구백육십일만원정") \
        == m["construction"]["cost_summary_won"]["총공사비(도급, 천단위 절사)"] == 89_610_000


def _sheet_values(rows):
    out = set()
    for row in rows:
        for v in row:
            try:
                f = float(v)
                if f == int(f):
                    out.add(int(f))
            except (TypeError, ValueError):
                pass
    return out


def test_quotes_nonsan_anchor_cells_match_source():
    # 39차(레드팀 F8): 전사값을 원본 xls 셀에서 직접 재확인하는 앵커 대조 —
    # 37차 가드(파일 존재)보다 한 계층 깊다. 관대 파서(chunking_lib_v2)가 3파일
    # 전량 판독 가능함이 38차에 실증되어 실행 비용이 확인됨.
    import pytest as _pt
    _pt.importorskip("xlrd", reason="xlrd 미설치(환경 특성상 pip 유실 반복)")
    from chunking_lib_v2 import _xls_sheets_lenient

    data = json.load(open(os.path.join(_REPO, "견적비교_논산딸기3사.json"), encoding="utf-8"))
    by = {v["vendor_name"]: v for v in data["vendor_quotes"]}

    # 임미라: 집계표 총액 + 양액 세부시트 4블록 소계(F1 분해 재전사의 원문 근거 고정)
    imr = _xls_sheets_lenient(os.path.join(_REPO, by["임미라(수현건설)"]["source_file"]))
    assert imr, "임미라 xls 판독 실패"
    assert 560_744_760 in _sheet_values(imr["집계표"])
    yang = _sheet_values(imr["양액및 보일러.무인방제"])
    for sub in (22_440_000, 85_953_000, 44_920_000, 25_107_700):
        assert sub in yang, f"양액 세부 소계 {sub:,} 소실 — F1 분해 근거 붕괴"
    assert 22_440_000 + 85_953_000 + 44_920_000 + 25_107_700 == 178_420_700
    # F6 원본 결함 고정: 자동개폐 세부시트 블록 합계 30,022,000+15,230,000(노무 포함
    # 45,252,000)이 집계표에서 재료비 45,252,000+노무 6,000,000=51,252,000으로 재가산
    # — 이중계상 6,000,000이 "원본의 사실"임을 원문 셀로 못박음
    auto = _sheet_values(imr["자동개폐시설,환경제어"])
    assert 30_022_000 in auto and 15_230_000 in auto
    assert 30_022_000 + 15_230_000 == 45_252_000
    jib = _sheet_values(imr["집계표"])
    assert 45_252_000 in jib and 51_252_000 in jib

    # 최선동·한수진: 공종별집계표 직접공사비 합계 + 원가계산 총액
    for name, direct, total in (("최선동(렉창)", 497_440_760, 613_782_000),
                                ("한수진", 499_026_400, 618_001_000)):
        sheets = _xls_sheets_lenient(os.path.join(_REPO, by[name]["source_file"]))
        assert sheets, f"{name} xls 판독 실패"
        allv = set()
        for rows in sheets.values():
            allv |= _sheet_values(rows)
        assert direct in allv and total in allv, name
        assert by[name]["direct_cost_total"] == direct
        assert by[name]["total_with_overhead"] == total


# ── P1-6 잔여 해소(2026-08-18): 감리비 참고 표시(CAPEX 불산입) ─────────────

def test_consulting_report_supervision_fee_reference_block():
    # 통합보고서에 법정요율 참고 블록이 3종 전체로 렌더되고, CAPEX 불산입·판단성
    # 문구가 고정돼야 한다(문구가 빠지면 참고치가 판정으로 오독될 수 있음).
    cases_by_id = {c["case_id"]: c for c in C.load_cases()}
    case = cases_by_id["wonchaewon"]
    res = rr.compute(C.case_to_input(case))
    html = bs.consulting_report_page(case, res, C.case_to_input(case))
    assert "설계·감리비 참고(법정요율 — CAPEX 불산입)" in html
    for grade in e.SUPERVISION_FEE_GRADES:  # 종을 고르지 않고 3종 병기(판단성)
        assert grade in html
    assert "산입하지 않는다" in html and "국토교통부고시 제2020-635호" in html
    # 참고 블록 유무와 무관하게 투자지표는 동일해야 한다(불산입의 계산적 증거)
    assert res["economics"]["roi"] == rr.compute(C.case_to_input(case))["economics"]["roi"]


# ── P3-21d(2026-08-17): 이용균 부분 케이스(시공축 전용) ─────────────────

def test_partial_case_yonggyun_loads_and_is_arithmetically_consistent():
    cases_by_id = {c["case_id"]: c for c in C.load_cases()}
    y = cases_by_id["yonggyun"]
    assert y.get("partial") == "construction_only"
    cs = y["construction"]["cost_summary_won"]
    # 원문 3중 검증 구조가 JSON에서도 유지되는지 산술 가드
    assert cs["직접재료비"] + cs["직접노무비"] + cs["경비"] == cs["직접공사비"]
    assert cs["공급가액"] + cs["부가가치세"] == cs["합계"]
    assert cs["도급비(만단위 절사)"] == 506_000_000
    trades = y["construction"]["trades_material_won"]
    assert sum(trades.values()) == cs["직접재료비"]      # 집계표 ↔ 원가계산서 대사
    assert y["input"]["total_construction_cost"] == 506_000_000


def test_partial_case_renders_construction_page_and_skips_4axis():
    cases_by_id = {c["case_id"]: c for c in C.load_cases()}
    y = cases_by_id["yonggyun"]
    html_out = bs.partial_construction_page(y)
    assert "시공축 부분 케이스" in html_out or "부분 케이스" in html_out
    assert "506,000,000" in html_out                  # 도급비
    assert "골조(MS신형 125-75)" in html_out           # 공종 표
    assert "벤치마크" in html_out                      # benchmark_check 연동
    assert "ROI" not in html_out                       # 4축 경제성 미산출(가공값 금지)
    # 로더가 partial을 정상 케이스로 오인해 FarmInput 변환을 시도하면 안 된다
    import pytest as _pt
    with _pt.raises(TypeError):
        C.case_to_input(y)   # 필수 필드 없음 — 부분 케이스는 이 경로로 못 감(main이 분기)


# ── financing 기입양식(2026-08-18): 예시 파일 무결성 ─────────────────────

def test_financing_example_file_is_valid_and_clearly_synthetic():
    # 예시 파일은 (a) 스키마대로 엔진 계산이 돌아가야 하고, (b) 합성 예시임이
    # 명시돼 있어야 하며(실케이스 오염 방지), (c) cases/ 밖에 있어야 한다.
    with open("financing_예시.json", encoding="utf-8") as f:
        data = json.load(f)
    fin = data["financing"]
    assert "예시" in fin["note"] or "합성" in fin["note"]
    am = e.loan_amortization(fin["loan_principal_won"], fin["annual_rate_pct"],
                             fin["term_years"], fin.get("grace_years", 0), fin["method"])
    assert len(am["rows"]) == fin["term_years"]
    assert am["rows"][-1]["잔액"] == 0.0
    assert not os.path.exists(os.path.join("cases", "financing_예시.json"))


# ── 시나리오 가정값 스키마(2026-08-18, 데이터 대기 ④) ───────────────────

def _uminjae_with_example_scenarios():
    cases_by_id = {c["case_id"]: c for c in C.load_cases()}
    base = cases_by_id["uminjae"]
    with open("시나리오_예시.json", encoding="utf-8") as f:
        sc = json.load(f)["scenarios"]
    return dict(base, scenarios=sc), C.case_to_input(base)


def test_scenario_rows_engine_recompute_and_direction():
    case, inp = _uminjae_with_example_scenarios()
    rows = bs.scenario_rows(case, inp)
    assert rows[0]["name"].startswith("Base") and len(rows) == 4   # Base + 3세트
    by = {r["name"]: r["res"]["economics"] for r in rows}
    # 방향성: 수확·단가 상향(Best)은 Base보다 ROI 상승, Worst는 하락(엔진 재계산 일관성)
    assert by["Best"]["roi"] > by["Base(케이스 입력)"]["roi"] > by["Worst"]["roi"]
    # 예시 무결성: 합성 명시·cases/ 밖
    with open("시나리오_예시.json", encoding="utf-8") as f:
        note = json.load(f)["scenarios"]["note"]
    assert "예시" in note or "합성" in note
    assert not os.path.exists(os.path.join("cases", "시나리오_예시.json"))


def test_scenario_rows_rejects_bad_fields_and_missing_note():
    import pytest as _pt
    case, inp = _uminjae_with_example_scenarios()
    bad = dict(case, scenarios={"note": "t", "sets": [
        {"name": "X", "assumptions": {"snow_cm": 100}, "note": "물리 입력 변경 시도"}]})
    with _pt.raises(ValueError):
        bs.scenario_rows(bad, inp)          # 화이트리스트 밖 필드 거부
    noname = dict(case, scenarios={"note": "t", "sets": [
        {"name": "Y", "assumptions": {"opex": 1_000_000}, "note": ""}]})
    with _pt.raises(ValueError):
        bs.scenario_rows(noname, inp)       # 근거(note) 필수


def test_scenario_section_renders_conditionally_and_irr_label():
    case, inp = _uminjae_with_example_scenarios()
    res = rr.compute(inp)
    html_with = bs.consulting_report_page(case, res, inp)
    assert "시나리오 표 (가정 주입" in html_with and "Worst" in html_with
    assert "산출불가(적자)" in html_with     # 적자 시나리오 IRR 오독 방지 분기
    cases_by_id = {c["case_id"]: c for c in C.load_cases()}
    plain = cases_by_id["uminjae"]
    html_without = bs.consulting_report_page(plain, res, inp)
    assert "시나리오 가정값 미제공" in html_without
    assert "시나리오 표 (가정 주입" not in html_without


# ── 리모델링 실측 사례(2026-08-18, 데이터 대기 ③ 표본 1호) ──────────────

def test_partial_case_mulhyangki_remodeling_structure():
    cases_by_id = {c["case_id"]: c for c in C.load_cases()}
    mh = cases_by_id["mulhyangki"]
    assert mh.get("partial") == "construction_only"
    assert "재축" in mh["input"]["business_type"]
    cs = mh["construction"]["cost_summary_won"]
    # 총액 3중 대사 구조: 절사 전 89,610,883 → 천단위 절사 89,610,000(한글 대사)
    assert cs["원가계산 합계(절사 전)"] == 89_610_883
    assert cs["총공사비(도급, 천단위 절사)"] == 89_610_000
    assert mh["input"]["total_construction_cost"] == 89_610_000
    # 리모델링 특유 구조: 철거비·부산물 공제(음수)·폐기물처리 실존
    trades = mh["construction"]["trades_material_won"]
    assert any("철거" in k for k in trades)
    assert any(v < 0 for v in trades.values())          # 고철 매각 공제
    assert any("폐기물" in k for k in trades)
    # 부분 발췌임이 명시돼야 한다(전액 대사로 오독 방지)
    assert "부분 발췌" in mh["construction"]["trades_note"]


def test_partial_case_mulhyangki_renders():
    cases_by_id = {c["case_id"]: c for c in C.load_cases()}
    mh = cases_by_id["mulhyangki"]
    html_out = bs.partial_construction_page(mh)
    assert "재축" in html_out and "폭설피해복구" in html_out
    assert "89,610,000" in html_out
    assert "-432,000" in html_out or "−432,000" in html_out   # 공제 항목 노출
    assert "ROI" not in html_out                              # 4축 미산출 유지
