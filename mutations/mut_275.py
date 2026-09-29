"""275차 뮤테이션 — 축 대응표 가드(test_275cha…axes)를 일부러 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 275
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-x', '-k', 'axes'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
C = 'consulting_package.py'
T = os.path.join('webapp_templates', 'axis_map.html')
B = os.path.join('webapp_templates', '_base.html')
M = [
 ("M1 한 행을 빠뜨림", C, "    rows = []" + chr(10) + "    for spec in PACKAGE_SPEC:",
  "    rows = []" + chr(10) + "    for spec in PACKAGE_SPEC[1:]:"),
 ("M2 축 이름을 새로 지음", C, 'f"{fn} {fn_name[fn]}"', '"기능축 " + fn'),
 ("M3 플랫폼을 이름 없이 냄", C, 'AXIS_NONE if pk is None else f"{pk} {pn}"', '"P1 설계검증"'),
 ("M4 기입 대응을 D25 밖으로 넓힘", C, 'ENTRY_STEP_OF_CODE: dict = {"D25": ("rules", "issue", "renew")}',
  'ENTRY_STEP_OF_CODE: dict = {"D25": ("rules", "issue", "renew"), "D26": ("rules",)}'),
 ("M5 대응 없음을 빈칸으로 숨김", C, 'AXIS_NONE: str = "대응 없음"', 'AXIS_NONE: str = ""'),
 ("M6 대응 없는 단계를 지움", C, 'ENTRY_STEP_NO_CODE: tuple = ("case", "docs", "evidence")',
  'ENTRY_STEP_NO_CODE: tuple = ("case", "docs")'),
 ("M7 엔진 검증에서 일부만 걸리게", C, 'codes, note = [r["code"] for r in rows], "산출물 전체"',
  'codes, note = [r["code"] for r in rows][:5], "산출물 전체"'),
 ("M8 새 축을 만듦", C, "AXIS_NONE: str =", "OBJECT_AXIS = ('부지', '시설', '장비')\nAXIS_NONE: str ="),
 ("M9 「새 축을 만들지 않는다」 삭제", C, "새 축을 만들지 않는다", "새 축을 만들어도 된다"),
 ("M10 판정 어휘 유입", T, "<h1>축 대응표</h1>", "<h1>축 대응표 — 추천 순</h1>"),
 ("M11 분류 경계 문구 삭제", C, "🔴분류이지 판정이 아니다 — 어떤 축도 더 낫다고 하지 않는다. ",
  "이 표가 더 나은 축을 고른다. "),
 ("M12 메뉴 링크 제거", B, '<a href="/axes">축 대응표<small>', '<a href="/axes_x">축 대응표<small>'),
 ("M13 축 개수 표기 틀림", C, '("기입", "ENTRY_STEPS", len(ENTRY_STEPS))',
  '("기입", "ENTRY_STEPS", 6)'),
 ("M14 「없는 대응을 만들어 채우면」 경고 삭제", C, "없는 대응을 만들어 채우면",
  "없는 대응은 채워도 되고"),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
