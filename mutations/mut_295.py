"""295차 뮤테이션 — 인터뷰 반영분 가드(test_294cha 둘 · test_295cha)를 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 295
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', 'test_webapp.py',
                              '-q', '-x', '-k', '294cha or 295cha'], capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
P = 'PRD_콘솔_UIUX재설계_20261002.md'
C = 'measure_console_ia.py'
M = [
 # ── 🔴 M9를 손으로 고침 ─────────────────────────────────────────────
 ("M1 M9 기준선을 낮춤", P, '| M9 | 수를 내면서 출처로 가는 길이 없는 화면 | 6 | 0 |',
  '| M9 | 수를 내면서 출처로 가는 길이 없는 화면 | 2 | 0 |'),
 ("M2 M9 행 삭제", P, '| M9 | 수를 내면서 출처로 가는 길이 없는 화면 | 6 | 0 | 미착수 |\n', ''),
 ("M3 M9 이름을 바꿈", P, '| M9 | 수를 내면서 출처로 가는 길이 없는 화면 |', '| M9 | 출처 없는 화면 |'),
 ("M4 M9를 완료로 적음", P, '| M9 | 수를 내면서 출처로 가는 길이 없는 화면 | 6 | 0 | 미착수 |',
  '| M9 | 수를 내면서 출처로 가는 길이 없는 화면 | 6 | 0 | 완료 295차 |'),
 # ── 🔴 ★결정 줄을 지움 ──────────────────────────────────────────────
 ("M5 표시 위생 결정 삭제", P, '4. **표시 위생을 먼저**', '4. 표시 순서는 내가 정했다'),
 ("M6 골조 설명 결정 삭제", P, '6. **골조 단독은 설명부터**', '6. 골조 단독은 내가 정했다'),
 ("M7 공종 미룸 결정 삭제", P, '7. **공종 × 단계 확정은 미룬다**', '7. 공종 × 단계는 확정했다'),
 # ── 🔴 고백을 지움 ──────────────────────────────────────────────────
 ("M8 최종 사용자 0명 삭제", P, '최종 사용자(농업인·투자자·공공기관) 본인에게 물은 것은 0명',
  '사용자 전수에게 물었다'),
 ("M9 측정 반쪽 고백 삭제", P, '정적 사이트 쪽 지표는 0개', '정적 사이트도 함께 잰다'),
 ("M10 「무엇을 먼저 찾는지」 삭제", P, '무엇을 먼저 찾는지', '무엇이 중요한지'),
 # ── 🔴 WO 분해를 흘림 ───────────────────────────────────────────────
 ("M11 WO-021 행 삭제", P, '| WO-021 | 수에서 출처로 — 골조 단독부터 | M9 | WO-012 | **3** |\n', ''),
 ("M12 제목에서 목표 수 삭제", P, '# PRD — 콘솔 UI·UX 재설계 (화면 21 → 9)',
  '# PRD — 콘솔 UI·UX 재설계'),
 # ── 🔴 측정기를 느슨하게 ────────────────────────────────────────────
 ("M13 결과 표본을 버림", C, '        probe = RESULT_SAMPLES.get(path, path)', '        probe = path'),
 ("M14 출처 힌트를 넓힘", C, 'SOURCE_HINTS = ("/refs", "근거")', 'SOURCE_HINTS = ("/", "근거")'),
 ("M15 금액 정규식을 죽임", C, '_MONEY = re.compile(r"[0-9][0-9,]{5,}\\s*원")',
  '_MONEY = re.compile(r"ZZZZ[0-9]")'),
 ("M16 비율 정규식을 죽임", C, '_PCT = re.compile(r"[0-9]+(?:\\.[0-9]+)?\\s*%")',
  '_PCT = re.compile(r"ZZZZ%")'),
 ("M17 M9를 박아 넣음", C, '    m9 = len(m9_screens)', '    m9 = 6'),
 ("M18 출처 유무 판정을 뒤집음", C, '        if not any(any(h2 in h for h2 in SOURCE_HINTS) for h in hrefs):',
  '        if any(any(h2 in h for h2 in SOURCE_HINTS) for h in hrefs):'),
 # ── 🔴 골조 단독의 성질을 흔듦(test_295cha) ─────────────────────────
 ("M19 PRD의 3,000㎡ 값을 고침", P, '전부 148,284,833원', '전부 150,000,000원'),
 ("M20 PRD의 3,300㎡ 값을 고침", P, '**3,300㎡ → 163,113,316원**', '**3,300㎡ → 999,999,999원**'),
 ("M21 PRD의 주소 무관 서술 삭제", P, '주소에 무관하고 면적에 비례', '지역마다 다르게'),
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
