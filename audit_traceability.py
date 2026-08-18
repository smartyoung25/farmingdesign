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
STATUS_ENUM = ("실측", "부분실측", "법정기준", "공공기준", "참고기준", "추정", "확인요망", "미검증")
# 필수 provenance 커버 필드 — 웹 마법사(35차)의 근거 필수 5필드 + 설계하중 2필드
CASE_REQUIRED_PROV = ("base_yield_kg_m2", "price_won_per_kg", "opex",
                      "total_construction_cost", "subsidy_rate", "snow_cm", "wind_ms")
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


def audit_registry() -> dict:
    hard = []
    reg = json.load(open(os.path.join(ROOT, "엔진데이터_레지스트리.json"), encoding="utf-8"))
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
    return {"hard": hard, "attention": attention, "n_constants": len(reg["constants"]),
            "n_refs": n_refs}


def audit() -> dict:
    ca, qu, rg = audit_cases(), audit_quotes(), audit_registry()
    hard = ca["hard"] + qu["hard"] + rg["hard"]
    return {"ok": not hard, "hard_failures": hard, "case_coverage_gaps": ca["gaps"],
            "registry_attention": rg["attention"],
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
