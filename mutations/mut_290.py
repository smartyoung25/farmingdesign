"""290차 뮤테이션 — 준비물 사다리 가드(test_290cha)를 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 290
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-x', '-k', '290cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
C = 'consulting_package.py'
T = os.path.join('webapp_templates', 'guide.html')
M = [
 # ── 🔴 규칙을 안 쓰고 손으로 묶음 ───────────────────────────────────
 ("M1 묶음을 손표로 대체", C, 'for s in screens if _readiness_tier(s["input"]) == key]',
  'for s in screens if key == "none"]'),
 ("M2 규칙 순서를 뒤집음(케이스가 먼저 걸림)", C,
  '    if "케이스 파일이 필요 없다" in s:' + chr(10) + '        return "three"',
  '    if False:' + chr(10) + '        return "three"'),
 ("M3 읽기 판정을 느슨하게", C, '    if s.startswith("넣는 것 없음") or "관점 이름" in s:',
  '    if True:'),
 ("M4 계단 하나 삭제", C, '    ("other", "다른 자료가 있어야",', '    ("other_x", "다른 자료가 있어야",'),
 ("M5 계단 이름을 바꿔 적음", C, '"name": name, "line": line, "rule": rule,',
  '"name": name + "(권장)", "line": line, "rule": rule,'),
 # ── 🔴 근거 행을 뗌 ─────────────────────────────────────────────────
 ("M6 근거 행 삭제", C, '"input": s["input"]}                      # 근거 행 — 왜 이 계단인가',
  '"input": ""}'),
 ("M7 화면 설명 칸 추가로 모양 바꿈", C, '{"path": s["path"], "name": s["name"], "what": s["what"],',
  '{"path": s["path"], "name": s["name"], "what": s["what"], "rank": 1,'),
 ("M8 화면에서 규칙 숨김", T, '· 규칙: {{ t.rule }}', ''),
 # ── 🔴 수요를 안다고 함 ─────────────────────────────────────────────
 ("M9 사용성 미측정 기록 삭제", C, '**사용성 인터뷰 0명 · "' + chr(10) + '                 "실측 0회**라 수요를 모른다',
  '사용자가 많이 쓰는 순서다'),
 ("M10 인기 순위라고 적음", C, '**「많이 쓰는 기능」으로 묶지 않았다**', '많이 쓰는 순으로 묶었다'),
 ("M11 계단 우열을 매김", C, '**어느 계단이 더 낫다고 하지 않는다**', '위 계단일수록 좋다'),
 ("M12 근거 주석 삭제", C, '수요를 알 수 없다(11-B ⓔ)', '수요는 분명하다'),
 ("M13 화면에 판정 어휘", T, '<h2>무엇부터 볼까 — 준비물 사다리', '<h2>무엇부터 볼까 — 권장 순서'),
 # ── 🔴 질문을 화면에 배정해 버림 ────────────────────────────────────
 ("M14 질문에 화면을 배정", C, '"note": READINESS_UNMAPPED}', '"note": "/design"}'),
 ("M15 미대응 표기 비움", C, 'READINESS_UNMAPPED: str = "질문 대응 없음"', 'READINESS_UNMAPPED: str = ""'),
 ("M16 「잇지 않았다」 삭제", C, '**질문 ↔ 화면 대응은 만들지 않았다**(배정은 판단이다)',
  '질문마다 화면을 붙였다'),
 ("M17 화면의 미배정 경고 삭제", T, '<b>어느 질문이 어느 화면인지는 잇지 않았습니다</b>',
  '<b>질문마다 화면을 붙였습니다</b>'),
 # ── 🔴 화면이 빠지거나 겹침 ─────────────────────────────────────────
 ("M18 화면 하나 흘림", C, 'for s in screens if _readiness_tier(s["input"]) == key]',
  'for s in screens[:-1] if _readiness_tier(s["input"]) == key]'),
 ("M18b 근거 행을 빈 값으로", C, '"input": s["input"]}                      # 근거 행 — 왜 이 계단인가',
  '"input": s.get("nope", "")}'),
 ("M19 계단 수를 부풀림", C, '"screens": rows, "n": len(rows)})', '"screens": rows, "n": len(rows) + 1})'),
 ("M20 전체 수를 틀리게", C, '"tiers": tiers, "total": len(screens),', '"tiers": tiers, "total": 20,'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
