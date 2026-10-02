"""294차 뮤테이션 — PRD 지표 가드(test_294cha 둘)를 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 294
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', 'test_webapp.py',
                              '-q', '-x', '-k', '294cha'], capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
P = 'PRD_콘솔_UIUX재설계_20261002.md'
C = 'measure_console_ia.py'
M = [
 # ── 🔴 기준선·목표를 손으로 고침 ────────────────────────────────────
 ("M1 기준선을 낮춰 적음", P, '| M3 | 화면에 날것으로 나가는 별표 | 576 | 0 |',
  '| M3 | 화면에 날것으로 나가는 별표 | 300 | 0 |'),
 ("M2 목표를 기준선과 같게", P, '| M2 | 안내 화면이 가리키는데 열리지 않는 링크 | 8 | 0 |',
  '| M2 | 안내 화면이 가리키는데 열리지 않는 링크 | 8 | 8 |'),
 ("M3 고치지 않고 완료로 적음", P, '| M1 | 사용자가 세는 화면 | 21 | 9 | 미착수 |',
  '| M1 | 사용자가 세는 화면 | 21 | 9 | 완료 294차 |'),
 ("M4 지표 행 하나 삭제", P, '| M8 | 본문이 자기 말을 뒤집는 곳 | 2 | 0 | 미착수 |\n', ''),
 ("M5 지표 이름을 바꿈", P, '| M6 | 같은 산출물 27행을 각자 내는 자료 지도 화면 |',
  '| M6 | 자료 화면 |'),
 ("M6 지표 번호를 어긋나게", P, '| M7 | 기입이 흩어진 화면 |', '| M9 | 기입이 흩어진 화면 |'),
 ("M7 상태 어휘를 늘림", P, '| M5 | 홈 본문이 링크하지 않는 1층 화면 | 3 | 0 | 미착수 |',
  '| M5 | 홈 본문이 링크하지 않는 1층 화면 | 3 | 0 | 진행 중 |'),
 ("M8 측정 명령 삭제", P, '`python measure_console_ia.py`', '측정기로 센다'),
 # ── 🔴 ★결정의 출처를 지움 ──────────────────────────────────────────
 ("M9 질문 배정 결정 삭제", P, '「셋 다 기본설계로」', '「내가 고른 배정」'),
 ("M10 범위 결정 삭제", P, '「구조도대로 전면(21→9)」', '「구조도안」'),
 ("M11 홈 갈래 결정 삭제", P, '「진행 중 사업장」이 위', '사업장이 위'),
 ("M12 결정 날짜 삭제", P, '★사용자 결정 2026-10-02 (구조도 확인 후',
  '결정 (구조도 확인 후'),
 # ── 🔴 미검증을 통과로 세게 만듦 ────────────────────────────────────
 ("M13 「인터뷰 0명」 고백 삭제", P, '인터뷰 0명 · 실측 0회', '사용성을 확인했다'),
 ("M14 WO 하나를 분해에서 지움", P,
  '| WO-020 | 표시 위생 — 날것 마크다운 · 자기 모순 문장 | M3 · M4 · M8 | 없음 |\n', ''),
 ("M15 1절 제약 삭제", P, '**판정·추천 자동화 금지.**', '📌판정은 규칙으로 한다.'),
 ("M16 회귀 벤치마크 값 삭제", P, 'C2 ROI 14.2% · Payback 7.1년 · 실질ROI 28.3%',
  'C2 회귀 기준 그대로'),
 ("M17 목표 화면 수 표기 삭제", P, '(화면 21 → 9)', '(화면 재배치)'),
 # ── 🔴 측정기를 느슨하게 만듦 ───────────────────────────────────────
 ("M18 본문 대신 전체 HTML을 셈", C, '    home_links = set(_HREF.findall(_main_of(get("/")[1])))',
  '    home_links = set(_HREF.findall(get("/")[1]))'),
 ("M19 별표를 세기 전에 지움", C, '    return _TAG.sub(" ", html)',
  '    return _TAG.sub(" ", html).replace("**", "")'),
 ("M20 404를 세지 않음", C, '    m2_broken = sorted(h for h in guide_links if get(h)[0] != 200)',
  '    m2_broken = sorted(h for h in guide_links if get(h)[0] >= 500)'),
 ("M21 지표 이름 순서를 바꿈", C, '    ("M3_raw_stars", "화면에 날것으로 나가는 별표"),\n    ("M4_raw_backticks", "화면에 날것으로 나가는 백틱"),\n',
  '    ("M4_raw_backticks", "화면에 날것으로 나가는 백틱"),\n    ("M3_raw_stars", "화면에 날것으로 나가는 별표"),\n'),
 ("M22 재는 화면에서 하나 뺌", C, 'READ_SCREENS = ("/refs", "/guide", "/flow", "/functions", "/design", "/for", "/axes")',
  'READ_SCREENS = ("/guide", "/flow", "/functions", "/design", "/for", "/axes")'),
 ("M23 별표 수를 박아 넣음", C, '    m3, m4 = stars, backticks', '    m3, m4 = 576, backticks'),
 ("M24 자기 모순을 세지 않음", C, '    m8 = len(contradictions)', '    m8 = 2 if contradictions else 0'),
 ("M25 자료 지도 목록을 줄임", C, 'MAP_SCREENS = ("/flow", "/functions", "/axes", "/for", "/for/{name}")',
  'MAP_SCREENS = ("/flow", "/functions", "/axes", "/for")'),
 ("M26 1층 목록에서 하나 뺌", C, 'FIRST_FLOOR = ("/design", "/case/", "/flow", "/refs")',
  'FIRST_FLOOR = ("/case/", "/flow", "/refs")'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    nl = '\r\n' if '\r\n' in s else '\n'
    aa, bb = a.replace('\n', nl), b.replace('\n', nl)
    if s.count(aa) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(aa, bb, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
