"""251차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 251  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거); sys.stdout.reconfigure(encoding='utf-8')
A='audit_work_orders.py'; W='webapp.py'
M=[("M1 R9 끔", A, '    if leaked:\n        # 메시지가', '    if False:\n        # 메시지가'),
   ("M2 R9 메시지가 이름을 되풀이", A, 'f"{sorted(set(cdsp.scrub(n) for n in leaked))}) — case_display', 'f"{sorted(leaked)}) — case_display'),
   ("M3 색인 화면 제목 scrub 제거", W, '"title": cdsp.scrub(p["title"]), "type"', '"title": p["title"], "type"'),
   ("M4 상세 본문 scrub 제거", W, 'cdsp.scrub(p["sections"][n]["body"])', 'p["sections"][n]["body"]'),
   ("M5 WO 문서에 실명 재유입", 'docs/work-orders/WO-005_D8_무인방제이관.md', 'A7 안개분무시설', '최선동 안개분무시설')]
for n,f,a,b in M:
    raw=open(f,'rb').read(); s=raw.decode('utf-8'); crlf='\r\n' in s
    a2=a.replace('\n','\r\n') if crlf else a; b2=b.replace('\n','\r\n') if crlf else b
    if s.count(a2)<1: print("적용불가",n); continue
    open(f,'wb').write(s.replace(a2,b2,1).encode('utf-8'))
    try:
        r=subprocess.run([sys.executable,'-m','pytest','test_webapp.py','-q','-x','-k','251cha'],capture_output=True)
        print("잡음" if r.returncode else "놓침", n)
    finally:
        open(f,'wb').write(raw)
