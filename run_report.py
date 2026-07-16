"""
SmartFarm 4축 리포트 실행 스크립트
입력(부지·작목·면적·유형·피복 등) → 진단·설계·시공·경제성 리포트 출력.
실시간 시세(단가·노임·유가)는 인자로 주입(엔진은 조회 안 함).
실행: python run_report.py
"""
import smartfarm_engine as e
from dataclasses import dataclass


@dataclass
class FarmInput:
    business_type: e.BusinessType
    crop: str
    region: str
    area_m2: float
    cover: e.Cover
    snow_cm: float
    wind_ms: float
    surface_area_m2: float
    t_target: float
    t_min: float
    fr: float
    base_yield_kg_m2: float
    price_won_per_kg: float
    fitness_pct: float
    opex: float
    total_construction_cost: float
    subsidy_rate: float = 0.0


def build_report(inp: FarmInput) -> str:
    L = []
    L.append(f"{'='*56}")
    L.append(f" SmartFarm 4축 리포트 — {inp.crop} / {inp.business_type.value}")
    L.append(f" {inp.region} · {inp.area_m2:,.0f}㎡ ({e.m2_to_py(inp.area_m2):,.0f}평) · {inp.cover.value}")
    L.append(f"{'='*56}")
    sel = e.select_specs(inp.snow_cm, inp.wind_ms)
    L.append("\n[설계] 내재해형 규격 선정 (지역 설계강도 충족)")
    L.append(f"  적설심 {inp.snow_cm}cm / 풍속 {inp.wind_ms}m/s → 충족 {len(sel['candidates'])}종")
    for form, s in sel["min_by_form"].items():
        L.append(f"   · {form} 최소사양: {s.name} (설계 적설심{s.snow_cm}/풍속{s.wind_ms})")
    hr = e.heating_load(inp.surface_area_m2, inp.cover.value,
                        inp.t_target, inp.t_min, inp.fr, floor_area_m2=inp.area_m2)
    v = e.verify_heating_vs_actual(hr.load_per_m2, inp.cover.value)
    L.append("\n[설계/시공] 난방부하")
    L.append(f"  최대난방부하 {hr.max_load_kcal_h:,.0f} kcal/h ({hr.load_per_m2:,.0f} kcal/h·㎡)")
    L.append(f"  난방기 용량 {hr.heater_capacity_kcal_h:,.0f} kcal/h")
    L.append(f"  실측 대조: 기준 {v['ref_kcal_h_m2']} × {v['ratio']} → {v['status']}")
    bc = e.benchmark_check(inp.total_construction_cost, inp.area_m2, inp.cover)
    L.append(f"\n[시공] 총공사비 벤치마크 대조 ({len(e.ACTUALS)}건 A-11)")
    L.append(f"  총공사비 {inp.total_construction_cost:,.0f}원 = {bc['unit_won_m2']:,}원/㎡")
    L.append(f"  {inp.cover.value} 밴드 {bc['band'][0]:,}~{bc['band'][1]:,} → {bc['status']}")
    prod = e.production_kg(inp.area_m2, inp.base_yield_kg_m2, inp.fitness_pct)
    revenue = prod * inp.price_won_per_kg
    fin = e.finance(revenue, inp.opex, inp.total_construction_cost, subsidy_rate=inp.subsidy_rate)
    L.append("\n[경제성] 생산·수익")
    L.append(f"  환경적합도 {inp.fitness_pct:.0f}% → 수율조정 {e.yield_adjustment(inp.fitness_pct)*100:+.0f}%")
    L.append(f"  생산량 {prod:,.0f} kg × {inp.price_won_per_kg:,.0f}원 = 매출 {revenue:,.0f}원")
    L.append(f"  OPEX {inp.opex:,.0f} · 감가 {fin.depreciation:,.0f}")
    L.append(f"  영업이익 {fin.operating_profit:,.0f}원")
    L.append(f"  ROI {fin.roi:.1%} · Payback {fin.payback_years:.1f}년" if fin.payback_years else "  (초기적자·J커브)")
    if fin.npv is not None:
        L.append(f"  NPV(10y,5%) {fin.npv:,.0f}원 · IRR {fin.irr:.1%}" if fin.irr else "  IRR N/A")
    if fin.real_roi_after_subsidy:
        L.append(f"  보조금 {inp.subsidy_rate:.0%} 반영 실질ROI {fin.real_roi_after_subsidy:.1%}")
    L.append("\n※ 단가·노임·유가는 조회 시점 실측 주입값 기준. 투자 확정조언 아님(추정).")
    return "\n".join(L)


def demo():
    inp = FarmInput(
        business_type=e.BusinessType.NEW,
        crop="토마토", region="충남", area_m2=3456, cover=e.Cover.GLASS,
        snow_cm=30, wind_ms=35,
        surface_area_m2=5000, t_target=10, t_min=-7.8, fr=0.7,
        base_yield_kg_m2=38.5, price_won_per_kg=2500, fitness_pct=95,
        opex=186_420_000, total_construction_cost=702_030_000,
        subsidy_rate=0.5,
    )
    print(build_report(inp))


if __name__ == "__main__":
    demo()
