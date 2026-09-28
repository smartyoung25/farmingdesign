"""223차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 223  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
T = 'webapp_templates/case_detail.html'
M = [
 ("M1 순서를 ①~⑥으로 되돌림", 'consulting_package.py',
  '"⑤운영", "⑥사후관리", "④타당성검증")', '"④타당성검증", "⑤운영", "⑥사후관리")'),
 ("M2 엔진 밖 하드코딩", T, '{{ p.outside | join(" · ") }}', '경영진 역량 · 시장위치'),
 ("M3 부록 표시 제거", T, '<details class="doc{% if d.appendix %} appx{% endif %}">', '<details class="doc">'),
 ("M4 탭 역순", T, '{% for p in platform %}', '{% for p in platform | reverse %}'),
 ("M5 템플릿 산술", T, '통과 {{ g.n_passed }}', '통과 {{ g.n_passed + 0 }}'),
 ("M6 정적 보고서가 새 순서 사용", 'build_site.py', 'import consulting_package as cpkg', 'import consulting_package as cpkg  # STAGE_ORDER'),
 ("M7 레일에서 산출물 하나 누락", 'consulting_package.py',
  'for x in items if x["stage"] == st]\n        rail.append', 'for x in items if x["stage"] == st][:-1]\n        rail.append'),
 ("M8 등급 하드코딩", T, '<div class="gg">{{ g.grade }}</div>', '<div class="gg">C</div>'),
 ("M9 묶음 변경(④를 설계검증에)", 'consulting_package.py',
  '("P1", "설계검증", ("①공종설계", "②품질설계", "③감리"),', '("P1", "설계검증", ("①공종설계", "②품질설계", "③감리", "④타당성검증"),'),
 ("M10 부분 케이스에 레일", 'webapp.py', '    if not case.get("partial"):\r\n        rail = ', '    if True:\r\n        rail = '),
]
res = []
for name, f, a, b in M:
    raw = open(f, 'rb').read()
    s = raw.decode('utf-8')
    if s.count(a) != 1:
        res.append((name, f"적용 불가({s.count(a)})")); continue
    open(f, 'wb').write(s.replace(a, b).encode('utf-8'))
    try:
        r = subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-x', '-k', '223cha'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
