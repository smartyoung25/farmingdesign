"""249차 보충 뮤테이션(266차) — 249차 원 스크립트는 D-7·D-11이 닫혀 **지금 살아서 잡는 것이 0**이었다(레드팀 33회차 B3).
249차 가드가 아직 여는 경로 — **열린 D-14(WO-008)** — 를 지금 상태로 다시 잰다. 원 스크립트는 당시 기록이라 그대로 둔다.
실행: python mutations/run_all.py 249
"""
import subprocess, sys, os, glob
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '249cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
R = os.path.join('docs', 'work-orders', 'README.md')
W8 = glob.glob(os.path.join('docs', 'work-orders', 'WO-008_*.md'))[0]
M = [
 ("M1 열린 D-14의 WO를 색인에서 완료로", R, '| 착수 시 배정 | 없음 | 자료 대기 |', '| 착수 시 배정 | 없음 | 완료 |'),
 ("M2 열린 D-14의 WO가 [확인 필요]를 잃음", W8, '[확인 필요', '[확인됨'),
 ("M3 WO-008 제목에서 D 번호 제거", W8, '# 작업지시서 WO-008: D-14 ', '# 작업지시서 WO-008: '),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용불가", n); continue
    new = s.replace(a, b) if n.startswith("M2") else s.replace(a, b, 1)
    open(f, 'wb').write(new.encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
