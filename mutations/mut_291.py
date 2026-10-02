"""291차 뮤테이션 — 화면↔단계 가드(test_291cha)를 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 291
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-x', '-k', '291cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
C = 'consulting_package.py'
T = os.path.join('webapp_templates', 'service_flow.html')
CD = os.path.join('webapp_templates', 'case_detail.html')
M = [
 # ── 🔴 배정표를 저장함(파생을 버림) ─────────────────────────────────
 ("M1 코드를 손표로 대체", C, '        codes = _template_codes(tpl) if tpl else []',
  '        codes = ["D1"] if tpl else []'),
 ("M2 템플릿을 안 읽고 비움", C, '    found = {c for c in _re.findall(r"\\bD\\d{1,2}\\b", txt) if c in known}',
  '    found = set()'),
 ("M3 라우트 본문을 길이로 자름(긴 라우트 놓침)", C,
  "        end = marks[k + 1][0] if k + 1 < len(marks) else len(src)",
  "        end = min(pos + 900, marks[k + 1][0] if k + 1 < len(marks) else len(src))"),
 ("M4 템플릿 추출을 첫 건만", C, '            out.setdefault(path, hit.group(1))', '            pass'),
 # ── 🔴 단계를 손으로 달음 ───────────────────────────────────────────
 ("M5 단계를 임의로", C, '        stages = [st for st in STAGE_ORDER' + chr(10) + '                  if any(stage_of.get(c) == st for c in codes)]',
  '        stages = ["①공종설계"] if codes else []'),
 ("M6 단계 순서를 뒤집음", C, '        stages = [st for st in STAGE_ORDER',
  '        stages = [st for st in reversed(STAGE_ORDER)'),
 ("M7 역방향을 따로 만듦", C, '                 "screens": [r["path"] for r in rows if st in r["stages"]]}',
  '                 "screens": [r["path"] for r in rows]}'),
 # ── 🔴 확인 필요를 숨기거나 지어냄 ──────────────────────────────────
 ("M8 확인 필요를 단계 밖으로 숨김", C,
  '    "three": "확인 필요 — 산출물을 내는데 코드를 적지 않는다",', '    "three": "단계 밖 — 지도·안내",'),
 ("M9 확인 필요 목록 비움", C, '"needs_decision": [r["path"] for r in rows if r["needs_decision"]],',
  '"needs_decision": [],'),
 ("M10 /design에 코드를 지어냄", C, '        tpl = tpls.get(s["path"], "")',
  '        tpl = tpls.get(s["path"], "")' + chr(10) + '        if s["path"] == "/design": tpl = "case_detail.html"'),
 ("M11 화면에서 확인 필요 절 삭제", T, '아직 정하지 못한 화면', '참고'),
 # ── 🔴 집계를 틀리게 ────────────────────────────────────────────────
 ("M12 단계 안 수를 부풀림", C, '"in_stage": sum(1 for r in rows if r["in_stage"]),',
  '"in_stage": sum(1 for r in rows if r["in_stage"]) + 1,'),
 ("M13 단계 밖 수를 틀리게", C, '"out_of_stage": sum(1 for r in rows if not r["in_stage"]),',
  '"out_of_stage": 0,'),
 ("M14 in_stage 판정을 뒤집음", C, '"in_stage": bool(codes),', '"in_stage": True,'),
 # ── 🔴 템플릿이 바뀌면 따라가야 한다 ────────────────────────────────
 ("M15 케이스 상세에서 D코드 삭제", CD, 'D23 투자 실사 카드', 'D투자 실사 카드'),
 ("M16 케이스 상세에 없는 코드 추가", CD, '<div class="ph">D24 설계값', '<div class="ph">D2 D24 설계값'),
 # ── 🔴 ★결정 기록·경계 삭제 ────────────────────────────────────────
 ("M17 ★결정 기록 삭제", C, '"decided": "★사용자 결정 2026-10-02 — 화면 ↔ 단계는 **산출물 D를 경유**한다",',
  '"decided": "내부 정리",'),
 ("M18 「저장하지 않는다」 삭제", C, '🔴**배정표를 저장하지 않는다**', '📌배정표를 저장한다'),
 ("M19 「따라 바뀐다」 삭제", C, '템플릿이 바뀌면 매핑도 따라 바뀐다', '매핑은 고정이다'),
 ("M20 288차 공백을 다시 엶", C, '{"무엇": "화면 ↔ 단계 대응 — ✅291차에 닫혔다", "왜": (',
  '{"무엇": "화면 ↔ 단계 대응", "왜": ('),
 ("M21 화면에 판정 어휘", T, '<h2>화면 ↔ 단계 — 어느 화면이 어느 단계에 서나</h2>',
  '<h2>화면 ↔ 단계 — 권장 순서</h2>'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
