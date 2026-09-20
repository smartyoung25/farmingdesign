"""케이스 표시 계층 — 산출물에서 실명을 뺀다 (183차 신설)

**무엇인가**: 케이스 5건은 실제 농가·기관 이름을 달고 있다(농가명·농장주·기관명).
산출물은 팀과 공유되므로 **생성되는 HTML에는 실명을 싣지 않는다**.

🔴 **경계 — 내부 데이터는 손대지 않는다.**
- `cases/*.json`의 `case_id`·`title`, `smartfarm_engine.py`의 출처 표기,
  `엔진데이터_레지스트리.json`, 테스트 앵커는 **그대로**다. 이름은 **값이 아니라 출처**이고,
  바꾸면 **추적성이 끊긴다**(1절: 출처를 파일명·시트·행까지 병기한다).
- 따라서 이 모듈은 **표시·파일명 계층에서만** 동작한다. 내부 식별자 ↔ 표시 코드는
  `ALIASES`가 **1:1**로 고정한다.

🔴 **범위 — 「케이스」에 한정한다.**
`SmartFarm_근거대장.html`·`SmartFarm_CAPEX분해.html`에는 **실측 출처의 업체·농가 이름**이
남아 있다(한일그린텍·이두희·윤성호·공주장원리·당진이상근 등). 그것은 **케이스가 아니라
근거의 출처**이고, 가리면 근거대장이 근거대장이 아니게 된다 — **★사용자 결정으로 남긴다**.
"""
from __future__ import annotations

import hashlib as _hashlib
import re

# ─────────────────────────────────────────────────────────────
# 표시 별칭 — 코드는 순서, 라벨은 **식별에 필요한 것만**(작목·피복·형식·성격·지역)
#   🔴 지역은 남긴다: 설계하중·기상 조회의 근거라서 가리면 숫자를 읽을 수 없다.
#      행정구역명은 실명이 아니다.
# ─────────────────────────────────────────────────────────────
ALIASES = {
    "chuncheon":  {"code": "C1", "label": "토마토 · 유리 · 신규",
                   "region": "강원(춘천)", "kind": "4축"},
    "wonchaewon": {"code": "C2", "label": "토마토 · 유리 · 신규",
                   "region": "충남", "kind": "4축",
                   "note": "관통 회귀 기준 케이스"},
    "uminjae":    {"code": "C3", "label": "토마토 · 필름 · 신규(2023)",
                   "region": "충남 천안", "kind": "4축"},
    "yonggyun":   {"code": "C4", "label": "오이 · 4연동 · 자립형(2024)",
                   "region": "—", "kind": "부분"},
    "mulhyangki": {"code": "C5", "label": "증식온실 재축 · 리모델링(폭설복구)",
                   "region": "—", "kind": "부분"},
}

# 산출물에서 지워야 할 실명(한글)과 내부 식별자(로마자).
#   🔴 긴 이름부터 지운다 — `이용균`을 먼저 지우지 않으면 `용균`만 남아 흔적이 된다.
REAL_NAMES = ("물향기수목원", "이용균", "원채원", "우민재", "물향기", "용균")


def _order(names):
    return sorted(names, key=len, reverse=True)


def alias(case: dict) -> dict:
    """케이스 → 표시 정보.

    🔴 등재되지 않은 케이스(웹앱으로 새로 저장된 것 등)도 **이름을 쓰지 않는다** —
    `case_id`의 해시로 안정적인 코드를 만든다. 예외를 던지면 새 케이스를 저장하는
    흐름이 막히고, `case["title"]`로 물러서면 **실명이 그대로 나간다**.
    해시는 되돌릴 수 없고 같은 케이스에 늘 같은 코드를 준다.
    """
    cid = case.get("case_id")
    if not cid:
        raise ValueError("case_id가 없다 — 표시 코드를 만들 수 없다")
    if cid not in ALIASES:
        inp = case.get("input") or {}
        bits = [str(inp.get(k)) for k in ("crop", "cover") if inp.get(k)]
        return {"case_id": cid, "code": _fallback_code(cid),
                "label": " · ".join(bits) or "미등재 케이스",
                "region": str(inp.get("region") or "—"),
                "kind": "부분" if case.get("partial") else "4축",
                "title": "%s · %s" % (_fallback_code(cid),
                                      " · ".join(bits) or "미등재 케이스"),
                "unregistered": True}
    a = dict(ALIASES[cid])
    a["case_id"] = cid
    parts = [a["code"]]
    if a["region"] and a["region"] != "—":
        parts.append(a["region"])
    parts.append(a["label"])
    a["title"] = " · ".join(parts)
    return a


def _fallback_code(cid: str) -> str:
    """등재 전 케이스의 표시 코드 — **이름에서 만들지 않는다**(해시라 되돌릴 수 없다)."""
    return "CX-" + _hashlib.sha1(cid.encode("utf-8")).hexdigest()[:4]


def code(case: dict) -> str:
    return alias(case)["code"]


def scrub(text: str) -> str:
    """산출물 문자열에서 케이스 실명·내부 식별자를 **표시 코드로 바꾼다**.

    🔴 지우지 않고 **바꾼다** — 지우면 문장이 깨지고, 무엇을 가렸는지도 알 수 없다.
    🔴 **긴 이름부터** 바꾼다: `이용균`보다 `용균`을 먼저 바꾸면 `이C4`가 남는다.
    """
    if not text:
        return text
    out = text
    for cid in _order(ALIASES):
        out = out.replace(cid, ALIASES[cid]["code"])
    for nm in _order(_NAME_TO_CODE):
        out = out.replace(nm, _NAME_TO_CODE[nm])
    return out


_NAME_TO_CODE = {
    "원채원": "C2", "우민재": "C3", "이용균": "C4", "용균": "C4",
    "물향기수목원": "C5", "물향기": "C5",
}


def audit(text: str) -> dict:
    """산출물에 실명·식별자가 남았는지 센다(가드가 쓴다)."""
    found = {}
    for nm in list(REAL_NAMES) + list(ALIASES):
        n = len(re.findall(re.escape(nm), text or ""))
        if n:
            found[nm] = n
    return found
