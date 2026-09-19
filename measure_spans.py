# -*- coding: utf-8 -*-
"""레지스트리 서술의 인라인 마크다운 스팬을 센다 — **재현 가능하게**.

🔴 왜 있는가(155차): 148차가 `md()`의 지원 범위를 정할 때 근거로 삼은 실측치
   *"굵게 1,887 · 코드 443 · 인용 130(23중첩)"*이 **코퍼스와 정규식을 적지 않아**
   레드팀 28회차에서 **「확인 불가」**로 분류됐다. 세는 규칙이 없으면 그 수는
   검산되지 않는다 — 131차 이래 이 리포가 반복해 배운 것이다.

   이 도구가 고정하는 것:
     ① **코퍼스** — `엔진데이터_레지스트리.json`을 로드해 얻는 **모든 문자열 값**
        (최상위 `as_of`·`note`·범례 포함. `constants`만 세면 수가 달라진다)
        ⚠️ 엔진의 `CAPEX_MAJOR_EVIDENCE_STATUS`를 **더하지 않는다** — 그 값은
        레지스트리에 이미 등재돼 있어 더하면 **같은 문자열을 두 번** 센다.
     ② **시점** — 기본은 `BASELINE_REV`(= `099e461`, 147차 커밋 = 148차 착수 시점).
        작업 트리를 재려면 `--rev WORKTREE`.
     ③ **정규식** — 아래 세 패턴. 인용 상한은 `--quote-max`(기본 80).

기본 실행은 148차 기준선(`--rev 099e461 --quote-max 80`)을 그대로 재현한다.
"""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
REG = "엔진데이터_레지스트리.json"

# 148차 기준선 — 이 둘이 **단일 출처**다(CLI 기본값도 여기서 온다).
#   147차 커밋 = 148차 착수 시점의 레지스트리. 인용 상한 80은 148차 스크립트와 같다.
BASELINE_REV = "099e461"
BASELINE_QUOTE_MAX = 80

BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)
CODE = re.compile(r"`([^`]+)`")


def quote_re(limit):
    """`*"인용"*` — 상한이 결과를 바꾼다. 148차가 이 값을 적지 않았다."""
    return re.compile(r'\*"[^"]{2,%d}"\*' % limit)


def strings_of(node, acc=None):
    """JSON 트리의 문자열 값 전량(키는 세지 않는다)."""
    acc = [] if acc is None else acc
    if isinstance(node, dict):
        for v in node.values():
            strings_of(v, acc)
    elif isinstance(node, list):
        for v in node:
            strings_of(v, acc)
    elif isinstance(node, str):
        acc.append(node)
    return acc


def load(rev=None):
    if rev in (None, "", "WORKTREE"):
        return json.load(open(os.path.join(ROOT, REG), encoding="utf-8"))
    out = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (rev, REG)],
                         capture_output=True)
    if out.returncode:
        raise SystemExit("git show 실패: %s" % out.stderr.decode("utf-8", "replace")[:200])
    return json.loads(out.stdout.decode("utf-8"))


def measure(rev=BASELINE_REV, quote_max=BASELINE_QUOTE_MAX):
    vals = strings_of(load(rev))
    QUOTE = quote_re(quote_max)
    bold = [m for v in vals for m in BOLD.finditer(v)]
    quotes = [m for v in vals for m in QUOTE.finditer(v)]
    return {
        "rev": rev or "WORKTREE",
        "quote_max": quote_max,
        "strings": len(vals),
        "chars": sum(len(v) for v in vals),
        "bold": len(bold),
        "code": sum(len(CODE.findall(v)) for v in vals),
        "quote": len(quotes),
        # 🔴 148차는 인용 수를 상한 80으로, 중첩 수를 상한 120으로 세어
        #   **두 정규식의 결과를 한 문장에 붙였다**(155차 발견). 여기서는
        #   중첩도 **같은 상한**으로 센다 — 그래야 두 수가 한 모집단에서 나온다.
        "quote_nested": sum(1 for m in quotes if "**" in m.group()),
        "bold_inner_star": sum(1 for m in bold if "*" in m.group(1)),
        "bold_multiline": sum(1 for m in bold if "\n" in m.group(1)),
        "bold_longest": max((len(m.group(1)) for m in bold), default=0),
        "odd_bold_strings": sum(1 for v in vals if v.count("**") % 2),
    }


def render(r):
    return (
        "코퍼스: 레지스트리 JSON 전체 문자열 · 시점 {rev} · 인용 상한 {quote_max}\n"
        "  문자열 {strings:,}개 · {chars:,}자\n"
        "  **굵게** {bold:,}  (내부 단일별표 {bold_inner_star} · 줄바꿈 {bold_multiline}"
        " · 최장 {bold_longest}자)\n"
        "  `코드`   {code:,}\n"
        '  *"인용"* {quote:,}  (안에 굵게를 품는 것 {quote_nested})\n'
        "  `**` 개수가 홀수인 문자열 {odd_bold_strings}\n".format(**r)
    )


def main():
    ap = argparse.ArgumentParser(description="레지스트리 마크다운 스팬 실측")
    ap.add_argument("--rev", default=BASELINE_REV,
                    help="측정 시점 커밋(기본 099e461 = 147차 커밋 = 148차 착수 시점). "
                         "작업 트리는 WORKTREE")
    ap.add_argument("--quote-max", type=int, default=BASELINE_QUOTE_MAX,
                    help="인용 패턴의 본문 상한(기본 80 — 148차 스크립트와 같다)")
    a = ap.parse_args()
    sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print(render(measure(a.rev, a.quote_max)))


if __name__ == "__main__":
    main()
