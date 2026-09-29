"""276차 뮤테이션 — 참조 카탈로그 가드(test_276cha…refs)를 일부러 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 276
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-x', '-k', 'refs'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
C = 'consulting_package.py'
W = 'webapp.py'
T = os.path.join('webapp_templates', 'refs_catalog.html')
B = os.path.join('webapp_templates', '_base.html')
M = [
 ("M1 근거 문서 한 건을 빠뜨림", C, 'for n in names("근거_*.md"):', 'for n in names("근거_*.md")[1:]:'),
 ("M2 원문 갈래에서 법령을 뺌", C, 'for pat in ("법령_*.pdf", "고시_*.pdf"):',
  'for pat in ("고시_*.pdf",):'),
 ("M3 생성 산출물에서 index를 뺌", C, 'names("SmartFarm_*.html") + names("index.html")',
  'names("SmartFarm_*.html")'),
 ("M4 설명 없음을 빈 문자열로 숨김", C, 'REFS_NO_DESC: str = "설명 없음(등재 필요)"',
  'REFS_NO_DESC: str = ""'),
 ("M5 지도 미등재 표시를 지움", C, '"extra": "" if n in mapped else REFS_NOT_IN_MAP,',
  '"extra": "",'),
 ("M6 리포에 없음 표시를 지움", C, '"extra": "" if exists else REFS_NOT_IN_REPO,',
  '"extra": "",'),
 ("M7 설명을 지어냄", C, '"desc": ref_note.get(f) or REFS_NO_DESC,',
  '"desc": ref_note.get(f) or "원문 자료",'),
 ("M8 status를 새로 매김", C, '"statuses": sorted({status_of[c] for c in cs_',
  '"statuses": ["실측"] or sorted({status_of[c] for c in cs_'),
 ("M9 건수를 문서에서 옮김", C, '        g["count"] = len(g["items"])', '        g["count"] = 77'),
 ("M10 개인 이름 scrub 제거", W, '"name": cdsp.scrub(x["name"]),', '"name": x["name"],'),
 ("M11 메뉴 링크 제거", B, '<a href="/refs">참조 카탈로그<small>', '<a href="/refs_x">참조 카탈로그<small>'),
 ("M12 화면에서 항목을 일부만 그림", T, '{% for x in g["items"] %}', '{% for x in g["items"][:5] %}'),
 ("M13 경계 문구 삭제(지어내지 않는다)", C, '설명을 지어내지 않는다', '설명을 채워 넣는다'),
 ("M14 경계 문구 삭제(status)", C, 'status를 새로 매기지 않는다', 'status를 여기서 매긴다'),
 ("M15 note에서 「리포에 없음」 삭제", C, '열 수 없는 원문은 **「리포에 없음」**으로 드러낸다',
  '열 수 없는 원문은 목록에서 뺀다'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
