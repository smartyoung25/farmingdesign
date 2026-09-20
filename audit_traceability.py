"""최종 검증 게이트 — 대조가능성 자동 감사 (2026-08-18, 46차)

목적(로드맵 기둥 C-정책 2, 사용자 원지시 "최후 검증은 기존 견적·시방서·도면
원천자료 기반으로 적절한지"의 기계 판정판):
  산출물 데이터 계열(케이스·견적비교·레지스트리)의 수치가 다음 4범주 중 하나로
  분류되는지 전수 감사한다 —
  ① 엔진 재계산(rr.compute 재현) ② 레지스트리 상수(status enum+source_refs 실재)
  ③ 전사값(3중 대사 green+source_file 실재) ④ 명시 표기([추정]/[확인요망]/판단성)

자동화 경계(1절 판단성 원칙의 검증판):
  이 게이트는 "대조 가능한 상태인가"까지만 답한다. "값이 옳은가"(원문 페이지와의
  동일성·출처의 적절성·근거 약함→단정문 전환)는 레드팀·컨설턴트 몫이다.

판정 2층:
  - hard_failures: 실재 깨짐·대사 깨짐·enum 위반·엔진 재계산 실패 — 하나라도 있으면
    게이트 FAIL("근거 없는 값 금지"의 기계 판정).
  - coverage_gaps: 필수 provenance 미커버 필드 — FAIL은 아니고 백로그 목록
    (첫 감사 리포트의 갭 목록이 다음 작업 대상이 된다).

read-only. 엔진 계층(smartfarm_engine·build_site·webapp)이 이 모듈을 import하지
않는다(41차 chunk_probe와 동일 원칙 — 게이트는 감사자이지 계산 참여자가 아니다).

실행: python audit_traceability.py   (리포트 출력 + 검증게이트_감사리포트.md 갱신)
"""
import glob
import io
import json
import os
import sys

import cases as C
import render_report as rr
import build_site as bs
import smartfarm_engine as e

ROOT = os.path.dirname(os.path.abspath(__file__))
# 🔴187차 — 「결정」 추가. ★사용자가 정한 값(등급 경계 등)은 실측도 법정기준도
#   아니다. 「추정」으로 적으면 **근거를 못 찾은 값**처럼 읽히고, 「참고기준」으로
#   적으면 **외부 기준을 가져온 값**처럼 읽힌다 — 둘 다 거짓이라 칸을 새로 만든다.
STATUS_ENUM = ("실측", "부분실측", "법정기준", "공공기준", "참고기준", "추정",
               "확인요망", "미검증", "결정")
# 필수 provenance 커버 필드
#   종전(46~86차): 웹 마법사(35차)의 근거 필수 5필드 + 설계하중 2필드 = 7.
#   ⚠️ 87차 용어 정정: 이 범위는 **실수로 빠뜨린 '사각'이 아니라 35차에 사용자가 확정한
#     정책의 결과**였다(86차 기록의 "감사 사각"은 부정확한 표기라 정정한다). 72·74차의
#     '사각'은 상수가 레지스트리에 **아예 없어 감사가 볼 수 없던** 경우이고, 이건 감사가
#     케이스를 정상적으로 보되 **그 필드의 근거를 요구하지 않기로 정해 둔** 경우다.
#   ✅ 87차 확대(사용자 지시): 산출물 수치를 직접 움직이는 5필드를 추가한다 —
#     area_m2(생산량·벤치마크·ROI) · surface_area_m2·fr·t_target(난방부하) ·
#     fitness_pct(생산량). 계기는 86차 실측이다: uminjae는 provenance 14건으로 이미
#     이 필드들을 갖췄는데 wonchaewon·chuncheon은 7건 최소만 갖춰 **케이스 간 문서화
#     편차**가 드러나지 않고 있었다.
#   ⚠️ cover·crop·region은 제외했다 — 분류·식별자라 '근거'보다 '입력 자체'에 가깝고
#     uminjae조차 crop에는 provenance가 없다(일관된 기준을 세우기 전엔 넣지 않는다).
#   ⚠️ 확대 결과 coverage_gaps가 생긴다. 그것이 **감사기 설계 의도**다(위 docstring:
#     "FAIL은 아니고 백로그 목록 — 첫 감사 리포트의 갭 목록이 다음 작업 대상이 된다").
#     wonchaewon·chuncheon의 갭은 86차가 확인한 **원천자료 부재** 때문에 당장 채울 수
#     없다(원채원은 말뭉치 검색 0건).
#   ⚠️ webapp.WIZARD_PROV_FIELDS와 **짝**이다 — 한쪽만 넓히면 마법사로 만든 새 케이스가
#     생성 즉시 갭을 낸다. 87차에 함께 넓혔다(설계하중 2종은 마법사가 고시 조회로
#     자동 생성하므로 WIZARD_PROV_FIELDS에는 들어가지 않는다).
CASE_REQUIRED_PROV = ("base_yield_kg_m2", "price_won_per_kg", "opex",
                      "total_construction_cost", "subsidy_rate", "snow_cm", "wind_ms",
                      "area_m2", "surface_area_m2", "fr", "t_target", "fitness_pct")
PARTIAL_REQUIRED_PROV = ("input.total_construction_cost", "construction.cost_summary_won",
                         "construction.trades_material_won")


def _ref_ok(r: dict) -> bool:
    return bool(r.get("file")) and os.path.isfile(os.path.join(ROOT, r["file"]))


def audit_cases() -> dict:
    hard, gaps = [], {}
    for c in C.load_cases():
        cid = c["case_id"]
        prov = c.get("provenance")
        if not isinstance(prov, dict):
            hard.append((cid, "provenance dict형 아님(43차 스키마 위반)"))
            continue
        for field, v in prov.items():
            if v.get("status") not in STATUS_ENUM:
                hard.append((cid, f"{field}: status {v.get('status')!r} enum 밖"))
            if not (v.get("source") or "").strip():
                hard.append((cid, f"{field}: source 비어 있음"))
            for r in v.get("source_refs", []):
                if not _ref_ok(r):
                    hard.append((cid, f"{field}: 원문 소실 {r.get('file')}"))
        if c.get("partial"):
            missing = [f for f in PARTIAL_REQUIRED_PROV if f not in prov]
        else:
            missing = [f for f in CASE_REQUIRED_PROV if f not in prov]
            try:  # 범주 ①: 엔진 재계산 성립
                ec = rr.compute(C.case_to_input(c))["economics"]
                if not (ec["roi"] == ec["roi"]):  # NaN 가드
                    hard.append((cid, "엔진 재계산 NaN"))
            except Exception as ex:
                hard.append((cid, f"엔진 재계산 실패: {ex}"))
        if missing:
            gaps[cid] = missing
    return {"hard": hard, "gaps": gaps}


def audit_quotes() -> dict:
    hard = []
    n_vendors = 0
    for path in sorted(glob.glob(os.path.join(ROOT, "견적비교_*.json"))):
        name = os.path.basename(path)
        data = json.load(open(path, encoding="utf-8"))
        if not (data.get("provenance") or "").strip():
            hard.append((name, "provenance 비어 있음"))
        for v in data["vendor_quotes"]:
            n_vendors += 1
            vn = v["vendor_name"]
            if not v.get("source_file") or not os.path.isfile(os.path.join(ROOT, v["source_file"])):
                hard.append((name, f"{vn}: source_file 소실/비어 있음"))
            for chk in bs.quotes_vendor_3way_check(v):
                if not chk["ok"]:
                    hard.append((name, f"{vn}: 3중 대사 불일치 — {chk['name']} {chk['detail']}"))
            valid_keys = {k for k, _kor, _d in e.CAPEX_MAJOR_CATEGORIES}
            for row in v["raw_rows"]:
                key = bs.quotes_mapping_key(row[2])
                if key not in valid_keys:
                    hard.append((name, f"{vn}: 매핑 키 미등록 {key!r}"))
    return {"hard": hard, "n_vendors": n_vendors}


def audit_registry(reg=None) -> dict:
    """152차: `reg`를 주입할 수 있다 — `ref_basis` 불변식을 **합성 레지스트리로
    실제로 시험**하기 위해서다(139차 red self-test와 같은 이유: 위반이 0건이면
    검사가 도는지 결과로 구별되지 않는다). 기본은 디스크 원본이다."""
    hard = []
    if reg is None:
        reg = json.load(open(os.path.join(ROOT, "엔진데이터_레지스트리.json"),
                             encoding="utf-8"))
    attention = []  # ④범주 명시 표기 목록(FAIL 아님 — 정직 표기의 확인)
    for key, ent in reg["constants"].items():
        if ent["status"] not in STATUS_ENUM:
            hard.append((key, f"status {ent['status']!r} enum 밖"))
        if ent["status"] in ("미검증", "확인요망", "추정"):
            attention.append((key, ent["status"]))
        for r in ent.get("source_refs", []):
            if not _ref_ok(r):
                hard.append((key, f"원문 소실 {r.get('file')}"))
            if r.get("match", "exact") not in ("exact", "near", "partial"):
                hard.append((key, f"match 값 위반 {r.get('match')!r}"))
    n_refs = sum(len(ent.get("source_refs", [])) for ent in reg["constants"].values())
    # 133차 — 🔴 ref가 0건이면 위 루프가 한 번도 돌지 않는다: 그 상수의 출처는
    # 이 게이트가 **한 번도 검사한 적이 없다**. '실측'을 표방하는 상수가 그 상태면
    # 특히 위험하므로(전사 오류가 가장 일어나기 쉬운 계열이다) 드러내 둔다.
    # FAIL은 아니다 — 파생·결정 상수처럼 원문 ref 개념이 없는 것도 섞여 있다.
    blind = [(key, ent["status"]) for key, ent in reg["constants"].items()
             if ent["status"] in ("실측", "부분실측") and not ent.get("source_refs")]

    # 🔴 152차 — 사각 6건은 **한 덩어리가 아니다**(151차 발견). 자료가 들어오면
    #   풀리는 것과, 파일 ref라는 개념 자체가 성립하지 않는 것은 성격이 다르다.
    #   후자를 사각으로 세면 **영원히 0으로 남는 수를 백로그처럼 끌고 다니게 된다**.
    #   분류 근거는 **레지스트리의 `ref_basis` 선언**에서 읽는다 — 감사기에
    #   상수명을 하드코딩하면 지식이 두 곳으로 갈라지고, 서술을 파싱하면
    #   141차 교훈("파서를 쓰지 말았어야 했다")을 반복한다.
    legend = reg.get("ref_basis_legend") or {}
    structural, blocked = [], []
    for key, status in blind:
        basis = reg["constants"][key].get("ref_basis")
        (structural if basis else blocked).append((key, status, basis))

    # 불변식 — 선언이 있으면 값은 범례 안이어야 하고, refs와 공존할 수 없다
    for key, ent in reg["constants"].items():
        basis = ent.get("ref_basis")
        if basis is None:
            continue
        if basis not in legend:
            hard.append((key, "ref_basis '%s'가 ref_basis_legend에 없다" % basis))
        if ent.get("source_refs"):
            hard.append((key, "ref_basis 선언과 source_refs가 함께 있다 — "
                              "파일 ref를 붙였다면 그 선언이 틀렸다"))
    return {"hard": hard, "attention": attention, "n_constants": len(reg["constants"]),
            "n_refs": n_refs, "refless_measured": blind,
            "refless_blocked": blocked, "refless_structural": structural}


def audit() -> dict:
    ca, qu, rg = audit_cases(), audit_quotes(), audit_registry()
    hard = ca["hard"] + qu["hard"] + rg["hard"]
    return {"ok": not hard, "hard_failures": hard, "case_coverage_gaps": ca["gaps"],
            "refless_blocked": rg["refless_blocked"],
            "refless_structural": rg["refless_structural"],
            "registry_attention": rg["attention"],
            "refless_measured": rg["refless_measured"],
            "counts": {"cases": len(C.load_cases()), "quote_vendors": qu["n_vendors"],
                       "registry_constants": rg["n_constants"], "source_refs": rg["n_refs"]}}


def render_report(a: dict) -> str:
    lines = ["# 검증 게이트 감사 리포트 (audit_traceability — 46차 신설)", "",
             f"판정: {'PASS — hard 결함 0건' if a['ok'] else 'FAIL — hard 결함 ' + str(len(a['hard_failures'])) + '건'}",
             f"규모: 케이스 {a['counts']['cases']}건 · 견적 업체 {a['counts']['quote_vendors']}건 · "
             f"레지스트리 상수 {a['counts']['registry_constants']}개(source_refs {a['counts']['source_refs']}건)", ""]
    if a["hard_failures"]:
        lines.append("## hard 결함 (게이트 FAIL 사유 — 즉시 수정 대상)")
        lines += [f"- {w}: {msg}" for w, msg in a["hard_failures"]]
        lines.append("")
    lines.append("## 케이스 provenance 커버리지 갭 (FAIL 아님 — 백로그)")
    if a["case_coverage_gaps"]:
        for cid, fields in a["case_coverage_gaps"].items():
            lines.append(f"- {cid}: {', '.join(fields)}")
    else:
        lines.append("- 없음")
    lines += ["", "## 명시 표기 상수 (④범주 — 정직 표기 확인, FAIL 아님)"]
    lines += [f"- {k}: {s}" for k, s in a["registry_attention"]] or ["- 없음"]
    nb, ns = len(a["refless_blocked"]), len(a["refless_structural"])
    lines += ["", "## 추적성 사각 — '실측' 계열인데 source_refs 0건 "
                  "(133차 신설 · **152차 분류**, FAIL 아님)",
              "> ref가 0건이면 원문 실재 검사가 **한 번도 돌지 않는다**. 아래 상수의 출처는",
              "> 이 게이트가 검사한 적이 없다 — 서술만 읽고 믿는 상태다.",
              "> 🔴 151차 실증: `OVERHEAD_RATES`를 붙여 보니 등재 서술의 단정이 **반증**됐다.",
              "",
              f"### (가) 원문이 리포에 없어 못 붙인다 — 자료가 들어오면 풀린다 ({nb}건)"]
    lines += [f"- {k}: {s}" for k, s, _ in a["refless_blocked"]] or ["- 없음"]
    lines += ["",
              f"### (나) 파일 ref 개념이 성립하지 않는다 — **사각이 아니다** ({ns}건)",
              "> 레지스트리 `ref_basis` 선언으로 분리한 것이다(`ref_basis_legend` 참고).",
              "> 이쪽은 자료가 들어와도 0으로 남는다 — 백로그로 세지 말 것."]
    lines += [f"- {k}: {s} — `{b}`" for k, s, b in a["refless_structural"]] or ["- 없음"]
    lines += ["", f"> **실제 백로그는 (가) {nb}건**이다(총 {nb + ns}건 중)."]
    lines += ["", "> 이 게이트는 '대조 가능한 상태인가'까지만 답한다 — 값의 옳음(원문 동일성·출처",
              "> 적절성·근거 약함→단정문)은 레드팀·컨설턴트 몫(판단성). 절차: 검증절차_레드팀.md"]
    return "\n".join(lines)


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    a = audit()
    report = render_report(a)
    out = os.path.join(ROOT, "검증게이트_감사리포트.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(report)
    print(f"\n리포트 저장: {os.path.basename(out)}")
    sys.exit(0 if a["ok"] else 1)


if __name__ == "__main__":
    main()
