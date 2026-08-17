# -*- coding: utf-8 -*-
"""시나리오 가정값 미리보기 — 케이스에 붙이기 전에 다단 KPI 표를 눈으로 확인한다.

사용:
  python 시나리오_미리보기.py 시나리오_예시.json cases/uminjae.json
      # 첫 인자의 scenarios 블록을 둘째 인자 케이스에 합성해 미리보기
  python 시나리오_미리보기.py cases/uminjae.json
      # 케이스 파일에 이미 scenarios 블록이 있으면 하나만

계산·검증은 build_site.scenario_rows()(엔진 재호출·화이트리스트·근거 필수)에
위임 — 이 스크립트는 출력만 한다. 스키마는 시나리오_가정값_기입양식.md 참고.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_site as bs
import cases as C


def main():
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        return 1
    with open(sys.argv[-1], encoding="utf-8") as f:
        case = json.load(f)
    if len(sys.argv) == 3:
        with open(sys.argv[1], encoding="utf-8") as f:
            case = dict(case, scenarios=json.load(f)["scenarios"])
    if not case.get("scenarios"):
        print("scenarios 블록이 없다 — 기입양식.md 1절 스키마 참고")
        return 1
    if case.get("partial"):
        print("부분 케이스는 4축 계산이 없어 시나리오 미리보기 대상이 아니다")
        return 1

    inp = C.case_to_input(case)
    rows = bs.scenario_rows(case, inp)
    print(f"케이스: {case['title']} — 시나리오 {len(rows) - 1}세트 + Base")
    print(f"{'시나리오':14s} {'ROI':>7} {'Payback':>9} {'NPV(억)':>9} {'IRR':>7}  가정(변경분)")
    for r in rows:
        ec = r["res"]["economics"]
        pb = f"{ec['payback']:.1f}년" if ec["payback"] else "—"
        if ec["irr"] is not None:
            irr = f"{ec['irr']*100:.1f}%"
        else:
            irr = ">100%" if ec["npv"] > 0 else "산출불가"
        assum = " ".join(f"{k}={v:,}" if isinstance(v, (int, float)) else f"{k}={v}"
                         for k, v in r["assumptions"].items()) or "—"
        print(f"{r['name']:14s} {ec['roi']*100:6.1f}% {pb:>9} {ec['npv']/1e8:9.2f} {irr:>7}  {assum}")
    note = case["scenarios"].get("note", "")
    if "예시" in note or "합성" in note:
        print("⚠️ scenarios note에 '예시/합성' 표기 — 실케이스에 붙이기 전에 근거 있는 가정으로 교체할 것")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
