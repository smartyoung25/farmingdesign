"""254차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 254  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')  # 266차: 265차 치환이 이 문장을 주석 속에 넣었다 — 되살림
W='docs/work-orders/WO-009_D15_품셈주적용조건.md'; L='근거_결정대기대장_20260915.md'
M=[("M1 엔진이 적용조건을 냄", 'smartfarm_engine.py', '        "total_labor_days": round(sum(item.labor_per_unit.values()) * quantity, 3),\n    }', '        "total_labor_days": round(sum(item.labor_per_unit.values()) * quantity, 3),\n        **({"적용조건": "p.144"} if category == "온실피복공사" else {}),\n    }'),
   ("M2 대장 D-15 다시 열기", L, '| ~~**D-15**~~ ✅**닫힘(254차)** |', '| **D-15** |'),
   ("M3 p.129 문구 삭제", L, '(*"유리닦기 등의 공정이 없는 것으로 조사"*)와 p.144 `[주]`(*"유리끼우기, 유리닦기 및 마무리 작업을 포함한다"*) 중', '(생략)와 p.144 `[주]`(*"유리끼우기, 유리닦기 및 마무리 작업을 포함한다"*) 중'),
   ("M4 ⓐ·ⓑ 기준을 켬", W, '- [ ] (ⓐ·ⓑ 해당 없음 — ⓒ 선택) 채택하지', '- [x] (ⓐ·ⓑ 해당 없음 — ⓒ 선택) 채택하지'),
   ("M5 WO-009 색인 대기로", 'docs/work-orders/README.md', '| 254차 | 없음 | 완료 |', '| 254차 | 없음 | 결정 대기 |')]
for n,f,a,b in M:
    raw=open(f,'rb').read(); s=raw.decode('utf-8'); crlf='\r\n' in s
    a2=a.replace('\n','\r\n') if crlf else a; b2=b.replace('\n','\r\n') if crlf else b
    if s.count(a2)<1: print("적용불가",n,s.count(a2)); continue
    open(f,'wb').write(s.replace(a2,b2,1).encode('utf-8'))
    try:
        r=subprocess.run([sys.executable,'-m','pytest','test_engine.py','-q','-x','-k','254cha'],capture_output=True)
        print("잡음" if r.returncode else "놓침", n)
    finally:
        open(f,'wb').write(raw)
