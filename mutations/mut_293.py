"""293차 뮤테이션 — 공종×단계 초안 가드(test_293cha)를 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 293
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-x', '-k', '293cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
C = 'consulting_package.py'
E = 'smartfarm_engine.py'
T = os.path.join('webapp_templates', 'service_flow.html')
M = [
 # ── 🔴 초안이 확정으로 둔갑 ─────────────────────────────────────────
 ("M1 초안 표기 삭제", C, 'TRADE_STAGE_STATUS: str = "초안 — 확인요망(★사용자 확정 전)"',
  'TRADE_STAGE_STATUS: str = "확정"'),
 ("M2 「초안이다」 선언 삭제", C, '🔴**이것은 초안이다 — 확정이 아니다.**', '📌정리했다.'),
 ("M3 「내 읽기」 고백 삭제", C, '**나머지 아홉은 내 읽기**일 뿐이고', '나머지 아홉도 근거가 있고'),
 ("M4 「고치면 바뀐다」 삭제", C, '사용자가 고치면 그대로 바뀐다', '이대로 쓴다'),
 ("M5 화면의 초안 배지 삭제", T, '초안입니다(확정 아님)', '확정'),
 ("M6 화면의 확정 전 경고 삭제", T, '확정 전이다 — 고쳐 주셔야 합니다', '참고'),
 ("M7 화면에 확정 어휘", T, '<h2>공종 × 단계 — ', '<h2>공종 × 단계(확정되었습니다) — '),
 # ── 🔴 근거/초안 구분을 흐림 ────────────────────────────────────────
 ("M8 전부 근거 있다고 함", C, '            "derived": derived,', '            "derived": True,'),
 ("M9 전부 초안이라고 함", C, '        derived = key in req', '        derived = False'),
 ("M10 근거 문구를 초안에도 붙임", C,
  '            "basis": TRADE_STAGE_DERIVED if derived else TRADE_STAGE_STATUS,',
  '            "basis": TRADE_STAGE_DERIVED,'),
 ("M11 근거 수를 부풀림", C, '"derived_n": sum(1 for r in rows if r["derived"]),', '"derived_n": 13,'),
 ("M12 근거 넷의 단계를 흩음", C, '"hvac":                       ("①공종설계",', '"hvac":                       ("③감리",'),
 # ── 🔴 공종을 빠뜨림 ────────────────────────────────────────────────
 ("M13 초안에서 한 공종 삭제", C, '    "land_acquisition":           ("④타당성검증", "부지 매입비 — 자산이라 재무에서 다룬다"),\n', ''),
 ("M14 행을 하나 흘림", C, '    for key, name, desc in e.CAPEX_MAJOR_CATEGORIES:', '    for key, name, desc in e.CAPEX_MAJOR_CATEGORIES[:-1]:'),
 ("M15 단계별 묶음을 따로 만듦", C, '        hit = [r["name"] for r in rows if r["stage"] == st]', '        hit = [r["name"] for r in rows]'),
 # ── 🔴 엔진·레지스트리로 승격 ───────────────────────────────────────
 ("M16 엔진에 공종×단계 상수", E, 'CAPEX_MAJOR_CATEGORIES',
  'TRADE_STAGE = {}' + chr(13) + chr(10) + 'CAPEX_MAJOR_CATEGORIES'),
 ("M17 「엔진에 넣지 않는다」 삭제", C, '🔴 **엔진에 넣지 않는다.**', '📌 엔진에 넣는다.'),
 ("M18 조립 계층 이유 삭제", C, '판단성 초안은 조립 계층에 둔다', '어디에 두어도 된다'),
 # ── 🔴 퇴화 기록 삭제(왜 초안인지의 근거) ───────────────────────────
 ("M19 퇴화 기록 삭제", C, '**퇴화했다**(13공종이 전부 `capex_breakdown` 한 함수를 지나 ④로 몰린다)',
  '잘 되었다'),
 ("M20 RFQ 근거 문구 삭제", C, 'TRADE_STAGE_DERIVED: str = "RFQ 필수 스코프 — 발주 사양서(D2)가 ①공종설계다"',
  'TRADE_STAGE_DERIVED: str = "근거 있음"'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
