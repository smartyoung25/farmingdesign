"""237차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 237  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
V11, V10, RM = '릴리스_v1.1_20260927.md', '릴리스_v1.0_20260923.md', 'README.md'
M = [
 ("M1 v1.1 라우트 수 틀림", V11, '| 웹 콘솔 라우트 | **26**(GET·POST) |', '| 웹 콘솔 라우트 | **25**(GET·POST) |'),
 ("M2 v1.1 보증 한계 문구 삭제", V11, '**값의 옳음은 보증하지 않는다**', '**값도 대체로 옳다**'),
 ("M3 지난 판(v1.0) 수치를 현재로 고침", V10, '| 회귀 | 3파일 **366 passed**', '| 회귀 | 3파일 **375 passed**'),
 ("M4 README에서 v1.1 삭제", RM, '| **`릴리스_v1.1_20260927.md`** |', '| **`릴리스.md`** |'),
 ("M5 v1.1 ★대기 수 틀림", V11, '| **★사용자 결정 대기**(대장의 ★ 표시) | **19** |', '| **★사용자 결정 대기**(대장의 ★ 표시) | **0** |'),
 ("M6 v1.1 레지스트리 수 낡음", V11, '| 레지스트리 상수 · `source_refs` | **72** · **184** |', '| 레지스트리 상수 · `source_refs` | **70** · **182** |'),
]
res = []
for name, f, a, b in M:
    raw = open(f, 'rb').read()
    s = raw.decode('utf-8')
    if s.count(a) != 1:
        res.append((name, f"적용 불가({s.count(a)})")); continue
    open(f, 'wb').write(s.replace(a, b).encode('utf-8'))
    try:
        r = subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '207cha'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
