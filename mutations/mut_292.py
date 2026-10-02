"""292차 뮤테이션 — `/design` ★결정(D1·D3·D18) 가드를 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 292
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-x', '-k', '291cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
C = 'consulting_package.py'
BD = os.path.join('webapp_templates', 'basic_design.html')
M = [
 # ── 🔴 ★결정을 지움(코드를 템플릿에서 뗀다) ────────────────────────
 ("M1 D1을 템플릿에서 뗌", BD, '<h2>D1 입지 진단 — 재해 조건</h2>', '<h2>입지 진단 — 재해 조건</h2>'),
 ("M2 D3을 템플릿에서 뗌", BD, '<h2>D3 설계 대안 — 조건을 통과하는 규격</h2>',
  '<h2>설계 대안 — 조건을 통과하는 규격</h2>'),
 ("M3 D18을 템플릿에서 뗌", BD, '<h2>D18 인허가 체크리스트 — 착공 전 확인</h2>',
  '<h2>인허가 체크리스트 — 착공 전 확인</h2>'),
 # ── 🔴 결정 밖의 코드를 끼워 넣음 ───────────────────────────────────
 ("M4 D6을 임의로 추가", BD, '<h2>개산 — 참고 금액</h2>', '<h2>D6 개산 — 참고 금액</h2>'),
 ("M5 D2를 임의로 추가", BD, '<h2>D3 설계 대안', '<h2>D2 D3 설계 대안'),
 # ── 🔴 파생을 끊음 ──────────────────────────────────────────────────
 ("M6 템플릿을 안 읽음", C, '        codes = _template_codes(tpl) if tpl else []',
  '        codes = [] if s["path"] == "/design" else (_template_codes(tpl) if tpl else [])'),
 ("M7 /design에 코드를 손으로 박음", C, '        tpl = tpls.get(s["path"], "")',
  '        tpl = tpls.get(s["path"], "")' + chr(10) +
  '        if s["path"] == "/design": tpl = ""'),
 ("M8 단계를 손으로 달음", C, '        stages = [st for st in STAGE_ORDER',
  '        stages = ["②품질설계"] if s["path"] == "/design" else [st for st in STAGE_ORDER'),
 # ── 🔴 확인 필요 규칙 자체를 없앰(다음 화면이 안 걸린다) ────────────
 ("M9 확인 필요 계단 삭제", C, '    "three": "확인 필요 — 산출물을 내는데 코드를 적지 않는다",',
  '    "three": "단계 밖 — 지도·안내",'),
 ("M10 needs_decision 판정 삭제", C,
  '            "needs_decision": (not codes) and tier_of[s["path"]] == SCREEN_NEEDS_DECISION,',
  '            "needs_decision": False,'),
 ("M11 확인 필요 키를 바꿈", C, 'SCREEN_NEEDS_DECISION: str = "three"', 'SCREEN_NEEDS_DECISION: str = "none"'),
 # ── 🔴 집계가 결정을 반영하지 않음 ──────────────────────────────────
 ("M12 단계 안 수 고정", C, '"in_stage": sum(1 for r in rows if r["in_stage"]),', '"in_stage": 5,'),
 ("M13 단계 밖 수 고정", C, '"out_of_stage": sum(1 for r in rows if not r["in_stage"]),', '"out_of_stage": 16,'),
 ("M14 ①공종설계 역방향 비움", C, '                 "screens": [r["path"] for r in rows if st in r["stages"]]}',
  '                 "screens": [r["path"] for r in rows if st in r["stages"] and "design" not in r["path"]]}'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
