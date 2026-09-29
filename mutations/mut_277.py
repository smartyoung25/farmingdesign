"""277차 뮤테이션 — 사용 안내 가드(test_277cha…guide)를 일부러 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 277
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-x', '-k', 'guide'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
C = 'consulting_package.py'
W = 'webapp.py'
T = os.path.join('webapp_templates', 'guide.html')
B = os.path.join('webapp_templates', '_base.html')
M = [
 ("M1 화면 하나를 안내에서 뺌", C, '    ("/refs", "참조 카탈로그"', '    ("/refs_x", "참조 카탈로그"'),
 ("M2 새 라우트를 안내 없이 추가", W, '@app.get("/guide")',
  '@app.get("/새화면_가드시험")\ndef probe_screen(request: Request):\n    return PlainTextResponse("x")\n\n\n@app.get("/guide")'),
 ("M3 화면 아닌 경로를 숨김", C, '    ("/health", "화면이 아니다', '    ("/health_x", "화면이 아니다'),
 ("M4 안 나오면 칸을 비움", C, '"부분 케이스는 4축이 없어 **부분 케이스 페이지 하나**만 나온다"', '""'),
 ("M5 확인 필요를 답으로 바꿈", C, '"**확인 필요.** 2026년 지침 가점 항목에', '"가점을 받는다. 2026년 지침 가점 항목에'),
 ("M6 확인 필요 표시만 뗌", C, '"근거_외부수집_기능공백_20260924.md 6-d", False),',
  '"근거_외부수집_기능공백_20260924.md 6-d", True),'),
 ("M7 출처를 없는 파일로", C, '"consulting_package.py D5 · 근거_외부수집_기능공백_20260924.md 6-b"',
  '"consulting_package.py D5 · 없는문서_20260101.md 6-b"'),
 ("M8 출처가 없는 이름을 가리킴", C, 'smartfarm_engine.WEATHER_MATCH_RULE',
  'smartfarm_engine.WEATHER_NO_SUCH_RULE'),
 ("M9 기입 7단계를 6으로", C, '    ("renew", "연차 재검", "사람", "年次審査(연차심사)"),', ''),
 ("M10 상태기계 보존 주석 삭제", C, '기입 7단계(`ENTRY_STEPS`)는 그대로 둔다', '기입 7단계를 이 문서가 대신한다'),
 ("M11 「어디까지 했는가」 경고 삭제", C, '매뉴얼로 바꾸면 「어디까지 했는가」를 잃는다', '매뉴얼로 바꿔도 된다'),
 ("M12 수치 금지 경계 삭제", C, '수치를 새로 적지 않는다', '수치를 여기에 적는다'),
 ("M13 메뉴 링크 제거", B, 'href="/guide">사용 안내</a>', 'href="/guide_x">사용 안내</a>'),
 ("M14 판정 어휘 유입", T, '<h1>사용 안내</h1>', '<h1>사용 안내 — 추천 설정</h1>'),
 ("M15 화면을 일부만 그림", T, '{% for s in g.screens %}', '{% for s in g.screens[:5] %}'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
