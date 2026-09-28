"""268차 뮤테이션 — 레드팀 34회차 반영 가드(test_268cha)를 일부러 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 268
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '268cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
D = '근거_관리동_실재점검_20260915.md'
R = os.path.join('mutations', 'run_all.py')
M = [
 ("M1 「별동」 되살림", D, "**관리동 구역이 도면에 실재**(개요표", "**관리동이 별동으로 실재**(개요표"),
 ("M2 개요표 산술 틀림", D, "재배 3,027 + 관리동 432 = 온실 **3,459㎡**", "재배 3,027 + 관리동 432 = 온실 **3,559㎡**"),
 ("M3 규격 대응 주장 복귀", D, "🔴**규격은 내역서와 하나도 맞지 않는다**", "규격이 내역서 라인과 대응한다"),
 ("M4 요약 건수 부풀림", D, "명시하는 것 6건**", "명시하는 것 8건**"),
 ("M5 실행기 -z 제거", R, "'--porcelain', '-uall', '-z'", "'--porcelain', '-uall'"),
 ("M6 복원 실패를 삼킴", R, "def _checkout(path):", "def _checkout_old(path):"),
 ("M7 README 합계 행 틀림", os.path.join('mutations', 'README.md'), "개 전부 통과 | **", "개 전부 통과 | **9"),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
