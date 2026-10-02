"""289차 뮤테이션 — 공종 매핑 가드(test_289cha)를 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 289
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-x', '-k', '289cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
C = 'consulting_package.py'
E = 'smartfarm_engine.py'
T = os.path.join('webapp_templates', 'service_flow.html')
M = [
 # ── 🔴 배정해 버림(찾기를 손표로 바꿈) ──────────────────────────────
 ("M1 매핑을 손표로 대체", C, '"words": [w for w in TRADE_ASK if (w in desc) or (w in name)],',
  '"words": ["부지"] if key == "site_preparation" else [],'),
 ("M2 낱말을 설명 밖에서 가져옴", C, 'hit = [{"key": r["key"], "name": r["name"], "sample_nonzero": r["sample_nonzero"]}',
  'hit = [{"key": r["key"], "name": r["name"], "sample_nonzero": 99}'),
 ("M3 요청 낱말 하나 삭제", C, '"부지", "설계", "감리", "시공", "환경제어", "양액", "배관", "전기", "재활용", "히트펌프",',
  '"부지", "설계", "감리", "환경제어", "양액", "배관", "전기", "재활용", "히트펌프",'),
 ("M4 요청 낱말 순서 바꿈", C, '"부지", "설계", "감리", "시공",', '"설계", "부지", "감리", "시공",'),
 # ── 🔴 없는 것을 있다고 함 ──────────────────────────────────────────
 ("M5 「시공」을 억지로 넣음", E, '"철골, 기초, 피복재, 도어 등 — 스마트팜 물리적 기본 구조"',
  '"철골, 기초, 피복재, 도어 등 — 스마트팜 시공의 물리적 기본 구조"'),
 ("M6 「재활용」을 억지로 넣음", E, '"양액기, 펌프, 관수 배관, 폐양액 처리 — 작물 생장 핵심 제어 설비"',
  '"양액기, 펌프, 관수 배관, 폐양액 재활용 — 작물 생장 핵심 제어 설비"'),
 ("M7 못 찾음 표기 삭제", C, 'TRADE_NOT_FOUND: str = "공종 설명에 없다"', 'TRADE_NOT_FOUND: str = ""'),
 ("M8 found를 항상 참으로", C, '"found": bool(hit),', '"found": True,'),
 # ── 🔴 표본 커버리지를 다시 세지 않음 ───────────────────────────────
 ("M9 0원을 건수로 셈", C, 'nz = sum(1 for c in chunks.values() if (c.get(key) or 0) > 0)',
  'nz = sum(1 for c in chunks.values() if key in c)'),
 ("M10 표본 수를 부풀림", C, '"sample_nonzero": nz,', '"sample_nonzero": nz + 1,'),
 ("M11 표본 0건 목록 비움", C, '"no_sample": [r["name"] for r in rows if r["sample_nonzero"] == 0],',
  '"no_sample": [],'),
 ("M12 RFQ 필수를 임의로", C, '"rfq": key in req,', '"rfq": True,'),
 # ── 🔴 하이어라키를 새로 만듦 ───────────────────────────────────────
 ("M13 엔진에 새 공종 상수", E, 'CAPEX_MAJOR_CATEGORIES',
  'NUTRIENT_RECYCLE = {}' + chr(13) + chr(10) + 'CAPEX_MAJOR_CATEGORIES'),
 ("M14 공종 하나 삭제", C, '    for key, name, desc in cats:' + chr(10) + '        nz =',
  '    for key, name, desc in cats[:-1]:' + chr(10) + '        nz ='),
 ("M15 공종 이름을 바꿔 적음", C, '"name": name, "desc": desc,', '"name": name.split(". ")[-1], "desc": desc,'),
 # ── 🔴 비어 있는 것을 숨김 ──────────────────────────────────────────
 ("M16 표본 0건 절 삭제", T, '<b>표본 금액이 0건인 공종 {{ trades.no_sample|length }}종</b>', '<b>공종 현황</b>'),
 ("M17 「없다」를 화면에서 숨김", T, '🔴 {{ a.note }}', '—'),
 ("M18 경계 문구 삭제", C, '**어느 공종이 더 중요하다고 하지 않는다**', '중요도 순이다'),
 ("M19 화면에 판정 어휘", T, '<h2>공종 — 요청한 항목이 어느 공종에 걸리나</h2>', '<h2>공종 — 권장 공종</h2>'),
 # ── 🔴 출처·경계 기록 삭제 ──────────────────────────────────────────
 ("M20 지시 출처 표기 삭제", C, '★사용자 지시 2026-10-02의 낱말 그대로', '임의 목록'),
 ("M21 「배정하지 않는다」 삭제", C, '🔴 **배정하지 않는다**', '📌 배정한다'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
