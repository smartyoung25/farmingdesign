"""
SmartFarm 계산 엔진 (결정론적 코어)
- 진단·설계·시공·경제성 4축 중 '자동화하기(계산)' 부분을 함수로 고정.
- 실시간 시세(시장가격·노임·유가)는 인자로 주입받는다(엔진은 조회하지 않음).
- 근거: SmartFarm_엔진데이터.md의 A-2/A-5/A-11/A-12, B(환경인자), C(재무).
모든 단가·규격은 특정 시점 실측 기반 → 밴드/기준시점 개념으로 사용.
"""
from __future__ import annotations
import csv
import os
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
#   ✅ 2026-07-22 SPEC_TABLE 전면 확장(32종→249종) — 7절 "SPEC_TABLE 개정 확인,
#   재구축 보류" 후속. 2026-07-21에 REGION_DESIGN_LOAD를 갱신시킨 농림축산식품부
#   고시 제2025-108호가 SPEC_TABLE(구조 규격표) 쪽도 개정시켰음을 확인했고,
#   농사로(nongsaro.go.kr) 공식 마스터 목록 "★원예특작 내재해형 시설규격
#   운영현황(2026.3.기준).xlsx"(cntntsNo=265222, fileSn=1, 172KB)를 직접
#   다운로드해 openpyxl로 1.단동(157종)+2.연동(81종)+3.광폭(11종)=249종 전량을
#   전사했다(인삼·버섯 시트 및 각 시트 내 작물란="인삼"/"버섯" 표기 행은
#   2026-07-22 사용자 확인 하에 제외 — 작목 전용 구조라 범위 밖이라는 기존
#   방침과 동일선상. 포도·감귤 등 작물 특화형과 천안시·밀양군 등 지자체
#   개발분, 서까래 간격별 하위변형은 전부 포함하기로 사용자 확인).
#   ⚠️ 규격명이 하위변형끼리 중복되는 경우(예: "10-단동-01"이 서까래 간격
#   500~900mm별로 17개 변형, 설계강도가 전부 다름)는 원문 연번을 괄호로 붙여
#   구분했다(예: "10-단동-01(6-1)") — name 필드를 select_specs()가 유일키로
#   쓰지는 않지만 사람이 보고서에서 구분할 수 있어야 하기 때문.
#   교차검증: 기존 32종 값(적설심·풍속)이 새 249종 안에 전량 정확히 존재함을
#   자동 대조 완료(REGION_DESIGN_LOAD 때와 달리 "틀린 값을 고치는" 게 아니라
#   "이미 맞는 32종에 217종을 추가로 채워넣는" 확장 — 예: 옛 "10-광폭-1(아치)"
#   (적설33·풍속40)이 새 "10-광폭-01"과 값이 정확히 일치). 옛 이름 표기(예:
#   "07-연동-1")는 이번에 원문 공식 표기(zero-padded, "07-연동-01")로 통일했다
#   — 과거 세션의 축약 표기였을 뿐 두 표기를 모두 하드코딩해 참조하는 테스트는
#   없음을 grep으로 확인 후 교체(회귀 영향 없음).
#   select_specs()/siting_lookup() 로직 자체는 변경 없음 — SPEC_TABLE이 몇
#   종이든 그대로 동작하는 구조라 확장만으로 충분했다.
# ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Spec:
    name: str
    form: str          # 연동/단동/광폭
    width_m: float
    snow_cm: int       # 설계 적설심
    wind_ms: int       # 설계 풍속
    height_m: Optional[float] = None       # 측고(2026-07-22 추가, 표시용)
    ridge_height_m: Optional[float] = None  # 동고
    registered_year: Optional[int] = None
    developer: str = ""                     # 개발자/지역(농촌진흥청/민간/지자체 등)
    crop: str = ""                          # 작물 특화형이면 작목명(일반형은 공란)
    rafter_spec: str = ""                   # 서까래 규격 및 간격(참고용, 계산에 안 쓰임)

# 농림축산식품부 고시 제2025-108호 기준(2026-07-22 확정) — 249종
# (연동81+단동157+광폭11, 인삼·버섯 제외). 상세 출처는 위 주석 참고.
SPEC_TABLE: list[Spec] = [
    # 연동형(81종)
    Spec("07-연동-01", "연동", 7, 53, 40, height_m=2.8, ridge_height_m=4.7, registered_year=2007, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@3,000"),
    Spec("08-연동-01", "연동", 8, 57, 36, height_m=4.5, ridge_height_m=5.7, registered_year=2008, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.5t@600"),
    Spec("10-연동-01", "연동", 8, 55, 40, height_m=5.4, ridge_height_m=7.4, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ59.9×3.2t@3,000"),
    Spec("10-연동-02", "연동", 8, 55, 40, height_m=5.4, ridge_height_m=7.4, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ59.9×3.2t@3,000"),
    Spec("12-연동-01", "연동", 7, 55, 40, height_m=4.5, ridge_height_m=6.5, registered_year=2012, developer="농촌진흥청", crop="", rafter_spec="φ59.9×2.3t@4,000"),
    Spec("07-연동(민)-01", "연동", 8, 60, 35, height_m=2, ridge_height_m=3.7, registered_year=2007, developer="민간", crop="", rafter_spec="φ25.4×1.5t@600"),
    Spec("08-연동(민)-01", "연동", 7, 63, 32, height_m=2, ridge_height_m=3.63, registered_year=2008, developer="민간", crop="", rafter_spec="󰋪40×60×3.0t@2,000"),
    Spec("07-포도-01(8)", "연동", 5, 40, 35, height_m=2.5, ridge_height_m=4.3, registered_year=2007, developer="농촌진흥청", crop="포도", rafter_spec="φ31.8×1.5t@600"),
    Spec("07-포도-01(8-1)", "연동", 5, 35, 30, height_m=2.5, ridge_height_m=4.3, registered_year=2007, developer="농촌진흥청", crop="포도", rafter_spec="φ25.4×1.5t@600"),
    Spec("10-포도-01", "연동", 3, 44, 35, height_m=2.1, ridge_height_m=3, registered_year=2010, developer="충북농업기술원", crop="포도", rafter_spec="φ25.4×1.5t@1,000"),
    Spec("08-감귤-01", "연동", 5.5, 50, 40, height_m=3.3, ridge_height_m=4.5, registered_year=2008, developer="농촌진흥청", crop="감귤", rafter_spec="φ48.1×2.1t@2,000"),
    Spec("18-연동(등)-01", "연동", 8, 26, 28, height_m=5.5, ridge_height_m=6.723, registered_year=2018, developer="천안시", crop="", rafter_spec="󰋪30×30×1.5t@1,000"),
    Spec("19-연동(등)-01", "연동", 8, 20, 30, height_m=6, ridge_height_m=7.264, registered_year=2019, developer="밀양군", crop="파프리카", rafter_spec="󰋪30×30×1.5t@800"),
    Spec("19-연동(등)-02", "연동", 5.5, 20, 40, height_m=3.3, ridge_height_m=4.77, registered_year=2019, developer="제주시", crop="", rafter_spec="φ48.1×2.3t@2,000"),
    Spec("19-연동(등)-03", "연동", 8, 20, 30, height_m=6, ridge_height_m=7.3, registered_year=2019, developer="밀양군", crop="파프리카", rafter_spec="φ31.8×1.7t@600"),
    Spec("19-연동(등)-04", "연동", 8, 20, 34, height_m=6.5, ridge_height_m=7.8, registered_year=2018, developer="함안군", crop="", rafter_spec="󰋪30×30×1.5t@800"),
    Spec("20-연동(등)-01", "연동", 7, 28, 26, height_m=3.5, ridge_height_m=5.2, registered_year=2019, developer="곡성군", crop="", rafter_spec="φ31.8×1.5t@600"),
    Spec("20-연동(등)-02", "연동", 8, 28, 26, height_m=3.5, ridge_height_m=5.3, registered_year=2019, developer="곡성군", crop="", rafter_spec="φ31.8×1.5t@600"),
    Spec("20-연동(등)-03", "연동", 5.5, 28, 26, height_m=3.3, ridge_height_m=4.5, registered_year=2019, developer="곡성군", crop="", rafter_spec="φ25.4×1.5t@600"),
    Spec("20-연동(등)-04", "연동", 8, 20, 32, height_m=3.3, ridge_height_m=5.2, registered_year=2020, developer="경주시", crop="", rafter_spec="φ31.8×1.7t@600"),
    Spec("20-연동(등)-05", "연동", 8, 26, 28, height_m=6, ridge_height_m=7.22, registered_year=2020, developer="부여군", crop="", rafter_spec="φ31.8×1.5@1,000"),
    Spec("20-연동(등)-06", "연동", 12, 30, 30, height_m=6.3, ridge_height_m=7.69, registered_year=2020, developer="경북도", crop="", rafter_spec="φ31.8×1.5t@833.33"),
    Spec("20-연동(등)-07", "연동", 8, 30, 30, height_m=6.3, ridge_height_m=7.69, registered_year=2020, developer="경북도", crop="", rafter_spec="φ31.8×1.5t@750"),
    Spec("20-연동(등)-08", "연동", 8, 40, 30, height_m=6.3, ridge_height_m=7.69, registered_year=2020, developer="전북도", crop="", rafter_spec="φ31.8×1.7t@714"),
    Spec("20-연동(등)-09", "연동", 8, 26, 30, height_m=6, ridge_height_m=7.2, registered_year=2020, developer="전주시", crop="딸기", rafter_spec="φ42.2×2.1t@1,000"),
    Spec("20-연동(등)-10", "연동", 8, 22, 34, height_m=5.4, ridge_height_m=7.4, registered_year=2020, developer="해남군", crop="", rafter_spec="φ33.5×2.1t@600"),
    Spec("21-연동(등)-01", "연동", 8, 30, 30, height_m=5.5, ridge_height_m=7.849, registered_year=2021, developer="민간", crop="", rafter_spec="φ31.8×1.7t@500"),
    Spec("21-연동(등)-02", "연동", 8, 24, 26, height_m=2.5, ridge_height_m=3.9, registered_year=2021, developer="구례군", crop="", rafter_spec="φ31.8×1.5t@500"),
    Spec("21-연동(등)-03", "연동", 8.5, 24, 26, height_m=2.5, ridge_height_m=4, registered_year=2021, developer="구례군", crop="", rafter_spec="φ31.8×1.5t@500"),
    Spec("21-연동(등)-04", "연동", 8, 28, 26, height_m=5, ridge_height_m=6.25, registered_year=2021, developer="음성군", crop="", rafter_spec="󰋪30×30×1.5t@800"),
    Spec("21-연동-01", "연동", 8, 41, 41, height_m=6, ridge_height_m=7.1, registered_year=2021, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@800"),
    Spec("21-연동-02", "연동", 8, 37, 32, height_m=6, ridge_height_m=7.1, registered_year=2021, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.5t@800"),
    Spec("21-연동-03", "연동", 8, 50, 40, height_m=6, ridge_height_m=7.1, registered_year=2021, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@800"),
    Spec("21-연동-04", "연동", 8, 40, 30, height_m=6, ridge_height_m=7.1, registered_year=2021, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.7t@800"),
    Spec("21-연동(등)-05", "연동", 8, 26, 30, height_m=7.3, ridge_height_m=8.7, registered_year=2021, developer="전주시", crop="", rafter_spec="φ31.8×1.5t@900"),
    Spec("22-연동(등)-01", "연동", 10.8, 28, 28, height_m=6.6, ridge_height_m=7.5, registered_year=2022, developer="논산시", crop="", rafter_spec="󰋪75×45×3.2t"),
    Spec("22-연동(등)-02", "연동", 8.5, 24, 26, height_m=2.65, ridge_height_m=4.6, registered_year=2022, developer="구례군", crop="", rafter_spec="φ31.8×1.5t@600"),
    Spec("22-연동(등)-03", "연동", 8, 35, 35, height_m=4.5, ridge_height_m=5.75, registered_year=2022, developer="농협경제지주", crop="", rafter_spec="φ31.8×1.5t@800"),
    Spec("22-연동(등)-04", "연동", 8, 45, 45, height_m=4.5, ridge_height_m=5.75, registered_year=2022, developer="농협경제지주", crop="", rafter_spec="φ31.8×1.5t@800"),
    Spec("22-연동(등)-05", "연동", 8, 35, 40, height_m=6, ridge_height_m=7.25, registered_year=2022, developer="농협경제지주", crop="", rafter_spec="φ31.8×1.5t@800"),
    Spec("22-연동(등)-06", "연동", 8, 45, 45, height_m=6, ridge_height_m=7.25, registered_year=2022, developer="농협경제지주", crop="", rafter_spec="φ31.8×1.5t@800"),
    Spec("22-연동(등)-07", "연동", 8, 35, 40, height_m=6, ridge_height_m=7.25, registered_year=2022, developer="농협경제지주", crop="", rafter_spec="󰋪30×30×1.5t@800"),
    Spec("22-연동(등)-08", "연동", 8, 30, 30, height_m=6, ridge_height_m=7.25, registered_year=2022, developer="농협경제지주", crop="", rafter_spec="󰋪30×30×1.5t@800"),
    Spec("22-연동(등)-09", "연동", 7, 45, 32, height_m=4.5, ridge_height_m=6.3, registered_year=2022, developer="농협경제지주", crop="", rafter_spec="φ31.8×1.5t@600"),
    Spec("22-연동(등)-10", "연동", 7, 45, 38, height_m=6, ridge_height_m=7.8, registered_year=2022, developer="농협경제지주", crop="", rafter_spec="φ31.8×1.5t@600"),
    Spec("22-연동(등)-11", "연동", 8, 50, 38, height_m=4.5, ridge_height_m=6.75, registered_year=2022, developer="농협경제지주", crop="", rafter_spec="φ31.8×1.5t@600"),
    Spec("22-연동(등)-12", "연동", 8, 50, 38, height_m=6, ridge_height_m=8.25, registered_year=2022, developer="농협경제지주", crop="", rafter_spec="φ31.8×1.7t@600"),
    Spec("23-연동(등)-01", "연동", 7, 30, 26, height_m=5, ridge_height_m=6.7, registered_year=2023, developer="진천군", crop="", rafter_spec="φ33.5×2.3t@600"),
    Spec("23-연동(등)-02", "연동", 8, 30, 26, height_m=3, ridge_height_m=5, registered_year=2023, developer="진천군", crop="", rafter_spec="φ33.5×2.3t@600"),
    Spec("23-연동(등)-03", "연동", 8, 30, 26, height_m=5, ridge_height_m=7, registered_year=2023, developer="진천군", crop="", rafter_spec="φ42.2×2.1t@600"),
    Spec("24-연동(등)-01", "연동", 8, 42, 30, height_m=4.5, ridge_height_m=6.75, registered_year=2024, developer="담양군", crop="", rafter_spec="φ31.8×1.7t@600"),
    Spec("24-연동(등)-02", "연동", 9.6, 42, 36, height_m=5, ridge_height_m=7.7, registered_year=2024, developer="현대금속농공", crop="", rafter_spec="φ33.5×2.1t@600"),
    Spec("24-연동(등)-03", "연동", 9.6, 42, 36, height_m=6, ridge_height_m=8.7, registered_year=2024, developer="현대금속농공", crop="", rafter_spec="φ33.5×2.1t@600"),
    Spec("25-연동(등)-01", "연동", 8, 26, 28, height_m=3.5, ridge_height_m=5.5, registered_year=2025, developer="부여군", crop="", rafter_spec="φ31.8×1.7t@600"),
    Spec("25-연동(등)-02", "연동", 3.5, 26, 36, height_m=2.7, ridge_height_m=3.8, registered_year=2025, developer="포항군", crop="", rafter_spec="φ25.4×1.5t@600"),
    Spec("25-연동-03", "연동", 7, 30, 26, height_m=3, ridge_height_m=4.7, registered_year=2025, developer="남원시", crop="", rafter_spec="φ31.8×1.7t@500"),
    Spec("25-연동-04", "연동", 11, 22, 40, height_m=3.35, ridge_height_m=7.35, registered_year=2025, developer="트러스하우스군", crop="", rafter_spec="ㅡ"),
    Spec("25-연동-05", "연동", 9, 24, 30, height_m=6, ridge_height_m=7.4, registered_year=2025, developer="팜스코건설", crop="", rafter_spec="φ33.5×2.1t@800"),
    Spec("25-연동-06", "연동", 9.6, 30, 26, height_m=6, ridge_height_m=7.75, registered_year=2025, developer="서진비에스", crop="", rafter_spec="30×34.55×1.8t@1000"),
    Spec("25-연동-07", "연동", 6, 24, 30, height_m=1.6, ridge_height_m=3, registered_year=2025, developer="성주군농업기술센터", crop="참외", rafter_spec="φ31.8×1.7t@600"),
    Spec("25-연동-08", "연동", 6, 24, 30, height_m=1.6, ridge_height_m=3, registered_year=2025, developer="성주군농업기술센터", crop="참외", rafter_spec="φ33.5×2.1t@800"),
    Spec("25-연동-09", "연동", 6.7, 24, 30, height_m=2, ridge_height_m=4, registered_year=2025, developer="성주군농업기술센터", crop="참외", rafter_spec="φ31.8×1.7t@500"),
    Spec("25-연동-10", "연동", 6.7, 24, 30, height_m=2, ridge_height_m=4, registered_year=2025, developer="성주군농업기술센터", crop="참외", rafter_spec="φ33.5×2.1t@700"),
    Spec("25-연동-11", "연동", 6.4, 24, 30, height_m=2, ridge_height_m=3.5, registered_year=2025, developer="성주군농업기술센터", crop="참외", rafter_spec="φ33.5×2.3t@700"),
    Spec("25-연동-12", "연동", 6, 24, 30, height_m=2.2, ridge_height_m=4.1, registered_year=2025, developer="성주군농업기술센터", crop="참외", rafter_spec="φ33.5×2.3t@700"),
    Spec("25-연동-13", "연동", 7, 24, 30, height_m=2.2, ridge_height_m=4.4, registered_year=2025, developer="성주군농업기술센터", crop="참외", rafter_spec="φ33.5×2.3t@600"),
    Spec("25-연동-14", "연동", 6, 24, 30, height_m=2.2, ridge_height_m=4.1, registered_year=2025, developer="성주군농업기술센터", crop="참외", rafter_spec="φ33.5×2.3t@700"),
    Spec("25-연동-15", "연동", 6, 24, 30, height_m=2.2, ridge_height_m=4.1, registered_year=2025, developer="성주군농업기술센터", crop="참외", rafter_spec="φ33.5×2.3t@700"),
    Spec("25-연동-16", "연동", 7, 24, 30, height_m=2.2, ridge_height_m=4.4, registered_year=2025, developer="성주군농업기술센터", crop="참외", rafter_spec="φ33.5×2.3t@600"),
    Spec("25-연동-17", "연동", 7, 24, 30, height_m=2.2, ridge_height_m=4.4, registered_year=2025, developer="성주군농업기술센터", crop="참외", rafter_spec="φ33.5×2.3t@600"),
    Spec("25-연동-18", "연동", 6, 24, 30, height_m=2.2, ridge_height_m=3.4, registered_year=2025, developer="성주군농업기술센터", crop="참외", rafter_spec="φ33.5×2.1t@600"),
    Spec("25-연동-19", "연동", 7, 24, 30, height_m=2.2, ridge_height_m=3.6, registered_year=2025, developer="성주군농업기술센터", crop="참외", rafter_spec="φ33.5×2.3t@700"),
    Spec("25-연동-20", "연동", 6, 24, 30, height_m=2.2, ridge_height_m=3.4, registered_year=2025, developer="성주군농업기술센터", crop="참외", rafter_spec="φ33.5×2.1t@600"),
    Spec("25-연동-21", "연동", 6, 24, 30, height_m=2.2, ridge_height_m=3.4, registered_year=2025, developer="성주군농업기술센터", crop="참외", rafter_spec="φ33.5×2.1t@600"),
    Spec("25-연동-22", "연동", 7, 24, 30, height_m=2.2, ridge_height_m=3.6, registered_year=2025, developer="성주군농업기술센터", crop="참외", rafter_spec="φ33.5×2.3t@700"),
    Spec("25-연동-23", "연동", 7, 24, 30, height_m=2.2, ridge_height_m=3.6, registered_year=2025, developer="성주군농업기술센터", crop="참외", rafter_spec="φ33.5×2.3t@700"),
    Spec("25-연동-24", "연동", 7, 24, 30, height_m=4, ridge_height_m=5.7, registered_year=2025, developer="성주군농업기술센터", crop="참외", rafter_spec="φ31.8×1.7t@600"),
    Spec("25-연동-25", "연동", 7, 24, 30, height_m=4, ridge_height_m=5.7, registered_year=2025, developer="성주군농업기술센터", crop="참외", rafter_spec="φ31.8×1.7t@600"),
    Spec("26-연동-01", "연동", 6, 40, 34, height_m=2.3, ridge_height_m=3.9, registered_year=2026, developer="영덕군농업기술센터", crop="", rafter_spec="ϕ42.2×2.1t@900"),
    Spec("26-연동-02", "연동", 7, 40, 34, height_m=2.3, ridge_height_m=4.15, registered_year=2026, developer="영덕군농업기술센터", crop="", rafter_spec="ϕ42.2×2.1t@700"),
    Spec("26-연동-03", "연동", 8, 40, 34, height_m=2.3, ridge_height_m=4.4, registered_year=2026, developer="영덕군농업기술센터", crop="", rafter_spec="ϕ42.2×2.3t@600"),
    # 단동형(157종)
    Spec("07-단동-01(1)", "단동", 5, 50, 35, height_m=1.2, ridge_height_m=2.6, registered_year=2007, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.5t@600"),
    Spec("07-단동-01(1-1)", "단동", 5, 45, 34, height_m=1.2, ridge_height_m=2.6, registered_year=2007, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.5t@700"),
    Spec("07-단동-01(1-2)", "단동", 5, 40, 31, height_m=1.2, ridge_height_m=2.6, registered_year=2007, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.5t@800"),
    Spec("07-단동-01(1-3)", "단동", 5, 35, 30, height_m=1.2, ridge_height_m=2.6, registered_year=2007, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.5t@900"),
    Spec("07-단동-02(2)", "단동", 6, 50, 35, height_m=1.7, ridge_height_m=3.3, registered_year=2007, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@600"),
    Spec("07-단동-02(2-1)", "단동", 6, 43, 32, height_m=1.7, ridge_height_m=3.3, registered_year=2007, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@700"),
    Spec("07-단동-02(2-2)", "단동", 6, 38, 30, height_m=1.7, ridge_height_m=3.3, registered_year=2007, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@800"),
    Spec("07-단동-02(2-3)", "단동", 6, 34, 28, height_m=1.7, ridge_height_m=3.3, registered_year=2007, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@900"),
    Spec("07-단동-03(3)", "단동", 7, 50, 36, height_m=1.4, ridge_height_m=3.3, registered_year=2007, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@600"),
    Spec("07-단동-03(3-1)", "단동", 7, 42, 34, height_m=1.4, ridge_height_m=3.3, registered_year=2007, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@700"),
    Spec("07-단동-03(3-2)", "단동", 7, 37, 32, height_m=1.4, ridge_height_m=3.3, registered_year=2007, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@800"),
    Spec("07-단동-03(3-3)", "단동", 7, 33, 30, height_m=1.4, ridge_height_m=3.3, registered_year=2007, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@900"),
    Spec("07-단동-04(4)", "단동", 8, 48, 37, height_m=1.5, ridge_height_m=3.6, registered_year=2007, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@500"),
    Spec("07-단동-04(4-1)", "단동", 8, 38, 33, height_m=1.5, ridge_height_m=3.6, registered_year=2007, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@600"),
    Spec("07-단동-04(4-2)", "단동", 8, 32, 31, height_m=1.5, ridge_height_m=3.6, registered_year=2007, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@700"),
    Spec("07-단동-04(4-3)", "단동", 8, 28, 29, height_m=1.5, ridge_height_m=3.6, registered_year=2007, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@800"),
    Spec("07-단동-04(4-4)", "단동", 8, 25, 27, height_m=1.5, ridge_height_m=3.6, registered_year=2007, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@900"),
    Spec("07-단동-18", "단동", 7, 50, 40, height_m=1.3, ridge_height_m=2.8, registered_year=2007, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@500"),
    Spec("10-단동-01(6)", "단동", 6, 52, 37, height_m=1.7, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@500"),
    Spec("10-단동-01(6-1)", "단동", 6, 45, 34, height_m=1.7, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@600"),
    Spec("10-단동-01(6-2)", "단동", 6, 38, 31, height_m=1.7, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@700"),
    Spec("10-단동-01(6-3)", "단동", 6, 33, 29, height_m=1.7, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@800"),
    Spec("10-단동-01(6-4)", "단동", 6, 30, 28, height_m=1.7, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@900"),
    Spec("10-단동-01(6-5)", "단동", 6, 49, 38, height_m=1.7, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@500"),
    Spec("10-단동-01(6-6)", "단동", 6, 41, 32, height_m=1.7, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@600"),
    Spec("10-단동-01(6-7)", "단동", 6, 35, 29, height_m=1.7, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@700"),
    Spec("10-단동-01(6-8)", "단동", 6, 30, 27, height_m=1.7, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@800"),
    Spec("10-단동-01(6-9)", "단동", 6, 27, 26, height_m=1.7, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@900"),
    Spec("10-단동-01(6-10)", "단동", 6, 33, 27, height_m=1.7, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.7t@500"),
    Spec("10-단동-01(6-11)", "단동", 6, 27, 25, height_m=1.7, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.7t@600"),
    Spec("10-단동-01(6-12)", "단동", 6, 23, 23, height_m=1.7, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.7t@700"),
    Spec("10-단동-01(6-13)", "단동", 6, 20, 22, height_m=1.7, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.7t@800"),
    Spec("10-단동-01(6-14)", "단동", 6, 30, 26, height_m=1.7, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.5t@500"),
    Spec("10-단동-01(6-15)", "단동", 6, 25, 23, height_m=1.7, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.5t@600"),
    Spec("10-단동-01(6-16)", "단동", 6, 21, 22, height_m=1.7, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.5t@700"),
    Spec("10-단동-02(7)", "단동", 7, 50, 38, height_m=1.4, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@500"),
    Spec("10-단동-02(7-1)", "단동", 7, 42, 35, height_m=1.4, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@600"),
    Spec("10-단동-02(7-2)", "단동", 7, 36, 32, height_m=1.4, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@700"),
    Spec("10-단동-02(7-3)", "단동", 7, 31, 30, height_m=1.4, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@800"),
    Spec("10-단동-02(7-4)", "단동", 7, 28, 29, height_m=1.4, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@900"),
    Spec("10-단동-02(7-5)", "단동", 7, 46, 37, height_m=1.4, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@500"),
    Spec("10-단동-02(7-6)", "단동", 7, 38, 33, height_m=1.4, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@600"),
    Spec("10-단동-02(7-7)", "단동", 7, 33, 31, height_m=1.4, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@700"),
    Spec("10-단동-02(7-8)", "단동", 7, 28, 29, height_m=1.4, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@800"),
    Spec("10-단동-02(7-9)", "단동", 7, 25, 27, height_m=1.4, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@900"),
    Spec("10-단동-02(7-10)", "단동", 7, 30, 32, height_m=1.4, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.7t@500"),
    Spec("10-단동-02(7-11)", "단동", 7, 24, 29, height_m=1.4, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.7t@600"),
    Spec("10-단동-02(7-12)", "단동", 7, 21, 27, height_m=1.4, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.7t@700"),
    Spec("10-단동-02(7-13)", "단동", 7, 26, 30, height_m=1.4, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.5t@500"),
    Spec("10-단동-02(7-14)", "단동", 7, 22, 28, height_m=1.4, ridge_height_m=3.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.5t@600"),
    Spec("10-단동-03(8)", "단동", 7, 45, 36, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@500"),
    Spec("10-단동-03(8-1)", "단동", 7, 37, 33, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@600"),
    Spec("10-단동-03(8-2)", "단동", 7, 32, 31, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@700"),
    Spec("10-단동-03(8-3)", "단동", 7, 28, 29, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@800"),
    Spec("10-단동-03(8-4)", "단동", 7, 24, 27, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@900"),
    Spec("10-단동-03(8-5)", "단동", 7, 41, 34, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@500"),
    Spec("10-단동-03(8-6)", "단동", 7, 34, 31, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@600"),
    Spec("10-단동-03(8-7)", "단동", 7, 29, 29, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@700"),
    Spec("10-단동-03(8-8)", "단동", 7, 25, 27, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@800"),
    Spec("10-단동-03(8-9)", "단동", 7, 22, 26, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@900"),
    Spec("10-단동-03(8-10)", "단동", 7, 28, 28, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.7t@500"),
    Spec("10-단동-03(8-11)", "단동", 7, 23, 26, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.7t@600"),
    Spec("10-단동-03(8-12)", "단동", 7, 24, 27, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.5t@500"),
    Spec("10-단동-03(8-13)", "단동", 7, 20, 24, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.5t@600"),
    Spec("10-단동-04(9)", "단동", 8.2, 41, 35, height_m=1.6, ridge_height_m=3.9, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@500"),
    Spec("10-단동-04(9-1)", "단동", 8.2, 34, 32, height_m=1.6, ridge_height_m=3.9, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@600"),
    Spec("10-단동-04(9-2)", "단동", 8.2, 29, 30, height_m=1.6, ridge_height_m=3.9, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@700"),
    Spec("10-단동-04(9-3)", "단동", 8.2, 25, 28, height_m=1.6, ridge_height_m=3.9, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@800"),
    Spec("10-단동-04(9-4)", "단동", 8.2, 22, 26, height_m=1.6, ridge_height_m=3.9, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@900"),
    Spec("10-단동-04(9-5)", "단동", 8.2, 37, 34, height_m=1.6, ridge_height_m=3.9, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@500"),
    Spec("10-단동-04(9-6)", "단동", 8.2, 31, 31, height_m=1.6, ridge_height_m=3.9, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@600"),
    Spec("10-단동-04(9-7)", "단동", 8.2, 26, 28, height_m=1.6, ridge_height_m=3.9, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@700"),
    Spec("10-단동-04(9-8)", "단동", 8.2, 23, 26, height_m=1.6, ridge_height_m=3.9, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@800"),
    Spec("10-단동-04(9-9)", "단동", 8.2, 20, 25, height_m=1.6, ridge_height_m=3.9, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@900"),
    Spec("10-단동-04(9-10)", "단동", 8.2, 22, 29, height_m=1.6, ridge_height_m=3.9, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ25.4×1.7t@500"),
    Spec("10-단동-05(10)", "단동", 8.2, 30, 32, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@500"),
    Spec("10-단동-05(10-1)", "단동", 8.2, 25, 30, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@600"),
    Spec("10-단동-05(10-2)", "단동", 8.2, 22, 27, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.7t@700"),
    Spec("10-단동-05(10-3)", "단동", 8.2, 28, 31, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@500"),
    Spec("10-단동-05(10-4)", "단동", 8.2, 23, 28, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@600"),
    Spec("10-단동-05(10-5)", "단동", 8.2, 20, 26, height_m=1.6, ridge_height_m=3.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@700"),
    Spec("10-단동-06(11)", "단동", 7.6, 28, 39, height_m=1.7, ridge_height_m=3.7, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@500"),
    Spec("10-단동-06(11-1)", "단동", 7.6, 35, 42, height_m=1.7, ridge_height_m=3.7, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ42.2×2.1t@1000"),
    Spec("10-단동-06(11-2)", "단동", 7.6, 44, 47, height_m=1.7, ridge_height_m=3.7, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ42.2×2.1t@800"),
    Spec("10-단동-07(12)", "단동", 8.9, 27, 41, height_m=1.7, ridge_height_m=3.9, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ42.2×2.1t@900"),
    Spec("10-단동-07(12-1)", "단동", 8.9, 30, 43, height_m=1.7, ridge_height_m=3.9, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ42.2×2.1t@800"),
    Spec("10-단동-07(12-2)", "단동", 8.9, 35, 46, height_m=1.7, ridge_height_m=3.9, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ42.2×2.1t@700"),
    Spec("10-단동-07(12-3)", "단동", 8.9, 41, 50, height_m=1.7, ridge_height_m=3.9, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ42.2×2.1t@600"),
    Spec("10-단동-08(13)", "단동", 7.6, 25, 33, height_m=1.7, ridge_height_m=3.7, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ42.2×2.1t@800"),
    Spec("10-단동-08(13-1)", "단동", 7.6, 33, 38, height_m=1.7, ridge_height_m=3.7, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ42.2×2.1t@600"),
    Spec("10-단동-08(13-2)", "단동", 7.6, 38, 41, height_m=1.7, ridge_height_m=3.7, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ48.1×2.1t@700"),
    Spec("10-단동-08(13-3)", "단동", 7.6, 44, 44, height_m=1.7, ridge_height_m=3.7, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ48.1×2.1t@600"),
    Spec("10-단동-09(14)", "단동", 8.9, 26, 36, height_m=1.7, ridge_height_m=3.9, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ48.1×2.1t@700"),
    Spec("10-단동-09(14-1)", "단동", 8.9, 32, 40, height_m=1.7, ridge_height_m=3.9, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ59.9×2.3t@1,000"),
    Spec("10-단동-09(14-2)", "단동", 8.9, 36, 42, height_m=1.7, ridge_height_m=3.9, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ59.9×2.3t@900"),
    Spec("10-단동-09(14-3)", "단동", 8.9, 40, 45, height_m=1.7, ridge_height_m=3.9, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ59.9×2.3t@800"),
    Spec("10-단동-10", "단동", 5.4, 30, 28, height_m=1.2, ridge_height_m=2.6, registered_year=2010, developer="성주군", crop="", rafter_spec="φ25.4×1.5t@800"),
    Spec("10-단동-11", "단동", 5.6, 29, 27, height_m=1.2, ridge_height_m=2.4, registered_year=2010, developer="성주군", crop="", rafter_spec="φ31.8×1.5t@1000"),
    Spec("10-단동-12", "단동", 5.6, 27, 27, height_m=1.2, ridge_height_m=2.4, registered_year=2010, developer="성주군", crop="", rafter_spec="φ25.4×1.5t@650"),
    Spec("10-단동-13", "단동", 5.8, 30, 28, height_m=1.3, ridge_height_m=2.6, registered_year=2010, developer="성주군", crop="", rafter_spec="φ31.8×1.5t@900"),
    Spec("12-단동-01(19)", "단동", 7, 55, 42, height_m=2, ridge_height_m=3.9, registered_year=2012, developer="농촌진흥청", crop="", rafter_spec="φ42.2×2.1t@900"),
    Spec("12-단동-01(19-1)", "단동", 7, 34, 33, height_m=2, ridge_height_m=3.9, registered_year=2012, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@600"),
    Spec("12-단동-01(19-2)", "단동", 7, 28, 30, height_m=2, ridge_height_m=3.9, registered_year=2012, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@700"),
    Spec("12-단동-01(19-3)", "단동", 7, 25, 28, height_m=2, ridge_height_m=3.9, registered_year=2012, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@800"),
    Spec("12-단동-01(19-4)", "단동", 7, 22, 27, height_m=2, ridge_height_m=3.9, registered_year=2012, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@900"),
    Spec("07-단동(민)-01", "단동", 6, 25, 25, height_m=1.1, ridge_height_m=2.8, registered_year=2007, developer="한국인삼농업기자재㈜", crop="", rafter_spec="φ25.4×1.5t@600"),
    Spec("07-단동(민)-02", "단동", 6, 40, 25, height_m=1.2, ridge_height_m=2.9, registered_year=2007, developer="한국인삼농업기자재㈜", crop="", rafter_spec="φ25.4×1.5t@600"),
    Spec("07-단동(민)-03", "단동", 7, 60, 25, height_m=1.2, ridge_height_m=2.9, registered_year=2007, developer="한국인삼농업기자재㈜", crop="", rafter_spec="φ25.4×1.5t@600"),
    Spec("07-단동(민)-04", "단동", 8.2, 60, 35, height_m=1.2, ridge_height_m=2.9, registered_year=2007, developer="한국인삼농업기자재㈜", crop="", rafter_spec="φ25.4×1.5t@600"),
    Spec("08-단동(민)-01", "단동", 7, 71, 35, height_m=2, ridge_height_m=3.63, registered_year=2008, developer="㈜탄탄하우스", crop="", rafter_spec="󰋪40×60×3.0t@2,000"),
    Spec("18-단동(등)-01", "단동", 8.2, 30, 24, height_m=2, ridge_height_m=4.3, registered_year=2018, developer="천안시", crop="딸기", rafter_spec="φ25.4×1.5t@1,500"),
    Spec("19-단동(등)-01", "단동", 8.4, 28, 28, height_m=1.8, ridge_height_m=4, registered_year=2019, developer="공주시", crop="", rafter_spec="φ31.8×1.7t@500"),
    Spec("19-단동(등)-02", "단동", 8.4, 28, 28, height_m=1.8, ridge_height_m=4, registered_year=2019, developer="공주시", crop="", rafter_spec="φ42.2×2.1t@1,000"),
    Spec("19-단동(등)-03", "단동", 8.6, 28, 28, height_m=2.1, ridge_height_m=4.5, registered_year=2019, developer="공주시", crop="", rafter_spec="φ42.2×2.1t@800"),
    Spec("20-단동(등)-01", "단동", 8, 28, 26, height_m=2, ridge_height_m=4.2, registered_year=2020, developer="곡성군", crop="", rafter_spec="φ42.2×2.1t@750"),
    Spec("21-단동(등)-01", "단동", 7, 20, 34, height_m=1.5, ridge_height_m=3.1, registered_year=2021, developer="농촌진흥청(시설연)", crop="수박", rafter_spec="φ31.8×1.7t@600"),
    Spec("21-단동(등)-02", "단동", 7, 20, 34, height_m=1.8, ridge_height_m=3.4, registered_year=2021, developer="농촌진흥청(시설연)", crop="수박", rafter_spec="φ33.5×2.1t@700"),
    Spec("21-단동(등)-03", "단동", 7, 20, 34, height_m=2, ridge_height_m=3.6, registered_year=2021, developer="농촌진흥청(시설연)", crop="수박", rafter_spec="φ33.5×2.1t@600"),
    Spec("21-단동(등)-04", "단동", 7.5, 20, 34, height_m=1.5, ridge_height_m=3.2, registered_year=2021, developer="농촌진흥청(시설연)", crop="수박", rafter_spec="φ33.5×2.1t@650"),
    Spec("21-단동(등)-05", "단동", 7.5, 20, 34, height_m=1.8, ridge_height_m=3.5, registered_year=2021, developer="농촌진흥청(시설연)", crop="수박", rafter_spec="φ33.5×2.1t@700"),
    Spec("21-단동(등)-06", "단동", 7.5, 20, 34, height_m=2, ridge_height_m=3.7, registered_year=2021, developer="농촌진흥청(시설연)", crop="수박", rafter_spec="φ42.2×2.1t@900"),
    Spec("21-단동(등)-07", "단동", 8, 20, 34, height_m=1.5, ridge_height_m=3.3, registered_year=2021, developer="농촌진흥청(시설연)", crop="수박", rafter_spec="φ42.2×2.1t@1,100"),
    Spec("21-단동(등)-08", "단동", 8, 20, 34, height_m=1.8, ridge_height_m=3.6, registered_year=2021, developer="농촌진흥청(시설연)", crop="수박", rafter_spec="φ42.2×2.1t@1,000"),
    Spec("21-단동(등)-09", "단동", 8, 20, 34, height_m=2, ridge_height_m=3.8, registered_year=2021, developer="농촌진흥청(시설연)", crop="수박", rafter_spec="φ42.2×2.1t@900"),
    Spec("21-단동(대형)-01", "단동", 28, 50, 40, height_m=5.5, ridge_height_m=14, registered_year=2021, developer="농촌진흥청", crop="", rafter_spec="φ48.1×2.1t@1,000"),
    Spec("21-단동(대형)-02", "단동", 28, 40, 30, height_m=6.5, ridge_height_m=15, registered_year=2021, developer="농촌진흥청", crop="", rafter_spec="φ48.1×2.1t@1,000"),
    Spec("21-단동(대형)-03", "단동", 28, 50, 40, height_m=6.5, ridge_height_m=15, registered_year=2021, developer="농촌진흥청", crop="", rafter_spec="φ48.1×2.3t@1,000"),
    Spec("21-단동(대형)-04", "단동", 38, 50, 40, height_m=5.5, ridge_height_m=17, registered_year=2021, developer="농촌진흥청", crop="", rafter_spec="φ48.1×2.3t@1,000"),
    Spec("21-단동(대형)-05", "단동", 38, 50, 40, height_m=6.5, ridge_height_m=18, registered_year=2021, developer="농촌진흥청", crop="", rafter_spec="φ48.1×2.3t@1,000"),
    Spec("21-단동(대형)-06", "단동", 48, 50, 40, height_m=5.5, ridge_height_m=20, registered_year=2021, developer="농촌진흥청", crop="", rafter_spec="φ48.1×2.3t@1,000"),
    Spec("21-단동(대형)-07", "단동", 48, 50, 40, height_m=6.5, ridge_height_m=21, registered_year=2021, developer="농촌진흥청", crop="", rafter_spec="φ48.1×2.3t@1,000"),
    Spec("22-단동(등)-01", "단동", 7.6, 35, 35, height_m=2.1, ridge_height_m=4.3, registered_year=2022, developer="농협경제지주", crop="", rafter_spec="φ33.5×2.1t@500"),
    Spec("22-단동(등)-02", "단동", 7.6, 45, 43, height_m=2.1, ridge_height_m=4.3, registered_year=2022, developer="농협경제지주", crop="", rafter_spec="φ42.2×2.1t@500"),
    Spec("22-단동(등)-03", "단동", 8.6, 45, 43, height_m=2.2, ridge_height_m=4.5, registered_year=2022, developer="농협경제지주", crop="", rafter_spec="φ42.2×2.1t@500"),
    Spec("23-단동(등)-01", "단동", 8, 22, 28, height_m=3.5, ridge_height_m=5.1, registered_year=2023, developer="합천군", crop="춘란", rafter_spec="φ31.8×1.7t@600 φ31.8×1.7t@2,000"),
    Spec("23-단동(등)-02", "단동", 7, 40, 35, height_m='1.6/3.0', ridge_height_m=4.49, registered_year=2023, developer="국제원예연구원", crop="", rafter_spec="φ33.5×2.1t@2,000 φ31.8x1.7t@2,000"),
    Spec("23-단동(등)-03", "단동", 9, 36, 32, height_m='1.8/3.5', ridge_height_m=5.47, registered_year=2023, developer="국제원예연구원", crop="", rafter_spec="φ33.5×2.1t@2,000 φ31.8x1.7t@2,000"),
    Spec("23-단동(등)-04", "단동", 11, 31, 29, height_m='2.0/4.0', ridge_height_m=6.35, registered_year=2023, developer="국제원예연구원", crop="", rafter_spec="φ33.5×2.1t@2,000"),
    Spec("23-단동(등)-05", "단동", 8, 38, 34, height_m='2.0/3.5', ridge_height_m=5.22, registered_year=2023, developer="국제원예연구원", crop="", rafter_spec="φ33.5×2.1t@2,000"),
    Spec("23-단동(등)-06", "단동", 10, 32, 31, height_m='2.2/4.0', ridge_height_m=6.16, registered_year=2023, developer="국제원예연구원", crop="", rafter_spec="φ33.5×2.1t@2,000"),
    Spec("23-단동(등)-07", "단동", 7, 40, 32, height_m=2.5, ridge_height_m=4.4, registered_year=2023, developer="평창군", crop="", rafter_spec="φ42.2×2.1t@600"),
    Spec("23-단동(등)-08", "단동", 8.2, 40, 32, height_m=2.5, ridge_height_m=4.8, registered_year=2023, developer="평창군", crop="", rafter_spec="φ42.2×2.1t@500"),
    Spec("23-단동(등)-09", "단동", 7, 40, 40, height_m=2.5, ridge_height_m=4.4, registered_year=2023, developer="평창군", crop="", rafter_spec="φ48.1×2.1t@500"),
    Spec("24-단동(등)-01", "단동", 8, 40, 40, height_m=2, ridge_height_m=4, registered_year=2024, developer="국립농업과학원", crop="양파육묘", rafter_spec="φ42.2×2.1t@650"),
    Spec("24-단동(등)-02", "단동", 8, 40, 34, height_m=2, ridge_height_m=4, registered_year=2024, developer="국립농업과학원", crop="양파육묘", rafter_spec="φ33.5×2.1t@600"),
    Spec("24-단동(등)-03", "단동", 8, 22, 28, height_m=2, ridge_height_m=4, registered_year=2024, developer="국립농업과학원", crop="양파육묘", rafter_spec="φ31.8×1.7t@600"),
    Spec("24-단동(등)-04", "단동", 8.5, 42, 30, height_m=2, ridge_height_m=4.2, registered_year=2024, developer="담양군", crop="", rafter_spec="φ42.2×2.3t@500"),
    Spec("24-단동(등)-05", "단동", 8.2, 42, 30, height_m=2, ridge_height_m=4.2, registered_year=2024, developer="담양군", crop="", rafter_spec="φ42.2×2.1t@500"),
    Spec("24-단동(등)-06", "단동", 14, 34, 39, height_m=2, ridge_height_m=4.3, registered_year=2024, developer="국립원예특작과학원", crop="딸기육묘", rafter_spec="φ48.1×2.1t@1,000"),
    Spec("24-단동(등)-07", "단동", 14, 34, 39, height_m=2, ridge_height_m=4.3, registered_year=2024, developer="국립원예특작과학원", crop="딸기육묘", rafter_spec="φ48.1×2.1t@1,000"),
    Spec("24-단동(등)-08", "단동", 14, 55, 46, height_m=2, ridge_height_m=4.3, registered_year=2024, developer="국립원예특작과학원", crop="딸기육묘", rafter_spec="φ59.9×2.3t@1,500"),
    Spec("24-단동(등)-09", "단동", 14, 55, 46, height_m=2, ridge_height_m=4.3, registered_year=2024, developer="국립원예특작과학원", crop="딸기육묘", rafter_spec="φ59.9×2.3t@1,500"),
    Spec("24-단동(등)-10", "단동", 7, 30, 39, height_m=1.8, ridge_height_m=3.4, registered_year=2024, developer="국립원예특작과학원", crop="수박", rafter_spec="φ42.2×2.1t@900"),
    Spec("24-단동(등)-11", "단동", 7, 33, 41, height_m=2, ridge_height_m=3.6, registered_year=2024, developer="국립원예특작과학원", crop="수박", rafter_spec="φ42.2×2.1t@900"),
    Spec("24-단동(등)-12", "단동", 7.5, 30, 41, height_m=1.8, ridge_height_m=3.5, registered_year=2024, developer="국립원예특작과학원", crop="수박", rafter_spec="φ42.2×2.1t@800"),
    Spec("25-단동(등)-01", "단동", 8.2, 26, 28, height_m=2.2, ridge_height_m=4.5, registered_year=2025, developer="부여군", crop="", rafter_spec="φ33.5×2.1t@500"),
    Spec("25-단동-02", "단동", 11, 22, 40, height_m=3.35, ridge_height_m=7.35, registered_year=2025, developer="트러스하우스군", crop="", rafter_spec="ㅡ"),
    # 광폭형(11종)
    Spec("10-광폭-01", "광폭", 14.8, 33, 40, height_m=2.2, ridge_height_m=4.3, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="φ33.5×2.1t@500"),
    Spec("10-광폭-02", "광폭", 16, 35, 40, height_m=2.1, ridge_height_m=4.5, registered_year=2010, developer="농촌진흥청", crop="", rafter_spec="용융도금 트러스 골조@1,200"),
    Spec("13-광폭(보온재)-01", "광폭", 14, 25, 28, height_m=2, ridge_height_m=4.1, registered_year=2013, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@600"),
    Spec("13-광폭(보온재)-02", "광폭", 16, 23, 28, height_m=2, ridge_height_m=4.1, registered_year=2013, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@600"),
    Spec("13-광폭(보온재)-03", "광폭", 18, 23, 29, height_m=2, ridge_height_m=4.1, registered_year=2013, developer="농촌진흥청", crop="", rafter_spec="φ33.5×2.1t@600"),
    Spec("13-광폭(보온재)-04", "광폭", 21, 23, 27, height_m=2, ridge_height_m=4.2, registered_year=2013, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@600"),
    Spec("13-광폭(보온재)-05", "광폭", 24, 20, 27, height_m=2, ridge_height_m=4.2, registered_year=2013, developer="농촌진흥청", crop="", rafter_spec="φ31.8×1.5t@600"),
    Spec("13-광폭(보온재)-06", "광폭", 27, 20, 27, height_m=2, ridge_height_m=4.2, registered_year=2013, developer="농촌진흥청", crop="", rafter_spec="φ33.5×2.1t@700"),
    Spec("10-광폭(민)-01", "광폭", 15, 40, 40, height_m=3, ridge_height_m=6, registered_year=2010, developer="민간", crop="", rafter_spec="용융도금 트러스 골조@1,200"),
    Spec("10-광폭(민)-02", "광폭", 17, 40, 35, height_m=3, ridge_height_m=7, registered_year=2010, developer="민간", crop="", rafter_spec="용융도금 트러스 골조@1,200"),
    Spec("10-광폭(민)-03", "광폭", 22, 40, 35, height_m=3, ridge_height_m=7, registered_year=2010, developer="민간", crop="", rafter_spec="용융도금 트러스 골조@1,200"),
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
# 난방부하계수 U (kcal/㎡·hr·℃). 2026-07-19 재조사(레지스트리 U_VALUE source
# 참고): 유리(5.3)는 물리계산+독립문헌 이중검증으로 타당범위 확인(단 원출처는
# 국토부 건축기준 오염 의심). 필름·불소필름이 같은 값(5.7)인 건 단순화가
# 아니라 "얇은 단일층 필름은 재질(PO/PE/불소)보다 표면공기막 저항이 U값을
# 지배한다"는 물리적으로 타당한 근사(재질별로 쪼갤 근거 없음, 오히려 쪼개면
# 근거 없는 정밀도가 됨). 미해결 변수는 재질이 아니라 층수 — 한국 상업
# 온실의 '필름' 피복이 단일층인지 이중층인지에 따라 U값이 크게(~40%) 달라질
# 수 있는데 케이스 데이터에 층수 구분이 없다.
# 2026-07-19 후속: 우민재 케이스 원문(스마트팜스펙/우민재/3. 공사설명서(우민재).pdf
# p.1 "4) 피복공사")을 직접 열람해 이 변수를 그 케이스에 한해 확정했다 —
# "온실상부,측면: 장기성 PO필름 0.15T(외피) / 내부: 장기성 PO필름 0.1T(내피)"로
# 명시돼 있고, 공사내역서 수량(0.15t 4,157㎡ + 0.1T 1,118㎡)과도 정합해 우민재는
# 이중층 피복이 확인됨(n=1, 다른 케이스로 일반화 불가). 그런데 cases/uminjae.json은
# cover="필름" 하나로만 기록해 U_VALUE["필름"]=5.7(층수 미구분 근사치)이 그대로
# 적용된다 — 실제 이중층 구조면 공기층 단열효과로 진짜 U값은 이보다 낮을 가능성이
# 높아, 현재 우민재 케이스의 heating_load() 결과는 난방부하를 과대추정하는
# 방향으로 편향됐을 수 있다.
# 2026-07-19 추가후속: 이중층 U값의 국내 1차 출처를 직접 탐색했다. 가장 유력한
# 후보인 국립원예특작과학원 「온실 열손실 저감 및 차단 기술 연구」최종보고서
# (KISTI ScienceON TRKO202100009930, 2021-02)는 목차상 "피복 및 보온재의 이중
# 피복 조합별 열관류율(24개 조합) 측정표"를 정확히 담고 있어 존재는 확인됐지만,
# 본문 PDF가 KISTI/NTIS 로그인 뒤에 있어 이번 세션(로그인 세션 없음, 대체
# 렌더링도 10초 이상 빈 화면으로 실패)에선 수치를 못 가져왔다. 한국농업기계학회
# PO필름 논문(우민재와 동일한 외피0.15+내피0.10 이중구조를 실측)도 확인했으나
# 무료 초록에는 열관류율 수치가 없고, 애초에 PO/PE 재질 비교 실험이라 단일-이중
# 비교값도 아니다. 국내 1차 출처 확보는 실패로 남겨두고, 대신 국제 온실원예
# 자료(다수 수렴)로 [추정]값을 추가한다 — RIMOL 등 미국 온실업체 자료가 제시하는
# "4mm 공기층을 사이에 둔 1mm PE막 2장" 이중필름 U=4.4W/㎡K, 및 R값 환산치
# (단일 R=0.85→이중 R=1.25, Btu 관행단위 환산 시 U≈4.5W/㎡K)가 서로 근접해
# 4.4W/㎡K를 채택 → kcal 환산(×0.86) 시 약 3.8kcal/㎡·hr·℃(단일층 5.7 대비 약
# 33% 낮음, 국제자료가 말하는 '야간 열손실 40% 감소'와 같은 방향·크기대).
# 국내 1차 출처가 아니므로 여전히 [추정] 등급이며, 위 KISTI 보고서 원문을
# 확보하면 최우선으로 이 값을 교체할 것.
# 2026-07-19 재추가후속: 위 KISTI 보고서는 여전히 로그인장벽으로 못 뚫었지만,
# 사용자가 찾아준 별개의 국내 1차 출처를 확보해 국제자료 추정치를 실측치로
# 교체했다 — 이현우 등(경북대 농업토목공학과), "플라스틱온실의 피복방식에 따른
# 보온 및 광투과 성능 평가", 시설원예·식물공장 22(3):270-278 (2013), DOI
# 10.12791/KSBEC.2013.22.3.270 (koreascience.kr 무료 원문 PDF, 로그인 불필요).
# 경기도 화성시 실험온실(토마토, 3연동)에서 겨울철 2개월간 실제 경유소비량을
# 측정해 역산한 관류열전달계수(Table 2, 온실실험 기준, W/㎡K): 일중피복 3.09,
# 공기주입 이중피복 2.73(2회 평균), 관행 이중피복 2.12 — 모형실험값(2.93/-/2.20)과
# 근접해 신뢰성 확인됨. 우민재는 공기주입 방식(블로워로 공기층 유지) 언급이
# 원문에 없고 외피+내피를 각각 별도 골조에 씌우는 통상적 시공(공사내역서 PO필름
# 0.15t/0.1T 별도 수량 계상)이라 '관행 이중피복' 쪽이 더 가깝다고 판단해 그 값을
# 채택 — 2.12W/㎡K×0.86≈1.82kcal/㎡·hr·℃로 필름_이중을 교체(기존 국제추정 3.8→
# 실측 1.82, 상태 [추정]에서 격상). 관행 이중피복/일중피복 비율(2.12/3.09≈0.686,
# 약 31% 감소)이 국제자료 기반 추정 비율(약33%감소)과 거의 일치해 방향·크기 모두
# 교차검증됨 — 그래서 '필름_이중'은 이 실측값을 신뢰하고 교체한다.
# ⚠️ 그런데 이 논문은 동시에 훨씬 더 큰 별개의 의문을 던진다 — 실측 일중피복
# U=3.09W/㎡K(≈2.66kcal/㎡·hr·℃)가 현재 U_VALUE["필름"]=5.7과 2배 이상
# 차이난다(5.7은 미국 온실원예 교재의 이론 R값 계산과 맞았던 값). 즉 '필름_이중'은
# 이 논문의 절대값을 그대로 썼지만, 그 절대값의 기준이 되는 '필름'(단일층) 자체가
# 이 논문 기준으로는 훨씬 낮아야 한다는 뜻 — 두 물리적으로 타당해 보이는 독립
# 출처(미국 이론계산 vs 한국 실측)가 단일층 기준값에서 정면으로 충돌한다. 이건
# 이번 세션에서 결론짓지 않는다(케이스 회귀 영향 범위가 크고, 그동안 "이중검증
# 통과"로 기록해온 5.7의 신뢰도를 흔드는 사안이라 사용자 확인 필요) — U_VALUE["필름"]
# 은 그대로 두고 이 모순만 정확히 기록해 다음 판단의 근거로 남긴다.
# 2026-07-19 최종후속(사용자 지시로 재검토·결정): 5.7의 원출처 두 건(미국 교재
# R값, 불소필름 물성계산)은 전부 "이론계산"이었지 실측이 아니었다 — 반면 이현우
# 등(2013)은 실제 온실에서 겨울 2개월간 측정한 진짜 연료소비량을 역산한 "실측"이고,
# 같은 논문의 모형계산과도 교차검증됨(엔진 실측>이론 우선 원칙과 일치). 사용자
# 승인 하에 필름·불소필름·단동을 5.7→2.66(Table 2 온실실측 일중피복 3.09W/㎡K
# 환산치)으로 전면 교체한다. 필름_이중(1.82)과 같은 논문·같은 실험조건에서 나온
# 짝값이라 내적 일관성도 확보됨(2.66×0.686≈1.82, 정확히 일치).
# ⚠️ 알려진 트레이드오프(교체는 하되 이 리스크는 명시적으로 남긴다): heating_load()의
# 목적은 "최대난방부하"(장비 용량 설계용, 극한조건 기준)인데, 이현우 등의 값은
# "2개월 평균" 연료소비 기반 — 설계 극한야간이 아닌 평균조건을 반영한다. 즉 이
# 교체로 향후 필름 케이스의 난방장비 용량 추천이 과소산정될 위험이 있다(설계
# 안전마진 감소). 원문서(엔진데이터 A-4/A-5) 자체가 미확보라 "5.7이 원래 설계
# 최대부하 의도였다"는 것도 추정일 뿐 확정 근거는 없다 — 그럼에도 실측 데이터가
# 없는 것보다 있는 게 낫다는 판단 하에, 그리고 heating_load()가 안전율(safety
# 파라미터, 기본 1.1)을 이미 곱하는 구조라는 점을 감안해 사용자가 교체를 택함.
# 2026-07-20: 위 트레이드오프에 대한 구조 개선을 적용한다 — heating_load()가
# u_design(최대부하용)·u_period(기간/연료소비용) 두 인자를 받도록 분리했다.
# 미지정 시 둘 다 U_VALUE[cover]로 폴백해 기존 회귀값(원채원 케이스 등)은 완전히
# 그대로다 — 이번 변경은 "숫자 교체"가 아니라 "값을 나중에 따로 넣을 수 있는
# 구조"만 만든 것. 즉 극한설계조건 U값의 실제 근거(1차 출처)가 아직 없으므로
# u_design에 넣을 확정값은 여전히 [확인요망]이며, 근거 확보 전까지는 호출부가
# u_design을 지정하지 않는 한 계속 안전마진 감소 위험이 남는다.
U_VALUE = {"유리": 5.3, "필름": 2.66, "불소필름": 2.66, "단동": 2.66, "필름_이중": 1.82}
# 보온비 fr (피복조합) — ⚠️ 2026-07-19 재조사: 이 표는 어떤 함수에서도 참조되지
# 않는 미사용 상수다(heating_load()는 fr을 호출부가 직접 숫자로 주입받는다).
# FR_TABLE 자체는 국내 관행 그대로 "열절감률"(값이 클수록 보온이 잘 됨: PO단일
# 0.35 < 다겹보온 0.5 < 이중커튼 0.85)을 담고 있어 인용 출처(다겹보온커튼
# 열절감률45% 등)와 방향이 일치한다 — 표 자체는 안 고친다. 문제는 heating_load()의
# 공식(`부하 = 면적×U×ΔT×fr`)이 fr을 *노출비율*(클수록 부하가 커짐, 즉 보온이
# 나쁠수록 커야 함)로 기대한다는 것 — "열절감률"을 그대로 곱하면 이중커튼(최선
# 보온)이 PO단일(커튼 없음)보다 부하가 더 크게 나오는 반전이 생긴다.
# ✅ 방향 수정(2026-07-20): FR_TABLE 값은 그대로 두고, 아래 curtain_exposure_ratio()가
# 열절감률→노출비율(1-절감률) 변환을 전담한다 — heating_load(fr=...)에는 반드시
# FR_TABLE 원값이 아니라 curtain_exposure_ratio()의 반환값을 넣을 것.
# ⚠️ 절감률 자체의 절대값(0.35/0.5/0.85)은 여전히 1차 출처 미확보([확인요망],
# 유력 후보는 NIHHS '온실에너지계산' API 가이드문서, atis.rda.go.kr 로그인장벽으로
# 미확보) — 이번 수정은 "방향"만 고친 것이지 절감률 수치를 검증한 게 아니다.
FR_TABLE = {"PO단일": 0.35, "다겹보온": 0.5, "이중커튼": 0.85, "2중커튼": 0.85}


def curtain_exposure_ratio(curtain: str) -> float:
    """FR_TABLE의 열절감률(클수록 보온 잘 됨)을 heating_load()의 fr 인자가
    기대하는 노출비율(클수록 부하가 커짐, 즉 보온이 나쁠수록 커야 함)로 변환.
    반환값 = 1 - FR_TABLE[curtain] — 값이 작을수록 보온이 잘 돼 난방부하가
    줄어드는 올바른 방향이 된다. curtain이 FR_TABLE에 없으면 ValueError."""
    if curtain not in FR_TABLE:
        raise ValueError(f"'{curtain}'은 FR_TABLE에 없는 피복조합이다 (선택: {list(FR_TABLE)})")
    return 1 - FR_TABLE[curtain]
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
                 fuel: str = "등유", floor_area_m2: Optional[float] = None,
                 u_design: Optional[float] = None, u_period: Optional[float] = None
                 ) -> HeatingResult:
    """최대난방부하 = Aw × u_design × ΔT × 보온비. 기간(연료소비)부하는 u_period 사용. (A-5 구조)
    u_design/u_period 미지정 시 둘 다 U_VALUE[cover]로 폴백(기존 동작과 동일 —
    설계극한조건과 기간평균조건에 서로 다른 U값 근거가 확보되기 전까지의 임시
    상태, U_VALUE source 주석 참고). degree_hours: 난방디그리아워(기본은 A-5
    예시값). fuel: 연료종류."""
    u_d = u_design if u_design is not None else U_VALUE.get(cover, 5.7)
    u_p = u_period if u_period is not None else U_VALUE.get(cover, 5.7)
    dt = t_target - t_min
    max_load = surface_area_m2 * u_d * dt * fr
    heater = max_load * safety
    period_load = degree_hours * u_p * fr * surface_area_m2  # 기간난방부하 근사
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
# 입지: 지역→설계하중 매핑 (2026-07-21, 2025-108호 개정 반영으로 전면 교체)
#   ⚠️ 2026-07-21 발견: 기존 소스(농림축산식품부 고시 제2014-78호, 2014년)는
#   이미 폐기된 구버전이었다 — 농림축산식품부가 2025-10-31자로 「원예·특작시설
#   내재해 설계기준 및 내재해형 시설규격 등록 규정」을 개정(고시 제2025-108호,
#   공포·시행 2025.10.31)했고, 이 개정이 현재 유효한 최신 고시다(law.go.kr
#   admRulSeq=2100000266030으로 확인, 이전 admRulSeq=2100000181537은 2019-44호로
#   이미 한 세대 전 버전이었음). 발견 계기: 스마트팜스펙/2025년 청년농업인...
#   이준호(함평) 온실 구조계산서(2025년 작성)가 함평을 적설심 40cm로 명시했는데
#   기존 REGION_DESIGN_LOAD엔 36cm로 등록돼 있어 불일치 발견 → 원본 2014-78호
#   (농사로 재다운로드, 32MB)를 대조한 결과 2014-78호 자체엔 36cm가 맞게
#   전사돼 있었음(우리 과거 전사는 정확했음) → 문제는 그 출처 자체가 낡았다는 것.
#   신규 출처: 농림축산식품부 보도자료 "폭설·강풍 피해 예방 위한 원예·특작시설
#   내재해 설계기준 개정"(2025.11.3, mafra.go.kr/bbs/home/792/575791)의 첨부
#   참고자료(bbs/home/792/591630/download.do) "참고2 개정된 지역별 적설심
#   설계기준"·"참고3 개정된 지역별 풍속 설계기준" — 개정 후 전체 표(diff가
#   아니라 전면 교체본)를 pdfplumber로 표 구조 그대로 추출(raw text 파싱이 아니라
#   PDF 테이블 셀 경계 인식 사용 — 이전 표에서 컬럼 밀림 오독 위험을 인지해
#   더 안전한 방법 채택), 172개 지역 전량 스냅·풍속 두 표의 키 집합이 정확히
#   일치함을 자동 검증 후 병합. 기존 40cm/40m·s "이상" 뭉뚱그림 구간이 22개
#   지역(적설)·16개 지역(풍속)에서 실측 수치로 구체화됨(예: 대관령 40→167cm,
#   울릉 40→197cm, 함평 36→40cm) — 나머지 지역도 14개(적설)·8개(풍속) 상향
#   조정 반영, 172개 중 84개 값 변경·88개 불변. 지명 중복 2건은 기존과 동일하게
#   광역 힌트로 구분(고성(강원)/고성(경남), 광주(경기)/광주광역시).
#   ⚠️ 영향 확인: 기존 케이스 중 `cases/chuncheon.json`(강원 춘천, wind_ms만
#   32→34 변경, snow_cm은 32로 불변)·`cases/uminjae.json`(충남 천안 성환읍,
#   변경 없음)·`cases/wonchaewon.json`(region="충남"만, 애초에 조회 불가라
#   무관) — 춘천 케이스 wind_ms를 함께 갱신했다(원채원 회귀 기준값은 영향 없음).
# ─────────────────────────────────────────────────────────────
REGION_DESIGN_LOAD: dict = {
    "가평": {"snow_cm": 24, "wind_ms": 32},
    "강릉": {"snow_cm": 93, "wind_ms": 40},
    "강진": {"snow_cm": 24, "wind_ms": 34},
    "강화": {"snow_cm": 24, "wind_ms": 36},
    "거제": {"snow_cm": 20, "wind_ms": 32},
    "거창": {"snow_cm": 30, "wind_ms": 26},
    "경산": {"snow_cm": 20, "wind_ms": 28},
    "경주": {"snow_cm": 20, "wind_ms": 32},
    "계룡": {"snow_cm": 32, "wind_ms": 32},
    "고령": {"snow_cm": 22, "wind_ms": 28},
    "고산": {"snow_cm": 20, "wind_ms": 45},
    "고성(강원)": {"snow_cm": 79, "wind_ms": 43},
    "고성(경남)": {"snow_cm": 20, "wind_ms": 38},
    "고양": {"snow_cm": 24, "wind_ms": 32},
    "고창": {"snow_cm": 48, "wind_ms": 34},
    "고흥": {"snow_cm": 20, "wind_ms": 34},
    "곡성": {"snow_cm": 28, "wind_ms": 26},
    "공주": {"snow_cm": 28, "wind_ms": 32},
    "과천": {"snow_cm": 26, "wind_ms": 28},
    "광명": {"snow_cm": 26, "wind_ms": 30},
    "광양": {"snow_cm": 20, "wind_ms": 34},
    "광주(경기)": {"snow_cm": 24, "wind_ms": 26},
    "광주광역시": {"snow_cm": 38, "wind_ms": 32},
    "괴산": {"snow_cm": 30, "wind_ms": 26},
    "구례": {"snow_cm": 24, "wind_ms": 28},
    "구리": {"snow_cm": 24, "wind_ms": 28},
    "구미": {"snow_cm": 24, "wind_ms": 32},
    "군산": {"snow_cm": 34, "wind_ms": 38},
    "군위": {"snow_cm": 22, "wind_ms": 28},
    "군포": {"snow_cm": 26, "wind_ms": 28},
    "금산": {"snow_cm": 26, "wind_ms": 24},
    "김제": {"snow_cm": 40, "wind_ms": 32},
    "김천": {"snow_cm": 28, "wind_ms": 32},
    "김포": {"snow_cm": 24, "wind_ms": 32},
    "김해": {"snow_cm": 20, "wind_ms": 34},
    "나주": {"snow_cm": 36, "wind_ms": 34},
    "남양주": {"snow_cm": 24, "wind_ms": 28},
    "남원": {"snow_cm": 30, "wind_ms": 26},
    "남해": {"snow_cm": 20, "wind_ms": 34},
    "논산": {"snow_cm": 28, "wind_ms": 28},
    "단양": {"snow_cm": 26, "wind_ms": 30},
    "담양": {"snow_cm": 40, "wind_ms": 30},
    "당진": {"snow_cm": 28, "wind_ms": 32},
    "대관령": {"snow_cm": 167, "wind_ms": 43},
    "대구": {"snow_cm": 20, "wind_ms": 28},
    "대전": {"snow_cm": 32, "wind_ms": 32},
    "동두천": {"snow_cm": 22, "wind_ms": 30},
    "동해": {"snow_cm": 85, "wind_ms": 38},
    "마산": {"snow_cm": 20, "wind_ms": 36},
    "목포": {"snow_cm": 34, "wind_ms": 36},
    "무안": {"snow_cm": 36, "wind_ms": 34},
    "무주": {"snow_cm": 30, "wind_ms": 26},
    "문경": {"snow_cm": 38, "wind_ms": 28},
    "밀양": {"snow_cm": 20, "wind_ms": 32},
    "보령": {"snow_cm": 26, "wind_ms": 36},
    "보성": {"snow_cm": 20, "wind_ms": 30},
    "보은": {"snow_cm": 34, "wind_ms": 24},
    "봉화": {"snow_cm": 24, "wind_ms": 26},
    "부산": {"snow_cm": 24, "wind_ms": 36},
    "부안": {"snow_cm": 47, "wind_ms": 32},
    "부여": {"snow_cm": 26, "wind_ms": 28},
    "부천": {"snow_cm": 24, "wind_ms": 32},
    "사천": {"snow_cm": 20, "wind_ms": 34},
    "산청": {"snow_cm": 24, "wind_ms": 30},
    "삼척": {"snow_cm": 79, "wind_ms": 26},
    "상주": {"snow_cm": 34, "wind_ms": 30},
    "서귀포": {"snow_cm": 20, "wind_ms": 43},
    "서산": {"snow_cm": 30, "wind_ms": 34},
    "서울": {"snow_cm": 26, "wind_ms": 30},
    "서천": {"snow_cm": 32, "wind_ms": 36},
    "성남": {"snow_cm": 26, "wind_ms": 28},
    "성산": {"snow_cm": 24, "wind_ms": 40},
    "성주": {"snow_cm": 24, "wind_ms": 30},
    "세종": {"snow_cm": 30, "wind_ms": 28},
    "속초": {"snow_cm": 91, "wind_ms": 46},
    "수원": {"snow_cm": 26, "wind_ms": 28},
    "순창": {"snow_cm": 38, "wind_ms": 28},
    "순천": {"snow_cm": 22, "wind_ms": 26},
    "시흥": {"snow_cm": 26, "wind_ms": 32},
    "신안": {"snow_cm": 30, "wind_ms": 40},
    "아산": {"snow_cm": 26, "wind_ms": 28},
    "안동": {"snow_cm": 22, "wind_ms": 28},
    "안산": {"snow_cm": 26, "wind_ms": 30},
    "안성": {"snow_cm": 26, "wind_ms": 26},
    "안양": {"snow_cm": 26, "wind_ms": 28},
    "양구": {"snow_cm": 30, "wind_ms": 32},
    "양산": {"snow_cm": 20, "wind_ms": 34},
    "양양": {"snow_cm": 99, "wind_ms": 42},
    "양주": {"snow_cm": 24, "wind_ms": 30},
    "양평": {"snow_cm": 24, "wind_ms": 28},
    "여수": {"snow_cm": 20, "wind_ms": 42},
    "여주": {"snow_cm": 26, "wind_ms": 24},
    "연천": {"snow_cm": 24, "wind_ms": 30},
    "영광": {"snow_cm": 42, "wind_ms": 34},
    "영덕": {"snow_cm": 40, "wind_ms": 34},
    "영동": {"snow_cm": 30, "wind_ms": 28},
    "영암": {"snow_cm": 30, "wind_ms": 32},
    "영양": {"snow_cm": 26, "wind_ms": 30},
    "영월": {"snow_cm": 32, "wind_ms": 30},
    "영주": {"snow_cm": 28, "wind_ms": 32},
    "영천": {"snow_cm": 20, "wind_ms": 30},
    "예산": {"snow_cm": 26, "wind_ms": 30},
    "예천": {"snow_cm": 28, "wind_ms": 30},
    "오산": {"snow_cm": 26, "wind_ms": 28},
    "옥천": {"snow_cm": 32, "wind_ms": 28},
    "옹진": {"snow_cm": 26, "wind_ms": 36},
    "완도": {"snow_cm": 20, "wind_ms": 42},
    "완주": {"snow_cm": 26, "wind_ms": 30},
    "용인": {"snow_cm": 26, "wind_ms": 26},
    "울릉": {"snow_cm": 197, "wind_ms": 53},
    "울산": {"snow_cm": 20, "wind_ms": 32},
    "울주": {"snow_cm": 20, "wind_ms": 32},
    "울진": {"snow_cm": 42, "wind_ms": 45},
    "원주": {"snow_cm": 26, "wind_ms": 26},
    "음성": {"snow_cm": 28, "wind_ms": 26},
    "의령": {"snow_cm": 20, "wind_ms": 32},
    "의성": {"snow_cm": 20, "wind_ms": 26},
    "의왕": {"snow_cm": 26, "wind_ms": 28},
    "의정부": {"snow_cm": 24, "wind_ms": 30},
    "이천": {"snow_cm": 28, "wind_ms": 24},
    "익산": {"snow_cm": 28, "wind_ms": 30},
    "인제": {"snow_cm": 32, "wind_ms": 30},
    "인천": {"snow_cm": 26, "wind_ms": 36},
    "임실": {"snow_cm": 40, "wind_ms": 26},
    "장성": {"snow_cm": 43, "wind_ms": 32},
    "장수": {"snow_cm": 38, "wind_ms": 26},
    "장흥": {"snow_cm": 22, "wind_ms": 32},
    "전주": {"snow_cm": 26, "wind_ms": 30},
    "정선": {"snow_cm": 86, "wind_ms": 34},
    "정읍": {"snow_cm": 54, "wind_ms": 26},
    "제주": {"snow_cm": 20, "wind_ms": 43},
    "제천": {"snow_cm": 26, "wind_ms": 26},
    "증평": {"snow_cm": 32, "wind_ms": 26},
    "진도": {"snow_cm": 24, "wind_ms": 40},
    "진안": {"snow_cm": 34, "wind_ms": 26},
    "진주": {"snow_cm": 20, "wind_ms": 32},
    "진천": {"snow_cm": 30, "wind_ms": 26},
    "진해": {"snow_cm": 20, "wind_ms": 34},
    "창녕": {"snow_cm": 20, "wind_ms": 30},
    "창원": {"snow_cm": 20, "wind_ms": 36},
    "천안": {"snow_cm": 26, "wind_ms": 28},
    "철원": {"snow_cm": 22, "wind_ms": 34},
    "청도": {"snow_cm": 20, "wind_ms": 30},
    "청송": {"snow_cm": 22, "wind_ms": 30},
    "청양": {"snow_cm": 26, "wind_ms": 30},
    "청원": {"snow_cm": 34, "wind_ms": 28},
    "청주": {"snow_cm": 34, "wind_ms": 28},
    "추풍령": {"snow_cm": 32, "wind_ms": 32},
    "춘천": {"snow_cm": 32, "wind_ms": 34},
    "충주": {"snow_cm": 26, "wind_ms": 26},
    "칠곡": {"snow_cm": 22, "wind_ms": 30},
    "태백": {"snow_cm": 79, "wind_ms": 28},
    "태안": {"snow_cm": 28, "wind_ms": 34},
    "통영": {"snow_cm": 20, "wind_ms": 41},
    "파주": {"snow_cm": 24, "wind_ms": 30},
    "평창": {"snow_cm": 55, "wind_ms": 32},
    "평택": {"snow_cm": 26, "wind_ms": 28},
    "포천": {"snow_cm": 22, "wind_ms": 32},
    "포항": {"snow_cm": 20, "wind_ms": 36},
    "하남": {"snow_cm": 24, "wind_ms": 28},
    "하동": {"snow_cm": 20, "wind_ms": 32},
    "함안": {"snow_cm": 20, "wind_ms": 34},
    "함양": {"snow_cm": 30, "wind_ms": 26},
    "함평": {"snow_cm": 40, "wind_ms": 34},
    "합천": {"snow_cm": 22, "wind_ms": 28},
    "해남": {"snow_cm": 22, "wind_ms": 36},
    "홍성": {"snow_cm": 26, "wind_ms": 32},
    "홍천": {"snow_cm": 32, "wind_ms": 24},
    "화성": {"snow_cm": 26, "wind_ms": 30},
    "화순": {"snow_cm": 30, "wind_ms": 32},
    "화천": {"snow_cm": 28, "wind_ms": 36},
    "횡성": {"snow_cm": 34, "wind_ms": 26},
}


def siting_design_load(region_name: str) -> Optional[dict]:
    """행정구역명(자유입력 문자열) → {snow_cm, wind_ms}. 매핑표에 없으면 None을
    반환한다(예외 아님) — 호출부는 None일 때 사용자 수동입력으로 넘겨야 한다.
    케이스의 region 필드는 "강원(춘천)"·"충남 천안(성환읍)"처럼 자유 서술형이라
    정확히 일치하는 키를 먼저 찾고, 없으면 REGION_DESIGN_LOAD의 시군구명이
    region_name에 부분 포함되는지로 찾는다. 단 지명 중복 항목(괄호가 붙은
    "고성(강원)" 등)은 부분매칭 후보에서 제외한다 — 광역 힌트 없는 "고성"만으로는
    어느 지역인지 판단할 근거가 없어(모래 위 자동화 금지) 애매하면 None을 반환한다."""
    if region_name in REGION_DESIGN_LOAD:
        return dict(REGION_DESIGN_LOAD[region_name])
    candidates = [k for k in REGION_DESIGN_LOAD if "(" not in k and k in region_name]
    if len(candidates) == 1:
        return dict(REGION_DESIGN_LOAD[candidates[0]])
    return None


def siting_lookup(region_name: str, form: Optional[str] = None) -> Optional[dict]:
    """지역명 하나로 설계하중 조회(siting_design_load)→규격 후보 필터(select_specs)까지
    잇는 상위 함수(compute 레이어, 새 계산 로직 없음). 지역이 매핑표에 없으면 None을
    그대로 반환한다 — snow_cm/wind_ms를 지어내 select_specs()에 넘기지 않는다."""
    load = siting_design_load(region_name)
    if load is None:
        return None
    sel = select_specs(load["snow_cm"], load["wind_ms"], form)
    return {
        "region_name": region_name,
        "region_snow_cm": load["snow_cm"],
        "region_wind_ms": load["wind_ms"],
        "candidates": sel["candidates"],
        "min_by_form": sel["min_by_form"],
    }


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
    # 2026-07-21 추가(7절 "CAPEX 표본 n=2" 과제) — 스마트팜스펙/이두희/ 원가계산서
    # (Git LFS 포인터 상태였던 걸 사용자 승인 하에 pull, "이두희 천안 20251028.pdf"=
    # "원가계산서_이두희(천안) 20251028.pdf"와 동일 LFS 객체) 53페이지 전량 추출.
    # 문서 자체의 14개 세부공종("1-1.1중골조자재"~"7-1.영세율적용") 합계열을 원문
    # 그대로 대조해 재료비(313,242,961)+직접노무비(104,203,908)+기계경비(6,008,111)
    # 소계와 원단위까지 재현(단, "7-1.영세율적용"=자동모터개폐 10,151,480은 별도
    # 세율 처리로 재료비 소계엔 안 잡히는 것으로 확인 — 14개 항목 합계열 합산
    # 433,606,460을 known_total로 채택, 상세는 레지스트리 source 참고).
    # ⚠️ "5-3.베드설치"(재배베드·코코피트·예인축 등 101,301,410원, 전체의 23.9%)는
    # 9/13개 카테고리 어디에도 안 맞아 unclassified로 남김(사용자 확인, 억지 매핑
    # 안 함) — 우민재·최혁진엔 이 정도 규모 재배시설 항목이 없어 기존 스키마가
    # 애초에 이걸 수용하도록 설계되지 않았다는 뜻. 향후 재배시설 케이스가 더
    # 쌓이면 14번째 카테고리 신설을 검토할 것(이번엔 스키마 확장 안 함).
    # ⚠️ ACTUALS의 기존 이두희 총액(582,455,045원)과 이 원가계산서 최종합계
    # (520,275,969원, 14개 항목합+overhead) 사이 62,179,076원 차이가 미해명 —
    # 어느 쪽이 더 최신/정확한 계약금액인지 원문에서 확정 못 함(7절 참고).
    "이두희": {
        "greenhouse_structure": 173890221,   # 1-1(113,391,900)+1-2(36,986,173)+1-3(17,921,202)+2(5,590,946)
        "auto_opening_system": 98756345,     # 1-4렉피니언식(30,564,619)+3차광예인(20,685,664)+4다겹예인(37,354,582)+7-1자동모터개폐(10,151,480)
        "hvac": 0,                           # 이 견적범위엔 보일러/난방설비 라인 자체가 없음(별도 발주 추정)
        "irrigation_fertigation": 33433898,  # 5-1기계실(9,056,219)+5-2관수(4,286,510)+5-4퇴수(5,091,169)+6-2양액제어(15,000,000)
        "ict_control": 26224586,             # 6-1환경제어시스템 전액
        "electrical": 0,                     # 별도 전기공사 라인 없음(각 공종에 배선 소액 산재, 집계 불가)
    },
}
# 위 6개 항목 외(7~13, unclassified) 미기재 케이스 → capex_major_breakdown()이 0 채움.
# unclassified_direct_cost(qa_safety 잔액) — 원문 총액 재대조용, 별도 기록.
CAPEX_MAJOR_UNCLASSIFIED = {"우민재": 2679227, "최혁진": 0, "이두희": 101301410}  # 이두희=베드설치(5-3)


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
# 설계→시공 연결: RFQ 사양서(구조화 사양표) 생성 + 견적서 정합성 검증
#   (2026-07-18) 사용자 요청: "설계시에는 RFQ 사양서·도면을 만드는 과정,
#   견적시에는 견적서를 사양서·도면과 정합시키는 과정을 상세히 계산".
#   이 프로젝트는 CAD 도구가 아닌 결정론 계산 코어이므로 "도면"은 실제
#   도면 이미지가 아니라 규격코드·치수·설계하중·난방용량을 정리한
#   구조화 사양표로 만든다(사용자 확정, 2026-07-18). 새 계산 로직은
#   추가하지 않고 select_specs·heating_load·greenhouse_total_estimate·
#   structure_only_estimate·capex_major_breakdown·benchmark_check를
#   합성(compute 레이어)만 한다 — 엔진 단일출처 원칙 유지.
# ─────────────────────────────────────────────────────────────
# 필수 공종 스코프 기본값 — CAPEX_MAJOR_EVIDENCE_STATUS에서 "실측(2건)"으로
# 확인된, 우민재·최혁진 두 실측 케이스 모두에 공통으로 존재한 4개 카테고리.
# ict_control/electrical은 "부분실측"(최혁진만 존재)이라 기본 필수에서 제외
# (결과 리포트에는 그대로 표시됨 — 완전성 판정에서만 뺀다).
RFQ_REQUIRED_CATEGORIES_DEFAULT = [
    "greenhouse_structure", "auto_opening_system", "hvac", "irrigation_fertigation",
]


@dataclass
class RfqPackage:
    spec_name: str
    form: str
    width_m: float
    snow_cm: int                  # 채택 규격의 설계기준(공급 스펙)
    wind_ms: int
    region_snow_cm: float         # 입지 실제 하중(참고 — 스펙 대비 여유 확인용)
    region_wind_ms: float
    area_m2: float
    area_py: float
    cover: str
    heating: HeatingResult
    total_estimate_a_won: Optional[float]   # 방법A(온실전체 개산, 스펙명에 단가 있을 때만)
    total_estimate_b_won: float             # 방법B(골조단독)
    benchmark_band_won_m2: tuple
    required_categories: list


def generate_rfq_package(region_snow_cm: float, region_wind_ms: float,
                         area_m2: float, cover: Cover, form: str,
                         t_target: float, t_min: float, fr: float,
                         surface_area_m2: Optional[float] = None,
                         safety: float = 1.1, degree_hours: float = 10098.0,
                         efficiency: float = 0.85, fuel: str = "등유",
                         required_categories: Optional[list] = None) -> RfqPackage:
    """설계 축 함수만 호출해 구조화한 RFQ 사양서(=구조화 사양표, CAD 도면 아님).
    form(연동/단동/광폭)은 판단성 결정이라 필수 인자로 받는다 — 엔진이 임의로
    고르지 않는다. 해당 지역강도를 만족하는 규격이 그 형식에 없으면 예외.
    area_m2는 바닥면적(방법A/B 평단가·벤치마크 기준, render_report.py의
    FarmInput.area_m2와 동일 의미). surface_area_m2는 난방부하 계산용 표면적
    (지붕·측벽 포함, 바닥면적보다 큼) — 미지정 시 area_m2로 근사(단동 등
    표면적≈바닥면적에 가까운 경우만 정확, 연동형은 실측값을 넘기는 것을 권장)."""
    sel = select_specs(region_snow_cm, region_wind_ms, form)
    chosen = sel["min_by_form"].get(form)
    if chosen is None:
        raise ValueError(
            f"'{form}' 형식으로 지역 설계강도(적설{region_snow_cm}cm·풍속{region_wind_ms}m/s)를 "
            f"충족하는 규격이 없다")
    surf = surface_area_m2 if surface_area_m2 is not None else area_m2
    heating = heating_load(surf, cover.value, t_target, t_min, fr, safety,
                           degree_hours, efficiency, fuel, floor_area_m2=area_m2)
    area_py = m2_to_py(area_m2)
    est_a = greenhouse_total_estimate(chosen.name, area_py)
    est_b = structure_only_estimate(area_py)
    band = BENCHMARK_BANDS.get(cover, (115000, 310000))
    req = required_categories if required_categories is not None else \
        list(RFQ_REQUIRED_CATEGORIES_DEFAULT)
    return RfqPackage(chosen.name, chosen.form, chosen.width_m, chosen.snow_cm,
                      chosen.wind_ms, region_snow_cm, region_wind_ms, area_m2,
                      area_py, cover.value, heating, est_a, est_b, band, req)


@dataclass
class ReconciliationCheck:
    name: str
    status: str      # "일치"|"불일치"|"확인요망"|"정상"|"경계"|"경고(밴드이탈)"
    detail: str


@dataclass
class QuoteReconciliation:
    rfq: RfqPackage
    capex: CapexMajorBreakdown
    checks: list
    match_score_pct: float
    overall_status: str


def reconcile_quote(rfq: RfqPackage, quote_categories: dict,
                    quote_direct_cost_total: float,
                    quote_total_with_overhead: float,
                    quote_area_m2: Optional[float] = None,
                    quote_spec_name: Optional[str] = None) -> QuoteReconciliation:
    """견적서를 RFQ 사양서와 4가지로 정합 검증한다(완전성/면적/규격코드/금액밴드).
    quote_direct_cost_total(순공사비=재+노+경)과 quote_total_with_overhead(제경비
    포함 총공사비)를 분리해서 받는다 — 완전성 검사는 전자, 밴드 판정은 후자를
    쓴다. 섞으면 밴드가 왜곡된다(우민재 직접공사비 456,158,140원 vs 총공사비
    557,152,000원처럼 두 값이 실제로 다르다). 새 계산 로직 없음 — 기존
    capex_major_breakdown·benchmark_check 결과를 그대로 판정에 쓴다."""
    checks: list = []

    capex = capex_major_breakdown(quote_categories, quote_direct_cost_total)
    missing = [k for k in rfq.required_categories if capex.items.get(k, 0.0) <= 0.0]
    checks.append(ReconciliationCheck(
        "필수 공종 완전성",
        "일치" if not missing else "불일치",
        "누락 없음" if not missing else f"누락: {', '.join(missing)}"))

    if quote_area_m2 is None:
        checks.append(ReconciliationCheck("면적 정합", "확인요망", "견적서에 면적 미기재"))
    else:
        diff_pct = abs(quote_area_m2 - rfq.area_m2) / rfq.area_m2 * 100
        checks.append(ReconciliationCheck(
            "면적 정합", "일치" if diff_pct <= 2.0 else "불일치",
            f"사양서 {rfq.area_m2}㎡ vs 견적서 {quote_area_m2}㎡ (차이 {diff_pct:.1f}%)"))

    if quote_spec_name is None:
        checks.append(ReconciliationCheck("규격코드 정합", "확인요망", "견적서에 규격코드 미기재"))
    else:
        checks.append(ReconciliationCheck(
            "규격코드 정합", "일치" if quote_spec_name == rfq.spec_name else "불일치",
            f"사양서 {rfq.spec_name} vs 견적서 {quote_spec_name}"))

    bcheck = benchmark_check(quote_total_with_overhead, quote_area_m2 or rfq.area_m2,
                             Cover(rfq.cover))
    checks.append(ReconciliationCheck(
        "총액 단가 밴드", bcheck["status"],
        f"{bcheck['unit_won_m2']:,}원/㎡ (밴드 {bcheck['band'][0]:,}~{bcheck['band'][1]:,})"))

    bad = [c for c in checks if c.status in ("불일치", "경고(밴드이탈)")]
    unresolved = [c for c in checks if c.status == "확인요망"]
    ok_count = len(checks) - len(bad) - len(unresolved) * 0.5
    match_score = round(max(ok_count, 0) / len(checks) * 100, 1)
    if bad:
        overall = f"불일치({len(bad)}건)"
    elif unresolved:
        overall = f"부분정합(확인요망 {len(unresolved)}건)"
    else:
        overall = "정합"

    return QuoteReconciliation(rfq, capex, checks, match_score, overall)


# ─────────────────────────────────────────────────────────────
# 시공발주관리(7단계): 다중 견적 비교 (2026-07-19, Phase F)
#   업체선정은 판단성 영역이라 이 함수는 "누가 이겼다"를 정하지 않는다.
#   reconcile_quote()를 업체별로 반복 호출해 결과를 표로 나란히 정리할 뿐이다
#   (새 계산 로직 없음). 컨설턴트가 표를 보고 최종 선정한다.
# ─────────────────────────────────────────────────────────────
@dataclass
class VendorQuote:
    vendor_name: str
    categories: dict
    direct_cost_total: float
    total_with_overhead: float
    area_m2: Optional[float] = None
    spec_name: Optional[str] = None


@dataclass
class QuoteComparisonRow:
    vendor_name: str
    overall_status: str
    match_score_pct: float
    total_with_overhead_won: float
    unit_won_m2: float


@dataclass
class QuoteComparison:
    rfq: RfqPackage
    rows: list                  # QuoteComparisonRow, 입력 순서 그대로(정렬·순위 없음)
    reconciliations: dict       # vendor_name -> QuoteReconciliation(상세)
    lowest_cost_vendor: Optional[str]        # 참고정보일 뿐, 추천 아님
    highest_match_score_vendor: Optional[str]  # 참고정보일 뿐, 추천 아님


def compare_quotes(rfq: RfqPackage, vendor_quotes: list) -> QuoteComparison:
    """같은 RFQ 사양서에 여러 업체 견적서를 대입해 나란히 비교한다(7단계 업체선정
    지원). reconcile_quote()를 업체별로 그대로 호출할 뿐 새 판정 로직은 없다 —
    '최저가'·'최고점수' 필드는 참고정보로만 노출하고, 어느 쪽이 낫다고 결론짓지
    않는다(업체선정은 판단성 영역, 최종 선택은 컨설턴트 몫)."""
    rows = []
    reconciliations = {}
    for vq in vendor_quotes:
        recon = reconcile_quote(rfq, vq.categories, vq.direct_cost_total,
                                vq.total_with_overhead, vq.area_m2, vq.spec_name)
        reconciliations[vq.vendor_name] = recon
        unit = vq.total_with_overhead / (vq.area_m2 or rfq.area_m2)
        rows.append(QuoteComparisonRow(vq.vendor_name, recon.overall_status,
                                       recon.match_score_pct, vq.total_with_overhead,
                                       round(unit)))

    lowest_cost = min(rows, key=lambda r: r.total_with_overhead_won).vendor_name if rows else None
    highest_score = max(rows, key=lambda r: r.match_score_pct).vendor_name if rows else None
    return QuoteComparison(rfq, rows, reconciliations, lowest_cost, highest_score)


# ─────────────────────────────────────────────────────────────
# 시공발주관리(7단계): 공정표 근거 — 표준 품셈(노무투입량) (2026-07-19, Phase G)
#   출처: 「스마트팜 표준화를 위한 사전설계 및 온실공사 품셈 정립」최종보고서
#   (한국농어촌공사 발주·농어촌연구원×㈜지엘종합건축사사무소 수행, 2021-12,
#   E:\이암허브\...\202201_스마트팜 표준화_품셈.pdf) 제7장(원문 printed
#   p.138~162) — 경량철골유리온실공사 7개 공종(철골공사·온실피복공사·
#   천창개폐장치공사·알루미늄공사·수평스크린공사·측벽스크린공사·행잉거터
#   공사, 57종) + 경량철골비닐온실공사 2개 공종(철골공사(파이프자재)·
#   온실피복공사, 7종) = 64개 세부품목 전량(2026-07-19 원문 이미지 전수
#   대조로 완료 — 제7장 품셈 산정 파트는 이걸로 전체 완료).
#   원문 제3절 말미(printed p.163~164)의 <그림7-18/7-19> 온실공사품셈 활용
#   단가산정 결과(유리 총공사비 3,487,006,776원·비닐 2,172,632,667원+제경비)는
#   이미 TOTAL_PYEONG_PRICE 레지스트리 source에 반영된 '온실품셈' 수치와
#   정확히 일치 — 기존 기록의 교차검증으로 확인됨.
#   품셈 단위: "인"=인·일(사람이 하루 종일 투입될 때를 1로 하는 노무투입량
#   비율), 장비는 hr(시간). 공기(캘린더 일수)는 팀 규모(crew_size)라는
#   시세성/판단성 입력 없이는 계산할 수 없어 이 라운드에서는 인·일 합산까지만
#   한다(공기 추정은 다음 단계).
#   ⚠️ 품목명 단독으로는 공종을 특정할 수 없다 — "모터설치대"(천창개폐장치공사·
#   수평스크린공사)·"체인커플링"(천창개폐장치공사·수평스크린공사)·"턴버클"
#   (철골공사·행잉거터공사)·"스크린개폐모터"(수평스크린공사·측벽스크린공사)가
#   서로 다른 공종에 같은 이름, 다른 값으로 존재한다(원문 자체가 그렇다).
#   그래서 조회는 (공종, 품목명) 조합 키를 쓴다 — 이름만으로 추측해 엉뚱한
#   공종의 값을 돌려주지 않는다.
# ─────────────────────────────────────────────────────────────
@dataclass
class PumsemItem:
    category: str                    # 공종
    name: str                        # 세부 품목명
    unit: str                        # 물량 단위(개소/㎡)
    labor_per_unit: dict             # {직종: 인/단위}
    equipment_hours_per_unit: dict   # {장비규격: hr/단위}


PUMSEM_ITEMS: list[PumsemItem] = [
    # 철골공사(9종, 개소당)
    PumsemItem("철골공사", "스틸돌리", "개소",
               {"철골공": 0.21, "특별인부": 0.07}, {"지게차/5TON": 0.19}),
    PumsemItem("철골공사", "외부기둥", "개소",
               {"철골공": 0.18, "특별인부": 0.06}, {"고소작업대6M": 0.69, "백호0.6TON": 0.17}),
    PumsemItem("철골공사", "내부기둥", "개소",
               {"철골공": 0.16, "특별인부": 0.06}, {"고소작업대6M": 0.61, "지게차/5TON": 0.15}),
    PumsemItem("철골공사", "트러스", "개소",
               {"철골공": 0.14, "특별인부": 0.05}, {"고소작업대6M": 0.53, "지게차/5TON": 0.13}),
    PumsemItem("철골공사", "퍼린", "개소",
               {"철골공": 0.02, "특별인부": 0.003}, {"고소작업대6M": 0.03}),
    PumsemItem("철골공사", "브레싱", "개소",
               {"철골공": 0.02, "특별인부": 0.005}, {"고소작업대6M": 0.05}),
    PumsemItem("철골공사", "커텐받침대", "개소",
               {"철골공": 0.08, "특별인부": 0.03}, {"고소작업대6M": 0.27}),
    PumsemItem("철골공사", "보강대", "개소",
               {"철골공": 0.06, "특별인부": 0.02}, {"고소작업대6M": 0.21, "지게차/5TON": 0.05}),
    PumsemItem("철골공사", "턴버클", "개소",
               {"철골공": 0.01, "특별인부": 0.003}, {"고소작업대6M": 0.03}),
    # 온실피복공사(4종, ㎡당)
    PumsemItem("온실피복공사", "천창유리", "㎡",
               {"유리공": 0.02, "조력공": 0.01}, {"고소작업대13M": 0.05, "지게차/5TON": 0.01}),
    PumsemItem("온실피복공사", "측면강화유리", "㎡",
               {"유리공": 0.01, "조력공": 0.004},
               {"고소작업대6M": 0.06, "고소작업대13M": 0.05, "지게차/5TON": 0.02}),
    PumsemItem("온실피복공사", "천장우레탄판넬", "㎡",
               {"내장공": 0.02, "보통인부": 0.01}, {"고소작업대13M": 0.07, "지게차/5TON": 0.02}),
    PumsemItem("온실피복공사", "샌드위치판넬", "㎡",
               {"내장공": 0.02, "보통인부": 0.01},
               {"고소작업대6M": 0.13, "고소작업대13M": 0.1, "지게차/5TON": 0.03}),
    # 천창개폐장치공사(13종, 개소당)
    PumsemItem("천창개폐장치공사", "천창개폐모터", "개소",
               {"철골공": 0.3, "조력공": 0.25}, {"고소작업대6M": 0.5}),
    PumsemItem("천창개폐장치공사", "궤도센서", "개소",
               {"철골공": 0.13, "조력공": 1}, {"고소작업대6M": 4, "고소작업대13M": 1}),
    PumsemItem("천창개폐장치공사", "클램프", "개소",
               {"철골공": 0.04, "조력공": 0.33}, {"고소작업대6M": 1.33, "고소작업대13M": 0.33}),
    PumsemItem("천창개폐장치공사", "랙드라이브", "개소",
               {"철골공": 0.01, "조력공": 0.4}, {"고소작업대6M": 0.8, "지게차/5TON": 0.1}),
    PumsemItem("천창개폐장치공사", "모터설치대", "개소",
               {"철골공": 0.31, "조력공": 0.9}, {"고소작업대6M": 1.6, "고소작업대13M": 0.9}),
    PumsemItem("천창개폐장치공사", "체인카플링", "개소",
               {"철골공": 0.003, "조력공": 0.03},
               {"고소작업대6M": 0.1, "고소작업대13M": 0.03, "지게차/5TON": 0.03}),
    PumsemItem("천창개폐장치공사", "체인휠", "개소",
               {"철골공": 0.01, "조력공": 0.08},
               {"고소작업대6M": 0.3, "고소작업대13M": 0.08, "지게차/5TON": 0.08}),
    PumsemItem("천창개폐장치공사", "랙", "개소",
               {"철골공": 0.02, "조력공": 0.08}, {"고소작업대6M": 0.2}),
    PumsemItem("천창개폐장치공사", "랙파이프연결구", "개소",
               {"철골공": 0.002, "조력공": 0.01},
               {"고소작업대6M": 0.05, "고소작업대13M": 0.01, "지게차/5TON": 0.01}),
    PumsemItem("천창개폐장치공사", "샤프트가딩클립", "개소",
               {"철골공": 0.01, "조력공": 0.08},
               {"고소작업대6M": 0.3, "고소작업대13M": 0.08, "지게차/5TON": 0.08}),
    PumsemItem("천창개폐장치공사", "구동축", "개소",
               {"철골공": 0.04, "조력공": 0.33},
               {"고소작업대6M": 1.33, "고소작업대13M": 0.33, "지게차/5TON": 0.33}),
    PumsemItem("천창개폐장치공사", "종동파이프", "개소",
               {"철골공": 0.04, "조력공": 0.31},
               {"고소작업대6M": 1.24, "고소작업대13M": 0.31, "지게차/5TON": 0.31}),
    PumsemItem("천창개폐장치공사", "푸시바", "개소",
               {"철골공": 0.01, "조력공": 0.04},
               {"고소작업대6M": 0.18, "고소작업대13M": 0.04, "지게차/5TON": 0.04}),
    # 알루미늄공사(6종, 개소당)
    PumsemItem("알루미늄공사", "거터", "개소",
               {"철골공": 0.04, "특별인부": 0.01},
               {"고소작업대6M": 0.16, "고소작업대13M": 0.04, "지게차/5TON": 0.04}),
    PumsemItem("알루미늄공사", "서까래바", "개소",
               {"철골공": 0.02, "특별인부": 0.003},
               {"고소작업대6M": 0.03, "고소작업대13M": 0.01, "지게차/5TON": 0.01}),
    PumsemItem("알루미늄공사", "용마루바", "개소",
               {"철골공": 0.02, "특별인부": 0.01},
               {"고소작업대6M": 0.09, "고소작업대13M": 0.02, "지게차/5TON": 0.02}),
    PumsemItem("알루미늄공사", "천창", "개소",
               {"철골공": 0.05, "특별인부": 0.02},
               {"고소작업대6M": 0.18, "고소작업대13M": 0.04, "지게차/5TON": 0.04}),
    PumsemItem("알루미늄공사", "마감바", "개소",
               {"철골공": 0.01, "특별인부": 0.002},
               {"고소작업대6M": 0.02, "고소작업대13M": 0.01, "지게차/5TON": 0.01}),
    PumsemItem("알루미늄공사", "선홈통공사", "개소",
               {"철골공": 0.05, "특별인부": 0.02},
               {"고소작업대6M": 0.19, "고소작업대13M": 0.05, "지게차/5TON": 0.05}),
    # 수평스크린공사(13종)
    PumsemItem("수평스크린공사", "스크린개폐모터", "개소",
               {"철골공": 1, "조력공": 0.5}, {"고소작업대6M": 7, "고소작업대13M": 5}),
    PumsemItem("수평스크린공사", "모터설치대", "개소",
               {"철골공": 0.6, "조력공": 0.3}, {"고소작업대6M": 4.2, "고소작업대13M": 3}),
    PumsemItem("수평스크린공사", "체인커플링", "개소",
               {"철골공": 0.03, "조력공": 0.02}, {"고소작업대6M": 0.22, "고소작업대13M": 0.16}),
    PumsemItem("수평스크린공사", "드럼설치", "개소",
               {"철골공": 0.01, "조력공": 0.004}, {"고소작업대6M": 0.05, "고소작업대13M": 0.04}),
    PumsemItem("수평스크린공사", "베어링P/L", "개소",
               {"철골공": 0.02, "조력공": 0.01}, {"고소작업대6M": 0.11, "고소작업대13M": 0.08}),
    PumsemItem("수평스크린공사", "예인로라·가이드로라", "개소",
               {"철근공": 0.005, "조력공": 0.002}, {"고소작업대6M": 0.03, "고소작업대13M": 0.02}),
    PumsemItem("수평스크린공사", "스크린바", "개소",
               {"철골공": 0.003, "조력공": 0.001}, {"고소작업대6M": 0.02, "고소작업대13M": 0.01}),
    PumsemItem("수평스크린공사", "스크린바가스켓", "개소",
               {"철근공": 0.02, "조력공": 0.01}, {"고소작업대6M": 0.14, "고소작업대13M": 0.1}),
    PumsemItem("수평스크린공사", "구동2축", "개소",
               {"철골공": 0.005, "조력공": 0.002}, {"고소작업대6M": 0.03, "고소작업대13M": 0.02}),
    PumsemItem("수평스크린공사", "와이어(예인·코팅·SUS·PVC튜브)", "M",
               {"철골공": 0.001, "조력공": 0.0003}, {"고소작업대6M": 0.004, "고소작업대13M": 0.003}),
    PumsemItem("수평스크린공사", "스크린체인웨이트", "M",
               {"철근공": 0.003, "조력공": 0.002}, {"고소작업대6M": 0.02, "고소작업대13M": 0.02}),
    PumsemItem("수평스크린공사", "포켓설치알루미늄", "개소",
               {"철골공": 0.02, "조력공": 0.01}, {"고소작업대6M": 0.12, "고소작업대13M": 0.08}),
    PumsemItem("수평스크린공사", "스크린", "㎡",
               {"철골공": 0.001, "조력공": 0.001}, {"고소작업대6M": 0.01, "고소작업대13M": 0.01}),
    # 측벽스크린공사(6종, 개소당·와이어스트레이너·스크린클립도 개소당)
    PumsemItem("측벽스크린공사", "스크린개폐모터", "개소",
               {"철골공": 1.33, "조력공": 0.67}, {"고소작업대6M": 5.33}),
    PumsemItem("측벽스크린공사", "가이드레일", "개소",
               {"철골공": 0.44, "조력공": 0.22}, {"고소작업대6M": 1.78}),
    PumsemItem("측벽스크린공사", "권취축", "개소",
               {"철골공": 0.02, "조력공": 0.01}, {"고소작업대6M": 0.08}),
    PumsemItem("측벽스크린공사", "롤업스크린", "㎡",
               {"철골공": 0.006, "조력공": 0.003}, {"고소작업대6M": 0.02}),
    PumsemItem("측벽스크린공사", "와이어스트레이너", "개소",
               {"철골공": 0.08, "조력공": 0.04}, {"고소작업대6M": 0.32}),
    PumsemItem("측벽스크린공사", "스크린클립", "개소",
               {"철골공": 0.006, "조력공": 0.003}, {"고소작업대6M": 0.03}),
    # 행잉거터공사(6종)
    PumsemItem("행잉거터공사", "트러스걸이", "개소",
               {"철골공": 0.004, "조력공": 0.006}, {"고소작업대6M": 0.03}),
    PumsemItem("행잉거터공사", "와이어", "개소",
               {"철골공": 0.004, "조력공": 0.006}, {}),
    PumsemItem("행잉거터공사", "턴버클", "개소",
               {"철골공": 0.004, "조력공": 0.006}, {}),
    PumsemItem("행잉거터공사", "삼각대", "개소",
               {"철근공": 0.013, "조력공": 0.018}, {}),
    PumsemItem("행잉거터공사", "행잉거터", "M",
               {"철골공": 0.002, "보통인부": 0.003}, {}),
    PumsemItem("행잉거터공사", "그라운드커버", "㎡",
               {"보통인부": 0.004}, {}),
    # 경량철골비닐온실공사(제3절, 원문 printed p.160~162) — 유리온실과 구조체계가
    # 달라(파이프 프레임 vs 철골 프레임) 카테고리명을 구분한다("(비닐)" 접미)
    # 철골공사(파이프자재)(5종, 개소당)
    PumsemItem("철골공사(비닐·파이프자재)", "지붕서까래", "개소",
               {"철골공": 0.01, "조력공": 0.003}, {"고소작업대6M": 0.02, "지게차/5TON": 0.01}),
    PumsemItem("철골공사(비닐·파이프자재)", "서까래도리", "개소",
               {"철골공": 0.01, "조력공": 0.003}, {"고소작업대6M": 0.02, "지게차/5TON": 0.01}),
    PumsemItem("철골공사(비닐·파이프자재)", "달대파이프", "개소",
               {"철골공": 0.05, "조력공": 0.02}, {"고소작업대6M": 0.13, "지게차/5TON": 0.06}),
    PumsemItem("철골공사(비닐·파이프자재)", "지붕횡대파이프", "개소",
               {"철골공": 0.005, "조력공": 0.002}, {"고소작업대6M": 0.01, "지게차/5TON": 0.01}),
    PumsemItem("철골공사(비닐·파이프자재)", "측면간살", "개소",
               {"철골공": 0.002, "조력공": 0.001}, {"고소작업대6M": 0.01, "지게차/5TON": 0.003}),
    # 온실피복공사(비닐)(2종, ㎡당)
    PumsemItem("온실피복공사(비닐)", "농업용PO필름(천창및지붕)", "㎡",
               {"철골공": 0.01, "특별인부": 0.004, "보통인부": 0.002}, {"고소작업대6M": 0.01}),
    PumsemItem("온실피복공사(비닐)", "농업용PO필름(측면및방풍벽)", "㎡",
               {"철골공": 0.01, "특별인부": 0.003, "보통인부": 0.002}, {"고소작업대6M": 0.01}),
]

PUMSEM_ITEM_BY_KEY: dict = {(item.category, item.name): item for item in PUMSEM_ITEMS}


def pumsem_labor_days(category: str, item_name: str, quantity: float) -> Optional[dict]:
    """(공종, 품목) 1건의 물량×품셈 인력계수 = 직종별 총 인·일. 품셈표에 없는
    조합(아직 확보 못한 공종·품목, 또는 공종을 잘못 지정)이면 None — 값을
    지어내지 않는다. 품목명만으로 조회하지 않는 이유는 PUMSEM_ITEMS 상단 주석
    참고(동명이의 품목이 공종마다 다른 값으로 존재)."""
    item = PUMSEM_ITEM_BY_KEY.get((category, item_name))
    if item is None:
        return None
    return {
        "category": category, "item_name": item_name, "unit": item.unit,
        "quantity": quantity,
        "labor_days_by_trade": {trade: round(rate * quantity, 3)
                                for trade, rate in item.labor_per_unit.items()},
        "total_labor_days": round(sum(item.labor_per_unit.values()) * quantity, 3),
    }


def pumsem_project_labor_summary(quantities: dict) -> dict:
    """{(공종, 품목명): 물량} → 프로젝트 전체 직종별 총 인·일 + 품목별 상세.
    품셈표에 없는 (공종,품목) 조합은 unmatched로 그대로 노출한다(0으로 채우거나
    감추지 않음 — 근거 없는 값 금지)."""
    details = []
    unmatched = []
    totals_by_trade: dict = {}
    for (category, name), qty in quantities.items():
        r = pumsem_labor_days(category, name, qty)
        if r is None:
            unmatched.append((category, name))
            continue
        details.append(r)
        for trade, days in r["labor_days_by_trade"].items():
            totals_by_trade[trade] = totals_by_trade.get(trade, 0.0) + days
    return {
        "details": details, "unmatched": unmatched,
        "totals_by_trade": {k: round(v, 3) for k, v in totals_by_trade.items()},
        "total_labor_days": round(sum(totals_by_trade.values()), 3),
    }


# ─────────────────────────────────────────────────────────────
# 기술·기자재 선택(3단계)·시공발주관리(7단계): 기자재DB (2026-07-19, Phase H)
#   출처: 스마트팜코리아(smartfarmkorea.net, 농정원=농림수산식품교육문화정보원
#   운영, 농림축산식품부 산하 공공기관, 2016년부터 운영) 기자재정보 DB 스냅샷.
#   E:\이암허브\...\스마트팜코리아_DB(231025)_기자재정보_시공업체리스트_250117.xlsx
#   (2025-01-17 스냅샷) 시트를 그대로 CSV로 변환해 `기자재DB/`에 저장(1,000행
#   이상이라 이 파일에는 박아넣지 않는다 — 값은 CSV 원문 그대로, 계산 없이
#   필터·가격 파싱만 한다). 정책번호-2023-03 「2023 스마트팜 기자재 제조기업
#   현황」(같은 폴더 PDF, 69p)이 같은 DB의 공식 출판물로 확인돼 신뢰도 뒷받침.
#   시공업체 리스트(참고자료 시트)는 원 출처가 대한전문건설협회 도급순위임을
#   DB 자체가 명시 — 재인용 데이터.
# ─────────────────────────────────────────────────────────────
_EQUIPMENT_DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "기자재DB")


def _load_csv_rows(filename: str) -> list:
    """기자재DB/ 폴더의 CSV를 딕셔너리 리스트로 읽는다. 폴더·파일이 없으면
    빈 리스트를 반환(예외 아님) — 원본 스냅샷이 이 리포지토리 밖 폴더에서
    변환된 것이라 없을 수 있다는 걸 감안한다. 헤더 중복(예: 장비정보.csv의
    '모델명'이 두 번 나옴 — 장비 자체 모델명 vs 판매사례 모델명)은 자동으로
    '컬럼명(2)'로 구분해 값이 서로 덮어써지지 않게 한다."""
    path = os.path.join(_EQUIPMENT_DB_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        seen: dict = {}
        cols = []
        for h in header:
            seen[h] = seen.get(h, 0) + 1
            cols.append(h if seen[h] == 1 else f"{h}({seen[h]})")
        return [dict(zip(cols, row)) for row in reader]


def _parse_won(text: Optional[str]) -> Optional[int]:
    """'9,500,000원' 같은 원문 표기를 정수로 변환. 파싱 불가(빈 값·'-' 등)면
    None — 0으로 지어내지 않는다."""
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None


def equipment_lookup(standard_device_name: str) -> list:
    """표준 장치명(예: '환경제어기'·'양액기'·'축산방역기')으로 장비정보.csv를
    검색한다. 새 계산 없음 — 원문 필터만."""
    rows = _load_csv_rows("장비정보.csv")
    return [r for r in rows if r.get("표준 장치명") == standard_device_name]


def equipment_component_prices(equipment_model_name: str) -> dict:
    """장비 모델명으로 필수·선택 구성품과 표준가격(원)을 조회한다. 가격은
    CSV 원문 문자열('9,500,000원')을 정수로 파싱만 한다(창작 없음). 구성품이
    없는 모델명이면 빈 리스트 + 합계 0을 반환(예외 아님)."""
    def _fmt(rows):
        return [{
            "구성품": r.get("구성품"), "장치명": r.get("장치명"),
            "모델명": r.get("모델명"), "사양": r.get("사양"),
            "제조사": r.get("제조사"), "제조국": r.get("제조국"),
            "표준가격_원": _parse_won(r.get("표준 가격(원)")),
        } for r in rows]

    required = _fmt([r for r in _load_csv_rows("장비정보_필수구성품.csv")
                     if r.get("장비 모델명") == equipment_model_name])
    optional = _fmt([r for r in _load_csv_rows("장비정보_선택구성품.csv")
                     if r.get("장비 모델명") == equipment_model_name])
    return {
        "장비모델명": equipment_model_name,
        "필수구성품": required, "선택구성품": optional,
        "필수구성품_합계_원": sum(c["표준가격_원"] or 0 for c in required),
    }


def construction_company_list(region: Optional[str] = None) -> list:
    """온실 시공업체 도급순위 리스트(대한전문건설협회 인용, 스마트팜코리아DB
    재수록). region이 주어지면 소재지에 그 문자열이 포함된 업체만 반환한다
    (부분일치, 판단성 여지 없음 — 업체선정 자체는 컨설턴트 몫)."""
    rows = _load_csv_rows("시공업체_도급순위.csv")
    if region:
        rows = [r for r in rows if region in (r.get("소재지") or "")]
    return [{"상호": r.get("상호"), "소재지": r.get("소재지"), "연락처": r.get("연락처")}
            for r in rows]


# ─────────────────────────────────────────────────────────────
# 정부지원 사업신청 및 승인(6단계): 보조사업 체크리스트 (2026-07-19, Phase I)
#   판단성 영역 — "이 농가가 어느 사업에 해당하는가"·"보조율이 몇 %인가"는
#   공모 회차마다 바뀌고 자동판정할 근거가 없어 계산하지 않는다. 5단계 절차와
#   참고 출처만 구조화해 컨설턴트가 직접 확인·기입하도록 하는 체크리스트다
#   (스마트팜포털 farm.smart.go.kr 안내 수준). 사업유형 이름 목록도 참고용일
#   뿐 보조율은 싣지 않는다 — 근거 없는 값 금지.
#   출처: 스마트팜_견적단계_정리_250418.xlsx '보조금 신청 및 승인' 시트
#   (2026-07-18 검토, 실제 컨설팅 업무흐름 자료로 신뢰 가능 판단 — 통합작업체계
#   문서 2절 참고). 그 시트가 예시로 든 보조율 수치(50%·70%·50~70%)는 공모
#   회차마다 바뀌는 값이라 여기 옮기지 않는다.
# ─────────────────────────────────────────────────────────────
@dataclass
class SubsidyProcedureStep:
    step_no: int
    title: str
    description: str
    reference: str


SUBSIDY_APPLICATION_PROCEDURE: list[SubsidyProcedureStep] = [
    SubsidyProcedureStep(
        1, "사업 대상 확인",
        "농가가 해당 회차 공모의 지원 대상 요건(작목·규모·자격 등)에 맞는지 확인",
        "농림축산식품부·스마트팜 지원센터, 스마트팜포털(farm.smart.go.kr) 공고문"),
    SubsidyProcedureStep(
        2, "서류 준비",
        "사업계획서·농지 증명서·예산안·설계도서 등 공모 요강이 요구하는 구비서류 준비",
        "해당 회차 정부지원사업 지침서·지자체 제출 서식"),
    SubsidyProcedureStep(
        3, "신청서 제출",
        "지자체 또는 농림축산식품부 포털을 통해 신청 접수",
        "스마트팜포털(farm.smart.go.kr)"),
    SubsidyProcedureStep(
        4, "심사 및 현장평가",
        "심사위원 서면·현장 평가, 필요 시 보완 요구 대응",
        "지역 농업기술센터, 해당 회차 심사 체크리스트"),
    SubsidyProcedureStep(
        5, "보조금 승인 및 계약",
        "최종 승인 후 사업비 집행 계약 체결, 보조금 교부 결정",
        "보조금관리시스템(e나라도움), 농협 스마트팜팀 등 사업 주관기관"),
]

# 사업유형 이름만 참고용으로 나열 — 보조율·자격요건은 공모 회차마다 바뀌므로
# 값을 고정하지 않는다(자동판정 금지). 신청 시 반드시 최신 공고문 확인.
SUBSIDY_PROGRAM_TYPES_REFERENCE: list[str] = [
    "스마트팜 시설현대화사업", "청년농업인 스마트팜 종합자금 지원사업",
    "스마트팜 혁신밸리 임대형 스마트팜", "첨단온실신축지원사업",
]


def subsidy_application_checklist() -> list:
    """6단계(정부지원 사업신청 및 승인) 체크리스트 — 계산·자동판정 없음.
    5단계 절차를 구조화해 반환하고, 각 항목의 '상태'는 항상 '확인요망'으로
    시작한다(컨설턴트가 실제로 확인한 뒤 채워야 함 — 엔진이 대신 판정하지
    않는다)."""
    return [
        {"단계": s.step_no, "제목": s.title, "설명": s.description,
         "참고자료": s.reference, "상태": "확인요망"}
        for s in SUBSIDY_APPLICATION_PROCEDURE
    ]


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
# 경제성 OPEX: 항목 분해 (2026-07-16 제안값 → 2026-07-21 확정, Step3/P0-d 완료)
#   원문 CSV 확보 완료: 농촌진흥청 「농산물소득분석 조사입력항목코드_20201015」
#   (공공데이터포털 data.go.kr ID 15069669), 사용자가 직접 다운로드해
#   `소득분석DB/농촌진흥청_농산물소득분석 조사입력항목코드_20201015.csv`에 원본 보존
#   (CP949/EUC-KR 인코딩, 1,213행). 열어보니 이 CSV는 OPEX 항목명 15개짜리 단순
#   목록이 아니라 농산물소득조사 시스템 전체의 코드 테이블(코드타입 A~V, 축산·
#   양잠·미곡 포함 전작목 공통)이었다 — "직접경비/간접경비"에 해당하는 부분은
#   코드타입 Q("농진청_홈페이지_소득분석항목코드") 안의 경영비(3010000)·생산비
#   (3000000) 계열 669개 행 중 일부다.
#   아래 목록은 그 669개 행에서 **시설원예(스마트팜 온실) 관련 항목만 큐레이션**한
#   것이다 — 이 선별 자체는 원문이 태그해준 게 아니라 에이전트가 항목명으로 판단한
#   것이므로(축산·양잠·미곡 전용 항목인 가축상각비·사료비·도정료·잠실잠구비·
#   종계비·종축비·탈곡료 등 다수 제외), 값(코드·항목명)은 원문 그대로이나 **선별
#   기준은 검토 대상**이다. 원문에 같은 이름이 서로 다른 코드로 중복 등장하는 경우
#   (위탁영농비=3010005/3010125, 차입금이자=3010004/3010147)는 상위(경영비 직속)
#   코드를 채택하고 하위(중간재비 계열) 중복은 뺐다. "수리비"는 원문에 水利(용수
#   요금)와 修理(수선비) 두 개념이 같은 한글 표기·다른 코드로 존재해 혼동 방지를
#   위해 둘 다 살려뒀다(3010118/3010119) — 기존 제안값의 "수리비(용수)"·"수선비"
#   추정이 우연히 방향은 맞았음을 확인. "광열동력비"(3010104)와 "수도광열비"
#   (3010117)의 실질적 중복 여부는 원문에 정의 문서가 없어 [확인요망]으로 남긴다.
#   CSV 로더는 필요 시 `_load_income_item_rows()`로 원본을 재조회할 수 있으나,
#   항목 수가 적어(25개) PUMSEM_ITEMS와 같은 방식으로 코드에 직접 전사했다.
#   주의: `스마트팜스펙/`의 원가계산서·공내역서는 전부 CAPEX(시공비) 문서이고
#   이 OPEX(운영비, 매년 반복되는 종묘·비료·농약·에너지·인건비)와는 다른
#   자료다 — 혼동해서 재사용하지 않는다.
# ─────────────────────────────────────────────────────────────
@dataclass
class OpexItemCode:
    category: str  # "직접경비" | "간접경비"
    name: str       # 농진청 공식 항목명(원문 그대로)
    code: str       # 농진청 공식 코드(Q타입, 원문 그대로)


OPEX_ITEM_CATEGORIES = [
    # 직접경비(경영비 중 중간재비 계열, 시설원예 관련 항목만 큐레이션)
    OpexItemCode("직접경비", "종묘비", "030101A0"),
    OpexItemCode("직접경비", "무기질비료비", "3010112"),
    OpexItemCode("직접경비", "유기질비료비", "3010126"),
    OpexItemCode("직접경비", "농약비", "3010107"),
    OpexItemCode("직접경비", "광열동력비", "3010104"),
    OpexItemCode("직접경비", "수도광열비", "3010117"),
    OpexItemCode("직접경비", "소농구비", "3010116"),
    OpexItemCode("직접경비", "대농구상각비", "3010109"),
    OpexItemCode("직접경비", "대농구수리임차료", "3010110"),
    OpexItemCode("직접경비", "영농시설상각비", "3010122"),
    OpexItemCode("직접경비", "영농시설비", "3010121"),
    OpexItemCode("직접경비", "영농시설수리.임차료", "3010123"),
    OpexItemCode("직접경비", "수리(水利)비", "3010118"),
    OpexItemCode("직접경비", "수리(修理)비", "3010119"),
    OpexItemCode("직접경비", "제재료비", "3010131"),
    OpexItemCode("직접경비", "주재료비", "3010144"),
    OpexItemCode("직접경비", "위탁영농비", "3010005"),
    OpexItemCode("직접경비", "잡비", "3010130"),
    # 간접경비(경영비 상위·생산비 계열)
    OpexItemCode("간접경비", "임차료", "3010001"),
    OpexItemCode("간접경비", "고용노력비", "030100A0"),
    OpexItemCode("간접경비", "차입금이자", "3010004"),
    OpexItemCode("간접경비", "자가노력비", "030000A0"),
    OpexItemCode("간접경비", "유동자본이자", "3000006"),
    OpexItemCode("간접경비", "고정자본이자", "3000007"),
    OpexItemCode("간접경비", "토지자본이자(지대)", "3000008"),
]

_INCOME_ITEM_DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "소득분석DB")


def _load_income_item_rows() -> list:
    """소득분석DB/ 폴더의 농진청 조사입력항목코드 원문 CSV(CP949)를 딕셔너리
    리스트로 읽는다. 폴더·파일이 없으면 빈 리스트 반환(예외 아님). OPEX_ITEM_
    CATEGORIES는 이 원문에서 큐레이션한 결과를 코드에 직접 전사해둔 것이라
    평소엔 이 함수가 필요 없고, 큐레이션 기준을 재검토하거나 축산/기타 작목
    항목까지 원문 그대로 확인하고 싶을 때만 쓴다."""
    path = os.path.join(_INCOME_ITEM_DB_DIR,
                        "농촌진흥청_농산물소득분석 조사입력항목코드_20201015.csv")
    if not os.path.exists(path):
        return []
    with open(path, encoding="cp949", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        return [dict(zip(header, row)) for row in reader]


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


@dataclass
class OperatingBreakeven:
    breakeven_revenue_won: float
    breakeven_kg: float


def operating_breakeven(opex: float, price_won_per_kg: float) -> OperatingBreakeven:
    """영업 손익분기(2026-07-21, 컨설팅 리포트 4섹션용) — CAPEX 회수(payback_years,
    finance()가 이미 계산)와는 별개로, '그 해 매출이 OPEX를 커버하는 지점'만 본다.
    손익분기 매출 = opex(매출-OPEX=0이 되는 지점이므로), 손익분기 생산량 =
    opex/price_won_per_kg. 새 데이터 없이 기존 두 입력만으로 구하는 순수 계산이다."""
    if price_won_per_kg <= 0:
        raise ValueError("price_won_per_kg는 0보다 커야 한다")
    return OperatingBreakeven(opex, opex / price_won_per_kg)


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
