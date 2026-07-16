"""
SmartFarm 4축 리포트 — 춘천(강원) 케이스 생성기 (경로 C)
- 계산은 전적으로 smartfarm_engine 에 위임(엔진이 유일한 계산 출처).
- 원채원(충남) 케이스와 '농가 규모/피복/주입 시세값'은 동일하게 두고,
  지역 기인 변수만 춘천 기준으로 교체 → 기후·설계강도 차이 효과를 분리해 보인다.

지역 기인 교체값(근거):
  · 난방 설계 외기온도 t_min = -14.7°C
      (건축물에너지절약설계기준 별표7 / 대한설비공학회 냉난방설계용 표준기상데이터, 춘천)
      ↔ 충남 원채원 데모는 -7.8°C
  · 설계 적설심 40cm / 설계 풍속 30m/s  (강원 춘천 내재해형 설계강도 통상값)
      ※ 정확한 내재해형 '지정값'은 농사로 '원예특작시설 내재해형 기준'에서 확인 요망 [확인요망]

주입 시세값(단가·OPEX·총공사비)은 baseline 과 동일하게 두었다. 실제 춘천은
한랭지라 난방 연료비(OPEX)와 적설 대응 구조비(총공사비)가 baseline 보다 높을 개연성이 크다 [추정].
정확한 견적·시세가 확보되면 해당 칸만 교체해 재생성하면 된다.

실행: python render_chuncheon.py
"""
import smartfarm_engine as e
from run_report import FarmInput
from render_report import compute, render_html


def chuncheon_input() -> FarmInput:
    return FarmInput(
        business_type=e.BusinessType.NEW,
        crop="토마토", region="강원(춘천)", area_m2=3456, cover=e.Cover.GLASS,
        snow_cm=40, wind_ms=30,               # 춘천 설계강도(통상값) [확인요망]
        surface_area_m2=5000, t_target=10,
        t_min=-14.7,                          # 춘천 난방 설계 외기온도(별표7)
        fr=0.7,
        base_yield_kg_m2=38.5, price_won_per_kg=2500, fitness_pct=95,
        opex=186_420_000, total_construction_cost=702_030_000,  # baseline 동일 [추정]
        subsidy_rate=0.5,
    )


def main(out_path: str = "SmartFarm_리포트_춘천.html") -> dict:
    inp = chuncheon_input()
    res = compute(inp)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(render_html(res))
    return res


if __name__ == "__main__":
    r = main()
    h, ec = r["heating"], r["economics"]
    print("HTML 생성 완료 · SmartFarm_리포트_춘천.html")
    print(f"난방부하 {h['max_load']:,.0f} kcal/h ({h['load_per_m2']:,.0f}/㎡)"
          f" · 실측대조 {h['status']}")
    print(f"ROI {ec['roi']:.1%} · Payback {ec['payback']:.1f}년 · 실질ROI {ec['real_roi']:.1%}")
