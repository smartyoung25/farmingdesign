# -*- coding: utf-8 -*-
"""품셈 PDF 제7장 제2·3절(인쇄 p.138~162)에서 64계수를 **텍스트층으로** 재추출한다.

113차는 25쪽을 렌더링해 **육안**으로 64종을 전수 대조했다. 24회차 레드팀이
이 PDF의 해당 구간에 **Type0 텍스트층이 살아 있음**을 찾아내, 같은 대조를
**기계로 재현**할 수 있게 됐다. 이 모듈이 그 경로다.

왜 바로 읽히지 않는가
    폰트가 ToUnicode 없이 임베드된 서브셋(`PGFPCD+Batang` / `PGHBIG+Gulim`)이라
    `pdfplumber`가 `(cid:N)`만 내준다. 다만 `CIDToGIDMap=Identity`라 **cid == GID**이고,
    서브셋의 glyph 아웃라인을 **시스템 Batang/Gulim의 cmap**과 해시 대조하면
    GID→유니코드가 복원된다(모호 0건).

한계(중요)
    · 한글 일부는 시스템 폰트와 아웃라인이 달라 복원되지 않는다(`\ufffd`로 남는다).
      **숫자·소수점은 전량 복원**되므로 계수 대조에는 지장이 없다.
    · 따라서 이 모듈은 **품목명이 아니라 (공종, 순번, 계수 시퀀스)로 대조**한다.
    · 시스템 폰트(`C:\\Windows\\Fonts\\batang.ttc`·`gulim.ttc`)가 있어야 한다.
      없으면 `FontsUnavailable`을 올린다 — 호출부가 skip 처리한다.
    · 부록1 공사일보와 인쇄 p.109·115~137은 **Type3 벡터/스캔**이라 이 경로가 통하지
      않는다(116~124차가 그 구간에서 읽은 수치는 여전히 육안 판독 근거다).
"""
from __future__ import annotations

import functools
import hashlib
import os
import re

PDF_PATH = os.path.join("시설평가", "202201_스마트팜 표준화_품셈.pdf")
PRINT_TO_PDF = 24                      # 1-based PDF = 인쇄 + 24 → 0-based = 인쇄 + 23

# 원문 차례(목차 PDF 19 = 120차 확인). 엔진 선언 순서와는 다르다(120차 ⑦).
SECTION_PAGES = [
    ("철골공사", 138, 140),
    ("알루미늄공사", 141, 143),
    ("온실피복공사", 144, 145),
    ("천창개폐장치공사", 146, 150),
    ("수평스크린공사", 151, 155),
    ("측벽스크린공사", 156, 157),
    ("행잉거터공사", 158, 159),
    ("철골공사(비닐·파이프자재)", 160, 161),
    ("온실피복공사(비닐)", 162, 162),
]

_CID = re.compile(r"^\(cid:(\d+)\)$")
_ITEM_HEAD = re.compile(r"^\s*(\d{1,2})\s*\.")      # "1. 스틸돌리"
_UNIT_TAIL = re.compile(r"\(\s*[^)]{0,6}당\s*\)")   # "(개소당)" · "(㎡당)" — 품목 시작 줄
_NUM = re.compile(r"^\d+(?:\.\d+)?$")


class FontsUnavailable(RuntimeError):
    """시스템 Batang/Gulim이 없어 cid→유니코드 복원을 할 수 없다."""


def _outline_sig(glyphset, gname):
    from fontTools.pens.recordingPen import RecordingPen

    if gname not in glyphset:
        return None
    pen = RecordingPen()
    try:
        glyphset[gname].draw(pen)
    except Exception:
        return None
    return hashlib.sha1(repr(pen.value).encode()).hexdigest() if pen.value else None


@functools.lru_cache(maxsize=1)
def _system_index():
    """시스템 Batang·Gulim의 (아웃라인 해시 → 유니코드) 사전."""
    from fontTools.ttLib import TTCollection

    idx = {}
    for name in ("batang.ttc", "gulim.ttc"):
        path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name)
        if not os.path.exists(path):
            raise FontsUnavailable(path)
        font = TTCollection(path).fonts[0]
        gs, cm = font.getGlyphSet(), font.getBestCmap()
        for uni, gname in cm.items():
            sig = _outline_sig(gs, gname)
            if sig:
                idx.setdefault(sig, set()).add(uni)
    return {k: frozenset(v) for k, v in idx.items()}


@functools.lru_cache(maxsize=8)
def _map_for_fontfile(data: bytes):
    """서브셋 폰트 바이트 → {cid: 유니코드}. 같은 폰트가 여러 쪽에 쓰이므로 캐시한다."""
    from fontTools.ttLib import TTFont
    import io as _io

    sysidx = _system_index()
    sub = TTFont(_io.BytesIO(data))
    gs = sub.getGlyphSet()
    mp = {}
    for gid, gname in enumerate(sub.getGlyphOrder()):
        sig = _outline_sig(gs, gname)
        if sig is None:
            continue
        hit = sysidx.get(sig)
        if hit:
            mp[gid] = sorted(hit)[0]              # 모호 0건이 실측(24회차·125차)
    return mp


def build_cid_map(reader_page):
    """임베드 서브셋 폰트를 꺼내 (폰트 리소스명 → {cid: 유니코드})를 만든다."""
    from fontTools.ttLib import TTFont
    import io as _io

    out = {}
    for key, ref in reader_page["/Resources"]["/Font"].items():
        f = ref.get_object()
        if f.get("/Subtype") != "/Type0":
            continue
        desc = f["/DescendantFonts"][0].get_object()
        if str(desc.get("/CIDToGIDMap")) != "/Identity":
            continue                                  # Identity가 아니면 이 경로를 쓰지 않는다
        fd = desc["/FontDescriptor"]
        if "/FontFile2" not in fd:
            continue
        out[str(key)] = _map_for_fontfile(bytes(fd["/FontFile2"].get_data()))
    return out


def _decode(ch, cidmaps, fontkey_by_name):
    m = _CID.match(ch["text"])
    if not m:
        return ch["text"]
    key = fontkey_by_name.get(ch["fontname"])
    uni = cidmaps.get(key, {}).get(int(m.group(1))) if key else None
    return chr(uni) if uni else "\ufffd"


def extract_page(pdf, reader, print_page):
    """한 쪽에서 [(순번, 계수 시퀀스)] 를 뽑는다.

    계수는 표의 **수량 열**(헤더 `수 량`의 x 위치)에 있는 값만 취한다 —
    규격 열의 `6M`·`5TON`이나 [주]의 `3%`·`8시간`이 섞이지 않게 한다.
    """
    i = print_page + PRINT_TO_PDF - 1                 # 0-based
    page = pdf.pages[i]
    cidmaps = build_cid_map(reader.pages[i])
    # fontname(PGFPCD+Batang) → 리소스 키(/TT4) 대응
    fontkey_by_name = {}
    for key, ref in reader.pages[i]["/Resources"]["/Font"].items():
        base = str(ref.get_object().get("/BaseFont") or "").lstrip("/")
        if base:
            fontkey_by_name[base] = str(key)

    chars = [c for c in page.chars]
    for c in chars:
        c["_u"] = _decode(c, cidmaps, fontkey_by_name)

    # 줄 단위로 묶는다
    lines = {}
    for c in chars:
        lines.setdefault(round(c["top"] / 3), []).append(c)
    ordered = [sorted(v, key=lambda c: c["x0"]) for _, v in sorted(lines.items())]

    # 품목 경계는 **표 헤더 줄**(`구 분 / 규 격 / 단 위 / 수 량`)로 잡는다.
    #   순번("1.")이나 단위 표기("(개소당)")로 잡으면 앞 글자가 복원되지 않은 줄에서
    #   경계를 놓친다(125차에 둘 다 실측으로 실패). 헤더는 품목당 정확히 한 번 나온다.
    #
    # 수량은 줄의 **마지막 숫자 토큰**이다. x 좌표로 열을 자르면 자릿수가 많은 값이
    #   왼쪽으로 삐져나와 잘린다 — `0.0003`의 첫 `0`이 열 좌단 밖이라 `0003`→3.0으로
    #   읽히는 오류를 125차에 실측했다(수량 열은 오른쪽 정렬이다).
    def is_header(row_text):
        return "분" in row_text and "위" in row_text and row_text.count("수") >= 1

    items, cur, collecting = [], None, False
    for row in ordered:
        text = "".join(c["_u"] for c in row).strip()
        if not text:
            continue
        if is_header(text):
            cur = [len(items) + 1, []]
            items.append(cur)
            collecting = True
            continue
        if text.startswith("[주]"):
            collecting = False          # [주] 안의 3%·8시간·할증률이 섞이지 않게
            continue
        if not collecting or cur is None:
            continue
        if _UNIT_TAIL.search(text):
            continue                    # 다음 품목의 이름 줄("10. 와이어 … (M당)")
        # 수량이 있는 줄은 **단위 열**을 달고 있다("… - 인 0.21" / "… hr 0.19").
        #   규격이 줄바꿈으로 떨어져 나온 조각("5TON")에서 5를 줍지 않게 한다(125차 실측).
        if "인" not in text and "hr" not in text:
            continue
        toks = [t for t in re.findall(r"\d+(?:\.\d+)?", text) if _NUM.match(t)]
        if toks:
            cur[1].append(float(toks[-1]))
    return [(n, v) for n, v in items if v]


# 제7장 제1절·조사 절의 제원 표(115·119차가 육안으로 읽은 것들).
#   같은 텍스트층 경로로 기계 재확인한다. 숫자는 Batang이라 전량 복원되고,
#   표 제목(YDIYGO120 서브셋)은 시스템에 없는 폰트라 복원되지 않는다.
TABLE_PAGES = {
    110: "표 7-2 유리온실 구역별 면적",
    112: "표 7-4·7-5 비닐온실 개요·구역별 면적",
    120: "표 7-7·7-8 부여 현장 개요·구역별 면적",
    122: "표 7-9 함평 현장 개요",
}


def page_lines(pdf, reader, print_page):
    """한 쪽의 복원 텍스트를 줄 단위로 돌려준다(미복원 글자는 U+FFFD)."""
    i = print_page + PRINT_TO_PDF - 1
    page = pdf.pages[i]
    cidmaps = build_cid_map(reader.pages[i])
    fontkey_by_name = {}
    for key, ref in reader.pages[i]["/Resources"]["/Font"].items():
        base = str(ref.get_object().get("/BaseFont") or "").lstrip("/")
        if base:
            fontkey_by_name[base] = str(key)
    lines = {}
    for c in page.chars:
        c["_u"] = _decode(c, cidmaps, fontkey_by_name)
        lines.setdefault(round(c["top"] / 3), []).append(c)
    out = []
    for _, row in sorted(lines.items()):
        text = "".join(c["_u"] for c in sorted(row, key=lambda c: c["x0"])).strip()
        if text:
            out.append(text)
    return out


def extract_tables():
    """{인쇄 쪽: [복원된 줄]} — 제원 표 쪽의 텍스트."""
    import pdfplumber
    from pypdf import PdfReader

    _system_index()
    out = {}
    reader = PdfReader(PDF_PATH)
    with pdfplumber.open(PDF_PATH) as pdf:
        for pp in sorted(TABLE_PAGES):
            out[pp] = page_lines(pdf, reader, pp)
    return out


def extract_notes():
    """64품목의 **[주] 항목**을 공종·순번별로 뽑는다.

    125차 파서는 [주]를 **버린다**(수량이 아니므로). 그런데 [주]에는 계수의
    **적용 조건**이 적혀 있다 — 공구손료 3%·재료량 설계수량 적용·장비 8시간 기준 등.
    이 함수가 그것을 기록으로 남긴다.

    ⚠️ 한글 일부는 복원되지 않아 `�`가 섞인다. 그래서 **문자열 그대로 쓰지 말고
    아래 `NOTE_RULES`처럼 복원되는 부분만으로 판정**해야 한다.
    """
    import pdfplumber
    from pypdf import PdfReader

    _system_index()
    out = []
    reader = PdfReader(PDF_PATH)
    with pdfplumber.open(PDF_PATH) as pdf:
        for cat, lo, hi in SECTION_PAGES:
            per_item = []
            for pp in range(lo, hi + 1):
                lines = page_lines(pdf, reader, pp)
                cur, in_note = None, False
                for text in lines:
                    if "분" in text and "위" in text and text.count("수") >= 1:
                        cur = []
                        per_item.append(cur)
                        in_note = False
                        continue
                    # 줄 앞에 세로쓰기 낱글자("품/셈/산/정")나 미복원 글자가 붙는 일이 있어
                    #   startswith로는 [주] 시작을 놓친다(127차 실측: 구동축 ①을 통째로
                    #   흘려 [2,3]으로 보였다). 앞머리 몇 글자 안에서 찾는다.
                    if "[주]" in text[:6] or any(ch in text.replace("[주]", "")[:4] for ch in _MARU):
                        in_note = True
                    if in_note and _UNIT_TAIL.search(text):
                        in_note = False     # 다음 품목 이름 줄에서 [주]가 끝난다
                        continue
                    if in_note and re.match(r"^-\s*\d{2,3}\s*-$", text):
                        in_note = False     # 쪽 꼬리말
                        continue
                    if in_note and cur is not None and len(text) > 2:
                        cur.append(text)    # 세로쓰기 낱글자("품/셈/산/정")는 버린다
            for n, notes in enumerate(per_item, 1):
                out.append((cat, n, notes))
    return out


# [주]에서 판정할 규칙 — 복원되는 조각만 쓴다(미복원 글자를 피한다).
NOTE_RULES = {
    "공구손료3%": "3%",          # "공구손료 및 경장비 … 기계경비는 인력품의 3%로 계상한다"
    "장비8시간": "8시간",         # "현장투입된 장비는 하루 8시간 작업 기준 …"
    "재료량설계수량": "설계수",     # "재료량은 설계수량을 적용한다"
}
# "별도 계상"은 "별"이 복원되지 않아 문자열로 못 잡는다 —
#   `계상한다`가 있고 `3%`가 없는 줄로 판정한다(공구손료 규정과 구분).
_MARU = "①②③④⑤⑥⑦⑧⑨"


def note_numbers(notes):
    """[주] 항목의 번호 시퀀스. 원문 번호 누락·중복을 드러낸다."""
    out = []
    for text in notes:
        # 줄 앞머리에 세로쓰기 낱글자("품/셈/산/정")나 미복원 글자가 붙는 일이 있어
        #   `startswith`로는 놓친다(127차 실측: 구동축 ①을 놓쳐 [2,3]으로 보였다).
        head = text.replace("[주]", "")[:4]
        for k, ch in enumerate(_MARU, 1):
            if ch in head:
                out.append(k)
                break
    return out


def classify_notes(rows=None):
    """{규칙: [(공종, 순번)]} — 어느 품목에 어떤 적용 조건이 붙었는가."""
    rows = rows if rows is not None else extract_notes()
    hit = {k: [] for k in NOTE_RULES}
    hit["별도계상"] = []
    for cat, no, notes in rows:
        blob = " ".join(notes)
        for key, needle in NOTE_RULES.items():
            if needle in blob:
                hit[key].append((cat, no))
        if any("계상한다" in t and "3%" not in t for t in notes):
            hit["별도계상"].append((cat, no))
    return hit


def extract_all():
    """(공종, 순번, 계수 시퀀스) 전량. 원문 차례 순서로 돌려준다."""
    import pdfplumber
    from pypdf import PdfReader

    _system_index()                                   # 폰트 없으면 여기서 올린다
    rows = []
    reader = PdfReader(PDF_PATH)
    with pdfplumber.open(PDF_PATH) as pdf:
        for cat, lo, hi in SECTION_PAGES:
            got = []
            for p in range(lo, hi + 1):
                got.extend(v for _, v in extract_page(pdf, reader, p))
            for n, vals in enumerate(got, 1):         # 쪽이 넘어가도 순번은 이어진다
                rows.append((cat, n, vals))
    return rows


if __name__ == "__main__":
    import io as _io

    out = []
    for cat, no, vals in extract_all():
        out.append("%-24s %2d  %s" % (cat, no, vals))
    _io.open("pumsem_extract_dump.txt", "w", encoding="utf-8").write("\n".join(out))
    print("추출 %d건 → pumsem_extract_dump.txt" % len(out))
