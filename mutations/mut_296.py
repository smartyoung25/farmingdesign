"""296차 뮤테이션 — 측정 정의 정정분 가드(test_294cha 둘 · test_295cha)를 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 296
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
 # ── 🔴 스타일 제거를 되돌림(576·6으로 돌아간다) ─────────────────────
 ("M1 스타일 제거를 지움", C, '    return _TAG.sub(" ", _STYLE_SCRIPT.sub(" ", html))',
  '    return _TAG.sub(" ", html)'),
 ("M2 스타일 패턴을 안 맞게", C, '_STYLE_SCRIPT = re.compile(r"<(?:style|script)[^>]*>.*?</(?:style|script)>", re.S | re.I)',
  '_STYLE_SCRIPT = re.compile(r"<(?:zzstyle)[^>]*>.*?</(?:zzstyle)>", re.S | re.I)'),
 ("M3 스크립트만 지움", C, 'r"<(?:style|script)[^>]*>.*?</(?:style|script)>"',
  'r"<(?:script)[^>]*>.*?</(?:script)>"'),
 ("M4 여러 줄 플래그 제거", C, 're.compile(r"<(?:style|script)[^>]*>.*?</(?:style|script)>", re.S | re.I)',
  're.compile(r"<(?:style|script)[^>]*>.*?</(?:style|script)>", re.I)'),
 # ── 🔴 정정한 기준선을 되돌림 ────────────────────────────────────────
 ("M5 M3 기준선을 576으로", P, '| M3 | 화면에 날것으로 나가는 별표 | 534 | 0 |',
  '| M3 | 화면에 날것으로 나가는 별표 | 576 | 0 |'),
 ("M6 M9 기준선을 6으로", P, '| M9 | 수를 내면서 출처로 가는 길이 없는 화면 | 4 | 0 |',
  '| M9 | 수를 내면서 출처로 가는 길이 없는 화면 | 6 | 0 |'),
 ("M7 정정 기록 삭제", P, '🔴 **M3·M9 정정(296차)**', '📌 기준선 정리'),
 ("M8 가드 한계 고백 삭제", P, '**측정 정의가 옳은지**는 재지 않는다', '측정 정의까지 함께 잰다'),
 # ── 🔴 ★결정 줄을 지움 ──────────────────────────────────────────────
 ("M9 단계 순서 결정 삭제", P, '9. **단계 순서 — 타당성검증을 맨 앞으로**',
  '9. 단계 순서는 내가 정했다'),
 ("M10 재활용 결정 삭제", P, '10. **「양액재활용」의 재활용은 4. 양액·관수 설비 설명에 넣는다**',
  '10. 재활용은 다루지 않는다'),
 ("M11 시공 결정 삭제", P, '11. **「시공」은 공종에 넣지 않는다**', '11. 시공 공종을 만든다'),
 ("M12 게이트 결정 삭제", P, '12. **단계 게이트는 둘 다, 단 순서가 있다**',
  '12. 단계 게이트는 바로 올린다'),
 ("M13 번호 유지 근거 삭제", P, '🔴 **번호는 다시 붙이지 않는다**(제 추천, 채택)',
  '📌 번호도 다시 붙인다'),
 ("M14 원문 복원 사실 삭제", P, '이 결정은 **원문 순서를 복원한다**', '이 결정은 새 순서를 만든다'),
 # ── 🔴 WO 분해를 흘림 ───────────────────────────────────────────────
 ("M15 WO-022 행 삭제", P,
  '| WO-022 | 단계 순서 재정렬 — 타당성검증을 맨 앞으로(번호 유지) | — | 없음 | **0** |\n', ''),
 ("M16 WO-023 행 삭제", P,
  '| WO-023 | 공종 설명 보강 — 재활용을 양액·관수에, 시공은 단계에 | — | WO-022 | **7** |\n', ''),
 ("M17 WO-024 행 삭제", P,
  '| WO-024 | 단계 게이트 조건 전사 — 설계서 §8을 산출물 표의 열로 | — | WO-017 | **8** |\n', ''),
 # ── 🔴 측정기를 느슨하게 ────────────────────────────────────────────
 ("M18 본문 정의를 넓힘", C, '    m = _MAIN.search(html)\n    return m.group(1) if m else html',
  '    return html'),
 ("M19 날것 수를 박아 넣음", C, '    m3, m4 = stars, backticks', '    m3, m4 = 534, backticks'),
 ("M20 M9를 박아 넣음", C, '    m9 = len(m9_screens)', '    m9 = 4'),
 # ── 🔴 골조 단독 재측정 기록을 흔듦 ─────────────────────────────────
 ("M21 PRD의 3,300㎡ 값을 고침", P, '**3,300㎡ → 163,113,316원**', '**3,300㎡ → 999,999,999원**'),
 ("M22 PRD의 주소 무관 서술 삭제", P, '주소에 무관하고 면적에 비례', '지역마다 다르게'),
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
