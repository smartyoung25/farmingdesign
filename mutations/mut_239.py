"""239차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 239  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
CP, R, W = 'consulting_package.py', '엔진데이터_레지스트리.json', '작업지시서.md'
M = [
 ("M1 미제출=불합격(ⓑ)로 되돌림", CP, 'None if not _att_given else not _att_short),', 'not _att_short),'),
 ("M2 미제출=통과로 셈", CP, 'None if not _att_given else not _att_short),', 'True if not _att_given else not _att_short),'),
 ("M3 레지스트리 결정 기록 삭제", R, '★**사용자 결정(2026-09-28): B11 ⓐ**', '**메모(2026-09-28)**'),
 ("M4 작업지시서 B11 다시 대기", W, '| ~~B11~~ ✅ |', '| **B11** | ★'),
]
res = []
for name, f, a, b in M:
    raw = open(f, 'rb').read()
    s = raw.decode('utf-8')
    if s.count(a) != 1:
        res.append((name, f"적용 불가({s.count(a)})")); continue
    open(f, 'wb').write(s.replace(a, b).encode('utf-8'))
    try:
        r = subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '239cha'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
