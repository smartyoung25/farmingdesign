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
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# 평→㎡ 환산 (1평 = 400/121 ㎡ = 3.3057851…의 소수 넷째 자리 반올림)
# ✅ 근거 정리(2026-08-20 73차): 척관법 정의 1척 = 10/33 m에서
#   1평 = 6척 × 6척 = 36 × (10/33)² = 3600/1089 = **400/121 ㎡**로 확정 도출된다.
#   ⚠️ 두 전제(1척=10/33m, 1평=6척 사방)의 1차 법령 원문은 미확보다[확인요망, 17회차 F3] —
#   1902년 도량형규칙 계열이라는 것이 통설이고, 1간=20/11m 경로로도 같은 값이 나온다
#   (6×10/33 = 20/11 검산 일치). 값 자체는 두 전제에서 산술적으로 확정된다.
#   ⚠️ 평은 「계량에 관한 법률」상 **비법정단위**다(면적의 법정단위는 ㎡). 같은 법 제6조②는
#   비법정단위를 **"계량이나 광고에" 사용하는 것**을 금지하고(전면 금지가 아니다 — 17회차 F2),
#   제6조③은 표시요건을 갖추면 **법정단위와 병기**할 수 있게 한다 → 대외 문서의 ㎡ 병기는
#   관행 권고가 아니라 이 조항이 근거다. 2007-07-01은 과태료 단속 개시 시점이고 현행법
#   시행일이 아니다(현행 2014-05-28 전부개정·2015-01-01 시행).
#   ⚠️ status를 '법정기준'이 아닌 '참고기준'으로 둔 이유는 **현행 계량법이 이 환산값을
#   조문으로 규정하지 않기 때문**이다. 다만 1척=10/33m 정의 자체는 1902년(광무 6)
#   도량형규칙 계열에서 왔다고 알려져 있어 "법령과 무관한 값"은 아니다[추정 — 원문 미확보,
#   17회차 F3]. legend 8종에 "수학적 확정값"에 대응하는 등급이 없다.
#   ⚠️ **A-2 평단가 원표와 기준이 다르다**(13회차 F6 → 73차 등재): 원표(내재해형 고시
#   예정공사비)의 평수 열은 33행 전부 면적÷**3.3**으로 재현되는데 여기서는 3.3058을 쓴다.
#   같은 면적에 원표 평단가를 곱하면 약 **-0.175%** 계통 차가 생긴다 — 원표 총금액과
#   원단위로 대조할 때는 기준을 먼저 맞출 것.
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
                 form: Optional[str] = None, crop: Optional[str] = None) -> dict:
    """지역 설계강도를 충족하는 규격 필터 + 형식별 최소사양.
    조건: 설계적설심 >= 지역적설심 AND 설계풍속 >= 지역풍속 (과설계 지양은 최소사양으로).

    crop (P1-11, 2026-08-17 결정 — 상세는 레지스트리 SPEC_TABLE):
      None(기본) = 작물특화형(참외·수박·포도·육묘 등 47종) 제외, 일반형 202종만.
                   작물 미지정 질의에 특정작물 전용 구조(저측고 터널·비가림 등)를
                   "최소사양"으로 내미는 범주 오류 방지 — 격자 측정에서 추천의
                   9.5%가 작물특화형으로 왜곡됨을 확인하고 기본 제외로 확정.
      "수박" 등  = 일반형 + 해당 작물 특화형이 함께 후보 경쟁(타 작물 특화형 제외).
                   특화형이 없는 작물(예: 토마토)은 자연히 일반형만 남는다 — 오류 아님.
      "*"        = 전 249종 포함(구버전 동작 재현용).
    사용 가능한 작물명은 spec_crops() 참고. 어느 경우든 최종 선택은 사용자 몫
    (min_by_form은 참고 정보)."""
    def crop_ok(s):
        if crop == "*":
            return True
        if crop is None:
            return not s.crop
        return (not s.crop) or s.crop == crop
    ok = [s for s in SPEC_TABLE
          if s.snow_cm >= region_snow_cm and s.wind_ms >= region_wind_ms
          and (form is None or s.form == form) and crop_ok(s)]
    # 형식별 최소사양(적설심, 풍속 오름차순 최솟값)
    per_form: dict[str, Spec] = {}
    for s in ok:
        cur = per_form.get(s.form)
        if cur is None or (s.snow_cm, s.wind_ms) < (cur.snow_cm, cur.wind_ms):
            per_form[s.form] = s
    return {"candidates": ok, "min_by_form": per_form}


def spec_crops() -> list[str]:
    """SPEC_TABLE에 작물특화형이 등록된 작물명 목록(P1-11) — select_specs(crop=...)용."""
    return sorted({s.crop for s in SPEC_TABLE if s.crop})


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
# 2026-08-16 (P1-5 해결): 위 [확인요망]을 해소한다 — Diop et al., "Overall Heat
# Transfer Coefficient Measurement of Covering Materials with Thermal Screens
# for Greenhouse using the Hot Box Method", 한국농공학회논문집 54(5), 2012
# (koreascience.or.kr 무료 원문). 핫박스(통제된 소형 챔버) 실내 측정 — PE필름
# 단일피복 Table 2: 저풍속 9.0 W/㎡K · 고풍속 10.4 W/㎡K(×0.86 kcal 환산 →
# 7.7~8.9kcal/㎡·hr·℃). heating_load()의 u_design은 "최대난방부하"(장비 용량
# 설계용, 극한조건 기준)가 목적이므로 두 조건 중 더 가혹한 고풍속값(8.9)을
# 채택한다 — 이현우 등(2013) 현장실측(2.66)은 "2개월 평균" 연료소비 기반이라
# u_period(기간·연료소비 계산용)에는 그대로 남기고, u_design에만 이 핫박스값을
# 적용해 u_design/u_period가 서로 다른 실측 출처를 갖도록 완전히 분리한다.
# 대상은 논문이 다룬 PE필름 계열(필름·불소필름·단동, 기존 "재질무관" 원칙과
# 동일하게 적용)뿐 — "유리"·"필름_이중"은 이 논문 대상이 아니라 손대지 않는다.
# ─────────────────────────────────────────────────────────────
# 🔴 2026-09-13 100차 — u_design / u_period 이원화의 정체 확정 (값 변경 0)
#   사용자 지시 "a 진행". 98·99차가 함께 지목한 지점이다. **이원화는 결함이 아니라
#   "그 재질에 현장 실측이 있느냐"의 반영**임이 드러났다.
#
#   ── 구조 ──
#     재질        u_design            u_period           비
#     필름 계열   5.7 (설계 표준표)   2.66 (현장 실측)   2.143  ← 갈림
#     유리        5.3 (폴백)          5.3                1.000  ← 통일
#     필름_이중   1.82 (폴백)         1.82               1.000  ← 통일
#
#   🔴 **유리가 통일된 것은 "통일이 옳아서"가 아니라 유리에 현장 실측이 없어서다.**
#     필름 계열만 이현우 등(2013) 현장 실측(2개월 평균 **연료소비 역산**) 2.66을
#     갖고 있어 u_period가 따로 선다. 유리는 그 자리에 설계 계열 값(5.3)이 그대로
#     들어가 있다.
#
#   ── 왜 두 값이 맞는가(이원화 유지 근거) ──
#   • 목적이 다르다: u_design은 **장비 용량**(극한 1야간), u_period는 **연료 예측**
#     (재배기간 누적). 원문도 최대난방부하와 기간난방부하를 다른 식으로 준다.
#   • 근거 등급이 다르다: u_period 2.66은 **실제 연료 소비를 역산한 실측**이고,
#     원문 식(3-3-6) Ū = H_T/(A_c·ΔT)는 최대부하에서 기간부하를 **근사**하는 방법이다.
#     실측이 있으면 근사보다 직접적이다 — 그래서 통일(ⓐ안)을 채택하지 않는다.
#
#   ✅ **98차 잔차가 정확히 분해된다**: 필름의 원문/엔진 기간부하 비 1.560은
#       **2.1429(이원화 5.7/2.66) × 0.7278(일조 k/3600) = 1.5595**다.
#       유리는 1.0 × 0.7278 = 0.7278로 98차 관측 0.728과 맞는다.
#       → 98차가 "필름은 이 축만으로 설명되지 않는다"고 남긴 잔차의 정체가 이것이다.
#
#   ⚠️ **[확인요망] 그래서 유리 케이스의 기간난방부하가 과대일 개연성이 생긴다.**
#     필름의 실측/설계 비가 2.66/5.7 = 0.467인데, 유리엔 그런 보정이 없다. 만약
#     유리에도 같은 성격의 현장 실측이 들어오면 연료소비량이 크게 내려갈 수 있다
#     (같은 비를 가정하면 원채원·chuncheon 27,040 → 12,619 L, **−53.3%**).
#     ⚠️**가정이지 근거가 아니다** — 유리 현장 실측이 리포에 없다. 값은 바꾸지 않는다.
#     📌 **원채원이 바로 그 케이스이고 회귀 기준**이다(ROI 14.2%). 유리 실측 확보는
#        작업지시서 14절 B1(원문 미보유 3건)과 같은 성격의 차단이다.
#
#   ── 남은 선택지(엔진이 고르지 않는다) ──
#     ⓐ 통일(u_period ← u_design 5.7): 원문 식 체계와 일치하나 **필름 연료소비량이
#        2.143배**로 뛴다. 실측을 근사로 바꾸는 방향이라 채택하지 않았다.
#     ⓑ **이원화 유지 + 근거 명문화**(100차 채택) — 값 변경 0.
#     ⓒ 조합별 직접 표(`COVER_ASSEMBLIES`)로 두 자리 모두 대체 — 국내 매뉴얼 권고
#        방식이고 82차가 49행을 전사해 뒀다. 케이스 이관은 미완(14절 C5).
# ─────────────────────────────────────────────────────────────
U_VALUE = {"유리": 5.3, "필름": 2.66, "불소필름": 2.66, "단동": 2.66, "필름_이중": 1.82}
# ─────────────────────────────────────────────────────────────
# 🔴 2026-09-13 99차 — ★사용자 결정으로 U_DESIGN 8.9 → 5.7 교체 (사용자 지시 "a 진행")
#   77차부터 이월된 최대 미해결(작업지시서 14절 B2)을 닫는다. 값이 바뀌므로 경위를 남긴다.
#
#   ── 왜 5.7인가: 서로 다투던 두 경로가 같은 값으로 수렴한다 ──
#   ① 20회차 F2 경로 — `온실열손실저감및차단기술연구.pdf` PDF p.12:
#      "PE필름(0.08mm)에 대한 난방부하계수 **5.7 kcal/㎡·h·℃를 기준**으로 하여 … 상대적인
#       열절감율을 산정". 즉 fr이 PE 5.7 기준 상대값이므로 식의 계수 자리엔 5.7이 와야 한다.
#      검산 3건이 닫힌다: 5.7×(1−0.70)=1.71 vs 표11#5 1.7 · 5.7×(1−0.537)=2.64 vs 표10#12 2.6 ·
#      5.7×(1−0.323)=3.86 vs 표10#11 3.9.
#   ② 78차 반론 경로 — 신개념온실 PDF p.334(인쇄 298): "**단일피복의 열관류율**에 각종 보온
#      방법별 열절감율을 고려한 것이 온실의 열관류율이다". 즉 계수 자리엔 5.7이 아니라
#      **그 온실의 단일피복 열관류율**이 온다(78차가 F2를 재검토로 되돌린 근거).
#      → 그런데 그 값을 원문 표에서 읽으면 결국 5.7이다. [표 3-3-30] 「보온피복 방법별
#      야간의 열관류율 비교」 **PDF p.336(인쇄 300)** 원문 직접 확인:
#          1중피복  유리온실 RDA 6.16 / KRC 5.70 / 일본 5.82
#                   플라스틱온실 RDA **6.63** / KRC 6.05 / 일본 6.75
#      단위는 **원문 표 머리에 `(단위: W/m²K)`로 명기돼 있다**(수식 폰트 PUA 글리프라
#      텍스트 추출에선 빈칸으로 나오고, 600dpi 렌더로 판독 — 104차 레드팀 V2).
#      83차의 교차 대조는 그 결론을 독립적으로 뒷받침한 것이다. ×0.86 하면
#          플라스틱 1중피복 RDA 6.63 × 0.86 = **5.7018 → 5.7**
#   🔴 이 표가 엔진과 **같은 축**임을 보증하는 교차 확인: 같은 행의 유리온실 RDA
#      6.16 × 0.86 = **5.2976 ≈ 5.3**으로 `U_VALUE["유리"]=5.3`과 정확히 맞는다.
#      즉 엔진의 유리 값은 이미 이 표에서 온 값이고, 필름 자리에 들어갈 짝이 5.7이다.
#   → **①②가 수렴하므로 77·78차 이견이 닫힌다.** 5.7은 "둘 중 하나를 고른 값"이 아니라
#     **두 경로가 함께 지목하는 값**이다.
#
#   ── 버린 값: 8.9의 정체 ──
#   Diop et al.(2012) 핫박스 PE필름 단일피복 **고풍속 10.4 W/㎡K × 0.86 = 8.94 ≈ 8.9**.
#   측정은 유효하나 **국내 설계 표준표의 1중피복(6.05~6.75 W)보다 1.5배 이상 높은
#   실험실 고풍속 극한**이다. 국내 매뉴얼 체계와 축이 다르다.
#
#   ── ⚠️ 이 교체가 만드는 새 리스크(사용자가 알고 결정한 사항) ──
#   8.9 → 5.7은 **부하가 줄어드는 방향**이다(배율 0.640). 77차는 "과대하면 오버사이징
#   방향이라 작물 리스크는 아니다"라고 적었는데, **그 안전판을 없애는 변경**이다.
#   최대난방부하와 난방기 용량이 36% 줄어들므로 **장비 언더사이징 위험이 새로 생긴다.**
#   완충은 `safety`(기본 1.1)뿐이다. ✅**101차에 그 값의 출처가 확정됐다** — 원문
#   PDF p.389(인쇄 353) "온풍난방의 설치용량은 최대난방부하에 **10%의 안전계수**"
#   (14절 B3 종결). 완충 자체는 근거를 가졌으나 **크기가 −36%를 덮지는 못한다**.
#   📌 실무 주의: 이 엔진의 난방기 용량을 카탈로그와 대조할 때 종전보다 작게 나온다.
#
#   ── 영향 범위(전수 확인) ──
#   • 최대난방부하·난방기 용량만 움직인다. **연료소비량은 불변**이다(u_period=U_VALUE 사용).
#     → OPEX·ROI가 안 움직이고 **원채원 회귀 기준(ROI 14.2%)은 안전하다.**
#   • 유리 케이스(원채원·chuncheon)는 U_DESIGN에 '유리' 키가 없어 **완전 불변**.
#   • 움직이는 것: uminjae 최대난방부하 372,826 → **238,776 kcal/h**(−36.0%),
#     견적비교 2건(군산·논산, 둘 다 필름).
#   • 98차가 남긴 필름 불일치도 줄어든다(원문/엔진 비 2.435 → 1.560, 일조 6.0h 기준).
#     **해소는 아니다** — 나머지 차이는 u_design(5.7) vs u_period(2.66)의 이원화다
#     (100차에 정체 확정: 1.560 = 2.1429 × 0.7278).
#   🔴 **104차 레드팀 F6 — 99차가 "영향 범위 전수 확인"이라 적고 빠뜨린 것**:
#     `verify_heating_vs_actual()`(A-12 실측 대조)의 uminjae 비가 **0.89 → 0.57**로
#     내려갔다(0.89 × 0.6404). 판정 대역이 0.35~1.8로 넓어 뱃지는 '정상'을 유지하지만,
#     **엔진이 가진 유일한 실측 대조 지표**가 크게 움직였는데 기록되지 않았다.
#     101차의 +8.8% 보정을 얹어도 0.57 → **0.62**로 0.89를 회복하지 못한다.
#     📌 **반대 읽기도 있다(양쪽을 다 적는다)**: 유리 케이스는 99차 전후 모두
#       chuncheon 0.57 · wonchaewon 0.41이었다. 99차 이전엔 필름만 0.89로 높았고,
#       이후 세 케이스가 0.57/0.57/0.41로 **서로 가까워졌다** — 이 지표만으로는
#       99차가 틀렸다고 볼 수 없다.
#     ⚠️ **다만 세 케이스 전부 기준의 41~57%다** — A-12 실측 기준(유리 231·필름 180
#       kcal/h·㎡) 자체가 엔진과 계통적으로 어긋나 있을 가능성이 남는다[확인요망].
#       이건 99차가 만든 문제가 아니라 그보다 오래된 문제이고, 대역이 넓어(0.35~1.8)
#       지금까지 드러나지 않았다.
# ─────────────────────────────────────────────────────────────
U_DESIGN = {"필름": 5.7, "불소필름": 5.7, "단동": 5.7}
# 보온비 fr (피복조합) — ⚠️ 2026-07-19 재조사 시점 기록: "이 표는 어떤 함수에서도
# 참조되지 않는 미사용 상수"였다(heating_load()는 fr을 호출부가 직접 숫자로 주입).
# ⚠️ 이 서술은 2026-07-20 curtain 경로 신설 이후 **더 이상 사실이 아니다**(68차
# 레드팀 12회차 F2로 정정): 현재 build_site.py(견적비교 로더)·webapp.py가
# curtain= 인자로 heating_load()를 호출하고 그 안에서 curtain_exposure_ratio()가
# 이 표를 참조하는 **live 경로**다. 값 변경은 curtain 입력이 있는 산출물에
# 즉시 반영되므로 "미사용이라 안전"하다고 읽지 말 것.
# FR_TABLE 자체는 국내 관행 그대로 "열절감률"(값이 클수록 보온이 잘 됨: PO단일
# 0.35 < 다겹보온 0.5 < 이중커튼 0.70[⚠️이 줄의 0.85는 68차 교체 전 값이라
# 2026-09-13 76차에 정정 — 아래 68차 블록이 교체 경위다])을 담고 있어 인용 출처(다겹보온커튼
# 열절감률45% 등)와 방향이 일치한다 — 표 자체는 안 고친다. 문제는 heating_load()의
# 공식(`부하 = 면적×U×ΔT×fr`)이 fr을 *노출비율*(클수록 부하가 커짐, 즉 보온이
# 나쁠수록 커야 함)로 기대한다는 것 — "열절감률"을 그대로 곱하면 이중커튼(최선
# 보온)이 PO단일(커튼 없음)보다 부하가 더 크게 나오는 반전이 생긴다.
# ✅ 방향 수정(2026-07-20): FR_TABLE 값은 그대로 두고, 아래 curtain_exposure_ratio()가
# 열절감률→노출비율(1-절감률) 변환을 전담한다 — heating_load(fr=...)에는 반드시
# FR_TABLE 원값이 아니라 curtain_exposure_ratio()의 반환값을 넣을 것.
# ⚠️ 절감률 자체의 절대값(0.35/0.5/0.85)은 여전히 1차 출처 미확보([확인요망]).
# 2026-08-17 라운드5(P1-9, NIHHS 공식 웹계산기 실측 프로빙 — 상세는 레지스트리):
#   ①NIHHS OpenAPI 활용가이드(v1.0 docx) 정독 결과 KWR(보온비)은 응답 필드이며
#     보온비 계수표는 가이드에도 없음(종전 "사용자 필수입력값" 기록은 오인, 정정).
#   ②웹계산기(nihhs.go.kr farmerUseProgram3) 보온재 16종 프로빙으로 공식 실효
#     절감률 확보(PO피복·전주 기준, 무보온 대비): PE필름 33.6% ≈ 0.35 정합,
#     알루미늄보온스크린 51.8%·다겹보온커튼 56.3% ≈ 0.5 근사,
#     최대조합(다겹+PE필름부직포)도 65.4%에 그침 → **이중커튼 0.85는 공식
#     계산기의 어떤 조합으로도 재현 불가(과대 의심)** — 0.85 사용 시 주의.
#   ③방향성 최종 확증: NIHHS 모델도 보온재가 좋을수록 부하 감소 — FR_TABLE을
#     "열절감률"로 읽는 현행 해석이 공식 계산기와 정합.
# 2026-08-19 68차(사용자 지시 "FR_TABLE 0.85 재조사" → 재조사 후 사용자 결정으로
# 교체): **이중커튼·2중커튼 0.85 → 0.70**. 근거는 농사로(농촌진흥청 공식 포털)
# "스마트온실 관리 및 작물재배 > 스크린 사용 적정 개수" 표 — 유리온실 기준
# 스크린 1장 U6.0(보온력 54%)·**2장 U2.1(보온력 70%)**·3장 U1.5(78%).
#   ✅ 이 표는 내적으로 검증된다(68차 12회차 F1로 논거 정정): 원문이 1장 행에서
#     "에너지 스크린의 U-value는 6"이라 하므로 6은 스크린 자체 U다 — 유리+스크린
#     n장을 직렬 열저항으로 합성해 U_n=1/(1/7+n/6)로 두면 열손실 감소율이
#     1장 53.8%·2장 70.0%·3장 77.8%로 **3행 전부** 표기값(54·70·78%)을 재현한다
#     (2장은 표기 U 2.1과도 정확히 일치). 즉 이 표의 "보온력"이 FR_TABLE의
#     "열절감률"(=열손실 감소율)과 **같은 정의**임을 표 자체가 입증한다.
#     ※ 초판 주석의 "1장만 재현 불가[확인요망]"는 (7−U표기)/7을 전 행에 적용한
#       오독이었다 — 철회. 표 신뢰도는 초판 기록보다 높다.
#       단 1장 값(54%)은 여전히 미채택(스크린 '매수'별 구분이라 FR_TABLE의
#       피복·커튼 '종류'별 키와 범주가 다름).
#   ✅ 교차 검증: 실질 독립 3건이 63~70%로 수렴 — 농사로 70%·NIHHS 계산기
#     최대조합 65.4%(47차 실측)·해외 학술 이중 63%(참고: 에어로겔 다겹커튼
#     66.7~71.2%는 다겹이지 2중 스크린이 아니고, 해외 삼중 70%는 삼중 값이다.
#     초판의 "6종 독립"은 과대 집계 — 12회차 F6 정정). 세 출처의 측정 정의
#     동질성은 미검증이라 "구간의 방향성" 근거이지 소수점 비교 근거는 아니다.
#     **0.85를 지지하는 출처는 국내외 어디에도 없음**이 재확인됐다.
#   📎 0.85 유래 정황[추정]: 리포 내 제품 카탈로그(시설평가/스마트온실 구축
#     가이드라인 p200~206)에서 단일 스크린 보온율은 20~75%인 반면 **차광률은
#     85~86%대가 흔하다**(TEMPA 8672 D "보온72%·차광86%", DTS85(B) "차광 85%") —
#     차광률을 보온율로 옮겨 적었을 가능성. 원문서 A-5 미확보라 확정 불가.
#   📎 **경쟁 가설 — 절감률 단순 가산(2026-09-13 76차, 레드팀 19회차 F3)**:
#     사용자 보유 `(최종)온실 선정 및 비용 견적 프로그램.xlsx` `시설구성내역!L10`이
#     0.85인데 **바로 옆 칸에 구성이 병기돼 있다** — `N10`="보온다겹 0.5",
#     `P10`="PO 0.35". 즉 **0.35+0.5의 단순 가산**이다(직렬 합성이면
#     1-(1-0.35)(1-0.5)=0.675로 현행 0.70과 근사). 차광률 가설의 1차 반례이며,
#     가산의 피가산항이 하필 리포가 NIHHS 실측과 "근사 정합"으로 인정한 0.35·0.5다.
#     ⚠️ 두 가설 중 하나를 확정하지 않는다 — 이 xlsx가 A-5 원문서라는 증거는 없고
#     같은 오류를 독립적으로 저질렀을 수도 있다. 차광률 가설도 삭제하지 않고 병기한다.
#     ⚠️ 이 발견은 현행 0.70을 **반박하지 않고 지지한다**(가산 오류 복원값 0.675 ≈ 0.70).
#     단 독립 곱과 농사로의 직렬 열저항은 서로 다른 모델이고 대상 조합도 다르므로
#     (유리+스크린2장 vs PO필름+보온다겹커튼) "구간의 방향성" 근거일 뿐이다[추정].
#     영향범위 실측·판단 잔여는 근거_난방계수_이견_20260913.md.
#   ⚠️ PO단일 0.35·다겹보온 0.5는 변경하지 않는다(NIHHS 실측 33.6%·56.3%와 근사
#     정합, 47차) — 4키 중 2키만 공공 출처를 확보했으므로 상수 status는
#     '공공기준'이 아니라 **'부분실측'**이고 ref에는 match="partial"을 붙인다
#     (12회차 F3·F4 — 44차 F5 "부분 근거를 exact로 위장 금지" 선례).
#   ⚠️ 사용 시 2가지 더(12회차 F2·F5): ①curtain="이중커튼" 입력 시 노출비율이
#     0.15→0.30이 되어 산정 난방부하가 정확히 2배가 된다(실측 33,375→66,750
#     kcal/h) — 이번 교체로 케이스 값이 안 움직인 것은 견적비교 2건의 curtain이
#     모두 "다겹보온"이어서일 뿐이다. ②이 표는 유리온실(무보온 U=7) 기준이라
#     필름 등 타 피복 적용은 근사이며, 최대난방부하 산정에서 절감률을 밴드 상단
#     으로 잡을수록 장비 언더사이징 방향임에 주의.
#     상세 근거: 근거_농사로_스크린보온력표_20260819.md
FR_TABLE = {"PO단일": 0.35, "다겹보온": 0.5, "이중커튼": 0.70, "2중커튼": 0.70}


def curtain_exposure_ratio(curtain: str) -> float:
    """FR_TABLE의 열절감률(클수록 보온 잘 됨)을 heating_load()의 fr 인자가
    기대하는 노출비율(클수록 부하가 커짐, 즉 보온이 나쁠수록 커야 함)로 변환.
    반환값 = 1 - FR_TABLE[curtain] — 값이 작을수록 보온이 잘 돼 난방부하가
    줄어드는 올바른 방향이 된다. curtain이 FR_TABLE에 없으면 ValueError.

    ✅ 이 변환의 원문 근거(77차): 김평화 p.49 식의 마지막 항이 문자 그대로
    "**(1 - 피복 열절감률)**"이다 — 2026-07-20에 물리적 추론으로 세운 방향 수정이
    원문 자구와 일치함이 사후 확인됐다(heating_load docstring 참고)."""
    if curtain not in FR_TABLE:
        raise ValueError(f"'{curtain}'은 FR_TABLE에 없는 피복조합이다 (선택: {list(FR_TABLE)})")
    return 1 - FR_TABLE[curtain]
# ─────────────────────────────────────────────────────────────
# 피복·보온재 조합별 난방부하계수 (2026-09-13 82차 신설 — 사용자 결정 "ⓒ로 결정")
#   결정 경위: 76~78차 난방 계수 이견의 3안 중 **ⓒ(조합별 계수 직접 조회)**를
#   사용자가 채택했다. 근거는 78차에 확보한 국내 표준 매뉴얼 권고다 —
#   `스마트팜연구DB/에너지절감과생산성향상을위한신개념온실설계및표준화연구.pdf`
#   PDF p.337(인쇄 301): "관류열부하 계산에서는 **보온피복의 열절감율을 포함시킨
#   열관류율**을 **외피복과 보온피복의 조합에 따른 설계자료로 제시**하기로 하였다."
#   즉 `U x (1 - 절감률)` 런타임 곱셈 대신 **조합별 값을 표에서 바로 읽는다**.
#
#   ✅ 출처: `스마트팜연구DB/온실열손실저감및차단기술연구.pdf`
#     (농진청 국가연구개발보고서 — KISTI TRKO202100009930. 78차에 리포 안에서
#      발견됐다. 7절이 오랫동안 "로그인 장벽으로 확보 실패"로 적어 온 그 문서다)
#     PDF p.24(인쇄 18) [표 9] 단일 피복재 9종 · PDF p.25(인쇄 19) [표 10] 단일 보온재 16종 ·
#     p.26 [표 11] 이중 조합 24종 = **49행 전량 전사**.
#     측정: 핫박스(Hotbox) 실측, 외기 -10℃·내부 18~20℃(내외부 온도차 28~30℃),
#     피복재 9종·보온재 16종·이중 24조합·삼중 59조합(p.12).
#
#   ✅ 전사 검산 49/49 통과: 원문이 `열절감율 = (피복재 난방부하계수 - 5.7) x 100 / 5.7`
#     (PE필름 0.08mm = 5.7 kcal 기준)로 정의하므로 `계수 = round(5.7 x (1 - 절감율), 1)`이
#     성립해야 한다 — **49행 전부 일치**. 반대로 `계수 = round(열관류율 x 0.86, 1)`은
#     3행에서 0.1 어긋나는데, 이는 열관류율 열이 소수 1자리로 반올림돼 정밀도를
#     잃은 탓이다(절감율 열이 더 정밀하다). 세 열을 **원문 그대로** 싣고 이 관계를
#     테스트로 고정한다.
#
#   ⚠️ **원문의 재료명 표기가 표마다 다르다** — 표 9·10은 "PE필름(0.08)"·
#     "다겹보온커튼(4겹)", 표 11은 "pe-0.15"·"5겹다겹". 정규화하지 않고 **원문
#     표기를 그대로 키로** 쓴다(전사값 원단위 보존). 사용 가능한 키는
#     `cover_assembly_options()`로 조회한다.
#
#   ⚠️ **유리온실이 없다.** 이 표는 플라스틱온실(PE/PO/EVA) 전용이라
#     `chuncheon`·`wonchaewon`(유리) 케이스는 이 경로로 옮길 수 없다.
#     유리 계열 조합값은 [표 3-3-30](신개념온실 p.336)이 주지만 **원문 단위 표기가
#     깨져 있어 kcal인지 W인지 미확정**이다(78차 ④c) — 별도 차수.
#
#   ⚠️ `FR_TABLE`을 **삭제하지 않았다.** 견적비교 2건이 `curtain="다겹보온"`으로
#     그 경로를 쓰고 있어 지우면 산출물이 깨진다. 두 경로의 값이 어긋나는 것도
#     이미 관측됐다(표 10 다겹보온커튼 4겹 53.7% vs `FR_TABLE["다겹보온"]` 0.5).
#     **어느 조합으로 매핑할지는 판단성**이라 이 차수에서 정하지 않는다 —
#     신규 경로를 정본으로 추가하고 기존 경로는 그대로 둔다(마이그레이션은 별도 결정).
# ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class CoverAssembly:
    layers: tuple        # 구성(원문 표기 그대로). 1중=1개, 2중=2개
    u_w_m2k: float       # 열관류율 (W/m2·℃) — 원문 열 그대로
    coef_kcal: float     # 난방부하계수 (kcal/h·m2·℃) — 원문 열 그대로
    savings_pct: float   # 열절감율 (%) — PE필름(0.08mm) 5.7 기준 상대값
    table: str           # 원문 표 번호


# 열절감율 산정 기준값(원문 p.12) — 표 9 #1 PE필름(0.08)의 난방부하계수와 같다.
# 별도 상수로 두지 않고 표에서 찾아 쓴다(중복 선언 방지) — `_pe_baseline_coef()`.
COVER_ASSEMBLIES: list = [
    CoverAssembly(("PE필름(0.08)",), 6.6, 5.7, 0.0, "표9"),
    CoverAssembly(("PE필름(0.10)",), 6.2, 5.3, 7.0, "표9"),
    CoverAssembly(("PE필름(0.15)",), 5.6, 4.8, 15.8, "표9"),
    CoverAssembly(("PO필름(0.08)",), 6.0, 5.2, 8.8, "표9"),
    CoverAssembly(("PO필름(0.10)",), 5.2, 4.5, 21.1, "표9"),
    CoverAssembly(("PO필름(0.15)",), 5.1, 4.4, 22.8, "표9"),
    CoverAssembly(("EVA필름(0.10)",), 6.2, 5.3, 7.0, "표9"),
    CoverAssembly(("EVA필름(0.08)",), 6.4, 5.5, 3.5, "표9"),
    CoverAssembly(("EVA필름(0.05)",), 6.6, 5.7, 0.0, "표9"),
    CoverAssembly(("부직포 80g",), 5.7, 4.9, 13.6, "표10"),
    CoverAssembly(("직조필름(0.15mm)",), 6.0, 5.2, 9.2, "표10"),
    CoverAssembly(("옥스포드 300",), 5.6, 4.8, 15.6, "표10"),
    CoverAssembly(("옥스포드 600",), 5.7, 4.9, 13.8, "표10"),
    CoverAssembly(("AL스크린(차광율10%)",), 5.9, 5.1, 10.4, "표10"),
    CoverAssembly(("AL스크린(차광율55%)",), 5.5, 4.7, 16.7, "표10"),
    CoverAssembly(("AL스크린(차광율75%)",), 5.4, 4.7, 18.1, "표10"),
    CoverAssembly(("AL스크린(차광율85%)",), 5.4, 4.6, 18.8, "표10"),
    CoverAssembly(("AL스크린(차광율95%)",), 5.2, 4.5, 21.3, "표10"),
    CoverAssembly(("AL스크린(차광율100%)",), 4.8, 4.2, 27.0, "표10"),
    CoverAssembly(("다겹보온커튼(3겹)",), 4.5, 3.9, 32.3, "표10"),
    CoverAssembly(("다겹보온커튼(4겹)",), 3.1, 2.6, 53.7, "표10"),
    CoverAssembly(("다겹보온커튼(5겹)",), 2.7, 2.3, 59.6, "표10"),
    CoverAssembly(("다겹보온커튼(외피)",), 2.0, 1.7, 70.2, "표10"),
    CoverAssembly(("다겹보온커튼(AL+3겹)",), 2.4, 2.1, 63.2, "표10"),
    CoverAssembly(("고기능다겹보온커튼",), 3.2, 2.8, 51.7, "표10"),
    CoverAssembly(("pe-0.15", "pe-0.10",), 3.24, 2.8, 51.0, "표11"),
    CoverAssembly(("pe-0.10", "pe-0.10",), 3.47, 3.0, 47.0, "표11"),
    CoverAssembly(("po-0.15", "po-0.10",), 2.88, 2.5, 56.0, "표11"),
    CoverAssembly(("po-0.10", "po-0.10",), 2.92, 2.5, 56.0, "표11"),
    CoverAssembly(("pe-0.15", "5겹다겹",), 1.96, 1.7, 70.0, "표11"),
    CoverAssembly(("pe-0.15", "3겹다겹",), 2.87, 2.5, 56.0, "표11"),
    CoverAssembly(("pe-0.15", "4겹알루미늄",), 1.8, 1.6, 72.0, "표11"),
    CoverAssembly(("pe-0.15", "고기능다겹",), 2.41, 2.1, 63.0, "표11"),
    CoverAssembly(("pe-0.15", "알루미늄스크린(차광55%)",), 2.93, 2.5, 56.0, "표11"),
    CoverAssembly(("pe-0.10", "5겹다겹",), 1.87, 1.6, 72.0, "표11"),
    CoverAssembly(("pe-0.10", "3겹다겹",), 2.9, 2.5, 56.0, "표11"),
    CoverAssembly(("pe-0.10", "4겹알루미늄",), 1.82, 1.6, 72.0, "표11"),
    CoverAssembly(("pe-0.10", "고기능다겹",), 2.41, 2.1, 63.0, "표11"),
    CoverAssembly(("pe-0.10", "알루미늄스크린(차광55%)",), 2.87, 2.5, 56.0, "표11"),
    CoverAssembly(("po-0.15", "5겹다겹",), 1.84, 1.6, 72.0, "표11"),
    CoverAssembly(("po-0.15", "3겹다겹",), 2.79, 2.4, 58.0, "표11"),
    CoverAssembly(("po-0.15", "4겹알루미늄",), 1.71, 1.5, 74.0, "표11"),
    CoverAssembly(("po-0.15", "고기능다겹",), 2.28, 2.0, 65.0, "표11"),
    CoverAssembly(("po-0.15", "알루미늄스크린(차광55%)",), 2.8, 2.4, 58.0, "표11"),
    CoverAssembly(("po-0.10", "5겹다겹",), 1.67, 1.4, 75.0, "표11"),
    CoverAssembly(("po-0.10", "3겹다겹",), 2.59, 2.2, 61.0, "표11"),
    CoverAssembly(("po-0.10", "4겹알루미늄",), 1.73, 1.5, 74.0, "표11"),
    CoverAssembly(("po-0.10", "고기능다겹",), 2.28, 2.0, 65.0, "표11"),
    CoverAssembly(("po-0.10", "알루미늄스크린(차광55%)",), 2.84, 2.4, 58.0, "표11"),
]


def _pe_baseline_coef() -> float:
    """열절감율 산정 기준(PE필름 0.08mm)의 난방부하계수를 표에서 찾는다.
    원문 p.12가 5.7 kcal/h·m2·℃로 명시한 값이며, 표 9 #1이 그 행이다."""
    for a in COVER_ASSEMBLIES:
        if a.layers == ("PE필름(0.08)",):
            return a.coef_kcal
    raise RuntimeError("표 9 #1(PE필름 0.08) 행이 표에서 사라졌다 — 전사 확인 필요")


def cover_assembly_options(n_layers: Optional[int] = None) -> list:
    """조회 가능한 조합 키 목록. n_layers를 주면 그 층수만.
    원문 표기가 표마다 달라(표9·10 vs 표11) 사용 전에 이 목록으로 확인할 것."""
    return [a.layers for a in COVER_ASSEMBLIES
            if n_layers is None or len(a.layers) == n_layers]


def cover_assembly_lookup(layers) -> Optional[CoverAssembly]:
    """피복·보온재 조합 -> 실측 난방부하계수. 원문 표기 **정확 일치**만 찾는다.

    정규화(대소문자·공백·표기 통일)를 하지 않는 이유: 원문 재료명이 표마다 다르게
    적혀 있는데 임의로 통일하면 어느 행을 집었는지 추적할 수 없게 된다. 표기가
    헷갈리면 `cover_assembly_options()`로 실제 키를 확인할 것.

    찾지 못하면 None — 가까운 조합을 대신 돌려주지 않는다(근거 없는 값 금지).
    """
    key = tuple(layers) if not isinstance(layers, str) else (layers,)
    for a in COVER_ASSEMBLIES:
        if a.layers == key:
            return a
    return None


# 연료 순발열량 (kcal/단위) - A-5
# ✅ 원출처 확정·현행화(2026-08-19 70차, 사용자 지시 "FUEL_LHV 재조사" → 결정으로 교체):
#   정체는 **에너지법 시행규칙 [별표] 에너지열량 환산기준(제5조제1항 관련)**이었다 —
#   재조사 전 6종이 <개정 2017. 12. 28.> 판 순발열량 열과 **전량 원단위 일치**해 출처가
#   확정됐고(미검증 → 법정기준), 현행 <개정 2022. 11. 21.> 판으로 갱신했다.
#   원문 PDF 리포 보존: 법령_에너지법시행규칙_별표_에너지열량환산기준_20221121.pdf
#   갱신 내역(2017판 → 2022판): 등유 8,170→8,150 · 경유 8,410→8,420 · B-C유 9,360→9,390 ·
#   LPG프로판 11,060→11,040 · LNG 11,800(불변).
#   ⚠️ **전기 2,290 → 860 정정(성격 오류)**: 같은 별표 **비고 5**가
#   "최종 에너지사용자가 사용하는 전력량 값을 열량 값으로 환산할 경우에는 **1kWh=860kcal**를
#   적용한다"고 명시한다. 이 상수의 사용처(fuel_use = 기간부하 ÷ (LHV×효율) = 사용자가 실제
#   쓸 전력량)는 비고 5에 해당하므로 860이 맞다 — 물리적으로도 1kWh=3.6MJ=860kcal이며
#   비고 6(1cal=4.1868J)만으로 독립 도출된다(3.6e6/4.1868/1000≈860).
#   ⚠️ 14회차 F2로 단정 격하: 별표 본문의 전기 행(발전기준 2,130·소비기준 2,290)이 국가
#   에너지통계용 1차에너지 계수라는 것은 **[추정]**이다 — 별표 비고 1~7 어디에도 두 기준의
#   정의가 없다(860/2,290=37.6%·860/2,130=40.4%가 화력 발전효율대라는 정황뿐).
#   ⚠️ 14회차 F1(중요): 2,290을 쓰면 필요 전력량이 2.66배 과소 산출"됐다"는 성립하지 않는다 —
#   fuel 인자는 현재 어떤 live 경로에서도 지정되지 않고(render_report는 heating_load 반환에서
#   fuel_consumption을 버리고, build_site·webapp의 generate_rfq_package 호출에 fuel 인자가
#   없다) 연료소비량은 산출물 HTML에 렌더되지도 않는다. 즉 이 정정의 실효 영향은 **현재 0**이며,
#   fuel 경로를 쓰기 시작할 때부터 효과가 난다(그 인터페이스부터 만들어야 한다).
#   ⚠️ 단위가 연료마다 다르다: 등유·경유·B-C유=L, LNG·LPG프로판=kg, 전기=kWh —
#   fuel_use 결과를 "리터"로 단정 표기하지 말 것.
#   ⚠️ 커버리지 한계(14회차 F5): 별표 30여 행 중 **6종만** 담았다. 특히 **도시가스(LNG)
#   9,190 kcal/Nm3**이 없어, 배관 도시가스(Nm3 과금)를 여기 "LNG"(kg 기준 11,800)로 넘기면
#   소비량이 약 1.28배 과소 나온다 — 필요해지면 별표에서 추가할 것(부탄 10,880/kg·
#   부생연료유1호 8,310/L·2호 9,010/L도 미등록).
#   상세: 근거_에너지법_열량환산기준_20260819.md
FUEL_LHV = {"등유": 8150, "경유": 8420, "B-C유": 9390,
            "LPG프로판": 11040, "LNG": 11800, "전기": 860}

# 연료 총발열량 (kcal/단위) - 같은 별표의 총발열량 열
# 📌 신설·보류(2026-08-20 72차): 14회차 F4의 "efficiency의 발열량 기준 미상" 문제를
#   풀려고 도입했다. 72차 중반에 fuel_use를 이 표와 짝짓도록 바꿨으나 **레드팀 16회차
#   F1의 반박으로 계산을 순발열량 조합으로 되돌렸다**(사용자 결정). 반박 요지:
#   ①근거로 삼은 산업부 고시「고효율에너지기자재 보급촉진에 관한 규정」의 "열효율 표시는
#   총발열량을 기준으로" 각주는 **가스식 응축(콘덴싱) 보일러 표**에 붙은 것이고, 이 엔진의
#   대상은 리포 원출처가 명시하듯 **등유 온풍난방기**(비응축)다 — 범주를 넘은 일반화였다.
#   ②물리적 개연성이 반대다: 0.85가 총발열량 기준이면 순발열량 환산 **91.2%**(비응축
#   기기가 배기 현열손실 8.8% 이내여야 성립 — 도달 난이), 순발열량 기준이면 총발열량
#   환산 **79.3%**(비응축 통상 대역).
#   ⚠️ **따라서 이 상수는 현재 계산에 쓰이지 않는다** — 값 자체는 별표 원문 전사라 정확하고,
#   0.85의 기준이 확정되면 곧바로 쓸 수 있도록 남겨 둔다. 두 조합의 차이는 등유 기준
#   7.24%(8,740/8,150). 미사용 상태는 테스트로 고정한다(12회차 F2 교훈 — "미사용"이라는
#   단정은 코드로 확인돼야 한다).
#   ⚠️ 전기는 연소가 없어 총·순 구분이 성립하지 않는다 — 별표도 전기 행의 두 값이
#   동일하다. FUEL_LHV와 같은 860(비고 5, 최종 사용자 환산)을 그대로 둔다.
#   출처: 에너지법 시행규칙 [별표] 에너지열량 환산기준 <개정 2022.11.21.> 총발열량 열
#   (법령_에너지법시행규칙_별표_에너지열량환산기준_20221121.pdf, 70차 확보)
FUEL_HHV = {"등유": 8740, "경유": 9020, "B-C유": 9980,
            "LPG프로판": 12000, "LNG": 13080, "전기": 860}

# 난방 계산 기본값 3종 — 72차에 함수 기본인자에서 모듈 상수로 승격
# ✅ 승격 이유(2026-08-20 72차): 셋 다 `heating_load()` 시그니처에 리터럴로만 있어
#   레지스트리에 등재되지 않았고, 그래서 대조가능성 감사 게이트의 검사 대상에서 통째로
#   빠져 있었다(71차 "미검증 0건"은 레지스트리 안쪽만의 이야기였다). 값을 바꾸지 않고
#   자리만 옮겨 근거 표기 체계 안으로 들여왔다.
# ⚠️ 세 값 모두 원출처 미확보 — 아래 status는 레지스트리에 정직하게 기재했다.
HEATING_EFFICIENCY_DEFAULT = 0.85   # 난방기 열효율 [확인요망] — 원출처 미상, HHV 기준 가정
DEGREE_HOURS_DEFAULT = 10098.0      # 난방 디그리아워 [추정] — A-5 예시값(지역 실측 아님)
HEATING_SAFETY_FACTOR = 1.1         # 온풍난방 설치용량 안전계수 10% — 101차 원문 확정
#   출처: 신개념온실 PDF p.389(인쇄 353) "온풍난방의 설치용량은 최대난방부하에 10%의
#   안전계수를 적용" + PDF p.377(인쇄 341) "난방기 용량 산정 시 0.1∼0.3의 안전계수".
#   이 엔진 대상은 등유 온풍난방기(16회차 F1)이므로 1.1이 맞다. 방식별 값은
#   HEATING_SAFETY_FACTOR_BY_METHOD 참조(온수난방은 1.2~1.3).


@dataclass
class HeatingResult:
    max_load_kcal_h: float       # 최대난방부하
    load_per_m2: float           # 면적당 부하
    heater_capacity_kcal_h: float
    fuel_consumption: float      # 연료소비량(단위)
    fuel_unit_lhv: float


def heating_load(surface_area_m2: float, cover: str, t_target: float,
                 t_min: float, fr: Optional[float] = None,
                 safety: float = HEATING_SAFETY_FACTOR,
                 degree_hours: float = DEGREE_HOURS_DEFAULT,
                 efficiency: float = HEATING_EFFICIENCY_DEFAULT,
                 fuel: str = "등유", floor_area_m2: Optional[float] = None,
                 u_design: Optional[float] = None, u_period: Optional[float] = None,
                 curtain: Optional[str] = None,
                 assembly: Optional[tuple] = None,
                 wind_factor: float = 1.0,
                 sunshine_k: Optional[float] = None) -> HeatingResult:
    """최대난방부하 = Aw × u_design × ΔT × 보온비. 기간(연료소비)부하는 u_period 사용.

    ✅ 식 원출처 자구 확보(2026-09-13 77차, 사용자 지시 "최대부하 산정 커튼 전제 진행"):
      시설평가/20230627_스마트팜 시설의 구조와 이해_김평화(제공).pdf **PDF p.49**(이 자료는 슬라이드 PDF라 인쇄 쪽번호가 없다) —
        "난방부하 = 하우스표면적 * 난방부하계수 * (내부설정온도 - 외부기온)
         * (1 - 피복 열절감률)"
      종전 "(A-5 구조)" 표기는 미확보 문서에 기댄 것이었다 — 이제 식 원문이 있다.
      이 자구로 확정된 것: **fr = (1 - 열절감률) = 노출비율**
      (curtain_exposure_ratio의 방향 변환이 원문과 일치함이 사후 확인됐다).

    🔴 그러나 u_design에 무엇을 넣어야 하는가는 **미해결이고, 현행이 과대일 가능성이
      크다**(2026-09-13 77차 후반, 레드팀 20회차 F2로 판정 역전):
      77차 중반에는 "식이 난방부하계수와 열절감률을 다른 항으로 분리하니 단일피복 U +
      별도 fr은 이중계상이 아니다"라고 결론냈다가 **철회했다.** 식이 두 항을 나눈다는
      관찰은 맞지만 앞 항에 무엇이 들어가는지는 식만으로 정할 수 없고, 그 정의가
      리포 안 다른 문서에 있었다 —
        스마트팜연구DB/온실열손실저감및차단기술연구.pdf **PDF p.12(인쇄 6)**:
          "열관류율 측정값에 **0.86을 곱하여** … **난방부하계수**로 환산 …
           **PE필름(0.08mm)에 대한 난방부하계수 5.7 kcal/m2·h·℃를 기준**으로 하여
           … **상대적인 열절감율**을 식(1)에 의하여 산정"
          "열절감율 = (피복재 난방부하계수 - 5.7(PE필름(0.08mm)난방부하계수)) × 100 / 5.7"
        같은 쪽이 보온재도 "동일 방식·동일 5.7 기준"으로 산정한다고 명시한다.
      즉 **열절감율은 PE 5.7 기준의 상대값**이므로 식의 난방부하계수 자리에는 **5.7**이
      와야 `5.7 × (1 - 열절감율)`이 그 재료의 실제 난방부하계수가 된다. 같은 보고서
      실측표로 검산하면 정확히 닫힌다 — 5.7×(1-0.70)=1.71 vs 표11#5 **1.7** ·
      5.7×(1-0.537)=2.64 vs 표10#12 **2.6** · 5.7×(1-0.323)=3.86 vs 표10#11 **3.9**.
      엔진은 그 자리에 U_DESIGN=8.9를 넣으므로 **8.9/5.7 = 1.56배 과대** 혐의가 있다.
      ⚠️ **값은 바꾸지 않았다 — ★사용자 판단이다**: 8.9(고풍속 극한, 장비 용량 설계용)와
      5.7(실험실 핫박스, 외기 -10℃)은 측정 조건이 다르고, "설계 극한을 쓰겠다"는 것은
      그 자체로 방어 가능한 선택이다. 선택지·검산·영향범위는
      **근거_난방계수_이견_20260913.md 4절 ①**(78차 ★결정 대기).
      📎 같은 김평화 PDF p.53 참고자료 10번 = "최대난방부하 및 연료소비량 계산
        (별도 자료)" — A-5가 그 별도 자료일 가능성[추정].
      ⚠️ 검색 범위(19회차 F2·20회차 F1 교훈 — 범위 없는 유일성 단정 금지): 위 자구가
        "1곳뿐"인 것은 청킹 인덱스 2폴더(스마트팜스펙/·시설평가/ 59,509청크, 단 그
        2폴더 236파일 중 175개만 색인)·리포 루트 PDF 14개·기자재DB/소득분석DB/cases/
        claudeguide·스마트팜연구DB 36개 범위 안에서만이다. 리포 내 .hwp 10·레거시
        .xls 17·이미지 52건은 파서 부재로 미검색이고, 리포 밖 자료는 전부 미검색이다.
    fr/curtain (P1-9, 2026-08-17 — 정확히 하나만 지정):
      fr      = 노출비율(0<fr<=1, 작을수록 보온이 잘 됨). ⚠️ FR_TABLE 원값
                (열절감률, 클수록 보온이 잘 됨)을 넣으면 방향이 반전된다 —
                FR_TABLE 조합을 쓰려면 curtain 인자를 쓸 것.
      curtain = FR_TABLE 피복조합명("PO단일"/"다겹보온"/"이중커튼"/"2중커튼").
                내부에서 curtain_exposure_ratio()로 변환해 방향반전이 구조적으로
                불가능하다."""
    # ── P1-9: fr 방향반전 버그의 시그니처 수준 차단(82차에 assembly 추가로 3분기) ──
    if sum(x is not None for x in (fr, curtain, assembly)) != 1:
        raise ValueError(
            "fr(노출비율) / curtain(FR_TABLE 조합명) / assembly(실측 조합키) 중 "
            "정확히 하나만 지정할 것 — FR_TABLE 원값(열절감률)을 그대로 곱하는 "
            "방향반전 사고를 막기 위한 강제(P1-9). 실측 조합값을 쓰려면 "
            "assembly=('pe-0.15','5겹다겹') 식으로 넘겨라(cover_assembly_options 참고)")
    if assembly is not None:
        # 82차(사용자 결정 ⓒ): 조합별 실측 난방부하계수를 직접 쓴다.
        # 이 계수에는 **보온 효과가 이미 포함**돼 있으므로 절감률을 또 곱하지
        # 않는다(fr=1.0) — 국내 표준 매뉴얼이 권고하는 구조다(신개념온실 p.337).
        if u_design is not None or u_period is not None:
            raise ValueError(
                "assembly와 u_design/u_period를 함께 줄 수 없다 — 조합 계수에 "
                "보온 효과가 이미 포함돼 있어 이중 지정이 된다")
        a = cover_assembly_lookup(assembly)
        if a is None:
            raise ValueError(
                f"{tuple(assembly)!r}은 COVER_ASSEMBLIES에 없는 조합이다 — "
                f"원문 표기가 표마다 다르니 cover_assembly_options()로 실제 키를 "
                f"확인할 것(가까운 조합으로 대신 계산하지 않는다)")
        u_design = u_period = a.coef_kcal
        fr = 1.0
    elif curtain is not None:
        fr = curtain_exposure_ratio(curtain)
    if not (0 < fr <= 1):
        raise ValueError(f"fr(노출비율)은 0<fr<=1 범위여야 한다(입력: {fr})")
    u_d = u_design if u_design is not None else U_DESIGN.get(cover, U_VALUE.get(cover, 5.7))
    u_p = u_period if u_period is not None else U_VALUE.get(cover, 5.7)
    dt = t_target - t_min
    # ── 풍속보정계수 f_w (2026-09-13 96차 신설 — 사용자 지시 "a 진행") ──
    #   원문 식(3-3-1): 최대난방부하 = (관류+틈새+지중) × **풍속보정계수**.
    #   엔진은 3성분 중 관류만 계산하므로(84차 기록) 그 범위 안에서 f_w를 곱한다.
    #   값은 [표 3-3-35] WIND_CORRECTION_FACTOR 조회값만 받는다(임의 실수 거부)
    #   — 83차부터의 "근거 없는 값 금지"를 시그니처 수준에서 지킨다.
    #
    #   ✅ **safety(1.1)와의 이중계상이 아님을 원문으로 확정했다**(96차). 83차가
    #   "HEATING_SAFETY_FACTOR 1.1이 표 3-3-35의 강풍·단일피복과 값이 같은데 정체
    #   미확정"으로 남긴 항목이다. 신개념온실 **PDF p.343(인쇄 307)**:
    #     "최대난방부하는 … 구한다. 여기에 온실 설치지역의 **풍속에 따른 보정계수**,
    #      **난방방식에 따른 안전계수**, 공기분산방식에 따른 보정계수, 난방배관방식에
    #      따른 보정계수를 적용하여 최종 난방시스템의 설치용량을 결정한다."
    #   → 원문이 **풍속보정계수와 안전계수를 별개 항목으로 나란히 나열**한다.
    #   게다가 엔진은 safety를 max_load가 아니라 **heater(설치용량)에만** 곱한다
    #   (아래 `heater = max_load * safety`) — 적용 단계도 서로 다르다.
    #   ✅ **101차에 1.1의 출처도 확정됐다**: PDF p.389(인쇄 353) "온풍난방의 설치용량은
    #   최대난방부하에 **10%의 안전계수**를 적용 … 온수난방은 20∼30%". 이 엔진 대상이
    #   등유 온풍난방기라 1.1이 맞다. 📌"난방방식별 안전계수"는 **표가 아니라 본문**이었다 —
    #   못 찾은 게 아니라 표가 없었다(14절 B3·B6 종결). 방식별 값은
    #   `HEATING_SAFETY_FACTOR_BY_METHOD`.
    #
    #   ⚠️ **기간난방부하(period_load)에는 곱하지 않는다** — 원문의 기간난방부하 식은
    #   난방디그리아워 × 평균난방부하계수 × 피복면적 계열이고 f_w가 들어가지 않는다
    #   (일조시간 조정계수 [표 3-3-36]이 그 자리의 보정이다). 따라서 fuel_use도 불변.
    if wind_factor not in set(WIND_CORRECTION_FACTOR.values()):
        raise ValueError(
            f"wind_factor는 [표 3-3-35] 조회값이어야 한다"
            f"(가능: {sorted(set(WIND_CORRECTION_FACTOR.values()))}, 입력: {wind_factor!r}) — "
            f"wind_correction_factor()로 구할 것. 임의 값은 근거가 없다")
    max_load = surface_area_m2 * u_d * dt * fr * wind_factor
    # ✅ heater_capacity의 발열량 기준 확정(2026-08-20 73차, 사용자 지시로 조사):
    #   16회차가 "정격 **출력** 기준인지 **입열량** 기준인지 어느 문서에도 정의 없음 —
    #   출력 기준이면 현행이 옳고 입열량 기준이면 효율 나눗셈이 빠진 것"으로 확인 불가에
    #   남겼던 항목이다. 리포 원출처가 정의로 답한다 —
    #   시설평가/20230627_스마트팜 시설의 구조와 이해_김평화(제공).pdf p.49:
    #     "1. 최대난방부하 : 난방을 행하는 기간 중 **난방기가 최대로 공급할 수 있는 열량**"
    #     "• **난방기 용량 결정!**"
    #   즉 max_load는 난방기가 *공급하는*(=출력) 열량이고, 여기에 안전율만 곱한
    #   heater_capacity도 **정격 난방능력(출력) 기준**이다 → **효율 나눗셈은 불필요**하며
    #   현행 구조가 맞다. 연료소비량(fuel_use)만 입열량 계산이라 효율로 나눈다.
    #   ⚠️ 남은 미확보(17회차 F4로 전파): ①~~safety 출처 미상~~ → **101차 종결**(신개념온실
    #   PDF p.389/인쇄 353 "온풍난방 10%"). 같은 문서 p.53이 수치편을 "별도 자료"로
    #   분리한 것은 별개 사실로 남는다. ②**국내 등유
    #   온풍난방기 카탈로그의 정격 표기 관행은 리포에서 확인되지 않았다** — 위 판정은
    #   식 원출처의 *정의*에 근거한 것이지 기기 표기 관행을 확인한 것이 아니다.
    #   리포 내 유일한 부분 증거는 히트펌프 1건(기자재DB/장비정보.csv r25 이화글로벌
    #   CPV-Q2906KX "정격 능력 난방 33KW, 소비전력 난방 10.3KW" — 출력·입력 분리 표기)인데,
    #   등유 온풍기로 확대하면 72차 F1과 같은 범주 확장이 되므로 확증에는 쓰지 않는다.
    #   ⚠️ **실무 주의**: 정격을 입열량으로 표기하는 카탈로그와 heater_capacity를 직접
    #   대조하면 효율만큼(η=0.85 기준 약 15%) 언더사이징된다. 대조 전 표기 기준을 확인할 것.
    heater = max_load * safety
    period_load = degree_hours * u_p * fr * surface_area_m2  # 기간난방부하 근사
    # 98차: 원문 식(3-3-5)의 일조 조정계수 k. 기본 None이면 **현행 그대로**다
    #   (현행은 k=PERIOD_LOAD_K_NO_SUNSHINE=3600에 해당 — 위 블록 주석의 유리
    #   케이스 검산으로 확인). 값을 주면 k/3600 배율로 일조 취득을 반영한다.
    #   ⚠️케이스에 걸면 OPEX가 20~33% 움직여 원채원 회귀가 깨진다 — ★사용자 결정.
    if sunshine_k is not None:
        if sunshine_k not in set(PERIOD_LOAD_ADJUST_K.values()):
            raise ValueError(
                f"sunshine_k는 [표 3-3-36] 조회값이어야 한다"
                f"(가능: {sorted(set(PERIOD_LOAD_ADJUST_K.values()))}, 입력: {sunshine_k!r}) — "
                f"period_load_adjust_k()로 구할 것. 보간·임의 값은 근거가 없다")
        period_load *= sunshine_k / PERIOD_LOAD_K_NO_SUNSHINE
    # 16회차 F10: 가드는 두 표 모두를 본다 — 한쪽만 연료가 추가되면 여기서 잡힌다
    # (14회차 F5의 도시가스 추가 같은 후속 작업에서 KeyError가 새지 않도록).
    if fuel not in FUEL_LHV or fuel not in FUEL_HHV:
        # 14회차 F3: 종전 폴백 8170은 현행 별표에서 등유가 아니라 석유코크스 값이라
        # 어느 연료와도 연결되지 않는 고아 숫자였고, 오타·미등록 연료가 경고 없이
        # 계산되던 경로였다 — curtain_exposure_ratio와 같은 방식으로 거부한다.
        raise ValueError(f"'{fuel}'은 FUEL_LHV에 없는 연료다 (선택: {list(FUEL_LHV)})")
    # ⚠️ 발열량 기준 미해결(72차 결론): 이 식은 리포 원출처(시설평가/20230627_스마트팜
    # 시설의 구조와 이해_김평화(제공).pdf p.49)의 "난방연료소비량 = 기간난방부하 /
    # (연료발열량 × 난방장치 열이용효율)"을 그대로 구현한 것인데, 원문이 "연료발열량"
    # 이라고만 해 총발열량인지 순발열량인지 특정하지 않는다. 72차에 총발열량 조합으로
    # 바꿨다가 **레드팀 16회차 F1의 반박으로 되돌렸다** — 근거로 삼았던 고시 각주가
    # 가스식 응축보일러 표에 붙은 것이었고(이 시스템 대상은 등유 온풍난방기), 물리적
    # 개연성도 순발열량 쪽이다: 0.85가 총발열량 기준이면 순발열량 환산 91.2%로 비응축
    # 기기엔 도달 난이하나, 순발열량 기준이면 총발열량 환산 79.3%로 통상 대역이다.
    # 두 조합의 차이는 등유 기준 7.24%다(FUEL_HHV 상수로 언제든 대조 가능).
    lhv = FUEL_LHV[fuel]
    fuel_use = period_load / (lhv * efficiency)
    denom = floor_area_m2 or surface_area_m2
    return HeatingResult(max_load, max_load / denom, heater, fuel_use, lhv)


# ─────────────────────────────────────────────────────────────
# 최대난방부하 3성분 구조 (2026-09-13 84차 신설 — 사용자 지시 "c 진행")
#   경위: 83차가 원문 식에서 **엔진의 구조적 공백**을 발견했다 —
#   `에너지절감과생산성향상을위한신개념온실설계및표준화연구.pdf` PDF p.344(인쇄 308) 식(3-3-1):
#     **최대난방부하 = (관류열부하 + 틈새환기전열부하 + 지중전열부하) × 풍속보정계수**
#   `heating_load()`는 **관류열부하만** 계산한다(Aw×U×ΔT×fr). 76~82차 내내 "U를 얼마로
#   볼 것인가"를 다퉜는데 식 자체가 3성분 중 1성분만 담고 있었다.
#
#   ✅ **85차에 식을 확정했다**(사용자 지시 "a 진행"): 수식이 이미지라 텍스트 추출이
#   안 되므로 `pypdfium2`로 해당 페이지를 300dpi 렌더해 **직접 열람**했다 —
#     H_T = (H_W + H_V + H_S)·f_w   (3-3-1)
#     H_W = U·A_c·(T_i − T_o)       (3-3-2)
#     H_V = ρ_i·c_p·N·V·(T_i − T_o) (3-3-3)
#     H_S = F·L_s·(ΔT − Θ)          (3-3-4)
#   84차에 "추정"으로 남겼던 지중전열부하 식 형태가 1차 출처(신개념온실 p.345)와
#   2차(정밀계측 p.62) **양쪽에서 동일하게 확인**됐다. 표 3-3-34 전사도 원문과 완전 일치.
#   ⚠️ **원문 변수 정의·단위는 아래 보고서가 실제
#   사용값을 실어 확정했다 — `시설에너지절감을위한온실내부전영역정밀환경계측시스템
#   연구.pdf` PDF p.62(인쇄 55): 공기비열 **0.24 kcal/kg·℃**, 틈새환기율 이중피복 **0.0001265
#   회/s**(=0.455 회/h, 표 3-3-34의 0.3~0.6 범위 안), 외주부 열손실계수 **7.5**,
#   둘레길이 240m, 풍속보정계수 1.0. 이 값들로 각 항의 차원이 닫힘을 확인했다.
#
#   ⚠️ **`heating_load()`를 건드리지 않았다.** 기존 케이스·견적비교가 그 함수를 타므로
#   신규 구조는 **별도 함수**로 얹는다(82차 assembly와 같은 방식). 관류열부하는
#   `heating_load()` 결과를 그대로 받아 쓴다 — 재계산하지 않는다.
#
#   ⚠️ **누락 입력을 숨기지 않는다**(79차 채택 원칙 §J: "자료가 부족하면 계산 가능한
#   범위까지만 계산하고 누락 입력값을 명확히 표시한다"). 틈새환기(체적·환기율·공기밀도)
#   와 지중(둘레길이·열손실계수)은 **케이스에 없는 입력**이라, 주지 않으면 그 성분을
#   None으로 두고 `missing`에 무엇이 필요한지 적는다. 임의값으로 채우지 않는다.
# ─────────────────────────────────────────────────────────────

# [표 3-3-34] 온실의 종류별 틈새환기율 (신개념온실 p.345 전사)
#   원문이 회/s와 회/h 두 단위를 병기한다. 여기선 **회/h**를 쓴다(부하 단위가 kcal/h).
#   ⚠️ 전부 **범위**다 — 79차 채택 §G "계수 근거가 약하면 임의의 소수점 값으로 만들지
#   말고 Low/Base/High 범위를 사용한다"에 따라 단일값으로 접지 않는다.
INFILTRATION_RATE_PER_HOUR = {
    "단일피복": (0.5, 1.0),
    "이중피복": (0.3, 0.6),
    "단일피복+보온커튼1층": (0.2, 0.4),
    "단일피복+보온커튼2층": (0.1, 0.2),
    "단일피복+보온커튼3층": (0.05, 0.1),
    "이중피복+보온커튼1층": (0.1, 0.2),
    "완전기밀": (0.0, 0.0),
}

# 지중전열부하 계수 (신개념온실 p.345 본문 전사)
#   외주부 단위길이당 열손실계수 P, 부하경감 기준온도차 Δt0.
#   원문: "대규모 온실 7.5~10, 소규모 온실 2.5~5.0" / "대규모 10℃, 소규모 15℃ 정도"
#   ⚠️ 원문이 대규모·소규모의 **면적 경계를 정의하지 않는다**[확인요망].
#   ⚠️ 85차 확인: P의 단위는 원문이 **W/m·℃**로 명시한다(신개념온실 p.345).
#     kcal/h 체계로 쓰려면 W_TO_KCAL_PER_HOUR를 곱해야 한다 —
#     `heating_load_components()`가 내부에서 환산한다.
GROUND_LOSS_COEF = {           # (P_low[W/m·℃], P_high[W/m·℃], Δt0[℃])
    "대규모": (7.5, 10.0, 10.0),
    "소규모": (2.5, 5.0, 15.0),
}

# [표 3-3-35] 풍속보정계수 (신개념온실 p.345 전사)
#   주) 강풍지역 = 난방설계용 **동절기 평균풍속 3.0m/s 이상**인 지역
#   📌 83차 발견: `HEATING_SAFETY_FACTOR = 1.1`이 이 표의 "강풍지역·단일피복"과 값이
#      같다. 다만 엔진은 조건 없이 항상 곱하고 원문은 조건부다 — 정체는 미확정.
WIND_CORRECTION_FACTOR = {
    ("일반지역", "단일피복"): 1.0,
    ("일반지역", "보온피복"): 1.0,
    ("강풍지역", "단일피복"): 1.1,
    ("강풍지역", "보온피복"): 1.05,
}
WIND_STRONG_THRESHOLD_MS = 3.0   # 강풍지역 판정 기준(동절기 평균풍속, m/s) — 원문 주석

# ─────────────────────────────────────────────────────────────
# 온실 환경설계용 기상자료 (2026-09-13 88차 신설 — 사용자 지시 "c 진행")
#   출처: `스마트팜연구DB/에너지절감과생산성향상을위한신개념온실설계및표준화연구.pdf`
#     PDF p.350~351(인쇄 314~315) **[표 3-3-38] TAC 위험율별 온실의 난방설계 기온(℃)**
#     PDF p.359~360(인쇄 323~324) **[표 3-3-42] 온실설계용 설정온도별 난방디그리아워(10³℃·h)**
#   원문 p.349: 1981~2010 **30년 전체 기상자료(매 시간자료)를 TAC법으로 분석**.
#     기상청 자료 가용 78지역 중 69지역의 기온 데이터를 분석했다(일사량은 22지역뿐).
#   원문 p.344: **"설계외기온은 TAC 1%의 값을 권장하며 온실의 투자수준에 따라 조정"**.
#
#   ✅ 전사 검산(69×2, 88차): 앵커 4건이 원문과 일치(속초 TAC1 -9.3 · 전주 -9.4 ·
#     부산 8℃ 10.269 · 속초 8℃ 18.895) + 단조성 3종 위반 0건 —
#     ①TAC 1% ≤ 2.5% ≤ 5%(평균) ②최소 ≤ 평균 ≤ 최대 ③설정온도 8<12<16<20.
#
#   ⚠️ **설정온도 보간을 하지 않는다.** 원문이 8/12/16/20℃ 네 값만 주는데 케이스
#     t_target은 10·15℃다 — 보간은 근거 없는 값을 만드는 일이라 **정확 일치만**
#     돌려주고 없으면 None과 함께 인접 설정온도를 알려준다(호출부 판단).
#   ⚠️ 지역명은 **기상관측지점명**이다(행정구역명이 아니다). "천안"은 있으나
#     "논산"·"군산"처럼 관측지점이 있는 곳만 조회된다 — 없으면 인접 지점 대용이
#     필요하고 그 선택은 판단성이다.
#   ⚠️ 이 표들은 **아직 계산에 쓰이지 않는다** — 케이스 t_min·degree_hours를 이 값으로
#     교체하면 산출물 수치가 움직이므로 별도 결정이다(도달성 가드로 고정).
# ─────────────────────────────────────────────────────────────
# 지역 -> (TAC1% 평균, TAC2.5% 평균, TAC5% 평균, 자료기간). 단위 ℃.
#   원문은 위험율별로 평균·최대·최소 3열을 주는데 여기엔 **평균만** 싣는다 —
#   설계 권장이 평균값이고(p.344), 최대·최소는 연차 변동폭 참고용이다.
DESIGN_OUTDOOR_TEMP_TAC = {
    "속초": (-9.3, -7.6, -6.2, "1981-2010"),
    "철원": (-17.8, -15.9, -14.1, "1988-2010"),
    "대관령": (-18.6, -16.9, -15.3, "1981-2010"),
    "춘천": (-15.5, -13.8, -12.1, "1981-2010"),
    "강릉": (-8.7, -7.1, -5.6, "1981-2010"),
    "서울": (-11.8, -10.3, -8.9, "1981-2010"),
    "인천": (-10.7, -9.4, -8.1, "1981-2010"),
    "원주": (-15.3, -13.6, -11.9, "1981-2010"),
    "울릉도": (-5.8, -4.5, -3.3, "1981-2010"),
    "수원": (-12.4, -11.0, -9.5, "1981-2010"),
    "충주": (-14.4, -12.7, -11.1, "1981-2010"),
    "서산": (-10.7, -9.3, -8.0, "1981-2010"),
    "울진": (-7.9, -6.5, -5.1, "1981-2010"),
    "청주": (-12.1, -10.6, -9.0, "1981-2010"),
    "대전": (-10.9, -9.4, -8.0, "1981-2010"),
    "추풍령": (-10.9, -9.4, -8.1, "1981-2010"),
    "안동": (-12.1, -10.5, -9.1, "1982-2010"),
    "포항": (-7.0, -5.6, -4.3, "1981-2010"),
    "군산": (-8.1, -6.7, -5.5, "1981-2010"),
    "대구": (-7.8, -6.5, -5.2, "1981-2010"),
    "전주": (-9.4, -7.9, -6.6, "1981-2010"),
    "울산": (-6.7, -5.3, -4.1, "1981-2010"),
    "창원": (-5.6, -4.2, -2.9, "1985-2010"),
    "광주": (-7.2, -5.9, -4.8, "1981-2010"),
    "부산": (-5.9, -4.5, -3.1, "1981-2010"),
    "통영": (-5.1, -3.8, -2.7, "1981-2010"),
    "목포": (-5.2, -4.1, -3.0, "1981-2010"),
    "여수": (-5.5, -4.1, -3.1, "1981-2010"),
    "흑산도": (-2.5, -1.4, -0.5, "1997-2010"),
    "완도": (-3.7, -2.7, -1.8, "1981-2010"),
    "제주": (0.0, 0.8, 1.6, "1981-2010"),
    "고산": (0.4, 1.3, 2.0, "1988-2010"),
    "성산": (-1.3, -0.4, 0.4, "1981-2010"),
    "서귀포": (-0.3, 0.8, 1.6, "1981-2010"),
    "진주": (-9.5, -8.2, -6.9, "1981-2010"),
    "강화": (-13.0, -11.6, -10.3, "1981-2010"),
    "양평": (-15.4, -13.7, -12.0, "1981-2010"),
    "이천": (-14.0, -12.3, -10.7, "1981-2010"),
    "인제": (-16.7, -15.0, -13.3, "1981-2010"),
    "홍천": (-17.5, -15.7, -13.9, "1981-2010"),
    "태백": (-15.2, -13.6, -12.1, "1986-2010"),
    "제천": (-16.8, -15.0, -13.3, "1981-2010"),
    "보은": (-14.1, -12.4, -10.8, "1981-2010"),
    "천안": (-13.0, -11.2, -9.6, "1981-2010"),
    "보령": (-9.1, -7.8, -6.5, "1981-2010"),
    "부여": (-11.4, -9.9, -8.4, "1981-2010"),
    "금산": (-12.9, -11.3, -9.9, "1981-2010"),
    "부안": (-9.4, -7.6, -6.2, "1981-2010"),
    "임실": (-13.8, -11.9, -10.1, "1981-2010"),
    "정읍": (-9.0, -7.6, -6.2, "1981-2010"),
    "남원": (-11.5, -9.8, -8.3, "1981-2010"),
    "장수": (-13.9, -11.9, -10.2, "1988-2010"),
    "순천": (-9.3, -7.9, -6.8, "1981-2010"),
    "장흥": (-7.7, -6.5, -5.4, "1981-2010"),
    "해남": (-6.6, -5.4, -4.2, "1981-2010"),
    "고흥": (-6.9, -5.8, -4.6, "1981-2010"),
    "봉화": (-15.5, -13.7, -12.1, "1988-2010"),
    "영주": (-13.0, -11.4, -9.9, "1981-2010"),
    "문경": (-10.9, -9.5, -8.1, "1981-2010"),
    "영덕": (-8.2, -6.8, -5.4, "1981-2010"),
    "의성": (-14.8, -13.3, -11.7, "1981-2010"),
    "구미": (-9.7, -8.3, -7.2, "1981-2010"),
    "영천": (-10.4, -9.0, -7.7, "1981-2010"),
    "거창": (-11.3, -9.9, -8.6, "1981-2010"),
    "합천": (-9.9, -8.6, -7.4, "1981-2010"),
    "밀양": (-8.9, -7.7, -6.6, "1981-2010"),
    "산청": (-8.6, -7.3, -6.0, "1981-2010"),
    "거제": (-5.3, -4.2, -3.1, "1981-2010"),
    "남해": (-5.7, -4.6, -3.5, "1981-2010"),
}

# 지역 -> (8℃, 12℃, 16℃, 20℃ 설정온도별 난방디그리아워, 자료기간). 단위 10³℃·h.
HEATING_DEGREE_HOURS_1000 = {
    "속초": (18.895, 33.392, 52.133, 75.929, "1981-2010"),
    "철원": (34.232, 50.802, 70.761, 94.629, "1988-2010"),
    "대관령": (44.641, 64.615, 89.09, 118.542, "1981-2010"),
    "춘천": (30.513, 46.411, 65.7, 88.776, "1981-2010"),
    "강릉": (16.967, 30.618, 48.289, 70.701, "1981-2010"),
    "서울": (23.435, 37.896, 55.83, 77.672, "1981-2010"),
    "인천": (22.757, 37.529, 55.996, 78.618, "1981-2010"),
    "원주": (29.734, 45.401, 64.452, 87.275, "1981-2010"),
    "울릉도": (15.51, 29.509, 48.104, 72.353, "1981-2010"),
    "수원": (25.494, 40.553, 59.048, 81.331, "1981-2010"),
    "충주": (28.88, 44.514, 63.527, 86.302, "1981-2010"),
    "서산": (24.308, 39.574, 58.456, 81.305, "1981-2010"),
    "울진": (16.129, 29.866, 48.243, 71.959, "1981-2010"),
    "청주": (24.357, 39.045, 57.126, 78.927, "1981-2010"),
    "대전": (22.466, 36.863, 54.803, 76.578, "1981-2010"),
    "추풍령": (24.683, 40.003, 59.032, 82.288, "1981-2010"),
    "안동": (25.285, 40.475, 59.248, 82.044, "1982-2010"),
    "포항": (13.23, 25.48, 42.012, 63.174, "1981-2010"),
    "군산": (19.149, 33.535, 51.624, 73.758, "1981-2010"),
    "대구": (16.267, 29.211, 45.922, 66.726, "1981-2010"),
    "전주": (19.831, 33.745, 51.273, 72.629, "1981-2010"),
    "울산": (14.074, 25.704, 42.264, 63.42, "1981-2010"),
    "창원": (11.103, 22.649, 38.447, 58.897, "1985-2010"),
    "광주": (16.904, 30.138, 47.14, 68.168, "1981-2010"),
    "부산": (10.269, 21.255, 36.948, 57.887, "1981-2010"),
    "통영": (10.848, 22.355, 38.454, 59.649, "1981-2010"),
    "목포": (14.154, 27.166, 44.174, 65.576, "1981-2010"),
    "여수": (11.604, 23.483, 39.702, 60.796, "1981-2010"),
    "흑산도": (10.661, 23.892, 41.884, 65.047, "1997-2010"),
    "완도": (11.643, 23.94, 40.644, 62.223, "1981-2010"),
    "제주": (5.62, 15.543, 30.551, 50.762, "1981-2010"),
    "고산": (4.849, 14.395, 29.403, 50.099, "1988-2010"),
    "성산": (7.21, 17.506, 32.693, 53.163, "1981-2010"),
    "서귀포": (4.114, 12.107, 25.517, 44.465, "1981-2010"),
    "진주": (19.602, 33.344, 50.933, 72.618, "1981-2010"),
    "강화": (27.908, 43.659, 63.129, 86.777, "1981-2010"),
    "양평": (30.01, 45.821, 65.03, 87.981, "1981-2010"),
    "이천": (28.356, 43.968, 62.972, 85.84, "1981-2010"),
    "인제": (32.918, 49.642, 70.028, 94.591, "1981-2010"),
    "홍천": (34.109, 50.67, 70.642, 94.447, "1981-2010"),
    "태백": (35.024, 53.025, 75.306, 102.541, "1986-2010"),
    "제천": (33.959, 50.677, 70.816, 94.885, "1981-2010"),
    "보은": (29.483, 45.595, 65.226, 88.811, "1981-2010"),
    "천안": (26.509, 41.908, 60.755, 83.463, "1981-2010"),
    "보령": (21.047, 35.769, 54.253, 78.654, "1981-2010"),
    "부여": (24.545, 39.652, 58.221, 80.533, "1981-2010"),
    "금산": (27.407, 43.016, 62.117, 85.062, "1981-2010"),
    "부안": (20.385, 34.991, 53.337, 75.695, "1981-2010"),
    "임실": (28.647, 44.688, 64.308, 87.847, "1981-2010"),
    "정읍": (20.176, 34.307, 52.099, 73.837, "1981-2010"),
    "남원": (24.383, 39.308, 57.729, 79.865, "1981-2010"),
    "장수": (29.271, 45.678, 65.781, 90.113, "1988-2010"),
    "순천": (21.284, 35.785, 54.096, 76.412, "1981-2010"),
    "장흥": (18.683, 32.672, 50.63, 72.761, "1981-2010"),
    "해남": (16.445, 29.926, 47.432, 69.222, "1981-2010"),
    "고흥": (15.96, 29.17, 46.512, 68.244, "1981-2010"),
    "봉화": (32.928, 50.077, 70.848, 95.767, "1988-2010"),
    "영주": (27.075, 42.839, 62.208, 85.588, "1981-2010"),
    "문경": (24.35, 39.653, 58.653, 81.818, "1981-2010"),
    "영덕": (17.173, 31.128, 49.39, 72.478, "1981-2010"),
    "의성": (29.621, 45.444, 64.71, 87.757, "1981-2010"),
    "구미": (22.343, 36.985, 55.224, 77.418, "1981-2010"),
    "영천": (22.529, 37.266, 55.757, 78.328, "1981-2010"),
    "거창": (24.923, 40.402, 59.604, 82.861, "1981-2010"),
    "합천": (20.534, 34.577, 52.437, 74.35, "1981-2010"),
    "밀양": (19.113, 32.801, 50.322, 71.952, "1981-2010"),
    "산청": (19.423, 33.672, 51.856, 74.209, "1981-2010"),
    "거제": (12.94, 25.319, 42.09, 63.641, "1981-2010"),
    "남해": (13.244, 25.717, 42.346, 63.621, "1981-2010"),
}

_HDH_SET_TEMPS = (8, 12, 16, 20)


def design_outdoor_temp(region: str, tac: str = "1%") -> Optional[float]:
    """[표 3-3-38] 조회 — 지역의 난방설계 외기온(℃). 원문 권장은 TAC 1%다.

    tac: "1%"|"2.5%"|"5%". 지역이 표에 없으면 None(인접 지점 대용은 판단성이라
    엔진이 고르지 않는다). 지역명은 **기상관측지점명**이다.
    """
    row = DESIGN_OUTDOOR_TEMP_TAC.get(region)
    if row is None:
        return None
    idx = {"1%": 0, "2.5%": 1, "5%": 2}.get(tac)
    if idx is None:
        raise ValueError(f"tac은 '1%'|'2.5%'|'5%' 중 하나여야 한다: {tac!r}")
    return row[idx]


def heating_degree_hours(region: str, set_temp_c: float) -> dict:
    """[표 3-3-42] 조회 — 설정온도별 난방디그리아워(℃·h, 원문의 10³ 단위를 푼 값).

    **보간하지 않는다.** 원문이 8/12/16/20℃만 주므로 정확히 일치할 때만 값을
    돌려주고, 아니면 value=None과 함께 인접 설정온도를 알려준다 — 사이 값을
    지어내지 않기 위함이다(호출부가 어느 쪽을 쓸지 정한다).
    """
    row = HEATING_DEGREE_HOURS_1000.get(region)
    if row is None:
        return {"region": region, "value": None, "reason": "표에 없는 지역(기상관측지점명 확인)",
                "available_set_temps": list(_HDH_SET_TEMPS)}
    if set_temp_c in _HDH_SET_TEMPS:
        return {"region": region, "set_temp_c": set_temp_c,
                "value": row[_HDH_SET_TEMPS.index(set_temp_c)] * 1000.0,
                "period": row[4]}
    lo = max([t for t in _HDH_SET_TEMPS if t < set_temp_c], default=None)
    hi = min([t for t in _HDH_SET_TEMPS if t > set_temp_c], default=None)
    return {"region": region, "set_temp_c": set_temp_c, "value": None,
            "reason": f"원문이 {_HDH_SET_TEMPS}℃만 제시 — 보간은 근거 없는 값이라 하지 않는다",
            "lower": None if lo is None else {"set_temp_c": lo, "value": row[_HDH_SET_TEMPS.index(lo)] * 1000.0},
            "upper": None if hi is None else {"set_temp_c": hi, "value": row[_HDH_SET_TEMPS.index(hi)] * 1000.0},
            "period": row[4]}


# ─────────────────────────────────────────────────────────────
# [표 3-3-44] 지역별·월별 평균풍속(m/s)의 평년값 — 69지역
#   (2026-09-13 95차 전사. 사용자 지시 "다음 차수 진행")
#   출처: 에너지절감과생산성향상을위한신개념온실설계및표준화연구.pdf
#         **PDF p.364~365 / 인쇄 쪽 328~329**
#   📌 **원문이 이 표의 용도를 직접 적는다** — PDF p.349(인쇄 313):
#      "표 3-3-44는 온실의 난방부하 산정시 **풍속에 따른 보정계수 적용에 참고**할 수
#       있도록 지역별 월별 평균풍속의 평년값을 정리한 것"
#      즉 [표 3-3-35] `WIND_CORRECTION_FACTOR`(84차 등재)의 입력 자료다 —
#      84차가 `wind_correction_factor(winter_mean_wind_ms, ...)`를 만들면서
#      호출부에 떠넘긴 그 인자를 이 표가 채운다.
#   값은 **(1월…12월, 연평균)** 13개다.
#   전사 검산: 69행·중복 0 · **69행 전부 12개월 평균 = 표기 연평균**(±0.06 이내,
#     이탈 0건) · 다른 두 표(69지역)와 지역 집합 대조.
#
#   ⚠️ **원문이 '동절기'의 개월을 정의하지 않는다.** [표 3-3-35] 주)는
#     "강풍지역은 난방설계용 **동절기** 평균풍속이 3.0m/s 이상인 지역에 적용"이라고만
#     적는다(PDF p.345 / 인쇄 309). 그래서 `mean_wind()`는 months를 **필수 인자**로
#     받는다 — 어느 달을 동절기로 묶을지는 판단성이고 엔진이 고르지 않는다.
#
#   ⚠️ **지역명 1건이 다른 표와 어긋난다**: 이 표는 **'마산'**, [표 3-3-38]
#     `DESIGN_OUTDOOR_TEMP_TAC`·[표 3-3-42] `HEATING_DEGREE_HOURS_1000`은
#     **'창원'**이다(나머지 68개는 완전 일치). 마산관측소는 현재 창원시 소재라 같은
#     지점일 가능성이 크지만 **원문이 그렇게 말하지 않았으므로 통합하지 않고 원문
#     표기 그대로 전사**한다. 별칭 처리는 판단성이라 사용자 결정 사안이다[확인요망].
#
#   ⚠️ **아직 계산에 쓰이지 않는다**(88차 두 표와 동일) — 케이스에 풍속보정계수를
#     걸면 난방부하가 움직이므로 별도 결정이다(도달성 가드로 고정).
#   📌 참고 관찰(적용 안 함): 12·1·2월 평균으로 보면 강풍지역(3.0m/s 이상)이 실제로
#     나온다 — 고산 9.53·흑산도 6.97·대관령 5.47·여수 4.73·목포 4.53. 🔴**리포의
#     실제 케이스 중 군산이 3.83으로 걸린다**(견적비교 군산무화과 계열): 보온피복
#     기준 계수 1.05가 붙으면 그 케이스 최대난방부하가 5% 늘어난다. 천안 1.57·
#     춘천 1.20·서산 2.27은 일반지역이라 계수 1.0(현행과 동일).
#     ⚠️12·1·2월 묶음 자체가 원문에 없는 가정이다 — 참고일 뿐이고 ★사용자 결정.
# ─────────────────────────────────────────────────────────────
MONTHLY_MEAN_WIND_MS = {
    "속초": (3.3, 3.1, 3.1, 3.3, 3.0, 2.4, 2.3, 2.2, 2.4, 2.7, 3.0, 3.2, 2.8),
    "철원": (1.4, 1.6, 2.1, 2.3, 2.2, 1.9, 2.0, 1.8, 1.6, 1.4, 1.6, 1.4, 1.8),
    "대관령": (5.6, 5.0, 4.5, 4.8, 4.3, 3.2, 3.7, 3.0, 2.7, 3.8, 5.1, 5.8, 4.3),
    "춘천": (1.1, 1.4, 1.6, 1.7, 1.5, 1.3, 1.2, 1.2, 1.1, 1.0, 1.1, 1.1, 1.3),
    "강릉": (3.5, 3.1, 2.8, 2.8, 2.4, 1.8, 1.8, 1.7, 2.0, 2.5, 3.0, 3.4, 2.6),
    "서울": (2.4, 2.6, 2.8, 2.8, 2.5, 2.2, 2.3, 2.1, 1.9, 2.0, 2.2, 2.3, 2.3),
    "인천": (3.2, 3.5, 3.7, 3.5, 3.0, 2.5, 2.6, 2.4, 2.1, 2.3, 3.0, 3.3, 2.9),
    "원주": (1.0, 1.2, 1.5, 1.6, 1.3, 1.1, 1.0, 1.0, 0.9, 0.9, 1.0, 1.0, 1.1),
    "울릉도": (3.6, 3.8, 4.1, 4.4, 4.1, 3.2, 3.6, 3.4, 3.3, 3.5, 3.7, 3.6, 3.7),
    "수원": (1.5, 1.8, 2.0, 2.0, 1.8, 1.7, 1.8, 1.7, 1.5, 1.3, 1.5, 1.5, 1.7),
    "충주": (1.1, 1.3, 1.4, 1.5, 1.3, 1.2, 1.0, 1.0, 1.0, 1.0, 1.1, 1.1, 1.2),
    "서산": (2.2, 2.4, 2.8, 2.8, 2.7, 2.3, 2.6, 2.3, 2.0, 1.9, 2.2, 2.2, 2.4),
    "울진": (4.4, 4.2, 4.1, 4.2, 3.8, 3.2, 3.2, 3.2, 3.5, 3.7, 4.0, 4.2, 3.8),
    "청주": (1.6, 1.8, 2.0, 2.1, 2.0, 1.8, 1.9, 1.8, 1.6, 1.4, 1.5, 1.5, 1.8),
    "대전": (1.7, 1.8, 2.2, 2.3, 2.2, 1.9, 2.1, 1.9, 1.8, 1.4, 1.5, 1.5, 1.9),
    "추풍령": (3.9, 3.7, 3.3, 3.1, 2.5, 1.9, 1.7, 1.7, 1.7, 2.1, 2.8, 3.5, 2.7),
    "안동": (1.9, 2.0, 2.1, 2.1, 1.7, 1.6, 1.4, 1.4, 1.3, 1.3, 1.6, 1.8, 1.7),
    "포항": (3.0, 2.9, 3.0, 3.0, 2.8, 2.5, 2.6, 2.7, 2.7, 2.6, 2.6, 2.8, 2.8),
    "군산": (3.8, 4.1, 4.5, 4.2, 4.0, 3.6, 3.4, 3.5, 3.5, 3.5, 3.7, 3.6, 3.8),
    "대구": (2.9, 2.9, 3.0, 2.9, 2.8, 2.7, 2.6, 2.6, 2.3, 2.2, 2.4, 2.6, 2.7),
    "전주": (1.4, 1.6, 1.8, 1.9, 1.8, 1.6, 1.7, 1.6, 1.4, 1.3, 1.4, 1.4, 1.6),
    "울산": (2.4, 2.4, 2.5, 2.3, 2.1, 1.9, 2.0, 2.0, 1.9, 1.8, 1.9, 2.2, 2.1),
    "마산": (2.2, 2.3, 2.4, 2.3, 2.3, 2.3, 2.4, 2.2, 2.1, 2.0, 1.9, 2.0, 2.2),
    "광주": (2.1, 2.2, 2.3, 2.3, 2.3, 2.1, 2.5, 2.2, 1.9, 1.7, 1.8, 1.9, 2.1),
    "부산": (3.7, 3.8, 4.0, 4.0, 3.6, 3.3, 3.8, 3.7, 3.6, 3.3, 3.4, 3.6, 3.7),
    "통영": (2.7, 2.7, 2.9, 2.7, 2.4, 2.3, 2.6, 2.6, 2.5, 2.4, 2.4, 2.6, 2.6),
    "목포": (4.6, 4.8, 4.5, 4.0, 3.7, 3.2, 3.6, 3.3, 3.2, 3.7, 4.1, 4.2, 3.9),
    "여수": (4.9, 4.8, 4.6, 4.0, 3.4, 3.1, 3.3, 3.6, 4.2, 4.0, 4.1, 4.5, 4.0),
    "흑산도": (7.2, 6.8, 6.2, 5.4, 4.9, 4.2, 5.0, 4.5, 4.6, 5.3, 6.2, 6.9, 5.6),
    "완도": (4.8, 4.7, 4.2, 3.6, 3.1, 2.8, 2.9, 2.9, 3.0, 3.4, 3.7, 4.3, 3.6),
    "제주": (4.5, 4.2, 3.9, 3.4, 3.0, 3.0, 3.0, 3.0, 3.1, 3.2, 3.7, 4.3, 3.5),
    "고산": (9.9, 9.3, 8.2, 6.6, 5.6, 4.7, 5.3, 5.2, 5.5, 6.6, 7.9, 9.4, 7.0),
    "성산": (3.5, 3.7, 3.6, 3.2, 3.0, 2.6, 2.9, 2.9, 3.1, 3.1, 3.1, 3.2, 3.2),
    "서귀포": (2.8, 3.0, 3.2, 3.0, 2.7, 2.7, 2.7, 3.0, 3.3, 3.0, 2.8, 2.8, 2.9),
    "진주": (1.9, 2.1, 2.2, 2.1, 1.9, 1.8, 2.1, 1.7, 1.5, 1.3, 1.5, 1.6, 1.8),
    "강화": (1.5, 1.8, 2.0, 2.1, 1.9, 1.6, 1.7, 1.6, 1.4, 1.4, 1.5, 1.5, 1.7),
    "양평": (1.1, 1.3, 1.5, 1.5, 1.2, 1.1, 1.1, 1.0, 0.9, 0.9, 1.1, 1.1, 1.2),
    "이천": (1.2, 1.4, 1.7, 1.8, 1.5, 1.2, 1.3, 1.1, 1.0, 0.9, 1.1, 1.1, 1.3),
    "인제": (1.7, 1.8, 2.2, 2.4, 2.1, 1.7, 1.8, 1.6, 1.5, 1.4, 1.6, 1.7, 1.8),
    "홍천": (0.8, 1.0, 1.2, 1.3, 1.2, 1.0, 0.9, 0.9, 0.8, 0.8, 0.9, 0.8, 1.0),
    "태백": (1.7, 1.7, 1.9, 2.1, 1.9, 1.5, 1.7, 1.6, 1.4, 1.5, 1.6, 1.7, 1.7),
    "제천": (1.4, 1.5, 1.7, 1.7, 1.5, 1.3, 1.2, 1.2, 1.2, 1.1, 1.2, 1.2, 1.4),
    "보은": (1.5, 1.6, 1.7, 1.7, 1.5, 1.2, 1.1, 1.1, 1.0, 1.0, 1.3, 1.4, 1.3),
    "천안": (1.5, 1.7, 2.0, 1.9, 1.7, 1.5, 1.5, 1.5, 1.4, 1.3, 1.5, 1.5, 1.6),
    "보령": (1.9, 2.0, 2.1, 2.1, 2.1, 1.8, 2.3, 1.9, 1.7, 1.6, 1.9, 1.9, 1.9),
    "부여": (1.0, 1.2, 1.4, 1.4, 1.4, 1.2, 1.3, 1.2, 1.1, 0.9, 1.0, 1.0, 1.2),
    "금산": (1.1, 1.3, 1.4, 1.5, 1.3, 1.1, 1.1, 1.0, 0.9, 0.9, 1.0, 1.0, 1.1),
    "부안": (1.5, 1.8, 2.0, 2.0, 1.8, 1.6, 1.7, 1.4, 1.3, 1.3, 1.4, 1.4, 1.6),
    "임실": (1.2, 1.4, 1.6, 1.7, 1.5, 1.3, 1.4, 1.2, 1.0, 1.0, 1.2, 1.2, 1.3),
    "정읍": (0.9, 1.1, 1.2, 1.4, 1.3, 1.1, 1.2, 1.1, 1.0, 0.9, 1.0, 0.9, 1.1),
    "남원": (1.4, 1.6, 1.7, 1.7, 1.5, 1.3, 1.3, 1.1, 1.1, 1.0, 1.2, 1.2, 1.3),
    "장수": (1.8, 1.8, 2.0, 2.1, 1.9, 1.6, 1.8, 1.4, 1.3, 1.3, 1.5, 1.7, 1.7),
    "순천": (1.5, 1.6, 1.6, 1.5, 1.3, 1.1, 1.0, 0.9, 0.8, 0.9, 1.2, 1.3, 1.2),
    "장흥": (2.2, 2.3, 2.2, 2.1, 1.9, 1.6, 1.6, 1.5, 1.3, 1.4, 1.7, 2.0, 1.8),
    "해남": (2.3, 2.5, 2.5, 2.5, 2.3, 2.1, 2.3, 2.1, 1.7, 1.7, 1.9, 2.1, 2.2),
    "고흥": (1.7, 1.8, 1.8, 1.6, 1.5, 1.3, 1.4, 1.4, 1.3, 1.2, 1.4, 1.6, 1.5),
    "봉화": (1.3, 1.3, 1.4, 1.4, 1.3, 1.1, 1.0, 1.0, 1.0, 1.0, 1.1, 1.3, 1.2),
    "영주": (3.4, 3.1, 2.8, 2.6, 2.1, 1.5, 1.3, 1.3, 1.4, 1.9, 2.4, 3.1, 2.2),
    "문경": (2.1, 2.1, 2.1, 2.0, 1.6, 1.3, 1.0, 1.0, 1.1, 1.3, 1.7, 2.0, 1.6),
    "영덕": (2.9, 2.8, 2.7, 2.7, 2.4, 2.0, 1.8, 1.9, 2.0, 2.1, 2.4, 2.8, 2.4),
    "의성": (1.2, 1.3, 1.4, 1.4, 1.2, 1.0, 0.8, 0.8, 0.8, 0.8, 0.9, 1.1, 1.1),
    "구미": (2.2, 2.1, 2.0, 2.0, 1.7, 1.3, 1.1, 1.1, 1.1, 1.3, 1.6, 1.9, 1.6),
    "영천": (2.3, 2.1, 2.1, 2.0, 1.8, 1.6, 1.5, 1.4, 1.3, 1.4, 1.7, 2.1, 1.8),
    "거창": (1.3, 1.4, 1.6, 1.6, 1.3, 1.1, 1.0, 1.0, 0.9, 1.0, 1.1, 1.2, 1.2),
    "합천": (1.1, 1.2, 1.5, 1.6, 1.4, 1.3, 1.3, 1.1, 1.0, 0.9, 1.0, 1.0, 1.2),
    "밀양": (1.3, 1.5, 1.6, 1.7, 1.5, 1.5, 1.5, 1.4, 1.3, 1.1, 1.2, 1.2, 1.4),
    "산청": (2.1, 1.9, 1.8, 1.7, 1.4, 1.2, 1.2, 1.0, 0.8, 1.0, 1.4, 1.9, 1.5),
    "거제": (1.8, 1.8, 1.9, 1.9, 1.8, 1.7, 1.8, 1.6, 1.4, 1.3, 1.4, 1.6, 1.7),
    "남해": (1.9, 1.9, 2.0, 1.9, 1.7, 1.5, 1.5, 1.6, 1.6, 1.6, 1.7, 1.8, 1.7),
}


def monthly_mean_wind(region: str) -> Optional[tuple]:
    """[표 3-3-44] 조회 — (1월…12월, 연평균) 평균풍속 m/s. 표에 없으면 None.

    지역명은 **기상관측지점명**이다(행정구역명 아님). ⚠️이 표만 '마산'을 쓰고
    [표3-3-38]·[표3-3-42]는 '창원'을 쓴다 — 별칭 해소는 하지 않는다(위 주석).
    """
    return MONTHLY_MEAN_WIND_MS.get(region)


def mean_wind(region: str, months) -> Optional[float]:
    """지정한 월들의 평균 풍속(m/s). 표에 없는 지역이면 None.

    months: 1~12의 정수 iterable. **기본값을 두지 않는다** — 원문이 '동절기'를
      정의하지 않으므로(위 주석) 어느 달을 묶을지는 호출부가 정한다. 엔진이
      동절기를 정하면 그건 근거 없는 값이다(1절).
      예) 12·1·2월로 보려면 mean_wind("천안", (12, 1, 2)).

    연평균이 필요하면 monthly_mean_wind(region)[12]를 쓴다 — 원문 표기값이고
    여기서 12개월을 다시 평균 내 만든 값이 아니다.
    """
    row = MONTHLY_MEAN_WIND_MS.get(region)
    if row is None:
        return None
    ms = list(months)
    if not ms:
        raise ValueError("months가 비어 있다 — 평균 낼 달을 지정해야 한다")
    if any((not isinstance(m, int)) or m < 1 or m > 12 for m in ms):
        raise ValueError(f"months는 1~12 정수여야 한다: {months!r}")
    return sum(row[m - 1] for m in ms) / len(ms)


# ─────────────────────────────────────────────────────────────
# 기간난방부하 식(3-3-5)의 일조 조정계수 k — [표 3-3-36] + [표 3-3-45]
#   (2026-09-13 98차 전사·구현. 사용자 지시 "d1 진행")
#   출처: 에너지절감과생산성향상을위한신개념온실설계및표준화연구.pdf
#     식(3-3-5)·(3-3-6)과 [표 3-3-36] — PDF p.345~346 / 인쇄 309~310
#     [표 3-3-45] 월별 평균 일조시간 — PDF p.366~367 / 인쇄 330~331
#
#   원문 식(수식이 이미지라 300dpi 렌더해 직접 판독 — 85차와 같은 방법):
#       Q_H = k · Ū · A_c · (HDH)                         (3-3-5)
#       Ū   = H_T / (A_c (T_i − T_o))                     (3-3-6)
#     Q_H 기간난방부하(J) · Ū 평균난방부하계수(W/㎡·℃) · A_c 피복면적(㎡)
#     HDH 난방디그리아워(℃·h) · H_T 최대난방부하
#     **k는 "일조시간에 따른 조정계수(단위환산 포함, 표 3-3-36)"** — 원문 자구다.
#
#   🔴 **엔진의 현행 기간난방부하는 k=3600에 해당한다(추정이 아니라 검산으로 확인)**:
#     현행 `period_load = HDH × u_p × fr × A_c`(kcal 계열)를 원문 식과 대조하면,
#     **u_design == u_period인 유리 케이스**에서 Ū = u·fr이 되어 두 식이 k만 다르다.
#     실제로 chuncheon·wonchaewon에서 원문/엔진 비가 **정확히 k/3600**으로 재현됐다
#     (4.5h 0.783 · 6.0h 0.728 · 7.5h 0.672 — 표의 2820/2620/2420 ÷ 3600과 일치).
#     즉 현행은 **일조 취득을 전혀 반영하지 않은 상한**이고, 원문대로면 일조
#     4.5~7.5h 구간에서 기간난방부하·연료소비량이 **21.7~32.8% 낮아진다**.
#
#   ⚠️ **그래서 자동 적용하지 않는다.** 케이스에 걸면 OPEX가 20~33% 움직이고
#     **원채원 회귀 기준(ROI 14.2%)이 직접 깨진다** — ★사용자 결정 사안이다.
#     `heating_load(sunshine_k=...)`는 기본 None(현행 유지)이고, 명시한 호출만 적용된다.
#
#   ⚠️ **필름 케이스는 이 축만으로 설명되지 않는다**: uminjae는 원문/엔진 비가
#     2.25~2.62로 유리 케이스와 전혀 다르다. u_design(8.9)과 u_period(2.66)가 갈라져
#     있어서다 — 원문은 Ū를 **최대난방부하에서 유도**(식 3-3-6)하므로 u_design 계열을
#     쓰는 셈이다. 이는 77차 `U_DESIGN` 8.9 vs 5.7 이견(작업지시서 14절 B2)과 같은
#     축이고, 그 결정 전에는 필름 케이스에 이 식을 적용할 수 없다[확인요망].
# ─────────────────────────────────────────────────────────────
# [표 3-3-36] 일평균 일조시간에 따른 온실의 기간난방부하 조정계수 k
#   원문 표 그대로 5점만 준다 — **보간하지 않는다**(88차 heating_degree_hours 방식).
#   📌 **104차 레드팀 F9 — 같은 페이지가 B4(총/순 발열량)의 단서를 준다**:
#     이 표가 실린 PDF p.346(인쇄 310)에는 식(3-3-7) 연료소비량 = 기간난방부하 ÷
#     (발열량 × 효율)과 **"효율은 온풍난방의 경우 0.8∼0.9"**, 그리고 바로 아래
#     **[표 3-3-37] 에너지원별 총발열량**(등유 8,790 kcal/L …)이 함께 있다.
#     → `HEATING_EFFICIENCY_DEFAULT=0.85`는 그 범위의 **중앙값**이고, 원문이 그 식에
#     쓸 표로 제시한 것은 **총발열량** 표다. ⚠️**확정은 아니다** — 기호 정의가
#     "연료의 발열량"이라 총발열량과의 짝짓기를 문장으로 명시하지 않았고, 엔진의
#     `FUEL_HHV` 등유 8,740은 에너지법 별표 계열로 이 표와 **다른 출처**다.
#     14절 B4(총/순 7.24% 차)의 **유력 단서**로 기록한다.
PERIOD_LOAD_ADJUST_K = {3.0: 3020.0, 4.5: 2820.0, 6.0: 2620.0, 7.5: 2420.0, 9.0: 2220.0}

# 현행 엔진 기간난방부하가 암묵적으로 쓰는 k(=W·h→J 환산만, 일조 취득 0).
#   위 블록 주석의 유리 케이스 검산으로 확인된 값이지 임의 기준이 아니다.
PERIOD_LOAD_K_NO_SUNSHINE = 3600.0

# [표 3-3-45] 월별 평균 일조시간(h/일)의 평년값 — 69지역, (1월…12월, 연평균)
#   전사 검산: 69행·중복 0 · 지역 집합이 [표3-3-38]·[표3-3-42]와 **완전 일치**.
#   📌 95차가 남긴 '마산↔창원' 이례가 더 좁혀졌다 — 이 표는 **'창원'**이므로
#      세 표 중 [표 3-3-44] 풍속표만 '마산'을 쓴다(1/3).
#   ⚠️ 연평균 자기검산: 68행이 ±0.06 안, **장흥 1행만 Δ0.067**이다(12개월 평균
#      5.767 vs 표기 5.7). 인접 지역(순천 5.33·광주 5.86)과 정합해 **행 밀림이 아니라
#      원문 반올림 차**로 본다 — 테스트가 이 1건을 이름으로 고정한다.
MONTHLY_SUNSHINE_HOURS = {
    "속초": (5.9, 6.1, 6.1, 7.1, 7.0, 5.4, 4.4, 4.9, 5.5, 6.1, 5.6, 5.9, 5.8),
    "철원": (5.2, 5.9, 5.8, 6.5, 6.7, 5.9, 4.1, 5.3, 6.0, 6.2, 4.9, 4.8, 5.6),
    "대관령": (6.4, 6.6, 6.5, 7.6, 7.4, 6.0, 4.5, 4.2, 4.8, 6.2, 5.9, 6.2, 6.0),
    "춘천": (5.3, 6.2, 6.4, 7.2, 7.1, 6.7, 4.7, 5.5, 5.8, 5.6, 4.7, 4.8, 5.8),
    "강릉": (5.9, 6.2, 6.0, 6.8, 6.7, 5.5, 4.5, 4.8, 5.2, 6.1, 5.7, 5.9, 5.8),
    "서울": (5.2, 5.8, 6.1, 6.8, 6.9, 6.1, 3.9, 4.9, 5.9, 6.4, 5.1, 4.9, 5.7),
    "인천": (5.7, 6.5, 6.6, 7.3, 7.5, 6.8, 5.1, 6.2, 6.6, 6.8, 5.6, 5.5, 6.3),
    "원주": (5.2, 5.9, 6.1, 7.1, 7.1, 6.5, 4.7, 5.5, 5.8, 6.0, 5.0, 4.9, 5.8),
    "울릉도": (2.9, 3.7, 5.4, 7.1, 7.3, 5.8, 4.9, 5.3, 5.3, 5.7, 4.3, 3.2, 5.1),
    "수원": (5.4, 6.1, 6.4, 7.2, 7.1, 6.3, 4.4, 5.4, 6.1, 6.5, 5.3, 5.2, 5.9),
    "충주": (5.4, 6.3, 6.5, 7.8, 7.8, 7.3, 5.8, 6.4, 6.3, 6.2, 5.1, 5.0, 6.3),
    "서산": (4.9, 6.0, 6.5, 7.3, 7.5, 6.4, 4.6, 5.9, 6.3, 6.6, 4.9, 4.6, 6.0),
    "울진": (6.6, 6.7, 6.6, 7.6, 7.6, 6.5, 5.3, 6.0, 5.8, 6.6, 6.3, 6.6, 6.5),
    "청주": (5.3, 6.1, 6.5, 7.4, 7.6, 6.5, 4.9, 5.8, 5.9, 6.5, 5.3, 5.1, 6.1),
    "대전": (5.3, 6.2, 6.5, 7.1, 7.2, 6.0, 4.5, 5.1, 5.6, 6.3, 5.4, 5.2, 5.9),
    "추풍령": (5.6, 6.2, 6.3, 7.2, 7.3, 6.1, 4.7, 5.1, 5.5, 6.5, 5.7, 5.4, 6.0),
    "안동": (6.0, 6.5, 6.5, 7.3, 7.2, 6.3, 4.8, 5.4, 5.0, 5.9, 5.5, 5.7, 6.0),
    "포항": (6.1, 6.3, 6.1, 7.1, 7.2, 6.1, 5.2, 5.5, 5.2, 6.2, 6.1, 6.1, 6.1),
    "군산": (4.8, 5.9, 6.2, 7.0, 6.9, 5.9, 4.8, 5.8, 6.2, 6.2, 5.0, 4.7, 5.8),
    "대구": (6.2, 6.6, 6.5, 7.3, 7.4, 6.1, 4.9, 5.3, 5.4, 6.6, 6.0, 6.1, 6.2),
    "전주": (4.9, 5.6, 6.0, 7.1, 7.0, 5.8, 4.4, 5.2, 5.6, 6.3, 5.2, 4.6, 5.6),
    "울산": (6.2, 6.3, 6.0, 6.9, 6.9, 5.8, 4.9, 5.4, 5.0, 6.2, 6.1, 6.3, 6.0),
    "창원": (5.8, 6.6, 6.1, 7.0, 6.6, 5.3, 4.4, 5.1, 5.3, 6.6, 6.0, 5.7, 5.9),
    "광주": (5.2, 5.9, 6.2, 7.1, 7.2, 5.6, 4.7, 5.6, 5.7, 6.6, 5.5, 5.0, 5.9),
    "부산": (6.4, 6.5, 6.2, 7.0, 7.2, 6.0, 5.3, 6.5, 5.6, 6.7, 6.5, 6.6, 6.4),
    "통영": (6.4, 6.9, 6.5, 6.9, 7.0, 5.8, 4.7, 6.1, 5.7, 6.8, 6.5, 6.7, 6.3),
    "목포": (4.6, 5.5, 5.9, 6.8, 7.0, 5.7, 5.1, 6.6, 6.0, 6.8, 5.5, 4.6, 5.9),
    "여수": (6.2, 6.7, 6.6, 7.2, 7.1, 5.8, 5.1, 6.3, 6.0, 7.0, 6.4, 6.4, 6.4),
    "흑산도": (3.1, 4.9, 6.0, 6.7, 6.2, 5.1, 3.7, 6.1, 6.0, 6.6, 5.0, 3.5, 5.2),
    "완도": (4.8, 5.6, 5.8, 6.8, 6.7, 5.3, 4.7, 5.9, 5.5, 6.6, 5.4, 4.8, 5.7),
    "제주": (2.3, 3.8, 5.1, 6.5, 6.8, 5.7, 6.3, 6.3, 5.4, 5.8, 4.2, 2.7, 5.1),
    "고산": (2.9, 4.5, 5.4, 6.5, 6.5, 5.3, 5.7, 7.0, 6.3, 6.7, 5.1, 3.5, 5.5),
    "성산": (4.0, 5.2, 5.5, 6.4, 6.6, 4.9, 5.1, 5.6, 5.2, 6.1, 5.2, 4.2, 5.3),
    "서귀포": (4.9, 5.5, 5.6, 6.4, 6.4, 4.8, 4.6, 5.9, 5.9, 6.7, 5.7, 5.2, 5.6),
    "진주": (6.2, 6.5, 6.3, 6.9, 6.7, 5.3, 4.9, 5.4, 5.3, 6.4, 5.8, 6.1, 6.0),
    "강화": (5.8, 6.7, 7.0, 7.8, 7.8, 7.4, 5.6, 6.5, 7.1, 7.1, 5.7, 5.4, 6.7),
    "양평": (5.5, 6.3, 6.6, 7.2, 7.5, 6.9, 5.3, 5.8, 6.3, 6.3, 5.2, 5.2, 6.2),
    "이천": (5.4, 6.0, 6.2, 7.0, 7.2, 6.2, 4.6, 5.1, 5.5, 6.1, 5.1, 5.1, 5.8),
    "인제": (5.2, 5.7, 6.2, 7.1, 7.2, 6.8, 5.1, 5.6, 5.9, 5.7, 4.7, 4.7, 5.8),
    "홍천": (5.2, 6.0, 6.3, 7.2, 7.3, 6.8, 5.1, 5.7, 5.9, 5.9, 4.9, 4.9, 5.9),
    "태백": (5.6, 6.2, 6.3, 7.3, 7.4, 6.5, 4.5, 4.7, 5.0, 6.1, 5.6, 5.5, 5.9),
    "제천": (5.3, 5.8, 6.2, 7.2, 7.5, 7.1, 5.2, 5.9, 5.9, 6.3, 5.1, 5.0, 6.0),
    "보은": (5.6, 6.4, 6.9, 7.8, 8.0, 7.3, 5.8, 6.3, 6.4, 6.7, 5.5, 5.3, 6.5),
    "천안": (5.5, 6.6, 7.0, 7.8, 8.0, 7.4, 5.9, 6.7, 6.6, 6.9, 5.5, 5.2, 6.6),
    "보령": (5.2, 6.4, 7.0, 7.9, 8.0, 7.4, 6.0, 7.1, 7.3, 7.3, 5.6, 5.0, 6.7),
    "부여": (5.8, 6.7, 7.2, 8.2, 8.3, 7.6, 6.3, 7.1, 7.1, 7.1, 5.7, 5.4, 6.9),
    "금산": (5.5, 6.3, 6.8, 7.7, 7.9, 7.1, 5.8, 6.2, 6.1, 6.3, 5.3, 5.1, 6.3),
    "부안": (5.3, 6.4, 7.0, 8.0, 8.2, 7.3, 6.6, 7.3, 7.2, 7.2, 5.7, 5.0, 6.8),
    "임실": (5.2, 6.2, 6.6, 7.7, 7.7, 6.4, 5.4, 6.0, 6.4, 6.8, 5.7, 5.0, 6.2),
    "정읍": (4.8, 5.8, 6.3, 7.5, 7.6, 6.5, 5.6, 6.3, 6.4, 6.7, 5.2, 4.6, 6.1),
    "남원": (5.1, 6.3, 6.5, 7.4, 7.2, 6.1, 5.1, 5.7, 6.0, 6.4, 5.4, 5.0, 6.0),
    "장수": (4.9, 6.1, 6.3, 7.3, 7.2, 6.0, 4.7, 5.0, 5.5, 6.1, 5.3, 4.7, 5.7),
    "순천": (4.8, 5.5, 5.9, 6.7, 6.6, 5.3, 4.4, 5.1, 5.0, 5.5, 4.7, 4.5, 5.3),
    "장흥": (4.9, 5.7, 6.1, 7.0, 7.0, 5.7, 4.7, 5.8, 5.6, 6.4, 5.4, 4.9, 5.7),
    "해남": (5.2, 6.1, 6.6, 7.5, 7.7, 6.6, 5.9, 7.2, 6.6, 7.1, 5.8, 5.2, 6.5),
    "고흥": (5.6, 6.3, 6.6, 7.5, 7.5, 6.4, 5.8, 6.8, 6.4, 7.1, 6.0, 5.7, 6.5),
    "봉화": (5.9, 6.4, 6.4, 7.5, 7.4, 6.6, 4.7, 5.3, 5.3, 6.1, 5.7, 5.8, 6.1),
    "영주": (6.2, 6.9, 7.1, 8.0, 8.3, 7.5, 5.5, 6.1, 6.3, 6.9, 6.0, 5.9, 6.7),
    "문경": (5.8, 6.6, 6.8, 7.8, 8.1, 7.2, 5.4, 6.1, 6.2, 6.9, 5.7, 5.4, 6.5),
    "영덕": (6.7, 7.0, 7.0, 8.1, 8.2, 7.2, 6.3, 6.8, 6.4, 7.0, 6.5, 6.6, 7.0),
    "의성": (5.7, 6.3, 6.5, 7.4, 7.6, 6.7, 5.2, 5.6, 5.3, 6.0, 5.4, 5.5, 6.1),
    "구미": (5.4, 6.2, 6.4, 7.5, 7.6, 6.6, 5.5, 5.8, 5.7, 6.3, 5.3, 5.1, 6.1),
    "영천": (5.5, 6.4, 6.6, 7.4, 7.5, 6.6, 5.6, 6.0, 5.6, 6.4, 5.3, 5.1, 6.2),
    "거창": (6.2, 6.9, 7.0, 7.8, 7.9, 6.8, 5.7, 5.9, 5.7, 6.5, 5.8, 5.9, 6.5),
    "합천": (6.1, 6.6, 6.6, 7.3, 7.3, 6.1, 5.2, 5.7, 5.7, 6.5, 5.8, 5.9, 6.2),
    "밀양": (6.2, 6.5, 6.6, 7.3, 7.4, 6.2, 5.2, 6.0, 5.5, 6.7, 6.0, 6.1, 6.3),
    "산청": (5.6, 6.4, 6.7, 7.5, 7.5, 6.3, 5.5, 5.7, 5.6, 6.4, 5.5, 5.2, 6.1),
    "거제": (5.3, 6.4, 6.5, 7.2, 7.5, 6.2, 4.8, 5.9, 5.8, 6.7, 5.5, 5.4, 6.1),
    "남해": (6.3, 6.8, 6.9, 7.5, 7.6, 6.5, 5.7, 6.4, 6.1, 7.2, 6.4, 6.3, 6.6),
}


def monthly_sunshine(region: str) -> Optional[tuple]:
    """[표 3-3-45] 조회 — (1월…12월, 연평균) 일평균 일조시간 h/일. 없으면 None.

    지역명은 **기상관측지점명**이다. 이 표는 '창원'을 쓴다([표3-3-44]만 '마산').
    """
    return MONTHLY_SUNSHINE_HOURS.get(region)


def period_load_adjust_k(sunshine_h: float) -> dict:
    """[표 3-3-36] 조회 — 일평균 일조시간에 따른 기간난방부하 조정계수 k.

    **보간하지 않는다.** 원문이 3.0/4.5/6.0/7.5/9.0h 5점만 주므로 정확히 일치할
    때만 값을 주고, 아니면 value=None과 인접 2점을 돌려준다(호출부가 정한다).

    `ratio_vs_current`는 k / PERIOD_LOAD_K_NO_SUNSHINE — 현행 엔진 기간난방부하에
    곱하면 원문 식(3-3-5)이 되는 배율이다(유리 케이스 검산으로 확인된 관계).
    """
    pts = sorted(PERIOD_LOAD_ADJUST_K)
    if sunshine_h in PERIOD_LOAD_ADJUST_K:
        k = PERIOD_LOAD_ADJUST_K[sunshine_h]
        return {"sunshine_h": sunshine_h, "k": k,
                "ratio_vs_current": k / PERIOD_LOAD_K_NO_SUNSHINE}
    lo = max([p for p in pts if p < sunshine_h], default=None)
    hi = min([p for p in pts if p > sunshine_h], default=None)
    return {"sunshine_h": sunshine_h, "k": None,
            "reason": f"원문이 {pts}h 5점만 제시 — 보간은 근거 없는 값이라 하지 않는다",
            "lower": None if lo is None else {"sunshine_h": lo, "k": PERIOD_LOAD_ADJUST_K[lo]},
            "upper": None if hi is None else {"sunshine_h": hi, "k": PERIOD_LOAD_ADJUST_K[hi]}}


# ─────────────────────────────────────────────────────────────
# 🔴 2026-09-13 101차 — `HEATING_SAFETY_FACTOR=1.1`의 출처 확정 + 3성분 비중 확보
#   (작업지시서 14절 B3 종결 · B5 정량화. 값 변경 0)
#   83차가 "정체 후보 발견, 출처 미상"으로, 96차가 "개념은 풍속보정계수와 별개임을
#   확정했으나 값 출처는 여전히 미상"으로 남긴 항목이다. 원문이 본문으로 답한다 —
#   표가 아니라 서술이었다.
#
#   `에너지절감과생산성향상을위한신개념온실설계및표준화연구.pdf`
#     **PDF p.389 / 인쇄 353**:
#       "**온풍난방의 설치용량은 최대난방부하에 10%의 안전계수를 적용**하며, 덕트를
#        이용하여 공기분산이 필요하므로 … **온수난방의 설치용량은 최대난방부하에
#        20∼30%의 안전계수를 적용**하며, 배관방식이 중요한 설계요소가 된다."
#     **PDF p.377 / 인쇄 341**(교차 확인):
#       "난방기 용량 산정 시 **0.1∼0.3의 안전계수**를 적용하므로"
#
#   ✅ **이 엔진의 대상은 등유 온풍난방기**(16회차 F1 확정)이므로 **1.1이 정확히 맞다.**
#      `HEATING_SAFETY_FACTOR`는 더 이상 [추정]이 아니다 — status를 공공기준으로 올린다.
#   📌 96차가 원문에서 읽은 "난방방식에 따른 안전계수"의 실체가 이것이다(표가 아니라 본문).
#      같은 문장이 "공기분산방식"(온풍 덕트)·"난방배관방식"(온수 배관)도 **설계요소**로
#      말할 뿐 별도 계수표를 주지 않는다 — 14절 B6의 "표 미발견"은 **표가 없어서**였다.
# ─────────────────────────────────────────────────────────────
HEATING_SAFETY_FACTOR_BY_METHOD = {
    "온풍난방": (1.1, 1.1),      # 원문 "10%"
    "온수난방": (1.2, 1.3),      # 원문 "20∼30%"
}

# ─────────────────────────────────────────────────────────────
# [표 3-3-51] 실내외 기온차 그룹별 전체 난방부하의 구성 비율(%)
#   PDF p.378 / 인쇄 342 — **평균 3열만** 전사했다(그룹 5행 + 계). 값은 (관류,
#   틈새환기, 지중) **평균** %다. ⚠️원문은 3성분 각각에 **표준편차 열**을 함께 준다
#   (그룹1 관류 95.6/SD 2.64 · 틈새 6.5/2.97 · 지중 −2.1/1.93 …) — **6행×3열을 전사하지
#   않았다**. 변동폭이 필요하면 원문을 볼 것(101차 레드팀 F5).
#   본문(PDF p.377/인쇄 341) 요약: "관류열부하가 88.7∼95.6%, 틈새환기전열부하가
#   6.5∼9.6%, 지중전열부하가 –2.1∼1.7% … 전체적으로는 관류 92%, 틈새 9%, 지중 –1%".
#   전사 검산: **계 행 91.9 + 8.6 + (−0.5) = 100.0 정확히 닫힌다.**
#
#   🔴 **84차가 남긴 구조적 공백(14절 B5)이 이 표로 정량화된다.**
#     `heating_load()`는 **관류열부하만** 계산하므로 원문 기준 **전체의 91.9%**만 잡는다.
#     누락 몫은 틈새환기 8.6%p + 지중 −0.5%p = **8.1%p**이고, **과소율은 그 값이 아니라
#     1/0.919 − 1 = 8.8%**다(⚠️%p와 %를 섞지 말 것 — 101차 초판이 둘을 혼용했다:
#     레드팀 F4). 보정하면 uminjae 238,776 → **259,822 kcal/h**.
#     ⚠️ 실내외 기온차 그룹에 따라 관류 비중이 95.6%(그룹1) ~ 88.7%(그룹5)로 달라진다 —
#        단일 보정계수로 접으면 그 변동을 지운다.
#   ⚠️ **보정하지 않았다** — 케이스 최대난방부하·난방기 용량이 약 8% 올라가고, 이는
#     99차(U_DESIGN −36%)와 반대 방향이라 **합성 효과를 사용자가 보고 정해야 한다**.
#     ★사용자 결정. 값 변경 0.
#   📌 원문이 함께 적는 비교 기준(일본시설원예협회 2007): 관류 60∼100% · 틈새 0∼20% ·
#     지중 −20∼20%. 단 원문은 "그 기준을 본 실험온실(1.2ha)에 그대로 적용하면 지중이
#     −28∼20%로 과대평가된다"며 **대형 온실에서는 자기 방식(외주부 열손실)을 권한다**.
# ─────────────────────────────────────────────────────────────
HEATING_LOAD_COMPONENT_SHARES_PCT = {
    1: (95.6, 6.5, -2.1),
    2: (93.0, 8.1, -1.1),
    3: (91.4, 9.3, -0.7),
    4: (90.1, 9.7, 0.3),
    5: (88.7, 9.6, 1.7),
    "계": (91.9, 8.6, -0.5),
}


def transmission_share_pct(group=None) -> float:
    """[표 3-3-51] 관류열부하가 전체 난방부하에서 차지하는 비율(%).

    group=None이면 원문 '계' 행(91.9%)을, 1~5를 주면 그 실내외 기온차 그룹 값을
    돌려준다. **엔진 `heating_load()`가 잡는 몫이 이만큼**이라는 뜻이다 —
    나머지(틈새환기·지중)는 84차 이후 여전히 미산정이다(14절 B5).

    ⚠️ 이 값으로 보정하지 않는다. 보정은 케이스 값을 약 8% 움직이는 ★사용자 결정이다.
    """
    key = "계" if group is None else group
    if key not in HEATING_LOAD_COMPONENT_SHARES_PCT:
        raise ValueError(
            f"그룹은 1~5 또는 None(계)이어야 한다: {group!r}")
    return HEATING_LOAD_COMPONENT_SHARES_PCT[key][0]


# 와트 → kcal/h 환산 (85차 신설). 원문 온실열손실저감및차단기술연구 p.12가
#   "1W=0.86kcal/h 인 점을 고려하여"로 명시한 관행 환산값이다(정확값 0.859845).
#   ⚠️ 필요한 이유: **원문 난방부하 식 체계는 SI(W)인데 이 엔진은 kcal/h**다.
#   특히 지중전열부하의 F는 원문이 **W/m·℃**로 준다 — 환산 없이 관류열부하(kcal/h)와
#   더하면 단위가 섞인다(84차 구현의 실제 결함, 85차에 수식 원문 확인 중 발견).
W_TO_KCAL_PER_HOUR = 0.86

# 공기 비열 (kcal/kg·℃)
#   ✅ 85차 수식 원문 확인(페이지 렌더 열람): 정밀계측 보고서 p.62는 값 0.24를 쓰면서
#     단위를 "J/kg℃"로 적고, 1차 출처(신개념온실 p.345)도 c_p를 "J/kg℃"로 라벨한다.
#     그러나 **0.24는 J 값이 아니다** — 0.24 kcal/kg·℃ × 4,186.8 = 1,004.8 J/kg·K로
#     표준 공기 정압비열과 일치한다. 즉 **원문의 단위 라벨이 오기**이고 값은 kcal 계열이다.
#     1차 출처는 c_p의 **수치를 제시하지 않아** 이 판정과 충돌하지 않는다.
#   ⚠️ 공기 **밀도**는 상수로 두지 않는다 — 정밀계측 p.62가 "1 kg/m³"로 명시하는데
#     (85차 렌더 확인: 추출 결손이 아니라 **원문 그대로 1**이다 — 84차 주석의
#     "소수점이 떨어졌을 가능성"은 정정한다) 상온 공기 물리값 약 1.2와 다르다.
#     어느 쪽을 쓸지는 호출부가 정한다(근거 없는 값 금지).
AIR_SPECIFIC_HEAT_KCAL_KG_C = 0.24


@dataclass
class HeatingLoadComponents:
    transmission_kcal_h: float              # 관류열부하 — heating_load() 결과 그대로
    infiltration_kcal_h: Optional[float]    # 틈새환기전열부하
    ground_kcal_h: Optional[float]          # 지중전열부하
    wind_factor: float
    total_kcal_h: Optional[float]           # 3성분이 모두 있을 때만. 아니면 None
    partial_total_kcal_h: float             # 계산된 성분만 합 × 보정계수
    missing: list                           # 빠진 성분과 그에 필요한 입력
    basis_note: str


def wind_correction_factor(winter_mean_wind_ms: float, has_thermal_screen: bool) -> float:
    """[표 3-3-35] 조회. 강풍지역은 동절기 평균풍속 3.0m/s 이상(원문 주석).
    판정이 아니라 표 조회다 — 조건을 주면 계수를 돌려줄 뿐이다."""
    region = "강풍지역" if winter_mean_wind_ms >= WIND_STRONG_THRESHOLD_MS else "일반지역"
    cover = "보온피복" if has_thermal_screen else "단일피복"
    return WIND_CORRECTION_FACTOR[(region, cover)]


def heating_load_components(
        transmission_kcal_h: float,
        t_target: float, t_min: float,
        volume_m3: Optional[float] = None,
        infiltration_per_hour: Optional[float] = None,
        air_density_kg_m3: Optional[float] = None,
        perimeter_m: Optional[float] = None,
        ground_loss_coef_w_m_c: Optional[float] = None,
        ground_base_dt: Optional[float] = None,
        wind_factor: float = 1.0) -> HeatingLoadComponents:
    """원문 식(3-3-1)의 3성분 구조로 최대난방부하를 조립한다.

      최대난방부하 = (관류 + 틈새환기 + 지중) × 풍속보정계수

    transmission_kcal_h: `heating_load().max_load_kcal_h`를 그대로 넘긴다 —
      관류열부하를 여기서 다시 계산하지 않는다(단일 출처 유지).

    틈새환기전열부하 H_V = ρ_i·c_p·N·V·(T_i − T_o)  ← 원문 식(3-3-3), 85차 확정
      ⚠️ 원문 체계는 SI(c_p J/kg℃ · N 회/s → W)인데 이 엔진은 kcal/h다. 여기서는
      **c_p kcal/kg·℃ · N 회/h**로 일관되게 옮겨 결과가 곧 kcal/h가 되게 했다
      (차원 확인 완료). 원문 c_p 라벨의 오기는 AIR_SPECIFIC_HEAT_KCAL_KG_C 주석 참고.
      → volume_m3 · infiltration_per_hour · air_density_kg_m3 셋이 다 있어야 계산한다.
        환기율은 `INFILTRATION_RATE_PER_HOUR`가 온실 종류별 **범위**를 준다.
    지중전열부하 H_S = F·L_s·(ΔT − Θ)   ← 원문 식(3-3-4), 85차에 페이지 렌더로 확정
      → perimeter_m · ground_loss_coef_w_m_c · ground_base_dt 셋이 다 있어야 계산한다.
        Δt가 기준온도차 이하면 지중열류 방향이 바뀌므로 0으로 둔다(음수 부하 금지 —
        이 절삭은 원문에 없는 구현 판단이다).
        ⚠️ F의 단위가 **W/m·℃**라 결과가 W다 — 내부에서 W_TO_KCAL_PER_HOUR로 환산해
        관류열부하(kcal/h)와 더한다. 84차 구현은 이 환산이 빠져 단위가 섞여 있었다.

    **없는 입력을 지어내지 않는다** — 못 구한 성분은 None이고 `missing`이 무엇이
    필요한지 적는다. `total_kcal_h`는 3성분이 다 있을 때만 채워지고, 그 전까지는
    `partial_total_kcal_h`(구한 것만 합산)를 쓴다. 둘을 구분하는 이유는 부분합을
    완전한 최대난방부하로 오독하면 **과소산정**이 되기 때문이다.
    """
    dt = t_target - t_min
    missing = []

    infiltration = None
    if all(v is not None for v in (volume_m3, infiltration_per_hour, air_density_kg_m3)):
        infiltration = (air_density_kg_m3 * AIR_SPECIFIC_HEAT_KCAL_KG_C
                        * infiltration_per_hour * volume_m3 * dt)
    else:
        missing.append("틈새환기전열부하: volume_m3·infiltration_per_hour·"
                       "air_density_kg_m3 필요(환기율은 INFILTRATION_RATE_PER_HOUR 참고)")

    ground = None
    if all(v is not None for v in (perimeter_m, ground_loss_coef_w_m_c, ground_base_dt)):
        # 원문 F는 W/m·℃라 결과가 W다 — kcal/h 체계로 환산해 더한다(85차 정정).
        ground = (ground_loss_coef_w_m_c * perimeter_m * max(dt - ground_base_dt, 0.0)
                  * W_TO_KCAL_PER_HOUR)
    else:
        missing.append("지중전열부하: perimeter_m·ground_loss_coef_w_m_c·ground_base_dt "
                       "필요(계수는 GROUND_LOSS_COEF 참고 — 단위 W/m·℃)")

    parts = [transmission_kcal_h] + [x for x in (infiltration, ground) if x is not None]
    partial = sum(parts) * wind_factor
    total = partial if not missing else None
    note = ("원문 식(3-3-1) 3성분 구조 — 신개념온실설계및표준화연구 p.344. "
            "관류열부하는 heating_load() 결과를 그대로 받는다(재계산 아님). "
            "⚠️미입력 성분은 지어내지 않고 None으로 둔다 — partial_total을 완전한 "
            "최대난방부하로 읽으면 과소산정이다.")
    return HeatingLoadComponents(
        transmission_kcal_h=transmission_kcal_h, infiltration_kcal_h=infiltration,
        ground_kcal_h=ground, wind_factor=wind_factor, total_kcal_h=total,
        partial_total_kcal_h=partial, missing=missing, basis_note=note)


# ─────────────────────────────────────────────────────────────
# 🔴 A-12 실측 대조 기준 (2026-09-13 105차 — 상수 승격 + 조사. 값 변경 0)
#   104차 레드팀 F6이 "세 케이스 전부 기준의 41~57%"라며 연 질문을 조사했다.
#
#   ⚠️ **첫 발견은 감사 사각이었다**: 231·180은 `verify_heating_vs_actual()` 안에
#     **하드코딩된 리터럴**이라 레지스트리에 없었고, 따라서 **대조가능성 감사 게이트가
#     볼 수 없는 값**이었다(72·74차가 같은 패턴을 고친 적이 있다). 상수로 승격한다.
#
#   ⚠️ **원문서가 없다**: A-12는 `SmartFarm_엔진데이터.md`의 항목인데 그 파일이
#     **리포에 존재하지 않는다**(A-4/A-5와 같은 상황 — 레지스트리가 "원문서 미확보"로
#     적어 온 그 문서다). 즉 이 엔진의 "실측 이중검증"은 **출처를 열어볼 수 없는 값**으로
#     이뤄지고 있다. status는 `확인요망`이다.
#
#   🔴 **조사 결과 — 이 기준은 99차가 버린 값 쪽을 가리킨다**:
#     A-12를 맞추려면 `u_design`이 얼마여야 하는지 역산했다(현행 식 그대로,
#     바닥면적 분모·ΔT·fr 케이스값 사용).
#         chuncheon  필요 9.23   (현행 5.3)
#         uminjae    필요 9.98   (현행 5.7 · 99차 이전 8.9)
#         wonchaewon 필요 12.81  (현행 5.3)
#     → 필요치 **9~13**은 Diop 핫박스 고풍속 대역(8.9~10.4W → 8.9 kcal)과 **같은 쪽**이고,
#       99차가 채택한 국내 표준표 1중피복 대역(5.3~5.7)과는 어긋난다.
#     **이것은 99차 결정에 대한 반대 신호다** — 기록한다(값은 바꾸지 않는다).
#
#   ⚠️ **그러나 반대 신호를 판정으로 읽으면 안 된다**: 231/180이 **어떤 조건**에서 나온
#     값인지 알 수 없다(원문서 부재). 분모가 바닥면적인지 피복면적인지, ΔT·보온커튼
#     전개 여부가 무엇인지, 3성분을 포함하는지, 난방기 용량(×safety) 기준인지 —
#     어느 하나만 달라도 역산치가 크게 움직인다. 예: fr=1.0(커튼 미전개 극한) 가정이면
#     필요치가 6.46/6.99/8.97로 내려오고, 3성분 포함(÷0.919)이면 8.48/9.17/11.77이다.
#   📌 그래서 이 지표는 **자릿수 검증 전용**이고(대역 0.35~1.8), 함수 도크스트링이
#     처음부터 그렇게 적어 왔다. 104차가 관찰한 0.89→0.57도 **악화로도 개선으로도
#     읽을 근거가 없다** — 기준의 조건을 모르기 때문이다.
#   → **A-12 원문서 확보가 이 항목의 차단점**이다(14절 B1과 같은 성격: 리포 밖).
# ─────────────────────────────────────────────────────────────
HEATING_VERIFY_REF_KCAL_H_M2 = {"유리": 231.0, "기타": 180.0}
HEATING_VERIFY_RATIO_BAND = (0.35, 1.8)


def verify_heating_vs_actual(load_per_m2: float, cover: str) -> dict:
    """A-12 실측 기준과의 이중검증 — **자릿수 오류(10배·0.1배)를 잡는 용도다.**

    ⚠️ 정밀 일치 검증이 아니다. 기준값 231/180의 **측정 조건이 확인되지 않았고**
    (A-12 원문서 미확보, 105차) 실측은 설계외기온·목표온도·보온비에 따라 크게
    변동하므로 대역이 0.35~1.8로 넓다. **비율의 이동을 품질 신호로 읽지 말 것** —
    105차 조사가 그 근거를 위 블록 주석에 적어 뒀다.
    """
    ref = HEATING_VERIFY_REF_KCAL_H_M2["유리" if cover == "유리"
                                       else "기타"]
    ratio = load_per_m2 / ref
    lo, hi = HEATING_VERIFY_RATIO_BAND
    status = "정상" if lo <= ratio <= hi else "재확인(입력 외기온·보온비 점검)"
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
# ✅ 성격 규명(2026-08-17 P1-10, 상세는 레지스트리): 이 표는 "양액·난방·전기 제외,
#   제경비(일반관리비·이윤·부가세) 제외, 온실건축(재배동+관리동) 순공사원가" 계열로
#   판정 — 품셈 보고서(2021)의 온실품셈 0101 환산값(비닐 446,532·유리 568,824원/평)과
#   3~4% 오차 정합. 품셈 표준품셈(1,160,000원/평+)과의 2.4~3배 괴리는 설비 3종
#   포함(×1.61)·제경비(×1.39)·표준품셈 과다계상(×1.17)의 곱으로 완전 분해됨(잔차 4%).
#   따라서 방법A 결과를 "풀패키지 총사업비"로 읽으면 안 된다 — 설비 포함 총액 개산이
#   필요하면 ×1.6 안팎(실측·견적 12건 표본 329k~889k원/평과 정합)은 별도 판단으로 얹을 것.
# ✅ 원출처 확보(2026-08-19 69차, 사용자 지시 "TOTAL_PYEONG_PRICE 재조사"):
#   `E:/이암허브/2025/스마트팜견적타당성/(최종)온실 선정 및 비용 견적 프로그램.xlsx`
#   [골조예상비용] 시트 — 제목 "하우스 공사 예상비용(골조)", 출처 라벨 **"내재해형 고시"
#   예정공사비 / (사)한국농업시설협회(akaf.or.kr)**. 표 33종 전량 전사, `총금액÷평수=평단가`
#   검산 33/33 재현. 기존 4종은 원표와 원단위 일치했고, **10-연동-2(랙피니언식 천창개폐,
#   653,651원/평)가 원표에 있는데 누락돼 있어 추가**(같은 10-연동이라도 권취식 572,614 →
#   랙피니언식 653,651로 +14.2% — 개폐 방식이 단가를 가르는 신호). 단동 19·광폭 6·과수 3종도
#   함께 편입해 4종 → 33종.
#   ⚠️ 협회 원표·고시 원문 자체는 미확보(사이트 인증서 만료로 접근 실패) — 이 상수는
#   **2차 자료(견적 프로그램) 전사**이며 "예정공사비가 어느 공종까지 포함하는가"는
#   [확인요망]으로 남는다. 상세: 근거_내재해형고시_예정공사비_20260819.md
#   ⚠️ 평 환산 기준 차이(13회차 F6): 원표 평수 열은 면적÷**3.3**㎡/평으로 재현되나
#   엔진 m2_to_py는 3.3058을 쓴다 — 같은 면적에 이 단가를 곱하면 약 -0.175%
#   계통 과소. 개산 용도에선 무시 가능하나 원표 총금액과 원단위 대조 시엔 주의.
#   ⚠️ 47차 P1-10 판정("설비·제경비 제외 온실건축 순공사원가")과 실측이 어긋난다 —
#   69차 CAPEX 표본 12건(면적 확보 9건) 역산 결과 연동 5종(10-연동-2 포함)은 "구조만" 밴드
#   (174,919~365,620원/평) 밖에 전부 있고 직접공사비 전체 밴드(265,574~663,813)에는 5종 모두
#   들어온다. 원표 공종 내역 미확보라 성격 확정은 보류하고 관측 사실만 기록(69차 범위 결정).
TOTAL_PYEONG_PRICE = {
    # 연동
    "07-연동-1": 430465,  # (1-2W)
    "08-연동-1": 389990,  # (2스팬 벤로형)
    "10-연동-1": 572614,  # (1-2W형, 권취식 천창개폐)
    "10-연동-2": 653651,  # (1-2W형, 랙피니언식 천창개폐)
    "12-연동-1": 584794,  # (1-2W형)
    # 단동
    "07-단동-1": 60345,
    "07-단동-2": 100176,
    "07-단동-3": 93524,
    "07-단동-4": 99298,
    "10-단동-1": 90718,
    "10-단동-2": 85485,
    "10-단동-3": 87495,
    "10-단동-4": 92556,
    "10-단동-5": 90477,
    "10-단동-6": 209296,
    "10-단동-7": 201363,
    "10-단동-8": 238099,
    "10-단동-9": 233782,
    "10-단동-10": 97516,
    "10-단동-11": 88648,
    "10-단동-12": 100818,
    "10-단동-13": 90171,
    "07-단동-18": 105490,
    "12-단동-1": 108632,
    # 광폭
    "13-광폭(보온재)-1": 225187,
    "13-광폭(보온재)-2": 234682,
    "13-광폭(보온재)-3": 232013,
    "13-광폭(보온재)-4": 229113,
    "13-광폭(보온재)-5": 218560,
    "13-광폭(보온재)-6": 216886,
    # 과수
    "07-포도-1": 191081,
    "10-포도-1": 226129,
    "08-감귤-1": 211928,
}
# A-8 골조 단독 단가(원/평) — 공종상세용(방법 B). 2026-07: 우민재 공사내역서의
# "0103.철골공사" 실측 163,470원/평과 오차 0.04%로 거의 정확히 일치 확인.
STRUCTURE_ONLY_PYEONG = 163400


def _a2_key(spec_name: str) -> Optional[str]:
    """SPEC_TABLE 이름(2025-108호, 번호 2자리 zero-pad: "07-연동-01") ↔ A-2 원표
    키(번호 1자리: "07-연동-1")의 표기 차이만 흡수한다. 69차 레드팀 13회차 F2로
    발견: 이 정규화가 없으면 유일 호출부(chosen.name은 SPEC_TABLE에서 옴)에서
    33키 중 5키만 도달 가능했다(연동은 0종). 정규화 후 18/33 도달 — 연동 5종은
    전부 포함되고, 나머지 15종(단동 대부분·광폭·과수)은 SPEC_TABLE(2025-108호)에
    아예 없는 구형·타계열 규격이라 도달 불가가 정상이다.
    ⚠️ 번호 표기만 맞추는 것이지 "두 표의 같은 코드가 같은 규격"임을 검증한 것은
    아니다[확인요망] — 둘 다 내재해형 고시 계열 코드라 대응 개연성이 높다는 근거뿐."""
    if spec_name in TOTAL_PYEONG_PRICE:
        return spec_name
    m = re.match(r"^(.*-)(\d+)$", spec_name)
    if m:
        cand = f"{m.group(1)}{int(m.group(2))}"      # 07-연동-01 → 07-연동-1
        if cand in TOTAL_PYEONG_PRICE:
            return cand
    return None


def greenhouse_total_estimate(spec_name: str, area_py: float) -> Optional[float]:
    """방법 A: 온실 전체 개산 = A-2 평단가 × 면적. (골조 단독 아님!)"""
    key = _a2_key(spec_name)
    p = TOTAL_PYEONG_PRICE.get(key) if key else None
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
    ("auto_opening_system", "2. 자동개폐 시스템", "천창, 수평·측면스크린, 보온커튼, 개폐모터 — 환경 자동화 설비(보온커튼 소속은 2026-08-17 사용자 결정: 우민재 방식 통일)"),
    ("hvac", "3. 냉·난방 설비", "보일러, 히트펌프, 송풍기, 난방배관 — 에너지 효율 핵심 설비"),
    ("irrigation_fertigation", "4. 양액·관수 설비", "양액기, 펌프, 관수 배관, 폐양액 처리 — 작물 생장 핵심 제어 설비"),
    ("ict_control", "5. ICT 및 제어설비", "복합환경제어기, 센서, 서버, 소프트웨어 — 스마트팜의 제어 두뇌 역할"),
    ("electrical", "6. 전기 설비", "전기 인입, 배선반, 조명, 분전함 등 — 전력 공급 인프라"),
    ("auxiliary_facility", "7. 부대시설", "기계실, 창고, 출입구, 작업동 등 — 생산 보조 공간"),
    ("thermal_storage_insulation", "8. 축열·보온 설비", "축열탱크, 단열판 등 — 난방비 절감 요소(보온커튼은 자동개폐 시스템으로 분류: 2026-08-17 사용자 결정)"),
    ("equipment_procurement", "9. 기자재 구매", "트롤리, 컨베이어, 선별대 등 — 생산성 향상 보조 장비"),
    ("design_supervision_fee", "10. 설계·감리비", "기본·실시설계, 감리 용역비 등 — 설치의 행정·기술 지원"),
    ("site_preparation", "11. 부지 조성비", "성토, 배수로, 석축, 진입로 등 — 시설 설치 위한 기반 공사"),
    ("contingency", "12. 예비비", "물가변동, 오차 대응용 2~5% — 불확실성 대비"),
    ("land_acquisition", "13. 부지 매입비", "토지 구입비 — 자산이지만 감가상각 제외(finance()의 land_cost로 별도 처리)"),
]

# 근거 상태 — 2026-07-16 기준 우민재·최혁진 원문 대조 결과. 근거 없는 항목은
# 값을 만들지 않고 0 + 미검증으로 남긴다(다음 문서 확보 시 갱신).
# 상태 어휘 3종(2026-08-16, P1-6 결정): "실측" = 실제 케이스 지출액 대조 완료.
# "미검증" = 근거문서 자체가 없음. "참고요율(법정기준)" = 실제 지출액이 아니라
# 법정/공식 요율표 — 개별 케이스 실측과는 성격이 달라 그대로 "실측"으로 승격하면
# 안 되지만, 근거가 아예 없는 "미검증"과도 다르다(케이스 개산에 참고 가능).
CAPEX_MAJOR_EVIDENCE_STATUS = {
    # 2026-08-18 51차 레드팀(4회차) F2·F3: 건수 표기가 이두희(07-21)·윤성호(08-17) 추가 이후
    # 누적 미갱신 상태였음을 발견 — CAPEX_MAJOR_CASE_CHUNKS의 실제 0 아닌 값 기준으로 전면 현행화.
    # 이후 표본 추가 차수는 이 건수도 같은 차수에 동기한다(52차 이준희~61차 구창회 — 12표본).
    "greenhouse_structure": "실측(14건: 우민재·최혁진·이두희·윤성호·한일그린텍·이준희·맹주연·강정구·백가은·조윤정·박규현·구창회·한수진·최선동·임미라 — 오기수는 설비 전용 "
                            "부분 범위 견적이라 골조·피복 품목 전무(0))",
    "auto_opening_system": "실측(15건: 전 표본 — 보온커튼·스크린은 구동부와 함께 "
                           "이 카테고리 소속으로 확정, 2026-08-17 사용자 결정(우민재 방식 통일). "
                           "종전 표기 '모터·보온재 미분리'는 문제가 아니라 관례로 승격. 박규현 170,837,702는 마그마 "
                           "동력피복제어기 24,000,000 포함 — 구동 제어반 계열 최대 관측. ⚠️91차가 이 자리를 최선동 9,500,000원으로 "
                           "교체했다가 레드팀 F1로 철회했다(같은 파일의 박규현 주석이 24,000,000을 단일 라인 최대로 "
                           "이미 기록 중이라 한 파일이 두 최대치를 주장하게 됐다). 91차 추가분 최선동 '콘트롤박스 "
                           "천창10단자' 9,500,000원은 **'콘트롤박스·하우스콘트롤' 명칭 계열 안에서만** 최대다 — "
                           "한일그린텍 7,434,000·구창회 7,153,738·맹주연 5,400,000·임미라 복합40호기 5,000,000·"
                           "한수진 4,500,000·강정구 3,800,000)",
    "hvac": "실측(10건: 우민재·최혁진·윤성호·이준희[유동휀만 — 난방설비는 '본 공사제외']·맹주연[유동팬 42대·환풍기 "
            "6대·설치노무 — 010108 혼재 공종에서 명시 라인 분리]·백가은·조윤정[환기+난방+근권배관 36,744,300 — 난방 계열 "
            "독립 공종 수 최다(3개), 금액·비중은 표본 4위]·박규현[전기 공종 내 실물 팬 세트 3,090,400 분리 — 배기휀 4대·"
            "유동휀 24대]·한수진[🔴표본 최초의 냉방 실측 — 블라젠 냉난방기 삼상8마력 3대 31,500,000(공간)+냉온수기 2대 "
            "22,000,000(근권), 91차]·최선동[동일 업체·동일 구성, 안개분무시설 18,500,000은 공종명이 '무인방제기'라 hvac 제외·"
            "unclassified — 귀속 미확정[확인요망], 감응 3.7%p]·임미라[히트펌프 블록 수냉식온수기 8마력3상 3대 27,000,000 등, "
            "축열조탱크는 8번으로 라인분리] — 이두희·한일그린텍·강정구·오기수·구창회는 견적 범위에 난방설비 자체가 없어 0. "
            "한일그린텍·구창회(동일 업체 1·2호 현장)는 유동휀·환풍기가 실재하나 '환급금 재투자' 블록이라 직접공사비 분모 밖, "
            "강정구·오기수는 부분 범위 견적[각각 골조 쪽만·설비 쪽만 — 오기수는 유동휀·배기휀 '단자'만 예비])",
    "irrigation_fertigation": "실측(14건: 우민재·최혁진·이두희·윤성호·한일그린텍·이준희·맹주연·오기수·백가은·조윤정·박규현·구창회·한수진·최선동·임미라 — 강정구는 부분 범위 "
                              "견적이라 관수·양액 품목 전무(0))",
    "ict_control": "실측(6건: 최혁진·이두희·윤성호·이준희·오기수·임미라[91차 — SUNNET 관제씨스템 9,200,000+통합모니터 S/W+우적·일사량·풍향풍속·온습도 센서 일체 15,230,000, 국산이나 마그마 3건(17.9~26.2M)보다 낮은 대역] — 우민재·한일그린텍·맹주연·강정구·백가은·조윤정·박규현·구창회·한수진·최선동은 독립 환경제어시스템 라인 없음(0). ⚠️[확인요망] 한수진(콘트롤박스 4,500,000)·최선동(콘트롤박스 천창10단자 9,500,000)은 **둘 다** 금액 0인 단자 명세에 '일사량,기상대'가 동일하게 적혀 있으나 별도 센서 품목·금액 라인이 없어 구동 제어반으로 유지했다 — ict 이동 가정 감응 한수진 0.90%p·최선동 1.91%p(91차는 한수진에만 캐비엇을 달았는데 원문 조건이 같고 감응도 최선동이 크다: 레드팀 F3 정정). — 구창회 하우스콘트롤 7,153,738원은 1호 7,434,000원 동계열 개폐 접점 제어반(감응 1.89%p): "
                   "한일그린텍 하우스콘트롤 7,434,000원·맹주연 컨트롤박스 5,400,000원·강정구 콘트롤박스[환경제어용] "
                   "3,800,000원은 구동 제어반이라 자동개폐 소속(강정구는 명칭에 '환경제어'가 있으나 실체는 천창·커튼· "
                   "측창 구동 단자 통합 — 센서·복합제어 라인 부재). 이준희 83,463,440원은 표본 최대 관측치 — 원인은 "
                   "제어기 브랜드/패키지(PRIVA Compact CC 80,000,000원이 95.85%, 기존 3건은 국산 마그마 계열 — "
                   "54차 5회차 F1 귀속 정정). 오기수 40,000,000원은 한글 '프라바 오피스·컴팩' 표기로 PRIVA(프리바) "
                   "계열 [추정](라틴 표기 없음 — 이준희의 라틴 리터럴과 근거 등급 상이, 8회차 F2). 비교 시 집계 레벨 "
                   "주의: 오기수 40M은 공종 총액(PC·센서 번들), 이준희 80M은 공종 내 단일 제어기 라인 — 같은 축의 "
                   "밴드 아님. 오기수 컨트롤박스설치 내 환경제어복합기 등 900,000은 독립 ict 공종 별존을 논거로 "
                   "자동개폐 유지(8회차 F3 — 이동 가정 감응 ±0.5%p))",
    "electrical": "실측(4건: 최혁진·윤성호·이준희·박규현[전기 공종 잔여 2,832,665 — 케이블·잡자재·인건비, 공종의 제어기·팬은 "
                  "실체 분리] — 우민재·이두희·한일그린텍·맹주연·강정구·오기수·백가은·조윤정·구창회·한수진·최선동·임미라는 별도 전기공사 공종 없음(0), "
                  "전선류는 각 공종 내 산재로 집계 불가)",
    "auxiliary_facility": "실측(1건: 윤성호 '0116 관리사(사무동)공사' 40,093,200원 — 독립 공종, 2026-08-17 P2-17)",
    "thermal_storage_insulation": "부분실측(축열탱크만 2건: 윤성호 축열조 90ton 41,958,000원[2026-08-17 P2-17]·임미라 축열조탱크 FRP보온 20톤 11,000,000원[91차 — 히트펌프 블록 내 라인분리, 윤성호와 동일 방식] 라인분리. "
                                  "보온커튼은 이 카테고리가 아니라 자동개폐 시스템 소속 — 2026-08-17 사용자 결정으로 "
                                  "분류경계 확정(우민재 방식 통일). 이동혁(공주) 다겹보온커튼 분리견적 59,948,820원/1,139평은 "
                                  "자동개폐 계열의 커튼 시스템 일체 참고단가로만 기록. 이 카테고리의 잔여 공백은 "
                                  "단열판·기타 고정 단열재 실측뿐)",
    "equipment_procurement": "미검증(근거문서 없음 — 기자재DB/의 equipment_lookup()에서 개별 품목 단가로 조달, 2026-08-16 P3-22 결정). 📌 91차 후보 기록(채택 아님): 무인방제 설비 2건(최선동 안개분무시설 18,500,000·임미라 무인방제시설 25,107,700)이 '생산성 향상 보조 장비' 정의에 들어올 여지가 있으나 카테고리 정의 확장은 판단성이라 unclassified 유지 — 사용자 결정 사안",
    "design_supervision_fee": "참고요율(법정기준) — 「공공발주사업에 대한 건축사의 업무범위와 대가기준」(국토교통부고시 "
                              "제2020-635호) 별표5 건축공사감리 대가요율. 2026-07-23 웹 확인(10억 1.11~1.35%, 20억 "
                              "1.02~1.24%) → 2026-08-18 별표5 공식 PDF 원문 전사(17구간×3종, SUPERVISION_FEE_RATE_TABLE)로 "
                              "격상, 웹 확인값과 일치. 적용 방식은 사용자 결정(2026-08-18): 참고 표시 전용 — "
                              "design_supervision_fee_reference()가 통합보고서에 3종 추정 구간을 렌더하되 CAPEX 합계 "
                              "불산입, 값은 0 유지(종별 선택·실계약액은 판단성·시세성). 개별 케이스 실지출 대조는 아직 없음 — 91차 관찰: 임미라 집계표에 '컨설팅의뢰비' 10,000,000원 단독 행이 있으나 설계·감리 용역 명시가 없어 이 카테고리로 매핑하지 않고 unclassified(값 0 유지)",
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
    # ✅ ACTUALS 이두희 총액(582,455,045원)과의 62,179,076원 차이는 2026-08-17
    # P1-7에서 해명 완료 — 갑지 p1: 총공사비 582,455,045 = 공급가액 520,275,969
    # + 부가세 52,027,596 + 영세율적용(자동모터개폐) 10,151,480. 두 값은 같은
    # 문서의 다른 집계 레벨이며 둘 다 정확(ACTUALS 주석 참고).
    "이두희": {
        "greenhouse_structure": 173890221,   # 1-1(113,391,900)+1-2(36,986,173)+1-3(17,921,202)+2(5,590,946)
        "auto_opening_system": 98756345,     # 1-4렉피니언식(30,564,619)+3차광예인(20,685,664)+4다겹예인(37,354,582)+7-1자동모터개폐(10,151,480)
        "hvac": 0,                           # 이 견적범위엔 보일러/난방설비 라인 자체가 없음(별도 발주 추정)
        "irrigation_fertigation": 33433898,  # 5-1기계실(9,056,219)+5-2관수(4,286,510)+5-4퇴수(5,091,169)+6-2양액제어(15,000,000)
        "ict_control": 26224586,             # 6-1환경제어시스템 전액
        "electrical": 0,                     # 별도 전기공사 라인 없음(각 공종에 배선 소액 산재, 집계 불가)
    },
    # 2026-08-17 추가(P2-17 "청킹→엔진 승격" 첫 실사용) — 정본 인덱스 9축 프로브
    # (부대시설·축열 키워드)로 발견 후 원문 직접 대조: 스마트팜스펙/견적참조/
    # "221206 윤성호 청년스마트팜 내역서.pdf"(㈜그린플러스, 2022-12, 29p).
    # 공종별 집계표(p3) 16개 공종 합 1,162,078,090원이 원가계산서(p2)의
    # 재료비(862,942,975)+직접노무비(258,938,516)+산출경비(40,196,599)와 원단위
    # 일치, 세부페이지(p24~29) 합계열과도 대조 완료. 총공사비는 1,354,052,287원
    # (일반관리비·이윤 포함 공급가), 계약명목 1,489,000,000원(VAT 포함, 단위절삭).
    # 이 표본으로 7·8번 카테고리가 처음 채워졌다:
    #   7. auxiliary_facility — "0116. 관리사(사무동)공사" 독립 공종(1식 외주).
    #   8. thermal_storage_insulation — 0114 난방설비 내 "축열조 90ton" 단일
    #      라인을 분리(최혁진 0113 환경제어 라인분리와 동일 방식). 보온커튼·
    #      스크린은 자동개폐 소속(2026-08-17 사용자 결정으로 관례 확정).
    # 0110 행잉거터(34,792,329)+0111 작물와이어(4,428,023)는 재배시설 성격이라
    # 이두희 베드설치 선례에 따라 unclassified(강제 매핑 안 함).
    "윤성호": {
        "greenhouse_structure": 610497614,   # 0101가설(56,819,296)+0102기초(112,328,151)+0103철골(127,145,291)+0104알루미늄(128,991,788)+0105피복(118,807,959)+0106판넬창호(66,405,129)
        "auto_opening_system": 110592840,    # 0107천창개폐(25,657,502)+0108수평스크린(84,935,338) — 보온스크린 포함(확정 관례)
        "hvac": 147766589,                   # 0109유동휀·훈증기(9,672,200)+0114난방설비(180,052,389)−축열조(41,958,000)
        "irrigation_fertigation": 89451477,  # 0112양액설비공사 전액
        "ict_control": 18908340,             # 0113환경제어시스템 1구역(마그마) — 최혁진과 동일 시스템·동일 공종코드
        "electrical": 63589678,              # 0115전기공사 전액
        "auxiliary_facility": 40093200,      # 0116관리사(사무동)공사 — 이 카테고리 최초의 독립 공종 실측
        "thermal_storage_insulation": 41958000,  # 축열조 90ton(011401 난방기계실 내 라인분리)
    },
    # 2026-08-18 추가(51차 "다른 견적 세부 분석" 1호) — 40차에 총액만 대조했던
    # 스마트팜스펙/한일그린텍/설계예산서(한일그린텍).pdf(20p)를 공종 레벨로 전량
    # 분해. 공사 집계표(p4) 8공종 소계가 원가계산서(p3)의 직접재료비(241,374,292)
    # +직접노무비(97,796,120)+기계경비(16,427,000)=직접공사비 355,597,412원과
    # 원단위 일치, 내역서 세부(p7~20) 각 공종 소계와도 대조 완료. known_total은
    # 관례대로 직접공사비 355,597,412원(본공사) — "환급금 재투자" 블록 22,635,750원
    # (농업용 배지 9,424,800·유동휀 9,600,000·배출환풍기 989,100 등, p5·p20)은
    # 원가계산서에서 관리비·이윤 없이 별도 계상되는 부가세 환급분 재투자 설계라
    # 본공사 직접공사비 밖으로 분리 유지(포함하지 않음 — 주석·레지스트리에만 기록).
    # 매핑 근거(전 공종이 기존 선례로 결정, 신규 판단 없음):
    #   전면 판넬시공→온실구조(윤성호 0106판넬창호 선례), 커튼(드럼 예인식)→자동
    #   개폐(보온커튼=자동개폐 확정 관례), 동력장치공사→자동개폐(개폐모터 24대
    #   [M304 12+M232 3+M432 1+M231A양축 8, p16 4개 라인 합산 — 레드팀 4회차 F1로
    #   첫 라인만 세던 '12대' 오기 정정]·커튼모터 5대·하우스콘트롤 접점용
    #   7,434,000원·전선류 — 계산서 발행 품목명 자체가 '동력피복개폐기'[영세율
    #   19,424,405원, p5]; 이두희 7-1 자동모터개폐 선례. 하우스콘트롤은 환경제어
    #   시스템이 아니라 개폐 접점 제어반이라 ict_control 분리 안 함 — 최혁진·
    #   윤성호의 분리는 '환경제어시스템' 명시 라인만 해당, p16~17 전문에 센서·
    #   복합제어 성격 라인 부재 확인).
    # 원문 관찰 2건(레드팀 4회차 F5·F7 — 산출물 값엔 영향 없음):
    #   ① 집계 구조 비대칭: 우민재 known_total엔 qa_safety(안전관리비 등 2,679,227)가
    #     공종 라인으로 포함되나, 한일그린텍의 산업안전보건관리비 1,440,000원은
    #     원가계산서 산식 항목이라 집계표(=known_total) 밖 — 문서 구조 차이로 기록.
    #   ② 원문 내부 1원 갭: p3 공급가액 소계 표기 416,072,106 vs 원가 빌드업 재계산
    #     364,153,182+29,132,254+22,786,671=416,072,107(p5 소계 표기와 동일).
    #     총공사비 체인은 p3 표기 계열(…106)로 일관 성립.
    # 스탠딩 거터(스티, 67.5m 28줄) 46,519,015원은 재배시설 성격이라 이두희
    # 베드설치·윤성호 행잉거터 선례에 따라 unclassified(강제 매핑 안 함) —
    # 분류합 309,078,397+거터 46,519,015=355,597,412 원단위 재현(잔차 0).
    "한일그린텍": {
        "greenhouse_structure": 216821456,   # 기초(14,694,738)+골조 MS신형125-75(158,498,030)+피복(27,231,655)+전면판넬(16,397,033)
        "auto_opening_system": 73885517,     # 커튼 드럼예인식(52,411,062)+동력장치공사(21,474,455) — 개폐·커튼모터+접점제어반+전선
        "hvac": 0,                           # 본공사 범위에 난방설비 없음(유동휀·배출환풍기는 환급금 재투자 블록 — known_total 밖)
        "irrigation_fertigation": 18371424,  # 양액공급기(마그마 100v02 30T 그린씨에스)+물탱크·여과기·배관 일체
        "ict_control": 0,                    # 환경제어시스템 독립 라인 없음(하우스콘트롤 접점용은 동력장치공사 소속 — 위 주석)
        "electrical": 0,                     # 별도 전기공사 공종 없음(전선류는 각 공종 내 산재 — 이두희와 동일 상황)
    },
    # 2026-08-18 추가(52차 "다른 견적 세부 분석" 2호) — 스마트팜스펙/견적참조/
    # "충남 서산(이준희) 온실 시공 견적서_부가세 환급.xlsx"(팜스코건설(주), 2026-05,
    # "2025년 청년자립형 스마트팜 지원사업", 벤로형 유리온실 측고 6.3m·동고 7.3m,
    # 5,404.32㎡=재배실 4,756.32+관리실 648). '벤로형' 명시는 표본 최초이나 유리
    # 피복 자체는 최혁진("철골 유리온실 3,459㎡"·4mm 일반유리)·윤성호(천창·거터
    # 4mm 유리)가 선재 — 54차 레드팀(5회차) F2로 '최초의 유리온실' 오독 방지 병기.
    # 공종별집계표 합계행(재 758,880,699+노 237,736,474+경비 13,720,008)=직접공사비
    # 1,010,337,181원이 원가계산서 직재·직노·산출경비(기계경비)와 원단위 일치 —
    # known_total 채택. 도급 체인도 원단위 재현: 원가 계 1,079,731,365+이윤 11,177,726
    # (일반관리비 0% — 한일그린텍 8%와 대조적, 제경비 구조 업체별 상이 신호)
    # =공급가액 1,090,909,091+부가세 109,090,909=1,200,000,000 → 영세율 적용
    # -1,056,000 → 부가가치세 환급 -26,179,000(절사 전 26,179,841) → 실부담
    # 1,172,765,000("일금 일십일억칠천이백칠십육만오천원정" 한글 대사 일치) —
    # 견적서 자체가 부가세 환급 체인을 명시한 표본 최초 사례(군산 환급 병기·한일
    # 환급 재투자와 같은 주제 계열).
    # 매핑(전 공종 기존 선례 적용): 가설→온실구조(우민재 scaffold 편입 관례),
    # 기초·주요철골·0401 유리피복·0402 벽체및관리동지붕→온실구조(관리실 648㎡는
    # 독립 공종이 아니라 혼입 — auxiliary_facility 0 유지), 06 천창개폐+07 수평
    # 스크린→자동개폐(보온스크린 관례), 09 유동휀→hvac(윤성호 0109 선례, 난방설비
    # 11은 "본 공사제외" — 급수·위생 10도 제외), 12 양액시설 하위 중 1201 기계실·
    # 1203 관수·1204 배수·1207 CO2배관→관수양액(이두희 5-1/5-2/5-4 선례, CO2배관은
    # 원문이 양액시설 하위로 편성한 소속을 따름 — 세부는 PE배관·점적호스·라인밸브로
    # 관수 성격), 1209 복합환경제어시스템 83,463,440→ict_control(최혁진·윤성호
    # 0113 '환경제어시스템' 명시 라인 관례 — 표본 최대 관측치, 기존 3건 17.9~26.2M의
    # 3~4.7배. 원인은 제어기 브랜드/패키지: 내역서 r735 "PRIVA 복합환경제어
    # Compact CC" 1SET 80,000,000원이 소계의 95.85%, 기존 3건은 전부 국산 마그마
    # 계열 — 54차 레드팀(5회차) F1로 종전 '벤로형 유리 사양 신호' 귀속을 정정:
    # 유리온실 표본 최혁진·윤성호의 ict는 17.9~18.9M이라 유리 사양으로는 최대값이
    # 설명되지 않는다), 13 동력간선→electrical(윤성호 0115 선례).
    # unclassified 3건 93,326,116원(강제 매핑 안 함): 1202 행잉거터 65,624,205(윤성호
    # 0110 선례)+1205 유인줄 19,138,167(윤성호 0111 작물와이어 선례)+05 기타공사
    # 8,563,744(선홈통·집수정·기계실 바닥배수 — 빗물·배수 부대, 13분류 어디에도
    # 깔끔히 안 맞음). 분류합 917,011,065+93,326,116=1,010,337,181(잔차 0).
    # 원본 관찰 3건([확인요망] 계열):
    # ①08 예인형 개폐장치공사가 집계표에 금액 미반영인데 내역서엔 #REF! 파손 항목
    #   (재료비 열만 파손 — 노무 소계 8,603,500은 산출됨)과 실항목(보온다겹스크린
    #   6,050,000 등)이 잔존. 54차 레드팀(5회차) F6 대조군 병기: 이 문서에서 금액
    #   미반영 공종은 5건이고 그중 4건(10 급수위생 1,502,650·1101 기계실난방
    #   63,746,846·1102 튜브레일 75,835,752·1206 핸드탭 2,243,737 — 내역서 적산
    #   잔존 규모)은 전부 '본 공사제외' 주석이 달린 정상 미채택 패턴 — 08만 주석
    #   없이 #REF!가 있어, 미채택 대안인지 수식 파손 누락인지 원문만으로 확정
    #   불가(발주 전 확인 필요).
    # ②0401 재배실지붕공사(PO)는 단가만 있고 금액 0 — 유리 채택·PO 대안 미채택
    #   흔적(비교 견적 잔재).
    # ③집계 구조 비대칭(51차 한일 관찰의 재발, 규모 확대 — 5회차 F4): 이준희
    #   산업안전보건관리비 27,047,871(두 산식 중 적은금액 적용)+환경보전비
    #   5,051,685=32,099,556원이 원가계산서 경비 소계(83,114,192) 안에 있어
    #   known_total(집계표) 밖인 반면, 우민재 known_total은 qa_safety 2,679,227을
    #   공종 라인으로 포함 — 케이스 간 비중 비교 시 분모 구성이 문서 구조에 따라
    #   다름을 기록(CAPEX분해 페이지 각주 참조).
    "이준희": {
        "greenhouse_structure": 564263718,   # 가설(6,314,238)+기초(69,936,701)+주요철골(169,114,684)+0401유리피복(174,804,328)+0402벽체·관리동지붕(144,093,767)
        "auto_opening_system": 173455706,    # 06천창개폐(47,477,403)+07수평스크린(125,978,303) — 보온스크린 포함(확정 관례)
        "hvac": 7093767,                     # 09유동휀 설치 공사 전액(난방설비 11은 "본 공사제외" 명기 — 발주 계획은 원문에 없음)
        "irrigation_fertigation": 66934911,  # 1201기계실(28,952,319)+1203관수(28,859,014)+1204배수(3,904,157)+1207CO2배관(5,219,421)
        "ict_control": 83463440,             # 1209복합환경제어시스템 전액 — 표본 최대(PRIVA Compact CC 80,000,000이 95.85% — 위 주석)
        "electrical": 21799523,              # 13동력간선공사 전액
    },
    # 2026-08-18 추가(55차 "다른 견적 세부 분석" 3호) — 스마트팜스펙/견적참조/
    # "천안 맹주연님 견적서_251014(최종견적서).pdf"(주식회사 백두건설, 2025-10-14,
    # "2026년 청년자립형 스마트팜 지원사업", 규격 "(벤로형)9.4m*99m=3연동" — 문서에
    # 면적 명시값 없음, 규격만 기록). ⚠️ 명칭은 '벤로형'이나 피복(010105)은 전량
    # PO/PE 필름(천창·고랑·측면 필름 등 — 유리 라인 0건): 명칭≠재질(5회차 F2 교훈
    # 즉시 적용 — '벤로형=유리' 추정 금지). 딸기 행잉거터 재배동.
    # 공종별집계표(p3) 13개 하위 공종의 재·노·경 열합이 원가계산서(p2) 직접재료비
    # 360,447,860+직접노무비 72,269,120+기계경비 7,025,247과 원단위 일치 —
    # known_total은 그 합 439,742,227 채택. ⚠️ 원문 내부 갭 5건(6회차 F2로 전수화
    # — 종전 "1원 잔재 3곳" 한정 서술은 불완전했음): ①집계표 총계행 표기
    # 439,742,226(구성 합 대비 -1) ②경비 소계 표기 51,455,849(항목합 51,455,848
    # 대비 +1) ③공급가액 표기 547,125,903(빌드업 547,125,902 대비 +1) — 이상 1원
    # 계열(한일그린텍 4회차 F7 동계열, 채택값은 전부 구성 합 기준) ④환급품목표
    # (p52~54) 소계 3건 합 101,756,540+14,080,913+110,723,039=226,560,492 vs 합계
    # 표기 226,473,083(Δ87,409 — '만단위절사' 주석으로도 미설명[절사면 226,560,000],
    # 환급금 22,647,308은 표기 계열 ×10%) ⑤이윤 표기 24,250,441 vs 표기 산식
    # "(노무+경비+일반관리비)*15%" 재계산 162,427,601×15%=24,364,140(Δ113,699 —
    # 실효 14.93%, 비고 '15%이내' 한도 문언과는 정합).
    # 도급 체인: 순공사비 계 493,278,737(재+노 81,375,029[간노 12.6% 포함]+경비
    # 항목합 51,455,848 — 계 표기와 원단위 일치)+일반관리비 6% 29,596,724+이윤
    # 24,250,441(실효 14.93% — 위 갭 ⑤)=공급가액 547,125,902+부가세 54,712,590=
    # 601,838,492(표기 공급가액 547,125,903 기준으로는 601,838,493 — 6회차 F1로
    # 두 계열 혼용 서술 정정) → 합계 표기 601,838,000(문서 표기 '백원단위절삭').
    # 부가세환급금 22,647,308(환급품목 합계 표기 226,473,083×10%, 집계표 별행)은
    # 병기만 — 합계가 환급 차감 전 금액이라 이준희(차감 후 실부담 표기)와 표기
    # 방식이 다름(환급 주제 3번째 표본).
    # 매핑(기존 선례 적용): 기초+골조파이프+부속자재1·2+피복+샌드위치판넬→온실구조
    # (판넬은 윤성호 0106 선례), 천창공사+커튼공사→자동개폐(보온커튼 관례).
    # 010108 '환기 및 개폐 시설공사'는 혼재 공종이라 명시 라인만 분리(최혁진 0113·
    # 윤성호 축열조 라인 분리 방식): 유동팬 42대 5,040,000+환풍기 6대 1,123,200+
    # 유동팬설치 노무 2,508,576=8,671,776→hvac(노무 분리는 수량산출서 p29가 뒷받침
    # — '개폐모터설치 15대'=천창모터 12+개폐기 3, '유동팬설치 42대'), 잔여
    # 14,751,446(천창모터 12대·동력피복개폐기 3대·컨트롤박스[자동] 5,400,000·전선
    # 4종 2,609,400·개폐모터설치 노무)→자동개폐. 전선 4종의 귀속 근거(6회차 F5로
    # 재서술 — 종전 '개폐 블록 직후 배치' 논거는 원문 순서와 불일치): 용도 미기재
    # (귀속 불명)이나 ①제어반·모터류와 같은 공종의 잔여로 두는 최소 개입 ②4종 중
    # 3종(545,040·467,280·688,680)이 커튼공사(자동개폐 소속, p11)의 전선 3종과
    # 규격·수량·금액 완전 동일 — hvac 확증 근거 없음. 감응: 전량 hvac 이동 가정
    # 시에도 hvac 2.0→2.6%·자동개폐 23.1→22.5% 수준(분리 검산
    # 14,751,446+8,671,776=23,423,222 소계 재현).
    # 컨트롤박스는 개폐 자동 제어반(한일 하우스콘트롤 계열 — ict 분리 안 함).
    # 020110 '양액제어시스템(딸기)'은 명칭에 '제어'가 있으나 실체는 양액기(경농
    # 20,400,000)+탱크·교반기·배관·인건비 — 환경제어 컨트롤러 아님(이두희 6-2
    # 양액제어 선례대로 관수양액), +공급시설(점적호스·전자밸브)+배수배관(이두희
    # 5-4 퇴수 선례)=43,578,304. 020109 '바닥재및행잉거터(딸기)' 46,977,648은
    # 재배시설 성격(행잉거터 1,900m·바닥재·지반정리 장비대여) — 윤성호 0110
    # 선례대로 unclassified. 분류합 392,764,579+46,977,648=439,742,227(잔차 0).
    "맹주연": {
        "greenhouse_structure": 239153913,   # 기초(28,148,966)+골조파이프(124,024,505)+부속자재1(14,080,913)+부속자재2(29,487,743)+피복(25,521,173)+샌드위치판넬(17,890,613)
        "auto_opening_system": 101360586,    # 천창(36,129,616)+커튼(50,479,524)+환기및개폐 잔여(14,751,446 — 천창모터·개폐기·컨트롤박스·전선)
        "hvac": 8671776,                     # 유동팬 42대(5,040,000)+환풍기 6대(1,123,200)+유동팬설치 노무(2,508,576) — 010108 명시 라인 분리
        "irrigation_fertigation": 43578304,  # 양액제어시스템(33,686,562 — 실체는 양액기+주변)+공급시설(5,934,127)+배수배관(3,957,615)
        "ict_control": 0,                    # 독립 환경제어시스템 없음(컨트롤박스 5,400,000은 개폐 제어반 — 자동개폐 소속)
        "electrical": 0,                     # 별도 전기공사 공종 없음(전선류는 각 공종 내 산재)
    },
    # 2026-08-18 추가(56차 "다른 견적 세부 분석" 4호) — 스마트팜스펙/견적참조/
    # "1. 군산 강정구 농가_8.4×44×10연동_와이드_딸기.pdf"(㈜서진비에스, 견적일
    # 2022-04-25 — 각 표본 기록 기준 가장 이른 견적일(윤성호 2022-12, 나머지는
    # 2025~2026 계열): 물가 시점 2022-04 주의. 딸기 스마트팜 시설공사,
    # 폭8.4M×길이44M×10연동=3,696㎡ 와이드 연동, 랙피니언 양개 천창).
    # ⚠️ 견적 범위가 좁은 부분 범위 시공 견적: 골조·천창개폐·피복(1·2중 PO필름)+
    # 관리동 판넬·출입문 부속(약 5,597,384원 — 부속자재 공종 내 혼입)만 — 관수·
    # 양액·보온커튼·난방·환기휀 품목 전무(콘트롤박스에 커튼·환풍기·유동휀
    # "단자"만 예비). 카테고리 0들은 설비 부재가 아니라 견적 범위 밖.
    # 공종별집계표(p3) 5공종 합=재 223,202,937+직노 67,810,080+산출경비 5,908,267
    # =직접공사비 296,921,284 원단위 일치 — known_total 채택(간노 13%·보험료·
    # 관리비·이윤·부가세 제외, 기존 7표본과 동일 레벨).
    # 도급 체인(원단위 재현): 순공사원가 323,584,540+일반관리비 2% 6,471,690+이윤
    # 5,295,649(실효 4.956% — 표기 산식 5% 재계산 5,342,665와 Δ47,016, '15% 이내'
    # 문언 정합)−영세율 품목 10,200,000=공급가액 325,151,879(표기 325,151,878 —
    # 1원 갭)+부가세 32,515,188+영세율 10,200,000=367,867,066→천원 절사
    # **공사금액 367,867,000**(p2 원가계산서 머리의 한글 "삼억육천칠백팔십육만
    # 칠천원정"과 일치 — 7회차 F2: 종전 '표지' 서술은 위치 오기, p1 표지엔 금액
    # 표기 없음), −부가세환급예정 13,050,745(환급품목 130,507,454×10%, p4 공종별
    # 환급표)=354,816,255→천원 버림 **총공사금액 354,816,000**(같은 줄 괄호 숫자와
    # 일치). p2 머리 "일금 [한글] ([숫자]원정)"이 서로 다른 두 값인 것: 각각 표 내
    # 공사금액(환급 차감 전)·총공사금액(차감 후) 행과 일치해 **차감 전·후 병기로
    # [추정]**되나, 문서에 라벨이 없고 "일금 X원정 (X원정)"은 통상 동일값 이중
    # 표기 관례라 의도된 병기인지 템플릿 미갱신(한글 갱신 누락)인지 원문만으로
    # 확정 불가(7회차 F3로 단정 격하 — 환급 주제 4번째 표본, 이준희=차감 후,
    # 맹주연=차감 전 단일 표기).
    # 원문 내부 갭 3건(7회차 F4로 전수화): ①경비 소계 표기 23,756,213(항목합
    # 23,756,212 대비 +1) ②공급가액 표기 1원(위) — 1원 계열(한일 4회차 F7 동계열)
    # ③측면개폐모터 480,000에 비고 '영세율' 표시가 있으나 영세율 품목 총액
    # 10,200,000=개폐모타 6,400,000+콘트롤박스 3,800,000에 정확히 미포함(표시·
    # 집계 불일치. 가이드로라 180,000은 비고 공란).
    # 매핑: 기초+농업용파이프 잔여(골조·트러스 제작비 — '1.2중개폐파이프' 347,061
    # 제외)+부속자재(클램프·패드·물받이·관리동 판넬 및 출입문 부속 약 5,597,384
    # 포함[독립 공종 아니라 auxiliary 분리 안 함 — 윤성호 0116과 구분]·골조 공사비
    # 노무 35,962,080 — 개폐 요소 0건 확인)+비닐자재 잔여=222,117,979(온실구조),
    # 천창개폐 73,796,244+명시 개폐 명칭 라인 분리 2건(비닐 공종의 측면개폐모터
    # DC60W 4대 480,000+가이드로라 180,000=660,000, 파이프 공종의 1.2중개폐파이프
    # 347,061[측면 개폐 필름 권취 축 계열로 추정 — 구조 부재 가능성은 도면 부재로
    # 확정 불가, 7회차 F5: '명시 개폐 명칭 라인 분리' 규칙의 일관 적용이며 금액
    # 0.12%라 어느 귀속이든 비중 한 자리 수준])=74,803,305(자동개폐). 천창개폐 내
    # "콘트롤박스(환경제어용)" 3,800,000은 명칭에 '환경제어'가 있으나 실체는
    # 천창·커튼·측창·환풍기 구동 단자 통합 제어반(센서·복합제어 시스템 라인 부재
    # — 한일 하우스콘트롤·맹주연 컨트롤박스 계열)이라 ict 분리 안 함.
    # 분류합 222,117,979+74,803,305=296,921,284(잔차 0 — unclassified 0은 최혁진에
    # 이어 두 번째[7회차 F1로 '표본 최초' 오기 정정]).
    "강정구": {
        "greenhouse_structure": 222117979,   # 기초(11,451,200)+농업용파이프 잔여(101,291,331)+부속자재(81,198,324)+비닐자재 잔여(28,177,124)
        "auto_opening_system": 74803305,     # 천창개폐 랙피니언(73,796,244)+측면개폐모터·가이드로라(660,000)+1.2중개폐파이프(347,061) — 명시 라인 분리
        "hvac": 0,                           # 견적 범위 밖(환기휀·난방 품목 전무 — 콘트롤박스 단자 예비만)
        "irrigation_fertigation": 0,         # 견적 범위 밖(관수·양액 품목 전무)
        "ict_control": 0,                    # 콘트롤박스(환경제어용) 3,800,000은 구동 단자 통합 제어반 — 자동개폐 소속(위 주석)
        "electrical": 0,                     # 별도 전기공사 공종 없음
    },
    # 2026-08-18 추가(57차 "다른 견적 세부 분석" 5호) — 스마트팜스펙/견적참조/
    # "견적서_군산 오기수 농가_0803.pdf"(㈜서진비에스 — 강정구와 동일 업체
    # [사업자번호·대표 동일]의 후속 견적, 견적일 원문 표기는 "2023-08"까지
    # (일자 없음 — 강정구 2022-04-25로부터 약 15~16개월 뒤): 동일 업체 시계열
    # 관찰 가능. 스마트팜 ICT 융복합확산사업, 폭8.5m×96m×4연동=3,264㎡ 약989평).
    # ⚠️ 강정구(골조·개폐·피복만)와 정반대 극의 부분 범위 견적 — **설비 전용**
    # (컨트롤박스·커튼·행잉거터·양액·관수·환경제어시스템만, 골조·피복·기초 품목
    # 전무): ICT 융복합 '확산'사업 성격(기존 온실에 설비 투입). 두 표본이 상보적
    # 부분 범위 쌍을 이룬다. 0 카테고리는 설비 부재가 아니라 견적 범위 밖.
    # 공종별집계표(p3) 7공종 합=재 164,863,706+직노 31,834,400+산출경비 2,876,832
    # =직접공사비 199,574,938 원단위 일치 — known_total 채택(간노 12.2%·보험료·
    # 관리비·이윤·부가세 제외 — 직접공사비 레벨. 단 8회차 F6: 표본 간 분모 구성
    # 비대칭은 별도[우민재만 qa_safety가 공종 라인으로 분모 내 — CAPEX분해 각주],
    # 오기수 안전관리비 5,763,255도 산식 항목이라 분모 밖).
    # 도급 체인(원단위 재현): 순공사원가 213,940,044+일반관리비 5% 10,697,002
    # (비고 산식 표기는 '6% 이내')+이윤 8% 4,781,867('15% 이내' — 업체·건별 실효율
    # 상이 신호: 강정구 4.96%↔오기수 8%, 같은 업체도 다름)−영세율 9,170,000=
    # 공급가액 220,248,913+부가세 22,024,891+영세율 9,170,000=총공사금액
    # 251,443,804(한글 "이억오천일백사십사만삼천팔백사원정" — 원단위 한글 표기,
    # 환급 차감 전. 부가세환급예정 2,397,481 병기 — 맹주연 계열 표기).
    # 원문 내부 갭·결함 관찰 4건(8회차 F4로 전수화): ①경비 소계 표기 13,358,142
    # (항목합 13,358,143 대비 -1원 — 1원 계열) ②p4 환급품목표 계가 23,974,813으로
    # 첫 행(커텐공사) 값 그대로 — 관리동커텐 1,648,320 합산 누락(실합 25,623,133),
    # 환급예정 2,397,481도 누락 계 기준(합산 시 2,562,313 — Δ164,832)[확인요망:
    # 실환급 신청 시 재검토 대상] ③집계표 별행 "*부가세환급품목 2,397,481"의
    # 라벨은 '품목'인데 값은 '금액' — 강정구 문서(별행=품목 합)와 같은 업체인데
    # 별행 의미가 비일관 ④행잉거터 잡자재 라벨 "재료비의 3%"의 값 310,330이
    # 공종 재료비 전액(33,286,860)의 3%가 아니라 주자재(헹잉거터 22,942,500)
    # 제외 잔여 10,344,360의 3% — 타 4개 공종 잡자재는 전액 기준으로 재현되어
    # 같은 문서 내 산식 기준이 1개 공종만 다름(업체 관례인지 오류인지 원문만으로
    # 판별 불가).
    # 매핑(기존 선례): 컨트롤박스설치 5,310,000→자동개폐. ⚠️ 8회차 F3: 이 공종엔
    # 환경제어복합기 650,000+온도표시계 150,000+CO2단자 100,000=900,000이 있어
    # 종전 귀속 기준("센서·복합제어 라인 부재" — 강정구·한일·맹주연에 성립)이
    # 여기선 그대로 성립하지 않는다. 유지 논거: 별도의 독립 환경제어시스템 공종
    # (40,000,000 — 기상대·센서·소프트웨어 완비)이 실존해 이 박스는 구동 단자
    # 제어반+부속 표시기 성격이 지배적(공종 단위 관례). 감응: 900,000을 ict로
    # 이동 가정 시 자동개폐 36.0→35.5%·ict 20.0→20.5%(표시 한 자리 변동 수준).
    # 커텐공사 63,684,894+관리동커텐 2,817,269→자동개폐(보온커튼 관례. 유동휀·
    # 배기휀은 단자만 있고 실물 휀 품목 없음 — hvac 0), 양액시설(양액기 네타플랙스
    # 23,000,000 — 수입계, 경농 20.4M·마그마 13.9M과 브랜드 스펙트럼)+관수배관=
    # 47,941,137(관수양액), 환경제어시스템 40,000,000→ict_control(독립 공종 —
    # 최혁진 선례. CPS+UPS 1식 40,000,000 단일 금액 라인에 기상대·광센서·EC/PH·
    # CO2센서·컴팩 프로그램·"프라바 오피스"·PC가 금액 공란으로 부속: 한글 표기
    # '프라바'뿐이라 **PRIVA(프리바) 계열로 [추정]** — 이준희의 라틴 리터럴
    # "PRIVA Compact CC"와 근거 등급이 다름(8회차 F2로 단정 격하). 참고 비교도
    # 집계 레벨 주의: 오기수 40M은 공종 총액(PC·센서 번들), 이준희 80M은 공종
    # 83.5M 내 단일 제어기 라인 — 같은 축의 밴드 아님),
    # 행잉거터설치 39,821,638→unclassified(딸기 거터 2,300m — 윤성호 선례).
    # 분류합 159,753,300+39,821,638=199,574,938(잔차 0).
    "오기수": {
        "greenhouse_structure": 0,           # 견적 범위 밖(설비 전용 — 골조·피복·기초 품목 전무)
        "auto_opening_system": 71812163,     # 컨트롤박스(5,310,000 구동 단자 제어반)+커텐공사(63,684,894)+관리동커텐(2,817,269)
        "hvac": 0,                           # 실물 휀 품목 없음(컨트롤박스에 유동휀·배기휀 '단자'만 예비)
        "irrigation_fertigation": 47941137,  # 양액시설공사(35,567,476 — 네타플랙스 양액기)+관수배관공사(12,373,661)
        "ict_control": 40000000,             # 환경제어시스템 독립 공종 — 한글 '프라바 오피스' 표기로 PRIVA 계열 [추정](위 주석), 표본 2위 관측
        "electrical": 0,                     # 별도 전기공사 공종 없음
    },
    # 2026-08-18~19 추가(59차 "다른 견적 세부 분석" 7호) — 스마트팜스펙/견적참조/
    # "논산딸기백가은님75각 시공 견적서(최종).pdf"+"논산딸기조윤정님75각 외몽골셀액
    # 분리(최종).pdf"(그린팜스글로벌㈜, 2026-05-20, 청년 자립형 스마트팜 신축,
    # 각 1091py=3,600㎡ 75각). ⚠️ 쌍 견적 대조 결과: 두 문서는 표지(p1) 필지
    # BL21↔BL22·농가명·연락처 3줄만 다르고 **나머지 22p 전체가 문자 단위 동일**
    # (전문 diff) — 파일명의 '외몽골셀액분리'는 구성 요약일 뿐 옵션 차이 아님.
    # 동일 패키지를 인접 필지 2농가에 동일 단가로 발행한 것(동일 단가 정책 실측).
    # 표본은 중복 왜곡(같은 값 2회로 관측범위 오염)을 피해 **1건("백가은·조윤정")
    # 통합 편입**, source_refs에 두 파일 모두 등재.
    # 공종별집계표(p3) 8공종(하위 16공종) 합=재 286,680,383+직노 100,648,000+
    # 산출경비 11,300,000=직접공사비 398,628,383 원단위 일치(하우스 하위 4공종
    # 합 173,102,523·양액 하위 6공종 합 97,632,160 재현) — known_total 채택.
    # 도급 체인: 순공사원가 411,245,695(경비 소계 23,917,312 — 건강보험료는 산식만
    # 있고 값 공란)+일반관리비 12,748,617(실효 3.1% — '6% 이내' 정합)=합계 표기
    # 423,994,311(항목합 423,994,312 대비 -1원)+부가세 42,399,431=466,393,742→
    # 총공사원가 466,000,000. ⚠️ 절사 라벨 불일치: 문서 표기 '십만단위 절사'인데
    # 실절사는 백만 미만 393,742(십만단위 절사면 466,300,000이어야 함).
    # 원문 갭·결함 5건(9회차 F1로 전수화): ①합계 1원 ②절사 라벨-실절사 불일치
    # ③p23 세부 총계행의 재·노 열이 근권배관 공종 미합산(재 282,216,083=집계표
    # 대비 -4,464,300·노 97,648,000=-3,000,000, 합계열 398,628,383은 정합 — 내부
    # 모순, 집계표가 정본) ④건강보험료 값 공란 ⑤p3 집계표 근권배관 수량 셀 '2'
    # (타 공종 전부 '1'·p4 내역총괄은 '1'·단가×2≠합계 — 내부 모순, 오기인지 다른
    # 산출 단위인지 원문만으로 확정 불가). 라인 단위 환급/비환급 구분+10% 열이
    # 전 품목에 있는 최초 표본 — 총괄: 비환급 195,448,500+환급 203,179,883=
    # 398,628,383(환급 부가세 20,317,988 — 환급 주제 5번째 표본).
    # 매핑(선례+개폐 구동 세트 분리 3곳 — 9회차 F4로 규칙 서술 정밀화: 분리 단위는
    # '명시 개폐 명칭 라인'이 아니라 개폐기·전용 제어반·전용 배선·권취 파이프 등
    # **개폐 구동 세트**이며, 세트 전용성이 확인될 때만 분리하고 공용 가능성이
    # 있으면 잔여 유지[맹주연 010108 전선=팬 공용 가능성이 그 사례]):
    # 기초/토목+골조(1) 잔여[개폐기 파이프 432,000 분리]+골조(2)+피복 잔여
    # [자동개폐기 8대 616,000+가이드로라 240,000+콘트롤박스(온도·우적) 1,080,000+
    # 전선 550,000=2,486,000 분리 — 이 공종의 전력 부하가 개폐기·제어반뿐이라
    # 전선은 세트 전용 배선(9회차 F4로 분리 편입)]+외몽골시설 잔여[개폐파이프
    # 73,600+자동개폐기 5대 385,000+콘트롤박스 600,000+전선 440,000=1,498,600
    # 분리, 동일 논거 — 외몽골=몽골식 외피 터널 구조물이라 잔여는 온실구조]
    # =190,486,323(온실구조), 커튼 58,949,000+분리 3건 4,416,600=63,365,600
    # (자동개폐), 환기 12,080,000(유동팬 50·배기팬 5 — 윤성호 선례. 콘트롤박스
    # [온도/속도] 950,000 포함 — 공종 내 제어반)+난방 17,200,000(난방기[습식용]
    # FC-12S3 5대 — 기종 사양[온풍/온수]은 원문 미기재·카탈로그 미확보, 9회차
    # F2로 '온풍' 무근거 표기 삭제)+근권배관 7,464,300=36,744,300(hvac — 난방
    # 계열 독립 공종 수 최다[3개], 금액·비중은 표본 4위[9회차 F7 정정]. 근권배관은
    # 지온관 1,625,000·엑셀 15mm 계열이 근권 가온 배관 실체라는 **[추정] 배정**
    # — 유리: '지온관' 명칭+급액 13mm 라인은 4-6 보조배관에 별존[구경 분리].
    # 불리[9회차 F3 병기]: 문서 전체에 열원[보일러·온수·순환펌프] 0건·농수관
    # 50mm 등 관수 명칭이 이 공종 재료비의 17.4%[778,000]. irrigation 이동 가정
    # 감응 ±1.9%p), 양액기계(MAGMA-1000 V2.0 16,500,000 — 코퍼스 마그마 5번째
    # 관측[ict 3건+한일그린텍 양액기 마그마 100v02, 9회차 F6 계수 정정], 양액기
    # 로는 2번째)+주위시설+회수시설+양액보조배관=44,695,260(관수양액), ict 0
    # (독립 환경제어 없음 — 콘트롤박스는 4건[피복 온도·우적/외몽골/커튼 전자
    # 타이머/환기 온도·속도, 합 3,680,000. 9회차 F5로 '3종' 오기 정정]이며 전부
    # 공종별 구동 제어반: 우적·온도는 센서 입력이나 복합제어[기상대·EC/pH·CO2·
    # PC] 라인 0건이라 유지, 전량 ict 이동 가정 감응 0.92%p), electrical 0.
    # unclassified 63,336,900(강제 매핑 안 함): 4-4 바닥제 5,580,000(맹주연 바닥재
    # 선례)+4-5 베드시설 47,356,900(딸기 베드·상토 — 이두희 5-3 베드설치 선례
    # 직행)+8 기타 10,400,000(장비대 일괄 임대 — 전 공종 공용 시공 장비라 특정
    # 공종 귀속 불가, 우민재 가설[구조물 가설재]과 성격 상이해 structure 편입
    # 안 함. 단 동일 성격의 펌프카 900,000은 1-1 기초 공종 내 라인이라 공종 귀속
    # 우선대로 structure행 — 비대칭 감응 기록[9회차]). 분류합 335,291,483+
    # 63,336,900=398,628,383(잔차 0).
    "백가은·조윤정": {
        "greenhouse_structure": 190486323,   # 기초/토목(13,712,000)+골조1 잔여(71,133,642)+골조2(16,209,400)+피복 잔여(69,129,481)+외몽골 잔여(20,301,800)
        "auto_opening_system": 63365600,     # 커튼(58,949,000)+개폐 구동 세트 분리 3곳(골조1 432,000·피복 2,486,000·외몽골 1,498,600 — 전용 배선 포함)
        "hvac": 36744300,                    # 환기(12,080,000)+난방(17,200,000)+근권배관(7,464,300 — 지온관 계열 [추정] 배정, 반대근거 위 주석)
        "irrigation_fertigation": 44695260,  # 양액기계 MAGMA-1000(16,500,000)+주위시설(8,010,500)+회수(1,149,000)+보조배관(19,035,760)
        "ict_control": 0,                    # 독립 환경제어시스템 없음(콘트롤박스 4건은 공종별 구동 제어반 — 감응 0.92%p 위 주석)
        "electrical": 0,                     # 별도 전기공사 공종 없음(개폐 세트 전용 배선 외 전선류는 각 공종 산재)
    },
    # 2026-08-19 추가(60차 "다른 견적 세부 분석" 8호) — 스마트팜스펙/견적참조/
    # "박규현 견적서.pdf"(문서번호 JW20260323, 2026-04-07, "충남자립형 스마트팜
    # 지원사업" — 표지에 "(벤로Venlo형 주기둥ㅁ125*75 4연동 오이 행잉거터 연질필름
    # 스마트팜)" 명시: 명칭 '벤로형'+연질필름을 표지가 스스로 밝힘[맹주연 계열].
    # 오이 작목은 CAPEX 표본 11건 중 최초이나 리포 전체로는 yonggyun(이용균 —
    # 오이 4연동, 9.6m·행잉거터·자립형)이 선재: 코퍼스 최근접 쌍(10회차 F3 한정).
    # 면적 9.6×98×3PLAN 2,822.4+9.6×89×1PLAN 854.4=3,676.8㎡[1,114.1평].
    # "박규현 견적서 (1).pdf"와는 SHA-256 완전 동일 파일(2부 선별 불요 — 10회차
    # F2로 종전 '무인본 기준' 서술 정정: p1에 날인 이미지 실재[날인본]).
    # 공종별집계표(p3): a.온실 8공종(재 264,422,873+노 145,644,218=410,067,091)+
    # b.양액시설 4공종(105,892,562+18,936,600=124,829,162), 합계 재 370,315,435+
    # 노 164,580,818=**직접공사비 534,896,253**(⚠️ 경비 열이 전 행 공란[값 0]인
    # 표본 — 원가계산서 기계경비도 '직접산출' 표기에 값 공란, known_total은 재+노
    # 2요소. 기존 표본[재+노+경]과 집계 레벨이 한 요소 좁음을 명기 — 경비 소계
    # 40,688,539를 타 표본처럼 분모에 넣으면 구조 −3.1%p 등: CAPEX분해 분모 각주
    # 참조). 환급/비환급/영세
    # 3분류 총괄이 집계표에 직접: 환급 313,542,997+비환급 206,856,006+영세
    # 14,497,250=534,896,253(원단위 정합 — 환급 주제 6번째 표본).
    # 도급 체인: 공급가액 575,584,792(재+노+보험료 등 경비 소계 40,688,539, 일반
    # 관리비·이윤 0% — 영세율 14,497,250 포함)+부가세 56,108,754([공급가액−영세율]
    # ×10% 재현 — 영세율 행은 부가세 산정에서만 차감되는 내역)=합계 631,693,546
    # (한글 '육억삼천일백육십구만삼천오백사십육원정' 원단위 일치).
    # ⚠️ 부가세환급 산식이 "부가세환급품목×5%" 표기: 15,677,150=313,542,997×5%
    # 재현 — 타 표본(10%)과 달리 5%만 환급 예정 계상(사유 원문 미기재 [확인요망]
    # — 실환급 검토 시 확인 대상). 공제 후 616,016,396.
    # 매핑(선례 적용): 기초기둥타설및판넬+골조+부속자재(클램프·패드·물받이·설치
    # 인건비 72,362,727 — 개폐 요소 0건)+피복=233,306,324(온실구조).
    # ⚠️ "8. 전기 장치 공사" 29,923,065는 명칭≠실체(재료 80%가 제어기·10%가 팬)
    # — 명시 실체 라인 분리 3분할: ①동력피복제어기기(마그마 스마트팜, AC×4/DC×13
    # 모터 채널) 24,000,000→자동개폐(명칭이 '동력피복[개폐] 제어'라 구동 제어반
    # 계열[한일 하우스콘트롤·오기수 컨트롤박스 동계열] **최대 관측** — '환경제어
    # 시스템' 명시가 아니라 ict 분리 기준 미충족. AC×4는 수평커튼 1HP 모터 4대·
    # DC×13은 내외개폐 DC모터 13대와 수치 일치[채널 정황 — 카탈로그 미확보라 확정
    # 불가, 10회차]. 마그마 브랜드가 최혁진·윤성호 ict[17.9~18.9M]와 동일 계열이라
    # 복합환경제어기일 가능성 [추정] 병기했으나 같은 견적의 양액기도 마그마(동력
    # 시비기)라 브랜드=ict 등식은 약함: ict 이동 가정 감응 4.5%p) ②실물 팬 세트
    # (배기휀 DS-201s 4대 800,000+유동휀 DS-900 24대 2,280,000+배기펜패드 10,400)
    # =3,090,400→hvac(윤성호 유동휀 선례 — 이 견적의 유일한 환기 실물) ③잔여
    # (케이블 3종 1,519,022·케이블타이 9,754·잡자재·설치 인건비) 2,832,665→
    # electrical(공종 명칭 소속 — 분리 검산 24,000,000+3,090,400+2,832,665=
    # 29,923,065). 내외 개폐(환기) 장치 14,327,963(개폐 모터·개폐축+측면 다겹커튼
    # — 팬 없음, 전체 자동개폐)+수평커튼(산광·보온 스크린+AL 고정 스크린)
    # 71,129,815+천창개폐 61,379,924+마그마 제어기=170,837,702(자동개폐).
    # 양액 하위: 기계실 26,517,342(동력시비기 3HP '스마트팜(마그마)' 16,500,000
    # 포함 — 코퍼스 마그마 7번째 관측[양액기로는 한일 100v02·백가은/조윤정
    # MAGMA-1000에 이어 3번째], ⚠️ 백가은·조윤정 양액기와 단가 16,500,000 동일 —
    # 10회차 F4)+회수 4,058,080+관수 16,495,710=47,071,132(관수양액), 베드및벤치
    # 77,758,030(코코피트·거터·레일파이프·운반레일 — 재배·물류 시설, 이두희 5-3
    # 선례)→unclassified. ict 0(환경제어시스템 명시 라인 없음 — 센서·기상대·
    # EC/pH 0건). 분류합 457,138,223+77,758,030=534,896,253(잔차 0).
    "박규현": {
        "greenhouse_structure": 233306324,   # 기초기둥타설및판넬(18,299,200)+골조(75,849,039)+부속자재(89,477,387)+피복(49,680,698)
        "auto_opening_system": 170837702,    # 내외개폐(14,327,963)+수평커튼(71,129,815)+천창개폐(61,379,924)+마그마 동력피복제어기(24,000,000 — 구동 제어반 최대 관측)
        "hvac": 3090400,                     # 전기 공종 내 실물 팬 세트 분리(배기휀 4대+유동휀 24대+패드 — 윤성호 선례)
        "irrigation_fertigation": 47071132,  # 기계실(26,517,342)+회수(4,058,080)+관수(16,495,710)
        "ict_control": 0,                    # 환경제어시스템 명시 라인 없음(마그마 제어기는 동력피복제어 명칭 — auto 소속, [추정] 병기 위 주석)
        "electrical": 2832665,               # 전기 공종 잔여(케이블 3종·잡자재·설치 인건비 — 분리 검산 위 주석)
    },
    # 2026-08-19 추가(61차 "다른 견적 세부 분석" 9호) — 스마트팜스펙/견적참조/
    # "시공견적서.pdf"의 실체는 **농업회사법인 한일그린텍(주)의 구창회 귀하 착공
    # 내역서**(2026-04-13, "2026년 청년 자립형 스마트팜 지원사업(3714㎡)", 위치
    # 충남 당진시 순성면 본리 42-4,5 — 개요 8m×87m×5연동 3,480㎡+방풍 포함
    # 3,714㎡ MS-8 측고 5.0m). **한일그린텍 표본(이영준 3,202㎡)과 동일 업체·동일
    # 양식의 2호 현장** — 서진비에스 쌍(강정구·오기수)에 이은 두 번째 동일 업체
    # 비교 쌍(㎡당 직접공사비: 이영준분 111,055원/㎡ vs 구창회분 102,010원/㎡ —
    # 방풍 포함 면적 기준 참고 관찰). 당진 소재이나 ACTUALS의 '당진이상근'과는
    # 다른 농가. ACTUALS 추가는 벤치마크 기준 변경이라 하지 않음(판단성 — 사용자
    # 결정 사안으로만 기록).
    # 공사 집계표(p4) 7공종(한일 1호와 달리 전면 판넬 공종 없음) 소계=원가계산서
    # (p3) 직접재료비 250,002,799+직접노무비 112,939,613+기계경비 15,922,187=
    # 직접공사비 378,864,599 원단위 일치 — known_total 채택. "환급금 재투자"
    # 21,580,478(농업용 배지 11,848,320+환풍기 4,992,415+시공비 — p5)은 한일 1호와
    # 동일하게 관리비·이윤 밖 별도 계상이라 known_total 밖 분리.
    # ⚠️ 원문 내부 갭 4건(11회차 F2로 전수화) — 특히 ①이 중대: ①**간접노무비
    # 16,940,941이 공급가액에서 증발** — 일반관리비 8%·이윤 15%는 간노 포함
    # 기준으로 재현되는데(계 428,711,806=재+노 129,880,554[간노 포함]+경비
    # 48,828,453 원단위 재현), 공급가액 소계 478,018,700은 간노 제외 빌드업
    # (411,770,865+34,296,944+31,950,892=478,018,701)과 일치하고 p5 내역서에도
    # 간노 대응 행이 없음 — 총공사비가 간노만큼(3.1%) 낮게 책정된 구조.
    # 11회차 F4의 1호 교차 대조로 "간노 제외가 업체 원가 체계" 가설은 기각
    # (1호는 간노 칸 자체가 공란[산식만] — 2호에서만 계상 후 미반영): 오류 쪽
    # 가중[확인요망 — 발주 검토 시 질의 문안: '원가계산서에 계상된 간접노무비가
    # 내역서·공급가액에 대응 행이 없습니다']. 부수 관찰: 1호 경비는 산식 미적용
    # 수기값 다수(40차 관찰과 연결), 2호는 전 항목 산식 재현 — 동일 업체·양식
    # 이나 '동일 채움 수준'은 아님(마크업 배율 1.3517 vs 1.4453 차의 원인).
    # ②공급 소계 p3 표기 478,018,700 vs p5 표기·빌드업 478,018,701(1원 계열 —
    # 한일 4회차 F7 동형) ③과세 공급가액 p3 281,891,609 vs p5 281,891,610(1원)
    # ④환경보전비 1,814,712의 표기 산식 '직접공사비*0.5%'의 실기준은 재+직노
    # 362,942,412(×0.5% 절사 일치 — 기계경비 미포함): 같은 문서에서 '직접공사비'
    # 용어가 362,942,412(원문 산식 용례)와 378,864,599(집계표 소계=리포 각주
    # 용례) 두 값 — known_total은 집계표 소계 앵커라 무영향이나 용어 상충 기록.
    # 도급 체인: 소계 523,841,898+환급금 재투자 23,738,525=547,580,423→천단위
    # 절사 총공사비 547,580,000(한글 일치 — 환급 주제 7번째 표본).
    # 매핑(한일 1호 선례 그대로): 기초+골조+피복=224,747,872(온실구조), 커튼
    # 드럼예인식+동력장치공사=84,493,629(자동개폐 — 세부 p16~18: 개폐모터 26대
    # [M304 12+M232 3+M432 1+M231A양축 10]·커튼모터 5대, 1호 24대/5대와 동형.
    # 계산서 발행 품목명 '동력피복개폐기' 영세율 19,786,702[p3·p5]가 auto 귀속을
    # 보강), 양액공급기 18,235,999(관수양액), 스탠딩 거터(스티, 76.5m 30줄)
    # 51,387,099는 재배시설 성격 unclassified(한일 1호와 동일). hvac 0(환풍기는
    # 환급 재투자 블록 — 분모 밖). ict 0의 근거(11회차 F1로 5요소 병기): 하우스
    # 콘트롤 접점용 7,153,738(p17 no.14 — 1호 7,434,000 동계열 개폐 접점 제어반,
    # 제조사 열 공란)이 있으나 센서·복합제어 라인 부재 — ict 이동 가정 감응
    # 1.89%p(auto 22.3→20.4%). electrical 0.
    # ㎡당 참고 관찰의 정규화(11회차 F3): 직접공사비 111,055↔102,010원/㎡ 격차
    # 의 57%는 범위 차(1호에만 판넬 공종 5,121원/㎡) — 판넬 제외 시 105,933↔
    # 102,010(−3.7%), 총공사비 기준 150,105↔147,437(−1.8%), 규격도 상이(9.6m×
    # 4연동 vs 8m×5연동): like-for-like 비교 아님.
    # 분류합 327,477,500+51,387,099=378,864,599(잔차 0).
    "구창회": {
        "greenhouse_structure": 224747872,   # 기초(16,961,447)+골조 MS신형125-75(177,124,132)+피복(30,662,293)
        "auto_opening_system": 84493629,     # 커튼 드럼예인식(62,626,931)+동력장치공사(21,866,698) — 한일 1호 선례
        "hvac": 0,                           # 본공사 범위에 난방 없음(환풍기 4,992,415는 환급금 재투자 블록 — 분모 밖)
        "irrigation_fertigation": 18235999,  # 양액공급기 일체
        "ict_control": 0,                    # 독립 환경제어시스템 라인 없음(한일 1호와 동일 구조)
        "electrical": 0,                     # 별도 전기공사 공종 없음
    },
    # 2026-09-13 추가(91차 "CAPEX 표본 확대" 13호) — 스마트팜스펙/견적참조/
    # "한수진스마트팜딸기하우스견적서.xls"(다온팜[대표 이숙현, 논산시 채운면],
    # "2026년 청년자립형 스마트팜 보급 지원사업", 폭44m×길이93m×6연동=4,092㎡,
    # 현장 논산시 지산동 362번지, PO필름 딸기). 최선동과 **동일 업체·동일 양식의
    # 2호 현장** — 한일그린텍(이영준·구창회)·서진비에스(강정구·오기수)에 이은
    # 세 번째 동일 업체 비교 쌍.
    # 공종별집계표 합계행(재 340,333,800+노 155,442,600+경 3,250,000)=원가계산서
    # 직접재료비·직접노무비·산출경비와 원단위 일치 — known_total 499,026,400 채택.
    # 도급 체인: 합계 524,010,222(간노 11%·산재 3.56%·고용 1.01%·기타경비 2.93%)
    # +일반관리비 27,547,217+이윤 16,443,760=공급가액 568,001,200 → 부가세
    # 49,999,900 → 영세율품목 68,002,200 → 총공사금액 618,001,000("천원미만절삭",
    # 한글 '일금 육억일천팔백만일천원정' 대사 일치). 부가세환급예정 21,876,144
    # (환급품목 218,761,440×10%)은 별행 병기 — 차감 전 표기 계열(맹주연과 동일).
    # ⚠️ **이 차수의 모든 집계는 합계열이 아니라 재+노+경 열합으로 계산했다** — 다온팜
    # 양식 2건에 합계열 갭이 **3건** 있다(91차 최초 기재는 여과기 1건만 들었다 — 레드팀
    # F7로 전수화): 한수진 r279 여과기 50mm 열합 90,000 vs 합계열 100,000(Δ10,000) ·
    # 한수진 r332 노무비(배관설비/배수구) 열합 6,120,000 vs **합계열 0** · 최선동 r9
    # 노무비 경비 열합 4,717,500 vs 합계열 4,719,000(Δ1,500). 재+노+경 열합만이 공종
    # 소계·원가계산서와 정합한다(맹주연 1원 계열과 동종의 원문 내부 갭).
    # 매핑(기존 선례 적용): 1기초·2철골·3부속자재·5농업용비닐자재→온실구조(피복은
    # 한일그린텍 선례), 4자동개폐장치·7커텐공사→자동개폐(보온커튼 확정 관례).
    # ⚠️ 4공종의 '콘트롤박스' 4,500,000원은 자동개폐 소속 — 한일그린텍 하우스콘트롤
    # 7,434,000·맹주연 컨트롤박스 5,400,000·강정구 3,800,000과 같은 구동 제어반
    # 대역이다. 다만 그 아래 금액 0인 단자 명세에 '일사량,기상대'가 적혀 있어
    # 강정구('센서·복합제어 라인 부재')보다 센서 포함 가능성이 크다[확인요망] —
    # 별도 센서 품목·금액 라인이 없어 ict 분리 근거로는 부족하다고 보고 유지
    # (ict 이동 가정 감응: auto 18.8→17.9%, ict 0→0.9%).
    # 🔴 **hvac 표본 최초의 냉방 실측**: 6공종에 블라젠 냉·난방기 삼상8마력 3대
    # 31,500,000(공간 냉난방)+냉·온수기 삼상8마력 2대 22,000,000(근권 냉온수)이
    # 실재한다 — 기존 12표본의 hvac은 전부 유동휀·환풍기·온수보일러 계열이었다.
    # 지온 계열 라인분리(백가은·조윤정 '근권배관' 선례): 8공종 지온엘보 660,000
    # +지온발소 303,600, 9공종 지온호스 1,734,000+지온새들 207,000 — 근권 냉온수
    # 분배 배관이라 본체(냉온수기)가 있는 hvac으로 귀속. 감응 0.58%p.
    # 8공종 '양액시설공사'(86,983,850)는 혼재 공종이라 명시 라인 분리(맹주연
    # 010108 방식): 양액기 마그마 17,000,000+원수탱크 5T 550,000+액비통 880,000+
    # 여과기 50mm 90,000+여과기 20mm 260,000+수위조절기 120,000+전선 200,000+원수탱크
    # 3T 380,000+교반기 600,000+급수모터 700,000+점적호스 700,000+피스 8mm 300,000+
    # 잡자재 200,000+부자재(양액기설치) 1,080,000=23,060,000→관수양액, 지온 963,600→hvac,
    # 잔여 62,960,250(상판·기둥파이프·침하방지판·쌍클립·바닥지·육묘상자(배드)·
    # 흑백비닐·방근포·상토·받침대설치 노무 14,620,000)→unclassified(이두희 5-3
    # 베드설치·백가은 4-5 베드시설 선례). 9공종 배관설비는 원예용수도관·전자변·
    # 배수파이프 계열이라 잔여 11,749,000→관수양액(이두희 5-2관수·5-4퇴수 선례).
    # 분류합 436,066,150+62,960,250=499,026,400(잔차 0).
    "한수진": {
        "greenhouse_structure": 237445740,   # 1기초(24,208,000)+2철골(61,670,790)+3부속자재(113,364,250)+5농업용비닐(38,202,700)
        "auto_opening_system": 93976810,     # 4자동개폐장치(6,660,000 — 콘트롤박스 4,500,000 포함)+7커텐공사(87,316,810)
        "hvac": 69834600,                    # 6유동휀·배기휀·냉난방(66,930,000 — 블라젠 냉난방기·냉온수기 53,500,000 포함)+지온 계열(2,904,600)
        "irrigation_fertigation": 34809000,  # 8 양액 계열 잔여(23,060,000)+9 배관설비 잔여(11,749,000)
        "ict_control": 0,                    # 독립 환경제어시스템 라인 없음(콘트롤박스는 구동 제어반 — 위 주석 [확인요망])
        "electrical": 0,                     # 별도 전기공사 공종 없음(전선류는 각 공종 내 산재)
    },
    # 2026-09-13 추가(91차 14호) — 스마트팜스펙/견적참조/
    # "스마트팜하우스(렉창)5연동견적서_최선동.xls"(다온팜, 청년자립형 스마트팜
    # 지원사업, 폭37m×길이85m×5연동=3,145㎡, 현장 논산시 부적면 마구평리 385-1,
    # 렉피니언 양개폐 PO필름). 한수진과 동일 업체·동일 9공종 양식 — 매핑 판단을
    # 한 번만 하고 두 현장에 그대로 적용했다(신규 판단 없음).
    # 공종별집계표 합계행(재 352,183,510+노 140,507,250+경 4,750,000)=원가계산서
    # 3항목과 원단위 일치 — known_total 497,440,760 채택. 도급 체인: 합계
    # 520,024,068+일반관리비 27,337,665+이윤 14,639,747=공급가액 562,001,482 →
    # 부가세 51,780,848[(공급가액-영세율품목 44,193,000)×10%] → 총공사금액
    # 613,782,000("천원미만절사", 한글 '일금 육억일천삼백칠십팔만이천원정' 일치).
    # ⚠️ 한수진과 부가세 비고 **표기**가 다르다 — 한수진 '제출용공급가액×10%',
    # 최선동 '(공급가액-영세율품목)×10%'. 📌92차 검산 결과 **산식은 동일**하다
    # (제출용공급가액 = 공급가액-영세율품목: 한수진 568,001,200-68,002,200=499,999,000,
    # ×10%=49,999,900로 원문 표기와 일치). 91차의 "산식이 다르다"는 표현을 정정한다
    # — 갈리는 것은 라벨뿐이다(값 채택 영향 없음).
    # 🔴 unclassified에 **무인방제 설비**가 처음 들어온다: 6공종 명칭이 "유동휀 및
    # 배기휀,무인방제기"인데 그 안의 '안개분무시설' 식1 18,500,000(영세율)은
    # 유동휀·배기휀과 성격이 다르고 13개 카테고리 어디에도 깔끔히 맞지 않는다 —
    # 강제 매핑하지 않고 unclassified(이두희 5-3 선례의 원칙). ⚠️ 원문이 세부
    # 내역을 주지 않아 **방제용인지 포그 냉방용인지 확정 불가**[확인요망]:
    # 공종명은 '무인방제기'라 방제로 읽었으나, hvac 귀속 가정 시 hvac 13.2→16.9%·
    # 미분류 13.7→10.0%로 3.7%p 움직인다(감응 큼 — 발주 전 확인 필요. 91차 최초 기재의
    # 17.0/9.9는 반올림 오기였다 — 레드팀 F4 정정: 84,139,400/497,440,760=16.91%,
    # 49,535,800/497,440,760=9.96%).
    # 📌 후보 기록(채택 아님): 무인방제기를 '9.기자재 구매'(생산성 향상 보조
    # 장비)로 볼 여지가 있다 — 그 카테고리는 현재 "미검증(근거문서 없음)"이라
    # 첫 실측이 될 수 있으나 카테고리 정의 확장은 판단성이라 사용자 결정 사안.
    # 나머지 매핑은 한수진과 동일. 4천창자동개폐장치의 '콘트롤박스 천창10단자'
    # 9,500,000은 **'콘트롤박스·하우스콘트롤' 명칭 계열 안에서만 최대**다(종전 한일그린텍
    # 7,434,000). ⚠️구동 제어반 계열 전체의 최대는 여전히 박규현 '동력피복제어기기'
    # 24,000,000원이다 — 91차가 이를 최선동으로 교체했다가 레드팀 F1로 철회했다.
    # ⚠️[확인요망] 한수진과 마찬가지로 콘트롤박스 아래 금액 0인 단자 명세에 '일사량,기상대'가
    # 있다(내역서 r147) — 별도 센서 품목·금액 라인이 없어 자동개폐 유지, ict 이동 감응 1.91%p.
    # 8공종 잔여 베드 계열 49,535,800(상판·기둥파이프·침하방지판·은흑바닥지·배드·
    # 흑백비닐·방근포·상토·받침대설치 노무 14,000,000)+안개분무 18,500,000=
    # unclassified 68,035,800. 분류합 429,404,960+68,035,800=497,440,760(잔차 0).
    "최선동": {
        "greenhouse_structure": 198839100,   # 1기초(27,797,500 — 판넬공사 11,950,000 포함)+2철골(52,536,750)+3부속자재(88,677,050)+5농업용비닐(29,827,800)
        "auto_opening_system": 136356260,    # 4천창자동개폐(51,928,500 — 콘트롤박스 9,500,000 포함)+7커텐공사(84,427,760)
        "hvac": 65639400,                    # 6공종(81,345,000)−안개분무 18,500,000+지온 계열(2,794,400)
        "irrigation_fertigation": 28570200,  # 8 양액 계열 잔여(17,415,000)+9 배관설비 잔여(11,155,200)
        "ict_control": 0,                    # 독립 환경제어시스템 라인 없음(한수진과 동일 구조)
        "electrical": 0,                     # 별도 전기공사 공종 없음
    },
    # 2026-09-13 추가(91차 15호) — 스마트팜스펙/견적참조/"수현건설임미라님견적서.xls"
    # (㈜수현건설[대표 김현국, 논산시 강변로], 2026-06-10, 설치규격 7.5×90.4m
    # 6연동 4,258.86㎡[원문 단위 표기 '㎥'는 오기]). 83차가 "논산 3사" 조사에서
    # 다겹보온커튼 구성 매핑 불가를 확인했던 바로 그 문서 — 이번엔 CAPEX 공종
    # 분해 목적으로 편입한다.
    # ⚠️ **집계 레벨이 다른 표본**: 이 견적서엔 제경비·일반관리비·이윤·부가세가
    # 없다. 총괄표 직접재료비 463,233,160+직접노무비 97,511,600=560,744,760이
    # 그대로 집계표 합계이자 계약 표기 금액(한글 '일금 오억육천칠십사만사천칠백
    # 육십 원정')이다 — 즉 **known_total과 계약금액이 같다**(박규현의 재+노 2요소
    # 레벨보다 한 걸음 더 나간 형태). 따라서 이 표본의 ㎡당 단가(131,665원/㎡ —
    # 560,744,760/4,258.86=131,665.46, 91차 최초 기재 131,666은 반올림 오기[레드팀 F5])는
    # ACTUALS(부가세 포함 최종 총공사금액)와 **같은 축이 아니다** — 밴드 비교 금지.
    # ⚠️[확인요망] 표기 면적과 규격이 맞지 않는다(레드팀 F6): 표지 '7.5 X 90.4M 6연동'을
    # 곱하면 4,068㎡인데 표기는 4,258.86으로 **+4.69%** 크다(방풍·관리동 포함 여부 미상).
    # 상세시트 인건비 수량 4,258과는 일치해 4,258.86을 채택했으나, ㎡당 단가가 전적으로
    # 이 값에 의존하므로 원문 확인 전까지 참고치다.
    # 🔴 **원문 중복계상 6,000,000원 발견**: 집계표의 '자동개폐시설및 복합환견제어
    # (ICT)' 행은 재료비 45,252,000+노무비 6,000,000=51,252,000인데, 상세시트
    # 두 블록의 소계는 재 39,252,000+노 6,000,000=45,252,000이다. 즉 집계표
    # 재료비 칸에 상세시트의 **합계**(45,252,000)가 들어가 노무비 6,000,000이
    # 두 번 계상됐다. 총괄표·계약 한글금액이 모두 이 부풀린 값 위에 서 있어
    # known_total은 문서의 운용값 560,744,760을 그대로 채택하되(맹주연 '구성 합
    # 채택'과 반대 방향의 판단 — 여기선 3중 표기가 전부 일치하는 쪽이 집계표다),
    # 카테고리 분류는 상세시트 라인 기준이라 차액 6,000,000이 unclassified로
    # 남는다. **미분류에 원문 결함분이 섞여 있음을 명시한다**(감추지 않음).
    # 🔴 **표본 6번째의 독립 ICT + 두 번째 축열조 실측**:
    #   ict_control 15,230,000 = 상세시트 '복합환경제어(ICT)' 블록 전액(관제씨스템
    #   SUNNET 9,200,000·통합모니터 S/W 1,500,000·우적/일사량/풍향풍속/온습도
    #   센서·센서컨버터·기상봉·SPD·피뢰침·인건비) — 센서·복합제어 라인이 실재해
    #   구동 제어반(콘트롤박스 복합40호기 5,000,000, 자동개폐 소속)과 명확히 갈린다.
    #   국산 SUNNET 계열로 마그마 3건(17.9~26.2M)보다 낮고 PRIVA 2건과는 다른 대역.
    #   thermal_storage_insulation 11,000,000 = 히트펌프 블록 내 '축열조탱크 FRP보온
    #   20톤' 라인분리(윤성호 축열조 90ton 41,958,000 선례 — 이 카테고리 2번째 실측).
    # 매핑: 골조공사(184,464,840)+피복공사(37,693,320)→온실구조. 자동개폐 상세시트
    # 블록1(30,022,000) 중 배기환풍기 1,500,000+유동팬 60대 7,200,000+천창배기팬
    # 36대 3,060,000+팬시설 인건비 3,000,000=14,760,000→hvac(윤성호 0109 선례),
    # 잔여 15,262,000(콘트롤박스·커텐모터·비닐/부직포개폐기·렉창모터·전선·개폐기
    # 인건비)→자동개폐. 커튼공사 90,913,900→자동개폐. '양액시설, 및 난방' 시트는
    # 4개 명명 블록으로 갈린다: 양액기및시설 22,440,000→관수양액 / 히트펌프
    # 44,920,000−축열조 11,000,000=33,920,000→hvac / 무인방제시설 25,107,700→
    # unclassified(최선동 안개분무와 동일 판단 — 여기선 견인장치·약대·고압펌프·
    # 레일파이프까지 품목이 전개돼 **방제 설비임이 명확**하다) / 배드시설
    # 85,953,000은 혼재라 명시 라인 분리 — 관수·배수 계열 5,080,400(수도관·융착
    # 부속·라인밸브·PVC배수·배수트랩·점적호스·관수새들)→관수양액, 지온호스
    # 2,940,000+엑셀연결부속 1,008,000=3,948,000→hvac(근권 온수, 본체는 같은
    # 시트의 수냉식온수기), 잔여 76,924,600(배드 3,654개·기둥/중방파이프·가로장·
    # 배드받침·바닥지·흑백필름·반근지·상토·포크레인/롤러 장비·인건비 17,032,000)
    # →unclassified. 집계표 단독 2행 물류및장비 8,000,000·컨설팅의뢰비 10,000,000은
    # 상세시트가 없고 13분류 어디에도 안 맞아 unclassified(컨설팅의뢰비를
    # '10.설계·감리비'로 볼 여지가 있으나 설계·감리 용역 명시가 없어 강제 매핑
    # 안 함 — 그 카테고리는 참고요율 상태 유지).
    # ⚠️ 선례 불일치 기록(백로그): 백가은·조윤정의 '4-5 베드시설'은 블록 전량을
    # unclassified로 뒀는데 여기선 배드시설 블록 안의 관수·지온 라인을 분리했다.
    # 이번 차수의 분리 규칙은 "①그 설비의 **본체**가 같은 문서에 실재하고 ②라인
    # 명칭이 그 설비에 명확히 귀속될 때만 분리"이고 임미라는 양액기·수냉식온수기가
    # 같은 시트에 있어 둘 다 충족한다. 백가은 재검토는 별도 차수(값 미변경).
    # unclassified 126,032,300 = 배드 잔여 76,924,600+무인방제 25,107,700+물류및
    # 장비 8,000,000+컨설팅의뢰비 10,000,000+**원문 중복계상 6,000,000**.
    # 분류합 434,712,460+126,032,300=560,744,760(잔차 0).
    "임미라": {
        "greenhouse_structure": 222158160,   # 골조공사(184,464,840)+피복공사(37,693,320)
        "auto_opening_system": 106175900,    # 자동개폐 블록1 잔여(15,262,000)+커튼공사(90,913,900)
        "hvac": 52628000,                    # 팬 계열(14,760,000)+히트펌프 잔여(33,920,000)+지온 계열(3,948,000)
        "irrigation_fertigation": 27520400,  # 양액기및시설(22,440,000)+배드시설 내 관수·배수(5,080,400)
        "ict_control": 15230000,             # 복합환경제어(ICT) 블록 전액 — SUNNET 관제+센서류(센서 실재 표본)
        "electrical": 0,                     # 별도 전기공사 공종 없음(전선류는 각 블록 내 산재)
        "thermal_storage_insulation": 11000000,  # 축열조탱크 FRP보온 20톤(히트펌프 블록 내 라인분리, 윤성호 선례)
    },
}
# 위 6개 항목 외(7~13, unclassified) 미기재 케이스 → capex_major_breakdown()이 0 채움.
# unclassified_direct_cost(qa_safety 잔액) — 원문 총액 재대조용, 별도 기록.
CAPEX_MAJOR_UNCLASSIFIED = {"우민재": 2679227, "최혁진": 0, "이두희": 101301410,  # 이두희=베드설치(5-3)
                            "윤성호": 39220352,  # 윤성호=행잉거터(0110)+작물와이어(0111), 재배시설 성격
                            "한일그린텍": 46519015,  # 스탠딩 거터(스티) 67.5m 28줄 — 재배시설 성격(이두희·윤성호 선례)
                            "이준희": 93326116,  # 행잉거터(65,624,205)+유인줄(19,138,167)=재배시설 + 기타공사(8,563,744)=선홈통·바닥배수 부대
                            "맹주연": 46977648,  # 020109 바닥재및행잉거터(딸기) — 행잉거터 1,900m·바닥재·지반정리 장비, 재배시설 성격(윤성호 선례)
                            "강정구": 0,  # 미분류 0(최혁진에 이어 두 번째) — 부분 범위 견적(골조·개폐·피복만)이라 5공종 전부 매핑 가능
                            "오기수": 39821638,  # 4. 행잉거터설치 — 딸기 거터 2,300m, 재배시설 성격(윤성호·이준희·맹주연 선례)
                            "백가은·조윤정": 63336900,  # 4-4 바닥제(5,580,000)+4-5 베드시설(47,356,900 — 이두희 선례)+8 기타 장비대(10,400,000 — 공용 임대)
                            "박규현": 77758030,  # b-3 베드및벤치(코코피트·거터·레일파이프·운반레일 — 재배·물류 시설, 이두희 5-3 선례)
                            "구창회": 51387099,  # 스탠딩 거터(스티) 76.5m 30줄 — 재배시설 성격(한일 1호와 동일 계열)
                            "한수진": 62960250,  # 8공종 내 베드 계열(상판·기둥파이프·육묘상자·상토·받침대설치 노무) — 이두희 5-3 선례
                            "최선동": 68035800,  # 8공종 베드 계열 49,535,800 + 안개분무시설(무인방제) 18,500,000 — 후자는 13분류 미해당[확인요망]
                            "임미라": 126032300}  # 배드시설 잔여 76,924,600+무인방제 25,107,700+물류및장비 8,000,000+컨설팅의뢰비 10,000,000+원문 중복계상 6,000,000

# 표본별 known_total(직접공사비 분모) 단일 출처 — 2026-08-18 53차(레드팀 4회차 F8
# 구조 개선): 종전엔 같은 값이 build_site.py 지역변수 major_totals와 test_engine.py
# 앵커 리터럴에 이중 하드코딩되어, 한쪽만 드리프트해도 테스트가 잡지 못했다(5표본
# 공통 선재 — 52차 이준희 추가로 6표본). 이 상수가 유일한 출처이고 build_site는
# 이를 그대로 읽는다. 값은 기존 하드코딩과 동일(변경 없음) — 각 값의 원문 대조
# 전문은 CAPEX_MAJOR_CASE_CHUNKS 블록 주석·레지스트리 source 참조. 앵커:
# test_engine.py의 케이스별 reconcile 테스트가 원문 리터럴(cb.total == N)로 고정.
CAPEX_MAJOR_KNOWN_TOTALS = {
    "우민재": 456_158_140,      # major합+qa_safety 원단위 일치(공사내역서, 2026-07-16)
    "최혁진": 694_575_784,      # major합 원단위 일치(공사비 내역서, 2026-07-16)
    "이두희": 433_606_460,      # 원가계산서 14개 세부공종 합계열 총합(2026-07-21)
    "윤성호": 1_162_078_090,    # 공종별집계표 p3=원가계산서 p2 재+직노+산출경비(2026-08-17 P2-17)
    "한일그린텍": 355_597_412,  # 집계표 p4 소계=원가계산서 p3 재+직노+기계경비(51차 — 환급금 재투자 22,635,750 별도)
    "이준희": 1_010_337_181,    # 집계표 합계행=원가계산서 직재+직노+산출경비(52차 — 실부담 1,172,765,000 별도 기록)
    "맹주연": 439_742_227,      # 집계표 13공종 열합=원가계산서 직재+직노+기계경비(55차 — 총계행 표기 439,742,226은 원문 1원 갭, 구성 합 채택)
    "강정구": 296_921_284,      # 집계표 5공종 합=원가계산서 직재+직노+산출경비(56차 — 부분 범위 견적, 2022-04 물가 시점 주의)
    "오기수": 199_574_938,      # 집계표 7공종 합=원가계산서 직재+직노+산출경비(57차 — 설비 전용 부분 범위, 강정구와 상보 쌍)
    "백가은·조윤정": 398_628_383,  # 집계표 8공종 합=원가계산서 직재+직노+산출경비(59차 — 쌍 견적 22p 동일이라 통합 1건, 두 파일 refs)
    "박규현": 534_896_253,      # 집계표 12공종 합=원가계산서 직재+직노(60차 — ⚠️ 경비 열 없는 표본: 재+노 2요소 레벨)
    "구창회": 378_864_599,      # 집계표 7공종 소계=원가계산서 직재+직노+기계경비(61차 — 한일그린텍 2호 현장, 환급 재투자 21,580,478 별도)
    "한수진": 499_026_400,      # 집계표 합계행=원가계산서 직재+직노+산출경비(91차 — 총공사금액 618,001,000 별도, 다온팜 1호 현장)
    "최선동": 497_440_760,      # 집계표 합계행=원가계산서 직재+직노+산출경비(91차 — 총공사금액 613,782,000 별도, 다온팜 2호 현장)
    "임미라": 560_744_760,      # 집계표 합계=총괄표 직재+직노 (91차 — ⚠️ 제경비·이윤·부가세 없는 표본: known_total이 곧 계약 표기액, 원문 중복계상 6,000,000 포함)
}


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
    # 54차 레드팀(5회차) F3: 반올림은 표시 정밀도(1자리)로 한 번만 — 2자리 선반올림
    # 후 렌더의 :.1f 재반올림이 겹치면 .x5 경계에서 원문 재계산과 어긋난다(이준희
    # 온실구조 55.849% → 55.85 → 55.9 vs 단일 반올림 55.8). 9키 capex_breakdown
    # 쪽은 동일 패턴이나 OBSERVED_RANGE 경계 판정과 얽혀 별도 검토(백로그).
    shares = {k: (round(v / known_total * 100, 1) if known_total else 0.0) for k, v in filled.items()}
    return CapexMajorBreakdown(filled, unclassified, known_total, shares)


# ─────────────────────────────────────────────────────────────
# 시공: 실측 벤치마크 밴드 대조 (엔진데이터 A-11)
#   ※ ACTUALS 는 현재 7건. (원 지침은 8건이나 1건 데이터 미확보 → 7건으로 유지)
#   2026-07 스마트팜스펙/ 실문서 대조: 최혁진·이두희 기존값 정확히 일치(실측 확정),
#   우민재 신규 추가(공사내역서 총공사비 557,152,000원 확인) → 필름 밴드 상한 220→240 확대.
#   2026-08-17 P1-7 해명: ACTUALS의 집계 기준은 "부가세 포함 최종 총공사금액"으로
#   원문 보유 3건 전부 일관 확인 — 이두희 582,455,045=공급가액 520,275,969+부가세
#   52,027,596+영세율적용(자동모터개폐) 10,151,480(갑지 p1 원단위 재현, 07-21 미해명
#   62,179,076원 차이는 부가세+영세율이었음), 최혁진 930,000,000=총계 853,929,346+
#   부가세(단위절삭), 우민재 557,152,000=총원가+부가세+재해예방기술지도비 950,000.
#   CAPEX_MAJOR_CASE_CHUNKS의 known_total(직접공사비 기준)과는 집계 레벨이 다를 뿐
#   둘 다 정확하다.
#   2026-08-18 40차 — 한일그린텍 원문 대조 완료: 스마트팜스펙/한일그린텍/
#   설계예산서(한일그린텍).pdf(2026-04-21, 이영준 귀하, "2026년 청년 자립형
#   스마트팜 지원사업(3202㎡)") p2~3에서 총공사비 480,636,000 원단위 일치
#   (절사 전 480,636,200 = 공급가액[과세 236,626,148+환급 160,021,553+영세
#   19,424,405]+부가세 39,664,769+환급금 재투자 24,899,325 — "부가세 포함 최종
#   총공사금액" 기준선과 정합, 한글 '일금사억팔천육십삼만육천원정' 대사 일치).
#   면적 3202㎡=재배동 9.6m×78m×4연동 2,995㎡+방풍(폭 1.5m) 포함. 단 문서 성격이
#   "설계예산서"(물가변동 시 조정 조항 명시 — 계약 확정액 아님)라 공주장원리
#   전례대로 값 유지·"원문 대조 완료(설계예산)" 판정만 기록, 실측 확정 격상은
#   계약·정산 확인 시.
#   2026-09-13 92차 — ★사용자 결정으로 **한수진·최선동 2건 신규 편입**(7→9건).
#   91차가 CAPEX 표본으로 편입하며 "추가 자격은 갖췄으나 벤치마크 기준 변경은
#   판단성"이라 후보로만 남겼던 건이다(61차 구창회 관례). 원문 대조:
#     한수진 — 스마트팜스펙/견적참조/한수진스마트팜딸기하우스견적서.xls(다온팜,
#       "2026년 청년자립형 스마트팜 보급 지원사업", 논산시 지산동 362, 폭44m×길이93m
#       ×6연동=4,092㎡, PO필름 딸기). 원가계산 시트 체인 원단위 재현: 순공사원가 계
#       524,010,222(간노 11%·산재 3.56%·고용 1.01%·기타경비 2.93%)+일반관리비
#       27,547,217+이윤 16,443,760=공급가액 568,001,200 → 부가세 49,999,900
#       [(공급가액-영세율품목 68,002,200)×10%] → 합 618,001,100 → **천원미만절삭
#       618,001,000**(한글 '일금 육억일천팔백만일천원정' 대사 일치). 151,027원/㎡.
#     최선동 — 스마트팜스펙/견적참조/스마트팜하우스(렉창)5연동견적서_최선동.xls
#       (다온팜 2호 현장, 논산시 부적면 마구평리 385-1, 폭37m×길이85m×5연동=3,145㎡,
#       렉피니언 양개폐 PO필름). 순공사원가 계 520,024,068+일반관리비 27,337,665
#       +이윤 14,639,747=공급가액 562,001,482 → 부가세 51,780,848[(공급가액-영세율
#       품목 44,193,000)×10%] → 합 613,782,330 → **천원미만절사 613,782,000**
#       (한글 '일금 육억일천삼백칠십팔만이천원정' 일치). 195,161원/㎡.
#     → 두 건 모두 **"부가세 포함 최종 총공사금액"**이라는 ACTUALS 집계 기준(P1-7)에
#       정확히 부합한다. 📌 91차가 "부가세 산식이 다르다"고 적었던 것은 **표기 차이**일
#       뿐이다 — 한수진 비고 '제출용공급가액×10%'의 제출용공급가액 = 공급가액-영세율
#       품목이라 두 문서의 산식은 수치까지 동일하다(92차 검산으로 확인, 91차 표현 정정).
#   ⚠️ **문서 성격은 견적서다** — 계약서·정산서가 아니다. 한일그린텍(설계예산서)
#     전례와 같은 등급이고, 기존 확정액 계열 3건(이두희·최혁진·우민재)보다 약하다.
#     계약·정산 확인 시 실측 확정으로 격상한다. 이 때문에 ACTUALS_COUNT의 status는
#     여전히 '부분실측'이다.
#   ⚠️ **BENCHMARK_BANDS는 바꾸지 않았다** — 151,027·195,161이 둘 다 필름 밴드
#     (115,000~240,000) 안이라 경계가 움직이지 않는다. 밴드 근거는 그대로
#     공주 120,000 ~ 우민재 240,000이다(92차는 밴드 내부 관측을 2건 늘렸을 뿐이다).
#   면적은 문서의 **사업량 표기**를 그대로 쓴다(한일그린텍 3,202 전례) —
#     44×93=4,092 · 37×85=3,145로 규격 곱과 일치한다.
#   ✅ 2026-09-13 93차 — 92차가 [확인요망]으로 남긴 **관리동·방풍 포함 여부가
#     도면으로 확정됐다**(사용자 지시 "h 진행"). 근거는 각 10종 도면 중 평면도·
#     측면골조도·주단면도(스마트팜스펙/견적참조/"한수진 - *.pdf"·"최선동 - *.pdf").
#     ① **관리동(작업동)은 온실 외곽 사각형 안이다** — 평면도가 사각형 내부에
#       '관리동'(한수진)·'작업동'(최선동) 라벨과 폭 9,000을 찍었고, 내역서의
#       작업동바닥콘크리트타설 규격이 **9m×42m**(한수진)·**9m×35m**(최선동)로
#       **골조 스팬 폭과 정확히 일치**한다. 별동이 아니라 온실 안의 구획이다.
#       (최선동 '판넬공사(출입문포함) 35m×5m'은 바닥이 아니라 칸막이 벽 —
#       골조 폭 35m × 측고 5m이고, 정면골조도의 측고 5,000과 맞는다.
#       '관리동 비닐 0.1*500*37'의 37m도 사업량 폭과 일치.)
#     ② **사업량 폭은 골조 스팬 합보다 2,000 크다** — 한수진 44,000 vs 42,000
#       (6연동×7,000) · 최선동 37,000 vs 35,000(5연동×7,000). 양측 1,000씩이고
#       주단면도의 '일중방풍벽·1중방풍개폐구동축·1중방풍가로대·방풍치마' 구성과
#       정합한다 → **방풍 폭이 포함된 외곽 치수**다(한일그린텍 3,202과 같은 관례).
#     ③ **견적서 자체가 이 면적을 단가 분모로 쓴다** — 노무비 라인이 단위 ㎡에
#       수량 4,092(한수진 4개 라인)·3,145(최선동 5개 라인)를 그대로 넣는다
#       (예: 4,092×18,450=75,497,400). ACTUALS 분모로 쓰는 근거가 여기 있다.
#     ⚠️ 길이 방향 처리는 두 도면이 다르다 — 한수진 93,000=31×3,000(추가 없음),
#       최선동 85,000=28×3,000+1,000. 후자의 +1,000이 무엇인지는 도면 텍스트로
#       확정되지 않는다[확인요망]. 배치도 2종은 치수 텍스트가 추출되지 않아
#       (벡터/이미지) **부지 내 별동 존재 여부는 확인하지 못했다**.
#   🔴 93차 부수 발견 — **ACTUALS의 면적 기준이 표본마다 같지 않다**:
#     이두희 2,736은 규격 8m×6연동×57m 역산값이라 **골조 순면적(방풍 미포함)**이고,
#     한일그린텍 3,202·한수진 4,092·최선동 3,145는 **방풍 포함 외곽**이다.
#     같은 온실을 어느 기준으로 재느냐로 ㎡당 단가가 **4.8~7.0% 움직인다**
#     (한수진 151,027↔158,218[골조스팬]↔175,170[재배동만] · 최선동 195,161↔
#     208,769↔233,822 · 한일그린텍 150,105↔160,479[재배동 2,995]).
#     → **밴드 대조는 이 정도의 기준 혼재를 안고 있다**(밴드 폭이 115k~240k로
#     2.1배라 현재 9건의 정상/경계 판정은 어느 기준으로도 바뀌지 않음을 확인).
#     ⚠️ 다만 **우민재 239,841원/㎡는 필름 밴드 상한 240,000에 159원 차로 붙어
#     있고**(0.07%), 그 상한 자체가 우민재에서 유도된 값이다.
#
#   ── 2026-09-13 94차: 면적 기준 통일 시도 → **통일 불가 판정**(사용자 지시 "a 진행") ──
#   93차가 선행 조건으로 지목한 **우민재 면적 기준을 확정했다**:
#     `스마트팜스펙/우민재/3. 공사설명서(우민재).pdf` p1 면적표 —
#       온실/방풍실 2,001.67 + 작업장 320.20 = **합계 2,321.87㎡**(비닐 온실)
#       규격: 온실내부 폭 8m·길이 60m×4동·40m×1동 / **방풍벽 폭 1.0m**
#     `0. 도면(우민재).pdf` 배치도 면적개요 — 온실내부 1,921.6(32m×60.05m)
#       + 방풍벽 80.07(1M×60.05m, 20.02m) + 작업장 320.2(8m×40.02m)
#       = **2,321.87** · 폭 41M = 온실 4동 32 + 작업장 1동 8 + 방풍벽 1.
#     → 우민재도 **방풍벽·작업장을 포함한 외곽 면적**이다. 한일그린텍·한수진·
#       최선동과 **같은 기준**이고, 93차가 우려한 "상한 앵커의 기준 미상"은 해소됐다.
#   🔴 그 과정에서 **우민재 원문 내부 불일치**를 발견했다 — 같은 문서철의
#     공사비내역서 총표지는 "경량철골온실(내재해형) =2,323m2"라 적고, 설계설명서·
#     도면 면적개요는 **2,321.87**이다(Δ1.13㎡, 0.05%). `ACTUALS`의 2,323은
#     총표지 계열이다. 2,321.87을 쓰면 239,842 → **239,958원/㎡**로 필름 밴드
#     상한 240,000과의 간격이 159원 → **42원**으로 줄어든다. ⚠️`ACTUALS` 값
#     교체는 회귀 기준 변경이라 **하지 않았다**(판단성 — 사용자 결정 사안으로 기록).
#   🔴 **기준 통일은 성립하지 않는다** — 9건의 면적 근거가 이렇게 갈린다:
#     [방풍 포함 확정 4건] 우민재 2,323(94차)·한일그린텍 3,202(40차)·
#       한수진 4,092·최선동 3,145(93차 도면)
#     [방풍 미포함 확정 1건] 이두희 2,736 = 8m×6연동×57m **규격 역산**이다.
#       그런데 같은 설계예산서에 "2. 방풍벽 골조자재" 5,590,946원(방풍벽[측면]
#       210본·[마구리] 120본)이 실재한다 — **방풍이 시공되는데 면적엔 없다**.
#       방풍 폭이 원문에 없어 환산도 불가하다[확인요망].
#     [기준 미확인 1건] 최혁진 3,459 — 내역서가 이 수량을 단가 분모로 쓰지만
#       (건축물 현장정리·수평보기·구조부 먹매김·폐기물 수집·알미늄 후레임)
#       면적 개요표가 없다. 유리온실이라 방풍 공종 자체가 0건이다.
#     [원문 미보유 3건] 공주장원리 3,759·당진이상근 3,030·원채원 3,456 —
#       89차가 파일명 전수 검색으로 0건을 확인했다. **기준을 물어볼 문서가 없다.**
#   🔴 따라서 **밴드 재산정도 할 수 없다**: 필름 밴드의 하한 앵커
#     "공주120"(450,000,000/3,759=119,712)이 바로 그 **원문 미보유 3건 중
#     하나**다. 상한 앵커 우민재는 94차에 확정됐으나 하한이 미확정인 채로
#     밴드를 다시 그으면 근거 없는 경계가 된다.
#   → 이 차수가 한 일: 선행 조건(우민재)을 해소하고, **통일이 어디서 막히는지를
#     확정**했다. 밴드·ACTUALS 값은 건드리지 않았다. 다음 선택지는 판단성이다 —
#     ⓐ원문 미보유 3건 확보 요청 후 재시도 ⓑ이두희만 방풍 포함으로 환산(방풍
#     폭 확인 선행) ⓒ기준 혼재를 명시한 채로 밴드 유지(현행).
#   ── ACTUALS 원문 대조 현황(92차 기준) ──
#   원문 대조 완료 6건: 이두희·최혁진·우민재(P1-7, 확정액 계열)+한일그린텍(40차,
#     설계예산 — 원단위 일치)+한수진·최선동(92차, 견적서 — 원단위 일치).
#     근접 대조 1건: 공주장원리(이동혁 견적 448,000,000
#     vs 450,000,000, 0.4% 차 — 견적서라 값 유지, P2-17). 미대조 2건: 당진이상근
#     (원문 미발견)·원채원(원문 미보유 — 회귀 기준 케이스인데 A-11 지침값,
#     43차 provenance 통일 시 확보 요청 목록 등재).
# ─────────────────────────────────────────────────────────────
# (하한, 상한) 원/㎡
BENCHMARK_BANDS = {
    Cover.FILM:     (115000, 240000),   # 공주120 ~ 우민재240 (이두희213 · 92차 한수진151·최선동195는 밴드 내부 — 경계 불변)
    Cover.GLASS:    (180000, 230000),   # 원채원203
    Cover.FLUORINE: (230000, 310000),   # 최혁진269
}
# 실측 9건(면적/총액/피복) — 회귀 테스트 근거
ACTUALS = [
    ("공주장원리", 3759, 450000000, Cover.FILM),
    ("한일그린텍", 3202, 480636000, Cover.FILM),
    ("당진이상근", 3030, 512480000, Cover.FILM),
    ("원채원",     3456, 702030000, Cover.GLASS),
    ("이두희",     2736, 582455045, Cover.FILM),
    ("최혁진",     3459, 930000000, Cover.FLUORINE),
    ("우민재",     2323, 557152000, Cover.FILM),
    # 2026-09-13 92차 ★사용자 결정 편입(위 블록 주석에 원문 체인 전문) —
    # 문서 성격은 **견적서**(한일그린텍 설계예산서와 같은 등급, 확정액 계열보다 약함).
    ("한수진",     4092, 618001000, Cover.FILM),   # 다온팜 1호, 논산 지산동 — 151,027원/㎡
    ("최선동",     3145, 613782000, Cover.FILM),   # 다온팜 2호, 논산 부적면 — 195,161원/㎡
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
                         t_target: float, t_min: float,
                         fr: Optional[float] = None,
                         surface_area_m2: Optional[float] = None,
                         safety: float = HEATING_SAFETY_FACTOR,
                         degree_hours: float = DEGREE_HOURS_DEFAULT,
                         efficiency: float = HEATING_EFFICIENCY_DEFAULT, fuel: str = "등유",
                         required_categories: Optional[list] = None,
                         curtain: Optional[str] = None,
                         crop: Optional[str] = None,
                         wind_factor: float = 1.0) -> RfqPackage:
    """설계 축 함수만 호출해 구조화한 RFQ 사양서(=구조화 사양표, CAD 도면 아님).
    form(연동/단동/광폭)은 판단성 결정이라 필수 인자로 받는다 — 엔진이 임의로
    고르지 않는다. 해당 지역강도를 만족하는 규격이 그 형식에 없으면 예외.
    area_m2는 바닥면적(방법A/B 평단가·벤치마크 기준, render_report.py의
    FarmInput.area_m2와 동일 의미). surface_area_m2는 난방부하 계산용 표면적
    (지붕·측벽 포함, 바닥면적보다 큼) — 미지정 시 area_m2로 근사(단동 등
    표면적≈바닥면적에 가까운 경우만 정확, 연동형은 실측값을 넘기는 것을 권장)."""
    sel = select_specs(region_snow_cm, region_wind_ms, form, crop=crop)  # P1-11: 작물 필터 위임
    chosen = sel["min_by_form"].get(form)
    if chosen is None:
        raise ValueError(
            f"'{form}' 형식으로 지역 설계강도(적설{region_snow_cm}cm·풍속{region_wind_ms}m/s)를 "
            f"충족하는 규격이 없다")
    surf = surface_area_m2 if surface_area_m2 is not None else area_m2
    # P1-9: fr/curtain을 그대로 위임 — 정확히-하나 검증은 heating_load()가 수행
    # 96차: wind_factor는 그대로 위임한다(값 검증은 heating_load가 수행).
    #   호출부가 [표 3-3-44] MONTHLY_MEAN_WIND_MS → mean_wind() → 
    #   wind_correction_factor()로 구해 넘긴다 — 엔진이 지역·동절기를 고르지 않는다.
    heating = heating_load(surf, cover.value, t_target, t_min, fr, safety,
                           degree_hours, efficiency, fuel, floor_area_m2=area_m2,
                           curtain=curtain, wind_factor=wind_factor)
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
# 설계 대안 비교 (2026-09-13, 75차 신설 — 컨설팅 흐름 "몇 가지 대안 선정" 단계)
#   경위: 사용자 첨부 자료 5종 검토에서, 같은 입지조건 위에 규격·피복·커튼
#   조합을 달리한 대안을 나란히 놓는 계층이 엔진에 통째로 없음을 확인했다.
#   `compare_quotes`는 "같은 사양서에 여러 업체 견적"(7단계)이고, 이 함수는
#   "같은 입지에 여러 설계안"(4단계)이라 대상이 다르다.
#   ⚠️ 새 계산은 하나도 하지 않는다 — select_specs·heating_load·
#   verify_heating_vs_actual·greenhouse_total_estimate·structure_only_estimate를
#   호출해 한 표로 모을 뿐이다(1절 "병렬 계산기 금지"). 새 상수도 없다.
#   ⚠️ `compare_quotes`와 달리 "최저비용"·"최소부하" 같은 참고 순위 필드를
#   두지 않는다(75차 사용자 확인). 업체 비교는 금액이라는 단일 축이 있지만
#   설계 대안의 우열은 작목·작형·운영조건에 따라 뒤집히므로, 참고정보로
#   노출해도 판정으로 읽힌다 — 대안 선정은 판단성 영역이다.
#   ⚠️ 설계강도 미달·미등재 대안도 행에서 빼지 않는다. 사용자가 올린 대안을
#   조용히 버리면 "왜 빠졌는지"가 산출물에 남지 않는다 — spec_ok 플래그와
#   notes로 드러낸다.
#   ⚠️ 도달성(12~14회차 교훈): 75차 시점에 이 함수는 build_site·webapp 렌더
#   경로에 연결돼 있지 않다 — 산출물 수치에 참여하지 않는다. 이 사실은 주석이
#   아니라 `test_compare_design_options_not_wired_into_render_paths`가 지킨다
#   (19회차 F4 — 74차 test_cluster_..._unreached와 같은 관례).
#   ⚠️ 렌더 연결 전에 처리할 입력 가드 4건(19회차, 76차 범위 — 셋 다 heating_load
#   기존 동작이라 이번 차수 범위 밖):
#     ①cover 미지원 문자열 → U_DESIGN→U_VALUE→5.7 순 폴백으로 예외도 note도
#       없이 계산된다. 5.7은 2026-07-19에 교체돼 어느 표에도 없는 고아값이다
#       (14회차 F3이 FUEL_LHV 8170 폴백을 같은 사유로 제거한 선례).
#     ②curtain 오타는 반대로 ValueError로 비교표 전체를 소멸시킨다 — 같은 표
#       안에서 오류 처리 원칙이 갈린다(spec_name 미등재는 행을 남기는데).
#     ③floor_area_m2=0은 falsy라 표면적으로 조용히 폴백해 heating_verify가
#       "재확인"에서 "정상"으로 뒤집힌다.
#     ④area_py=0은 개산 0원을 note 없이 낸다(미등재 None과 구분 불가).
# ─────────────────────────────────────────────────────────────
@dataclass
class DesignOption:
    """설계 대안 1건의 입력. surface_area_m2(표면적)는 난방부하용,
    area_py(평)는 개산 단가용 — 서로 다른 면적이므로 호출부가 각각 준다."""
    label: str                      # 대안 이름(사용자 지정, 표 식별용)
    spec_name: str                  # SPEC_TABLE 규격명
    cover: str                      # U_VALUE/U_DESIGN 키("유리"/"필름"/…)
    curtain: str                    # FR_TABLE 피복조합명
    area_py: float                  # 재배면적(평) — 평단가 개산용
    surface_area_m2: float          # 온실 표면적(㎡) — 난방부하용
    t_target: float                 # 난방 목표온도(℃)
    t_min: float                    # 설계 외기온(℃)
    floor_area_m2: Optional[float] = None   # 면적당 부하 분모(미지정 시 표면적)


@dataclass
class DesignOptionRow:
    label: str
    spec_name: str
    cover: str
    curtain: str
    spec_ok: Optional[bool]         # 입지 설계강도 충족 여부(None=SPEC_TABLE 미등재)
    snow_cm: Optional[int]          # 그 규격의 설계 적설심
    wind_ms: Optional[int]          # 그 규격의 설계 풍속
    max_load_kcal_h: float
    load_per_m2: float
    heater_capacity_kcal_h: float
    heating_verify: dict            # verify_heating_vs_actual() 결과 그대로
    greenhouse_total_won: Optional[float]   # 평단가 미등재 규격이면 None(0 날조 금지)
    structure_only_won: float


@dataclass
class DesignOptionComparison:
    region_snow_cm: float
    region_wind_ms: float
    rows: list                      # DesignOptionRow, 입력 순서 그대로(정렬·순위 없음)
    notes: list                     # str, 대안별 경고(설계강도 미달·미등재 등)


def compare_design_options(region_snow_cm: float, region_wind_ms: float,
                           options: list) -> DesignOptionComparison:
    """같은 입지조건(적설심·풍속) 위에 설계 대안 여러 건을 나란히 놓는다.

    기존 설계축 함수만 호출해 한 표로 모으는 조립 함수다 — 어느 대안이 낫다고
    결론짓지 않으며 순위·추천 필드도 두지 않는다(대안 선정은 판단성 영역,
    최종 선택은 컨설턴트·사용자 몫).

    spec_ok: select_specs(crop="*")의 후보 집합에 해당 규격이 들어가는지로
      판정한다 — 설계강도 필터 규칙을 이 함수가 다시 쓰지 않고 그대로 빌린다.
      crop="*"를 쓰는 이유는 "추천"이 아니라 "이 규격이 강도를 넘는가"라는
      멤버십 질의이기 때문이다(작물특화형이라고 탈락시키면 안 된다).
    """
    passing = {s.name for s in select_specs(region_snow_cm, region_wind_ms,
                                            crop="*")["candidates"]}
    by_name = {s.name: s for s in SPEC_TABLE}

    rows, notes = [], []
    for o in options:
        spec = by_name.get(o.spec_name)
        if spec is None:
            spec_ok, snow, wind = None, None, None
            notes.append(f"{o.label}: '{o.spec_name}'은 SPEC_TABLE(고시 제2025-108호) "
                         f"미등재 규격 — 설계강도 충족 여부를 판정할 수 없다")
        else:
            spec_ok = o.spec_name in passing
            snow, wind = spec.snow_cm, spec.wind_ms
            if not spec_ok:
                notes.append(f"{o.label}: '{o.spec_name}'의 설계강도"
                             f"(적설 {snow}cm·풍속 {wind}m/s)가 입지 요구"
                             f"(적설 {region_snow_cm}cm·풍속 {region_wind_ms}m/s)에 미달")

        h = heating_load(surface_area_m2=o.surface_area_m2, cover=o.cover,
                         t_target=o.t_target, t_min=o.t_min, curtain=o.curtain,
                         floor_area_m2=o.floor_area_m2)
        total = greenhouse_total_estimate(o.spec_name, o.area_py)
        if total is None:
            notes.append(f"{o.label}: '{o.spec_name}'은 A-2 평단가표"
                         f"(TOTAL_PYEONG_PRICE) 미등재 — 온실 전체 개산 불가")

        rows.append(DesignOptionRow(
            label=o.label, spec_name=o.spec_name, cover=o.cover, curtain=o.curtain,
            spec_ok=spec_ok, snow_cm=snow, wind_ms=wind,
            max_load_kcal_h=h.max_load_kcal_h, load_per_m2=h.load_per_m2,
            heater_capacity_kcal_h=h.heater_capacity_kcal_h,
            heating_verify=verify_heating_vs_actual(h.load_per_m2, o.cover),
            greenhouse_total_won=total,
            structure_only_won=structure_only_estimate(o.area_py)))

    return DesignOptionComparison(region_snow_cm, region_wind_ms, rows, notes)


# ─────────────────────────────────────────────────────────────
# 설계 문서 정합성 매트릭스 (2026-09-13, 80차 신설)
#   경위: 79차 지침 편입 판정에서 **채택 1순위**로 뽑힌 항목이다. 외부 패키지
#   `00_MASTER_INSTRUCTIONS.md` K절이 "도면 수량 ↔ 시방서 규격 ↔ QOM 수량 ↔
#   견적 단가/금액" 순서 대조를 요구하고, 사용자 첨부 A파일(스마트팜 수출단지
#   구축 체크리스트 v1.2)의 `P2_정합성매트릭스` 시트가 그 요구를 **Rev 문자열
#   일치 비교**로 이미 구현하고 있었다 — 둘이 같은 사양을 가리킨다.
#   상세 판정: 지침편입_SmartFarmROI패키지_v1.1_비판검토.md 2-1절.
#
#   원본 수식(A파일 `P2_정합성매트릭스!N4`, 전사):
#     =IF(A4="","",
#        IF(OR(C4="",E4="",G4="",I4=""),"MISSING_DOC",
#          IF(OR(D4="",F4="",H4="",J4=""),"MISSING_REV",
#            IF(AND(D4=F4,D4=H4,D4=J4),"OK","REV_MISMATCH"))))
#   4축 = C/D 도면번호·Rev · E/F 시방서번호·Rev · G/H BoQ항목ID·Rev ·
#         I/J 규격서ID·Rev. 분기 우선순위(DOC > REV > MISMATCH)도 그대로 따른다.
#
#   ⚠️ 상태 코드는 **영문 원문 그대로** 둔다(리포 관례는 한글이지만 여기선 예외).
#     이 함수는 그 시트 로직의 전사이고, 엔진 출력과 엑셀 셀을 **직접 대조**할 수
#     있어야 대조가능성이 유지된다(전사값 원단위 보존과 같은 취지).
#
#   ⚠️ **판정이 아니다.** 네 코드는 전부 *사실 분류*(문서가 있나·Rev가 적혔나·
#     서로 같나)이지 *가치 판단*(적합·부적합·추진 여부)이 아니다. 79차가 거부한
#     판정 자동화(100점 평가·최종판정 4문구·Site Score)와 갈리는 지점이 정확히
#     여기다. 설계 적합 여부는 구조기술사·컨설턴트 몫으로 남는다.
#
#   ⚠️ 스코프: **Rev 정합성만** 본다. 수량 차이(도면수량 vs 견적수량)와 금액
#     대사는 이 함수가 아니라 `reconcile_quote()`·`compare_quotes()` 소관이다 —
#     둘을 한 함수에 합치면 "무엇이 안 맞는지"가 뭉개진다.
# ─────────────────────────────────────────────────────────────
DOC_AXES = ("도면", "시방서", "BoQ", "규격서")


@dataclass
class DocRefRow:
    """요구사항 1건이 걸쳐 있는 4개 문서의 식별자·Rev. 공란은 ""(또는 None)."""
    req_id: str
    requirement: str = ""
    drawing_no: str = ""
    drawing_rev: str = ""
    spec_no: str = ""
    spec_rev: str = ""
    boq_id: str = ""
    boq_rev: str = ""
    std_id: str = ""
    std_rev: str = ""
    equipment_model: str = ""   # 참고 정보(판정에 쓰지 않음)
    manufacturer: str = ""      # 참고 정보
    verification: str = ""      # 검증/시험항목 — 참고 정보


@dataclass
class DocConsistencyRow:
    req_id: str
    requirement: str
    status: str                 # OK | MISSING_DOC | MISSING_REV | REV_MISMATCH
    missing_docs: list          # 식별자가 빈 축 이름
    missing_revs: list          # 식별자는 있으나 Rev가 빈 축 이름
    rev_map: dict               # 축 이름 -> Rev 문자열(빈 것 포함)
    mismatch_detail: str        # REV_MISMATCH일 때만 채움


@dataclass
class DocConsistencyReport:
    rows: list                  # DocConsistencyRow, 입력 순서 그대로(정렬·순위 없음)
    counts: dict                # 상태별 건수
    notes: list                 # str


def _blank(v) -> bool:
    """A파일 수식의 ="" 판정과 같은 의미. None·공백문자열·공백만 있는 문자열."""
    return v is None or str(v).strip() == ""


def doc_consistency_check(rows: list) -> DocConsistencyReport:
    """도면·시방서·BoQ·규격서 4축의 식별자·Rev 정합성을 행 단위로 분류한다.

    A파일 `P2_정합성매트릭스`의 판정 수식을 그대로 옮긴 것이라 분기 우선순위도
    동일하다: 식별자 누락(MISSING_DOC) > Rev 누락(MISSING_REV) > Rev 불일치
    (REV_MISMATCH) > 전부 일치(OK). 앞 단계에서 걸리면 뒤 단계는 보지 않는다 —
    식별자가 없는데 Rev를 비교하는 것은 의미가 없기 때문이다.

    Rev 비교는 **문자열 그대로** 한다("Rev2"와 "rev2"는 다르다). 표기 정규화를
    넣으면 원본 시트와 결과가 갈리고, 무엇이 실제 불일치인지 흐려진다.

    판정이 아니라 사실 분류다 — 어느 행이 좋다/나쁘다고 결론짓지 않고 순위·추천
    필드도 두지 않는다(설계 적합 판단은 구조기술사·컨설턴트 몫).
    """
    out, notes = [], []
    for r in rows:
        axes = {
            "도면": (r.drawing_no, r.drawing_rev),
            "시방서": (r.spec_no, r.spec_rev),
            "BoQ": (r.boq_id, r.boq_rev),
            "규격서": (r.std_id, r.std_rev),
        }
        rev_map = {k: ("" if _blank(v[1]) else str(v[1])) for k, v in axes.items()}
        missing_docs = [k for k, v in axes.items() if _blank(v[0])]
        missing_revs = [k for k, v in axes.items() if _blank(v[1])]

        if missing_docs:
            status, detail = "MISSING_DOC", ""
            notes.append(f"{r.req_id}: 식별자 누락 — {', '.join(missing_docs)}")
        elif missing_revs:
            status, detail = "MISSING_REV", ""
            notes.append(f"{r.req_id}: Rev 미기재 — {', '.join(missing_revs)}")
        else:
            revs = {rev_map[k] for k in axes}
            if len(revs) == 1:
                status, detail = "OK", ""
            else:
                status = "REV_MISMATCH"
                detail = " / ".join(f"{k}={rev_map[k]}" for k in axes)
                notes.append(f"{r.req_id}: Rev 불일치 — {detail}")

        out.append(DocConsistencyRow(
            req_id=r.req_id, requirement=r.requirement, status=status,
            missing_docs=missing_docs, missing_revs=missing_revs,
            rev_map=rev_map, mismatch_detail=detail))

    counts = {s: 0 for s in ("OK", "MISSING_DOC", "MISSING_REV", "REV_MISMATCH")}
    for row in out:
        counts[row.status] += 1
    return DocConsistencyReport(rows=out, counts=counts, notes=notes)


# ─────────────────────────────────────────────────────────────
# 시공발주관리(7단계): 공정표 근거 — 표준 품셈(노무투입량) (2026-07-19, Phase G)
#   ✅ 2026-09-14 107차 — **인쇄↔PDF 오프셋을 실측했다: 인쇄 = PDF − 24**.
#     이 PDF는 폰트에 ToUnicode가 없어 본문이 `(cid:N)` 글리프로만 추출된다.
#     각 쪽 꼬리말(`- N -`)의 글리프 시퀀스를 자리수 패턴으로 역해독해
#     10쪽(38·39·40·41·162·184·186·187·188·195)에서 대조했고, 글리프→숫자
#     대응이 **모순 없이 하나로 결정**되며 전 쪽에서 오프셋이 −24로 같다.
#     앞머리(38~41)와 본문(162~195) 양쪽에서 같으므로 구간 차이도 없다.
#   📌 102차가 이 인용을 `[오프셋 미검증]`으로 흐렸고 104차 레드팀 F1이
#     되돌렸는데, 107차는 **되돌린 게 아니라 측정했다** — 제7장 계열 라벨은
#     처음부터 정확한 인쇄 쪽번호였다.
#   ✅ 2026-09-14 108차 — **렌더링해서 육안으로 재확인했다**(pypdfium2).
#     PDF 39·40·195의 꼬리말이 각각 `- 15 -`·`- 16 -`·`- 171 -`이고
#     PDF 195는 실제로 「제8장 결론 및 향후 연구과제」다 — 오프셋·라벨 모두 옳다.
#     📌cid 글리프 역해독보다 `page.to_image()` 렌더링이 빠르고 확실하다.
#   🔴 **그러나 107차는 오프셋을 엉뚱한 라벨에 적용했다**: `p.15~16`을
#     "인쇄 쪽번호"로 보고 PDF 39~40이라 확정했는데, 그 쪽은 [표 2-3]
#     스마트팜 도입 성과조사다. 해당 내용은 **PDF 15~16**(요약보고서)에 있다 —
#     `p.15~16`은 처음부터 **PDF 쪽번호**였다(102차가 밝힌 바로 그 패턴).
#     ⚠️**오프셋을 알게 됐다고 모든 기존 라벨이 인쇄 쪽번호인 것은 아니다.**
#     라벨의 *종류*는 오프셋과 별개로 확인해야 한다.
#   📌 **요약보고서 구간(PDF 14~16 등)은 쪽 꼬리말이 없다** — 절 번호 체계도
#     본문과 다르다(`6. 온실공사품셈 정립`·`7. 향후 연구과제`). 이 구간은
#     `인쇄 p.N` 표기가 원천적으로 불가능하므로
#     **`PDF p.N(요약보고서 — 인쇄 쪽번호 없음)`**으로 적는다(102차 김평화 선례).
#   근거: `근거_7절정합성감사_품셈오프셋실측_20260914.md`(오프셋),
#         `근거_품셈요약보고서_원문확인_20260914.md`(원문 육안 대조·107차 정정)
#   출처: 「스마트팜 표준화를 위한 사전설계 및 온실공사 품셈 정립」최종보고서
#   (한국농어촌공사 발주·농어촌연구원×㈜지엘종합건축사사무소 수행, 2021-12,
#   리포 내 `시설평가/202201_스마트팜 표준화_품셈.pdf`(git 추적, 89,821,538B — 같은 폴더의 `농어촌공사(2022), …품셈 정립.pdf`와 SHA-256 동일한 **같은 파일 2부**))
#   제7장 **제2·3절**(원문 인쇄 p.138~162 = PDF 162~186)
#     🔴110차 정정 — 종전 `제7장(p.138~162)`은 **장 범위가 아니다**.
#       목차(PDF 19) 확인: **제7장은 인쇄 p.109~167**이고
#       138~162는 **제2절(유리 138~159) + 제3절(비닐 160~162)**의 범위다.
#       전사한 64개 품목이 온 자리는 정확하나 **이름이 틀렸다**.
#     🔴원문 결함(기록만 한다): 목차의 제3절(160, 비닐 품셈 산정)과 본문
#       인쇄 p.163의 "제3절 온실공사품셈 적용 단가 산정"이 **번호가 겹치고**,
#       **인쇄 163~167은 목차에 등재돼 있지 않다**.
#     ✅비닐 `공사원가계산서`는 **보고서에 인쇄되지 않았다**(110차) — 인쇄 p.164는
#       상·하단 둘 다 「공종별집계표」이고(600dpi 확대 확인) 제7장은 p.167에서
#       끝난다. 부록(도면/내역서/시방서, 인쇄 p.273)에도 **본문이 없다**.
#       🔴23회차 레드팀 F1 — 110차가 이것을 "표지뿐"이라 적은 것은 **틀렸다**:
#         PDF 297(인쇄 273)은 표지가 아니라 **본문**이고
#         `□ 부록 2(도면/내역서/시방서) - 별첨` 아래 **별첨 대상 6종**이 열거돼 있다
#         (유리·비닐 각 도면/내역서/시방서). 기존 레지스트리 서술("'– 별첨'으로만
#         표기")이 **맞았고** 110차의 정정이 방향을 거꾸로 잡았다.
#         원인: 그 쪽을 **렌더링만 하고 읽지 않은 채** 단정했다 — 108차가 107차를
#         두고 진단한 실수의 **자기 반복**이다(루브릭 R6 신설 계기).
#       ⚠️부재 단정의 검색 범위: 110차는 제7장 7쪽만 열고 단정했고,
#         **23회차 레드팀이 제6장·부록 92쪽을 실제로 열어 부재를 확인**했다 —
#         결론은 유지되나 **근거가 사후에 채워졌다**. 미열람은 제1~5장·제7장 제1절.
#       → 108차 [확인요망](비닐 노무비 229 vs 원문 228)은 **원문으로 확정 불가**.
#   — 경량철골유리온실공사 7개 공종(철골공사·온실피복공사·
#   천창개폐장치공사·알루미늄공사·수평스크린공사·측벽스크린공사·행잉거터
#   공사, 57종) + 경량철골비닐온실공사 2개 공종(철골공사(파이프자재)·
#   온실피복공사, 7종) = 64개 세부품목 전량(2026-07-19 원문 이미지 전수
#   대조로 완료 — 제7장 품셈 산정 파트는 이걸로 전체 완료).
#   원문 제3절 말미(인쇄 p.163~164(PDF 187~188))의 <그림7-18/7-19> 온실공사품셈 활용
#   단가산정 결과(유리 총공사비 3,487,006,773원·비닐 2,172,632,667원+제경비)는
#   이미 TOTAL_PYEONG_PRICE 레지스트리 source에 반영된 '온실품셈' 수치와
#   정확히 일치 — 기존 기록의 교차검증으로 확인됨.
#   🔴 2026-09-14 109차 정정 — 유리 총공사비는 `…776`이 아니라 **`…773`**이다.
#     <그림 7-18> 공사원가계산서를 확대해 읽고 계층 검산으로 확정했다:
#       계 2,852,203,252 × 6% = 일반관리비 171,132,195
#       + 이윤 146,670,711 → 공급가액 3,170,006,158
#       × 10% = 부가세 317,000,615 → 도급액 **3,487,006,773**
#     비닐 2,172,632,667은 정확하다(집계표 계 = 1,691,276,568 + 438,555,609
#     + 42,800,490).
#   ✅ 109차 출처 매핑 — 요약본 6.2 = **제7장 제3절 2**(인쇄 p.165~166 =
#     PDF 189~190)의 축약이고, 표준품셈 축의 1차 출처는 **제4장 제2절 4**다.
#     ⚠️23회차 레드팀 F4 — <그림 4-13>만 적었으나 **그것은 유리 전용**이다:
#       유리 4,196 = <그림 4-13>(인쇄 p.72) ·
#       비닐 3,509 = **<그림 4-14>**(인쇄 p.73 = PDF 97) ·
#       유리↔비닐 대비 = **<그림 4-15>**(온실건축 2,148/1,664 · 양액환경 301/301
#       동일 · 전기 250/250 동일 · 제경비 1,231/1,027 · 합계 4,196/3,509).
#   ⚠️ 원문 결함(고치지 않고 기록만 한다 — 91차 '철근공' 오기와 같은 원칙):
#     ①[표 7-11] 비닐은 2021년 두 열만 내부 검산이 맞다(노무비 열 단위 혼입 등)
#     ②<그림 7-19>에 공사원가계산서가 없고 집계표가 두 번 인쇄돼 있다
#     ③비닐 문단인데 "유리온실"이라 적은 오기 3곳
#   근거: `근거_요약본6.2_본문출처추적_20260914.md`
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
#   🔴 2026-09-14 118차 — 이 64종이 어디서 관측됐는지, 그리고 비닐 7종은 어디서도
#     관측되지 않았다는 것. 부록1 공사일보 **168장 전량**(PDF 213의 2장 + 214~296의
#     83쪽 × 2)을 렌더링 육안으로 읽었다.
#     · 공사명은 **168장 전부 "부여군 가설유리 온실 신축사업"** 단일 현장이고,
#       공종 흐름 13단계에 **유리온실 7공종이 전부·순서까지 대응**한다.
#     · 🔴 **비닐 공정(PO필름 피복·파이프 골조)은 0건**이다 → **비닐 7종**
#       (철골공사(비닐·파이프자재) 5 + 온실피복공사(비닐) 2)은 **1차 관측자료가
#       부록1에 없다**. 유도 경로가 유리 57종과 다르고 원문이 그 경로를 밝히지
#       않는다 → [확인요망]. **값은 그대로 둔다**(등재·변경은 ★사용자 결정).
#     · 관측 총량은 **2,040 인·일**이다 — 116차가 적은 2,033은 **05-24 자 누계**였다
#       (최종 05-25 일보에서 보통인부 353 → 360). 품셈 범위 안은 **1,652**다.
#     · 🎯 면적 품목 2쌍은 일별 투입이 **품목별로 갈린다**: 유리공 166 =
#       측면강화유리 30 + 천창유리 136 / 내장공 42 = 외벽 판넬 18 + 천장 판넬 24.
#       천장 판넬 역산 1,200㎡는 도면의 관리동 지붕 1,152㎡와 **+4.2%**로 맞는다.
#       나머지는 물량 정의가 원문에 없어 역산이 닫히지 않는다(117차 결론 유지).
#   근거: `근거_공사일보_전수확인_20260914.md`
#   🎯 2026-09-14 119차 — 유도 원리가 원문에 있다. 인쇄 p.120~137은 제1절의 잔여가
#     아니라 별도 절 **「제2절 온실품셈의 조사」**다(114·115차가 자재 소개로 오판).
#     · 🔴 **조사 현장은 2곳**이다 — 부여 OO온실([표 7-7]) + **함평 나비엑스포내
#       전시온실**([표 7-9], 연면적 1,600㎡). 118차의 "단일 현장"은 **공사일보에
#       한한 말**이다. ✅ **두 현장 모두 유리·벤로타입**이라 비닐 결론은 강해진다.
#     · ✅ **유도 원리**(p.131·133 동일 문구): "본 품셈은 **구성요소당 필요한 설치
#       시간등을 세분화하여 조사**하였으며, 유리온실 및 비닐온실 품셈 적용시 **각자
#       적용하거나 전체 구성에 필요한 품을 합산**하여 설계예가에 적용 할 수 있음" +
#       "본 조사는 **부재등의 각 개소마다 설치시간 장비등을 조사**하였음".
#       → **분모가 "개소"인 것은 의도된 설계**다. 그리고 p.123: "그 밖의 인력의
#       셈은 **건설공사 표준 품셈 및 건설업 임금실태조사 보고서에 준하여** 작성".
#       → 비닐 7종의 [확인요망] 사유가 바뀐다: "관측 기록이 없다"가 아니라
#       **"공통 적용 원리는 명시돼 있으나 비닐 고유 파이프 5종의 조사 출처가 없다"**.
#     · 🎯 **`철근공` 4건**(p.123): "인부의 노임은 건설업 임금실태조사 보고서의
#       **철근공과 유사**하게 나타났으며 … **철골공 및 특수인부 등으로 대체 작성**".
#       → "단순 오기" 가설이 더 약해진다. ⚠️원문은 **노임 유사성**만 말하므로
#       [확인요망]은 **유지**한다.
#     · ⚖️ **표준품셈 대비(이견으로만 기록)**(p.129): 건설공사 표준품셈 10-3-2
#       커튼월유리 16㎜이하 **0.131** vs 천창유리 **0.02**(1/6.55)·측면강화유리
#       **0.01**(1/13.1). 원문 근거는 "온실은 실링재 도포·유리닦기 공정이 없다"인데
#       그것만으로 6.55~13.1배가 설명되는지는 **원문이 말하지 않는다**. 판정하지 않는다.
#     · 📌 공기 산정의 빠진 입력이 원문에 있다(p.123): "경력 10~20년, **인원 10~15명**".
#       ⚠️전문 시공팀의 일반적 규모이지 특정 공정의 투입 인원이 아니다 → ★사용자 결정
#       (등재하지 않았다). 장비 임대료(p.137)는 **시세성**이라 옮겨 적지 않았다.
#   근거: `근거_품셈_온실품셈의조사_20260914.md`
#   🔴 2026-09-14 120차 — 아래 선언 순서는 **원문 차례와 다르다**(값 영향 0).
#     원문 목차(PDF 19)·본문: 철골 → **알루미늄** → 피복 → 천창개폐 → 수평스크린
#       → 측벽스크린 → 행잉거터 (제2절 p.138·141·144·146·151·156·158) + 비닐(제3절 p.160)
#     이 파일: 철골 → 피복 → 천창개폐 → **알루미늄** → 수평 → 측벽 → 행잉거터
#     → **알루미늄공사가 원문 2번째인데 여기서는 4번째**다. 조회가 (공종,품목명)
#       조합 키라 pumsem_labor_days()·pumsem_project_labor_summary() 결과는 같다.
#       **고치지 않고 기록만 한다** — 재정렬은 값 무관 변경이라 ★사용자 결정이다.
#     ✅ 각 공종 **1번 품목**은 원문 표 1번과 9/9 일치한다(목차 → 시작 쪽 → 1번
#       항목이라는 다른 경로로 113차 전수 대조를 교차검증했다).
#     🔴 본문 인쇄 p.120의 「제2절 온실품셈의 조사」는 **목차에 없는 제목**이고 절
#       번호가 p.138의 제2절과 충돌한다 — **원문 편집 오류**다. 목차 기준 제7장
#       제1절은 **p.109~137**이다(119차가 p.109~119라 적은 것을 정정).
#     🎯 철골 계수에는 정량 근거가 있다(p.125): "일반 철골조대비 **30% 이상 적은
#       품**" · "H빔 대비 **70%이하의 볼트본조임 개소**" · 공장 선조립 반입.
#       ⚠️유리 쪽 이견(표준품셈 대비 6.55~13.1배)은 이것으로 설명되지 않는다.
#     🔴 알루미늄은 119차식 대비가 불가능하다(p.127): 표준품셈 10-4-1은 **10kg당**,
#       이 파일의 알루미늄 6종은 **개소당**이다. 부재 중량을 모르면 환산도 못 한다.
#   근거: `근거_품셈_목차대조_20260914.md`
#   🔴 2026-09-14 121차 — 공종별 인·일 배분과 `철근공` 판단 반전.
#     공사일보 공종 경계 12시점의 누계를 차분해 13단계 배분을 냈다(전 시점 자기정합).
#     ✅ **품셈의 직종 구성이 관측과 0인 자리까지 맞는다**: 피복공사에 철골공 0 ·
#       철골/알루미늄에 조력공 0 · 천창개폐/스크린에 특별인부 0 — 셋 다 품셈에도 없다.
#     🔴 **예외가 `철근공`이다.** 품셈은 수평스크린 3품목(예인로라·가이드로라 /
#       스크린바가스켓 / 스크린체인웨이트) + 행잉거터 1품목(삼각대)에 철근공을 쓰는데,
#       **그 두 공종 기간의 철근공 투입이 0**이다. 누계 48은 전부 철근콘크리트①
#       (기초, 2020-11-09~12-08)에서 나왔고 그 뒤 최종까지 48 고정이다.
#       → 116차의 "관측 결과일 개연성이 높다"가 **무너진다**. 이 현장 관측에서
#         유도된 값이 아니다. ⚠️단 119차가 확인한 "그 밖의 인력의 셈은 표준품셈·
#         임금실태조사에 준하여 작성"에 따라 **준용일 가능성**이 열려 있어 "오기"로
#         확정되지도 않는다 → [확인요망] 유지, 사유만 다시 바꾼다.
#     ⚖️ 조력공 직종비 검산(🔴24회차 F1 정정 — 종전 "118차 역산의 독립 검증"은 틀렸다):
#       0.01×6,800 + 0.004×3,000 = 80 vs 관측 78(−2.5%). 그런데 6,800·3,000이
#       관측 유리공÷계수라 **물량이 식에서 소거된다**(136×0.5 + 30×0.4 = 80).
#       → 검증되는 것은 **품셈 표 내부의 직종비**(0.01/0.02·0.004/0.01)가 관측 직종비와
#         맞는다는 것뿐이고, **역산 물량의 타당성도 계수의 절대 크기도 아니다**.
#     📌 관측 모집단은 공종 기준 **1,255 인·일**이다(118차의 직종 기준 1,652보다 좁다 —
#       가설·토목·철근콘크리트·양액 구간에도 온실공·특별인부·보통인부가 투입됐다).
#     🔴 120차 기간 정정: 측벽스크린은 03-25~04-01이 아니라 **03-25~03-31**이다.
#   근거: `근거_공사일보_공종별배분_20260914.md`
#   📌 2026-09-14 122차 — 일별 투입 전량(168일보 `계` 행)을 읽어 121차 배분을 다른
#     경로로 교차검증했다(12공종 일치 + 행잉거터는 누락 3일분 20 보정 후 일치,
#     누계 전 구간 연속 검산). 🔴24회차 F4 정정 — 종전 "13공종 전부 일치"는 부정확.
#     🔴 **2021-05-18·19·20 일보가 편철에 없다** — 05-17 누계 1,992 + 05-21 금일 7
#       ≠ 05-21 누계 2,019이고 +20이 설명되지 않는다. 총 작업일은 168일이 아니라
#       **최대 171일**이고 총 공기 205 캘린더일에 대해 가동률 83.4%다(가정 포함).
#     📌 **철골공사는 20일 내내 12명 고정**(편차 0). 알루미늄② 12×3일·측벽스크린
#       13×7일도 편차 0 — 120차의 "모듈형 선조립 반입" 서술과 정합한다.
#     🎯 품셈 7공종 실측 평균 **10.1~14.5명/일**(가중평균 11.9 = 1,235÷104)로
#       119차가 원문에서 찾은 "인원 10~15명" 구간 안이다. 품셈 범위 밖 공종은
#       1.0~16.4명으로 편차가 커서, 그 서술이 온실 상부 공사에만 해당함을 보여준다.
#       ⚠️그래도 **등재하지 않는다** — 공기 산정은 판단성이고 이 현장 하나의
#       실측을 일반 계수로 올리는 것은 ★사용자 결정이다.
#     🔴 원문 날짜 오기 3건(기록만): 04-14·03-29·12-02가 각각 연속 두 블록에 찍혔다
#       (누계는 정상 증가하므로 실제로는 다른 날이다).
#   근거: `근거_공사일보_일별투입_20260914.md`
#   🎯 2026-09-15 124차 — 일별 **직종 구성** 17시점(총계 수준이 바뀌는 지점마다).
#     · **주력 크루는 온실공 8명**이다 — 철골·알루미늄·수평스크린·측벽스크린이 전부
#       같고 표준 구성은 온실공 8 + 특별인부 3 + 보통인부 1(=12) 또는 온실공 8 +
#       조력공 4 + 보통인부 1(=13)이다. 119차가 원문에서 찾은 "인원 10~15명"의
#       실체가 여기서 드러난다. **피복공사에는 온실공이 0명**(유리공·조력공·내장공).
#     · ✅ **"같은 총계 = 같은 구성"이 3/3 재현**된다 → 122차의 일별 총계로부터
#       직종 구성을 추정할 수 있다(⚠️3쌍에서만 재확인).
#     · 🎯 **직종비**(123차 F1이 재정의한 물량 무관 검산)를 일별 원자 단위로 보면:
#       **천창유리 계수 0.50 vs 관측 0.50 — 정확 일치**(단일 품목이라 물량 가중
#       가정이 필요 없다) · 수평스크린 0.510 vs 0.500 · 측벽스크린 0.503 vs 0.500.
#       ⚠️측면강화유리 0.40 vs 0.333 · 천창개폐 4.15 vs 8.0 · 행잉거터 2.57 vs 1.4는
#       어긋나는데, **품목이 많아 단순 합 비율이 현장을 대표하지 못하기** 때문이다.
#       121차가 구간 합으로 본 −2.5%가 **일별로는 0%**다(천창유리).
#     · 📌 품셈에 없는 **보통인부가 17시점 전부에 상주**(1~2명인 것은 **16시점**이고
#       05-21은 단독 7명이다 — 🔴129차/25회차 F4), **창호공**도 2시점에 나온다
#       (자재입고·도어 설치 — 부대 작업으로 보이나 원문이 그렇게 분류하지는 않는다).
#       05-21은 **보통인부 7명 단독 = 그라운드커버 설치**이고, 품셈 행잉거터공사의
#       `그라운드커버 {보통인부 0.004}`가 단일 직종인 것과 일치한다.
#   근거: `근거_공사일보_직종별구성_20260915.md`
#   ✅ 2026-09-15 125차 — 아래 64계수는 **원문 PDF 텍스트층에서 기계 재추출**해
#     대조된다(`pumsem_extract.py` + `test_125cha_…`). **불일치 0건**.
#     · 폰트가 ToUnicode 없는 서브셋이라 `(cid:N)`만 나오지만 `CIDToGIDMap=/Identity`라
#       cid == GID이고, 서브셋 glyph 아웃라인을 시스템 Batang/Gulim cmap과 해시 대조하면
#       GID→유니코드가 복원된다(340 매핑·모호 0건). 숫자는 전량 복원된다.
#     · 🔴 **값을 고치면 그 테스트가 잡는다** — 원문을 함께 고칠 수는 없기 때문이다.
#       (113차의 육안 전수 대조를 되돌려 확인할 수 있게 만든 것이 125차의 목적이다.)
#     · 🎯 129차 — **직종명까지 대조**한다(`extract_labor_trades()`, 64/64 불일치 0).
#       값만 보면 계수가 같은 4쌍에서 품목·직종이 뒤바뀌어도 통과했다(25회차 F7).
#       🎯그 부산물로 **원문이 정말 `철근공`이라 적는지**가 기계 확인된다(수평스크린 3 +
#       행잉거터 1) — 다만 121차의 "해당 공종 기간 관측 0"은 그대로라 [확인요망]의
#       **사유는 바뀌지 않는다**.
#     ⚠️ 129차(25회차 F9): 이 경로를 **"독립"이라 부르지 않는다** — 파서 결함 6건이
#       전부 엔진 값과의 대조 실패로 드러났고 휴리스틱이 **엔진을 정답지로 튜닝**됐다.
#       회귀 가드로서의 가치는 그대로이고, 최초 전사의 독립 검증으로 성립하는 것은
#       **원문을 직접 연 건**(P2의 0.0003)뿐이다.
#     ⚠️ 적용 범위는 **인쇄 p.138~162뿐**이다. 부록1 공사일보(스캔)·p.109~137(Type3
#       벡터 글리프)에는 통하지 않는다 — 116~124차가 그 구간에서 읽은 수치는 여전히
#       육안 판독 근거다. 의존성·시스템 폰트가 없으면 테스트가 skip되므로 skip 수를
#       확인해야 한다(pip 패키지가 세션 간 유실되는 환경이다).
#   근거: `근거_품셈64계수_기계재추출_20260915.md`
#   ✅ 2026-09-15 126차 — 같은 경로로 **제원 표 5종**도 기계 재확인했다(115·119차 육안
#     판독과 전부 일치). [표 7-2] 9,792.00 · [표 7-5] +방풍실 314 = 10,106 ·
#     [표 7-7] 연면적 18,707.03(≠ [표 7-8] 9,792.00) · [표 7-9] 1,600㎡.
#     🔴 원문 표기 오기 2건(기록만): 재배 2구역이 `4032.00`으로 **천단위 쉼표가 없고**,
#       [표 7-5] 합계만 `10,106㎡`로 **소수점이 없다**. 115·119차가 `4,032.00`으로
#       정규화해 옮긴 것을 정정했다 — 기계 추출이라야 잡히는 종류다.
#     ❌ **품목명 기계 대조는 중단**했다: 미복원 글리프 385자 중 composite 130개가
#       전부 미매칭이고 simple도 255개라 **폰트 버전이 다르다**. 비트맵 근사 매칭은
#       오탐 위험이 커서 하지 않는다 → 품목명 정확성은 **113차 육안 전수 대조에 의존**한다
#       (단 계수 시퀀스가 기계 대조되므로 품목이 뒤바뀌면 시퀀스가 어긋나 잡힌다).
#   근거: `근거_품셈제원표_기계재확인_20260915.md`
#   🔴 2026-09-15 127차 — [주] 항목을 64품목 전량 추출했다(`extract_notes()`).
#     · **공구손료 3%는 26품목(41%)에만** 붙는다 — 전 품목 일괄이 아니다.
#       🔴129차(25회차 F2): 요율은 **3종**이다 — 3% 26품목 · **2% 4품목**(알루미늄
#       1·2·3·6) · **잡재료 5% 2품목**(온실피복 3·4). ★등재 후보는 플래그가 아니라
#       **품목별 요율값**이어야 하고, 선홈통은 **2%와 3%를 동시에** 말한다.
#       (철골 8·알루미늄 2·피복 1·천창개폐 4·수평스크린 5·측벽스크린 1·비닐철골 5,
#        **행잉거터는 0**). 119차가 올린 ★등재 후보는 **품목별 플래그**여야 한다.
#     · 장비 8시간 38품목 · 별도 계상 **22**품목(🔴129차 정정 — 26은 2%·5% 줄 오분류) ·
#       재료량=설계수량 10품목(철골 9+알루미늄 1).
#     🔴 천창유리 [주](p.144)는 번호가 **①②④**로 ③이 없고 **②와 ④가 같은 말**이다
#       (**번호 이상**은 64품목 중 이 1건뿐 — 기계 검사). 🔴129차(25회차 F3): 선홈통
#       (알루미늄 6, p.143)은 번호가 연속이라 그 검사에 안 걸렸으나 **2%와 3%를 동시에**
#       말하고 오타·중복도 있다 — "원문 결함 2건"이라는 닫힌 수는 틀렸다.
#     🔴 **119차 ⑥ 이견이 강화된다**: p.129는 "온실 창호 기준 유리닦기 등의 공정이
#       없는 것으로 조사"라며 낮은 계수의 근거로 삼는데, p.144 [주]는 "본 품은
#       유리끼우기, 유리닦기 및 마무리 작업을 포함한다"고 적는다. **원문의 두 곳이
#       서로 다른 말을 한다** — 판정하지 않고 이견으로만 둔다.
#     ⚠️ 적용 조건을 **엔진에 등재하지 않았다**(★사용자 결정).
#   근거: `근거_품셈주석_적용조건_20260915.md`
#   📒 2026-09-15 130차 — `[확인요망]` **대장**을 만들었다
#     (`근거_확인요망대장_20260915.md`). 이 상수의 [확인요망] 15건을 **5항목**으로
#     정리했다: A 비닐 노무비(108차~) · B 선홈통 2%/3%(113차~, **114차 구조 설명**) ·
#     C 비닐 피복의 이중층 전제(115차) · D 철근공 4품목(91차~) · E 비닐 7종 경로(118차~).
#     🔴 **새 원문을 읽기 전에 대장을 먼저 본다** — 127차가 113차를, 129차가 114차를
#       놓쳐 **같은 원문을 세 번 읽으며 두 번 후퇴**했다.
#     🎯 A의 원천 표를 확정했다: 인쇄 p.103(제6장, 비닐 2021 노무비 **702**)과
#       p.166(제7장 비교표, 표준품셈 **650** / 온실품셈 **439**). 두 표의 702↔650은
#       **비목 분해 차이**로 보이고, 108차가 쓴 **473은 차트 값**이라 표(439)와 다르다.
#   근거: `근거_확인요망대장_20260915.md`
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
    # 경량철골비닐온실공사(제3절, 원문 인쇄 p.160~162(PDF 184~186)) — 유리온실과 구조체계가
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
# ✅ 71차 현행화(사용자 결정 "현행 사업명으로 갱신") + 15회차 F1·F5·F9 정정:
#   출처는 **2026년 스마트농업 육성 시행계획**(농림축산식품부 스마트농업정책과, 2025.11 —
#   근거 「스마트농업 육성 및 지원에 관한 법률」제4조. 리포 보존:
#   근거_농식품부_2026스마트농업육성시행계획_202511.pdf).
#   ⚠️ F1 정정: 초판은 "첨단온실신축지원사업"을 '원문 미확인'으로 제거했으나, **같은 문서
#   붙임 과제표에 「스마트팜 온실신축 '27년 사업자 공모(원예경영과, '26.4.)」가 실재**했다 —
#   정확문자열 매칭에 머문 탓이다. 현행 명칭으로 되살렸다(이 리포 본업인 온실 신축에 가장
#   직결되는 사업이라 누락의 대가가 컸다).
#   "스마트팜 시설현대화사업"은 독립 사업명으로는 확인되지 않고 지원 내용이 ICT융복합확산
#   계열에 흡수된 것으로 읽힌다(「기존 온실의 스마트화·현대화 촉진」·「ICT시설 및 현대화
#   시설 도입 3,572건 지원」) — 별도 등재하지 않되 [확인요망].
#   ⚠️ F9 정정: 개소수·시작연도·임대기간 등 **시점 종속 수치는 명칭에서 뺐다**(원문 스스로
#   "사업규모·예산은 재정여건에 따라 변경될 수 있음"이라 명시). 보조율·자격요건도 담지 않는다.
#   ⚠️ 원문이 '사업'으로 지칭한 것은 종합자금·ICT융복합확산·온실신축이고, 임대형·혁신밸리는
#   정책 수단·거점 명칭이라 status는 '원문 전사'(공공기준)가 아니라 **참고기준**이다(F5).
#   같은 이유로 초판의 '스마트팜 혁신밸리 청년창업보육센터'(원문 두 문장의 합성)는 원문 표현
#   '스마트팜 혁신밸리'로 되돌렸다 — 신설 테스트가 엔진 원소를 원문에 대조해 실제로 검출했다.
#   신청 전 스마트팜포털(farm.smart.go.kr)·해당 지자체 공고문 확인 필수. 자동판정에 쓰지 않는다.
SUBSIDY_PROGRAM_TYPES_REFERENCE: list[str] = [
    "스마트팜 종합자금(융자)",
    "스마트팜ICT융복합확산(보조+융자)",
    "스마트팜 온실신축(원예경영과 소관)",
    "임대형 스마트팜",
    "스마트팜 혁신밸리",
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
# B4~B8 확장 (2026-08-17, 사용자 결정 — Layer B 커버리지 갭 해소 1차)
#   Layer B 재점검(P2-15)이 정량화한 엔진 미모델링 5개 도메인(전기·통신·구동·
#   데이터활용·장애대응) 중 "결정론 근거가 존재하는 것만" 상수화한다:
#   · B8 장애대응 → WARRANTY_STATUTORY (법정 하자담보책임기간 — 아래)
#   · B4 전기     → ELECTRICAL_PUMSEM_LUMP_WON_PER_HA (품셈 표준설계 정액 참고치)
#   · B6 구동     → 신규 상수 없음: PUMSEM_ITEMS(천창개폐·수평/측벽스크린 공종
#                   품셈)·기자재DB(구동기 모델)·CAPEX auto_opening_system(실측
#                   4건)이 이미 커버 — 개폐기 제품단가는 시세성이라 상수화 부적합.
#   · B5 통신·B7 데이터활용 → 상수화 부적합 판정(2026-08-17): 프로토콜 선택·
#                   계측 항목 구성은 판단성 영역이고 결정론 수치 근거가 말뭉치에
#                   없다(언급 어휘뿐). 장비 측면은 기자재DB 조회로 충족. 법정
#                   하자기간(통신 1년)만 WARRANTY_STATUTORY에 포함.
# ─────────────────────────────────────────────────────────────
# 법정 하자담보책임기간(년) — 온실 시공 관련 공종 발췌.
# 1차 출처(원문 PDF 확보·전사): 건설산업기본법 시행령 [별표4] <개정 2021.8.3>
#   (law.go.kr flSeq=159636557 — 리포지토리 사본: 법령_건산법시행령_별표4_하자담보책임기간_20210803.pdf)
#   ⭐ 별표4 제19호가 "온실설치: 2년"을 명시한다 — 온실 공사 하자담보의 직접 법정근거.
#   비고(원문): 2 이상 공종이 복합된 공사는 하자책임을 구분할 수 없는 경우를
#   제외하고는 각각의 세부 공종별 기간을 적용한다.
# 전기·통신은 별표4 소관이 아니라 각각 전기공사업법·정보통신공사업법 관할.
# ✅ 2026-08-18 원문 확보로 [확인요망] 2건 해소(법제처 공식 뷰어 직접 열람):
#   · 전기(건축물 전기설비) 1년 — 전기공사업법 시행령 [별표 3의2]<개정 2021.1.5.>
#     제7호 "산업시설물, 건축물 및 구조물의 전기설비공사: 1년"(현행 시행령
#     [시행 2026.1.2., 대통령령 제35998호]에서 확인. 발전 7/3년·전력구 10/5/2년·
#     지중 5/3년·송전 3년·변전 3년·배전 3/2년·그 밖 1년 전체 표 전사 완료).
#   · 통신(그 외 정보통신공사) 1년 — 정보통신공사업법 시행령 제37조<개정
#     2021.1.5.> 제3호 "제1호 및 제2호의 공사 외의 공사: 1년"(현행 [시행
#     2026.3.24., 대통령령 제36220호]에서 확인). 제2호 케이블 설치공사는
#     "구내에서 시공되는 공사는 제외한다" 단서가 있어 온실 구내 통신배선은
#     3년 대상이 아니라 제3호(1년)에 해당함이 원문으로 확정됨.
WARRANTY_STATUTORY = {
    "온실설치":          {"years": 2, "근거": "건산법 시행령 별표4 제19호(2021.8.3)"},
    "토공":              {"years": 2, "근거": "건산법 시행령 별표4 제15호②"},
    "미장·타일":         {"years": 1, "근거": "건산법 시행령 별표4 제15호③"},
    "방수":              {"years": 3, "근거": "건산법 시행령 별표4 제15호④"},
    "도장":              {"years": 1, "근거": "건산법 시행령 별표4 제15호⑤"},
    "창호설치":          {"years": 1, "근거": "건산법 시행령 별표4 제15호⑦"},
    "지붕":              {"years": 3, "근거": "건산법 시행령 별표4 제15호⑧"},
    "판금":              {"years": 1, "근거": "건산법 시행령 별표4 제15호⑨"},
    "철물(철골 제외)":    {"years": 2, "근거": "건산법 시행령 별표4 제15호⑩"},
    "철근콘크리트(기타)": {"years": 3, "근거": "건산법 시행령 별표4 제15호⑪ — 기초 콘크리트 해당"},
    "급배수·냉난방·환기·공조·자동제어·가스·배연설비":
                         {"years": 2, "근거": "건산법 시행령 별표4 제15호⑫ — 관수·난방·환기·복합제어 설비 해당"},
    "승강기·인양기기":    {"years": 3, "근거": "건산법 시행령 별표4 제15호⑬"},
    "보일러 설치":        {"years": 1, "근거": "건산법 시행령 별표4 제15호⑭"},
    "그 외 건물내 설비":  {"years": 1, "근거": "건산법 시행령 별표4 제15호⑮"},
    "건축 구조상 주요부분(일반 건축물)": {"years": 5, "근거": "건산법 시행령 별표4 제14호②"},
    "건축 기타부분":      {"years": 1, "근거": "건산법 시행령 별표4 제14호③"},
    "조경":              {"years": 2, "근거": "건산법 시행령 별표4 제11호"},
    "부지정지":          {"years": 2, "근거": "건산법 시행령 별표4 제10호"},
    "전기(건축물 전기설비)": {"years": 1, "근거": "전기공사업법 시행령 별표3의2 제7호(개정 2021.1.5) — 원문 확인 2026-08-18"},
    "통신(그 외 정보통신공사)": {"years": 1, "근거": "정보통신공사업법 시행령 제37조 제3호(개정 2021.1.5) — 원문 확인 2026-08-18, 구내 케이블 제외 단서 포함"},
}


def warranty_period(work_type: str) -> Optional[dict]:
    """공종명 → 법정 하자담보책임기간(년)·법령 근거. 등록되지 않은 공종은
    None — 값을 지어내지 않는다(유사 공종 유추도 하지 않음: 어느 호를 적용할지는
    판단성 영역이라 컨설턴트 몫). 복합공사는 세부 공종별 적용(별표4 비고)."""
    item = WARRANTY_STATUTORY.get(work_type)
    if item is None:
        return None
    return {"공종": work_type, "years": item["years"], "근거": item["근거"],
            "비고": "복합공사는 하자책임 구분 불가한 경우를 제외하고 세부 공종별 적용(별표4 비고)"}


# ── LCC 기반: 기자재 내용연수 (2026-08-18, 데이터 대기 항목 ② 해소) ──
# 출처: 조달청 고시 「내용연수」 [별표 1] 내용연수표(차량 제외)
#   [시행 2025.1.1.] [조달청고시 제2024-30호, 2024.12.26. 일부개정] — 공식 PDF를
#   law.go.kr에서 직다운로드해 39페이지 전문 파싱, 스마트팜 설비 해당 품목만 발췌
#   (리포 사본: 법령_조달청고시_내용연수표_별표1_20241226.pdf).
# 성격: 공공물품 관리 기준(불용 판단 기준)이지 농가 실사용 수명 보증이 아니다 —
#   LCC 교체주기 계산의 "참고 기준연수"로 쓰고, 실측 수명이 확보되면 케이스별
#   주입값이 우선한다. 고시 2.가.2)가 "유사분류 물품의 내용연수 적용"을 명시적으로
#   허용하므로, 복합환경제어기→빌딩자동제어장치 같은 유사분류 대응은 고시 자체의
#   적용 규칙을 따른 것이다(주석에 대응 관계 명시).
# ⚠️ 온실 구조체(골조·피복)는 "물품"이 아니라 이 표에 없다 — 구조체는
#   STRUCTURE_SERVICE_LIFE_STATUTORY(법인세법 시행규칙 별표5·6, 2026-08-18 확보) 참조.
# 말뭉치 관찰치(참고, 레지스트리 source 기록): EC센서 내구연한 1년 이상(시방서),
#   ICT 장비 경제적 내용연수 10년(기자재 기술현황 보고서), 경질PVC 피복 수명
#   3년(교육자료), 스크린 내구년한 5년 이상(가이드라인).
EQUIPMENT_SERVICE_LIFE_REFERENCE = {
    # 난방
    "온풍난방기":       {"years": 11, "code": "40101866"},
    "전기보일러":       {"years": 13, "code": "40102003"},
    "소형기름보일러":   {"years": 10, "code": "40102007"},
    "연관보일러":       {"years": 10, "code": "40102001"},
    "열펌프(히트펌프)": {"years": 9,  "code": "40101806"},
    "냉난방기":         {"years": 9,  "code": "40101787"},
    # 공조·환기
    "송풍기(유동·배기팬류)": {"years": 10, "code": "40101601"},
    "공기조화기":       {"years": 10, "code": "40101709"},
    "에어커튼":         {"years": 9,  "code": "27131605"},
    # 펌프(양액·관수)
    "정량펌프(양액공급류)": {"years": 11, "code": "40151505"},
    "원심펌프":         {"years": 12, "code": "40151503"},
    "수중펌프":         {"years": 10, "code": "40151513"},
    "부스터펌프":       {"years": 10, "code": "40151566"},
    "자동펌프":         {"years": 12, "code": "40151599"},
    # 관수·방제
    "살수기":           {"years": 9,  "code": "21101803"},
    "분무기":           {"years": 10, "code": "21101801"},
    "제어밸브":         {"years": 12, "code": "40141609"},
    # 전기
    "분전반":           {"years": 8,  "code": "39121101"},
    "배전반":           {"years": 12, "code": "39121103"},
    "전동기제어반":     {"years": 9,  "code": "39121104"},
    "배전용변압기":     {"years": 11, "code": "39121001"},
    "디젤발전기(비상전원)": {"years": 12, "code": "26111601"},
    "삼상유도전동기(개폐·구동모터류)": {"years": 13, "code": "26101115"},
    # 제어·ICT
    "빌딩자동제어장치(복합환경제어 유사분류)": {"years": 11, "code": "39121801"},
    "프로세스제어반":   {"years": 11, "code": "41112498"},
    "컴퓨터서버":       {"years": 6,  "code": "43211501"},
    "데스크톱컴퓨터":   {"years": 5,  "code": "43211507"},
    "네트워크라우터":   {"years": 8,  "code": "43222609"},
    "무선데이터통신장비": {"years": 9, "code": "43221721"},
    # 센서·계측
    "온도감지기":       {"years": 10, "code": "41111970"},
    "온습도트랜스미터": {"years": 10, "code": "41112114"},
    "온도조절기":       {"years": 11, "code": "41112205"},
    "습도계":           {"years": 8,  "code": "41112301"},
    "온습도측정기":     {"years": 11, "code": "41112303"},
    # 감시
    "보안용카메라":     {"years": 6,  "code": "46171610"},
}


# ── LCC 기반: 온실 구조체 법정 기준내용연수 (2026-08-18, ② 잔여 소항목 해소) ──
# 출처: 법인세법 시행규칙 [별표 5] 건축물 등의 기준내용연수 및 내용연수범위
#   <개정 2024.11.11.> · [별표 6] 업종별 자산의 기준내용연수 및 내용연수범위
#   <개정 2024.3.22.>(모두 제15조제3항 관련). 현행 규칙 [시행 2026.7.1.]
#   [재정경제부령 제37호] — law.go.kr 법령 뷰어의 별표 공식 PDF 직다운로드
#   (flSeq 166450707·166450715, 리포 사본: 법령_법인세법시행규칙_별표5_건축물기준
#   내용연수_시행20260701.pdf / 별표6_업종별기준내용연수_시행20260701.pdf) 전문 파싱.
# 성격: 세법상 감가상각 "기준내용연수"(과세 목적 법정기준)이지 물리적 수명·보증이
#   아니다 — LCC 교체주기의 참고 기준으로 쓰고, 실측 수명 확보 시 케이스 주입값 우선.
# ⚠️ 판단성(자동 매핑 금지): 특정 온실 구조체에 어느 호를 적용할지는 세무 판단 영역.
#   ①별표5 비고3 가목 단축 열거에 "축사"는 있으나 "온실"은 미열거 — 유추 적용을
#   엔진이 하지 않는다(warranty_period의 '유사 공종 유추 금지'와 동일 원칙).
#   ②구조체가 별표5 "건물·구축물"인지 별표6 "업종별 자산"(농업 5년)인지의 구분도
#   판단. 따라서 키는 법정 호 단위이며 온실유형(유리/비닐) 키를 두지 않는다.
# 별표5 비고 요지: ①복합구조는 주된 구조 적용. ②"부속설비"는 전기·급배수위생·가스·
#   냉난방통풍·보일러·승강기 등 포함, "구축물"은 토지에 정착한 토목설비·공작물 일체.
#   부속설비를 건물과 구분해 업종별 자산으로 회계처리하면 별표6 적용 가능.
#   ③비고3 가~다목 해당 시 제3호→10년(8~12)·제4호→20년(15~25)으로 단축.
# 별표6 비고1: 별표3·별표5 적용 자산을 제외한 모든 감가상각자산에 적용.
# 참고(재탐색 방지): 농진청 소득자료집은 2022 전국판·2020 전북판 원문 확인 결과
#   고정자산 내용연수표 미수록(감가상각 정액법 서술뿐) — 소득자료집 경로는 닫음.
STRUCTURE_SERVICE_LIFE_STATUTORY = {
    "별표5_제3호(연와조·블록조·콘크리트조·목조 등 기타 조)": {
        "years": 20, "range": (15, 25),
        "대상": "연와조, 블록조, 콘크리트조, 토조, 토벽조, 목조, 목골모르타르조, "
               "기타 조의 모든 건물(부속설비 포함)과 구축물"},
    "별표5_제4호(철골·철근콘크리트조 등)": {
        "years": 40, "range": (30, 50),
        "대상": "철골ㆍ철근콘크리트조, 철근콘크리트조, 석조, 연와석조, 철골조의 "
               "모든 건물(부속설비 포함)과 구축물"},
    "별표5_비고3(제3호 단축)": {
        "years": 10, "range": (8, 12),
        "대상": "비고3 가~다목 해당 시 제3호 대체 — 가목(변전소·발전소·공장·창고·"
               "정거장·정류장·차고·폐수폐기물처리 건물·대형마트·전문점·국제회의시설·"
               "무역거래기반시설·축사), 나목(하수도·굴뚝·경륜장·포장도로·폐수폐기물"
               "처리 구축물), 다목(진동이 심하거나 부식성 물질에 심하게 노출된 것)"},
    "별표5_비고3(제4호 단축)": {
        "years": 20, "range": (15, 25),
        "대상": "비고3 가~다목 해당 시 제4호 대체(열거는 제3호 단축과 동일)"},
    "별표6_제2호(농업 01 업종별 자산)": {
        "years": 5, "range": (4, 6),
        "대상": "한국표준산업분류 01 농업 업종에 사용되는 자산(별표3·별표5 적용 "
               "자산 제외 — 별표6 비고1). 단서: 과수는 제9호 20년(15~25) 적용"},
}


def lcc_replacement_schedule(items: list, horizon_years: int) -> dict:
    """LCC 교체주기 계산(결정론) — Step6 제외항목 'LCC 10/15/20년 누적'의 계산기.

    items: [{"name", "unit_cost_won", "service_life_years"}] — 가격은 시세성이라
    항상 주입값, 수명은 EQUIPMENT_SERVICE_LIFE_REFERENCE 참조 또는 실측 주입.
    가정(명시): 수명 도달 연도마다 동일 명목가로 교체(물가상승·잔존가치·성능개선
    미모델링 — 근거 없는 값을 만들지 않기 위한 의도적 단순화), 지평 마지막
    연도(horizon) 시점 교체는 계산에 넣지 않는다(그 시점 재투자 여부는 판단성).
    반환: 품목별 교체연도 목록·재투자액과 총계. 판정·추천 없음."""
    if horizon_years <= 0:
        raise ValueError(f"horizon_years는 양수여야 한다: {horizon_years}")
    rows = []
    total_replacement = 0.0
    for it in items:
        life = it["service_life_years"]
        cost = it["unit_cost_won"]
        if life <= 0 or cost < 0:
            raise ValueError(f"{it.get('name')}: 수명은 양수, 가격은 0 이상이어야 한다")
        years = list(range(life, horizon_years, life))
        repl_cost = cost * len(years)
        total_replacement += repl_cost
        rows.append({"name": it["name"], "service_life_years": life,
                     "unit_cost_won": cost, "replacement_years": years,
                     "n_replacements": len(years), "replacement_cost_won": repl_cost})
    return {"horizon_years": horizon_years, "rows": rows,
            "total_replacement_cost_won": total_replacement,
            "note": "명목가 기준(물가상승·잔존가치 미반영), 지평 말 시점 교체 제외"}


# ── 감리비 참고: 건축공사감리 대가요율 (2026-08-18, P1-6 잔여 해소 — 사용자 결정: 참고 표시) ──
# 출처: 「공공발주사업에 대한 건축사의 업무범위와 대가기준」 [시행 2020.9.14.]
#   [국토교통부고시 제2020-635호] [별표 5] 건축공사감리 대가요율 — law.go.kr 행정규칙
#   뷰어의 별표 공식 PDF 직다운로드(flSeq 144640381, 리포 사본:
#   법령_건축사대가기준_별표5_공사감리대가요율_20200914.pdf) 17구간×3종 전문 전사.
# 적용 조항(본문 원문 확인 2026-08-18): 제14조① 건축공사감리업무 대가는 별표5 적용,
#   제16조① 공사비가 중간부분이면 직선보간법, ② 5천만원 미만은 5천만원으로 간주,
#   ③ 5천억원 초과는 별도 공식(실비정액가산 계열) — 온실 스케일 밖이라 미지원(None).
# '공사비' 정의(별표5 주): 발주자의 공사비 총예정금액(자재대 포함) 중 용지비·보상비·
#   법률수속비 및 부가가치세를 제외한 일체의 금액 — 부가세 포함가를 넣으면 과대 추정.
# ⚠️ 성격(사용자 결정 2026-08-18): CAPEX 합계에 산입하지 않는 참고 표시 전용 —
#   CAPEX_MAJOR_EVIDENCE_STATUS["design_supervision_fee"] 값은 0 유지. 종별(별표3
#   난이도: 제1종 단순~제3종 복잡) 선택과 실제 계약액은 판단성·시세성 — 엔진은 3종
#   전체를 병기하고 종을 고르지 않는다.
SUPERVISION_FEE_RATE_TABLE = [
    # (공사비 앵커(원), 제1종(단순)%, 제2종(보통)%, 제3종(복잡)%) — 별표5 원문 순서는
    # 3종→1종이지만 저장은 단순→복잡 오름차순(각 행 검증: 1종 < 2종 < 3종)
    (50_000_000,      2.02, 2.24, 2.46),   # "5천만원 이하" 행(제16조②와 짝)
    (100_000_000,     1.90, 2.11, 2.32),
    (200_000_000,     1.51, 1.68, 1.85),
    (300_000_000,     1.39, 1.54, 1.70),
    (500_000_000,     1.29, 1.43, 1.57),
    (1_000_000_000,   1.11, 1.23, 1.35),
    (2_000_000_000,   1.02, 1.13, 1.24),
    (3_000_000_000,   0.98, 1.09, 1.20),
    (5_000_000_000,   0.96, 1.07, 1.18),
    (10_000_000_000,  0.94, 1.04, 1.14),
    (20_000_000_000,  0.91, 1.01, 1.11),
    (30_000_000_000,  0.90, 1.00, 1.10),
    (50_000_000_000,  0.88, 0.98, 1.08),
    (100_000_000_000, 0.87, 0.97, 1.07),
    (200_000_000_000, 0.86, 0.95, 1.05),
    (300_000_000_000, 0.85, 0.94, 1.03),
    (500_000_000_000, 0.84, 0.93, 1.02),
]

SUPERVISION_FEE_GRADES = ("제1종(단순)", "제2종(보통)", "제3종(복잡)")


def design_supervision_fee_reference(construction_cost_won: float) -> Optional[dict]:
    """건축공사감리 대가 참고 추정(결정론·CAPEX 불산입).

    별표5 요율표 + 제16조(직선보간·5천만 간주)로 3종 전체의 요율·감리비를 계산해
    돌려준다. 종별 선택·실계약액은 판단성이라 판정하지 않는다. 공사비는 별표5 주)
    정의(부가세 등 제외) 기준 — 호출자가 정의 차이를 note로 전달해야 한다.
    5천억 초과는 제16조③ 별도 공식이라 None(미지원 명시)."""
    if construction_cost_won <= 0:
        raise ValueError(f"공사비는 양수여야 한다: {construction_cost_won}")
    if construction_cost_won > SUPERVISION_FEE_RATE_TABLE[-1][0]:
        return None  # 제16조③ 공식(평균급여액 기반) 미확보 — 지어내지 않는다
    effective = max(construction_cost_won, SUPERVISION_FEE_RATE_TABLE[0][0])
    rows = SUPERVISION_FEE_RATE_TABLE
    if effective <= rows[0][0]:
        rates = rows[0][1:]
        basis = "5천만원 이하 구간(제16조② 간주 포함)"
    else:
        for (lo_c, *lo_r), (hi_c, *hi_r) in zip(rows, rows[1:]):
            if lo_c <= effective <= hi_c:
                if effective == lo_c:
                    rates, basis = tuple(lo_r), f"앵커({lo_c:,}원)"
                elif effective == hi_c:
                    rates, basis = tuple(hi_r), f"앵커({hi_c:,}원)"
                else:
                    t = (effective - lo_c) / (hi_c - lo_c)
                    rates = tuple(l + t * (h - l) for l, h in zip(lo_r, hi_r))
                    basis = f"직선보간({lo_c:,}~{hi_c:,}원, 제16조①)"
                break
    rate_map = dict(zip(SUPERVISION_FEE_GRADES, rates))
    return {
        "입력공사비_원": construction_cost_won,
        "산정공사비_원": effective,
        "요율_pct": {g: round(r, 4) for g, r in rate_map.items()},
        "감리비_원": {g: round(effective * r / 100) for g, r in rate_map.items()},
        "산정구간": basis,
        "근거": "국토교통부고시 제2020-635호 별표5·제14조①·제16조(원문 전사 2026-08-18)",
        "note": ("참고 추정 전용(CAPEX 불산입) — '공사비'는 부가세·용지비 등 제외 정의(별표5 주), "
                 "종별 선택은 별표3 난이도 판단(판단성), 실제 계약액은 협의(시세성)"),
    }


# B4 전기 — 품셈 표준설계 전기공사 정액(참고치). 출처: 「스마트팜 표준화를 위한
# 사전설계 및 온실공사 품셈 정립」(농어촌공사, 2021-12) 1ha 표준설계 공종별집계표의
# '0103 전기공사' 정액 250,000,000원/ha (P1-10 라운드4에서 그림7-18/19 원단위
# 대사로 검증된 값). 구조(유리/비닐) 무관 정액이며 2021년 시점가 — 실측 케이스
# 전기공사(CAPEX electrical: 최혁진 부분실측)와 병용하되, 수전용량 산정식(전기설비
# 기술기준)은 근거 미확보라 모델링하지 않는다.
ELECTRICAL_PUMSEM_LUMP_WON_PER_HA = 250_000_000


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
    """환경적합도(%) = Σ(인자비율 × 가중치). 광0.5 온0.2 습0.2 CO2 0.1 (B). **[추정]**

    ⚠️ 71차 재조사(사용자 지시 "남은 미검증 3건"): 이 가중치 세트의 **공공 근거를 확보하지
    못했다**. 농사로·농진청 스마트팜 자료에 환경요인(광·온·습·CO2) 목록은 있으나 "적합도 =
    Σ(비율×가중치)"의 이 배분(0.5/0.2/0.2/0.1)을 규정한 공공 기준은 찾지 못했다 — 이런
    가중치는 작목·생육단계·모델마다 달라 단일 표준이 없을 개연성이 크다. 근거 없이 값을
    바꾸는 것도 1절 위반이므로 **값은 그대로 두고 [추정]으로 표기**한다.
    ⚠️ 이 함수는 **산출물 경로에서 호출되지 않는다**(레지스트리 등재·테스트 참조뿐 —
    build_site·webapp·render_report 어디에도 호출 없음). 쓰기 전에 작목별 가중치 근거를
    먼저 확보할 것. 상세: 근거_미검증상수_재조사_20260819.md
    """
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


# 재무 기본 파라미터(FINANCE_DEFAULTS) — 71차 항목별 성격 분리(사용자 결정 "근거 연결 + 성격 분리")
#   ✅ useful_life=15: **법인세법 시행규칙 [별표 5] 제3호**(연와조·블록조·콘크리트조·목조 등
#      기타 조의 모든 건물·구축물) 기준내용연수 20년 / **내용연수범위 15~25년**의 **하한**과
#      일치한다(원문 리포 보유: 법령_법인세법시행규칙_별표5_건축물기준내용연수_시행20260701.pdf).
#      ⚠️ 다만 "온실을 제3호로 볼 것인가"와 "범위 중 하한을 고를 것인가"는 **판단성**이다
#      (하한 = 보수적 = 빠른 감가상각). 별표5 비고3 단축은 10년(8~12), 별표6 농업 자산은
#      5년(4~6)으로 갈리므로 사업자 상황에 맞게 주입해 바꿔 쓸 것.
#   ⚠️ discount_rate=0.05: **시세성**(금리 연동) — 1절 원칙상 조회·확정 대상이 아니라
#      **인자로 주입**받아야 하는 값이다. 0.05는 중립 출발점일 뿐 근거값이 아니다.
#   ⚠️ years=10: 평가기간 **관행**(판단성). NPV·회수 비교 창의 길이일 뿐 법정 근거가 없다.
#   ⚠️ subsidy_rate=0.0 · land_cost=0.0: 중립 기본값(주입 전제 — 0이 "해당 없음"을 뜻함).
#   ⚠️ 영향 범위(15회차 F3·F4로 정정 — 초판 서술은 부정확했다):
#      · finance()를 타는 케이스는 **3건**(chuncheon·uminjae·wonchaewon)이다. mulhyangki·
#        yonggyun은 partial 경로(partial_construction_page)라 finance()를 타지 않는다.
#      · **useful_life만** 회귀 3지표를 움직인다(15→20 시 ROI 14.16%→15.83%,
#        Payback 7.06→6.32년, 실질ROI 28.32%→31.66%) — 변경 시 벤치마크 재설정 선행.
#      · discount_rate·years는 ROI·Payback·실질ROI에 **영향 0**이고 NPV·IRR만 움직인다
#        (dr 0.05→0.03 시 NPV 427,042,081→545,256,258 / years 10→20 시 IRR 16.2%→20.3%).
#      상세: 근거_미검증상수_재조사_20260819.md
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
# 금융조달: 대출상환표 (2026-08-17 P3-18 택1 — Step6 제외항목 중 첫 해소)
#   Step6 통합보고서에서 "case에 없는 입력(대출조건) 필요"로 제외했던 항목.
#   상환표 수학은 순수 결정론이고, 시세성 입력(원금·금리·기간·방식)은 케이스별
#   주입 원칙을 따른다 — cases/*.json 최상위 "financing" 블록(선택):
#     {"loan_principal_won", "annual_rate_pct", "term_years", "grace_years",
#      "method"("원리금균등"|"원금균등"), "note"(조건 출처)}
#   실제 대출조건이 없는 케이스에 가공 금리를 채우지 않는다(블록 없으면 미표시).
#   연 단위 상환표를 쓴다(농업 정책자금 관행이 연 단위 상환·거치이고, 케이스
#   리포트 가독성 기준) — 월 단위가 필요해지면 별도 결정.
# ─────────────────────────────────────────────────────────────
def loan_amortization(principal_won: float, annual_rate_pct: float,
                      term_years: int, grace_years: int = 0,
                      method: str = "원리금균등") -> dict:
    """연 단위 대출상환표. 거치기간엔 이자만 납부, 상환기간은 method에 따라
    원리금균등(연 납입액 일정) 또는 원금균등(연 원금 일정·이자 체감).
    반환: {"rows": [{연차, 구분, 원금, 이자, 납입액, 잔액}...], "총이자",
    "총납입액", 입력 echo}. 판정·추천 없음 — 계산표만 제공한다."""
    if principal_won <= 0:
        raise ValueError(f"대출원금은 양수여야 한다: {principal_won}")
    if annual_rate_pct < 0:
        raise ValueError(f"금리는 음수일 수 없다: {annual_rate_pct}")
    if term_years <= 0 or grace_years < 0 or grace_years >= term_years:
        raise ValueError(
            f"기간 오류: term_years={term_years}, grace_years={grace_years} — "
            "0 <= 거치 < 전체기간 이어야 한다")
    if method not in ("원리금균등", "원금균등"):
        raise ValueError(f"method는 '원리금균등'|'원금균등' 중 하나: {method}")

    r = annual_rate_pct / 100.0
    rows = []
    bal = float(principal_won)
    for y in range(1, grace_years + 1):
        interest = bal * r
        rows.append({"연차": y, "구분": "거치", "원금": 0.0, "이자": interest,
                     "납입액": interest, "잔액": bal})
    m = term_years - grace_years
    if method == "원리금균등":
        if r > 0:
            annuity = bal * r * (1 + r) ** m / ((1 + r) ** m - 1)
        else:
            annuity = bal / m
        for i in range(1, m + 1):
            interest = bal * r
            principal = annuity - interest
            if i == m:                      # 부동소수 잔차는 마지막 회차에서 정산
                principal = bal
            bal -= principal
            rows.append({"연차": grace_years + i, "구분": "상환",
                         "원금": principal, "이자": interest,
                         "납입액": principal + interest, "잔액": max(bal, 0.0)})
    else:  # 원금균등
        principal_fixed = bal / m
        for i in range(1, m + 1):
            interest = bal * r
            principal = principal_fixed if i < m else bal
            bal -= principal
            rows.append({"연차": grace_years + i, "구분": "상환",
                         "원금": principal, "이자": interest,
                         "납입액": principal + interest, "잔액": max(bal, 0.0)})
    total_interest = sum(row["이자"] for row in rows)
    return {
        "rows": rows,
        "총이자": total_interest,
        "총납입액": principal_won + total_interest,
        "원금": principal_won, "연이율_pct": annual_rate_pct,
        "전체기간_년": term_years, "거치기간_년": grace_years, "방식": method,
    }


# ─────────────────────────────────────────────────────────────
# 금융 지표 확장: DSCR · 최대 감당 투자비 (2026-09-13, 81차 신설)
#   경위: 79차 지침 편입 판정의 엔진 공백 지도 2·3번이다. 외부 패키지
#   `00_MASTER` F절이 `DSCR = Cash Available for Debt Service / Debt Service`,
#   `08_FINANCE_ROI`가 "목표 IRR·Payback·최소 DSCR을 만족하는 CAPEX 상한 역산"을
#   요구한다. 79차는 **식은 채택하되 계산 주체를 엔진으로 돌린다**고 판정했다
#   (패키지 원문은 Claude가 직접 계산하라고 하는데 그건 병렬 계산기라 거부).
#   상세: 지침편입_SmartFarmROI패키지_v1.1_비판검토.md 3-2·5절.
#
#   ⚠️ 새 상수 0. 임계값(목표 IRR·Payback·DSCR)은 **전부 호출부가 주입**한다 —
#     "DSCR 1.3 이상이면 양호" 같은 기준선을 엔진이 갖지 않는다. 그건 금융기관·
#     사업자마다 다른 **판단성** 값이고, 1절이 금지하는 판정 자동화의 입구다.
#
#   ⚠️ CADS 정의(명시): 이 엔진에서 **CADS = revenue - opex** 다.
#     `finance()`가 쓰는 연간 현금흐름(`operating_profit + depreciation`)과 같은
#     값이며 감가상각은 비현금이라 되돌려 놓은 것이다. **세금·운전자본 변동·
#     법인세 효과는 모델에 없다** — 표준 정의의 CADS보다 단순하므로 금융기관
#     제출용으로 쓸 때는 이 차이를 반드시 밝힐 것[확인요망].
#
#   ⚠️ 이 엔진은 매출·운영비를 연도별로 바꾸지 않는다(램프업·물가 미반영).
#     따라서 CADS는 전 연차 동일하고 DSCR의 연차 변동은 **상환액에서만** 온다.
# ─────────────────────────────────────────────────────────────
@dataclass
class DscrRow:
    year: int
    cads: float                    # 부채상환가능현금(= revenue - opex)
    debt_service: float            # 그 해 원리금 납입액
    dscr: Optional[float]          # 납입액 0이면 None(무한대로 표기하지 않는다)


@dataclass
class DscrResult:
    rows: list                     # DscrRow, 연차 순
    cads_annual: float
    min_dscr: Optional[float]
    min_dscr_year: Optional[int]
    basis_note: str                # CADS 정의·미반영 항목 명시(산출물에 그대로 노출용)


def dscr_schedule(revenue: float, opex: float, loan: dict) -> DscrResult:
    """대출상환표(`loan_amortization()` 반환)에 연간 CADS를 대입해 연차별 DSCR을 낸다.

    loan: `loan_amortization()`이 돌려준 딕셔너리 그대로. 그 함수의 `rows`에서
      `연차`·`납입액`만 읽는다 — 상환 계산을 여기서 다시 하지 않는다.

    판정하지 않는다 — "DSCR 1.3 이상이면 통과" 같은 기준선을 두지 않고 값과
    최솟값 위치만 돌려준다. 기준 충족 여부는 호출부·금융기관 몫이다.
    """
    if not isinstance(loan, dict) or "rows" not in loan:
        raise ValueError("loan은 loan_amortization()의 반환 딕셔너리여야 한다")
    cads = revenue - opex
    rows = []
    for r in loan["rows"]:
        ds = float(r["납입액"])
        rows.append(DscrRow(year=int(r["연차"]), cads=cads, debt_service=ds,
                            dscr=(cads / ds if ds > 0 else None)))
    vals = [(r.dscr, r.year) for r in rows if r.dscr is not None]
    min_dscr, min_year = min(vals) if vals else (None, None)
    note = ("CADS = 매출 - 운영비(감가상각 제외). 세금·운전자본 변동 미반영 — "
            "표준 DSCR보다 단순하므로 금융기관 제출 시 차이를 밝힐 것. "
            "매출·운영비가 연도별로 고정이라 DSCR 변동은 상환액에서만 온다.")
    return DscrResult(rows=rows, cads_annual=cads, min_dscr=min_dscr,
                      min_dscr_year=min_year, basis_note=note)


@dataclass
class MaxCapexResult:
    max_capex_won: Optional[float]   # 제약을 전부 만족하는 CAPEX 상한. 불가면 None
    current_capex_won: Optional[float]
    gap_won: Optional[float]         # 상한 - 현재. 음수면 현재가 상한을 넘었다는 뜻
    binding: list                    # 상한에서 걸리는 제약 이름(복수 가능)
    constraints: dict                # 입력 echo
    feasible_at_zero: bool           # 최소 규모에서도 제약을 못 맞추는지
    notes: list


def max_investable_capex(revenue: float, opex: float,
                         target_irr: Optional[float] = None,
                         max_payback_years: Optional[float] = None,
                         min_dscr: Optional[float] = None,
                         subsidy_rate: float = 0.0,
                         equity_won: float = 0.0,
                         loan_rate_pct: float = 0.0,
                         loan_term_years: int = 0,
                         loan_grace_years: int = 0,
                         loan_method: str = "원리금균등",
                         current_capex_won: Optional[float] = None,
                         useful_life: int = 15,
                         discount_rate: float = 0.05,
                         years: int = 10,
                         land_cost: float = 0.0) -> MaxCapexResult:
    """지정한 재무 제약을 전부 만족하는 **CAPEX 상한**을 역산한다.

    패키지가 말하는 질문의 전환이다 — "얼마에 지을 수 있는가"가 아니라
    **"얼마 이하로 지어야 사업성이 있는가"**.

    제약은 주는 것만 건다(전부 None이면 상한이 없어 None을 돌려준다):
      target_irr        : IRR >= 이 값(소수. 0.08 = 8%)
      max_payback_years : Payback <= 이 값
      min_dscr          : 전 연차 최소 DSCR >= 이 값

    금융구조(명시적 단순 모델): `대출 = max(0, CAPEX x (1 - 보조율) - 자기자본)`.
    min_dscr을 걸면 loan_rate_pct·loan_term_years가 필요하다.

    계산은 전부 기존 함수 위임이다 — `finance()`·`loan_amortization()`·
    `dscr_schedule()`. 탐색만 여기서 한다(새 재무 산식 없음).

    **단조성**: 이 엔진에서 연간 현금흐름(revenue - opex)은 CAPEX와 무관하므로
    CAPEX가 커지면 IRR은 단조 감소, Payback은 단조 증가, 대출이 커져 DSCR은 단조
    감소한다. 그래서 배가 탐색 + 이분 탐색이 성립한다.

    판정하지 않는다 — 상한과 현재와의 차이를 돌려줄 뿐 "추진 가능/불가"를 말하지
    않는다. 임계값도 엔진이 갖지 않고 호출부가 준다.
    """
    cons = {"target_irr": target_irr, "max_payback_years": max_payback_years,
            "min_dscr": min_dscr, "subsidy_rate": subsidy_rate,
            "equity_won": equity_won, "loan_rate_pct": loan_rate_pct,
            "loan_term_years": loan_term_years, "loan_grace_years": loan_grace_years,
            "loan_method": loan_method, "useful_life": useful_life,
            "discount_rate": discount_rate, "years": years, "land_cost": land_cost}
    notes = []
    if target_irr is None and max_payback_years is None and min_dscr is None:
        return MaxCapexResult(None, current_capex_won, None, [], cons, True,
                              ["제약이 하나도 지정되지 않아 상한이 정의되지 않는다 — "
                               "target_irr·max_payback_years·min_dscr 중 최소 1개 필요"])
    if min_dscr is not None and loan_term_years <= 0:
        raise ValueError("min_dscr 제약을 걸려면 loan_term_years(>0)가 필요하다")

    def measured_irr(capex: float, fin) -> Optional[float]:
        """`irr()`의 기본 탐색 상한은 hi=1.0(=100%)이라 그보다 높은 IRR에서
        None을 돌려준다 — 작은 CAPEX 구간이 전부 그렇다. 그 None을 '위반'으로
        읽으면 탐색이 하한에서 바로 실패한다(81차 실측). `irr()` 자체는 건드리지
        않고(회귀 위험) 여기서 탐색 범위만 넓혀 다시 묻는다.
        현금흐름은 `finance()`가 이미 계산한 값으로 재구성한다 — 현금흐름 '규칙'을
        다시 쓰지 않는다(연간 CF = operating_profit + depreciation).
        두 경로가 어긋나면 test_max_capex_irr_probe_agrees_with_finance가 잡는다."""
        if fin.irr is not None:
            return fin.irr
        cfs = [-capex] + [fin.operating_profit + fin.depreciation] * years
        # 1e9는 **알고리즘 탐색 상한**이지 도메인 상수가 아니다(레지스트리 대상 아님).
        # CAPEX가 아주 작으면 IRR이 1e8%대까지 가므로 넉넉히 잡는다.
        search_hi = 1e9
        r = irr(cfs, hi=search_hi)
        if r is not None:
            return r
        # 그래도 부호변화가 없으면 방향을 NPV 부호로 판별한다 —
        # 고율에서도 NPV>0이면 IRR이 탐색 상한보다 높다는 뜻이라 '무한대'로 본다
        # (제약 IRR>=target은 자동 충족). 반대면 하한 미만이라 측정 불가로 둔다.
        return float("inf") if npv(search_hi, cfs) > 0 else None

    def violated(capex: float) -> list:
        """제약 위반 목록. 비어 있으면 이 CAPEX는 허용."""
        bad = []
        fin = finance(revenue, opex, capex, useful_life=useful_life,
                      discount_rate=discount_rate, years=years,
                      subsidy_rate=subsidy_rate, land_cost=land_cost)
        if target_irr is not None:
            r = measured_irr(capex, fin)
            if r is None or r < target_irr:
                bad.append("IRR")
        if max_payback_years is not None:
            if fin.payback_years is None or fin.payback_years > max_payback_years:
                bad.append("Payback")
        if min_dscr is not None:
            principal = max(0.0, capex * (1 - subsidy_rate) - equity_won)
            if principal <= 0:
                pass                      # 대출이 없으면 DSCR 제약은 비활성
            else:
                loan = loan_amortization(principal, loan_rate_pct,
                                         loan_term_years, loan_grace_years,
                                         loan_method)
                res = dscr_schedule(revenue, opex, loan)
                if res.min_dscr is None or res.min_dscr < min_dscr:
                    bad.append("DSCR")
        return bad

    # 하한: 아주 작은 CAPEX에서도 제약을 못 맞추면 상한 자체가 없다
    lo = 1.0
    if violated(lo):
        return MaxCapexResult(None, current_capex_won, None, violated(lo), cons, False,
                              notes + ["최소 규모에서도 제약을 만족하지 못한다 — "
                                       "매출·운영비 가정 또는 제약 자체를 재검토할 것"])
    # 배가 탐색으로 위반이 나오는 hi 확보(60회 = 알고리즘 가드, 도메인 값 아님)
    hi = max(float(current_capex_won or 0.0), lo) * 2 or 2.0
    for _ in range(60):
        if violated(hi):
            break
        lo, hi = hi, hi * 2
    else:
        return MaxCapexResult(None, current_capex_won, None, [], cons, True,
                              notes + ["탐색 상한(배가 60회)까지 제약이 걸리지 않았다 — "
                                       "제약이 사실상 구속력이 없다는 뜻이다"])
    # 이분 탐색: lo=허용, hi=위반. 1원 미만으로 좁힌다
    for _ in range(200):
        if hi - lo < 1.0:
            break
        mid = (lo + hi) / 2
        if violated(mid):
            hi = mid
        else:
            lo = mid
    binding = violated(hi)
    gap = None if current_capex_won is None else lo - current_capex_won
    if gap is not None and gap < 0:
        notes.append(f"현재 CAPEX가 상한을 {abs(gap):,.0f}원 초과한다 — "
                     f"초과분은 설계 검토 대상이지 판정이 아니다")
    return MaxCapexResult(max_capex_won=lo, current_capex_won=current_capex_won,
                          gap_won=gap, binding=binding, constraints=cons,
                          feasible_at_zero=True, notes=notes)


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
# 단지(클러스터) 경제성 기본값 2종 — 74차에 함수 기본인자에서 모듈 상수로 승격
# ✅ 승격 이유(2026-08-20 74차, 사용자 지시): 16회차 F8이 "전수 점검이 모듈 상수만 훑어
#   함수 기본인자 2건 누락"으로 지적하고 17회차 F1이 "73차가 이를 '마지막 미등재 상수'라
#   잘못 닫았다"고 재지적한 바로 그 2건이다. 72차 난방 3종과 같은 사유 — 시그니처
#   리터럴로만 있어 레지스트리·대조가능성 감사의 검사 대상 밖이었다. 값은 바꾸지 않고
#   자리만 옮겨 근거 표기 체계 안으로 들인다.
# ⚠️ **0.15는 값의 근거 미확보**(리포에서 "OPEX 절감률 15%"를 특정한 자료는 없다).
#   다만 관련 관측은 있다[18회차 F9 — 내 "근거 0건" 단정의 두 번째 반증]:
#   `스마트팜연구DB/농업부문에너지이용실태.pdf` p33·p40·p78이 "재배규모가 클수록
#   단위면적당 사용량은 감소하여 **규모의 경제**가 실현"을 서술하고, p40 표 3-15는
#   오이 농가의 규모구간별 단위 경유 사용량 실측치(20.4→17.5→16.4→17.5→12.4)를 싣는다.
#   ⚠️ 근거로는 쓰지 않는다 — ①그것은 **단일 농가 재배면적**의 규모 경제이지 **단지
#   공동운영**의 경제가 아니고(72차 F1형 범주 확장 방지) ②계열이 단조롭지 않아
#   인접 구간 -6~-14%·최대 구간 -39%로 0.15를 사이에 두고 벌어진다(반증도 아니다).
# ⚠️ **0.7은 유래 정황이 있다**[추정 — 18회차 F1이 내 "근거 0건" 단정을 반증]:
#   (내가 검색한 청킹 인덱스는 `스마트팜스펙/`·`시설평가/` **2개 폴더만** 커버하고
#   본문이 200자로 절단된다 — 인덱스 0건은 "리포에 없음"이 아니다.)
#   ①`스마트팜_단계별_엑셀패키지/17_정책별_자기부담금_시뮬레이터.xlsx`에 **청년창업형
#   스마트팜 보조금 비율 70%**(확산 50·에너지 60·현대화 40)가 실재하고 ②이 엔진 자신이
#   L2440에서 같은 70%를 언급하고 있다. 값 일치가 출처 증명은 아니지만(69차 교훈)
#   "리포에 근거가 없다"는 내 서술은 거짓이었다.
# 🔴 **자기모순 관측(18회차 F1 파생)**: 위 L2440 주석은 "보조율 수치(50%·70%·50~70%)는
#   **공모 회차마다 바뀌는 값이라 여기 옮기지 않는다 — 근거 없는 값 금지**"라고 선언한다.
#   그런데 아래 CLUSTER_SUBSIDY_RATE_SHARED = 0.7이 정확히 그 옮기지 않기로 한 값이다.
#   1절 원칙의 "시세성 값은 주입만 받는다"에도 보조율이 해당한다고 보면, 이 상수는
#   **기본값을 갖는 것 자체가 재검토 대상**이다(인자 필수화 등) — 74차 승인 범위는
#   "등재"까지라 값·시그니처는 손대지 않고 관측만 기록한다.
# ⚠️ 리포에서 확인되는 보조율은 서로 다른 값이 여럿이다 — 시행계획(보조 55%),
#   온실 신개축 공모계획 p4(50%), 엑셀패키지(70/50/60/40), ROI 지침 docx(30~50%),
#   그리고 **단지 기반조성** 자료 2건(장성군 육성지구 과업설명서 보조 91.5%,
#   제주 임대형 과업지시서 100%). 사업·연도별로 달라지는 값임이 확인된다.
# ⚠️ 도달성(12~14회차 교훈): `cluster_economics`는 현재 **산출물 렌더 경로에 없다**
#   (전 모듈 grep — 엔진 정의와 test_engine 1건뿐). 즉 두 값은 **계산에 참여하지 않는다**.
#   (단 등재 이후 근거대장 HTML에는 상수 행으로 렌더된다 — 18회차 F6.)
CLUSTER_SCALE_SAVING_RATE = 0.15    # 규모의 경제 OPEX 절감률 [추정] — 근거 미확보
CLUSTER_SUBSIDY_RATE_SHARED = 0.7   # 공동시설 보조율 [추정] — 근거 미확보


def cluster_economics(n_farms: int, per_farm_capex: float,
                      shared_capex: float, per_farm_opex: float,
                      scale_saving_rate: float = CLUSTER_SCALE_SAVING_RATE,
                      subsidy_rate_shared: float = CLUSTER_SUBSIDY_RATE_SHARED) -> dict:
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
