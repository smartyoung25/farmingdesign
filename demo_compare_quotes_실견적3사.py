# -*- coding: utf-8 -*-
"""P3-20(2026-08-17) — 3~7단계 확장 기능을 실제 케이스 데이터로 실행한 재점검 시연.
실행: python demo_compare_quotes_실견적3사.py

7단계: P2-16으로 편입된 실견적 3건(임미라·최선동·한수진 — 전부 필름 연동
딸기하우스, 496~561M 직접공사비)을 compare_quotes()에 대입. 3사 공종별 금액은
각 견적서 '공종별 집계표' 시트에서 원문 전사(문서청킹 인덱스로 추출·합계 대사).
공종→카테고리 매핑 원칙: 혼재 행(예: 임미라 '양액시설, 및 난방')은 근거 없이
금액을 쪼개지 않고 지배 항목에 통째 배정 — 누락 플래그가 뜨면 그게 곧 "견적서가
해당 공종을 분리 표기하지 않았다"는 정직한 컨설팅 신호다(실행 결과 실제로
임미라 hvac 누락·최선동 면적차 21.4%·3사 규격코드 미기재가 검출됐다).

이 스크립트는 P3-20 재점검의 증거물이자, compare_quotes()를 케이스 파이프라인에
연결할 때의 프로토타입이다(연결 여부는 사용자 결정 대기 — 작업지시서 11절).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smartfarm_engine as e

# ── 7단계: RFQ + 실견적 3건 비교 ──
region = "논산"
load = e.REGION_DESIGN_LOAD[region]
snow, wind = load["snow_cm"], load["wind_ms"]
print(f"[7단계] RFQ 지역: {region} (적설 {snow}cm · 풍속 {wind}m/s)")

rfq = e.generate_rfq_package(
    region_snow_cm=snow, region_wind_ms=wind,
    area_m2=4000, cover=e.Cover.FILM, form="연동",
    t_target=15, t_min=-12.4, curtain="다겹보온",  # P1-9 신설 경로 사용
    crop="딸기",                                     # P1-11 신설 필터 사용
)
print(f"  채택 규격: {rfq.spec_name} (적설 {rfq.snow_cm}·풍속 {rfq.wind_ms}) | "
      f"난방부하 {rfq.heating.max_load_kcal_h:,.0f} kcal/h")

VQ = e.VendorQuote
quotes = [
    # 임미라(수현건설) — 4,068㎡ 6연동. '양액시설, 및 난방' 혼재행은 양액에 통배정(주:난방 미분리)
    VQ("임미라(수현건설)", {
        "greenhouse_structure": 184464840 + 37693320,          # 골조 + 피복
        "auto_opening_system": 51252000 + 90913900,            # 자동개폐·ICT혼재 + 커튼(08-17 결정)
        "irrigation_fertigation": 178420700,                   # 양액+난방 혼재(분리 불가)
        "equipment_procurement": 8000000,                      # 물류·장비
        "design_supervision_fee": 10000000,                    # 컨설팅의뢰비
    }, direct_cost_total=560744760, total_with_overhead=560744760, area_m2=4068),
    # 최선동(렉창) — 3,145㎡ 5연동
    VQ("최선동(렉창)", {
        "greenhouse_structure": 27797500 + 52536750 + 88677050 + 29827800,  # 기초+철골+부속+비닐
        "auto_opening_system": 51928500 + 84427760,            # 천창개폐 + 커튼
        "hvac": 81345000,                                      # 유동·배기휀(송풍기류, 무인방제 혼재)
        "irrigation_fertigation": 67981200 + 12919200,         # 양액 + 배관설비
    }, direct_cost_total=497440760, total_with_overhead=613782000, area_m2=3145),
    # 한수진 — 4,092㎡ 6연동
    VQ("한수진", {
        "greenhouse_structure": 24208000 + 61670790 + 113364250 + 38202700,
        "auto_opening_system": 6660000 + 87316810,
        "hvac": 66930000,                                      # 휀·냉난방시설
        "irrigation_fertigation": 86983850 + 13690000,
    }, direct_cost_total=499026400, total_with_overhead=618001000, area_m2=4092),
]

cmp = e.compare_quotes(rfq, quotes)
print(f"\n  {'업체':16s} {'종합':12s} {'일치도':>6s} {'총액':>13s} {'원/㎡':>9s}")
for r in cmp.rows:
    print(f"  {r.vendor_name:16s} {r.overall_status:12s} {r.match_score_pct:5.0f}% "
          f"{r.total_with_overhead_won:13,.0f} {r.unit_won_m2:9,.0f}")
print(f"  (참고) 최저가: {cmp.lowest_cost_vendor} / 최고일치: {cmp.highest_match_score_vendor} — 추천 아님")
for name, recon in cmp.reconciliations.items():
    flags = [f"{c.name}:{c.status}({c.detail})" for c in recon.checks if c.status != "일치"]
    if flags:
        print(f"  · {name}: {' / '.join(flags[:3])}")

# ── 3단계: 기자재DB 실측 대조 ──
print("\n[3단계] equipment_lookup('환경제어기'):")
rows = e.equipment_lookup("환경제어기")
prices = []
for r in rows:
    comp = e.equipment_component_prices(r.get("모델명", ""))
    t = comp.get("필수구성품_합계_원") or 0
    if isinstance(t, (int, float)) and t > 0:
        prices.append(t)
print(f"  등록 모델 {len(rows)}건, 구성품 가격 확보 {len(prices)}건")
if prices:
    print(f"  필수구성 합계 범위: {min(prices):,} ~ {max(prices):,}원")
    print(f"  실측 대조: 최혁진 0113 환경제어 46,927,833원 / 윤성호 55,000,000원 — DB 범위와 자릿수 정합 여부 확인용")

# ── 6단계: 보조사업 체크리스트 / 시공업체 ──
cl = e.subsidy_application_checklist()
print(f"\n[6단계] 체크리스트 {len(cl)}단계 — 전부 상태='확인요망'인가: {all(c['상태'] == '확인요망' for c in cl)}")
comp = e.construction_company_list("전북")
print(f"[7단계 보조] 전북 시공업체: {len(comp)}곳")

# ── 3단계 보조: 품셈 ──
k = next(iter(e.PUMSEM_ITEM_BY_KEY))
d = e.pumsem_labor_days(k[0], k[1], 100)
print(f"[3단계 보조] pumsem_labor_days({k[0]},{k[1]},100) → 직종 {len(d.get('직종별_인일', d))}개 항목 반환")
print(f"  없는 조합 → {e.pumsem_labor_days('철골공사', '존재하지않는품목', 1)} (None=정직)")
