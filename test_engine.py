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

    # ⚖️ 조력공 직종비 검산 — 🔴24회차 레드팀 F1: **물량과는 무관하다**
    #   종전 이 자리는 "118차 역산의 독립 검증"이라 적었는데 틀렸다. 예측에 쓰는
    #   물량 6,800·3,000 자체가 관측 유리공÷계수라 식에서 **물량이 소거된다** —
    #   검증되는 것은 품셈 표 내부의 **직종비**뿐이고 역산 물량의 타당성이 아니다.
    coef = {(x.category, x.name): x.labor_per_unit for x in e.PUMSEM_ITEMS}
    roof_g, side_g = 136, 30                 # 관측 유리공(118차 분해)
    c_roof = coef[("온실피복공사", "천창유리")]
    c_side = coef[("온실피복공사", "측면강화유리")]

    def predict(scale):
        """역산 물량에 임의 배율을 걸어도 예측이 같은가 — 물량 소거의 증명."""
        roof_m2 = roof_g / c_roof["유리공"] * scale
        side_m2 = side_g / c_side["유리공"] * scale
        # 유리공도 같은 배율로 관측됐다고 두어야 같은 역산이다
        return (c_roof["조력공"] * roof_m2 + c_side["조력공"] * side_m2) / scale

    assert predict(1) == 80
    for scale in (0.5, 2, 10):
        assert predict(scale) == predict(1), scale   # 🔴 물량이 소거된다

    # 남는 것은 직종비뿐이다 — 136×(0.01/0.02) + 30×(0.004/0.01)
    ratio_only = (roof_g * (c_roof["조력공"] / c_roof["유리공"])
                  + side_g * (c_side["조력공"] / c_side["유리공"]))
    assert ratio_only == 80, ratio_only

    observed = delta(5, 2)                   # 피복 구간 조력공
    assert observed == 78
    assert abs(ratio_only - observed) / ratio_only < 0.03, (ratio_only, observed)

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

def test_122cha_daily_headcount_and_missing_logs():
    """122차 — 일별 투입 전량 판독: 작업일수·실측 crew size·**일보 3일 누락**.

    121차는 공종 **경계** 누계만 차분했다. 이번엔 168일보의 `계` 행을 전량 읽어
    일별 합산으로 같은 배분이 나오는지 확인한다(다른 경로의 교차검증).

    🔴 그 과정에서 **2021-05-18·19·20 일보가 편철에 없다**는 것이 드러났다 —
    05-17 누계 1,992 + 05-21 금일 7 ≠ 05-21 누계 2,019이고 **+20이 설명되지
    않는다**. 118차의 `168장 전량`은 맞지만 **전체 공사일을 덮지 않는다**.

    🎯 실측 평균은 품셈 7공종에서 **10.1~14.5명/일**이고, 119차가 원문에서 찾은
    *"인원 10~15명"*과 맞는다. ⚠️ 등재는 하지 않는다(공기는 판단성·★사용자 결정).
    """
    # 공종별 일별 투입(원문 `계` 행 금일, 시간 순) — 기록된 일보만
    DAILY = {
        "가설":       [3, 11, 11, 11],
        "토목":       [1, 1],
        "철근콘크리트①": [4, 7, 4, 8, 18, 18, 10] + [13] * 14 + [30, 11, 16, 16, 16, 12],
        "철골":       [12] * 20,
        "알루미늄①":   [12] * 12 + [14],
        "피복":       [9] * 8 + [13] * 20,
        "알루미늄②":   [12] * 3,
        "천창개폐":    [10] * 10 + [12],
        "수평스크린":   [16] * 5 + [13] * 5,
        "측벽스크린":   [13] * 7,
        "양액시스템":   [1, 1, 11, 11, 11, 11, 15, 5, 1, 1, 10, 10, 10, 14, 10, 6] + [19] * 8,
        "철근콘크리트②": [14] * 6 + [31],
        "행잉거터":    [2] + [13] * 7 + [7] * 4,
    }
    # 121차가 경계 누계 차분으로 낸 값 — 행잉거터만 누락 3일(20 인·일)이 빠져 있다
    FROM_121 = {
        "가설": 36, "토목": 2, "철근콘크리트①": 352, "철골": 240, "알루미늄①": 158,
        "피복": 332, "알루미늄②": 36, "천창개폐": 112, "수평스크린": 145,
        "측벽스크린": 91, "양액시스템": 280, "철근콘크리트②": 115, "행잉거터": 141,
    }
    MISSING = 20            # 2021-05-18·19·20 — 일보가 없는 구간의 인·일

    # 🔴24회차 F4: "13공종 전부 일치"는 부정확하다 — 12공종은 그대로 일치하고
    #   행잉거터만 누락 3일분 20을 보정해야 맞는다.
    exact, corrected = [], []
    for name, days in DAILY.items():
        if sum(days) == FROM_121[name]:
            exact.append(name)
        else:
            corrected.append(name)
            assert sum(days) + MISSING == FROM_121[name], (name, sum(days))
    assert len(exact) == 12 and corrected == ["행잉거터"], (len(exact), corrected)

    # 총계가 118차 정정값 2,040과 맞는다
    assert sum(sum(v) for v in DAILY.values()) + MISSING == 2040
    assert sum(len(v) for v in DAILY.values()) == 168, "기록된 일보는 168장이다"

    # 🔴 누락 구간 — 05-17 누계 + 05-21 금일 ≠ 05-21 누계
    assert 1992 + 7 != 2019
    assert 2019 - 1992 - 7 == MISSING

    # 📌 선조립 공정은 일별 편차가 0이다(120차 ④ 모듈형 반입과 정합)
    for name in ("철골", "알루미늄②", "측벽스크린"):
        assert len(set(DAILY[name])) == 1, (name, sorted(set(DAILY[name])))

    # 🎯 품셈 7공종의 실측 평균이 원문 "10~15명" 구간에 들어간다 — **기록분 기준**
    #   🔴24회차 F5: 행잉거터는 누락 3일(20 인·일)이 그 구간 안이라, 보정하면
    #   9.4(3일 다 작업)까지 내려가 **구간을 벗어난다**. 조건부 진술임을 고정한다.
    PUMSEM_PHASES = ("철골", "알루미늄①", "알루미늄②", "피복",
                     "천창개폐", "수평스크린", "측벽스크린", "행잉거터")
    for name in PUMSEM_PHASES:
        avg = sum(DAILY[name]) / len(DAILY[name])
        assert 10 <= avg <= 15, (name, round(avg, 1))
    hang = FROM_121["행잉거터"]                       # 141 = 기록 121 + 누락 20
    assert round(hang / (len(DAILY["행잉거터"]) + 3), 1) == 9.4    # 3일 다 작업 → 이탈
    assert round(hang / (len(DAILY["행잉거터"]) + 1), 1) == 10.8   # 1일만 작업 → 구간 안
    man_days = sum(sum(DAILY[n]) for n in PUMSEM_PHASES)
    work_days = sum(len(DAILY[n]) for n in PUMSEM_PHASES)
    assert man_days == 1235 and work_days == 104
    assert round(man_days / work_days, 1) == 11.9

    # 피크 2건은 품셈 범위 **밖** 공종에서 나온다 — 품셈 공종 피크는 16명이다
    assert max(DAILY["철근콘크리트②"]) == 31 and max(DAILY["철근콘크리트①"]) == 30
    assert max(max(DAILY[n]) for n in PUMSEM_PHASES) == 16

    # crew size는 **엔진 상수가 아니다**(공기 산정은 판단성 — ★사용자 결정)
    import smartfarm_engine as _e
    for attr in ("PUMSEM_CREW_SIZE", "PUMSEM_WORK_DAYS", "PUMSEM_DAILY_HEADCOUNT"):
        assert not hasattr(_e, attr), (
            f"{attr}: 실측 crew size가 엔진 상수로 올라왔다 — 이 현장 하나의 관측이고 "
            f"공기 산정은 판단성이다(★사용자 결정)")

    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8").read()
    for probe, why in (
        # 119·120차 교훈: 짧은 앵커는 우연히 만족된다. 날짜 셋을 통째로 고정한다.
        ("2021-05-18·19·20", "누락 일보 — 168장이 전체 공사일을 덮지 않는다"),
        ("편차 0", "선조립 공정의 균일성 — 120차 모듈형 서술과 정합"),
        ("10~15명", "원문 서술과 실측이 맞는다는 기록"),
    ):
        assert probe in reg, (
            f"122차 일별 판독 기록에서 `{probe}`가 사라졌다 — {why}")

def test_123cha_redteam24_corrections_are_recorded():
    r"""123차 — 레드팀 24회차(112~122차 누적)의 정정이 기록에 고정돼 있는가.

    발견 14건 중 **12건 타당 · 2건 거짓 양성**이었다. 가장 중요한 것은 [상] 2건:

    · **F1** — 121차가 *"118차 역산의 독립 검증"*이라 적은 조력공 검산은 **물량이
      식에서 소거**되므로 역산 물량의 검증이 아니다(위 121차 가드에서 배율 불변으로
      증명한다). 문서·엔진 주석·레지스트리·작업지시서 **4곳에 전파**돼 있었다.
    · **F2** — 작업지시서 2절 스냅샷이 *"112차가 ROOT 기준으로 바꿔 … 재발하지
      않는다"*고 적었으나 **폐기된 초안**이다. 실제로는 사용자가 리터럴로 확정했고
      `test_chunking_v2.py`는 리터럴 `C:\FarmingDesign`을 쓴다 — **드라이브 이동 시
      재발한다**. 2절은 44차 F1이 유지 절차를 못 박은 **살아 있는 스냅샷**이라
      틀린 채로 두면 다음 이동 때 게이트가 다시 빨개진다.

    거짓 양성 2건(F6 스트립 범위 표기 · F13 함평 명칭)은 둘 다 에이전트가 **텍스트층이
    없는 구간을 읽지 못해** 생겼다 — 루브릭 개정 근거로 남긴다.
    """
    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))

    # F2 — 픽스처는 리터럴이고, 2절은 그 사실을 말해야 한다
    chunk = open(_o.path.join(repo, "test_chunking_v2.py"), encoding="utf-8").read()
    assert chunk.count(r"C:\FarmingDesign") >= 4, "픽스처 4곳이 리터럴이 아니다"
    assert "사용자 결정(2026-09-14): 리터럴" in chunk, (
        "픽스처 상단의 사용자 결정 주석이 사라졌다 — 112차 ③")

    order = open(_o.path.join(repo, "작업지시서.md"), encoding="utf-8").read()
    assert "다음 이동에도 재발하지 않는다" not in order, (
        "2절 스냅샷에 폐기된 초안(ROOT 기준)이 되살아났다 — 24회차 F2")
    assert "드라이브를 또 옮기면 이 4곳이 다시 깨진다" in order, (
        "2절에서 드라이브 이동 시 재발 경고가 사라졌다 — 24회차 F2")

    # F1 — 4곳 전파분이 전부 정정된 상태인가
    reg = open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8").read()
    engine = open(_o.path.join(repo, "smartfarm_engine.py"), encoding="utf-8").read()
    doc = open(_o.path.join(repo, "근거_공사일보_공종별배분_20260914.md"),
               encoding="utf-8").read()
    for text, where in ((reg, "레지스트리"), (engine, "엔진 주석"),
                        (doc, "121차 문서"), (order, "작업지시서")):
        assert "역산 물량의 자기정합성이 한 단계 올라간다" not in text, (
            f"{where}에 24회차 F1이 반증한 주장이 되살아났다")
        assert "소거" in text, (
            f"{where}에서 '물량이 소거된다'는 F1의 핵심이 사라졌다")

    # F4·F5 — 조건부 진술의 단서
    for probe, why in (
        ("12공종", "F4 — 13공종 전부 일치가 아니다"),
        ("9.4", "F5 — 행잉거터 누락 보정 시 구간 이탈"),
    ):
        assert probe in reg, f"24회차 기록에서 `{probe}`가 사라졌다 — {why}"

    # 거짓 양성 2건이 루브릭 개정 근거로 남아 있는가
    for probe in ("거짓 양성", "F6", "F13"):
        assert probe in reg, f"24회차 거짓 양성 기록에서 `{probe}`가 사라졌다"

def test_124cha_daily_trade_mix_and_ratios():
    """124차 — 일별 **직종 구성** 17시점: 주력 크루의 실체와 직종비.

    122차는 `계` 행만 읽었고 121차는 경계 시점의 누계만 읽었다. 이번엔 **총계 수준이
    바뀌는 지점마다** 직종 구성을 읽어 두 가지를 고정한다:

    · 🎯 **주력 크루는 온실공 8명**이다 — 철골·알루미늄·수평스크린·측벽스크린이 전부
      같고, 119차가 원문에서 찾은 *"인원 10~15명"*의 실체가 여기서 드러난다.
    · 🎯 **직종비**가 품셈 계수비와 맞는 곳과 어긋나는 곳이 갈린다. **천창유리는 단일
      품목이라 물량 가중 가정이 필요 없고 정확히 0.50으로 일치**한다.

    ⚠️ 123차 F1이 못 박았듯 이것은 **물량·계수 절대 크기와 무관**하다 — 검증되는 것은
    품셈 표 내부의 **직종 간 비율**뿐이다.
    """
    # (공종, 날짜, 계, {직종: 금일}) — 원문 `투입인원현황` 금일 열 판독
    MIX = [
        ("철골",       "12-09", 12, {"온실공": 8, "특별인부": 3, "보통인부": 1}),
        ("철골",       "12-15", 12, {"온실공": 8, "특별인부": 3, "보통인부": 1}),
        ("알루미늄①",  "01-05", 12, {"온실공": 8, "특별인부": 3, "보통인부": 1}),
        ("알루미늄①",  "01-18", 14, {"온실공": 8, "특별인부": 4, "보통인부": 2}),
        ("알루미늄②",  "02-25", 12, {"온실공": 8, "특별인부": 3, "보통인부": 1}),
        ("피복:측면",  "01-19",  9, {"유리공": 6, "조력공": 2, "보통인부": 1}),
        ("피복:천창",  "02-01", 13, {"유리공": 8, "조력공": 4, "보통인부": 1}),
        ("피복:천창",  "02-10", 13, {"유리공": 8, "조력공": 4, "보통인부": 1}),
        ("천창개폐",   "02-27", 10, {"온실공": 1, "조력공": 8, "보통인부": 1}),
        ("천창개폐",   "03-12", 12, {"온실공": 1, "창호공": 1, "조력공": 8, "보통인부": 2}),
        ("수평스크린", "03-13", 16, {"온실공": 8, "창호공": 2, "조력공": 4, "보통인부": 2}),
        ("수평스크린", "03-19", 13, {"온실공": 8, "조력공": 4, "보통인부": 1}),
        ("측벽스크린", "03-25", 13, {"온실공": 8, "조력공": 4, "보통인부": 1}),
        ("측벽스크린", "03-29", 13, {"온실공": 8, "조력공": 4, "보통인부": 1}),
        ("행잉거터",   "05-08",  2, {"보통인부": 2}),
        ("행잉거터",   "05-10", 13, {"온실공": 5, "조력공": 7, "보통인부": 1}),
        ("행잉거터",   "05-21",  7, {"보통인부": 7}),
    ]
    # 각 시점의 구성 합 = 그날 `계`
    for phase, day, total, mix in MIX:
        assert sum(mix.values()) == total, (phase, day, sum(mix.values()), total)
    assert len(MIX) == 17

    # ✅ "같은 총계 = 같은 구성" — 3쌍에서 재현된다(전량 판독을 대신한 근거)
    pairs = [("철골", "12-09", "12-15"), ("피복:천창", "02-01", "02-10"),
             ("측벽스크린", "03-25", "03-29")]
    by = {(p, d): m for p, d, _, m in MIX}
    for phase, a, b in pairs:
        assert by[(phase, a)] == by[(phase, b)], (phase, a, b)

    # 🎯 주력 크루 = 온실공 8명(피복은 0 — 품셈에 철골공이 없는 것과 같다)
    for phase in ("철골", "알루미늄①", "알루미늄②", "수평스크린", "측벽스크린"):
        days = [m for p, _, _, m in MIX if p == phase]
        assert all(m.get("온실공") == 8 for m in days), (phase, days)
    assert all("온실공" not in m for p, _, _, m in MIX if p.startswith("피복"))

    # 🎯 직종비를 **엔진 계수**에서 읽어 대조한다(리터럴 산술 금지 — 23회차 C1)
    coef = {(x.category, x.name): x.labor_per_unit for x in e.PUMSEM_ITEMS}

    def cat_ratio(cat, num, den):
        n = sum(x.labor_per_unit.get(num, 0) for x in e.PUMSEM_ITEMS if x.category == cat)
        d = sum(x.labor_per_unit.get(den, 0) for x in e.PUMSEM_ITEMS if x.category == cat)
        return n / d

    # 천창유리 — **단일 품목**이라 물량 가중 가정이 필요 없다 → 정확히 일치
    roof = coef[("온실피복공사", "천창유리")]
    assert roof["조력공"] / roof["유리공"] == 0.5
    mix = by[("피복:천창", "02-01")]
    assert mix["조력공"] / mix["유리공"] == 0.5          # 🎯 관측도 정확히 0.5

    # 스크린 2공종 — 계수합 비율과 2% 안에서 맞는다
    for cat, phase, day in (("수평스크린공사", "수평스크린", "03-19"),
                            ("측벽스크린공사", "측벽스크린", "03-25")):
        m = by[(phase, day)]
        obs = m["조력공"] / m["온실공"]
        assert abs(cat_ratio(cat, "조력공", "철골공") - obs) / obs < 0.03, (cat, obs)

    # ⚠️ 어긋나는 곳 — 품목이 많아 단순 합 비율이 현장을 대표하지 못한다
    side = coef[("온실피복공사", "측면강화유리")]
    m = by[("피복:측면", "01-19")]
    assert side["조력공"] / side["유리공"] == 0.4
    assert round(m["조력공"] / m["유리공"], 3) == 0.333   # −17%
    m = by[("천창개폐", "02-27")]
    assert m["조력공"] / m["온실공"] == 8.0
    assert round(cat_ratio("천창개폐장치공사", "조력공", "철골공"), 2) == 4.15

    # 📌 품셈에 없는 직종이 상주한다 — 121차 "부대 작업" 추정의 관측 근거
    with_bo = [d for _, d, _, m in MIX if "보통인부" in m]
    assert len(with_bo) == 17            # 🔴25회차 F4: 17시점 **전부에 상주**하되
    one_or_two = [d for _, d, _, m in MIX if m.get("보통인부") in (1, 2)]
    assert len(one_or_two) == 16         #   **1~2명인 것은 16시점**이다(05-21은 단독 7명)
    assert "보통인부" not in {j for x in e.PUMSEM_ITEMS
                              if x.category in ("철골공사", "알루미늄공사",
                                                "수평스크린공사", "측벽스크린공사")
                              for j in x.labor_per_unit}
    # 그라운드커버 날(05-21)은 보통인부 단독 — 품셈 57번도 보통인부 단일 직종이다
    assert by[("행잉거터", "05-21")] == {"보통인부": 7}
    gc = coef[("행잉거터공사", "그라운드커버")]   # 피복공사가 아니라 행잉거터공사다
    assert set(gc) == {"보통인부"}, gc

    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8").read()
    for probe, why in (
        ("온실공 8명", "주력 크루의 실체 — 119차 '10~15명'의 내용"),
        ("같은 총계 = 같은 구성", "전량 판독을 대신한 근거(3/3 재현)"),
        ("단일 품목이라", "천창유리가 물량 가중 가정에서 자유로운 이유"),
    ):
        assert probe in reg, (
            f"124차 직종 구성 기록에서 `{probe}`가 사라졌다 — {why}")

def test_125cha_pumsem_64_reextracted_from_pdf_textlayer():
    """125차 — 64계수를 **원문 PDF 텍스트층에서 기계 재추출**해 엔진과 대조한다.

    113차는 25쪽을 렌더링해 **육안**으로 64종을 전수 대조했다. 그 대조는 사람이
    한 번 한 것이라 **되돌려 확인할 수 없었다** — 24회차 레드팀이 이 구간에
    Type0 텍스트층이 살아 있음을 찾아내면서 길이 열렸고, 125차가 그것을
    `pumsem_extract.py`로 상시화했다.

    이 테스트가 green인 한 **엔진의 64계수는 원문과 같다**. 누가 값을 고치면
    (원문을 함께 고치지 않는 한) 여기서 잡힌다.

    ⚠️ 의존성(pdfplumber·fontTools·pypdf)이나 시스템 Batang/Gulim이 없으면 skip한다 —
    이 환경은 pip 패키지가 세션 간 유실되므로(CLAUDE.md) skip 수를 꼭 확인할 것.
    """
    import pytest
    pytest.importorskip("pdfplumber")
    pytest.importorskip("fontTools")
    pytest.importorskip("pypdf")
    import pumsem_extract as px

    try:
        rows = px.extract_all()
    except px.FontsUnavailable as exc:
        pytest.skip("시스템 Batang/Gulim 없음: %s" % exc)

    assert len(rows) == 64, "원문에서 뽑은 품목 수가 64가 아니다: %d" % len(rows)

    # 엔진을 **원문 차례**로 정렬한다(선언 순서는 다르다 — 120차 ⑦)
    expected = []
    for cat, _, _ in px.SECTION_PAGES:
        items = [x for x in e.PUMSEM_ITEMS if x.category == cat]
        for n, x in enumerate(items, 1):
            expected.append((cat, n, x.name,
                             list(x.labor_per_unit.values())
                             + list(x.equipment_hours_per_unit.values())))
    assert len(expected) == 64

    bad = []
    for (cat1, no1, name, want), (cat2, no2, got) in zip(expected, rows):
        if (cat1, no1) != (cat2, no2) or want != got:
            bad.append("%s %d %s: 엔진=%s 원문=%s" % (cat1, no1, name, want, got))
    assert not bad, "원문과 어긋난다(%d건)\n" % len(bad) + "\n".join(bad)

    # 🔴25회차 F7 — 값만 보면 **직종이 뒤바뀌어도 통과**한다(수평스크린
    #   `예인로라·가이드로라`(철근공)와 `구동2축`(철골공)은 계수가 같다).
    #   직종명도 원문에서 뽑아 대조한다 — 🎯그 부산물로 91차부터 [확인요망]으로
    #   끌어온 "원문이 정말 철근공이라 적는가"가 **기계로 확인**된다(25회차 F8).
    trades = px.extract_labor_trades()
    assert len(trades) == 64
    bad_t = []
    for (cat1, no1, name, _), (cat2, no2, got) in zip(expected, trades):
        want = [k for k in
                [x for x in e.PUMSEM_ITEMS
                 if x.category == cat1][no1 - 1].labor_per_unit]
        if (cat1, no1) != (cat2, no2) or want != got:
            bad_t.append("%s %d %s: 엔진=%s 원문=%s" % (cat1, no1, name, want, got))
    assert not bad_t, "직종명이 원문과 어긋난다(%d건)\n" % len(bad_t) + "\n".join(bad_t)

    # 🎯 철근공 4품목이 원문 그대로다 — 91·113·116·121차가 다룬 그 항목이다
    rebar = [(c, n) for c, n, ts in trades if "철근공" in ts]
    assert len(rebar) == 4, rebar
    assert {c for c, _ in rebar} == {"수평스크린공사", "행잉거터공사"}, rebar

    # 원문에서 뽑은 값의 범위가 엔진과 같은가(파서가 엉뚱한 숫자를 주웠는지 본다)
    flat = sorted(v for _, _, vals in rows for v in vals)
    eng_flat = sorted(v for x in e.PUMSEM_ITEMS
                      for v in list(x.labor_per_unit.values())
                      + list(x.equipment_hours_per_unit.values()))
    assert flat == eng_flat, (len(flat), len(eng_flat), flat[:3], flat[-3:])

def test_126cha_spec_tables_reextracted_from_pdf():
    """126차 — 제원 표 5종을 **원문 텍스트층에서 기계 재확인**한다.

    115·119차가 육안으로 읽은 값(9,792 · 10,106 · 314 · 18,707.03 · 1,600)과
    115차 E1(`재배 1구역`이 두 번)을 **기계 추출로 재현**한다. 125차가 계수에 대해
    한 일을 제원 표로 넓힌 것이다.

    🔴 그 과정에서 **원문 표기 오기 2건**이 드러났다:
      · `4032.00`에 **천단위 쉼표가 없다**(세 표 전부 — 같은 표의 다른 값에는 있다)
      · [표 7-5] 합계만 **소수점이 없다**(`10,106㎡`)
    115·119차는 이것을 `4,032.00`으로 **정규화해 옮겼다** — 사람이 표를 읽을 때
    자연스럽게 하는 일이고 **기계 추출이라야 잡힌다**.

    ⚠️ 의존성·시스템 폰트가 없으면 skip한다(125차와 같다).
    """
    import re
    import pytest
    pytest.importorskip("pdfplumber")
    pytest.importorskip("fontTools")
    pytest.importorskip("pypdf")
    import pumsem_extract as px

    try:
        tables = px.extract_tables()
    except px.FontsUnavailable as exc:
        pytest.skip("시스템 Batang/Gulim 없음: %s" % exc)

    assert set(tables) == {110, 112, 120, 122}

    def nums(pp):
        return re.findall(r"[\d,]+\.\d+|[\d,]{3,}", " ".join(tables[pp]))

    # [표 7-2] 유리온실 — 115차 육안과 일치
    assert "4,608.00" in nums(110) and "1,152.00" in nums(110)
    assert "9,792.00" in nums(110)
    # 🔴 N1 — 재배 2구역만 천단위 쉼표가 없다
    assert "4032.00" in nums(110) and "4,032.00" not in nums(110)

    # [표 7-4]·[표 7-5] 비닐온실 — 방풍실 314가 차이 전부다(115차 ②)
    assert "10,106.00" in nums(112)          # [표 7-4] 연면적
    assert "314" in nums(112)
    assert "10,106" in nums(112)             # 🔴 N2 — 합계만 소수점이 없다
    assert "4032.00" in nums(112)

    # [표 7-7]·[표 7-8] 부여 — 119차가 잡은 내부 불일치
    assert "18,707.03" in nums(120)          # 연면적
    assert "9,792.00" in nums(120)           # 구역별 합계
    assert "18,707.03" != "9,792.00"         # 같은 쪽에서 서로 다르다

    # [표 7-9] 함평 — 24회차 F13
    #   🔴25회차 F6: 종전 `"나비" not in 쪽 전체`는 **못 읽어서 통과**했다.
    #   같은 쪽 소제목 「나) 함평 나비엑스포내 전시온실」은 글리프가 전량 미복원이라
    #   이 경로로 판정할 수 없다 — 단정 범위를 **[표 7-9] 사업명 행**으로 좁힌다.
    assert "1,600" in nums(122)
    biz = [x for x in tables[122] if "전시온실" in x and "건립사업" in x]
    assert len(biz) == 1, biz
    assert "나비" not in biz[0], biz[0]      # 사업명 행에는 없다(소제목은 판정 불가)

    # ✅ 115차 E1 — "재배 1구역"이 세 표 전부에서 2회
    for pp in (110, 112, 120):
        hits = [x for x in tables[pp] if "재배" in x and "1구역" in x]
        assert len(hits) == 2, (pp, hits)

    # 검산: 4,608 + 4,032 + 1,152 = 9,792 / +314 = 10,106
    assert 4608 + 4032 + 1152 == 9792
    assert 9792 + 314 == 10106

def test_127cha_pumsem_notes_conditions_and_defects():
    """127차 — 품셈 **[주] 항목**의 적용 조건과 원문 결함을 고정한다.

    125차 파서는 [주]를 버렸다(수량이 아니므로). 그런데 [주]에는 계수의 **적용
    조건**이 있다 — 특히 `공구손료 및 경장비의 기계경비는 인력품의 3%로 계상한다`.

    🔴 그 3%가 **64품목 전부가 아니라 26품목(41%)에만** 붙는다. 119차가 후보로
    올린 *"★공구손료 3% 등재 여부"*는 **일괄 적용이 아니라 품목별 플래그**여야
    한다는 뜻이다 — 이 수치가 사라지면 그 전제를 다시 세우게 된다.

    🔴 그리고 천창유리 [주]는 번호가 **①②④**(③ 누락)이고 **②와 ④가 같은 말**이다.
    64품목 중 번호 이상은 **이 1건뿐**이다.

    ⚠️ 의존성·시스템 폰트가 없으면 skip한다(125·126차와 같다).
    """
    import pytest
    pytest.importorskip("pdfplumber")
    pytest.importorskip("fontTools")
    pytest.importorskip("pypdf")
    import pumsem_extract as px

    try:
        rows = px.extract_notes()
    except px.FontsUnavailable as exc:
        pytest.skip("시스템 Batang/Gulim 없음: %s" % exc)

    assert len(rows) == 64
    assert all(notes for _, _, notes in rows), "[주]가 없는 품목이 있다"

    hit = px.classify_notes(rows)

    # 🔴 공구손료 3% — 전 품목 일괄이 아니다
    assert len(hit["공구손료3%"]) == 26, len(hit["공구손료3%"])
    by_cat = {}
    for cat, _ in hit["공구손료3%"]:
        by_cat[cat] = by_cat.get(cat, 0) + 1
    assert by_cat.get("행잉거터공사", 0) == 0, "행잉거터공사에는 3%가 붙지 않는다"
    assert by_cat.get("철골공사(비닐·파이프자재)") == 5, "비닐 철골 5품목은 전부 붙는다"

    # 🔴25회차 F2 — 원문의 요율 규정은 **3종**이다. 127차는 3%만 보고
    #   나머지 38품목이 "규정 없음"으로 읽히게 했다.
    rates = px.rate_rules(rows)
    assert {k: len(v) for k, v in rates.items()} == {"2": 4, "3": 26, "5": 2}, rates
    assert {c for c, _ in rates["2"]} == {"알루미늄공사"}          # 공구손료 2%
    assert {c for c, _ in rates["5"]} == {"온실피복공사"}          # 잡재료 5%
    # 🔴25회차 F3 — 알루미늄 6(선홈통)은 **한 [주]에서 2%와 3%를 둘 다** 말한다
    assert ("알루미늄공사", 6) in rates["2"] and ("알루미늄공사", 6) in rates["3"]

    # 나머지 적용 조건의 분포
    assert len(hit["장비8시간"]) == 38
    # 🔴25회차 F1 — 127차가 26으로 셌으나 2%·5% 줄을 오분류한 것이었다
    assert len(hit["별도계상"]) == 22
    assert len(hit["재료량설계수량"]) == 10
    mat = {cat for cat, _ in hit["재료량설계수량"]}
    assert mat == {"철골공사", "알루미늄공사"}, mat

    # 🔴 원문 결함 — 번호 이상은 천창유리 1건뿐이다
    odd = []
    for cat, no, notes in rows:
        seq = px.note_numbers(notes)
        if seq and seq != list(range(1, len(seq) + 1)):
            odd.append((cat, no, seq))
    assert odd == [("온실피복공사", 1, [1, 2, 4])], odd

    # 그 품목이 엔진에서 천창유리인가(공종 1번)
    cover = [x for x in e.PUMSEM_ITEMS if x.category == "온실피복공사"]
    assert cover[0].name == "천창유리", cover[0].name

    # 적용 조건은 **엔진 상수가 아니다**(공구손료 3% 등재는 ★사용자 결정)
    import smartfarm_engine as _e
    for attr in ("PUMSEM_TOOL_LOSS_RATE", "PUMSEM_NOTE_FLAGS"):
        assert not hasattr(_e, attr), (
            f"{attr}: [주]의 적용 조건이 엔진 상수로 올라왔다 — 26품목에만 붙는 "
            f"규정이고 등재는 ★사용자 결정이다")

    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8").read()
    for probe, why in (
        ("26품목", "3%가 전 품목 일괄이 아니라는 기록"),
        ("①②④", "천창유리 [주] 번호 누락"),
        ("유리닦기", "p.129와 p.144가 서로 다른 말을 한다는 기록"),
    ):
        assert probe in reg, (
            f"127차 [주] 기록에서 `{probe}`가 사라졌다 — {why}")

def test_128cha_pdf_guards_skip_instead_of_silently_passing(monkeypatch):
    """128차 — 원문 대조 가드 3종이 **조용히 통과하지 않고 skip**되는가.

    125~127차 가드는 "엔진 64계수·제원 표·[주] 적용 조건이 원문과 같다"를 보증한다.
    그런데 이 환경은 **pip 패키지가 세션 간 유실**되고(CLAUDE.md), 시스템 Batang/Gulim이
    없는 기계도 있다. 그때 세 가드는 **skip**된다 — 보증이 사라지는데 게이트는 green이다.

    🔴 실측: 시스템 폰트를 못 찾게 하면 3파일 게이트가 **290 passed가 아니라
    303 passed + 5 skipped**가 된다. 작업지시서 2절이 skip 경고는 달았으나
    **그때의 기대치를 적지 않아** 다른 기계에서 숫자가 어긋난다.

    이 테스트는 두 가지를 고정한다:
      · 세 가드가 폰트 부재 시 **예외가 아니라 skip**으로 끝난다(조용한 통과도 아니다)
      · 2절 스냅샷에 **skip 시 기대치**가 적혀 있다
    """
    import pytest
    pytest.importorskip("pdfplumber")
    pytest.importorskip("fontTools")
    pytest.importorskip("pypdf")
    import pumsem_extract as px

    def boom(*a, **k):
        raise px.FontsUnavailable("128차 테스트 — 시스템 폰트가 없는 상황을 흉내낸다")

    monkeypatch.setattr(px, "_system_index", boom)

    guards = (
        test_125cha_pumsem_64_reextracted_from_pdf_textlayer,
        test_126cha_spec_tables_reextracted_from_pdf,
        test_127cha_pumsem_notes_conditions_and_defects,
    )
    for fn in guards:
        with pytest.raises(BaseException) as caught:
            fn()
        assert caught.type.__name__ == "Skipped", (
            f"{fn.__name__}: 폰트가 없을 때 skip이 아니라 {caught.type.__name__}으로 "
            f"끝났다 — 조용히 통과하거나 게이트를 깨뜨린다")

    # 2절 스냅샷이 skip 시 기대치를 적고 있는가
    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    order = open(_o.path.join(repo, "작업지시서.md"), encoding="utf-8").read()
    assert "303 passed + 5 skipped" in order, (
        "2절 스냅샷에 **폰트·의존성 부재 시 기대치**가 없다 — 다른 기계에서 게이트를 "
        "돌린 사람이 숫자 불일치로 멈추거나, 반대로 skip을 정상으로 오인한다")

def test_129cha_redteam25_corrections_are_recorded():
    """129차 — 레드팀 25회차의 정정이 기록에 고정돼 있는가.

    발견 11건 중 [상] 3건이 **모두 127차 [주] 분류기**에 몰려 있었다:
      · **F1** 원문 요율이 3%만이 아니라 **2%·5%도 있어** "별도 계상 26"이 실제 **22**였다.
        틀린 수를 **테스트가 하드 게이트로 고정**하고 있었다.
      · **F2** 공구손료 **2% 4품목**·잡재료 **5% 2품목**이 산출물 어디에도 없었다 →
        119차 ★등재 후보는 "있음/없음 플래그"가 아니라 **품목별 요율값**이어야 한다.
      · **F3** 알루미늄 6(선홈통)이 **한 [주]에서 2%와 3%를 동시에** 말한다 —
        번호는 연속이라 127차의 기계 검사에 걸리지 않았고 *"원문 결함 2건"*이 틀렸다.

    그리고 **F8이 기회**였다 — 텍스트층이 `?근공`/`??공`을 구분할 만큼 복원되므로
    **직종명까지 기계 대조**할 수 있고, 그 부산물로 91차부터 이어온 철근공
    [확인요망]의 "원문 표기" 부분이 닫힌다(위 125차 가드에 넣었다).
    """
    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8").read()
    engine = open(_o.path.join(repo, "smartfarm_engine.py"), encoding="utf-8").read()
    order = open(_o.path.join(repo, "작업지시서.md"), encoding="utf-8").read()

    # F1 — 틀린 수(26)가 되살아나지 않았는가
    for text, where in ((reg, "레지스트리"), (engine, "엔진 주석")):
        assert "별도 계상 26" not in text and "별도계상 26" not in text, (
            f"{where}에 25회차 F1이 반증한 '별도 계상 26품목'이 남아 있다")

    # F2 — 요율 3종이 기록됐는가
    for probe, why in (
        ("2%", "공구손료 2% 4품목 — 127차가 누락했다"),
        ("5%", "잡재료 5% 2품목 — 127차가 누락했다"),
        ("요율값", "★등재 후보가 플래그가 아니라 요율값이라는 정정"),
    ):
        assert probe in reg, f"25회차 F2 기록에서 `{probe}`가 사라졌다 — {why}"

    # F3 — 🔴재검증에서 **113차가 이미 기록**했음이 드러났다. 가드는 "127차가 113차를
    #   확인하지 않았다"는 사실 쪽을 지킨다(`원문 결함 2건`은 113·109차의 정당한
    #   서술에도 쓰여 금지 문자열로 쓸 수 없다 — 과도한 가드였다).
    assert "113차가 이미 기록한 것" in reg, (
        "25회차 F3 재검증: 113차가 선홈통 2%/3%·천창유리 ③ 누락을 이미 기록했다는 "
        "연결이 사라졌다 — 그것이 없으면 또 '새 발견'으로 다시 세게 된다")
    assert "113차보다 후퇴" in reg, (
        "127차가 113차 기록을 확인하지 않아 후퇴했다는 메타 발견이 사라졌다")

    # F8 — 철근공 원문 표기가 기계 확인됐다는 기록
    assert "기계로 확인" in reg or "기계 확인" in reg, (
        "25회차 F8: 철근공 원문 표기의 기계 확인 기록이 사라졌다")

    # F9 — "독립 경로" 과신이 완화됐는가
    assert "같은 실수를 반복할 경로가 없다" not in reg, (
        "25회차 F9가 반증한 독립성 단정이 되살아났다")

    # F11 — 모호 매핑 가드가 살아 있는가
    import pumsem_extract as px
    assert hasattr(px, "AmbiguousGlyph"), "25회차 F11 가드(모호 매핑 예외)가 사라졌다"

def test_130cha_confirm_pending_ledger_exists():
    """130차 — `[확인요망]` **대장**이 있고 5항목이 살아 있는가.

    129차 F3는 *"127차가 113차 기록을 확인하지 않아 후퇴했다"*였다. 130차에 같은
    점검을 넓히니 **한 단계 더** 있었다 — B(선홈통)는 113차 제기 후 **114차가 이미
    구조를 설명**(방법 ② "표준품셈 참조는 최근 기준 우선" + `[주]⑤`의 표준품셈 참조)
    했는데 127·129차 둘 다 몰랐다. **같은 원문을 세 번 읽으며 두 번 후퇴**했다.

    원인은 `[확인요망]`이 레지스트리 서술 속에 흩어져 **"지금 살아 있는 항목이
    무엇이고 어디까지 갔는가"를 한눈에 볼 수 없다**는 것이다. 이 테스트는 그
    대장이 사라지지 않게 한다.
    """
    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    led = _o.path.join(repo, "근거_확인요망대장_20260915.md")
    assert _o.path.exists(led), "[확인요망] 대장이 사라졌다 — 130차 산출물이다"
    text = open(led, encoding="utf-8").read()

    # 5항목이 살아 있는가
    for tag, why in (
        ("비닐 노무비", "A — 108차 제기, 130차에 원천 표 2개 확정"),
        ("선홈통", "B — 113차 제기, **114차가 구조 설명**(두 번 재발견됐다)"),
        ("이중층", "C — 115차: 비닐 피복 계수의 전제"),
        ("철근공", "D — 91차부터, 129차에 원문 표기 기계 확인"),
        ("파이프 5종", "E — 118차: 비닐 고유 부재의 조사 출처"),
    ):
        assert tag in text, f"대장에서 항목 `{tag}`가 사라졌다 — {why}"

    # 130차가 찾은 원천 표(A) — 이 수치가 없으면 또 제6장을 뒤지게 된다
    for num, why in (
        ("702", "제6장 p.103 비닐 2021 노무비"),
        ("650", "제7장 p.166 표준품셈 열 노무비 — 702와 다르다"),
        ("439", "p.166 온실품셈 열 노무비 — 차트의 473과 다르다"),
        ("3,509", "두 표를 같은 계열로 잇는 총공사비"),
    ):
        assert num in text, f"대장에서 `{num}`이 사라졌다 — {why}"

    # 🔴 114차 해석으로 거슬러 올라간 사실이 기록돼 있는가
    assert "114차가" in text and "최근 기준" in text, (
        "B 항목에서 114차 해석 연결이 사라졌다 — 그것이 없으면 또 113차까지만 간다")

    # 대장 사용법(1→2→3)이 남아 있는가 — 이것이 재발 방지 장치다
    assert "먼저 이 표" in text, "대장 사용법이 사라졌다"

def test_131cha_ledger_counts_items_not_strings():
    """131차 — `[확인요망]` **문자열 수는 항목 수가 아니다**.

    130차는 *"레지스트리 전체 50건 / `PUMSEM_ITEMS` 15건"*이라 적었다. 131차에 같은
    방식으로 다시 세니 **53건 / 18건**이다 — 🔴**늘어난 3건은 130차가 대장을 만들며
    레지스트리에 쓴 로그 문장 자체**다(*"`[확인요망]` 대장을 만들었다"* 등). 즉
    **대장을 만드는 행위가 대장의 집계를 늘린다.**

    35건을 전수로 열어 읽으니 **9건은 이미 닫혔고**(`WARRANTY_STATUTORY`는 4건 전부)
    **1건은 중복**(`TOTAL_PYEONG_PRICE`의 비닐 노무비 = A)이며, 살아 있는 25 문자열은
    **항목으로는 20개**다 — 한 항목이 **여러 상수에 걸치기 때문**이다.

    이 테스트가 막는 것: ①닫힌 항목이 다시 열린 것처럼 세어지는 것 ②`grep` 집계를
    항목 수로 쓰는 것 ③한 항목이 상수별로 흩어져 다시 후퇴하는 것.
    """
    import os as _o, json as _j, re as _re, io as _io
    repo = _o.path.dirname(_o.path.abspath(__file__))
    text = open(_o.path.join(repo, "근거_확인요망대장_20260915.md"), encoding="utf-8").read()

    # ① 닫힌 4건이 "닫힘"으로 표시돼 있는가 — 닫은 차수까지
    for const, closer, why in (
        ("WARRANTY_STATUTORY", "2026-08-18", "전기·통신 2건을 법제처 원문 열람으로 해소"),
        ("FR_TABLE", "68차", "직렬 열저항으로 3행 전부 재현 — 1장 54%는 철회됐다"),
        ("ACTUALS_COUNT", "93차", "관리동·방풍 포함 여부를 도면으로 확정"),
        ("GROUND_LOSS_COEF", "85차", "식 형태 H_S = F·L_s·(ΔT − Θ) 확정"),
    ):
        assert const in text and closer in text, (
            f"대장에서 `{const}`의 닫힘 표시(`{closer}`)가 사라졌다 — {why}")

    # ② 🔴 닫힌 것이 레지스트리에서 실제로 닫혔는지 원본으로 확인한다(대장 주장의 뒷받침)
    reg = _j.load(_io.open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8"))
    consts = reg["constants"]
    war = consts["WARRANTY_STATUTORY"]
    assert "해소" in war["status_note"] and "1차 출처 확보 완료" in war["status_note"], (
        "WARRANTY_STATUTORY의 해소 선언이 사라졌다 — 대장의 닫힘 판정 근거다")
    assert "철회" in consts["FR_TABLE"]["source"], (
        "FR_TABLE 68차 F1의 철회 기록이 사라졌다 — 1장 54%가 다시 열린 것처럼 보인다")

    # ③ 🔴 문자열 집계가 항목 수보다 크다는 사실 자체를 실측으로 못 박는다
    strings = sum(len(_re.findall(r"\[확인요망\]", _j.dumps(v, ensure_ascii=False)))
                  for v in consts.values())
    LIVE_ITEMS = 24   # PUMSEM 5(130차) + 그 밖 19(131차, 🔴26회차 F4로 20→19)
    assert strings > LIVE_ITEMS, (
        f"레지스트리 [확인요망] 문자열 {strings}건이 살아 있는 항목 {LIVE_ITEMS}개보다 "
        "많지 않다 — 131차 실측(53 > 25)과 어긋난다. 항목을 다시 세어라")
    assert "**53건 / `PUMSEM_ITEMS` 18건**" in text, (
        "131차 실측(53 / 18)이 대장에서 사라졌다 — 130차의 50 / 15와 다르다는 것이 발견이다")
    assert strings >= 53, (
        f"레지스트리 [확인요망]이 {strings}건으로 131차 실측 53건보다 줄었다 — "
        "서술이 지워졌다는 뜻이다. 어느 항목이 사라졌는지 확인하라")
    assert "자기증식" in text, (
        "🔴 문자열 집계가 자기증식한다는 131차 발견이 대장에서 사라졌다")
    assert "세지 않는다" in text, (
        "`grep`으로 세지 말라는 규칙이 사라졌다 — 130차가 그렇게 세어 틀렸다")

    # ④ 항목 식별자가 남아 있는가(AC3는 닫힘 표기로, AC5는 신규로)
    for tag, why in (
        ("U1", "유리 5.3 kcal — 경쟁 가설 2개가 같은 숫자에 도달"),
        ("U2", "u_design 5.7 vs u_period 2.66 이원화 — ★77차 B2가 선행"),
        ("FR2", "농사로 표는 유리온실 U=7 기준 — 타 피복은 근사"),
        ("FR3", '"피복"이 클래딩인지 스크린인지 원문 정의 없음'),
        ("FL1", "efficiency 0.85의 발열량 기준(HHV/LHV) 미상"),
        ("GL1", "대규모·소규모 면적 경계 미정의"),
        ("CV1", "핫박스 실측의 풍속 조건 미명시"),
        ("IN1", "권고표이지 개별 온실 실측이 아니다"),
        ("AC2", "최선동 +1,000의 정체"),
        ("AC3", "🔴26회차 F4 — 94차가 이미 닫았다(대장에 닫힘으로 남긴다)"),
        ("AC5", "94차가 새로 연 것 — 2,323 vs 원문 2,321.87, 밴드 여유 158원→42원"),
        ("AC4", "이두희 방풍 폭 환산 불가"),
        ("CM1", "최선동 안개분무 18,500,000 — 3.7%p"),
        ("CM2", "콘트롤박스 — 한수진·최선동 둘 다"),
        ("CM3", "08 예인형 개폐장치 집계표 미반영"),
        ("CM4", "부가세환급 5% 사유 미기재"),
        ("CM5", "임미라 4,258.86 vs 4,068"),
        ("TP1", "협회 원표·고시 원문 미확보"),
        ("SB1", "스마트팜 시설현대화사업 독립 사업명 미확인"),
        ("OP1", "광열동력비 ↔ 수도광열비 중복 여부"),
        ("WD1", "마산 ↔ 창원 별칭 — ★사용자 결정"),
    ):
        assert tag in text, f"대장에서 항목 `{tag}`가 사라졌다 — {why}"

    # ⑤ 🔴 항목이 상수 경계를 넘는다는 것 — 이것이 흩어짐의 원인이다
    for item, spans in (
        ("U2", ("U_VALUE", "U_DESIGN", "PERIOD_LOAD_ADJUST_K")),
        ("CM1", ("CAPEX_MAJOR_CASE_CHUNKS", "CAPEX_MAJOR_UNCLASSIFIED",
                 "CAPEX_MAJOR_EVIDENCE_STATUS")),
    ):
        for c in spans:
            assert c in text, (
                f"`{item}`이 걸친 상수 `{c}`가 대장에서 사라졌다 — "
                "한 항목이 상수별로 흩어지는 것이 129·130차 후퇴의 원인이다")

    # ⑥ 회귀 기준에 닿는 두 항목은 ★사용자 결정임이 남아 있어야 한다
    assert "BENCHMARK_BANDS" in text and "원채원 ROI 14.2%" in text, (
        "AC3(밴드)·U2(기간부하)가 회귀 기준에 닿는다는 경고가 사라졌다")


def test_132cha_registry_prose_cited_files_are_not_empty():
    """132차 — 🔴 레지스트리가 *"보존"*을 주장하는 파일이 **비어 있었다**.

    `OPEX_ITEM_CATEGORIES`의 `desc`는 *"원본은 `소득분석DB/농촌진흥청_…csv`
    (CP949, 1,213행)에 보존"*이라 적는다. 그 파일은 **0바이트**이고, `git`상
    **승격 커밋(b652848)부터 줄곧** 비어 있었다 — 원본은 리포에 들어온 적이 없다.

    `source_refs`가 `null`인 상수가 **16개**라 `audit_traceability.py`는 이 주장을
    **검사하지 않는다**(그래서 게이트는 PASS였다). 이 테스트가 그 사각을 메운다:
    레지스트리 서술이 **전체 경로로 지목한** 리포 파일은 실재하고 비어 있지 않아야
    한다. 알려진 1건만 예외로 두되, **문서에 기록된 채로만** 통과시킨다.
    """
    import os as _o, json as _j, re as _re, io as _io
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = _j.load(_io.open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8"))

    # 대장이 이 구멍을 기록하고 있어야 예외가 성립한다
    led = open(_o.path.join(repo, "근거_확인요망대장_20260915.md"), encoding="utf-8").read()
    assert "0바이트" in led and "b652848" in led, (
        "OP1의 원문 부재(0바이트·승격 커밋)가 대장에서 사라졌다 — "
        "그 기록이 없으면 아래 예외를 둘 근거도 없다")
    # 보존 실패(132차 발견) — 서술이 "보존"을 주장하는데 비어 있다
    KNOWN_EMPTY = {"소득분석DB/농촌진흥청_농산물소득분석 조사입력항목코드_20201015.csv"}
    # 설계된 tombstone(CLAUDE.md "손대지 말 것") — 성격이 다르므로 따로 둔다
    TOMBSTONES = {"cases/gyeongbuk_ddalgi.json"}
    assert "tombstone" in led, (
        "tombstone과 보존 실패를 구분한 132차 기록이 대장에서 사라졌다 — "
        "둘을 뭉뚱그리면 다음에 0바이트를 보고 또 헷갈린다")

    pat = _re.compile(r"`([^`]*/[^`]+\.(?:csv|xlsx|xls|pdf|json|md|jsonl))`")
    cited = {}
    for name, v in reg["constants"].items():
        prose = " ".join(str(v.get(f) or "") for f in ("desc", "source", "status_note"))
        for m in pat.finditer(prose):
            cited.setdefault(m.group(1).strip(), set()).add(name)
    assert len(cited) >= 7, f"전체 경로 인용이 {len(cited)}종뿐이다 — 132차 실측은 7종이다"

    bad = []
    for path, owners in sorted(cited.items()):
        full = _o.path.join(repo, path)
        if not _o.path.exists(full):
            bad.append(f"{path} 없음 ({','.join(sorted(owners))})")
        elif _o.path.getsize(full) == 0 and path not in (KNOWN_EMPTY | TOMBSTONES):
            bad.append(f"{path} 0바이트 ({','.join(sorted(owners))})")
    assert not bad, (
        "레지스트리가 지목한 원문이 사라졌거나 비었다: " + " / ".join(bad) +
        " — 값을 '실측'이라 부를 근거가 리포에 없다는 뜻이다")

    # 🔴 알려진 1건이 복구되면 예외를 지우라고 알린다(조용히 남겨 두지 않는다)
    for path in KNOWN_EMPTY:
        full = _o.path.join(repo, path)
        if _o.path.exists(full) and _o.path.getsize(full) > 0:
            raise AssertionError(
                f"{path}가 복구됐다 — KNOWN_EMPTY에서 빼고 OP1(광열동력비↔수도광열비 "
                "중복 여부)을 원문으로 확인하라. 132차가 기다리던 자료다")


def test_132cha_ijunhee_08_breakage_is_a_single_cell():
    """132차 — CM3: `08 예인형`의 누락 원인이 **단일 셀**임을 원본에서 고정한다.

    `공종별내역서!E276`(개폐모터 3대 단가)이 `'단가대비표 (2)'!#REF!`로 끊겨
    `F276 → F298(SUM)`까지 전파된다. **노무 열은 멀쩡**하고(8,603,500),
    파손 셀 하나를 뺀 나머지 21줄은 전부 산출값을 갖는다(재료 12,578,871).

    54차 F6이 *"08만 주석 없이 #REF!"*라 관찰한 것을 **원인 셀 단위로** 못 박는다.
    """
    import os as _o
    import pytest as _pt
    openpyxl = _pt.importorskip("openpyxl")
    repo = _o.path.dirname(_o.path.abspath(__file__))
    src = _o.path.join(repo, "스마트팜스펙", "견적참조",
                       "충남 서산(이준희) 온실 시공 견적서_부가세 환급.xlsx")
    if not _o.path.exists(src):
        _pt.skip("이준희 견적 원본이 없다 — 리포 밖 자료 환경")

    wf = openpyxl.load_workbook(src, data_only=False)
    wv = openpyxl.load_workbook(src, data_only=True)
    det_f, det_v = wf["공종별내역서"], wv["공종별내역서"]

    assert det_f["E276"].value == "='단가대비표 (2)'!#REF!", (
        "E276의 파손 수식이 바뀌었다 — CM3의 원인 셀이다")

    # 🔴 26회차 F3 — 종전 가드는 `if ws.title == "공종별내역서"`로 **다른 시트를
    #    수집 자체에서 버렸다**. 주석은 "워크북 전체"라 적었으나 타 시트가 새로
    #    깨져도 절대 실패하지 않았다 — 132차 유일성 주장이 게이트된 적이 없었다.
    #    (그 사각에서 26회차 F2의 오기가 났다: `단가대비표 (2)!O432`는 라벨이 아니라
    #     `조사가격1` 가격 열이다.)
    broken = {}
    for ws in wf.worksheets:            # 수식본을 본다 — 원인 셀을 잡아야 한다
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                if isinstance(v, str) and v.startswith("=") and "#REF!" in v:
                    broken.setdefault(ws.title, set()).add(c.coordinate)
    assert broken == {
        "공종별내역서": {"E276"},
        "단가대비표 (2)": {"B331", "C331", "D331", "B332", "C332", "D332",
                        "B333", "C333", "D333", "B334", "C334", "D334", "O432"},
        "양액물량공량": {"A371", "B371"},
    }, f"워크북의 #REF! 원인 셀 집합이 바뀌었다: { {k: sorted(v) for k, v in broken.items()} }"

    # 내역서 금액 열로 전파된 칸(E276 → F298 계열)
    money = {c.coordinate for row in wv["공종별내역서"].iter_rows() for c in row
             if isinstance(c.value, str) and "#REF!" in c.value and c.column_letter in "EFKL"}
    assert money == {"E276", "F276", "K276", "L276", "F298", "L298"}, (
        f"내역서 금액 열의 #REF! 전파가 바뀌었다: {sorted(money)}")

    # 🔴 유일성의 진짜 근거는 "라벨 칸뿐"이 아니라 **하류 참조가 없다**는 것이다
    downstream = [
        (ws.title, c.coordinate) for ws in wf.worksheets
        for row in ws.iter_rows() for c in row
        if isinstance(c.value, str) and c.value.startswith("=")
        and "단가대비표 (2)" in c.value
        and any(("%s%s" % (col, n)) in c.value
                for col in "ABCDEFGHIJKLMNOPQR" for n in ("331", "332", "333", "334", "432"))
    ]
    assert not downstream, (
        f"파손 행을 참조하는 수식이 생겼다: {downstream} — "
        "집계표 총계가 더 이상 무사하다고 말할 수 없다")

    # 노무 열은 파손되지 않았다
    assert det_v["H298"].value == 8_603_500, "08 블록 노무비 합계가 바뀌었다"

    # 파손 셀을 뺀 복원 가능 부분
    mat = sum(v for v in (det_v[f"F{r}"].value for r in range(277, 298))
              if isinstance(v, (int, float)))
    assert mat == 12_578_871, f"복원 가능 재료비가 {mat:,}로 바뀌었다 (132차 실측 12,578,871)"

    # 🔴 미채택 4공종과의 차이 — 08만 '본 공사제외' 주석이 없다
    agg_v, agg_f = wv["공종별집계표"], wf["공종별집계표"]
    notes = {r: agg_v[f"L{r}"].value for r in (15, 17, 18, 19, 20, 27)}
    assert notes[15] is None, "08 행에 '본 공사제외' 주석이 생겼다 — 미채택 판정 근거가 바뀐다"
    assert all(notes[r] == "본 공사제외" for r in (17, 18, 19, 20, 27)), (
        "'본 공사제외' 주석 5개 행(10·11·1101·1102·1206)이 바뀌었다 — 08과의 대조군이다")

    # 🔴 26회차 F1 — 대조군이 전수가 아니었다. 문서는 "4공종"이라 적었는데 주석 행은 5개이고,
    #    무엇보다 **주석 없이 금액이 0인 행이 08만이 아니다**. R10(0401 PO)은 내역서에
    #    114,241,498원 블록이 실재하는데 **수량 공란**으로 총계에서 빠진다 — 주석도 #REF!도 없다.
    silent_zero = {r for r in range(5, 32)
                   if agg_v[f"A{r}"].value and not agg_v[f"K{r}"].value
                   and agg_f[f"L{r}"].value is None}
    assert silent_zero == {8, 10, 15, 21, 29}, (
        f"주석 없이 금액 0인 행이 {sorted(silent_zero)}로 바뀌었다 — "
        "26회차 실측은 8·10·15·21·29 다섯이다(08만이 아니다)")
    assert agg_v["D10"].value == 92_115_438 and agg_f["C10"].value is None, (
        "R10(0401 PO)의 '수량 공란으로 제외' 패턴이 바뀌었다 — F1 대조군의 핵심이다")

    # 08에 고유하게 남는 것: 주석도 없고 금액 열 수식도 없는 유일한 행
    def _has_formula(r):
        return any(isinstance(agg_f[f"{c}{r}"].value, str)
                   and str(agg_f[f"{c}{r}"].value).startswith("=") for c in "DEFGHIJK")
    no_note_no_formula = {r for r in range(5, 32)
                          if agg_v[f"A{r}"].value and agg_f[f"L{r}"].value is None
                          and not _has_formula(r)}
    assert no_note_no_formula == {15}, (
        f"'주석도 없고 금액 수식도 없는' 행이 {sorted(no_note_no_formula)}다 — "
        "08(R15)의 고유성이 이것뿐이라는 26회차 정정이 깨졌다")


def test_132cha_parkgyuhyeon_refund_base_is_material_only():
    """132차 — CM4: 5%가 **비목 구성으로 설명되지 않음**을 산술로 고정한다.

    환급 기준액 313,542,997은 **재료비만**이다(노무 164,580,818 전액 비환급).
    10%면 31,354,300이고 계상액 15,677,150은 **정확히 절반**이다 →
    *"노무비가 섞여서 5%"* 가설은 배제된다.

    대조군: 백가은·조윤정은 기준액이 **재+노+경**인데 요율이 10%다 —
    두 표본은 **기준액 정의도 요율도 다르다**. (레지스트리 등재 수치 간 산술)
    """
    # 박규현 — 3분류가 재료비 총액으로 닫힌다(노무는 전액 비환급)
    refund, nonrefund, zero_rated = 313_542_997, 206_856_006, 14_497_250
    material, labor = 370_315_435, 164_580_818
    assert refund + nonrefund + zero_rated == material + labor
    # 🔴 26회차 F8 — 종전의 두 번째 단언 `nonrefund - labor + refund + zero == material`은
    #    첫 단언의 양변에서 labor를 뺀 **항등식**이라 정보가 0이었다(노무가 어떤 비율로
    #    섞여 있어도 통과한다). 실제로 고정해야 하는 것은 **환급·영세에 노무가 0**이고
    #    **비환급이 노무를 전부 머금는다**는 분해다.
    nonrefund_material = 42_275_188          # 26회차 재집계(온실 23,486,906 + 양액 18,788,282)
    assert nonrefund_material + labor == nonrefund, (
        "비환급이 노무비 전액을 머금는다는 분해가 깨졌다")
    assert refund + zero_rated + nonrefund_material == material, (
        "환급·영세·비환급재료의 합이 재료비 총액과 맞지 않는다 — "
        "환급 기준액이 재료비만이라는 CM4의 배제 논거다")
    assert round(refund * 0.05) == 15_677_150, (
        "5% 계상액이 재현되지 않는다 (313,542,997×5% = 15,677,149.85 → 반올림)")
    assert round(refund * 0.10) == 31_354_300 and 15_677_150 * 2 == 31_354_300, (
        "계상액이 전액 VAT의 정확히 절반이라는 사실이 깨졌다")

    # 백가은·조윤정 — 기준액이 재+노+경이고 요율은 10%
    bg_mat, bg_lab, bg_exp = 286_680_383, 100_648_000, 11_300_000
    bg_refund, bg_nonrefund = 203_179_883, 195_448_500
    assert bg_refund + bg_nonrefund == bg_mat + bg_lab + bg_exp, (
        "백가은·조윤정의 환급 기준액이 재+노+경이라는 대조군이 깨졌다")
    assert bg_refund // 10 == 20_317_988

    import os as _o
    repo = _o.path.dirname(_o.path.abspath(__file__))
    doc = open(_o.path.join(repo, "근거_대장3항목_리포내확인_20260915.md"),
               encoding="utf-8").read()
    assert '"노무비가 섞여서 5%"는 성립하지 않는다' in doc, (
        "CM4의 배제 결론(경쟁 가설 하나를 제거한 문장)이 근거문서에서 사라졌다")
    assert "정확히 그 절반" in doc, (
        "5%가 전액 VAT의 절반이라는 산술 결과가 근거문서에서 사라졌다")
    assert "판단성" in doc, (
        "제도 해석을 하지 않았다는 표기가 사라졌다 — 판정 자동화 금지 선이다")


def test_133cha_refless_measured_constants_are_pinned():
    """133차 — 🔴 `source_refs`가 0건이면 **원문 실재 검사가 한 번도 돌지 않는다**.

    `audit_traceability.py`의 레지스트리 검사는 `for r in ent.get("source_refs", [])`라
    **빈 리스트를 0회 순회**한다. 검사되는 것은 `status`가 enum 안에 있는지뿐이고
    `"실측"`은 enum 안에 있다 → **적어두기만 하면 통과한다.**

    전수 결과: 54개 중 **16개가 refs 0건**이고, 그중 **12개가 '실측' 계열**이다.
    🔴 패턴이 거꾸로다 — **법령·고시에서 온 21개(공공기준·법정기준)는 전부 ref가
    있는데**, 전사 오류가 가장 일어나기 쉬운 '실측' 16개 중 **11개(69%)가 0건**이다.

    이 테스트는 **그 12개를 고정**한다. 새 상수가 ref 없이 '실측'으로 들어오면
    실패하고, 12개 중 하나에 ref가 붙으면 **목록을 줄이라고** 실패한다.
    """
    import os as _o, json as _j, io as _io
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = _j.load(_io.open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8"))
    consts = reg["constants"]

    # 🔴 134차에 (A)계열 5개(+참고기준 1개)를 부착해 12 → 7로 줄었다.
    #    🔴 **151차에 6으로 줄었다** — `OVERHEAD_RATES`를 (B)로 분류한 것이 틀렸다.
    #    *"원가계산서 6건 중 일부가 Google Drive"*라 적었으나 **3건은 리포에 실재**한다
    #    (이두희 원가계산서 · 최혁진 내역서 · 우민재 xlsx). 붙여 보니 **등재의
    #    「6개 문서 전부 동일」 단정이 반증**됐다(산재 3.56/3.7/3.764%로 셋 다 다르다).
    #    남은 6개는 **붙일 원문이 없거나 ref 개념이 없는 것들**이다.
    REFLESS_MEASURED = {
        # (B) 원문이 리포 밖이다 — ★사용자가 넣어야 붙일 수 있다
        "SPEC_TABLE",                    # 농사로 마스터 xlsx(2025-108호, 249종)
        "SPEC_COUNT",                    # 그 표의 종수(파생이기도 하다)
        # 🔴163차 — `REGION_DESIGN_LOAD`는 **여기서 빠졌다**: 고시 [별표]가 리포 안
        #   구조검토서 2건(함평·천안, PDF p5~p6)에 전재돼 있었고 172지역을 전수
        #   대조(지명 집합 전량 일치·하향 0건)해 partial 2건을 붙였다. 133차의
        #   "원문이 리포에 없다"는 **현행 2025-108호 전면표**에 한해 유효하다.
        "OPEX_ITEM_CATEGORIES",          # 🔴 132차 — 인용 CSV가 0바이트
        # (C) 파생·결정이라 원문 ref 개념이 없다 — 결함이 아니다
        "CAPEX_MAJOR_CATEGORIES",        # 사용자 제안 분류표(2026-07-16 대화)
        "RFQ_REQUIRED_CATEGORIES_DEFAULT",  # CAPEX_MAJOR_EVIDENCE_STATUS에서 도출
    }
    got = {k for k, v in consts.items()
           if v.get("status") in ("실측", "부분실측") and not v.get("source_refs")}
    assert got == REFLESS_MEASURED, (
        f"'실측' 계열 refs 0건 집합이 바뀌었다.\n  새로 들어옴: {sorted(got - REFLESS_MEASURED)}"
        f"\n  빠짐(ref가 붙었다면 목록에서 지워라): {sorted(REFLESS_MEASURED - got)}\n"
        "ref 없이 '실측'을 표방하면 추적성 감사가 그 출처를 한 번도 보지 않는다")

    # 🔴 거꾸로 된 패턴 — 법령·고시 계열은 전부 ref가 있다(이것이 깨지면 더 나빠진 것이다)
    statutory = {k: v for k, v in consts.items() if v.get("status") in ("공공기준", "법정기준")}
    assert statutory and all(v.get("source_refs") for v in statutory.values()), (
        "공공기준·법정기준 상수 중 refs가 사라진 것이 있다 — "
        "지금까지 이 계열은 21개 전부 ref를 갖고 있었다")

    # 산출물에 닿는데 아직 사각인 둘은 특히 표시해 둔다(★사용자가 원문을 넣어야 한다)
    for k, why in (("SPEC_TABLE", "select_specs()가 render_report·run_report에서 쓰인다"),):
        assert k in REFLESS_MEASURED, f"{k}가 목록에서 빠졌다 — {why}"
    # 🔴163차 — 반대 방향으로 고정한다: `REGION_DESIGN_LOAD`는 **풀렸다**.
    #   webapp이 조회 결과에 status='실측'을 찍어 내보내는데 그 근거가 서술뿐이던
    #   상태가 끝났다 — 되돌아가면 그 '실측' 표기가 다시 무근거가 된다.
    assert ("REGION_DESIGN_LOAD" not in REFLESS_MEASURED
            and consts["REGION_DESIGN_LOAD"].get("source_refs")), (
        "🔴 REGION_DESIGN_LOAD의 refs가 사라져 다시 사각이 됐다")


def test_133cha_audit_report_surfaces_the_blind_spot():
    """133차 — 감사 리포트가 **그 사각을 매번 드러내는지**.

    종전 리포트에는 이 목록이 **어디에도 없었다**. 133차에 `추적성 사각` 절을
    신설했다 — **FAIL은 아니다**((C)처럼 정당한 0건이 섞여 있다). 판정 의미는
    바꾸지 않았고, **보이게** 만든 것이다.
    """
    import os as _o, sys as _s
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import audit_traceability as at

    a = at.audit()
    assert "refless_measured" in a, "감사 결과에 추적성 사각 집계가 사라졌다"
    assert len(a["refless_measured"]) == 5, (
        f"추적성 사각이 {len(a['refless_measured'])}건이다 — 133차 12건 → "
        "134차 7건 → 🔴151차 `OVERHEAD_RATES` 부착으로 6건 → "
        "🔴163차 `REGION_DESIGN_LOAD` 부착으로 **5건**")

    # 사각은 FAIL 사유가 아니다 — 판정 의미를 바꾸지 않았음을 고정한다
    assert a["ok"] and not a["hard_failures"], (
        "133차는 판정 의미를 바꾸지 않았다 — 사각을 hard_failure로 올리면 "
        "파생·결정 상수까지 FAIL이 된다")

    report = at.render_report(a)
    assert "추적성 사각" in report and "한 번도" in report, (
        "리포트에서 추적성 사각 절이 사라졌다 — 보이지 않으면 종전과 같다")
    for k in ("SPEC_TABLE", "SPEC_COUNT", "OPEX_ITEM_CATEGORIES"):
        assert k in report, f"리포트 사각 목록에서 {k}가 빠졌다"

    # 저장된 리포트 파일도 같은 절을 담고 있어야 한다(게이트 실행 산출물)
    saved = open(_o.path.join(repo, "검증게이트_감사리포트.md"), encoding="utf-8").read()
    assert "추적성 사각" in saved, (
        "저장된 감사 리포트에 사각 절이 없다 — audit_traceability.py를 다시 실행하라")

    doc = open(_o.path.join(repo, "근거_추적성사각_refs0건_20260915.md"), encoding="utf-8").read()
    assert "빈 리스트는 0회 순회한다" in doc, "133차 기제 설명이 근거문서에서 사라졌다"
    assert "붙일 수 있는데 안 붙었다" in doc, (
        "(A)계열 — 원문이 리포에 실재하는데 ref가 없다는 구분이 사라졌다")


def test_134cha_attached_refs_actually_back_their_values():
    """134차 — 붙인 `source_refs`가 **정말 그 값의 출처인지** 검산으로 고정한다.

    `_ref_ok()`는 **파일이 있는지만** 본다. 파일만 존재하면 통과하므로,
    엉뚱한 파일을 붙여도 게이트는 green이다 — **없느니만 못한 ref**가 될 수 있다.
    그래서 134차가 붙인 6개 상수는 **값과 원문의 연결을 다시 계산해** 고정한다:

    - `EQUIPMENT_DB_META` — `csv_row_counts`가 **실제 CSV 행수와 8/8 일치**하는가
    - `CAPEX_CASE_CHUNKS` — 9공종 합이 서술의 **직접공사비 총액과 원단위 일치**하는가
    - `CAPEX_MAJOR_UNCLASSIFIED` — 15키가 전부 **표본 파일로 덮이는가**
    - `PUMSEM_ITEMS` — 1차 출처가 **품셈 PDF**이고 기계 추출 스냅샷이 붙어 있는가
    """
    import os as _o, json as _j, io as _io, csv as _csv
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = _j.load(_io.open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8"))
    C = reg["constants"]

    ATTACHED = {
        "PUMSEM_ITEMS": 11, "ELECTRICAL_PUMSEM_LUMP_WON_PER_HA": 1,
        "CAPEX_CASE_CHUNKS": 2, "CAPEX_MAJOR_UNCLASSIFIED": 16,
        "CAPEX_MAJOR_EVIDENCE_STATUS": 17, "EQUIPMENT_DB_META": 9,
    }
    for k, n in ATTACHED.items():
        refs = C[k].get("source_refs") or []
        assert len(refs) == n, f"{k}의 refs가 {len(refs)}건이다 — 134차 부착은 {n}건"
        paths = [r["file"] for r in refs]
        assert len(set(paths)) == len(paths), f"{k}에 같은 파일이 두 번 붙었다"
        for r in refs:
            full = _o.path.join(repo, r["file"])
            assert _o.path.isfile(full), f"{k}: {r['file']} 이 사라졌다"
            assert _o.path.getsize(full) > 0, (
                f"{k}: {r['file']} 이 0바이트다 — 132차 OPEX와 같은 상황이 된다")
            assert r.get("note"), f"{k}: {r['file']} 에 note가 없다(왜 이 파일인지 적어야 한다)"

    # ① 🎯 EQUIPMENT_DB_META — CSV 행수를 다시 세어 등재값과 대조한다
    counts = C["EQUIPMENT_DB_META"]["value"]["csv_row_counts"]
    assert len(counts) == 8
    for name, n in counts.items():
        p = _o.path.join(repo, "기자재DB", name)
        assert _o.path.isfile(p), f"기자재DB/{name} 이 사라졌다 — 런타임이 읽는 파일이다"
        rows = None
        for enc in ("utf-8-sig", "cp949"):
            try:
                rows = list(_csv.reader(_io.open(p, encoding=enc, newline="")))
                break
            except (UnicodeDecodeError, LookupError):
                continue
        assert rows is not None, f"기자재DB/{name} 인코딩을 읽지 못했다"
        body = len([r for r in rows[1:] if any(c.strip() for c in r)])
        assert body == n, (
            f"기자재DB/{name} 행수가 {body}인데 등재값은 {n}이다 — "
            "ref가 가리키는 파일이 등재값의 출처라는 주장이 깨진다")
    csv_refs = {r["file"] for r in C["EQUIPMENT_DB_META"]["source_refs"]
                if r["file"].startswith("기자재DB/")}
    assert csv_refs == {"기자재DB/%s" % n for n in counts}, (
        "csv_row_counts의 8종과 붙인 CSV refs가 어긋난다")

    # ② 🎯 CAPEX_CASE_CHUNKS — 9공종 합이 서술 총액과 원단위로 맞는가
    cc = C["CAPEX_CASE_CHUNKS"]["value"]
    for name, total in (("우민재", 456_158_140), ("최혁진", 694_575_784)):
        got = sum(cc[name].values())
        assert got == total, f"{name} 9공종 합 {got:,} ≠ 서술 총액 {total:,}"

    # 🔴 note만 보면 **파일을 바꿔치기해도 통과한다**(_ref_ok는 실재만 본다).
    #    그래서 표본명↔파일 짝이 형제 상수의 매핑과 같은지 대조한다.
    #    변이 M1(실재하는 엉뚱한 파일로 교체)이 이 검사가 없을 때 통과했다.
    sib_note = {r["file"]: (r.get("note") or "")
                for r in C["CAPEX_MAJOR_CASE_CHUNKS"]["source_refs"]}
    for cname in ("CAPEX_CASE_CHUNKS", "CAPEX_MAJOR_UNCLASSIFIED",
                  "CAPEX_MAJOR_EVIDENCE_STATUS"):
        for r in C[cname]["source_refs"]:
            if r["file"] not in sib_note:
                continue          # 이동혁 커튼 견적처럼 형제에 없는 보조 자료
            mine = (r.get("note") or "").split("—")[0].split("표본")[0]
            names = [n for n in mine.replace("·", " ").split() if n]
            assert names, f"{cname}: {r['file']} note에서 표본명을 못 읽었다"
            assert any(n in sib_note[r["file"]] for n in names), (
                f"{cname}: {r['file']} 의 note가 '{mine.strip()}'인데 "
                f"형제 상수는 이 파일을 '{sib_note[r['file']][:20]}'로 적는다 — "
                "표본명과 파일이 어긋났다(잘못 붙은 ref는 없느니만 못하다)")

    # ③ CAPEX_MAJOR_UNCLASSIFIED — 15키가 전부 표본 refs로 덮이는가
    unc = C["CAPEX_MAJOR_UNCLASSIFIED"]["value"]
    notes = " | ".join(r.get("note") or "" for r in C["CAPEX_MAJOR_UNCLASSIFIED"]["source_refs"])
    for key in unc:
        for nm in key.split("·"):          # '백가은·조윤정'은 쌍 견적 통합 키다
            assert nm in notes, f"미분류 키 '{key}'의 표본 {nm}을 가리키는 ref가 없다"
    # 형제 상수와 같은 원문 집합을 쓰는가(133차가 지적한 바로 그 점)
    sib = {r["file"] for r in C["CAPEX_MAJOR_CASE_CHUNKS"]["source_refs"]}
    assert {r["file"] for r in C["CAPEX_MAJOR_UNCLASSIFIED"]["source_refs"]} == sib, (
        "미분류가 형제 CAPEX_MAJOR_CASE_CHUNKS와 다른 원문 집합을 가리킨다")

    # ④ PUMSEM_ITEMS — 1차 출처가 품셈 PDF이고 기계 추출 스냅샷이 함께 붙었는가
    pum = C["PUMSEM_ITEMS"]["source_refs"]
    assert pum[0]["file"] == "시설평가/202201_스마트팜 표준화_품셈.pdf", (
        "PUMSEM_ITEMS의 첫 ref가 1차 출처(품셈 PDF)가 아니다")
    assert pum[0].get("match", "exact") == "exact"
    files = {r["file"] for r in pum}
    assert "pumsem_extract_dump.txt" in files and \
           "근거_PUMSEM64종_원문전수대조_20260914.md" in files, (
        "64계수의 대조 기록(113차 육안·125차 기계)이 refs에서 빠졌다")

    # ⑤ 등급 — 맥락 자료를 exact로 올리지 않았는가(20회차 F3의 교훈)
    for k in ("PUMSEM_ITEMS", "CAPEX_MAJOR_EVIDENCE_STATUS", "EQUIPMENT_DB_META"):
        assert any(r.get("match") == "partial" for r in C[k]["source_refs"]), (
            f"{k}에 partial 등급이 하나도 없다 — 맥락 자료까지 exact로 올렸다는 뜻이다")
    ev = C["CAPEX_MAJOR_EVIDENCE_STATUS"]["source_refs"]
    assert all(r.get("match") == "partial" for r in ev), (
        "EVIDENCE_STATUS의 상태 문자열은 표본 전체에서 유도된다 — "
        "개별 표본을 exact로 올리면 과대 표기다")

    doc = open(_o.path.join(repo, "근거_추적성refs부착_20260915.md"), encoding="utf-8").read()
    assert "파일만 존재하면 통과한다" in doc, (
        "_ref_ok의 한계(실재만 보고 내용은 안 본다)가 근거문서에서 사라졌다")
    assert "하나도 바꾸지 않았다" in doc and "92 → 148" in doc, (
        "값 불변 + refs만 92→148이라는 표기가 사라졌다")


def test_135cha_redteam26_corrections_are_pinned():
    """135차(레드팀 26회차) — 정정 10건이 되돌아가지 않게 고정한다.

    🔴 이번 회차는 성격이 달랐다: 25회차까지 발견이 **서술·집계**에 몰렸는데
    이번엔 **가드 자체의 결함 2건**이 나왔다(F3 — 유일성 가드가 한 시트만 봤다 ·
    F8 — CM4 가드의 단언이 항등식이라 정보가 0이었다). 그 둘은 132차 가드에서
    직접 고쳤고, 이 테스트는 **나머지 서술·데이터 정정**을 고정한다.

    📌 처음 변이를 돌렸을 때 **5종이 전부 통과**했다 — 정정을 고정하는 가드가
    없었기 때문이다. 그것이 이 테스트가 생긴 이유다.
    """
    import os as _o, json as _j, io as _io
    repo = _o.path.dirname(_o.path.abspath(__file__))
    led = open(_o.path.join(repo, "근거_확인요망대장_20260915.md"), encoding="utf-8").read()
    d132 = open(_o.path.join(repo, "근거_대장3항목_리포내확인_20260915.md"), encoding="utf-8").read()
    d134 = open(_o.path.join(repo, "근거_추적성refs부착_20260915.md"), encoding="utf-8").read()
    rt = open(_o.path.join(repo, "검증절차_레드팀.md"), encoding="utf-8").read()
    reg = _j.load(_io.open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8"))
    C = reg["constants"]

    # ── F4 [상] 대장이 이미 닫힌 것을 살아 있다고 적었다 ──────────────────
    assert "94차" in led and "2,321.87" in led, (
        "AC3를 닫은 94차 근거(공사설명서 면적표 2,321.87)가 대장에서 사라졌다")
    assert "5 + 19 = 24개" in led, (
        "대장의 항목 수가 26회차 정정(19 / 24)에서 벗어났다 — 131차는 20 / 25로 적었다")
    assert "| ✅ **이미 닫혔다** | **10** |" in led, "닫힘 수 10이 되돌아갔다"
    assert "## 6. 살아 있는 항목 19개" in led, "6절 제목의 항목 수가 되돌아갔다"
    assert led.count("AC5") >= 1 and "158원 → 42원" in led, (
        "AC5(94차가 새로 연 2,323 vs 2,321.87 — 밴드 여유 **158원**→42원)가 대장에서 사라졌다. "
        "🔴153차: 종전 이 가드가 **미정정값 159원을 고정**하고 있었다")
    assert "구조적으로 누락된다" in led, (
        "🔴 대장이 `[확인요망]` 문자열을 모집단으로 삼아 **태그 없는 미해결을 놓친다**는 "
        "26회차 F4의 구조적 교훈이 사라졌다")
    # 레지스트리 쪽 기록도 함께(문서만 고치고 레지스트리를 두면 또 어긋난다)
    assert "94차 ①이 이미 확정" in C["ACTUALS_COUNT"]["source"], (
        "ACTUALS_COUNT에 26회차 F4 기록이 사라졌다")

    # ── F1 [상] CM3 대조군이 전수가 아니었다 ─────────────────────────────
    assert "대조군이 전수가 아니었다" in d132, "F1 정정이 사라졌다"
    assert "1101" in d132 and "114,241,498" in d132, (
        "주석 행이 5개(1101 포함)라는 것과 R10(PO)의 실재 금액이 사라졌다")
    assert "C10" in d132 and "공란" in d132 and "주석도 없고" in d132, (
        "'주석 없이 수량 공란으로 제외'라는 제3의 패턴(R10 PO)이 사라졌다 — F1의 핵심이다")

    # ── F2 [중] "전부 라벨 칸"이 틀렸다 ──────────────────────────────────
    assert "조사가격1" in d132, (
        "O432가 라벨이 아니라 가격 열이라는 F2 정정이 사라졌다")
    assert "하류 수식이" in d132, (
        "유일성의 옳은 근거(하류 참조 0건)가 사라졌다")

    # ── F5 [중] 134차 부착분의 match가 데이터에 기록돼 있는가 ────────────
    ADDED = ("PUMSEM_ITEMS", "ELECTRICAL_PUMSEM_LUMP_WON_PER_HA", "CAPEX_CASE_CHUNKS",
             "CAPEX_MAJOR_UNCLASSIFIED", "CAPEX_MAJOR_EVIDENCE_STATUS", "EQUIPMENT_DB_META")
    missing = [(k, r["file"]) for k in ADDED for r in C[k]["source_refs"] if "match" not in r]
    assert not missing, (
        f"134차 부착 refs 중 match 미기재가 남았다: {missing[:3]} … — "
        "감사기가 기본값 exact로 잡으므로 등급이 데이터에 없는 채 exact가 된다")
    assert "정책이 데이터에 없었다" in d134 or "데이터에 적지 않았다" in d134, (
        "F5 정정(정책을 선언했지만 데이터에 적지 않았다)이 134차 문서에서 사라졌다")

    # ── F6 [중] 유일한 미검산 ref가 명시돼 있는가 ────────────────────────
    assert "글리프 구간" in d134 and "확인 불가" in d134, (
        "ELECTRICAL_PUMSEM_LUMP의 값을 기계 확인할 수 없다는 F6 병기가 사라졌다")
    assert "원문에 없다는 뜻이 아니다" in d134, (
        "R6 규율(못 읽은 것을 부재로 읽지 않는다) 표기가 사라졌다")

    # ── F7 [하] 철회된 문구를 되살린 ref note ────────────────────────────
    ev_notes = " | ".join(r.get("note") or "" for r in C["CAPEX_MAJOR_EVIDENCE_STATUS"]["source_refs"])
    assert "자동개폐 계열 참고단가로 재분류" in ev_notes, (
        "F7 정정이 사라졌다 — 이동혁 ref note가 2026-08-17에 제거된 "
        "'판단성 보류' 문구를 다시 진술하고 있다")

    # ── F9·F10 [하] ──────────────────────────────────────────────────────
    assert "부분 경로" in d132, "F9(전수 확인의 검색 범위 병기)가 사라졌다"
    assert "3,010" in led, (
        "F10(p.166 온실품셈 열 성분 합 3,010 vs 표기 3,009)이 대장에서 사라졌다")

    # ── 회차 기록 ────────────────────────────────────────────────────────
    assert "### 26회차" in rt and "거짓 양성 0건" in rt, "26회차 기록이 사라졌다"
    assert "가드 자체의 결함" in rt, (
        "🔴 이번 회차의 성격(가드가 지킨다고 적힌 것을 실제로는 안 지켰다)이 사라졌다")


def test_136cha_pdf_is_opened_once_and_output_is_identical(monkeypatch):
    """136차 — 89.8MB PDF를 **프로세스당 한 번만** 열고, **추출 결과는 그대로**인가.

    종전에는 `extract_all`·`extract_tables`·`extract_notes`·`extract_labor_trades`가
    각각 `PdfReader(PDF_PATH)` + `pdfplumber.open(PDF_PATH)`를 따로 불러
    **한 pytest 프로세스 안에서 같은 PDF를 4회 파싱**했다.

    ⚠️ 이 변경을 **세그폴트(133·135차 1회씩)의 해결이라고 말하지 않는다** —
    재현 조건을 잡지 못했고 인과를 확인하지 않았다. 확실한 것은 **파싱 4회 → 1회**와
    **출력 불변**뿐이다(교차 3회 실측 19.53s → 15.02s).

    🔴 이 테스트의 본체는 **출력 불변**이다. 성능을 얻자고 추출값이 한 글자라도
    달라지면 125·129차가 세운 64계수 대조가 통째로 흔들린다.
    """
    import pytest as _pt
    _pt.importorskip("pdfplumber")
    _pt.importorskip("fontTools")
    _pt.importorskip("pypdf")
    import hashlib as _h
    import pdfplumber as _pp
    import pypdf as _py
    import pumsem_extract as px

    try:
        px._system_index()
    except px.FontsUnavailable:
        _pt.skip("시스템 폰트(batang/gulim)가 없다 — 128차 skip 규율과 같다")

    # ① PDF를 몇 번 여는가 — 공유 핸들을 비우고 네 함수를 연달아 부른다
    px.close_doc()
    opens = {"pdfplumber": 0, "pypdf": 0}
    _open, _reader = _pp.open, _py.PdfReader

    def _counted_open(*a, **k):
        opens["pdfplumber"] += 1
        return _open(*a, **k)

    class _CountedReader(_reader):
        def __init__(self, *a, **k):
            opens["pypdf"] += 1
            super().__init__(*a, **k)

    monkeypatch.setattr(_pp, "open", _counted_open)
    monkeypatch.setattr(_py, "PdfReader", _CountedReader)

    got = {
        "extract_all": repr(px.extract_all()),
        "extract_tables": repr(px.extract_tables()),
        "extract_notes": repr(px.extract_notes()),
        "extract_labor_trades": repr(px.extract_labor_trades()),
    }
    assert opens == {"pdfplumber": 1, "pypdf": 1}, (
        f"네 함수가 PDF를 {opens}회 열었다 — 136차 이전은 각 4회였고 목표는 각 1회다")

    # 파생 함수도 같은 핸들을 타는가(추가 open이 없어야 한다)
    noterows = px.extract_notes()
    got["rate_rules"] = repr(px.rate_rules(noterows))
    got["classify_notes"] = repr(px.classify_notes(noterows))
    got["note_numbers"] = repr([px.note_numbers(n) for _, _, n in noterows])
    assert opens == {"pdfplumber": 1, "pypdf": 1}, (
        f"파생 함수가 PDF를 다시 열었다: {opens}")

    # ② 🔴 출력 불변 — 136차 변경 직전(HEAD=d53ed41)에 뜬 다이제스트와 같아야 한다
    EXPECTED = {
        "extract_all": "1e9d0884cdf2d994",
        "extract_tables": "4dcdb9b7e623a008",
        "extract_notes": "9f1f2b933ddd8298",
        "extract_labor_trades": "08b677b28efc396c",
        "rate_rules": "282cd312da7ed1ec",
        "classify_notes": "902cc0756975b258",
        "note_numbers": "9e4cc9c1b519dbce",
    }
    digest = {k: _h.sha256(v.encode()).hexdigest()[:16] for k, v in got.items()}
    assert digest == EXPECTED, (
        "추출 결과가 136차 리팩터 전과 달라졌다:\n" +
        "\n".join(f"  {k}: {EXPECTED[k]} -> {digest[k]}"
                  for k in EXPECTED if EXPECTED[k] != digest[k]) +
        "\n→ 성능을 얻자고 값이 바뀌면 125·129차의 64계수 대조가 흔들린다")

    # ③ close_doc()이 핸들을 실제로 놓는가(테스트 격리·명시 해제 경로)
    assert px._DOC is not None
    px.close_doc()
    assert px._DOC is None, "close_doc() 후에도 공유 핸들이 남아 있다"
    px.close_doc()          # 두 번 불러도 안전해야 한다


def test_137cha_every_ref_records_its_match_grade():
    """137차 — `source_refs` **148건 전부**가 등급을 데이터에 기록하는가.

    🔴 26회차 F5가 지적한 것: `audit_traceability.py`는 `r.get("match", "exact")`로
    **기본값을 exact**로 잡는다. 즉 등급을 안 적으면 **데이터에 없는 채 exact**가 되고,
    `build_site`의 배지 맵(`near`→[근접] · `partial`→[부분])에서도 **무배지**가 된다.
    134차가 자기 부착분 30건을 명시했고, 137차가 **나머지 56건**을 확정했다.

    이 테스트가 막는 것: ①새 ref가 등급 없이 들어와 **조용히 exact가 되는 것**
    ②확정한 등급이 되돌아가는 것.
    """
    import os as _o, json as _j, io as _io
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = _j.load(_io.open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8"))
    C = reg["constants"]

    missing = [(k, r.get("file")) for k, v in C.items()
               for r in (v.get("source_refs") or []) if "match" not in r]
    assert not missing, (
        f"등급이 없는 ref가 {len(missing)}건 있다: {missing[:3]} … — "
        "감사기가 기본값 exact로 잡으므로 등급이 데이터에 없는 채 exact가 된다")

    dist = {}
    for k, v in C.items():
        for r in (v.get("source_refs") or []):
            dist[r["match"]] = dist.get(r["match"], 0) + 1
    assert dist == {"exact": 90, "partial": 55, "near": 9}, (
        f"등급 분포가 {dist}로 바뀌었다 — 163차 실측은 exact 90 / partial 55 / near 9이다"
        "(137차 확정 exact90/partial50/near8 → 151차 partial +3 → 161차 near +1"
        "= `FR_TABLE`의 [표 3-3-27] → 🔴163차 **partial +2** = "
        "`REGION_DESIGN_LOAD`의 고시 [별표] 사본 2건). "
        "ref를 늘렸다면 새 ref의 등급을 정하고 이 수를 갱신하라")

    # ── 🔴 near 4건 — 값이 원문과 **같지 않다**는 것이 핵심이다 ──────────
    def _ref(const, needle):
        hit = [r for r in C[const]["source_refs"] if needle in r["file"]]
        assert len(hit) == 1, (const, needle, len(hit))
        return hit[0]

    for const, needle, gap, why in (
        ("STRUCTURE_ONLY_PYEONG", "1. 공사내역서", "163,468",
         "등재 163,400 — 값이 이 문서에서 나온 게 아니라 A-8 엔진값을 근사 확인한 것이다"),
        ("BENCHMARK_BANDS", "1. 공사내역서", "239,842",
         "등재 상한 240,000 — 올려 잡은 경계이고 하한 115,000은 다른 계열이다"),
        ("ACTUALS_COUNT", "3. 공사설명서(우민재)", "2,321.87",
         "등재 2,323 — 26회차 F4가 올린 AC5가 이 차이다"),
        ("ACTUALS_COUNT", "0. 도면(우민재)", "2,321.87",
         "등재 2,323 — AC5"),
    ):
        r = _ref(const, needle)
        assert r["match"] == "near", f"{const}/{needle}의 등급이 near가 아니다 — {why}"
        assert gap in (r.get("note") or ""), (
            f"{const}/{needle}의 note에서 원문 값 {gap}이 사라졌다 — "
            "near는 '얼마나 다른가'가 적혀 있어야 뜻이 있다")

    # ── partial 7건 — 문서가 값의 일부·해석 근거일 뿐이다 ────────────────
    drawings = [r for r in C["ACTUALS_COUNT"]["source_refs"]
                if r["file"].endswith(("평면도.pdf", "측면골조도.pdf", "주단면도.pdf"))]
    assert len(drawings) == 6 and all(r["match"] == "partial" for r in drawings), (
        "한수진·최선동 도면 6건은 면적 기준의 **해석 근거**이지 등재 면적값의 출처가 아니다")
    assert C["SUBSIDY_PROGRAM_TYPES_REFERENCE"]["source_refs"][0]["match"] == "partial", (
        "시행계획 원문은 사업 명칭 4건 확인·2건 미확인이라 등재값 전체를 뒷받침하지 않는다")

    # ── 법령·고시 원문은 exact다(그 별표에서 값이 직접 나온다) ───────────
    # ⚠️ 상수 전체가 아니라 **137차가 등급을 매긴 그 별표 ref**만 본다
    #    (FUEL_HHV에는 137차 대상이 아닌 기존 partial ref가 하나 더 있다)
    for const, needle in (("FUEL_LHV", "에너지열량환산기준"),
                          ("FUEL_HHV", "에너지열량환산기준"),
                          ("STRUCTURE_SERVICE_LIFE_STATUTORY", "별표5_건축물기준내용연수"),
                          ("STRUCTURE_SERVICE_LIFE_STATUTORY", "별표6_업종별기준내용연수"),
                          ("SUPERVISION_FEE_RATE_TABLE", "공사감리대가요율"),
                          ("EQUIPMENT_SERVICE_LIFE_REFERENCE", "조달청고시_내용연수표")):
        assert _ref(const, needle)["match"] == "exact", (
            f"{const}의 별표 원문({needle}) ref가 exact가 아니다 — 값이 그 별표에서 직접 나온다")

    # ── 등급은 산출물에 보인다: build_site 배지 맵이 살아 있는가 ─────────
    bs = open(_o.path.join(repo, "build_site.py"), encoding="utf-8").read()
    assert '"near": " <b>[근접]</b>"' in bs and '"partial": " <b>[부분]</b>"' in bs, (
        "build_site의 match 배지 맵이 사라졌다 — 등급을 적어도 독자가 볼 수 없게 된다")
    # 🔴 137차 실측 — 레지스트리 서술에 배지 문자열을 쓰면 그 서술이 렌더돼 **배지 수가
    #    늘어난다**(9·50으로 부풀었다). 131차 `[확인요망]` 자기증식·134차 ref note에 이은
    #    **세 번째**다: **세는 문자열을 서술에 쓰지 않는다**.
    prose_badge = [k for k, v in C.items()
                   if "[근접]" in (v.get("source") or "") or "[부분]" in (v.get("source") or "")]
    assert not prose_badge, (
        f"레지스트리 서술이 배지 문자열을 쓴다: {prose_badge} — "
        "그 서술이 근거대장으로 렌더돼 배지 집계를 부풀린다(137차 실측)")

    ledger = open(_o.path.join(repo, "SmartFarm_근거대장.html"), encoding="utf-8").read()
    assert ledger.count("[근접]") == 9 and ledger.count("[부분]") == 55, (
        f"근거대장 배지가 [근접] {ledger.count('[근접]')}·[부분] {ledger.count('[부분]')}다 — "
        "163차 실측(9·55)과 어긋난다. build_site.py를 다시 돌렸는지 확인하라"
        "(137차 확정 8·50 → 151차 partial +3 → 161차 near +1"
        "= `FR_TABLE`의 [표 3-3-27] → 🔴163차 **partial +2**"
        "= `REGION_DESIGN_LOAD`의 고시 [별표] 사본 2건)")
    # 🔴 152차 — 이 가드는 **커밋된 HTML**을 읽는다. 게이트를 돌릴 때 `build_site.py`를
    #   pytest **뒤에** 실행하면 낡은 산출물로 통과해 버린다(151차에 실제로 그랬다).
    #   순서는 **build_site → pytest**다.


def test_138cha_known_totals_are_recomputable_from_the_documents():
    """138차 — `exact`라 적은 값이 **원문에서 재현되는가**.

    137차가 `exact` 45건을 확정했으나 *"정말 원단위로 일치하는지 재계산하지 않았다"*를
    한계로 남겼다. 138차가 견적 원문 **39건**을 대조한 결과 **불일치 0건**이고,
    그중 **3건은 총액이 문서에 인쇄돼 있지 않은 재집계값**이었다.

    🔴 두 표본에서 같은 구조가 나왔다 — `known_total`은 **문서의 총계가 아니라
    "문서가 총계에서 뺀 행까지 포함한 재집계"**다:
      우민재 문서 합계행 453,478,913 + '합계제외' 3행 2,679,227 = 456,158,140
      이두희 문서 `계`   423,454,980 + 영세율 적용 10,151,480 = 433,606,460
    **인쇄값만으로 정확히 재현되므로 exact는 유지**하되 그 사실을 note에 적었다.
    """
    import os as _o, json as _j, io as _io
    repo = _o.path.dirname(_o.path.abspath(__file__))
    reg = _j.load(_io.open(_o.path.join(repo, "엔진데이터_레지스트리.json"), encoding="utf-8"))
    C = reg["constants"]

    # ① 재집계 산술 — 문서 총계 + 뺀 행 = 등재 known_total
    assert 453_478_913 + 2_679_227 == 456_158_140, "우민재 재집계 산술이 깨졌다"
    assert 423_454_980 + 10_151_480 == 433_606_460, "이두희 재집계 산술이 깨졌다"
    assert 360_447_860 + 72_269_120 + 7_025_247 == 439_742_227, "맹주연 3성분 합이 깨졌다"

    # ② 🔴 우민재의 차이가 곧 미분류다 — 이 정합이 138차의 발견이다
    kt = C["CAPEX_MAJOR_KNOWN_TOTALS"]["value"]
    unc = C["CAPEX_MAJOR_UNCLASSIFIED"]["value"]
    assert kt["우민재"] == 456_158_140 and unc["우민재"] == 2_679_227
    assert kt["우민재"] - unc["우민재"] == 453_478_913, (
        "우민재 known_total − 미분류가 문서 합계행(453,478,913)이 아니다 — "
        "엔진의 미분류가 문서의 '합계제외' 집합과 같다는 138차 정합이 깨졌다")
    assert kt["이두희"] == 433_606_460 and kt["맹주연"] == 439_742_227

    # ③ 재검산 사실이 note에 남아 있는가(인쇄값이 아니라는 것)
    for const, needle, mark in (
        ("CAPEX_MAJOR_KNOWN_TOTALS", "1. 공사내역서", "453,478,913"),
        ("CAPEX_MAJOR_KNOWN_TOTALS", "이두희 천안", "10,151,480"),
        ("CAPEX_MAJOR_KNOWN_TOTALS", "맹주연", "기계경비"),
        ("CAPEX_MAJOR_CASE_CHUNKS", "1. 공사내역서", "합계제외"),
        ("CAPEX_MAJOR_CASE_CHUNKS", "이두희 천안", "423,454,980"),
        ("CAPEX_MAJOR_CASE_CHUNKS", "맹주연", "360,447,860"),
    ):
        hit = [r for r in C[const]["source_refs"] if needle in r["file"]]
        assert len(hit) == 1, (const, needle)
        note = hit[0].get("note") or ""
        assert "138차 재검산" in note and mark in note, (
            f"{const}/{needle}의 138차 재검산 기록({mark})이 사라졌다 — "
            "이 값이 문서에 인쇄된 것이 아니라는 표시다")
        assert hit[0]["match"] == "exact", (
            f"{const}/{needle}의 등급이 바뀌었다 — 인쇄값만으로 정확히 재현되므로 exact다")

    doc = open(_o.path.join(repo, "근거_exact39_원단위재검산_20260915.md"), encoding="utf-8").read()
    assert "불일치 0건" in doc and "확인 불가 | **0**" in doc, (
        "138차 대조 결과(불일치 0·확인 불가 0)가 근거문서에서 사라졌다")
    assert "과교정" in doc, (
        "🔴 파서를 두 번 고친 기록(P1 과소·P2 과교정)이 사라졌다 — "
        "125차 P1~P3·133·134차에 이은 같은 계열이다")
    assert "회계 판단" in doc, (
        "재집계 규칙의 타당성을 판정하지 않았다는 표기가 사라졌다")


def test_139cha_every_exact_ref_carries_a_checkable_anchor():
    """139차 — `exact` ref가 **검산 가능한 대조 기준**을 갖는가.

    138차는 39건 중 **9건에 note가 아무 금액도 적지 않아 대조하지 못했다**.
    기준이 없으면 그 ref는 **앞으로도 영원히 검산되지 않는다** — `_ref_ok()`는
    파일 실재만 보므로 게이트도 그것을 모른다.

    139차가 9건에 앵커를 적고, 재검산기를 **리포 도구(`verify_refs.py`)로 남겼다**.
    이 테스트는 그 도구의 **정적 검사**를 매 게이트마다 돌린다(원문 16종을 여는
    전수 재검산은 `python verify_refs.py --full`로 돌리고 스냅샷을 비교한다).
    """
    import os as _o, sys as _s
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import verify_refs as vr

    consts = vr.load_registry()
    rows = vr.exact_refs(consts)
    assert len(rows) == 39, f"대상 exact ref가 {len(rows)}건이다 — 138·139차 실측은 39건"

    # ① 🔴 앵커 없는 ref가 0건인가 — 139차의 본체다
    # 🔴 도구를 신뢰만 하면 안 된다 — 139차 변이 M5(static_check 무력화)가 통과했다.
    #    가드가 **직접** 센다.
    empty = [(k, _o.path.basename(f)) for k, f, anchors, _ in rows if not anchors]
    assert not empty, (
        f"대조 기준이 없는 exact ref: {empty} — 기준이 없으면 영원히 검산되지 않는다")
    problems = vr.static_check(consts)
    assert len(problems) == len(empty), (
        "verify_refs.static_check가 앵커 없는 ref를 놓친다 — 도구가 무력화됐다")

    # 🔴 red 자기검증 — 앵커 없는 ref가 0건이면 **도구가 무력화돼도 결과로는 구별되지
    #    않는다**(139차 변이 M5). 합성 입력으로 도구가 실제로 잡는지 시험한다
    #    (`test_cases.py`의 `at._ref_ok({...}) is False`와 같은 선례).
    fake = {k: {"source_refs": []} for k in vr.TARGET}
    fake[vr.TARGET[0]]["source_refs"] = [
        {"file": "없는폴더/없는파일.pdf", "match": "exact", "note": "금액이 없는 note"}]
    assert len(vr.static_check(fake)) == 1, (
        "verify_refs.static_check가 앵커 없는 ref를 잡지 못한다 — 도구가 무력화됐다")
    assert not problems, (
        "대조 기준(앵커 금액)이 없는 exact ref: "
        + " / ".join(f"{k} {_o.path.basename(f)}" for k, f, _ in problems)
        + " — 기준이 없으면 그 ref는 영원히 검산되지 않는다")

    # ② 139차가 새로 적은 9건의 앵커가 살아 있는가
    by_file = {}
    for k, f, anchors, note in rows:
        by_file.setdefault((k, _o.path.basename(f)), (anchors, note))
    for (const, base), want in (
        (("ACTUALS_COUNT", "이두희 천안 20251028.pdf"), 582_455_045),
        (("ACTUALS_COUNT", "혁진 스마트팜 온실 신축공사_공사비 내역서.pdf"), 930_000_000),
        (("ACTUALS_COUNT", "설계예산서(한일그린텍).pdf"), 480_636_000),
        (("ACTUALS_COUNT", "한수진스마트팜딸기하우스견적서.xls"), 618_001_000),
        (("ACTUALS_COUNT", "스마트팜하우스(렉창)5연동견적서_최선동.xls"), 613_782_000),
        (("CAPEX_MAJOR_CASE_CHUNKS", "221206 윤성호 청년스마트팜 내역서.pdf"), 1_162_078_090),
        (("CAPEX_MAJOR_CASE_CHUNKS", "논산딸기조윤정님75각 외몽골셀액분리(최종).pdf"), 398_628_383),
        (("CAPEX_CATEGORY_OBSERVED_RANGE", "1. 공사내역서 스마트팜 확대보급 시범사업.xlsx"), 456_158_140),
        (("CAPEX_CATEGORY_OBSERVED_RANGE", "혁진 스마트팜 온실 신축공사_공사비 내역서.pdf"), 694_575_784),
    ):
        anchors, _ = by_file[(const, base)]
        assert want in anchors, (
            f"{const}/{base}의 139차 앵커 {want:,}가 사라졌다 — "
            "138차에 '대조할 금액이 없다'로 남았던 9건이다")

    # ③ ACTUALS 앵커는 엔진 값과 같아야 한다(서술만 고치고 값이 흘러가는 것을 막는다)
    import smartfarm_engine as e
    actual = {row[0]: row[2] for row in e.ACTUALS}
    for base, name in (("이두희 천안 20251028.pdf", "이두희"),
                       ("혁진 스마트팜 온실 신축공사_공사비 내역서.pdf", "최혁진"),
                       ("설계예산서(한일그린텍).pdf", "한일그린텍"),
                       ("한수진스마트팜딸기하우스견적서.xls", "한수진"),
                       ("스마트팜하우스(렉창)5연동견적서_최선동.xls", "최선동")):
        anchors, _ = by_file[("ACTUALS_COUNT", base)]
        assert actual[name] in anchors, (
            f"{name}의 ACTUALS 총공사비 {actual[name]:,}가 ref 앵커와 어긋난다")

    # ④ 전수 재검산 스냅샷이 있고 139차 실측과 맞는가
    dump = open(_o.path.join(repo, "verify_refs_dump.txt"), encoding="utf-8").read()
    assert "OK 31 · RECOMPUTED 8" in dump, (
        "verify_refs_dump.txt가 148차 실측(OK 31 · RECOMPUTED 8)과 다르다 — "
        "앵커를 바꿨다면 `python verify_refs.py --full`로 스냅샷을 다시 뜨라")
    # 🔴 148차: 139차 실측은 OK 32 · RECOMPUTED 7이었다. 148차가 앵커에
    #   **단위가 붙은 면적**(`2,736㎡`)을 추가하고 `\b`가 한글 접미사 앞에서
    #   실패하던 것을 고치자 **이두희 ref 하나가 OK → RECOMPUTED로 이동**했다:
    #   `2,736`은 문서에 인쇄돼 있지 않고 규격 8m×6연동×57m의 **역산**이다
    #   (8×6×57=2,736). 139차 note가 금액과 면적을 한 괄호로 묶어
    #   *「문서에서 확인」*이라 적은 것이 부정확했다 — 합은 39로 같다.
    # ⚠️ 부분 문자열로 보면 안 된다 — `CAPEX_MAJOR_CASE_CHUNKS`에 "UNK"가 들어 있다
    #    (139차에 이 가드가 자기 오탐으로 한 번 발화했다). 상태는 **줄 머리**에 있다.
    bad_lines = [ln for ln in dump.splitlines()
                 if ln.startswith("MISS") or ln.startswith("UNK")]
    assert not bad_lines, (
        "재검산 스냅샷에 MISS/UNK 줄이 생겼다: %s — 앵커가 원문에서 확인되지 않거나 "
        "재집계 선언이 없는 ref가 있다" % bad_lines[:2])

    # ⑤ 인쇄돼 있지 않은 앵커는 note가 재집계를 선언해야 한다(도구의 규율)
    # 🔴 변이 M3(빈 문자열 추가)이 통과했다 — 빈 표지는 **모든 note에 들어 있다**
    assert all(w.strip() for w in vr.RECOMPUTED), (
        f"재집계 선언 표지에 빈 값이 섞였다: {vr.RECOMPUTED} — "
        "빈 문자열은 모든 note에 매칭돼 인쇄되지 않은 값이 전부 통과한다")
    assert vr.RECOMPUTED and "재집계" in vr.RECOMPUTED, (
        "verify_refs의 재집계 선언 규율이 사라졌다 — 그것이 없으면 "
        "인쇄되지 않은 값이 조용히 통과한다")


def test_140cha_partial_and_near_refs_carry_criteria():
    """140차 — `partial`·`near` **58건**도 대조 기준을 갖는가.

    139차가 `exact` 39건을 닫았지만 **나머지 58건은 여전히 "무엇을 보면 되는지"가
    없었다**. `partial`은 그 문서가 값의 *일부·해석 근거*일 뿐이라 **금액 앵커가
    성립하지 않는 경우가 많다** — 그래서 기준을 넓혔다:
    **①숫자 ②위치(쪽·표·시트·절·행) ③인용 문구** 중 하나 이상.

    🔴 **146차 한정(레드팀 27회차 [6])**: 아래 "기준 없는 ref 0건"은 **`93차`·`110차`의
    숫자를 기준으로 세어 나온 0**이었다. 차수 번호는 경위 표시이지 대조 기준이 아니다 —
    `verify_refs.weak_check()`가 그 7건을 드러낸다(`test_146cha_*`가 고정). 이 가드의
    0건 주장은 **"기준이 아예 없는 ref"에 한정**해서만 유효하다.

    🔴 이번에도 자동 유도를 한 번 접었다: `CAPEX_MAJOR_EVIDENCE_STATUS`의 상태
    문자열에서 포함/제외를 `—`로 갈라 세려 했는데 **주석 안에도 `—`가 있어**
    `hvac` 10건이 **4건으로 오독**됐다. → 자동 분류를 포기하고 **"이름이 몇 개
    카테고리에 나타나는가 + 포함·제외가 섞여 있다"**를 기준으로 적었다.
    """
    import os as _o, sys as _s
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import verify_refs as vr

    consts = vr.load_registry()
    rows = vr.soft_refs(consts)
    assert len(rows) == 64, (
        f"partial·near가 {len(rows)}건이다 — 163차 실측은 64건"
        "(140차 58 + `OVERHEAD_RATES` 3 + `FR_TABLE` 1 + `REGION_DESIGN_LOAD` 2)")

    # ① 🔴 기준 없는 ref가 0건인가 — 가드가 **직접** 센다(139차 M5 교훈)
    empty = [(k, _o.path.basename(f), g) for k, f, g, note in rows
             if not vr.soft_criteria(note)]
    assert not empty, (
        f"대조 기준(숫자·위치·인용)이 없는 partial·near ref: {empty[:3]} — "
        "기준이 없으면 그 문서에서 무엇을 봐야 하는지 알 수 없다")
    assert len(vr.soft_check(consts)) == len(empty), (
        "verify_refs.soft_check가 기준 없는 ref를 놓친다 — 도구가 무력화됐다")

    # ② red 자기검증 — 기준 없는 ref가 0건이면 도구 무력화가 결과로 구별되지 않는다
    fake = {"X": {"source_refs": [
        {"file": "a.pdf", "match": "partial", "note": "설명만 있고 기준이 없다"}]}}
    assert len(vr.soft_check(fake)) == 1, (
        "verify_refs.soft_check가 기준 없는 ref를 잡지 못한다 — 도구가 무력화됐다")

    # ③ 140차가 채운 24건 중 대표 앵커가 살아 있는가
    by = {(k, _o.path.basename(f)): note for k, f, _, note in rows}
    for const, base, mark, why in (
        ("U_DESIGN", "근거_난방계수_이견_20260913.md", "8.9",
         "76차 이견 문서의 §0 결론(현행값 유지)"),
        ("FR_TABLE", "근거_농사로_스크린보온력표_20260819.md", "15℃",
         "유리온실 무보온 U=7·온도차 15℃ 기준"),
        ("FINANCE_DEFAULTS", "법령_법인세법시행규칙_별표5_건축물기준내용연수_시행20260701.pdf",
         "15~25", "useful_life=15의 범위 정합"),
        ("PUMSEM_ITEMS", "근거_품셈표준설계_면적구성_20260914.md", "그림 7-3",
         "벤로타입은 유리온실에만 — 114차 정정"),
        ("PUMSEM_ITEMS", "근거_요약본6.2_본문출처추적_20260914.md", "4,196/3,509",
         "23회차 F4 정정 배너"),
        ("HEATING_EFFICIENCY_DEFAULT", "근거_열효율기준_총발열량_20260820.md", "제2020-10호",
         "§3-A 철회 사유 — 순발열량 조합 유지"),
        ("CLUSTER_SCALE_SAVING_RATE", "근거_단지경제성_기본값_20260820.md", "0.15",
         "머리말 대상 줄"),
        ("CLUSTER_SUBSIDY_RATE_SHARED", "근거_단지경제성_기본값_20260820.md", "0.7",
         "머리말 대상 줄"),
    ):
        note = by[(const, base)]
        assert mark in note, f"{const}/{base}의 140차 대조 기준({mark})이 사라졌다 — {why}"

    # ④ 🔴 EVIDENCE_STATUS 16건 — 카테고리 수가 상수 자신의 값과 맞는가
    val = consts["CAPEX_MAJOR_EVIDENCE_STATUS"]["value"]
    SAMPLES = ("우민재", "최혁진", "이두희", "윤성호", "한일그린텍", "이준희", "맹주연",
               "강정구", "오기수", "백가은", "조윤정", "박규현", "구창회", "한수진",
               "최선동", "임미라")
    notes = {f: note for k, f, _, note in rows if k == "CAPEX_MAJOR_EVIDENCE_STATUS"}
    graded = 0
    for name in SAMPLES:
        cnt = sum(1 for t in val.values() if name in str(t))
        hit = [n for n in notes.values() if n.startswith(name) and "140차 대조 기준" in n]
        assert len(hit) == 1, f"{name} 표본의 EVIDENCE_STATUS ref가 {len(hit)}건이다"
        assert ("중 **%d개**" % cnt) in hit[0], (
            f"{name}의 카테고리 수가 상수 값과 어긋난다 — 값은 {cnt}개에 이름이 나타난다")
        graded += 1
    assert graded == 16

    # ⑤ 포함·제외가 섞여 있다는 경고가 남아 있는가(이것이 없으면 수를 오독한다)
    sample_notes = " ".join(notes.values())
    assert "포함과 제외가 섞여 있다" in sample_notes, (
        "나타남에 제외 사유가 섞인다는 140차 경고가 사라졌다 — "
        "오기수는 greenhouse_structure에 '골조·피복 품목 전무(0)'로 등장한다")
    assert "4건으로 오독" in sample_notes, (
        "🔴 `—` 분할이 깨진다는 140차 실측(hvac 10 → 4)이 사라졌다 — "
        "그 기록이 없으면 다음 차수가 같은 자동 분류를 다시 시도한다")


def test_141cha_declared_counts_match_the_case_data():
    """141차 — 상태 문자열의 **선언 건수**가 실데이터와 맞는가.

    🔴 140차는 *"자동으로 셀 수 없다"*고 결론냈다 — 상태 문자열을 `—`로 쪼개려다
    **주석 안의 `—` 때문에 `hvac` 10건이 4건으로 오독**됐기 때문이다.
    **그것은 방법의 문제였다**: 문자열을 파싱할 게 아니라 **상수 자신의 데이터**
    (`CAPEX_MAJOR_CASE_CHUNKS` = 케이스 15 × 카테고리 금액)를 세면 된다.

    141차 실측: **선언 건수 8종이 전부 "금액>0 케이스 수"와 일치**하고,
    잔차(분류합 + 미분류 = `known_total`)도 **15케이스 전부 0건 불일치**다.

    📌 세는 단위는 **파일이 아니라 케이스**다 — `백가은·조윤정`은 **쌍 견적 통합 1건**.
    140차가 이름을 세어 15 vs 14로 어긋난 이유가 이것이다.
    """
    import os as _o, json as _j, io as _io, re as _re
    repo = _o.path.dirname(_o.path.abspath(__file__))
    C = _j.load(_io.open(_o.path.join(repo, "엔진데이터_레지스트리.json"),
                         encoding="utf-8"))["constants"]
    chunks = C["CAPEX_MAJOR_CASE_CHUNKS"]["value"]
    status = C["CAPEX_MAJOR_EVIDENCE_STATUS"]["value"]
    unc = C["CAPEX_MAJOR_UNCLASSIFIED"]["value"]
    kt = C["CAPEX_MAJOR_KNOWN_TOTALS"]["value"]

    assert len(chunks) == 15 and "백가은·조윤정" in chunks, (
        "케이스 키가 15개(쌍 견적 통합 1건 포함)가 아니다 — 세는 단위가 바뀌었다")

    # ① 🎯 선언 건수 vs 금액>0 케이스 수
    HEAD = _re.compile(r"^(실측|부분실측)\((?:축열탱크만\s*)?(\d+)건")
    EXPECT = {"greenhouse_structure": 14, "auto_opening_system": 15, "hvac": 10,
              "irrigation_fertigation": 14, "ict_control": 6, "electrical": 4,
              "auxiliary_facility": 1, "thermal_storage_insulation": 2}
    declared = {}
    for cat, txt in status.items():
        m = HEAD.match(str(txt))
        if m:
            declared[cat] = int(m.group(2))
    assert declared == EXPECT, (
        f"선언 건수가 바뀌었다: {declared} — 141차 실측은 {EXPECT}")
    for cat, n in EXPECT.items():
        present = [k for k, v in chunks.items() if v.get(cat, 0)]
        assert len(present) == n, (
            f"{cat}: 선언 {n}건인데 금액>0 케이스는 {len(present)}건이다 "
            f"({sorted(present)}) — 서술과 데이터가 어긋났다")

    # ② 잔차 — 분류합 + 미분류 = known_total (15케이스 전부)
    for k, v in chunks.items():
        got = sum(v.values()) + unc.get(k, 0)
        assert got == kt[k], (
            f"{k}: 분류합+미분류 {got:,} ≠ known_total {kt[k]:,}")

    # ③ 🔴 8종 전부가 "나머지가 왜 0인지"를 적는가
    #    141차는 `("0)", "없어 0", "전무", "전 표본")` 휴리스틱으로 쟀는데, 142차가
    #    채운 문구("0인 것은"·"0 사유")를 그 패턴이 못 잡았다 — **또 프로즈 휴리스틱이
    #    틀렸다**(140·141차와 같은 계열). → 휴리스틱을 버리고 **카테고리별 표지를 명시**한다.
    REASON_MARK = {
        "greenhouse_structure": "오기수는 설비 전용 부분 범위 견적",
        "auto_opening_system": "전 표본",
        "hvac": "견적 범위에 난방설비 자체가 없어 0",
        "irrigation_fertigation": "강정구는 부분 범위 견적",
        "ict_control": "독립 환경제어시스템 라인 없음(0)",
        "electrical": "별도 전기공사 공종 없음(0)",
        # 🔴 142차가 채운 둘
        "auxiliary_facility": "관리실 648",
        "thermal_storage_insulation": "축열탱크가 실재하는지는 확인되지 않았다",
    }
    assert set(REASON_MARK) == set(EXPECT)
    missing = [c for c, mark in REASON_MARK.items() if mark not in str(status[c])]
    assert not missing, (
        f"'나머지가 왜 0인지'를 적지 않는 카테고리: {missing} — "
        "141차에 auxiliary_facility·thermal_storage_insulation 둘이 비어 있었고 "
        "142차가 채웠다(R6 — 부재에 근거 병기)")

    # ④ 카테고리 키 커버리지 — 청크에만 있는 키가 생기면 상태표가 뒤진 것이다
    used = {c for v in chunks.values() for c in v}
    assert not (used - set(status)), (
        f"CASE_CHUNKS에만 있는 카테고리: {sorted(used - set(status))} — "
        "상태표가 데이터를 따라오지 못했다")

    doc = open(_o.path.join(repo, "근거_선언건수_검수_20260915.md"), encoding="utf-8").read()
    assert "방법의 문제였다" in doc, (
        "🔴 140차의 '셀 수 없다'가 방법의 문제였다는 141차 정정이 사라졌다")
    assert "쌍 견적 통합 1건" in doc, "세는 단위(케이스·쌍 견적 1건) 규칙이 사라졌다"
    assert "auxiliary_facility" in doc and "thermal_storage_insulation" in doc, (
        "제외 사유를 적지 않는 2건의 기록이 사라졌다")


def test_142cha_zero_reasons_are_recorded_facts_not_judgements():
    """142차 — 비대칭 2건의 0 사유는 **리포가 이미 기록한 사실**이다(판정 아님).

    141차가 남긴 것: `auxiliary_facility`(미언급 14건)·`thermal_storage_insulation`
    (13건)만 *"나머지가 왜 0인지"*를 적지 않았다.

    🔴 `CAPEX_MAJOR_CASE_CHUNKS`의 서술을 뒤지니 **사유가 이미 기록돼 있었다**:
      이준희 — 재배실 4,756.32 + **관리실 648㎡**가 실재하나 '0402 재배실벽체 및
               관리동지붕공사'가 온실구조에 **혼입**돼 0(52차)
      강정구 — 부속자재에 **관리동 판넬 및 출입문 부속 약 5,597,384원** 포함,
               **독립 공종이 아니라** 분리 안 함(56차)
      오기수 — **관리동커텐 2,817,269원**이 자동개폐로 귀속(57차)
    → **"부대시설이 없다"가 아니다.** 나머지 11건은 **확인되지 않았다**(판정하지 않는다).

    ⚠️ 이것은 **112차 이후 첫 엔진 상수 값 변경**이다 — 다만 `build_site`가
    **접두만**(`startswith`) 읽으므로 표시 분류는 불변이고, 계산에는 쓰이지 않는다.
    """
    import os as _o, sys as _s, json as _j, io as _io
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import smartfarm_engine as e

    C = _j.load(_io.open(_o.path.join(repo, "엔진데이터_레지스트리.json"),
                         encoding="utf-8"))["constants"]
    status = C["CAPEX_MAJOR_EVIDENCE_STATUS"]["value"]

    # ① 엔진과 레지스트리가 같은가(값을 바꿨으니 둘 다 움직여야 한다)
    assert e.CAPEX_MAJOR_EVIDENCE_STATUS == status, (
        "엔진 상수와 레지스트리 값이 어긋났다 — 142차는 **둘 다** 바꿨다")

    # ② 🔴 표시 분류 불변 — build_site는 접두만 읽는다
    for cat, want in (("auxiliary_facility", "실측"),
                      ("thermal_storage_insulation", "부분")):
        assert status[cat].startswith(want), (
            f"{cat}의 접두가 바뀌었다 — build_site의 태그 분류가 달라진다")

    # ③ 기록된 사실 3건이 살아 있는가(사유의 실체다)
    aux = status["auxiliary_facility"]
    for who, mark in (("이준희", "관리실 648"), ("이준희", "혼입"),
                      ("강정구", "5,597,384"), ("오기수", "2,817,269")):
        assert mark in aux, f"{who}의 0 사유({mark})가 사라졌다 — 리포가 기록한 사실이다"
    assert "'부대시설이 없다'는 뜻이 아니다" in aux, (
        "🔴 '실측 1건'이 '부대시설이 1건뿐'이라는 뜻이 아니라는 142차 정정이 사라졌다")

    # ④ 판정하지 않았다는 표기 — 나머지는 미확인이다
    for cat in ("auxiliary_facility", "thermal_storage_insulation"):
        assert "판정하지 않는다" in status[cat], (
            f"{cat}에서 미판정 표기가 사라졌다 — 0 사유는 판단성이다")
    assert "나머지 11건의 0 사유는 확인되지 않았다" in aux
    assert "13건에 축열탱크가 실재하는지는 확인되지 않았다" in status["thermal_storage_insulation"]

    # ⑤ 🔴 "언급 ≠ 근거"가 실증됐다 — 이름을 적자 언급 카테고리가 늘었다
    refs = C["CAPEX_MAJOR_EVIDENCE_STATUS"]["source_refs"]
    grew = [r for r in refs if "142차" in (r.get("note") or "")
            and "언급 ≠ 근거" in (r.get("note") or "")]
    assert len(grew) == 3, (
        f"언급 카테고리가 늘어난 표본 note가 {len(grew)}건이다 — "
        "142차 실측은 이준희·강정구·오기수 3건이다")
    for r in grew:
        assert r["note"].startswith(("이준희", "강정구", "오기수")), r["note"][:20]

    doc = open(_o.path.join(repo, "근거_0사유보강_20260915.md"), encoding="utf-8").read()
    assert "첫 엔진 상수 값 변경" in doc, (
        "112차 이후 첫 엔진 값 변경이라는 사실이 근거문서에서 사라졌다")
    assert "접두만" in doc, "표시 분류가 불변인 이유(접두만 읽는다)가 사라졌다"


def test_143cha_auxiliary_facility_exists_in_13_of_14_zero_cases():
    """143차 — `auxiliary_facility`가 0인 14건에 **관리동이 정말 없는가**.

    142차는 3건만 리포 기록으로 채우고 **11건을 미확인**으로 남겼다. 143차가 견적 원문
    **12파일을 직접 열어** 찾으니 **13건에 실재**한다(임미라만 미확인).

    🔴 **그래도 0이 틀린 것은 아니다** — 찾은 항목은 거의 전부 **골조·기초·커튼·피복
    공종 안의 라인**이고 **독립 부대시설 공종은 윤성호 `0116` 하나뿐**이라, 분류 규칙
    (독립 공종만 편입)상 **0이 맞다**. **문제는 값이 아니라 읽힘이다.**

    📌 방법적 교훈: **검색 대상을 내역서 1종으로 잡으면 놓친다** — 우민재는 내역서
    키워드 0건이었는데 **공사설명서에 작업장이 있었다**.
    """
    import os as _o, sys as _s, json as _j, io as _io
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import smartfarm_engine as e

    C = _j.load(_io.open(_o.path.join(repo, "엔진데이터_레지스트리.json"),
                         encoding="utf-8"))["constants"]
    aux = C["CAPEX_MAJOR_EVIDENCE_STATUS"]["value"]["auxiliary_facility"]

    assert e.CAPEX_MAJOR_EVIDENCE_STATUS["auxiliary_facility"] == aux, (
        "엔진과 레지스트리가 어긋났다 — 143차도 둘 다 바꿨다")
    assert aux.startswith("실측"), "접두가 바뀌었다 — build_site 태그가 달라진다"

    # ① 원문에서 찾은 증거가 남아 있는가(표본별 금액·품명)
    for who, mark in (("최혁진", "1,020,144"), ("이두희", "11,887,296"),
                      ("한일그린텍", "1,406,856"), ("맹주연", "12,125,520"),
                      ("백가은·조윤정", "6,370,000"), ("박규현", "AL고정스크린"),
                      ("구창회", "1,985,596"), ("한수진", "1,150,000"),
                      ("최선동", "240,500"), ("우민재", "샌드위치패널")):
        assert mark in aux, f"{who}에서 찾은 증거({mark})가 사라졌다 — 143차 원문 판독이다"
    assert "13건에 관리동·작업동 계열이 실재" in aux, (
        "🔴 14건 중 13건에 실재한다는 143차 결론이 사라졌다")

    # ② 🔴 "0이 틀린 것은 아니다" — 분류 규칙을 뒤집지 않았음을 고정한다
    assert "0이 틀린 것은 아니다" in aux and "독립 공종" in aux, (
        "분류 규칙(독립 공종만 편입)상 0이 맞다는 유보가 사라졌다 — "
        "이것이 없으면 '값이 틀렸다'로 읽힌다")
    assert "★사용자 결정" in aux, (
        "금액 이관은 ★사용자 결정이라는 표기가 사라졌다")

    # ③ 임미라는 미확인이다 — R6 병기(검색 대상·미열람 구간)
    assert "임미라만 확인되지 않았다" in aux and "견적서 1종뿐" in aux, (
        "임미라 미확인과 그 사유(도면·설명서 부재)가 사라졌다 — "
        "'없다'로 읽으면 R6 위반이다")

    # ④ 값은 여전히 0이다(서술만 늘었다)
    chunks = C["CAPEX_MAJOR_CASE_CHUNKS"]["value"]
    nonzero = [k for k, v in chunks.items() if v.get("auxiliary_facility", 0)]
    assert nonzero == ["윤성호"], (
        f"auxiliary_facility 금액>0 케이스가 {nonzero}로 바뀌었다 — "
        "143차는 서술만 보강했고 값은 옮기지 않았다(★사용자 결정)")

    # ⑤ 🔴 일괄 생성한 문구가 임미라에만 틀렸다 — 그 정정이 남아 있는가
    im = [r for r in C["CAPEX_MAJOR_EVIDENCE_STATUS"]["source_refs"]
          if (r.get("note") or "").startswith("임미라")]
    assert len(im) == 1 and "실재 증거가 아니다" in im[0]["note"], (
        "임미라 note의 143차 정정이 사라졌다 — 임미라는 '확인되지 않았다'로 언급된 것이지 "
        "관리동 실재 증거가 아니다(일괄 생성 문구가 이 표본에만 틀렸다)")

    doc = open(_o.path.join(repo, "근거_관리동_실재점검_20260915.md"), encoding="utf-8").read()
    assert "내역서 1종으로 잡으면 놓친다" in doc, (
        "🔴 검색 대상을 좁게 잡으면 놓친다는 143차 방법 교훈이 사라졌다 — "
        "우민재가 그 사례다")
    assert "미열람 구간" in doc, "임미라 미확인의 R6 병기가 근거문서에서 사라졌다"


def test_144cha_decision_ledger_covers_every_star():
    """144차 — ★결정 **대기 전량**이 한 곳에 있는가.

    🔴 106차는 14절 E절을 만들며 *"★가 붙은 나머지는 전부 E절로 동결됐다"*고 적었는데
    **E절 표는 8건**이고 **`B7`('동절기' 개월 정의)이 빠져 있었다** — 그 진술은 당시에도
    정확하지 않았다. 그 뒤 **4건이 더 생겼고 어느 목록에도 들어가지 않았다**.

    144차가 **대기 전량 13건 + 자료 4건**을 대장으로 모았다. 이 테스트가 막는 것:
    ①새 ★가 대장 밖에 생기는 것 ②E절(동결 8)을 대기 전량으로 착각하는 것.
    """
    import os as _o, re as _re
    repo = _o.path.dirname(_o.path.abspath(__file__))
    led = open(_o.path.join(repo, "근거_결정대기대장_20260915.md"), encoding="utf-8").read()
    wi = open(_o.path.join(repo, "작업지시서.md"), encoding="utf-8").read()

    # ① 13개 결정 식별자가 전부 있는가
    for tag, why in (
        ("D-1", "3성분 8% 보정 — 최대난방부하 +8.8%"),
        ("D-2", "99차 재검토 5.7→8.9 — 대장 U2의 선행"),
        ("D-3", "일조 조정계수 — 🔴원채원 회귀를 깬다"),
        ("D-4", "COVER_ASSEMBLIES 이관 — 적용 지점을 바꾼다"),
        ("D-5", "t_min 처리"),
        ("D-6", "마산↔창원 별칭 — 대장 WD1과 같은 항목"),
        ("D-7", "우민재 2,321.87 — 대장 AC5와 같은 항목"),
        ("D-8", "무인방제 편입 — 대장 CM1과 얽힌다"),
        ("D-9", "🔴'동절기' 개월 정의 — 106차가 E절에 넣지 않았다"),
        ("D-10", "공구손료 품목별 요율값(129차 F2)"),
        ("D-11", "크루 구성 공기 산정"),
        ("D-12", "공종 선언 순서 재정렬"),
        ("D-13", "부대시설 금액 이관(143차) — 분류 규칙 변경"),
    ):
        assert ("**%s**" % tag) in led, (
            f"대장에서 {tag}가 사라졌다 — {why} "
            "(부분 문자열이 아니라 **굵은 표기**로 찾는다 — D-9가 D-99에 "
            "먹히는 것을 144차 변이가 잡았다)")
    for tag in ("S-1", "S-2", "S-3", "S-4"):
        assert ("**%s**" % tag) in led, f"대장에서 자료 항목 {tag}가 사라졌다"

    # ② 🔴 E절이 '대기 전량'이 아니라는 사실 — 이것이 144차의 발견이다
    i = wi.index("### E. ★ 동결")
    j = wi.index("### D. 다음 후보", i)
    # ⚠️ 절 전체를 보면 안 된다 — 144차가 이 절에 **정정 배너**를 달며 그 이름들을
    #    적었고, 그러자 "E절에 없다"가 깨졌다(131차 자기증식과 같은 계열).
    #    동결 여부는 **표 행**이 말한다.
    E_rows = [ln for ln in wi[i:j].split(chr(10))
              if ln.startswith("|") and not ln.startswith("| ★ |")
              and set(ln) - set("|- ")]
    E_table = chr(10).join(E_rows)
    assert "동절기" not in E_table, (
        "E절 표에 동절기가 들어왔다면 대장의 D-9 서술(106차가 빠뜨렸다)을 갱신하라")
    for kw in ("공구손료", "크루", "부대시설"):
        assert kw not in E_table, f"E절 표에 {kw}가 들어왔다 — 대장의 ⓒ분류를 갱신하라"
    assert len(E_rows) >= 5, f"E절 표 행이 {len(E_rows)}개다 — 동결 목록이 사라졌는지 확인하라"
    assert "E절 표는 8건" in led and "B7" in led, (
        "🔴 'E절 8건 vs 대기 13건'이라는 144차 발견이 대장에서 사라졌다")

    # ③ B7이 작업지시서에 ★로 살아 있는가(닫혔다면 대장도 닫아야 한다)
    m = _re.search(r"\| B7 \|[^\n]*", wi)
    assert m and "★" in m.group(0), (
        "14절 B7이 사라졌거나 ★가 빠졌다 — 대장 D-9의 근거다")

    # ④ 회귀 기준에 닿는 2건이 표시돼 있는가
    assert "원채원 ROI 14.2%가 직접 깨진다" in led, (
        "D-3 관련 문자열이 대장에서 사라졌다 — ⚠️149차에 이 단정은 **철회**됐고 "
        "지금은 철회 배너 안의 **인용**으로만 존재한다(살아 있는 경고가 아니다)")
    assert "158원 → 42원" in led, (
        "D-7의 밴드 여유 감응이 사라졌다 — 🔴153차에 159 → 158로 정정됐다"
        "(240,000 − 557,152,000÷2,323 = 158.42)")

    # ⑤ 🔴 세면 부풀려진다 — 항목과 문자열을 구분했는가(131차 교훈)
    assert "366" in led and "항목으로 세면 13건" in led, (
        "★ 문자열 366회 vs 항목 13건이라는 구분이 사라졌다 — "
        "세면 부풀려진다는 131차 교훈이 여기에도 적용된다")

    # ⑥ 결정을 내리지 않았다는 표기(이 차수는 정리다)
    assert "결정은 **하나도 내리지 않았다**" in led, (
        "144차가 결정을 내리지 않았다는 표기가 사라졌다 — 판정 자동화 금지선이다")
    # 🔴 145차가 이 한계를 **해소**했다 — 가드가 설계대로 발화해 갱신됐다
    assert "145차에 측정됐다" in led, (
        "D-10~D-12의 감응 측정(145차) 연결이 대장에서 사라졌다")
    assert "나머지 10건의 감응은" in led, (
        "나머지 10건은 여전히 인용값이라는 한계가 사라졌다 — "
        "13건 전부가 측정된 것처럼 읽히면 안 된다")


def test_145cha_decision_sensitivities_are_measured():
    """145차 — D-10~D-12의 감응을 **측정**했다(결정은 내리지 않았다).

    🔴 **D-10의 후보 설계가 부정확했다**: 129차 F2는 *"품목별 요율값(0/2%/3%/5%)"*이라
    적었으나 원문 `[주]`를 분모까지 읽으면 **두 계열**이다 —
      공구손료·경장비 = **인력품(노무)의 %** (2%·3%, 29품목)
      잡재료·소모재료 = **주재료비의 %** (5%, 2품목)
    온실피복 #4는 ③ 공구손료 3% + ④ 잡재료 5%를 **동시에** 갖지만 **모순이 아니다**
    (분모가 다르다). 진짜 모순은 **선홈통**(같은 분모에 2%와 3%)뿐이고,
    그 감응은 **0.0059%p**라 **집계 수준에서 결정을 막지 않는다**.

    D-11은 **단순 반비례**(크루 1.0~16.4 → 공기 16.4배)다.

    🔴 **146차 정정(레드팀 27회차 [2])**: 여기 있던 *"D-12는 산출물 감응 0"*은 **틀렸다**.
    145차는 생성기의 `pumsem` **호출 경로**만 보고 **데이터 경로**(레지스트리 →
    `SmartFarm_근거대장.html`)를 보지 않았다. 아래 호출 경로 검사는 그대로 유효하지만
    **결론은 `test_146cha_*`가 뒤집는다** — 순서는 `test_registry`의 리스트 동일성으로
    고정돼 있고 근거대장 HTML에 선언 순서대로 인쇄된다.
    """
    import os as _o, sys as _s, re as _re, collections as _c
    import pytest as _pt
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import smartfarm_engine as e

    # ── D-11 · D-12는 원문 없이도 잴 수 있다 ────────────────────────────
    qty = {(it.category, it.name): 1.0 for it in e.PUMSEM_ITEMS}
    summ = e.pumsem_project_labor_summary(qty)
    assert round(summ["total_labor_days"], 3) == 11.920, (
        f"전 품목 물량 1.0의 총 인·일이 {summ['total_labor_days']}로 바뀌었다 — "
        "145차 실측은 11.920이다(D-11 감응의 분자)")
    assert len(summ["totals_by_trade"]) == 7
    for crew, days in ((8.0, 1.49), (16.4, 0.73)):
        assert abs(summ["total_labor_days"] / crew - days) < 0.01, (
            f"크루 {crew}명의 공기가 {summ['total_labor_days'] / crew:.2f}일로 바뀌었다")

    # D-12 — **호출 경로** 감응 0: 생성기 어디에서도 pumsem을 부르지 않는다
    #   ⚠️146차: 이것만으로 "산출물 감응 0"이라 결론한 것이 잘못이었다(위 docstring)
    for f in ("build_site.py", "webapp.py", "render_report.py", "run_report.py", "cases.py"):
        p = _o.path.join(repo, f)
        if not _o.path.exists(p):
            continue
        assert "pumsem" not in open(p, encoding="utf-8").read(), (
            f"{f}가 pumsem을 부르기 시작했다 — D-12(공종 선언 순서)의 감응이 "
            "0이 아니게 된다. 145차 측정을 다시 하라")

    doc = open(_o.path.join(repo, "근거_감응측정_D10_D12_20260915.md"), encoding="utf-8").read()
    assert "감응이 **0이 아니다**" in doc, (
        "🔴 D-12 감응의 146차 정정이 사라졌다 — 145차의 '산출물 감응 0'으로 되돌리지 마라")
    assert "16.4배" in doc, "D-11의 크루 범위 감응이 사라졌다"
    assert "결정도 내리지 않았다" in doc, (
        "145차가 결정을 내리지 않았다는 표기가 사라졌다 — 판정 자동화 금지선이다")

    # ── D-10은 원문을 열어야 한다 — 폰트 없으면 skip(128차 규율) ────────
    _pt.importorskip("pdfplumber")
    _pt.importorskip("fontTools")
    _pt.importorskip("pypdf")
    import pumsem_extract as px
    try:
        px._system_index()
    except px.FontsUnavailable:
        _pt.skip("시스템 폰트가 없다 — 128차 skip 규율과 같다")

    RATE = _re.compile(r"(\d+)%")
    by_cat = _c.defaultdict(list)
    for it in e.PUMSEM_ITEMS:
        by_cat[it.category].append(it)
    seq2item = {(c, n): it for c, its in by_cat.items() for n, it in enumerate(its, 1)}
    coef = {(it.category, it.name): sum(it.labor_per_unit.values()) for it in e.PUMSEM_ITEMS}
    total = sum(coef.values())

    tool, misc = _c.defaultdict(set), _c.defaultdict(set)
    for cat, no, notes in px.extract_notes():
        joined = []
        for t in notes:
            if joined and RATE.search(t) and "공구" not in t and "재료" not in t:
                joined[-1] = joined[-1] + " " + t
            else:
                joined.append(t)
        for t in joined:
            m = RATE.search(t)
            if not m:
                continue
            (tool if "공구" in t else misc if "재료" in t else tool)[int(m.group(1))].add((cat, no))

    # 🔴 분모가 다른 두 계열 — 하나의 필드로 담을 수 없다
    assert sorted(tool) == [2, 3], f"공구손료 요율이 {sorted(tool)}로 바뀌었다 — 실측은 2%·3%"
    assert sorted(misc) == [5], f"잡재료 요율이 {sorted(misc)}로 바뀌었다 — 실측은 5%"
    assert len(tool[2]) == 4 and len(tool[3]) == 26 and len(misc[5]) == 2, (
        f"품목 수가 바뀌었다: 공구 2% {len(tool[2])} · 3% {len(tool[3])} · 잡재료 5% {len(misc[5])}")

    both = tool[2] & tool[3]
    assert len(both) == 1 and seq2item[next(iter(both))].name == "선홈통공사", (
        f"같은 분모에 두 요율이 붙은 품목이 {sorted(both)}로 바뀌었다 — "
        "실측은 알루미늄공사 #6 선홈통공사 하나다(113차 E1)")
    misc_names = {seq2item[p].name for p in misc[5]}
    assert misc_names == {"천장우레탄판넬", "샌드위치판넬"}, (
        f"잡재료 5% 품목이 {misc_names}로 바뀌었다")

    tool_items = tool[2] | tool[3]
    assert len(tool_items) == 29
    share = sum(coef[(seq2item[p].category, seq2item[p].name)] for p in tool_items) / total
    assert abs(share - 0.665) < 0.005, (
        f"공구손료 규정 품목의 인·일 비중이 {share:.3f}로 바뀌었다 — 145차 실측 66.5%")

    lo = sum((2 if p in tool[2] else 3) / 100 * coef[(seq2item[p].category, seq2item[p].name)]
             for p in tool_items) / total
    hi = sum((3 if p in tool[3] else 2) / 100 * coef[(seq2item[p].category, seq2item[p].name)]
             for p in tool_items) / total
    assert abs(lo - 0.019802) < 1e-4 and abs(hi - 0.019861) < 1e-4, (
        f"가중 평균 공구손료율이 {lo:.6f}~{hi:.6f}로 바뀌었다 — 실측 1.9802~1.9861%")
    assert (hi - lo) * 100 < 0.01, (
        "선홈통 모순의 감응이 0.01%p를 넘었다 — '집계 수준에서 결정을 막지 않는다'가 깨진다")

    assert "분모가 다르다" in doc and "두 필드가 필요하다" in doc, (
        "🔴 D-10의 후보 설계 정정(한 필드 → 두 필드)이 근거문서에서 사라졌다")


def test_146cha_redteam27_corrections_hold():
    """146차 — 레드팀 27회차 발견 13건을 **원문으로 재검증**한 뒤의 정정이 살아 있는가.

    🔴 타당 8건 중 **5건이 내가 쓴 137·140·142·143·145차의 결함**이었다. 공통 원인은
    **절대표현**(유일한·전량·0건)과 **문자열 탐색으로 감응을 재는 습관**이다.
    거짓 양성 5건은 조치하지 않았다([4]·[5]·[8]·[11]·[13] — 근거문서 §8).

    이 가드가 막는 것: 정정이 조용히 원복되는 것.
    """
    import os as _o, sys as _s, re as _re
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import smartfarm_engine as e
    import verify_refs as vr

    rd = lambda n: open(_o.path.join(repo, n), encoding="utf-8").read()
    reg = rd("엔진데이터_레지스트리.json")
    doc = rd("근거_레드팀27_재검증_20260915.md")

    # ── [1] 🔴 두 면적 계열을 섞은 식이 되살아나지 않는가 ──────────────
    F, PY = 114870017, 3.3057851239669422
    assert abs(F / (2323.0 / PY) - 163467.75) < 0.5, "2,323㎡ 기준 단가 재검산이 깨졌다"
    assert abs(F / (2321.87 / PY) - 163547.31) < 0.5, "2,321.87㎡ 기준 단가 재검산이 깨졌다"
    assert abs(F / 702.36 - 163548.63) < 0.5
    assert e.STRUCTURE_ONLY_PYEONG == 163400, (
        "등재값이 바뀌었다 — 146차는 **서술만** 고쳤다(값 불변)")
    DQ = chr(34)
    assert "÷702.36평=163,470" not in reg.replace("'÷702.36평=163,470'", ""), (
        "🔴 레지스트리에 '702.36평=163,470'이 인용부호 없이 되살아났다 — "
        "702.36평은 2,321.87㎡ 계열이고 163,470은 2,323㎡ 계열이라 **한 식에 못 쓴다**")
    assert "702.7075" in reg and "163,468" in reg, (
        "표지 2,323㎡ 기준 통일값(702.7075평·163,468원/평)이 사라졌다")
    for const, needle in (("STRUCTURE_ONLY_PYEONG", "163,468"),):
        assert needle in reg, f"{const}의 정정값 {needle}이 사라졌다"

    # D-7의 추가 감응(144차가 빠뜨린 줄)
    led = rd("근거_결정대기대장_20260915.md")
    assert "0.0415% → 0.0902%" in led, (
        "D-7이 채택되면 near 오차가 2.2배가 된다는 146차 감응이 대장에서 사라졌다")

    # ── [2] 🔴 D-12는 '산출물 감응 0'이 아니다 — 반례 2건이 실재하는가 ──
    treg = rd("test_registry.py")
    assert 'eng == C["PUMSEM_ITEMS"]["value"]' in treg, (
        "🔴 test_registry의 리스트 동일성 비교가 사라졌다 — 그것이 D-12의 반례①"
        "(선언 순서가 테스트로 고정돼 있다)이다")
    ledger_html = _o.path.join(repo, "SmartFarm_근거대장.html")
    if _o.path.exists(ledger_html):
        html = open(ledger_html, encoding="utf-8").read()
        first = e.PUMSEM_ITEMS[0]
        assert first.name in html and first.unit in html, (
            f"🔴 근거대장 HTML에서 PUMSEM 첫 품목({first.name})이 사라졌다 — "
            "레지스트리 value가 선언 순서대로 인쇄된다는 것이 D-12의 반례②다")
    sens = rd("근거_감응측정_D10_D12_20260915.md")
    assert "감응이 **0이 아니다**" in sens, (
        "🔴 D-12 감응 정정이 사라졌다 — 145차의 '산출물 감응 0'은 호출 경로만 본 결론이다")
    assert "데이터 변경 차수" in led, "대장의 D-12가 '데이터 변경 차수'로 정정된 표기가 사라졌다"

    # ── [3] 🔴 build_site는 상태 문자열을 **전문**으로 렌더한다 ─────────
    bs = rd("build_site.py")
    assert "{md(ev)}" in bs, (
        "🔴 build_site가 상태 문자열 **전문**을 렌더하지 않게 바뀌었다면 "
        "`근거_0사유보강`의 146차 정정(유일한 사용처가 아니다)을 갱신하라. "
        "148차부터 그 자리는 `esc(ev)`가 아니라 `md(ev)`다 — 여전히 전문이고, "
        "이제 마크다운을 **태그로** 렌더한다(리터럴 별표가 아니라)")
    zero = rd("근거_0사유보강_20260915.md")
    assert ("*" + DQ + "유일한 사용처" + DQ + "*는 틀렸다") in zero, (
        "142차의 '유일한 사용처' 절대표현에 대한 146차 정정이 사라졌다")
    assert "리터럴로" in zero, "마크다운이 HTML에 리터럴로 나간다는 실측이 사라졌다"

    # ── [6] 🔴 기준이 차수 번호뿐인 ref 7건 ────────────────────────────
    assert vr.soft_criteria("근거(93차 — 외곽 치수)", strict=True) == set(), (
        "🔴 strict 모드가 차수 번호를 여전히 '숫자 기준'으로 센다 — "
        "그 숫자로는 원문을 다시 찾아갈 수 없다")
    assert "숫자" in vr.soft_criteria("근거(93차 — 외곽 치수)"), (
        "기본 모드까지 바뀌었다 — 140차 판정을 소급해 흔들지 않기로 했다")
    weak = vr.weak_check()
    assert len(weak) == 0, (
        f"기준이 차수 번호뿐인 partial·near가 {len(weak)}건 생겼다: {weak[:3]} — "
        "146차에 7건이었고 **147차가 원문으로 전부 닫았다**"
        "(`근거_도면대조기준_20260916.md`). 새로 생겼다면 그 note에 "
        "숫자·위치·인용을 채워라 — 차수 번호는 기준이 아니다")
    assert len(vr.soft_check()) == 0, (
        "기준이 **아예** 없는 ref가 생겼다 — weak(차수뿐)과 다른 등급이다")

    # ── [7] 🔴 오기수 관리동커텐은 **독립 공종**이었다 ─────────────────
    ev = e.CAPEX_MAJOR_EVIDENCE_STATUS["auxiliary_facility"]
    assert "하나뿐**이라 분류 규칙" not in ev, (
        "🔴 '독립 부대시설 공종은 윤성호 0116 하나뿐이라 …0이 맞다'는 **단정문**이 "
        "되살아났다 — 오기수 집계표 p2의 '3. 관리동커텐공사 2,817,269'가 반례다(원문 확인). "
        "146차는 그 문구를 인용부호 안에 넣고 '틀렸다'로 뒤집었다")
    assert "한 규칙으로 설명되지 않는다" in ev, (
        "14건의 0이 한 규칙으로 설명되지 않는다는 146차 정정이 사라졌다")
    assert "보온커튼 관례(57차)로 자동개폐에 귀속" in ev, (
        "오기수의 진짜 0 사유(공종 성격)가 사라졌다")
    # 재집계 값은 '약'이 아니라 정확한 합이다([8] — 거짓 양성이 드러낸 구멍)
    assert "부속 5,597,384원" in ev and "약 5,597,384" not in ev, (
        "강정구 재집계 값의 '약'이 되살아났다 — 판넬·출입문 7줄 합으로 **정확히** 맞는다")
    assert "211,384" in zero and "2,500,000" in zero, (
        "🔴 강정구 5,597,384의 재집계 식이 사라졌다 — 식이 없어서 레드팀이 재현에 실패했다")

    # ── [9] D-10 감응의 가정이 적혀 있는가 ─────────────────────────────
    assert "직종 노임이 균일할 때" in sens, (
        "🔴 1.98%가 '직종 노임 균일' 가정 위의 수치라는 표기가 사라졌다 — "
        "공구손료의 분모는 인력품(금액)이지 인·일이 아니다")
    assert "56.8%" in sens and "96.2%" in sens, (
        "규정 품목의 직종 쏠림(철골공 56.8% + 조력공 39.4% = 96.2%) 실측이 사라졌다")

    # ── [10] 🔴 대장이 '대기 전량'을 다시 선언하지 않는가 ──────────────
    # 🔴 표 **행**으로 좁힌다 — 본문 산문에도 "D-14"가 나와 부분문자열 검사는
    #   내 설명문에 걸려 통과해 버린다(146차 뮤테이션 M5가 그렇게 빠져나갔다.
    #   131차 자기부풀림·144차 B7과 같은 함정이다).
    rows = [ln for ln in led.splitlines() if ln.lstrip().startswith("|")]
    for tag in ("D-14", "D-15"):
        assert any(ln.lstrip().startswith("| **%s** |" % tag) for ln in rows), (
            f"146차가 올린 {tag}가 대장 **표에서** 사라졌다 — 산문 언급은 등재가 아니다")
    assert "이 대장은 **대기 전량**이다 — 둘은 다르다" not in led, (
        "🔴 '대기 전량'이라는 절대표현이 되살아났다 — 106차의 '전부 동결됐다'와 같은 실수다")
    assert "탐색 범위는" in led, "R6(유일성·전량 주장은 탐색 범위를 병기) 표기가 사라졌다"
    eng_src = open(_o.path.join(repo, "smartfarm_engine.py"),
                   encoding="utf-8", newline="").read().replace(chr(13) + chr(10), "\n")
    stars = [i for i, ln in enumerate(eng_src.split("\n"), 1) if "★" in ln]
    assert len(stars) == 22, (
        f"엔진의 ★ 줄이 {len(stars)}개다 — 146차 전수는 22개다. "
        "새 ★가 생겼다면 **대장에 먼저 올려라**(대장 §5-3)")

    # ── [12] 스냅샷의 skip 수가 앞뒤로 맞는가 ──────────────────────────
    wi = rd("작업지시서.md")
    assert "skip 3건인지" not in wi, (
        "🔴 '303 passed + 5 skipped' 바로 뒤에 'skip 3건인지'가 되살아났다")
    assert "skip 5건인지" in wi, "정정된 skip 수가 사라졌다"

    # ── 이 차수가 무엇을 안 했는지 ─────────────────────────────────────
    assert "결정은 하나도 내리지 않았다" in doc, (
        "146차가 결정을 내리지 않았다는 표기가 사라졌다 — 판정 자동화 금지선이다")
    assert "거짓 양성 5" in doc, "거짓 양성 5건 분류가 사라졌다 — 레드팀 발견도 검증 대상이다"


def test_147cha_drawing_refs_carry_criteria():
    """147차 — 146차 [6]이 연 weak 7건을 **원문으로** 닫았는가.

    🔴 부수 소득이 더 크다: 평면도 2장의 치수가 등재 면적을 **정확히 재현**한다
    (93×44=4,092 · 85×37=3,145). 등재 기준은 **전장 × 외곽폭**이지 연동폭이 아니다.
    93차가 *"외곽 치수"*라 적었지만 **어느 치수인지**는 없었다.

    ⚠️ 그래도 **등급은 올리지 않았다** — 도면에 면적은 인쇄돼 있지 않고 곱셈 결과이며
    값의 출처는 견적서 사업량 표기다(140차 RECOMPUTED 규율).
    """
    import os as _o, sys as _s
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import smartfarm_engine as e
    import verify_refs as vr
    import pumsem_extract as px

    doc = open(_o.path.join(repo, "근거_도면대조기준_20260916.md"), encoding="utf-8").read()

    # ── ① 재집계가 등재 면적과 일치하는가 ──────────────────────────────
    area = {r[0]: r[1] for r in e.ACTUALS if isinstance(r, (list, tuple)) and len(r) >= 2}
    for who, L, W in (("한수진", 93, 44), ("최선동", 85, 37)):
        assert area.get(who) == L * W, (
            f"{who} 등재 면적 {area.get(who)}가 도면 재집계 {L}×{W}={L * W}와 어긋난다 — "
            "147차 실측은 정확히 일치였다. 면적을 바꿨다면 도면 note도 함께 고쳐라")
    assert 93 * 44 == 4092 and 85 * 37 == 3145

    # 연동폭이 아니라 **외곽폭**이라는 것이 147차의 요지다
    assert 7 * 6 + 1 * 2 == 44 and 7 * 5 + 1 * 2 == 37
    for mark in ("전장 × 외곽폭", "4,092", "3,145", "7,000 × 6 = 42,000"):
        assert mark in doc, f"근거문서에서 {mark}가 사라졌다"

    # ── ② 🔴 세로쓰기 뒤집힘 교훈이 남아 있는가 ────────────────────────
    assert "upright" in doc and "000,44" in doc, (
        "🔴 세로쓰기 치수가 뒤집혀 추출된다는 실측(upright로 확인)이 사라졌다 — "
        "138차 자릿수 교훈의 도면판이다")
    assert "부분문자열은 항목이 아니다" in doc, (
        "'3,000'을 세면 '93,000' 안의 것까지 세진다는 경고가 사라졌다(131차 계열)")

    # ── ③ weak 7건이 실제로 닫혔는가 — note를 직접 본다 ────────────────
    rows = vr.soft_refs()
    DRAW = ("한수진 - 평면도", "한수진 - 측면골조도", "한수진 - 주단면도",
            "최선동 - 평면도", "최선동 - 측면골조도", "최선동 - 주단면도")
    seen = 0
    for k, f, g, note in rows:
        base = _o.path.basename(f)
        if not any(d in base for d in DRAW):
            continue
        seen += 1
        assert vr.soft_criteria(note, strict=True) == {"숫자", "위치", "인용"}, (
            f"{base}의 대조 기준이 {sorted(vr.soft_criteria(note, strict=True))}로 줄었다 — "
            "147차는 숫자·위치·인용 셋을 전부 채웠다(차수 번호를 뺀 뒤에도)")
        assert "**" not in note, (
            f"🔴 {base} note에 마크다운 별표가 들어왔다 — ⚠️153차: 148차부터 `build_site.md()`가 "
            "마크다운을 **태그로 렌더**한다(146차 [3]의 「해석하지 않는다」는 더 이상 사실이 "
            "아니다). 그래도 note에는 쓰지 않는다 — 강조는 「」로 하라")
        assert "147차 대조 기준" in note, f"{base}의 147차 대조 기준이 사라졌다"
    assert seen == 6, f"도면 ref가 {seen}건이다 — 147차 실측은 6건"

    # 평면도 2건만 재집계 식을 갖는다(골조도·단면도는 면적을 주지 않는다)
    plan = {_o.path.basename(f): note for k, f, g, note in rows if "평면도" in _o.path.basename(f)}
    assert len(plan) == 2, f"평면도 ref가 {len(plan)}건이다"
    for base, note in plan.items():
        who = "한수진" if "한수진" in base else "최선동"
        L, W, A, BAYS = ((93, 44, "4,092", 6) if who == "한수진"
                         else (85, 37, "3,145", 5))
        # 외곽폭의 분해식 — 연동폭만 틀려도 잡아야 한다(뮤테이션 N7)
        assert f"외곽폭 {W},000 = 7,000×{BAYS}연동 + 양측 1,000" in note, (
            f"{base} note에서 외곽폭 분해식이 사라졌거나 틀렸다 — "
            f"{who}는 7,000×{BAYS}연동 + 양측 1,000 = {W},000이다")
        assert f"「{7 * BAYS},000」" in note, (
            f"{base} note에서 연동폭 {7 * BAYS},000이 사라졌다")
        for tok in (f"{L},000", f"{W},000", A):
            assert tok in note, f"{base} note에서 {tok}가 사라졌다"
        # 🔴 재집계 **식** 자체를 고정한다 — 값만 세면 note 다른 자리의 같은 숫자에
        #   걸려 통과한다(147차 뮤테이션 N6이 그렇게 빠져나갔다)
        assert f"{L} × {W} = {A}" in note, (
            f"{base} note에서 재집계 식 '{L} × {W} = {A}'가 사라졌다 — "
            "도면에 면적은 인쇄돼 있지 않으므로 식이 곧 대조 기준이다")
        assert "재집계" in note, f"{base} note가 재집계임을 밝히지 않는다 — 도면에 면적은 없다"

    # ── ④ PUMSEM_ITEMS ref의 쪽번호가 SECTION_PAGES와 1:1인가 ─────────
    pum = [note for k, f, g, note in rows
           if k == "PUMSEM_ITEMS" and "비닐원가계산서_부재확정" in f]
    assert len(pum) == 1, f"비닐 원가계산서 ref가 {len(pum)}건이다"
    note = pum[0]
    starts = [lo for name, lo, hi in px.SECTION_PAGES]
    assert starts == [138, 141, 144, 146, 151, 156, 158, 160, 162], (
        f"SECTION_PAGES 시작 쪽이 {starts}로 바뀌었다 — note의 목차표와 1:1이 깨진다")
    for p in starts:
        assert str(p) in note, (
            f"note에서 공종 시작 쪽 {p}가 사라졌다 — 이 1:1 대응이 이 ref의 대조 기준이다")
    assert "109~167" in note and "목차" in note, "제7장 범위 정정의 앵커가 사라졌다"
    assert vr.soft_criteria(note, strict=True) == {"숫자", "위치", "인용"}

    # ── ⑤ 등급은 올리지 않았다 ────────────────────────────────────────
    C = vr.load_registry()
    dist = {}
    for k, v in C.items():
        for r in (v.get("source_refs") or []):
            dist[r["match"]] = dist.get(r["match"], 0) + 1
    assert dist == {"exact": 90, "partial": 55, "near": 9}, (
        f"등급 분포가 {dist}로 바뀌었다 — 147차는 note만 채웠고 등급은 건드리지 않았다"
        "(151차에 `OVERHEAD_RATES` partial 3건이 더해져 50 → 53, "
        "163차에 `REGION_DESIGN_LOAD`의 [별표] 사본 2건이 더해져 53 → 55). "
        "도면이 면적을 정확히 재현해도 값의 출처는 견적서 사업량 표기다")
    assert "등급은 `partial` 그대로 둔다" in doc, "등급을 올리지 않았다는 표기가 사라졌다"

    # ── ⑥ 이 차수가 하지 않은 것 ──────────────────────────────────────
    assert "3,745" in doc and "3,757" in doc, (
        "🔴 근거대장 HTML의 리터럴 별표 실측(146차 3,757 → 147차 3,745)이 사라졌다 — "
        "146차는 CAPEX분해 80개만 보고 규모를 과소평가했다")
    assert "결정은 하나도 내리지 않았다" in doc, (
        "147차가 결정을 내리지 않았다는 표기가 사라졌다 — 판정 자동화 금지선이다")


def test_148cha_markdown_render_and_area_anchor():
    """148차 — 146차가 *"후보"*·*"기록만"*으로 남긴 [3]·[5]를 닫았는가.

    [3] 생성기가 마크다운을 렌더하지 않아 산출물에 리터럴 별표가 **3,833개** 있었다.
        고칠 자리는 데이터가 아니라 **생성기**다 — `md()`를 넣었다.
    [5] 앵커가 7자리 이상만 잡아 **면적이 검산 대상 밖**이었고, 게다가 `\\b`가
        **한글 접미사 앞에서 실패**해 `40,093,200원`이 통째로 안 잡혔다.

    🔴 [5]를 열자 결함이 하나 나왔다 — 이두희 2,736은 문서에 **인쇄돼 있지 않은
    역산값**(8×6×57)인데 139차 note가 금액과 묶어 "문서에서 확인"이라 적었다.
    """
    import os as _o, re as _re, sys as _s, json as _j, glob as _g
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import verify_refs as vr
    import build_site as bsmod

    rd = lambda n: open(_o.path.join(repo, n), encoding="utf-8").read()
    doc = rd("근거_마크다운렌더_면적앵커_20260916.md")

    # ── ① md()가 설계대로 도는가 ───────────────────────────────────────
    md = bsmod.md
    DQ = chr(34)
    cases = [
        ("**굵게** 보통", "<b>굵게</b> 보통"),
        ("`CODE_X`", "<code>CODE_X</code>"),
        ("*" + DQ + "인용 안에 **굵게**" + DQ + "*",
         "<i>&quot;인용 안에 <b>굵게</b>&quot;</i>"),
        # 🔴 치수는 절대 건드리면 안 된다 — 레지스트리에 21곳 있다
        ("ㅁ60*60*2.3T 와 4000*4000", "ㅁ60*60*2.3T 와 4000*4000"),
        # 이스케이프가 먼저다
        ("<script>x</script>", "&lt;script&gt;x&lt;/script&gt;"),
        # 짝이 안 맞으면 깨진 HTML을 만들지 않고 그대로 둔다
        ("짝 없는 ** 하나", "짝 없는 ** 하나"),
    ]
    for src, want in cases:
        got = md(src)
        assert got == want, f"md({src!r}) = {got!r} — 기대 {want!r}"
    # 태그를 우리가 넣은 것 외에는 만들지 않는다
    assert "<" not in md("a < b & c > d").replace("&lt;", "").replace("&gt;", "")

    # md_cut: 자르다 짝이 깨진 `**`는 버린다
    cut = bsmod.md_cut("가" * 150 + " **잘릴 강조입니다", 160)
    assert "**" not in cut, f"자른 뒤 리터럴 별표가 남았다: …{cut[-40:]}"

    # ── ② 산출물에 리터럴 별표가 남지 않는가 ──────────────────────────
    left = {}
    for f in sorted(_g.glob(_o.path.join(repo, "SmartFarm_*.html"))) + \
            [_o.path.join(repo, "index.html")]:
        if not _o.path.exists(f):
            continue
        n = open(f, encoding="utf-8").read().count("**")
        if n:
            left[_o.path.basename(f)] = n
    total = sum(left.values())
    assert total <= 2, (
        f"산출물의 리터럴 마크다운 별표가 {total}개다({left}) — 148차 실측은 2개이고 "
        "그 2개는 **코드 스팬 안**이라 리터럴이 맞다. 늘었다면 `esc(...)`로 내보내는 "
        "서술 필드가 새로 생긴 것이다 — `md(...)`로 바꿔라")
    for mark in ("3,833", "1,887"):
        assert mark in doc, f"근거문서에서 {mark}가 사라졌다"
    # 🔴 156차: 종전 "치수 표기가 21곳"은 **「곳」이 아니라 패턴 출현 횟수**였다.
    #   단위를 갈라 적은 표가 살아 있는지 본다(자세한 검사는 test_156cha_).
    assert "「21곳」은 「곳」이 아니었다" in doc

    # 🔴 생성된 HTML만 보면 **소스 회귀를 놓친다**(148차 뮤테이션 P1이 그렇게
    #   빠져나갔다 — HTML은 커밋된 것을 읽으므로 다시 빌드하기 전엔 안 바뀐다).
    #   서술 필드의 **호출 지점**을 직접 고정한다.
    bs = rd("build_site.py")
    Q = chr(39)
    for call in ("{md(ev)}",
                 "{md(v[" + Q + "source" + Q + "])}",
                 "{md(r[" + Q + "note" + Q + "])}",
                 "{md(c[" + Q + "source" + Q + "])}",
                 "{md(vtxt)}",
                 "{md(case[" + Q + "partial_note" + Q + "])}",
                 "{md(data[" + Q + "provenance" + Q + "])}",
                 "md_cut(c.get(" + Q + "status_note" + Q + ", ''), 160)"):
        assert call in bs, (
            f"build_site에서 `{call}` 호출이 사라졌다 — 서술 필드를 `esc(...)`로 "
            "되돌리면 리터럴 마크다운이 다시 산출물로 나간다(146차 [3])")
    assert bs.count("md(") >= 17, (
        f"md( 호출이 {bs.count('md(')}회다 — 148차 실측은 17회 이상이다")

    # ── ③ 🔴 레지스트리에 생따옴표를 넣지 않는다(JSON이 깨진다) ───────
    reg_raw = rd("엔진데이터_레지스트리.json")
    _j.loads(reg_raw)          # 146·148차에 두 번 깨뜨렸다 — 로드 자체가 가드다
    assert "「" in reg_raw, (
        "레지스트리의 인용 표기 「」가 사라졌다 — 생따옴표는 JSON 문자열을 깨뜨린다")
    assert "「」를 쓴다" in doc, "148차가 굳힌 인용 관례가 근거문서에서 사라졌다"

    # ── ④ 면적 앵커 — 단위가 붙은 것만 ────────────────────────────────
    A = vr.anchors_of
    assert A("연면적 2,736㎡ 확인") == [2736], "단위 붙은 면적이 앵커로 안 잡힌다"
    assert A("2021년 12월 · 수량 1,200개") == [], (
        "🔴 단위 없는 4자리가 앵커로 들어왔다 — 연도·수량이 앵커가 되면 거짓 불일치가 "
        "는다(138차 P2 과잉교정)")
    assert A("금액 40,093,200원") == [40093200], (
        "🔴 `\\b`가 한글 접미사 앞에서 실패하던 버그가 되살아났다 — 한글은 `\\w`다")
    assert A("4,092평 규모") == [4092]
    assert A("456,158,140 직접공사비") == [456158140], "부분문자열 456,158이 끼면 안 된다"
    assert A("2,323㎡ vs 2,321.87㎡") == [2323], "소수 꼬리가 앵커로 끼면 안 된다"

    n_anchor = sum(len(vr.anchors_of(r[-1])) for r in vr.exact_refs())
    assert n_anchor == 57, (
        f"exact ref 앵커 총수가 {n_anchor}다 — 148차 실측은 57(종전 51). "
        "note를 고쳤다면 `python verify_refs.py --full`로 스냅샷을 다시 뜨라")

    # ── ⑤ 🔴 이두희 2,736은 역산이다 ──────────────────────────────────
    assert 8 * 6 * 57 == 2736
    note = [r[-1] for r in vr.exact_refs()
            if r[0] == "ACTUALS_COUNT" and "이두희 천안 20251028.pdf" in r[1]]
    assert len(note) == 1, f"이두희 ACTUALS_COUNT ref가 {len(note)}건이다"
    note = note[0]
    assert "인쇄돼 있지 않" in note, (
        "🔴 이두희 면적 2,736이 원문에 인쇄돼 있지 않다는 선언이 사라졌다 — "
        "53쪽 전수에서 0건이고 8m×6연동×57m의 역산값이다. 선언이 없으면 "
        "`full_check`가 MISS로 떨어진다")
    assert "역산" in note and "582,455,045" in note, (
        "이두희 note에서 금액(문서 확인)과 면적(역산)의 구분이 사라졌다")
    dump = rd("verify_refs_dump.txt")
    assert "OK 31 · RECOMPUTED 8" in dump
    assert not [ln for ln in dump.splitlines()
                if ln.startswith("MISS") or ln.startswith("UNK")], (
        "재검산 스냅샷에 MISS/UNK가 생겼다")

    # ── ⑥ 이 차수가 하지 않은 것 ──────────────────────────────────────
    assert "면적 기준 통일" in doc and "★사용자 결정" in doc, (
        "이두희 방풍 미포함 기준이 ★대기임을 밝힌 표기가 사라졌다 — 148차는 표기만 고쳤다")
    assert "결정은 하나도 내리지 않았다" in doc


def test_149cha_entangled_four_are_measured():
    """149차 — ⓐ 얽힘 블록(D-1~D-4)의 감응을 **측정**했다(결정은 내리지 않았다).

    🔴 **대장 한 행과 표제가 틀렸다**:
      ① D-3 *"OPEX 20~33% 움직여 원채원 ROI 14.2%가 깨진다"* → **깨지지 않는다.**
         `sunshine_k`는 **연료소비량만** 움직이고 그 값은 `compute()` 반환 dict에도
         생성기 5개에도 없다. "20~33%"는 **연료 감소율을 그대로 옮겨 적은 것**이다.
      ② *"순서와 조합이 곧 결과다"* → **D-2와 D-4는 배타**다(엔진이 거부).
      ③ D-2는 **필름 계열만** — `U_DESIGN`에 유리 키가 없다.

    ⚠️ 146차 [2]의 교훈대로 **호출 경로와 데이터 경로를 둘 다** 봤다.
    """
    import os as _o, sys as _s
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import smartfarm_engine as e
    import render_report as rr
    from cases import load_cases, case_to_input

    rd = lambda n: open(_o.path.join(repo, n), encoding="utf-8").read()
    doc = rd("근거_얽힘4건_감응측정_20260916.md")
    led = rd("근거_결정대기대장_20260915.md")

    cs = {c.get("case_id"): c for c in load_cases()}
    um = case_to_input(cs["uminjae"])       # 필름 — D-2 적용 대상
    wc = case_to_input(cs["wonchaewon"])    # 유리 — 회귀 기준 케이스

    def hl(inp, **kw):
        fr = kw.pop("fr", inp.fr)
        return e.heating_load(inp.surface_area_m2, inp.cover.value,
                              inp.t_target, inp.t_min, fr,
                              floor_area_m2=inp.area_m2, **kw)

    # ── ① 🔴 경제성은 난방과 연결돼 있지 않다 ─────────────────────────
    r = rr.compute(wc)
    ec = r["economics"]
    assert abs(ec["roi"] - 0.1416150) < 1e-5, f"원채원 ROI가 {ec['roi']}로 바뀌었다"
    assert abs(ec["payback"] - 7.0613973) < 1e-4
    assert abs(ec["real_roi"] - 0.2832301) < 1e-5
    assert "fuel_consumption" not in r["heating"], (
        "🔴 compute()의 heating 블록에 fuel_consumption이 들어왔다 — "
        "들어오면 D-3의 산출물 감응이 0이 아니게 된다. 149차 측정을 다시 하라")
    # 데이터 경로: opex는 케이스 입력이지 연료에서 유도되지 않는다
    assert ec["opex"] == wc.opex, (
        "🔴 compute()의 opex가 입력과 달라졌다 — 유도가 생겼다면 D-3이 회귀에 닿는다")
    for f in ("build_site.py", "webapp.py", "render_report.py",
              "run_report.py", "cases.py"):
        p = _o.path.join(repo, f)
        if _o.path.exists(p):
            assert "fuel" not in open(p, encoding="utf-8").read(), (
                f"{f}가 fuel을 쓰기 시작했다 — D-3 감응 측정을 다시 하라")

    # ── ② D-3은 연료만 움직인다 · 최대부하 불변 ───────────────────────
    base = hl(wc)
    assert set(e.PERIOD_LOAD_ADJUST_K.values()) == {3020.0, 2820.0, 2620.0, 2420.0, 2220.0}
    lo, hi = None, None
    for k in sorted(e.PERIOD_LOAD_ADJUST_K.values()):
        h = hl(wc, sunshine_k=k)
        assert abs(h.max_load_kcal_h - base.max_load_kcal_h) < 1e-6, (
            "🔴 sunshine_k가 최대부하를 움직이기 시작했다 — 149차 실측은 불변이다")
        ratio = h.fuel_consumption / base.fuel_consumption - 1
        lo = ratio if lo is None else min(lo, ratio)
        hi = ratio if hi is None else max(hi, ratio)
    assert abs(lo - (-0.383333)) < 1e-4 and abs(hi - (-0.161111)) < 1e-4, (
        f"연료 감응이 {lo:.4f}~{hi:.4f}로 바뀌었다 — 149차 실측은 −38.3%~−16.1%")
    # 🔴 대장이 적던 −21.7/−32.8은 k=2820·2420의 **연료** 변동률이다
    assert abs(hl(wc, sunshine_k=2820.0).fuel_consumption / base.fuel_consumption
               - 0.783333) < 1e-5
    assert abs(hl(wc, sunshine_k=2420.0).fuel_consumption / base.fuel_consumption
               - 0.672222) < 1e-5

    # ── ③ 🔴 D-2와 D-4는 배타 — 엔진이 거부한다 ───────────────────────
    KEY = ("po-0.10", "5겹다겹")
    assert e.cover_assembly_lookup(KEY) is not None, "D-4 측정에 쓴 조합키가 사라졌다"
    try:
        hl(um, u_design=8.9, fr=None, assembly=KEY)
        raise AssertionError(
            "🔴 엔진이 assembly와 u_design의 동시 지정을 허용하기 시작했다 — "
            "D-2/D-4가 '배타'라는 149차 결론이 깨진다. 대장 ⓐ 표제를 다시 고쳐라")
    except ValueError:
        pass

    # ── ④ D-2는 필름 계열만 ───────────────────────────────────────────
    assert set(e.U_DESIGN) == {"필름", "불소필름", "단동"}, (
        f"U_DESIGN 키가 {sorted(e.U_DESIGN)}로 바뀌었다 — 유리가 들어오면 "
        "D-2의 적용 범위(필름 계열만)가 달라진다")
    assert "유리" in e.U_VALUE and "유리" not in e.U_DESIGN

    # ── ⑤ 네 항목의 감응 크기 ─────────────────────────────────────────
    ub = hl(um)
    assert round(ub.max_load_kcal_h) == 238776, f"uminjae 기준 최대부하 {ub.max_load_kcal_h}"
    d2 = hl(um, u_design=8.9).max_load_kcal_h
    assert abs(d2 / ub.max_load_kcal_h - 1.561) < 0.002, (
        f"D-2 감응이 {d2 / ub.max_load_kcal_h:.3f}배로 바뀌었다 — 149차 실측 +56.1%")
    assert abs(1.0881 - 1.0881) < 1e-9 and round(ub.max_load_kcal_h * 1.0881) == 259812

    opts = e.cover_assembly_options()
    loads = [hl(um, fr=None, assembly=k).max_load_kcal_h for k in opts]
    span = max(loads) / min(loads)
    assert abs(span - 4.07) < 0.02, (
        f"D-4의 조합 간 최대부하 폭이 {span:.2f}배로 바뀌었다 — 149차 실측 4.07배")
    assert len(opts) == 49, f"조합이 {len(opts)}종이다 — 149차 실측 49종"

    # ── ⑥ 실측 이중검증은 이 변동을 잡지 못한다(기록) ─────────────────
    for load in (base.load_per_m2, base.load_per_m2 * 1.0881,
                 base.load_per_m2 * 1.68):
        v = e.verify_heating_vs_actual(load, wc.cover.value)
        assert v["status"] == "정상", (
            "verify_heating_vs_actual의 띠가 좁아졌다 — 149차는 +68%에서도 '정상'이라 "
            "기록했다. 띠를 좁히는 것은 판정 기준 변경이라 ★사용자 결정이다")

    # ── ⑦ 대장이 정정을 담고 있는가 ───────────────────────────────────
    assert "149차 정정" in led and "얽힘이 아니라 배타" in led, (
        "🔴 대장의 149차 정정 배너가 사라졌다 — D-3 행과 ⓐ 표제가 틀렸다는 발견이다")
    assert "OPEX가 20~33% 움직여 원채원 ROI 14.2%가 직접 깨진다" not in led.replace(
        "「OPEX가 20~33% 움직여 원채원 ROI 14.2%가 직접 깨진다」", ""), (
        "🔴 철회한 D-3 단정이 인용부호 밖에서 되살아났다")
    assert "~~**여전히 미측정: D-5~D-9 · D-13~D-15.**~~" in led, (
        "🔴153차: 149차가 남긴 「여전히 미측정」은 150차에 해소됐으므로 **취소선으로** "
        "남아 있어야 한다 — 종전 이 가드가 낡은 주장을 살아 있는 것으로 고정했다")
    # 🔴 표 **행**에서 직접 본다 — 배너만 보면 행이 되살아나도 통과한다
    #   (149차 뮤테이션 Q6이 그렇게 빠져나갔다)
    d3 = [ln for ln in led.splitlines()
          if ln.lstrip().startswith("| **D-3** |")]
    assert len(d3) == 1, f"대장에 D-3 행이 {len(d3)}개다"
    assert "149차 정정: 깨지지 않는다" in d3[0], (
        "🔴 D-3 행에서 149차 정정이 사라졌다 — `sunshine_k`는 연료소비량만 움직이고 "
        "그 값은 산출물에 도달하지 않는다")
    assert "−16.1~−38.3%" in d3[0], "D-3 행의 149차 전 표 실측 범위가 사라졌다"
    d4 = [ln for ln in led.splitlines() if ln.lstrip().startswith("| **D-4** |")]
    assert len(d4) == 1 and "4.07배" in d4[0] and "배타" in d4[0], (
        "D-4 행에서 149차 실측(4.07배)이나 D-2와의 배타 표기가 사라졌다")

    # ── ⑧ 이 차수가 하지 않은 것 ──────────────────────────────────────
    assert "결정은 하나도 내리지 않았다" in doc
    assert doc.count("시세성") >= 2 and doc.count("연료 **ℓ**까지가 한계다") == 2, (
        "🔴 OPEX 효과를 낼 수 없는 이유(유가=시세성, 연료 ℓ까지가 한계)가 "
        "근거문서에서 줄었다 — §2와 §7 두 곳에 있어야 한다")
    assert "주입만 받는다" in doc, "시세성은 주입만 받는다는 1절 표기가 사라졌다"


def test_150cha_remaining_eight_are_measured():
    """150차 — 나머지 8건(D-5~D-9·D-13~D-15)의 감응을 **측정**했다.

    🔴 **D-5와 D-6은 별개가 아니다**: 케이스 `region`이 기상표 키와 **0/25** 매칭이다
    (표는 관측지점명, 케이스는 행정구역 표기). C3의 *"전부 계산 미연결"*의 실제 원인이
    이것이고, D-6은 그 계열의 **유일한 잔여 불일치**(마산↔창원)다.

    이로써 **D-1~D-15 전부 감응이 붙었다**(145·149·150차). 결정은 여전히 0건이다.
    """
    import os as _o, sys as _s
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import smartfarm_engine as e
    from cases import load_cases, case_to_input

    rd = lambda n: open(_o.path.join(repo, n), encoding="utf-8").read()
    doc = rd("근거_잔여결정8건_감응측정_20260916.md")
    led = rd("근거_결정대기대장_20260915.md")

    # ── D-5 🔴 케이스 지역명이 표에 닿지 않는다 ───────────────────────
    TBL = (e.DESIGN_OUTDOOR_TEMP_TAC, e.HEATING_DEGREE_HOURS_1000,
           e.MONTHLY_SUNSHINE_HOURS, e.MONTHLY_MEAN_WIND_MS, e.REGION_DESIGN_LOAD)
    regs = []
    for c in load_cases():
        try:
            regs.append(case_to_input(c).region)
        except Exception:
            regs.append(None)
    hit = sum(1 for r in regs for d in TBL if r is not None and r in d)
    assert hit == 0, (
        f"케이스 region이 기상표에 {hit}건 매칭된다 — 150차 실측은 0건이다. "
        "정규화가 생겼다면 D-5·D-6의 감응 측정을 다시 하라(잘못 이으면 다른 지점의 "
        "기상값이 조용히 들어온다)")
    # 부분 매칭은 춘천·천안만 이어지고 원채원은 이어지지 않는다
    tac = set(e.DESIGN_OUTDOOR_TEMP_TAC)
    sub = {r: sorted(k for k in tac if k in r) for r in regs if r}
    assert any(v == ["춘천"] for v in sub.values()), "춘천 부분 매칭이 사라졌다"
    assert any(v == ["천안"] for v in sub.values()), "천안 부분 매칭이 사라졌다"
    assert any(r == "충남" and not sub[r] for r in sub), (
        "🔴 원채원의 region이 '충남'(지점 없음)이라는 사실이 바뀌었다 — "
        "S-1(원문 미보유)과 같은 매듭이다")

    # ── D-6 🔴 4개 기상표의 유일한 불일치 ─────────────────────────────
    S = [set(e.DESIGN_OUTDOOR_TEMP_TAC), set(e.HEATING_DEGREE_HOURS_1000),
         set(e.MONTHLY_SUNSHINE_HOURS), set(e.MONTHLY_MEAN_WIND_MS)]
    assert all(len(x) == 69 for x in S), f"기상표 키 수가 {[len(x) for x in S]}로 바뀌었다"
    assert S[0] == S[1] == S[2], "TAC·난방도일·일조의 키가 어긋났다"
    assert S[0] - S[3] == {"창원"} and S[3] - S[0] == {"마산"}, (
        f"🔴 마산↔창원이 4개 기상표의 **유일한** 불일치라는 150차 실측이 깨졌다: "
        f"TAC−풍속={sorted(S[0] - S[3])} 풍속−TAC={sorted(S[3] - S[0])}")

    # ── D-7 재검산 — 대장의 159원은 158원이다 ─────────────────────────
    A = {r[0]: r for r in e.ACTUALS}
    um = A["우민재"]
    assert um[1] == 2323 and um[2] == 557152000
    hi = e.BENCHMARK_BANDS[e.Cover.FILM][1]
    assert hi == 240000
    gap_now = hi - um[2] / 2323
    gap_alt = hi - um[2] / 2321.87
    assert 158.0 <= gap_now < 159.0, f"현행 밴드 여유가 {gap_now:.2f}원이다 — 150차 실측 158.4원"
    assert 41.0 <= gap_alt < 43.0, f"교체 시 여유가 {gap_alt:.2f}원이다 — 실측 약 42원"
    assert "158원 → 42원" in led, (
        "🔴 대장의 D-7 여유가 158원으로 정정된 표기가 사라졌다(종전 159원은 반올림)")

    # ── D-8 · D-13 — 분류 이관의 몫 ───────────────────────────────────
    tot = sum(e.CAPEX_MAJOR_KNOWN_TOTALS.values())
    assert tot == 7918192671, f"known_total 합이 {tot}로 바뀌었다"
    d8 = 18500000 + 25107700
    assert abs(100 * d8 / tot - 0.551) < 0.005, "D-8의 몫(0.551%)이 바뀌었다"
    U = e.CAPEX_MAJOR_UNCLASSIFIED
    assert U["최선동"] == 68035800 and U["임미라"] == 126032300, (
        "D-8 두 건이 담긴 미분류 금액이 바뀌었다 — 이관 감응을 다시 재라")
    assert e.CAPEX_MAJOR_EVIDENCE_STATUS["equipment_procurement"].startswith("미검증"), (
        "🔴 `equipment_procurement`이 더는 미검증이 아니다 — "
        "D-8이 '그 카테고리의 첫 실측'이라는 전제가 깨진다")
    for mark in ("37,226,888", "77,320,088", "1.93배"):
        assert mark in doc, f"D-13 실측에서 {mark}가 사라졌다"

    # ── D-9 — 갈리는 수는 정의의 넓이에 달려 있다 ─────────────────────
    W, TH = e.MONTHLY_MEAN_WIND_MS, e.WIND_STRONG_THRESHOLD_MS
    assert TH == 3.0 and len(next(iter(W.values()))) == 13
    def strong(ms):
        return {r for r, v in W.items()
                if (v[12] if ms is None else sum(v[m - 1] for m in ms) / len(ms)) >= TH}
    multi = [(12, 1, 2), (12, 1, 2, 3), (11, 12, 1, 2), (11, 12, 1, 2, 3),
             (1, 2), (10, 11, 12, 1, 2, 3, 4), None]
    single = [(m,) for m in range(1, 13)]
    def flips(sets):
        ss = [strong(x) for x in sets]
        return set(W) - set.intersection(*ss) - (set(W) - set.union(*ss))
    assert len(flips(multi)) == 5, f"다월 후보의 갈림이 {len(flips(multi))}곳이다 — 실측 5곳"
    f_all = flips(multi + single)
    assert len(f_all) == 11, f"전 후보의 갈림이 {len(f_all)}곳이다 — 실측 11곳"
    assert f_all == {"강릉", "대관령", "대구", "서귀포", "성산", "속초",
                     "영주", "완도", "인천", "추풍령", "포항"}, (
        f"갈리는 지역 명단이 {sorted(f_all)}로 바뀌었다 — 95·96차 대장 명단과 같아야 한다")
    assert e.wind_correction_factor(2.9, False) == 1.0
    assert e.wind_correction_factor(3.0, False) == 1.1
    assert e.wind_correction_factor(3.0, True) == 1.05
    # 🔴 근거문서의 명단도 계산과 함께 고정한다 — 산문만 고치면 안 잡힌다
    #   (150차 뮤테이션 R9가 그렇게 빠져나갔다)
    listed = " · ".join(sorted(f_all))
    assert listed in doc, (
        f"근거문서의 갈림 명단이 계산과 다르다 — 계산은 「{listed}」다. "
        "이름 하나만 바꿔도 잡히도록 **명단 전체 문자열**을 고정한다"
        "(150차 뮤테이션 R9가 개별 이름 검사를 빠져나갔다)")

    # ── D-14 · D-15 — 품셈 쪽 ─────────────────────────────────────────
    tot_c = sum(sum(i.labor_per_unit.values()) for i in e.PUMSEM_ITEMS)
    vin = sum(sum(i.labor_per_unit.values()) for i in e.PUMSEM_ITEMS if "비닐" in i.category)
    assert abs(100 * vin / tot_c - 1.15) < 0.02, (
        f"비닐 7종의 몫이 {100 * vin / tot_c:.2f}%다 — 150차 실측 1.15%")
    assert len([i for i in e.PUMSEM_ITEMS if "비닐" in i.category]) == 7
    gl = [i for i in e.PUMSEM_ITEMS if i.category == "온실피복공사"]
    assert len(gl) == 4, f"온실피복공사(유리)가 {len(gl)}품목이다 — D-15 이견이 걸리는 자리다"
    assert abs(100 * sum(sum(i.labor_per_unit.values()) for i in gl) / tot_c - 0.87) < 0.02
    # 요약표(§0)와 본문(§5) 두 곳에 있어야 한다 — 한 곳만 지워도 잡는다(R8)
    assert doc.count("64품목 전부가") >= 2, (
        f"D-15의 [주] 전수(64/64) 실측이 {doc.count('64품목 전부가')}곳으로 줄었다 — "
        "요약표와 본문 두 곳에 있어야 한다")
    for n in ("천창개폐장치공사 · 수평스크린공사", "각 13"):
        assert n in doc, f"[주] 공종별 집계에서 {n}가 사라졌다"

    # ── 대장이 정정을 담고 있는가 ─────────────────────────────────────
    assert "D-1~D-15 전부 감응이 붙었다" in led, (
        "145·149·150차로 전 항목의 감응이 채워졌다는 표기가 대장에서 사라졌다")
    # 🔴 두 표현을 **둘 다** 본다 — 한쪽만 지우면 부분문자열 검사는 통과한다(R7)
    for phrase in ("D-6과 같은 뿌리", "한 뿌리를 공유", "지역명 정규화", "S-1"):
        assert phrase in led, (
            f"🔴 대장에서 「{phrase}」가 사라졌다 — D-5·D-6이 한 뿌리이고 "
            "원채원은 S-1이 있어야 닿는다는 150차 발견이다")

    # ── 이 차수가 하지 않은 것 ────────────────────────────────────────
    assert "결정은 하나도 내리지 않았다" in doc
    assert "정규화 규칙을 만들지 않았다" in doc, (
        "지역명 정규화가 판단성이라 손대지 않았다는 표기가 사라졌다")


def test_151cha_overhead_refs_and_blind_spot_classes():
    """151차 — 추적성 사각 **7 → 6**. 붙여 보니 단정 하나가 반증됐다.

    🔴 133차 분류가 틀렸다: `OVERHEAD_RATES`를 *"원가계산서 6건 중 일부가 Google
    Drive"*라며 (B) **원문이 리포 밖**으로 넣었는데, **3건은 리포에 실재**한다.
    **부분 부재를 전체 부재로 읽은** 것이다.

    붙이자 등재 서술의 단정이 반증됐다 — *"산재 3.56%·고용 1.01%는 6개 문서 전부
    동일"*이지만 **산재는 세 문서가 셋 다 다르다**(3.56 / 3.7 / 3.764%).
    133차가 경고한 그대로다: *"ref가 0건이면 원문 실재 검사가 한 번도 돌지 않는다"*.

    ⚠️ **요율 값은 바꾸지 않았다** — 법정요율은 시세성 계열이라 ★사용자 결정이다.
    """
    import os as _o, sys as _s, json as _j
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import verify_refs as vr
    import audit_traceability as at

    rd = lambda n: open(_o.path.join(repo, n), encoding="utf-8").read()
    doc = rd("근거_추적성사각_요율대조_20260916.md")

    # ── ① 🔴 값은 하나도 바뀌지 않았다 ────────────────────────────────
    # 엔진은 dict가 아니라 `OverheadRates` 데이터클래스로 들고 있다 —
    #   드리프트 가드가 대조하는 **레지스트리 값**을 본다
    _C0 = vr.load_registry()
    assert _C0["OVERHEAD_RATES"]["value"] == {
        "health": 0.03595, "pension": 0.0475, "industrial_accident": 0.0356,
        "employment": 0.0101, "general_admin": 0.05, "profit": 0.1,
        "safety_mgmt": 0.025}, (
        "🔴 OVERHEAD_RATES 값이 바뀌었다 — 151차는 ref를 붙이고 서술을 고쳤을 뿐이다. "
        "법정요율 교체는 시세성 계열 값 변경이라 ★사용자 결정이다")

    # ── ② refs 3건이 붙었고 원문이 실재하는가 ─────────────────────────
    C = vr.load_registry()
    refs = C["OVERHEAD_RATES"].get("source_refs") or []
    assert len(refs) == 3, f"OVERHEAD_RATES의 refs가 {len(refs)}건이다 — 151차는 3건이다"
    WANT = {"원가계산서_이두희(천안) 20251028.pdf",
            "혁진 스마트팜 온실 신축공사_공사비 내역서.pdf",
            "1. 공사내역서 스마트팜 확대보급 시범사업.xlsx"}
    assert {_o.path.basename(r["file"]) for r in refs} == WANT
    for r in refs:
        p = _o.path.join(repo, r["file"])
        assert _o.path.isfile(p), (
            f"🔴 {r['file']}가 리포에서 사라졌다 — 실재하니까 붙일 수 있었던 ref다")
        assert r["match"] == "partial", (
            "등급이 partial이 아니다 — 문서마다 요율이 달라 등재값은 여러 문서의 "
            "**채택 결과**이지 어느 한 문서의 전사가 아니다")
        assert vr.soft_criteria(r["note"], strict=True) >= {"숫자", "위치"}, (
            f"{_o.path.basename(r['file'])}의 대조 기준이 줄었다")
        assert "151차 대조 기준" in r["note"], (
            f"🔴 {_o.path.basename(r['file'])}의 note가 「대조 기준」 선언을 잃었다 — "
            "「참고」로 낮추면 그 문서에서 무엇을 봐야 하는지가 흐려진다")

    # ── ③ 🔴 반증된 단정이 되살아나지 않는가 ──────────────────────────
    src = C["OVERHEAD_RATES"]["source"]
    assert "151차 정정" in src, "반증 기록이 source에서 사라졌다"
    for tok in ("3.7%", "3.764%", "1.35%"):
        assert tok in src, (
            f"🔴 source에서 반례 요율 {tok}가 사라졌다 — 산재는 이두희 3.56 / "
            "우민재 3.7 / 최혁진 3.764로 셋 다 다르다")
    # 원문의 앵커 금액이 note에 살아 있는가(문서를 다시 찾아갈 수 있어야 한다)
    joined = " ".join(r["note"] for r in refs)
    for amt in ("4,006,431", "1,136,656", "7,369,083", "2,643,002",
                "903,014", "246,498", "14,525,517"):
        assert amt in joined, f"원문 앵커 {amt}가 note에서 사라졌다"

    # ── ④ 사각이 6건이고, 그중 2건은 구조상 0이다 ─────────────────────
    a = at.audit()
    assert a["counts"]["source_refs"] == 154, (
        f"source_refs가 {a['counts']['source_refs']}다 — 163차 실측은 154건"
        "(134차 148 + OVERHEAD_RATES 3 + FR_TABLE 1 + REGION_DESIGN_LOAD 2)")
    # `refless_measured`는 (상수명, status) 쌍을 준다 — 이름만 뽑는다
    blind = {x[0] if isinstance(x, (list, tuple)) else x
             for x in a["refless_measured"]}
    assert len(blind) == 5, f"추적성 사각이 {len(blind)}건이다 — 163차는 5건"
    assert "OVERHEAD_RATES" not in blind, (
        "🔴 OVERHEAD_RATES가 다시 사각으로 돌아갔다 — refs 3건이 지워졌는지 보라")
    STRUCTURAL = {"CAPEX_MAJOR_CATEGORIES", "RFQ_REQUIRED_CATEGORIES_DEFAULT"}
    assert STRUCTURAL <= blind, (
        "파생·결정이라 파일 ref 개념이 없는 2건이 사각 목록에서 사라졌다")
    # 🔴163차 — `REGION_DESIGN_LOAD`가 빠져 4건 → 3건이 됐다(고시 [별표] 사본 확보)
    DATA_BLOCKED = {"SPEC_TABLE", "SPEC_COUNT", "OPEX_ITEM_CATEGORIES"}
    assert DATA_BLOCKED <= blind and blind == STRUCTURAL | DATA_BLOCKED, (
        f"사각 5건의 구성이 {sorted(blind)}로 바뀌었다 — "
        "자료로 풀리는 3건 + 구조상 0인 2건이다")

    # ── ⑤ 리포에 원문이 없다는 것도 재확인된 사실이다 ─────────────────
    assert _o.path.getsize(
        _o.path.join(repo, "소득분석DB",
                     "농촌진흥청_농산물소득분석 조사입력항목코드_20201015.csv")) == 0, (
        "🔴 OPEX CSV가 더는 0바이트가 아니다 — S-3가 들어왔다면 "
        "`OPEX_ITEM_CATEGORIES`에 ref를 붙이고 사각을 6 → 5로 줄여라")

    # ── ⑥ 이 차수가 하지 않은 것 ──────────────────────────────────────
    for mark in ("값은 바꾸지 않았다", "★사용자 결정", "safety_mgmt"):
        assert mark in doc, f"근거문서에서 {mark}가 사라졌다"
    assert "부분 부재를 전체 부재로" in doc, (
        "133차 분류 오류의 성격(부분 부재 → 전체 부재)이 근거문서에서 사라졌다")
    assert "결정은 하나도 내리지 않았다" in doc


def test_152cha_blind_spot_classes_are_declared_not_guessed():
    """152차 — 추적성 사각 6건을 감사기가 **분류**한다: 자료로 풀리는 4 / 구조상 0인 2.

    🔴 분류 근거를 **어디에 두느냐**가 이 차수의 설계다.
      ①감사기에 상수명 하드코딩 → 지식이 두 곳으로 갈라진다
      ②`source` 서술 파싱 → 141차 교훈(*"파서를 쓰지 말았어야 했다"*)의 반복
      ③**레지스트리에 `ref_basis` 명시 선언** ← 채택
    선언에는 불변식이 따라붙는다 — 범례 안의 값이어야 하고 `source_refs`와
    **공존할 수 없다**(파일 ref를 붙였다면 그 선언이 틀린 것이다).
    """
    import os as _o, sys as _s, json as _j, copy as _c
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import audit_traceability as at

    rd = lambda n: open(_o.path.join(repo, n), encoding="utf-8").read()
    reg = _j.loads(rd("엔진데이터_레지스트리.json"))

    # ── ① 선언이 레지스트리에 있고 범례가 있다 ────────────────────────
    legend = reg.get("ref_basis_legend")
    assert legend and set(legend) == {"결정", "파생"}, (
        f"ref_basis_legend가 {sorted(legend or [])}로 바뀌었다 — 152차는 결정·파생 둘이다")
    declared = {k: v["ref_basis"] for k, v in reg["constants"].items() if "ref_basis" in v}
    assert declared == {"CAPEX_MAJOR_CATEGORIES": "결정",
                        "RFQ_REQUIRED_CATEGORIES_DEFAULT": "파생"}, (
        f"ref_basis 선언이 {declared}로 바뀌었다 — 152차 실측은 2건이다. "
        "새 상수에 붙였다면 근거문서와 이 수를 함께 갱신하라")

    # ── ② 🔴 분류가 **선언에서** 오는가 — 하드코딩이 아닌가 ───────────
    src = rd("audit_traceability.py")
    # 분류 **블록** 안만 본다 — `CAPEX_MAJOR_CATEGORIES`는 :116에서 견적 키 검증용
    #   엔진 속성으로 정당하게 쓰인다(전체 파일 검사는 그 정당한 사용까지 잡는다)
    i = src.index('legend = reg.get("ref_basis_legend")')
    j = src.index('"refless_structural": structural}')
    block = src[i:j]
    for name in declared:
        assert name not in block, (
            f"🔴 분류 블록이 상수명 「{name}」을 직접 들고 있다 — 분류 근거는 "
            "레지스트리 `ref_basis` 선언 한 곳에만 있어야 한다(두 곳에 두면 갈라진다)")
    assert 'ent.get("ref_basis")' in block and 'get("ref_basis")' in src, (
        "감사기가 선언을 읽지 않는다")

    # ── ③ 분류 결과 ───────────────────────────────────────────────────
    a = at.audit()
    blocked = {k for k, _s0, _b in a["refless_blocked"]}
    structural = {k for k, _s0, _b in a["refless_structural"]}
    assert structural == set(declared), (
        f"구조상 0인 집합이 {sorted(structural)}로 바뀌었다 — 선언과 같아야 한다")
    assert blocked == {"SPEC_TABLE", "SPEC_COUNT", "OPEX_ITEM_CATEGORIES"}, (
        f"자료로 풀리는 집합이 {sorted(blocked)}로 바뀌었다 — 🔴163차에 "
        "`REGION_DESIGN_LOAD`가 풀려 4건 → **3건**이다")
    total = {k for k, _s0 in a["refless_measured"]}
    assert total == blocked | structural and len(total) == 5, (
        "분류 합이 사각 전체와 다르다 — 빠지거나 겹친 항목이 있다")

    # ── ④ 🔴 불변식이 **실제로 도는가**(139차 red self-test와 같은 이유) ──
    #    위반이 0건이면 검사가 도는지 결과로 구별되지 않는다
    base = at.audit_registry(reg)
    assert not [h for h in base["hard"] if "ref_basis" in h[1]], (
        "현재 레지스트리에 ref_basis 불변식 위반이 있다")
    r1 = _c.deepcopy(reg)
    r1["constants"]["SPEC_COUNT"]["ref_basis"] = "추측"
    assert [h for h in at.audit_registry(r1)["hard"] if "ref_basis_legend에 없다" in h[1]], (
        "🔴 범례 밖 ref_basis 값을 감사기가 잡지 못한다 — 선언이 무의미해진다")
    r2 = _c.deepcopy(reg)
    r2["constants"]["ACTUALS_COUNT"]["ref_basis"] = "파생"
    assert [h for h in at.audit_registry(r2)["hard"] if "함께 있다" in h[1]], (
        "🔴 `ref_basis`와 `source_refs`의 공존을 감사기가 잡지 못한다 — "
        "파일 ref를 붙이고도 '구조상 0'이라 우기는 상태가 통과한다")

    # ── ⑤ 리포트가 두 절로 갈렸는가 ───────────────────────────────────
    rep = at.render_report(a)
    assert "### (가) 원문이 리포에 없어 못 붙인다" in rep
    assert "### (나) 파일 ref 개념이 성립하지 않는다" in rep
    # 🔴163차 — `REGION_DESIGN_LOAD`가 풀려 (가)4→3 · 총6→5가 됐다
    assert "**실제 백로그는 (가) 3건**이다(총 5건 중)" in rep, (
        "🔴 실제 백로그가 3건이라는 결론이 리포트에서 사라졌다 — "
        "151차 발견은 '영원히 0인 수를 백로그처럼 끌고 다니지 말라'였다")
    assert "`결정`" in rep and "`파생`" in rep, "분류 사유가 리포트에 인쇄되지 않는다"

    # ── ⑥ 🔴 게이트 순서 교훈 — 낡은 산출물로 통과하지 않게 ───────────
    doc = rd("근거_사각분류_코드화_20260916.md")
    assert "build_site → pytest" in doc, (
        "🔴 게이트 순서(build_site를 pytest **앞에**)가 근거문서에서 사라졌다 — "
        "151차에 실제로 낡은 HTML로 배지 가드가 통과했다")
    ledger = rd("SmartFarm_근거대장.html")
    assert ledger.count("[부분]") == 55, (
        f"근거대장 [부분] 배지가 {ledger.count('[부분]')}다 — build_site를 먼저 돌렸는지 보라")

    # ── ⑦ 이 차수가 하지 않은 것 ──────────────────────────────────────
    assert "값 변경 0" in doc and "결정은 하나도 내리지 않았다" in doc


def test_154cha_plan_coverage_claims_hold():
    """154차 — 작업계획서(2026-07-16) 대비 최종 정리의 **구조적 주장**을 고정한다.

    ⚠️ **수치는 고정하지 않는다.** 상수 54·refs 151·근거문서 58 같은 값은
    작업이 이어지면 **설계상 움직인다** — 그것을 가드에 박으면 매 차수 갱신만
    강요하고 아무것도 지키지 못한다. 대신 **바뀌면 정리가 틀리는 것**만 본다:
    계획서가 말한 함수가 실재하는가 · 4섹션 리포트가 살아 있는가 ·
    P3 미착수와 스냅샷 시점이 정직하게 적혀 있는가.
    """
    import os as _o, sys as _s, glob as _g
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import smartfarm_engine as e

    rd = lambda n: open(_o.path.join(repo, n), encoding="utf-8").read()
    doc = rd("최종개발내용_작업계획서대비_20260919.md")
    plan = rd("작업계획_컨설팅모델_입지설계운영경제성.md")

    # ── ① 계획서가 신규로 요구한 함수가 실재하는가(P1-a · P1-b) ───────
    for fn, why in (("siting_lookup", "P1-a 지명 → 설계하중"),
                    ("siting_design_load", "P1-a 결정론 부분"),
                    ("opex_breakdown", "P1-b OPEX 항목 분해")):
        assert callable(getattr(e, fn, None)), (
            f"🔴 계획서 {why}의 `{fn}()`이 사라졌다 — 정리의 '완료' 표기가 거짓이 된다")
    # 계획서가 "그대로 사용"이라 적은 기존 함수들
    for fn in ("select_specs", "heating_load", "verify_heating_vs_actual",
               "production_kg", "finance", "improvement_roi", "cluster_economics",
               "greenhouse_total_estimate", "npv", "irr"):
        assert callable(getattr(e, fn, None)), (
            f"🔴 계획서가 '그대로 사용'이라 적은 `{fn}()`이 사라졌다")

    # ── ② P0-b · P0-d의 데이터가 실재하는가 ───────────────────────────
    assert len(e.REGION_DESIGN_LOAD) >= 172, (
        f"REGION_DESIGN_LOAD가 {len(e.REGION_DESIGN_LOAD)}지역이다 — "
        "P0-b는 2025-108호 172지역으로 닫혔다. 줄었다면 정리를 다시 쓰라")
    assert len(e.OPEX_ITEM_CATEGORIES) >= 25, "P0-d의 OPEX 항목이 줄었다"

    # ── ③ P2 — 통합 리포트가 계획서 6절 4섹션 구조인가 ────────────────
    reports = _g.glob(_o.path.join(repo, "SmartFarm_통합보고서_*.html"))
    assert reports, "🔴 통합보고서가 하나도 없다 — P2 '완료' 표기가 거짓이 된다"
    h = open(reports[0], encoding="utf-8").read()
    for sec in ("입지진단서", "설계적정성보고서", "운영계획서", "경제성분석서"):
        assert sec in h, (
            f"🔴 통합보고서에서 「{sec}」 섹션이 사라졌다 — "
            "계획서 6절이 요구한 4섹션 구조다")

    # ── ④ 🔴 정리가 **정직한가** — 미착수·부분을 부분이라 적었는가 ────
    assert "❌ **미착수**" in doc, (
        "P3(설명 계층) 미착수 표기가 사라졌다 — 계획서의 마지막 단계다")
    assert "입력·재생성 계층" in doc, (
        "`webapp.py`가 설명 계층이 아니라 입력 계층이라는 구분이 사라졌다 — "
        "이걸 흐리면 P3를 완료로 읽게 된다")
    for partial in ("P0-a", "P0-c"):
        assert partial in doc, f"{partial} 항목이 정리에서 사라졌다"
    assert "원문서는 끝내 미확보" in doc, (
        "🔴 P0-a(`U_VALUE`·`FR_TABLE`)의 원문 미확보가 「완료」로 둔갑했다 — "
        "계획서가 *'다른 모든 작업보다 우선'*이라 적은 항목이다")

    # ── ⑤ 스냅샷 시점과 미반영 사실이 적혀 있는가 ─────────────────────
    assert "fd2c116" in doc and "152차) 시점이다" in doc, (
        "🔴 이 정리가 어느 커밋 시점의 수치인지가 사라졌다 — "
        "수치는 계속 움직이므로 시점 없이는 검증할 수 없다")
    assert "153차" in doc and "별도 차수" in doc, (
        "레드팀 28회차 결과가 이 문서에 반영되지 않았다는 표기가 사라졌다")

    # ── ⑥ 계획서 원문이 그대로 있는가(대조 기준이다) ──────────────────
    for mark in ("P0-a", "P1-a", "siting_lookup", "opex_breakdown",
                 "1. 입지진단서", "4. 경제성분석서"):
        assert mark in plan, (
            f"🔴 작업계획서에서 「{mark}」가 사라졌다 — 이 정리의 **대조 기준**이다")

    # ── ⑦ 결정·값을 건드리지 않았다 ───────────────────────────────────
    assert "결정은 하나도 내리지 않았다" in doc
    assert "정리만 했다" in doc, "이 차수가 정리뿐이라는 표기가 사라졌다"


def test_153cha_redteam28_corrections_hold():
    """153차 — 레드팀 28회차 발견 11건. **거짓 양성 0건**(27회차는 5건이었다).

    🔴 재검증에서 **레드팀보다 나쁜 것**이 나왔다 — [7]을 *"제어문자 1곳"*(중)이라
    했으나 실제로는 **4곳**이고 그중 2곳이 `verify_refs._LOC`의 **살아 있는 정규식**
    안이었다. `\\b`가 백스페이스로 변환돼 박히는 바람에 **엑셀 셀 참조·「행」·「열」
    세 분기가 죽어** soft ref 61건 중 **21건**의 위치 판정이 과소 인식됐다.
    146차 `_ROUND` · 148차 `NUM`에 이은 **같은 버그의 세 번째**다.

    발견의 공통 성격: **연쇄 정정이 한 곳만 반영된 자리**([1]·[2]·[3]·[5]).
    """
    import os as _o, sys as _s, re as _re, glob as _g
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import verify_refs as vr
    import build_site as bsmod

    rd = lambda n: open(_o.path.join(repo, n), encoding="utf-8").read()
    led = rd("근거_결정대기대장_20260915.md")

    # ── [7] 🔴 저장소 전체에 제어문자가 없는가 ────────────────────────
    CTRL = _re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
    dirty = []
    for pat in ("*.py", "*.md", "*.json"):
        for f in _g.glob(_o.path.join(repo, pat)):
            for i, ln in enumerate(open(f, encoding="utf-8", errors="replace"), 1):
                if CTRL.search(ln):
                    dirty.append(f"{_o.path.basename(f)}:{i}")
    assert not dirty, (
        f"🔴 제어문자가 들어왔다: {dirty[:5]} — 파이썬 문자열에 `\\b`를 쓰면 "
        "**백스페이스로 변환**된다. 146·148·153차에 세 번 밟았다. "
        "정규식은 리터럴이 아니라 `.pattern`을 눈으로 확인하라")

    # `_LOC`의 세 분기가 **실제로 산다**
    assert chr(8) not in vr._LOC.pattern
    for probe in ("내역서 3행", "5열 참조", "집계표 E276"):
        assert vr._LOC.search(probe), (
            f"🔴 `_LOC`가 「{probe}」를 위치로 인식하지 못한다 — "
            "셀 참조·행·열 분기가 다시 죽었다")

    # ── [1] D-7은 158원이다 — 한 파일 안에서 갈리지 않는가 ────────────
    exact = 240000 - 557152000 / 2323
    assert 158.0 <= exact < 159.0, exact
    rows = [ln for ln in led.splitlines() if ln.lstrip().startswith("| **D-7** |")]
    assert len(rows) == 2, f"대장의 D-7 행이 {len(rows)}개다(§2·§4 두 곳)"
    for r in rows:
        assert "158원 → 42원" in r, (
            "🔴 대장의 D-7 행이 158원으로 통일돼 있지 않다 — 150차 정정이 §2에만 "
            "반영돼 §4가 159원으로 남아 있었다(레드팀 28회차 [1])")
        assert "159원 → 42원" not in r

    # ── [2] 「여전히 미측정」이 취소선으로 닫혔는가 ────────────────────
    assert "~~**여전히 미측정: D-5~D-9 · D-13~D-15.**~~" in led, (
        "149차가 남긴 「여전히 미측정」이 150차 뒤에도 살아 있으면 안 된다")
    assert "D-1~D-15 전부 감응이 붙었다" in led

    # ── [3] 「그대로 렌더된다」가 정정됐는가 ──────────────────────────
    reg = rd("엔진데이터_레지스트리.json")
    assert reg.count("「그대로 렌더된다」는 148차에 거짓이 됐다") == 6, (
        "🔴 147차 note 6건의 정정이 사라졌다 — 148차가 `md()`를 넣어 "
        "「해석하지 않는다」가 거짓이 됐는데 note·HTML이 그대로였다")

    # ── [4] 취소선이 태그로 렌더되는가 ────────────────────────────────
    md = bsmod.md
    assert md("~~26~~ 22품목") == "<s>26</s> 22품목", (
        "🔴 `~~취소선~~`이 리터럴로 남는다 — 철회된 단정이 평문으로 인쇄되고 "
        "「26 22품목」으로 읽힌다")
    assert md("~~**굵은 취소**~~") == "<s><b>굵은 취소</b></s>"
    assert md("짝 없는 ~~ 하나") == "짝 없는 ~~ 하나", "깨진 HTML을 만들면 안 된다"
    ledger_html = rd("SmartFarm_근거대장.html")
    assert ledger_html.count("~~") == 0 and ledger_html.count("<s>") >= 2, (
        f"근거대장의 리터럴 `~~`가 {ledger_html.count('~~')}개다 — 0이어야 한다")

    # ── [11] md_cut이 세 표지를 모두 재균형하는가 ─────────────────────
    for mark in ("**", "~~", "`"):
        cut = bsmod.md_cut("가" * 150 + " " + mark + "잘릴 표지", 160)
        assert mark not in cut, f"자른 뒤 `{mark}`가 리터럴로 남는다"

    # ── [5] 기준선 라벨 · [8] 호출 수 · [9] 분모 · [10] 단위 ──────────
    d148 = rd("근거_마크다운렌더_면적앵커_20260916.md")
    assert "146차) **3,845**" in d148 and "147차) **3,833**" in d148, (
        "🔴 「3,833」이 146차 값이 아니라 **147차 후** 값이라는 정정이 사라졌다")
    assert "23곳" in d148, "md 호출 실측(23곳)이 사라졌다 — 148차는 17이라 적었다"
    d150 = rd("근거_잔여결정8건_감응측정_20260916.md")
    assert "**매칭 0 / 15.**" in d150 and "0 / 25" not in d150.replace("「0/25」", ""), (
        "🔴 분모 정정(25 → 15)이 사라졌다 — region 필드가 **없는** 부분케이스 2건을 "
        "불일치로 세고 있었다")
    wi = rd("작업지시서.md")
    assert "93m × 44m = 4,092㎡" in wi, (
        "헤더의 면적식이 mm×mm로 돌아갔다 — 93,000×44,000은 4,092가 아니다")

    # ── [6] safety_mgmt — 2.5%는 세 문서 어디에도 없다 ────────────────
    d151 = rd("근거_추적성사각_요율대조_20260916.md")
    for rate in ("2.07%", "2.93%", "1.86%"):
        assert rate in d151, f"🔴 안전관리비 실측 {rate}가 사라졌다"
    assert "등재 2.5%는 어디에도 없다" in d151, (
        "🔴 등재 `safety_mgmt` 2.5%가 세 원문 어디에도 인쇄돼 있지 않다는 "
        "153차 확인이 사라졌다 — 151차가 반증한 「전부 동일」과 같은 계열이다")
    assert "2.07%" in reg and "1.86%" in reg, "레지스트리 source에 실측 요율이 없다"

    # ── 값은 바꾸지 않았다 ────────────────────────────────────────────
    C = vr.load_registry()
    assert C["OVERHEAD_RATES"]["value"]["safety_mgmt"] == 0.025, (
        "🔴 `safety_mgmt` 값이 바뀌었다 — 153차는 **기록만** 했다. "
        "법정요율 교체는 ★사용자 결정이다")


def test_155cha_span_measurement_is_reproducible():
    """155차 — 148차의 스팬 실측치를 **재현 가능하게** 만들었다.

    레드팀 28회차가 *"코퍼스 범위를 적지 않아 정확 재현 불가"*로 「확인 불가」에
    넣은 항목이다. 세는 규칙이 없으면 그 수는 **영원히 검산되지 않는다** —
    131차 이래 반복된 교훈이고, 140차 `soft_check` 0건도 같은 자리에서 틀렸다.

    🔴 재현하는 과정에서 결함이 하나 더 나왔다: *"130(그중 23)"*은
    **두 정규식의 수를 한 문장에 붙인 것**이다(130은 인용 상한 80, 23은 120).
    """
    import os as _o, sys as _s
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import measure_spans as ms

    doc = open(_o.path.join(repo, "근거_마크다운렌더_면적앵커_20260916.md"),
               encoding="utf-8").read()

    # ── ① 148차 기준선이 **한 줄로** 재현되는가 ───────────────────────
    r = ms.measure()          # 기본값 = --rev 099e461 --quote-max 80
    assert r["rev"] == "099e461" and r["quote_max"] == 80, (
        "기본값이 148차 기준선(147차 커밋 · 인용 상한 80)이 아니다 — "
        "기본으로 재현되지 않으면 도구의 의미가 준다")
    for k, want in (("strings", 2731), ("chars", 209110), ("bold", 1887),
                    ("code", 443), ("quote", 130)):
        assert r[k] == want, (
            f"🔴 148차 기준선 {k}가 {r[k]}다 — 기록은 {want}. "
            "코퍼스·시점·정규식 중 하나가 바뀌었다")

    # 🔴 판정 근거가 된 넷은 인용 상한과 무관해야 한다
    r120 = ms.measure(quote_max=120)
    for k in ("bold", "bold_inner_star", "bold_multiline", "bold_longest",
              "odd_bold_strings", "code", "strings", "chars"):
        assert r[k] == r120[k], (
            f"{k}가 인용 상한에 따라 달라진다({r[k]} vs {r120[k]}) — "
            "그러면 md() 설계 근거가 흔들린다")
    assert (r["bold_inner_star"], r["bold_multiline"],
            r["bold_longest"], r["odd_bold_strings"]) == (1, 0, 85, 0), (
        "md() 설계를 정한 네 값(내부 단일별표 1 · 줄바꿈 0 · 최장 85 · 홀수 0)이 바뀌었다")

    # ── ② 🔴 섞인 수가 정정됐는가 ─────────────────────────────────────
    assert r["quote_nested"] == 17 and r120["quote_nested"] == 23, (
        f"중첩이 상한80 {r['quote_nested']} / 상한120 {r120['quote_nested']}다 — "
        "155차 실측은 17 / 23이다. 148차는 **130(상한80)과 23(상한120)을 붙여** 적었다")
    assert "17은 안에 굵게를 품는다" in doc, (
        "🔴 중첩 수를 상한 80으로 통일한 정정이 사라졌다")
    assert "두 정규식의 수를 한 문장에 붙인 것" in doc

    # ── ③ 코퍼스 정의가 문서와 도구에서 같은가 ────────────────────────
    src = open(_o.path.join(repo, "measure_spans.py"), encoding="utf-8").read()
    assert "CAPEX_MAJOR_EVIDENCE_STATUS" in src and "이중계수" in doc, (
        "엔진 `CAPEX_MAJOR_EVIDENCE_STATUS`를 더하면 **레지스트리에 이미 있는 값을 "
        "두 번 센다**는 경고가 사라졌다 — 레드팀이 그렇게 재서 1,940이 나왔다")
    for mark in ("099e461", "인용 상한", "measure_spans.py", "모든 문자열 값"):
        assert mark in doc, f"근거문서에서 {mark}가 사라졌다"

    # 실제로 이중계수가 수를 바꾸는지 — 경고가 빈말이 아님을 보인다
    import json as _j
    reg = ms.load("099e461")
    dup = ms.strings_of(reg) + list(reg["constants"]["CAPEX_MAJOR_EVIDENCE_STATUS"]["value"].values())
    assert len(dup) > r["strings"], "이중계수 경고를 시험할 수 없다"

    # ── ④ 작업 트리도 잴 수 있는가(시점을 바꿔도 도구가 산다) ─────────
    w = ms.measure(rev="WORKTREE")
    assert w["strings"] >= r["strings"] and w["odd_bold_strings"] == 0, (
        "작업 트리의 `**` 짝이 깨졌다 — md()가 리터럴을 남기게 된다")


def test_156cha_dimension_count_rule_is_explicit():
    """156차 — 「치수 표기 21곳」의 세는 단위를 밝혔다. 레드팀 28회차 「확인 불가」 마지막.

    🔴 **「21곳」은 「곳」이 아니었다.** 148차가 쓴 규칙은 연결 문자열 위의
    `\\d\\*\\d` **출현 횟수**이고, `ㅁ60*60*2.3T` 하나가 `0*6`·`0*2`로 두 번 잡힌다.
    단위를 갈라 세면 출현 **21** · 토큰 **17** · 서로 다른 토큰 **8** · 담은 문자열 **4**.
    131차 *"문자열 수는 항목 수가 아니다"*의 재발이고 150차 「0/25」와 같은 계열이다.

    그리고 *"규격이 깨진다"*의 **메커니즘**을 적었다 — 단일 별표 하나로는 이탤릭이
    성립하지 않는다. 실제 파손은 **한 문자열 안의 두 치수 토큰이 서로 짝지어져**
    사이 전체를 이탤릭으로 만들고 **별표 2개를 삼키는** 것이다.
    """
    import os as _o, re as _re, sys as _s
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import measure_spans as ms
    import build_site as bsmod

    doc = open(_o.path.join(repo, "근거_마크다운렌더_면적앵커_20260916.md"),
               encoding="utf-8").read()
    r = ms.measure()          # 148차 기준선

    # ── ① 네 수가 **따로** 나오는가 ───────────────────────────────────
    for k, want in (("dim_star_hits", 21), ("dim_tokens", 17),
                    ("dim_tokens_distinct", 8), ("dim_carrier_strings", 4),
                    ("dim_single_stars", 22)):
        assert r[k] == want, (
            f"🔴 {k}가 {r[k]}다 — 156차 실측은 {want}. 치수 계수 규칙이 바뀌었다")
    assert r["dim_star_hits"] > r["dim_tokens"] > r["dim_tokens_distinct"] > r["dim_carrier_strings"], (
        "네 수의 대소 관계가 깨졌다 — 이 관계가 바로 「21은 곳이 아니다」의 근거다")

    # 148차가 적은 21은 **출현 횟수**와만 같아야 한다
    assert r["dim_star_hits"] == 21 and r["dim_carrier_strings"] != 21

    # ── ② 문서가 단위를 갈라 적었는가 ─────────────────────────────────
    assert "「21곳」은 「곳」이 아니었다" in doc
    for mark in ("출현 횟수", "**17**", "**8**", "**4**", "measure_spans.py"):
        assert mark in doc, f"🔴 치수 계수표에서 {mark}가 사라졌다"
    assert "131차" in doc and "150차 「0/25」와 같은 계열" in doc, (
        "이 결함이 131차 자기부풀림·150차 분모와 **같은 계열**이라는 진단이 사라졌다")

    # ── ③ 🔴 파손 메커니즘이 적혀 있고 사실인가 ───────────────────────
    assert "두 치수 토큰이 서로 짝지어지는 것" in doc, (
        "🔴 *「규격이 깨진다」*의 메커니즘이 사라졌다 — 단일 별표 하나로는 "
        "이탤릭이 성립하지 않으므로, 그 설명 없이는 주장이 검증되지 않는다")
    # 실제로 그렇게 깨지는지 보인다
    vals = ms.strings_of(ms.load(ms.BASELINE_REV))
    carriers = [v for v in vals if ms.DIM_STAR.search(v)]
    assert len(carriers) == 4
    # 🔴 파손은 **결과로** 확인한다 — 매칭 문자열 안에서 `\d\*\d`를 찾으면 0이다
    #   (매칭이 별표 **사이**를 잡으므로 양끝 별표는 그룹 밖이다). 일반 이탤릭을
    #   실제로 적용해 **규격 토큰이 살아남는지**를 본다.
    GEN = _re.compile(r"\*(.+?)\*")
    broke = 0
    for v in carriers:
        specs = {m.group().strip() for m in ms.DIM_TOKEN.finditer(v) if "*" in m.group()}
        after = GEN.sub(lambda m: "<i>%s</i>" % m.group(1), v)
        lost = [t for t in specs if t not in after]
        if lost and after.count("*") < v.count("*"):
            broke += 1
    assert broke >= 2, (
        "🔴 일반 이탤릭이 치수 규격을 파괴하는 것을 재현하지 못했다 — "
        "그러면 *「일반 이탤릭을 지원하지 않는다」*는 결정의 근거가 사라진다")

    # ── ④ 현행 md()는 별표를 **보존**하는가 ───────────────────────────
    for v in carriers:
        seg = v[:400]
        assert seg.count("*") == bsmod.md(seg).count("*"), (
            "🔴 md()가 치수 표기의 별표를 삼킨다 — 규격이 깨진다")
    assert bsmod.md("ㅁ60*60*2.3T") == "ㅁ60*60*2.3T"
    assert bsmod.md("Ø31.8*1.7T@3000") == "Ø31.8*1.7T@3000"

    # ── ⑤ 레드팀 「확인 불가」 3건의 현재 상태 ────────────────────────
    rt = open(_o.path.join(repo, "검증절차_레드팀.md"), encoding="utf-8").read()
    assert "148차 §1 스팬 실측치" in rt and "「치수 표기 21곳」" in rt, (
        "28회차의 「확인 불가」 목록이 사라졌다 — 무엇이 닫혔는지 셀 수 없게 된다")
    # 🔴 목록이 있는 것만으로는 부족하다 — **해소 표기**까지 본다(뮤테이션 X8)
    assert "✅**155차 해소**" in rt and "✅**156차 해소**" in rt, (
        "🔴 28회차 「확인 불가」 2건의 해소 표기가 사라졌다 — "
        "닫힌 것을 닫혔다고 적지 않으면 영원히 백로그로 남는다(152차 교훈)")
    assert "확인 불가 3건 중 2건이 155·156차에 닫혔다" in rt
    assert "❌**미해소**(사용자만 가능)" in rt, (
        "남은 1건(Google Drive 3문서)이 **리포 밖이라 사용자만 풀 수 있다**는 "
        "표기가 사라졌다 — 내가 못 하는 것을 못 한다고 적는 자리다")


def test_157cha_d4_scope_and_source_match():
    """157차 — D-4의 **적용 범위**와 **성격**을 확정했다. 결정은 내리지 않았다.

    🔴 149차가 D-4를 유리 케이스에 과적용했다: `COVER_ASSEMBLIES` 49종에
    **유리 조합이 0건**인데 필름 조합을 유리에 강제 주입해 *"유리 케이스에도
    적용된다"*고 적었다. 같은 차수에서 D-2에 대해 *"필름 계열만"*이라고
    **자기 정정까지 하고도** 바로 옆 항목에서 같은 오류를 반복했다.

    🔴 그리고 *"어느 조합인가"*는 **판단이 아니라 원문 조회**였다 — 우민재
    공사설명서가 「PO필름 0.15T(외피)/0.1T(내피)」라 명시하고 표11에 그 조합이 있다.

    ⚠️ **채택 여부는 여전히 ★사용자 결정**이다. 이 가드는 사실만 고정한다.
    """
    import os as _o, sys as _s, json as _j, glob as _g
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import smartfarm_engine as e

    rd = lambda n: open(_o.path.join(repo, n), encoding="utf-8").read()
    doc = rd("근거_D4적용범위_원문일치_20260920.md")

    # ── ① 🔴 조합표에 유리가 없다 — D-4의 적용 범위를 정하는 사실 ────
    A = e.COVER_ASSEMBLIES
    assert len(A) == 49
    glassy = [a for a in A if any("유리" in L for L in a.layers)]
    assert not glassy, (
        f"🔴 조합표에 유리 조합이 생겼다: {[a.layers for a in glassy][:3]} — "
        "149차의 '유리 케이스에도 적용된다'가 과적용이라는 157차 정정을 다시 보라")
    tables = {}
    for a in A:
        tables.setdefault(a.table, set()).add(len(a.layers))
    assert tables == {"표9": {1}, "표10": {1}, "표11": {2}}, (
        f"조합표의 층수 구성이 {tables}로 바뀌었다 — 표11이 **2층 전용**이라는 것이 "
        "우민재 원문(외피+내피)과 맞물리는 근거다")

    # D-2도 유리는 대상이 아니다(149차가 자기 정정한 사실)
    assert "유리" not in e.U_DESIGN and "유리" in e.U_VALUE

    # ── ② 닿는 완전 케이스는 uminjae 하나 ────────────────────────────
    film_full = []
    for f in sorted(_g.glob(_o.path.join(repo, "cases", "*.json"))):
        try:
            c = _j.loads(open(f, encoding="utf-8").read())
        except Exception:
            continue                      # 0바이트 tombstone
        inp = c.get("input") or {}
        if inp.get("cover") in e.U_DESIGN and inp.get("surface_area_m2") and inp.get("fr"):
            film_full.append(c["case_id"])
    assert film_full == ["uminjae"], (
        f"D-2·D-4가 닿는 완전 케이스가 {film_full}로 바뀌었다 — 157차 실측은 uminjae 하나다")

    # ── ③ 🔴 원문이 지정한 조합이 표에 있다 ──────────────────────────
    KEY = ("po-0.15", "po-0.10")
    a = e.cover_assembly_lookup(KEY)
    assert a is not None and a.table == "표11" and len(a.layers) == 2, (
        "🔴 우민재 원문(PO 0.15 외피 / PO 0.1 내피)에 대응하는 2층 조합이 사라졌다 — "
        "D-4가 '원문 조회'라는 157차 결론의 근거다")
    assert abs(a.coef_kcal - 2.5) < 1e-9 and abs(a.savings_pct - 56.0) < 1e-9
    # 케이스 provenance가 그 원문을 인용하고 있는가
    um = _j.loads(rd(_o.path.join("cases", "uminjae.json")))
    prov = um["provenance"]["cover"]["source"]
    assert "PO필름 0.15T(외피)" in prov and "0.1T(내피)" in prov, (
        "🔴 우민재 cover provenance에서 원문 피복 사양이 사라졌다")
    assert "근거가" in um["provenance"]["fr"]["source"] or "미확보" in um["provenance"]["fr"]["source"], (
        "fr=0.70의 근거 부재 기록이 사라졌다 — D-4 채택 시 제거되는 것이 이것이다")

    # ── ④ 감응(사실) ─────────────────────────────────────────────────
    inp = um["input"]

    def H(**kw):
        fr = kw.pop("fr", inp["fr"])
        return e.heating_load(inp["surface_area_m2"], inp["cover"], inp["t_target"],
                              inp["t_min"], fr, floor_area_m2=inp["area_m2"], **kw)

    base = H().max_load_kcal_h
    d4 = H(fr=None, assembly=KEY).max_load_kcal_h
    assert round(base) == 238776 and round(d4) == 149609, (base, d4)
    assert abs(d4 / base - 0.627) < 0.002, "D-4 감응이 −37.3%에서 바뀌었다"
    assert abs(H(u_design=8.9).max_load_kcal_h / base - 1.561) < 0.002

    # 조합과 fr은 **배타**다 — 82차 ★결정으로 신설된 구조
    try:
        H(fr=None, assembly=KEY, u_design=8.9)
        raise AssertionError("assembly와 u_design의 배타가 깨졌다")
    except ValueError:
        pass

    # ── ⑤ 부수 — 케이스 주입 설계하중이 표와 일치하는가 ──────────────
    #    D-5를 결정해도 값이 안 바뀐다는 근거다. 어긋나면 여기서 잡힌다.
    for cid, sub, snow, wind in (("chuncheon", "춘천", 32, 34),
                                 ("uminjae", "천안", 26, 28)):
        c = _j.loads(rd(_o.path.join("cases", cid + ".json")))["input"]
        t = e.REGION_DESIGN_LOAD[sub]
        assert (c["snow_cm"], c["wind_ms"]) == (snow, wind) == (t["snow_cm"], t["wind_ms"]), (
            f"🔴 {cid}의 주입 설계하중이 표({sub})와 어긋난다 — "
            "157차 실측은 일치였고, 그 일치가 D-5 결정의 감응을 0으로 만든다")
    wc = _j.loads(rd(_o.path.join("cases", "wonchaewon.json")))["input"]
    assert e.siting_design_load(wc["region"]) is None, (
        "원채원 region이 표에 닿기 시작했다 — 그러면 주입값 30·35를 표와 대조하라(S-1)")

    # ── ⑥ 결정하지 않았다 ────────────────────────────────────────────
    assert "결정 0" in doc and "이 차수가 **하지 않은 것** — 결정" in doc
    # 🔴 149차 문서가 **정정 배너**를 달고 있는가 — 틀린 측정이 배너 없이 남으면
    #   다음에 그것을 인용한다(뮤테이션 Y5가 그렇게 빠져나갔다)
    d149 = rd("근거_얽힘4건_감응측정_20260916.md")
    assert "157차 정정 — 아래 「유리 케이스에도 적용된다」는 과적용이다" in d149, (
        "🔴 149차의 D-4 과적용에 정정 배너가 없다 — 유리 케이스 4.07배 표가 "
        "그대로 인용될 수 있다")
    assert "유리 조합은 0건" in d149
    assert "과소산정 여부 별도 확인 권장" in doc, (
        "D-4가 부하를 낮추는 방향이라 난방기 용량 과소산정 위험이 있다는 경고가 사라졌다")
    assert "배선은 하지 않았다" in doc, (
        "`siting_lookup` 배선이 설계 선택을 낳아 하지 않았다는 표기가 사라졌다")


def test_158cha_siting_probe_is_computed_not_claimed():
    """158차 — 「0/15 매칭」은 **틀린 측정**이었고, Ⅰ섹션의 코드 동작 주장을 계산으로 바꿨다.

    🔴 150차·157차가 잰 것은 `region in table`(**직접 키 매칭**)이다.
    `siting_design_load()`는 **부분 매칭을 내장**해 3건 중 **2건을 정상 조회**하고
    주입값과 일치한다 — **그 함수의 docstring이 이미 그렇게 적고 있었다**.
    나는 함수를 호출하지 않고 사전 조회만 하고 결론을 냈다.

    🔴 그리고 케이스가 손으로 적은 *"siting_design_load(…) = {…}"*가 **낡아 있었다**
    (chuncheon wind_ms 32 vs 실제 34). 147차 note *「그대로 렌더된다」*가 148차에
    거짓이 된 것과 같은 유형이라 **생성기가 실제로 호출**하게 했다.
    """
    import os as _o, sys as _s, json as _j, re as _re
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import smartfarm_engine as e
    import build_site as bs

    rd = lambda n: open(_o.path.join(repo, n), encoding="utf-8").read()
    doc = rd("근거_설계하중조회_측정정정_20260920.md")

    # ── ① 🔴 함수는 부분 매칭을 한다 — 「0/15」가 잰 것이 아니다 ─────
    cases = {}
    for cid in ("chuncheon", "uminjae", "wonchaewon"):
        inp = _j.loads(rd(_o.path.join("cases", cid + ".json")))["input"]
        cases[cid] = inp
        assert inp["region"] not in e.REGION_DESIGN_LOAD, (
            f"{cid}의 region이 표의 **직접 키**가 됐다 — 「0/15」 정정 서술을 다시 보라")
    ok = {cid: e.siting_design_load(i["region"]) for cid, i in cases.items()}
    assert ok["chuncheon"] == {"snow_cm": 32, "wind_ms": 34}, ok["chuncheon"]
    assert ok["uminjae"] == {"snow_cm": 26, "wind_ms": 28}, ok["uminjae"]
    assert ok["wonchaewon"] is None, (
        "원채원이 조회되기 시작했다 — region 해상도가 올라갔다면 주입값 30·35를 "
        "표와 대조하라(S-1)")
    # 조회되는 2건은 **주입값과 일치**한다 — 이것이 D-5 감응 0의 근거다
    for cid in ("chuncheon", "uminjae"):
        assert (ok[cid]["snow_cm"], ok[cid]["wind_ms"]) == \
               (cases[cid]["snow_cm"], cases[cid]["wind_ms"]), (
            f"🔴 {cid}의 주입값이 매핑표 조회와 어긋난다")
    assert "부분 포함되는지로 찾는다" in (e.siting_design_load.__doc__ or ""), (
        "🔴 함수 docstring의 부분 매칭 설명이 사라졌다 — 158차가 확인한 근거다")

    # ── ② 케이스의 코드 동작 주장이 실제와 맞는가 ─────────────────────
    #    손으로 적은 "함수가 이렇게 답한다"는 낡는다. 적혀 있다면 맞아야 한다.
    PAT = _re.compile(r"siting_design_load\('([^']+)'\)\s*=\s*(\{[^}]*\})")
    checked = 0
    for cid in ("chuncheon", "uminjae", "wonchaewon"):
        src = _j.loads(rd(_o.path.join("cases", cid + ".json")))["site"]["design_load_source"]
        for m in PAT.finditer(src):
            checked += 1
            arg, claimed = m.group(1), m.group(2)
            real = e.siting_design_load(arg)
            assert str(real) == claimed, (
                f"🔴 {cid}의 서술이 `siting_design_load({arg!r})` = {claimed}라 적었으나 "
                f"실제 반환은 {real}다 — 손으로 쓴 코드 동작 주장이 낡았다(158차 유형)")
    assert checked >= 2, f"검사한 주장이 {checked}건이다 — 최소 2건은 있어야 한다"

    # ── ③ 🔴 Ⅰ섹션이 **호출**하는가 ─────────────────────────────────
    src = rd("build_site.py")
    # 🔴 정의만 세면 **호출부가 사라져도 통과**한다(뮤테이션 Z3). 정의 + 호출 = 2회 이상
    assert src.count("_siting_probe(") >= 2 and "e.siting_design_load(" in src, (
        f"🔴 `_siting_probe` 등장이 {src.count('_siting_probe(')}회다 — "
        "정의(1) + Ⅰ섹션 호출(1) 이상이어야 한다. 호출이 빠지면 Ⅰ섹션이 "
        "손으로 쓴 주장으로 되돌아간다")
    assert "{_siting_probe(site.get(" in src, "Ⅰ섹션의 호출 지점이 사라졌다"
    # 값의 권위는 케이스 주입값이다 — 조회값으로 **대체하지 않는다**
    probe = bs._siting_probe("강원(춘천)", {"snow_cm": 32, "wind_ms": 34})
    assert "일치" in probe and "32" in probe and "34" in probe
    bad = bs._siting_probe("강원(춘천)", {"snow_cm": 99, "wind_ms": 99})
    assert "불일치" in bad, (
        "🔴 주입값과 조회값이 달라도 대조가 드러나지 않는다 — 대조의 의미가 없다")
    none = bs._siting_probe("충남", {"snow_cm": 30, "wind_ms": 35})
    assert "없음" in none and "주입값 사용" in none, (
        "조회 불가일 때 **주입값을 쓴다**는 표기가 사라졌다 — fallback 설계 선택을 "
        "만들지 않기로 한 것이 158차 결정이다")

    # 산출물에 실제로 실렸는가
    for cid in ("chuncheon", "uminjae", "wonchaewon"):
        h = rd("SmartFarm_통합보고서_%s.html" % cid)
        assert "매핑표 대조" in h, f"{cid} 리포트에 매핑표 대조 행이 없다"

    # ── ④ 정정이 기록됐는가 ──────────────────────────────────────────
    assert "틀린 측정" in doc and "직접 키 매칭" in doc
    assert "그런 조회 함수가" in doc and doc.count("기상 4표") >= 2, (
        "🔴 0이라는 관찰이 **기상 4표에는 여전히 해당한다**는 구분이 사라졌다 — "
        "정정이 과잉교정이 된다. 이 구분은 §1과 §4 두 곳에 있어야 한다")
    led = rd("근거_결정대기대장_20260915.md")
    assert "158차 정정: 틀린 측정이었다" in led
    d150 = rd("근거_잔여결정8건_감응측정_20260916.md")
    assert "~~**매칭 0 / 15.**~~" in d150, "150차의 틀린 수치에 취소선이 없다"

    # ── ⑤ 값은 바꾸지 않았다 ─────────────────────────────────────────
    assert (cases["wonchaewon"]["snow_cm"], cases["wonchaewon"]["wind_ms"]) == (30, 35), (
        "🔴 원채원 주입 설계하중이 바뀌었다 — 158차는 **대조만** 했다")
    assert "결정은 하나도 내리지 않았다" in doc


def test_159cha_weather_tables_unreachable_and_province_lost():
    """159차 — D-5 잔여 범위(기상 4표)의 감응 **계산 0 · 산출물 0**, 그리고
    원채원을 대조할 수 없는 **진짜 이유**(광역 열 유실).

    🔴 측정 방법이 한 번 부풀었다: `def …(?=\\ndef )` 정규식이 **모듈 수준
    선언**(표 dict)을 함수 본문으로 삼켜 `heating_load`·`generate_rfq_package`가
    표를 읽는다고 나왔다(414줄 vs 실제 78줄). **AST로 다시 셌다** —
    141차 *"파서를 쓰지 말았어야 했다"*·156차 「21곳」과 같은 계열이다.
    """
    import ast as _ast, os as _o, sys as _s, json as _j
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import smartfarm_engine as e

    rd = lambda n: open(_o.path.join(repo, n), encoding="utf-8").read()
    doc = rd("근거_D5잔여감응_province유실_20260920.md")
    TBL = {"DESIGN_OUTDOOR_TEMP_TAC", "HEATING_DEGREE_HOURS_1000",
           "MONTHLY_SUNSHINE_HOURS", "MONTHLY_MEAN_WIND_MS"}

    # ── ① 🔴 AST로 — 표를 **함수 본문에서** 읽는 것이 누구인가 ───────
    tree = _ast.parse(rd("smartfarm_engine.py"))
    users = set()
    for node in _ast.walk(tree):
        if isinstance(node, _ast.FunctionDef):
            for n in _ast.walk(node):
                if isinstance(n, _ast.Name) and n.id in TBL:
                    users.add(node.name)
    assert users == {"design_outdoor_temp", "heating_degree_hours",
                     "monthly_sunshine", "mean_wind", "monthly_mean_wind"}, (
        f"기상 4표를 읽는 함수가 {sorted(users)}로 바뀌었다 — 159차 실측은 5개다. "
        "늘었다면 **계산 도달 0**이라는 결론을 다시 재라")

    # ── ② 생성기가 그 다섯을 부르는가 — 계산 도달 0 ──────────────────
    gen = "".join(rd(f) for f in ("build_site.py", "webapp.py", "render_report.py",
                                  "run_report.py", "cases.py"))
    calls = {fn: gen.count(fn + "(") for fn in users}
    assert sum(calls.values()) == 0, (
        f"🔴 생성기가 기상 4표 함수를 부르기 시작했다: {calls} — "
        "D-5 잔여 범위의 감응이 0이 아니게 된다")
    # 표가 아니라 스칼라 기본값을 쓴다
    assert isinstance(e.DEGREE_HOURS_DEFAULT, float) and e.DEGREE_HOURS_DEFAULT == 10098.0

    # ── ③ 데이터 경로는 있다 — 근거대장 값 열(146차 [2] 교훈) ────────
    ledger = rd("SmartFarm_근거대장.html")
    for t in TBL:
        assert t in ledger, (
            f"{t}가 근거대장에서 사라졌다 — 계산 도달 0과 **데이터 도달**은 다르다")
    assert "계산 0 · 산출물 0" in doc and "호출 경로와 데이터 경로를 둘 다" in doc

    # ── ④ 🔴 정규식 함정이 기록됐는가 ────────────────────────────────
    # 🔴 맨 숫자만 보면 대비가 깨져도 통과한다(뮤테이션 A5) — **행 전체**를 고정한다
    assert "모듈 수준 선언" in doc, "정규식이 모듈 선언을 삼킨 진단이 사라졌다"
    for row in ("`heating_load` | **414** | **78** |",
                "`generate_rfq_package` | **60** | **20** |"):
        assert row in doc, (
            f"🔴 정규식 캡처 vs AST 본문 대비 행이 사라졌다: {row} — "
            "이 대비가 'AST로 다시 세야 했다'는 근거다")
    assert "주석 한 줄" in doc, "generate_rfq_package의 hit이 주석이었다는 확인이 사라졌다"

    # ── ⑤ 🔴 광역 열이 없다 — 원채원 대조가 불가능한 이유 ────────────
    vals = {tuple(sorted(v)) for v in e.REGION_DESIGN_LOAD.values()}
    assert vals == {("snow_cm", "wind_ms")}, (
        f"🔴 `REGION_DESIGN_LOAD` 값 구조가 {vals}로 바뀌었다 — province가 "
        "복원됐다면 원채원 주입값 30·35를 소속 광역 범위와 대조하라(159차가 못 한 것)")
    paren = [k for k in e.REGION_DESIGN_LOAD if "(" in k]
    assert sorted(paren) == ["고성(강원)", "고성(경남)", "광주(경기)"], (
        f"광역 힌트가 붙은 키가 {sorted(paren)}로 바뀌었다 — 동명 3건뿐이었다")
    reg = _j.loads(rd("엔진데이터_레지스트리.json"))
    assert "(province, 지명)" in reg["constants"]["REGION_DESIGN_LOAD"]["source"], (
        "🔴 원문에 province 열이 **있었다**는 기록이 사라졌다 — "
        "등재하며 버려졌다는 159차 진단의 근거다")
    assert "등재하면서 버렸다" in doc and "S-4" in doc

    # ── ⑥ 원채원은 여전히 대조 불가 ──────────────────────────────────
    wc = _j.loads(rd(_o.path.join("cases", "wonchaewon.json")))["input"]
    assert (wc["snow_cm"], wc["wind_ms"]) == (30, 35)
    assert e.siting_design_load(wc["region"]) is None

    # ── ⑦ 하지 않은 것 ───────────────────────────────────────────────
    assert "외부 지식으로 채워 넣지 않았다" in doc, (
        "행정구역 소속을 지식으로 채우지 않았다는 표기가 사라졌다 — 1절 경계다")
    assert "쓰이지 않는 경로에 판단을 박는 것" in doc, (
        "기상 4표용 조회 함수를 지금 만들지 않는 이유가 사라졌다")
    assert "결정은 하나도 내리지 않았다" in doc


def test_160cha_s1_absence_and_canonical_index():
    """160차 — S-1 「원문 미보유」를 **탐색 범위와 함께** 확정하고, 정본 인덱스를 고정했다.

    🔴 나는 **낡은 인덱스**(`_전체.jsonl`, 7월판 48,433청크)를 보고 커버리지가
    비대칭이라 결론했다. 최신은 **`_전체_9축.jsonl`(9월, 148,424청크)**이고
    다시 재면 희박은 9건이 아니라 **사실상 0건**이다.

    남은 「희박」 2건도 결함이 아니었다 — `백가은·조윤정`은 **엔진 표본명이 합성**이라
    이름으로 세면 0이 나오고(인덱스엔 각 435), `구창회`는 원문이 **도면 한 건**이다.
    131차 「문자열 수는 항목 수가 아니다」·156차 「21곳」과 같은 계열이다.
    """
    import os as _o, sys as _s, json as _j
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import smartfarm_engine as e

    rd = lambda n: open(_o.path.join(repo, n), encoding="utf-8").read()
    doc = rd("근거_S1부재검증_인덱스정본_20260920.md")

    # ── ① 정본 인덱스가 9축인가 — 크기·존재로 고정 ───────────────────
    nine = _o.path.join(repo, "문서청킹_인덱스_전체_9축.jsonl")
    old = _o.path.join(repo, "문서청킹_인덱스_전체.jsonl")
    assert _o.path.exists(nine) and _o.path.exists(old), "인덱스 파일이 사라졌다"
    assert _o.path.getsize(nine) > _o.path.getsize(old) * 3, (
        "🔴 9축 인덱스가 더 이상 최신·최대가 아니다 — 어느 것이 정본인지 다시 정하고 "
        "160차의 커버리지 측정을 다시 하라")
    assert "_전체_9축.jsonl" in rd("작업지시서.md")

    # ── ② 🔴 S-1 부재 — 파일명 전수(탐색 범위를 코드로 재현) ─────────
    EXCL = (".git", "__pycache__", "노지견적", "노지시방서", "대산온실")
    GEN = ("SmartFarm_", "근거_", "작업", "인수인계")
    found = []
    for root, dirs, files in _o.walk(repo):
        if any(x in root for x in EXCL):
            continue
        for f in files:
            if any(k in f for k in ("원채원", "공주장원리", "당진이상근")):
                if not any(f.startswith(g) for g in GEN) and not f.endswith(".md"):
                    found.append(_o.path.relpath(_o.path.join(root, f), repo))
    # 남는 것은 리포가 만든 산출물·케이스뿐이어야 한다
    assert all(x.startswith("cases") or x.startswith("SmartFarm_") for x in found), (
        f"🔴 원문 미보유 3건의 자료가 리포에 들어왔다: {found[:5]} — "
        "S-1이 풀렸다면 회귀 기준의 설계하중·밴드를 다시 대조하라")

    # ── ③ 커버리지 — 9축에서 CAPEX 표본이 실제로 잡히는가 ────────────
    #    (전량 로드는 비싸다 — 대표 3건만 존재 확인)
    need = {"이두희": 0, "윤성호": 0, "강정구": 0, "백가은": 0, "조윤정": 0}
    wc = 0
    with open(nine, encoding="utf-8") as fh:
        for line in fh:
            if wc == 0 and "원채원" in line:
                wc += 1
            for k in need:
                if '"case_name": "%s"' % k in line:
                    need[k] += 1
    assert wc == 0, (
        "🔴 9축 인덱스에 원채원이 나타났다 — S-1이 들어왔다면 §1 표를 갱신하라")
    for k, n in need.items():
        assert n >= 100, (
            f"🔴 9축 인덱스에서 {k}의 청크가 {n}건이다 — 160차 실측은 100건 이상이다. "
            "7월판(`_전체.jsonl`)을 보고 있지 않은지 확인하라")

    # ── ④ 🔴 합성 표본명 함정 ────────────────────────────────────────
    assert "백가은·조윤정" in e.CAPEX_MAJOR_KNOWN_TOTALS, (
        "엔진의 합성 표본명이 바뀌었다 — 인덱스 조회가 0을 내는 원인이었다")
    assert need["백가은"] >= 100 and need["조윤정"] >= 100, (
        "인덱스는 두 이름을 **분리**해 담는다 — 합성명으로 세면 0이다")
    assert "엔진 표본명이 합성" in doc and "이름으로 세면 0이 나온다" in doc

    # ── ⑤ 정정과 한계가 기록됐는가 ───────────────────────────────────
    assert "나는 낡은 인덱스를 보고 있었다" in doc
    assert "148,424" in doc and "48,433" in doc
    assert "확인할 수 없다" in doc, (
        "🔴 146차 [8]에서 레드팀이 어느 인덱스를 썼는지 **단정하지 않았다**는 "
        "표기가 사라졌다 — 보고서에 없는 것을 추정으로 적으면 안 된다")
    assert "지우면 그 판정들의 재현이 불가능해진다" in doc, (
        "낡은 인덱스를 **삭제하지 않은 이유**가 사라졌다")
    led = rd("근거_결정대기대장_20260915.md")
    assert "160차에 자료로 확정" in led and "9축 148,424청크 중 0" in led

    # ── ⑥ 결정하지 않았다 ────────────────────────────────────────────
    assert "결정은 하나도 내리지 않았다" in doc
    assert "청킹 인덱스를 재생성하지 않았다" in doc


def test_161cha_p0a_sources_and_unit_conversion():
    """161차 — P0-a 재탐색. `U_VALUE`는 **이미 풀려 있었고**, `FR_TABLE`은 후보를 찾았다.

    🔴 나는 `[표 3-3-30]`을 열어 *"등재 유리 5.3이 어디에도 없다"*고 적었다가
    **기존 ref note를 읽고 틀렸음을 알았다** — 표는 **W/㎡·K**이고 엔진은
    **kcal/㎡·hr·℃**라 **×0.86** 환산이다(100차가 이미 지목). 158차의
    *"함수는 호출해서 확인한다"*와 같은 유형: **등재된 근거를 읽지 않고 원문만 봤다.**

    🔴 그리고 ref를 붙이며 **중복 키**를 만들 뻔했다 — 두 상수에 이미
    `source_refs`가 있었고, 새 키를 삽입하면 JSON 파서가 **뒤엣것만 남긴다**.
    배열에 append해야 한다.
    """
    import os as _o, sys as _s, json as _j
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import smartfarm_engine as e

    rd = lambda n: open(_o.path.join(repo, n), encoding="utf-8").read()
    doc = rd("근거_P0a원문발견_9축재탐색_20260920.md")
    reg = _j.loads(rd("엔진데이터_레지스트리.json"))
    C = reg["constants"]

    # ── ① 🔴 중복 키가 없는가(JSON은 조용히 뒤엣것만 남긴다) ─────────
    src = rd("엔진데이터_레지스트리.json")
    for k in ("FR_TABLE", "U_VALUE", "U_DESIGN"):
        i = src.find('"%s": {' % k)
        j = src.find("\n    },", i)
        assert src[i:j].count('"source_refs"') == 1, (
            f"🔴 {k}에 `source_refs` 키가 둘이다 — JSON 파서는 **뒤엣것만** 남기므로 "
            "앞의 ref가 조용히 사라진다. 배열에 append하라")

    # ── ② W → kcal 환산이 등재값을 설명하는가(100차 확정) ────────────
    #    표 3-3-30은 W/㎡·K, 엔진은 kcal/㎡·hr·℃ — 1W = 0.86 kcal/h
    assert abs(6.16 * 0.86 - 5.2976) < 1e-4
    assert abs(6.63 * 0.86 - 5.7018) < 1e-4
    assert abs(e.U_VALUE["유리"] - 5.3) < 1e-9, "U_VALUE[유리] 값이 바뀌었다"
    assert abs(e.U_DESIGN["필름"] - 5.7) < 1e-9, "U_DESIGN[필름] 값이 바뀌었다"
    assert abs(6.16 * 0.86 - e.U_VALUE["유리"]) < 0.01, (
        "🔴 유리 6.16 W×0.86 = 5.298 ≈ 5.3이라는 **정상환산설**이 깨졌다")
    assert abs(6.63 * 0.86 - e.U_DESIGN["필름"]) < 0.01, (
        "🔴 플라스틱 6.63 W×0.86 = 5.702 ≈ 5.70이라는 99차 채택 근거가 깨졌다")
    # 그 근거가 ref에 **적혀 있다**
    ud = " ".join(r.get("note") or "" for r in C["U_DESIGN"]["source_refs"])
    uv = " ".join(r.get("note") or "" for r in C["U_VALUE"]["source_refs"])
    assert "6.63" in ud and "0.86" in ud and "5.70" in ud, (
        "U_DESIGN의 환산 근거(6.63×0.86=5.70)가 ref에서 사라졌다")
    assert "6.16" in uv and "5.298" in uv, (
        "U_VALUE의 환산 근거(6.16×0.86=5.298)가 ref에서 사라졌다")
    assert any(r.get("match") == "exact" for r in C["U_DESIGN"]["source_refs"]), (
        "U_DESIGN의 exact ref가 사라졌다 — 99차 채택 근거다")
    assert "이미 해소돼 있었다" in doc and "등재된 근거를 읽지 않고 원문만 봤다" in doc

    # ── ③ 🔴 FR_TABLE — 수치 근거 후보가 붙었고 정합하지 않는다 ──────
    fr = C["FR_TABLE"]["source_refs"]
    assert len(fr) == 3, f"FR_TABLE의 refs가 {len(fr)}건이다 — 161차 실측은 3건"
    cand = [r for r in fr if "신개념온실" in r["file"] or "에너지절감과생산성" in r["file"]]
    assert len(cand) == 1 and cand[0]["match"] == "near", (
        "🔴 [표 3-3-27] ref가 사라졌거나 등급이 near가 아니다 — 등재값이 이 문서에서 "
        "나온 것이 **아니라** 근접·불일치를 보이므로 near다")
    note = cand[0]["note"]
    # 표 **행 형태**로 고정한다 — 맨 숫자는 같은 note의 다른 문장에도 있다(뮤테이션 C4)
    for row in ("폴리에틸렌 필름 30~35", "다겹보온커튼 58~67",
                "알루미늄 스크린(LSP) 43~47"):
        assert row in note, f"🔴 [표 3-3-27]의 행 「{row}」이 대조 기준에서 사라졌다"
    for tok in ("표 3-3-27", "1층"):
        assert tok in note, f"[표 3-3-27] 대조 기준에서 {tok}가 사라졌다"
    assert _o.path.isfile(_o.path.join(repo, cand[0]["file"])), "원문이 사라졌다"

    # 값은 바뀌지 않았다 — 정합하지 않는 표를 채택하는 것은 ★결정이다
    assert e.FR_TABLE == {"PO단일": 0.35, "다겹보온": 0.5,
                          "이중커튼": 0.7, "2중커튼": 0.7}, (
        "🔴 FR_TABLE 값이 바뀌었다 — 161차는 ref를 붙이고 대조만 했다. "
        "표 3-3-27 채택은 ★사용자 결정이고, 채택하려면 어느 행을 PO단일·이중커튼에 "
        "대응시킬지부터 정해야 한다")
    assert not (0.58 <= e.FR_TABLE["다겹보온"] <= 0.67), (
        "다겹보온이 표 범위(58~67%)로 들어왔다면 **값이 교체된 것**이다 — "
        "그것은 ★결정이므로 근거문서를 갱신하라")

    # ── ④ 탐색 범위가 좁았다는 진단 ──────────────────────────────────
    assert "스마트팜스펙/` 전수 검색" in doc and "스마트팜연구DB/`를 보지 않았다" in doc, (
        "🔴 종전 「전무」가 **탐색 범위 탓**이었다는 진단이 사라졌다 — R6의 실례다")
    assert "88,915" in doc

    # ── ⑤ 단정하지 않은 것 ───────────────────────────────────────────
    assert "단정하지 않는다" in doc
    assert "결정은 하나도 내리지 않았다" in doc

    # ── ⑥ 🔴 162차 — 전수 스캔이 끝나고 2층 값이 나왔다 ──────────────
    #    161차는 **인덱스가 가리킨 쪽만 보고** "미확보"라 적었다.
    assert "55∼65%" in doc or "55~65" in doc, (
        "🔴 2층 커튼 열절감율(p375, 55~65%)이 근거문서에서 사라졌다 — "
        "161차의 「이중커튼 출처 미확보」를 뒤집은 발견이다")
    assert "인덱스가 가리킨 쪽만 보고" in doc, (
        "🔴 161차가 전수 스캔 전에 결론을 냈다는 자기 진단이 사라졌다")
    assert "재료별 값이 아니다" in doc, (
        "p313의 「열절감율 50%」가 **설계 예시의 가정값**이지 재료별 값이 아니라는 "
        "구분이 사라졌다 — 숫자 일치를 근거로 읽으면 안 된다")
    # 네 값 중 원문 범위 안은 PO단일 하나
    assert 0.30 <= e.FR_TABLE["PO단일"] <= 0.35, "PO단일이 폴리에틸렌 30~35를 벗어났다"
    assert not (0.55 <= e.FR_TABLE["이중커튼"] <= 0.65), (
        "이중커튼이 2층 범위(55~65%)로 들어왔다면 **값이 교체된 것**이다 — ★결정이다")
    note2 = cand[0]["note"]
    assert "55∼65%" in note2 and "p375" in note2, (
        "FR_TABLE ref에서 2층 열절감율 대조 기준이 사라졌다")


_BYEPYO_PDFS = (
    "스마트팜스펙/2025년 청년농업인 스마트팜 자립기반 구축지원사업 준호네 자연농장 "
    "이준호/25 - 117 - [함평] 이준호 온실 검토서.pdf",
    "스마트팜스펙/견적참조/설계도25 - 233 - [천안] 이두희 온실 검토서_251024 final.pdf",
)


def _byepyo_tail_row(pdfplumber, path, page):
    """165차 — 셀 파싱이 놓치는 **마지막 「40 이상」 행**을 좌표로 뽑는다.

    🔴 163·164차는 이 행의 16개 지명을 **테스트 안에 손으로 적어 넣고** 다시 셌다.
    그래서 `len(w40) == 16`은 **깨질 수 없는 가드**였다(156차 *"매칭 텍스트로 재서
    늘 0"*과 같은 계열). 이제 **헤더 열의 x중심**으로 꼬리 단어를 열에 배정해
    **실제로 센다** — 원문이 바뀌면 수가 달라진다.
    """
    import re as _re
    ZONES = ["강원도", "경기권", "경상권", "전라권", "충청권", "제주도"]
    ALIAS = {("강원도", "고성"): "고성(강원)", ("경상권", "고성"): "고성(경남)",
             ("경기권", "광주"): "광주(경기)", ("전라권", "광주"): "광주광역시"}
    with pdfplumber.open(path) as pdf:
        words = pdf.pages[page - 1].extract_words()
    centers = {}
    for wd in words:
        t = wd["text"].strip()
        if t in ZONES and t not in centers:
            centers[t] = (wd["x0"] + wd["x1"]) / 2
    assert len(centers) == len(ZONES), f"권역 헤더를 {len(centers)}개만 찾았다"

    y40 = None
    for i, wd in enumerate(words):
        if wd["text"].strip() == "40" and i + 1 < len(words) \
                and words[i + 1]["text"].strip() == "이상":
            y40 = wd["top"]
            break
    assert y40 is not None, "「40 이상」 라벨을 찾지 못했다"

    order = sorted(centers.items(), key=lambda kv: kv[1])
    out = {}
    for wd in words:
        if wd["top"] < y40 - 14:
            continue
        t = wd["text"].strip().strip(",")
        if not t or t == "-" or t == "이상" or _re.search(r"\d", t):
            continue
        x = (wd["x0"] + wd["x1"]) / 2
        zone = min(order, key=lambda kv: abs(x - kv[1]))[0]
        out[ALIAS.get((zone, t), t)] = 40
    return out


def _parse_byepyo(pdfplumber, path, page, bands):
    """163차 — 검토서에 전재된 고시 [별표]를 권역 열 x 구간 행으로 읽는다."""
    import re as _re
    ZONES = ["강원도", "경기권", "경상권", "전라권", "충청권", "제주도"]
    ALIAS = {("강원도", "고성"): "고성(강원)", ("경상권", "고성"): "고성(경남)",
             ("경기권", "광주"): "광주(경기)", ("전라권", "광주"): "광주광역시"}
    with pdfplumber.open(path) as pdf:
        rows = pdf.pages[page - 1].extract_tables()[0][1:]
    got = {}
    for bi, row in enumerate(rows):
        if bi >= len(bands):
            break
        for zi, zone in enumerate(ZONES):
            if zi + 1 >= len(row):
                continue
            for nm in _re.split(r"[,\s]+", row[zi + 1] or ""):
                nm = nm.strip(" ,")
                if nm and nm != "-" and not _re.search(r"\d", nm):
                    got[ALIAS.get((zone, nm), nm)] = bands[bi]
    return got


def test_163cha_design_load_byepyo_registered():
    """163차 — `REGION_DESIGN_LOAD`의 원문 [별표]가 **리포 안에 있었다**.

    133차는 이 상수를 *"원문이 리포에 없다 — ★사용자 몫"*으로 이관했고, 그 결과
    `source_refs`가 **0건**이라 추적성 감사가 **한 번도 돌지 않았다**. 162차에서
    *"「없다」는 판정에는 전수 확인이 필요하다"*를 배운 직후 재탐색하니, 고시 [별표]가
    리포 안 **구조검토서 2건**(PDF p5~p6)에 통째로 전재돼 있었다.

    🔴 원문 **서술**에는 오류가 있다 — 함평 검토서 p3 결론문이 *"장수군에 적합한"*이라
    적지만 적용값 40cm/34㎧는 함평 기준이다. 그래서 대조는 **서술이 아니라 표**에 댔다.
    """
    import os as _o, sys as _s, json as _j
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import smartfarm_engine as e
    import audit_traceability as A

    rd = lambda n: open(_o.path.join(repo, n), encoding="utf-8").read()
    doc = rd("근거_설계하중별표_리포내발견_20260920.md")
    reg = _j.loads(rd("엔진데이터_레지스트리.json"))
    ent = reg["constants"]["REGION_DESIGN_LOAD"]

    # ── ① 🔴 중복 키가 없는가(161차 교훈 — JSON은 조용히 뒤엣것만 남긴다) ──
    src = rd("엔진데이터_레지스트리.json")
    i = src.find('"REGION_DESIGN_LOAD": {')
    j = src.find('"RFQ_REQUIRED_CATEGORIES_DEFAULT"', i)
    assert i >= 0 and j > i
    assert src[i:j].count('"source_refs"') == 1, (
        "🔴 REGION_DESIGN_LOAD에 `source_refs` 키가 둘이다 — 파서는 **뒤엣것만** 남긴다")

    # ── ② ref 2건이 서 있고 원문이 실재하는가 ────────────────────────
    refs = ent.get("source_refs") or []
    assert len(refs) == 2, (
        f"🔴 REGION_DESIGN_LOAD의 refs가 {len(refs)}건이다 — 163차 실측은 2건이다. "
        "0건으로 돌아갔다면 이 상수는 다시 **추적성 감사 사각**이다")
    for r in refs:
        assert r["match"] == "partial", (
            "🔴 match가 partial이 아니다 — 이 별표는 **이전 판**이라 등재값(현행 판)을 "
            "전량 확정하지 못하고 지명 집합과 하한만 뒷받침한다. exact는 과대다")
        assert _o.path.isfile(_o.path.join(repo, r["file"])), f"원문 소실 {r['file']}"
    assert {r["file"] for r in refs} == set(_BYEPYO_PDFS), (
        "🔴 ref가 가리키는 검토서가 바뀌었다 — 두 번째 사본은 **독립성**이 근거력이다")

    # ── ③ 감사 사각이 실제로 줄었는가(수가 아니라 **명단**으로 본다) ──
    a = A.audit()
    blocked = {k for k, _st, _b in a["refless_blocked"]}
    assert "REGION_DESIGN_LOAD" not in blocked, (
        "🔴 REGION_DESIGN_LOAD가 다시 refless_blocked에 있다")
    assert blocked == {"SPEC_COUNT", "SPEC_TABLE", "OPEX_ITEM_CATEGORIES"}, (
        f"🔴 남은 사각 명단이 바뀌었다: {sorted(blocked)} — 163차 실측은 3건이다")
    assert a["counts"]["source_refs"] == 154, (
        f"source_refs가 {a['counts']['source_refs']}건이다 — 163차 실측은 154건")

    # ── ④ 값은 바뀌지 않았다 ─────────────────────────────────────────
    assert len(e.REGION_DESIGN_LOAD) == 172
    assert e.REGION_DESIGN_LOAD["함평"] == {"snow_cm": 40, "wind_ms": 34}
    assert e.REGION_DESIGN_LOAD["천안"] == {"snow_cm": 26, "wind_ms": 28}
    assert e.REGION_DESIGN_LOAD["장수"] == {"snow_cm": 38, "wind_ms": 26}

    # ── ⑤ 단정하지 않은 것이 문서에 남아 있는가 ──────────────────────
    assert "2025-108호 아님" in doc and "2014-78호 아님" in doc, (
        "🔴 별표가 **현행 판도 최초 판도 아니다**라는 판별이 사라졌다")
    assert "단정하지 않는다" in doc and "2019-44호" in doc
    assert "장수군" in doc, "🔴 원문 서술 오류(결론문 지명) 기록이 사라졌다"
    assert "값은 하나도 바꾸지 않았다" in doc
    assert "★사용자 몫이다" in doc, "현행 판 원문 확보가 사용자 몫이라는 표기가 사라졌다"


def test_163cha_design_load_byepyo_reparse():
    """163차 — [별표]를 **다시 파싱해** 등재 172지역과 대조한다(문자열이 아니라 결과로).

    🔴 **하향이 0건**이어야 한다 — 개정 사유가 *"폭설·강풍 피해 예방"*(상향)이므로
    등재값이 별표 구간보다 **낮아지는 지역**은 전사 오류 신호다. 「40 이상」 칸은
    하한만 주므로 *"등재 >= 40"* 만 검사한다.
    """
    import os as _o, sys as _s, pytest as _p
    pdfplumber = _p.importorskip("pdfplumber")
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import smartfarm_engine as e
    import warnings as _w

    SNOW = [20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40]
    WIND = [24, 26, 28, 30, 32, 34, 36, 38, 40]
    RDL = e.REGION_DESIGN_LOAD
    parsed = []
    with _w.catch_warnings():
        _w.simplefilter("ignore")
        for rel in _BYEPYO_PDFS:
            path = _o.path.join(repo, rel)
            assert _o.path.isfile(path), f"별표 원문이 사라졌다 {rel}"
            parsed.append((_parse_byepyo(pdfplumber, path, 5, SNOW),
                           _parse_byepyo(pdfplumber, path, 6, WIND)))

    # 두 사본이 서로 같은가 — 한 PDF의 추출 사고가 아님을 보이는 교차 확인
    assert parsed[0][0] == parsed[1][0], "🔴 두 사본의 적설 별표가 다르게 읽힌다"
    assert parsed[0][1] == parsed[1][1], "🔴 두 사본의 풍속 별표가 다르게 읽힌다"

    snow, wind = parsed[0]
    # 🔴165차 자기정정 — 풍속표는 셀 파싱이 마지막 「40 이상」 행을 놓친다.
    #    163·164차는 그 16개 지명을 **여기에 손으로 적어 넣고** 다시 세서
    #    `len(w40) == 16`이 **깨질 수 없는 가드**였다. 이제 좌표로 **실제 추출**한다.
    tails = []
    with _w.catch_warnings():
        _w.simplefilter("ignore")
        for rel in _BYEPYO_PDFS:
            tails.append(_byepyo_tail_row(pdfplumber, _o.path.join(repo, rel), 6))
    assert tails[0] == tails[1], "🔴 두 사본의 「40 이상」 꼬리 행이 다르게 읽힌다"
    assert not (set(tails[0]) & set(wind)), (
        "🔴 꼬리 행 지명이 이미 셀 파싱에 들어 있다 — 보충이 중복이면 수가 어긋난다")
    wind.update(tails[0])

    for axis, table, key in (("적설", snow, "snow_cm"), ("풍속", wind, "wind_ms")):
        assert set(table) == set(RDL), (
            f"🔴 {axis} 별표의 지명 집합이 등재 172지역과 어긋난다 — "
            f"별표에만 {sorted(set(table) - set(RDL))[:5]} · "
            f"등재에만 {sorted(set(RDL) - set(table))[:5]}")
        down = [(k, table[k], RDL[k][key]) for k in table if RDL[k][key] < table[k]]
        assert not down, (
            f"🔴 {axis}에서 등재값이 별표 구간보다 **낮아진 지역**이 있다: {down[:5]} — "
            "개정은 상향이므로 하향은 전사 오류 신호다. 원인부터 찾아라")
    assert sum(1 for k in snow if RDL[k]["snow_cm"] == snow[k] and snow[k] != 40) == 136
    assert sum(1 for k in wind if RDL[k]["wind_ms"] == wind[k] and wind[k] != 40) == 148

    # ── 🔴164차 — 레지스트리 서술의 네 수치를 **결과로** 재현한다 ──────
    #    서술: "40 이상 뭉뚱그림이 22개(적설)·16개(풍속)에서 구체화 …
    #           나머지 14개(적설)·8개(풍속) 상향 … 172개 중 84개 변경·88개 불변"
    #    앞의 넷은 맞고 **뒤의 둘이 틀렸다** — 22+14=36 · 16+8=24이므로
    #    바뀐 지역은 **합쳐도 최대 60**이다. 84는 어떤 읽기로도 나오지 않는다.
    s40 = {k for k in snow if snow[k] == 40}
    w40 = {k for k in wind if wind[k] == 40}
    sup_s = {k for k in snow if snow[k] != 40 and RDL[k]["snow_cm"] > snow[k]}
    sup_w = {k for k in wind if wind[k] != 40 and RDL[k]["wind_ms"] > wind[k]}
    # 🔴165차 — 네 수치는 이제 **전부 원문에서 기계로** 나온다(풍속 16 포함).
    #    164차 시점의 "네 수치 전부 일치"는 풍속 16에 한해 **자기대조**였다.
    assert (len(s40), len(w40), len(sup_s), len(sup_w)) == (22, 16, 14, 8), (
        f"🔴 서술의 네 수치와 별표 실측이 어긋났다: "
        f"40이상 적설 {len(s40)}(22)·풍속 {len(w40)}(16) · "
        f"그 밖 상향 적설 {len(sup_s)}(14)·풍속 {len(sup_w)}(8). "
        "164차는 **이 넷이 맞다**는 것을 확인하고 합산만 정정했다")
    assert w40 == set(tails[0]), (
        "🔴 풍속 「40 이상」 집합이 꼬리 추출 결과와 다르다 — 어느 한쪽이 섞였다")
    changed = (s40 | sup_s) | (w40 | sup_w)
    assert len(changed) == 49 and 172 - len(changed) == 123, (
        f"🔴 바뀐 지역이 {len(changed)}개다 — 164차 실측은 49개 변경·123개 불변이다. "
        "레지스트리 서술의 84·88은 이 실측과도, 같은 문장의 네 수치와도 맞지 않는다")
    assert len(sup_s | sup_w) == 22 and len(s40 | w40) == 31, (
        "🔴 확정 변경 22건 · 판정 불가 31건이 어긋났다 — 「40 이상」 칸은 하한만 주므로 "
        "그 지역의 변경 여부는 **확정할 수 없다**. 둘을 합쳐 세면 안 된다")
    # 🔴 서술이 든 예시 「함평 36→40」은 그 묶음일 수 없다 — 별표에서 40 이상 칸이다
    assert snow["함평"] == 40, (
        "🔴 별표의 함평이 「40 이상」 칸이 아니게 됐다 — 164차 §3의 전제가 깨졌다")


def test_164cha_change_count_claim_is_internally_impossible():
    """164차 — 「84개 값 변경·88개 불변」은 **같은 문장 안에서** 이미 틀려 있었다.

    사용자 지시 *"오류는 개선, 자료 없음은 스킵"*. 이 오류는 **원문이 없어도**
    판정된다 — 서술이 스스로 준 네 수치(22·16·14·8)가 축별 변경 지역
    **적설 36 · 풍속 24**를 뜻하므로 합쳐도 **최대 60개 지역**이다.

    🔴 앞의 네 수치는 **전부 실측과 일치**했다(163차 [별표] 대조). 합산 단계의
    오류이지 대조 단계의 오류가 아니다 — 그래서 값을 의심하지 않았다.
    """
    import os as _o, sys as _s, json as _j
    repo = _o.path.dirname(_o.path.abspath(__file__))
    if repo not in _s.path:
        _s.path.insert(0, repo)
    import smartfarm_engine as e

    rd = lambda n: open(_o.path.join(repo, n), encoding="utf-8").read()
    doc = rd("근거_설계하중_변경건수_정정_20260920.md")
    reg = _j.loads(rd("엔진데이터_레지스트리.json"))
    src = reg["constants"]["REGION_DESIGN_LOAD"]["source"]

    # ── ① 산술 자체 — 외부 자료가 필요 없다 ──────────────────────────
    snow_changed, wind_changed = 22 + 14, 16 + 8
    assert snow_changed == 36 and wind_changed == 24
    assert snow_changed + wind_changed == 60 < 84, (
        "🔴 이 산술이 깨지면 164차의 판정 근거가 사라진다 — "
        "네 수치가 함의하는 상한은 60개 지역이고 84는 그 위다")

    # ── ② 원 서술이 **지워지지 않았는가**(무엇이 틀렸는지가 기록이다) ──
    #    🔴 1차 설계가 뮤테이션 M2를 놓쳤다: `"84개 값 변경" in src`로 쟀는데
    #    **내 정정문이 원 서술을 인용**하고 있어 원문을 지워도 통과했다.
    #    131·134·137차 「세는 문자열을 서술에 쓰지 마라」와 같은 계열이다 —
    #    **인용본에 없는 자리**를 앵커로 잡고, 개수까지 함께 고정한다.
    for tok in ("상향 조정 반영, 172개 중 84개 값 변경·88개 불변",
                "함평 36→40cm)"):
        assert tok in src, (
            f"🔴 원 서술에서 「{tok}」가 사라졌다 — 164차는 **덧붙여 정정**했지 "
            "지우지 않았다. 지우면 무엇이 어떻게 틀렸는지가 남지 않는다")
    assert src.count("84개 값 변경") == 2, (
        f"🔴 「84개 값 변경」이 {src.count('84개 값 변경')}번 나온다 — "
        "원 서술 1 + 164차 정정문의 인용 1 = 2가 맞다. 1이면 한쪽이 지워진 것이고, "
        "3 이상이면 서술이 또 불어난 것이다")

    # ── ③ 정정이 붙어 있는가 ─────────────────────────────────────────
    for tok in ("84는 어떤 읽기로도 나오지 않는다", "49개 변경 · 123개 불변",
                "확정 변경은 22건 · 판정 불가 31건", "합산 단계의 오류"):
        assert tok in src, f"🔴 164차 정정에서 「{tok}」가 사라졌다"
    assert "판(2014-78호/2019-44호/2025-108호)은 확정하지 않았다" in src, (
        "🔴 판을 확정하지 않았다는 표기가 사라졌다 — 고시 원문이 리포에 없다")

    # ── ④ 163차 문서가 **약화됐음을 스스로 밝히는가** ────────────────
    b163 = rd("근거_설계하중별표_리포내발견_20260920.md")
    assert "164차 정정 — 이 판별의 뒤쪽 근거가 약해졌다" in b163, (
        "🔴 163차 문서만 읽는 사람에게 판별이 약화된 사실이 보이지 않는다")
    assert "근거_설계하중_변경건수_정정_20260920.md" in b163

    # ── ⑤ 값은 바뀌지 않았다 ─────────────────────────────────────────
    assert len(e.REGION_DESIGN_LOAD) == 172
    assert e.REGION_DESIGN_LOAD["함평"] == {"snow_cm": 40, "wind_ms": 34}
    assert e.REGION_DESIGN_LOAD["대관령"]["snow_cm"] == 167
    assert e.REGION_DESIGN_LOAD["울릉"]["snow_cm"] == 197

    # ── ⑥ 하지 않은 것 ───────────────────────────────────────────────
    assert "엔진 값 0건 변경" in doc and "원인은 추정하지 않았다" in doc
    assert "자료 없음은 스킵" in doc


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
