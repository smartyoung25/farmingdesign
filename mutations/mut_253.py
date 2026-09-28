"""253차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 253  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')  # 266차: 265차 치환이 이 문장을 주석 속에 넣었다 — 되살림
W='docs/work-orders/WO-007_D13_관리동이관.md'; L='근거_결정대기대장_20260915.md'
M=[("M1 부대시설 값 변경", 'smartfarm_engine.py', '"auxiliary_facility": 40093200,', '"auxiliary_facility": 77320088,'),
   ("M2 대장 D-13 다시 열기", L, '| ~~**D-13**~~ ✅**닫힘(253차)** |', '| **D-13** |'),
   ("M3 ⓐ 기준을 켬", W, '- [ ] (ⓐ 해당 없음 — ⓑ 선택) 이관 라인 합이', '- [x] (ⓐ 해당 없음 — ⓑ 선택) 이관 라인 합이'),
   ("M4 닫힌 행에 실명", L, '(S1 「0116 관리사(사무동)공사」 1건)', '(윤성호 「0116 관리사(사무동)공사」 1건)'),
   ("M5 146차 정정 기록 삭제", L, '🔴146차 정정(「독립 부대시설 공종은 S1 하나뿐」은 틀렸다', '🔴(「독립 부대시설 공종은 S1 하나뿐」은 틀렸다'),
   ("M6 이관 측정 이력 삭제", L, '37,226,888 이관 시 40,093,200 → 77,320,088(1.93배)', '이관 시 측정 생략')]
for n,f,a,b in M:
    raw=open(f,'rb').read(); s=raw.decode('utf-8')
    if s.count(a)<1: print("적용불가",n,s.count(a)); continue
    open(f,'wb').write(s.replace(a,b,1).encode('utf-8'))
    try:
        r=subprocess.run([sys.executable,'-m','pytest','test_engine.py','-q','-x','-k','253cha'],capture_output=True)
        print("잡음" if r.returncode else "놓침", n)
    finally:
        open(f,'wb').write(raw)
