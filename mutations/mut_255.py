"""255차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 255  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거); sys.stdout.reconfigure(encoding='utf-8')
W='docs/work-orders/WO-006_D11_크루구성.md'; L='근거_결정대기대장_20260915.md'
run=lambda: subprocess.run([sys.executable,'-m','pytest','test_engine.py','-q','-x','-k','255cha'],capture_output=True).returncode
assert run()==0, "원본이 실패한다 — 뮤테이션 무효"
M=[("M1 엔진에 공기 함수 추가", 'smartfarm_engine.py', 'def pumsem_project_labor_summary(', 'def pumsem_schedule_days(summary, crew_size):\n    return summary["total_labor_days"] / crew_size\n\n\ndef pumsem_project_labor_summary('),
   ("M2 대장 D-11 다시 열기", L, '| ~~**D-11**~~ ✅**닫힘(255차)** |', '| **D-11** |'),
   ("M3 측정 이력 삭제", L, '크루 8명 1.49일 · 16.4명 0.73일 · 124차', '124차'),
   ("M4 ⓑ 기준을 켬", W, '- [ ] (ⓑ 해당 없음 — ⓒ 선택)', '- [x] (ⓑ 해당 없음 — ⓒ 선택)'),
   ("M5 ①에 항목 되살림", L, '📌 **남은 항목 없음** —', '| D-11 | 크루 |\n📌 **남은 항목 없음** —'),
   ("M6 케이스에 크루 입력", 'cases/chuncheon.json', '"area_m2": 3456,', '"area_m2": 3456, "crew_size": 8,')]
for n,f,a,b in M:
    raw=open(f,'rb').read(); s=raw.decode('utf-8'); crlf='\r\n' in s
    a2=a.replace('\n','\r\n') if crlf else a; b2=b.replace('\n','\r\n') if crlf else b
    if s.count(a2)<1: print("적용불가",n,s.count(a2)); continue
    open(f,'wb').write(s.replace(a2,b2,1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f,'wb').write(raw)
