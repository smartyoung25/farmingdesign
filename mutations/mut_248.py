"""248차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 248  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')  # 266차: 265차 치환이 이 문장을 주석 속에 넣었다 — 되살림
T='webapp_templates/work_orders.html'; D='webapp_templates/work_order_detail.html'; B='webapp_templates/_base.html'; W='webapp.py'
M=[("M1 확인 수를 템플릿이 다시 셈", T, 'data-checked="{{ r.checked }}"', 'data-checked="{{ r.total }}"'),
   ("M2 첫 WO 행 누락", W, '    for f in r["files"]:\n        p, ix = f["parsed"]', '    for f in r["files"][1:]:\n        p, ix = f["parsed"]'),
   ("M3 참조 메뉴 링크 제거", B, '        <a href="/workorders">작업지시서(WO)<small>', '        <a href="/x">작업지시서(WO)<small>'),
   ("M4 절 순서 역전", W, 'for n in p["order"]]})', 'for n in reversed(p["order"])]})'),
   ("M5 모두 확인으로 표시", D, "{{ '확인' if c.checked else '미확인' }}", "확인"),
   ("M6 README 번호도 허용", W, '_WO_ID_RE = re.compile(r"^WO-\d{3}(?:-fix\d+)?$")', '_WO_ID_RE = re.compile(r"^.+$")')]
for n,f,a,b in M:
    raw=open(f,'rb').read(); s=raw.decode('utf-8'); crlf='\r\n' in s
    a2=a.replace('\n','\r\n') if crlf else a; b2=b.replace('\n','\r\n') if crlf else b
    if s.count(a2)!=1: print("적용불가",n,s.count(a2)); continue
    open(f,'wb').write(s.replace(a2,b2).encode('utf-8'))
    try:
        r=subprocess.run([sys.executable,'-m','pytest','test_webapp.py','-q','-x','-k','248cha'],capture_output=True)
        print("잡음" if r.returncode else "놓침", n)
    finally:
        open(f,'wb').write(raw)
