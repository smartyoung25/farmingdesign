# -*- coding: utf-8 -*-
"""콘솔 화면의 정보구조 결함을 센다 — **재현 가능하게**.

🔴 왜 있는가(294차): 콘솔 UI·UX 재설계의 기준선을 *「화면 21 · 404 8개 · 날것 별표
   576」*처럼 적으면, 세는 규칙이 없어 **그 수가 검산되지 않는다**. 155차가
   `measure_spans.py`로 같은 문제를 닫은 전례를 그대로 따른다 — 131차 이래 이 리포가
   반복해 배운 것이다: *세는 규칙이 없으면 그 수는 검산되지 않는다.*

   이 도구가 고정하는 것:
     ① **코퍼스** — 실행 중인 서버가 아니라 `TestClient(webapp.app)`가 돌려주는 응답.
        서버는 파이썬 모듈을 재시작 전까지 메모리에 들고 있어 **차수가 바뀌면 화면과
        어긋난다**(294차 착수 시점 `/flow`가 500이었다). 디스크의 코드를 재는 것이 기준이다.
     ② **본문의 정의** — `<main>` 안쪽만. 머리 메뉴·바닥글은 모든 화면에 같은 링크를
        복제하므로 섞으면 화면마다 수가 같아진다. 🔴**스타일·스크립트 블록은 먼저
        지운다**(296차) — 태그만 지우면 CSS가 본문으로 섞여 별표가 42개 부풀려졌다.
     ③ **태그 제거 후** 센다 — 날것 마크다운은 **사용자가 읽는 글자**에 섞인 것이라서,
        HTML 속성·주석 안의 별표를 세면 수가 부풀려진다.

⚠️ 계산하지 않는다 — 전부 **항목·출현 건수 집계**다(1절 258차 단서). 엔진 값을 다시
   계산·합산·비율로 내지 않는다. 이 파일은 제2의 계산 출처가 아니다.

사용: python measure_console_ia.py
"""
from __future__ import annotations

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 날것 마크다운을 재는 화면 — 사용 안내가 「넣는 것 없음(읽기)」으로 등재한 읽기 화면
#   + 세 칸만 넣는 기본설계. 케이스 코드가 필요한 화면은 케이스에 따라 글자 수가
#   달라져 기준선이 흔들리므로 뺀다.
READ_SCREENS = ("/refs", "/guide", "/flow", "/functions", "/design", "/for", "/axes")

# 같은 산출물 27행을 각자 다시 내는 「자료 지도」 화면
MAP_SCREENS = ("/flow", "/functions", "/axes", "/for", "/for/{name}")

# 목표 구조의 1층 — 일하는 화면 둘 + 자료 화면 둘. 홈 본문이 전부 링크해야 한다.
FIRST_FLOOR = ("/design", "/case/", "/flow", "/refs")

# 🔴 결과가 나오는 상태로 재야 하는 화면 — 빈 폼을 재면 금액이 0으로 잡힌다(295차).
#   표본은 고정값이다(결정론). 값 자체는 지표가 아니고 **출처 링크의 유무**만 센다.
RESULT_SAMPLES = {
    "/design": "/design?addr=%EC%B6%A9%EC%B2%AD%EB%82%A8%EB%8F%84+%EB%85%BC%EC%82%B0%EC%8B%9C"
                "&crop=%ED%86%A0%EB%A7%88%ED%86%A0&area_m2=3300",
}

# 수에서 출처로 가는 링크로 인정하는 것 — 참조 카탈로그와 근거 문서다.
SOURCE_HINTS = ("/refs", "근거")

_MONEY = re.compile(r"[0-9][0-9,]{5,}\s*원")
_PCT = re.compile(r"[0-9]+(?:\.[0-9]+)?\s*%")

_TAG = re.compile(r"<[^>]+>")
# 🔴 296차 — 태그만 지우면 `<style>` 안의 CSS가 본문으로 섞인다. 공용 스타일 블록이
#   화면마다 별표 여섯 개를 더해 **합 42개**를 부풀렸다(별표 576 → 534). 정보구조
#   에이전트가 보고한 534가 맞았고 내 576이 틀렸다.
_STYLE_SCRIPT = re.compile(r"<(?:style|script)[^>]*>.*?</(?:style|script)>", re.S | re.I)
_HREF = re.compile(r'href="([^"]+)"')
_MAIN = re.compile(r"<main[^>]*>(.*?)</main>", re.S)


def _client():
    from fastapi.testclient import TestClient
    import webapp
    return TestClient(webapp.app)


def _main_of(html: str) -> str:
    m = _MAIN.search(html)
    return m.group(1) if m else html


def _text_of(html: str) -> str:
    """사용자가 **읽는 글자**만 남긴다 — 스타일·스크립트 블록을 먼저 지운다."""
    return _TAG.sub(" ", _STYLE_SCRIPT.sub(" ", html))


def measure(fetch=None, flow=None, ssm=None) -> dict:
    """지표를 전부 재서 dict로 돌려준다. 값은 **건수**뿐이다.

    🔴 주입점이 열려 있는 이유(152차 전례): 가드가 **합성 화면**을 먹여 지표가
    *입력에서 나오는지*를 확인한다. 열어 두지 않으면 측정기가 현재 실측치를 그대로
    박아 넣어도 가드가 구별하지 못한다(294차 뮤테이션 M23·M24가 그 길이었다).

    fetch(path) -> (status_code, html). 주지 않으면 디스크의 코드를 TestClient로 읽는다.
    """
    import consulting_package as cp

    if fetch is None:
        c = _client()
        def fetch(path):
            r = c.get(path)
            return r.status_code, r.text
    get = fetch

    # ── M1 사용자가 세는 화면 ────────────────────────────────────────
    #   정의: 사용 안내가 등재한 화면 수. 화면을 늘리면 등재가 늘고, 합치면 줄어든다.
    screens = tuple(t[0] for t in cp.GUIDE_SCREENS)
    m1 = len(screens)

    # ── M2 안내 화면이 가리키는데 열리지 않는 링크 ───────────────────
    guide_body = _main_of(get("/guide")[1])
    guide_links = sorted({h for h in _HREF.findall(guide_body) if h.startswith("/")})
    m2_broken = sorted(h for h in guide_links if get(h)[0] != 200)
    m2 = len(m2_broken)

    # ── M3·M4 화면에 날것으로 나가는 마크다운 ───────────────────────
    stars = backticks = 0
    per_screen = {}
    for p in READ_SCREENS:
        t = _text_of(get(p)[1])
        s, b = t.count("**"), t.count("`")
        per_screen[p] = {"stars": s, "backticks": b}
        stars += s
        backticks += b
    m3, m4 = stars, backticks

    # ── M5 홈 본문이 링크하지 않는 1층 화면 ─────────────────────────
    #   목표 구조의 1층 넷만 센다 — 2층(만드는 쪽 도구)은 홈에서 내리는 것이 설계이고,
    #   홈 자신을 세면 머리 메뉴에만 있는 자기 링크가 늘 걸린다.
    #   자리표시자를 담은 경로는 **첫 자리표시자 앞까지**로 접두 비교한다 —
    #   홈은 실제 코드가 박힌 주소를 링크하기 때문이다.
    home_links = set(_HREF.findall(_main_of(get("/")[1])))
    def _linked(path: str) -> bool:
        stem = path.split("{", 1)[0]
        return any(h == path or h.startswith(stem) for h in home_links)
    m5_unlinked = sorted(p for p in FIRST_FLOOR if not _linked(p))
    m5 = len(m5_unlinked)

    # ── M6 자료 지도 화면 수 ────────────────────────────────────────
    m6_live = sorted(p for p in MAP_SCREENS
                     if get(p.replace("{name}", "농업인"))[0] == 200)
    m6 = len(m6_live)

    # ── M7 기입이 흩어진 화면 수 ────────────────────────────────────
    #   정의: 사용 안내가 등재한 경로 중 `/entry`로 시작하는 것의 수.
    #   목표 구조에서 기입은 **사업장 한 곳 화면의 레일**로 들어가고 견적은 도구층으로
    #   내려가므로, 등재되는 `/entry*` 화면은 하나도 남지 않는다.
    m7_screens = sorted(p for p in screens if p.startswith("/entry"))
    m7 = len(m7_screens)

    # ── M9 수를 내면서 출처로 가는 길이 없는 화면 ───────────────────
    #   인터뷰(2026-10-02)에서 「이 수가 어떻게 나왔는가」를 **네 수 전부**에서 말로
    #   설명해야 했다고 답했다. 리포에는 근거 문서 84건·참조 179건이 있는데 화면에서
    #   수 → 출처로 가는 경로가 없다. 그것을 센다.
    m9_screens = []
    for path in [p for p in screens if "{" not in p]:
        probe = RESULT_SAMPLES.get(path, path)
        st, html = get(probe)
        if st != 200:
            continue
        body = _main_of(html)
        txt = _text_of(body)
        if not (_MONEY.search(txt) or _PCT.search(txt)):
            continue
        hrefs = _HREF.findall(body)
        if not any(any(h2 in h for h2 in SOURCE_HINTS) for h in hrefs):
            m9_screens.append(path)
    m9 = len(m9_screens)

    # ── M8 본문이 자기 말을 뒤집는 곳 ───────────────────────────────
    contradictions = []
    ssm = cp.screen_stage_map() if ssm is None else ssm
    flow = cp.service_flow() if flow is None else flow
    gaps_text = " ".join(str(g) for g in flow.get("gaps", []))
    if not ssm.get("needs_decision") and "확인 필요" in gaps_text:
        contradictions.append(
            "screen_stage_map의 needs_decision이 비었는데 gaps 본문이 「확인 필요」라 적는다")
    for lens in flow.get("lenses", []):
        why = str(lens.get("why", ""))
        head = re.split(r"\s—\s", why)[0]
        items = [x.strip() for x in head.split("·") if x.strip()]
        if len(items) < 2:
            continue
        body = _text_of(get(str(lens.get("path", "/")))[1])
        absent = [x for x in items if x not in body]
        if absent:
            contradictions.append(
                "렌즈 「%s」가 %s를 적는데 그 화면 본문에 없다: %s"
                % (lens.get("label"), "·".join(items), "·".join(absent)))
    m8 = len(contradictions)

    # ── 참고치(목표를 걸지 않은 것) ─────────────────────────────────
    fields = {}
    for p in ("/entry/newcase", "/design"):
        b = _main_of(get(p)[1])
        ins = re.findall(r"<input[^>]*>", b)
        visible = [i for i in ins if 'type="hidden"' not in i and 'type="submit"' not in i]
        fields[p] = len(visible) + b.count("<select") + b.count("<textarea")

    return {
        "M1_screens": m1,
        "M2_broken_guide_links": m2,
        "M2_detail": m2_broken,
        "M3_raw_stars": m3,
        "M4_raw_backticks": m4,
        "M3_detail": per_screen,
        "M5_home_unlinked_screens": m5,
        "M5_detail": m5_unlinked,
        "M6_map_screens": m6,
        "M6_detail": m6_live,
        "M7_entry_screens": m7,
        "M7_detail": m7_screens,
        "M8_contradictions": m8,
        "M8_detail": contradictions,
        "M9_numbers_without_source": m9,
        "M9_detail": m9_screens,
        "fields": fields,
    }


# PRD가 추적하는 지표 ↔ 사람이 읽는 이름. PRD 표의 행 이름이 이 순서·이름과 같아야 한다.
METRIC_LABELS = (
    ("M1_screens", "사용자가 세는 화면"),
    ("M2_broken_guide_links", "안내 화면이 가리키는데 열리지 않는 링크"),
    ("M3_raw_stars", "화면에 날것으로 나가는 별표"),
    ("M4_raw_backticks", "화면에 날것으로 나가는 백틱"),
    ("M5_home_unlinked_screens", "홈 본문이 링크하지 않는 1층 화면"),
    ("M6_map_screens", "같은 산출물 27행을 각자 내는 자료 지도 화면"),
    ("M7_entry_screens", "기입이 흩어진 화면"),
    ("M8_contradictions", "본문이 자기 말을 뒤집는 곳"),
    ("M9_numbers_without_source", "수를 내면서 출처로 가는 길이 없는 화면"),
)


def main() -> int:
    r = measure()
    out = io.StringIO()
    w = lambda s="": print(s, file=out)
    w("콘솔 정보구조 실측 — 기준은 디스크의 코드(TestClient), 본문은 <main> 안쪽")
    w()
    for key, label in METRIC_LABELS:
        w("%-3s %-44s %6d" % (key.split("_")[0], label, r[key]))
    w()
    w("열리지 않는 링크 %d개:" % r["M2_broken_guide_links"])
    for h in r["M2_detail"]:
        w("   " + h)
    w()
    w("날것 마크다운 화면별:")
    for p, d in r["M3_detail"].items():
        w("   %-12s 별표 %4d · 백틱 %4d" % (p, d["stars"], d["backticks"]))
    w()
    w("홈이 링크하지 않는 화면 %d개:" % r["M5_home_unlinked_screens"])
    for p in r["M5_detail"]:
        w("   " + p)
    w()
    w("자기 모순 %d건:" % r["M8_contradictions"])
    for s in r["M8_detail"]:
        w("   " + s)
    w()
    w()
    w("수를 내면서 출처로 가는 길이 없는 화면 %d개:" % r["M9_numbers_without_source"])
    for p2 in r["M9_detail"]:
        w("   " + p2)
    w()
    w("참고 — 보이는 입력 칸: " + " · ".join(
        "%s %d" % (k, v) for k, v in r["fields"].items()))
    # 윈도 콘솔은 cp949다 — 한글·장붙임표를 그대로 쓰면 깨진다(리포 환경 특성).
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.stdout.write(out.getvalue())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
