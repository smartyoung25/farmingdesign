# -*- coding: utf-8 -*-
"""financing 실조건 미리보기 — 케이스에 붙이기 전에 상환표를 눈으로 확인한다.

사용:
  python financing_미리보기.py financing_예시.json      # {"financing": {...}} 파일
  python financing_미리보기.py cases/uminjae.json       # financing 블록이 있는 케이스도 동일

계산은 전적으로 smartfarm_engine.loan_amortization()에 위임(P3-18) — 이 스크립트는
출력만 한다. 스키마·기입 절차는 financing_실조건_기입양식.md 참고.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smartfarm_engine as e


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    fin = data.get("financing")
    if fin is None:
        print(f"'{sys.argv[1]}'에 최상위 financing 블록이 없다 — 기입양식.md 1절 스키마 참고")
        return 1

    am = e.loan_amortization(fin["loan_principal_won"], fin["annual_rate_pct"],
                             fin["term_years"], fin.get("grace_years", 0),
                             fin.get("method", "원리금균등"))
    grace = f" · 거치 {am['거치기간_년']}년" if am["거치기간_년"] else ""
    print(f"대출 {am['원금']:,.0f}원 · 연 {am['연이율_pct']}% · {am['전체기간_년']}년{grace} · {am['방식']}")
    print(f"{'연차':>4} {'구분':>4} {'원금':>14} {'이자':>13} {'납입액':>14} {'잔액':>14}")
    for r in am["rows"]:
        print(f"{r['연차']:>4} {r['구분']:>4} {r['원금']:>14,.0f} {r['이자']:>13,.0f} "
              f"{r['납입액']:>14,.0f} {r['잔액']:>14,.0f}")
    print(f"총이자 {am['총이자']:,.0f}원 · 총납입액 {am['총납입액']:,.0f}원")
    if "예시" in (fin.get("note") or "") or "합성" in (fin.get("note") or ""):
        print("⚠️ note에 '예시/합성' 표기가 있다 — 실케이스에 붙이기 전에 실제 약정 조건으로 교체할 것")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
