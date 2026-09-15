"""source_refs 재검산기 — `exact` ref의 앵커가 원문에서 확인되는가.

138·139차 산물. `audit_traceability.py`의 `_ref_ok()`는 **파일 실재만** 보므로
"이 파일이 그 값의 출처다"라는 주장은 게이트 밖이었다. 이 모듈이 그 자리를 맡는다.

판독 규율(138차에 두 번 고쳤다):
  - PDF가 숫자를 **자간 공백으로 쪼개** 렌더한다(`3 70,315,435`) → 놓치면 과소 판정
  - 공백을 **통째로 지우면 인접한 두 숫자가 붙는다** → 과교정
  → 같은 줄에서 **x 간격 4px 안의 숫자 토큰만** 결합한다(132차에서 검증된 방식).

앵커가 문서에 인쇄돼 있지 않은 경우가 있다 — `known_total`이 **문서 총계가 아니라
"문서가 총계에서 뺀 행까지 포함한 재집계"**인 표본들이다(우민재·이두희·맹주연).
그런 ref는 note에 **재집계임을 선언**해야 하고, 이 모듈은 그 선언을 요구한다.

사용:
    python verify_refs.py            # 정적 검사(앵커 유무·선언 일관성)만
    python verify_refs.py --full     # 원문 16종을 열어 전수 재검산(느리다)
"""
from __future__ import annotations

import collections
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(ROOT, "엔진데이터_레지스트리.json")
DUMP = os.path.join(ROOT, "verify_refs_dump.txt")

# 견적 원문을 쓰는 상수 4종 — 법령 별표 계열은 범위 밖이다(138차와 같다)
TARGET = ("CAPEX_MAJOR_CASE_CHUNKS", "CAPEX_MAJOR_KNOWN_TOTALS",
          "ACTUALS_COUNT", "CAPEX_CATEGORY_OBSERVED_RANGE")

NUM = re.compile(r"\b\d{1,3}(?:,\d{3}){2,}\b")
TOK = re.compile(r"^[\d,]+$")
# note가 "이 앵커는 인쇄돼 있지 않다"를 선언하는 말들
RECOMPUTED = ("재집계", "인쇄돼 있지 않", "합계제외", "재현한다", "3성분 합")


def load_registry():
    return json.load(io.open(REGISTRY, encoding="utf-8"))["constants"]


def anchors_of(note):
    return sorted({int(m.group().replace(",", "")) for m in NUM.finditer(note or "")})


def exact_refs(consts=None):
    """[(상수, 파일, 앵커들, note)] — 대상 4상수의 exact ref 전량."""
    consts = consts or load_registry()
    out = []
    for k in TARGET:
        for r in consts[k].get("source_refs") or []:
            if r.get("match") != "exact":
                continue
            out.append((k, r["file"], anchors_of(r.get("note")), r.get("note") or ""))
    return out


def static_check(consts=None):
    """원문을 열지 않고 볼 수 있는 것: 앵커가 있는가 · 선언이 있는가."""
    problems = []
    for k, f, anchors, note in exact_refs(consts):
        if not anchors:
            problems.append((k, f, "대조 기준(앵커 금액)이 note에 없다 — 검산할 수 없다"))
    return problems


def _emit(s):
    out = set()
    for m in NUM.finditer(s):
        out.add(int(m.group().replace(",", "")))
    t = s.replace(",", "")
    if t.isdigit() and 6 <= len(t) <= 12:
        out.add(int(t))
    return out


def document_numbers(path):
    """(문서에서 읽은 정수 집합, 사유). 못 읽으면 (None, 사유) — 부재로 읽지 않는다."""
    ext = os.path.splitext(path)[1].lower()
    nums = set()
    try:
        if ext in (".xlsx", ".xlsm"):
            import openpyxl
            for data_only in (True, False):
                wb = openpyxl.load_workbook(path, data_only=data_only)
                for ws in wb.worksheets:
                    for row in ws.iter_rows():
                        for c in row:
                            v = c.value
                            if isinstance(v, (int, float)):
                                nums.add(int(round(v)))
                            elif isinstance(v, str):
                                nums |= _emit(v) | _emit(v.replace(" ", ""))
            return nums, "openpyxl 전 시트(수식본·캐시값본)"
        if ext == ".xls":
            sys.path.insert(0, ROOT)
            import chunking_lib_v2 as cl
            for _, rows in (cl._xls_sheets_lenient(path) or {}).items():
                for row in rows:
                    for v in row:
                        if isinstance(v, (int, float)):
                            nums.add(int(round(v)))
                        elif isinstance(v, str):
                            nums |= _emit(v)
            return nums, "관대 파싱(_xls_sheets_lenient)"
        if ext == ".pdf":
            import pdfplumber
            chars = 0
            with pdfplumber.open(path) as pdf:
                for pg in pdf.pages:
                    t = pg.extract_text() or ""
                    chars += len(t)
                    for m in NUM.finditer(t):
                        nums.add(int(m.group().replace(",", "")))
                    rows = collections.defaultdict(list)
                    for w in pg.extract_words():
                        rows[round(w["top"])].append(w)
                    for _, ws in rows.items():
                        ws.sort(key=lambda w: w["x0"])
                        cur = None
                        for w in ws:
                            if TOK.match(w["text"]):
                                if cur and w["x0"] - cur[2] < 4:
                                    cur = (cur[0] + w["text"], cur[1], w["x1"])
                                else:
                                    if cur:
                                        nums |= _emit(cur[0])
                                    cur = (w["text"], w["x0"], w["x1"])
                            else:
                                if cur:
                                    nums |= _emit(cur[0])
                                cur = None
                        if cur:
                            nums |= _emit(cur[0])
            if chars < 200:
                return None, "텍스트층이 사실상 비어 있다(%d자) — 스캔 개연" % chars
            return nums, "pdfplumber 텍스트 + 단어 x결합(%d자)" % chars
    except Exception as ex:                       # noqa: BLE001 — 실패는 실패로 기록
        return None, "읽기 실패: %r" % (ex,)
    return None, "지원하지 않는 형식(%s)" % ext


def full_check(consts=None):
    """원문을 열어 앵커를 찾는다. [(상수, 파일, 상태, 상세)]."""
    consts = consts or load_registry()
    cache, out = {}, []
    for k, f, anchors, note in exact_refs(consts):
        path = os.path.join(ROOT, f)
        if f not in cache:
            cache[f] = document_numbers(path)
        nums, why = cache[f]
        if nums is None:
            out.append((k, f, "UNK", why))
            continue
        missing = [a for a in anchors if a not in nums]
        if not missing:
            out.append((k, f, "OK", why))
            continue
        # 인쇄돼 있지 않은 앵커는 note가 **재집계임을 선언**해야 한다
        if any(w in note for w in RECOMPUTED):
            out.append((k, f, "RECOMPUTED", "인쇄 없음 %s — note가 재집계를 선언한다"
                        % [format(m, ",") for m in missing]))
        else:
            out.append((k, f, "MISS", "인쇄 없음 %s — note에 선언이 없다"
                        % [format(m, ",") for m in missing]))
    return out


def render(rows):
    tally = collections.Counter(st for _, _, st, _ in rows)
    lines = ["# source_refs 재검산 결과 (verify_refs.py)", "",
             "대상: %s의 exact ref %d건" % (" · ".join(TARGET), len(rows)),
             "결과: " + " · ".join("%s %d" % (k, v) for k, v in sorted(tally.items())), ""]
    for k, f, st, why in rows:
        lines.append("%-11s %-32s %s" % (st, k, f))
        lines.append("            %s" % why)
    return "\n".join(lines)


def main():
    consts = load_registry()
    problems = static_check(consts)
    if problems:
        for k, f, why in problems:
            print("STATIC %s %s — %s" % (k, f, why))
        return 1
    print("정적 검사 통과: exact ref 전부가 대조 기준(앵커)을 갖는다")
    if "--full" in sys.argv:
        rows = full_check(consts)
        text = render(rows)
        io.open(DUMP, "w", encoding="utf-8", newline="").write(text + "\n")
        print(text.split("\n")[3])
        print("스냅샷 저장: %s" % os.path.basename(DUMP))
    return 0


if __name__ == "__main__":
    sys.exit(main())
