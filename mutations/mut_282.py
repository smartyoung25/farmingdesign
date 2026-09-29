"""282차 뮤테이션 — 시설 작목 수량 가드(test_282cha)를 일부러 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 282
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-x', '-k', '282cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
E = 'smartfarm_engine.py'
C = 'consulting_package.py'
R = '엔진데이터_레지스트리.json'
D = '근거_시설작목수량_등재_20260929.md'
T = os.path.join('webapp_templates', 'basic_design.html')
M = [
 # ── 전사 오류(원문 재판독이 잡아야 한다) ─────────────────────────────
 ("M1 한 종의 수량을 한 자리 틀리게", E, '"시설딸기": 2_893,', '"시설딸기": 2_983,'),
 ("M2 마지막 종을 통째로 뺌", E, '    "시설포도": 1_596,' + chr(13) + chr(10), ''),
 ("M3 노지 작목을 끼워 넣음", E, '    "시설포도": 1_596,',
  '    "시설포도": 1_596,' + chr(10) + '    "사과": 1_982,'),
 ("M4 시설장미를 「본」인 채 넣음", E, '    "시설포도": 1_596,',
  '    "시설포도": 1_596,' + chr(10) + '    "시설장미": 65_840,'),
 ("M5 최대값을 평균값으로 바꿈", E, '"시설토마토(수경)": 14_310,', '"시설토마토(수경)": 14_301,'),
 # ── 🔴 시세성 유입 ───────────────────────────────────────────────────
 ("M6 같은 표의 총수입을 등재", E, 'FACILITY_YIELD_BASIS = {',
  'FACILITY_YIELD_INCOME_WON_10A = {"시설딸기": 26_307_065}' + chr(10) + 'FACILITY_YIELD_BASIS = {'),
 ("M7 소득률을 상수로 등재", E, '_M2_PER_10A = 1_000.0',
  'FACILITY_INCOME_RATE = {"시설수박": 50.9}' + chr(10) + '_M2_PER_10A = 1_000.0'),
 ("M8 금액 제외 선언 삭제", E, '**금액은 등재하지 않는다.**', '금액은 나중에 본다.'),
 # ── 🔴 고르기·판정 유입 ──────────────────────────────────────────────
 ("M9 비슷한 이름을 골라 줌", E, '    v = FACILITY_YIELD_KG_10A.get(str(crop).strip())',
  '    v = FACILITY_YIELD_KG_10A.get(str(crop).strip()) or FACILITY_YIELD_KG_10A.get("시설" + str(crop).strip())'),
 ("M10 후보 중 하나를 골라 줌", C, '        hits = [n for n in e.facility_yield_crops() if crop in n]',
  '        hits = [n for n in e.facility_yield_crops() if crop in n][:1]'),
 ("M11 「고르지 않는다」 경계 삭제", C, '**전국 평균**이고 **고르지 않는다** —',
  '**전국 평균**이고 이 값을 쓰면 된다 —'),
 ("M12 수량 참고에 판정 어휘 유입", T, '<h2>수량 참고 — 농진청 소득자료집</h2>',
  '<h2>수량 참고 — 권장 수량</h2>'),
 # ── 🔴 못 내는 것을 숨김 / 이유를 되돌림 ──────────────────────────────
 ("M13 경제성 한계를 삭제", C, '    cannot.append({"무엇": "경제성(ROI·회수기간)·경제면적", "왜": (',
  '    None if True else cannot.append({"무엇": "경제성(ROI·회수기간)·경제면적", "왜": ('),
 ("M14 이유를 「수량 미등재」로 되돌림", C, '"수량은 282차에 등재됐다(전국 평균 · 시설 계열 %d종) — 그런데 **단가가 시세성**이라 "',
  '"수량이 등재돼 있지 않다 — %d "'),
 # ── 🔴 케이스·레지스트리·근거 문서 ───────────────────────────────────
 ("M15 케이스 수량을 전국 평균으로 덮어씀", os.path.join('cases', 'wonchaewon.json'),
  '"base_yield_kg_m2": 38.5', '"base_yield_kg_m2": 14.31'),
 ("M16 레지스트리 사본만 고침", R, '"시설가지": 13114', '"시설가지": 13141'),
 ("M17 레지스트리 status를 결정으로", R,
  '"status": "공공기준",' + chr(13) + chr(10) + '      "status_note": "원문 전사(수량 열만)',
  '"status": "결정",' + chr(13) + chr(10) + '      "status_note": "원문 전사(수량 열만)'),
 ("M18 원문 참조를 partial로 낮춤", R,
  '금액 4열과 시설장미(본)는 제외",' + chr(13) + chr(10) + '          "match": "exact"',
  '금액 4열과 시설장미(본)는 제외",' + chr(13) + chr(10) + '          "match": "partial"'),
 ("M19 근거 문서에서 간극 판정 유보를 삭제", D, '이 차수는 **판정하지 않는다**', '이 차수는 케이스 값을 쓴다'),
 ("M20 근거 문서에서 「본」 제외 사유 삭제", D, '**단위가 ㎏이 아니다**', '단위는 같다'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
