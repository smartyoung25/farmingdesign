# -*- coding: utf-8 -*-
"""P3-20(2026-08-17) 재점검 시연 → P3-23으로 사이트 파이프라인에 정식 연결됨.
실행: python demo_compare_quotes_실견적3사.py

데이터는 견적비교_논산딸기3사.json 단일 소스(3사 공종별 집계표 원문 전사,
공종 합계=총액 원단위 일치 검증됨), 계산·렌더 연결은 build_site.py의
load_quotes_comparison()/quotes_comparison_page()가 담당한다. 이 스크립트는
같은 로더를 불러 콘솔 요약만 출력한다(P3-20 재점검의 재현 가능한 증거물).

시연에서 확인된 실질 컨설팅 신호(2026-08-17):
  · 임미라: hvac 누락 플래그 — '양액시설, 및 난방' 혼재 표기 검출
  · 최선동: 면적 정합 불일치(사양서 4,000㎡ vs 견적 3,145㎡, 21.4%)
  · 3사 공통: 규격코드 미기재(확인요망), 총액 밴드 내 정상(137,843~195,161원/㎡)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smartfarm_engine as e
from build_site import load_quotes_comparison

data, rfq, cmp = load_quotes_comparison()
ri = data["rfq_input"]
print(f"[7단계] RFQ: {ri['region']}(적설 {ri['region_snow_cm']}·풍속 {ri['region_wind_ms']}) "
      f"→ 규격 {rfq.spec_name} | 난방부하 {rfq.heating.max_load_kcal_h:,.0f} kcal/h")
print(f"\n  {'업체':16s} {'종합':12s} {'일치도':>5s} {'총액':>13s} {'원/㎡':>9s}")
for r in cmp.rows:
    print(f"  {r.vendor_name:16s} {r.overall_status:12s} {r.match_score_pct:4.0f}% "
          f"{r.total_with_overhead_won:13,.0f} {r.unit_won_m2:9,.0f}")
print(f"  (참고) 최저가: {cmp.lowest_cost_vendor} / 최고일치: {cmp.highest_match_score_vendor} — 추천 아님")
for name, recon in cmp.reconciliations.items():
    flags = [f"{c.name}:{c.status}({c.detail})" for c in recon.checks if c.status not in ("일치", "정상")]
    if flags:
        print(f"  · {name}: {' / '.join(flags[:3])}")

# ── 3·6단계 확장 기능 실데이터 동작 확인(P3-20 재점검분 유지) ──
rows = e.equipment_lookup("환경제어기")
prices = []
for r in rows:
    t = e.equipment_component_prices(r.get("모델명", "")).get("필수구성품_합계_원") or 0
    if t > 0:
        prices.append(t)
print(f"\n[3단계] 환경제어기 {len(rows)}모델, 구성품 가격 연결 {len(prices)}건"
      + (f" ({min(prices):,}~{max(prices):,}원)" if prices else ""))
cl = e.subsidy_application_checklist()
print(f"[6단계] 보조사업 체크리스트 {len(cl)}단계 — 전항목 확인요망: {all(c['상태'] == '확인요망' for c in cl)}")
print(f"[7단계 보조] 전북 시공업체 {len(e.construction_company_list('전북'))}곳")
