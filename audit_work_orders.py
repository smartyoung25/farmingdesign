"""WO 형식 검사기 — docs/work-orders/의 작업지시서가 스킬 양식을 지키는가 (2026-09-28, 247차 · WO-002)

목적: `dev-work-order-writer` 스킬(.claude/skills/dev-work-order-writer/SKILL.md)의
  Verification Checklist 가운데 **기계로 판정할 수 있는 항목**만 본다.
  리포 적용 방식·이견은 docs/work-orders/README.md 한 곳에 있다.

규칙(R1~R8은 WO-002 6절 · R9는 251차 사용자 지시 — WO 없이 추가, 256차 명시):
  R1 템플릿 9절이 순서대로 있고 비어 있지 않다(「해당 없음」 뒤에는 이유)
  R2 수용기준마다 「(확인:」이 있고 금지 표현이 없다
  R3 3절 「제외」 항목이 1개 이상
  R4 작업 단위 1~7개, 각각 「완료 조건:」
  R5 코드 블록 안에 함수·클래스 정의나 import 줄이 없다(Iron Law 7)
  R6 헤더 — 제목 번호 = 파일명 번호 · 작성일 · 작업 유형 6종 · 선행 지시서 실재
  R7 수정 지시서(-fixK)는 원 지시서가 실재한다
  R8 README 색인과 폴더가 서로 빠짐없이 대응한다
  R9 개인 이름·내부 식별자가 없다 — 표시 코드(C*·A*·S*·V*)로 쓴다(251차, 사용자 지시
     「개인 이름은 무기명으로 처리」). 판정은 `case_display.audit` 그대로(제2의 명단 금지)

자동화 경계: 이 검사가 「통과」라고 해서 WO가 옳다는 뜻이 아니다 — 수용기준이 목적을
  실제로 덮는지, 가정이 타당한지는 사람(또는 레드팀)이 본다.

read-only. 엔진 계층(smartfarm_engine·build_site)은 이 모듈을 import하지 않는다 —
  감사자이지 계산 참여자가 아니다(audit_traceability와 같은 원칙).

실행: python audit_work_orders.py   (종료 코드 PASS=0, FAIL=1 · 파일을 쓰지 않는다)
"""
import io
import os
import re
import sys

import case_display as cdsp

ROOT = os.path.dirname(os.path.abspath(__file__))
WO_DIR = os.path.join(ROOT, "docs", "work-orders")

SECTION_TITLES = ("목적", "배경·사용자", "범위", "입력·출력", "기술 조건",
                  "작업 단위", "수용기준", "제약·주의사항", "보고 형식")
WORK_TYPES = ("신규 기능", "버그 수정", "리팩터링", "자동화 스크립트", "데이터 처리", "테스트 보강")
# 스킬 Iron Law 2의 금지 표현. 「잘」은 낱말 안의 글자(잘못·잘라)를 잡지 않도록 홀로 선 것만 본다.
#   256차(레드팀 30회차 B8): 붙여 쓴 「잘된다」·「잘동작」도 잡고, 「잘못·잘라·잘린·잘려·잘랐·잘게」는 통과시킨다.
BANNED = (("잘", re.compile(r"(?<![가-힣])잘(?!못|라|린|려|랐|게)")),
          ("적절히", re.compile("적절히")),
          ("원활하게", re.compile("원활하게")),
          ("빠르게", re.compile("빠르게")),
          ("깔끔하게", re.compile("깔끔하게")),
          ("사용자 친화적", re.compile(r"사용자\s*친화적")),
          ("정상 동작", re.compile(r"정상\s*동작")),
          ("문제없이", re.compile(r"문제\s*없이")))
ID_RE = r"WO-\d{3}(?:-fix\d+)?"
FILE_RE = re.compile(r"^(" + ID_RE + r")_.+\.md$")
CODE_LINE = re.compile(r"^\s*(def |async def |class |function |import |from \S+ import )")
NA_OK = re.compile(r"해당\s*없음\s*(—|–|-|:|\()\s*\S")
# 256차: 「(확인: )」처럼 확인 방법이 빈 것도 확인 방법이 없는 것이다
CONFIRM_OK = re.compile(r"\(확인:\s*[^)\s]")
# 256차: 선택되지 않은 분기의 기준 — 「(ⓐ 해당 없음 — ⓑ 선택)」. 체크하지 않고 「해당 없음」으로 센다
NA_CRIT = re.compile(r"^\([^)]*해당\s*없음\s*—[^)]*\)")


def parse_wo(text):
    """WO 마크다운 → 헤더·절·작업 단위·수용기준. 판정하지 않고 읽기만 한다."""
    text = text.replace("\r\n", "\n")
    lines = text.split("\n")
    m = re.match(r"^# 작업지시서 (" + ID_RE + r"): (.+)$", lines[0] if lines else "")
    head = {}
    for ln in lines[1:12]:
        hm = re.match(r"^- (작성일|작업 유형|선행 지시서): (.*)$", ln)
        if hm:
            head[hm.group(1)] = hm.group(2).strip()
    sections, order, cur = {}, [], None
    in_code = False
    code_lines = []
    for ln in lines:
        if ln.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(ln)
            continue
        sm = re.match(r"^## (\d+)\. (.+)$", ln)
        if sm:
            cur = int(sm.group(1))
            order.append(cur)
            sections[cur] = {"title": sm.group(2).strip(), "body": []}
            continue
        if cur is not None:
            sections[cur]["body"].append(ln)
    body = lambda n: sections.get(n, {}).get("body", [])
    tasks = [ln.strip() for ln in body(6) if re.match(r"^- T\d+:", ln)]
    criteria = []
    for ln in body(7):
        cm = re.match(r"^\s*- \[( |x|X)\] (.+)$", ln)
        if cm:
            criteria.append({"text": cm.group(2).strip(), "checked": cm.group(1) != " ",
                             "na": bool(NA_CRIT.match(cm.group(2).strip()))})
    return {
        "id": m.group(1) if m else None,
        "title": m.group(2).strip() if m else None,
        "date": head.get("작성일"), "type": head.get("작업 유형"), "prereq": head.get("선행 지시서"),
        "order": order,
        "sections": {n: {"title": s["title"], "body": "\n".join(s["body"]).strip()}
                     for n, s in sections.items()},
        "tasks": tasks,
        "criteria": criteria,
        "n_criteria": len(criteria),
        "n_checked": sum(1 for c in criteria if c["checked"]),
        "n_na": sum(1 for c in criteria if c["na"]),
        "n_applicable": sum(1 for c in criteria if not c["na"]),
        "n_confirm_needed": text.count("[확인 필요"),
        "code_lines": code_lines,
    }


def _exclusions(scope_body):
    """3절에서 「제외」 줄 아래 들여쓴 항목(또는 같은 줄 콜론 뒤 내용)을 모은다."""
    out, on = [], False
    for ln in scope_body.split("\n"):
        if re.match(r"^- 제외", ln):
            on = True
            tail = ln.split(":", 1)[1].strip() if ":" in ln else ""
            if tail:
                out.append(tail)
            continue
        if on:
            if re.match(r"^\s+- \S", ln):
                out.append(ln.strip()[2:])
            elif re.match(r"^- ", ln):
                on = False
    return out


def check_wo(text, name, known_ids):
    """문제 목록을 돌려준다. 빈 목록이면 기계 규칙 통과."""
    p = parse_wo(text)
    probs = []
    fm = FILE_RE.match(name)
    # R6 헤더
    if not p["id"]:
        probs.append("R6 제목 줄이 「# 작업지시서 WO-NNN: 작업명」 형식이 아니다")
    elif not fm or fm.group(1) != p["id"]:
        probs.append(f"R6 제목 번호 {p['id']}와 파일명 {name}이 다르다")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", p["date"] or ""):
        probs.append("R6 작성일이 YYYY-MM-DD가 아니다")
    if p["type"] not in WORK_TYPES:
        probs.append(f"R6 작업 유형 「{p['type']}」이 6종({' / '.join(WORK_TYPES)}) 밖이다")
    pre = p["prereq"]
    if pre is None:
        probs.append("R6 선행 지시서 줄이 없다")
    elif not pre.startswith("없음"):
        refs = re.findall(ID_RE, pre)
        if not refs:
            probs.append(f"R6 선행 지시서 「{pre}」가 「없음」도 WO 번호도 아니다")
        for r in refs:
            if r not in known_ids:
                probs.append(f"R6 선행 지시서 {r}가 폴더에 없다")
    # R7 수정 지시서
    if p["id"] and "-fix" in p["id"]:
        base = p["id"].split("-fix")[0]
        if base not in known_ids:
            probs.append(f"R7 수정 지시서의 원 지시서 {base}가 폴더에 없다")
    # R1 9절
    if p["order"] != list(range(1, 10)):
        probs.append(f"R1 절 번호가 1~9 순서가 아니다: {p['order']}")
    for n, want in enumerate(SECTION_TITLES, 1):
        s = p["sections"].get(n)
        if not s:
            continue
        if not s["title"].startswith(want):
            probs.append(f"R1 {n}절 제목 「{s['title']}」이 「{want}」가 아니다")
        if not s["body"]:
            probs.append(f"R1 {n}절이 비어 있다 — 해당 없으면 「해당 없음 — 이유」를 쓴다")
        for ln in s["body"].split("\n"):
            # 「해당 없음」처럼 낫표로 인용한 것은 낱말을 가리키는 것이지 선언이 아니다
            bare = re.sub(r"「해당\s*없음」", "", ln)
            if re.search(r"해당\s*없음", bare) and not NA_OK.search(bare):
                probs.append(f"R1 {n}절 「해당 없음」 뒤에 이유가 없다")
    # R3 제외
    if not _exclusions(p["sections"].get(3, {}).get("body", "")):
        probs.append("R3 3절 「제외」 항목이 없다 — 이번에 하지 않는 것을 1개 이상 쓴다")
    # R4 작업 단위
    if not 1 <= len(p["tasks"]) <= 7:
        probs.append(f"R4 작업 단위가 {len(p['tasks'])}개다 — 1~7개(넘으면 WO를 나눈다)")
    for t in p["tasks"]:
        if "완료 조건:" not in t:
            probs.append(f"R4 「{t[:20]}…」에 완료 조건이 없다")
    # R2 수용기준
    if not p["criteria"]:
        probs.append("R2 수용기준이 0개다")
    for c in p["criteria"]:
        if not CONFIRM_OK.search(c["text"]):
            probs.append(f"R2 「{c['text'][:24]}…」에 확인 방법 「(확인: …)」이 없다")
        for word, rx in BANNED:
            if rx.search(c["text"]):
                probs.append(f"R2 「{c['text'][:24]}…」에 금지 표현 「{word}」가 있다")
    # R9 개인 이름 — 파일명과 본문 모두. 코드 ↔ 이름 매핑은 case_display.py에만 있다
    leaked = {**cdsp.audit(name), **cdsp.audit(text)}
    if leaked:
        # 메시지가 이름을 되풀이하면 그 자체가 누출이다 — 해당 코드만 적는다
        probs.append(f"R9 개인 이름·내부 식별자 {len(leaked)}종이 있다(해당 코드 "
                     f"{sorted(set(cdsp.scrub(n) for n in leaked))}) — case_display 표시 코드로 쓴다")
    # R5 구현 코드
    bad = [ln.strip() for ln in p["code_lines"] if CODE_LINE.match(ln)]
    if bad:
        probs.append(f"R5 코드 블록에 구현 코드가 있다: 「{bad[0][:30]}」 — 인터페이스·입출력 예시만 쓴다")
    return probs


def _read(path):
    return io.open(path, encoding="utf-8").read()


def index_rows(readme_text):
    """README 색인 표 → [(번호, 파일명, 작업명, 차수, 선행, 상태)]"""
    rows = []
    for m in re.finditer(r"^\| \[(" + ID_RE + r")\]\(([^)]+)\) \| ([^|]+)\| ([^|]+)\| ([^|]+)\| ([^|]+)\|",
                         readme_text.replace("\r\n", "\n"), re.M):
        rows.append(tuple(x.strip() for x in m.groups()))
    return rows


def audit(folder=WO_DIR):
    """폴더 전체 검사. pass는 문제 0건이고 WO가 1건 이상일 때만 True."""
    res = {"folder": folder, "files": [], "problems": [], "index": [],
           "index_missing": [], "index_extra": [], "pass": False}
    if not os.path.isdir(folder):
        res["problems"].append(f"폴더가 없다: {folder}")
        return res
    names = sorted(f for f in os.listdir(folder) if FILE_RE.match(f))
    if not names:
        res["problems"].append("WO 파일이 0건이다")
    known = {FILE_RE.match(f).group(1) for f in names}
    for f in names:
        t = _read(os.path.join(folder, f))
        pr = check_wo(t, f, known)
        res["files"].append({"name": f, "id": FILE_RE.match(f).group(1), "parsed": parse_wo(t), "problems": pr})
        res["problems"] += [f"{f}: {x}" for x in pr]
    readme = os.path.join(folder, "README.md")
    if not os.path.exists(readme):
        res["problems"].append("R8 README.md(색인)가 없다")
    else:
        rt = _read(readme)
        if cdsp.audit(rt):
            res["problems"].append(f"R9 README.md에 개인 이름·내부 식별자 {len(cdsp.audit(rt))}종이 있다(해당 코드 "
                                   f"{sorted(set(cdsp.scrub(n) for n in cdsp.audit(rt)))})")
        rows = index_rows(rt)
        res["index"] = rows
        listed = {r[1] for r in rows}
        res["index_missing"] = sorted(set(names) - listed)
        res["index_extra"] = sorted(listed - set(names))
        for f in res["index_missing"]:
            res["problems"].append(f"R8 {f}가 README 색인에 없다")
        for f in res["index_extra"]:
            res["problems"].append(f"R8 색인의 {f}가 폴더에 없다")
        for r in rows:
            if not r[1].startswith(r[0] + "_"):
                res["problems"].append(f"R8 색인 번호 {r[0]}와 링크 {r[1]}이 다르다")
    res["pass"] = bool(names) and not res["problems"]
    return res


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    r = audit()
    print("WO 형식 검사 — 스킬 체크리스트 중 기계 판정 가능한 항목만 본다(통과 ≠ 내용이 옳음)")
    for f in r["files"]:
        p = f["parsed"]
        tag = "OK " if not f["problems"] else "ERR"
        print(f"  {tag} {f['name']} — 수용기준 확인 {p['n_checked']}/{p['n_applicable']}"
              f"{' (해당 없음 ' + str(p['n_na']) + ')' if p['n_na'] else ''} · "
              f"작업 단위 {len(p['tasks'])} · [확인 필요] {p['n_confirm_needed']}")
    for x in r["problems"]:
        print(f"  - {x}")
    if r["pass"]:
        print(f"WO 형식 검사: PASS ({len(r['files'])}건)")
    else:
        print(f"WO 형식 검사: FAIL (문제 {len(r['problems'])}건)")
    return 0 if r["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
