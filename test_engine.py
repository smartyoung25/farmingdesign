"""
SmartFarm 엔진 회귀 테스트
- 실측 벤치마크(현재 7건)가 각 피복 밴드 안에 들어오는지
- 규격선정·난방 이중검증·재무지표·유형분기 로직 검증
실행: pytest test_engine.py -v   (또는 python test_engine.py)
"""
import smartfarm_engine as e


# ── 1. 실측 벤치마크 밴드 검증 (현재 9건) ───────────────────────────
def test_all_actuals_within_band():
    for name, area, total, cover in e.ACTUALS:
        r = e.benchmark_check(total, area, cover)
        assert r["status"] in ("정상", "경계"), \
            f"{name}: {r['unit_won_m2']}원/㎡ 밴드이탈 {r['band']}"


def test_92cha_actuals_additions_reproduce_source_chain():
    """92차 ★사용자 결정 편입 2건의 원문 체인을 고정한다.

    ACTUALS의 집계 기준은 "부가세 포함 최종 총공사금액"(P1-7)이다. 두 건 모두
    공급가액+부가세를 천원미만절삭한 값이고, 부가세는 (공급가액-영세율품목)×10%로
    원문 표기와 원단위 일치한다 — 그 체인을 여기 리터럴로 박아 둔다.
    밴드는 건드리지 않았다: 두 건 다 필름 밴드 내부라 경계가 움직이면 안 된다.
    """
    rows = {r[0]: r for r in e.ACTUALS}
    assert len(e.ACTUALS) == 9
    # 한수진: 공급가액 568,001,200 + 부가세 49,999,900 = 618,001,100 → 절삭
    assert rows["한수진"] == ("한수진", 4092, 618_001_000, e.Cover.FILM)
    assert int((568_001_200 + 49_999_900) // 1000) * 1000 == 618_001_000
    assert round((568_001_200 - 68_002_200) * 0.1) == 49_999_900
    # 최선동: 562,001,482 + 51,780,848 = 613,782,330 → 절삭
    assert rows["최선동"] == ("최선동", 3145, 613_782_000, e.Cover.FILM)
    assert int((562_001_482 + 51_780_848) // 1000) * 1000 == 613_782_000
    assert round((562_001_482 - 44_193_000) * 0.1) == 51_780_848
    # 면적은 규격 곱과 일치(문서 사업량 표기 채택)
    assert 44 * 93 == 4092 and 37 * 85 == 3145
    # 밴드 경계는 불변 — 두 건 다 내부여서 넓힐 이유가 없었다
    assert e.BENCHMARK_BANDS[e.Cover.FILM] == (115000, 240000)
    for nm in ("한수진", "최선동"):
        _, area, total, cover = rows[nm]
        assert e.benchmark_check(total, area, cover)["status"] == "정상", nm
    # 견적서 성격이라 실측 확정이 아니다 — 레지스트리 status가 이를 지켜야 한다
    import json as _j, os as _o
    reg = _j.load(open(_o.path.join(_o.path.dirname(_o.path.abspath(__file__)),
                                    "엔진데이터_레지스트리.json"), encoding="utf-8"))
    assert reg["constants"]["ACTUALS_COUNT"]["status"] == "부분실측"


def test_93cha_actuals_area_basis_is_not_uniform():
    """93차: ACTUALS의 면적 기준이 표본마다 다르다는 사실을 고정한다.

    한수진·최선동의 사업량 면적은 도면상 **방풍 폭 포함 외곽**이고 관리동을 안에
    담는다(평면도·측면골조도·주단면도). 이두희 2,736은 규격 8m×6연동×57m 역산이라
    **골조 순면적**이다. 같은 온실을 어느 기준으로 재느냐로 ㎡당 단가가 4.8~7.0%
    움직이므로, 밴드 대조는 그만큼의 기준 혼재를 안고 있다.

    ⚠️ 이 테스트는 "기준을 통일했다"를 주장하지 않는다 — **통일돼 있지 않다는 것**과
    **그럼에도 현재 판정이 뒤집히지 않는다**는 두 사실을 같이 박아 둔다. 기준을
    통일하는 차수가 오면 이 테스트가 먼저 깨져서 알려 준다.
    """
    rows = {r[0]: r for r in e.ACTUALS}
    # 도면 그리드: 사업량 폭 = 골조 스팬 합 + 방풍 2,000(양측 1,000)
    assert 6 * 7 + 2 == 44 and 44 * 93 == 4092          # 한수진
    assert 5 * 7 + 2 == 37 and 37 * 85 == 3145          # 최선동
    # 이두희는 방풍 없는 골조 순면적(레지스트리 명기 규격 역산)
    assert 8 * 6 * 57 == 2736 == rows["이두희"][1]
    # 기준을 바꿔도 9건의 밴드 판정은 뒤집히지 않는다(밴드 폭 2.1배)
    alt = {"한수진": (3906, 3528), "최선동": (2940, 2625),
           "한일그린텍": (2995,), "이두희": (2850,)}
    for nm, areas in alt.items():
        _, area, total, cover = rows[nm]
        for a in (area,) + areas:
            assert e.benchmark_check(total, a, cover)["status"] == "정상", (nm, a)
    # ⚠️ 우민재는 필름 밴드 상한에 159원/㎡ 차로 붙어 있고 상한이 우민재에서 나왔다
    _, ua, ut, uc = rows["우민재"]
    hi = e.BENCHMARK_BANDS[uc][1]
    assert 0 < hi - ut / ua < 200, "우민재-상한 간격이 변했다 — 밴드 앵커를 재확인할 것"


def test_94cha_area_basis_unification_is_blocked():
    """94차: 면적 기준 통일이 **왜 불가능한지**를 고정한다(결론이 아니라 차단 지점).

    사용자가 통일+밴드 재산정을 지시했고, 선행 조건이던 우민재 기준은 확정됐다
    (설계설명서·도면 면적개요: 온실내부+방풍벽+작업장=2,321.87, 방풍 포함).
    그러나 원문이 아예 없는 3건이 남고, 그중 하나가 **필름 밴드의 하한 앵커**다 —
    그래서 밴드를 다시 그을 수 없다. 원문이 확보되면 이 테스트가 먼저 깨진다.
    """
    import os as _o
    rows = {r[0]: r for r in e.ACTUALS}
    # 우민재 면적 구성 — 도면 면적개요가 원단위로 닫힌다(94차 확정)
    assert abs(32 * 60.05 - 1921.6) < 0.01                    # 온실내부
    assert abs((1 * 60.05 + 1 * 20.02) - 80.07) < 0.01        # 방풍벽 폭 1.0m
    assert abs(1921.6 + 80.07 + 320.2 - 2321.87) < 0.01       # 합계
    assert abs(2001.67 + 320.20 - 2321.87) < 0.01             # 설계설명서 면적표
    assert 32 + 8 + 1 == 41                                    # 폭 41M 분해
    # ⚠️ 등재값은 총표지 계열 2,323 — 원문 합계 2,321.87과 1.13㎡ 어긋난다
    assert rows["우민재"][1] == 2323
    assert round(2323 - 2321.87, 2) == 1.13
    # 원문 미보유 3건은 여전히 ACTUALS에 있고, 그중 하나가 필름 밴드 하한 앵커다
    no_source = {"공주장원리", "당진이상근", "원채원"}
    assert no_source <= set(rows), "원문 미보유 3건이 ACTUALS에서 사라졌다 — 94차 결론 재확인"
    lo = e.BENCHMARK_BANDS[e.Cover.FILM][0]
    _, ga, gt, _ = rows["공주장원리"]
    assert lo < gt / ga < lo * 1.05, "하한 앵커(공주장원리)와 밴드 하한의 관계가 변했다"
    # 스마트팜스펙에 그 3건 자료가 들어오면 통일 재시도가 가능해진다(89차 핀과 연동)
    root = _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), "스마트팜스펙")
    if _o.path.isdir(root):
        blob = " ".join(fn for _d, _s, fns in _o.walk(root) for fn in fns)
        assert "장원리" not in blob and "이상근" not in blob, \
            "원문 미보유 3건 자료가 들어왔다 — 면적 기준 통일을 재시도할 것(94차 ⓐ)"


def test_95cha_monthly_mean_wind_transcription():
    """95차 [표 3-3-44] 전사 고정 — 값·구조·자기정합성.

    원문 앵커(PDF p.364~365 / 인쇄 328~329)를 리터럴로 박고, 표 자체의
    자기검증(12개월 평균 = 표기 연평균)을 69행 전량에 건다. 88차 두 표와 같은
    69지역이어야 하되 **'마산'↔'창원' 1건만 다르다** — 이 차이는 결함이 아니라
    원문 그대로 둔 상태이므로 사라지거나 늘어나면 알려야 한다.
    """
    W = e.MONTHLY_MEAN_WIND_MS
    assert len(W) == 69
    # 원문 앵커 3건(첫 행·케이스 지역·최대 지역)
    assert W["속초"] == (3.3, 3.1, 3.1, 3.3, 3.0, 2.4, 2.3, 2.2, 2.4, 2.7, 3.0, 3.2, 2.8)
    assert W["천안"] == (1.5, 1.7, 2.0, 1.9, 1.7, 1.5, 1.5, 1.5, 1.4, 1.3, 1.5, 1.5, 1.6)
    assert W["고산"] == (9.9, 9.3, 8.2, 6.6, 5.6, 4.7, 5.3, 5.2, 5.5, 6.6, 7.9, 9.4, 7.0)
    # 표의 자기정합성 — 69행 전부 12개월 평균이 표기 연평균과 맞는다
    for nm, row in W.items():
        assert len(row) == 13, nm
        assert abs(sum(row[:12]) / 12 - row[12]) <= 0.06, nm
    # 88차 두 표와 지역 집합 — '마산'↔'창원' 1건만 다르다(원문 표기 유지)
    tac = set(e.DESIGN_OUTDOOR_TEMP_TAC)
    assert len(tac) == 69 and set(e.HEATING_DEGREE_HOURS_1000) == tac
    assert set(W) - tac == {"마산"} and tac - set(W) == {"창원"}


def test_95cha_mean_wind_requires_explicit_months():
    """원문이 '동절기'를 정의하지 않으므로 엔진이 개월을 고르면 안 된다.

    mean_wind(region, months)의 months는 **기본값이 없어야** 한다 — 기본값이
    생기는 순간 근거 없는 동절기 정의가 엔진에 박힌다(1절).
    """
    import inspect
    sig = inspect.signature(e.mean_wind)
    assert sig.parameters["months"].default is inspect.Parameter.empty, \
        "mean_wind(months)에 기본값이 생겼다 — 동절기 정의는 원문에 없다(판단성)"
    assert e.monthly_mean_wind("천안")[12] == 1.6      # 연평균은 원문 표기값 그대로
    assert abs(e.mean_wind("천안", (12, 1, 2)) - (1.5 + 1.5 + 1.7) / 3) < 1e-9
    assert e.monthly_mean_wind("없는지역") is None and e.mean_wind("없는지역", (1,)) is None
    for bad in ((), (0,), (13,), (1.5,)):
        try:
            e.mean_wind("천안", bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"months={bad!r}를 통과시켰다")
    # 표 3-3-35 연결 — 군산은 12·1·2월 기준 강풍지역이다(참고 관찰, 적용은 안 함)
    assert e.mean_wind("군산", (12, 1, 2)) >= e.WIND_STRONG_THRESHOLD_MS
    assert e.wind_correction_factor(e.mean_wind("군산", (12, 1, 2)), True) == 1.05
    assert e.wind_correction_factor(e.mean_wind("천안", (12, 1, 2)), True) == 1.0


def test_95cha_wind_table_not_wired_into_outputs():
    """도달성 가드(74차 관례) — 전사만 했고 산출물 경로에 연결하지 않았다."""
    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    for fname in ("build_site.py", "render_report.py", "webapp.py", "cases.py"):
        src = open(_o.path.join(repo, fname), encoding="utf-8").read()
        for name in ("MONTHLY_MEAN_WIND_MS", "monthly_mean_wind", "mean_wind"):
            assert name not in src, f"{fname}가 {name}을 참조한다 — 케이스 값이 움직인다"


def test_96cha_wind_factor_scope_and_validation():
    """96차 풍속보정계수 — 적용 범위와 입력 검증.

    원문 식(3-3-1)의 f_w는 **최대난방부하**에 곱한다. 기간난방부하 식에는 f_w가
    없으므로(그 자리는 일조시간 조정계수 [표3-3-36]) 연료소비량은 움직이면 안 된다.
    기본값 1.0이라 기존 호출은 전부 불변이다.
    """
    base = e.heating_load(1000, "필름", 15, -12.4, curtain="다겹보온")
    win = e.heating_load(1000, "필름", 15, -12.4, curtain="다겹보온", wind_factor=1.05)
    assert abs(win.max_load_kcal_h / base.max_load_kcal_h - 1.05) < 1e-12
    assert abs(win.load_per_m2 / base.load_per_m2 - 1.05) < 1e-12
    assert abs(win.heater_capacity_kcal_h / base.heater_capacity_kcal_h - 1.05) < 1e-12
    # 🔴 기간난방부하 계열은 불변 — f_w가 거기 들어가면 원문에 없는 계산이 된다
    assert win.fuel_consumption == base.fuel_consumption
    # 표 조회값만 받는다(임의 실수 거부) — "근거 없는 값 금지"의 시그니처 수준 방어
    assert set(e.WIND_CORRECTION_FACTOR.values()) == {1.0, 1.05, 1.1}
    for bad in (1.02, 0.9, 2.0, 1.2):
        try:
            e.heating_load(1000, "필름", 15, -12.4, curtain="다겹보온", wind_factor=bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"wind_factor={bad}를 통과시켰다")


def test_96cha_wind_factor_is_not_the_safety_factor():
    """83차가 '정체 미확정'으로 남긴 이중계상 의혹을 구조로 고정한다.

    원문(신개념온실 PDF p.343/인쇄 307)이 "풍속에 따른 보정계수"와 "난방방식에
    따른 안전계수"를 **별개 항목으로 나란히** 나열한다. 엔진도 적용 단계가 다르다 —
    wind_factor는 max_load에, safety는 heater(설치용량)에만 곱한다. 두 계수가
    같은 단계로 합쳐지면 이 테스트가 깨진다.
    """
    r = e.heating_load(1000, "필름", 15, -12.4, curtain="다겹보온",
                       safety=1.1, wind_factor=1.05)
    # heater = max_load × safety (wind_factor는 이미 max_load 안에 있다)
    assert abs(r.heater_capacity_kcal_h - r.max_load_kcal_h * 1.1) < 1e-9
    # safety만 바꾸면 max_load는 불변이어야 한다(단계 분리의 증거)
    r2 = e.heating_load(1000, "필름", 15, -12.4, curtain="다겹보온",
                        safety=1.0, wind_factor=1.05)
    assert r2.max_load_kcal_h == r.max_load_kcal_h
    assert abs(r2.heater_capacity_kcal_h - r2.max_load_kcal_h) < 1e-9
    # 1.1이 표의 '강풍·단일피복'과 값이 같다는 관찰은 유지되나 별개 개념이다
    assert e.WIND_CORRECTION_FACTOR[("강풍지역", "단일피복")] == e.HEATING_SAFETY_FACTOR


def test_98cha_sunshine_tables_transcription():
    """98차 [표3-3-36]·[표3-3-45] 전사 고정.

    표3-3-45의 지역 집합은 88차 두 표와 **완전 일치**한다 — 즉 세 표 중
    [표3-3-44] 풍속표만 '마산'을 쓴다(95차 이례가 1/3로 좁혀졌다).
    연평균 자기검산은 68행이 ±0.06 안이고 **장흥 1행만** Δ0.067이다(원문 반올림 차) —
    이 예외를 이름으로 고정해, 다른 행이 어긋나면 바로 드러나게 한다.
    """
    S = e.MONTHLY_SUNSHINE_HOURS
    assert len(S) == 69
    assert S["속초"] == (5.9, 6.1, 6.1, 7.1, 7.0, 5.4, 4.4, 4.9, 5.5, 6.1, 5.6, 5.9, 5.8)
    assert S["군산"] == (4.8, 5.9, 6.2, 7.0, 6.9, 5.9, 4.8, 5.8, 6.2, 6.2, 5.0, 4.7, 5.8)
    tac = set(e.DESIGN_OUTDOOR_TEMP_TAC)
    assert set(S) == tac == set(e.HEATING_DEGREE_HOURS_1000)
    assert "창원" in S and "마산" not in S
    assert set(e.MONTHLY_MEAN_WIND_MS) - tac == {"마산"}      # 풍속표만 마산
    off = {nm for nm, v in S.items() if abs(sum(v[:12]) / 12 - v[12]) > 0.06}
    assert off == {"장흥"}, off
    for nm, v in S.items():
        assert len(v) == 13 and abs(sum(v[:12]) / 12 - v[12]) <= 0.07, nm
    # 표3-3-36은 원문 5점 그대로 — 보간하지 않는다
    assert e.PERIOD_LOAD_ADJUST_K == {3.0: 3020.0, 4.5: 2820.0, 6.0: 2620.0,
                                      7.5: 2420.0, 9.0: 2220.0}
    hit = e.period_load_adjust_k(6.0)
    assert hit["k"] == 2620.0 and abs(hit["ratio_vs_current"] - 2620 / 3600) < 1e-12
    miss = e.period_load_adjust_k(5.0)
    assert miss["k"] is None
    assert miss["lower"]["k"] == 2820.0 and miss["upper"]["k"] == 2620.0


def test_98cha_engine_period_load_equals_k_3600():
    """🔴 98차 핵심 — 엔진의 현행 기간난방부하가 **원문 식에서 k=3600**임을 고정한다.

    u_design == u_period인 유리 케이스에서 Ū = u·fr이 되어 원문 식(3-3-5)과
    엔진 식이 k만 다르다. 이 항등이 성립해야 "현행은 일조 취득 0의 상한"이라는
    98차 결론이 선다 — 깨지면 그 결론부터 다시 봐야 한다.
    """
    Aw, dt = 5000.0, 24.7
    t_target, t_min, fr = 18.0, 18.0 - dt, 0.7
    r = e.heating_load(Aw, "유리", t_target, t_min, fr=fr)
    # 항등의 전제: 유리는 U_DESIGN에 키가 없어 u_design이 U_VALUE로 폴백된다
    assert "유리" not in e.U_DESIGN and e.U_VALUE["유리"] == 5.3
    eng_period = r.fuel_consumption * r.fuel_unit_lhv * e.HEATING_EFFICIENCY_DEFAULT
    # 원문 식: Q_H = k·Ū·A_c·HDH  (Ū = H_T/(A_c·dt), H_T는 W)
    U_bar = (r.max_load_kcal_h / e.W_TO_KCAL_PER_HOUR) / (Aw * dt)
    for h, k in ((4.5, 2820.0), (6.0, 2620.0), (7.5, 2420.0)):
        QH_kcal = k * U_bar * Aw * e.DEGREE_HOURS_DEFAULT / 4186.8
        assert abs(QH_kcal / eng_period - k / 3600.0) < 1e-3, h
    assert e.PERIOD_LOAD_K_NO_SUNSHINE == 3600.0


def test_98cha_sunshine_k_not_auto_applied():
    """적용은 ★사용자 결정 — 기본은 현행 그대로여야 한다(원채원 회귀 보호).

    sunshine_k는 기본 None이고, 주면 **연료소비량만** k/3600으로 움직이며
    최대난방부하·난방기 용량은 불변이다(원문 식에서 k는 기간부하 쪽 계수다).
    """
    import inspect
    assert inspect.signature(e.heating_load).parameters["sunshine_k"].default is None
    base = e.heating_load(5000, "유리", 18, -6.7, fr=0.7)
    adj = e.heating_load(5000, "유리", 18, -6.7, fr=0.7, sunshine_k=2620.0)
    assert adj.max_load_kcal_h == base.max_load_kcal_h
    assert adj.heater_capacity_kcal_h == base.heater_capacity_kcal_h
    assert abs(adj.fuel_consumption / base.fuel_consumption - 2620 / 3600) < 1e-12
    for bad in (2700.0, 3600.0, 1.0, 0.728):
        try:
            e.heating_load(5000, "유리", 18, -6.7, fr=0.7, sunshine_k=bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"sunshine_k={bad}를 통과시켰다")
    # 도달성 가드 — 산출물 경로가 이 상수·함수를 참조하면 안 된다
    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    for fname in ("build_site.py", "render_report.py", "webapp.py", "cases.py"):
        src = open(_o.path.join(repo, fname), encoding="utf-8").read()
        for name in ("MONTHLY_SUNSHINE_HOURS", "PERIOD_LOAD_ADJUST_K",
                     "monthly_sunshine", "period_load_adjust_k", "sunshine_k"):
            assert name not in src, f"{fname}가 {name}을 참조한다 — OPEX가 움직인다"


def test_100cha_dual_u_structure_and_residual_decomposition():
    """100차 — u_design/u_period 이원화의 정체를 고정한다.

    이원화는 결함이 아니라 **그 재질에 현장 실측이 있느냐**의 반영이다.
    필름 계열만 이현우 등(2013) 연료소비 역산 실측(2.66)을 갖고 있어 갈리고,
    유리·필름_이중은 그 실측이 없어 설계 계열 값이 그대로 들어가 통일돼 보인다.

    그리고 98차가 "필름은 이 축만으로 설명되지 않는다"며 남긴 잔차 1.560이
    **이원화 × 일조**로 정확히 분해된다 — 이 분해가 깨지면 두 차수의 결론을
    함께 다시 봐야 한다.
    """
    def ud(c):
        return e.U_DESIGN.get(c, e.U_VALUE[c])
    split = {c for c in e.U_VALUE if abs(ud(c) / e.U_VALUE[c] - 1) > 1e-9}
    assert split == {"필름", "불소필름", "단동"}, split
    for c in split:
        assert abs(ud(c) / e.U_VALUE[c] - 5.7 / 2.66) < 1e-12
    # 통일돼 보이는 재질은 U_DESIGN에 키가 없어 폴백된 것뿐이다
    for c in ("유리", "필름_이중"):
        assert c not in e.U_DESIGN and ud(c) == e.U_VALUE[c]
    # 98차 잔차 분해: 1.560 = 2.1429(이원화) × 0.7278(일조 k/3600)
    k6 = e.PERIOD_LOAD_ADJUST_K[6.0] / e.PERIOD_LOAD_K_NO_SUNSHINE
    assert abs((5.7 / 2.66) * k6 - 1.5595) < 1e-3
    assert abs(1.0 * k6 - 0.7278) < 1e-3


def test_100cha_glass_period_load_overstatement_is_recorded():
    """⚠️[확인요망] 유리 기간난방부하 과대 개연성이 기록으로 남아 있는가.

    필름은 실측/설계 비가 0.467인데 유리엔 그런 보정이 없다. 유리 현장 실측이
    들어오면 연료소비량이 크게 내려갈 수 있고, **원채원이 바로 그 케이스이자
    회귀 기준**이다. 값을 바꾸지는 않되 사실이 잊히지 않게 코드에 남긴다.
    """
    import os as _o
    assert abs(e.U_VALUE["필름"] / e.U_DESIGN["필름"] - 0.4667) < 1e-3
    assert e.U_VALUE["유리"] == 5.3 and "유리" not in e.U_DESIGN
    src = open(_o.path.join(_o.path.dirname(_o.path.abspath(__file__)),
                            "smartfarm_engine.py"), encoding="utf-8").read()
    assert "유리 케이스의 기간난방부하가 과대일 개연성" in src
    assert "원채원이 바로 그 케이스이고 회귀 기준" in src


def test_101cha_safety_factor_origin_confirmed():
    """🔴101차 — HEATING_SAFETY_FACTOR=1.1의 출처 확정(14절 B3 종결).

    원문(PDF p.389/인쇄 353)이 "온풍난방 10% · 온수난방 20~30%"로 방식별 안전계수를
    **본문으로** 준다. 이 엔진 대상은 등유 온풍난방기라 1.1이 맞다.
    83차가 발견한 "표3-3-35 강풍·단일피복 1.1과 값이 같다"는 **우연의 일치**다 —
    96차가 두 계수의 개념 분리를 원문으로 확정했다.
    """
    M = e.HEATING_SAFETY_FACTOR_BY_METHOD
    assert M["온풍난방"] == (1.1, 1.1) and M["온수난방"] == (1.2, 1.3)
    assert e.HEATING_SAFETY_FACTOR == M["온풍난방"][0]
    # 원문 p.377의 "0.1~0.3" 범위와 방식별 값이 정합한다
    lo = min(v[0] for v in M.values()) - 1.0
    hi = max(v[1] for v in M.values()) - 1.0
    assert abs(lo - 0.1) < 1e-9 and abs(hi - 0.3) < 1e-9


def test_101cha_component_shares_quantify_engine_gap():
    """🔴101차 — [표 3-3-51]이 84차의 구조적 공백(14절 B5)을 정량화한다.

    엔진은 관류열부하만 계산하므로 원문 기준 **전체의 91.9%**만 잡는다.
    전사 검산으로 각 행이 100%로 닫히는지 본다 — 닫히지 않으면 전사 결함이다.
    """
    S = e.HEATING_LOAD_COMPONENT_SHARES_PCT
    assert set(S) == {1, 2, 3, 4, 5, "계"}
    for k, v in S.items():
        assert len(v) == 3 and abs(sum(v) - 100.0) <= 0.1, k
    assert S["계"] == (91.9, 8.6, -0.5)
    assert S[1][0] == 95.6 and S[5][0] == 88.7        # 본문 88.7~95.6과 일치
    assert e.transmission_share_pct() == 91.9
    assert e.transmission_share_pct(1) == 95.6 and e.transmission_share_pct(5) == 88.7
    # 누락 몫 8.1% → 엔진 최대난방부하는 약 8% 과소다
    assert abs(100.0 - e.transmission_share_pct() - 8.1) < 1e-9
    for bad in (0, 6, "합계"):
        try:
            e.transmission_share_pct(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"group={bad!r}를 통과시켰다")


def test_101cha_shares_not_wired_into_outputs():
    """도달성 가드 — 8% 보정은 ★사용자 결정이라 산출물 경로에 연결하지 않았다."""
    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    for fname in ("build_site.py", "render_report.py", "webapp.py", "cases.py"):
        src = open(_o.path.join(repo, fname), encoding="utf-8").read()
        for name in ("HEATING_LOAD_COMPONENT_SHARES_PCT", "transmission_share_pct",
                     "HEATING_SAFETY_FACTOR_BY_METHOD"):
            assert name not in src, f"{fname}가 {name}을 참조한다 — 케이스 값이 움직인다"


# ─────────────────────────────────────────────────────────────
# 23회차 레드팀 C2 — 가드의 스캔 범위를 **열거에서 전수로** 바꾼다.
#   107·109·110차 가드는 `smartfarm_engine.py`·`엔진데이터_레지스트리.json` 2개만
#   돌았고, 정정 없는 잔존이 실제로 있던 `통합작업체계_…md`를 **통과시켰다**.
#   107차가 스스로 적은 "열거는 빠뜨리고 불변식은 안 빠뜨린다"의 3회차 재발이다.
# ─────────────────────────────────────────────────────────────
def _repo_text_files():
    """리포의 텍스트 산출물 전수(.py/.json/.md/.html). 검색 계층·스코프 제외는 뺀다."""
    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    skip = {".git", "__pycache__", ".pytest_cache", "노지견적", "노지시방서",
            "대산온실", ".claude", "node_modules"}
    out = []
    for root, dirs, files in _o.walk(repo):
        dirs[:] = [d for d in dirs if d not in skip]
        for f in files:
            if not f.endswith((".py", ".json", ".md", ".html")):
                continue
            if f.startswith("문서청킹_인덱스"):   # 검색 계층(대용량) — 계산 출처 아님
                continue
            if f == _o.path.basename(__file__):  # 가드 정의는 "잔존"이 아니다
                continue
            out.append(_o.path.join(root, f))
    return out


def _uncorrected_hits(needle, *, before=240, after=90,
                      markers=("정정", "오기", "철회", "반증", "틀렸", "오류")):
    """`needle`이 **정정 표시 없이** 살아 있는 자리만 돌려준다.

    이 리포의 관례(31차)는 원문 서술을 지우지 않고 옆에 현재 상태를 병기하는 것이다.
    그래서 금지 대상은 문자열 자체가 아니라 **정정 표시가 없는 잔존**이다.
    """
    import re as _re
    bad = []
    for path in _repo_text_files():
        try:
            src = open(path, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        for m in _re.finditer(_re.escape(needle), src):
            # 이 리포의 정정 관례는 `…776`은 **오기**다처럼 **인용 바로 뒤**에
            # 라벨을 붙인다. 창을 넓게 잡으면 같은 줄의 다른 정정문이 변이를
            # 흡수해 버린다(23회차 재설계에서 실측). 비대칭·좁게 본다.
            near = src[max(0, m.start() - before):m.start() + len(needle) + after]
            if not any(k in near for k in markers):
                bad.append((path, m.start()))
    return bad

def test_102cha_page_labels_are_unambiguous():
    """102차 — 쪽번호 표기에서 `printed p.`를 전부 걷어냈다(95차 발견의 마무리).

    83~88차가 적은 `printed p.X`의 X는 실제로는 **PDF 뷰어 쪽번호**였다(95차 발견).
    PDF로 열면 맞지만 인쇄본 쪽번호로 읽으면 엉뚱한 곳이라, 표기 자체를 금지한다.
    확인된 문서는 `PDF p.X(인쇄 Y)`로 적는다 — 읽는 사람이 속지 않는다.

    📌107차 정정: 이 도크스트링은 품셈을 "리포 밖"이라 적고 `[오프셋 미검증]`을
    남겨 뒀는데 **둘 다 더는 사실이 아니다** — 품셈은 리포 안
    `시설평가/202201_스마트팜 표준화_품셈.pdf`에 있고(104차 F1), 오프셋도
    107차에 실측했다(인쇄 = PDF − 24). 미검증 표기는 104차에 전부 걷혔다.
    """
    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    for fname in ("smartfarm_engine.py", "엔진데이터_레지스트리.json"):
        src = open(_o.path.join(repo, fname), encoding="utf-8").read()
        assert "printed p." not in src, (
            f"{fname}에 `printed p.`가 다시 들어왔다 — 그 숫자는 PDF 쪽번호이지 "
            f"인쇄 쪽번호가 아니다. `PDF p.X(인쇄 Y)` 또는 `[오프셋 미검증]`으로 적을 것")
    # 확인된 오프셋이 표기에 실제로 반영돼 있는가(문서별 앵커 1건씩)
    src = open(_o.path.join(repo, "smartfarm_engine.py"), encoding="utf-8").read()
    for anchor in ("PDF p.337(인쇄 301)", "PDF p.24(인쇄 18)", "PDF p.12(인쇄 6)",
                   "PDF p.62(인쇄 55)", "PDF p.389(인쇄 353)"):
        assert anchor in src, anchor


def test_105cha_verify_ref_is_registered_and_ratio_is_not_a_quality_signal():
    """105차 — A-12 실측 대조 기준을 상수로 승격하고 **한계를 코드에 박는다**.

    231·180은 함수 안 하드코딩이라 감사기가 볼 수 없었다(감사 사각). 원문서
    `SmartFarm_엔진데이터.md`가 리포에 없어 **측정 조건을 확인할 수 없으므로**,
    이 비율의 이동을 품질 신호로 읽으면 안 된다는 것도 함께 고정한다.
    """
    import os as _o
    assert e.HEATING_VERIFY_REF_KCAL_H_M2 == {"유리": 231.0, "기타": 180.0}
    assert e.HEATING_VERIFY_RATIO_BAND == (0.35, 1.8)
    assert e.verify_heating_vs_actual(231.0, "유리")["ratio"] == 1.0
    assert e.verify_heating_vs_actual(180.0, "필름")["ratio"] == 1.0
    assert e.verify_heating_vs_actual(180.0, "불소필름")["ref_kcal_h_m2"] == 180.0
    # 대역 경계
    assert e.verify_heating_vs_actual(231.0 * 0.35, "유리")["status"] == "정상"
    assert e.verify_heating_vs_actual(231.0 * 0.34, "유리")["status"].startswith("재확인")
    # 원문서가 정말 없다 — 있으면 이 테스트가 알리고 status를 올릴 수 있다
    repo = _o.path.dirname(_o.path.abspath(__file__))
    assert not _o.path.exists(_o.path.join(repo, "SmartFarm_엔진데이터.md")), (
        "A-12 원문서가 들어왔다 — 231/180의 측정 조건을 확인하고 status를 갱신할 것")
    # 한계가 코드에 적혀 있는가(잊히지 않게)
    src = open(_o.path.join(repo, "smartfarm_engine.py"), encoding="utf-8").read()
    assert "자릿수 검증 전용" in src
    assert "99차 결정에 대한 반대 신호" in src


def test_benchmark_flags_gross_error():
    # 명백한 과소 견적은 경고로 잡혀야 함
    r = e.benchmark_check(50_000_000, 3000, e.Cover.FILM)  # 16,667원/㎡
    assert r["status"] == "경고(밴드이탈)"


# ── 2. 규격 선정 (E2) ────────────────────────────────────────
def test_spec_selection_basic():
    res = e.select_specs(region_snow_cm=30, region_wind_ms=35)
    # 26종 중 충족 규격이 존재하고, 형식별 최소사양이 잡혀야
    assert len(res["candidates"]) >= 10
    assert "단동" in res["min_by_form"]
    assert "연동" in res["min_by_form"]


def test_spec_selection_rejects_understrength():
    # 폭설지역(적설심 60): 충족 규격이 급감해야
    res = e.select_specs(region_snow_cm=60, region_wind_ms=45)
    for s in res["candidates"]:
        assert s.snow_cm >= 60 and s.wind_ms >= 45


# ── 2-1. SPEC_TABLE 전면 확장(32→249종, 2025-108호) 회귀 (2026-07-22) ──────
def test_spec_table_form_counts_match_source_sheets():
    # 농사로 마스터 xlsx 시트별 모델수(인삼·버섯 제외)와 정확히 일치해야
    from collections import Counter
    counts = Counter(s.form for s in e.SPEC_TABLE)
    assert counts == {"연동": 81, "단동": 157, "광폭": 11}
    assert len(e.SPEC_TABLE) == 249


def test_spec_table_old_32_values_are_subset_of_new_249():
    # 2014-78호 기준 옛 32종의 (form, snow_cm, wind_ms) 값이 새 249종 안에
    # 전량 그대로 존재해야 한다 — REGION_DESIGN_LOAD와 달리 이번 확장은
    # "틀린 값을 고치는" 게 아니라 "맞는 32종에 217종을 추가하는" 것이었으므로.
    old_32 = [
        ("연동", 53, 40), ("연동", 57, 36), ("연동", 55, 40), ("연동", 55, 40), ("연동", 55, 40),
        ("단동", 50, 35), ("단동", 50, 35), ("단동", 50, 36), ("단동", 48, 37),
        ("단동", 41, 32), ("단동", 42, 35), ("단동", 37, 33), ("단동", 41, 35),
        ("단동", 30, 32), ("단동", 28, 39), ("단동", 27, 41), ("단동", 25, 33),
        ("단동", 26, 36), ("단동", 30, 28), ("단동", 29, 27), ("단동", 27, 27),
        ("단동", 30, 28), ("단동", 50, 40), ("단동", 55, 42),
        ("광폭", 33, 40), ("광폭", 35, 40), ("광폭", 25, 28), ("광폭", 23, 28),
        ("광폭", 23, 29), ("광폭", 23, 27), ("광폭", 20, 27), ("광폭", 20, 27),
    ]
    new_set = {(s.form, s.snow_cm, s.wind_ms) for s in e.SPEC_TABLE}
    for form, snow, wind in old_32:
        assert (form, snow, wind) in new_set, f"옛 규격 {form}/{snow}/{wind}이 새 SPEC_TABLE에서 사라짐"


# ── 3. 난방부하 이중검증 (E7/C7) ─────────────────────────────
def test_heating_dual_verify_glass():
    # 유리온실 근사 입력 → 면적당 부하가 실측(231)과 같은 자릿수
    hr = e.heating_load(surface_area_m2=5000, cover="유리",
                        t_target=10, t_min=-7.8, fr=0.7,
                        floor_area_m2=3456)
    v = e.verify_heating_vs_actual(hr.load_per_m2, "유리")
    assert v["status"] == "정상", v


# ── 3-1. 난방부하 max/period U 분리 (2026-07-20 구조개선, 2026-08-16 P1-5로 기본값 분리) ─
def test_heating_load_u_default_uses_u_design_for_max_load():
    # 2026-08-16(P1-5): "필름" 등 U_DESIGN이 있는 cover는 이제 u_design 기본값이
    # U_VALUE가 아니라 U_DESIGN(Diop 등 핫박스 극한조건값)이어야 한다.
    hr_default = e.heating_load(surface_area_m2=5000, cover="필름",
                                t_target=10, t_min=-7.8, fr=0.7)
    hr_explicit = e.heating_load(surface_area_m2=5000, cover="필름",
                                 t_target=10, t_min=-7.8, fr=0.7,
                                 u_design=e.U_DESIGN["필름"], u_period=e.U_VALUE["필름"])
    assert hr_default.max_load_kcal_h == hr_explicit.max_load_kcal_h
    assert hr_default.fuel_consumption == hr_explicit.fuel_consumption
    # U_DESIGN["필름"](8.9) > U_VALUE["필름"](2.66)이므로 기본값도 더 이상 같지 않다
    hr_old_coupled = e.heating_load(surface_area_m2=5000, cover="필름",
                                    t_target=10, t_min=-7.8, fr=0.7,
                                    u_design=e.U_VALUE["필름"], u_period=e.U_VALUE["필름"])
    assert hr_default.max_load_kcal_h > hr_old_coupled.max_load_kcal_h


def test_heating_load_u_default_stays_coupled_when_no_u_design_entry():
    # U_DESIGN에 없는 cover("유리")는 기존처럼 U_VALUE[cover]로 계속 폴백해야 한다
    # (Diop 논문은 PE필름 대상이라 유리는 손대지 않음 — 회귀 영향 없어야 함)
    assert "유리" not in e.U_DESIGN
    hr_default = e.heating_load(surface_area_m2=5000, cover="유리",
                                t_target=10, t_min=-7.8, fr=0.7)
    hr_explicit = e.heating_load(surface_area_m2=5000, cover="유리",
                                 t_target=10, t_min=-7.8, fr=0.7,
                                 u_design=e.U_VALUE["유리"], u_period=e.U_VALUE["유리"])
    assert hr_default.max_load_kcal_h == hr_explicit.max_load_kcal_h
    assert hr_default.fuel_consumption == hr_explicit.fuel_consumption


def test_heating_load_u_design_period_separation():
    # 서로 다른 u_design/u_period를 주면 max_load와 fuel_consumption이 독립적으로 반응해야
    base = e.heating_load(surface_area_m2=5000, cover="필름",
                          t_target=10, t_min=-7.8, fr=0.7,
                          u_design=2.66, u_period=2.66)
    higher_design_only = e.heating_load(surface_area_m2=5000, cover="필름",
                                        t_target=10, t_min=-7.8, fr=0.7,
                                        u_design=5.7, u_period=2.66)
    # u_design만 올리면 max_load(설비용량)는 커지되 fuel_consumption(연료소비)은 불변
    assert higher_design_only.max_load_kcal_h > base.max_load_kcal_h
    assert higher_design_only.fuel_consumption == base.fuel_consumption


# ── 3-2. FR_TABLE 방향성 수정 (2026-07-20) ────────────────────
def test_curtain_exposure_ratio_inverts_savings_rate():
    # 열절감률(클수록 좋음) → 노출비율(작을수록 좋음)로 뒤집혀야
    assert e.curtain_exposure_ratio("PO단일") == 1 - e.FR_TABLE["PO단일"]
    assert e.curtain_exposure_ratio("이중커튼") == 1 - e.FR_TABLE["이중커튼"]
    # 보온이 더 좋은 커튼일수록 노출비율은 더 작아야(방향 반전 확인)
    assert e.curtain_exposure_ratio("이중커튼") < e.curtain_exposure_ratio("다겹보온")
    assert e.curtain_exposure_ratio("다겹보온") < e.curtain_exposure_ratio("PO단일")


def test_curtain_exposure_ratio_unknown_curtain_raises():
    import pytest
    with pytest.raises(ValueError):
        e.curtain_exposure_ratio("존재하지않는커튼")


def test_fr_table_values_match_public_sources():
    # 68차: 0.85 재조사 후 교체(사용자 결정). 이중커튼·2중커튼은 농사로(농진청
    # 공식 포털) "스크린 사용 적정 개수" 표의 2장 보온력 70%가 근거 — 값이 되돌아
    # 가면(0.85 등) 근거 없는 상태로의 회귀이므로 여기서 잡는다.
    assert e.FR_TABLE["이중커튼"] == e.FR_TABLE["2중커튼"] == 0.70
    # PO단일·다겹보온은 NIHHS 공식 계산기 실측(33.6%·56.3%) 근사 정합값 — 변경 없음
    assert e.FR_TABLE["PO단일"] == 0.35 and e.FR_TABLE["다겹보온"] == 0.5
    # 순서(보온 성능)는 어떤 값 개정에서도 유지되어야 한다
    assert e.FR_TABLE["PO단일"] < e.FR_TABLE["다겹보온"] < e.FR_TABLE["이중커튼"] < 1.0


def test_total_pyeong_price_matches_source_table():
    # 69차: 원출처(내재해형 고시 예정공사비 — 한국농업시설협회, "온실 선정 및 비용
    # 견적 프로그램.xlsx" [골조예상비용]) 전사값 고정. 원표는 리포 밖 파일이라
    # 여기서는 전사 결과를 핀으로 잡고, 근거·검산은 보존본 md가 담는다.
    t = e.TOTAL_PYEONG_PRICE
    assert len(t) == 33                       # 4종 → 33종(연동 5·단동 19·광폭 6·과수 3)
    # 기존 4종은 재조사 후에도 원단위 불변(원표와 일치 확인됨)
    assert t["07-연동-1"] == 430_465 and t["08-연동-1"] == 389_990
    assert t["10-연동-1"] == 572_614 and t["12-연동-1"] == 584_794
    # 69차 추가분의 앵커: 총금액÷평수=평단가 재현(원표 검산과 동일 산식)
    assert round(470_629_000 / 720) == t["10-연동-2"] == 653_651   # 랙피니언식 천창개폐
    assert round(12_431_000 / 206) == t["07-단동-1"] == 60_345
    assert round(91_651_000 / 407) == t["13-광폭(보온재)-1"] == 225_187
    assert round(111_209_000 / 582) == t["07-포도-1"] == 191_081
    # 같은 10-연동이라도 개폐 방식이 단가를 가른다(권취식 < 랙피니언식)
    assert t["10-연동-1"] < t["10-연동-2"]
    # 개산 함수가 확장된 규격에서도 동작(방법 A — 골조 단독 아님)
    assert e.greenhouse_total_estimate("10-연동-2", 100) == 653_651 * 100


def test_fr_table_curtain_path_is_live_not_unused():
    # 68차 레드팀 12회차 F2 고정: FR_TABLE은 "미사용 참고표"가 아니다 —
    # curtain= 경로가 heating_load()에 실제로 반영된다(build_site·webapp이 이 경로
    # 사용). 값 교체가 산출물에 그대로 흘러가므로, 경로가 살아 있음을 못박는다.
    base = dict(surface_area_m2=1000, cover="필름", t_target=15, t_min=-10)
    load_new = e.heating_load(**base, curtain="이중커튼").max_load_kcal_h
    load_old_fr = e.heating_load(**base, fr=1 - 0.85).max_load_kcal_h   # 교체 전 값 재현
    assert load_new == pytest_approx(load_old_fr * 2)   # 0.15→0.30: 정확히 2배
    # 교체 후 값과 curtain 경로가 일치(표 → 노출비율 → 부하)
    assert load_new == e.heating_load(**base, fr=1 - e.FR_TABLE["이중커튼"]).max_load_kcal_h


def pytest_approx(v, tol=1e-6):
    class _A:
        def __eq__(self, other):
            return abs(other - v) <= tol * max(1.0, abs(v))
    return _A()


# ── 3-3. P1-9(2026-08-17): fr/curtain 시그니처 수준 강제 ────────────
def test_heating_load_curtain_param_converts_internally():
    base = dict(surface_area_m2=1000, cover="필름", t_target=15, t_min=-10)
    via_curtain = e.heating_load(**base, curtain="다겹보온")
    via_fr = e.heating_load(**base, fr=1 - e.FR_TABLE["다겹보온"])
    assert via_curtain.max_load_kcal_h == via_fr.max_load_kcal_h
    # 방향반전 구조 재발 방지: 보온이 좋을수록 부하가 작아야 한다
    l_po = e.heating_load(**base, curtain="PO단일").max_load_kcal_h
    l_dual = e.heating_load(**base, curtain="이중커튼").max_load_kcal_h
    assert l_dual < l_po


def test_heating_load_rejects_ambiguous_missing_or_invalid_fr():
    import pytest
    base = dict(surface_area_m2=1000, cover="필름", t_target=15, t_min=-10)
    with pytest.raises(ValueError):
        e.heating_load(**base)                              # fr·curtain 둘 다 없음
    with pytest.raises(ValueError):
        e.heating_load(**base, fr=0.7, curtain="다겹보온")   # 둘 다 지정(모호)
    with pytest.raises(ValueError):
        e.heating_load(**base, fr=1.5)                      # 노출비율 범위 밖
    with pytest.raises(ValueError):
        e.heating_load(**base, fr=0)                        # 0은 물리적으로 무의미


# ── 3-3b. B4~B8 확장(2026-08-17): 법정 하자담보·전기 품셈 정액 ──────
def test_warranty_statutory_greenhouse_anchor():
    # 별표4 제19호 "온실설치 2년" — 이 확장의 핵심 법정근거. 값이 바뀌면
    # 법령 개정을 확인하고 원문 PDF(리포 사본)와 함께 갱신해야 한다.
    r = e.warranty_period("온실설치")
    assert r["years"] == 2 and "별표4" in r["근거"]
    assert "세부 공종별" in r["비고"]          # 복합공사 비고(원문) 전달
    # 발췌 항목 대표값 대조(원문 PDF 전사)
    assert e.WARRANTY_STATUTORY["방수"]["years"] == 3
    assert e.WARRANTY_STATUTORY["지붕"]["years"] == 3
    assert e.WARRANTY_STATUTORY["급배수·냉난방·환기·공조·자동제어·가스·배연설비"]["years"] == 2


def test_warranty_period_unknown_returns_none_and_sources_are_primary():
    assert e.warranty_period("존재하지않는공종") is None   # 값 안 지어냄
    # 2026-08-18: 전기·통신 원문 확보로 [확인요망] 해소 — 근거에 조항·확인일이
    # 명시돼야 하고, 확인요망 꼬리표가 되살아나면 회귀다
    elec = e.WARRANTY_STATUTORY["전기(건축물 전기설비)"]["근거"]
    comm = e.WARRANTY_STATUTORY["통신(그 외 정보통신공사)"]["근거"]
    assert "확인요망" not in elec and "확인요망" not in comm
    assert "별표3의2 제7호" in elec and "원문 확인" in elec
    assert "제37조 제3호" in comm and "구내 케이블 제외" in comm


def test_electrical_pumsem_lump_reference():
    # P1-10 라운드4에서 원단위 대사로 검증된 품셈 표준설계 정액(2021)
    assert e.ELECTRICAL_PUMSEM_LUMP_WON_PER_HA == 250_000_000


# ── 3-3c. P3-18(2026-08-17): 금융조달 대출상환표 ────────────────────
def test_loan_amortization_equal_payment_hand_computed():
    import pytest as _pt
    # 1억·10%·3년·무거치 원리금균등: 연납입액 = 1e8×0.1×1.1³/(1.1³−1) = 40,211,480.4
    am = e.loan_amortization(100_000_000, 10.0, 3)
    annuity = 100_000_000 * 0.1 * 1.1**3 / (1.1**3 - 1)
    assert all(row["납입액"] == _pt.approx(annuity, rel=1e-9) for row in am["rows"])
    assert am["rows"][0]["이자"] == _pt.approx(10_000_000)
    assert am["rows"][-1]["잔액"] == 0.0                      # 완제
    assert am["총이자"] == _pt.approx(3 * annuity - 100_000_000, rel=1e-9)


def test_loan_amortization_equal_principal_with_grace():
    import pytest as _pt
    # 3억·6%·전체 3년(거치 1년) 원금균등: 거치 이자 18M → 상환 150M+18M, 150M+9M
    am = e.loan_amortization(300_000_000, 6.0, 3, grace_years=1, method="원금균등")
    assert [row["구분"] for row in am["rows"]] == ["거치", "상환", "상환"]
    assert am["rows"][0]["납입액"] == _pt.approx(18_000_000)   # 거치: 이자만
    assert am["rows"][1]["원금"] == _pt.approx(150_000_000)
    assert am["rows"][2]["이자"] == _pt.approx(9_000_000)      # 잔액 150M×6%
    assert am["총이자"] == _pt.approx(45_000_000)
    assert am["총납입액"] == _pt.approx(345_000_000)


def test_loan_amortization_zero_rate_and_validation():
    import pytest as _pt
    am = e.loan_amortization(90_000_000, 0.0, 3)              # 무이자: 3연 균등
    assert am["총이자"] == 0.0
    assert all(row["납입액"] == _pt.approx(30_000_000) for row in am["rows"])
    for bad in [dict(principal_won=0, annual_rate_pct=3, term_years=5),
                dict(principal_won=1e8, annual_rate_pct=-1, term_years=5),
                dict(principal_won=1e8, annual_rate_pct=3, term_years=5, grace_years=5),
                dict(principal_won=1e8, annual_rate_pct=3, term_years=5, method="이상한방식")]:
        with _pt.raises(ValueError):
            e.loan_amortization(**bad)


# ── 3-3d. LCC 기자재 내용연수(2026-08-18, 데이터 대기 ② 해소) ────────
def test_equipment_service_life_reference_values():
    # 조달청 고시 제2024-30호 [별표1] 원문 전사 대표값 가드(PDF 리포 사본과 대조)
    R = e.EQUIPMENT_SERVICE_LIFE_REFERENCE
    assert R["온풍난방기"]["years"] == 11 and R["온풍난방기"]["code"] == "40101866"
    assert R["전기보일러"]["years"] == 13
    assert R["송풍기(유동·배기팬류)"]["years"] == 10
    assert R["정량펌프(양액공급류)"]["years"] == 11
    assert R["분전반"]["years"] == 8
    assert R["빌딩자동제어장치(복합환경제어 유사분류)"]["years"] == 11
    assert R["컴퓨터서버"]["years"] == 6
    assert R["보안용카메라"]["years"] == 6
    # 전 항목이 8자리 물품분류번호와 양수 연수를 갖는다(추적성)
    assert all(len(v["code"]) == 8 and v["years"] > 0 for v in R.values())


def test_lcc_replacement_schedule_deterministic():
    import pytest as _pt
    items = [
        {"name": "온풍난방기", "unit_cost_won": 20_000_000, "service_life_years": 11},
        {"name": "데스크톱컴퓨터", "unit_cost_won": 1_500_000, "service_life_years": 5},
        {"name": "배전반", "unit_cost_won": 8_000_000, "service_life_years": 12},
    ]
    r = e.lcc_replacement_schedule(items, horizon_years=20)
    by = {row["name"]: row for row in r["rows"]}
    assert by["온풍난방기"]["replacement_years"] == [11]            # 11년 1회
    assert by["데스크톱컴퓨터"]["replacement_years"] == [5, 10, 15]  # 지평 말(20)은 제외
    assert by["배전반"]["replacement_years"] == [12]
    assert r["total_replacement_cost_won"] == _pt.approx(
        20_000_000 * 1 + 1_500_000 * 3 + 8_000_000 * 1)
    # 수명이 지평 이상이면 교체 없음
    r2 = e.lcc_replacement_schedule(
        [{"name": "전기보일러", "unit_cost_won": 30_000_000, "service_life_years": 13}], 10)
    assert r2["rows"][0]["n_replacements"] == 0
    with _pt.raises(ValueError):
        e.lcc_replacement_schedule(items, 0)
    with _pt.raises(ValueError):
        e.lcc_replacement_schedule([{"name": "x", "unit_cost_won": 1, "service_life_years": 0}], 10)


def test_structure_service_life_statutory_values():
    # 법인세법 시행규칙 별표5<개정 2024.11.11.>·별표6<개정 2024.3.22.> 원문 전사
    # 가드(PDF 리포 사본과 대조) — 값이 바뀌면 법령 개정 확인 후 함께 갱신할 것
    R = e.STRUCTURE_SERVICE_LIFE_STATUTORY
    k3 = "별표5_제3호(연와조·블록조·콘크리트조·목조 등 기타 조)"
    k4 = "별표5_제4호(철골·철근콘크리트조 등)"
    assert R[k3]["years"] == 20 and R[k3]["range"] == (15, 25)
    assert R[k4]["years"] == 40 and R[k4]["range"] == (30, 50)
    assert R["별표5_비고3(제3호 단축)"]["years"] == 10
    assert R["별표5_비고3(제3호 단축)"]["range"] == (8, 12)
    assert R["별표5_비고3(제4호 단축)"]["years"] == 20
    assert R["별표5_비고3(제4호 단축)"]["range"] == (15, 25)
    assert R["별표6_제2호(농업 01 업종별 자산)"]["years"] == 5
    assert R["별표6_제2호(농업 01 업종별 자산)"]["range"] == (4, 6)
    # 전 항목: 하한 ≤ 기준내용연수 ≤ 상한 (별표의 내용연수범위 구조)
    for v in R.values():
        lo, hi = v["range"]
        assert lo <= v["years"] <= hi and v["대상"]


def test_structure_service_life_no_greenhouse_type_keys():
    # 판단성 가드: 비고3 가목에 축사는 열거되나 온실은 미열거 — 온실유형→호
    # 자동 매핑 키가 등록되면 유추 적용(원칙 위반)이므로 구조적으로 차단한다.
    # 호 선택은 컨설턴트·세무사 몫(케이스에는 선택 근거와 함께 주입값으로).
    for k in e.STRUCTURE_SERVICE_LIFE_STATUTORY:
        assert k.startswith("별표"), k
        assert not any(w in k for w in ("유리", "비닐", "온실", "하우스")), \
            f"{k}: 온실유형 키 금지 — 호 적용은 판단성"


# ── 3-3e. P1-6 잔여 해소(2026-08-18): 감리비 참고 표시 ────────────────
def test_supervision_fee_rate_table_transcription():
    # 국토교통부고시 제2020-635호 별표5 원문 전사 가드(PDF 리포 사본 대조)
    T = e.SUPERVISION_FEE_RATE_TABLE
    assert len(T) == 17
    assert T[0] == (50_000_000, 2.02, 2.24, 2.46)      # "5천만원 이하" 행
    assert (1_000_000_000, 1.11, 1.23, 1.35) in T      # 07-23 웹 확인값과 일치 확인
    assert (2_000_000_000, 1.02, 1.13, 1.24) in T
    assert T[-1] == (500_000_000_000, 0.84, 0.93, 1.02)
    # 구조 가드: 공사비 오름차순, 요율은 단조 비증가, 각 행 단순<보통<복잡
    for (c1, *r1), (c2, *r2) in zip(T, T[1:]):
        assert c1 < c2 and all(a >= b for a, b in zip(r1, r2))
    for _, g1, g2, g3 in T:
        assert g1 < g2 < g3


def test_design_supervision_fee_reference():
    import pytest as _pt
    # 앵커 정확값(10억): 보간 없이 원문 요율 그대로
    r = e.design_supervision_fee_reference(1_000_000_000)
    assert r["요율_pct"]["제1종(단순)"] == 1.11 and r["요율_pct"]["제3종(복잡)"] == 1.35
    # 원채원 스케일(7.0203억): 5억~10억 직선보간(제16조①) — 손계산 대조
    cost = 702_030_000
    r2 = e.design_supervision_fee_reference(cost)
    t = (cost - 500_000_000) / (1_000_000_000 - 500_000_000)
    raw = 1.29 + t * (1.11 - 1.29)
    assert r2["요율_pct"]["제1종(단순)"] == _pt.approx(raw, abs=1e-4)
    assert r2["감리비_원"]["제1종(단순)"] == round(cost * raw / 100)
    assert "직선보간" in r2["산정구간"] and "불산입" in r2["note"]
    # 제16조②: 5천만원 미만은 5천만원으로 간주하여 산출
    r3 = e.design_supervision_fee_reference(30_000_000)
    assert r3["산정공사비_원"] == 50_000_000
    assert r3["감리비_원"]["제1종(단순)"] == round(50_000_000 * 2.02 / 100)
    # 제16조③: 5천억 초과는 별도 공식(미확보) — 지어내지 않고 None
    assert e.design_supervision_fee_reference(600_000_000_000) is None
    with _pt.raises(ValueError):
        e.design_supervision_fee_reference(0)


# ── 3-4. P1-11(2026-08-17): select_specs 작물특화형 필터 ────────────
def test_select_specs_default_excludes_crop_specific():
    # 왜곡 실측 지점(적설20·풍속26): 종전엔 파프리카 전용이 연동 최소사양으로 나왔음
    sel = e.select_specs(20, 26)
    assert all(not s.crop for s in sel["candidates"])  # 기본은 일반형만
    assert sel["min_by_form"]["연동"].name == "20-연동(등)-04"
    assert sel["min_by_form"]["연동"].crop == ""


def test_select_specs_crop_param_includes_that_crop_only():
    sel = e.select_specs(20, 30, form="단동", crop="수박")
    crops_in = {s.crop for s in sel["candidates"]}
    assert crops_in <= {"", "수박"}          # 일반형 + 수박 특화형만
    assert "수박" in crops_in                # 수박 특화형이 실제 포함됨
    assert sel["min_by_form"]["단동"].name == "21-단동(등)-01"  # 수박 전용이 최소로 경쟁


def test_select_specs_star_reproduces_legacy_and_unknown_crop_is_generic():
    legacy = e.select_specs(20, 26, crop="*")
    assert legacy["min_by_form"]["연동"].crop == "파프리카"     # 구버전 왜곡 동작 재현
    tomato = e.select_specs(20, 26, crop="토마토")              # 특화형 없는 작물
    default = e.select_specs(20, 26)
    assert {s.name for s in tomato["candidates"]} == {s.name for s in default["candidates"]}
    assert "수박" in e.spec_crops() and "참외" in e.spec_crops()


def test_generate_rfq_package_accepts_curtain_path():
    pkg_curtain = e.generate_rfq_package(
        region_snow_cm=40, region_wind_ms=30, area_m2=3000, cover=e.Cover.FILM,
        form="연동", t_target=15, t_min=-10, curtain="다겹보온")
    pkg_fr = e.generate_rfq_package(
        region_snow_cm=40, region_wind_ms=30, area_m2=3000, cover=e.Cover.FILM,
        form="연동", t_target=15, t_min=-10, fr=1 - e.FR_TABLE["다겹보온"])
    assert pkg_curtain.heating.max_load_kcal_h == pkg_fr.heating.max_load_kcal_h


def test_heating_load_with_curtain_exposure_ratio_direction():
    # 실제 heating_load()에 연결했을 때도 "보온 잘 될수록 부하가 작다"가 성립해야
    def load_for(curtain):
        fr = e.curtain_exposure_ratio(curtain)
        return e.heating_load(surface_area_m2=5000, cover="유리",
                              t_target=10, t_min=-7.8, fr=fr).max_load_kcal_h

    assert load_for("이중커튼") < load_for("다겹보온") < load_for("PO단일")


# ── 4. 골조 단가 정의 구분 (이중계산 방지) ───────────────────
def test_structure_vs_total_price_distinct():
    area_py = 1000
    total = e.greenhouse_total_estimate("07-연동-1", area_py)   # 온실전체
    struct = e.structure_only_estimate(area_py)                 # 골조단독
    # 온실전체가 골조단독보다 훨씬 커야(이중계산이면 같아짐)
    assert total > struct * 2


# ── 5. 재무지표 (F5/F6) ──────────────────────────────────────
def test_finance_positive_case():
    f = e.finance(revenue=332_640_000, opex=186_420_000,
                  capex=702_030_000, subsidy_rate=0.5)
    assert f.operating_profit > 0
    assert f.roi > 0
    assert f.payback_years and f.payback_years > 0
    # 보조금 반영 실질ROI가 명목ROI보다 커야
    assert f.real_roi_after_subsidy > f.roi


def test_npv_irr_consistency():
    cfs = [-1000, 300, 300, 300, 300, 300]
    n = e.npv(0.05, cfs)
    r = e.irr(cfs)
    assert r is not None
    # IRR 할인율에서 NPV≈0
    assert abs(e.npv(r, cfs)) < 1.0


def test_env_fitness_and_yield():
    fit = e.env_fitness(light_r=1.0, temp_r=1.0, humid_r=1.0, co2_r=1.0)
    assert 99 <= fit <= 101              # 완전 최적 ≈ 100%
    assert e.yield_adjustment(fit) == 0.0
    assert e.yield_adjustment(55) == -0.40


# ── 6. 리뉴얼 개선 ROI (F7) ─────────────────────────────────
def test_improvement_roi():
    r = e.improvement_roi(annual_saving=12_000_000, invest=36_000_000)
    assert abs(r["roi"] - 1/3) < 1e-6
    assert abs(r["payback"] - 3.0) < 1e-6


# ── 7. 단지 경제성 (F8) ─────────────────────────────────────
def test_cluster_economics():
    c = e.cluster_economics(n_farms=5, per_farm_capex=600_000_000,
                            shared_capex=750_000_000,
                            per_farm_opex=100_000_000)
    assert c["per_farm_share"] == 150_000_000
    # 보조 70% 반영 후 공동분담 급감 (부동소수 허용)
    assert abs(c["per_farm_share_after_subsidy"] - 45_000_000) < 1
    # 규모의 경제로 OPEX 감소
    assert abs(c["per_farm_opex_after_scale"] - 85_000_000) < 1


# ── 8. CAPEX 카테고리 분해 (2026-07-16, 스마트팜스펙 실측 청킹) ─────
def test_capex_breakdown_umj_reconciles_to_source():
    # 우민재 원본 내역서 순공사비 합계(재+노+경) = 456,158,140원과 원단위 일치해야
    cb = e.capex_breakdown(e.CAPEX_CASE_CHUNKS["우민재"])
    assert cb.total == 456_158_140
    assert abs(sum(cb.shares_pct.values()) - 100.0) < 0.5  # 반올림 오차만 허용


def test_capex_breakdown_chj_reconciles_to_source():
    # 최혁진 원본 내역서 순공사비 합계 = 694,575,784원과 원단위 일치해야
    cb = e.capex_breakdown(e.CAPEX_CASE_CHUNKS["최혁진"])
    assert cb.total == 694_575_784
    assert abs(sum(cb.shares_pct.values()) - 100.0) < 0.5


def test_capex_breakdown_missing_category_defaults_zero():
    cb = e.capex_breakdown({"frame": 100_000_000})
    assert cb.total == 100_000_000
    assert cb.shares_pct["frame"] == 100.0
    assert cb.items["electrical_aux"] == 0.0


def test_capex_observed_range_reference_not_pass_fail():
    # 관측범위는 정상/경고를 가르지 않는다 — 벗어나도 함수는 에러를 내지 않음
    extreme = {"frame": 900_000_000, "scaffold": 1}
    cb = e.capex_breakdown(extreme)
    assert "frame" in cb.out_of_observed_range  # 참고 표시는 되지만
    assert cb.total > 0                          # 계산 자체는 그대로 진행


# ── 9. OPEX 항목 분해 (2026-07-16, 제안값) ─────────────────────
def test_opex_breakdown_total_unchanged():
    # 원채원 케이스 기존 lump-sum(186,420,000원)을 항목 분해해도 총액은 불변
    items = {"종묘비": 40_000_000, "비료비": 15_000_000, "광열동력비": 60_000_000}
    ob = e.opex_breakdown(items, known_total=186_420_000)
    assert ob.total == 186_420_000
    assert ob.unclassified == 186_420_000 - sum(items.values())
    assert ob.unclassified >= 0


def test_opex_breakdown_full_classification_zero_unclassified():
    items = {"종묘비": 100}
    ob = e.opex_breakdown(items, known_total=100)
    assert ob.unclassified == 0


def test_opex_breakdown_rejects_overclassification():
    import pytest
    with pytest.raises(ValueError):
        e.opex_breakdown({"종묘비": 200}, known_total=100)


# ── 9-1. 영업 손익분기 (2026-07-21, Step6 리포트용) ──────────
def test_operating_breakeven_basic():
    r = e.operating_breakeven(opex=186_420_000, price_won_per_kg=2500)
    assert r.breakeven_revenue_won == 186_420_000
    assert r.breakeven_kg == 186_420_000 / 2500


def test_operating_breakeven_rejects_nonpositive_price():
    import pytest
    with pytest.raises(ValueError):
        e.operating_breakeven(opex=100, price_won_per_kg=0)


# ── 10. 입지 지역 매핑 (2026-07-21, 2025-108호 개정 반영으로 전면 갱신) ──
def test_siting_design_load_returns_none_for_unmapped_region():
    # 매핑표에 없는 지명 — 예외 없이 None만 반환해야
    assert e.siting_design_load("충남 임의지역") is None


def test_siting_design_load_matches_existing_case_regions():
    # 케이스 region 필드는 자유서술형("강원(춘천)", "충남 천안(성환읍)") — 부분일치로 조회
    # 2025-108호 개정으로 춘천 wind_ms 32→34(snow_cm은 32로 불변), 천안은 무변경
    assert e.siting_design_load("강원(춘천)") == {"snow_cm": 32, "wind_ms": 34}
    assert e.siting_design_load("충남 천안(성환읍)") == {"snow_cm": 26, "wind_ms": 28}


def test_siting_design_load_exact_match_for_disambiguated_duplicates():
    # 고성·광주는 지명이 두 도에 중복돼 괄호로 구분 — 정확일치만 허용
    # 2025-108호 개정으로 고성(강원)은 종전 "40cm 이상" 뭉뚱그림이 실측 79cm로 구체화,
    # 광주광역시는 36→38cm로 상향. 고성(경남)·광주(경기)는 무변경
    assert e.siting_design_load("고성(강원)") == {"snow_cm": 79, "wind_ms": 43}
    assert e.siting_design_load("고성(경남)") == {"snow_cm": 20, "wind_ms": 38}
    assert e.siting_design_load("광주(경기)") == {"snow_cm": 24, "wind_ms": 26}
    assert e.siting_design_load("광주광역시") == {"snow_cm": 38, "wind_ms": 32}


def test_siting_design_load_ambiguous_duplicate_name_returns_none():
    # 광역 힌트 없는 "고성"만으로는 강원/경남 중 어느 쪽인지 판단 근거가 없다 — 지어내지 않음
    assert e.siting_design_load("고성") is None


def test_region_design_load_count():
    assert len(e.REGION_DESIGN_LOAD) == 172


def test_siting_lookup_returns_none_for_unmapped_region():
    assert e.siting_lookup("충남 임의지역") is None


def test_siting_lookup_matches_manual_select_specs_chain():
    # siting_lookup()은 siting_design_load()+select_specs()를 그대로 이은 것 — 수동 체이닝과 동일해야
    load = e.siting_design_load("강원(춘천)")
    manual = e.select_specs(load["snow_cm"], load["wind_ms"])
    result = e.siting_lookup("강원(춘천)")
    assert result["region_snow_cm"] == load["snow_cm"]
    assert result["region_wind_ms"] == load["wind_ms"]
    assert result["candidates"] == manual["candidates"]
    assert result["min_by_form"] == manual["min_by_form"]


def test_siting_lookup_respects_form_filter():
    result = e.siting_lookup("충남 천안(성환읍)", form="연동")
    assert set(result["min_by_form"].keys()) <= {"연동"}
    assert all(c.form == "연동" for c in result["candidates"])


def test_siting_lookup_without_form_covers_multiple_forms():
    # form 미지정 시 select_specs()처럼 연동/단동/광폭 후보를 형식별로 모두 반환
    result = e.siting_lookup("강원(춘천)")
    assert set(result["min_by_form"].keys()) == set(e.select_specs(32, 34)["min_by_form"].keys())


# ── 11. CAPEX 13개 상위 카테고리 (2026-07-16, 사용자 제안 채택) ─────
def test_capex_major_breakdown_umj_reconciles_to_source():
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["우민재"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["우민재"])
    assert cb.total == 456_158_140  # 원문 리터럴 앵커 — 단일 출처 상수의 드리프트를 여기서 잡는다(53차 F8)
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["우민재"]
    assert sum(cb.items.values()) + cb.unclassified == 456_158_140


def test_capex_major_breakdown_chj_reconciles_to_source():
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["최혁진"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["최혁진"])
    assert cb.total == 694_575_784
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["최혁진"]
    assert sum(cb.items.values()) + cb.unclassified == 694_575_784


def test_capex_major_breakdown_dh_reconciles_to_source():
    # 2026-07-21 추가 — 이두희 원가계산서 14개 세부공종 합계열 총합(433,606,460)이
    # known_total. unclassified는 '5-3.베드설치'(101,301,410, 9/13카테고리 어디에도
    # 안 맞아 미분류로 남긴 항목)와 정확히 일치해야 한다.
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["이두희"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["이두희"])
    assert cb.total == 433_606_460
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["이두희"]
    assert sum(cb.items.values()) + cb.unclassified == 433_606_460


def test_capex_major_breakdown_ysh_reconciles_to_source():
    # 2026-08-17 추가(P2-17 청킹→엔진 승격 1호) — 윤성호 내역서 공종별집계표(p3)
    # 16개 공종 합 1,162,078,090원(=원가계산서 p2 재료비+직접노무비+산출경비)이
    # known_total. unclassified는 행잉거터(0110)+작물와이어(0111)=39,220,352원.
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["윤성호"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["윤성호"])
    assert cb.total == 1_162_078_090
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["윤성호"]
    assert sum(cb.items.values()) + cb.unclassified == 1_162_078_090
    # 축열조 라인분리 정합: hvac 잔액 + 축열조 = 0109 유동휀·훈증기 + 0114 난방설비 원문값
    assert cb.items["hvac"] + cb.items["thermal_storage_insulation"] == 9_672_200 + 180_052_389
    # 이 표본으로 처음 채워진 두 카테고리(다른 3개 케이스에선 전부 0)
    assert cb.items["auxiliary_facility"] == 40_093_200
    assert cb.items["thermal_storage_insulation"] == 41_958_000


def test_capex_major_breakdown_hanil_reconciles_to_source():
    # 2026-08-18 추가(51차 "다른 견적 세부 분석" 1호) — 한일그린텍 설계예산서(20p)
    # 공사 집계표(p4) 8공종 소계 합=원가계산서(p3) 직접재료비+직접노무비+기계경비
    # =직접공사비 355,597,412원이 known_total. unclassified는 스탠딩 거터(스티,
    # 67.5m 28줄) 46,519,015원(재배시설 성격 — 이두희 베드·윤성호 행잉거터 선례).
    assert 241_374_292 + 97_796_120 + 16_427_000 == 355_597_412  # 원가계산서 p3 원단위 재현
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["한일그린텍"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["한일그린텍"])
    assert cb.total == 355_597_412
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["한일그린텍"] == 46_519_015
    assert sum(cb.items.values()) + cb.unclassified == 355_597_412
    # 공종→카테고리 합성 앵커(집계표 p4 원문 소계): 기초+골조+피복+전면판넬 / 커튼+동력장치
    assert cb.items["greenhouse_structure"] == 14_694_738 + 158_498_030 + 27_231_655 + 16_397_033
    assert cb.items["auto_opening_system"] == 52_411_062 + 21_474_455
    assert cb.items["irrigation_fertigation"] == 18_371_424
    # 본공사 범위에 난방·독립 환경제어·별도 전기 공종 없음(환급금 재투자 블록은 known_total 밖)
    assert cb.items["hvac"] == cb.items["ict_control"] == cb.items["electrical"] == 0
    # 40차 ACTUALS 대조와의 집계 레벨 정합: 총공사비 480,636,000(절사 전 480,636,200)
    # = 도급 공급가액 소계 416,072,106 + 부가세 39,664,769 + 환급금 재투자 24,899,325(=공급 22,635,750+부가세 2,263,575).
    # 절사 전 합에서 원가계산서 p3 소계 455,736,875(=416,072,106+39,664,769)를 원단위 재현.
    assert 416_072_106 + 39_664_769 == 455_736_875
    assert 455_736_875 + 22_635_750 + 2_263_575 == 480_636_200


def test_capex_major_breakdown_ljh_reconciles_to_source():
    # 2026-08-18 추가(52차 "다른 견적 세부 분석" 2호) — 이준희(서산, 표본 최초의
    # 벤로형 유리온실 5,404.32㎡) 공종별집계표 합계행=원가계산서 직재+직노+산출경비
    # =직접공사비 1,010,337,181원이 known_total. unclassified는 행잉거터+유인줄
    # (재배시설 — 윤성호 0110/0111 선례)+기타공사(선홈통·바닥배수 부대).
    assert 758_880_699 + 237_736_474 + 13_720_008 == 1_010_337_181  # 원가계산서 원단위 재현
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["이준희"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["이준희"])
    assert cb.total == 1_010_337_181
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["이준희"] == 93_326_116
    assert sum(cb.items.values()) + cb.unclassified == 1_010_337_181
    # 공종→카테고리 합성 앵커(공종별집계표 원문 소계)
    assert cb.items["greenhouse_structure"] == 6_314_238 + 69_936_701 + 169_114_684 + 174_804_328 + 144_093_767
    assert cb.items["auto_opening_system"] == 47_477_403 + 125_978_303
    assert cb.items["hvac"] == 7_093_767            # 09 유동휀만(난방설비 11은 "본 공사제외")
    assert cb.items["irrigation_fertigation"] == 28_952_319 + 28_859_014 + 3_904_157 + 5_219_421
    assert cb.items["ict_control"] == 83_463_440    # 1209 복합환경제어 — 표본 최대(PRIVA Compact CC 80,000,000이 95.85%, 54차 F1 귀속 정정)
    assert cb.items["electrical"] == 21_799_523     # 13 동력간선공사
    assert 65_624_205 + 19_138_167 + 8_563_744 == 93_326_116  # 미분류 구성 원문 소계
    # 도급·부가세 환급 체인(견적서·원가계산서 시트 원단위 재현 — 환급 명시 표본 최초)
    assert 1_079_731_365 + 11_177_726 == 1_090_909_091          # 원가 계+이윤=공급가액(일반관리비 0%)
    assert 1_090_909_091 + 109_090_909 == 1_200_000_000         # +부가세=도급 합계
    assert 1_200_000_000 - 1_056_000 - 26_179_000 == 1_172_765_000  # 영세율·환급 차감=실부담


def test_capex_major_breakdown_mjy_reconciles_to_source():
    # 2026-08-18 추가(55차 "다른 견적 세부 분석" 3호) — 맹주연(천안, 명칭 '벤로형'
    # 이나 피복은 전량 PO/PE 필름 — 명칭≠재질). 집계표 13공종 열합=원가계산서
    # 직재+직노+기계경비=439,742,227이 known_total(총계행 표기 439,742,226은 원문
    # 1원 갭 — 구성 합 채택). unclassified는 바닥재및행잉거터(재배시설, 윤성호 선례).
    assert 360_447_860 + 72_269_120 + 7_025_247 == 439_742_227  # 원가계산서 3항목 원단위 재현
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["맹주연"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["맹주연"])
    assert cb.total == 439_742_227
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["맹주연"] == 46_977_648
    assert sum(cb.items.values()) + cb.unclassified == 439_742_227
    # 공종→카테고리 합성 앵커(집계표 원문 소계)
    assert cb.items["greenhouse_structure"] == 28_148_966 + 124_024_505 + 14_080_913 + 29_487_743 + 25_521_173 + 17_890_613
    assert cb.items["auto_opening_system"] == 36_129_616 + 50_479_524 + 14_751_446
    # 혼재 공종 010108 '환기 및 개폐'의 명시 라인 분리(최혁진 0113·윤성호 축열조 방식):
    # 유동팬 42대+환풍기 6대+설치노무 → hvac, 잔여(개폐모터·컨트롤박스·전선) → 자동개폐
    assert cb.items["hvac"] == 5_040_000 + 1_123_200 + 2_508_576 == 8_671_776
    assert 8_671_776 + 14_751_446 == 23_423_222                 # 분리 검산 = 공종 소계 재현
    assert cb.items["irrigation_fertigation"] == 33_686_562 + 5_934_127 + 3_957_615
    assert cb.items["ict_control"] == cb.items["electrical"] == 0
    # 도급 체인(원가계산서 원단위): 순공사비 계+관리비 6%+이윤 15%=공급가액, +부가세→합계 절삭
    assert 493_278_737 + 29_596_724 + 24_250_441 == 547_125_902  # 표기 547,125,903은 원문 1원 갭
    assert 547_125_902 + 54_712_590 == 601_838_492               # 절삭 후 표기 601,838,000
    assert 226_473_083 // 10 == 22_647_308                       # 부가세환급금 = 환급품목×10%


def test_capex_major_breakdown_kjg_reconciles_to_source():
    # 2026-08-18 추가(56차 "다른 견적 세부 분석" 4호) — 강정구(군산 딸기 와이드
    # 연동 3,696㎡, 서진비에스 2022-04 — 표본 중 최고(最古), 물가 시점 주의).
    # 부분 범위 시공 견적(골조·천창개폐·피복만): 0인 카테고리는 설비 부재가 아니라
    # 견적 범위 밖. 표본 최초의 unclassified 0.
    assert 223_202_937 + 67_810_080 + 5_908_267 == 296_921_284  # 원가계산서 3항목 원단위 재현
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["강정구"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["강정구"])
    assert cb.total == 296_921_284
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["강정구"] == 0
    assert sum(cb.items.values()) == 296_921_284
    # 공종→카테고리 합성 앵커(집계표 원문 소계 — 명시 개폐 명칭 라인 2건 분리 반영)
    assert cb.items["greenhouse_structure"] == 11_451_200 + (101_638_392 - 347_061) + 81_198_324 + 28_177_124
    # 명시 개폐 명칭 라인 분리(7회차 F5 일관 적용): 비닐 공종의 측면개폐모터·가이드로라
    # + 파이프 공종의 1.2중개폐파이프(측면 개폐 권취 축 계열 추정 — 규칙 일관 적용)
    assert 480_000 + 180_000 == 660_000
    assert 28_177_124 + 660_000 == 28_837_124                    # 비닐 공종 분리 검산
    assert (101_638_392 - 347_061) + 347_061 == 101_638_392      # 파이프 공종 분리 검산
    assert cb.items["auto_opening_system"] == 73_796_244 + 660_000 + 347_061
    for k in ("hvac", "irrigation_fertigation", "ict_control", "electrical"):
        assert cb.items[k] == 0                                  # 부분 범위 견적(범위 밖)
    # 도급 체인 + 환급 차감 전·후 값(p2 원가계산서 머리 — 한글=차감 전 공사금액과 일치,
    # 괄호 숫자=차감 후 총공사금액과 일치. 병기 의도 여부는 [추정] — 7회차 F3)
    assert 323_584_540 + 6_471_690 + 5_295_649 - 10_200_000 == 325_151_879  # 표기 325,151,878은 1원 갭
    assert (325_151_878 + 32_515_188 + 10_200_000) // 1000 * 1000 == 367_867_000  # 공사금액(한글 일치값)
    assert 130_507_454 // 10 == 13_050_745                       # 부가세환급예정액
    assert (367_867_000 - 13_050_745) // 1000 * 1000 == 354_816_000  # 총공사금액(괄호 숫자 일치값)
    # 원문 갭 ③(7회차 F4): 영세율 표시된 측면개폐모터 480,000이 영세율 총액에 미포함
    assert 6_400_000 + 3_800_000 == 10_200_000


def test_capex_major_breakdown_oks_reconciles_to_source():
    # 2026-08-18 추가(57차 "다른 견적 세부 분석" 5호) — 오기수(군산, 서진비에스
    # 2023-08 — 강정구와 동일 업체 시계열). 설비 전용 부분 범위 견적(골조·피복
    # 전무 — 강정구와 상보 쌍): 0 카테고리는 견적 범위 밖.
    assert 164_863_706 + 31_834_400 + 2_876_832 == 199_574_938  # 원가계산서 3항목 원단위 재현
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["오기수"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["오기수"])
    assert cb.total == 199_574_938
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["오기수"] == 39_821_638
    assert sum(cb.items.values()) + cb.unclassified == 199_574_938
    # 공종→카테고리 합성 앵커(집계표 원문 소계)
    assert cb.items["auto_opening_system"] == 5_310_000 + 63_684_894 + 2_817_269
    assert cb.items["irrigation_fertigation"] == 35_567_476 + 12_373_661
    assert cb.items["ict_control"] == 40_000_000   # PRIVA 계열 2번째 관측(프라바 오피스) — 표본 2위
    for k in ("greenhouse_structure", "hvac", "electrical"):
        assert cb.items[k] == 0                    # 설비 전용 부분 범위(범위 밖)
    # 도급 체인(원단위): 순공사원가+관리비 5%+이윤 8%−영세율=공급가액, +부가세+영세율=총액
    assert 164_863_706 + 35_718_196 + 13_358_142 == 213_940_044
    assert 213_940_044 + 10_697_002 + 4_781_867 - 9_170_000 == 220_248_913
    assert 220_248_913 + 22_024_891 + 9_170_000 == 251_443_804  # 한글 원단위 표기와 일치(환급 차감 전)
    # 원문 결함 관찰 고정(57차): p4 환급표 계가 첫 행 값 그대로 — 관리동커텐 합산 누락
    assert 23_974_813 + 1_648_320 == 25_623_133   # 실합(표기 계 23,974,813과 Δ1,648,320)
    assert 23_974_813 // 10 == 2_397_481          # 환급예정은 누락 계 기준(합산 시 2,562,313)


def test_capex_major_breakdown_bgj_reconciles_to_source():
    # 2026-08-19 추가(59차 "다른 견적 세부 분석" 7호) — 백가은·조윤정 통합 표본
    # (논산, 그린팜스글로벌 2026-05 — 쌍 견적이 표지 3줄 외 22p 문자 단위 동일이라
    # 중복 왜곡을 피해 1건 편입). 딸기 75각 3,600㎡, 난방 계열 최다 구성 표본.
    assert 286_680_383 + 100_648_000 + 11_300_000 == 398_628_383  # 원가계산서 3항목 원단위 재현
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["백가은·조윤정"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["백가은·조윤정"])
    assert cb.total == 398_628_383
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["백가은·조윤정"] == 63_336_900
    assert sum(cb.items.values()) + cb.unclassified == 398_628_383
    # 하위 공종 합 재현(집계표 상위 행)
    assert 13_712_000 + 71_565_642 + 16_209_400 + 71_615_481 == 173_102_523  # 하우스 하위 4공종
    assert 16_500_000 + 8_010_500 + 1_149_000 + 5_580_000 + 47_356_900 + 19_035_760 == 97_632_160  # 양액 하위 6공종
    # 개폐 구동 세트 분리 3곳(9회차 F4로 규칙 정밀화 — 전용 배선 포함: 피복·외몽골
    # 공종의 전력 부하가 개폐 세트뿐이라 전선 550,000·440,000은 세트 전용 배선)
    assert 616_000 + 240_000 + 1_080_000 + 550_000 == 2_486_000  # 피복 내 개폐기·가이드로라·콘트롤박스·전선
    assert 73_600 + 385_000 + 600_000 + 440_000 == 1_498_600     # 외몽골 내 개폐파이프·개폐기·콘트롤박스·전선
    assert cb.items["greenhouse_structure"] == 13_712_000 + (71_565_642 - 432_000) + 16_209_400 + (71_615_481 - 2_486_000) + (21_800_400 - 1_498_600)
    assert cb.items["auto_opening_system"] == 58_949_000 + 432_000 + 2_486_000 + 1_498_600
    assert cb.items["hvac"] == 12_080_000 + 17_200_000 + 7_464_300  # 환기+난방+근권배관(지온관 — 온수 배관)
    assert cb.items["irrigation_fertigation"] == 16_500_000 + 8_010_500 + 1_149_000 + 19_035_760
    assert cb.items["ict_control"] == cb.items["electrical"] == 0
    assert 5_580_000 + 47_356_900 + 10_400_000 == 63_336_900     # 미분류 구성(바닥제+베드+장비대)
    # 도급 체인 + 원문 갭 고정: 합계 1원·절사 라벨 불일치(십만단위 표기, 실제 백만 미만 절사)
    assert 411_245_695 + 12_748_617 == 423_994_312               # 표기 423,994,311은 1원 갭
    assert 423_994_311 + 42_399_431 == 466_393_742
    assert 466_393_742 // 1_000_000 * 1_000_000 == 466_000_000   # 실절사(백만 미만) — 십만단위면 466,300,000
    assert 195_448_500 + 203_179_883 == 398_628_383              # 환급/비환급 총괄 정합


def test_capex_major_breakdown_pgh_reconciles_to_source():
    # 2026-08-19 추가(60차 "다른 견적 세부 분석" 8호) — 박규현(충남, 표지가 스스로
    # '벤로형+연질필름' 명시, 표본 최초 오이 작목 3,676.8㎡). ⚠️ 경비 열이 없는
    # 표본: known_total은 재+노 2요소 레벨(원가계산서 기계경비 '직접산출' 공란).
    assert 370_315_435 + 164_580_818 == 534_896_253              # 원가계산서 재+노 원단위 재현
    assert 264_422_873 + 145_644_218 == 410_067_091              # a.온실 소계
    assert 105_892_562 + 18_936_600 == 124_829_162               # b.양액 소계
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["박규현"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["박규현"])
    assert cb.total == 534_896_253
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["박규현"] == 77_758_030
    assert sum(cb.items.values()) + cb.unclassified == 534_896_253
    assert cb.items["greenhouse_structure"] == 18_299_200 + 75_849_039 + 89_477_387 + 49_680_698
    # "전기 장치 공사"의 명칭≠실체 3분할(제어기→auto·실물 팬→hvac·잔여→electrical)
    assert 24_000_000 + 3_090_400 + 2_832_665 == 29_923_065      # 분리 검산 = 공종 소계
    assert 800_000 + 2_280_000 + 10_400 == 3_090_400             # 팬 세트(배기휀 4·유동휀 24·패드)
    assert cb.items["auto_opening_system"] == 14_327_963 + 71_129_815 + 61_379_924 + 24_000_000
    assert cb.items["hvac"] == 3_090_400
    assert cb.items["electrical"] == 2_832_665
    assert cb.items["irrigation_fertigation"] == 26_517_342 + 4_058_080 + 16_495_710
    assert cb.items["ict_control"] == 0
    # 도급 체인 + 환급 3분류·5% 산식 관찰 고정
    assert 313_542_997 + 206_856_006 + 14_497_250 == 534_896_253  # 환급/비환급/영세 총괄
    assert (575_584_792 - 14_497_250) // 10 == 56_108_754         # 부가세 = (공급−영세)×10%
    # 합계 = 공급가액(영세 포함)+부가세 — 영세율 행은 부가세 산정에서만 차감되는 내역
    assert 575_584_792 + 56_108_754 == 631_693_546                # 합계(한글 원단위 일치값)
    assert round(313_542_997 * 0.05) == 15_677_150                # 환급 "×5%" 산식 재현([확인요망])
    assert 631_693_546 - 15_677_150 == 616_016_396                # 부가세 공제 후


def test_capex_major_breakdown_gch_reconciles_to_source():
    # 2026-08-19 추가(61차 "다른 견적 세부 분석" 9호) — 구창회(당진, "시공견적서
    # .pdf"의 실체는 한일그린텍의 착공내역서 — 이영준 3,202㎡와 동일 업체 2호 현장,
    # 3,714㎡ MS-8 5연동). 매핑은 한일 1호 선례 그대로.
    assert 250_002_799 + 112_939_613 + 15_922_187 == 378_864_599  # 원가계산서 3항목 원단위 재현
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["구창회"],
                                  known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["구창회"])
    assert cb.total == 378_864_599
    assert cb.unclassified == e.CAPEX_MAJOR_UNCLASSIFIED["구창회"] == 51_387_099
    assert sum(cb.items.values()) + cb.unclassified == 378_864_599
    assert cb.items["greenhouse_structure"] == 16_961_447 + 177_124_132 + 30_662_293
    assert cb.items["auto_opening_system"] == 62_626_931 + 21_866_698
    assert cb.items["irrigation_fertigation"] == 18_235_999
    for k in ("hvac", "ict_control", "electrical"):
        assert cb.items[k] == 0     # 환풍기는 환급 재투자 블록(분모 밖) — 한일 1호와 동일 구조
    # 도급 체인 + 원문 갭 ①(간접노무비 증발) 고정: 관리비·이윤은 간노 포함 기준으로
    # 재현되는데, 공급가액 소계는 간노 제외 빌드업과 일치 — Δ16,940,941 [확인요망]
    assert 250_002_799 + 129_880_554 + 48_828_453 == 428_711_806        # 계(간노 포함)
    assert round(428_711_806 * 0.08) == 34_296_944                       # 일반관리비 8%(간노 포함 기준)
    assert (129_880_554 + 48_828_453 + 34_296_944) * 15 // 100 == 31_950_892  # 이윤 15%(간노 포함 기준, 원미만 절사)
    assert 428_711_806 + 34_296_944 + 31_950_892 == 494_959_642          # 간노 포함 빌드업
    assert (428_711_806 - 16_940_941) + 34_296_944 + 31_950_892 == 478_018_701  # 간노 제외=공급 소계(표기 …700은 1원 갭)
    assert 478_018_700 + 45_823_198 == 523_841_898
    assert (523_841_898 + 23_738_525) // 1000 * 1000 == 547_580_000      # 총공사비(한글 일치값)


def test_capex_major_known_totals_single_source_sync():
    # 2026-08-18 53차(레드팀 4회차 F8 구조 개선) — known_total은 엔진 상수
    # CAPEX_MAJOR_KNOWN_TOTALS가 단일 출처다(build_site major_totals가 직접 읽음 —
    # 종전 이중 하드코딩은 한쪽만 드리프트해도 테스트가 못 잡았다). 값 자체는 위
    # 케이스별 reconcile 테스트의 원문 리터럴(cb.total == N)이 고정하고, 여기서는
    # 표본 3상수의 키 집합 동기를 고정한다(새 표본을 한쪽에만 추가하면 실패).
    assert (set(e.CAPEX_MAJOR_KNOWN_TOTALS)
            == set(e.CAPEX_MAJOR_CASE_CHUNKS)
            == set(e.CAPEX_MAJOR_UNCLASSIFIED))


def test_capex_major_breakdown_unmapped_categories_default_zero():
    # 근거 없는 7개(부대시설·기자재구매·설계감리비·부지조성비·예비비·부지매입비, 8번 등)는 0
    cb = e.capex_major_breakdown(e.CAPEX_MAJOR_CASE_CHUNKS["우민재"],
                                 known_total=e.CAPEX_MAJOR_KNOWN_TOTALS["우민재"])
    for k in ("auxiliary_facility", "thermal_storage_insulation", "equipment_procurement",
              "design_supervision_fee", "site_preparation", "contingency", "land_acquisition"):
        assert cb.items[k] == 0.0


def test_capex_major_breakdown_rejects_overclassification():
    import pytest
    with pytest.raises(ValueError):
        e.capex_major_breakdown({"greenhouse_structure": 200}, known_total=100)


def test_capex_major_categories_count_and_keys():
    assert len(e.CAPEX_MAJOR_CATEGORIES) == 13
    keys = [k for k, _, _ in e.CAPEX_MAJOR_CATEGORIES]
    assert keys[-1] == "land_acquisition"  # 13번 부지매입비가 마지막


# ── 12. 부지매입비는 감가상각에서 제외 (2026-07-16) ──────────────
def test_finance_land_cost_excluded_from_depreciation():
    f_no_land = e.finance(revenue=500_000_000, opex=200_000_000, capex=1_000_000_000,
                          useful_life=10, land_cost=0.0)
    f_with_land = e.finance(revenue=500_000_000, opex=200_000_000, capex=1_000_000_000,
                            useful_life=10, land_cost=200_000_000)
    assert abs(f_no_land.depreciation - 100_000_000) < 1e-6      # 1,000,000,000/10
    assert abs(f_with_land.depreciation - 80_000_000) < 1e-6     # (1,000,000,000-200,000,000)/10
    assert f_with_land.depreciation < f_no_land.depreciation
    # 토지비를 감가상각에서 뺀 만큼 영업이익이 늘어나 ROI가 개선되어야
    assert f_with_land.roi > f_no_land.roi


def test_finance_default_land_cost_zero_preserves_regression():
    # land_cost 기본값 0 — 기존 원채원 회귀값(ROI 14.2%)에 영향 없어야
    f = e.finance(revenue=332_640_000, opex=186_420_000, capex=702_030_000, subsidy_rate=0.5)
    assert abs(f.roi - 0.142) < 0.001
    assert abs(f.payback_years - 7.1) < 0.05


# ── 13. RFQ 사양서 생성 + 견적서 정합성 검증 (2026-07-18) ─────────
def _rfq_uminjae():
    return e.generate_rfq_package(
        region_snow_cm=30, region_wind_ms=35, area_m2=2323, cover=e.Cover.FILM,
        form="연동", t_target=10, t_min=-7.8, fr=0.7, surface_area_m2=3362)


def _rfq_choihyeokjin():
    # 최혁진은 cases/*.json이 없어(원가계산서만 확보) 설계입력(적설·풍속·목표온도)이
    # 이 저장소엔 없다 — 원채원 baseline 설계조건([추정])을 그대로 써서 RFQ 생성
    # 메커니즘만 확인한다(면적·피복·CAPEX 실측값만 최혁진 고유값).
    return e.generate_rfq_package(
        region_snow_cm=30, region_wind_ms=35, area_m2=3459, cover=e.Cover.FLUORINE,
        form="연동", t_target=10, t_min=-7.8, fr=0.7)


def test_generate_rfq_package_rejects_understrength_form():
    import pytest
    with pytest.raises(ValueError):
        e.generate_rfq_package(region_snow_cm=60, region_wind_ms=45, area_m2=2323,
                               cover=e.Cover.FILM, form="연동", t_target=10, t_min=-7.8, fr=0.7)


def test_reconcile_quote_uminjae_self_consistency():
    # 우민재의 실측 CAPEX_MAJOR_CASE_CHUNKS를 '견적서'로 대입 — 같은 케이스의
    # 입력으로 만든 RFQ 사양서와 자체정합해야 한다(근거 없는 새 데이터 없음).
    rfq = _rfq_uminjae()
    result = e.reconcile_quote(
        rfq, e.CAPEX_MAJOR_CASE_CHUNKS["우민재"],
        quote_direct_cost_total=456_158_140, quote_total_with_overhead=557_152_000,
        quote_area_m2=2323)
    by_name = {c.name: c for c in result.checks}
    assert by_name["필수 공종 완전성"].status == "일치"
    assert by_name["면적 정합"].status == "일치"
    assert by_name["규격코드 정합"].status == "확인요망"   # 실제 발주 규격코드 근거 없음 — 지어내지 않음
    assert by_name["총액 단가 밴드"].status in ("정상", "경계")
    assert result.overall_status.startswith("부분정합")     # 규격코드 확인요망 1건만 남음
    assert result.match_score_pct >= 85.0


def test_reconcile_quote_choihyeokjin_self_consistency():
    rfq = _rfq_choihyeokjin()
    result = e.reconcile_quote(
        rfq, e.CAPEX_MAJOR_CASE_CHUNKS["최혁진"],
        quote_direct_cost_total=694_575_784, quote_total_with_overhead=930_000_000,
        quote_area_m2=3459)
    by_name = {c.name: c for c in result.checks}
    assert by_name["필수 공종 완전성"].status == "일치"
    assert by_name["면적 정합"].status == "일치"
    assert by_name["총액 단가 밴드"].status in ("정상", "경계")


def test_reconcile_quote_flags_missing_required_category():
    rfq = _rfq_uminjae()
    quote = dict(e.CAPEX_MAJOR_CASE_CHUNKS["우민재"])
    dropped = quote["hvac"]
    quote["hvac"] = 0.0
    result = e.reconcile_quote(
        rfq, quote, quote_direct_cost_total=456_158_140 - dropped,
        quote_total_with_overhead=557_152_000, quote_area_m2=2323)
    by_name = {c.name: c for c in result.checks}
    assert by_name["필수 공종 완전성"].status == "불일치"
    assert "hvac" in by_name["필수 공종 완전성"].detail
    assert result.overall_status.startswith("불일치")


def test_compare_quotes_handles_empty_list():
    rfq = _rfq_uminjae()
    comparison = e.compare_quotes(rfq, [])
    assert comparison.rows == []
    assert comparison.lowest_cost_vendor is None
    assert comparison.highest_match_score_vendor is None


def test_compare_quotes_does_not_let_lowest_cost_win_over_defects():
    # 최저가 업체가 필수 공종을 누락했다면 '최저가'와 '최고점수'가 서로 다른
    # 업체를 가리켜야 한다 — compare_quotes()가 자동으로 승자를 정하지 않는다는 증거
    rfq = _rfq_uminjae()
    vendor_real = e.VendorQuote("업체A(실측)", e.CAPEX_MAJOR_CASE_CHUNKS["우민재"],
                                456_158_140, 557_152_000, area_m2=2323)
    quote_defective = dict(e.CAPEX_MAJOR_CASE_CHUNKS["우민재"])
    dropped = quote_defective["hvac"]
    quote_defective["hvac"] = 0.0
    vendor_cheap = e.VendorQuote("업체B(냉난방누락·저가)", quote_defective,
                                 456_158_140 - dropped, 480_000_000, area_m2=2323)

    comparison = e.compare_quotes(rfq, [vendor_real, vendor_cheap])

    assert len(comparison.rows) == 2
    assert comparison.reconciliations["업체B(냉난방누락·저가)"].overall_status.startswith("불일치")
    assert comparison.lowest_cost_vendor == "업체B(냉난방누락·저가)"
    assert comparison.highest_match_score_vendor == "업체A(실측)"
    assert comparison.lowest_cost_vendor != comparison.highest_match_score_vendor


def test_pumsem_labor_days_known_item():
    r = e.pumsem_labor_days("철골공사", "외부기둥", 10)
    assert r["category"] == "철골공사"
    assert r["labor_days_by_trade"] == {"철골공": 1.8, "특별인부": 0.6}
    assert r["total_labor_days"] == 2.4


def test_pumsem_labor_days_unmapped_item_returns_none():
    # 비닐온실 공종(제3절)은 아직 미확보(Phase G 다음 라운드)
    assert e.pumsem_labor_days("비닐철골공사", "지붕서까래", 5) is None


def test_pumsem_labor_days_wrong_category_for_real_item_returns_none():
    # "외부기둥"은 철골공사에만 있다 — 엉뚱한 공종을 붙이면 이름이 맞아도 None
    assert e.pumsem_labor_days("알루미늄공사", "외부기둥", 5) is None


def test_pumsem_labor_days_disambiguates_same_name_across_categories():
    # "모터설치대"는 천창개폐장치공사·수평스크린공사 두 공종에 같은 이름,
    # 다른 값으로 존재한다 — 공종을 명시해야 올바른 값이 나온다는 걸 증명
    ceiling = e.pumsem_labor_days("천창개폐장치공사", "모터설치대", 1)
    screen = e.pumsem_labor_days("수평스크린공사", "모터설치대", 1)
    assert ceiling["total_labor_days"] != screen["total_labor_days"]
    assert ceiling["labor_days_by_trade"] == {"철골공": 0.31, "조력공": 0.9}
    assert screen["labor_days_by_trade"] == {"철골공": 0.6, "조력공": 0.3}


def test_pumsem_project_labor_summary_aggregates_and_flags_unmatched():
    result = e.pumsem_project_labor_summary({
        ("철골공사", "외부기둥"): 10,
        ("철골공사", "내부기둥"): 5,
        ("비닐철골공사", "지붕서까래"): 3,
    })
    assert result["unmatched"] == [("비닐철골공사", "지붕서까래")]
    assert result["totals_by_trade"] == {"철골공": 2.6, "특별인부": 0.9}
    assert result["total_labor_days"] == 3.5


def test_pumsem_items_cover_glass_and_vinyl_greenhouse():
    # 제7장 품셈 산정 파트 전체(유리 7공종57종 + 비닐 2공종7종) = 64종
    assert len(e.PUMSEM_ITEMS) == 64
    categories = {it.category for it in e.PUMSEM_ITEMS}
    assert "철골공사(비닐·파이프자재)" in categories
    assert "온실피복공사(비닐)" in categories


def test_pumsem_labor_days_vinyl_greenhouse_item():
    r = e.pumsem_labor_days("온실피복공사(비닐)", "농업용PO필름(천창및지붕)", 100)
    assert r["labor_days_by_trade"] == {"철골공": 1.0, "특별인부": 0.4, "보통인부": 0.2}
    assert r["total_labor_days"] == 1.6


# ── 12. 기자재DB (2026-07-19, Phase H) ──────────────────────
def test_equipment_lookup_finds_known_device():
    r = e.equipment_lookup("환경제어기")
    assert len(r) == 85
    assert all(row["표준 장치명"] == "환경제어기" for row in r)


def test_equipment_lookup_unknown_device_returns_empty():
    assert e.equipment_lookup("존재하지않는장치명") == []


def test_equipment_component_prices_parses_won_and_sums():
    r = e.equipment_component_prices("HS-8000")
    assert len(r["필수구성품"]) == 2
    assert r["필수구성품"][0]["표준가격_원"] == 9_500_000
    assert r["필수구성품_합계_원"] == 10_500_000


def test_equipment_component_prices_unknown_model_returns_empty_not_zero_fabricated():
    r = e.equipment_component_prices("존재하지않는모델")
    assert r["필수구성품"] == [] and r["선택구성품"] == []
    assert r["필수구성품_합계_원"] == 0


def test_construction_company_list_filters_by_region():
    r = e.construction_company_list("충청남도")
    assert r == [{"상호": "(주)그린플러스", "소재지": "충청남도 예산군 응봉면 응봉로 50-42",
                  "연락처": "041-332-6421"}]


def test_construction_company_list_no_region_returns_all():
    assert len(e.construction_company_list()) == 84


# ── 13. 보조사업 체크리스트 (2026-07-19, Phase I) ────────────
def test_subsidy_application_checklist_has_five_steps_all_pending():
    checklist = e.subsidy_application_checklist()
    assert len(checklist) == 5
    assert [c["단계"] for c in checklist] == [1, 2, 3, 4, 5]
    assert all(c["상태"] == "확인요망" for c in checklist)


def test_subsidy_application_checklist_no_rates_fabricated():
    # 보조율(%) 수치는 공모 회차마다 바뀌므로 체크리스트 어디에도 없어야 한다
    checklist = e.subsidy_application_checklist()
    for item in checklist:
        assert "%" not in item["설명"]


def test_reconcile_quote_flags_band_deviation():
    rfq = _rfq_uminjae()
    result = e.reconcile_quote(
        rfq, e.CAPEX_MAJOR_CASE_CHUNKS["우민재"],
        quote_direct_cost_total=456_158_140,
        quote_total_with_overhead=100_000_000,   # 명백한 과소견적(43,047원/㎡)
        quote_area_m2=2323)
    by_name = {c.name: c for c in result.checks}
    assert by_name["총액 단가 밴드"].status == "경고(밴드이탈)"
    assert result.overall_status.startswith("불일치")


# ── 설계 대안 비교 (75차) ─────────────────────────────────────
# 입지: 적설 55cm·풍속 35m/s 기준 3대안
#   12-연동-01(55/40)      → 충족 + A-2 평단가 등재
#   07-연동-01(53/40)      → 적설 미달
#   07-연동(민)-01(60/35)  → 충족이나 A-2 평단가 미등재
# ⚠️ 19회차 레드팀 F1: 대안마다 면적·온도·피복·커튼을 **전부 다르게** 준다.
#   초판 픽스처는 3대안이 난방 입력을 공유해 행-옵션 매핑이 뒤틀려도 테스트가
#   통과했다(뮤테이션으로 실증). 또 area_py와 floor_area_m2를 독립 상수로 줘
#   같은 대안 안에서 1,488㎡와 2,016㎡가 섞여 있었다 — 여기서는 바닥면적
#   하나에서 평을 파생시켜 어긋날 수 없게 묶는다(generate_rfq_package 관례).
def _design_opts():
    def opt(label, spec, cover, curtain, floor_m2, surface_m2, t_target, t_min):
        return e.DesignOption(label=label, spec_name=spec, cover=cover,
                              curtain=curtain, area_py=e.m2_to_py(floor_m2),
                              surface_area_m2=surface_m2, t_target=t_target,
                              t_min=t_min, floor_area_m2=floor_m2)
    return [
        opt("A안", "12-연동-01", "필름", "다겹보온", 2016.0, 6027.47, 7.0, -21.7),
        opt("B안", "07-연동-01", "유리", "2중커튼", 1050.0, 3200.0, 12.0, -15.0),
        opt("C안", "07-연동(민)-01", "필름", "PO단일", 1500.0, 4400.0, 9.0, -10.0),
    ]


def test_compare_design_options_preserves_input_order():
    r = e.compare_design_options(55, 35, _design_opts())
    assert [row.label for row in r.rows] == ["A안", "B안", "C안"]
    assert (r.region_snow_cm, r.region_wind_ms) == (55, 35)


def test_compare_design_options_keeps_understrength_option_visible():
    # 설계강도 미달 대안을 조용히 버리지 않는다 — 행에 남고 spec_ok=False + note
    r = e.compare_design_options(55, 35, _design_opts())
    by = {row.label: row for row in r.rows}
    assert by["A안"].spec_ok is True
    assert by["B안"].spec_ok is False, "07-연동-01(적설 53)은 적설 55 요구에 미달"
    assert by["C안"].spec_ok is True
    assert (by["B안"].snow_cm, by["B안"].wind_ms) == (53, 40)
    assert any("B안" in n and "미달" in n for n in r.notes)


def test_compare_design_options_unlisted_price_is_none_not_zero():
    # 평단가 미등재 규격에 0을 날조하지 않는다(1절 "근거 없는 값 금지")
    r = e.compare_design_options(55, 35, _design_opts())
    by = {row.label: row for row in r.rows}
    assert by["C안"].greenhouse_total_won is None
    assert by["A안"].greenhouse_total_won is not None
    assert any("C안" in n and "평단가" in n for n in r.notes)
    # 골조 단독은 면적만 있으면 항상 나온다
    assert by["C안"].structure_only_won == e.structure_only_estimate(e.m2_to_py(1500.0))


def test_compare_design_options_is_not_a_second_calculator():
    # 난방·비용 수치가 원 함수 직접 호출과 원단위까지 일치해야 한다
    # (병렬 계산기 금지 — 이 함수는 조립만 한다).
    # 19회차 F1 반영: 대안별 입력이 전부 달라 행-옵션 오배선도 여기서 잡힌다.
    opts = _design_opts()
    r = e.compare_design_options(55, 35, opts)
    seen = set()
    for o, row in zip(opts, r.rows):
        h = e.heating_load(surface_area_m2=o.surface_area_m2, cover=o.cover,
                           t_target=o.t_target, t_min=o.t_min,
                           curtain=o.curtain, floor_area_m2=o.floor_area_m2)
        assert row.max_load_kcal_h == h.max_load_kcal_h
        assert row.load_per_m2 == h.load_per_m2
        assert row.heater_capacity_kcal_h == h.heater_capacity_kcal_h
        assert row.heating_verify == e.verify_heating_vs_actual(h.load_per_m2, o.cover)
        assert row.greenhouse_total_won == e.greenhouse_total_estimate(o.spec_name, o.area_py)
        assert row.structure_only_won == e.structure_only_estimate(o.area_py)
        seen.add(row.max_load_kcal_h)
    # 세 대안의 난방부하가 서로 달라야 위 대조가 의미를 갖는다(픽스처 자기검사)
    assert len(seen) == 3, "대안별 입력이 구분되지 않으면 오배선을 잡지 못한다"


def test_compare_design_options_exposes_no_ranking_or_recommendation():
    # compare_quotes와 달리 참고 순위 필드조차 두지 않는다(대안 선정=판단성)
    r = e.compare_design_options(55, 35, _design_opts())
    fields = set(r.__dataclass_fields__) | set(r.rows[0].__dataclass_fields__)
    banned_kw = ("lowest", "highest", "best", "recommend", "rank",
                 "추천", "순위", "최적", "최저", "1위", "우수")
    bad_fields = [f for f in fields if any(k in f.lower() for k in banned_kw)]
    assert bad_fields == [], f"판정·순위 필드 발견: {bad_fields}"
    # 19회차 F7: 필드명뿐 아니라 사용자가 읽는 notes 문구도 본다
    bad_notes = [n for n in r.notes if any(k in n.lower() for k in banned_kw)]
    assert bad_notes == [], f"notes에 판정 어휘 유입: {bad_notes}"


def test_compare_design_options_unlisted_spec_name_yields_none_spec_ok():
    # 19회차 F11: spec_ok 3분기 중 None(SPEC_TABLE 미등재) 경로도 고정한다.
    # 미등재는 "미달"과 다르다 — 판정 불가이지 탈락이 아니다.
    o = _design_opts()[0]
    o.spec_name = "99-없는규격-99"
    r = e.compare_design_options(55, 35, [o])
    assert r.rows[0].spec_ok is None
    assert r.rows[0].snow_cm is None and r.rows[0].wind_ms is None
    assert any("미등재" in n and "판정할 수 없다" in n for n in r.notes)
    assert not any("미달" in n for n in r.notes), "미등재를 미달로 표기하면 안 된다"


def test_compare_design_options_membership_uses_star_crop():
    # 19회차 F6: crop="*" 선택을 고정한다. 기본값(None)이면 작물특화형은
    # 설계강도를 충족해도 후보 집합에서 빠져 spec_ok=False로 오검출된다.
    # 규격명을 하드코딩하지 않고 "작물특화형이면서 55/35를 충족하는 규격"을
    # 표에서 직접 고른다 — 이름이 바뀌어도 검사 의도가 살아 있다.
    spec = next(s for s in e.SPEC_TABLE
                if s.crop and s.snow_cm >= 55 and s.wind_ms >= 35)
    # 이 규격이 기본값(crop=None) 후보에서는 실제로 빠지는지부터 확인한다
    # (빠지지 않으면 이 테스트는 아무것도 증명하지 못한다)
    assert spec.name not in {s.name for s in e.select_specs(55, 35)["candidates"]}
    o = _design_opts()[0]
    o.spec_name = spec.name
    r = e.compare_design_options(55, 35, [o])
    assert r.rows[0].spec_ok is True, \
        "작물특화형이라는 이유로 강도 충족 규격을 미달 처리하면 안 된다"


def test_compare_design_options_not_wired_into_render_paths():
    # 19회차 F4 + 74차 관례(test_cluster_constants_registry_sync_and_unreached):
    # "렌더 경로 미연결"은 주석이 아니라 코드로 확인돼야 한다(12회차 F2).
    import os
    repo = os.path.dirname(os.path.abspath(__file__))
    for fname in ("build_site.py", "webapp.py", "render_report.py", "app.py",
                  "run_report.py", "render_chuncheon.py", "cases.py"):
        path = os.path.join(repo, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            assert "compare_design_options" not in f.read(), (
                f"{fname}이 compare_design_options를 쓰기 시작했다 — 설계 대안 "
                f"비교가 산출물에 도달하면 cover 무검증 폴백(19회차 F2)·면적 "
                f"가드(F8·F9)를 먼저 처리하고 이 테스트를 함께 갱신할 것")


def test_compare_design_options_empty_list():
    r = e.compare_design_options(55, 35, [])
    assert r.rows == [] and r.notes == []


# ── 난방 계수 이견의 사실관계 고정 (76차) ────────────────────
# 근거_난방계수_이견_20260913.md의 결론("현행값 유지")은 두 사실에 기대고 있다:
#   ①2중커튼 계열 키가 live 산출물에서 쓰이지 않는다(바꿔도 안 움직인다)
#   ②케이스의 fr=0.7을 노출비율로 읽어야 실측 대조를 통과한다
# 둘 중 하나가 깨지면 이견을 다시 열어야 하므로 여기서 지킨다.
def test_fr_table_rejects_additive_composition_value():
    # 19회차 F3: E파일의 0.85는 0.35+0.5의 단순 가산이었다. 직렬/독립 합성은
    # 0.675이고 농사로 직렬 열저항은 0.700 — 68차가 채택한 값이 후자다.
    # 가산값 0.85가 표에 되돌아오면 실패한다(68차 결정의 회귀 방어).
    assert e.FR_TABLE["PO단일"] == 0.35
    assert e.FR_TABLE["다겹보온"] == 0.5
    assert e.FR_TABLE["이중커튼"] == 0.70
    assert e.FR_TABLE["2중커튼"] == 0.70
    assert 0.85 not in e.FR_TABLE.values(), (
        "0.85는 절감률 단순 가산(0.35+0.5) 값이다 — 되돌리려면 "
        "근거_난방계수_이견_20260913.md의 3모델 비교부터 갱신할 것")
    # 가산이 아니라 독립 곱으로 합성하면 현행값과 근사한다(모델 동질성은 [추정])
    assert abs((1 - (1 - 0.35) * (1 - 0.5)) - 0.675) < 1e-12


def test_double_curtain_keys_have_no_live_usage():
    """76차 영향범위 실측: 2중커튼 계열이 산출물 입력에 쓰이지 않음을 고정한다.
    쓰이기 시작하면 0.70 값의 근거 등급(부분실측·4키 중 2키)을 먼저 올려야 하므로
    여기서 알린다(74차 도달성 가드와 같은 관례)."""
    import glob
    import json
    import os
    repo = os.path.dirname(os.path.abspath(__file__))
    used = []
    for pat in ("견적비교_*.json", os.path.join("cases", "*.json")):
        for path in glob.glob(os.path.join(repo, pat)):
            if os.path.getsize(path) == 0:      # gyeongbuk_ddalgi tombstone
                continue
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            for blob in (d, d.get("input") or {}, d.get("rfq_input") or {}):
                if isinstance(blob, dict) and blob.get("curtain") in ("이중커튼", "2중커튼"):
                    used.append(os.path.basename(path))
    assert used == [], (
        f"{used}가 2중커튼 계열을 쓰기 시작했다 — FR_TABLE 0.70은 4키 중 2키만 "
        f"공공 출처(status 부분실측)이고 이견이 열려 있다. "
        f"근거_난방계수_이견_20260913.md를 먼저 갱신할 것")


def test_case_fr_is_exposure_ratio_not_reduction_rate():
    """76차 3-2: 케이스의 fr=0.7은 '노출비율'이어야 실측 대조를 통과한다.
    열절감률로 읽으면(노출 0.3) chuncheon·wonchaewon이 '재확인'으로 떨어진다.
    fr에 provenance가 없어 문서상 확정이 아니므로(이견 문서 5절) 이 방증을
    코드로 남긴다 — P1-9가 시그니처로 막은 방향반전이 데이터 쪽에서 새는지 본다."""
    import glob
    import json
    import os
    repo = os.path.dirname(os.path.abspath(__file__))
    checked = 0
    for path in sorted(glob.glob(os.path.join(repo, "cases", "*.json"))):
        if os.path.getsize(path) == 0:
            continue
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        i = d.get("input", d)
        if not (i.get("surface_area_m2") and i.get("fr")):
            continue                            # 부분 케이스
        h = e.heating_load(i["surface_area_m2"], i["cover"], i["t_target"],
                           i["t_min"], fr=i["fr"], floor_area_m2=i["area_m2"])
        v = e.verify_heating_vs_actual(h.load_per_m2, i["cover"])
        assert v["status"] == "정상", (
            f"{os.path.basename(path)}: fr={i['fr']}를 노출비율로 읽었는데 "
            f"실측 대조가 {v['status']}(ratio {v['ratio']}) — fr의 성격을 "
            f"근거_난방계수_이견_20260913.md 3-2와 함께 재검토할 것")
        checked += 1
    assert checked == 3, f"설계 파라미터를 가진 케이스가 3건이어야 한다(실측 {checked})"


# ── 최대난방부하 식의 원출처 자구 고정 (77차) ────────────────
# 김평화 p.49: "난방부하 = 하우스표면적 * 난방부하계수 * (내부설정온도 - 외부기온)
#               * (1 - 피복 열절감률)"
# 이 자구가 확정하는 것은 **fr = (1-열절감률) = 노출비율**이라는 정의 하나다.
# ⚠️ 77차 중반에 "식이 두 항을 분리하니 U_DESIGN 이중계상은 해소"라고 결론냈다가
#   레드팀 20회차 F2로 **철회**했다 — 스마트팜연구DB/온실열손실저감및차단기술연구.pdf
#   p.12가 열절감율을 "PE필름(0.08mm) 난방부하계수 5.7 기준 상대값"으로 정의하므로
#   식의 난방부하계수 자리에는 5.7이 와야 하고, 8.9는 1.56배 과대 혐의다(미해결).
#   상세·선택지는 근거_난방계수_이견_20260913.md 4절 ①(78차 ★사용자 판단).
def test_heating_load_matches_source_formula_structure():
    """식이 네 인자의 곱 그대로인지 — 원출처 구조에서 벗어나면 실패한다."""
    Aw, dt_target, dt_min, fr = 6027.47, 7.0, -21.7, 0.30
    u = 8.9
    r = e.heating_load(Aw, "필름", dt_target, dt_min, fr=fr, u_design=u)
    expected = Aw * u * (dt_target - dt_min) * fr
    assert r.max_load_kcal_h == expected, "max_load가 원출처 식의 단순 곱이 아니다"
    # 각 항이 선형으로 들어가는지(어느 항에도 숨은 보정이 없는지)
    r2 = e.heating_load(Aw * 2, "필름", dt_target, dt_min, fr=fr, u_design=u)
    assert r2.max_load_kcal_h == expected * 2
    r3 = e.heating_load(Aw, "필름", dt_target, dt_min, fr=fr / 2, u_design=u)
    assert r3.max_load_kcal_h == expected / 2


def test_higher_savings_rate_lowers_load_per_source_formula():
    """(1 - 열절감률) 구조상 절감률이 클수록 부하가 작아야 한다.
    2026-07-20의 방향 수정이 원문 자구와 맞음을 결과 수준에서 고정한다."""
    common = dict(surface_area_m2=6027.47, cover="필름", t_target=7.0, t_min=-21.7)
    loads = {c: e.heating_load(curtain=c, **common).max_load_kcal_h
             for c in ("PO단일", "다겹보온", "2중커튼")}
    assert loads["2중커튼"] < loads["다겹보온"] < loads["PO단일"], (
        f"절감률이 클수록 부하가 커진다 — 방향반전 {loads}")
    # 원출처 식 그대로인지: 부하비 = (1-절감률)비
    assert abs(loads["2중커튼"] / loads["PO단일"]
               - (1 - e.FR_TABLE["2중커튼"]) / (1 - e.FR_TABLE["PO단일"])) < 1e-9


# 인용 자구의 정본(正本) — 원문 p.49에서 그대로 옮긴 조각이다.
# 20회차 F5: 초판 가드는 PDF 쪽만 봐서, 엔진 docstring의 인용을 훼손해도
#   (예: '열절감률'→'열절감율') 3건 전부 green이었다(뮤테이션 M8로 실증).
#   71차 F6이 "PDF→PDF 검사라 무력"이라며 뒤집었던 것과 같은 유형이라 확장한다.
_P49_FRAGMENTS = ("난방부하 = 하우스표면적", "난방부하계수",
                  "내부설정온도 - 외부기온", "1 - 피복 열절감률")


def test_heating_formula_source_text_still_in_original_pdf():
    """인용 자구가 ①원문 PDF ②엔진 docstring ③레지스트리 source ④이견 문서에
    모두 살아 있는지 — 원문 교체·소실과 **인용 드리프트**를 함께 검출한다.
    audit_traceability는 ref 파일의 '실재'만 보고 '내용'은 보지 않는다(설계 경계).
    ⚠️ pdfplumber 유실 시 조용히 skip된다(환경 특성) — skip 수를 확인할 것."""
    import json
    import os
    pytest = __import__("pytest")
    pdfplumber = pytest.importorskip("pdfplumber")
    repo = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(repo, "시설평가",
                        "20230627_스마트팜 시설의 구조와 이해_김평화(제공).pdf")
    if not os.path.exists(path):
        pytest.skip("원문 PDF 미보유(리포 밖 환경)")
    with pdfplumber.open(path) as pdf:
        text = pdf.pages[48].extract_text() or ""    # printed p.49
    for frag in _P49_FRAGMENTS:
        assert frag in text, (
            f"김평화 p.49 원문에서 '{frag}'를 찾지 못했다 — 원문이 바뀌었거나 "
            f"정본 조각이 틀렸다")

    # 인용을 담은 리포 산출물 3곳이 원문과 같은 자구를 쓰고 있는가(드리프트 검출)
    with open(os.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8") as f:
        reg_src = json.load(f)["constants"]["FR_TABLE"]["source"]
    with open(os.path.join(repo, "근거_난방계수_이견_20260913.md"), encoding="utf-8") as f:
        issue_md = f.read()
    quoted = {"엔진 heating_load docstring": e.heating_load.__doc__,
              "레지스트리 FR_TABLE.source": reg_src,
              "근거_난방계수_이견_20260913.md": issue_md}
    for where, blob in quoted.items():
        assert "1 - 피복 열절감률" in blob, (
            f"{where}의 인용이 원문 자구('1 - 피복 열절감률')와 어긋났다 — "
            f"하이픈이 U+2212로 바뀌었거나(20회차 F6 실제 사례) 표기가 드리프트했다")


def test_u_design_resolved_to_57_by_two_converging_paths():
    """🔴 99차 ★사용자 결정 — U_DESIGN 8.9 → 5.7. 77차부터의 최대 미해결을 닫는다.

    이 테스트의 앞 버전(77차)은 "불일치가 조용히 잊히지 않도록" 8.9를 고정하고
    U_DESIGN이 바뀌면 이견 문서를 함께 갱신하라고 알렸다 — 실제로 그렇게 작동했다.
    이제는 **왜 5.7인지**를 고정한다. 다투던 두 경로가 같은 값으로 수렴한다:

      ① 20회차 F2 — 열절감율이 PE필름(0.08mm) 난방부하계수 **5.7 기준 상대값**이므로
         식의 계수 자리엔 5.7이 와야 한다(검산 3건이 닫힌다).
      ② 78차 반론 — 계수 자리엔 "**그 온실의 단일피복 열관류율**"이 온다(신개념온실
         PDF p.334). 그 값을 [표 3-3-30]에서 읽으면 플라스틱 1중피복 RDA
         **6.63 W × 0.86 = 5.70**이다.

    ②가 엔진과 같은 축임은 같은 행의 유리값으로 보증된다 —
    유리 1중피복 RDA 6.16 × 0.86 = 5.2976 ≈ `U_VALUE["유리"]` 5.3.
    """
    PE_BASELINE = 5.7
    assert e.U_DESIGN["필름"] == PE_BASELINE == 5.7
    assert e.U_DESIGN["불소필름"] == e.U_DESIGN["단동"] == 5.7
    assert "유리" not in e.U_DESIGN and "필름_이중" not in e.U_DESIGN   # 대상 밖(불변)
    # ① 원문 정의 검산: 5.7 × (1 - 절감률) = 그 조합의 난방부하계수(보고서 실측표)
    for savings, measured in ((0.70, 1.7), (0.537, 2.6), (0.323, 3.9)):
        assert abs(PE_BASELINE * (1 - savings) - measured) < 0.06, savings
    # ② [표 3-3-30] 1중피복 RDA(W/㎡·℃) × 0.86 → kcal 난방부하계수
    assert abs(6.63 * e.W_TO_KCAL_PER_HOUR - 5.70) < 0.01      # 플라스틱 → U_DESIGN
    assert abs(6.16 * e.W_TO_KCAL_PER_HOUR - e.U_VALUE["유리"]) < 0.01   # 유리 → 엔진과 같은 축
    # 버린 값 8.9의 정체도 남긴다(Diop 핫박스 고풍속 10.4 W)
    assert abs(10.4 * e.W_TO_KCAL_PER_HOUR - 8.94) < 0.01
    # ⚠️ 방향: 부하가 **줄어드는** 교체다 — 장비 언더사이징 위험이 새로 생긴다
    assert e.U_DESIGN["필름"] < 8.9


def test_99cha_u_design_change_scope_and_regression_safety():
    """99차 교체의 영향 범위를 고정한다 — 특히 **원채원 회귀가 왜 안전한가**.

    u_design은 최대난방부하에만 쓰이고 기간난방부하·연료소비량은 u_period(U_VALUE)를
    쓴다. 그래서 OPEX·ROI가 안 움직인다. 유리 케이스는 U_DESIGN에 키 자체가 없어
    폴백되므로 완전 불변이다. 이 두 성질이 깨지면 회귀 기준이 위험해진다.
    """
    Aw, t_t, t_m, fr = 3362.0, 11.1, -6.7, 0.7
    film = e.heating_load(Aw, "필름", t_t, t_m, fr=fr)
    # 필름: max_load = Aw × 5.7 × dt × fr  (8.9였다면 0.6404배 더 컸다)
    assert abs(film.max_load_kcal_h - Aw * 5.7 * (t_t - t_m) * fr) < 1e-6
    assert abs(film.max_load_kcal_h / (Aw * 8.9 * (t_t - t_m) * fr) - 5.7 / 8.9) < 1e-12
    # 연료소비량은 u_period(U_VALUE 2.66) 기반이라 u_design과 무관하다
    assert abs(film.fuel_consumption
               - (e.DEGREE_HOURS_DEFAULT * e.U_VALUE["필름"] * fr * Aw)
               / (e.FUEL_LHV["등유"] * e.HEATING_EFFICIENCY_DEFAULT)) < 1e-6
    # 유리는 U_DESIGN에 키가 없어 U_VALUE로 폴백 — 원채원·chuncheon 불변의 근거
    glass = e.heating_load(5000.0, "유리", 18.0, -6.7, fr=fr)
    assert abs(glass.max_load_kcal_h - 5000.0 * e.U_VALUE["유리"] * 24.7 * fr) < 1e-6


# ── 설계 문서 정합성 매트릭스 (80차) ─────────────────────────
# 원본: 사용자 첨부 A파일 `스마트팜_수출단지_구축_체크리스트_템플릿_v1.2` 의
#   `P2_정합성매트릭스` 시트. 아래 4행은 그 시트의 **샘플 데이터 전사**라
#   엔진 출력과 엑셀 셀을 직접 대조할 수 있다(전사값 원단위 보존과 같은 취지).
def _matrix_rows():
    return [
        e.DocRefRow("R-ENV-01", "온도 제어 설정값 유지",
                    "HVAC-201", "Rev2", "SPEC-HVAC", "Rev1",
                    "BOQ-ENV-12", "Rev2", "STD-CTRL-01", "Rev1"),
        e.DocRefRow("R-ICT-01", "센서 데이터 1분 주기 수집",
                    "ICT-102", "Rev3", "SPEC-ICT", "Rev2",
                    "BOQ-ICT-05", "Rev3", "STD-DATA-01", "Rev1"),
        e.DocRefRow("R-IRR-02", "EC/pH 자동 보정",
                    "FERT-110", "Rev1", "SPEC-FERT", "Rev1",
                    "BOQ-FERT-07", "Rev1", "STD-FERT-02", "Rev1"),
        e.DocRefRow("R-STR-01", "내재해 설계(풍/설) 충족",
                    "STR-001", "Rev4", "SPEC-STR", "Rev3",
                    "BOQ-STR-01", "Rev4", "STD-STR-01", "Rev2"),
    ]


def test_doc_consistency_reproduces_source_matrix_sample():
    """A파일 샘플 4행을 원본 수식과 같은 결과로 재현하는가.
    R-IRR-02만 4축 Rev가 전부 Rev1이라 OK, 나머지 3건은 REV_MISMATCH다."""
    rep = e.doc_consistency_check(_matrix_rows())
    assert [r.status for r in rep.rows] == [
        "REV_MISMATCH", "REV_MISMATCH", "OK", "REV_MISMATCH"]
    assert rep.counts == {"OK": 1, "MISSING_DOC": 0,
                          "MISSING_REV": 0, "REV_MISMATCH": 3}
    assert [r.req_id for r in rep.rows] == ["R-ENV-01", "R-ICT-01",
                                            "R-IRR-02", "R-STR-01"]


def test_doc_consistency_branch_priority_matches_source_formula():
    """원본 수식의 중첩 IF 우선순위: MISSING_DOC > MISSING_REV > REV_MISMATCH.
    앞 단계에서 걸리면 뒤는 보지 않는다 — 식별자가 없는데 Rev를 비교하는 것은
    의미가 없기 때문이다. 세 조건을 동시에 만족시키는 행으로 순서를 고정한다."""
    row = e.DocRefRow("R-ALL", "세 결함 동시",
                      "", "Rev1",          # 도면: 식별자 누락
                      "SPEC-X", "",        # 시방서: Rev 누락
                      "BOQ-X", "Rev9",     # BoQ: Rev 불일치 유발
                      "STD-X", "Rev1")
    rep = e.doc_consistency_check([row])
    assert rep.rows[0].status == "MISSING_DOC", "누락이 불일치보다 앞서야 한다"
    # Rev 누락도 함께 기록은 하되 status는 MISSING_DOC이어야 한다
    assert rep.rows[0].missing_docs == ["도면"]
    assert rep.rows[0].missing_revs == ["시방서"]


def test_doc_consistency_missing_rev_is_not_mismatch():
    """식별자는 다 있는데 Rev만 비면 MISSING_REV — '불일치'로 뭉개지 않는다."""
    row = e.DocRefRow("R-REV", "Rev 미기재",
                      "D-1", "Rev1", "S-1", "", "B-1", "Rev1", "T-1", "Rev1")
    rep = e.doc_consistency_check([row])
    assert rep.rows[0].status == "MISSING_REV"
    assert rep.rows[0].missing_revs == ["시방서"]
    assert rep.rows[0].mismatch_detail == ""
    assert any("Rev 미기재" in n for n in rep.notes)


def test_doc_consistency_treats_blank_and_whitespace_as_empty():
    """원본 수식의 ="" 판정과 같은 의미 — None·""·공백만 있는 값 전부 공란."""
    row = e.DocRefRow("R-BLANK", "공백 처리",
                      None, "Rev1", "   ", "Rev1", "B-1", "Rev1", "T-1", "Rev1")
    rep = e.doc_consistency_check([row])
    assert rep.rows[0].status == "MISSING_DOC"
    assert rep.rows[0].missing_docs == ["도면", "시방서"]


def test_doc_consistency_rev_compare_is_literal_not_normalized():
    """Rev 비교는 문자열 그대로다 — 표기를 정규화하면 원본 시트와 결과가 갈리고
    무엇이 실제 불일치인지 흐려진다."""
    row = e.DocRefRow("R-CASE", "대소문자 차이",
                      "D-1", "Rev2", "S-1", "rev2", "B-1", "Rev2", "T-1", "Rev2")
    rep = e.doc_consistency_check([row])
    assert rep.rows[0].status == "REV_MISMATCH"
    assert "시방서=rev2" in rep.rows[0].mismatch_detail


def test_doc_consistency_exposes_no_verdict_or_ranking():
    """79차가 거부한 판정 자동화(점수·등급·적합 여부)가 유입되지 않았는가.
    네 코드는 사실 분류이지 가치 판단이 아니다 — 필드명과 notes 문구 양쪽을 본다."""
    rep = e.doc_consistency_check(_matrix_rows())
    fields = (set(rep.__dataclass_fields__) | set(rep.rows[0].__dataclass_fields__)
              | set(e.DocRefRow.__dataclass_fields__))
    banned = ("score", "grade", "rank", "recommend", "verdict", "pass_fail",
              "점수", "등급", "판정", "적합", "추천", "순위")
    bad_f = [f for f in fields if any(k in f.lower() for k in banned)]
    assert bad_f == [], f"판정·점수 필드 유입: {bad_f}"
    bad_n = [n for n in rep.notes if any(k in n for k in ("적합", "부적합", "추천", "점수", "등급"))]
    assert bad_n == [], f"notes에 판정 어휘 유입: {bad_n}"
    # 상태 코드는 원본 시트의 4종 그대로여야 한다(대조가능성)
    assert set(rep.counts) == {"OK", "MISSING_DOC", "MISSING_REV", "REV_MISMATCH"}


def test_doc_consistency_empty_input():
    rep = e.doc_consistency_check([])
    assert rep.rows == [] and rep.notes == []
    assert rep.counts == {"OK": 0, "MISSING_DOC": 0,
                          "MISSING_REV": 0, "REV_MISMATCH": 0}


def test_doc_consistency_not_wired_into_render_paths():
    """80차 도달성: 아직 산출물 렌더에 연결돼 있지 않다(74차 관례)."""
    import os
    repo = os.path.dirname(os.path.abspath(__file__))
    for fname in ("build_site.py", "webapp.py", "render_report.py", "app.py",
                  "run_report.py", "render_chuncheon.py", "cases.py"):
        path = os.path.join(repo, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            assert "doc_consistency_check" not in f.read(), (
                f"{fname}이 doc_consistency_check를 쓰기 시작했다 — 산출물에 "
                f"도달하면 입력 스키마(도면·시방·BoQ·규격서 4축)의 provenance "
                f"처리를 먼저 정하고 이 테스트를 함께 갱신할 것")


# ── DSCR · 최대 감당 투자비 (81차) ───────────────────────────
# 79차 지침 편입 판정의 엔진 공백 2·3번. 임계값은 엔진이 갖지 않고 전부 주입한다.
_WC_REV = 332_640_000.0      # 원채원 케이스 매출(엔진 재계산값)
_WC_OPEX = 186_420_000.0
_WC_CAPEX = 702_030_000.0


def _wonchaewon_finance_inputs():
    """회귀 케이스(원채원)의 매출·OPEX를 엔진으로 재계산해 픽스처와 대조한다 —
    상수를 손으로 적어두면 케이스가 바뀌어도 눈치채지 못한다."""
    import cases as C
    c = [x for x in C.load_cases() if x["case_id"] == "wonchaewon"][0]
    i = c["input"]
    rev = e.production_kg(i["area_m2"], i["base_yield_kg_m2"],
                          i["fitness_pct"]) * i["price_won_per_kg"]
    return rev, i["opex"], i["total_construction_cost"], i["subsidy_rate"]


def test_wonchaewon_fixture_constants_match_the_case():
    """_WC_* 상수가 실제 케이스와 어긋나면 아래 DSCR 테스트들이 조용히 다른
    농가를 검사하게 된다 — 손으로 적은 값의 드리프트를 여기서 잡는다."""
    rev, opex, capex, _ = _wonchaewon_finance_inputs()
    assert (rev, opex, capex) == (_WC_REV, _WC_OPEX, _WC_CAPEX)


def test_dscr_matches_cads_over_debt_service():
    """DSCR = (매출 - 운영비) / 그 해 납입액 — 원단위 일치. 상환 계산을 여기서
    다시 하지 않고 loan_amortization 결과를 그대로 쓴다."""
    loan = e.loan_amortization(500_000_000, 3.0, 10, 2)
    res = e.dscr_schedule(_WC_REV, _WC_OPEX, loan)
    assert res.cads_annual == _WC_REV - _WC_OPEX
    assert len(res.rows) == len(loan["rows"])
    for row, lr in zip(res.rows, loan["rows"]):
        assert row.year == lr["연차"]
        assert row.debt_service == lr["납입액"]
        assert row.dscr == res.cads_annual / lr["납입액"]


def test_dscr_min_is_the_worst_year_not_the_last():
    """최소 DSCR과 그 연차를 정확히 집는가. 거치 2년은 이자만 내 납입액이 작아
    DSCR이 높고, 상환 개시 후가 낮다 — '마지막 해'로 단정하면 안 된다."""
    loan = e.loan_amortization(500_000_000, 3.0, 10, 2)
    res = e.dscr_schedule(_WC_REV, _WC_OPEX, loan)
    vals = [(r.dscr, r.year) for r in res.rows if r.dscr is not None]
    assert (res.min_dscr, res.min_dscr_year) == min(vals)
    grace = [r for r in res.rows if r.year <= 2]
    assert all(r.dscr > res.min_dscr for r in grace), "거치기간이 최소일 리 없다"


def test_dscr_zero_debt_service_is_none_not_infinity():
    """납입액 0이면 무한대로 표기하지 않고 None — 근거 없는 수치를 만들지 않는다."""
    fake = {"rows": [{"연차": 1, "납입액": 0.0}, {"연차": 2, "납입액": 1_000_000.0}]}
    res = e.dscr_schedule(_WC_REV, _WC_OPEX, fake)
    assert res.rows[0].dscr is None
    assert res.rows[1].dscr == res.cads_annual / 1_000_000.0
    assert res.min_dscr_year == 2


def test_dscr_basis_note_states_what_is_not_modelled():
    """CADS 정의와 미반영 항목(세금·운전자본)을 산출물에 드러낼 수 있어야 한다 —
    표준 DSCR보다 단순하다는 사실을 숨기지 않는다."""
    loan = e.loan_amortization(100_000_000, 3.0, 5)
    note = e.dscr_schedule(_WC_REV, _WC_OPEX, loan).basis_note
    for frag in ("매출 - 운영비", "세금", "운전자본"):
        assert frag in note


def test_dscr_rejects_non_loan_dict():
    import pytest
    with pytest.raises(ValueError):
        e.dscr_schedule(_WC_REV, _WC_OPEX, {"연차": 1})


def test_max_capex_combined_equals_min_of_individual_limits():
    """제약을 동시에 걸면 상한은 개별 상한들의 최솟값이어야 한다(단조성의 귀결)."""
    rev, opex, capex, sub = _wonchaewon_finance_inputs()
    L = dict(loan_rate_pct=3.0, loan_term_years=10, loan_grace_years=2)
    a = e.max_investable_capex(rev, opex, target_irr=0.08, subsidy_rate=sub).max_capex_won
    b = e.max_investable_capex(rev, opex, max_payback_years=8, subsidy_rate=sub).max_capex_won
    c = e.max_investable_capex(rev, opex, min_dscr=1.3, subsidy_rate=sub, **L).max_capex_won
    both = e.max_investable_capex(rev, opex, target_irr=0.08, max_payback_years=8,
                                  min_dscr=1.3, subsidy_rate=sub, **L)
    assert abs(both.max_capex_won - min(a, b, c)) < 2.0, (a, b, c, both.max_capex_won)
    assert both.binding, "상한에서 어떤 제약이 걸리는지 알려야 한다"


def test_max_capex_irr_limit_is_consistent_with_case_regression():
    """원채원 회귀값(CAPEX 702,030,000에서 IRR 16.2%)과 정합하는가 —
    목표 IRR을 16%로 두면 상한이 현재 CAPEX '바로 위'에 있어야 한다.
    역산 로직이 finance()와 어긋나면 여기서 깨진다."""
    rev, opex, capex, sub = _wonchaewon_finance_inputs()
    m = e.max_investable_capex(rev, opex, target_irr=0.16,
                               subsidy_rate=sub, current_capex_won=capex)
    assert m.max_capex_won > capex, "IRR 16.2% > 16%이므로 상한이 현재보다 커야 한다"
    assert m.max_capex_won < capex * 1.05, "16.2%와 16%의 차이는 작다"
    assert m.gap_won == m.max_capex_won - capex


def test_max_capex_irr_probe_agrees_with_finance():
    """`measured_irr`의 넓힌 탐색이 `finance()`가 측정 가능한 구간에서는
    같은 값을 내는가 — 두 경로가 드리프트하면 역산이 조용히 틀어진다."""
    rev, opex, _, _ = _wonchaewon_finance_inputs()
    for capex in (3e8, 5e8, 7e8, 1.2e9):
        fin = e.finance(rev, opex, capex)
        if fin.irr is None:
            continue                      # finance가 못 재는 구간은 대조 대상 아님
        cfs = [-capex] + [fin.operating_profit + fin.depreciation] * 10
        assert abs(e.irr(cfs, hi=1e9) - fin.irr) < 1e-6


def test_max_capex_without_constraints_returns_none_with_reason():
    rev, opex, _, _ = _wonchaewon_finance_inputs()
    m = e.max_investable_capex(rev, opex)
    assert m.max_capex_won is None and m.notes


def test_max_capex_infeasible_when_opex_exceeds_revenue():
    """매출보다 운영비가 크면 어떤 규모에서도 제약을 못 맞춘다 —
    상한을 만들어내지 않고 None + 사유를 돌려준다."""
    m = e.max_investable_capex(100_000_000, 150_000_000, target_irr=0.08)
    assert m.max_capex_won is None
    assert m.feasible_at_zero is False
    assert any("최소 규모" in n for n in m.notes)


def test_max_capex_requires_loan_terms_for_dscr_constraint():
    import pytest
    with pytest.raises(ValueError):
        e.max_investable_capex(_WC_REV, _WC_OPEX, min_dscr=1.3)


def test_finance_extension_exposes_no_verdict_or_threshold_constant():
    """임계값을 엔진이 갖지 않는가 — 'DSCR 1.3 이상 양호' 같은 기준선은
    판단성이라 상수로 두지 않는다(79차 거부 판정). 판정 어휘도 없어야 한다."""
    import inspect
    sig = inspect.signature(e.max_investable_capex)
    for name in ("target_irr", "max_payback_years", "min_dscr"):
        assert sig.parameters[name].default is None, f"{name}에 기본 임계값이 생겼다"
    fields = (set(e.MaxCapexResult.__dataclass_fields__)
              | set(e.DscrResult.__dataclass_fields__)
              | set(e.DscrRow.__dataclass_fields__))
    banned = ("grade", "score", "verdict", "recommend", "pass", "적합", "등급", "판정", "추천")
    bad = [f for f in fields if any(k in f.lower() for k in banned)]
    assert bad == [], f"판정 필드 유입: {bad}"


def test_finance_extension_not_wired_into_render_paths():
    """81차 도달성(74차 관례)."""
    import os
    repo = os.path.dirname(os.path.abspath(__file__))
    for fname in ("build_site.py", "webapp.py", "render_report.py", "app.py",
                  "run_report.py", "render_chuncheon.py", "cases.py"):
        path = os.path.join(repo, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            body = f.read()
        for fn in ("dscr_schedule", "max_investable_capex"):
            assert fn not in body, (
                f"{fname}이 {fn}을 쓰기 시작했다 — CADS 정의가 세금·운전자본을 "
                f"빼고 있다는 사실(basis_note)을 산출물에 함께 노출하고 "
                f"이 테스트를 갱신할 것")


# ── 피복·보온재 조합별 난방부하계수 (82차, 사용자 결정 ⓒ) ────
# 출처: 농진청 「온실 열손실 저감 및 차단 기술 연구」 표9(피복재 9)·표10(보온재 16)·
#   표11(이중 24) = 49행 전량 전사. 원문 p.12가 산정식을 정의한다.
def test_cover_assemblies_transcription_is_internally_consistent():
    """전사 검산 — 원문 정의 `열절감율 = (계수 − 5.7) × 100 / 5.7`(PE필름 0.08 기준)이
    성립하면 `계수 = round(5.7 × (1 − 절감율), 1)`이어야 한다. **49행 전부** 통과해야
    전사가 온전한 것이다(한 행이라도 어긋나면 옮겨 적다 틀린 것).

    ⚠️ 역방향(`계수 = round(열관류율 × 0.86, 1)`)은 3행에서 0.1 어긋난다 — 열관류율
    열이 소수 1자리로 반올림돼 정밀도를 잃은 탓이지 전사 오류가 아니다. 그래서
    검산 기준을 절감율 쪽으로 잡는다."""
    base = e._pe_baseline_coef()
    assert base == 5.7
    assert len(e.COVER_ASSEMBLIES) == 49
    for a in e.COVER_ASSEMBLIES:
        derived = round(base * (1 - a.savings_pct / 100), 1)
        assert abs(derived - a.coef_kcal) <= 0.051, (
            f"{a.layers}: 계수 {a.coef_kcal} vs 절감율 역산 {derived} — 전사 확인 필요")


def test_cover_assemblies_table_composition():
    """표별 행 수와 층수 분포 — 원문 구성이 바뀌면(또는 일부만 옮겨졌으면) 깨진다."""
    from collections import Counter
    by_table = Counter(a.table for a in e.COVER_ASSEMBLIES)
    assert by_table == {"표9": 9, "표10": 16, "표11": 24}
    assert len(e.cover_assembly_options(1)) == 25      # 표9 9 + 표10 16
    assert len(e.cover_assembly_options(2)) == 24      # 표11
    # 원문 앵커 3행(각 표에서 1건씩) — 값이 바뀌면 잡는다
    assert e.cover_assembly_lookup(("PE필름(0.08)",)).coef_kcal == 5.7
    assert e.cover_assembly_lookup(("다겹보온커튼(4겹)",)).savings_pct == 53.7
    assert e.cover_assembly_lookup(("pe-0.15", "5겹다겹")).coef_kcal == 1.7


def test_cover_assembly_lookup_is_exact_match_only():
    """원문 표기를 정규화하지 않는다 — 임의 통일하면 어느 행을 집었는지 추적 불가.
    못 찾으면 가까운 조합을 대신 주지 않고 None(근거 없는 값 금지)."""
    assert e.cover_assembly_lookup(("pe-0.15",)) is None       # 표9 표기는 'PE필름(0.15)'
    assert e.cover_assembly_lookup(("PE필름(0.15)",)) is not None
    assert e.cover_assembly_lookup(("PE필름(0.15)", "5겹다겹")) is None
    assert e.cover_assembly_lookup(("없는자재",)) is None


def test_heating_load_assembly_uses_measured_coefficient_without_extra_reduction():
    """assembly 경로: 조합 계수에 보온 효과가 이미 포함돼 있으므로 절감률을 또
    곱하지 않는다(fr=1.0). 결과가 `면적 × 조합계수 × ΔT`와 원단위 일치해야 한다."""
    Aw, tt, tm = 6027.47001696239, 7.0, -21.7
    key = ("pe-0.15", "5겹다겹")
    a = e.cover_assembly_lookup(key)
    r = e.heating_load(Aw, "필름", tt, tm, assembly=key, floor_area_m2=2016.0)
    assert r.max_load_kcal_h == Aw * a.coef_kcal * (tt - tm)


def test_heating_load_assembly_is_mutually_exclusive_with_fr_and_curtain():
    """82차에 배타 가드가 3분기로 넓어졌다 — 셋 중 정확히 하나."""
    import pytest
    Aw, key = 1000.0, ("pe-0.15", "5겹다겹")
    for kw in ({}, {"fr": 0.3, "curtain": "다겹보온"},
               {"fr": 0.3, "assembly": key}, {"curtain": "다겹보온", "assembly": key},
               {"fr": 0.3, "curtain": "다겹보온", "assembly": key}):
        with pytest.raises(ValueError):
            e.heating_load(Aw, "필름", 7, -10, **kw)
    # 하나씩은 전부 통과
    for kw in ({"fr": 0.3}, {"curtain": "다겹보온"}, {"assembly": key}):
        e.heating_load(Aw, "필름", 7, -10, **kw)


def test_heating_load_assembly_rejects_u_override_and_unknown_key():
    """조합 계수와 u_design/u_period를 함께 주면 이중 지정이라 거부.
    미등록 조합도 거부한다 — 가까운 값으로 대신 계산하지 않는다."""
    import pytest
    key = ("pe-0.15", "5겹다겹")
    with pytest.raises(ValueError):
        e.heating_load(1000.0, "필름", 7, -10, assembly=key, u_design=8.9)
    with pytest.raises(ValueError):
        e.heating_load(1000.0, "필름", 7, -10, assembly=key, u_period=2.66)
    with pytest.raises(ValueError):
        e.heating_load(1000.0, "필름", 7, -10, assembly=("없는것", "없는것2"))


def test_existing_fr_and_curtain_paths_unchanged_by_assembly_addition():
    """82차 변경이 기존 두 경로의 값을 건드리지 않았는가(회귀).
    견적비교 2건이 curtain='다겹보온'으로 live다."""
    Aw = 6027.47001696239
    r_fr = e.heating_load(Aw, "필름", 7, -21.7, fr=0.15, u_design=5.7, floor_area_m2=2016.0)
    assert r_fr.max_load_kcal_h == Aw * 5.7 * 28.7 * 0.15
    r_c = e.heating_load(Aw, "필름", 7, -21.7, curtain="다겹보온", floor_area_m2=2016.0)
    assert r_c.max_load_kcal_h == Aw * e.U_DESIGN["필름"] * 28.7 * (1 - e.FR_TABLE["다겹보온"])


def test_fr_table_and_assembly_disagree_and_that_is_recorded_not_silently_merged():
    """두 경로가 같은 이름의 자재에 다른 값을 준다 — 82차는 이를 **합치지 않고**
    기록만 했다(매핑은 판단성). 그 불일치를 사실로 고정해 둔다.
    FR_TABLE['다겹보온']=0.5 vs 표10 다겹보온커튼 3겹 32.3%·4겹 53.7%·5겹 59.6%."""
    fr_val = e.FR_TABLE["다겹보온"] * 100
    measured = [e.cover_assembly_lookup((n,)).savings_pct
                for n in ("다겹보온커튼(3겹)", "다겹보온커튼(4겹)", "다겹보온커튼(5겹)")]
    assert not any(abs(m - fr_val) < 1.0 for m in measured), (
        f"FR_TABLE 0.5가 실측 {measured} 중 하나와 일치하게 됐다 — "
        f"매핑이 확정된 것이라면 근거_난방계수_이견_20260913.md를 함께 갱신할 것")
    # 유리온실이 표에 없다는 사실도 고정(chuncheon·wonchaewon 이관 불가 근거)
    assert not [a for a in e.COVER_ASSEMBLIES
                if any("유리" in x for x in a.layers)]


def test_cover_assemblies_not_wired_into_render_paths():
    """82차 도달성: 신규 경로는 아직 산출물에 연결돼 있지 않다(74차 관례).
    연결 시 케이스 값이 움직이므로 마이그레이션 결정이 선행돼야 한다."""
    import os
    repo = os.path.dirname(os.path.abspath(__file__))
    for fname in ("build_site.py", "webapp.py", "render_report.py", "app.py",
                  "run_report.py", "render_chuncheon.py", "cases.py"):
        path = os.path.join(repo, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            body = f.read()
        for token in ("assembly=", "cover_assembly_lookup", "COVER_ASSEMBLIES"):
            assert token not in body, (
                f"{fname}이 조합 경로를 쓰기 시작했다 — 케이스 난방부하가 움직이므로 "
                f"어느 조합으로 매핑할지(판단성) 결정하고 이 테스트를 갱신할 것")


# ── 미검증 상수 재조사 결과 고정 (83차) ─────────────────────
# 사용자 지시 "미검증인 내용에 대해 검증진행하라". 국내 표준 난방설계 매뉴얼
# (신개념온실설계및표준화연구 p.344~346·350·359) 대조 결과를 코드로 남긴다.
# **값은 하나도 바꾸지 않았다** — 정체 후보를 찾은 것이지 확정한 게 아니다.
def test_heating_constants_match_manual_leads_found_in_83():
    """83차에 찾은 원문 대응을 고정한다. 값이 바뀌면 근거 문서를 함께 갱신하라고 알린다."""
    # p.346: "난방기의 효율로 온풍난방의 경우 0.8∼0.9" — 0.85는 그 범위의 중앙값
    assert e.HEATING_EFFICIENCY_DEFAULT == 0.85
    assert abs(e.HEATING_EFFICIENCY_DEFAULT - (0.8 + 0.9) / 2) < 1e-9, (
        "0.85가 온풍난방 범위(0.8~0.9)의 중앙값이라는 83차 관측이 깨졌다")
    # p.345 표3-3-35: 강풍지역 단일피복 풍속보정계수 1.1 — 엔진 안전율과 값이 같다
    assert e.HEATING_SAFETY_FACTOR == 1.1
    # p.359 표3-3-42에 10,098은 없다 — 최근접이 부산 8℃ 10,269(=10.269×10³)
    assert e.DEGREE_HOURS_DEFAULT == 10098.0
    assert e.DEGREE_HOURS_DEFAULT != 10269.0


def test_glass_u_value_competing_hypothesis_is_recorded():
    """83차: 표3-3-33 유리 1중피복 6.2 W/㎡·℃ × 0.86 = 5.33 → 5.3.
    U_VALUE['유리']=5.3의 '출처 오염 확정적' 단정을 격하한 근거다.
    레지스트리가 이 경쟁 가설을 계속 싣고 있는지 확인한다(단정 재발 방지)."""
    import json
    import os
    repo = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8") as f:
        src = json.load(f)["constants"]["U_VALUE"]["source"]
    assert e.U_VALUE["유리"] == 5.3
    assert abs(6.2 * 0.86 - 5.33) < 0.005
    for frag in ("경쟁 가설", "표 3-3-33"):
        assert frag in src, (
            f"U_VALUE source에서 '{frag}'가 사라졌다 — 83차가 격하한 "
            f"'출처 오염 확정적' 단정이 되살아났는지 확인할 것")


# ── 최대난방부하 3성분 구조 (84차, 사용자 지시 "c 진행") ─────
# 원문 식(3-3-1): 최대난방부하 = (관류 + 틈새환기 + 지중) × 풍속보정계수
# 83차가 "엔진이 관류열부하만 계산한다"를 발견한 데 대한 구조 보강.
def test_heating_components_reproduce_report_testbed_transmission():
    """정밀계측 보고서 p.62 테스트베드(U=4.3·A=1983.47·Δt=10)의 관류열부하 **산식**을
    재현하는가. 3성분 함수는 이 값을 **받아 쓸 뿐 재계산하지 않는다**.
    ⚠️ 85차 주의: 원문 U는 W/㎡·℃라 원문 결과는 W이고 엔진 결과는 kcal/h다 —
    여기서 확인하는 것은 **곱셈 구조의 일치**이지 단위 동일성이 아니다."""
    h = e.heating_load(1983.47, "필름", 7, -3, fr=1.0, u_design=4.3)
    assert abs(h.max_load_kcal_h - 4.3 * 1983.47 * 10) < 1e-6
    r = e.heating_load_components(h.max_load_kcal_h, 7, -3)
    assert r.transmission_kcal_h == h.max_load_kcal_h


def test_heating_components_does_not_invent_missing_inputs():
    """없는 입력을 지어내지 않는다 — 못 구한 성분은 None이고 missing에 무엇이
    필요한지 적는다. total은 3성분이 다 있을 때만 채워진다(부분합을 완전한
    최대난방부하로 오독하면 과소산정이다)."""
    r = e.heating_load_components(100_000.0, 20, -10)
    assert r.infiltration_kcal_h is None and r.ground_kcal_h is None
    assert r.total_kcal_h is None
    assert r.partial_total_kcal_h == 100_000.0
    assert len(r.missing) == 2
    # 하나만 채워도 여전히 미완이다
    r2 = e.heating_load_components(100_000.0, 20, -10, perimeter_m=240,
                                   ground_loss_coef_w_m_c=7.5, ground_base_dt=10.0)
    assert r2.ground_kcal_h is not None and r2.total_kcal_h is None
    assert len(r2.missing) == 1


def test_heating_components_full_formula():
    """3성분이 다 있을 때 원문 식대로 조립되는가 — 각 항을 손으로 계산해 대조."""
    tr, tt, tm = 100_000.0, 20.0, -10.0
    dt = tt - tm
    r = e.heating_load_components(
        tr, tt, tm, volume_m3=6000, infiltration_per_hour=0.45,
        air_density_kg_m3=1.2, perimeter_m=240, ground_loss_coef_w_m_c=7.5,
        ground_base_dt=10.0, wind_factor=1.1)
    assert r.infiltration_kcal_h == 1.2 * e.AIR_SPECIFIC_HEAT_KCAL_KG_C * 0.45 * 6000 * dt
    assert r.ground_kcal_h == 7.5 * 240 * (dt - 10.0) * e.W_TO_KCAL_PER_HOUR
    assert r.total_kcal_h == (tr + r.infiltration_kcal_h + r.ground_kcal_h) * 1.1
    assert r.missing == []


def test_ground_load_clipped_when_dt_below_base():
    """Δt가 부하경감 기준온도차 이하면 지중열류 방향이 바뀐다 — 음수 부하를
    만들지 않고 0으로 절삭한다."""
    r = e.heating_load_components(100_000.0, 5, 0, perimeter_m=240,
                                  ground_loss_coef_w_m_c=7.5, ground_base_dt=10.0,
                                  volume_m3=1, infiltration_per_hour=0, air_density_kg_m3=1.2)
    assert r.ground_kcal_h == 0.0


def test_wind_correction_factor_table_matches_source():
    """[표 3-3-35] 전사 + 강풍지역 판정 기준(동절기 평균풍속 3.0m/s 이상)."""
    assert e.WIND_STRONG_THRESHOLD_MS == 3.0
    assert e.wind_correction_factor(2.9, False) == 1.0
    assert e.wind_correction_factor(2.9, True) == 1.0
    assert e.wind_correction_factor(3.0, False) == 1.1     # 강풍·단일피복
    assert e.wind_correction_factor(3.0, True) == 1.05     # 강풍·보온피복
    assert set(e.WIND_CORRECTION_FACTOR.values()) == {1.0, 1.1, 1.05}


def test_infiltration_and_ground_tables_are_ranges_not_single_values():
    """79차 채택 §G — 근거가 범위면 단일값으로 접지 않는다.
    표 3-3-34는 7종 전부 (low, high)이고 low <= high여야 한다."""
    assert len(e.INFILTRATION_RATE_PER_HOUR) == 7
    for name, (lo, hi) in e.INFILTRATION_RATE_PER_HOUR.items():
        assert lo <= hi, name
    assert e.INFILTRATION_RATE_PER_HOUR["완전기밀"] == (0.0, 0.0)
    assert e.INFILTRATION_RATE_PER_HOUR["단일피복"] == (0.5, 1.0)
    # 정밀계측 보고서 테스트베드 0.0001265 회/s = 0.4554 회/h 가 이중피복 범위 안
    lo, hi = e.INFILTRATION_RATE_PER_HOUR["이중피복"]
    assert lo <= 0.0001265 * 3600 <= hi
    # 지중 계수도 범위 + 기준온도차
    assert e.GROUND_LOSS_COEF["대규모"] == (7.5, 10.0, 10.0)
    assert e.GROUND_LOSS_COEF["소규모"] == (2.5, 5.0, 15.0)


def test_heating_load_unchanged_by_component_addition():
    """84차가 heating_load()를 건드리지 않았는가 — 케이스·견적비교가 이 함수를 탄다."""
    Aw = 6027.47001696239
    r = e.heating_load(Aw, "필름", 7, -21.7, curtain="다겹보온", floor_area_m2=2016.0)
    assert r.max_load_kcal_h == Aw * e.U_DESIGN["필름"] * 28.7 * (1 - e.FR_TABLE["다겹보온"])


def test_heating_components_not_wired_into_render_paths():
    """84차 도달성(74차 관례)."""
    import os
    repo = os.path.dirname(os.path.abspath(__file__))
    for fname in ("build_site.py", "webapp.py", "render_report.py", "app.py",
                  "run_report.py", "render_chuncheon.py", "cases.py"):
        path = os.path.join(repo, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            body = f.read()
        assert "heating_load_components" not in body, (
            f"{fname}이 3성분 구조를 쓰기 시작했다 — 케이스에 체적·둘레길이 입력이 "
            f"없어 partial_total이 렌더될 위험이 있다(과소산정 오독). 입력 스키마를 "
            f"먼저 정하고 이 테스트를 갱신할 것")


# ── 수식 원문 확정 + 단위 환산 (85차, 사용자 지시 "a 진행") ──
# 수식이 이미지라 pypdfium2로 300dpi 렌더해 직접 열람했다. 1차 출처(신개념온실
# p.345)와 2차(정밀계측 p.62) 양쪽에서 같은 식을 확인했다.
def test_ground_load_unit_conversion_w_to_kcal():
    """🔴 84차 결함 회귀 방지: 원문 F는 **W/m·℃**라 F·L·(ΔT−Θ)의 결과가 W다.
    관류열부하(kcal/h)와 더하려면 환산해야 하는데 84차 구현은 그냥 더했다.
    환산이 빠지면 지중 항이 1/0.86 = 약 16% 과대 계상된다."""
    assert e.W_TO_KCAL_PER_HOUR == 0.86
    r = e.heating_load_components(
        0.0, 20, -10, perimeter_m=240, ground_loss_coef_w_m_c=7.5,
        ground_base_dt=10.0, volume_m3=1, infiltration_per_hour=0.0,
        air_density_kg_m3=1.2)
    raw_w = 7.5 * 240 * (30.0 - 10.0)          # = 36,000 W (원문 단위)
    assert r.ground_kcal_h == raw_w * 0.86     # = 30,960 kcal/h
    assert r.ground_kcal_h != raw_w, "환산이 빠지면 단위가 섞인다(84차 결함)"


def test_source_formula_shape_is_pinned():
    """85차에 렌더로 확정한 식 형태를 결과 수준에서 고정한다.
      H_T = (H_W + H_V + H_S)·f_w · H_V = ρ·c_p·N·V·ΔT · H_S = F·L_s·(ΔT−Θ)
    구현이 다른 형태로 바뀌면(예: 보정계수를 관류에만 곱하면) 여기서 깨진다."""
    tr, tt, tm, fw = 50_000.0, 18.0, -12.0, 1.05
    dt = tt - tm
    rho, N, V = 1.2, 0.3, 4000.0
    F, L, th = 5.0, 180.0, 15.0
    r = e.heating_load_components(tr, tt, tm, volume_m3=V, infiltration_per_hour=N,
                                  air_density_kg_m3=rho, perimeter_m=L,
                                  ground_loss_coef_w_m_c=F, ground_base_dt=th,
                                  wind_factor=fw)
    hv = rho * e.AIR_SPECIFIC_HEAT_KCAL_KG_C * N * V * dt
    hs = F * L * (dt - th) * e.W_TO_KCAL_PER_HOUR
    assert r.infiltration_kcal_h == hv
    assert r.ground_kcal_h == hs
    # 보정계수는 **세 성분의 합 전체**에 곱한다(관류에만 곱하는 형태가 아니다)
    assert r.total_kcal_h == (tr + hv + hs) * fw
    assert r.total_kcal_h != tr * fw + hv + hs


def test_air_specific_heat_is_kcal_not_the_labelled_joule():
    """원문 두 보고서가 c_p를 'J/kg℃'로 라벨하지만 정밀계측이 쓰는 값 0.24는
    J 값이 아니다 — 0.24 kcal/kg·℃ × 4,186.8 = 1,004.8 J/kg·K로 표준 공기
    정압비열과 일치한다. 즉 원문 라벨이 오기이고 값은 kcal 계열이다.
    이 판정이 뒤집히면(누가 0.24를 J로 읽어 상수를 고치면) 여기서 알린다."""
    assert e.AIR_SPECIFIC_HEAT_KCAL_KG_C == 0.24
    joules = e.AIR_SPECIFIC_HEAT_KCAL_KG_C * 4186.8
    assert 1000 < joules < 1010, f"0.24가 kcal 계열이라는 판정이 깨졌다({joules})"


# ── 케이스 기하 데이터 (86차, 사용자 지시 "a 진행") ──────────
# 우민재 도면(0. 도면(우민재).pdf p.3·p.4)에서 치수를 전사해 cases/uminjae.json의
# **형제 블록** `dimensions`에 넣었다(`input`에 넣으면 FarmInput(**input)이 깨진다).
def _uminjae_case():
    import cases as C
    return [c for c in C.load_cases() if c["case_id"] == "uminjae"][0]


def test_uminjae_dimensions_transcription_checksum():
    """도면 자체 검산 — 세 면적 항의 합이 도면 합계와 원단위로 맞아야 전사가 온전하다."""
    g = _uminjae_case()["dimensions"]["transcribed"]
    assert g["status" if False else "form"] == "5연동"
    assert abs(32 * 60.05 - g["area_inner_m2"]) < 0.01
    assert abs(1 * 60.05 + 1 * 20.02 - g["area_windbreak_m2"]) < 0.01
    total = g["area_inner_m2"] + g["area_windbreak_m2"] + g["area_workroom_m2"]
    assert abs(total - g["area_total_m2"]) < 0.01, "도면 면적개요 합계가 안 맞는다"
    assert (g["eave_height_m"], g["ridge_height_m"]) == (6, 7.25)


def test_uminjae_dimensions_do_not_break_the_case_loader():
    """`dimensions`는 형제 블록이라 FarmInput 변환에 영향이 없어야 한다 —
    `input`에 넣으면 `cases.case_to_input()`이 TypeError로 깨진다."""
    import cases as C
    c = _uminjae_case()
    assert "dimensions" in c and "volume_m3" not in c["input"]
    inp = C.case_to_input(c)          # 깨지면 여기서 잡힌다
    assert inp.area_m2 == 2323        # 기존 입력 불변(도면 합계 2,321.87과는 1.13㎡ 차)


def test_uminjae_volume_is_a_range_not_a_single_value():
    """지붕 형상 가정에 따라 평균높이가 달라지므로 단일 체적을 정하지 않았다
    (79차 채택 §G). 범위가 박공~아치 평균높이와 맞는지 확인한다."""
    g = _uminjae_case()["dimensions"]
    lo, hi = g["derived"]["volume_inner_m3_range"]
    area = g["transcribed"]["area_inner_m2"]
    eave, ridge = g["transcribed"]["eave_height_m"], g["transcribed"]["ridge_height_m"]
    assert abs(lo - area * (eave + (ridge - eave) / 2)) < 1        # 박공
    assert abs(hi - area * (eave + (ridge - eave) * 2 / 3)) < 1    # 아치
    assert g["derived"]["perimeter_inner_m"] == round(2 * (32 + 60.05), 2)


def test_uminjae_three_component_impact_is_small_unlike_the_synthetic_example():
    """🔴 84·85차의 합성 예시(관류 대비 1.80배)는 **대표성이 없다**.
    실제 우민재 케이스에 표 범위를 양 끝으로 돌리면 **1.0~1.1배**에 그친다 —
    ΔT가 17.8℃로 작아 지중 항이 (ΔT−Θ)에서 거의 사라지고, 이중피복+커튼 온실의
    틈새환기율(0.1~0.2 회/h)도 낮기 때문이다. 과소산정 크기를 케이스 없이
    일반화하면 안 된다는 사실을 여기서 고정한다."""
    c = _uminjae_case()
    i, g = c["input"], c["dimensions"]
    h = e.heating_load(i["surface_area_m2"], i["cover"], i["t_target"], i["t_min"],
                       fr=i["fr"], floor_area_m2=i["area_m2"])
    L = g["derived"]["perimeter_inner_m"]
    ratios = []
    for N in (0.1, 0.2):                                   # 표3-3-34 이중피복+커튼1층
        for V in g["derived"]["volume_inner_m3_range"]:
            for F, th in ((2.5, 15.0), (10.0, 10.0)):      # 소규모/대규모 양 끝
                r = e.heating_load_components(
                    h.max_load_kcal_h, i["t_target"], i["t_min"], volume_m3=V,
                    infiltration_per_hour=N, air_density_kg_m3=1.2, perimeter_m=L,
                    ground_loss_coef_w_m_c=F, ground_base_dt=th, wind_factor=1.0)
                assert r.missing == []
                ratios.append(r.total_kcal_h / h.max_load_kcal_h)
    assert 1.0 < min(ratios) < 1.05, min(ratios)
    assert 1.05 < max(ratios) < 1.15, max(ratios)


# ── 온실 환경설계용 기상자료 (88차, 사용자 지시 "c 진행") ────
# [표 3-3-38] TAC 설계외기온 · [표 3-3-42] 난방디그리아워, 각 69지역 전사.
def test_weather_tables_transcription_and_monotonicity():
    """전사 검산 — 앵커 원문 일치 + 단조성 3종. 한 행이라도 어긋나면 전사 오류다."""
    assert len(e.DESIGN_OUTDOOR_TEMP_TAC) == 69
    assert len(e.HEATING_DEGREE_HOURS_1000) == 69
    assert set(e.DESIGN_OUTDOOR_TEMP_TAC) == set(e.HEATING_DEGREE_HOURS_1000)
    # 원문 앵커
    assert e.design_outdoor_temp("속초") == -9.3
    assert e.design_outdoor_temp("전주") == -9.4
    assert e.heating_degree_hours("부산", 8)["value"] == 10269.0
    assert e.heating_degree_hours("속초", 8)["value"] == 18895.0
    # ①TAC 1% <= 2.5% <= 5%  ②설정온도 단조증가
    for r in e.DESIGN_OUTDOOR_TEMP_TAC:
        a1, a2, a5 = (e.design_outdoor_temp(r, t) for t in ("1%", "2.5%", "5%"))
        assert a1 <= a2 <= a5, r
    for r, v in e.HEATING_DEGREE_HOURS_1000.items():
        assert v[0] < v[1] < v[2] < v[3], r


def test_heating_degree_hours_refuses_to_interpolate():
    """원문이 8/12/16/20℃만 주므로 사이 값을 지어내지 않는다 — value=None과 함께
    인접 설정온도를 알려준다(케이스 t_target 10·15℃가 전부 여기 걸린다)."""
    r = e.heating_degree_hours("전주", 15)
    assert r["value"] is None and "보간" in r["reason"]
    assert r["lower"]["set_temp_c"] == 12 and r["upper"]["set_temp_c"] == 16
    assert e.heating_degree_hours("전주", 16)["value"] == 51273.0
    # 표에 없는 지역도 값을 만들지 않는다(인접 지점 대용은 판단성)
    assert e.heating_degree_hours("논산", 8)["value"] is None
    assert e.design_outdoor_temp("논산") is None


def test_degree_hours_default_is_not_in_the_table():
    """83차 확인 재고정: DEGREE_HOURS_DEFAULT=10,098은 이 표의 어느 값도 아니다
    (최근접 부산 8℃ 10,269). NIHHS 예시값이라는 [추정] 표기가 맞다."""
    vals = {round(v[i] * 1000, 1) for v in e.HEATING_DEGREE_HOURS_1000.values() for i in range(4)}
    assert e.DEGREE_HOURS_DEFAULT not in vals
    assert min(abs(x - e.DEGREE_HOURS_DEFAULT) for x in vals) == 171.0   # 부산 8℃와의 차


def test_weather_tables_not_wired_into_render_paths():
    """88차 도달성 — 케이스 t_min을 이 표로 바꾸면 난방부하가 움직인다(uminjae 1.29배).
    교체는 ★사용자 결정이라 렌더 연결 전까지 여기서 지킨다."""
    import os
    repo = os.path.dirname(os.path.abspath(__file__))
    for fname in ("build_site.py", "webapp.py", "render_report.py", "app.py",
                  "run_report.py", "render_chuncheon.py", "cases.py"):
        path = os.path.join(repo, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            body = f.read()
        for tok in ("design_outdoor_temp", "heating_degree_hours",
                    "DESIGN_OUTDOOR_TEMP_TAC", "HEATING_DEGREE_HOURS_1000"):
            assert tok not in body, (
                f"{fname}이 기상자료 표를 쓰기 시작했다 — 케이스 t_min 교체는 산출물 "
                f"수치를 움직이므로(uminjae 1.29배) 결정 후 이 테스트를 갱신할 것")


# ── 지역 커버리지 사실 고정 (89차) ──────────────────────────
# 근거_스마트팜스펙_난방설계조건_부재_20260913.md 4절.
# ★t_min 교체 결정의 핵심 제약이라 코드로 남긴다 — 커버리지가 변하면 결론도 변한다.
def test_tac_table_covers_only_part_of_the_notice_regions():
    """88차 TAC 표(69 관측지점)는 고시 REGION_DESIGN_LOAD의 일부만 덮는다.
    지역명이 **기상관측지점명**이라 행정구역과 1:1이 아니기 때문이다 —
    없는 지역은 인접 지점 대용이 필요하고 그 선택은 판단성이다.
    ⚠️ 일괄 교체가 성립하지 않는 이유가 여기 있다."""
    rl = set(e.REGION_DESIGN_LOAD)
    tac = set(e.DESIGN_OUTDOOR_TEMP_TAC)
    covered = rl & tac
    assert len(rl) == 172, len(rl)
    assert len(tac) == 69
    assert len(covered) == 66, sorted(covered)
    ratio = len(covered) / len(rl)
    assert 0.37 < ratio < 0.40, f"고시 지역 커버율이 변했다({ratio:.0%}) — 결론 재검토"
    # 스마트팜스펙 주요 지역 중 미보유 5종(89차 실측) — 실무 사례의 절반이 여기 걸린다
    for r in ("경주", "김해", "논산", "횡성", "예산"):
        assert r in rl, r
        assert r not in tac, f"{r}가 TAC 표에 생겼다 — 커버리지 결론을 갱신할 것"


def test_regression_case_sources_absent_from_corpus_is_pinned():
    """86·89차: ACTUALS 9건(92차 한수진·최선동 편입) 중 원채원·공주장원리·당진이상근은 스마트팜스펙에
    폴더도 파일명도 없다. 원채원은 이 리포의 **회귀 기준**인데 그렇다 —
    자료가 들어오면 이 테스트가 알려 준다(그때 provenance를 채울 수 있다)."""
    import os
    repo = os.path.dirname(os.path.abspath(__file__))
    root = os.path.join(repo, "스마트팜스펙")
    if not os.path.isdir(root):
        __import__("pytest").skip("스마트팜스펙 폴더 미보유(리포 밖 환경)")
    names = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in ("노지견적", "노지시방서", "대산온실")]
        names += [os.path.join(os.path.relpath(dp, root), f) for f in fns]
    blob = " ".join(names)
    actuals = {a[0] for a in e.ACTUALS}
    assert {"원채원", "공주장원리", "당진이상근"} <= actuals
    for k in ("원채원", "장원리", "당진", "이상근"):
        assert k not in blob, (
            f"'{k}' 자료가 스마트팜스펙에 들어왔다 — 케이스 provenance 갭"
            f"(87차 백로그)을 채울 수 있는지 확인하고 이 테스트를 갱신할 것")


# ── 견적참조 case 분류 오류 수정 (90차) ──────────────────────
# 근거_견적참조_농가문서_인벤토리_20260913.md 3절.
# NAME_PATTERNS가 ①괄호·대괄호 안 지명 ②앞 글자 먹기 ③문서종류를 사람 이름으로
# 오인한다. 정규식을 고치지 않고 CASE_OVERRIDES로 바로잡았다(패턴 수정은 전 말뭉치
# 분류를 바꿔 회귀 범위가 크다). classify()를 직접 불러 고정한다 — 인덱스 전수
# 스캔(148,424청크)보다 빠르고 의도를 정확히 짚는다.
def test_estimate_reference_case_overrides_fix_misclassification():
    """오분류 9건이 바로잡혔는가. 특히 이두희는 CAPEX_MAJOR 표본 12건 중 하나인데
    그 설계예산서·원가계산서가 '천안'(지명)으로 잡혀 있었다."""
    import os
    import pytest
    F = pytest.importorskip("build_document_chunks_full_v2")
    if not os.path.isdir("스마트팜스펙/견적참조"):
        pytest.skip("말뭉치 미보유(리포 밖 환경)")
    expect = {
        "__원가설계도서_이두희(천안) 20251028.pdf": "이두희",
        "원가계산서_이두희(천안) 20251028.pdf": "이두희",
        "설계도25 - 233 - [천안] 이두희 온실 검토서_251024 final.pdf": "이두희",
        "군산이명환농가-(커튼1중)-753평견적서.pdf": "이명환",
        "논산딸기백가은님75각 시공 견적서(최종).pdf": "백가은",
        "수현건설임미라님견적서.xls": "임미라",
        "스마트팜하우스(렉창)5연동견적서_최선동.xls": "최선동",
        "설계내역서_이동혁.pdf": "이동혁",
        # 이름이 없는 문서는 잘못된 이름 대신 미상으로 되돌린다
        "시공견적서.pdf": "견적참조-미상",
        "산출내역서(본)_250630.pdf": "견적참조-미상",
    }
    for fn, want in expect.items():
        p = os.path.join("스마트팜스펙", "견적참조", fn)
        if not os.path.exists(p):
            continue
        got = F.classify(p)
        assert got and got[0] == want, f"{fn}: case={got[0] if got else None} (기대 {want})"


def test_estimate_reference_case_overrides_only_cover_named_files():
    """추측 금지 — 오버라이드는 파일명에 이름이 명확한 것만 건드린다.
    값이 사람 이름(2~4자 한글)이거나 '견적참조-미상'이어야 하고, 대상 경로는
    전부 실재해야 한다(경로가 틀리면 오버라이드가 조용히 무시된다)."""
    import os
    import re
    import pytest
    F = pytest.importorskip("build_document_chunks_full_v2")
    ok = re.compile(r"^[가-힣]{2,5}$")
    for rel, case in F.CASE_OVERRIDES.items():
        assert case == "견적참조-미상" or ok.match(case), (rel, case)
        if os.path.isdir("스마트팜스펙"):
            assert os.path.exists(rel), f"오버라이드 경로가 없다(무시된다): {rel}"


def test_103cha_name_patterns_precision_over_recall():
    """103차 — `NAME_PATTERNS` 개정(90차 이월). **정밀도 우선**으로 보수화했다.

    개정은 둘뿐이다: ①`{2,4}`→`{2,3}`(앞 글자 먹던 greedy 제거) ②`NOT_A_NAME`
    거부(지명·문서종류·업체명). 더 많이 맞히려는 공격적 패턴은 시제품에서 새 오탐을
    만들고 기존 정답을 잃어 **채택하지 않았다** — 틀린 이름은 조용히 틀리지만
    None(미상)은 복구 가능하다.
    """
    import pytest
    F = pytest.importorskip("build_document_chunks_full_v2")
    g = F.guess_case_from_filename
    # ① greedy 제거 — 앞 글자를 먹지 않는다
    assert g("군산이명환농가-(커튼1중)-753평견적서.pdf") == "이명환"
    assert g("논산딸기백가은님75각 시공 견적서(최종).pdf") == "백가은"
    assert g("수현건설임미라님견적서.xls") == "임미라"
    # ② 지명·문서종류·업체명은 이름이 아니다 → 틀린 이름 대신 None
    for fn in ("시공견적서.pdf", "산출내역서(본)_250630.pdf",
               "__원가설계도서_이두희(천안) 20251028.pdf",
               "스마트팜하우스(렉창)5연동견적서_최선동.xls",
               "설계내역서_이동혁.pdf"):
        assert g(fn) is None, fn
    # 기존에 맞던 것은 그대로 맞아야 한다(재현율 손실 금지)
    assert g("최선동 - 평면도.pdf") == "최선동"
    assert g("[맹주연]_충청남도 천안시 서북구.pdf") == "맹주연"
    assert g("박규현 견적서.pdf") == "박규현"
    assert g("충남 서산(이준희) 도면.pdf") == "이준희"
    assert g("논산_백가은 대표님 최종도면_0616.pdf") == "백가은"
    # {2,3}의 근거: 이 말뭉치의 **사람 이름은 전원 3글자**다.
    #   유일한 예외 "한일그린텍"(5자)은 사람이 아니라 **업체 case명**이고
    #   폴더 기반으로 잡히므로 파일명 패턴의 대상이 아니다('한일'은 NOT_A_NAME).
    names = {v for v in F.CASE_OVERRIDES.values() if v != "견적참조-미상"}
    persons = {n for n in names if len(n) != 5}
    assert persons and all(len(n) == 3 for n in persons), sorted(persons)
    assert names - persons == {"한일그린텍"}, sorted(names - persons)
    assert "한일" in F.NOT_A_NAME
    # 104차 레드팀 F8 — 거부 목록에 **사문 항목**(캡처 {2,3}과 매치 불가한 4글자+)이
    #   없어야 한다. 있으면 "막았다"는 착각만 남는다.
    assert all(2 <= len(w) <= 3 for w in F.NOT_A_NAME),         sorted(w for w in F.NOT_A_NAME if not 2 <= len(w) <= 3)
    # 104차 레드팀 F8 — 반대 방향: 실제 케이스명이 거부 목록과 겹치면 영구 미상이 된다
    assert not (names & F.NOT_A_NAME), sorted(names & F.NOT_A_NAME)


def test_103cha_pattern_change_leaves_index_untouched():
    """🔴개정이 기존 인덱스를 건드리지 않는가 — 90차가 요구한 '전후 분포 대조'.

    패턴이 바뀌어 분류가 달라지는 파일이 **전부 `CASE_OVERRIDES`에 들어 있어야**
    한다. 그래야 오버라이드가 최종값을 결정하므로 148,424청크 인덱스가 불변이고
    재청킹이 필요 없다. 오버라이드 밖에서 하나라도 바뀌면 인덱스가 드리프트한다.
    """
    import os
    import re
    import pytest
    F = pytest.importorskip("build_document_chunks_full_v2")
    if not os.path.isdir("스마트팜스펙"):
        pytest.skip("말뭉치 미보유(리포 밖 환경)")
    # 개정 전 패턴을 재현해 대조한다(현재 패턴과 다른 점은 {2,3}·NOT_A_NAME뿐)
    old_pats = [re.compile(p.pattern.replace("{2,3}", "{2,4}")) for p in F.NAME_PATTERNS]

    def old_guess(bn):
        for pat in old_pats:
            m = pat.search(bn)
            if m:
                return m.group(1)
        return None

    ov = {os.path.basename(k) for k in F.CASE_OVERRIDES}
    drifted = []
    for root, dirs, files in os.walk("스마트팜스펙"):
        dirs[:] = [d for d in dirs if d not in F.EXCLUDE_DIRS]
        for fn in files:
            if old_guess(fn) != F.guess_case_from_filename(fn) and fn not in ov:
                drifted.append(os.path.join(root, fn))
    assert not drifted, (
        f"오버라이드 밖에서 분류가 바뀐다 — 인덱스 재생성이 필요하다: {drifted[:5]}")


def test_107cha_pumsem_source_points_into_the_repo_and_offset_is_measured():
    """107차 — 품셈 원문의 **소재와 쪽번호 대응**을 고정한다.

    두 가지가 반복해서 사람을 속였다. ①이 PDF가 리포 밖에 있다는 서술(102차가
    그렇게 적었고 104차 레드팀 F1이 잡았다) ②`git ls-files | grep 품셈`이 0건을
    내는 것(git이 비ASCII 경로를 8진 이스케이프로 출력하기 때문 — `core.quotepath`).
    실제로는 리포 안에 있고, 107차에 인쇄↔PDF 오프셋을 **−24로 실측**했다
    (10쪽 꼬리말 글리프 역해독, 글리프→숫자 대응이 모순 없이 하나로 결정).

    이 테스트가 깨지면 표기가 다시 흐려진 것이다 — 값 문제가 아니라 **재현 경로**
    문제이므로 라벨을 되돌릴 것.

    🔴108차 정정: 107차는 오프셋을 `p.15~16`에도 곱해 "= PDF 39~40"이라 확정했는데
    **틀렸다**. 그 라벨은 처음부터 PDF 쪽번호였다(해당 내용은 PDF 15~16의
    요약보고서에 있고, 그 구간엔 쪽 꼬리말이 아예 없다). **오프셋을 알게 됐다고
    모든 기존 라벨이 인쇄 쪽번호인 것은 아니다** — 라벨의 종류는 따로 확인해야
    한다. 근거: 근거_7절정합성감사_품셈오프셋실측_20260914.md(오프셋),
            근거_품셈요약보고서_원문확인_20260914.md(원문 육안 대조)
    """
    import os as _o
    import re as _re
    repo = _o.path.dirname(_o.path.abspath(__file__))

    # 원문이 실제로 리포 안에 있다(이 사실이 라벨의 전제다)
    pdf = _o.path.join(repo, "시설평가", "202201_스마트팜 표준화_품셈.pdf")
    assert _o.path.exists(pdf), "품셈 원문이 리포에서 사라졌다 — 인용의 전제가 깨진다"

    # 불변식: 품셈 파일명은 **언제나** 리포 내 경로로만 등장한다.
    #   ⚠️107차 초판 가드는 축약형(`E:\이암허브\...\`)만 막았다가
    #   **전체 경로 형태 1건을 놓쳤다**(`…\2025\스마트팜견적타당성\…`).
    #   경로 문자열을 열거하는 대신 **파일명의 앞자리**를 고정한다 — 어떤 형태의
    #   외부 경로가 들어와도 걸린다(106차 좁은 glob과 같은 실패를 반복하지 않는다).
    name = "202201_스마트팜 표준화_품셈.pdf"
    for fname in ("smartfarm_engine.py", "엔진데이터_레지스트리.json"):
        src = open(_o.path.join(repo, fname), encoding="utf-8").read()
        hits = [m.start() for m in _re.finditer(_re.escape(name), src)]
        assert hits, f"{fname}이 품셈 원문 인용을 통째로 잃었다"
        for h in hits:
            assert src[max(0, h - 5):h] == "시설평가/", (
                f"{fname} 오프셋 {h}: 품셈이 리포 내 경로(`시설평가/`) 없이 "
                f"인용됐다 — 리포 밖 자료로 오해되면 아무도 원문을 열어보지 "
                f"않는다(102차가 그 오해 위에서 쪽번호를 흐렸고 104차 F1이 잡았다)")

    # 실측 오프셋(인쇄 = PDF − 24)이 기록돼 있는가
    reg = open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8").read()

    # 🔴108차 — 107차가 여기 박아 뒀던 `인쇄 p.15~16 = PDF 39~40`은 **틀렸다**.
    #   원문을 렌더링해 보니 PDF 39~40은 [표 2-3] 스마트팜 도입 성과조사이고,
    #   해당 내용은 PDF 15~16(요약보고서)에 있다. 앵커를 **반대 방향으로** 건다 —
    #   그 표기가 되살아나면 실패한다.
    #   이력 보존이 이 리포의 관례라 **정정문 안의 인용은 허용**한다 —
    #   금지하는 것은 `정정` 표시 없이 살아 있는 라벨이다.
    for m in _re.finditer("인쇄 p.15~16", reg):
        near = reg[max(0, m.start() - 300):m.start()]
        assert "108차 정정" in near, (
            "`인쇄 p.15~16`이 정정 표시 없이 살아 있다 — 그 구간은 요약보고서라 "
            "**쪽번호가 인쇄되지 않는다**(108차 원문 육안 확인). "
            "`PDF p.15~16(요약보고서 — 인쇄 쪽번호 없음)`으로 적을 것")
    assert "PDF p.15~16" in reg, "요약보고서 구간의 PDF 쪽 표기가 사라졌다"
    eng = open(_o.path.join(repo, "smartfarm_engine.py"), encoding="utf-8").read()
    assert "인쇄 = PDF − 24" in eng, "품셈 오프셋 실측 기록이 사라졌다"


def test_107cha_section7_marks_what_later_cycles_overturned():
    """107차 — 7절이 **닫힌 과제를 열린 것처럼** 보이게 두지 않는다.

    7절은 해결 이력 로그라 시간이 지나면 낡는다. 65차가 문서 전체를 실제 상태와
    대조하면서 7절만 **명시적으로 건너뛰었고**(그 차수의 「검증하지 않은 것」),
    그 뒤 68·77·99·101·105·106차가 바로 그 항목들을 움직였다.

    여기서 고정하는 것은 **정정 주석의 존재**다 — 원문 서술은 지우지 않는 것이
    이 리포의 관례(31차)이므로, 낡은 문장 옆에 현재 상태가 반드시 붙어 있어야
    한다. 주석이 사라지면 7절은 다시 사람을 속인다.
    """
    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    doc = open(_o.path.join(repo, "작업지시서.md"), encoding="utf-8").read()
    i = doc.index("## 7. 미해결 이슈")
    j = doc.index("## 8. 다음 세션", i)
    sec = doc[i:j]

    # 후행 차수가 뒤집은 자리마다 정정 주석이 붙어 있는가
    for probe, why in (
        ("99차에 5.7로 확정", "u_design 미해결 서술(99차가 닫았다)"),
        ("결론은 \"둘 다 아니다\"였다", "핫박스 vs 현장 판단(99차가 제3경로로 갔다)"),
        ("0.85 → 0.70으로 교체", "FR_TABLE 이중커튼 값(68차가 바꿨다)"),
        ("품셈 PDF는 리포 안에 있다", "품셈 소재(104차 F1·107차 실측)"),
        ("커밋 **112건**", "미커밋 유실 리스크(65차에 해소됐다)"),
    ):
        assert probe in sec, (
            f"7절에서 `{probe}` 정정이 사라졌다 — {why}. 원문은 보존하되 현재 상태를 함께 적을 것(31차 관례)")

    # 이 절이 현재 지도가 아니라는 안내(열린 것은 14절)
    assert "14절" in sec, "7절이 14절로 넘기는 포인터를 잃었다 — 7절은 이력 로그다"


def test_108cha_pumsem_summary_section_numbers_are_verified_against_the_page():
    """108차 — 원문을 **열어 보고** 확인한 것만 확정으로 적는다.

    107차의 실패는 방법이 아니라 **순서**였다: 오프셋을 측정한 뒤 그 오프셋을
    기존 라벨에 곱해 "확정"이라 적었고, 정작 **그 쪽을 열어보지 않았다**.
    108차는 pypdfium2로 렌더링해 육안 대조했다.

    여기서 고정하는 것은 두 가지다.
      ① 원문에서 직접 읽은 네 수치(4,196 / 3,487 / 3,509 / 3,009 백만원/ha)
      ② 정부지원 기준단가(3,000 / 1,500)는 **상수로 승격되지 않았다** —
         정책 기준단가는 1절이 정한 시세성이라 주입만 받는다.
    """
    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8").read()

    # ① 원문 육안 대조로 확인된 수치가 기록에 남아 있는가
    for v in ("4,196", "3,487", "3,509", "3,009"):
        assert v in reg, f"품셈 요약보고서 대조 수치 {v}가 사라졌다(108차 육안 확인)"
    assert "108차" in reg, "108차 육안 대조 기록이 사라졌다"

    # ② 정부지원 기준단가는 **엔진 상수가 아니다**(시세성 — 주입만 받는다)
    #   ⚠️23회차 레드팀 C3 — 초판은 `dir()` 모듈 레벨 **스칼라만** 봐서, 가장 자연스러운
    #     승격 경로인 dict(`TOTAL_PYEONG_PRICE` 등) 안을 전혀 보지 못했다. 동시에 단위와
    #     무관한 아무 상수나 3000이면 잘못된 메시지로 실패시키는 과잉이기도 했다.
    #     이제 **백만원/ha 단가를 담는 컨테이너까지 재귀로** 보되, 판정은 값이 아니라
    #     **그 값이 정책 기준단가로 등재됐는가**로 한다.
    import smartfarm_engine as _e

    def _walk(v, path, depth=0):
        if depth > 4:
            return
        if isinstance(v, dict):
            for k, sub in v.items():
                yield from _walk(sub, f"{path}[{k!r}]", depth + 1)
        elif isinstance(v, (list, tuple)):
            for i, sub in enumerate(v):
                yield from _walk(sub, f"{path}[{i}]", depth + 1)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            yield path, v

    #   ⚠️원 단위 3,000,000,000·1,500,000,000은 뺀다 — `SUPERVISION_FEE_RATE_TABLE`의
    #     **공사비 구간 경계**(30억·15억)와 숫자가 같을 뿐 전혀 다른 양이다.
    #     23회차 레드팀 재검증에서 이 가드가 낸 유일한 거짓 양성이었다.
    SUSPECT = (3000, 1500)   # 백만원/ha 단위로 등재되는 경우만 본다
    hits = []
    for attr in dir(_e):
        if attr.startswith("_") or attr.upper() != attr:
            continue                      # 상수 명명 규약(대문자)만 본다
        for path, val in _walk(getattr(_e, attr, None), attr):
            if val in SUSPECT:
                hits.append((path, val))
    assert not hits, (
        f"정부지원 기준단가(유리 3,000 / 비닐 1,500 백만원/ha)로 보이는 값이 엔진 상수에 "
        f"들어왔다: {hits}. 정책 기준단가는 1절이 정한 **시세성**이라 인자 주입만 허용되고, "
        f"2021-12 기준이라 현행 여부도 확인할 수 없다 — 승격은 ★사용자 결정 사안이다. "
        f"(오탐이라면 이 가드가 아니라 SUSPECT 목록을 좁힐 것)")

def test_109cha_pumsem_cost_sheet_reproduces_and_transcription_is_fixed():
    """109차 — `<그림 7-18>` 공사원가계산서가 **스스로 재현되는지**로 전사를 검증한다.

    108차까지 이 리포는 유리 총공사비를 `3,487,006,776`으로 적어 왔는데 원문은
    **`3,487,006,773`**이다. 확대해 읽은 것만으로는 오독 가능성이 남으므로,
    원가계산서의 **계층 산식을 그대로 계산해** 도급액이 나오는지 확인한다 —
    맞아떨어지면 읽은 값들이 서로를 검증한다.

    ⚠️ 이 수치들은 **교차검증용 서술**이지 엔진 상수가 아니다. 여기서 고정하는
    것은 기록의 정확성이다. 근거: 근거_요약본6.2_본문출처추적_20260914.md
    """
    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))

    # <그림 7-18>(인쇄 p.163) 공사원가계산서 — 원문에서 읽은 값
    gye = 2_852_203_252          # 계
    ilban = 171_132_195          # 일반관리비 = 계 * 6%
    iyun = 146_670_711           # 이윤 = (노무비+경비+일반관리비) * 15%
    gonggeup = 3_170_006_158     # 공급가액
    vat = 317_000_615            # 부가가치세 = 공급가액 * 10%
    dogeup = 3_487_006_773       # 도급액 = 총공사비

    # 원문 비고란의 산식이 그대로 성립하는가(절사 기준)
    assert int(gye * 0.06) == ilban, (gye * 0.06, ilban)
    assert gye + ilban + iyun == gonggeup, (gye + ilban + iyun, gonggeup)
    assert int(gonggeup * 0.1) == vat, (gonggeup * 0.1, vat)
    assert gonggeup + vat == dogeup, (gonggeup + vat, dogeup)

    # <그림 7-19>(인쇄 p.164) 비닐 공종별 집계표 — 계가 성분 합과 일치하는가
    assert 1_691_276_568 + 438_555_609 + 42_800_490 == 2_172_632_667

    for fname in ("smartfarm_engine.py", "엔진데이터_레지스트리.json"):
        src = open(_o.path.join(repo, fname), encoding="utf-8").read()
        assert "3,487,006,773" in src, (
            f"{fname}에서 정정된 유리 총공사비가 사라졌다")

    # 🔴23회차 레드팀 C2 — 2개 파일만 돌던 스캔을 **리포 전수**로 바꾼다.
    #   초판은 `통합작업체계_…md`에 정정 없이 남은 오기를 통과시켰다.
    bad = _uncorrected_hits("3,487,006,776")
    assert not bad, (
        f"전사 오기 `3,487,006,776`이 정정 표시 없이 남아 있다: {bad} "
        f"— 원문은 `…773`이다(109차 계층 검산·23회차 원문 재확인)")


def test_109cha_source_mapping_is_recorded():
    """109차 — 요약본 6.2가 **본문 어디서 왔는지**를 기록에 고정한다.

    108차의 「검증하지 않은 것」이 바로 이 항목이었다. 매핑이 사라지면 다음 사람이
    다시 300쪽을 뒤져야 한다.
    """
    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8").read()
    for probe, why in (
        ("제7장 제3절 2", "요약본 6.2의 본문 출처"),
        ("제4장 제2절 4", "표준품셈 축(4,196/3,509)의 1차 출처"),
        ("첨단온실신축지원사업", "정부지원 기준단가 3,000/1,500의 사업명"),
        ("표 7-11", "비닐 연도별 표 — 원문 결함을 기록해 둔 자리"),
    ):
        assert probe in reg, f"109차 출처 매핑에서 `{probe}`가 사라졌다 — {why}"

def test_110cha_pumsem_chapter_range_and_missing_vinyl_cost_sheet():
    """110차 — 인용의 **이름**과 **부재 사실**을 함께 고정한다.

    ①범위: 이 리포는 오래 `제7장(원문 인쇄 p.138~162)`이라 적어 왔는데 목차를 보면
      **제7장은 인쇄 p.109~167**이고 138~162는 제2·3절(품셈 산정)의 범위다.
      전사한 64개 품목이 온 자리는 맞았으나 **이름이 틀렸다** — 다음 사람이 장 전체를
      본 줄 알면 안 된다.

    ②부재: 비닐 `공사원가계산서`는 **보고서에 인쇄되지 않았다**(인쇄 p.164는 상·하단
      둘 다 「공종별집계표」, 제7장은 p.167에서 끝, 부록 p.273은 표지뿐).
      **이 사실이 기록에서 사라지면 108차 [확인요망]을 또 찾아 나서게 된다.**

    근거: 근거_비닐원가계산서_부재확정_20260914.md
    """
    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    for fname in ("smartfarm_engine.py", "엔진데이터_레지스트리.json"):
        src = open(_o.path.join(repo, fname), encoding="utf-8").read()
        assert "p.109~167" in src, (
            f"{fname}에서 제7장의 **실제 범위**(인쇄 p.109~167)가 사라졌다 — "
            f"`p.138~162`는 제2·3절이지 장 전체가 아니다(110차 목차 확인)")
        assert "인쇄되지 않았다" in src, (
            f"{fname}에서 비닐 공사원가계산서 **부재** 기록이 사라졌다 — "
            f"없다는 사실을 적어 두지 않으면 같은 탐색을 반복한다")

    # 🔴23회차 C2 — 장 범위 오기도 리포 전수로 본다(초판은 2파일만 돌았다)
    bad = _uncorrected_hits("제7장(원문 printed p.138~162)")
    bad += _uncorrected_hits("제7장(원문 인쇄 p.138~162)")
    assert not bad, (
        f"`제7장(p.138~162)`을 **장 범위로** 쓰는 표기가 정정 없이 남아 있다: {bad} "
        f"— 제7장은 인쇄 p.109~167이고 138~162는 제2·3절이다")

    # 🔴23회차 C4/R6 — 부재 단정의 **검색 범위 병기**가 함께 살아 있어야 한다.
    #   초판은 "인쇄되지 않았다"만 요구해서, 부재 단정의 유일한 방어선인
    #   "제6장·부록 92쪽" 한계 문장을 지워도 green이었다(루브릭 R6 취지와 정반대).
    reg = open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8").read()
    for probe in ("제6장(인쇄 p.91~108)", "92쪽", "미열람"):
        assert probe in reg, (
            f"부재 단정의 검색 범위 병기에서 `{probe}`가 사라졌다 — 루브릭 R6는 "
            f"\"병기 없는 부재 단정은 그 자체로 발견\"이라고 정한다. 110차는 이 92쪽을 "
            f"열지 않고 부재를 단정했고 23회차가 사후에 열어 채웠다")


def test_110cha_vinyl_chart_reconciles_with_table_7_11():
    """110차 — 인쇄되지 않은 원가계산서가 **존재했음**을 계산으로 뒷받침한다.

    비닐 차트(원가계산서 기준 6항목)와 [표 7-11](직접비 3항목 + 재비율)은 집계
    레벨이 다른데도 총액이 맞아떨어진다 — 즉 차트는 실재한 원가계산서에서 왔고
    인쇄만 누락된 것이다. 이 정합이 깨지면 둘 중 하나를 잘못 읽은 것이다.
    """
    # 🔴23회차 레드팀 C1 — 초판은 **파일을 하나도 읽지 않고** 테스트 내부 리터럴만
    #   계산했다(`assert 843-477 == 366`은 상수 접힘이라 항상 참). 레지스트리의 차트
    #   값을 훼손해도 PASS함을 변이 주입으로 확인했다. 이제 **기록에서 읽어** 검산한다 —
    #   "테스트를 늘렸다"가 "보호를 늘렸다"는 뜻이 아니라는 것이 이 회차의 교훈이다.
    import os as _o
    import re as _re
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8").read()

    # 기록에 남은 차트 합산식에서 숫자를 그대로 뽑아 온다
    m = _re.search(r"1,691\+(\d+)\+(\d+)\+(\d+)\+(\d+)\+(\d+) = \*\*([\d,]+)\*\*", reg)
    assert m, "레지스트리에서 비닐 차트 합산식을 찾지 못했다(기록이 지워졌거나 형식이 바뀌었다)"
    parts = [1691] + [int(x) for x in m.groups()[:5]]
    total = int(m.group(6).replace(",", ""))
    assert sum(parts) == total, (parts, total)      # 기록된 합이 실제로 맞는가
    assert total == 3009, total

    # [표 7-11] 재비율 역산이 기록된 값과 ±1 안에서 만나는가
    m2 = _re.search(r"\((\d+)−(\d+)\)\+\((\d+)−(\d+)\)\+(\d+)\+(\d+)\+(\d+) = "
                    r"\*\*(\d+)\*\*", reg)
    assert m2, "레지스트리에서 재비율 역산식을 찾지 못했다"
    g = [int(x) for x in m2.groups()]
    assert (g[0] - g[1]) + (g[2] - g[3]) + g[4] + g[5] + g[6] == g[7], g
    assert abs(g[7] - 837) <= 1, g[7]

    # 🔴비닐 노무비만 어긋난다는 관찰이 기록에 살아 있는가([확인요망]의 근거)
    assert "702−473" in reg and "228" in reg, (
        "비닐 노무비 229 vs 원문 228 불일치 기록이 사라졌다 — 이것이 [확인요망]의 근거다")

def test_113cha_pumsem_items_were_verified_against_the_source():
    """113차 — 64종 **전수** 원문 대조 결과를 고정한다.

    23회차 레드팀이 「확인 불가」에 남긴 최대 미확인이었다(61종 미대조).
    인쇄 p.138~162 25쪽을 렌더링해 육안 대조했고 불일치 0건이었다.

    여기서 막는 것은 **구조의 침식**이다 — 전수 대조가 성립하려면 64종·9공종이
    유지돼야 하고, 값이 바뀌면 대조 기록이 거짓이 된다.
    """
    import os as _o
    import collections as _c
    items = e.PUMSEM_ITEMS
    assert len(items) == 64, f"64종 전수 대조 기록과 어긋난다: {len(items)}종"

    cnt = _c.Counter(x.category for x in items)
    assert cnt == {
        "철골공사": 9, "온실피복공사": 4, "천창개폐장치공사": 13,
        "알루미늄공사": 6, "수평스크린공사": 13, "측벽스크린공사": 6,
        "행잉거터공사": 6, "철골공사(비닐·파이프자재)": 5, "온실피복공사(비닐)": 2,
    }, cnt

    # 🔴원문이 `철근공`인 4건 — 91차는 3건으로 적었고 113차가 삼각대를 찾았다.
    #   "오기로 보이니 고치자"가 반복될 자리라 원문 사실로 못 박는다.
    steel_bar = sorted(x.name for x in items
                       if "철근공" in x.labor_per_unit)
    assert steel_bar == sorted([
        "예인로라·가이드로라", "스크린바가스켓", "스크린체인웨이트", "삼각대",
    ]), (f"원문이 `철근공`으로 적은 품목이 바뀌었다: {steel_bar}. "
         f"원문 인쇄 p.152·153·154·158에서 직접 확인했다 — 임의로 `철골공`으로 "
         f"고치지 말 것(91차·113차)")

    # 품목명 재사용 4쌍은 공종마다 값이 **다르다** — (공종,품목명) 키 설계의 근거
    by = {(x.category, x.name): x for x in items}
    for a, b, label in (
        (("천창개폐장치공사", "모터설치대"), ("수평스크린공사", "모터설치대"), "모터설치대"),
        (("철골공사", "턴버클"), ("행잉거터공사", "턴버클"), "턴버클"),
        (("수평스크린공사", "스크린개폐모터"), ("측벽스크린공사", "스크린개폐모터"),
         "스크린개폐모터"),
    ):
        assert a in by and b in by, (a, b)
        assert by[a].labor_per_unit != by[b].labor_per_unit, (
            f"{label}: 두 공종의 값이 같아졌다 — 원문은 서로 다르게 적는다. "
            f"품목명 단독 키로 되돌리면 한쪽이 덮인다(91차·113차)")

    # 대조 기록이 레지스트리에 살아 있는가
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8").read()
    for probe in ("64종 원문 전수 대조", "불일치 0건", "삼각대"):
        assert probe in reg, f"113차 전수 대조 기록에서 `{probe}`가 사라졌다"

    # 🔴엔진에 없는 원문 계수 3종 — 이 값들이 조용히 상수로 들어오지 않았는지
    #   (비용 산정은 이 엔진의 스코프 밖이다 — 등재는 ★사용자 결정)
    assert not hasattr(e, "PUMSEM_TOOL_LOSS_RATE"), (
        "공구손료율(인력품의 2~3%)이 상수로 등재됐다 — 원문은 **품목 단위로 다르고** "
        "일부 품목엔 아예 없다. 단일 상수로 뭉치면 원문이 말하지 않은 것을 말하게 된다"
        "(113차). 등재는 ★사용자 결정 사안이다")

def test_114cha_pumsem_scope_limits_are_recorded():
    """114차 — 품셈의 **적용 전제**를 기록에 고정한다.

    64계수가 원문과 일치한다는 것(113차)과, 그 계수를 **어디에 쓸 수 있는가**는
    다른 문제다. 제7장 제1절이 세 가지를 규정한다 —
      ① 이 품셈은 예정가격 산정의 **참고자료**다(구속 기준이 아니다)
      ② 계수는 **벤로타입 1헥타르** 설계모델 기준이다
      ③ 자재 단가는 품셈이 정하지 않는다(지정기관 공표가격·국가계약법 시행규칙 7조)

    ③은 이 리포 1절의 `시세성 값은 주입만 받는다`와 같은 구조다 — 원문 근거가
    사라지면 그 원칙이 관례로만 남는다.
    """
    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8").read()
    for probe, why in (
        ("참고자료", "①이 품셈은 구속 기준이 아니라 참고자료다"),
        ("벤로타입", "②64계수의 설계모델 전제"),
        ("1헥타르", "②64계수의 규모 전제"),
        ("국가계약법 시행규칙", "③자재 단가는 품셈이 정하지 않는다"),
        ("8시간", "ⓒ장비 시간 기준의 일괄 규정 위치"),
    ):
        assert probe in reg, (
            f"품셈 적용 전제에서 `{probe}`가 사라졌다 — {why}. "
            f"전제 없이 계수만 남으면 벤로형이 아닌 규격에 그대로 쓰게 된다(114차)")

    # 정부지원 기준단가는 세 곳에서 교차 확인됐으나 여전히 상수가 아니다(시세성)
    import smartfarm_engine as _e
    assert not hasattr(_e, "GOV_SUPPORT_UNIT_PRICE"), (
        "정부지원 기준단가(3,000/1,500 백만원/ha)가 상수로 등재됐다 — 원문 세 곳"
        "(인쇄 p.72·109·171)에서 확인됐지만 **정책 기준단가는 시세성**이고 "
        "2021-12 기준이라 현행 여부를 확인할 수 없다. 등재는 ★사용자 결정 사안이다")

def test_115cha_pumsem_standard_design_is_recorded():
    """115차 — 품셈 표준설계의 **면적·형식 구성**을 기록에 고정한다.

    114차는 p.109의 총괄 서술만 읽고 64계수 전부의 전제를 `벤로타입 1헥타르`라
    적었다. p.112를 열어 보니 비닐은 **연동형**이고, `1헥타르`도 유리 9,792㎡
    (0.98ha)·비닐 10,106㎡다. 요약만 읽고 전제를 단정한 자리라 사실을 못 박는다.

    특히 두 값은 이 리포가 오래 다툰 문제에 직접 걸린다 —
      · 관리동 1,152㎡(11.8%)가 **포함**돼 있다(TOTAL_PYEONG_PRICE 괴리 원인 후보)
      · 방풍실 314㎡는 **비닐에만** 있고 유리↔비닐 면적차 전부다(ACTUALS 방풍 논쟁)
    """
    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8").read()

    for probe, why in (
        ("연동형", "비닐온실의 설계모델(벤로타입이 아니다)"),
        ("9,792", "유리온실 연면적 — 1ha가 아니라 0.98ha"),
        ("10,106", "비닐온실 연면적"),
        ("방풍실", "비닐에만 있는 314㎡ — ACTUALS 방풍 논쟁과 직결"),
        ("1,152", "관리동 면적 — 표준설계에 포함돼 있다"),
    ):
        assert probe in reg, (
            f"품셈 표준설계 제원에서 `{probe}`가 사라졌다 — {why}. "
            f"요약(p.109)만 읽으면 `벤로타입 1헥타르`로 단정하게 된다(114차가 그랬다)")

    # 면적 구성이 실제로 맞아떨어지는가 — 기록이 자기정합인지 계산으로 확인
    유리 = 4608 + 4032 + 1152
    assert 유리 == 9792, 유리
    assert 유리 + 314 == 10106, 유리 + 314      # 차이 전부가 방풍실
    assert round(1152 / 9792 * 100, 1) == 11.8   # 관리동 비중

    # 표준설계 면적은 **엔진 상수가 아니다**(케이스 데이터가 아니라 원문 제원)
    import smartfarm_engine as _e
    for attr in ("PUMSEM_STANDARD_AREA_M2", "PUMSEM_STANDARD_DESIGN"):
        assert not hasattr(_e, attr), (
            f"{attr}: 품셈 표준설계 제원이 엔진 상수로 올라왔다 — 이것은 원문의 "
            f"설계모델이지 이 리포의 케이스 데이터가 아니다. 등재는 ★사용자 결정이다")

def test_116cha_pumsem_observation_source_is_recorded():
    """116차 — 64계수가 **어디서 관측됐는지**를 기록에 고정한다.

    품셈은 부여군 가설유리 온실 신축사업의 일일 실측에서 나왔다(🔴119차 정정: 공사일보는
    이 한 현장뿐이나 **품셈 조사 현장은 2곳**이다 — 함평 나비엑스포내 전시온실이 있다) —
    원문이 `매공마다 조사인력을 파견하여 투입인원 장비등을 조사`라 적는다.
    총 2,040 인·일이 전부이고, 그 사실이 계수의 **정밀도 한계**를 규정한다.

    🔴 118차 정정 2건: 종전 `부여군 가월리`는 **오독**이고(117차 확인),
    종전 총량 `2,033`은 **05-24 자 누계**였다 — 83쪽 전수 확인에서 최종
    05-25 일보의 계가 **2,040**(보통인부 353이 아니라 **360**)임을 읽었다.

    그리고 공사일보에는 `철근공`이 별도 직종으로 48 인·일 관측돼 있다 —
    품셈의 `철근공` 4건을 `오기로 보이니 철골공으로 고치자`고 할 근거가
    이것으로 더 약해진다(91차 의심 → 113차 원문 확인 → 116차 관측 확인).
    """
    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8").read()

    for probe, why in (
        ("부여군 가설유리", "관측 현장 — 단일 현장이다(117차 정정: `가월리`가 아니라 `가설유리`)"),
        ("2,040", "총 투입 인·일(계수의 표본 크기 — 118차 정정, 2,033은 05-24 자 누계)"),
        ("온실공", "품셈 `철골공`의 실체"),
        ("철근공 48", "`철근공`이 관측된 별개 직종이라는 근거"),
        ("수량 열이 없다", "계수 유도를 재현할 수 없는 이유(분모 부재)"),
    ):
        assert probe in reg, (
            f"공사일보 관측 기록에서 `{probe}`가 사라졌다 — {why}. "
            f"이것이 없으면 64계수가 어디서 왔는지 다시 300쪽을 뒤지게 된다")

    # 원문에서 읽은 누계가 자기정합인가 — 직종 14종 합 = 계
    labor = [517, 2, 12, 132, 48, 23, 77, 11, 42, 166, 243, 276, 360, 131]
    assert sum(labor) == 2040, sum(labor)
    assert sum([90, 25, 1, 181, 343]) == 640

    # 관측 총량은 **엔진 상수가 아니다**(품셈의 근거이지 케이스 데이터가 아니다)
    import smartfarm_engine as _e
    for attr in ("PUMSEM_OBSERVED_LABOR_DAYS", "PUMSEM_SURVEY_SITE"):
        assert not hasattr(_e, attr), (
            f"{attr}: 공사일보 관측 총량이 엔진 상수로 올라왔다 — 이것은 품셈이 "
            f"만들어진 근거이지 이 리포가 계산에 쓰는 값이 아니다(★사용자 결정)")

def test_117cha_trade_to_item_mapping_and_sample_scope():
    """117차 — 직종↔품목 매핑과 **관측 표본의 실제 크기**를 고정한다.

    116차는 `2,033 인·일이 계수의 표본 크기`라 적었다. 직종을 품목에 매핑해 보면
    그중 **388(19.0%)은 품셈 범위 밖**(기초·가설·설비)이고 실제 표본은 **1,652**다
    (🔴118차 정정: 총량이 2,033이 아니라 **2,040**이라 품셈 범위 안이 1,645가 아니라
    **1,652**다 — 보통인부 353→360. 범위 밖 388은 불변).

    그리고 유리공·내장공은 각각 **2품목에만** 쓰여 역산에 쓸 수 있는 유일한 통로다 —
    이 구조가 깨지면 부분 검산(117차 A/B)의 전제가 사라진다.
    """
    import collections as _c
    by = _c.defaultdict(list)
    for x in e.PUMSEM_ITEMS:
        for job in x.labor_per_unit:
            by[job].append((x.category, x.name))

    # 품셈에 등장하는 직종은 7종뿐이다
    assert set(by) == {
        "철골공", "조력공", "특별인부", "보통인부",
        "철근공", "유리공", "내장공",
    }, sorted(by)

    # 역산 통로 — 이 둘만 2품목이고 모두 ㎡ 단위다
    assert len(by["유리공"]) == 2, by["유리공"]
    assert len(by["내장공"]) == 2, by["내장공"]
    glass = {n for _, n in by["유리공"]}
    inner = {n for _, n in by["내장공"]}
    assert glass == {"천창유리", "측면강화유리"}, glass
    assert inner == {"천장우레탄판넬", "샌드위치판넬"}, inner

    # 관측 표본의 구분 — 품셈 범위 안 1,645 / 밖 388
    inside = 517 + 48 + 42 + 166 + 243 + 276 + 360
    outside = 2 + 12 + 132 + 23 + 77 + 11 + 131
    assert inside == 1652 and outside == 388 and inside + outside == 2040

    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8").read()
    for probe, why in (
        ("가설유리", "공사명 — `가월리`가 아니다(117차 정정)"),
        ("1,652", "품셈 범위 안 표본(118차 정정 — 1,645도 2,040 전체도 아니다)"),
        ("불성립", "유리공 역산이 맞지 않는다는 기록"),
    ):
        assert probe in reg, (
            f"117차 역산 기록에서 `{probe}`가 사라졌다 — {why}")

def test_118cha_daily_log_full_read_splits_glass_and_interior():
    """118차 — 부록1 공사일보 **83쪽 전수** 확인이 역산 두 건을 품목별로 가른다.

    117차는 유리공 166을 **두 품목 합산**으로 보고 195.8 vs 166(+18%)을 `불성립`이라
    적었다. 일별 투입을 전수로 읽으면 **측면강화유리 30 + 천창유리 136**으로 갈리고,
    두 오차가 **서로 반대 방향**이었음이 드러난다 — 합산이 그것을 가렸다.

    내장공 42도 **외벽 18 + 천장 24**로 갈리고, 천장 역산 1,200㎡는 도면의 관리동
    지붕 1,152㎡와 **4.2% 안에서** 맞는다(117차의 합산 설명보다 강하다).

    이 분해가 기록에서 사라지면 `역산은 안 된다`는 117차 결론만 남아, 실제로는
    **품목별로는 닿았다**는 사실을 다시 83쪽에서 찾아내야 한다.
    """
    # 유리공 — 누계의 단조성이 구간 밖 0을 증명한다(01-19 누계 6, 최종 166)
    side_glass = 6 * 5        # 01-19~01-23 측면강화유리
    roof_glass = 8 * 17       # 02-01~02-23 천창유리
    assert side_glass == 30 and roof_glass == 136
    assert side_glass + roof_glass == 166, "유리공 누계와 어긋난다"

    # 내장공 — 01-25~01-27 외벽 / 01-28~01-30 천장
    wall_panel = 6 * 3
    roof_panel = 8 * 3
    assert wall_panel == 18 and roof_panel == 24
    assert wall_panel + roof_panel == 42, "내장공 누계와 어긋난다"

    # 계수로 역산한 물량 — 계수는 엔진에서 읽는다(리터럴 산술 금지, 23회차 C1)
    coef = {(x.category, x.name): x.labor_per_unit
            for x in e.PUMSEM_ITEMS}
    c_side = coef[("온실피복공사", "측면강화유리")]["유리공"]
    c_roof = coef[("온실피복공사", "천창유리")]["유리공"]
    c_wall = coef[("온실피복공사", "샌드위치판넬")]["내장공"]
    c_ceil = coef[("온실피복공사", "천장우레탄판넬")]["내장공"]
    assert (c_side, c_roof, c_wall, c_ceil) == (0.01, 0.02, 0.02, 0.02)

    assert round(side_glass / c_side) == 3000
    assert round(roof_glass / c_roof) == 6800
    assert round(wall_panel / c_wall) == 900
    assert round(roof_panel / c_ceil) == 1200

    # 천장 판넬 역산이 도면(관리동 지붕 16M×72M)과 4.2% 안에서 맞는다 — 검산 A의 핵심
    gwanri = 16 * 72
    assert gwanri == 1152
    assert round((roof_panel / c_ceil - gwanri) / gwanri * 100, 1) == 4.2

    # 비닐 7종은 실재하고(값 불변), 그 1차 관측자료가 부록1에 없다는 것이 118차 발견이다
    vinyl = [x for x in e.PUMSEM_ITEMS if "비닐" in x.category]
    assert len(vinyl) == 7, [x.name for x in vinyl]

    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8").read()
    for probe, why in (
        ("2,040", "최종 누계 — 2,033은 05-24 자였다(118차 정정)"),
        ("168장", "전수 범위 — 83쪽 표본이 아니다"),
        ("측면강화유리 30", "유리공 분해 — 117차 검산 B를 가르는 값"),
        ("비닐온실 공사일보는", "비닐 7종의 1차 관측자료 부재(R6 병기 후 단정)"),
    ):
        assert probe in reg, (
            f"118차 전수 확인 기록에서 `{probe}`가 사라졌다 — {why}. "
            f"이것이 없으면 83쪽을 다시 전량 렌더링하게 된다")

def test_119cha_pumsem_survey_section_is_recorded():
    """119차 — 「제2절 온실품셈의 조사」(인쇄 p.120~137)가 기록에 고정돼 있는가.

    114·115차는 이 22쪽을 `제1절의 잔여 = 자재 소개`로 판단해 넘겼다. 실제로는
    **64계수가 어떻게 만들어졌는지를 적은 절**이고, 여기서 나온 것들:
      · 조사 현장이 **2곳**이다(부여 + 함평) — 116·118차의 `단일 현장`을 정정한다
      · 유도 원리가 **개소당 설치시간 조사 + 유리·비닐 공통 적용**이라고 명시된다
      · `철근공`의 노임 근거(**온실공 노임 ≈ 철근공 → 철골공·특수인부로 대체 작성**)
      · 공기 산정에 빠져 있던 **크루 규모 10~15명**

    이 기록이 사라지면 `p.116~137은 자재 소개`라는 틀린 판단으로 되돌아간다.
    """
    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8").read()

    for probe, why in (
        ("온실품셈의 조사", "절 제목 — p.120~137이 제1절의 잔여가 아니라는 근거"),
        ("함평", "두 번째 조사 현장 — `단일 현장`이 아니다"),
        # ⚠️119차 자가 발견 — 앵커 `1,600`은 다른 상수 source에도 있어 변이를 못 잡았다
        #   (111차 C2와 같은 유형: 짧은 앵커가 우연히 만족된다). 유일한 문자열로 바꾼다.
        ("함평 엑스포내 전시온실", "두 번째 현장의 원문 사업명"),
        ("연면적 **1,600㎡**", "함평 전시온실 연면적 — 부여(9,792)와 다른 규모"),
        ("철근공과 유사", "`철근공` 4건의 원문 근거(오기 가설을 더 약화한다)"),
        ("10~15명", "공기 산정의 빠진 입력 — 원문이 준다(등재는 ★사용자 결정)"),
        ("각자 적용하거나", "유리·비닐 공통 적용 원리 — 비닐 7종 물음의 답 방향"),
    ):
        assert probe in reg, (
            f"「온실품셈의 조사」 기록에서 `{probe}`가 사라졌다 — {why}. "
            f"이것이 없으면 p.120~137을 다시 자재 소개로 오판하게 된다")

    # 두 조사 현장 모두 유리·벤로타입이다 → 118차의 비닐 부재 결론이 유지된다
    assert "두 현장 모두" in reg or "조사된 두 현장" in reg, (
        "두 현장이 모두 유리라는 기록이 사라졌다 — 비닐 부재 결론의 근거다")

    # 표준품셈 대비 — 계수는 엔진에서 읽는다(리터럴 산술 금지, 23회차 C1)
    coef = {(x.category, x.name): x.labor_per_unit for x in e.PUMSEM_ITEMS}
    roof = coef[("온실피복공사", "천창유리")]["유리공"]
    side = coef[("온실피복공사", "측면강화유리")]["유리공"]
    CURTAIN_16MM = 0.131          # 건설공사 표준품셈 10-3-2 커튼월유리(16㎜이하), 인쇄 p.129
    assert round(CURTAIN_16MM / roof, 2) == 6.55
    assert round(CURTAIN_16MM / side, 2) == 13.1

    # 크루 규모·투과율·장비 임대료는 **엔진 상수가 아니다**
    #   crew_size는 판단성(★사용자 결정), 장비 임대료는 시세성(1절 불변 원칙)
    import smartfarm_engine as _e
    for attr in ("PUMSEM_CREW_SIZE", "PUMSEM_LIFT_RENTAL",
                 "PUMSEM_GLASS_TRANSMITTANCE"):
        assert not hasattr(_e, attr), (
            f"{attr}: 원문이 값을 준다고 해서 엔진에 올리면 안 된다 — 크루 규모는 "
            f"판단성(★사용자 결정), 장비 임대료는 시세성(주입만 받는다)이다")

def test_120cha_toc_matches_pumsem_category_layout():
    """120차 — 원문 **목차**가 `PUMSEM_ITEMS`의 공종 배분·1번 품목과 정합한다.

    113차는 품셈 표 25쪽을 렌더링해 64종을 전수 대조했다. 목차는 **다른 경로**로
    같은 구조를 확인해 준다 — 공종별 시작 쪽에서 쪽수를 유도하면 유리 22쪽 + 비닐
    3쪽 = **25쪽**이 나오고, 각 공종의 **1번 품목**이 본문 표의 1번과 일치한다.

    🔴 다만 **엔진의 공종 선언 순서는 원문 차례와 다르다**(원문은 철골→알루미늄→
    피복→천창개폐, 엔진은 철골→피복→천창개폐→알루미늄). 조회가 (공종,품목명)
    키라서 **값·합산에는 영향이 없다** — 그래서 순서를 강제하지 않고, 대신
    **집합과 1번 품목**을 고정한다.

    그리고 목차에 「온실품셈의 조사」가 **없다** — 본문 인쇄 p.120의 그 제목은
    목차에 실리지 않았고 절 번호가 p.138의 제2절과 충돌한다(원문 편집 오류).
    119차가 그것을 보고 `제1절은 p.109~119에서 끝난다`고 적었는데, 목차 기준
    제1절은 **p.109~137**이다 — 115차의 `29쪽`이 맞았다.
    """
    # 원문 목차(PDF 19): 제7장 제2절 하위 7공종의 시작 쪽 + 각 공종 본문 1번 품목
    TOC = [
        ("철골공사",         138, "스틸돌리",     {"철골공": 0.21, "특별인부": 0.07}),
        ("알루미늄공사",     141, "거터",         {"철골공": 0.04, "특별인부": 0.01}),
        ("온실피복공사",     144, "천창유리",     {"유리공": 0.02, "조력공": 0.01}),
        ("천창개폐장치공사", 146, "천창개폐모터", {"철골공": 0.3, "조력공": 0.25}),
        ("수평스크린공사",   151, "스크린개폐모터", {"철골공": 1, "조력공": 0.5}),
        ("측벽스크린공사",   156, "스크린개폐모터", {"철골공": 1.33, "조력공": 0.67}),
        ("행잉거터공사",     158, "트러스걸이",   {"철골공": 0.004, "조력공": 0.006}),
    ]
    VINYL_START, VINYL_END = 160, 162      # 제3절 경량철골비닐온실공사

    # ① 시작 쪽에서 유도한 쪽수 — 유리 22쪽 + 비닐 3쪽 = 113차가 렌더링한 25쪽
    #   ⚠️120차 자가 발견: **총합만 보면 안 된다**. 시작 쪽 하나를 옮겨도 인접 구간이
    #   상쇄해 합은 그대로다(변이가 통과했다). 공종별 쪽수를 **개별로** 고정한다.
    bounds = [p for _, p, _, _ in TOC] + [VINYL_START]
    per_cat = [bounds[k + 1] - bounds[k] for k in range(len(TOC))]
    assert per_cat == [3, 3, 2, 5, 5, 2, 2], per_cat
    glass_pages = sum(per_cat)
    vinyl_pages = VINYL_END - VINYL_START + 1
    assert glass_pages == 22 and vinyl_pages == 3
    assert glass_pages + vinyl_pages == 25, "113차가 전수 대조한 쪽수와 어긋난다"

    # ② 공종 집합이 일치한다(순서는 강제하지 않는다 — 위 docstring 참조)
    cats = {x.category for x in e.PUMSEM_ITEMS}
    assert {n for n, _, _, _ in TOC} | {"철골공사(비닐·파이프자재)",
                                        "온실피복공사(비닐)"} == cats, sorted(cats)

    # ③ 각 공종의 **1번 품목**이 원문 표의 1번과 일치한다 — 113차 전수 대조의 교차검증
    first = {}
    for x in e.PUMSEM_ITEMS:
        first.setdefault(x.category, x)
    for name, _, item_name, labor in TOC:
        got = first[name]
        assert got.name == item_name, (name, got.name, item_name)
        assert got.labor_per_unit == labor, (name, got.labor_per_unit, labor)
    assert first["철골공사(비닐·파이프자재)"].name == "지붕서까래"
    assert first["온실피복공사(비닐)"].name == "농업용PO필름(천창및지붕)"

    # ④ 비닐은 2공종(철골 5 + 피복 2)이고 목차에서 3쪽을 차지한다
    vinyl = [x for x in e.PUMSEM_ITEMS if "비닐" in x.category]
    assert len({x.category for x in vinyl}) == 2 and len(vinyl) == 7

    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8").read()
    for probe, why in (
        ("목차에 「온실품셈의 조사」가 없다", "절 번호 중복이 원문 편집 오류라는 확정 근거"),
        ("30% 이상 적은 품", "철골 계수의 정량 근거 — 유리 쪽 이견과 대비된다"),
        ("70%이하의 볼트본조임", "철골 계수의 두 번째 정량 근거"),
        ("10kg당", "알루미늄은 단위가 달라 119차식 대비가 불가능하다는 기록"),
        ("선언 순서", "엔진 카테고리 순서가 원문 차례와 다르다는 기록(값 영향 0)"),
    ):
        assert probe in reg, (
            f"120차 목차 대조 기록에서 `{probe}`가 사라졌다 — {why}")

def test_121cha_phase_labor_split_and_rebar_absence():
    """121차 — 공종별 인·일 배분과 **`철근공`이 해당 공종에 없다**는 사실을 고정한다.

    공종 경계 12시점의 누계를 차분하면 13단계 배분이 나오고, 그 배분이 품셈의
    **직종 구성과 0인 자리까지 일치**한다 — 피복공사에 철골공 0, 철골·알루미늄에
    조력공 0, 천창개폐·스크린에 특별인부 0.

    🔴 예외가 `철근공`이다. 품셈은 수평스크린 3품목 + 행잉거터 1품목에 철근공을
    배분했는데, **그 두 공종 기간의 철근공 투입이 0**이다(48은 전부 기초 구간에서
    나왔다). 116차의 *"관측 결과일 개연성이 높다"*를 **뒤집는다** — 다만 준용인지
    표기 잔존인지는 판정하지 않는다(원문이 말하지 않는다).

    이 배분이 사라지면 116차의 뒤집힌 판단으로 되돌아가고, 공사일보 83쪽을 다시
    차분해야 한다.
    """
    # 공종 경계 누계(원문 판독) — 직종별, 시점 순서는 시간 순
    CUM = [                      # (라벨, 온실공, 조력공, 특별인부, 보통인부, 철근공, 계)
        ("11-05 가설末",          0,   0,   0,  22,  0,   36),
        ("11-07 토목末",          0,   0,   0,  24,  0,   38),
        ("12-08 철근콘크리트①末", 42,   0,  24, 107, 48,  390),
        ("12-31 철골末",         202,   0,  84, 127, 48,  630),
        ("01-18 알루미늄①末",    306,   0, 124, 141, 48,  788),
        ("02-23 피복末",         306,  78, 124, 187, 48, 1120),
        ("02-26 알루미늄②末",    330,  78, 133, 190, 48, 1156),
        ("03-12 천장개폐末",     341, 166, 133, 202, 48, 1268),
        ("03-24 수평스크린末",   421, 206, 133, 217, 48, 1413),
        ("03-31 측벽스크린末",   477, 234, 133, 224, 48, 1504),
        ("04-27 양액末",         477, 234, 238, 280, 48, 1784),
        ("05-07 철근콘크리트②末", 477, 234, 243, 301, 48, 1899),
        ("05-25 행잉거터末(최종)", 517, 276, 243, 360, 48, 2040),
    ]
    # 누계는 단조증가여야 한다
    for k in range(1, len(CUM)):
        for c in range(1, 6):
            assert CUM[k][c] >= CUM[k - 1][c], (CUM[k][0], c)
    # 최종 누계가 116차 정정값(118차 확인)과 맞는다
    assert CUM[-1][1:] == (517, 276, 243, 360, 48, 2040)

    def delta(idx, col):
        return CUM[idx][col] - (CUM[idx - 1][col] if idx else 0)

    # 🔴 철근공 — 기초 구간에서 48 전부, 스크린·행잉거터 구간은 0
    assert delta(2, 5) == 48, "철근공 48은 철근콘크리트①(기초)에서 나왔다"
    assert delta(8, 5) == 0, "수평스크린 구간의 철근공 투입은 0이다"
    assert delta(12, 5) == 0, "행잉거터 구간의 철근공 투입은 0이다"

    # 그런데 품셈은 그 두 공종에만 철근공을 쓴다 — 관측과 어긋나는 유일한 자리
    rebar = {(x.category, x.name) for x in e.PUMSEM_ITEMS
             if "철근공" in x.labor_per_unit}
    assert {c for c, _ in rebar} == {"수평스크린공사", "행잉거터공사"}, rebar
    assert len(rebar) == 4, rebar

    # ✅ 직종 구성이 0인 자리까지 맞는다 — 품셈에 없는 직종은 관측도 0이다
    trades = {}
    for x in e.PUMSEM_ITEMS:
        trades.setdefault(x.category, set()).update(x.labor_per_unit)
    assert "철골공" not in trades["온실피복공사"]
    assert delta(5, 1) == 0, "피복공사 구간의 온실공(=철골공) 투입은 0이다"
    assert "조력공" not in trades["철골공사"] and "조력공" not in trades["알루미늄공사"]
    assert delta(3, 2) == 0 and delta(4, 2) == 0, "철골·알루미늄 구간의 조력공은 0이다"
    assert "특별인부" not in trades["천창개폐장치공사"]
    assert delta(7, 3) == 0, "천장개폐 구간의 특별인부는 0이다"

    # ✅ 118차 역산의 독립 검증 — 유리공으로 구한 물량이 조력공 관측을 설명한다
    coef = {(x.category, x.name): x.labor_per_unit for x in e.PUMSEM_ITEMS}
    roof_m2, side_m2 = 6800, 3000            # 118차 역산(유리공 136·30 ÷ 계수)
    pred = (coef[("온실피복공사", "천창유리")]["조력공"] * roof_m2
            + coef[("온실피복공사", "측면강화유리")]["조력공"] * side_m2)
    assert pred == 80
    observed = delta(5, 2)                   # 피복 구간 조력공
    assert observed == 78
    assert abs(pred - observed) / pred < 0.03, (pred, observed)

    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8").read()
    for probe, why in (
        ("철근공 투입이 0", "116차 판단을 뒤집는 근거"),
        ("1,255", "공종 기준 관측 모집단 — 직종 기준 1,652보다 좁다"),
        ("03-25~03-31", "측벽스크린 기간(120차의 04-01 정정)"),
    ):
        assert probe in reg, (
            f"121차 공종별 배분 기록에서 `{probe}`가 사라졌다 — {why}")

if __name__ == "__main__":
    import sys, traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception as ex:
            print(f"  FAIL  {fn.__name__}: {ex}")
            traceback.print_exc()
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
