"""240차 보충 뮤테이션(266차) — 240차 원 스크립트의 변형이 전부 낡거나 상태 변화로 빠져 **지금 살아서 잡는 것이 0**이었다
(레드팀 33회차 B3). 240차 가드(정리표 = 본문 대기 항목)를 **현재 상태**로 다시 잰다. 원 스크립트는 당시 기록이라 그대로 둔다.
실행: python mutations/run_all.py 240
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '240cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
L = '근거_결정대기대장_20260915.md'
raw = open(L, 'rb').read(); s = raw.decode('utf-8')
row14 = next(l for l in s.splitlines(True) if l.startswith('| D-14 | 비닐 7종'))
M = [
 ("M1 정리표에서 열린 D-14 행 삭제", row14, ''),
 ("M2 닫힌 D-12를 본문에서 다시 열기", '| ~~**D-12**~~ ✅**닫힘(243차)** |', '| **D-12** |'),
 ("M3 정리표에 닫힌 D-7 행 되살림", row14, row14 + '| D-7 | C3 면적 | ⓐ ⓑ | — | — | — |\n'),
]
for n, a, b in M:
    if s.count(a) < 1: print("적용불가", n); continue
    open(L, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(L, 'wb').write(raw)
assert run() == 0
