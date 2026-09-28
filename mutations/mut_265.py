"""265차 뮤테이션 — 뮤테이션 스크립트 리포 편입 가드(test_265cha)를 일부러 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 265  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '265cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
S = os.path.join('mutations', 'mut_247.py')
R = os.path.join('mutations', 'run_all.py')
D = os.path.join('mutations', 'README.md')
M = [
 ("M1 절대 경로 복귀", S, 'os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))', "os.chdir(r'C:\\FarmingDesign')"),
 ("M2 유령 면제(스크립트에 없는 이름)", R, "'M5 지역명 부분 매칭이 생김(대장 미갱신)'", "'M9 없는 뮤테이션'"),
 ("M3 분류 없는 면제", R, "'상태 변화 — D-7이 250차에 닫혔다'", "'그냥 넘어감'"),
 ("M4 README 결과표에서 차수 누락", D, '| 247 |', '| 24x |'),
 ("M5 CLAUDE.md 명령 삭제", 'CLAUDE.md', 'python mutations/run_all.py', 'mutations 폴더 참고'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
# M6 스크립트 하나 삭제
f = os.path.join('mutations', 'mut_250.py'); raw = open(f, 'rb').read(); os.remove(f)
try: print("잡음" if run() else "놓침", "M6 차수 스크립트 삭제")
finally: open(f, 'wb').write(raw)
assert run() == 0
