"""
SmartFarm 계산 엔진 (결정론적 코어)
- 진단·설계·시공·경제성 4축 중 '자동화하기(계산)' 부분을 함수로 고정.
- 실시간 시세(시장가격·노임·유가)는 인자로 주입받는다(엔진은 조회하지 않음).
- 근거: SmartFarm_엔진데이터.md의 A-2/A-5/A-11/A-12, B(환경인자), C(재무).
모든 단가·규격은 특정 시점 실측 기반 → 밴드/기준시점 개념으로 사용.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

PYEONG_TO_M2 = 3.3058


# ─────────────────────────────────────────────────────────────
# 공통 유형
# ─────────────────────────────────────────────────────────────
class BusinessType(str, Enum):
    NEW = "신규"
    RENEWAL = "리뉴얼"
    CLUSTER = "단지"


class Cover(str, Enum):
    FILM = "필름"          # PO/PE 연동
    GLASS = "유리"          # 유리/PC복층 + 난방
    FLUORINE = "불소필름"    # F-Clean 등 고급
    SINGLE = "단동"


def py_to_m2(py: float) -> float:
    return py * PYEONG_TO_M2


def m2_to_py(m2: float) -> float:
    return m2 / PYEONG_TO_M2


# ─────────────────────────────────────────────────────────────
# 설계 E2: 내재해형 규격 선정 (엔진데이터 A-2, 실행검증 완료)
#   8열=설계적설심(cm), 9열=설계풍속(m/s).
#   2026-07 출처 확정: 농림축산식품부 고시 제2014-78호 "원예특작시설 내재해형
#   규격 설계도·시방서"(농사로 게재) 원문 대조 — 연동5·단동19·광폭8=32종 전체 수록
#   (과수3·인삼20·버섯2종은 작목 전용 구조라 범위 밖, 미수록).
#   대조 결과 기존 07-단동-4·10-단동-4의 width_m이 오기(각각 5.0→8.0, 7.0→8.2)로
#   확인돼 고시 원문 값으로 수정(적설심·풍속은 원래도 일치). width_m은 select_specs()
#   필터링에 쓰이지 않는 표시용 값이라 이 수정이 기존 계산 결과에 영향을 주지 않음.
# ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Spec:
    name: str
    form: str          # 연동/단동/광폭
    width_m: float
    snow_cm: int       # 설계 적설심
    wind_ms: int       # 설계 풍속

# 농식품부 고시 제2014-78호 원문 32종 전체(연동5+단동19+광폭8).
SPEC_TABLE: list[Spec] = [
    # 연동형(5종)
    Spec("07-연동-1", "연동", 7.0, 53, 40),
    Spec("08-연동-1", "연동", 8.0, 57, 36),
    Spec("10-연동-1", "연동", 8.0, 55, 40),
    Spec("10-연동-2", "연동", 8.0, 55, 40),
    Spec("12-연동-1", "연동", 7.0, 55, 40),
    # 단동형(19종)
    Spec("07-단동-1", "단동", 5.0, 50, 35),
    Spec("07-단동-2", "단동", 6.0, 50, 35),
    Spec("07-단동-3", "단동", 7.0, 50, 36),
    Spec("07-단동-4", "단동", 8.0, 48, 37),
    Spec("10-단동-1", "단동", 6.0, 41, 32),
    Spec("10-단동-2", "단동", 7.0, 42, 35),
    Spec("10-단동-3", "단동", 7.0, 37, 33),
    Spec("10-단동-4", "단동", 8.2, 41, 35),
    Spec("10-단동-5", "단동", 8.2, 30, 32),
    Spec("10-단동-6", "단동", 7.6, 28, 39),
    Spec("10-단동-7", "단동", 8.9, 27, 41),
    Spec("10-단동-8", "단동", 7.6, 25, 33),
    Spec("10-단동-9", "단동", 8.9, 26, 36),
    Spec("10-단동-10", "단동", 5.4, 30, 28),
    Spec("10-단동-11", "단동", 5.6, 29, 27),
    Spec("10-단동-12", "단동", 5.6, 27, 27),
    Spec("10-단동-13", "단동", 5.8, 30, 28),
    Spec("07-단동-18", "단동", 7.0, 50, 40),
    Spec("12-단동-1", "단동", 7.0, 55, 42),
    # 광폭형(8종)
    Spec("10-광폭-1(아치)", "광폭", 14.8, 33, 40),
    Spec("10-광폭-2(트러스)", "광폭", 16.0, 35, 40),
    Spec("13-광폭(보온재)-1", "광폭", 14.0, 25, 28),
    Spec("13-광폭(보온재)-2", "광폭", 16.0, 23, 28),
    Spec("13-광폭(보온재)-3", "광폭", 18.0, 23, 29),
    Spec("13-광폭(보온재)-4", "광폭", 21.0, 23, 27),
    Spec("13-광폭(보온재)-5", "광폭", 24.0, 20, 27),
    Spec("13-광폭(보온재)-6", "광폭", 27.0, 20, 27),
]


def select_specs(region_snow_cm: float, region_wind_ms: float,
                 form: Optional[str] = None) -> dict:
    """지역 설계강도를 충족하는 규격 필터 + 형식별 최소사양.
    조건: 설계적설심 >= 지역적설심 AND 설계풍속 >= 지역풍속 (과설계 지양은 최소사양으로)."""
    ok = [s for s in SPEC_TABLE
          if s.snow_cm >= region_snow_cm and s.wind_ms >= region_wind_ms
          and (form is None or s.form == form)]
    # 형식별 최소사양(적설심, 풍속 오름차순 최솟값)
    per_form: dict[str, Spec] = {}
    for s in ok:
        cur = per_form.get(s.form)
        if cur is None or (s.snow_cm, s.wind_ms) < (cur.snow_cm, cur.wind_ms):
            per_form[s.form] = s
    return {"candidates": ok, "min_by_form": per_form}


# ─────────────────────────────────────────────────────────────
# 설계 E7 / 시공 C7: 난방부하 (엔진데이터 A-4/A-5, A-12 이중검증)
# ─────────────────────────────────────────────────────────────
# 난방부하계수 U (kcal/㎡·hr·℃)
U_VALUE = {"유리": 5.3, "필름": 5.7, "불소필름": 5.7, "단동": 5.7}
# 보온비 fr (피복조합)
FR_TABLE = {"PO단일": 0.35, "다겹보온": 0.5, "이중커튼": 0.85, "2중커튼": 0.85}
# 연료 순발열량 (kcal/단위) - A-5
FUEL_LHV = {"등유": 8170, "경유": 8410, "B-C유": 9360,
            "LPG프로판": 11060, "LNG": 11800, "전기": 2290}


@dataclass
class HeatingResult:
    max_load_kcal_h: float       # 최대난방부하
    load_per_m2: float           # 면적당 부하
    heater_capacity_kcal_h: float
    fuel_consumption: float      # 연료소비량(단위)
    fuel_unit_lhv: float


def heating_load(surface_area_m2: float, cover: str, t_target: float,
                 t_min: float, fr: float, safety: float = 1.1,
                 degree_hours: float = 10098.0, efficiency: float = 0.85,
                 fuel: str = "등유", floor_area_m2: Optional[float] = None
                 ) -> HeatingResult:
    """최대난방부하 = Aw × U × ΔT × 보온비. (A-5 구조)
    degree_hours: 난방디그리아워(기본은 A-5 예시값). fuel: 연료종류."""
    u = U_VALUE.get(cover, 5.7)
    dt = t_target - t_min
    max_load = surface_area_m2 * u * dt * fr
    heater = max_load * safety
    period_load = degree_hours * u * fr * surface_area_m2  # 기간난방부하 근사
    lhv = FUEL_LHV.get(fuel, 8170)
    fuel_use = period_load / (lhv * efficiency)
    denom = floor_area_m2 or surface_area_m2
    return HeatingResult(max_load, max_load / denom, heater, fuel_use, lhv)


def verify_heating_vs_actual(load_per_m2: float, cover: str) -> dict:
    """A-12 실측(유리 약 231 kcal/h·㎡)과 이중검증.
    실측은 설계외기온·목표온도·보온비에 따라 크게 변동하므로 넓은 허용범위 사용.
    핵심 목적: 자릿수 오류(10배·0.1배)를 잡는 것이지 정밀 일치가 아님."""
    ref = 231 if cover in ("유리",) else 180  # 필름 기준 근사
    ratio = load_per_m2 / ref
    # 0.35~1.8: 설계조건 편차 허용. 이 범위 밖이면 입력 점검 신호.
    status = "정상" if 0.35 <= ratio <= 1.8 else "재확인(입력 외기온·보온비 점검)"
    return {"ref_kcal_h_m2": ref, "ratio": round(ratio, 2), "status": status}


# ─────────────────────────────────────────────────────────────
# 입지: 지역→설계하중 매핑 (2026-07-16, 스텁 — 공공자료 원문 미확보)
#   1차 소스: 「원예·특작시설 내재해 설계기준 및 내재해형 시설규격 등록 등에
#   관한 규정」(농림축산식품부 행정규칙, law.go.kr) 별표. 이 세션은 robots 차단으로
#   본문 자동열람이 안 돼 REGION_DESIGN_LOAD가 비어 있다 — 사람이 law.go.kr에서
#   별표를 직접 열람해 채워야 한다(작업계획 문서 P0-b 참고).
#   빈 상태에서도 함수는 예외를 던지지 않고 None을 반환 — 상위 로직(리포트·UI)이
#   '수동입력 필요'로 graceful fallback 하도록 설계했다. 자동화선을 넘지 않는다.
# ─────────────────────────────────────────────────────────────
REGION_DESIGN_LOAD: dict = {
    # "지역명(또는 법정동코드)": {"snow_cm": .., "wind_ms": .., "source": .., "status": ..}
    # 2026-07-16 기준 비어 있음 — P0-b(law.go.kr 별표 확보) 완료 후 채운다.
}


def siting_design_load(region_name: str) -> Optional[dict]:
    """행정구역명 → {snow_cm, wind_ms, source, status}. 매핑표에 없으면 None을
    반환한다(예외 아님) — 호출부는 None일 때 사용자 수동입력으로 넘겨야 한다."""
    return REGION_DESIGN_LOAD.get(region_name)


# ─────────────────────────────────────────────────────────────
# 시공 C3: 골조 (엔진데이터 A-2 주의 — 평단가는 '온실 전체' 개념)
# ─────────────────────────────────────────────────────────────
# A-2 온실전체 예정공사비 평단가(원/평) — 개산용(방법 A). 2026-07: 스마트팜스펙/
# 문서 중 07-연동-1형으로 명시된 유일 사례(물향기수목원 분재증식온실)가 279,758원/평으로
# 이 표의 430,465원과 괴리가 크나 재축(철거+보강)공사라 신축 단가와 기준이 달라 미반영.
TOTAL_PYEONG_PRICE = {
    "07-연동-1": 430465, "08-연동-1": 389990,
    "10-연동-1": 572614, "12-연동-1": 584794,
}
# A-8 골조 단독 단가(원/평) — 공종상세용(방법 B). 2026-07: 우민재 공사내역서의
# "0103.철골공사" 실측 163,470원/평과 오차 0.04%로 거의 정확히 일치 확인.
STRUCTURE_ONLY_PYEONG = 163400


def greenhouse_total_estimate(spec_name: str, area_py: float) -> Optional[float]:
    """방법 A: 온실 전체 개산 = A-2 평단가 × 면적. (골조 단독 아님!)"""
    p = TOTAL_PYEONG_PRICE.get(spec_name)
    return None if p is None else p * area_py


def structure_only_estimate(area_py: float) -> float:
    """방법 B: 골조 단독 = A-8 실측 단위단가 × 면적."""
    return STRUCTURE_ONLY_PYEONG * area_py


# ─────────────────────────────────────────────────────────────
# 시공 CAPEX: 공종 카테고리 분해 (2026-07-16, 스마트팜스펙 실측 2건 청킹)
#   우민재(`1. 공사내역서 스마트팜 확대보급 시범사업.xlsx`, 2023·필름·2,323㎡·
#   557,152,000원)·최혁진(`혁진 스마트팜 온실 신축공사_공사비 내역서.pdf`, 2025·
#   불소필름/유리·3,459㎡·930,000,000원) 원본 내역서(0101~0115 공종별 재료비+
#   노무비+경비)를 9개 표준 카테고리로 의미단위 청킹해 직접공사비 대비 비중(%)을
#   계산. 두 케이스 모두 직접공사비 합계가 원문 순공사비(재+노+경) 합계와
#   원단위까지 정확히 일치(456,158,140원 / 694,575,784원) — 청킹 과정에서
#   금액 누락·중복이 없음을 확인했다.
#   표본 2건뿐이라 "밴드"(정상/경고 판정)가 아니라 "관측범위"(참고정보)로만
#   쓴다 — benchmark_check처럼 정상/경고를 가르지 않는다. 표본이 늘면 갱신.
#   RFQ 공내역서 5건(경주형연동×3·과수·물향기수목원 재축)은 금액이 전부
#   공란(총액입찰 서식)이었으나, 카테고리 "이름" 자체는 이 9종 분류와 일치해
#   taxonomy 교차검증에는 썼다(수치 근거로는 미사용).
# ─────────────────────────────────────────────────────────────
CAPEX_CATEGORIES = [
    ("scaffold", "가설공사"),
    ("earthwork_foundation", "토공/기초공사"),
    ("frame", "골조(철골)공사"),
    ("envelope", "피복/외장공사"),
    ("shading_vent", "개폐/차광/보온설비"),
    ("irrigation_fertigation", "관수/양액설비"),
    ("hvac_control", "냉난방/환경제어설비"),
    ("electrical_aux", "전기/기타설비"),
    ("qa_safety", "품질/안전/기타"),
]

# 관측범위(%, 최소~최대) — 우민재·최혁진 2건 실측 청킹 결과. 밴드가 아니라
# 참고용 관측범위(n=2)다. 정상/경고를 가르지 않는다.
CAPEX_CATEGORY_OBSERVED_RANGE = {
    "scaffold": (0.11, 2.34),
    "earthwork_foundation": (2.78, 8.70),
    "frame": (13.21, 25.18),
    "envelope": (12.66, 30.84),
    "shading_vent": (10.38, 24.49),
    "irrigation_fertigation": (12.37, 17.90),
    "hvac_control": (16.29, 18.48),
    "electrical_aux": (0.0, 3.70),
    "qa_safety": (0.0, 0.59),
}

# 원본 케이스 청킹 결과(카테고리키→직접공사비 원) — 회귀테스트·레지스트리 근거.
CAPEX_CASE_CHUNKS = {
    "우민재": {
        "scaffold": 501940, "earthwork_foundation": 12703822, "frame": 114870017,
        "envelope": 57768488, "shading_vent": 111692580,
        "irrigation_fertigation": 81635980, "hvac_control": 74306086,
        "electrical_aux": 0, "qa_safety": 2679227,
    },
    "최혁진": {
        "scaffold": 16234651, "earthwork_foundation": 60400165, "frame": 91719642,
        "envelope": 214209479, "shading_vent": 72068459,
        "irrigation_fertigation": 85884934, "hvac_control": 128340578,
        "electrical_aux": 25717876, "qa_safety": 0,
    },
}


@dataclass
class CapexBreakdown:
    items: dict            # 카테고리키 → 금액(원)
    total: float
    shares_pct: dict       # 카테고리키 → 비중(%)
    out_of_observed_range: list   # 관측범위(n=2) 밖 카테고리 — 경고 아님, 참고 표시용


def capex_breakdown(items: dict) -> CapexBreakdown:
    """직접공사비 항목(카테고리키→금액)을 합산·비중화한다(창작 없음 — 값 추정 안 함).
    빈 카테고리는 0으로 채운다. 관측범위 이탈은 '표본 2건과 다른 구성'이라는
    참고정보일 뿐 정상/경고 판정이 아니다 — 판단은 사람(컨설턴트) 몫."""
    filled = {k: float(items.get(k, 0.0)) for k, _ in CAPEX_CATEGORIES}
    total = sum(filled.values())
    shares = {k: (round(v / total * 100, 2) if total else 0.0) for k, v in filled.items()}
    out = [k for k, pct in shares.items()
           if k in CAPEX_CATEGORY_OBSERVED_RANGE
           and not (CAPEX_CATEGORY_OBSERVED_RANGE[k][0] <= pct <= CAPEX_CATEGORY_OBSERVED_RANGE[k][1])]
    return CapexBreakdown(filled, total, shares, out)


# ─────────────────────────────────────────────────────────────
# 시공 CAPEX: 13개 상위(총사업비) 카테고리 — 2026-07-16, 사용자 제안 채택
#   위 9키(CAPEX_CATEGORIES)는 "시공사 공사비 내역서" 관점(직접공사비만).
#   이 13키는 "총사업비" 관점(설계비·부지비·예비비까지 포함) — 컨설팅
#   산출물에는 이쪽이 맞다. 2계층 구조: 9키는 1~6번 밑 하위 세부로 흡수.
#   근거 문서가 없는 항목(7·9·10·11·12·13, 5 일부)은 구조만 만들고 값 0 +
#   status "미검증(근거문서 없음)" — 모래 위 자동화 금지 원칙 유지.
#   13. 부지 매입비는 감가상각 대상이 아니므로 finance(land_cost=...)로 분리
#   처리한다(합산 CAPEX에 섞으면 감가상각이 과대계상됨 — 사용자 지적 반영).
# ─────────────────────────────────────────────────────────────
CAPEX_MAJOR_CATEGORIES = [
    ("greenhouse_structure", "1. 온실 구조", "철골, 기초, 피복재, 도어 등 — 스마트팜 물리적 기본 구조"),
    ("auto_opening_system", "2. 자동개폐 시스템", "천창, 수평·측면스크린, 개폐모터 — 환경 자동화 설비"),
    ("hvac", "3. 냉·난방 설비", "보일러, 히트펌프, 송풍기, 난방배관 — 에너지 효율 핵심 설비"),
    ("irrigation_fertigation", "4. 양액·관수 설비", "양액기, 펌프, 관수 배관, 폐양액 처리 — 작물 생장 핵심 제어 설비"),
    ("ict_control", "5. ICT 및 제어설비", "복합환경제어기, 센서, 서버, 소프트웨어 — 스마트팜의 제어 두뇌 역할"),
    ("electrical", "6. 전기 설비", "전기 인입, 배선반, 조명, 분전함 등 — 전력 공급 인프라"),
    ("auxiliary_facility", "7. 부대시설", "기계실, 창고, 출입구, 작업동 등 — 생산 보조 공간"),
    ("thermal_storage_insulation", "8. 축열·보온 설비", "축열탱크, 보온커튼, 단열판 등 — 난방비 절감 요소"),
    ("equipment_procurement", "9. 기자재 구매", "트롤리, 컨베이어, 선별대 등 — 생산성 향상 보조 장비"),
    ("design_supervision_fee", "10. 설계·감리비", "기본·실시설계, 감리 용역비 등 — 설치의 행정·기술 지원"),
    ("site_preparation", "11. 부지 조성비", "성토, 배수로, 석축, 진입로 등 — 시설 설치 위한 기반 공사"),
    ("contingency", "12. 예비비", "물가변동, 오차 대응용 2~5% — 불확실성 대비"),
    ("land_acquisition", "13. 부지 매입비", "토지 구입비 — 자산이지만 감가상각 제외(finance()의 land_cost로 별도 처리)"),
]

# 근거 상태 — 2026-07-16 기준 우민재·최혁진 원문 대조 결과. 근거 없는 항목은
# 값을 만들지 않고 0 + 미검증으로 남긴다(다음 문서 확보 시 갱신).
CAPEX_MAJOR_EVIDENCE_STATUS = {
    "greenhouse_structure": "실측(2건)", "auto_opening_system": "실측(2건, 모터·보온재 미분리)",
    "hvac": "실측(2건)", "irrigation_fertigation": "실측(2건)",
    "ict_control": "부분실측(최혁진만, 우민재는 해당 공종 없음)",
    "electrical": "부분실측(최혁진만, 우민재는 해당 공종 없음)",
    "auxiliary_facility": "미검증(근거문서 없음)", "thermal_storage_insulation": "미검증(근거문서 없음 — 자동개폐와 분리 재조사 필요)",
    "equipment_procurement": "미검증(근거문서 없음)", "design_supervision_fee": "미검증(근거문서 없음)",
    "site_preparation": "미검증(근거문서 없음)", "contingency": "미검증(근거문서 없음)",
    "land_acquisition": "미검증(근거문서 없음)",
}

# 원본 케이스를 13개 상위 카테고리로 재청킹한 결과. 9키(CAPEX_CASE_CHUNKS)의
# hvac_control을 hvac(냉난방 실행부)와 ict_control(환경제어시스템=제어반)로
# 원문 라인아이템 기준 재분리했다(최혁진 '0113 환경제어시스템 1구역'
# 17,856,555원만 ict_control, 나머지 유동휀·난방설비는 hvac).
# scaffold(가설공사)는 1.온실구조에 직접시공 준비비로 편입. qa_safety(품질
# 시험비·안전관리비·재해예방기술지도비)는 13개 어디에도 깔끔히 안 맞아
# capex_major_breakdown()의 unclassified로 남긴다(우겨넣지 않음).
CAPEX_MAJOR_CASE_CHUNKS = {
    "우민재": {
        "greenhouse_structure": 185844267,   # earthwork(12,703,822)+frame(114,870,017)+envelope(57,768,488)+scaffold(501,940)
        "auto_opening_system": 111692580,    # shading_vent 그대로(모터·보온재 미분리)
        "hvac": 74306086,                    # hvac_control 전액(우민재는 별도 환경제어시스템 라인 없음)
        "irrigation_fertigation": 81635980,
        "ict_control": 0,
        "electrical": 0,
    },
    "최혁진": {
        "greenhouse_structure": 382563937,   # earthwork(60,400,165)+frame(91,719,642)+envelope(214,209,479)+scaffold(16,234,651)
        "auto_opening_system": 72068459,
        "hvac": 110484023,                   # hvac_control(128,340,578) - ict_control(17,856,555)
        "irrigation_fertigation": 85884934,
        "ict_control": 17856555,             # 0113 환경제어시스템 1구역
        "electrical": 25717876,
    },
}
# 위 6개 항목 외(7~13, unclassified) 미기재 케이스 → capex_major_breakdown()이 0 채움.
# unclassified_direct_cost(qa_safety 잔액) — 원문 총액 재대조용, 별도 기록.
CAPEX_MAJOR_UNCLASSIFIED = {"우민재": 2679227, "최혁진": 0}  # qa_safety(품질시험비+안전관리비+재해예방기술지도비)


@dataclass
class CapexMajorBreakdown:
    items: dict            # 13개 상위 카테고리키 → 금액(원, 미기재는 0)
    unclassified: float    # known_total과의 잔액(13개 어디에도 안 맞는 항목, 예: qa_safety)
    total: float
    shares_pct: dict        # 13개 카테고리 → 비중(%, unclassified 제외 total 기준)


def capex_major_breakdown(items: dict, known_total: float) -> CapexMajorBreakdown:
    """13개 상위(총사업비) 카테고리로 합산. known_total과 항목합의 차액은
    unclassified로 그대로 노출한다(감추지 않음 — 근거 없는 값 금지 원칙).
    항목합이 총액을 초과하면 입력 오류로 보고 예외를 던진다."""
    filled = {k: float(items.get(k, 0.0)) for k, _, _ in CAPEX_MAJOR_CATEGORIES}
    classified = sum(filled.values())
    unclassified = known_total - classified
    if unclassified < -1e-6:
        raise ValueError("CAPEX 상위 카테고리 합이 총액을 초과했다 — 입력값 재확인 필요")
    unclassified = max(unclassified, 0.0)
    shares = {k: (round(v / known_total * 100, 2) if known_total else 0.0) for k, v in filled.items()}
    return CapexMajorBreakdown(filled, unclassified, known_total, shares)


# ─────────────────────────────────────────────────────────────
# 시공: 실측 벤치마크 밴드 대조 (엔진데이터 A-11)
#   ※ ACTUALS 는 현재 7건. (원 지침은 8건이나 1건 데이터 미확보 → 7건으로 유지)
#   2026-07 스마트팜스펙/ 실문서 대조: 최혁진·이두희 기존값 정확히 일치(실측 확정),
#   우민재 신규 추가(공사내역서 총공사비 557,152,000원 확인) → 필름 밴드 상한 220→240 확대.
# ─────────────────────────────────────────────────────────────
# (하한, 상한) 원/㎡
BENCHMARK_BANDS = {
    Cover.FILM:     (115000, 240000),   # 공주120 ~ 우민재240 (이두희213)
    Cover.GLASS:    (180000, 230000),   # 원채원203
    Cover.FLUORINE: (230000, 310000),   # 최혁진269
}
# 실측 7건(면적/총액/피복) — 회귀 테스트 근거
ACTUALS = [
    ("공주장원리", 3759, 450000000, Cover.FILM),
    ("한일그린텍", 3202, 480636000, Cover.FILM),
    ("당진이상근", 3030, 512480000, Cover.FILM),
    ("원채원",     3456, 702030000, Cover.GLASS),
    ("이두희",     2736, 582455045, Cover.FILM),
    ("최혁진",     3459, 930000000, Cover.FLUORINE),
    ("우민재",     2323, 557152000, Cover.FILM),
]


def benchmark_check(total_cost: float, area_m2: float, cover: Cover) -> dict:
    unit = total_cost / area_m2
    lo, hi = BENCHMARK_BANDS.get(cover, (115000, 310000))
    if lo <= unit <= hi:
        status = "정상"
    elif lo * 0.9 <= unit <= hi * 1.1:
        status = "경계"
    else:
        status = "경고(밴드이탈)"
    return {"unit_won_m2": round(unit), "band": (lo, hi), "status": status}


# ─────────────────────────────────────────────────────────────
# 시공 C13: 제경비 (엔진데이터 A-11, 4사 대조)
#   2026-07 실문서 6건 대조로 실측 확정. 4대보험 요율은 2026년 개정치 반영
#   (health 3.545%→3.595%, pension 4.50%→4.75%; industrial_accident·employment는
#   2025·2026 문서 전부에서 동일해 변경 없음).
# ─────────────────────────────────────────────────────────────
@dataclass
class OverheadRates:
    # 사실상 고정 (법정요율, 2026년 기준)
    health: float = 0.03595       # 직노 기준
    pension: float = 0.0475       # 직노
    industrial_accident: float = 0.0356  # 노무비
    employment: float = 0.0101    # 노무비
    # 업체·규모 차등(기본 중앙값)
    general_admin: float = 0.05   # 4~6%
    profit: float = 0.10          # 10~15%
    safety_mgmt: float = 0.025    # 1.86~3.11%


def apply_overheads(material: float, labor: float,
                    rates: OverheadRates = OverheadRates()) -> dict:
    direct = material + labor
    health = labor * rates.health   # (직노 근사=labor)
    pension = labor * rates.pension
    ind = labor * rates.industrial_accident
    emp = labor * rates.employment
    safety = direct * rates.safety_mgmt
    subtotal = direct + health + pension + ind + emp + safety
    admin = subtotal * rates.general_admin
    profit = (subtotal + admin) * rates.profit
    total = subtotal + admin + profit
    return {"direct": direct, "insurance": health + pension + ind + emp,
            "safety": safety, "admin": admin, "profit": profit,
            "total_before_vat": total}


# ─────────────────────────────────────────────────────────────
# 경제성 F1: 생산량 (환경적합도, 엔진데이터 B)
# ─────────────────────────────────────────────────────────────
# 환경적합도 구간 → 생산량 증감 (B: 90~109%=0 기준)
def yield_adjustment(fitness_pct: float) -> float:
    f = fitness_pct
    if f < 60: return -0.40
    if f < 70: return -0.20
    if f < 80: return -0.10
    if f < 90: return -0.05
    if f <= 109: return 0.0
    if f <= 119: return -0.05
    if f <= 129: return -0.10
    if f <= 139: return -0.20
    return -0.40


def env_fitness(light_r: float, temp_r: float, humid_r: float, co2_r: float) -> float:
    """환경적합도(%) = Σ(인자비율 × 가중치). 광0.5 온0.2 습0.2 CO2 0.1 (B)."""
    return (light_r * 0.5 + temp_r * 0.2 + humid_r * 0.2 + co2_r * 0.1) * 100


def production_kg(area_m2: float, base_yield_kg_m2: float, fitness_pct: float) -> float:
    return area_m2 * base_yield_kg_m2 * (1 + yield_adjustment(fitness_pct))


# ─────────────────────────────────────────────────────────────
# 경제성 OPEX: 항목 분해 (2026-07-16, 제안값 — 농진청 CSV 원문 미확보)
#   표준 출처는 농촌진흥청 「농산물소득분석 조사입력항목코드」(공공데이터포털
#   15069669)이나, 이번 세션은 포털 회원가입·API키 발급이 필요해 원문 CSV를
#   받지 못했다. 아래 항목명은 일반적인 농산물소득조사 관행 분류(직접경비/
#   간접경비)를 따른 **제안값**이다 — status="미검증(제안값)"으로 취급한다.
#   CSV 확보 시 이 리스트만 교체하면 된다(엔진 로직=합산·잔액검증은 안 바뀜).
#   주의: `스마트팜스펙/`의 원가계산서·공내역서는 전부 CAPEX(시공비) 문서이고
#   이 OPEX(운영비, 매년 반복되는 종묘·비료·농약·에너지·인건비)와는 다른
#   자료다 — 혼동해서 재사용하지 않는다.
# ─────────────────────────────────────────────────────────────
OPEX_ITEM_CATEGORIES_PROPOSED = [
    # 직접경비(관행 분류, 미검증)
    "종묘비", "비료비", "농약비", "광열동력비", "수리비(용수)", "기타재료비",
    "소농구비", "대농구상각비", "영농시설상각비", "수선비", "위탁영농비",
    "고용노동비", "기타비용",
    # 간접경비(관행 분류, 미검증)
    "임차료", "자기자본이자(간접)", "자가노동비(간접)",
]


@dataclass
class OpexBreakdown:
    items: dict           # 항목명 → 금액(원). 시세성 입력 — 엔진이 추정하지 않음
    unclassified: float   # known_total - 분류합. 항상 0 이상(가드)
    total: float


def opex_breakdown(items: dict, known_total: float) -> OpexBreakdown:
    """기존 lump-sum OPEX(known_total)를 항목별로 나눠 근거를 남긴다.
    항목값을 새로 추정/창작하지 않는다 — 입력된 항목만 합산하고, known_total과의
    차액은 unclassified로 그대로 드러낸다(감추지 않는다 — 근거 없는 값 금지 원칙).
    항목합이 총액을 초과하면 입력 오류로 보고 예외를 던진다."""
    classified = sum(items.values())
    unclassified = known_total - classified
    if unclassified < -1e-6:
        raise ValueError("OPEX 항목합이 총액을 초과했다 — 입력값 재확인 필요")
    return OpexBreakdown(dict(items), max(unclassified, 0.0), known_total)


# ─────────────────────────────────────────────────────────────
# 경제성 F5/F6: 손익 & 투자지표 (엔진데이터 C, 사업성 시트 구조)
# ─────────────────────────────────────────────────────────────
def npv(rate: float, cashflows: list[float]) -> float:
    """cashflows[0]는 t=0(보통 -CAPEX)."""
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cashflows))


def irr(cashflows: list[float], lo: float = -0.9, hi: float = 1.0,
        tol: float = 1e-6, it: int = 200) -> Optional[float]:
    """이분법 IRR. 부호변화 없으면 None."""
    f_lo, f_hi = npv(lo, cashflows), npv(hi, cashflows)
    if f_lo * f_hi > 0:
        return None
    for _ in range(it):
        mid = (lo + hi) / 2
        f_mid = npv(mid, cashflows)
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


@dataclass
class FinanceResult:
    revenue: float
    opex: float
    depreciation: float
    operating_profit: float
    roi: float
    payback_years: Optional[float]
    npv: Optional[float] = None
    irr: Optional[float] = None
    real_roi_after_subsidy: Optional[float] = None


def finance(revenue: float, opex: float, capex: float,
            useful_life: int = 15, discount_rate: float = 0.05,
            years: int = 10, subsidy_rate: float = 0.0,
            land_cost: float = 0.0) -> FinanceResult:
    """land_cost(2026-07-16 추가, 기본 0 — 기존 호출 결과 불변): capex에 포함된
    부지 매입비(CAPEX_MAJOR_CATEGORIES의 13번). 토지는 감가상각 대상이 아니므로
    감가상각 계산에서만 제외한다 — ROI/Payback/현금흐름은 여전히 capex 전액(토지
    포함) 기준(실제 투자금이므로). 토지 잔존가치 회수(terminal value)는 모델링하지
    않는다 — 근거 없는 값을 만들지 않기 위한 의도적 단순화."""
    depreciable_capex = capex - land_cost
    dep = depreciable_capex / useful_life
    op = revenue - opex - dep
    roi = op / capex if capex else 0.0
    payback = capex / op if op > 0 else None
    # 간이 현금흐름: t0=-capex, 이후 영업이익+감가(현금 유출 아님) 근사
    cfs = [-capex] + [op + dep] * years
    n = npv(discount_rate, cfs)
    r = irr(cfs)
    real_roi = None
    if subsidy_rate > 0 and op > 0:
        self_cost = capex * (1 - subsidy_rate)
        real_roi = op / self_cost if self_cost else None
    return FinanceResult(revenue, opex, dep, op, roi, payback, n, r, real_roi)


# ─────────────────────────────────────────────────────────────
# 경제성 F7: 개선 ROI (리뉴얼)
# ─────────────────────────────────────────────────────────────
def improvement_roi(annual_saving: float, invest: float) -> dict:
    if invest <= 0:
        return {"roi": None, "payback": None}
    return {"roi": annual_saving / invest,
            "payback": invest / annual_saving if annual_saving else None}


# ─────────────────────────────────────────────────────────────
# 경제성 F8: 단지 경제성
# ─────────────────────────────────────────────────────────────
def cluster_economics(n_farms: int, per_farm_capex: float,
                      shared_capex: float, per_farm_opex: float,
                      scale_saving_rate: float = 0.15,
                      subsidy_rate_shared: float = 0.7) -> dict:
    share = shared_capex / n_farms
    farm_total_capex = per_farm_capex + share
    farm_opex_after = per_farm_opex * (1 - scale_saving_rate)
    share_after_subsidy = share * (1 - subsidy_rate_shared)
    return {
        "cluster_total_area_note": f"{n_farms}농가",
        "shared_capex": shared_capex,
        "per_farm_share": share,
        "per_farm_total_capex": farm_total_capex,
        "per_farm_opex_after_scale": farm_opex_after,
        "per_farm_share_after_subsidy": share_after_subsidy,
    }
