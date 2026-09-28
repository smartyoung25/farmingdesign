"""250차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 250  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거); sys.stdout.reconfigure(encoding='utf-8')
W='docs/work-orders/WO-004_D7_C3면적.md'
run=lambda: subprocess.run([sys.executable,'-m','pytest','test_engine.py','-q','-x','-k','250cha'],capture_output=True).returncode
assert run()==0
M=[("M1 ACTUALS 교체", 'smartfarm_engine.py', '("우민재",     2323, 557152000, Cover.FILM)', '("우민재",     2321.87, 557152000, Cover.FILM)'),
   ("M2 대장 D-7 다시 열기", '근거_결정대기대장_20260915.md', '| ~~**D-7**~~ ✅**닫힘(250차)** |', '| **D-7** |'),
   ("M3 AC5 열린 채", '근거_확인요망대장_20260915.md', '| ~~**AC5**~~ | ✅ **250차', '| **AC5** | ✅ **250차'),
   ("M4 ⓐ 기준을 켬", W, '- [ ] (ⓐ 해당 없음 — ⓑ 선택) C3 케이스 파일', '- [x] (ⓐ 해당 없음 — ⓑ 선택) C3 케이스 파일'),
   ("M5 교체 이력 삭제", '근거_결정대기대장_20260915.md', '(교체했다면 158원 → 42원이었다)', '')]
for n,f,a,b in M:
    raw=open(f,'rb').read(); s=raw.decode('utf-8')
    if s.count(a)!=1: print("적용불가",n,s.count(a)); continue
    open(f,'wb').write(s.replace(a,b).encode('utf-8'))
    try:
        r=subprocess.run([sys.executable,'-m','pytest','test_engine.py','-q','-x','-k','250cha'],capture_output=True)
        print("잡음" if r.returncode else "놓침", n)
    finally:
        open(f,'wb').write(raw)
