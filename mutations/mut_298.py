"""298차 뮤테이션 — 폼 봉인·문장 파생 가드(test_298cha · 294·297차)를 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 298
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py',
                              '-q', '-x', '-k', '294cha or 297cha or 298cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
W = 'webapp.py'
C = 'consulting_package.py'
I = 'measure_console_ia.py'
D = os.path.join('webapp_templates', 'basic_design.html')
NL = chr(10)
M = [
 # ── 🔴 봉인을 풀어 근거 필드를 다시 오염시킨다 ──────────────────────
 ("M1 봉인 조건 삭제", W, '    if isinstance(value, str) and ctx.name not in FORM_TEMPLATES:',
  '    if isinstance(value, str):'),
 ("M2 봉인 집합을 비움", W, '    return frozenset(out)', '    return frozenset()'),
 ("M3 집합을 손으로 적음", W, "    for q in sorted((ROOT / \"webapp_templates\").glob(\"entry_*.html\")):",
  "    return frozenset({'entry_site.html'})" + NL
  + "    for q in sorted((ROOT / \"webapp_templates\").glob(\"entry_*.html\")):"),
 ("M4 폼 조건을 느슨하게", W, '        if "<form" in t and (\'value="{{\' in t or "<textarea" in t):',
  '        if "<form" in t and "zzz" in t:'),
 ("M5 컨텍스트 데코레이터 제거", W, '@pass_context' + NL + 'def _render_inline(ctx, value):',
  'def _render_inline(ctx, value):'),
 ("M6 훅을 다른 함수로 재지정", W, 'templates.env.finalize = _render_inline',
  'templates.env.finalize = lambda v: v'),
 ("M7 안전 표시 건너뛰기 삭제", W,
  '    if hasattr(value, "__html__"):' + NL + '        return value' + NL, ''),
 # ── 🔴 기본설계 칸 봉인을 푼다 ──────────────────────────────────────
 ("M8 주소 칸 필터 삭제", D, "value=\"{{ bd.input['주소'] | e }}\"", "value=\"{{ bd.input['주소'] }}\""),
 ("M9 면적 칸 괄호 삭제", D,
  "value=\"{{ (bd.input['면적_m2'] if bd.input['면적_m2'] else '') | e }}\"",
  "value=\"{{ bd.input['면적_m2'] if bd.input['면적_m2'] else '' | e }}\""),
 # ── 🔴 문장을 반환보다 넓게 만든다 ──────────────────────────────────
 ("M10 완료를 단언", C,
  '        _nd_tail = ("📌**「확인 필요」로 분류된 화면은 없다** — 단계 안 %d · 단계 밖 %d이고, "',
  '        _nd_tail = ("📌**모든 화면이 코드를 적는다** — 남은 것이 없다. %d %d"' ),
 ("M11 수를 안 적음", C, '                    % (_ssm["in_stage"], _ssm["out_of_stage"]))',
  '                    % (0, 0))'),
 ("M12 파생을 상수로", C, '    _ssm = screen_stage_map()', '    _ssm = {"needs_decision": [], "in_stage": 0, "out_of_stage": 0}'),
 ("M13 남아있다 주장으로", C, '        _nd_tail = ("⚠️다만 **코드를 적지 않는 화면 %d곳**(%s)은 **확인 필요**로 남아 있다"',
  '        _nd_tail = ("⚠️다만 **코드를 적지 않는 화면 %d곳**(%s)이 있다"'),
 # ── 🔴 모순 규칙을 무력화 ───────────────────────────────────────────
 ("M14 남아있다 규칙 삭제", I, '            and "남아 있다" in gaps_text):', '            and "zzz" in gaps_text):'),
 ("M15 역방향 규칙 삭제", I,
  '    if ssm.get("out_of_stage") and ("모든 화면이 코드를 적는다" in gaps_text',
  '    if False and ("모든 화면이 코드를 적는다" in gaps_text'),
 ("M16 역방향을 둔하게", I, '"모든 화면이 코드를 적는다" in gaps_text', '"zzzz" in gaps_text'),
 ("M17 모순 집계를 박아 넣음", I, '    m8 = len(contradictions)', '    m8 = 0'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    nl = '\r\n' if '\r\n' in s else NL
    aa, bb = a.replace(NL, nl), b.replace(NL, nl)
    if s.count(aa) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(aa, bb, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
