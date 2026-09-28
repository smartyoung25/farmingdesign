"""252차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 252  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거); sys.stdout.reconfigure(encoding='utf-8')
W='docs/work-orders/WO-005_D8_무인방제이관.md'
L='근거_결정대기대장_20260915.md'
M=[("M1 미분류 값 변경(이관)", 'smartfarm_engine.py', '"최선동": 68035800', '"최선동": 49535800'),
   ("M2 대장 D-8 다시 열기", L, '| ~~**D-8**~~ ✅**닫힘(252차)** |', '| **D-8** |'),
   ("M3 CM1 닫음", '근거_확인요망대장_20260915.md', '| **CM1** |', '| ~~**CM1**~~ |'),
   ("M4 ⓐ 기준을 켬", W, '- [ ] (ⓐ 해당 없음 — ⓑ 선택) 미분류가', '- [x] (ⓐ 해당 없음 — ⓑ 선택) 미분류가'),
   ("M5 닫힌 행에 실명", L, '(A7 안개분무 18,500,000 · S10', '(최선동 안개분무 18,500,000 · S10'),
   ("M6 이력 삭제", L, '합 43,607,700 = known_total 합의 0.551%', '합계는 이력')]
for n,f,a,b in M:
    raw=open(f,'rb').read(); s=raw.decode('utf-8')
    if s.count(a)<1: print("적용불가",n,s.count(a)); continue
    open(f,'wb').write(s.replace(a,b,1).encode('utf-8'))
    try:
        r=subprocess.run([sys.executable,'-m','pytest','test_engine.py','-q','-x','-k','252cha'],capture_output=True)
        print("잡음" if r.returncode else "놓침", n)
    finally:
        open(f,'wb').write(raw)
