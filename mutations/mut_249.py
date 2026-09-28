"""249차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 249  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os, glob
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거); sys.stdout.reconfigure(encoding='utf-8')
R='docs/work-orders/README.md'
w7=glob.glob('docs/work-orders/WO-004_*.md')[0]; w9=glob.glob('docs/work-orders/WO-009_*.md')[0]
M=[("M1 D-11 WO의 D 번호 제거", glob.glob('docs/work-orders/WO-006_*.md')[0], '# 작업지시서 WO-006: D-11 ', '# 작업지시서 WO-006: '),
   ("M2 D-7 선택을 WO가 확정", w7, '[확인 필요: D-7 — ⓐ 2,321.87로 교체 / ⓑ 2,323 유지(현행)]', '결정: ⓐ 교체'),
   ("M3 열린 D-15 WO를 완료로", R, '| 없음 | 결정 대기 |\n', '| 없음 | 완료 |\n'),
   ("M4 D-7 WO 중복", None, None, None)]
for n,f,a,b in M:
    if f is None:
        import shutil; dup=w7.replace('WO-004_','WO-010_')
        s=open(w7,encoding='utf-8').read().replace('WO-004:','WO-010:')
        open(dup,'w',encoding='utf-8').write(s)
        rd=open(R,'rb').read(); open(R,'ab').write(('| [WO-010]('+os.path.basename(dup)+') | x | x | 없음 | 결정 대기 |\n').encode('utf-8'))
        r=subprocess.run([sys.executable,'-m','pytest','test_engine.py','-q','-x','-k','249cha'],capture_output=True)
        print("잡음" if r.returncode else "놓침", n); os.remove(dup); open(R,'wb').write(rd); continue
    raw=open(f,'rb').read(); s=raw.decode('utf-8'); crlf='\r\n' in s
    a2=a.replace('\n','\r\n') if crlf else a; b2=b.replace('\n','\r\n') if crlf else b
    k=s.rfind(a2)
    if k<0: print("적용불가",n); continue
    open(f,'wb').write((s[:k]+b2+s[k+len(a2):]).encode('utf-8'))
    try:
        r=subprocess.run([sys.executable,'-m','pytest','test_engine.py','-q','-x','-k','249cha'],capture_output=True)
        print("잡음" if r.returncode else "놓침", n)
    finally:
        open(f,'wb').write(raw)
