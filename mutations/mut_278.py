"""278차 뮤테이션 — 관점별 입구 가드(test_278cha…perspective)를 일부러 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 278
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-x', '-k', 'perspective'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
C = 'consulting_package.py'
T = os.path.join('webapp_templates', 'perspective.html')
B = os.path.join('webapp_templates', '_base.html')
M = [
 ("M1 한 코드를 배정에서 뺌", C, '("D1", "D2", "D3", "D6", "D10", "D16", "D18", "D20", "D21")',
  '("D1", "D2", "D3", "D6", "D10", "D16", "D18", "D20")'),
 ("M2 관점 이름을 바꿈", C, '("투자자", "회수되나', '("투자자들", "회수되나'),
 ("M3 질문을 화면이 새로 짓게", T, '{{ r.ask }}', '{{ r.name }} 전용 묶음'),
 ("M4 가점 항목 원문을 고침", C, '설계도서(도면, 내역서, 시방서, 구조계산서, 부하계산서 등)가 준비된 경우',
  '설계도서가 준비된 경우'),
 ("M5 대응 없음을 대응 있음으로", C,
  '("후순위(감점)", "침수, 산사태 우려 지역", ()),', '("후순위(감점)", "침수, 산사태 우려 지역", ("D1",)),'),
 ("M6 대응 없음 문구를 비움", C, 'PERSPECTIVE_NONE: str = "대응 산출물 없음"', 'PERSPECTIVE_NONE: str = ""'),
 ("M7 화면이 가점을 단정", T, '가점을 주는 것은 심사 주체이고', '우리 산출물은 가점을 받는다.'),
 ("M8 심사 주체 문구 삭제", T, '가점을 주는 것은 심사 주체이고, 여기는 <b>이름 대응까지만</b> 적는다',
  '여기는 이름 대응까지만 적는다'),
 ("M9 고아 목록을 숨김", C, 'for s in PACKAGE_SPEC if s["code"] not in assigned]',
  'for s in PACKAGE_SPEC if False]'),
 ("M10 F0 제외를 되살림", B, '{% for f in nav_functions() %}\n',
  "{% for f in nav_functions() %}{% if f.fn != 'F0' %}\n"),
 ("M11 판정 어휘 유입", T, '<h1>{{ ix.one.name if ix.one else "관점별 입구" }}</h1>',
  '<h1>추천 묶음</h1>'),
 ("M12 단정 금지 주석 삭제", C, '**단정하지 않는다** — 대응 이름까지만 적고 판단은 심사 주체의 몫이다',
  '가점 대상임을 적는다'),
 ("M13 입구/판정 경계 삭제", C, '🔴관점은 **입구이지 판정이 아니다**', '관점은 무엇이 맞는지 고른다'),
 ("M14 산출물 이유를 새로 씀", C, '"why": why}', '"why": "이 관점에 필요"}'),
 ("M15 없는 관점이 200을 내게", C, '        if not one:\n            return {}',
  '        if not one:\n            return out'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
