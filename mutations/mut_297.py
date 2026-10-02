"""297차 뮤테이션 — 표시 위생 가드(test_297cha · test_294cha 둘)를 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 297
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', 'test_webapp.py',
                              '-q', '-x', '-k', '294cha or 297cha'], capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
W = 'webapp.py'
C = 'consulting_package.py'
B = 'build_site.py'
I = 'measure_console_ia.py'
G = os.path.join('webapp_templates', 'guide.html')
P = 'PRD_콘솔_UIUX재설계_20261002.md'
NL = chr(10)
M = [
 # ── 🔴 렌더 훅을 떼거나 무력화 ──────────────────────────────────────
 ("M1 훅 삭제", W, 'templates.env.finalize = _render_inline', '# 훅 없음'),
 ("M2 문자열을 건너뜀", W,
  '    if isinstance(value, str):' + NL + '        return Markup(bs.md(value))',
  '    if False:' + NL + '        return Markup(bs.md(value))'),
 ("M3 감싸지 않음(이중 이스케이프)", W, '        return Markup(bs.md(value))', '        return bs.md(value)'),
 # 🔴 M4는 **코드 줄만** 지운다 — 주석의 같은 낱말은 남는다(그 구멍이 놓침의 원인이었다)
 ("M4 안전 표시 값도 변환", W,
  '    if hasattr(value, "__html__"):' + NL + '        return value' + NL, ''),
 ("M5 문자열 검사를 없앰", W, '    if isinstance(value, str):', '    if value is not None:'),
 ("M6 다른 렌더로 바꿈", W, '        return Markup(bs.md(value))', '        return Markup(str(value))'),
 # ── 🔴 치수 표기를 깨뜨림 ───────────────────────────────────────────
 ("M7 단일 별표 이탤릭 추가", B,
  '    r"|~~(.{1,200}?)~~"                              # ~~취소선~~ (153차)',
  '    r"|~~(.{1,200}?)~~"                              # ~~취소선~~ (153차)' + NL
  + '    r"|[*](.{1,200}?)[*]"'),
 # ── 🔴 자리표시자 규칙을 무력화 ─────────────────────────────────────
 ("M8 규칙 한 곳 제거(카드)", G, '<{% if "{" in s.path %}div{% else %}a href="{{ s.path }}"{% endif %}',
  '<a href="{{ s.path }}"'),
 ("M9 규칙 다른 곳 제거(목록)", G,
  '{% if "{" in s.path %}<span style="color:var(--mut)">{{ s.path }} — 코드를 골라야 열린다</span>{% else %}<a href="{{ s.path }}">{{ s.path }}</a>{% endif %}',
  '<a href="{{ s.path }}">{{ s.path }}</a>'),
 ("M10 사유 문장 삭제", G, ' — 코드를 골라야 열린다', ''),
 ("M11 판정을 뒤집음", G, '{% if "{" in s.path %}<span', '{% if "}" not in s.path %}<span'),
 # ── 🔴 공백 문장을 다시 상수로 ──────────────────────────────────────
 ("M12 파생을 상수로", C, '    _nd = screen_stage_map()["needs_decision"]', '    _nd = []'),
 ("M13 항목이 생겨도 안 적음", C, '    if _nd:' + NL + '        _nd_tail = (',
  '    if False:' + NL + '        _nd_tail = ('),
 ("M14 비었는데 확인 필요라 적음", C,
  '        _nd_tail = "📌**모든 화면이 코드를 적는다** — 남은 것이 없다"',
  '        _nd_tail = "⚠️**확인 필요**로 남아 있다"'),
 ("M15 항목 목록을 안 적음", C, '% (len(_nd), " · ".join("`%s`" % x for x in _nd))',
  '% (len(_nd), "여럿")'),
 # ── 🔴 렌즈 라벨을 되돌림 ───────────────────────────────────────────
 ("M16 라벨을 없는 축으로", C, '("축", "/axes", "단계·플랫폼·기능·기입 — 산출물을 묶는 네 축"),',
  '("4축", "/axes", "입지·설계·운영·경제성 — 엔진이 계산하는 축"),'),
 # ── 🔴 기준선·상태를 손으로 고침 ────────────────────────────────────
 ("M17 M3 상태를 미착수로", P, '| M3 | 화면에 날것으로 나가는 별표 | 552 | 0 | 완료 297차 |',
  '| M3 | 화면에 날것으로 나가는 별표 | 552 | 0 | 미착수 |'),
 ("M18 M2 상태를 미착수로", P, '| M2 | 안내 화면이 가리키는데 열리지 않는 링크 | 8 | 0 | 완료 297차 |',
  '| M2 | 안내 화면이 가리키는데 열리지 않는 링크 | 8 | 0 | 미착수 |'),
 ("M19 M8 상태를 미착수로", P, '| M8 | 본문이 자기 말을 뒤집는 곳 | 2 | 0 | 완료 297차 |',
  '| M8 | 본문이 자기 말을 뒤집는 곳 | 2 | 0 | 미착수 |'),
 ("M20 통일 기록 삭제", P, '🔴 **M3·M4 통일(297차)**', '📌 측정 정리(297차)'),
 # ── 🔴 측정 상태를 되돌림(수로는 구별되지 않는다) ───────────────────
 ("M21 측정 상태를 빈 폼으로", I,
  '        t = _text_of(get(RESULT_SAMPLES.get(p, p))[1])', '        t = _text_of(get(p)[1])'),
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
