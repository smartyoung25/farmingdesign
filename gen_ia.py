# -*- coding: utf-8 -*-
"""IA 문서 생성기 (211차 신설).

🔴 `IA_20260924.md`는 **손으로 적지 않는다.** 기능 축은
`consulting_package`의 `BENCHMARK_FUNCTIONS`·`FUNCTION_OF_CODE`·`FUNCTION_GAPS`가
쥐고, 이 스크립트는 그것을 **그대로 펴서** 문서로 낸다.
가드(`test_webapp.py::test_211cha_ia_menu_matches_the_code`)가 문서와 코드를
대조하므로 문서를 손으로 고치면 실패한다.

실행: python gen_ia.py      (외부 패키지 없이 돈다)
"""
import io
import consulting_package as cpkg

OUT = "IA_20260924.md"
PROBE = ("내재해", "품셈", "감리", "수의계약", "나라장터", "지방계약",
         "하자이행보증", "KCS", "적격", "공급사")
LF = chr(10)
CRLF = chr(13) + LF


def build() -> str:
    ix = cpkg.function_index()
    src = io.open("smartfarm_engine.py", encoding="utf-8").read()
    L = []
    w = L.append
    w("# 정보구조(IA) · 메뉴 · 네비게이션 — 벤치마킹 3기능 축 (2026-09-24 · 211차)")
    w("")
    w("사용자 지시로 `Farmingdesign 벤치마킹`(2026-09-02)의 **주요 기능**을 축으로")
    w("산출물을 묶고 콘솔 메뉴·네비게이션을 세웠다.")
    w("")
    w("> 🔴 **이 문서는 손으로 적지 않는다.** 표는 `consulting_package.function_index()`")
    w("> 반환을 그대로 편 것이고, 가드가 **문서와 코드를 대조**한다 — 갈라지면 실패한다.")
    w("> 다시 내려면 `python gen_ia.py`.")
    w("")
    w("---")
    w("")
    w("## 0. 무엇을 가져오고 무엇을 두고 왔는가")
    w("")
    w("| | |")
    w("|---|---|")
    w("| 가져온 것 | 벤치마킹 머리말의 **Function 1~3 정의** — 기능 이름과 그 정의문 |")
    w("| 두고 온 것 | **밴드**(Basic/Standard/Premium)와 **요율**(1.5~3% · $29/월 · €490 …) |")
    w("")
    w("밴드는 **판단성**(무엇을 팔지는 사람이 정한다), 요율은 **시세성**이다 —")
    w("1절 불변 원칙이 조회·자동판정을 금한다. 그래서 **기능 축만** 옮겼다.")
    w("")
    w("🔴 **분류이지 판정이 아니다.** 이 축은 산출물을 *「고객이 무엇을 사는가」*로")
    w("묶을 뿐 순위·등급·추천을 만들지 않는다.")
    w("")
    w("## 1. 왜 기존 6단계를 그대로 쓰지 않았나 (실측)")
    w("")
    w("리포는 이미 `PACKAGE_SPEC.stage` **6단계**를 코드에 쥐고 있다. 그런데 벤치마킹")
    w("3기능과 **1:1이 아니라 교차**한다 — F2 시방은 D2(①공종설계)·D19(②품질설계)·")
    w("D20(⑥사후관리)에 **흩어져 있다**. 단계에서 기능을 유도하면 틀린다.")
    w("")
    w("→ 기능은 `FUNCTION_OF_CODE`가 **D코드마다 직접** 쥔다. 6단계는 그대로 둔다.")
    w("")
    w("## 2. 메뉴 (사이드바 = 이 순서)")
    w("")
    w("```")
    for r in ix["rows"]:
        w("%-3s %-10s %-42s %2d종%s" % (
            r["fn"], r["name"], r["desc"][:42], len(r["docs"]),
            ("  없는 것 %d건" % len(r["gaps"])) if r["gaps"] else ""))
    w("```")
    w("")
    w("사이드바는 `기능 지도` 아래 F1·F2·F3을 두고(F0 공통·근거는 참조 절에 이미 있다),")
    w("각 항목은 `/functions#F1` 같은 앵커로 간다. 케이스 상세에도 같은 축으로 묶어 낸다.")
    w("")
    w("## 3. 산출물 배정 (코드에서 생성 — 손으로 고치지 말 것)")
    w("")
    for r in ix["rows"]:
        w("### %s %s — %s" % (r["fn"], r["name"], r["desc"]))
        w("")
        w("| D | 산출물 | 단계 | 왜 이 기능인가 | 엔진 |")
        w("|---|---|---|---|---|")
        for d in r["docs"]:
            w("| %s | %s | %s | %s | %d |" % (
                d["code"], d["title"], d["stage"], d["why"], len(d["engine"])))
        w("")
        if r["gaps"]:
            w("**아직 없는 것**")
            w("")
            for g in r["gaps"]:
                w("- **%s** — %s" % (g["name"], g["why"]))
            w("")
    w("## 4. 벤치마킹 어휘가 엔진에 있는가 (원문 실측)")
    w("")
    w("| 어휘 | 엔진 원문 |")
    w("|---|---|")
    for p in PROBE:
        w("| `%s` | **%d**회 |" % (p, src.count(p)))
    w("")
    w("있는 셋(`내재해`·`품셈`·`감리`)은 **F1·F2의 뼈대**이고, 0회인 다섯")
    w("(`수의계약`·`나라장터`·`지방계약`·`하자이행보증`·`KCS`)은 **F3·F2의 구멍**이다.")
    w("")
    w("## 5. 다음에 열 것 — ★사용자 결정이 먼저인 것")
    w("")
    w("- **수의계약 한도**·**하자이행보증 요율**은 **법정값**이다. 1절에 따라 원문 확보 →")
    w("  레지스트리 등재 → 드리프트 가드 절차를 거쳐야 하고, **등재 자체가 ★결정**이다.")
    w("- **적격 공급사 풀**은 업체 **선정**에 닿는다 — 1절이 금한 판단성이다. 만들려면")
    w("  *「고르지 않고 나열만 한다」*는 경계를 먼저 정해야 한다(★).")
    w("- **기능 배정표 자체**도 분류 판단이라 ★확인 대상이다. 바꾸려면")
    w("  `consulting_package.FUNCTION_OF_CODE` 한 곳만 고치면 되고 가드가 대조한다.")
    w("")
    w("## 6. 이 문서를 고치는 법")
    w("")
    w("직접 고치지 않는다. `consulting_package.py`의 `BENCHMARK_FUNCTIONS`·")
    w("`FUNCTION_OF_CODE`·`FUNCTION_GAPS`를 고치고 `python gen_ia.py`로 다시 낸다.")
    w("가드(`test_webapp.py::test_211cha_ia_menu_matches_the_code`)가 문서와 코드를")
    w("대조하므로 손으로 고치면 **실패한다**.")
    w("")
    return LF.join(L)


if __name__ == "__main__":
    text = build()
    io.open(OUT, "w", encoding="utf-8", newline=CRLF).write(text)
    print("IA 생성 완료: %s (%d줄)" % (OUT, text.count(LF) + 1))
