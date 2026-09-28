"""247차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 247  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거); sys.stdout.reconfigure(encoding='utf-8')
F='audit_work_orders.py'
M=[("M1 R3 제외 검사 끔", 'if not _exclusions(p["sections"].get(3, {}).get("body", "")):', 'if False:'),
   ("M2 「잘」을 단순 포함으로", r'("잘", re.compile(r"(?<![가-힣])잘(?![가-힣])"))', '("잘", re.compile("잘"))'),
   ("M3 R5 구현 코드 검사 끔", '    if bad:\n        probs.append(f"R5', '    if False:\n        probs.append(f"R5'),
   ("M4 R8 색인 누락 무시", '        for f in res["index_missing"]:\n', '        for f in []:\n'),
   ("M5 작업 단위 상한 7→8", 'if not 1 <= len(p["tasks"]) <= 7:', 'if not 1 <= len(p["tasks"]) <= 8:'),
   ("M6 선행 실재 검사 끔", '            if r not in known_ids:\n                probs.append(f"R6 선행', '            if False:\n                probs.append(f"R6 선행')]
raw=open(F,'rb').read(); s=raw.decode('utf-8')
for n,a,b in M:
    if s.count(a)!=1: print("적용불가",n,s.count(a)); continue
    open(F,'wb').write(s.replace(a,b).encode('utf-8'))
    try:
        r=subprocess.run([sys.executable,'-m','pytest','test_engine.py','-q','-x','-k','247cha'],capture_output=True)
        print("잡음" if r.returncode else "놓침", n)
    finally:
        open(F,'wb').write(raw)
